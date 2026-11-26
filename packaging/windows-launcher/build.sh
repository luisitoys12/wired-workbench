#!/usr/bin/env bash
# Build reproducible del launcher de Windows. Requiere: bash, curl, python3, go>=1.21, sha256sum.
# Uso: ./build.sh [ruta/al/repo]   (por defecto: dos niveles arriba de este script)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${1:-$HERE/../..}"
PY_VER=3.12.8
PY_URL="https://www.python.org/ftp/python/${PY_VER}/python-${PY_VER}-embed-amd64.zip"
PY_SHA256=8d3f33be9eb810f23c102f08475af2854e50484b8e4e06275e937be61ce3d2fb
OUT="$HERE/dist"; WORK="$HERE/.work"
rm -rf "$WORK" "$OUT"; mkdir -p "$WORK" "$OUT"
curl -fsSL -o "$WORK/py.zip" "$PY_URL"
echo "$PY_SHA256  $WORK/py.zip" | sha256sum -c -
python3 - "$WORK" "$REPO" "$HERE/payload.zip" <<'PY'
import sys, zipfile, os, io
work, repo, out = sys.argv[1:4]
SOURCE_DATE = (2026, 1, 1, 0, 0, 0)  # fecha fija: payload reproducible
entries = {}
with zipfile.ZipFile(os.path.join(work, "py.zip")) as z:
    for n in z.namelist():
        data = z.read(n)
        if n == "python312._pth":
            data = b"python312.zip\r\n.\r\n..\\app\r\nimport site\r\n"
        entries["py/" + n] = data
def add_tree(src, dst, skip=("__pycache__",)):
    for root, dirs, files in os.walk(src):
        dirs[:] = sorted(d for d in dirs if d not in skip)
        for f in sorted(files):
            if f.endswith((".pyc",)): continue
            p = os.path.join(root, f)
            entries[dst + "/" + os.path.relpath(p, src).replace(os.sep, "/")] = open(p, "rb").read()
add_tree(os.path.join(repo, "wired_workbench"), "app/wired_workbench")
add_tree(os.path.join(repo, "examples"), "examples")
for f in ("README.md", "SECURITY.md"):
    p = os.path.join(repo, f)
    if os.path.exists(p): entries[f] = open(p, "rb").read()
nt = os.path.join(os.path.dirname(out), "THIRD-PARTY-NOTICES.txt")
entries["THIRD-PARTY-NOTICES.txt"] = open(nt, "rb").read()
if os.path.isdir(os.path.join(repo, "docs")): add_tree(os.path.join(repo, "docs"), "docs")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for n in sorted(entries):
        zi = zipfile.ZipInfo(n, SOURCE_DATE); zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = 0o644 << 16
        z.writestr(zi, entries[n])
PY
( cd "$HERE" && go test -tags nopayload -count=1 ./... )
( cd "$HERE" && GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-s -w -buildid=" -o "$OUT/wired.exe" . )
cp "$HERE/THIRD-PARTY-NOTICES.txt" "$OUT/"
( cd "$OUT" && sha256sum wired.exe > wired.exe.sha256 && sha256sum "$HERE/payload.zip" > payload.zip.sha256 )
echo "OK: $OUT/wired.exe"; cat "$OUT"/*.sha256
