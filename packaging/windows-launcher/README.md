# Launcher de Windows para WIRED Workbench (empaquetado, sin verificar en Windows)

Un `wired.exe` en Go que lleva embebido un runtime (Python 3.12.8 oficial "embeddable" + este paquete + ejemplos).
Es un lanzador compilado con runtime embebido. No es una compilacion nativa del Python.
No se ha ejecutado en Windows todavia: solo se probo la extraccion y los chequeos en Linux.

Uso: `wired.exe` (sin argumentos) abre la UI local en 127.0.0.1. `wired.exe <comando>` ejecuta la CLI (`catalog`, `validate`, `image-plan`, ...).
`wired.exe --third-party-notices` imprime los avisos de terceros (tambien van en el payload y junto al exe, como THIRD-PARTY-NOTICES.txt). `wired.exe --launcher-info` muestra version, sha256 del payload y carpeta de trabajo, sin extraer nada.
Los ejemplos se extraen en `%LOCALAPPDATA%\WiredWorkbench\runtime\<hash12>\examples`.

Seguridad de extraccion: carpeta por version (hash del payload), extraccion a carpeta temporal y renombrado atomico,
rechazo de rutas absolutas, `..`, `\`, enlaces simbolicos y tipos raros, topes de tamano, `O_EXCL` (nunca sobreescribe),
marcador de integridad con el hash, y no toca nunca `data\` ni otras versiones. Si una carpeta de runtime existe sin
marcador valido, se niega a usarla en vez de pisarla. No hay acceso a red.

Build: `./build.sh` (bash, curl, python3, go >= 1.21). Descarga Python embebido, verifica sha256 fijado, arma el payload con fecha fija,
corre las pruebas Go y compila con `GOOS=windows`. Salida en `dist/` con sus sha256. El resultado es reproducible bit a bit
(dos builds dieron el mismo hash). El exe no esta firmado: SmartScreen o un antivirus pueden avisar.

Esto no conecta con ningun hotel. El ejecutor real para Habbogz o Habbo.es no esta incluido.

## Procedencia del Python embebido
URL: https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip
Comprobado el 24-nov-2026: (1) el MD5 de la pagina oficial de la version (https://www.python.org/downloads/release/python-3128/), 1e86b04bc7d27c5c06edf8f617e1184a, coincide con el archivo bajado;
(2) la firma OpenPGP oficial (.asc en la misma carpeta) es valida ("Good signature") con la clave FC62 4643 4870 34E5, fingerprint 7ED1 0B65 31D7 C8E1 BC29 6021 FC62 4643 4870 34E5, de Steve Dower (binarios de Windows) segun https://www.python.org/downloads/metadata/pgp/ ; la clave se obtuvo de keyserver.ubuntu.com y se cotejo con ese ID publicado, sin cadena de confianza personal.
El sha256 fijado en build.sh (8d3f33be...) sale de esa misma descarga ya verificada; python.org no publica sha256 para este archivo. No se verifico la firma Authenticode de los .exe/.dll (requiere Windows).
