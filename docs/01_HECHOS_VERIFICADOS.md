# Angels Online - Hechos verificados

Regla del proyecto: en este documento solo entra lo que esta **medido**.
Cada afirmacion lleva su evidencia. Las conjeturas van en `02_ABIERTO.md`,
nunca aca, y nunca en el codigo.

Fecha: 2026-09-17

---

## 1. Framing  [PROBADO]

Header de 6 bytes ofuscado:

```
b0-1 : payload_length XOR 0x1357            (LE16)
b2-3 : sequence       XOR payload_length    (LE16)
b4   : flags          XOR (payload_length & 0xFF)
         bit 0 = cifrado    bit 7 = comprimido
b5   : checksum del payload EN CLARO
wire = 6 + (cifrado ? redondeo_a_16(payload_length) : payload_length)
```

**Evidencia doble:**
- Binario: `sub_81E900` (lector) y `sub_81EF80` (emisor) en `Angel_unpacked.c`.
  El emisor construye el header exactamente en este orden.
- Corpus: 163.314 frames S2C con **100,0%** de checksums validos y
  **100,0%** de cadenas de sub-mensaje exactas, 0 desincronizaciones.

Secuencia: el cliente incrementa 1..0x7FFE y vuelve a 1 (`sub_81EF80`).
El **servidor siempre usa seq=1** (2.730/2.731 medidos). Hello usa 0xFFFF.

## 2. Sub-mensajes  [PROBADO]

El payload contiene sub-mensajes concatenados:

```
[LE16 sub_len][LE16 opcode][sub_len-2 bytes de datos]
```

`sub_len` incluye el opcode. La suma de `2 + sub_len` consume el
`payload_length` exacto: verificado en 207.570 sub-mensajes.

## 3. Cifrado  [PROBADO]

Los servidores observados negocian **clave de sesion nula (16 bytes en cero)**,
entregada en el Hello. Consecuencia:

- **S2C queda en texto plano** (flag de cifrado sin activar).
- **C2S usa `CryptXORIV`**: XOR de 16 bytes donde, tras cada paquete, cada
  DWORD de la clave se incrementa en `padded_len`. Partiendo de clave cero,
  descifra **98,1%** de 45.183 frames C2S con checksum valido.

El cliente soporta ademas BLOWFISH, RIJNDAEL, MARS, RC62 y XOR simple
(clases RTTI en `Angel.exe`), pero no se observaron en uso.

**Consecuencia practica:** nuestro servidor elige la clave. Enviando clave
nula, el cifrado deja de ser un problema.

## 4. Handshake / Hello  [ESTRUCTURA VERIFICADA, SEMANTICA PARCIAL]

Frame con `seq=0xFFFF`, plano. Manejado por `sub_81EED0`.
Estructura decodificada de una captura real:

```
10 00 00 00     count = 16
<16 bytes>      (cero en las capturas)
50 00 00 00     len = 80
<80 bytes>      CODIGO MAQUINA x86 EJECUTABLE
18 00 00 00 / 01 00 00 00 / 10 00 00 00
<16 bytes>      clave de sesion (cero en las capturas)
```

El servidor envia **codigo x86 que el cliente ejecuta** (prologo, bucle,
`ret 0xc3`, padding `nop`). Es anti-cheat dinamico: probablemente un
checksum sobre la memoria del propio cliente.
**Pendiente:** leer `sub_81FC10`, `sub_81FAD0`, `sub_81FB70`.

## 5. Opcodes  [MEDIDO]

82 distintos: 59 S2C, 25 C2S. **20 de tamano fijo con >=50 muestras**,
o sea estructura deducible de forma directa y verificable.

Confirmado campo por campo contra datos reales:

**0x0005 ENTITY_MOVE (S2C, 22B fijo, 13.677 muestras)**
```
[LE32 entity_id][LE32 cur_x][LE32 cur_y][LE32 dst_x][LE32 dst_y][LE16 speed]
```
Muestra real: entity=7, cur=(5200,2383), dst=(5072,2543), speed=50.

## 6. Artefactos del sniffer  [RESUELTO]

Los `.bin` de `logs/raw_streams/` contienen secuencias de **6 bytes en cero**
entre frames (2.698 de 2.716 huecos). **No son protocolo.** `sub_81E900`
hace `if (v3 <= 0) return -2` ante longitud cero: el cliente real se
desconectaria. Son un bug de la herramienta que escribio las capturas.
El corpus los descarta.

---

## Herramientas

| archivo | funcion |
|---|---|
| `tools/validate_framing.py` | prueba el framing contra streams crudos |
| `tools/resync_probe.py` | distingue framing erroneo de huecos de captura |
| `tools/gap_histogram.py` | mide los huecos entre frames |
| `tools/gap_context.py` | contexto de opcodes alrededor de huecos |
| `tools/build_corpus.py` | construye `corpus/packets.db` y valida |
| `tools/opcode_map.py` | informe de cobertura por opcode |

`corpus/packets.db` (SQLite): 207.570 sub-mensajes reales consultables.

---

## 7. 0x0008 NPC_SPAWN (S2C)  [ESTRUCTURA MAYORMENTE RESUELTA]

4.066 muestras, cuerpo de **63 bytes fijos** (sub_len = 65).

```
+0   LE32   entity_id        1..0x38AD, enteros chicos correlativos
+4   LE32   flags            1 = NPC interactivo/hablable, 0 = objeto o jugador
+8   LE32   tile_x           14..325   (ESCALA TILE, no pixeles)
+12  LE32   tile_y           23..237
+16  char[17] nombre         ASCII, relleno con NUL, hasta 16 chars
+33  byte   ?                4..7
+34  LE32   sprite_id        ej 0x9C75, 0xEB51, 0xA47B
+38  LE16   ?                0 en NPCs, 7 en lo que parecen jugadores
+40  LE32   clase            200 (0xC8) en NPCs / 1 en jugadores  <- DISCRIMINADOR
+44  byte   ?
+45  LE16   npc_type_id      id de npc.xml
+47  byte   ?
+48  LE16   ?                0x0C80 en NPCs hablables, 0 en objetos
+50..62      relleno en cero
```

**Evidencia del `npc_type_id`:** Aurora Totem=1937, Iron Totem=1939,
Dark City Totem=1938 (consecutivos), Angels' Tutor=1895 (dentro del bloque
1892-1916 de los NPCs guia del tutorial segun npc.xml).

**No contemplado en el codigo actual:** `Slarm` y `Lily` traen `@40 = 1`
en lugar de 200 y sprites de otro rango. Son casi con certeza **personajes
de otros jugadores**. 0x0008 sirve para NPCs y jugadores, con `@40` como
discriminador.

### Correccion a `src/area_entity_data.py`

El archivo documenta `runtime_id = hi-word fijo + lo-word incremental`,
citando `0x13b00e85` y `0x127f0d54`, e implementa `_next_entity_id = 0x12341000`.

**El corpus no respalda eso.** 17.743 entity_id medidos: rango
`0x00000001..0x000038AD`, **0% por encima de 0xFFFF**, hi-word siempre 0x0000.

Matiz honesto: todas esas muestras son del servidor privado
(IP.DEL.SERVIDOR.PRIVADO). El corpus **no tiene ni una muestra del servidor de IGG**
-- esas conexiones fueron todas RST. Los valores `0x13b0`/`0x127f` no se
pueden confirmar ni refutar desde aqui; provienen de otra fuente.
Pendiente de resolver con el pcapng.

---

## 8. Servidor de IGG: cifrado real, descifrado  [PROBADO]

El pcapng de 499 MB contiene **una sesion completa de produccion de IGG**
(`209.151.154.242:24131`). Del clasificador estructural: es el UNICO endpoint
del pcap con protocolo AO (91,4% explicado); el resto del archivo es trafico
personal no relacionado y no se inspecciono.

A diferencia del servidor privado, **IGG usa cifrado real**. La clave viaja
en el Hello:

```
14 00 | 10 00 00 00 | 05 3d 11 03 d2 76 94 76 2c 20 f7 3a 4c 2d df 31
 |        |            |
 |        key_len=16   clave de sesion de 16 bytes
 sub_len=20
```

Aplicando esa clave:

| direccion | cifrador | checksums validos |
|---|---|---|
| S -> C | `CryptXOR` (clave fija) | **148.754 / 148.754 = 100,0%** |
| C -> S | `CryptXORIV` (clave evolutiva) | **1.176 / 1.176 = 100,0%** |

Resultado: **409.545 sub-mensajes de IGG descifrados**, incluido el flujo de
login completo (`0x0002 LOGIN_REQ`), que hasta ahora tenia solo 3 muestras.

**Aviso de privacidad:** `0x0002` transporta credenciales de cuenta. El
corpus guarda su tamano y metadatos, **nunca su contenido** (ver `SENSIBLES`
en `tools/build_corpus2.py`).

La segunda sesion del pcap (`67931_s2c` + `77876_c2s`) empieza a mitad de
conexion, sin Hello. Su clave se desconoce y queda sin descifrar.

## 9. entity_id: el esquema es libre  [RESUELTO]

| servidor | rango | > 0xFFFF |
|---|---|---|
| privado (IP.DEL.SERVIDOR.PRIVADO) | 0x00000001..0x000038AD | 0% |
| IGG (209.151.154.242)   | 0x72D90153..0xE1F705E2 | 100% |

Los dos esquemas conviven y **el mismo cliente acepta ambos**. Por lo tanto
el servidor elige libremente como asignar entity_id.

Matiz: en IGG el hi-word **no** es fijo (0x72F3, 0x731C, 0x72DA, 0xDE9F,
0xDE02...), asi que la descripcion "base fija + contador" de
`src/area_entity_data.py` no se sostiene ni siquiera para IGG. Pero como el
esquema es libre, es una imprecision de documentacion, no un bug.

## 10. Diferencia de version de protocolo  [OBSERVADO]

`0x0008 NPC_SPAWN` mide **62 bytes en IGG** y **63 en el servidor privado**.
Los dos servidores no corren la misma revision del protocolo. Al portar
estructuras entre capturas, verificar de cual servidor provienen.

## 0x0006 es ENTRAR AL MUNDO, y el redirect es su respuesta

Durante mucho tiempo el cliente se congelaba en "Enter game" sin abrir nunca
la conexion de mundo. El bloque de cuenta era correcto byte a byte, la clase,
el mapa, las ranuras y el equipo coincidian con una captura real, y aun asi
no pasaba nada. El error no estaba en ningun byte: estaba en **cuando**.

El servidor mandaba el REDIRECT (sub-mensaje 0x0004) junto con la respuesta al
0x0002 AUTH. El cliente lo recibe en un momento en que todavia no pidio entrar,
lo descarta, y despues se queda esperando una respuesta que ya paso.

La secuencia correcta es:

    C -> S  0x0002  AUTH
    S -> C  0x0000  bloque de cuenta (3 ranuras)
    C -> S  0x0003  crear personaje            (opcional)
    S -> C  0x0001  ficha creada
    C -> S  0x0006  ENTRAR AL MUNDO            <-- aca
    S -> C  0x0004  REDIRECT ip:puerto         <-- y la respuesta aca
    C ->    conexion nueva al puerto de mundo

Cuerpo del 0x0006 (37 B observados):

    +0   LE32  indice de ranura elegida
    +4   ASCIIZ ruta del sprite del personaje, p.ej. "\chr\i263g\20263_Wait.spr"

La ruta del sprite viene de la apariencia que el servidor mando en el bloque de
cuenta. Con la apariencia en cero el cliente no puede armarla y manda basura,
que es lo que explica los 0x0006 con contenido sin sentido que veiamos antes.

Como login y mundo son dos conexiones TCP distintas, el 0x0006 es ademas el
unico momento en que el servidor se entera de QUE personaje eligio el jugador.
Hay que anotarlo antes de mandar el redirect; la conexion de mundo llega desde
la misma IP con otro puerto de origen.

Verificado en loopback: AUTH devuelve solo 0x0000, el 0x0006 devuelve 0x0004,
y la sesion de mundo levanta el personaje de la ranura pedida.

### Punto de aparicion: pendiente de medicion

El mapa inicial 51 esta confirmado: `stage.name` en content.db dice
"Guide Palace", que es el lugar de las capturas de pantalla. El TILE dentro de
ese mapa NO esta confirmado. La cabecera de map/map051.mpc ("MAP\0", LE32 ancho,
LE32 alto, LE32 32, LE32 32) da 371x156 tiles, asi que (0,0) es la esquina y
casi seguro no se puede caminar ahi. Se usa el centro (185,78) como valor
provisional, deducido del tamano del mapa y no medido de ningun servidor.
Se cambia con AO_TILE=x,y sin recrear el personaje.

## El spawn real de Guide Palace es el tile (82,83) -- medido

Correccion de lo anterior: el centro geometrico (185,78) era un valor
provisional mio y estaba mal. La ficha 0x0002 que el servidor privado le
mandaba a un personaje recien creado trae, en +8 y +12, tile=(82,83).

Los tres NPC_SPAWN (0x0008) de esa misma captura son los del tutorial:

    entity=20  Interface Tutor  tile=(80,85)  sprite=40002  npc_type=1916
    entity=19  Angel Raphael    tile=(88,87)  sprite=40003  npc_type=1892
    entity=21  Angel Aide       tile=(96,85)  sprite=40052  npc_type=1893

Distancia del spawn real al NPC mas cercano: 2 tiles. Del spawn provisional
que yo habia puesto: 97 tiles. Por eso el jugador aparecia solo en un patio
vacio -- los NPCs se enviaban (estan en la plantilla y el cliente los
registraba: en el log pedia informacion de las entidades 20 y 21 con 0x0016),
pero quedaban fuera del rango de dibujado.

HP y MP de un personaje de nivel 1 recien creado, leidos de esa ficha:
296/296 y 218/218. En la ficha son cuatro LE32 consecutivos en +102, +106,
+110 y +114 (los primeros 16 bytes del campo 'stats', que arranca en +102).
Antes se mandaban los de la plantilla sin tocar, o sea los del personaje de
otro servidor; ahora salen del personaje del jugador.

## Lo que todavia NO esta identificado

- **Inventario y equipo.** Se probo la hipotesis de que 0x0064 (19.460 B) fuera
  el inventario: (19460-4)/76 = 256 entradas exactas, pero interpretando el
  primer LE32 de cada entrada como item_id solo el 11% cae en un id valido de
  item.xml, que es lo que da el azar con una tabla de 29.998 ids. Descartado:
  no alcanza para afirmar nada. Hay que buscar el handler en el binario.
- **Set de Student inicial.** Los items existen en item.xml: 26 Students'
  Uniform, 28 Students' Gloves, 30 Students' shoes. Falta el mensaje que los
  entrega.
- **Item mall.** La tabla shop tiene 226 filas; falta el mensaje de catalogo.
- Candidatos c2s sin esquema vistos en sesion real: 0x0012 (4 B, "02 00 14 00",
  donde 0x14=20 es el entity_id del Interface Tutor: probablemente interaccion
  con entidad), 0x0016 (pide datos de una entidad), 0x000F (latido cada 5 s,
  el segundo campo sube de a 65536), 0x012D y 0x014B (0 B).

## La captura del mundo NO era solo la entrada

Correccion importante sobre server/plantillas/mundo_real. Los 129 mensajes que
se guardaron como "secuencia de entrada al mundo" son dos cosas pegadas:

    indices  0..34   la entrada de verdad, termina en 0x0027
    indices 35..128  las RESPUESTAS a lo que fue haciendo el jugador grabado

Del 35 en adelante se repite el patron 0x006D (ack vacio, 0 bytes) + a veces
0x0016 (5 B: LE32 entity_id + U8 direccion) + 0x0005 ENTITY_MOVE, una vez por
cada movimiento. Los 27 ENTITY_MOVE son TODOS de la entidad 92, que es el
personaje que se grabo. Mandarlos al entrar era anunciar los movimientos de
una entidad que en este servidor no existe.

Ahora se mandan solo los 35 primeros. Los tres NPC_SPAWN, la ficha, la barra
de habilidades y las tablas siguen dentro. Con AO_SECUENCIA_COMPLETA=1 se
manda todo, por si hiciera falta comparar.

## Como descifrar el sentido cliente->servidor en una captura

El cliente cifra con clave EVOLUTIVA: despues de cada paquete, cada DWORD de
la clave se le suma la longitud con relleno. Aunque la clave base sea cero (y
entonces el primer paquete va en claro), a partir del segundo ya no lo esta.
Por eso un lector que use XorStatic solo logra parsear el primer frame del
stream c2s y descarta el resto. Hay que usar XorEvolving y descifrar EN ORDEN,
con un cifrador por sentido. Hecho asi, los 58 frames de la captura real
parsean al 100%.

## Que manda el cliente al hacer clic en un NPC

    c2s 0x0012, 4 B: 02 00 14 00   ->  [LE16 2][LE16 entity_id]  (0x14 = 20,
                                       el Interface Tutor)

El cliente lo manda tanto contra el servidor privado como contra este. La API
de red del cliente se ve en los scripts Lua (data1/script/*.l, bytecode 5.1):
game.netcommand{dwID=..., dwCmdID=..., dwParam=..., pParam=...}, que encaja
con esa forma de [comando][parametro].

Lo que el servidor contesta NO esta establecido. En la captura hay una rafaga
de 0x0012 s2c de 9 B ([LE32 id][LE32 valor][U8]) con ids 5240..5253 y valor 2,
pero no se puede afirmar que sea la respuesta: el proxy guardaba cada sentido
en un archivo distinto y sin marca de tiempo, asi que no hay forma de
correlacionar. Un intento de correlacion por conteo dio 6 movimientos del
cliente contra 19 del servidor antes del mensaje, lo que no prueba ni refuta
nada porque el servidor puede emitir varios ENTITY_MOVE por cada pedido.
Ademas esos ids son el estado de un personaje ajeno, con progreso: replicarlos
seria inventarle avances al jugador.

Para resolverlo, el proxy ahora escribe logs/proxy/<sesion>_orden.jsonl con
los dos sentidos mezclados y con marca de tiempo, y tools/correlacionar.py
muestra que contesto el servidor despues de cada pedido.

## Dialogo con los NPC -- resuelto

Se resolvio con una captura del servidor privado que lleva marca de tiempo en
los dos sentidos (el proxy ahora escribe *_orden.jsonl; tools/correlacionar.py
lo lee). Con los .bin separados por sentido era imposible.

    C -> S  0x0005  [LE32 entity_id][LE16 0]     clic en el NPC
    C -> S  0x0007  [U8 direccion]               el personaje se gira
    S -> C  0x0012  primera linea                140-150 ms despues
    C -> S  0x000B  [U8 01]                      "siguiente"
    S -> C  0x0012  linea siguiente
      ...
    S -> C  0x0012  nueve ceros                  cierra el cuadro

Linea de dialogo (0x0012):

    +0  LE32  id del texto        el texto NO viaja: vive en el cliente
    +4  LE16  valor               3 Raphael, 2 Interface Tutor, 52 Angel Aide
    +6  U8    cuantas cadenas van detras
    +7  U8    cuantas opciones de menu van detras
    +8  U8    0
    +9        las cadenas (terminadas en NUL) y despues las opciones (LE32)

Guion medido en Guide Palace, guardado en
server/plantillas/dialogos_guide_palace.json:

    entidad 19  Angel Raphael    5001 5002 5003 5004 5005
    entidad 20  Interface Tutor  5240 5243 5244 ... 5253   (5240 ofrece menu)
    entidad 21  Angel Aide       5022

Son textos del tutorial, iguales para cualquier personaje nuevo: no es
progreso de nadie. Lo unico que se cambia es el nombre del jugador, que va
como parametro en la primera linea de Angel Raphael.

Los seis mensajes nuevos pasan el roundtrip byte a byte contra el corpus:
0x0003 (1928), 0x0005 c2s (5021), 0x0007 c2s (15058), 0x000B c2s (16),
0x0016 s2c (2075) y 0x0012 (19).

## Lo que sigue faltando, y que hace falta para resolverlo

En la captura, al terminar el dialogo de Angel Raphael el servidor manda
0x001D (un atributo, kind 12, en cero) y 0x0003 colocando al jugador junto al
NPC. NO aparece ningun mensaje que abra la ventana de eleccion de clase, y en
esa sesion el jugador no llego a elegir ninguna. Por eso el dialogo termina y
no pasa nada mas.

Para cerrar la eleccion de clase, los items que se entregan con ella, la ropa
de Student que falta y el traslado a la zona de los baby slarms hace falta UNA
captura que llegue hasta el final:

    python tools/proxy.py --server-xml "G:/Play Angels Online/server.xml"
    (personaje NUEVO; hablar con Angel Raphael, abrir la ventana de clases,
     elegir una, confirmar, y dejar que el tutorial siga hasta el traslado)
    python tools/proxy.py --server-xml "G:/Play Angels Online/server.xml" --restaurar
    python tools/correlacionar.py

Con eso quedan a la vista, en orden y con tiempos, el mensaje que abre la
ventana, el que confirma la clase, el que entrega los items (que es el mismo
que falta para el inventario y para poder equipar) y el del traslado.

## Equipar y desequipar

CORRECCION de lo escrito mas arriba: el 0x0012 del CLIENTE no es hablar con un
NPC. Se confundio porque su cuerpo "02 00 14 00" aparecia justo despues de
hacer clic cerca de un NPC, y 0x14 = 20 coincidia con el entity_id del
Interface Tutor. Con una captura con marca de tiempo quedo claro que lo que el
servidor contesta no es un dialogo:

    C -> S  0x0012  [LE16 ranura_origen][LE16 ranura_destino]   mover un item
    S -> C  0x001B  131 B, el contenido del contenedor
    S -> C  0x0042  105 B, los stats ya recalculados
    S -> C  0x001D  dos veces, la apariencia (el sprite cambia de ropa)

Ranura 2 = el cuerpo, ranura 20 = la primera del inventario. Mover 2 -> 20 es
quitarse la ropa y 20 -> 2 ponersela. Se comprueba solo en el 0x0042.

El 0x0042 arranca igual que el campo 'stats' de la ficha 0x0002 (que empieza
en +102), lo que encaja con la nota vieja de que "+102..+206 es el bloque de
0x0042":

    +0   LE32  hp        296
    +4   LE32  hp_max    296
    +8   LE32  mp        218
    +12  LE32  mp_max    218
    +16  LE16  0
    +18  LE16  2000
    +20  LE32 x N   los stats, uno cada 4 bytes

El stat de indice 4 (+20+16 = +36, o sea +138 de la ficha) pasa de 5 a 15 al
equipar la ropa: son los mismos 15 que el cliente muestra como Dfs. Esto ya
habia aparecido al buscar donde estaban los stats en la ficha, y ahora queda
confirmado desde otro angulo.

Dialogo y equipo comparten el opcode 0x0012 en sentidos distintos: del
servidor es una linea de dialogo, del cliente es mover un item. No es raro en
este protocolo -- ya pasaba con 0x0005 (ENTITY_MOVE del servidor, hablar con
un NPC desde el cliente) y con 0x0007.

### Lo que NO quedo resuelto del 0x001B

El formato interno. Son registros de longitud variable y al mover un item la
lista entera se reordena: el tramo "01 54 57 6e 64 ec b9 ac 6a 1a" aparece en
+12 con la ropa quitada y en +4 con la ropa puesta, desplazado 8 bytes. Se
identificaron dos registros que llevan el item 0x1374 (4980, "Swordsman Lucky
Bag" en item.xml, que es la caja de clase) y un tercero sin identificar, pero
no el esquema completo.

Por eso server/equipo.py NO construye el mensaje: reproduce los dos estados
tal como los mando el servidor real, reescribiendo el entity_id. Alcanza para
la ropa inicial, que es lo unico que tiene un personaje recien creado, y no
alcanza para nada mas. Con una captura que tenga varios items distintos en el
inventario se puede deducir el formato y construirlo de verdad.

## Bug del proxy: no reensamblaba el stream

La primera captura perdio cuatro bloques de entre 4 y 5 KB -- los mas grandes,
entre ellos 0x0064 y 0x0155. La causa: el registro cronologico procesaba cada
trozo que devuelve recv() como si fuera un frame completo, y un frame partido
entre dos lecturas TCP se descartaba. Ya acumula por sentido y consume solo
frames enteros. Leidos desde el .bin, esos mismos bloques parsean sin
problema, asi que ninguna captura vieja se perdio.

## El kit inicial, identificado en item.xml

Corrigiendo lo anterior: el item 4980 que aparece en el 0x001B capturado es
"Swordsman Lucky Bag", pero NO es la caja de la que hablaba el jugador. Las
suyas son otras dos, y se identificaron cruzando el tooltip del cliente contra
item.xml campo a campo:

    1948   Newborn Gift Box        peso 10, nivel 5, no comerciable, no
                                   almacenable, "Gift box for Warrior player"
    20103  Level 1-10 Growth Box   peso 10, nivel 1, no comerciable, no
                                   almacenable, "Requires 7 free slots"

Los seis campos coinciden en los dos items, incluida la lista completa de lo
que suelta el Growth Box. La unica diferencia son los nombres: el cliente dice
"Spell Learning" donde item.xml dice "Spell Practise Hint", porque la tabla
salio de UPDATE13 y el cliente instalado es posterior. Mismo item.

La Newborn Gift Box cambia segun la clase, que es lo de "una caja por clase":

    1944  Archer y Productor      1948  Guerrero      1952  Mago

Ropa inicial: 26 Students' Uniform (equipada, +10 de defensa), 28 Students'
Gloves, 30 Students' shoes.

Queda anotado en server/personajes.py, pero TODAVIA NO SE ENTREGA: para eso
hace falta poder construir el 0x001B, y hoy solo se saben reproducir los dos
estados capturados.

### La captura que falta

Un personaje NUEVO, con el proxy puesto, desde el login hasta pasada la
eleccion de clase, moviendo dos o tres items entre ranuras distintas. Eso da
de una sola vez:

  - el 0x001B de un inventario con varios items DISTINTOS, que es lo unico que
    permite separar los campos del registro (con un solo item repetido en dos
    posiciones no se puede: no hay con que contrastar)
  - el mensaje que abre la ventana de eleccion de clase
  - el que confirma la clase elegida
  - el que entrega la caja y el resto del kit
  - el traslado a la zona de entrenamiento

## CORRECCION: 0x1374 no es un item, es el char_id

Mas arriba se dijo que el 0x001B llevaba el item 4980 "Swordsman Lucky Bag".
Es falso. 4980 es el char_id del personaje: el mismo numero llega en los
0x0040 y 0x0027 del arranque de la sesion. Se leyo como item_id, item.xml
devolvio un nombre plausible, y sobre eso se construyo la idea equivocada de
que el inventario capturado ya tenia una caja. Nunca la tuvo. El error lo
marco el jugador antes de que apareciera por analisis.

Leido bien, el 0x001B se compone de tres clases de bloque:

    [U8 01][8 bytes id de instancia][LE32 item_id]   un item
    [U8 01][LE32 char_id][LE16 ranura]               la ranura que lo recibe
    [U8 02][U8 01][LE32 char_id][LE16 ranura]        la ranura que se vacia

Con eso los dos estados se leen enteros y de forma coherente:

    puesto   +4 item 26 (inst 54576e64ecb9ac6a)  +37 destino r2  +123 origen r20
    quitado  +4 origen r2  +12 item 26 (misma inst)  +45 destino r20

Es decir: el 0x001B no describe el contenido del contenedor sino UN
MOVIMIENTO. Y el item es el 26, Students' Uniform, con lo que queda confirmado
que el servidor privado si entrega la prenda del set de Student.

Lo que falta para construirlo: la regla que decide en que offset del buffer de
131 bytes va cada bloque. Cambia entre los dos casos y con una sola prenda no
hay con que deducirla.

Leccion de metodo, por segunda vez en este proyecto: que un numero devuelva
una fila de la base de datos no prueba que sea una clave de esa tabla. Con
30.000 ids, casi cualquier entero pequeno "existe". Antes de darlo por bueno
hay que buscar ese mismo numero en el resto del trafico -- aca aparecia en
0x0040 y 0x0027, que no tienen nada que ver con items.

## Inventario: resuelto, y ahora se CONSTRUYE

Con una captura en la que el jugador paseo la misma prenda por 26 ranuras
distintas quedo a la vista la regla que faltaba. El 0x001B ordena sus bloques
por NUMERO DE RANURA ascendente, no por origen y destino:

    origen < destino:   vacia@+4    item@+12   recibe@+45
    origen > destino:   item@+4     recibe@+37  vacia@+123

Los 26 movimientos cumplen la regla sin excepciones. El generador de
server/inventario.py reconstruye los 26 mensajes reales byte a byte, asi que
ya no se reproducen estados capturados: se arma el mensaje para cualquier par
de ranuras.

Offsets de cada campo:

    caso asc    char_id +6   ranura_vacia +10  instancia +13
                item_id +21  char_id +46       ranura_destino +50
    caso desc   instancia +5  item_id +13      char_id +38
                ranura_destino +42             char_id +125  ranura_vacia +129

Los stats (0x0042) solo se mandan cuando cambia lo que el personaje lleva
puesto: de los 26 movimientos, solo los 2 que tocan la ranura 2 lo traen.

Queda pendiente calcular los stats de verdad. Hoy se reproducen los dos
estados medidos (con ropa y sin ropa), que alcanza mientras el unico equipo
sea la prenda inicial. Con mas de una pieza habra que sumar los bonus de
item.xml.

## La ventana de eleccion de clase no la abre el servidor

En las tres capturas, al terminar el dialogo de Angel Raphael el servidor
manda 0x001D (un atributo, kind 12) y 0x0003 colocando al jugador junto al
NPC, y nada mas. No hay ningun mensaje que abra la ventana.

La explicacion que encaja: el texto del dialogo trae "[career subject]"
marcado como enlace (se ve en otro color en el cliente), y al pulsarlo el
cliente abre la ventana por su cuenta. El texto vive en el cliente, no viaja
por la red, asi que el enlace tambien es cosa suya. Falta comprobarlo
pulsando ese enlace contra el servidor local.

Lo que si tiene que viajar es la CONFIRMACION de la clase elegida, y eso
todavia no se capturo.

## La ventana de eleccion de clase: donde esta y que falta

Esta definida en el cliente, en setting/eng/wnd04.xml:

    <window class="WND_CLASS_DLG_1" id="13300" range="100,100,655,388"
            title="Choose profession skills">     <!-- 選擇職業技能 -->

Es nativa del cliente, no de los scripts Lua. En tuition.l hay un
TuitionEventFirstChooseClass, pero ese script es el sistema de cartelitos de
ayuda del tutorial, no la ventana.

En las TRES capturas del servidor privado, al terminar el dialogo de Angel
Raphael el servidor manda 0x001D (un atributo, kind 12) y 0x0003 colocando al
jugador junto al NPC, y nada mas. Ningun mensaje abre la ventana 13300.

Hipotesis descartada: que el cliente la abriera solo al pulsar el enlace
"[career subject]" del texto. Se probo contra el servidor local y no se abre.

Queda abierto de donde sale el disparador. Lo que hace falta es una captura en
la que la ventana SE ABRA de verdad. Si tampoco se abre en el privado, la
explicacion probable es que ese servidor haya desactivado la eleccion de clase
del tutorial, igual que quito las cajas de regalo del kit inicial, y entonces
habria que buscar el dato en otra parte.

## Bug: el inventario no persistia

La sesion de MUNDO es otra conexion TCP y no pasa por el handler de login, asi
que no tenia ses.usuario. El guardado comprobaba ese campo antes de escribir,
lo encontraba vacio y no hacia nada -- sin error, sin aviso. Al reconectar
todo volvia a su sitio.

Se arregla poniendo ses.usuario al entrar al mundo, que es donde ya se sabe de
que cuenta viene la conexion (se resuelve por IP contra self.pendientes).
Comprobado: se deja la ropa en la ranura 33, queda {"33": 26} en cuentas.json
y al reconectar el servidor manda el 0x001B que la vuelve a poner ahi.

Nota sobre como se detecto tarde: la primera prueba dio "no persiste" pero el
servidor de prueba ni siquiera habia arrancado -- el puerto estaba ocupado y
el cliente de prueba se conecto a una instancia vieja. Conviene comprobar que
el servidor arranco antes de creerle a una prueba que falla.

## Las ranuras de equipo no son solo la del cuerpo

El juego tiene mochilas equipables (y podria tener capas con ranuras), asi que
el equipo son varias casillas y la mochila puede crecer. El codigo no cablea
la ranura 2: usa es_equipo(ranura), que hoy es "menor que 20" porque la 20 es
la primera casilla del panel Prop. Eso ultimo es inferencia, no medicion: la
unica ranura de equipo vista en el trafico es la 2.

## 0x001A es el inventario completo -- y con eso ya se pueden entregar items

Aparecio buscando otra cosa: el modo --novedades de tools/correlacionar.py lo
marco como no visto y su contenido tenia la misma pinta que el 0x001B.

    +0   LE32  contenedor (2)
    +4   una entrada de 86 bytes por item
    ...  una cola de 33 bytes en cero

Cada entrada:

    +0   U8    01
    +1   8 B   id de instancia
    +9   LE32  item_id
    +33  U8    01
    +34  LE32  char_id
    +38  LE16  ranura
    +51  U8    0x21 en la prenda equipable, 0 en el oro

El inventario capturado dice entonces: item 1 (Gold) en la ranura 0 e item 26
(Students' Uniform) en la ranura 2. Y 4 + 86*2 + 33 = 209, que es exactamente
lo que mide el mensaje real. Reconstruido con las instancias originales sale
IDENTICO byte a byte.

Con esto se cierra lo que faltaba: el 0x001B solo MUEVE items, el 0x001A los
DECLARA. El kit inicial ya se entrega (26 puesta, 28 y 30 en la mochila, y la
20103 Level 1-10 Growth Box).

Ranuras conocidas: 0 = el oro, 2 = el cuerpo, de la 20 en adelante la mochila.

SIN COMPROBAR: que el tamano sea 4 + 86*N + 33 para cualquier N. Solo se vio
con N=2, porque el personaje capturado tenia dos items. Con cinco da 467 bytes
y el cliente tiene que aceptarlo; si no lo hace, el fallo va a estar aqui.

## Eleccion de clase: la ventana la abre el CLIENTE, no el servidor

En la captura pasan 3,5 segundos entre que se cierra el dialogo de Angel
Raphael (el 0x0012 de ceros) y que llega la eleccion, sin un solo paquete en
medio. O sea que el cliente abre la ventana 13300, muestra las catorce clases
y espera, todo por su cuenta. El servidor no la abre ni puede abrirla.

Lo unico que viaja es la confirmacion:

    C -> S  0x003A  [U8 skill_id] x 6 + 3 bytes en cero

Para Swordsman llegaron 9, 12, 13, 15, 16 y 33. En setting/eng/skill.xml,
donde el atributo 編號 es justo ese skill_id, son Sword, Enhance, Grapple,
Reserve, Finesse y Garment: los seis que el cliente muestra en pantalla.
Tambien encajan con level.xml leyendo skill_id + 1 como indice de columna, que
es lo que ya decia la nota vieja de la ficha.

El servidor contesta por cada habilidad un 0x000D y un 0x0042:

    0x000D  [LE16 id_mensaje][U8 tipo][nombre NUL][2 ceros]
            id 333 habilidad, 425 hechizo, 492 item.  tipo 7 / 0

El generado sale identico byte a byte al real.

Despues manda 0x001C (1008 B, el arbol de habilidades), tres 0x000D mas con
los hechizos iniciales y los items de regalo con su 0x001B.

PENDIENTE: los stats de la clase. skill.xml trae los bonus de cada habilidad
(Enhance da +2 de defensa y +2 de constitucion, Grapple +4 de precision) y el
texto de ayuda lo confirma, asi que se pueden calcular. Todavia no se hace.

## Por que no aparecia la ventana: faltaba el 0x001D

Al cerrar cada dialogo el servidor real manda un atributo de entidad: kind 12
con valor 0. Esta en las cuatro capturas, tanto al entrar al mundo como al
terminar cada conversacion, y este servidor no lo mandaba.

Ademas, los 0x001D de la secuencia de entrada se enviaban con el entity_id del
personaje que se grabo, no con el del jugador: se estaban anunciando los
atributos de una entidad ajena. Ahora se reescriben.

## Regresion: entregar cinco items rompio el inventario

Se entrego el kit completo (26 puesta, 28, 30 y la 20103 en la mochila) dando
por bueno que el 0x001A midiera 4 + 86*N + 33 para cualquier N. Con cinco
items el cliente dejo vacias en pantalla las ranuras 20, 21 y 22 mientras el
servidor las creia ocupadas, asi que de las cinco entradas no leyo todas.

Revertido a las dos comprobadas (oro y ropa). La hipotesis del tamano era
deduccion, no medicion: solo se habia visto con N=2. Probablemente falte un
campo que diga cuantas entradas vienen -- la cabecera de 4 bytes vale 02 00
00 00 en las dos capturas y se leyo como "contenedor 2", pero con solo dos
items no se puede distinguir un numero de contenedor de un contador.

## CORRECCION del 0x001A: la cabecera es un contador y las entradas varian

Lo escrito antes estaba mal en dos puntos, y los dos se debian a haber mirado
un solo inventario de dos items.

    +0   LE32  CUANTAS ENTRADAS VIENEN     (no un "id de contenedor")
    +4   las entradas, de TAMANO VARIABLE  (no 86 fijos, y no hay cola)

    entrada de item corriente:  86 bytes
    entrada de item equipable: 119 bytes   (33 mas)

    +0 marca 01   +1 instancia 8 B   +9 item_id LE32
    +33 marca 01  +34 char_id LE32   +38 ranura LE16   +40 cantidad LE32

Comprobado con los dos inventarios capturados:

    2 items:  4 + 86 + 119              = 209
    8 items:  4 + 86 + 119*5 + 86*2     = 857

De donde salio el error: con dos items la cabecera valia 2 y habia dos
entradas, asi que se leyo como un numero de contenedor; y los 33 bytes de mas
de la prenda equipable se tomaron por una cola del mensaje, con lo que las
cuentas cuadraban igual. Al entregar cinco items el cliente dejo de leer donde
correspondia y quedaron ranuras vacias en pantalla que el servidor creia
ocupadas. Dos interpretaciones distintas producen los mismos bytes cuando solo
hay un caso; hacia falta un inventario con mas items, y ninguna relectura del
que ya habia lo iba a resolver.

Lo escondio ademas un detalle propio: el proxy guardaba solo los primeros 256
bytes de cada mensaje en el registro cronologico, y el inventario de ocho
items mide 857. Ya guarda 4096.

Inventario de un personaje recien creado: oro en la ranura 0 (cantidad 0) y
Students' Uniform en la 2. Ranuras vistas: 0 oro, 2 cuerpo, 3 y 4 manos,
5 guantes, 6 zapatos, 20 en adelante la mochila, 95 y 96 objetos de guia.

## Lo que da la eleccion de clase

Leido del inventario capturado justo despues de elegir Swordsman: dos Sabre
(item 10) en las ranuras 3 y 4, Students' Gloves (28) en la 5 y Students'
shoes (30) en la 6. El arma depende de la clase y solo esta medida la del
Swordsman.

El bloque de cuenta de ese personaje trae class_id = 5 en el slot (+5).
ATENCION: en setting/eng/class.xml el 5 es "Protector" y el Swordsman seria el
7, asi que o ese campo no indexa esa tabla o significa otra cosa. Se usa el
valor medido, no el de la tabla.

Estructura del slot, corregida: +1 nivel, +5 clase, +9/+10 apariencia,
+11 stage, +31 char_id LE32, +35 nombre.

Mapa del tutorial de combate: stage 57, "Fighting Palace" en content.db.

## Los stats se calculan, ya no se copian

El array que empieza en +20 del 0x0042 alterna valor base y valor efectivo:

    idx 0  ataque base    idx 1  R.Atk    idx 2  L.Atk
    idx 3  defensa base   idx 4  Dfs

El efectivo es el base mas lo que suma cada pieza puesta, y los bonus estan en
item.xml: la prenda 26 da def 10, los guantes 28 def 3 y accuracy 6, los
zapatos 30 def 3 y agility 5, y cada Sabre (10) atk_avg 26 y accuracy 1.

Verificado contra la sesion capturada, donde los saltos aparecen uno a uno:
la defensa va de 12 a 28 (+10 prenda, +3 guantes, +3 zapatos) y cada mano sube
27 al empunar su Sabre. El calculo propio reproduce esas mismas diferencias.

Los totales absolutos todavia no coinciden porque las BASES no se calculan: al
elegir clase, las habilidades suben la base (la defensa base pasa de 5 a 12 a
lo largo de la eleccion) y eso no esta implementado. skill.xml trae esos bonus
por habilidad.

## Lo que sigue sin resolver

- **Que clase resulta de unas habilidades.** El jugador puede MEZCLAR
  habilidades de distintas clases, asi que no hay una lista fija de seis por
  clase: el servidor deduce la clase de la combinacion, y esa regla no esta
  identificada. class.xml solo trae id y nombre.
- **El class_id del slot.** Vale 5 para un personaje que el jugador confirma
  como Warrior, y Warrior en class.xml es el 6, asi que el campo parece ir
  desplazado uno. Con un caso no alcanza, y queda sin explicar que un
  personaje sin clase lleve 0.
- **Las bases de los stats** segun habilidades y nivel.
- **El arbol de habilidades** (0x001C, 1008 B): capturado, sin analizar.
- **El arma que da cada clase**: solo esta medida la del Swordsman.

## CORRECCION del bloque de cuenta: donde va el equipo y donde las habilidades

El bloque capturado de un personaje CON clase y equipo aclara dos campos que
estaban mal documentados.

Lo que la documentacion previa llamaba "[479-586] arreglos de EQUIPO, 9 LE32
por ranura" y se dejaba en cero son en realidad las HABILIDADES: ahi estan las
seis del personaje (9, 12, 13, 15, 16, 33), una cada cuatro bytes.

El equipo va DENTRO del slot, cinco LE32 desde +81, en este orden:

    +81 cuerpo   +85 mano derecha   +89 mano izquierda   +93 guantes   +97 pies

En el bloque real: 26, 10, 10, 28, 30. Por eso el personaje aparecia desnudo
en la pantalla de seleccion aunque llevara la ropa puesta.

Resto del bloque confirmado: class_id en el slot +5, char_id LE32 en +31,
nombre en +35, hp_max y mp_max en los arreglos +455 y +467 del array.

El bloque generado ahora coincide con el real campo a campo.

## El atributo que habilita elegir clase es solo de Angel Raphael

Repasando las capturas por NPC, el 0x001D kind 12 aparece unicamente tras el
dialogo de la entidad 19, nunca tras el Interface Tutor (20) ni el Angel Aide
(21). Y deja de aparecer en cuanto el personaje ya tiene clase: en una misma
sesion se habla tres veces mas con Raphael y ya no se manda.

Mandarlo tras cualquier dialogo hacia que los tres NPC abrieran la ventana de
eleccion de clase. Ahora se manda solo tras Raphael y solo si el personaje no
tiene habilidades.

## Arma inicial por clase

Cruzando el nombre de la habilidad en setting/eng/skill.xml con la categoria
del item Freshman en item.xml:

    Staff Hit (8)  -> 19850 FreshmanWalking Stick   杖
    Sword     (9)  -> 19826 FreshmanSabre           刀
    Axe       (10) -> 19832 FreshmanStick           錘
    Spear     (11) -> 19838 FreshmanSpear           槍
    Shield    (14) -> 19820 FreshmanRound Shield    盾
    Longbow   (17) -> 19844 FreshmanCatapult        彈弓
    Mechanism (24) -> 19814 FreshmanCask            機甲
    Mantle    (32) -> 19856 FreshmanSharp Knife     影刃

El emparejamiento sale de los nombres, no de una captura. Lo unico medido es
el Swordsman, y ahi el privado entrego DOS armas (ranuras 3 y 4) y ademas dio
el item 10 "Sabre" en vez del 19826 "FreshmanSabre". Se usan los Freshman.

Las clases de produccion (Priest, Chef...) no tienen habilidad de arma y solo
reciben guantes y zapatos.

## La posicion ahora se guarda al salir

Las coordenadas del cliente van en pixeles y el tile mide 32: el 2640,2672
del primer movimiento da 82,83, que es justo el punto de aparicion de Guide
Palace. Al desconectar se guarda el ultimo tile, asi que al volver a entrar el
personaje aparece donde lo dejaron.

## Sigue sin resolver

- **Las opciones del dialogo.** El Interface Tutor ofrece "OK / No, thanks" y
  ninguna de las dos hace nada: las opciones viajan en el 0x0012 (n_opciones y
  los ids que van detras) y el cliente contesta con un 0x000B de valor
  distinto de 1 (se vio un 10), pero no esta implementado.
- **El arbol de habilidades** (0x001C, 1008 B): capturado, sin analizar. Las
  habilidades que NO se eligieron tienen que aparecer igual, en gris.
- **Borrar personaje**: el cliente se queda colgado. El mensaje no aparece en
  ninguna captura porque nunca se borro un personaje con el proxy puesto.
- **El avance de la quest** tras elegir clase, con el traslado al stage 57
  (Fighting Palace).
- **Las bases de los stats** segun habilidades y nivel.

## El arma freshman sale con resistencia 0/0

El tooltip que muestra el cliente se explica entero desde item.xml, asi que el
item es el correcto: 19832 FreshmanStick trae atk_avg 174 y atk_var 13 ("161-187
Attack"), accuracy 8 ("+8 Rigor"), crit_rate 1 ("+1 Beating rate"), nivel de
item 30 ("equivalent Level 30 item") y 43200 minutos de duracion ("Lasts 30
days"). Hasta el "Exceptional" sale del campo de color.

Lo unico que esta mal es la resistencia, que sale 0/0 y por tanto el arma
cuenta como rota. En item.xml esa columna es 耐久 y el FreshmanStick tiene 30.

Por que no se sabe donde va ese campo: las dos entradas equipables capturadas
son la prenda 26 y el arma 10, y NINGUNA de las dos tiene 耐久 en item.xml. Se
compararon byte a byte y resultaron identicas salvo instancia, item_id y
ranura, asi que sus 119 bytes no dicen nada sobre durabilidad. Hace falta una
captura con un item que si la tenga.

## El borrado de personaje sigue sin capturarse

El cliente avisa "This role will be deleted in 12 hours", asi que el borrado
es diferido, no inmediato. Pero el mensaje que manda al confirmar no aparece
en ninguna captura: en la unica sesion de login grabada el jugador entro
directo al mundo. Sin ese dato no se puede implementar.

## Opcodes vistos y aun sin identificar

    0x000C  c2s, 1 byte (se vio 05)
    0x001C  s2c, 1008 B, tras elegir clase: el arbol de habilidades
    0x0128  s2c, chat publico de otros jugadores
    0x0044  c2s, 11 B, al poner habilidades en la barra

## Durabilidad ("Hardiness"): offset +45 de la entrada

Encontrada comparando dos entradas equipables de la MISMA captura: el Cask
(item 584), que en item.xml tiene 耐久 = 180, lleva 180 en el offset +45; el
Sabre (10), que no tiene esa columna, lleva 0. Es el unico byte en que las dos
entradas difieren, aparte de instancia, item_id y ranura.

Por eso el arma freshman salia con "Hardiness 0/0" y contaba como rota: el
19832 tiene 耐久 30 y el servidor mandaba 0.

## Como se sabe si un item se lleva puesto

Antes se comparaba la CATEGORIA contra una lista escrita a mano, y se quedaba
corta: Stick, Spear, Catapult, Cask y Sharp Knife no estaban, sus entradas se
median como de 86 bytes en vez de 119 y a partir de ahi el mensaje entero se
desalineaba. La regla buena es mirar si item.xml le marca alguna ranura:

    右手裝備 左手裝備 頭部裝備 飾品裝備 身體裝備
    手部裝備 腳部裝備 背部裝備 寵物座騎裝備

Comprobado con el inventario de 16 items de un personaje de nivel 42: el
mensaje generado mide 1842 bytes, exactamente lo que mide el real.

## El borrado de personaje no se puede capturar en ese servidor

El cliente responde "The role is still in the protection period (%d hours %d
minutes %d seconds remaining), and cannot be deleted". O sea que el personaje
recien creado tiene un periodo de proteccion y el servidor privado rechaza el
borrado antes de mandar nada. Habria que reintentarlo con un personaje que
lleve creado el tiempo suficiente.

## Arma inicial: reglas de mano

    con Shield (14)      arma en la derecha + FreshmanRound Shield en la
                         izquierda. Es el Protector; el personaje de nivel 42
                         capturado lo confirma (Sword, Axe, Grapple, Shield,
                         Reserve, Garment -> Protector)
    Sword (9) o Mantle   dos armas iguales. Lo del Swordsman esta MEDIDO: el
                         servidor privado entrego dos Sabre, ranuras 3 y 4
    magia sin arma       FreshmanWalking Stick: las clases magicas no tienen
                         habilidad de arma cuerpo a cuerpo pero llevan baston
    produccion           nada: Chef y similares no tienen habilidad de arma

De todo esto lo unico medido es el Swordsman. El resto sale de cruzar los
nombres de skill.xml con las categorias de item.xml y de como funcionan las
clases; es una reconstruccion razonable, no un dato del servidor.

Con AO_DURABILIDAD se multiplica la durabilidad de todo lo que entrega el
servidor (AO_DURABILIDAD=100 deja el arma del kit en 3000 en vez de 30). Es
una palanca de este servidor, no del juego. Hoy no cambia nada porque no hay
desgaste implementado: la durabilidad no baja nunca.

## 0x001C: el arbol de habilidades

Sin este mensaje el panel de habilidades del cliente sale lleno de
interrogantes. No es que falten las elegidas: es que no conoce ninguna de las
otras treinta.

    +0    504 bytes en cero
    +504  36 registros de 14 bytes, uno por habilidad

Cada registro:

    +0   U8  skill_id
    +1   U8  nivel
    +3   U8  disponible
    +9   U8  categoria: la pestana del panel (Mana, Combat, Shoot, Mining,
             Craft). Vale 3, 4, 9 o 18
    +13  U8  orden: 1..6 en las seis elegidas, 0 en las demas

Las seis elegidas van primero y las otras treinta detras. El mensaje generado
para un Swordsman sale IDENTICO byte a byte al capturado. Se manda al elegir
clase y tambien al entrar al mundo, porque si no, al reconectar el panel
vuelve a quedar en interrogantes.

## La durabilidad tambien va en el mensaje de mover

El 0x001B la lleva en el mismo sitio relativo que el 0x001A: +45 del bloque
del item, o sea +57 en la disposicion ascendente y +49 en la descendente. Sin
eso, al equipar un arma el cliente la recibia con 0 y la mostraba rota en el
acto -- aunque siguiera pegando igual, porque el dano lo calcula el servidor y
la barra es solo cosa del cliente. El jugador lo noto: "parece que es visual
porque aun me sigue dando el dano que deberia dar".

## El tutorial de Angel Raphael, por etapas

Medido de una captura que recorre el tutorial entero. Cada tramo es una
conversacion completa; al terminarla el personaje pasa a la siguiente:

    0  5001..5005                          elegir clase
    1  5006, 5007, 5014..5018              da la ropa y ensena a equiparsela
                                           (5007 ofrece las opciones 5008/5009)
    2  5021, 5039..5043                    confirma y da 10 de oro
    3  5047                                confirma el examen; luego cambia de mapa

    Angel Aide: 5022 con las opciones 5045 (comprar) y 5046 (salir)

Pasada la ultima etapa se repite la ultima, que es lo que hace el juego: el
NPC sigue contestando en vez de quedarse mudo.

IMPORTANTE: el entity_id de los NPC CAMBIA entre sesiones. Angel Raphael fue
la entidad 19 en unas capturas y la 16 en otras. El guion va por nombre, no
por numero; identificarlos por entity_id solo funciona porque este servidor
manda siempre los mismos NPC_SPAWN de la plantilla.

La etapa se guarda en cuentas.json, asi que sobrevive al cierre.

## Lo que falta del tutorial

- Los tres hechizos iniciales. En la captura llegan como 0x000D con id de
  mensaje 425, y son los que el cliente pone en la barra F1..F3. No se mandan.
  Cuales son depende del arma. En magic.xml cada arma tiene sus tres registros
  de nivel 1 bajo su 技能限制1: lanza (槍術技能) son Basic Attack I, Bloody
  Song I y Endless Energy I, ids 801/802/803; espada (劍術技能) son Slicing
  Hit I, Swiftness Song I e Injury Cure I, ids 601/602/603. Verificado contra
  G:/extracted_paks/update26/setting/eng/magic.xml el 2026-09-18.
  La captura 1-skills-vacias.png es de un personaje de lanza.

  OJO con el nombre: en logs/proxy/mundo_103243_666191_s2c.bin el servidor
  privado manda "Slicing Chop I" y "Swiftness Song I" (offset 36631, cada uno
  precedido por 0d 00 a9 01 07 = msg_id 425, tipo 7). "Slicing Chop" no existe
  en ningun XML del cliente: en magic.xml la 601 se llama "Slicing Hit I". Ese
  servidor tiene la skill renombrada. Para el nombre canonico mandan los XML
  del cliente, no la captura; la captura vale para el formato del mensaje.
- La tienda del Angel Aide: el examen (Newbie Physical Examination File) por
  10 de oro. El mensaje de la tienda no esta identificado.
- El cambio de mapa al Fighting Palace (stage 57) al terminar el tutorial.
- Que el tutorial COMPRUEBE lo que pide: hoy avanza por hablar, no por
  equiparse la ropa ni por comprar el examen.

## Regresion: el Interface Tutor se quedo sin dialogo

Al pasar el guion a etapas se indexo por nombre con un diccionario que solo
tenia Angel Raphael y Angel Aide, y el Interface Tutor (entidad 20) quedo
fuera: el log decia "sin dialogo conocido" y el NPC no contestaba nada. Su
tramo estaba guardado desde la primera captura y se recupero.

## Recompensas del tutorial, por tramo

Los guantes y los zapatos NO van con la clase: el tutorial los entrega en el
tramo en que Angel Raphael dice "I will give you the uniform of the Angel
Lyceum, you will need to learn how to put it on". Y las diez monedas van en el
tramo siguiente, para comprar el examen.

    tramo 1  guantes (28) y zapatos (30)
    tramo 2  10 de oro

La cantidad de oro viaja en el 0x001A, en el campo de cantidad (+40) de la
entrada de la ranura 0.

## Lo que sigue sin hacer, y conviene decirlo claro

El tutorial AVANZA POR HABLAR, no por cumplir. No comprueba que el jugador se
haya equipado la ropa ni que haya comprado el examen: con darle a "siguiente"
pasa igual. Eso no es un fallo de protocolo, es logica de juego que todavia no
esta escrita.

Ademas faltan:

- **La tienda del Angel Aide.** La opcion "Buy the document" no hace nada
  porque las opciones del dialogo no estan implementadas y el mensaje que abre
  la tienda no esta identificado.
- **El cambio de mapa al Fighting Palace** al terminar el tutorial. El 0x0003
  solo coloca en un tile del mapa actual; el mensaje que cambia de mapa no
  esta identificado.
- **Las skills en el panel.** El 0x001C generado sale identico byte a byte al
  real y se manda al elegir clase y al entrar, asi que el problema no es ese
  mensaje. Pista pendiente: el servidor real manda ademas tres hechizos
  (los tres de nivel 1 del arma elegida; con lanza, Basic Attack I / Bloody
  Song I / Endless Energy I) con id de mensaje 425, y esos no se mandan.
- **Borrar personajes.**

## Para REGALAR un item no sirve el 0x001A

El 0x001A es el inventario completo y el cliente solo lo lee al entrar al
mundo. Al usarlo para entregar items, el chat decia "Obtain Students' Gloves"
pero el panel seguia vacio: habia que salir y volver a entrar para verlos. El
jugador lo describio exacto: "eliges la clase pero te desequipa todo pero sale
que te da cosas, entonces me salgo, entro de nuevo y esta todo".

Lo que refresca en caliente son DOS mensajes 0x001B por item, uno por
contenedor:

    contenedor 1  123 bytes
    contenedor 2  131 bytes

En los dos: +4 marca 01, +5 instancia de 8 bytes, +13 item_id LE32,
+38 char_id LE32, +42 ranura LE16, +49 durabilidad LE32.

Asi es como el servidor real entrega el arma al elegir clase: por cada item
manda un 0x000D con el nombre y despues estos dos 0x001B.

El oro es la excepcion y sigue yendo en el 0x001A: su cantidad vive en la
entrada de la ranura 0 y no hay un mensaje de "cambio de oro" identificado.

## Orden correcto del kit inicial

    al elegir clase   solo el arma (o el arma y el escudo)
    tramo 1           guantes y zapatos, cuando ensena a equiparse
    tramo 2           10 de oro

## El tutorial ya no se saltea

Antes avanzaba por hablar: con darle a "siguiente" se pasaba de tramo aunque
no se hubiera comprado nada. Ahora Angel Raphael no pasa del tramo 2 al 3 sin
el examen en la mochila, y el examen hay que comprarlo.

    1386  Newbie Physical Examination File, precio 10 en item.xml, que es
          justo lo que Raphael entrega en el tramo anterior

El requisito se comprueba al EMPEZAR la conversacion, no al terminarla: en el
juego, en cuanto llevas el examen encima Raphael suelta el "Good for you!" en
vez de repetir lo anterior.

Comprobado de punta a punta:

    1  5001..5005                elegir clase
    2  5006..5018                ropa
    3  5021..5043                10 de oro
    4  5021..5043                REPITE: falta el examen
    5  5022 (Angel Aide)         compra: -10 de oro, +examen
    6  5047                      avanza

LIMITACION: la compra no usa la ventana de tienda del cliente. No se sabe que
mensaje la abre, asi que "Buy the document" sigue sin hacer nada y la venta se
resuelve al cerrar el dialogo del Angel Aide: si lleva las diez monedas, se le
cobran y se le entrega el examen. El examen se PAGA, que era lo que faltaba,
pero no se compra como en el juego.

## Comprar en una tienda

La ventana de tienda la abre el CLIENTE por su cuenta: en la captura, entre el
dialogo con el Shopkeeper y la compra no viaja ni un solo mensaje. El cliente
sabe que vende cada NPC -- la tabla shop de content.db tiene 226 tiendas -- y
arma la lista y los precios solo. Igual que la ventana de eleccion de clase.

Por eso "Buy the document" no abria nada: no habia que abrir nada, habia que
atender la compra. El servidor solo interviene cuando el jugador confirma:

    C -> S  0x0027  [LE32 tienda][LE32 item_id][LE32 cantidad]
    S -> C  0x001B  descuenta el oro (contenedor 1)
    S -> C  0x000D  "N Gold"   id de mensaje 500 = pagaste
    S -> C  0x000D  nombre     id de mensaje 492 = obtuviste
    S -> C  0x001B  entrega el item
    S -> C  0x0035  [LE32 item_id][LE32 cantidad]   confirmacion

Medido comprando unos Gathering Gloves (item 63, precio 1 en item.xml) al
Shopkeeper del Lyceum. El cliente los llama "FreshmanGathering Gloves"; en
item.xml el 63 es "Gathering Gloves" a secas.

El precio sale de la columna price de item.xml.

## El oro ahora se guarda

Se entregaba en el tramo 2 del tutorial pero vivia solo en memoria: al
reconectar volvia a cero y no se podia comprar nada. Ahora va en cuentas.json.

## El tutorial no avanza hasta elegir clase

Al cerrar el primer dialogo el tutorial pasaba a la etapa 1 aunque el jugador
no hubiera elegido nada, y entregaba ahi mismo los guantes y los zapatos. Por
eso parecia que todo se daba de golpe al elegir clase: en realidad los guantes
venian ANTES, del avance indebido. Ahora la etapa 1 pide tener habilidades.

Orden correcto, comprobado:

    hablar sin elegir clase   no entrega nada, repite el tramo 0
    elegir clase              las seis habilidades y el arma
    volver a hablar           los guantes y los zapatos

## Se quito la venta automatica del examen

Mientras no se sabia como funcionaba la tienda, el examen se cobraba al cerrar
el dialogo del Angel Aide. Ahora que el 0x0027 esta identificado eso sobra y
ademas molestaba: descontaba las diez monedas y entregaba el examen sin abrir
ninguna ventana, que es justo lo que el jugador reportaba. La compra la hace
el cliente por la ventana de tienda.

## Cambio de mapa

Medido al terminar el tutorial en el servidor privado:

    S -> C  0x000C  [LE32 stage_id][24 bytes en cero]   "cambia a este mapa"
    C -> S  0x0009  vacio                               "listo, mandamelo"
    S -> C  la secuencia de entrada ENTERA otra vez, con la ficha ya en el
            mapa nuevo, y al final un 0x0003 colocando al jugador

En la captura el 0x000C llevaba 0x39 = 57 (Fighting Palace) y el cliente
respondio con el 0x0009 y recibio de nuevo 0x0014, 0x0002, 0x0064, 0x0155 y
todo lo demas. Se reconocio porque en el registro cronologico aparecia una
SEGUNDA tanda de mensajes de entrada a mitad de la sesion.

El mapa del personaje va en +4 de la ficha 0x0002 (el campo que estaba como
'flags').

Al terminar el tutorial, Angel Raphael manda al Angel Lyceum (stage 41 en
stage.xml). El tile de llegada NO esta medido: en la captura solo se vio el
del Fighting Palace, (39, 205). Se usa (100,100) y se cambia con
AO_TILE_LYCEUM.

## Tutorial customizado (NO es como el juego original)

A pedido del jugador, el tutorial de Angel Raphael se acorto a dos pasos:

    1  hablar y elegir clase  -> las seis habilidades y el arma de la clase
    2  volver a hablar        -> guantes, zapatos, las tres cajas de la clase,
                                 la Growth Box, y traslado al Angel Lyceum

El original tiene cuatro conversaciones, pasa por comprarle el examen al Angel
Aide y termina en el Fighting Palace. Los tramos 2 y 3 quedan medidos en el
historial de server/plantillas/tutorial.json por si se quiere volver atras.

Las cajas salen de item.xml, en tres familias segun el tipo de personaje:

    Guerrero           1948 (nv5)  1949 (nv10)  1951 (nv25)
    Mago               1952 (nv5)  1953 (nv10)  1955 (nv25)
    Arquero/Productor  1944 (nv5)  1945 (nv10)  1947 (nv25)

Mas la Growth Box 20103 (nivel 1); la familia sigue de diez en diez hasta la
20113 (nivel 100).

La familia se decide por las habilidades: magia -> Mago, arco o produccion ->
Arquero/Productor, el resto -> Guerrero.

## Los NPC de la plantilla son solo de Guide Palace

La secuencia de entrada trae tres NPC_SPAWN con Angel Raphael, el Interface
Tutor y Angel Aide en sus posiciones de Guide Palace. Se mandaban en CUALQUIER
mapa, asi que al llegar al Lyceum aparecian los tres flotando entre los NPC que
de verdad viven ahi. Ahora solo se mandan si el stage es 51.

## Lo que falta para que el Angel Lyceum este vivo

El mapa tiene sus propios NPC y monstruos, y ninguno esta implementado. Los
nombres se ven en el mapa del cliente:

    Shopkeeper, Skill Angel, Director Wolay, Angels' Tutor, Michael, Colonel,
    Magic Professor, Magic Teacher, Magic Seller, Ticket Angel, Marriage
    Angel, Bao Clerk, Chief Director, Pet Expert, Battle Professor, Scroll
    Seller, House Pickets, Little Exp Angel, Repair Angel, Badge Angel, Art
    Salesman, Armor Salesman, Weapon Salesman, Sewing Salesman, Cooking
    Salesman, Ironsmith, Mine Professor, Census Angel, Blessing Angel,
    BattlefieldAngel, Cupid, Angel Elementary, House Bulletin, C. Plan Seller,
    y los Lecturer de Art, Healing, Sewing, Armor y Weapon.
    Monstruos: Slarms y Lilys.
    Recursos: Copper, Poplar, Horseradish, Wild Alga, Beast Den.

El problema de fondo es el mismo de siempre: las POSICIONES de NPC, monstruos
y recursos son datos de servidor y no estan en el cliente. Con capturas del
Lyceum se sacan igual que se sacaron las de Guide Palace.

Tambien faltan las zonas de teletransporte del mapa (el jugador choco con una
y quedo trabado) y las quests de la zona.

## Las cajas se encadenan

Segun el jugador, abrir una caja entrega la siguiente de la serie: la de nivel
5 da la de 15, esa la de 25, y la de 35 ya trae un catalogo de objetos. En
item.xml las familias estan (1944/1945/1947 y las Growth Box 20103..20113),
pero abrir una caja todavia no esta implementado: hace falta el mensaje de
"usar item", que no esta identificado.

## Sigue sin resolverse el refresco del inventario

Con pocos items los dos 0x001B de entrega bastaban. Al entregar seis de golpe
al terminar el tutorial, el cliente vuelve a mostrar el inventario vacio hasta
reconectar. Puede ser que no acepte tantas entregas seguidas, o que falte algo
mas cuando son varias. No esta diagnosticado.

## El Angel Lyceum ya esta poblado

De una captura del mapa salieron 35 entidades con sus posiciones, guardadas en
server/plantillas/lyceum.json y reenviadas tal cual al entrar al stage 41:

    20 NPC        Director Wolay (130,64), Shopkeeper (131,87), Ironsmith
                  (93,94), Weapon Lecturer (114,93), Armor Lecturer (104,98),
                  Healing Lecturer (94,107), Magic Teacher (152,110), Magic
                  Seller (160,106), Gaoler Angel (148,109), Cupid (158,78),
                  Angel Elementary (132,80), House Bulletin (147,84), cuatro
                  House Pickets y los cuatro totems (Aurora, Iron, Dark City,
                  Breeze)
    15 monstruos  Slarm y Lily

Los monstruos llegan con klass distinto de 200, igual que los personajes; el
200 es solo para los NPC con dialogo.

El punto de aparicion del mapa NO esta medido: se usa el tile del Shopkeeper
(131,87), que al menos deja al jugador entre los NPC y no en un descampado
como el (100,100) inventado de antes. Se cambia con AO_TILE_LYCEUM.

Los monstruos estan puestos pero QUIETOS: no tienen inteligencia ni combate.
Las zonas de teletransporte del mapa tampoco estan.

## Recursos del mapa: 0x000E

Los 39 mensajes 0x000E de la captura del Lyceum son los recursos (vetas de
Copper, Poplar, Horseradish, Wild Alga, Beast Den):

    +0   LE32  entity_id
    +8   LE32  x en PIXELES   (dividido por 32 da el tile)
    +12  LE32  y en pixeles

Guardados junto a los NPC en server/plantillas/lyceum.json.

Los 0x0001 de 132 bytes que aparecen en la captura son OTROS JUGADORES reales
del servidor privado. No se guardan ni se replican.

## Lo que sigue faltando en el Lyceum

El jugador lo enumero y conviene tenerlo escrito:

- **Los House Pickets se mueven solos** y tienen un dialogo por defecto. Aqui
  estan quietos y mudos: no hay ni movimiento de NPC ni dialogo generico.
- **Director Wolay y Cupido tienen dialogo.** No se capturo ninguno, asi que
  no se sabe que ids de texto usan.
- **Cupido ademas sirve de punto de reaparicion** si se elige en sus opciones.
  Eso necesita las opciones de dialogo, que siguen sin implementarse.
- **A los monstruos no se les puede pegar.** Estan dibujados y nada mas: no
  hay combate, ni vida, ni muerte, ni botin.
- **Faltan NPC.** La captura recogio 20 y en el mapa del cliente se ven mas de
  cuarenta; los que no aparecieron estaban fuera del alcance de vision del
  jugador cuando se grabo.

## El Lyceum, ya completo

Fusionando las DOS capturas del mapa por entity_id salen 137 entidades y 158
recursos, contra las 35 y 39 de la primera. La diferencia es sencilla: en la
primera captura el jugador se quedo cerca del punto de llegada y solo se
anunciaron las entidades a su alcance de vision; en la segunda recorrio el
mapa entero.

    51 NPC        Skill Angel (205,95), Michael (215,110), Battle Professor
                  (227,86), Pet Expert (201,87), Marriage Angel (175,101),
                  Chief Director (186,104), Assassin Master (179,99), Porter
                  Shiwala (36,128), Magic Professor, Mine Professor, Repair
                  Angel, Badge Angel, Census Angel, Scroll Seller, los cinco
                  Salesman, los seis Lecturer, tres Gaoler Angel, cinco House
                  Pickets, los cuatro totems y el resto
    86 monstruos  Slarm y Lily
    158 recursos  Copper, Poplar, Horseradish, Wild Alga, Beast Den

Leccion: una captura solo trae lo que el jugador tuvo a la vista. Para poblar
un mapa hay que recorrerlo, no pararse en un punto.

## Dos errores propios al poblar el Lyceum

**Los dialogos del tutorial se daban a NPC equivocados.** Van por entity_id
(19 Angel Raphael, 20 Interface Tutor, 21 Angel Aide) y esos numeros SE
REPITEN en otros mapas: en el Lyceum la 19 es el Magic Seller, la 20 el Bao
Clerk y la 21 Michael, y a los tres les salia el dialogo del tutorial. Ahora
esos dialogos solo valen en Guide Palace.

**La separacion entre NPC y monstruo por el campo klass estaba mal.** Se daba
por hecho que klass=200 era NPC y el resto monstruos, y asi Bao Clerk quedaba
clasificado como monstruo. La separacion buena es cruzar el nombre contra la
tabla monster de content.db: los unicos monstruos del Lyceum son Slarm y Lily.

Y se quitan los monstruos que caen a nueve tiles o menos de un NPC: en el
juego las zonas de NPC no tienen enemigos, y la captura los recogio porque el
jugador paso por la frontera entre la plaza y el cesped.

## Combate

Medido matando Slarms en el Lyceum. El opcode de atacar es 0x0006, el MISMO
que en el login significa "entrar al mundo": otra vez el mismo numero con
significado distinto segun el servicio.

    C -> S  0x0006  [LE16 ataque][LE16 entity del objetivo][12 bytes en cero]

El primer campo cambia con lo que se use: 656 con el golpe normal, 732 con una
habilidad de la barra. Es el identificador del ataque, no una posicion.

El servidor contesta:

    0x0013  [LE32 entity][U8 1][U8 kind][LE32 valor]   atributo que cambia
              kind 0 = vida, kind 2 = otro contador que baja al pegar
    0x000A  [LE32 atacante][LE32 objetivo][LE32 dano]  el golpe en si
    0x0011  23 B, la animacion del ataque
    0x0003  coloca al monstruo (se mueve al pelear)

Y al morir el bicho:

    0x0013  [entity][1][0][0]        vida a cero: muerto
    0x000A  [entity][jugador][7]     el ultimo golpe
    0x001B  90 B                     el oro entra al inventario
    0x000D  id 492, "N Gold"         "obtuviste N de oro"
    0x000B  11 B                     estado de la entidad

EL BOTIN NO CAE AL SUELO. Lo dijo el jugador y el trafico lo confirma: no hay
ningun 0x0050 (item en el suelo) al matar; llega directo un 0x001B con el oro
y su aviso. Solo entra si hay hueco en la mochila, y se acumula en la ranura
que ya tenga ese item.

Con esto el combate es implementable: hace falta llevar la vida de cada
monstruo, aplicar el dano, avisar con 0x0013 y 0x000A, y al llegar a cero
soltar el botin y reaparecerlo pasado un rato.

## Combate implementado

server/combate.py lleva la vida de cada monstruo del mapa y responde al 0x0006:

    pego        0x000A con el dano + 0x0013 con la vida en porcentaje
    contraataca 0x000A del monstruo hacia el jugador
    muere       el botin entra al inventario (0x001A) con su aviso 0x000D

El dano es el ataque del jugador (el stat R.Atk del 0x0042, que ya se calcula
con el equipo) menos la defensa del monstruo, con un minimo de 1. Los datos de
cada bicho salen de la tabla monster de content.db buscando por el npc_type
que trae su NPC_SPAWN: Lily es el 7 y Slarm el 19.

Comprobado en los dos extremos:

    sin arma          pega 1 (ataque 5 - defensa 25) y el Slarm devuelve ~28
    con dos Sabre     pega 146 y lo mata de un golpe

Lo segundo esta desbalanceado, pero no por la formula: las armas Freshman son
items de nivel 30 equivalente (atk_avg 174) entregadas a un personaje de nivel
1. Es lo que pidio el jugador.

PENDIENTE del combate: la reaparicion esta escrita (SEGUNDOS_REAPARICION en
combate.py) pero no hay nada que la dispare -- falta un bucle que revise los
monstruos muertos y los reviva. Y los monstruos no atacan por su cuenta: solo
devuelven el golpe.

## Los dos bugs que venian arrastrandose

**El inventario que no aparecia hasta reconectar.** La causa no era el
protocolo: era un alias. Al entrar al mundo se hacia

    ses.inventario = dict(p.inventario)

es decir, una COPIA. Todo lo que se entregaba modificaba la copia, pero la
secuencia de entrada y la recarga de mapa leen p.inventario, que seguia sin
los items. Por eso los regalos salian en el chat y no en el panel, y al
reconectar aparecian: en disco si estaban. Ahora las dos cosas son el mismo
diccionario.

Se arrastraba desde hacia varias rondas y se intento arreglar tres veces
mirando el 0x001A y el 0x001B, que estaban bien.

**No se podia atacar en el Lyceum.** Los monstruos se cargaban al entrar al
mundo y no al CAMBIAR de mapa, asi que despues del traslado se seguia con los
de Guide Palace, que son ninguno. Ahora la recarga de mapa los recarga.

**El oro se perdia de vista al cambiar de mapa.** La secuencia armaba el
inventario con cantidad 1 para todo; ahora la ranura 0 lleva p.oro.

Comprobado de punta a punta: se elige Warrior, se habla, llegan los guantes,
los zapatos y las cuatro cajas, el traslado al Lyceum los mantiene todos, y
alli se le pega a un Slarm por 162.

## Para atacar hay que contestar el clic

El cliente hace dos cosas al atacar: primero manda 0x0005 con la entidad
(seleccionarla) y despues 0x0006 (pegar). Si el servidor no contesta al
primero, el cliente NO llega a mandar el segundo, y desde fuera parece que "no
deja atacar".

Lo que contesta el servidor real es la vida del objetivo:

    0x0013  [LE32 entity][1][kind 0][vida en porcentaje]

Eso es lo que le dice al cliente que ese objetivo se puede atacar. El handler
de 0x0005 rechazaba cualquier entidad sin dialogo, monstruos incluidos, y por
eso en el Lyceum no se podia pelear.

## NPC del Lyceum que faltan

De los que se ven en el mapa del cliente faltan cinco: BattlefieldAngel,
Blessing Angel, Colonel, Little Exp Angel y Ticket Angel. Estan en zonas por
las que el jugador no paso al grabar; se consiguen recorriendo esas esquinas.

Fortunia (npc 8814), Hestia (11119) y los payasos (2654 Naughty Clown, 11072
Noddy The Clown) SI existen en npc.xml pero no aparecen ni en el mapa del
cliente ni en ninguna captura. Lo mas probable es que sean NPC de evento, que
solo estan en ciertas fechas; el servidor privado tenia el mapa decorado de
Navidad cuando se grabo.

## Fijar el objetivo: 0x000A, no 0x0013

Correccion de lo escrito antes. Al hacer clic en un monstruo el servidor NO
contesta con la vida: contesta fijando el objetivo.

    S -> C  0x000A  [LE32 jugador][LE32 objetivo][LE32 0x03060001]

Ese ultimo valor es constante -- aparece igual (01 00 06 03) en todos los
clics sobre monstruos de la captura. Con NPC en cambio llega
[entity][0][0], que es "nada que atacar".

Sin ese mensaje el cliente no llega a mandar el 0x0006 y desde fuera parece
que el juego no responde. Es la secuencia completa:

    C -> 0x0005  clic en la entidad
    S -> 0x000A  objetivo fijado        <-- esto faltaba
    C -> 0x0007  girarse hacia el
    C -> 0x0006  atacar
    S -> 0x000A  el golpe + 0x0013 la vida

## Sobre los scripts Lua

Se revisaron los 70 de data1/script (bytecode Lua 5.1). Son la INTERFAZ del
cliente: ventanas, botones, listas. equip.l y item.l manejan los paneles de
equipo e inventario, mall.l la tienda de puntos, tuition.l los cartelitos de
ayuda del tutorial. La unica pieza util para el servidor fue descubrir la API
de red del cliente (game.netcommand con dwID, dwCmdID, dwParam), que confirmo
la forma de los mensajes. No hay logica de servidor ahi: ni posiciones de NPC,
ni dialogos, ni combate. Eso vive en el servidor y solo se saca de capturas.

## Los Lua de los updates: tambien son interfaz

Ademas de los 48 de data1 hay 21 scripts que solo existen en los updates. Se
revisaron todos y son lo mismo: ventanas. Sus llamadas son isexist, destroy,
regsetting, settitle, getappdata -- crear y destruir paneles. Ninguno trae
posiciones, dialogos ni reglas.

jumpmap.l, que por el nombre parecia el teletransporte, es la VENTANA del menu
de saltar a otro mapa (gotojumpmap), no las zonas de warp del suelo.

Lo que si dicen es que sistemas trae el juego, cada uno con su ventana:

    achievement  logros            collection   album de coleccion
    actboard     tablon de eventos dailyevent   evento diario
    farm         huerta            finaltower   torre final
    fuse         fusion de objetos gvg          guerra de gremios
    house        casas (41 KB, el mayor de todos)
    loginreward  premio por entrar onlinereward premio por tiempo jugado
    question     preguntas         roulette     ruleta
    salon        peluqueria        starcard     cartas
    battlepass   pase de batalla   battlefield  campo de batalla
    word         compra de titulos exchange     canje
    automall     tienda automatica

Todo eso existe en el cliente y no esta implementado en el servidor. Para cada
uno hace falta capturar su trafico.

CONCLUSION sobre los Lua, ya definitiva: son la interfaz del cliente y nada
mas. Lo unico que aportaron al servidor fue la forma de la API de red
(game.netcommand con dwID, dwCmdID, dwParam). No hay que volver a mirarlos
esperando encontrar logica de servidor.

## Los XML SI tienen datos que faltaban

Se habia dado por sentado que las posiciones y los destinos eran datos de
servidor y que solo se sacaban de capturas. Es falso, y el jugador tuvo que
preguntar dos veces ("y los xml?") para que se mirara.

**setting/eng/jumpmap.xml: 355 destinos de teletransporte.** Cada fila da el
stage y el tile de llegada, con el nombre del punto (Entrance, Birth Place):

    41  Angel Lyceum                  (152,74)
    3   Aurora City    Entrance       (337,25)   Birth Place  (206,173)
    26  Dark City      Entrance       (16,11)    Birth Place  (213,45)
    29  Breeze Woods   Entrance       (13,24)    Birth Place  (319,78)
    38  Iron Castle    Entrance       (41,9)     Birth Place  (74,149)

De aqui sale el punto de aparicion de CADA mapa. El del Lyceum se habia puesto
a ojo dos veces -- primero (100,100), despues (131,87) copiando el tile del
Shopkeeper de una captura -- y el dato correcto estaba en el cliente.
Guardado en server/plantillas/jumpmap.json.

**Los sp_*.xml colocan NPC.** 276 archivos con etiquetas <npc id map x y dir>,
356 NPC colocados, 178 de ellos en el Lyceum. Son NPC de EVENTO: Santa Claus,
Halloween Queen, Pumpkin Man, Xmas Elf, los Elfos elementales... y ahi estan
los que el jugador recordaba y no aparecian: Hestia (11119) en el Lyceum
(153,88), y payasos y demas. No salian en las capturas porque solo aparecen en
sus fechas.

LECCION: antes de pedir una captura, revisar si el dato ya esta en los XML del
cliente. Se pidieron varias capturas para cosas que estaban ahi.

## Que hay y que no hay en los XML del cliente

Buscando TODAS las etiquetas que colocan algo en un mapa, solo aparecen tres:

    <npc>    639 veces   NPC con id, mapa, tile y direccion
    <Boss>    10 veces   jefes de evento
    <ALIAS>            no coloca nada, es la tabla de nombres de archivo

No hay ninguna etiqueta que coloque MONSTRUOS normales. Eso confirma que los
bichos si son datos de servidor y solo salen de capturas; lo que estaba mal
era decir lo mismo de los NPC y de los puntos de aparicion.

Los <npc> se reparten en dos grupos:

    55   permanentes, de los sp_v##_questnpc.xml: 13 en cada una de las cuatro
         ciudades (Aurora City, Dark City, Breeze Woods, Iron Castle), 2 en
         Palm Base y 1 en Rainbow Town. Son los NPC de quest: Raziel, Vulcan
         Priest Lupin, Elder Wanta y companiia
    301  de evento, de los sp20##_*.xml: Santa Claus, Halloween Queen, los
         Elfos elementales, Hestia... 178 de ellos en el Lyceum. Solo salen en
         sus fechas, por eso no aparecian en ninguna captura

Guardados los permanentes en server/plantillas/npc_por_mapa.json, y el
servidor los coloca en CUALQUIER mapa sin necesitar captura: se les arma el
NPC_SPAWN desde cero con entity_id a partir del 900, para no chocar con los
de las capturas, que son bajos.

## Mapas y puntos de aparicion

stage.xml tiene 445 mapas. jumpmap.xml da el punto de llegada de 238 de ellos;
los otros 207 son mazmorras e interiores, a los que se entra por un portal y
no por el menu de teletransporte (Training Palace, Training Cave, los Testing
Map...). Para esos hace falta capturar el portal.

Estado del poblado:

    Guide Palace   3 NPC     de la captura del tutorial
    Angel Lyceum   133        de dos capturas (52 NPC + 81 monstruos)
    Aurora City    13 NPC     de los xml, sin captura
    Dark City      13 NPC     de los xml
    Breeze Woods   13 NPC     de los xml
    Iron Castle    13 NPC     de los xml
    Palm Base      2 NPC      de los xml
    Rainbow Town   1 NPC      de los xml

## El numero de dano: 0x0011

El 0x000A lleva la cuenta del golpe y el 0x0013 la vida, pero lo que el
jugador VE es el 0x0011. Sin el, el cliente hace el gesto de atacar y no
aparece ningun numero.

    +0   U8    efecto visual
    +1   U8    fase: 0x00 el golpe, 0x80 el cierre
    +2   LE32  atacante
    +6   LE32  objetivo
    +18  LE16  el dano que se dibuja
    +20  U8    2
    +21  LE16  el ataque usado (656 el normal)

Van de a dos: primero la fase 0x00 con el dano, despues la 0x80 con cero. El
generado sale identico byte a byte al capturado.

## Lo que hay en los XML sobre mapas, respondiendo del todo

- **NPC**: <npc id map x y dir>, 639 etiquetas. YA se usan.
- **Jefes de evento**: <Boss map x y>, 10 etiquetas.
- **Monstruos normales**: NO existen en ningun xml. Se busco etiqueta por
  etiqueta. Son datos de servidor y solo salen de capturas.
- **Quests**: quest.xml tiene 1450 quests con lugar (la columna 地點) y sus
  pasos: "Defeat Slarm", "Talk with Angels' Tutor", "Bring back X". Eso
  relaciona quest, mapa y objetivo, y es la base para implementar misiones.
- **Puntos de aparicion**: jumpmap.xml, 238 de los 445 mapas. Los otros 207
  son mazmorras e interiores a los que se entra por portal.

Asi que la respuesta a "los ids de los xml no tienen asociacion a los mapas":
los NPC si y ya se usan; los monstruos no la tienen en ningun lado.

## El orden de los mensajes de un golpe (corregido)

Se habia leido mal el 0x000A. La secuencia real es:

    C -> 0x0006  [ataque][objetivo]
    S -> 0x0013  [objetivo][1][0][vida en %]      la vida del objetivo
    S -> 0x000A  [atacante][0][0]                 abre el ataque, CON CEROS
    S -> 0x0011  fase 0x00, el dano, el ataque    <- el numero que se VE
    S -> 0x0011  fase 0x80, cero                  cierre
    S -> 0x0013  [atacante][1][2][valor]          le baja al que pega

El dano NO va en el 0x000A: ese mensaje lleva ceros y solo abre el ataque. Se
mandaba el dano ahi y el cliente lo ignoraba, asi que se veia el gesto sin
numero. El unico mensaje que dibuja el golpe es el 0x0011.

El campo kind 2 del 0x0013 del atacante baja unas unidades por golpe (864,
861, 857 en la captura); se resta de a 4.

## CORRECCION IMPORTANTE: los dialogos SI estan en el cliente

Se dijo varias veces que los dialogos de los NPC solo salian de capturas. Es
falso, y el jugador tuvo que insistir para que se mirara.

setting/eng/msg.xml tiene 42.036 textos indexados por el MISMO id que viaja en
el 0x0012. Los del tutorial estan ahi: el 5001 es "%1, welcome to the Guidance
Class of the Angel Lyceum", el 5022 es "Hello Little Angel, will you talk to
the [Angel Raphael]?". Se descubrieron por captura cuando bastaba con abrir el
archivo.

Y como el texto vive en el cliente, para dar dialogo a un NPC solo hace falta
saber su id de mensaje. Se encuentra buscando en msg.xml el texto donde el NPC
se presenta ("I am X", "I'm X", "my name is X"):

    Shopkeeper       12101  "Hello, I am the Shopkeeper! In my shop I have..."
    Director Wolay   10004  "I'm Director Wolay. Don't forget to study hard..."
    Cupid             5745  "Hi! I'm the loveliest of all the Angels..."
    Skill Angel       5023  "I'm the Skill Angel, are you satisfied with..."
    Repair Angel      5100  "Hello, I'm the Repair Angel; I can mend any..."
    Chief Director    5029  y los seis Lecturer, los cuatro Salesman...

17 de los 52 NPC del Lyceum ya tienen su linea, sin capturar nada. Los otros
35 no se presentan con esa formula; se les puede buscar el id de otra manera,
pero la via esta abierta.

Guardado en server/plantillas/dialogos_npc.json.

LECCION, y van dos veces: antes de pedir una captura, mirar los xml. Primero
paso con las posiciones y los puntos de aparicion (jumpmap.xml), y ahora con
los dialogos (msg.xml). El jugador lo dijo las dos veces.

## Dialogos con opciones

Faltaba la parte que hace que el cuadro tenga lineas de respuesta. El 0x0012
las lleva detras, y el campo val cambia por NPC:

    Cupid            5745  val 6   -> 5746 "What kind of help?"
                                     5747 "Set the place for your revival."
                                     5748 "Quit."
    Shopkeeper      12101  val 4   -> 12103 "Tell me about the buying and
                                             selling of goods"
                                     12105 "Quit"
    Director Wolay   5079  val 49  -> 5080 "I wish to return to Eden."
                                     5081 "I will choose to leave here."
    Aurora Totem     5136  val 0      sin opciones

Los textos de las opciones tambien estan en msg.xml, asi que el servidor solo
manda los numeros. Se guarda el cuerpo del 0x0012 tal como lo mando el
servidor real (server/plantillas/dialogos_npc.json), y para los NPC sin
captura se arma uno sin opciones con el id que se encontro por el nombre.

## Elegir una opcion del cuadro de dialogo

El cliente manda 0x000B con 1 para pasar de linea y con 10 + indice para
elegir una opcion (se vieron el 10 y el 11).

Lo que el servidor contesta NO esta resuelto. El unico caso capturado es el
dialogo 5795 con opciones [5797, 5798, 5799]: el jugador eligio la segunda y
el servidor contesto con el 5800, que no es ninguna de las tres. Hay una tabla
de "a que dialogo lleva cada opcion" que no viaja por la red, y con un caso no
se deduce.

Por ahora se cierra el cuadro, que es mejor que dejarlo colgado sin respuesta,
y queda anotada la unica respuesta medida (5798 -> 5800).

Para resolverlo del todo hacen falta capturas eligiendo opciones en varios
NPC: con cinco o seis casos se ve si el destino esta en msg.xml, si es una
tabla aparte o si lo decide el servidor.
