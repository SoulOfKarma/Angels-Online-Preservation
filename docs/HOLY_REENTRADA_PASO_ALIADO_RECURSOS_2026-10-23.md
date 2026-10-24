# Holy: revision de minas, aliados, pilares y reentrada

## Fallos corregidos

- Minas sin nombre: se enviaba000E sin su000F. Las60 minas ahora incluyen el nombre de material248..257 (Battle Mine1..10), mediante el constructor de nombres ya medido en otras zonas. La recoleccion conserva entidad, material y probabilidades originales.
- El clic en el golem entraba primero al manejador de monstruos y no alcanzaba el manejador de paso aliado. Ahora el aliado se intercepta antes de seleccionar/atacar. Para estatuas aliadas no hay accion ofensiva. El rechazo del ataque directo esta antes de cooldown, MP/SP, animacion y EXP.
- Ataques de area, explosiones/rebotes, adquisicion/objetivos de invocaciones y mascotas filtran estructuras aliadas. Se mantiene tambien la comprobacion defensiva final de Edificio.recibir, que ya impedia perder HP por aliados pero no evitaba todos los intentos/efectos ofensivos.
- Cruzar caminando el disparador de un golem propio vivo ahora usa el GOTO_TAG original: evento51 ->tag51,61 ->61,71 ->71,81 ->81, etc. Los tags ya quedan al otro lado; no se intercambian otra vez. Destruido el golem, no hay warp ni bloqueo: queda el arco abierto. Reparado con materiales, vuelven bloqueo rival y warp aliado. El cruce se atiende antes de armar portales de salida.
- El pilar azul estaba cerca de unas zonas invisibles que se habian convertido incorrectamente en salidas automaticas para cualquiera. MPC112/evento92 es disparador3 (clic), con TEAMID0, no salida por pisar para un competidor. Se retira ese viaje automatico de las12 zonas invisibles. Sus clics tampoco sacan a competidores. Los dos tornados de salida311,8 y23,284 permanecen disponibles.

## Reentrada y piedra

La transaccion de entrada existente ya consultaba la pertenencia persistida a esa ronda antes de cobrar. Las capturas revisadas muestran8537 con199 unidades antes y despues de las reentradas de las sesiones105548 y105600 del23 de octubre, sin un segundo descuento visible. No se afirma haber localizado un segundo cobro en esas capturas ni se modifican sus inventarios reales.

Se simplifica el dialogo: elegir Join estando ya registrado lleva directamente a la pagina de reentrada7611, sin repetir la confirmacion de registro. Se prueba que el registro descuenta una piedra (200 ->199) y que las reentradas durante registro, combate y tras recargar la ronda de SQLite mantienen199, mismo equipo y mismo ID de ronda. No requiere conservar otra piedra en la bolsa. Una ronda nueva no hereda gratuitamente la admision anterior y una ronda acabada no admite reentrada.

## Validacion

Pruebas focalizadas iniciales:38 aprobadas. `tools/test_holy_walk_reentry_allies.py` cubre60 nombres, los cuatro cruces de ambos equipos/ambos lados, destruccion y reparacion, zonas del pilar azul sin salida automatica, ataques basicos/hechizos a golem y estatua aliados por el router real sin MP/SP/CD/animacion, clic aliado sin ataque y reentrada persistida por el Clerk.

No se reinicio el servidor ni se editaron cuentas/rondas reales. Requiere reiniciar para cargar los cambios y comprobar recorrido y nombres en el cliente. No es una certificacion de todas las mecanicas de Holy.

Bateria ampliada final:404 pruebas aprobadas en92,59s; dos advertencias preexistentes de asyncio. Compilacion de los modulos modificados y git diff --check sin errores.

## Canal de equipo fuera de Holy

Revision posterior: el router0133 difundia globalmente por0139 cuando el emisor estaba fuera de112. Se elimina esa alternativa: tanto0133 como hbteam pasan por chat_equipo. Solo se permite en fase combate, dentro de112, con pertenencia a la ronda y no espectador. Registro, cierre, lobby y ausencia de ronda no emiten0139. El mensaje llega solo a companeros registrados del mismo equipo y mapa. No se modifica el cuadro de entrada del cliente: el bloqueo es autoritativo del servidor.

Validacion de esta revision:46 pruebas de Holy/chat aprobadas, compilacion y diff-check sin errores. Al ampliar tambien a test_house_system se observaron cinco fallos en expectativas de jabones, otros canales/GM y captura de mascotas; no se modificaron esos comportamientos en este cambio. No confundir esos resultados con una suite general completamente aprobada.

## Afinado del salto y avisos de cristal

Revision posterior a las capturas del golem: el cruce aun llamaba a CHANGE_MAP incluso con destino112. Ahora `salto` usa la recolocacion0003 del mismo mapa, conservando sesion, auras, invocaciones, HP/MP/SP y musica. Emite el efecto45 del hechizo1640, cuyo nombre XML es Swiftness Spell for Holy Battlefield. Replica posicion/efecto a observadores sin presencia.entrar ni despawns de escena. Se usa tambien en pasos de luz y Alex, todos internos a Holy.

El clic en un golem aliado no ataca ni teletransporta. Se activa caminando por la zona trasera (punto de llegada original o zona de un tile alrededor de dos tiles hacia afuera del guardia), ademas del disparador MPC original. El destino sigue siendo el tag original del otro lado. La llegada queda protegida contra rebote hasta abandonar su zona. Un golem destruido no activa salto; reconstruido lo recupera. La geometria de la zona trasera es un ajuste del servidor a las capturas, no un area exacta recuperada del servidor oficial.

El spawn de las parejas de guardianes fija diagonales opuestas segun el eje de su puerta, tambien tras reparar/publicar:1/5 en arcos normales y3/7 en los reflejados. Se fija wire+35 explicitamente porque `_npc_spawn` ignoraba `direccion` para klass1. Falta verificar visualmente los frames concretos del sprite del cliente, aunque los paquetes estan comprobados.

Al recoger el cristal enemigo se emite una sola banderola nativa0128/canal13 con autor del personaje y texto I have obtained Gabriel's Crystal! o Raphael's Crystal!. Tras entregar no se emite ni Super BC ni la franja Holy Battlefield:team1...: se actualiza013B y se retira el cristal. La victoria final sigue anunciando el cierre del evento. Destruir una estatua genera la banderola con su numero real restante y Rebirth area back., sin inventar25 estatuas iniciales.

Nuevas pruebas: `tools/test_holy_local_blink_notices.py` comprueba los dos equipos/ambos lados sin carga de mapa,0003 y1640, replica a observadores, ausencia de rebote, un paquete de movimiento real como el de la captura239,225, orientaciones opuestas de las20 parejas, recogida anunciada una sola vez, entrega sin anuncio y aviso de estatuas con contador real. Sigue pendiente la comprobacion visual en el cliente tras reiniciar.

Resultado de esta bateria ampliada:414 pruebas aprobadas en124,54s, dos advertencias preexistentes de asyncio. Compilacion y diff-check sin errores. No se reiniciaron procesos ni se modificaron inventarios reales.

## Aviso final y cuenta regresiva

El cierre de Holy usa la franja superior con el texto original de string.xml2147: The Holy Battlefield event ends now. Congratulations! %s won the event. Equipo1 corresponde a Jabaly y equipo2 a Raphael. En empate solo aparece The Holy Battlefield event ends now. Una cancelacion GM tampoco declara ganador. Se elimina del cierre publico de Holy el diagnostico Results saved y el motivo interno; Angel Arena conserva su comportamiento anterior.

La cuenta regresiva por chat usa string.xml2180: The event has now ended. You will be teleported out of the arena in %s seconds. Conserva los diez segundos, emite de10 a0 con ticks regulares y retorna a Sign-up Office. Reconectar no reinicia el plazo original. No se alteran los premios ni se agrega una afirmacion de recompensa a jugadores no elegibles. Los textos se comprobaron en los XML locales; queda pendiente su comprobacion visual con el cliente y el servidor reiniciado.

Validacion de esta revision:142 pruebas aprobadas en81,95s, incluyendo ambos ganadores, dos empates, cancelacion sin ganador, aviso idempotente, retorno10..0 y reconexion conservando plazo. Compilacion y git diff --check sin errores (solo advertencias de finales de linea en archivos previos). No se reinicio el servidor ni se modificaron cuentas reales.
