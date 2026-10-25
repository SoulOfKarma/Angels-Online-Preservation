# Olympus Tower, Item Mall y rankings —2026-10-24

## Alcance y fuentes

La ampliacion posterior del catalogo, Star Blessing, muebles y Daily Events
esta documentada en [la entrega de sistemas del24 de octubre](MALL_STAR_FURNITURE_DAILY_2026-10-24.md).
Esa nota actualiza el numero de ofertas y distingue los sistemas aun pendientes.

Referencia visual del usuario: https://www.youtube.com/watch?v=n0zDRetWwPY .
No fue posible obtener el video por el navegador; no se afirma haberlo visto.
Las capturas muestran Olly/Ozzy, el menu de la torre, Item Mall y Rankings.
Se contrastaron los archivos IGG locales y manejadores concretos de REA.
No se redistribuye codigo descompilado ni capturas de otras cuentas.

## Olympus

`tools/audit_olympus_sources.py` reproduce `plantillas/olympus_tower.json`
desde spmsg.xml de update26 y los MPC vigentes. Los msgid de sp_finaltower
son **nodos de spmsg**, no indices directos de msg.xml:511651 abre8312 y
sigue al menu8353. Esto corrige la interpretacion anterior de esos numeros.

- Olly11085/sprite40293,casilla(39,16),direccion5,retrato1093.
- Ozzy14750/sprite40003,casilla(44,14),direccion7,retrato3.
- Se conservan los40 nodos originales alcanzables,opciones y rechazos.
- Canje de Olly: ventana nativa0151,grupo280,18 recetas originales.
- Ozzy:1 Olympus Coin54260 ->1 Olympic Heart Box54262,una vez cada24h.
  El limite se deduce del token54261 de1440 minutos; no se renueva al
  reiniciar ni cambia al crear otro personaje. Coste y entrega atomicos.
- Caja54262 ->5 Olympic Hearts54904,con un hueco libre; formula33 del Heart
  quita la marca8561 fuera de Olympus y nunca consume dentro de la torre.
- Mapas217 y332,instancia individual y aislada por cuenta/personaje,incluso
  para IDs heredados repetidos. Omos11084 en217,(40,126).
-538 monstruos de217 y550 de332,todos declarados por sus generadores.
  No aparecen todos al entrar: cada piso habilita sus zonas con los eventos
  originales. No reaparecen al morir. Se reparten juntos los generadores de
  cada plataforma usando su componente transitable, sin cruzar paredes a otro
  piso. Las oleadas mezclan sus tipos a lo largo de la sala. El primer piso
  mantiene60 enemigos, separados al menos3 casillas, cubriendo64x27 casillas.
  Se conservan los guardianes individuales en su posicion original. Es una
  distribucion local, no una captura de posiciones oficiales.
- Enemigos normales de las oleadas: campo XML `主動` ausente, agresividad0;
  responden al ataque. Se conserva la agresividad original de tipos especiales
  como Rahaiga2825 (radio10). No se activa agresividad global por conjetura.
- Portal visible original: sprite60001,casilla(17,7),evento8 del MPC41.
  Conserva el dialogo512557 de la niebla y su continuacion512653; el acceso
  habilitado sigue en Olly. El objeto ausente ahora se envia como000E y se
  puede pulsar de cerca, ademas del disparador original al pisarlo.
- Se atienden111/112,temporizador nativo016A/016B. El acceso dialogado original
  declara3600000ms; algunos eventos declaran1800000ms. Se respeta el parametro
  del evento; pasar217/332 nunca vuelve a empezar el reloj.
- La marca8561 conserva79200 segundos del magic.xml vigente (22h),aunque el
  texto de reglas habla de24h. No se sustituye silenciosamente por otra cifra.
- Omos registra solo una corrida realmente terminada; no basta hablarle al
  entrar. Journal SQLite ligado a usuario+char_id. Salir/usar un Heart antes
  de otra entrada no permite reutilizar un resultado previo.
- Reconexion en el mismo proceso conserva el reloj de la corrida en memoria.
  Tras perder esa instancia/reiniciar,no se entrega una torre vacia como
  si estuviera limpia: se devuelve al Lyceum manteniendo la marca.

Pendiente: tabla completa de premios semanales top30. Se encontraron los
buffs6892..6897 y las marcas originales,pero no sus lotes completos por
puesto. Un resultado genuino no se marca como cobrado mientras falte esa
tabla. No se inventaron objetos ni cantidades.

## Rankings

Se conserva la ventana nativa y su0133,con pagina/faccion y columnas reales.
Se agregan38 (semana actual) y39 (semana anterior) segun finaltower.xml y pvp.lua.
Solo cuentan registros guardados con Omos: mejor resultado por cuenta/personaje,
tiempo restante mayor primero,luego nivel y rango. A falta de fecha original
de creacion en fichas heredadas,el ultimo desempate es char_id estable; no se
afirma haber recuperado una fecha historica que no existe.
Semana local del servidor,lunes00:00. Los otros rankings ya existentes se
mantienen; esto no implementa retroactivamente todos los tipos aun vacios.

## Item Mall

Hallazgo:012B/012D se atendian erroneamente como radar,con0061/0062 ficticios.
REA demuestra que son solicitudes de Item Mall;0061 es Store Cabinet y0062
es saldo AG. Un ID de zona ahi se interpretaba como dinero.

Se carga `mall.xml`,no shop.xml:475 productos historicos deUPDATE9. El
exportador conserva categorias,precios,cantidades,flags,fechas y duraciones.
Ofertas historicas ya vencidas no se muestran. No es el catalogo moderno del
video. La ampliacion local de novedades se detalla abajo.

### Novedades recuperadas y cadena de nivel300

Se verifico el listado final del sitio oficial, que termina el18/12/2025:
https://ao.igg.com/news/newslist.php . Incluye la bolsa Holiday Gingerbread
Man del4/12/2025 (https://ao.igg.com/news/news.php?aid=5540) y el huevo Royal
Attendant del6/11/2025. Sus IDs y contenidos existen en los XML IGG locales.
No se uso el catalogo de otro servidor privado ni se copiaron IDs Taiwan.

`tools/audit_recent_mall_sources.py` compila190 objetos,25 tablas de bolsas
y221 nodos de dialogo nativos de Gear Clerk/Fashionable. `recent_mall.py`
atiende solo ese conjunto. Catalogo:475 filas originales sin cambiar precios,
mas4 novedades (IDs locales39000..39003):

| Item | Nombre | AG por unidad | Procedencia del precio |
| --- | --- | --- | --- |
| 81972 | Night City Code-Newbie Box | 399 | Local, autorizado por Karma |
| 82270 | 2025-Bloodshadow Halloween Lucky Bag | 399 | Referencia local autorizada |
| 82408 | Enchanted-Royal Attendant Voucher Egg | 399 | Referencia local autorizada |
| 82660 | 2025-Holiday Gingerbread Man Earrings Lucky Bag | 399 | Referencia local autorizada |

La prioridad solicitada es precio original verificable;399 solo cubre la
falta de ese dato para estas novedades. Ni las noticias ni los archivos Mall
disponibles contienen su precio original. No se presenta399 como precio IGG.
Se habilitan como novedades de preservacion local, sin fingir ofertas vigentes.

-81972 da los8 premios de drop28458, todos juntos.81974 requiere nivel285 y
  da71989/71990 (personaje/habilidades290),20x25832,82004 y81975.81975 requiere
  nivel295 y da81997/81998 (personaje/habilidades300),20x25832,82004 y81978.
- Las cajas sin `probN` entregan todos los premios; los huevos con pesos
  conservan el sorteo individual original, incluidos premios repetidos con
  distintas cantidades. No se usan probabilidades uniformes inventadas.
- Gear Clerk(170,93) usa su menu nativo final, incluido grupo615: equipo280
  y vales de vestimenta. Fashionable se agrega en(158,91), posicion/direccion
  de UPDATE19 sp_fashionable.xml, con el menu final de spmsg UPDATE26. Sus
  grupos619/620/622 permiten canjear Halloween/Royal/Winter Holiday.
- Aperturas y canjes: una transaccion SQLite, dueno+char_id, inventario
  esperado, materiales y capacidad de todo el lote antes del commit. Fallo
  SQL o bolsa llena conserva el origen; avisos detallan lo recibido.
- Los temporales obtenidos usan la duracion XML en minutos y la infraestructura
  persistente `mall_fin/mall_item`; el plazo local comienza al recibirlos.
  Es la misma politica de compatibilidad que las entregas del Mall, sin
  pretender haber recuperado un reloj de equipamiento pausado oficial.
- Piedras82000..82003: reutilizables, solo nivel300 o menor, buff1800s,
  +400% EXP o skillEXP y +50 de velocidad de recoleccion/fabricacion, segun
  magic.xml. Se conserva el buff al morir; los items duran86400min(60dias).
- Limite: no se reconstruyeron canjes ausentes de monturas con Fortunia,
  como el vale82659. Su descripcion/remision esta disponible, pero no existe
  una receta completa en exchange.xml para ese vale. No se consume en un
  canje ficticio. Tampoco se completa aqui la tabla semanal top30 de Olympus.

Protocolos contrastados en G:/Angel.exe,SHA256
7c1f8cc16e2032081dc15ccc1a67de668803f62d8252ab570d1f4724c162d6e9b:

- inititemmall ->58DDB0 ->61F3B0 ->61F4D0: C2S012D vacio.
- S2C005F ->620E80: U32 cantidad y registros de57 bytes.
- S2C0060 ->621070: actualizacion de existencias del producto.
- S2C0061 ->6210E0: U8 cantidad,registros33+longitud de mensaje.
- S2C0062 ->621260: U32 Angel Gold.
- mallbuy ->620C20: C2S012B,U32 producto+U8 bandera.
- mallgive ->621610: C2S012C,U32 producto+nombre17.
- Store Cabinet ->6212A0: C2S002F,cmd22,id de entrega,destino.

Karma autorizo expresamente precios originales y AG local por cuenta;
posteriormente autorizo1.000.000 inicial para **existentes y nuevas**.
No hay pagos reales ni conversion monetaria externa.

- Wallet por cuenta,NO por personaje. INSERT OR IGNORE conserva el saldo
  gastado; login,reinicio,otro personaje o repetir la inicializacion no regalan
  otro millon. Trigger de alta para cuentas nuevas y ledger del abono inicial.
- Compra: debito y entrega en Cabinet en una transaccion. Sin saldo,producto
  inexistente/vencido o Cabinet lleno,no se descuenta AG.
- Regalo: nombre debe resolver a una sola cuenta; prohibicion de regalo
  original se comprueba tambien en servidor. Cabinet del destinatario.
- Retiro: propietario,espacio e inventario actual validados antes del commit;
  la entrega se borra junto al guardado. Repetirla no duplica objetos.
- Maximo10 entregas pendientes,el limite de registros del manejador nativo.
- Temporales: deadline absoluto persistente. Flag8 cuenta desde compra;
  los otros comienzan al retirar. Viaja con equipo/banco personal y se limpia
  al caducar. Se bloquean las rutas de transferencia que perderian el deadline
  (puesto/banco de liga) y la conversion de temporales en bonos permanentes.
- Ofertas con flag de regalo adicional sin tabla de ese regalo se rechazan
  sin cobrar. No se inventa un bono anunciado por el catalogo.
- Favorites conserva el mecanismo local del cliente;no se fabrica otra lista.

## Aplicacion de AG a datos reales

`tools/init_item_mall_wallets.py --apply` se ejecuto por peticion explicita.
9 wallets creadas,9 abonos iniciales,1.000.000 por cuenta,total9.000.000.
No se modificaron personajes,inventarios ni contrasenas. Respaldo online SQLite:
`data/backups/before_item_mall_AG_20261024_121308_006168.db` (ignorado por Git).
El modo sin argumentos solo verifica/resume,no regenera fondos.

No se reinicio el servidor ni los clientes. Codigo Python nuevo requiere
reinicio autorizado; no se afirma validacion visual en el cliente real.

## Evidencia REA local (ignorada por Git)

En docs/rea_evidence/:1792851626839(search_strings),1792851695452(668A40),
1792852123099(5F8590),1792852181079(5F8630),1792852316271(tabla Lua),
1792852451266/1273(wrappers Mall),1792852498292/8311(init/set page),
1792852606241(61F4D0),1792852788233/8248(catalog/stock),
1792852842427/2434(cabinet/balance),1792852982039/2063(gift/withdraw),
1792854354635/4653(gift confirmation/product request).

Pruebas nuevas en SQLite temporal:tools/test_olympus.py y tools/test_item_mall.py.
Incluyen dialogos/router,caja/corazon,oleadas/puertas,espacio y cuenta ajena,
abono unico y alta futura,regalo,retiro repetido,fallo SQL y caducidad.

Regresion dirigida actualizada:348 pruebas aprobadas; avisos existentes de
asyncio al programar timers sin event loop en los fixtures de pruebas.
Compilacion Python y git diff-check correctos. No equivale a haber probado
visualmente los nuevos paneles en el cliente real.
