"""
Dialogo con los NPC.

Protocolo, establecido con una captura del servidor privado que lleva marca de
tiempo en los dos sentidos (logs/proxy/*_orden.jsonl, tools/correlacionar.py):

    C -> S  0x0005  [LE32 entity_id][LE16 0]   clic en el NPC
    C -> S  0x0007  [U8 direccion]             el personaje se gira hacia el
    S -> C  0x0012  una linea de dialogo
    C -> S  0x000B  [U8 01]                    "siguiente"
    S -> C  0x0012  la linea siguiente
      ...
    S -> C  0x0012  nueve ceros                se acabo, cerrar el cuadro

Forma de la linea (0x0012):

    +0  LE32  id del texto      el texto en si vive en el cliente
    +4  LE16  valor             3 para Raphael, 2 para el Tutor, 52 para Aide
    +6  U8    cuantas cadenas vienen despues
    +7  U8    cuantas opciones de menu vienen despues
    +8  U8    0 SIEMPRE, lleve cadenas u opciones
    +9        primero las cadenas (terminadas en NUL), despues las opciones
              (LE32 con el id de dialogo de cada una)

Comprobado con las dos formas que aparecen en la captura: la primera linea de
Angel Raphael trae +6=2 y +7=0, y sus dos cadenas son "1" y el nombre del
jugador; la del Interface Tutor trae +6=0 y +7=2, y detras van los ids 5241 y
5242, que son las dos opciones que ofrece.

El texto NO viaja por la red: el servidor manda el id y el cliente lo busca.
Por eso alcanza con reproducir los ids para que salgan los dialogos.

De donde salen los ids: de la captura, no inventados. Son los del tutorial de
Guide Palace, iguales para cualquier personaje nuevo -- no son progreso de
nadie. Lo unico que se sustituye es el nombre del jugador, que el servidor
manda como parametro en la primera linea de Angel Raphael.
"""
import json
import pathlib
import struct

PLANTILLA = pathlib.Path(__file__).parent / 'plantillas' / 'dialogos_guide_palace.json'
FIN = bytes(9)                      # nueve ceros = cerrar el cuadro
_GUION = None


def _cargar():
    global _GUION
    if _GUION is None:
        crudo = json.loads(PLANTILLA.read_text(encoding='utf-8'))
        _GUION = {int(k): [bytes.fromhex(x) for x in v] for k, v in crudo.items()}
    return _GUION


def _con_nombre(linea: bytes, nombre: str) -> bytes:
    """Cambia el nombre del personaje grabado por el de quien esta jugando.

    Solo toca lineas que traigan cadenas (+6 > 0). El nombre es la ultima
    cadena de la lista.
    """
    if len(linea) <= 9 or linea[6] == 0:
        return linea
    partes = linea[9:].split(b'\x00')
    if len(partes) < 2:
        return linea
    partes[-2] = nombre.encode('ascii', 'replace')[:33]
    return linea[:9] + b'\x00'.join(partes)


def guion(entity_id: int):
    """Las lineas de dialogo de ese NPC, o None si no se le conoce ninguna."""
    return _cargar().get(entity_id)


def linea(entity_id: int, paso: int, nombre: str) -> bytes:
    """Sub-mensaje 0x0012 con la linea `paso`, o el de cierre si ya no hay."""
    g = guion(entity_id)
    if not g or paso >= len(g):
        return struct.pack('<H', 0x0012) + FIN
    return struct.pack('<H', 0x0012) + _con_nombre(g[paso], nombre)


def linea_de(guion, paso: int, nombre: str) -> bytes:
    """Sub-mensaje 0x0012 con la linea `paso` de ese guion, o el de cierre."""
    if not guion or paso >= len(guion):
        return struct.pack('<H', 0x0012) + FIN
    return struct.pack('<H', 0x0012) + _con_nombre(guion[paso], nombre)


def hay_mas(entity_id: int, paso: int) -> bool:
    g = guion(entity_id)
    return bool(g) and paso < len(g)


# ------------------------------------------------- tutorial por etapas
# El guion del tutorial, medido del servidor privado. Cada tramo es una
# conversacion entera: el jugador habla, avanza con 0x000B y al final llega el
# 0x0012 de ceros. Al terminar un tramo el personaje pasa al siguiente.
#
#   Angel Raphael
#     0  5001..5005  elegir clase
#     1  5006, 5007 (opciones 5008/5009), 5014..5018  da la ropa y ensena a
#                                                     equiparsela
#     2  5021, 5039..5043  confirma y da 10 de oro para el examen
#     3  5047  confirma el examen; despues cambia de mapa
#
#   Angel Aide
#     0  5022 (opciones 5045 comprar / 5046 salir)
#
# El entity_id de los NPC CAMBIA entre sesiones: Raphael fue 19 en unas
# capturas y 16 en otras. Por eso el guion va por nombre y no por numero.
TUTORIAL = pathlib.Path(__file__).parent / 'plantillas' / 'tutorial.json'
NOMBRE_POR_ENTIDAD = {19: 'raphael', 20: 'interface', 21: 'aide'}
_TUT = None


def _tutorial():
    global _TUT
    if _TUT is None:
        crudo = json.loads(TUTORIAL.read_text(encoding='utf-8'))
        _TUT = {k: [[bytes.fromhex(x) for x in tramo] for tramo in v]
                for k, v in crudo.items() if not k.startswith('_')}
    return _TUT


def recargar_tutorial():
    global _TUT
    _TUT = None


def guion_etapa(entity_id: int, etapa: int):
    """El tramo de dialogo que toca, o None si ese NPC ya no tiene mas."""
    nom = NOMBRE_POR_ENTIDAD.get(entity_id)
    if nom is None:
        return None
    tramos = _tutorial().get(nom, [])
    if not tramos:
        return None
    # Pasada la ultima etapa se repite la ultima, que es lo que hace el juego:
    # el NPC sigue contestando algo en vez de quedarse mudo.
    return tramos[min(etapa, len(tramos) - 1)]


def etapas(entity_id: int) -> int:
    nom = NOMBRE_POR_ENTIDAD.get(entity_id)
    return len(_tutorial().get(nom, [])) if nom else 0


# ------------------------------------------- dialogo propio de cada NPC
# Sacado de setting/eng/msg.xml, que trae los 42.036 textos del juego
# indexados por el mismo id que viaja en el 0x0012. Buscando el texto donde
# cada NPC se presenta ("I am X", "I'm X", "my name is X") se le puede dar su
# dialogo sin capturar nada: el texto vive en el cliente y el servidor solo
# manda el numero.
#
# Se llego tarde a esto: se dijo varias veces que los dialogos solo salian de
# capturas, y el jugador insistio en que estaban en los xml. Tenia razon.
DIALOGOS_NPC = pathlib.Path(__file__).parent / 'plantillas' / 'dialogos_npc.json'
_PROPIOS = None


def _propios():
    global _PROPIOS
    if _PROPIOS is None:
        if DIALOGOS_NPC.exists():
            _PROPIOS = json.loads(DIALOGOS_NPC.read_text(encoding='utf-8'))['npcs']
        else:
            _PROPIOS = {}
    return _PROPIOS


def armar_linea(mid: int, val: int = 4, opts: list = None, strings: list = None,
                acciones: list = None) -> bytes:
    """Construye un sub-mensaje 0x0012 completo.

    `acciones` son los LE32 que van DESPUES de las opciones, uno por opcion.
    En la captura del Angels' Tutor el 10102 lleva sus dos opciones y detras
    0x0f4272 y 0x0f4391, y el 10124 lleva 0x0f4393 y 0x0f4271. Nunca los
    mandabamos; los dialogos de tienda funcionan sin ellos, pero el del tutor
    los trae y conviene reproducirlos.
    """
    opts = opts or []
    strings = strings or []
    acciones = acciones or []
    cadenas_b = b''.join(s.encode('ascii', 'replace') + b'\x00' for s in strings)
    # El byte de relleno del +8 va SIEMPRE, con opciones o sin ellas. Se
    # llego a quitarlo creyendo que faltaba en las lineas con cadenas, por
    # haber copiado a mano un hex recortado de la captura; con eso todas las
    # lineas quedaban un byte corridas y el cliente se cerraba con un error.
    # Comprobado con las seis lineas del Angels' Tutor: en las seis el byte 8
    # es 0x00.
    hdr = struct.pack('<IHBBB', mid, val, len(strings), len(opts), 0)
    # El orden es opciones, acciones y AL FINAL las cadenas. Comprobado con
    # el 10201 del Aurora Angel, que lleva las dos cosas: cuatro opciones,
    # cuatro acciones y detras "1" y el nombre del jugador. Poniendo las
    # cadenas delante, una linea con las dos quedaba ilegible para el
    # cliente.
    body = (b''.join(struct.pack('<I', o) for o in opts)
            + b''.join(struct.pack('<I', a) for a in acciones)
            + cadenas_b)
    return struct.pack('<H', 0x0012) + hdr + body


# nombre -> (retrato, mensaje tras hablar con Michael, opciones, acciones)
# El Angel que vive en cada ciudad, con su menu propio. Solo esta medido el
# de Breeze Woods; los de las otras tres ciudades haran falta capturarlos.
# El Angel que vive en cada ciudad. Tiene TRES estados, medidos con el de
# Breeze Woods:
#
#   sin registrar (con la mision de registro pendiente)
#       50001, retrato 112, dos cadenas y CINCO opciones; la primera es
#       "I have come here to register!"
#   ya registrado
#       el mismo 50001 pero con CUATRO: desaparece la de registrarse
#   rango alto
#       55803, otro mensaje distinto
#
# El Angel de cada ciudad. LAS CUATRO CIUDADES SON EL MISMO DIALOGO con la
# base cambiada, y eso no es una suposicion: los cuatro bloques estan en
# msg.xml uno al lado del otro y dicen lo mismo palabra por palabra.
#
#   base    ciudad         x0001 bienvenida        x0002 registrarse
#   20000   Aurora City    "...Angel Protector of Aurora City..."
#   30000   Dark City      "...Guard Angel of Dark City..."
#   40000   Iron Castle    "...Guard Angel in Iron Castle..."
#   50000   Breeze Woods   "...Angel Protector of Breeze Woods..."
#
# y dentro de cada bloque: x0002 registrarse, x0003 la mision, x0004 el
# honor, x0005 salir, x0018 volver al Lyceum, x0019 el traslado.
#
# Las quests van igual de ordenadas en quest.xml:
#   registro  127 Aurora  128 Dark City  129 Iron Castle  130 Breeze Woods
#   conocer   133         134            135              136
#   nivel     137         138            139              140
#
# ANTES AQUI SOLO ESTABA BREEZE WOODS (stage 29). En las otras tres ciudades
# el Angel no encontraba entrada y se caia al dialogo de ELEGIR FACCION del
# Graduation Palace: salia con otro texto y otro retrato, la quest de
# registro no se completaba y la opcion de volver al Lyceum no existia.
#
# OJO: los codigos de accion (0x0f42xx) SOLO estan medidos para Breeze
# Woods. Para las otras tres se reutilizan los suyos porque la respuesta se
# despacha por el ID DE OPCION, no por la accion; si alguna vez se captura
# el Angel de otra ciudad, hay que comprobarlos.
_CIUDADES = (
    # stage, base del dialogo, indice para las quests
    (3,  20000, 0),   # Aurora City
    (26, 30000, 1),   # Dark City
    (38, 40000, 2),   # Iron Castle
    (29, 50000, 3),   # Breeze Woods  <- el unico medido
)

ANGEL_DE_CIUDAD = {}
for _st, _b, _i in _CIUDADES:
    ANGEL_DE_CIUDAD[_st] = {
        'sin_registrar': (_b + 1, (_b + 2, _b + 3, _b + 4, _b + 18, _b + 5),
                          (0x0f4258, 0x0f4252, 0x0f4254, 0x0f4260, 0)),
        'registrado': (_b + 1, (_b + 3, _b + 4, _b + 18, _b + 5),
                       (0x0f4252, 0x0f4254, 0x0f425d, 0)),
        'mision_registro': 127 + _i,
        'mision_conocer': 133 + _i,
        'mision_nivel': 137 + _i,
        'opcion_registrar': _b + 2,
        'opcion_lyceum': _b + 18,
        'msg_traslado': _b + 19,
        '_medido': _st == 29,
    }
del _st, _b, _i

# opcion -> stage, para despachar sin saber donde esta el jugador
CIUDAD_POR_OPCION = {}
for _st, _cfg in ANGEL_DE_CIUDAD.items():
    CIUDAD_POR_OPCION[_cfg['opcion_registrar']] = _st
    CIUDAD_POR_OPCION[_cfg['opcion_lyceum']] = _st
del _st, _cfg

ANGELES_FACCION = {
    'Aurora Angel':     (5,  10201, (10207, 10208, 10205, 10206),
                         (0x0f4252, 0x0f4253, 0x0f4254, 0)),
    'Dark City Angel':  (49, 10202, (10209, 10210, 10205, 10206),
                         (0x0f425d, 0x0f425e, 0x0f425f, 0)),
    'IronCastle Angel': (53, 10203, (10211, 10212, 10205, 10206),
                         (0x0f426a, 0x0f426b, 0x0f426c, 0)),
    'BreezeWood Angel': (52, 10204, (10213, 10214, 10205, 10206),
                         (0x0f4276, 0x0f4277, 0x0f4278, 0)),
}


def propio(nombre: str, faccion: str = "Heaven", jugador: str = "",
           visto_michael: bool = False, stage: int = 0,
           registrado: bool = False):
    """Una linea de dialogo para ese NPC, o None si no se le conoce ninguna."""
    if nombre == 'Director Wolay':
        if faccion in ("Heaven", "Neutral", "Neutrally", "Graduated"):
            return [armar_linea(10004, 49, [])[2:]]
        else:
            return [armar_linea(5079, 49, [5080, 5081])[2:]]
    if 'Repair Angel' in nombre:
        return [armar_linea(5100, 4, [5101, 12105])[2:]]
    if 'Cupid' in nombre:
        return [armar_linea(5745, 6, [5746, 5747, 5748])[2:]]
    # --- Graduation Palace -------------------------------------------
    # Los cuatro Angeles de faccion tienen DOS dialogos, medidos en la
    # captura del 22/09:
    #   antes de hablar con Michael  -> 10242 para los cuatro, cambiando
    #                                   solo el retrato, con las dos cadenas
    #   despues                      -> el suyo, con cuatro opciones
    # El retrato y el mensaje de cada uno:
    #   Aurora 5/10201, Dark City 49/10202, IronCastle 53/10203,
    #   BreezeWood 52/10204
    # Las dos primeras opciones de cada uno son "hablame de la ciudad" y
    # "hablame del totem"; las dos ultimas, 10205 (unirse) y 10206 (salir),
    # son iguales para los cuatro.
    # El Angel de una ciudad NO es el del Graduation Palace: tiene su propio
    # dialogo. Medido con el BreezeWood Angel de Breeze Woods: msg 55803,
    # retrato 112, cuatro opciones 20003, 20004, 20018 y 20005. La tercera es
    # "Send me back to the Angel Lyceum".
    if stage in ANGEL_DE_CIUDAD and nombre in ANGELES_FACCION:
        _cfg = ANGEL_DE_CIUDAD[stage]
        _clave = 'registrado' if registrado else 'sin_registrar'
        _msg, _ops, _acc = _cfg[_clave]
        return [armar_linea(_msg, 112, list(_ops),
                            ['1', jugador or '?'], list(_acc))[2:]]
    if nombre in ANGELES_FACCION:
        _retrato, _msg, _ops, _acc = ANGELES_FACCION[nombre]
        # El cambio de dialogo depende de haber hablado con MICHAEL, no de
        # la faccion: al llegar al Graduation Palace el personaje ya viene
        # como "Graduated", asi que atandolo a la faccion se veia siempre el
        # segundo dialogo sin haber hablado con el.
        if visto_michael:
            # Solo el de Aurora lleva las cadenas con el nombre; los otros
            # tres van sin ninguna. Asi esta en la captura.
            _cad = ['1', jugador or '?'] if _msg == 10201 else []
            return [armar_linea(_msg, _retrato, list(_ops),
                                _cad, list(_acc))[2:]]
        return [armar_linea(10242, _retrato, [], ['1', jugador or '?'])[2:]]
    if nombre == 'Michael':
        # Cinco lineas seguidas. La primera y la ultima llevan el nombre.
        return [armar_linea(10130, 1, [], ['1', jugador or '?'])[2:],
                armar_linea(10131, 1, [])[2:],
                armar_linea(10132, 1, [])[2:],
                armar_linea(10133, 1, [])[2:],
                armar_linea(10134, 1, [], ['1', jugador or '?'])[2:]]

    if "Angels' Tutor" in nombre:
        # Dos lineas seguidas, copiadas de la captura:
        #   10101  val 2, dos cadenas ("1" y el nombre), sin opciones
        #   10102  val 2, opciones 10135 y 10110 + una accion por opcion
        # Van las DOS opciones con sus dos acciones, exactamente como el
        # servidor real. Se probo recortarlo a la de salir y fue un error:
        # el cliente elige por INDICE, y con una sola opcion "Quit" pasaba a
        # ser la 0 mientras el cliente manda la 1. La otra opcion (10135) no
        # lleva a ningun lado aqui, asi que cierra el cuadro.
        return [armar_linea(10101, 2, [], ['1', jugador or '?'])[2:],
                armar_linea(10102, 2, [10135, 10110],
                            acciones=[0x0f4272, 0x0f4391])[2:]]
    if 'Jack' in nombre:
        return [armar_linea(5235, 4, [20001, 20002])[2:]]
    if 'Shiva' in nombre:
        return [armar_linea(5235, 4, [20003, 20004])[2:]]
    if 'Aurora Totem' in nombre:
        # msg.xml 5136. Un totem solo dice su frase: el bloque
        # anterior devolvia, para faccion Heaven, el dialogo 10201 que es
        # del Angel Protector ('I'm the Angel Protector from Aurora City').
        return [armar_linea(5136, 0, [])[2:]]
    if 'Breeze Totem' in nombre:
        # msg.xml 5139. Un totem solo dice su frase: el bloque
        # anterior devolvia, para faccion Heaven, el dialogo 10201 que es
        # del Angel Protector ('I'm the Angel Protector from Aurora City').
        return [armar_linea(5139, 0, [])[2:]]
    if 'Dark City Totem' in nombre:
        # msg.xml 5137. Un totem solo dice su frase: el bloque
        # anterior devolvia, para faccion Heaven, el dialogo 10201 que es
        # del Angel Protector ('I'm the Angel Protector from Aurora City').
        return [armar_linea(5137, 0, [])[2:]]
    if 'Iron Totem' in nombre:
        # msg.xml 5138. Un totem solo dice su frase: el bloque
        # anterior devolvia, para faccion Heaven, el dialogo 10201 que es
        # del Angel Protector ('I'm the Angel Protector from Aurora City').
        return [armar_linea(5138, 0, [])[2:]]
    d = _propios().get(nombre)
    if not d:
        return None
    # 'hex' es el cuerpo tal como lo manda el servidor real, con sus opciones
    # y su campo val, que cambia por NPC (6 Cupid, 4 Shopkeeper, 49 Wolay).
    # Sin esas opciones el cuadro sale sin las lineas de respuesta.
    return [bytes.fromhex(d['hex'])]


# ------------------------------------------- elegir una opcion del cuadro
PRIMERA_OPCION = 10
RESPUESTAS = {
    5798: 5800,
    # Descripciones de ciudades y totems
    10207: 10215,
    10208: 10223,
    10209: 10217,
    10210: 10224,
    10211: 10219,
    10212: 10225,
    10213: 10221,
    10214: 10226,
    # Pet Expert
    6101: 6105,
    6106: 6112,
    6107: 6113,
    6108: 6114,
    6109: 6115,
    6110: 6116,
    # Angels' Tutor
    10107: 10112,   # Score Regulation
    10108: 10115,   # Top Student Training
    # Medido: al decir que si llega el 10127 ("What a pity! ... I now will
    # transport you to Graduation Palace"), no el 10130. El 10130 es el
    # saludo de Michael, que ya es del otro mapa.
    10125: 10127,   # Quit training, confirmar -> 10127
    10119: 10121,   # Graduate confirm Yes -> 10121
}

# Tiendas especificas segun la entidad del NPC que vende (para opcion 12103)
TIENDAS_POR_ENTIDAD = {
    11: 17,    # Scroll Seller (Lyceum) -> Shop 17 (Combat Skill Scrolls: Crazy Roar, Recovery Shield, etc.)
    19: 18,    # Magic Seller (Lyceum) -> Shop 18 (Magic Scrolls: Shock Wave, Cure Spell, etc.)
    46: 21,    # C. Plan Seller (Lyceum) -> Shop 21 (Craft / Wood recipes)
    47: 22,    # C. Plan Seller (Lyceum) -> Shop 22 (Tailor / Sewing recipes)
    17: 16,    # Ironsmith (Lyceum) -> Shop 16 (Weaponsmith recipes)
    18: 20,    # Ironsmith (Lyceum) -> Shop 20 (Armorsmith recipes)
    36: 2,     # Weapon Salesman -> Shop 2
    37: 3,     # Armor Salesman -> Shop 3
    38: 5,     # Sewing Salesman -> Shop 5
    39: 7,     # Cooking Salesman -> Shop 7
    40: 6,     # Art Saleman -> Shop 6
    24: 1,     # Shopkeeper -> Shop 1
}

# Opciones de dialogo que abren la ventana de tienda (WND_NPCSALE).
# Medido en sub_605190/sub_656E70 del cliente: opcode S->C 0x0034 [LE16 shop_id].
TIENDAS_POR_OPCION = {
    12103: 1,    # Default compra/venta
    6102: 69,    # Pet Expert -> Shop 69 (Comida y galletas de mascota)
    5045: 37,    # Angel Aide (Guide Palace) -> Shop 37
}


def es_opcion(valor: int) -> bool:
    return valor >= PRIMERA_OPCION


def indice_opcion(valor: int) -> int:
    return valor - PRIMERA_OPCION


def opciones_de(linea: bytes):
    """Los ids de opcion que lleva una linea de dialogo."""
    if len(linea) < 9 or not linea[7]:
        return []
    n = linea[7]
    base = 9                   # las opciones van siempre justo tras la cabecera
    if len(linea) < base + 4 * n:
        return []
    return [struct.unpack_from('<I', linea, base + 4 * k)[0] for k in range(n)]


def respuesta_a(opcion_id: int, entidad: int = 0, val: int = 4,
                nombre: str = '', stage: int = 0, nivel: int = 0):
    """Devuelve tupla de sub-mensajes: apertura de tienda y/o cierre/continuacion de dialogo."""
    if opcion_id in TIENDAS_POR_OPCION:
        if opcion_id == 12103 and entidad in TIENDAS_POR_ENTIDAD:
            shop_id = TIENDAS_POR_ENTIDAD[entidad]
        else:
            shop_id = TIENDAS_POR_OPCION[opcion_id]
        pkg_shop = struct.pack('<HH', 0x0034, shop_id)
        pkg_cierre = struct.pack('<H', 0x0012) + FIN
        return (pkg_shop, pkg_cierre)

    if opcion_id == 5976:
        if nivel >= 60:
            return (armar_linea(7503, val, [7505, 7506],
                                acciones=[0x0f42dc, 0x0f42dd]),)
        return (armar_linea(7504, val, [7507, 7508],
                            acciones=[0x0f42de, 0x0f42df]),)
    if opcion_id == 7509:
        return (armar_linea(7510, val), armar_linea(7511, val))
    if opcion_id == 7554 or opcion_id in (7505, 7506, 7507, 7508):
        return (struct.pack('<H', 0x0012) + FIN,)

    # Pet Expert: 6101 "Tell me about pets", 6103 "Pet Revival" (WND_PET_RESURRECT 0x0066)
    if opcion_id == 6101:
        return (armar_linea(6105, 48, [6106, 6107, 6108, 6109, 6110, 6111]),)
    if opcion_id == 6103:
        pkg_cierre = struct.pack('<H', 0x0012) + FIN
        pkg_revival = struct.pack('<HBB', 0x0066, 1, 0)
        return (pkg_revival, pkg_cierre)
    if opcion_id in (6104, 6111, 6119, 5665, 5793) or 5802 <= opcion_id <= 5812:
        return (struct.pack('<H', 0x0012) + FIN,)

    # Opcion 10110: "Quit the training" con Angels' Tutor.
    # La confirmacion es el 10124 con val 2, no el 10123: medido en la
    # captura, 8c270000 02 0000 02 00 | 8d270000 8e270000, o sea msg 10124,
    # val 2, dos opciones 10125 (si) y 10126 (no).
    if opcion_id == 10110:
        # Son DOS lineas, medidas en la captura: primero el 10123 suelto
        # (val 2, sin cadenas ni opciones) y despues el 10124 con las dos
        # opciones 10125 (si) y 10126 (no). Mandabamos solo el 10123.
        return (armar_linea(10123, 2, []),
                armar_linea(10124, 2, [10125, 10126],
                            acciones=[0x0f4393, 0x0f4271]))

    # Opcion 10109: "Graduation" con Angels' Tutor
    if opcion_id == 10109:
        pkg_pregunta = armar_linea(10118, val, [10119, 10120])
        return (pkg_pregunta,)

    # Opcion 10205: "I decided to be an Angel Protector".
    #
    # La confirmacion depende de la FACCION del NPC con el que hablas. La
    # tabla iba por id de totem y los cuatro Angeles del Graduation Palace no
    # estaban en ella, asi que con cualquiera de ellos salia la de Aurora.
    # Ahora va por nombre, que sirve para los totems y para los Angeles.
    #
    # Medido con el BreezeWood Angel: msg 10234, retrato 52, opciones 10235 y
    # 10236, y una accion 0x0f427d. De las otras tres no hay captura de la
    # accion, asi que van sin ella.
    if opcion_id == 10205:
        por_nombre = {
            'aurora': (10231, ()),
            'dark city': (10232, ()),
            'iron': (10233, ()),
            'breeze': (10234, (0x0f427d, 0)),
        }
        mid, acc = 10231, ()
        _n = (nombre or '').lower()
        for clave, (m, a) in por_nombre.items():
            if clave in _n:
                mid, acc = m, a
                break
        return (armar_linea(mid, val, [10235, 10236], None, list(acc)),)

    # Opcion 50002: "I have come here to register!" con el Angel de la
    # ciudad. Medido: cinco lineas seguidas y al final las misiones nuevas y
    # la de registro completada.
    if opcion_id == 50002:
        return tuple(armar_linea(m, 112) for m in
                     (50006, 50007, 50008, 50009, 50010, 50017))

    # Opcion 20018: "Send me back to the Angel Lyceum" del Angel de una
    # ciudad. Medido: contesta con el 50019 y al cerrarse el cuadro cambia al
    # mapa 41.
    #
    # Hay DOS numeros para la misma opcion segun el menu del que salga: el
    # de rango alto (55803) la lleva como 20018 y los de registro (50001)
    # como 50018. Solo estaba puesto el primero, asi que despues de
    # registrarse el boton no hacia nada.
    if opcion_id in CIUDAD_POR_OPCION and opcion_id % 10000 == 18:
        # Cada ciudad contesta con SU mensaje de traslado, no con el de
        # Breeze Woods. Antes se devolvia siempre el 50019, asi que en
        # Aurora, Dark City o Iron Castle el jugador leia el texto de otra
        # ciudad.
        _cfg = ANGEL_DE_CIUDAD[CIUDAD_POR_OPCION[opcion_id]]
        return (armar_linea(_cfg['msg_traslado'], 112),)

    # Opcion 10235: confirmar que si. NO cierra el cuadro: quedan dos lineas
    # mas antes del viaje. Medido con el BreezeWood Angel:
    #   c2s 10 -> 10240  "I will send you to the Breeze Woods..."
    #   c2s 01 -> 10241  "At last, the Lyceum leader Michael..."
    #   c2s 01 -> las misiones, el cierre y el cambio de mapa
    # Aqui se contestaba con el cierre directamente y por eso el NPC
    # teletransportaba en el acto, sin decir nada.
    if opcion_id == 10235:
        return (armar_linea(10240, val), armar_linea(10241, val))

    # Almacen / Banco (Bao Clerk y Chief Director)
    if opcion_id in (5030, 5237):
        # Abrir almacen personal: WND_WAREHOUSE (opcode 0x002B)
        pkg_cierre = struct.pack('<H', 0x0012) + FIN
        pkg_bank = struct.pack('<HII', 0x002B, 1, 0)
        return (pkg_bank, pkg_cierre)

    # Skill Angel: 5024 ("Change Skill" / redistribucion) vs 5820 ("Choose profession skills")
    if opcion_id == 5024:
        pkg_cierre = struct.pack('<H', 0x0012) + FIN
        # 0x001D kind=10 es la ventana nativa de redistribucion de puntos
        pkg_skill_reset = struct.pack('<HIBBII', 0x001D, entidad, 1, 10, 0, 0)
        return (pkg_skill_reset, pkg_cierre)
    if opcion_id == 5820:
        pkg_cierre = struct.pack('<H', 0x0012) + FIN
        # 0x001D kind=12 es la ventana de seleccion de profesion
        pkg_prof = struct.pack('<HIBBII', 0x001D, entidad, 1, 12, 0, 0)
        return (pkg_prof, pkg_cierre)

    # Repair Angel: 5101 ("Repair the equipment.") -> abre WND_REPAIR (opcode 0x004F)
    if opcion_id == 5101:
        pkg_cierre = struct.pack('<H', 0x0012) + FIN
        pkg_repair = struct.pack('<HBB', 0x004F, 1, 0)
        return (pkg_repair, pkg_cierre)

    # Cupid: 5747 ("Set the place for your revival.") fija donde revives.
    #
    # Son DOS lineas de dialogo, 5751 y 5752, y NADA en el chat. Aqui se
    # mandaba un aviso escrito a mano ("Revival point has been set to X!")
    # que el juego no manda: el texto real sale del propio 5751, que dice
    # "Now, your [renascence place] is registered here...".
    if opcion_id == 5747:
        return (armar_linea(5751, val), armar_linea(5752, val))

    if opcion_id == 5746:
        # Descripcion de ayuda
        return (armar_linea(5749, val, []),)
    if opcion_id == 5748:
        return (struct.pack('<H', 0x0012) + FIN,)

    # Director Wolay: 5080 (Return to City), 5081 (Leave)
    if opcion_id == 5080:
        return (armar_linea(5082, val, []),)
    if opcion_id in (5081, 20002, 20004):
        return (struct.pack('<H', 0x0012) + FIN,)

    # Angel Raphael (Guide Palace)
    if opcion_id == 5009:  # "I don't want to join in." -> 5010 (preguntar si esta seguro)
        return (armar_linea(5010, 3, [5011, 5012]),)
    if opcion_id in (5012, 5242, 5046, 5059, 5064):  # Quit / cerrar
        return (struct.pack('<H', 0x0012) + FIN,)

    # Angel Raphael (Fighting Palace): 5063 "I'm ready to go to the Angel Lyceum."
    if opcion_id == 5063:
        return (armar_linea(5065, val, []),)

    sig = RESPUESTAS.get(opcion_id)
    if sig is None:
        return (struct.pack('<H', 0x0012) + FIN,)
    return (armar_linea(sig, val, []),)


def guion_fighting_palace(kills: int, nombre: str):
    """Guion de Angel Raphael en Fighting Palace segun las muertes de Little Slarm."""
    val = 5
    if kills < 2:
        return [
            armar_linea(5048, val, [], strings=["1", nombre])[2:],
            armar_linea(5049, val, [])[2:],
            armar_linea(5050, val, [])[2:],
            armar_linea(5051, val, [])[2:],
            armar_linea(5052, val, [])[2:],
            armar_linea(5053, val, [])[2:],
            armar_linea(5054, val, [])[2:],
            armar_linea(5055, val, [])[2:],
            armar_linea(5056, val, [5058, 5059])[2:],
        ]
    else:
        return [
            armar_linea(5060, val, [])[2:],
            armar_linea(5061, val, [])[2:],
            armar_linea(5062, val, [5063, 5064])[2:],
        ]




