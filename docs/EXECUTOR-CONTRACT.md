# Contrato del ejecutor `hgz-classic-editor/1`

WIRED Workbench no se conecta a ningún hotel. El comando `native-classic-apply` y `native-duck-discover` hablan con un **ejecutor local que usted aporta**, lanzado como lista explícita de argumentos (sin shell). Este documento describe lo que el ejecutor debe cumplir. No se incluye ningún ejecutor.

## Transporte
- Proceso hijo; una petición JSON por línea en stdin, una respuesta JSON por línea en stdout (UTF-8, `\n`).
- Petición: `{"protocol":"hgz-classic-editor/1","request_id":N,"action":"...","room_id":R, ...}` (máx. 64 KiB).
- Respuesta: mismo `protocol`, `request_id` y `room_id`, y `"ok": true`. Cualquier otra cosa (identidad distinta, ok falso, tiempo agotado a 30 s, cierre del proceso, más de 1 MiB) detiene el flujo sin reintentar.
- Las claves JSON duplicadas se rechazan.

## Acciones
- `inspect_room`: devuelve `room_id`, `owner_id`, `room_state`, `private_acceptance_room` (true) e `items` (cada uno con `id`, `base_id`, `position:[x,y,z]`). Sin escrituras.
- `read_box` (`box_id`, `role`): devuelve `settings` y `observed_via: "reopened_native_editor"`. La lectura debe salir de reabrir el editor nativo, no de un acuse de guardado.
- `configure_box` (`box_id`, `role`, `native`): aplica la configuración. Un acuse o clic no cuenta como persistencia.
- `stop`: cierre cooperativo al terminar. El ejecutor debe cerrar sus sesiones y borrar sus credenciales temporales.

## Qué hace el cliente antes de escribir
Exige un manifiesto con sala privada de pruebas, dueño exacto, `room_state` oculto, inventario exacto con ids reales y cuatro cajas distintas (repeat, chase, collision, teleport). Hace una inspección nueva antes de cada escritura y compara inventario; si algo cambió, se detiene. Toma una línea base de las cuatro cajas antes de escribir y comprueba cada resultado por reapertura. El informe distingue configuración verificada de juego verificado: el juego no lo prueba este programa.

## Límites
Esto solo cubre configurar editores WIRED clásicos en una sala privada de aceptación. No crea salas, no compra ni coloca muebles, no lee permisos generales. Compatibilidad con cada hotel depende de su ejecutor.

## Ejecutor genérico incluido (`wired_workbench/ui_executor.py`)
Habla este protocolo sobre un "driver". Se incluye `SimDriver`, un clon sintético en un archivo JSON, para pruebas y demos; no se conecta a ninguna red ni hotel. Un driver de navegador real tendría que implementarse aparte.
- Un driver solo puede escribir si declara `identity_verified` y la inspección trae dueño numérico, sala privada y estado `hide`. Una declaración del operador no cuenta.
- Un cliente real solo muestra nombres, no el id del dueño ni el estado del servidor: con `--unverified` (lo que ofrecería un driver de UI) la inspección omite esos datos y **ninguna escritura se emite**. En ese caso solo hay lectura y la configuración debe hacerse a mano.
- Escrituras perdidas se detectan por la lectura tras reapertura. `--scope-room` rechaza otra sala.
- Pruebas: configuración y readback sobre el clon, driver sin identidad, escritura perdida, dueño/estado equivocado, sala fuera de alcance.

## Driver de navegador (`wired_workbench/browser_driver.py`, dependencia opcional: Playwright)
`python -m wired_workbench.ui_executor --browser-url URL [--chrome-path RUTA]` opera la página con Playwright: lee los elementos de objetos, abre el editor de una caja, lee o rellena sus campos, pulsa Guardar y Cerrar. Los selectores se pueden cambiar con un perfil. No inicia sesión, no guarda credenciales y no abre direcciones por su cuenta: usted pasa la URL.
- **Identidad:** un cliente normal no expone el id numérico del dueño ni el estado real de la sala. Una página que expone un objeto JS no es fuente de identidad por sí sola. Hace falta las dos cosas: el gancho `window.__wiredIdentity` y que la URL empiece por un prefijo que el operador declare con `--trust-origin` (clon de prueba propio). Sin ambas el driver lee pero no escribe, y el id de sala del gancho debe coincidir con el de la página. Sin `--trust-origin` nunca hay identidad verificada.
- **Fixture:** `tests/fixtures/sim_client.html` es una página local que simula un editor; no es Habbogz ni Habbo.es y no demuestra compatibilidad con ningún cliente real. Pruebas: configuración y reapertura por los diálogos reales, página sin gancho (lee, no escribe), guardado perdido, sala abierta, campo inexistente.
- **Límites que requieren intervención manual:** selectores y formato de valores de un cliente real, que hay que escribir y comprobar por cliente; campos sin id estable; inventario real (no hay lectura de ids por UI).
- Antes de usarlo contra un hotel oficial, revise sus condiciones: prohíben el software de automatización no autorizado que dé ventaja injusta o interfiera con el servicio.
