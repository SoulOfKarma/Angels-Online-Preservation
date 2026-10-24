# Holy: puertas, colores y portador del cristal

Esta revision sustituye las conclusiones incorrectas de las notas del22 de octubre sobre TEAMID120 y60375/60376. No modifica cuentas ni rondas reales, no reinicia el servidor y no certifica una prueba visual en el cliente.

## Causas confirmadas y cambios

- El codigo120 enviado en001D NO corresponde al equipo. REA005f0ef0 indexa la tabla desde4408 con entradas de16 bytes;005ffe10 esta en4668, por tanto codigo38. Su subcampo1 establece TEAMID. En NPC/mascotas se usa0013 campo63,0060d540. Se conserva el equipo durante registro, aunque los ataques solo se habilitan al comenzar. Observadores y salidas reciben0.
- Marcas de mascotas, invocaciones y clones se envian tambien despues de sus spawns para observadores que llegan tarde. Las marcas enviadas antes del spawn no bastaban.
- server.obd define60373/60382 como puerta cerrada y60374/60383 como abierta, conservando el arco. No se despawnea definitivamente el conjunto al caer un guardian: se cambia a su version abierta. Destruir uno de los dos guardianes abre la pareja. Reconstruir con Building Material8536 restaura ambos y la version cerrada. Se conserva la transaccion atomica de inventario y construccion.
-60375/60376 son los portones de madera, no luz. Al comenzar se sustituyen por60403 naranja/60404 azul, definidos en server.obd como barrera de luz. Al entrar durante registro se muestra madera; el cambio de fase actualiza a los jugadores ya presentes.
- REA005b85d0 reutiliza una entidad existente sin cambiar su sprite. Por ello una sustitucion envia primero0007 y luego000E. Esto tambien corrige el cristal del suelo que permanecia visible al capturarlo. Las puertas mantienen cache por sesion y solo se sustituyen si cambia su paquete.
- Golems aliados vivos admiten clic cercano para cruzar usando los tags originales emparejados51..60/61..70 y71..80/81..90. Rival, muerto, observador, fase de registro y clic remoto no pueden usarlos. Una puerta destruida se atraviesa por el arco abierto. Los limites de base7/8 repelen al rival y al portador, como sus disparadores originales; no se inventa un destino de warp para esos limites.
- Los mini-warps originales de los eventos3/4 se exponen como pilares60402 durante combate: zona(28,247) ->tag4(283,55), zona(287,52) ->tag3(38,246). Son distintos de los limites de base7/8. Se usan destinos y condiciones de participacion sin rellenar HP/MP; el clic remoto falla.60402 es la representacion de luz elegida del mismo cliente para hacer accesible el disparador invisible60384; no es un spawn de servidor oficial capturado.
- XML3141 dice que la velocidad vuelve a la predeterminada. `_velocidad_de` aplica esa velocidad mientras dura el porte, sin eliminar monturas del inventario ni sus mejoras, y recupera sus bonos al entregar o perder el cristal.
- REA0060fc60 recibe0185 (entidad,flags bajos,flags altos), llama004b6790 y00600fb0. El bit04000000 activa DisplayMagicStatus_BearCrystal. Se envia para el portador, para otros observadores y al llegar tarde. Session conserva los snapshots0185 emitidos para preservar los otros bits al activar/quitar este. Se conserva el efecto3141 de vulnerabilidad, el limite de cinco minutos, caida al morir/desconectar, retorno y entrega idempotente.

## Contadores

REA005f3d70 y006692a0 confirman013B: dos marcadores de cristales, visibilidad del panel personal, puertas actuales, estatuas actuales, maximos10/25 y puntos de cinco digitos.00669000 toma TEAMID del jugador y elige digitos naranja24420 o azul24430. La marca de equipo incorrecta impedia tambien esta seleccion. Las construcciones, destrucciones y entregas siguen actualizando ese mismo panel; no se sustituyo por un contador inventado.

## Evidencia

Cliente analizado G:/Angel.exe, SHA2567c1f8cc16e2032081dc15ccc1a67de668803f62d8252ab570d1f4724c162d6e9b. Evidencias de esta sesion en docs/rea_evidence/179276*.json:

-1792761330895: dispatcher001D y base de tabla.
-1792761243455: TEAMID long38, subcampo1.
-1792761243483: TEAMID de NPC/pet, scalar63.
-1792761196836: aura por TEAMID1/2, texturas wnd01_w104_02 y siguiente.
-17927611969*: spawn de objetos y panel de contadores.
-1792761657613: handler0185 y flags de estado.
-1792761521313: bit de portador y efecto Lua nativo.
-1792762263674: reutilizacion de entidades estaticas, sin reemplazar sprite al reenviar000E.

Los objetos y tags proceden de map112.mpc de UPDATE9; los nombres y sprites abierto/cerrado/luz se contrastaron con el server.obd vigente. REA no reconstruye la logica del servidor oficial: el cruce de golems es una implementacion sobre esos tags y debe verificarse manualmente, asi como ajuste visual de pilares y bloqueo del recorrido del cliente. La progresion de resurreccion y la configuracion inicial10 estatuas/4 puertas no se han cambiado por una escena de video25/25.

## Prueba tras reinicio

Validacion: bateria ampliada391 pruebas aprobadas en69,93s, mas una prueba adicional aprobada de limites de base (rival/aliado/portador). Dos advertencias preexistentes de asyncio. Compilacion de los modulos modificados y git diff --check sin errores. La comprobacion automatizada no garantiza colores ni composicion final de sprites en pantalla.

Abrir una ronda NUEVA con `/hbstart 60 5`. Entrar con dos cuentas, confirmar naranja/azul propios y de companeros, observar madera durante registro y luz al comenzar. Probar golems desde ambos lados, romper uno, comprobar arco abierto, recolectar/converter materiales y donar para reconstruir. Robar cristal enemigo: verlo sobre el personaje, velocidad base, muerte, recuperacion y entrega. Entrar con un tercer observador para revisar actores ya presentes y comprobar contadores de cada bando. No declarar estas pruebas visuales aprobadas solo por pytest.
