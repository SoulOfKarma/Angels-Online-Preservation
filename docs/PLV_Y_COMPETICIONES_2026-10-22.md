# Supreme Power, servicios de Lyceum y auditoria de competiciones

## Implementado: PLV sin cambiar el nivel real

El cliente descompilado local muestra en `sub_63AA20` que el campo de estado
del personaje debe contener **0x02000000**. Si el nivel es superior a 400,
el texto del HUD pasa a `PLV (nivel - 400)`. No se debe enviar nivel 10:
un personaje 410 conserva su nivel, estadisticas, EXP y requisitos.

`supremo.estado` compone ese bit solo cuando existe la recompensa persistente
`logros_cont['supremo']` y nivel >=401. Se usa al entregar la recompensa,
en la ficha 0x0002 y en el spawn publico. Los mensajes de fantasma y revivir
conservan el bit y el estado base propio de casas 0x80000000.

No se conceden nuevas ramas. Las ranuras 7/8/9 siguen siendo por nivel;
ninguna llamada nueva agrega una decima. No requiere migrar cuentas ni
repetir las pruebas/materiales de Aliua para personajes con la marca guardada.
Reiniciar el servidor y reconectar para que una quest ya terminada muestre PLV.

## Implementado: Blessing Angel y viaje al Sign-up Office

Fuentes: MPC vigente de stage 41, raices 5383 y 7546, y magic.xml vigente.

- Blessing Angel: CAST 6755 hasta nivel 50 (+100 ATK/DEF, +60 MATK/MDEF),
  6756 desde nivel 51 (+200 ATK/DEF, +120 MATK/MDEF). Ambos duran 7200 s.
  No cobra MP, no rellena HP/MP y reemplaza el otro rango sin apilarlos.
- BattlefieldAngel: usa su raiz 7546, no una conversacion elegida por el
  retrato compartido. Su opcion lleva a stage 114, tag 1. El propio arbol
  rechaza a quienes no se graduaron/faccion Heaven.
- Stage 114: se incorporan los cuatro NPC originales del map114.mpc vigente
  (UPDATE21), con sus tipos, sprites y casillas: Low-Tier Clerk 2431 (23,45),
  BattlefieldClerk 2432 (67,43), Mid-Tier Clerk 11292 (26,47) y High-Tier Clerk
  11293 (29,48). Sus raices son 7550/7581/7551/7552 respectivamente.
- Los cuatro encargados miran al sur (direccion 6), con rotacion al aparecer.
  Se retiro el Exit Guide local: Karma identifico el tornado de retorno en
  (23,29). Devuelve al Lyceum (175,89), sin dialogo de confirmacion.

**Implementacion en curso, no produccion.** `competiciones.py` gestiona rondas
persistentes, ingreso, observadores, PvP separado y comandos GM. Holy incorpora
cristales y edificios. Las rondas GM estan en modo de prueba con entrada normal (gold/piedra) y no
se abren eventos automaticos mientras falten los premios oficiales completos.
Las acciones profundas 71/83/86/116 continuan bloqueadas; las opciones raiz
se manejan en el servicio propio, sin dejar un segundo camino de cobro.
Ver [estado actual y bloqueos](COMPETICIONES_GM_2026-10-22.md).

## Encontrado: horarios y reglas originales

Fuente: `update26/setting/eng/msg.xml`, IDs 7563..7567, 7594/7596,
7747/7748, 8267/8268 y 8361..8369. Son textos originales, no una captura
que confirme el reloj del servidor oficial. No fijan por si solos zona horaria.
El usuario eligio conservar los horarios oficiales encontrados.

### Angel Arena

| Nivel real | Dia | Hora indicada | Tasa en monedas |
| --- | --- | --- | --- |
| 60–89 | lunes | 19:30 | 75000 |
| 90–119 | martes | 19:30 | 350000 |
| 120–149 | miercoles | 19:30 | 1200000 |
| 150–179 | jueves | 19:30 | 6000000 |
| 180–209 | viernes | 19:30 | 30000000 |
| 210–239 | sabado | 19:30 | 75000000 |
| 240–259 | domingo | 19:30 | 200000000 |
| 260–279 | lunes | 19:31 | 4000000 |
| 280–299 | martes | 19:31 | 8000000 |
| 300–319 | miercoles | 19:31 | 8000000 |
| 320–339 | jueves | 19:31 | 8000000 |
| 340–359 | viernes | 19:31 | 8000000 |
| 360–379 | sabado | 19:31 | 8000000 |
| 380–400 | domingo | 19:31 | 8000000 |
| 401+ | domingo | 19:32 | 8000000 |

Correccion posterior: tasas260+ confirmadas por Karma como4M/8M. La copia
inglesa del XML tiene importes inconsistentes; la tabla de tasas anterior
400M/800M tambien era incorrecta. No son4.000M/8.000M. Ver
[capturas y correccion de entrada](DIALOGOS_COMPETICIONES_PROXY_2026-10-22.md).

Anuncio/inscripcion 15 minutos antes, servidor branch 1. El dialogo original
envia a stages 159/239/240; 113 es una version antigua que tambien queda en
stage.xml. El texto dice diez ganadores por grupo, titulo Battle Angel para
el primero; el muerto se convierte en espectador sin perder EXP. Falta la
motor historico completo no esta reconstruido: el actual tiene rondas basicas,
inscripcion y observadores; su clasificacion no replica aun las siete areas
y todas las eliminatorias originales. Los premios siguen sin entregarse.

### Holy Battlefield

Stage 112, sin restriccion de nivel. Viernes y domingo a las 12:00 y 21:00,
una hora; inscripcion 15 minutos antes. El texto de reglas habla de capturar
cristales, con victoria al terminar por mayor cantidad o alcanzar 20.
No confundirlo con Outpost Battlefield 47/48 ni Totem War.

El grafo del clerk 7581 contiene las piedras correctas y su prioridad:

- Un uso: 8537, 8770 (Trial), 24882. Hay REMOVE_ITEM explicito para ellas.
- Temporales: 16764, 16765, 28866 (7 dias) y 40921. No se deben consumir
  al entrar; hay que comprobar caducidad real persistente por ejemplar.
- 16762/16763 son cajas selladas, no pases ya activos.

El item 28866 declara duracion 10080 minutos. Hay una incongruencia en el
16765: nombre "60 Days", duracion XML 129600 minutos (90 dias).
Correccion posterior documentada: el servidor usa 60 dias para las nuevas
piedras16765, coherente con su producto/desellado. No se acortan fechas de
ejemplares ya activados. Ver [pases y runtime](HOLY_RUNTIME_Y_PASES_2026-10-22.md).

El servicio propio gestiona equipos, ingreso, cristales y reconstruccion de
edificios con transaccion de materiales. Tiene PvP propio y paquete de marcador
derivado del cliente; falta validacion visual en juego. Las acciones genericas
73..77 no se habilitaron globalmente. La entrega de premios sigue bloqueada
por falta de tabla completa y formula de IGG verificadas para niveles altos.

### Olympus Tower

Stage 217 y variante posterior 332; 315 figura como torre de prueba.
stage.xml declara instancia individual, 1000 paralelos, una persona, retorno
forzado al Lyceum 41 y mapa sin minimapa. No es un campo PvP compartido.

Hay generadores y eventos originales. Las acciones 111/112 usadas por la
torre no tienen DEFINE conocido en el eventdef disponible. En map217, 111
lleva 1800000 (30 minutos), mientras el texto 8327 describe 60 minutos:
resolver con el binario/captura antes de fijar un tiempo de competicion.

finaltower.xml declara rankings 38/39 para 217 y 57/58 para 315; el ranking
actual del servidor no calcula estos tipos. Los textos 8326..8350 describen
marca de 24 horas, registrar resultado con Omos, tiempo menor primero y
desempate por nivel, rango y creacion, top 30 y cierre semanal lunes 00:00.
No se han habilitado resultados ni premios ficticios.

NPC 11157: **Olympian Angel**, sprite 40195, existe en npc.xml. No se encontro
su colocacion en los MPC vigentes ni en sp_*.xml. Los sp_finaltower*.xml
colocan **Ozzy** 14750 (44,14) y **Olly** 11085 (39,16) en Lyceum, con textos
de Olympus Coins/Heart. No confundirlos automaticamente con el angel de
entrada solicitado. La restauracion del NPC de acceso sigue pendiente.

## Census Angel: pendiente de implementar de forma atomica

Corregido su dialogo: usa la raiz 5829 y el retrato 46 del MPC, con el
nombre del jugador como parametro. Ya no cae en el menu generico de canjes.
Las opciones informativas se recorren normalmente. Al llegar a una entrega
de cambio individual (accion 29) o de liga (61), se bloquea todo el lote
antes de aplicar costes, sellos, objetos o punto de resurreccion. El usuario
recibe un aviso explicito de que la transferencia sigue sin implementar.

Raiz original 5829, NPC 2006. El XML distingue transferencia individual y
de liga, tasas por nivel/nivel de liga, restricciones de poblacion y un sello
3541. El individuo con liga debe ser rechazado. El cambio colectivo debe
actualizar a todos los miembros, incluidos desconectados, y sincronizar
sesiones activas, liga y faccion del territorio/totem; no solo al lider.

La accion original 61 es GUILD_CHANGE_ALIGN y aun no se aplica; la 29 es
SET_ALIGNMENT y tampoco tiene aplicador en esta ruta. No se ha habilitado el
menu a medias, para no cobrar monedas y dejar la faccion sin cambiar.

Diferencia de reglas: el grafo original rechaza a la liga si posee territorio
(mensaje 6222). El usuario describe conservar la liga y actualizar tambien
su totem al transferirla. Esa adaptacion necesita transaccion para todos los
miembros y propiedad, y refresco de totem sin resetear su vida/nivel. Sigue
pendiente; no se ha cambiado ningun personaje real ni propietario al auditar.

## Verificacion

`tools/test_supreme_display.py`, `tools/test_aliua_skill_slots.py` y
`tools/test_competition_npc_basics.py` ejercitan paquetes reales, HUD/ficha,
persistencia del bit al revivir, nueve ramas intactas, menus del MPC, buffs,
viaje al lobby, sus cuatro NPC y rechazo sin consumir piedras.

Suite combinada de estas pruebas con Lyceum, buffs, eventos, instancias,
inventario y pets: **230 passed**, un aviso de deprecacion de asyncio en
una prueba existente. Se aislo el nivel del totem en una prueba antigua:
antes dependia del nivel que el usuario tuviera en su base local. No se
cambio ningun nivel del juego ni de un totem para hacer pasar esa prueba.

La cifra anterior corresponde a la etapa PLV/servicios, no a una validacion
del motor nuevo ni de sus premios. Las pruebas nuevas y limites actuales
se detallan en COMPETICIONES_GM_2026-10-22.md.
