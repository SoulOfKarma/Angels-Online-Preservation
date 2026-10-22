# Buffs de recursos y paredes — 2026-10-21

## Problemas corregidos

El servidor asignaba el HP/MP actual al nuevo maximo al aplicar ciertos
buffs. Aumentar la capacidad no implica recuperar recursos: ahora conserva
el valor actual (descontando el coste del lanzamiento), y solo lo recorta
si supera el limite. Esto cubre autocast, buffs a otro jugador y buffs de
pet; se eliminan tambien los numeros de curacion ficticios del bonus maximo.
Las curaciones explicitas, pociones y recuperaciones por nivel no se cambian.

Ademas, la formula 65 se interpretaba siempre como una marca ofensiva.
Los wrappers beneficiosos sobre uno mismo ahora seleccionan su efecto hijo;
Ember Brand y Holy Brand conservan su clasificacion ofensiva.

## Evidencia local

Fuente: `extracted_paks/update26/setting/eng/magic.xml` y su lector en
`server/combate.py`. Valores del rango V:

| Skill | Efecto relevante | Coste MP |
| --- | --- | --- |
| Third Spirit (15105) | +10000 HP y MP maximos, 300 s | 5100 |
| Sage Aura (13369) | +8000 MP maximos, 15 s; conserva sus otros bonos | 6250 |
| Charming Blessing (270) | +326 MP maximos, 2400 s | 108 |
| Mental Stimulation (15602) | Base 15657: +8590 MP maximos; reutilizacion con base activa: 15662, +859 MP cada 2 s | 8742 |
| Thoughtless Regeneration (16376) | Base 16538: +3010 MDEF; reutilizacion con base activa: 16543, +1524 HP cada 2 s, parametro de probabilidad 90 | 9487 |

La seleccion de hijos usa los parametros 1/2/3 del XML y mantiene el coste
y cooldown del padre. El efecto base puede coexistir con la regeneracion.
Si la tirada no activa el efecto adicional se aplica el base. Esta ultima
conducta de refresco no se ha contrastado con una captura oficial ni REA.
No se declara validada aqui la mecanica completa de negacion de efectos de
Thoughtless Regeneration.

Los tics conservan su primer pulso inmediato y luego su intervalo XML.
Reutilizar un efecto reemplaza su temporizador anterior, sin duplicar la
regeneracion. Los callbacks no se transfieren a otro personaje/pet.
Soul Discharge V sigue recuperando explicitamente 12000 MP.

## Peril Chasm y otros mapas

`_mapa_de_paso` devolvia stage 0 (sin colisiones) cuando el punto de spawn
del monstruo caia en una casilla bloqueada. Esto habilitaba atravesar todas
las paredes, no solo salir del spawn. Se elimina esa deduccion de vuelo o
noclip: caminar, perseguir y volver usan el stage real.

Comprobacion de solo lectura: la mascara de stage 339 coincide exactamente
con `extracted_paks/update25/map/map339.mpc`. Hay 395 mapas con mascara.
Los MPC locales sin mascara son 501, 901, 905, 908 y 997; no se han generado
colisiones nuevas ni se cambia el fallback de mapas desconocidos.

Limites: 43 de los 218 spawns de monstruos de Peril Chasm estan en celdas
bloqueadas. No se han desplazado automaticamente ni se inventa navegacion
especial para voladores/acuaticos. Algunos pueden quedar inmoviles si no
hay una salida transitable inmediata. La correccion evita el noclip, pero
queda revisar esos puntos y validar visualmente en el cliente.

## Pruebas

`tools/test_buff_resources_and_walls.py`: 15 pruebas, incluyendo lanzamientos
por el handler real sin levantar el servidor, maximos sin relleno,
recuperacion explicita, primer uso/reuso, cooldown del padre, no duplicacion
de tics, expiracion, cambio de personaje y conservacion de paredes.

La suite antigua `test_skills_and_buffs.py::test_stats_with_buffs` falla
por esperar critico base 6 y recibir 5; no se han modificado ese test ni
`inventario.stats` en esta correccion.

Antes de la subida se repitieron las 15 pruebas nuevas junto con las suites
de pets, inventario extendido, Aliua, clasificacion de skills y paquetes
visuales: **116 passed**. La prueba antigua indicada arriba queda fuera de
ese total; no se presenta como resuelta.

No se modifica la base de cuentas ni los datos de personajes. Reiniciar
el servidor es necesario para cargar el codigo; renovar los buffs durante
la prueba evita reutilizar efectos antiguos guardados.
