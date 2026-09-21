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
    +8  U8    0
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


def armar_linea(mid: int, val: int = 4, opts: list = None, strings: list = None) -> bytes:
    """Construye un sub-mensaje 0x0012 completo."""
    opts = opts or []
    strings = strings or []
    cadenas_b = b''.join(s.encode('ascii', 'replace') + b'\x00' for s in strings)
    hdr = struct.pack('<IHBBB', mid, val, len(strings), len(opts), 0)
    body = cadenas_b + b''.join(struct.pack('<I', o) for o in opts)
    return struct.pack('<H', 0x0012) + hdr + body


def propio(nombre: str, faccion: str = "Heaven"):
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
    if "Angels' Tutor" in nombre:
        return [armar_linea(10101, 4, [10107, 10108, 10109, 10110])[2:]]
    if 'Jack' in nombre:
        return [armar_linea(5235, 4, [20001, 20002])[2:]]
    if 'Shiva' in nombre:
        return [armar_linea(5235, 4, [20003, 20004])[2:]]
    if 'Aurora Totem' in nombre:
        if faccion not in ("Heaven", "Neutral", "Neutrally", "Graduated"):
            return [armar_linea(5136, 0, [])[2:]]
        return [bytes.fromhex(_propios().get('Aurora Totem', {}).get('hex', 'd92700000400000400dd270000df270000e0270000de270000'))]
    if 'Breeze Totem' in nombre:
        if faccion not in ("Heaven", "Neutral", "Neutrally", "Graduated"):
            return [armar_linea(5137, 0, [])[2:]]
        return [bytes.fromhex(_propios().get('Breeze Totem', {}).get('hex', 'dc2700000400000400dd270000e5270000e6270000de270000'))]
    if 'Dark City Totem' in nombre:
        if faccion not in ("Heaven", "Neutral", "Neutrally", "Graduated"):
            return [armar_linea(5138, 0, [])[2:]]
        return [bytes.fromhex(_propios().get('Dark City Totem', {}).get('hex', 'da2700000400000400dd270000e1270000e2270000de270000'))]
    if 'Iron Totem' in nombre:
        if faccion not in ("Heaven", "Neutral", "Neutrally", "Graduated"):
            return [armar_linea(5139, 0, [])[2:]]
        return [bytes.fromhex(_propios().get('Iron Totem', {}).get('hex', 'db2700000400000400dd270000e3270000e4270000de270000'))]
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
    10125: 10130,   # Quit training confirm Yes -> 10130
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
    base = 9 + linea[6]        # detras de las cadenas, si las hay
    if len(linea) < base + 4 * n:
        return []
    return [struct.unpack_from('<I', linea, base + 4 * k)[0] for k in range(n)]


def respuesta_a(opcion_id: int, entidad: int = 0, val: int = 4):
    """Devuelve tupla de sub-mensajes: apertura de tienda y/o cierre/continuacion de dialogo."""
    if opcion_id in TIENDAS_POR_OPCION:
        if opcion_id == 12103 and entidad in TIENDAS_POR_ENTIDAD:
            shop_id = TIENDAS_POR_ENTIDAD[entidad]
        else:
            shop_id = TIENDAS_POR_OPCION[opcion_id]
        pkg_shop = struct.pack('<HH', 0x0034, shop_id)
        pkg_cierre = struct.pack('<H', 0x0012) + FIN
        return (pkg_shop, pkg_cierre)

    # Pet Expert: 6101 "Tell me about pets", 6103 "Pet Revival" (WND_PET_RESURRECT 0x0066)
    if opcion_id == 6101:
        return (armar_linea(6105, 48, [6106, 6107, 6108, 6109, 6110, 6111]),)
    if opcion_id == 6103:
        pkg_cierre = struct.pack('<H', 0x0012) + FIN
        pkg_revival = struct.pack('<HBB', 0x0066, 1, 0)
        return (pkg_revival, pkg_cierre)
    if opcion_id in (6104, 6111, 6119, 5665, 5793) or 5802 <= opcion_id <= 5812:
        return (struct.pack('<H', 0x0012) + FIN,)

    # Opcion 10110: "Quit the training" con Angels' Tutor
    if opcion_id == 10110:
        pkg_pregunta = armar_linea(10123, val, [10125, 10126])
        return (pkg_pregunta,)

    # Opcion 10109: "Graduation" con Angels' Tutor
    if opcion_id == 10109:
        pkg_pregunta = armar_linea(10118, val, [10119, 10120])
        return (pkg_pregunta,)

    # Opcion 10205: "I decided to be an Angel Protector" en un totem
    if opcion_id == 10205:
        preguntas = {
            41: 10231, 150: 10231,  # Aurora
            44: 10232, 122: 10232,  # Dark City
            43: 10233, 121: 10233,  # Iron Castle
            45: 10234, 120: 10234,  # Breeze Woods
        }
        mid = preguntas.get(entidad, 10231)
        pkg_pregunta = armar_linea(mid, val, [10235, 10236])
        return (pkg_pregunta,)

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

    # Cupid: 5747 ("Set the place for your revival.") -> Checkpoint / Savepoint
    if opcion_id == 5747:
        pkg_cierre = struct.pack('<H', 0x0012) + FIN
        import clases as _c
        pkg_aviso = _c.aviso("Revival point has been set to Angel Lyceum!", tipo=0, msg_id=_c.MSG_ITEM)
        return (pkg_aviso, pkg_cierre)
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




