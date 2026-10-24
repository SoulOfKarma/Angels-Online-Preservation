# Retorno Outpost -> Lyceum: carrera de carga por Superwing

## Evidencia observada

Reporte de Karma: pantalla negra y cierre al volver desde Outpost Battlefield
(48, posicion 198,102) al Angel Lyceum. El registro muestra Angels GO! destino
1, Superwing de la casilla 23, a las 17:48:15 del 22/10/2026, no el tornado
de salida por faccion.

La grabacion `127_0_0_1_16769_20261022_174808_orden.jsonl` muestra:

| Tiempo relativo | Mensaje |
| --- | --- |
| 6.7118 | S2C 0x000C: cargar stage 41 |
| 6.7501 | S2C efectos/atributos de buff, HP/MP, stats y EXP de skill |
| 6.7501 | C2S 0x0006: Holy Soul Shield IV |
| 6.8679 | Mas efectos/stats de la habilidad |
| 6.8694 | Movimientos de monstruos de Lyceum antes de finalizar la secuencia |

El log confirma que Holy Soul Shield IV se ejecuto despues de la orden de
viaje y antes de REQ_0009. Angels GO! escribia stage/posicion directamente y
no activaba `mapa_cargando`: el guard de entrada y la pausa de IA no aplicaban.
Ademas, los temporizadores de buffs y los mensajes de otras sesiones podian
emitir paquetes aunque el recorrido del viaje si hubiera activado el guard.
Es una secuencia insegura observada, no una direccion de excepcion recuperada
del cliente. La confirmacion final del cierre requiere repetir el cruce en juego.

## Correccion

- Angels GO! entre mapas usa `_sincronizar_cambio_mapa`, cancela cualquier
  tornado pendiente y activa la proteccion comun. Mantiene el orden medido de
  cierre/inventario/stats/despawn anterior al CHANGE_MAP y consume una Superwing.
- Un salto al mismo mapa sigue siendo 0x0003, sin recargar ni bloquear el cliente.
- `Session.enviar` y `enviar_sin_espejo` activan la barrera al ver cualquier
  CHANGE_MAP de mundo: protege tambien recorridos antiguos que envian 0x000C
  directamente. El servicio de login no interpreta sus paquetes como viajes.
- Durante la carga no se transmiten entidades, movimientos, golpes, animaciones
  ni snapshots de stats. La secuencia de REQ_0009 los reconstruye a partir del
  estado actual; no se reproducen despues efectos viejos.
- Deltas de inventario y avisos/chat se difieren hasta DESPUES de la ficha y la
  secuencia nueva. La cola esta acotada a 256 mensajes; no retiene un backlog
  ilimitado si el cliente nunca confirma la carga.
- El guard de solicitudes incluye uso de objetos y un segundo Angels GO!,
  evitando doble viaje/doble consumo mientras se carga.
- `enviar_inmediato` tambien pasa por el filtro. Los buffs siguen actualizando
  el estado del servidor, sin lanzar paquetes a una escena aun no preparada.

## Verificacion y despliegue

`tools/test_map_loading.py`: retorno 48 -> 41, consumo unico, cancelacion del
tornado, salto local, secuencia real del handler REQ_0009, temporizadores,
envio inmediato, mensajes reenviados, UI diferida y separacion del login.

No se cambiaron las coordenadas de llegada ni se editaron datos de personajes.
Reiniciar el servidor y reconectar para cargar Python. Probar la Superwing
desde Outpost con auto-buffs activos y comprobar llegada/seguimiento desde
otro cliente. Esta validacion visual no se realizo desde las herramientas.
