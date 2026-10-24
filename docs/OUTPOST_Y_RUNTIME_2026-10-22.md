# Outpost, viajes y NPC (2026-10-22)

Correccion posterior del retorno por Superwing:
[carrera de carga Outpost -> Lyceum](CRASH_OUTPOST_LYCEUM_SUPERWING_2026-10-22.md).
La proteccion ahora incluye todas las emisiones de mundo durante carga,
no solamente solicitudes de movimiento/casteo y el bucle de IA.

## Alcance

- Outpost Battlefield 47/48: PvP permanente, sin depender del horario de Totem War. Se conservan las protecciones de faccion y liga; no concede bajas ni creditos de Totem War.
- 16 portales por mapa recuperados de map047/map048.mpc. Eventos 901..904: retorno a la base de la faccion correspondiente; 905: llegada aleatoria entre las 24 casillas originales; 906: ciudad de la faccion. Sentinel Angel utiliza el arbol original 6200 y sus requisitos de nivel/faccion.
- Director Wolay: sprite 40049 (npc1549), dialogo propio sin sustitucion por otro arbol. La opcion 5080 muestra la segunda respuesta 5082; el viaje queda pendiente hasta cerrarla, nunca al seleccionar la primera opcion.
- Parametros de nombre: parejas indice/valor, despues de opciones y acciones. SET_PLAYERNAME (accion 2) se interpreta por mensaje, no solo para Census. Las misiones incluyen el indice del parametro.

## Cruce Angel House Area 370 -> Lyceum 41

El registro mostraba movimiento y Lotus Armor del mapa antiguo entre CHANGE_MAP y el aviso de mapa cargado. Antes, el control de coordenadas antiguas se ejecutaba despues de enviar ACK/MOVE. Ahora se bloquean acciones de mundo durante la carga y se rechaza el movimiento viejo antes de emitir paquetes, incluso con ruta vacia. No se cambio la llegada medida (158,82).

Esto elimina una carrera observada en el servidor. La confirmacion definitiva del cierre del cliente requiere repetir el cruce en el juego.

## Invocaciones y dano PvP

La IA PvE se conserva. El nuevo modulo invocaciones_pvp selecciona rivales usando los mismos permisos de PvP (sala, faccion, liga, vida y evento), alcance, linea de vision y desplazamiento transitable. Usa ataque propio de la invocacion, defensa fisica/magica del rival y mitigacion de equipo/buffs; no vuelve a sumar equipo del dueno. La animacion sale de la entidad de la invocacion, mientras que la autoria pertenece al dueno. Se respeta cadencia y no_jugadores. No se modifico el planificador de combos del jugador.

Al salir se retiran ambas invocaciones de las pantallas del mapa viejo. Los viajes conservan sus datos para reaparecer; desconectar los elimina y cancela la tarea de IA. El reinicio diferido de IA tambien comprueba la desconexion. No se reaparecen invocaciones muertas o vencidas.

Se comprobo por regresion la formula existente: defensa antes del multiplicador y mitigacion una vez. No se afirma equivalencia exacta con una formula oficial no recuperada ni se hizo un rebalanceo arbitrario.

## Verificacion

`python -m pytest tools/test_outpost_runtime.py tools/test_competition_npc_basics.py tools/test_competiciones.py tools/test_holy_battlefield.py tools/test_supreme_display.py tools/test_aliua_skill_slots.py tools/test_ligas_regresiones_mundo.py tools/test_totem_war.py tools/test_instancias_mecanicas.py -q -p no:cacheprovider`

Reiniciar el proceso del servidor para cargar Python/plantillas y reconectar los clientes. Prueba manual pendiente: Angel House -> Lyceum, Wolay 5079 -> 5082 -> cierre, portales de cada faccion y combate de invocaciones con dos clientes; desconectar al dueno y comprobar la desaparicion desde el otro cliente.

Angel Arena/Holy Battlefield permanecen fuera de este arreglo prioritario; no se habilitaron premios inventados ni se declaran completos.
