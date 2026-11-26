//go:build nopayload

package main

import (
	"archive/zip"
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func mkzip(t *testing.T, files map[string]string) []byte {
	var b bytes.Buffer
	w := zip.NewWriter(&b)
	for n, c := range files {
		f, err := w.Create(n)
		if err != nil {
			t.Fatal(err)
		}
		f.Write([]byte(c))
	}
	w.Close()
	return b.Bytes()
}

func TestExtractAndReuse(t *testing.T) {
	root := t.TempDir()
	p := mkzip(t, map[string]string{"py/python.exe": "x", "app/a.py": "1", "examples/e.json": "{}"})
	d, err := ensureRuntime(root, p)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(d, "app", "a.py")); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(d, payloadHash(p)[:12]) {
		t.Fatal("directorio no versionado por hash")
	}
	// reutiliza sin reescribir
	st1, _ := os.Stat(filepath.Join(d, "app", "a.py"))
	d2, err := ensureRuntime(root, p)
	if err != nil || d2 != d {
		t.Fatal("no reutilizo", err)
	}
	st2, _ := os.Stat(filepath.Join(d, "app", "a.py"))
	if !st1.ModTime().Equal(st2.ModTime()) {
		t.Fatal("reescribio archivos")
	}
}

func TestVersionIsolationAndUserDataUntouched(t *testing.T) {
	root := t.TempDir()
	os.MkdirAll(filepath.Join(root, "data"), 0o700)
	user := filepath.Join(root, "data", "mi-sala.json")
	os.WriteFile(user, []byte("mio"), 0o600)
	p1 := mkzip(t, map[string]string{"py/python.exe": "1"})
	p2 := mkzip(t, map[string]string{"py/python.exe": "2"})
	d1, err1 := ensureRuntime(root, p1)
	d2, err2 := ensureRuntime(root, p2)
	if err1 != nil || err2 != nil || d1 == d2 {
		t.Fatal("versiones no aisladas", err1, err2)
	}
	b, _ := os.ReadFile(filepath.Join(d1, "py", "python.exe"))
	if string(b) != "1" {
		t.Fatal("version 1 alterada por version 2")
	}
	if b, _ := os.ReadFile(user); string(b) != "mio" {
		t.Fatal("datos del usuario alterados")
	}
}

func TestRejectsUnsafeEntries(t *testing.T) {
	for _, name := range []string{"../evil", "a/../../evil", "/abs", "C:/x", "a\\b", "..", "x/../.."} {
		root := t.TempDir()
		_, err := ensureRuntime(root, mkzip(t, map[string]string{name: "x"}))
		if err == nil {
			t.Fatalf("acepto %q", name)
		}
		// nada escapa ni queda a medias
		ents, _ := os.ReadDir(filepath.Join(root, "runtime"))
		for _, e := range ents {
			t.Fatalf("quedo residuo %s para %q", e.Name(), name)
		}
		if _, err := os.Stat(filepath.Join(filepath.Dir(root), "evil")); err == nil {
			t.Fatal("escribio fuera")
		}
	}
}

func TestRefusesToOverwriteForeignDir(t *testing.T) {
	root := t.TempDir()
	p := mkzip(t, map[string]string{"py/python.exe": "1"})
	d := filepath.Join(root, "runtime", payloadHash(p)[:12])
	os.MkdirAll(d, 0o700)
	os.WriteFile(filepath.Join(d, "algo"), []byte("ajeno"), 0o600)
	if _, err := ensureRuntime(root, p); err == nil {
		t.Fatal("sobreescribio carpeta sin marcador")
	}
	if b, _ := os.ReadFile(filepath.Join(d, "algo")); string(b) != "ajeno" {
		t.Fatal("altero contenido")
	}
}

func TestRejectsTamperedMarker(t *testing.T) {
	root := t.TempDir()
	p := mkzip(t, map[string]string{"py/python.exe": "1"})
	d, _ := ensureRuntime(root, p)
	os.WriteFile(filepath.Join(d, okMarker), []byte("otro\n"), 0o600)
	if _, err := ensureRuntime(root, p); err == nil {
		t.Fatal("acepto marcador alterado")
	}
}

func TestEmptyPayload(t *testing.T) {
	if _, err := ensureRuntime(t.TempDir(), nil); err == nil {
		t.Fatal("acepto payload vacio")
	}
}

func TestSizeCap(t *testing.T) {
	root := t.TempDir()
	big := strings.Repeat("a", 1<<20)
	files := map[string]string{}
	for i := 0; i < 5; i++ {
		files["f"+string(rune('a'+i))] = big
	}
	if _, err := ensureRuntime(root, mkzip(t, files)); err != nil {
		t.Fatal(err) // dentro del tope
	}
}
