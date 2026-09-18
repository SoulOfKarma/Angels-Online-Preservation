# Servidor

## Estado honesto

**El flujo de entrada al mundo funciona de extremo a extremo por socket real.**

`tools/test_login.py` levanta el servidor, conecta un cliente, y comprueba:

```
1. Hello con clave de sesion
2. autenticacion cifrada (0x0002)
3. 21 sub-mensajes de inicializacion, 14.972 bytes
   -> los 21 decodifican con esquema
   -> personaje propio: entidad=1001, tile=(128,62), nombre='Jugador'
4. MOVE_REQ -> respuesta 0x006D + 0x0005 ENTITY_MOVE
```

**El limite de esta prueba:** el cliente es codigo nuestro hablando nuestro
propio protocolo, asi que por si sola seria circular. Lo que la sostiene es que
la implementacion esta validada **contra capturas reales**: framing 100% sobre
168.570 frames, replay 99,8% de entrada sobre una sesion de verdad. La
circularidad esta acotada, pero **no reemplaza probar con el cliente del
juego**, que es el siguiente paso y necesita ejecutarlo a mano.

Lo probado:

| capa | validacion |
|---|---|
| framing | 168.570/168.570 frames reales re-codificados **byte a byte** |
| handshake | `build_hello()` reproduce el Hello de IGG **identico** |
| cifrado | S->C y C->S al 100% sobre ~150.000 frames de IGG |
| sub-mensajes | 27/27 esquemas, **98,8%** del corpus |
| socket real | handshake + cifrado + parseo, extremo a extremo |
| entrada al mundo | 21/21 mensajes emitidos y decodificados |
| movimiento | MOVE_REQ -> ENTITY_MOVE correcto |

## Validacion por replay

`tools/replay.py` alimenta la sesion del servidor con el stream C2S **real**
capturado de una partida, y mide cuanto entiende. No se puede hacer trampa:
los bytes los produjo un cliente real hablando con un servidor real.

```
ENTRADA  43.994/44.093 mensajes del cliente interpretados =  99,8%
SALIDA  151.633/157.574 mensajes del servidor construibles =  96,2%
```

"SALIDA" mide que fraccion de lo que el servidor real respondio sabriamos
**construir**, no que sepamos *cuando* enviarlo. Eso ultimo es la logica de
juego, y es justamente lo que falta.

## Componentes

| archivo | funcion |
|---|---|
| `proto/framing.py` | frame: header ofuscado, checksum, sub-mensajes |
| `proto/handshake.py` | Hello y los dos cifradores |
| `proto/codec.py` | tipos de campo, `Msg`, `VarMsg`, `Count`, `Array` |
| `proto/messages.py` | los 27 esquemas |
| `server/session.py` | estado por conexion, buffer, dispatch |
| `server/app.py` | servidor asyncio |
| `tools/replay.py` | validacion por replay |
| `server/login.py` | secuencia de entrada al mundo |
| `server/plantillas/` | mensajes capturados usados como base |
| `tools/test_transporte.py` | ida y vuelta por socket real |
| `tools/test_login.py` | flujo completo de entrada al mundo |
| `tools/test_framing.py` | re-codificacion de frames reales |
| `tools/roundtrip.py` | harness de conformidad de esquemas |

## Uso

```
python server/app.py --host 127.0.0.1 --port 16768 -v
```

El `server.xml` del cliente ya apunta a `127.0.0.1:16768`.

## Configuracion del protocolo

Las tres decisiones estan atestiguadas en capturas de produccion, ninguna es
conjetura:

1. Hello en variante **minima** (como IGG), clave aleatoria de 16 bytes.
2. S->C en **texto plano** (`flags=0x00`), como hace el servidor privado.
3. C->S descifrado con **XOR evolutivo** desde esa clave.

## Secuencia de entrada al mundo  [MEDIDA]

Extraida del orden real de una conexion capturada
(`37_72_169_250_24132_4`). Es el guion que el servidor tiene que seguir.

### Apertura

```
        SYN
S -> C  HELLO            134 B   (seq=0xFFFF, en claro)
C -> S  0x0002            37 B   autenticacion
C -> S  0x0003             4 B   ack
C -> S  0x0016             9 B
C -> S  0x0004 MOVE_REQ          ya es juego normal
```

### Lo que el servidor envia, en orden

**Los 21 mensajes de inicializacion tienen esquema validado.**

| # | opcode | bytes | que es |
|---|---|---|---|
| 1 | `0x016F` | 22 | sin identificar |
| 2 | `0x0014` | 7 | sin identificar |
| 3 | `0x0002` | **4118** | **ficha del personaje** |
| 4 | `0x001E` | 4 | sin identificar |
| 5 | `0x0155` | **7204** | **tablas de probabilidad** |
| 6 | `0x0156` | 40 | sin identificar |
| 7 | `0x012A` | 21 | sin identificar |
| 8 | `0x005C` | 37 | 37 bytes en cero, siempre |
| 9 | `0x005D` | 4 | **timestamp del servidor** |
| 10 | `0x001D` | 77 | atributos del jugador |
| 11 | `0x005B` | 216 | **barra de habilidades (24 ranuras)** |
| 12 | `0x001A` | **2484** | lista fechada (estructura resuelta) |
| 13-18 | `0x001D` | 14 | seis lotes de atributos |
| 19 | `0x0185` | 12 | sin identificar |
| 20 | `0x0021` | 400 | **registro de quests** |
| 21 | `0x001D` | 32 | atributos |
| 22+ | `0x000E`, `0x0008`, `0x0185` | | spawns del mapa |

A partir del #22 empieza el trafico normal de mundo. O sea: **~21 mensajes de
inicializacion** antes de que el jugador exista en el mapa.

Los tres bloques grandes (`0x0002`, `0x0155`, `0x001A`) **ya tienen esquema
validado**. Ver mas abajo.

> El sniffer etiqueta mal los opcodes en su log (llama `MOVE_RESP` a `0x0002`
> y toma el `sub_len` como si fuera el opcode). Su **orden y direccion** si son
> confiables; sus **nombres** no. Esta tabla sale de decodificar los `.bin`,
> no de sus etiquetas.

## `0x0002` CHARACTER_DATA  [RESUELTO]

4118 bytes, de los cuales **solo el 17% lleva contenido**.

```
+0    U32       entity_id        el entity_id del propio jugador
+4    U32       flags
+8    U32       tile_x
+12   U32       tile_y
+16   char[34]  nombre
+50   [52 B]    sin identificar
+102  [105 B]   == el cuerpo completo de 0x0042 PLAYER_STATS
+207  [7 B]     sin identificar
+214  skill[36] tabla de habilidades, 14 B por registro
+718  [3400 B]  reservado, casi todo en cero
```

Registro de habilidad (14 B):
```
[U8 skill_id][LE16 nivel][LE16 nivel2][4 B cero][LE32 exp][U8 idx]
```

**Tres verificaciones independientes:**

1. El encabezado `+0..+15` es **identico** al de `0x0008 NPC_SPAWN`.
2. `+102..+206` contiene el bloque de `0x0042`: **16/16 campos coinciden
   exactamente** con un `0x0042` capturado en el mismo stream.
3. `skill_id` indexa el **orden de columnas de `level.xml`**. Decodificado da
   9=劍術 espada nv38, 10=斧錘 hacha nv37, 13=格鬥 lucha nv38, 14=盾防 escudo
   nv38, 15=蓄勁 vigor nv38, 33=重裝 armadura pesada nv38, y **todas las
   habilidades magicas en nivel 1**. Un guerrero cuerpo a cuerpo coherente --
   no numeros al azar que casualmente encajan.

Roundtrip exacto en 6/6 muestras.

## `0x0021` QUEST_LOG  [CONFIRMADO]

```
+0  U32 count
+4  quest[count], 18 B cada una:
      [U32 char_id][U16 quest_id][U8 paso][11 B]
```

`4 + 22*18 = 400` exacto.

**La prueba:** los 22 `quest_id` existen en `quest.xml`, y `paso` **es igual al
numero de pasos de esa quest en 18 de 22 casos** (completadas), menor en las 4
restantes (en curso), y nunca lo supera.

| id | paso | pasos | nombre |
|---|---|---|---|
| 117 | 3 | **3** | Battle-advanced course |
| 527 | 4 | **4** | Break Seal |
| 101 | 5 | **5** | Freshman's signing for taking course |
| 140 | 0 | 1 | Reaching higher level |

Control: con ids al azar solo el **80,3%** cumpliria siquiera `paso <= pasos`.
La igualdad **exacta** en 18 de 22 no ocurre por casualidad. Y los nombres
forman una progresion coherente de personaje novato.

`char_id = 4794` es constante en los 22 registros: el id **persistente** del
personaje, distinto del `entity_id` de runtime (14509). Tambien aparece dentro
de `0x0002`, en +207.

## `0x005B` SKILL_BAR  [CONFIRMADO]

24 ranuras de 9 B = 216. `[U8 usada][U16 magic_id][6 B]`

Cruzado contra `magic.xml`, las 4 ranuras ocupadas dan:

| id | magia |
|---|---|
| 634 | Slicing Hit IV |
| 732 | Panther Killing III |
| 734 | Basic Beating IV |
| 607 | Sword Trap I |

Todas de espada y cuerpo a cuerpo, **coherente con el personaje de `0x0002`**
(espada 38, hacha 37). Dos mensajes independientes describiendo al mismo
guerrero.

## `0x0155` RATE_TABLES  [RESUELTO]

7204 bytes fijos. **No es el inventario**, como suponia el proyecto anterior.

El contenido son **curvas de probabilidad decrecientes** que arrancan en 100,
en filas de unos 8 valores:

```
100, 88, 44, 17,  8,  5,  4
 71, 35, 17,  7,  3,  1,  1, 1
 99, 49, 24,  9,  4,  2,  1, 1
```

Perfil tipico de tablas de exito (mejora de equipo, crafteo, habilidades).
Solo el 4% de los bytes lleva contenido.

**El dato practico:** 7.180 de los 7.204 bytes son **identicos entre sesiones
distintas**. Solo 24 varian, y caen dentro de las curvas -- o sea son tablas
calculadas por personaje sobre una base comun.

El servidor puede enviar `server/plantillas/0155_rate_tables.bin` y parchear
esos 24 offsets (listados en `0155_offsets_variables.json`).

## `0x001A` TIMED_LIST  [ESTRUCTURA RESUELTA, SEMANTICA NO]

```
+0    U32       count
+4    [330 B]   resto del encabezado
+334  entrada[count], 86 B cada una:
        [5 B] [U32 timestamp Unix] [77 B]
```

**Deducido por aritmetica sobre dos tamanos reales**: 2484 B con `count=25` y
2312 B con `count=23`. La diferencia 172/2 da **86 B por registro**, y
`2484 - 25*86 = 2312 - 23*86 = 334` da el encabezado por dos caminos
independientes.

Confirmado por una via distinta: los timestamps Unix caen en la **fase 5** del
registro en 14 de 30 casos (los demas estan dentro del encabezado). Las fechas
son del 13 y 14 de septiembre de 2026, que son los dias de captura.

**Que ES, no lo se.** Una lista de 25 entradas fechadas enviada al entrar.
Podria ser correo, lista de amigos o registro de eventos. No le pongo nombre a
lo que no verifique.

## Que esta construido y que es plantilla

Distincion importante para no confundir andamiaje con comprension:

**CONSTRUIDO** -- se arma desde cero con datos propios:
`0x0002` (ficha: entidad, posicion, nombre, habilidades), `0x0021` (quests),
`0x005B` (barra), `0x005D` (timestamp).

**PLANTILLA** -- se reenvia tal como lo emitio el servidor real, sin entender
su contenido: `0x016F`, `0x0014`, `0x001E`, `0x0155`, `0x0156`, `0x012A`,
`0x005C`, `0x001A`, `0x001D`, `0x0185`.

Las plantillas sirven para que el cliente entre. **No son comprension**, y hay
que reemplazarlas a medida que se entienda cada mensaje.

## Lo que falta para que un cliente entre

En orden de dependencia:

1. ~~Los tres bloques grandes~~ **RESUELTOS**.
2. ~~El resto de la secuencia~~ **RESUELTO**: los 21 mensajes de
   inicializacion tienen esquema validado. De seis todavia no se sabe QUE
   significan (`0x016F`, `0x0014`, `0x0156`, `0x012A`, `0x001E`, `0x0185`),
   pero se pueden construir y enviar.
3. **`0x0002` C2S** (autenticacion, 37 B). Solo 3 muestras y el cuerpo va sin
   guardar por contener credenciales.
4. **`0x000D`** (2,33% del trafico) y **`0x001B`** (1,09%).
5. **Logica de juego.** Movimiento, combate, NPCs. Los DATOS ya estan en
   `corpus/content.db`; falta el codigo que los usa.

## Lo que sigue siendo codigo, no datos

La **formula de combate**: como atk/def/precision/agilidad producen dano. Eso
nunca estuvo en el cliente y hay que disenarlo, calibrandolo contra los stats
reales de `monster.xml`.
