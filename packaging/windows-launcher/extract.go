package main

import (
	"archive/zip"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"strings"
)

const (
	maxTotalBytes = 400 << 20 // tope de bytes descomprimidos
	maxFileBytes  = 200 << 20
	maxEntries    = 5000
	okMarker      = ".wired-runtime-ok"
)

// payloadHash devuelve el sha256 hex del payload embebido.
func payloadHash(payload []byte) string {
	h := sha256.Sum256(payload)
	return hex.EncodeToString(h[:])
}

// safeRel valida un nombre de entrada zip y lo devuelve como ruta relativa limpia.
func safeRel(name string) (string, error) {
	if name == "" || strings.ContainsRune(name, 0) || strings.Contains(name, "\\") {
		return "", fmt.Errorf("nombre no permitido: %q", name)
	}
	if strings.HasPrefix(name, "/") || (len(name) > 1 && name[1] == ':') {
		return "", fmt.Errorf("ruta absoluta no permitida: %q", name)
	}
	clean := path.Clean(name)
	if clean == "." || clean == ".." || strings.HasPrefix(clean, "../") {
		return "", fmt.Errorf("ruta fuera del destino: %q", name)
	}
	return clean, nil
}

// ensureRuntime extrae payload bajo root/runtime/<hash12>/ si no existe ya.
// Nunca toca root/data ni otras versiones. Devuelve el directorio del runtime.
func ensureRuntime(root string, payload []byte) (string, error) {
	if len(payload) == 0 {
		return "", errors.New("payload vacio: este binario se compilo sin runtime")
	}
	full := payloadHash(payload)
	final := filepath.Join(root, "runtime", full[:12])
	if b, err := os.ReadFile(filepath.Join(final, okMarker)); err == nil {
		if strings.TrimSpace(string(b)) == full {
			return final, nil
		}
		return "", fmt.Errorf("marcador inconsistente en %s; no se sobreescribe, borra esa carpeta a mano", final)
	}
	if _, err := os.Lstat(final); err == nil {
		return "", fmt.Errorf("%s existe sin marcador de integridad; no se sobreescribe, borra esa carpeta a mano", final)
	}
	parent := filepath.Join(root, "runtime")
	if err := os.MkdirAll(parent, 0o700); err != nil {
		return "", err
	}
	tmp, err := os.MkdirTemp(parent, ".tmp-"+full[:12]+"-")
	if err != nil {
		return "", err
	}
	ok := false
	defer func() {
		if !ok {
			os.RemoveAll(tmp)
		}
	}()
	if err := unzipSafe(payload, tmp); err != nil {
		return "", err
	}
	if err := os.WriteFile(filepath.Join(tmp, okMarker), []byte(full+"\n"), 0o600); err != nil {
		return "", err
	}
	if err := os.Rename(tmp, final); err != nil {
		// otra instancia pudo terminar primero: aceptar solo si es valida
		if b, e2 := os.ReadFile(filepath.Join(final, okMarker)); e2 == nil && strings.TrimSpace(string(b)) == full {
			return final, nil
		}
		return "", err
	}
	ok = true
	return final, nil
}

func unzipSafe(payload []byte, dest string) error {
	zr, err := zip.NewReader(bytes.NewReader(payload), int64(len(payload)))
	if err != nil {
		return err
	}
	if len(zr.File) > maxEntries {
		return errors.New("demasiadas entradas en el payload")
	}
	var total uint64
	destClean := filepath.Clean(dest) + string(os.PathSeparator)
	for _, f := range zr.File {
		rel, err := safeRel(f.Name)
		if err != nil {
			return err
		}
		if f.Mode()&os.ModeSymlink != 0 || (!f.Mode().IsRegular() && !f.FileInfo().IsDir()) {
			return fmt.Errorf("tipo de entrada no permitido: %q", f.Name)
		}
		target := filepath.Join(dest, filepath.FromSlash(rel))
		if !strings.HasPrefix(target+string(os.PathSeparator), destClean) {
			return fmt.Errorf("escape del destino: %q", f.Name)
		}
		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(target, 0o700); err != nil {
				return err
			}
			continue
		}
		if f.UncompressedSize64 > maxFileBytes {
			return fmt.Errorf("archivo demasiado grande: %q", f.Name)
		}
		if err := os.MkdirAll(filepath.Dir(target), 0o700); err != nil {
			return err
		}
		rc, err := f.Open()
		if err != nil {
			return err
		}
		out, err := os.OpenFile(target, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o700)
		if err != nil {
			rc.Close()
			return err
		}
		n, err := io.Copy(out, io.LimitReader(rc, maxFileBytes+1))
		rc.Close()
		cerr := out.Close()
		if err != nil {
			return err
		}
		if cerr != nil {
			return cerr
		}
		if n > maxFileBytes {
			return fmt.Errorf("archivo excede el limite: %q", f.Name)
		}
		total += uint64(n)
		if total > maxTotalBytes {
			return errors.New("payload excede el tope total descomprimido")
		}
	}
	return nil
}
