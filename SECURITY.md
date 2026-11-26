# Seguridad y datos

- Herramienta local sin red, telemetría, cuentas, secretos ni conectores activos.
- Los archivos son datos. No se ejecutan scripts, SQL, expresiones, rutas ni URLs que contengan.
- Lector máximo 1 MiB; IDs y estados acotados; JSON con claves repetidas rechazado.
- SVG generado con escape de texto y sin recursos remotos.
- No importar contraseñas, cookies, tickets ni exportaciones con datos personales de jugadores.
- Usar archivos de confianza. Las cotas limitan entradas normales pero no constituyen auditoría formal ni aislamiento para entradas hostiles.
- Cualquier futuro adaptador requiere permisos acotados y rechazo de acciones por defecto. No dar consola, RCON amplio ni base de datos libre a un modelo.
- El esquema geométrico no valida física o permisos de un hotel. Su informe siempre impide aplicar.

Para comunicar un defecto, incluir versión y caso mínimo sin secretos. Canal de reporte del repositorio pendiente de definir antes de publicar.

La UI opt-in abre un servidor HTTP sólo en 127.0.0.1. Rechaza Host ajeno y exige Origin local más token de sesión para operaciones POST. No habilita CORS, LAN, TLS ni exposición remota; no debe publicarse mediante túnel. Los endpoints procesan únicamente modelos locales. La imagen de referencia se muestra mediante una URL blob del navegador sin subir sus bytes.

El editor del navegador usa JSON.parse: claves duplicadas pueden normalizarse antes de enviarlas. El lector CLI sí las rechaza. No tratar el editor web como analizador forense del JSON original. Se requiere revisión adicional de disponibilidad/concurrencia y entradas hostiles antes de exponerlo a usuarios no confiables.
