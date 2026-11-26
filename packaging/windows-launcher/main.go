// Launcher de WIRED Workbench: extrae un runtime embebido (Python oficial + app)
// a una carpeta por version y lo ejecuta. No se conecta a ninguna red.
package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
)

const version = "0.1.0-dev"

func dataRoot() (string, error) {
	if v := os.Getenv("WIRED_HOME"); v != "" {
		return v, nil
	}
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		d, err := os.UserCacheDir()
		if err != nil {
			return "", err
		}
		base = d
	}
	return filepath.Join(base, "WiredWorkbench"), nil
}

func main() {
	args := os.Args[1:]
	if len(args) == 1 && args[0] == "--launcher-info" {
		root, _ := dataRoot()
		fmt.Printf("wired launcher %s\npayload sha256: %s\nraiz: %s\n", version, payloadHash(payload), root)
		return
	}
	if len(args) == 1 && args[0] == "--third-party-notices" {
		fmt.Print(notices)
		return
	}
	root, err := dataRoot()
	if err != nil {
		fatal(err)
	}
	rt, err := ensureRuntime(root, payload)
	if err != nil {
		fatal(err)
	}
	var cmdArgs []string
	if len(args) == 0 {
		cmdArgs = []string{"-m", "wired_workbench.ui"}
	} else {
		cmdArgs = append([]string{"-m", "wired_workbench"}, args...)
	}
	cmd := exec.Command(filepath.Join(rt, "py", "python.exe"), cmdArgs...)
	cmd.Env = append(os.Environ(), "PYTHONDONTWRITEBYTECODE=1")
	cmd.Stdin, cmd.Stdout, cmd.Stderr = os.Stdin, os.Stdout, os.Stderr
	if err := cmd.Run(); err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			os.Exit(ee.ExitCode())
		}
		fatal(err)
	}
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, "wired launcher:", err)
	os.Exit(1)
}
