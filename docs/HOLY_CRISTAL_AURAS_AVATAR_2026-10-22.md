# Holy, Arena y Avatar: correcciones de runtime

Correccion posterior: ver HOLY_PUERTAS_COLORES_CRISTAL_2026-10-23.md. TEAMID120 y la identificacion de60375/60376 como puertas de luz de esta nota eran incorrectos; la revision posterior usa long38/1 (companeros scalar63) y60403/60404.

## Cambios

- Holy recoge el cristal enemigo al llegar a una casilla adyacente, sin depender de que el objeto del suelo admita clic. Rechaza muertos, espectadores, fase de registro, cristal propio en su base y doble recogida. La entrega sigue validando el angel del equipo, portador y presencia del cristal propio.
- La entrada inicial y reentrada de Holy usan los tags originales 1/2 del mapa112: naranja (32,282), azul (301,15). La resurreccion conserva la progresion de estatuas anterior; no se ha demostrado que esa progresion coincida con la version de los videos.
- Puertas y cristales originales conservan coordenadas de pixel y capa del MPC, en lugar de recentrarse por tile. Se incluyen las tres puertas de luz60375/60376 omitidas del mapa.
- Participantes y companeros reciben TEAMID120 y la marca hostil42. Arena usa modo36 y Holy62; las marcas se retiran al viajar. La faccion persistida del personaje no cambia.
- Formula29 reconoce NPC6269/6270 como clones de Avatar. Phantom Substitute se crea en un slot independiente de las otras invocaciones, con duracion XML y los47 bytes de apariencia/equipo exigidos por el cliente. Absorbe dano directo PvP y de monstruos hasta agotar su HP. Se conserva correctamente al viajar y se retira de observadores al desconectar.
- Nivel superior de Arena tomado de la curva XML actual471, extensible al actualizarla. El diagnostico TEST ROUND va al log, no al aviso publico.
- El Clerk distingue ausencia de tabla, premio ya cobrado y problemas de inventario. No se inventaron premios401+.

## Evidencia REA del cliente

Ejecutable analizado: SHA256 7c1f8cc16e2032081dc15ccc1a67de668803f62d8252ab570d1f4724c162d6e9b.

- FUN004b08b0: aura neutral Arena requiere modo activo y bit alto de faccion; sprite wnd01_w104_01.
- FUN004b0730: aura Holy deriva del TEAMID1/2.
- FUN006000b0: propiedad42 establece o limpia el bit0x80000000 del actor objetivo, sin reemplazar la faccion base.
- FUN005ff310: propiedad62 activa modo Holy.
- FUN005EC200 y FUN005EBBF0: spawn de NPC6269/6270 consume una cola adicional de47 bytes de apariencia y equipo.

## Limites pendientes

No se ha comprobado visualmente esta revision en el cliente: requiere reiniciar el servidor y probar. La configuracion inicial de diez estatuas/cuatro puertas sigue basada en la guia anterior, no se sustituyo por25/10 basandose solo en un video. La relacion de parametros de algunos bloqueos originales y la progresion de resurreccion necesitan contrastarse. La escala porcentual de estadisticas de clones es una interpretacion explicita del servidor; Ghostly Tactics, objetivos directos contra clones y todas las variantes de Avatar no estan reconstruidos. No hay tabla oficial verificada de objetos de premio para Arena401+ y no se entregan sustitutos inventados. Estas correcciones no significan que todo Holy sea una reproduccion completa del original.

## Prueba manual tras reinicio

Validacion automatizada:381 pruebas aprobadas en82,63s (dos avisos deprecados de asyncio preexistentes). Incluye recogida caminando de ambos cristales, rechazo por muerte/cristal propio, entrega idempotente, auras/marcas, spawn completo del clon, cuentas e inventarios, construccion, limites temporales y retorno. Compilacion de los modulos modificados y `git diff --check` sin errores.

Abrir registro Holy con `/hbstart 60 5` y entrar desde el Clerk (o `/hb enter`). Para Arena434 usar `/aastart 30 434 5`. Iniciar combate inmediatamente solo si se desea con `/hb begin` o `/aa begin`.

En Holy, probar ambos equipos: punto inicial, aura propia/rival, ataque dirigido, cristal enemigo, pase a aliado, muerte del portador, recuperacion del propio y entrega al angel. Verificar posiciones y bloqueo de puertas, construccion con materiales, destruccion y reapertura. Al finalizar, verificar EXP/skill EXP, cuenta10..0 y retorno a Sign-up Office. No considerar verificados los pasos visuales por las pruebas automatizadas.
