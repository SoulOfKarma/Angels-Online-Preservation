"""
Definiciones de mensajes, derivadas del corpus real.

Convencion: un campo se nombra solo cuando hay evidencia de que significa eso.
Lo demas queda como unk_<offset> -- estructuralmente exacto, semanticamente
honesto. Nunca un nombre inventado que despues alguien tome por confirmado.

REV: el servidor de IGG y el privado no corren la misma revision
(0x0008 mide 62 y 63 bytes respectivamente), asi que algunos mensajes se
definen por separado.
"""
from codec import Msg, U8, U16, U32, I32, Bytes, Str

# ---------------------------------------------------------------- S2C

Msg(0x0005, 's2c', 'ENTITY_MOVE', [
    U32('entity_id'), U32('cur_x'), U32('cur_y'),
    U32('dst_x'), U32('dst_y'), U16('speed'),
], note="Confirmado campo a campo: entity=7 cur=(5200,2383) dst=(5072,2543) speed=50")

Msg(0x0008, 's2c', 'NPC_SPAWN', [
    U32('entity_id'), U32('flags'), U32('tile_x'), U32('tile_y'),
    Str('name', 17), U8('unk_33'), U32('sprite_id'), U16('unk_38'),
    U32('klass'), U8('unk_44'), U16('npc_type_id'), U8('unk_47'),
    U16('unk_48'), Bytes('pad', 13),
], rev='privado',
   note="klass: 200=NPC, 1=personaje de jugador. npc_type_id verificado contra npc.xml")

Msg(0x0008, 's2c', 'NPC_SPAWN', [
    U32('entity_id'), U32('flags'), U32('tile_x'), U32('tile_y'),
    Bytes('name_raw', 17), U8('unk_33'), U32('sprite_id'), U16('unk_38'),
    U32('klass'), U8('unk_44'), U16('npc_type_id'), U8('unk_47'),
    U16('unk_48'), Bytes('pad', 12),
], rev='igg',
   note="IGG usa 62 bytes (uno menos de relleno). Y a diferencia del privado, "
        "NO limpia el campo de nombre: quedan bytes residuales tras el NUL, "
        "por eso va como Bytes y no como Str -- normalizarlo romperia el "
        "roundtrip en 784/788 muestras.")

Msg(0x0013, 's2c', 'UNK_0013', [
    U32('entity_id'), U8('unk_04', const=1), U8('unk_05'),
    U16('unk_06'), U16('unk_08'),
], note="166k muestras. @4 constante=1 verificado. @0 ES entity_id: cruza "
        "100,0% en el servidor privado. (Da 19,3% en IGG solo porque esa "
        "captura arranco a mitad de sesion y su universo de referencia esta "
        "incompleto -- no porque el campo signifique otra cosa.)")

Msg(0x000A, 's2c', 'UNK_000A', [
    U32('entity_id'), U32('unk_04'), U32('unk_08'),
], note="@4 tambien cae en el rango de entity_id -> posible par origen/destino")

Msg(0x000B, 's2c', 'ENTITY_STATUS', [
    U32('entity_id'), U8('kind'), U32('value'), Bytes('pad', 2),
])

Msg(0x0011, 's2c', 'UNK_0011', [
    U32('unk_00'), U32('unk_04'), U32('unk_08', const=0),
    U32('unk_12', const=0), U32('unk_16'), Bytes('tail', 3),
], rev='privado', note="@8 y @12 en cero SOLO en el servidor privado.")

Msg(0x0011, 's2c', 'UNK_0011', [
    U32('unk_00'), U32('unk_04'), U32('unk_08'),
    U32('unk_12'), U32('unk_16'), Bytes('tail', 3),
], rev='igg', note="En IGG @8 y @12 llevan datos; la constante del privado no aplica.")

Msg(0x0007, 's2c', 'ENTITY_POS', [U32('entity_id'), U8('unk_04')])
Msg(0x0016, 's2c', 'UNK_0016', [U32('entity_id'), U8('unk_04')])
Msg(0x0185, 's2c', 'UNK_0185', [U32('unk_00'), U32('unk_04'), U32('unk_08')])
Msg(0x0003, 's2c', 'UNK_0003', [U32('unk_00'), U32('unk_04'), U32('unk_08')])
Msg(0x001E, 's2c', 'UNK_001E', [U32('unk_00')])
Msg(0x0020, 's2c', 'UNK_0020', [U32('unk_00'), U32('unk_04'), U16('unk_08')])
Msg(0x006D, 's2c', 'MOVE_ACK', [])

# ---------------------------------------------------------------- C2S

Msg(0x0007, 'c2s', 'GIRAR', [U8('direccion')],
    note="El personaje se gira. Llega junto con el 0x0005 de hablarle a un "
         "NPC: 3 para el que tiene al norte, 4 para el del oeste, 0 para el "
         "del este. Mismos valores que el 0x0016 del servidor.")
Msg(0x0006, 'c2s', 'REQ_0006', [U32('unk_00'), U32('unk_04'),
                                U32('unk_08'), U32('unk_12')])
Msg(0x0016, 'c2s', 'REQ_0016', [U32('unk_00'), U8('unk_04')])  # 17,9% de cruce: no es entity_id
Msg(0x0005, 'c2s', 'HABLAR_NPC', [U32('entity_id'), U16('cero')],
    note="Clic en una entidad. Verificado con marca de tiempo: los entity_id "
         "19, 20 y 21 son Angel Raphael, Interface Tutor y Angel Aide, y el "
         "servidor contesta la primera linea del dialogo 140-150 ms despues.")
Msg(0x000F, 'c2s', 'REQ_000F', [U32('unk_00'), U32('unk_04')])
Msg(0x002E, 'c2s', 'REQ_002E', [U32('unk_00'), U8('unk_04')])
Msg(0x0003, 'c2s', 'REQ_0003', [])
Msg(0x0009, 'c2s', 'REQ_0009', [])


# ------------------------------------------------- longitud variable

from codec import VarMsg, Count, Array

VarMsg(0x001D, 's2c', 'ENTITY_ATTRS', [
    U32('entity_id'),
    Count('n', of='attrs'),
    Array('attrs', [U8('kind'), U32('a'), U32('b')]),
], note="len = 5 + n*9, verificado en ambos servidores. Opcode S2C mas "
        "frecuente (261k muestras). Lote de atributos por entidad: cada "
        "registro es (kind, a, b). b vale a menudo 0 o 0xFFFFFFFF.")

VarMsg(0x0004, 'c2s', 'MOVE_REQ', [
    U16('cur_x'), U16('cur_y'),
    Count('n', of='path'),
    U16('unk_05'),
    Array('path', [U16('x'), U16('y')]),
], puertos=(24131, 24132, 16769),
   note="len = 7 + n*4. NO es un solo destino: es una RUTA con hasta 5 "
        "waypoints. Verificado contra el log del emulador viejo: el cuerpo "
        "'1e 0c c5 01 01 4c 9b 10 0e af 01' da cur=(3102,453) y "
        "path=[(3600,431)], exactamente lo que ese log reporto. "
        "@5 varia sin patron claro (tick del cliente?), sin nombrar.")

Msg(0x0042, 's2c', 'PLAYER_STATS', [
    U32('hp'), U32('hp_max'), U32('mp'), U32('mp_max'),
    U32('unk_16'), U32('unk_20'), U32('unk_24'), U32('unk_28'),
    U32('unk_32'), U32('unk_36'), U32('unk_40'), U32('unk_44'),
    U32('unk_48'), U32('unk_52'), U32('unk_56'), U32('unk_60'),
    Bytes('resto', 41),
], note="Bloque de atributos del propio jugador, 105 bytes. hp/hp_max y "
        "mp/mp_max verificados: 'actual <= maximo' se cumple en 1593/1593 "
        "muestras, y el actual tiene 75 valores distintos contra 11 del "
        "maximo (el maximo casi no cambia). Los unk_* son el resto del panel "
        "de atributos; sin confirmar cual es cual.")

Msg(0x000E, 's2c', 'UNK_000E', [
    U32('unk_00'), U32('unk_04'), U32('unk_08'), U32('unk_12'),
    U32('unk_16', const=0), U32('unk_20', const=0),
    U32('unk_24', const=0), U32('unk_28', const=0),
    U32('unk_32'), U32('unk_36'), Bytes('tail', 3),
], rev='privado',
   note="@8 (150..10409) y @12 (97..7803) caen en escala de pixel, como las "
        "coordenadas de 0x0005 -- probablemente posicion, pero sin verificar, "
        "asi que no se nombran.")


# ------------------------------------------------- datos del personaje

from codec import FixedArray

# OJO: los opcodes estan acotados POR SERVICIO. Este 0x0002 es el del servidor
# de juego (puertos 24131/24132). En el puerto 30007 (avatares) el opcode
# 0x0002 es otra cosa completamente distinta: lleva nombres de archivo PNG.

Msg(0x0002, 's2c', 'CHARACTER_DATA', [
    U32('entity_id'), U32('flags'), U32('tile_x'), U32('tile_y'),
    Bytes('name_raw', 34),          # +16 .. +49
    Bytes('unk_50', 52),            # +50 .. +101
    Bytes('stats', 105),            # +102..+206  == el cuerpo de 0x0042
    Bytes('unk_207', 7),            # +207..+213
    FixedArray('skills', 36, [      # +214..+717
        U8('skill_id'), U16('level'), U16('level2'),
        Bytes('cero', 4), U32('exp'), U8('idx'),
    ]),
    Bytes('resto', 3400),           # +718..+4117 (casi todo en cero)
], rev='privado', puertos=(24131, 24132),
   note="Ficha completa del personaje, 4118 B. Solo el 17% lleva contenido.\n"
        "  - el encabezado (+0..+15) es identico al de 0x0008 NPC_SPAWN\n"
        "  - +102..+206 es el bloque de 0x0042 PLAYER_STATS: 16/16 campos\n"
        "    coinciden exactamente con un 0x0042 del mismo stream\n"
        "  - skills[36]: skill_id indexa el ORDEN DE COLUMNAS de level.xml.\n"
        "    Verificado: 9=劍術 espada nv38, 10=斧錘 hacha nv37, 13=格鬥 lucha,\n"
        "    14=盾防 escudo, 15=蓄勁 vigor, 33=重裝 armadura pesada, y todas\n"
        "    las magicas en nivel 1. Un guerrero cuerpo a cuerpo coherente.")

Msg(0x0155, 's2c', 'RATE_TABLES', [
    Bytes('bloque', 7204),
], rev='privado', puertos=(24131, 24132),
   note="7204 B fijos. NO es el inventario, como suponia el proyecto anterior:\n"
        "  el contenido son curvas de probabilidad decrecientes que arrancan\n"
        "  en 100, en filas de ~8 valores. Perfil tipico de tablas de exito\n"
        "  (mejora de equipo, crafteo, habilidades).\n"
        "  Solo el 4% de los bytes lleva contenido.\n"
        "  CLAVE PRACTICA: 7.180 de los 7.204 bytes son IDENTICOS entre\n"
        "  sesiones distintas; solo 24 varian, y caen dentro de las curvas.\n"
        "  O sea son tablas calculadas por personaje sobre una base comun.\n"
        "  El servidor puede enviar server/plantillas/0155_rate_tables.bin y\n"
        "  parchear esos 24 offsets (ver 0155_offsets_variables.json).")

VarMsg(0x001A, 's2c', 'TIMED_LIST', [
    Count('n', of='entradas', fmt='I'),
    Bytes('cabecera', 330),
    Array('entradas', [Bytes('pre', 5), U32('timestamp'), Bytes('resto', 77)]),
], rev='privado', puertos=(24131, 24132),
   note="Estructura deducida por aritmetica sobre dos tamanos reales:\n"
        "  2484 B con count=25 y 2312 B con count=23 -> 172/2 = 86 B por\n"
        "  registro; y 2484-25*86 = 2312-23*86 = 334, o sea el encabezado mide\n"
        "  334 B en ambos. Confirmado de forma independiente: los timestamps\n"
        "  Unix caen en la fase 5 del registro en 14 de 30 casos (el resto\n"
        "  esta dentro del encabezado).\n"
        "  Las marcas de tiempo son del 13-14/09/2026, las fechas de captura.\n"
        "  SEMANTICA DESCONOCIDA: una lista de 25 entradas fechadas en el\n"
        "  login. Podria ser correo, amigos o registro de eventos. No se le\n"
        "  pone nombre a lo que no esta verificado.")


# ------------------------------------------------- resto de la secuencia de login

VarMsg(0x0021, 's2c', 'QUEST_LOG', [
    Count('n', of='quests', fmt='I'),
    Array('quests', [U32('char_id'), U16('quest_id'), U8('paso'), Bytes('resto', 11)]),
], rev='privado', puertos=(24131, 24132),
   note="4 + n*18 = 400 exacto con n=22. CONFIRMADO como registro de quests:\n"
        "  los 22 quest_id existen en quest.xml, y 'paso' es igual al numero\n"
        "  de pasos de esa quest en 18 de 22 casos (completadas), menor en\n"
        "  las 4 restantes (en curso). Nunca lo supera. Con ids al azar solo\n"
        "  el 80% cumpliria siquiera paso<=pasos; la igualdad exacta en 18/22\n"
        "  no ocurre por casualidad.\n"
        "  Los nombres forman una progresion coherente de personaje novato.\n"
        "  char_id=4794 constante: id persistente del personaje (distinto del\n"
        "  entity_id de runtime, 14509). Tambien aparece en 0x0002 en +207.")

Msg(0x005B, 's2c', 'SKILL_BAR', [
    FixedArray('ranuras', 24, [U8('usada'), U16('magic_id'), Bytes('resto', 6)]),
], rev='privado', puertos=(24131, 24132),
   note="24 ranuras de 9 B = 216. CONFIRMADO contra magic.xml: las 4 usadas\n"
        "  dan 634=Slicing Hit IV, 732=Panther Killing III, 734=Basic Beating\n"
        "  IV, 607=Sword Trap I. Todas de espada/cuerpo a cuerpo, coherente\n"
        "  con el personaje de 0x0002 (espada 38, hacha 37).")

Msg(0x005D, 's2c', 'SERVER_TIME', [
    U32('timestamp'),
], rev='privado', puertos=(24131, 24132),
   note="Timestamp Unix. Las 3 muestras difieren entre si.")

Msg(0x016F, 's2c', 'UNK_016F', [Bytes('cuerpo', 22)], rev='privado', puertos=(24131,24132))
Msg(0x0014, 's2c', 'UNK_0014', [U32('unk_00'), Bytes('resto', 3)], rev='privado', puertos=(24131,24132))
Msg(0x0156, 's2c', 'UNK_0156', [Bytes('cuerpo', 40)], rev='privado', puertos=(24131,24132))
Msg(0x012A, 's2c', 'UNK_012A', [Bytes('cuerpo', 21)], rev='privado', puertos=(24131,24132))
Msg(0x005C, 's2c', 'UNK_005C', [Bytes('cuerpo', 37)], rev='privado', puertos=(24131,24132),
    note="37 bytes, todos en cero en todas las muestras.")


Msg(0x0002, 'c2s', 'AUTH', [
    Bytes('credenciales', 33),
    # OJO: el tamano NO es fijo. 73 B en el servidor de login (usuario en
    # claro + contrasena cifrada) y 33 B en el de mundo (con char_id). Esta
    # definicion cubre la variante de mundo, que es la del corpus; en login
    # el servidor lee el cuerpo crudo, no este esquema.
], rev='privado', puertos=(24131, 24132),
   note="Autenticacion, 33 B. DELIBERADAMENTE OPACO: transporta credenciales "
        "de cuenta. Se modela como bloque de bytes; no se desglosa en campos "
        "ni se vuelca su contenido en logs ni en el corpus.")


# --- dialogo con NPC ------------------------------------------------------
# Todo esto sale de una captura del servidor privado con marca de tiempo en
# los dos sentidos, no de suposiciones. Ver docs/01_HECHOS_VERIFICADOS.md.

Msg(0x000B, 'c2s', 'DIALOGO_SIGUIENTE', [U8('valor')],
    note="Avanzar el cuadro de dialogo. Vale 1 al pasar a la linea siguiente "
         "y otro numero al elegir una opcion del menu (se vio un 10).")

Msg(0x0012, 's2c', 'DIALOGO_LINEA', [
    U32('dialogo_id'), U16('valor'), U8('n_cadenas'), U8('n_opciones'),
    U8('cero'),
], note="Una linea de dialogo. El TEXTO no viaja por la red: el cliente lo "
        "busca por dialogo_id. Con dialogo_id 0 se cierra el cuadro. "
        "Aca solo se declara la cabecera de 9 bytes. Detras van n_cadenas "
        "cadenas terminadas en NUL (parametros que el cliente mete dentro "
        "del texto, por ejemplo el nombre del jugador) y n_opciones enteros "
        "LE32 con el id de dialogo de cada opcion del menu. Son de tipos "
        "distintos segun el caso y el codec no puede expresar eso sin "
        "mentir, asi que quedan en _extra y los arma server/dialogos.py. "
        "Las dos formas estan comprobadas en la captura: la primera linea "
        "de Angel Raphael trae n_cadenas=2 ('1' y el nombre) con "
        "n_opciones=0, y la del Interface Tutor n_cadenas=0 con "
        "n_opciones=2 (los ids 5241 y 5242).")

Msg(0x0003, 's2c', 'ENTIDAD_COLOCAR', [
    U32('entity_id'), U32('tile_x'), U32('tile_y'),
], note="Coloca una entidad en un tile, sin animacion de recorrido. En la "
        "captura el servidor lo usa para dejar al jugador pegado al NPC con "
        "el que habla: (89,86) esta al lado de Angel Raphael (88,87) y "
        "(81,86) al lado del Interface Tutor (80,85). "
        "Cuidado: el cruce de entity_id contra el universo de entidades da "
        "100% en el servidor privado pero solo 37% en las capturas de IGG, "
        "asi que esta lectura vale para el privado; en IGG el primer campo "
        "podria ser otra cosa.")

Msg(0x0001, 's2c', 'JUGADOR_ENTRA', [
    U32('entity_id'), U32('unk_04'), U32('tile_x'), U32('tile_y'),
    Str('nombre', 16), Bytes('unk_32', 20), U32('unk_52'), U32('unk_56'),
    U32('unk_60'),
    U32('eq0'), U32('eq1'), U32('eq2'), U32('eq3'), U32('eq4'),
    U32('eq5'), U32('eq6'), U32('eq7'), U32('eq8'), U32('eq9'),
    Bytes('cola', 24),
], note="OTRO JUGADOR aparece en el mapa. 128 bytes. Medido en Celestia el "
        "24/09/2026, cuando entro un segundo jugador en Hidden Grove. "
        "No confundir con el 0x0001 del LOGIN, que es la ficha de la ranura "
        "recien creada: es el mismo opcode en otro contexto. "
        "La cabecera es la de siempre -- entidad@0, casilla@8/12, nombre@16 "
        "en 16 bytes --, igual que el 0x0008 y la ficha 0x0002. "
        "Lo interesante son los DIEZ numeros de @64 a @100: son ITEM_ID, el "
        "equipo del jugador, que es como el cliente sabe con que dibujarlo. "
        "En la captura salieron 76901, 76902, 75922, 75921, 75913, 76904, "
        "75919, 60909, 7541 y 75356, y solo el 7541 esta en el item.xml de "
        "los paks extraidos: es 'Pan's Rescue', un arco. Los otros nueve "
        "son de updates mas nuevos. "
        "OJO: esto es POR ITEM_ID, mientras que el 0x0179, que dibuja la "
        "figura de la ID Card del propio personaje, va por SPRITE (40287.."
        "40295). Son dos mecanismos distintos. "
        "Nuestro servidor no manda este mensaje: no hay multijugador.")

VarMsg(0x0179, 's2c', 'APARIENCIA', [
    Count('n', of='grupos'),
    U32('unk_04'), U32('unk_08'), U8('flag'),
    Array('grupos', [Count('cuantos', of='sprites'),
                     Array('sprites', [U32('sprite')])]),
], note="LA APARIENCIA DEL PERSONAJE: es lo que dibuja la figura de la ID "
        "Card. Medido en Celestia el 24/09/2026 con la Card abierta "
        "cambiando piezas. Salen dos variantes: 327 bytes al entrar y 170 en "
        "cada equipado. La de 327 traia los grupos [40289,40288,40287], "
        "[40292,40291,40290], [40295,40294,40293] y [6144,0,0], con el resto "
        "vacios; son ids del rango de sprites de personaje y el usuario "
        "confirma que cambian con la ropa y el Fashion. "
        "Antes estaba anotado como 'sale identico siempre': era FALSO. "
        "NUESTRO SERVIDOR NO LO MANDA, y por eso la ID Card dibuja al "
        "personaje por defecto. PENDIENTE la tabla item -> sprite: esos ids "
        "no son el item_id ni el 原型外觀 de item.xml.")

Msg(0x0151, 'c2s', 'ANGELS_GO', [U32('destino')],
    note="Teletransporte de las Superwing (item 25832). El numero es el "
         "編號 de jumpmap.xml, no un stage: la tabla trae 355 destinos con "
         "su escenario y su casilla. Medido en Celestia el 24/09/2026 en "
         "Nightmare Palace: el id 120 dejo en (34,219) y el 119 en (20,23), "
         "que es justo lo que dice jumpmap.xml para esos dos. "
         "El servidor contesta 0x0012, un 0x001B con la Superwing a una "
         "unidad menos, 0x0042 y 0x0013, y ahi se bifurca: si el destino "
         "esta en el MISMO mapa cierra con un 0x0003 y no manda 0x000C; "
         "si es OTRO mapa cierra con un 0x0007 de 5B y el 0x000C, como un "
         "tornado, y no manda el 0x0003. Los dos casos medidos.")

Msg(0x0016, 's2c', 'ENTIDAD_DIRECCION', [U32('entity_id'), U8('direccion')],
    note="Hacia donde mira el sprite. Mismos valores que el 0x0007 del "
         "cliente. El 0x0016 c2s es otra cosa, todavia sin identificar.")
