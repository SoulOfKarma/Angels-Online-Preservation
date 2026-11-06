# Fortunia, Scrollmaker, item9 y Album

## Canjes

La fusion anterior reutilizaba grupos de Taiwan dentro de las tiendas IGG.
Las 8.470 recetas apartadas se recuperaron con sus IDs originales, grupos
propios 2000--2190 y materiales/premios intactos. Se conservaron tambien las
410 recetas que se habian agregado por separado: al compararlas resultaron
distintas de las otras 8.060, no duplicados.

Fortunia mantiene sus opciones anteriores y ofrece `Special Voucher and
Event Exchanges` dentro del menu de vales: runas, martillos/alimento,
pergaminos V, mascotas, EXP, equipo, vestimenta y eventos. Los 235 textos de
ese navegador estan en ingles. Los seis accesos antiguos estaban abriendo
`shop.xml` mediante 0x0034; sus numeros pertenecen a `exchange.xml` y ahora
abren el canje nativo 0x0151, incluido Runestone (grupo 596, 163 recetas).
Las cuatro opciones principales de armas, monturas y PD usan el mismo
protocolo correcto.

Scrollmaker recupera su arbol completo de spmsg: informacion, cuatro ramas
de pergaminos y seis de habilidades (grupos 374--382 y 477). Ambos usan las
entidades existentes 401/404 y sus posiciones originales; no se duplican.

Las recetas nuevas se validan contra NPC, distancia y grupo abierto; sus
transacciones usan SQLite y no consumen materiales si falla la entrega.
Los seis Time Treasure Lucky Bags conservan su limite original de 10 canjes
diarios por receta, con contador persistido en la misma transaccion.
Fashionable muestra `Winter Holiday Enchanted PD` para el grupo 622;
`Noryo Festival Enchanted PD` sigue abriendo su grupo original 607, de dos
recetas, sin las filas nuevas de aniversario.

El ejecutable IGG conserva el grupo recibido como u32 en 0x5F48CD y compara
ese valor con el campo de grupo de cada receta en 0x6704E8/0x670621. No usa
un arreglo limitado a 659 grupos. Evidencia: `work/exchange_group_igg.txt`.

Herramienta: `tools/restaurar_canjes_tw.py`; configuracion versionable:
`server/plantillas/tw_exchanges.json`. Respaldo:
`work/backup/fortunia_20261026_220814`.

## Traduccion y tooltip

Revisadas las 3.700 filas completas de item9 y los materiales/premios de
ambos NPC, incluyendo contenidos de cajas alcanzables: 9.813 objetos.
Instalados 6.379 cambios de campos visibles y 9.415 rotulos de recompensa.
Los nombres y descripciones revisados no conservan chino/japones. Se uso
traduccion asistida con cache, proteccion de marcadores numerados, revision
de unidades y correcciones manuales de vocabulario y objetos reportados.
Cache y correcciones: `work/traduccion/manual/item9_completo_*.json`.

Los objetos 82770--82777 tienen redaccion revisada. La normalizacion previa
retiro bloques `/c$2%s/c*` en 1.147 tooltips, pero NO resolvio el cierre de
Great Enma: el informe posterior del usuario lo confirmo. El analisis del
27 de octubre encontro que IGG tiene un expansor nativo para `%s`; no era
correcto atribuir el fallo a un printf sin argumentos. La causa demostrada
y su parche del ejecutable se documentan abajo.

No cambian clases, flags, estadisticas, requisitos ni drops. Se verifico
que tampoco se pierden cifras visibles. Se actualizaron los XML, ambos PAK
y los campos de texto de `corpus/content.db`, con integridad SQLite correcta.
Respaldo: `work/backup/item9_completo_20261026_233046`.
Herramientas: `tools/traducir_item9_pendientes.py` y
`tools/instalar_item9_traducido.py`.

## Album

El paquete real del jugador era 0x0016/0x33, ranura 63, objeto 66725
(`Zionic-Eldritch Boots`). Su categoria XML es `鞋子`, mientras el clasificador
solo aceptaba `靴子`, por lo que rechazaba unas botas validas. Ahora reconoce
ambas grafias y las dos variantes de martillo; el rango de mochila usa la
misma capacidad que el inventario. Se verifico deposito real y persistencia
de esas botas en una cuenta temporal. No se modificaron cuentas del usuario.

La estructura 0x0156 se contrasto con el handler IGG 0x5F5120 y ya era
correcta; no se altero. Evidencia: `work/album_handler_igg.txt`.

## Comprobacion y carga

Pruebas iniciales: `test_tw_exchanges`, `test_item9_translation`,
`test_album_native`, `test_recent_mall` y `test_traducir`: 75 casos correctos.
Cubren acceso por clic, grupos y textos instalados,
costes/premios originales, SQL atomico, limites diarios, conservacion del
equipo y serializacion del Album. Reiniciar el servidor propio y el cliente
para cargar codigo y tablas; no se inicia un servidor adicional.

## Ampliacion y correccion del 27 de octubre

Se agrego `TW Fortunia` en Angel Lyceum (170,82), entidad 71410140, cerca de
la Fortunia original. Conserva el arbol completo del NPC TW 8814 de
update32: 23 nodos y 838 recetas en 17 categorias. Los grupos son
2400--2416. La numeracion inicial 36000--36837 se corrigio a
35389--36226 tras detectar el corte de enumeracion descrito abajo.
Se preservan todos los costes,
premios, cantidades y opciones de la fuente; solo se traducen los textos.
El cliente permite IDs de receta menores a 50000 (GetExchange, 0x5D4700).

Incluye las cuatro mejoras de 45 estrellas (objetos 68614, 68654, 68634 y
68354; 103 vales correspondientes por unidad) y las seis gemas Perfect (P)
de Lv 450 (83205--83210; 81 Runestone Vouchers). Las primeras se encuentran
en `Exchange vouchers for rewards` > `Enhancement items and bonus cards` >
`31-star and above`. Las gemas estan en la segunda pagina de vales,
`Runestones` > `Lv 310 and above`. Tambien se incluyen los demas grados,
equipo, robots, mascotas, PD y tickets de coleccion del catalogo nativo.

El usuario aclaro que con "lo de Noryo" se referia a TODOS los objetos TW
que antes aparecian mezclados en ese menu. Son 199 recetas del aniversario
del mall, no las dos cajas PD de Noryo. Ahora la Fortunia original tiene una
entrada directa `TW Mall Anniversary - Coins, Keys and Lv 410 Sets` que
abre las 199 recetas (grupo 2173), ya traducidas: monedas, conversiones,
llaves, cajas de sets y el resto completo. No se recorto a los ejemplos de
la captura. El resto de las 8.470 recetas recuperadas sigue disponible en
el navegador de canjes especiales de Fortunia.

Se revisaron 10.661 objetos alcanzables de item9 y los cambiadores. La
ultima ampliacion modifico 17 campos y dejo traducidos 10.253 rotulos de
canje. `update26.pak` y su `.bak` contienen las mismas tablas instaladas.
Respaldos: `work/backup/fortunia_tw_nativo_20261027_001246`,
`work/backup/item9_completo_20261027_001324` y
`work/backup/fortunia_aniversario_20261027_001711`.

### Cierre al mostrar Great Enma

82771 y 82772--82777 referencian hechizos permanentes 23363 y 23351--23356,
ausentes de las tablas disponibles. El tooltip nativo llama a GetMagic
(0x4A5670) desde 0x641360 y pasa su resultado NULL a 0x63C1D0. Esa funcion
lee el campo magic+0x10 sin comprobar el puntero: causa un acceso a 0x10.
La funcion siguiente, 0x63BA90, si comprueba NULL.

`tools/parchear_tooltip_hechizo_ausente.py` agrega una guarda a 0x63C1D0:
devuelve false si falta el hechizo y conserva el prologo original para
punteros validos. La seccion RX `.twfix` aloja los 26 bytes de la guarda;
las secciones anteriores solo cambian en los 9 bytes del salto de entrada.
Se instalo en `C:\AO\Angels Online\angel.dat`, con respaldo
`work/backup/tooltip_enma_20261027_000434`. No se borraron referencias de los
objetos ni se inventaron definiciones de los hechizos ausentes. La guarda
evita el cierre; no implementa los efectos inexistentes de esos hechizos.

Unicorn x86 reproduce el acceso nulo con el codigo original; el parche
retorna sin error y conserva la pila/registros. Se comparo tambien un
hechizo valido y la integridad de todas las secciones existentes. No se
probo el hover en una sesion grafica real despues del parche.

Validacion final: 108 pruebas correctas, con 9 avisos DeprecationWarning
previos de asyncio. Incluye clic real por los 17 grupos, canjes de mejoras
45/gemas/llaves/sets con persistencia en SQLite temporal, comprobacion de
las 838+199 recetas completas, pruebas del Album y regresiones anteriores.
Se verificaron CRC de ambos PAK y hash del ejecutable instalado.

```
python -X utf8 -m pytest tools/test_fortunia_tw_native.py tools/test_tooltip_enma.py tools/test_item9_translation.py tools/test_tw_exchanges.py tools/test_album_native.py tools/test_recent_mall.py tools/test_traducir.py -q -p no:faulthandler
python -X utf8 -I tools/fortunia_tw_nativo.py verificar
```

Las pruebas de x86 usan Unicorn 2 instalado localmente en `work/vendor`.
Se desactiva faulthandler de pytest porque Unicorn usa excepciones SEH
internas de Windows que ese complemento imprime como errores fatales.

## Correccion de los menus vacios de TW Fortunia

El usuario confirmo visualmente que las ventanas abrian vacias. Las pruebas
anteriores comprobaban filas y paquetes del servidor, pero no la enumeracion
del cliente: la ventana nativa llama a GetExchange(1), GetExchange(2), etc.
y termina al primer NULL (0x6704D6--0x670543). Las 838 recetas empezaban en
36000, dejando vacio 35389: ninguna resultaba alcanzable para la ventana.
El limite de 50000 era correcto pero insuficiente para validar la carga.

Se renumeraron exclusivamente esas 838 recetas a 35389--36226, contiguas a
las anteriores. Se actualizo el mapa del servidor y ambos PAK. Se mantuvo
cada texto, grupo, coste, premio, cantidad y orden. La herramienta ahora
exige continuidad de IDs tanto al generar como al verificar.

TW Fortunia permanece cuatro casillas a la izquierda de la original y en
su misma fila (170,82 frente a 174,82). Usa el paquete visual original de
Fortunia, conservando direccion 5 y los bytes 48/49 (80 0C), que faltaban
al construir un NPC nuevo. Solo cambian identidad, nombre y coordenada X.

Regresion: se emulo el bloque x86 original de la ventana con las tablas
antes/despues. Antes encuentra cero mejoras de grado 31+; despues encuentra
las 60. Se verifico en ambos PAK que los 17 grupos y sus 838 recetas son
alcanzables antes del primer hueco. Los paquetes de ambos NPC coinciden en
Y, direccion y todos los ajustes visuales. 84 pruebas del cambio y canjes
anteriores correctas; compilacion y diff sin errores. No hubo comprobacion
grafica del cliente posterior a esta correccion.

Herramienta: `fortunia_tw_nativo.py reparar` / `instalar_reparacion`.
El respaldo y los hashes estan en `work/fortunia_tw_menu_fix.json`.
El hash de exchange.xml del informe anterior de traduccion corresponde a
la numeracion anterior; `fortunia_tw_nativo.py verificar` valida las tablas
actualizadas completas contra los dos paquetes instalados.

```
python -X utf8 -m pytest tools/test_exchange_client_enumeration.py tools/test_fortunia_tw_native.py tools/test_tw_exchanges.py tools/test_recent_mall.py -q -p no:faulthandler
```
