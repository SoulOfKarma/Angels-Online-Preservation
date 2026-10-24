# Segunda revision: interacciones y rendimiento

Cambios en fuente; no se reiniciaron procesos ni se modificaron cuentas,
rondas reales o memoria de los clientes.

## Corregido en fuente

- Swiftness (1 segundo) y Rushing (2 segundos en grado V) ahora reciben el
  desbloqueo nativo de cooldown al vencer, protegido frente a un recast.
- El salto local manda tambien el MOVE estacionario usado por Dimension Shift.
  Un movimiento antiguo, incluso con ruta vacia, ya no pisa la llegada durante
  los primeros 750 ms. Un clic desde la llegada se acepta inmediatamente.
- Los guardianes disparan al alcanzar su area trasera, no al terminar un
  waypoint largo que pase por ella. Se conserva el filtro aliado/puerta viva.
- Cada golpe no letal conserva HP y contribucion en SQLite, pero deja de
  revisar logros de todos los participantes y reenviar toda la escena.
  La destruccion sigue actualizando puerta, pareja, puntos y logros.
- Los constructores de ambos lados devuelven un menu util despues de cada
  seleccion, con exito o rechazo. Antes el router consumia dlg_mapa y dejaba
  un cuadro visible cuyas siguientes opciones terminaban cerrandolo.
  Salir ahora cierra inmediatamente. Se mantienen distancias y equipo.

## Evidencia y limite de auras

Se verificaron las rutinas cargadas004B08B0,005FFA00,006000B0 de los tres
clientes contra G:/Angel.exe: coinciden. No se escribio en los procesos.

El render de Arena requiere modo global36 y bit alto de faccion42, faccion
1..4 y ausencia de flags de ocultacion. La consulta acotada
`tools/inspect_competition_client.py PID [...]` lee estos campos y comprueba
el indice nativo de entidades; no lee credenciales ni datos de sesion.

La primera consulta encontro los clientes fuera de combate. El usuario
inicio luego una ronda, permitiendo verificar el fallo en memoria real:

| Cliente PID | Actor local | Rival visible | Modo Arena | Bit hostil local/rival |
| --- | --- | --- | --- | --- |
| 10584 | 1007, clase1102 | 2002, clase80000102 | 1 | si / no |
| 34396 | 1005, clase1102 | 2003, clase80000102 | 1 | si / no |

Ambos rivales tenian indice de red valido, TEAMID0 y ninguna ocultacion.
La rutina virtual004ABDC0 compara la clase del actor.006000B0 requiere
clase1102 para el actor exterior del paquete: los mensajes con el actor
publico80000102 eran ignorados antes de marcar al rival. El objetivo real
va por separado en el primer DWORD de argumentos.

Correccion: `presencia.para_receptor` dirige exclusivamente long42 al actor
local de cada receptor, conservando objetivo y valor. Se aplica en todos
los envios de presencia (spawn, equipo, transformacion, mascotas y summons)
y en el snapshot directo de fase/reentrada. TEAMID y otras propiedades no
se modifican. No se simulo un equipo de Holy para dibujar un aura de Arena.

Las lecturas no modificaron los clientes. Falta cargar esta ultima correccion
en el servidor y verificar visualmente la ronda; no se reinicio sin permiso.

## Pruebas

- Nueva suite `tools/test_competition_interaction_polish.py`: 11 casos,
  incluidos los seis constructores (frente/base/estatua por cada equipo),
  cooldowns/recast, movimiento antiguo, coste por impacto y contacto de warp.
- Seleccion de siete suites de regresion: 110 aprobadas.
- Otras siete suites de regresion: 134 aprobadas (dos avisos de asyncio).
- `test_arena_native_aura_receiver.py` reproduce el rechazo de clase del
  cliente sobre los paquetes anteriores y la aceptacion de los nuevos para
  ambos receptores; comprueba tambien spawn/transform y no alterar TEAMID.
- Las pruebas automatizadas no constituyen una validacion visual en cliente.
