# Ligas y territorios: evidencia original XML/MPC/Lua

Consulta local de 2026-10-19. Esta nota documenta datos originales y distingue
lo confirmado de lo que requiere reconstruir el servidor. No modifica BC ni
Super BC. La parte binaria REA se documenta por separado.

## Fuentes y método

Se leyó el XML incrustado en los MPC más recientes mediante
`tools/mapa_del_cliente.py` y los números de acciones/condiciones mediante los
DEFINE de `setting/eventdef.xml`, usando `tools/eventos_del_cliente.py`.
`server/dialogos_mapa.py` permite consultar la transcripción ya extraída del
grafo de diálogo. Se contrastaron nodos relevantes con el XML crudo del MPC.
Los textos y atributos se consultaron con `house_services.xml_rows`, que elige
el archivo de mayor update disponible: no combinar IDs de clientes distintos.

Los mapas 008/009/011/012/015/016/017/021 consultados corresponden a UPDATE19;
los campos de batalla 200 y 205 consultados corresponden a update24.

## Territorios privados y campos de batalla

`update26/setting/eng/stage.xml` relaciona explícitamente cada campo de batalla
con su territorio original (`原領地編號`). No es lo mismo un campo de batalla
que un mapa de recursos privado de sus propietarios.

| Campo de batalla | Territorio original | Area I, stage 50 | Area II, stage 100 | Area III, stage 117 | Area IV, stage 377 |
| --- | --- | --- | --- | --- | --- |
| 200 | 8 Crashing Hillock | paralelo 0 | paralelo 0 | — | — |
| 201 | 9 South of Mirror Lake | paralelo 1 | paralelo 1 | — | — |
| 202 | 11 Thunder Ruins | paralelo 2 | paralelo 2 | — | — |
| 203 | 12 North of Mirror Lake | paralelo 3 | paralelo 3 | — | — |
| 204 | 15 Mysterious Wetland | paralelo 4 | paralelo 4 | paralelo 0 | — |
| 205 | 16 Thorn Wasteland | paralelo 5 | paralelo 5 | paralelo 1 | paralelo 0 |
| 206 | 17 Quiet Vale | paralelo 6 | paralelo 6 | paralelo 2 | — |
| 207 | 21 Dragon Graveyard | paralelo 7 | paralelo 7 | paralelo 3 | paralelo 1 |

Estos destinos salen de la acción **37 CHANGE_PARA_MAP(stage, paralelo, tag)**
de los Terra Keeper. El tag de llegada es 1 en todos estos casos. Los límites
de paralelos del stage.xml son respectivamente 8, 8, 4 y 2.

Ejemplo preciso Thorn Wasteland (`UPDATE19/map/map016.mpc`):

- Nodo 1000042, mensaje 9014: menú de las cuatro áreas.
- Nodo 1000064: `CHANGE_PARA_MAP(50,5,1)`.
- Nodo 1000063: `CHANGE_PARA_MAP(100,5,1)`.
- Nodo 1000065: `CHANGE_PARA_MAP(117,1,1)`.
- Nodo 1000092: `CHANGE_PARA_MAP(377,0,1)`.
- Todos rechazan mediante **76 SPEC_MAP_OWN_GUILD(205)** negada.

Por tanto, no basta con pertenecer a cualquier liga: esa liga debe poseer el
territorio específico. Los paralelos son por territorio; no constituyen un
espacio gratuito distinto para cada liga.

## Heaven General: viaje y premios

NPC 2010, sprite 40005, retrato 47. Raíz 5920 en las ciudades stages 3,26,29,38.
Los números de los nodos internos cambian en cada ciudad.

En `map003`:

- 1000358 comprueba **28 HAVE_GUILD_REGION()** antes del menú de premios.
- 1000359 rechaza si ya se tiene el objeto oculto 3754 (condición 7).
- En ese mismo nodo, **condición 82(259200)** negada lleva a 1000621,
  mensaje **516877**, que exige explícitamente haber pertenecido a la liga
  durante 3 días. El número 82 no tiene DEFINE en el eventdef disponible;
  su significado aquí está respaldado por el parámetro en segundos y el texto,
  pero el detalle interno debe contrastarse con REA/servidor.
- 1000360 ofrece caja de combate; 1000361, caja de producción/recolección.
  Ambas vuelven a comprobar propiedad de territorio y espacio.
- Condición 3 sobre propiedad 29 corresponde a nivel; propiedad 51, rango.
  El comparador 4 es el usado por las ramas de umbral mínimo.

| Nivel mínimo | Rango mínimo | Caja combate | Caja producción |
| --- | --- | --- | --- |
| 30 | ninguno adicional | 3776 | 3777 |
| 40 | 7 | 3778 | 3779 |
| 50 | 8 | 3780 | 3781 |
| 60 | 9 | 3782 | 3783 |
| 70 | 10 | 9255 | 9256 |
| 80 | 11 | 9257 | 9258 |
| 90 | 12 | 13409 | 13410 |
| 100 | 13 | 13411 | 13412 |

Se evalúan primero las ramas de mayor nivel. Cada entrega usa
**51 CREATE_ITEM_DAY(3754,1,caja,1,0,0,0,0,0,0)**. El sello 3754 es oculto,
no eliminable, con `持續時間=1440`; texto 5943 prohíbe otra entrega el mismo
día. La implementación debe persistir el límite y coordinarlo con expiración
de objetos ocultos. El XML no demuestra por sí solo la zona horaria ni la
hora de corte del servidor oficial.

Hay una condición adicional 67(0,0) que lleva a mensaje 2601. No tiene DEFINE
en los datos examinados. No adjudicarle una semántica por el texto de
`string.xml` con el mismo ID: los namespaces msg/string son distintos.

Viaje al territorio: 1000362 y 1000364 comprueban HAVE_GUILD_REGION, y
1000365 ejecuta **50 GOTO_GUILD_REGION()** sin parámetros. El destino depende
de propiedad persistente de territorio; el MPC no contiene la tabla interna
de esta acción.

Insignias: opción mensaje 5959 conduce a 1000403, que ejecuta OPEN_SHOP(71).
`update26/setting/shop.xml` contiene 14 entradas, item1..item14, IDs 3735..3748.
Importante: son hijos XML, no atributos; `xml_rows('shop.xml')[71]` solo devuelve
el atributo ID y **no basta para obtener el catálogo**.

## Servicios en los mapas privados

Los cuatro mapas 50/100/117/377 comparten el gobernador de raíz 5940
(mensaje de rechazo 5936, retrato 8). HAVE_GUILD_REGION conduce a 1000001,
mensaje 5960. Opciones:

- 1000002: OPEN_BANK(0), banco personal.
- 1000003: OPEN_BANK(1), banco de liga.
- 1000004: entrega Regression Scroll, item3734, solo si no se tiene ya uno.

Se vuelven a comprobar territorio y espacio antes de entregar. El item3734
tiene magia residente 3071; su XML indica regreso al territorio, sin comercio
ni almacenamiento en banco. No basta dar el objeto si su magia no se conecta
a la propiedad y destino de territorio.

Los eventos de tornado de esos mapas ejecutan GOTO_GUILD_REGION y no un
teletransporte fijo a la ciudad. Debe resolverse según el territorio actual.

## Entrada al campo de batalla y defensas

En map016, nodo1000075 consulta **75 SPEC_MAP_OWN_ALIGNMENT(205)** y
**32 IS_PVP_ON()**. Dueños de facción van a tag5 de stage205; durante guerra,
los demás llegan a tag1/2/3/4 según facción1/2/3/4. Son comprobaciones distintas
de SPEC_MAP_OWN_GUILD, que controla las áreas privadas.

`update24/map/map205.mpc` contiene condiciones
**77 PVP_IS_GUARD_OWNER(index)**, con índices 0..3, para desplazamiento entre
defensas; no se debe reemplazar por una simple comprobación de pertenencia a
liga. Los registros de generadores confirmados del MPC son:

- zona6 tipo9847, zona7 tipo9848, zona8 tipo9849, zona9 tipo9850;
- zona18 tipo9851, zona19 tipo9852, zona20 tipo9853, zona21 tipo9854;
- zonas44..47 tipo9855, cantidad10 por zona.

Los eventos de muerte4, evento2..5, emiten CHAT(12,8282,0,0,0,0) y activan los
generadores18..21 y44..47 correspondientes. Los eventos6..9 activan de nuevo
los generadores6..9. Debe preservarse esa relación.

Los atributos vienen del monster.xml: fortalezas9847..9854 tienen AI153,
50 millones HP, defensa7420 y defensa mágica15590. Totem Guard IV9855 tiene
AI208,10 millones HP y ataque76000. **No son enemigos normales** y su AI/estado
de dueño requiere tratamiento de guerra. El evento de muerte de fortaleza no
demuestra por sí solo quién obtiene un territorio ni cuándo se consolida.

## Horarios y límites de lo demostrado

Mensaje6215 describe una guerra de **dos horas**, durante la cual se prohíbe
cambiar de facción. String1793 prohíbe abandonar territorio durante guerra.
String1755 impide invertir con HP de tótem inferior al90%; string1754 menciona
otra restricción cuando el tótem está débil. El Lua `extracted_luas/pvp.lua`
expone `toteminvest`, `toteminvestconfirm`, `toteminvestwnd`, `pickuptower`, y
`netcommand(25,0)` para punto de renacimiento. `guild.lua` define comando14
GIVEUP_REGION. Esto prueba funciones de interfaz, no sus paquetes ni reglas
completas de servidor.

No se confirmó en estos XML un horario semanal de Totem War ni una regla de
captura, de empate o de último golpe. Los textos con horarios de otras batallas
no deben reutilizarse. Mensaje5972 (18–22) es acceso a otra zona de monstruos,
no prueba de horario de Totem War. El REA del cliente puede confirmar paquetes,
estructuras y validaciones visuales; el planificador autoritativo puede residir
únicamente en el servidor original.

`guild_contrib.xml` define contribución a la liga (`獲得名聲`), no prueba la
experiencia de tótem. Textos5963..5985/5995 describen lotes200 y experiencia
de tótem; hay que cruzar la tabla/función de inversión antes de reutilizar
reputación de liga como experiencia de tótem.

Estos hallazgos permiten implementar viajes, comprobaciones y premios, siempre
que exista primero propiedad real persistente. No justifican asignar propiedad
al crear una liga ni anunciar Totem War completo sin combate y adjudicación.
