# WIRED Workbench

Herramientas locales, sin dependencias, para diseñar, explicar y validar modelos WIRED y para planear una sala a partir de una imagen. Pensado para Habbogz y Habbo.es. Estado: 0.1.0-dev.

## Qué hace hoy
- Modelo WIRED abstracto: causante, condición, selector, efecto, complemento y variable. Comandos `catalog`, `plan`, `validate`, `explain`, `simulate` con recetas (interruptor-lámpara, puerta de presión, mensaje por palabra clave).
- Planos de sala de vista superior: `layout-check` y `layout-svg` validan piezas, tamaños, límites y superposiciones.
- Imagen a plano: `image-plan imagen.png especificacion.json` convierte un PNG (8 bits) o PPM en un plano. Usted declara los tipos (color) y las piezas que tiene; la herramienta asigna cada pieza a una celda, informa cuántas faltan y no inventa muebles. Solo piezas 1x1 en vista superior.
- Interfaz local (`python -m wired_workbench.ui`) en 127.0.0.1, sin red externa.
- Ejecutor nativo opcional (`native-classic-apply`, `native-duck-discover`): configura cajas WIRED a través de un ejecutor local que usted elige y comprueba con reapertura. El repositorio incluye clientes genéricos (`ui_executor`, `browser_driver`, `native`, `duck_planner`, `role_selector`) que fallan cerrado: sin identidad y dueño verificados no escriben. No incluye ningún perfil ni conector verificado para hoteles reales ni para Habbogz o Habbo.es; hace falta aportar uno y una sala propia de prueba. Usar automatización contra un hotel oficial puede infringir sus términos de servicio.

## Qué no hace
No coloca, compra ni mueve muebles. No lee inventarios reales por sí solo. No garantiza compatibilidad con ninguna versión de Habbo ni con Habbo.es. Sin integración certificada: los planes son abstractos (`canApply: false`).

## Uso
Python 3.10 o superior. El paquete `packaging/windows-launcher` arma un `wired.exe` que lleva Python embebido (lanzador, no compilación nativa del Python; sin verificar aún en Windows). La automatización de navegador (`browser_driver`) usa Playwright, dependencia opcional que no se instala por defecto.

    python -m wired_workbench image-plan examples/corazon.png examples/corazon-spec.json --layout-out plan.json
    python -m wired_workbench layout-svg plan.json > plan.svg
    python -m unittest discover -s tests

## Licencia
Sin licencia concedida por ahora. Hasta que el titular decida, no se otorgan derechos de uso, copia ni redistribución más allá de lo que permita la plataforma donde se aloje. El nombre WiredWorkbench es provisional.
