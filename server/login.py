"""
Secuencia de entrada al mundo.

Emite los 21 mensajes de inicializacion en el orden medido de una captura real
(ver docs/05_SERVIDOR.md).

CRITERIO, para que quede claro que es que:

  PARAMETRIZADO -- campos que entendemos y construimos desde cero:
      0x0002  entity_id, posicion, nombre, habilidades
      0x0021  registro de quests
      0x005B  barra de habilidades
      0x005D  timestamp del servidor

  PLANTILLA    -- mensajes que sabemos emitir pero no interpretar. Se envian
                  tal como los emitio el servidor real. Es andamiaje honesto:
                  sirve para que el cliente entre, no es entender el mensaje.
      0x016F, 0x0014, 0x001E, 0x0155, 0x0156, 0x012A, 0x005C,
      0x001A, 0x001D, 0x0185
"""
import sys
import json
import time
import logging
import struct
import pathlib
from dataclasses import dataclass, field

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'proto'))
from codec import Msg
import messages  # noqa: registra los esquemas

log = logging.getLogger('app')
PLANTILLAS = pathlib.Path(__file__).parent / 'plantillas'

# mensajes que sabemos CONSTRUIR (el resto va como plantilla)
CONSTRUIDOS = {0x0002, 0x0021, 0x005B, 0x005D, 0x001A, 0x001D}


@dataclass
class Personaje:
    entity_id: int = 14509          # id de runtime
    char_id: int = 4794             # id persistente
    nombre: str = "Jugador"
    tile_x: int = 247
    tile_y: int = 24
    habilidades: list = field(default_factory=list)   # [(skill_id, nivel, exp)]
    barra: list = field(default_factory=list)         # [magic_id, ...] hasta 24
    quests: list = field(default_factory=list)        # [(quest_id, paso), ...]
    hp: int = 280
    hp_max: int = 280
    mp: int = 154
    mp_max: int = 154
    inventario: dict = field(default_factory=dict)  # {ranura: item_id}
    tutorial: int = 0        # en que tramo del tutorial va
    oro: int = 0
    stage: int = 51
    faction: str = "Heaven"
    nivel: int = 1
    exp: int = 0
    banco: dict = field(default_factory=dict)
    buffs: dict = field(default_factory=dict)


def _cargar_secuencia():
    """Secuencia de entrada al mundo, capturada de un servidor REAL.

    Reemplaza la que se armo con la captura vieja de IGG. Comparando ambas,
    a la anterior le faltaban DOS mensajes:
      - 0x018A (25 B), que va PRIMERO, antes que todo
      - 0x0064 (19.460 B), el mas grande de la secuencia
    Y varios tenian otro tamano (0x0156: 20 B contra 40; 0x001A: 209 contra
    2484). Por eso el cliente se quedaba en la pantalla de seleccion.

    Origen: logs/proxy/mundo_011628 -- 129 mensajes, 34.514 bytes.
    """
    d = PLANTILLAS / 'mundo_real'
    sec = json.loads((d / 'secuencia.json').read_text(encoding='utf-8'))
    for m in sec:
        m['datos'] = (d / m['archivo']).read_bytes()
    return sec


_SEC = None
MAPA_DE_LA_PLANTILLA = 51   # la captura es de Guide Palace


def secuencia(p: Personaje):
    """Devuelve [bytes] -- cada uno un sub-mensaje listo (opcode incluido)."""
    global _SEC
    if _SEC is None:
        _SEC = _cargar_secuencia()

    # La captura NO es solo la entrada al mundo: del indice 35 en adelante son
    # las RESPUESTAS a lo que fue haciendo el jugador que se grabo. El patron
    # 0x006D (ack vacio) + 0x0016 (direccion) + 0x0005 (ENTITY_MOVE) se repite
    # una vez por cada movimiento suyo, y los 27 ENTITY_MOVE son todos de su
    # entidad 92. Mandarlos al entrar significa anunciar los movimientos de una
    # entidad que en este servidor no existe, mas 17 mensajes de estado que son
    # de su personaje, no del nuestro. La entrada propiamente dicha son los 35
    # primeros (0..34), que terminan en 0x0027; el 35 ya es el ack del primer
    # movimiento. Con AO_SECUENCIA_COMPLETA=1 se manda todo, para comparar.
    import os as _o
    sec = _SEC if _o.environ.get('AO_SECUENCIA_COMPLETA') else _SEC[:35]

    # Los NPC de la plantilla son los de Guide Palace: Angel Raphael, el
    # Interface Tutor y Angel Aide, con sus posiciones de ese mapa. Mandarlos
    # en cualquier otro mapa los hace aparecer donde no van -- en el Lyceum
    # salian los tres flotando entre los NPC que de verdad viven ahi.
    #
    # Fuera de Guide Palace no se manda ninguno. El Lyceum tiene los suyos
    # (Shopkeeper, Skill Angel, Director Wolay, los Salesman, los Lecturer...)
    # y sus monstruos, pero sus posiciones son datos de SERVIDOR y no estan en
    # el cliente: hacen falta capturas de ese mapa para poder poblarlo.
    # 0x0008 NPC y monstruos, 0x000E los recursos, 0x0185 sus atributos.
    # Todos traen las posiciones de Guide Palace.
    NPC_DE_GUIDE_PALACE = {0x0008, 0x000E, 0x0185}
    if p.stage != MAPA_DE_LA_PLANTILLA:
        sec = [m for m in sec if m['opcode'] not in NPC_DE_GUIDE_PALACE]

    salida = []
    for m in sec:
        op, base = m['opcode'], m['datos']
        if op == 0x0002:
            salida.append(_ficha(p, base))
        elif op == 0x0021:
            salida.append(_quests(p, base))
        elif op == 0x005B:
            salida.append(_barra(p, base))
        elif op == 0x0014:
            # Opcode 0x0014: flags de mapa / radar (dword_A37C44 + 8400 en Angel.exe).
            # En sub_5AA6A0 (render del Scene Map), se comprueba:
            #   if (!sub_60D9F0(...) && !(*(_DWORD *)(v132 + 8400) & 0x20))
            # Si el bit 0x20 esta encendido, Angel.exe DESACTIVA por completo el Scene Map!
            # Antes se sobreescribia con p.entity_id (ej: 1001, 1003), que tienen el bit 0x20 encendido,
            # dejando el Scene Map completamente vacio (teal).
            # La captura oficial (init_02_0014.bin) manda 0x00000205 (517) con bit 0x20 en 0.
            salida.append(struct.pack('<H', 0x0014) + base)
        elif op == 0x001D:
            # Atributos de entidad. La plantilla trae el entity_id del
            # personaje que se grabo, asi que habia que reescribirlo: se
            # estaban anunciando los atributos de una entidad ajena.
            salida.append(struct.pack('<HI', 0x001D, p.entity_id) + base[4:])
        elif op == 0x001A:
            # El inventario. Antes se mandaba la plantilla tal cual, o sea el
            # inventario del personaje que se grabo; ahora se arma con el del
            # jugador, asi que cada item aparece en su ranura.
            import inventario as _inv
            # Con la cantidad de cada cosa: el oro vive en la ranura 0 y su
            # item_id siempre es 1 (ITEM_ORO) y su cantidad es p.oro.
            _items = [(int(r), _inv.ITEM_ORO if int(r) == _inv.RANURA_ORO else int(it),
                       p.oro if int(r) == _inv.RANURA_ORO else 1)
                      for r, it in p.inventario.items()]
            salida.append(_inv.completo(p.char_id, _items))

        elif op == 0x0008:
            # En Guide Palace (stage 51), asegurar las coordenadas exactas de AngelWar:
            # Raphael (19) en (244, 30), Tutor (20) en (236, 27), Aide (21) en (252, 27)
            b = bytearray(base)
            ent = struct.unpack_from('<I', b, 0)[0]
            if p.stage == 51:
                if ent == 19:
                    struct.pack_into('<II', b, 8, 244, 30)
                elif ent == 20:
                    struct.pack_into('<II', b, 8, 236, 27)
                elif ent == 21:
                    struct.pack_into('<II', b, 8, 252, 27)
            salida.append(struct.pack('<H', 0x0008) + bytes(b))
        elif op == 0x005D:
            salida.append(struct.pack('<HI', 0x005D, int(time.time())))
        elif op == 0x0196:
            # Opcode 0x0196 lleva el stage del mapa en offset 8 (2 bytes)
            b = bytearray(base)
            if len(b) >= 10:
                struct.pack_into('<H', b, 8, p.stage)
            salida.append(struct.pack('<H', 0x0196) + bytes(b))
        else:
            salida.append(struct.pack('<H', op) + base)   # plantilla tal cual
    salida += poblar(p.stage)
    # Atributos nativos iniciales del personaje (HP, MP, EXP bar)
    import combate as _cb_ini
    hp_val = 280 if (not p.habilidades and p.nivel == 1 and p.hp <= 205) else p.hp
    salida.append(_cb_ini.atributo(p.entity_id, hp_val, _cb_ini.KIND_HP))
    salida.append(_cb_ini.atributo(p.entity_id, p.mp, _cb_ini.KIND_MP))
    salida.append(_cb_ini.atributo(p.entity_id, p.exp, _cb_ini.KIND_EXP))
    # La barra de experiencia necesita los cuatro valores, no solo el actual:
    # sin el "cuanto falta para el siguiente nivel" el cliente la dibujaba
    # llena y con el numero de un personaje de nivel 1. Es el mismo 0x001D
    # compuesto que se manda al subir de nivel.
    #   kind 29 nivel, 30 exp actual, 31 exp del siguiente nivel, 32 la barra
    salida.append(
        struct.pack('<HIB', 0x001D, p.entity_id, 4)
        + struct.pack('<BII', 29, p.nivel, 0)
        + struct.pack('<BII', 30, p.exp, 0)
        + struct.pack('<BII', 31, _cb_ini.exp_para_nivel(p.nivel + 1), 0)
        + struct.pack('<BII', 32, p.exp, 0))
    return salida


PLAYGROUND_MONSTERS = {
    42: [  # East Playground: Slarm, Lily, Water Elf, Earth Elf, Wind Elf, Fire Elf
        (701, 19, "Slarm", (25, 110)),
        (702, 19, "Slarm", (35, 105)),
        (703, 19, "Slarm", (45, 115)),
        (704, 7, "Lily", (30, 95)),
        (705, 7, "Lily", (40, 85)),
        (706, 3, "Water Elf", (55, 100)),
        (707, 3, "Water Elf", (65, 110)),
        (708, 4, "Earth Elf", (50, 90)),
        (709, 4, "Earth Elf", (60, 80)),
        (710, 1, "Wind Elf", (70, 95)),
        (711, 1, "Wind Elf", (80, 105)),
        (712, 2, "Fire Elf", (85, 90)),
        (713, 2, "Fire Elf", (95, 100)),
    ],
    43: [  # West Playground: Slarm, Lily, Water Elf, Earth Elf, Wind Elf, Fire Elf
        (801, 19, "Slarm", (175, 30)),
        (802, 19, "Slarm", (165, 40)),
        (803, 19, "Slarm", (155, 35)),
        (804, 7, "Lily", (170, 55)),
        (805, 7, "Lily", (160, 60)),
        (806, 3, "Water Elf", (145, 50)),
        (807, 3, "Water Elf", (135, 45)),
        (808, 4, "Earth Elf", (150, 65)),
        (809, 4, "Earth Elf", (140, 70)),
        (810, 1, "Wind Elf", (130, 60)),
        (811, 1, "Wind Elf", (120, 50)),
        (812, 2, "Fire Elf", (115, 65)),
        (813, 2, "Fire Elf", (105, 55)),
    ],
    57: [  # Fighting Palace: 8 Little Slarms Este + 8 Little Slarms Oeste (16 en total)
        # 8 Little Slarms Este (derecha)
        (901, 224, "Little Slarm", (226, 35)),
        (902, 224, "Little Slarm", (228, 33)),
        (903, 224, "Little Slarm", (230, 31)),
        (904, 224, "Little Slarm", (233, 27)),
        (905, 224, "Little Slarm", (225, 29)),
        (906, 224, "Little Slarm", (227, 26)),
        (907, 224, "Little Slarm", (231, 35)),
        (908, 224, "Little Slarm", (224, 32)),
        # 8 Little Slarms Oeste (izquierda)
        (909, 224, "Little Slarm", (206, 35)),
        (910, 224, "Little Slarm", (204, 33)),
        (911, 224, "Little Slarm", (202, 31)),
        (912, 224, "Little Slarm", (199, 27)),
        (913, 224, "Little Slarm", (207, 29)),
        (914, 224, "Little Slarm", (205, 26)),
        (915, 224, "Little Slarm", (201, 35)),
        (916, 224, "Little Slarm", (208, 32)),
    ],
}


def _monster_spawn(entity_id, npc_type, nombre, tile):
    """Arma un NPC_SPAWN (0x0008) 100% identico a la captura real."""
    b = bytearray(63)
    struct.pack_into('<IIII', b, 0, entity_id, 0, tile[0], tile[1])
    n = str(nombre).encode('ascii', 'replace')[:16]
    b[16:16 + len(n)] = n
    SPRITES = {19: 42107, 7: 42041, 1: 42055, 2: 42056, 3: 42057, 4: 42058, 224: 42107}
    sprite_id = SPRITES.get(npc_type, 42107)
    b[32] = 0
    b[33] = 4 if npc_type == 19 else 1
    struct.pack_into('<H', b, 34, sprite_id)
    struct.pack_into('<H', b, 38, 7)
    struct.pack_into('<I', b, 40, 1)  # klass 1 = monster
    b[44] = 4 if npc_type == 19 else 3
    b[45] = npc_type & 0xFF
    b[46] = (npc_type >> 8) & 0xFF
    b[47] = 0x08
    b[48] = 0x80
    return struct.pack('<H', 0x0008) + bytes(b)


def rotar(entity_id: int, angulo: int) -> bytes:
    """0x0016: orienta a una entidad. [u4 entity][u1 angulo].

    La direccion NO viaja en el 0x0008: los diez Angel Raphael de la captura
    solo difieren en id y posicion, y el campo del offset 4 solo vale 0 o 1
    (es un flag, no un angulo). Asi que hay que mandarla aparte.
    """
    return struct.pack('<HIB', 0x0016, entity_id, angulo & 0xFF)


_TOTEM_BASE = None


# Los totems NO son NPC: son objetos de mapa, o sea 0x000E, igual que las
# vetas y los arboles. En el Angel Lyceum son los recursos 150, 121, 122 y 120
# de lyceum.json, con sprite 60051..60054 y la posicion en PIXELES. Por eso
# mandarlos como 0x0008 no funcionaba de ninguna manera: con el flag del
# offset 4 en 1 salia el nombre flotando y ningun dibujo, y con el sprite de
# npc.xml (40001) salia un NPC humanoide.
# Hacia donde mira Angel Raphael en el Fighting Palace. 0..7; probado:
# 2 = arriba, 4 = izquierda, 6 y 0 = derecha. Poner None para no mandar
# ninguna rotacion y dejarlo como viene por defecto.
ANGULO_RAPHAEL = 6

SPRITE_TOTEM = {'Aurora Totem': 60051, 'Dark City Totem': 60052,
                'Iron Totem': 60053, 'Breeze Totem': 60054}
# entity_id -> nombre de todo lo que se pone en el Fighting Palace, para que
# el clic encuentre su dialogo sin depender de ids escritos a mano.
TOTEMS_PUESTOS = {}
_TOTEM_OBJ = None


def _totem_objeto(entity_id: int, nombre: str, tile) -> bytes:
    """Un totem como objeto de mapa (0x000E), copiado del Lyceum."""
    global _TOTEM_OBJ
    if _TOTEM_OBJ is None:
        _TOTEM_OBJ = {}
        f = PLANTILLAS / 'lyceum.json'
        if f.exists():
            porsprite = {v: k for k, v in SPRITE_TOTEM.items()}
            for e in json.loads(f.read_text(encoding='utf-8')).get('recursos', []):
                b = bytes.fromhex(e['hex'])
                if len(b) < 36:
                    continue
                s = struct.unpack_from('<H', b, 34)[0]
                if s in porsprite:
                    _TOTEM_OBJ[porsprite[s]] = b
    base = _TOTEM_OBJ.get(nombre)
    if base is None:
        return None
    b = bytearray(base)
    struct.pack_into('<I', b, 0, entity_id)
    struct.pack_into('<II', b, 8, tile[0] * 32 + 16, tile[1] * 32 + 16)
    TOTEMS_PUESTOS[entity_id] = nombre
    return struct.pack('<H', 0x000E) + bytes(b)


_SPRITES_NPC = None


def sprite_de(npc_type: int, por_defecto: int = 40001) -> int:
    """El 圖號 de setting/eng/npc.xml para ese npc_type.

    El campo del offset 34 del 0x0008 no es un numero de sprite libre: es el
    圖號 de npc.xml. Los cuatro totems (1937-1940) lo tienen en 40001, no en
    60241 -- 60241 es el de "House Bulletin" (npc 2625), y por eso el cliente
    creaba la entidad, le ponia el nombre, y no dibujaba nada.
    """
    global _SPRITES_NPC
    if _SPRITES_NPC is None:
        import re as _re
        _SPRITES_NPC = {}
        raiz = pathlib.Path('G:/extracted_paks')
        for pak in ('update26', 'UPDATE18', 'data1'):
            f = raiz / pak / 'setting' / 'eng' / 'npc.xml'
            if not f.exists():
                continue
            for m in _re.finditer(r'<npc 編號="(\d+)" 圖號="(\d+)"',
                                  f.read_text(encoding='utf-8', errors='replace')):
                _SPRITES_NPC.setdefault(int(m.group(1)), int(m.group(2)))
            if _SPRITES_NPC:
                break
    return _SPRITES_NPC.get(npc_type, por_defecto)


def _totem_de_lyceum(entity_id: int, nombre: str, tile) -> bytes:
    """Un totem copiado BYTE A BYTE del que funciona en el Angel Lyceum.

    En el Lyceum los cuatro totems se ven y responden; en el Fighting Palace,
    armados con _totem_spawn(), no aparecian pese a que los dos mensajes
    parecian iguales. Asi que en vez de reconstruirlos se toma el 0x0008 de
    lyceum.json -- que viene de una captura de ESTA version del servidor -- y
    solo se le cambian el entity_id y la casilla.
    """
    global _TOTEM_BASE
    if _TOTEM_BASE is None:
        _TOTEM_BASE = {}
        f = PLANTILLAS / 'lyceum.json'
        if f.exists():
            for e in json.loads(f.read_text(encoding='utf-8'))['spawns']:
                if 'Totem' in e['nombre']:
                    _TOTEM_BASE[e['nombre']] = bytes.fromhex(e['hex'])
    base = _TOTEM_BASE.get(nombre)
    if base is None:
        return None
    b = bytearray(base)
    struct.pack_into('<I', b, 0, entity_id)
    struct.pack_into('<II', b, 8, tile[0], tile[1])
    # El flag del offset 4 vale 1 en los NPC que SI se dibujan (Angel Raphael
    # aparece con flag=1) y 0 en los totems, que no aparecian. Celestia manda
    # 0 en los totems, pero su cliente es de otra version. Se fuerza a 1.
    struct.pack_into('<I', b, 4, 1)
    return struct.pack('<H', 0x0008) + bytes(b)


def _totem_spawn(entity_id: int, npc_type: int, nombre: str, tile: tuple) -> bytes:
    """Arma un NPC_SPAWN (0x0008) identico al de lyceum.json para los totems de faccion."""
    b = bytearray(63)
    struct.pack_into('<IIII', b, 0, entity_id, 0, tile[0], tile[1])
    n = str(nombre).encode('ascii', 'replace')[:16]
    b[16:16 + len(n)] = n
    b[33] = 0x06
    struct.pack_into('<H', b, 34, 60241)
    struct.pack_into('<I', b, 40, 200)
    struct.pack_into('<H', b, 45, npc_type)
    return struct.pack('<H', 0x0008) + bytes(b)


def _npc_spawn(entity_id, npc_type, nombre, tile, sprite=0, klass=200,
               direccion=None):
    """Arma un NPC_SPAWN (0x0008) desde cero, para los NPC y monstruos.

    `direccion` va en el byte 33. Celestia manda 6 ahi en todos sus NPC y
    nosotros mandabamos 0: por eso Angel Raphael miraba a la derecha en vez
    de al frente. Los totems del Lyceum, que se ven bien orientados, tambien
    llevan 6. El 0x0016 rotate no sirve para esto: se probaron los ocho
    valores y el NPC no gira.
    """
    if klass == 1:
        return _monster_spawn(entity_id, npc_type, nombre, tile)
    b = bytearray(63)
    struct.pack_into('<IIII', b, 0, entity_id, 1, tile[0], tile[1])
    n = str(nombre).encode('ascii', 'replace')[:16]
    b[16:16 + len(n)] = n
    if not sprite:
        sprite = 40001
    if direccion is not None:
        b[33] = direccion & 0xFF
    struct.pack_into('<I', b, 34, sprite)
    struct.pack_into('<I', b, 40, klass)
    struct.pack_into('<H', b, 45, npc_type)
    return struct.pack('<H', 0x0008) + bytes(b)


def npc_de_los_xml(stage: int, desde=900):
    """NPC de quest que el cliente trae colocados en sus xml.

    No hacen falta capturas: sp_v##_questnpc.xml da el npc_type, el mapa y el
    tile. Los entity_id se inventan a partir de `desde` para no chocar con los
    de las capturas, que son bajos.
    """
    f = PLANTILLAS / 'npc_por_mapa.json'
    if not f.exists():
        return []
    d = json.loads(f.read_text(encoding='utf-8')).get('mapas', {})
    salida = []
    for k, e in enumerate(d.get(str(stage), [])):
        salida.append(_npc_spawn(desde + k, e['npc_type'], e['nombre'],
                                 e['tile'], e.get('sprite', 0)))
    return salida


def spawn_de(stage: int):
    """Tile de aparicion del mapa, de setting/eng/jumpmap.xml."""
    f = PLANTILLAS / 'jumpmap.json'
    if not f.exists():
        return None
    for d in json.loads(f.read_text(encoding='utf-8'))['destinos']:
        if d['stage'] == stage:
            return tuple(d['tile'])
    return None


def portales_de(stage: int):
    """Los 0x000E de los tornados que hay que dibujar en este mapa.

    Los del Lyceum ya vienen en lyceum.json; los de otros mapas se arman
    copiando ese mismo objeto y cambiandole id y posicion, igual que se hizo
    con los totems del Fighting Palace.
    """
    f = PLANTILLAS / 'portales.json'
    if not f.exists():
        return []
    cfg = json.loads(f.read_text(encoding='utf-8'))
    base_hex = cfg.get('plantilla_hex')
    if not base_hex:
        return []
    salida = []
    for por in cfg.get('mapas', {}).get(str(stage), []):
        if not por.get('dibujar'):
            continue
        b = bytearray(bytes.fromhex(base_hex))
        struct.pack_into('<I', b, 0, por['entity'])
        struct.pack_into('<II', b, 8,
                         por['tile'][0] * 32 + 16, por['tile'][1] * 32 + 16)
        salida.append(struct.pack('<H', 0x000E) + bytes(b))
    return salida


def poblar(stage: int):
    """NPC, monstruos, portales y totems propios del mapa."""
    salida = npc_de_los_xml(stage)
    salida += portales_de(stage)
    if stage == 57:
        # Fighting Palace: los diez Angel Raphael y los cuatro totems, con los
        # 0x0008 tal cual los manda Celestia. Antes estaban en posiciones
        # inventadas (209,39), (212,40)... y Raphael con klass=200 cuando es
        # 199, ademas de que solo se ponia uno de los diez.
        fp = PLANTILLAS / 'fighting_palace.json'
        if fp.exists():
            d_fp = json.loads(fp.read_text(encoding='utf-8'))
            # Se reconstruyen con nuestro constructor: el 0x0008 de Celestia
            # mide 62 o 64 bytes y este cliente espera 63. Reenviar los bytes
            # crudos lo crashea al entrar al mapa.
            for k, e in enumerate(d_fp['spawns']):
                if 'Totem' in e['nombre']:
                    # Los totems son objetos de mapa (0x000E), no NPC.
                    m_obj = _totem_objeto(300 + k, e['nombre'], tuple(e['tile']))
                    if m_obj is not None:
                        salida.append(m_obj)
                        continue
                # Todo lo demas -- los diez Angel Raphael -- como NPC, con su
                # direccion en el byte 33.
                TOTEMS_PUESTOS[300 + k] = e['nombre']
                salida.append(_npc_spawn(300 + k, e['npc_type'],
                                         e['nombre'], tuple(e['tile']),
                                         sprite=sprite_de(e['npc_type']),
                                         klass=e['klass'],
                                         direccion=ANGULO_RAPHAEL))
            # Ademas del byte 33 se manda el 0x0016: con el spawn solo,
            # Angel Raphael queda mirando a la derecha. Asi estaba cuando el
            # usuario lo dio por bueno.
            if ANGULO_RAPHAEL is not None:
                for k, e in enumerate(d_fp['spawns']):
                    if e['nombre'] == 'Angel Raphael':
                        salida.append(rotar(300 + k, ANGULO_RAPHAEL))
            _tot = sum(1 for e in d_fp['spawns'] if 'Totem' in e['nombre'])
            log.info('Fighting Palace: %d spawns de fighting_palace.json '
                     '(%d totems, %d Raphael)', len(d_fp['spawns']), _tot,
                     len(d_fp['spawns']) - _tot)
    if stage in PLAYGROUND_MONSTERS:
        for eid, ntype, nom, tile in PLAYGROUND_MONSTERS[stage]:
            salida.append(_npc_spawn(eid, ntype, nom, tile, klass=1))
        return salida
    f = PLANTILLAS / 'lyceum.json'
    if stage != 41 or not f.exists():
        return salida
    d = json.loads(f.read_text(encoding='utf-8'))
    salida += [struct.pack('<H', 0x0008) + bytes.fromhex(e['hex'])
               for e in d['spawns']]
    # Los recursos del mapa: vetas de cobre, arboles, hierbas, madrigueras.
    salida += [struct.pack('<H', 0x000E) + bytes.fromhex(e['hex'])
               for e in d.get('recursos', [])]
    return salida


def _ficha(p, base):
    m = Msg.registry[(0x0002, 's2c', 'privado')]
    d = m.parse(base)
    d['entity_id'] = p.entity_id
    d['tile_x'], d['tile_y'] = p.tile_x, p.tile_y
    d['flags'] = 0
    # En 0x0002, el mapa/stage real va en el offset 3953 (offset 3235 dentro de 'resto')
    r = bytearray(d['resto'])
    if len(r) >= 3239:
        struct.pack_into('<I', r, 3235, p.stage)
        d['resto'] = bytes(r)
    nom = p.nombre.encode('ascii', 'replace')[:33]
    d['name_raw'] = nom + b'\x00' * (34 - len(nom))
    u50 = bytearray(d['unk_50'])
    if len(u50) >= 24:
        # En el servidor oficial (mundo_021229), el nivel es un Big-Endian DWORD en offset 12:
        # [12..15] = 00 00 00 [nivel]. La exp va en offset 19 LE32.
        struct.pack_into('>I', u50, 12, max(1, p.nivel))
        struct.pack_into('<I', u50, 19, p.exp & 0xFFFFFFFF)
        d['unk_50'] = bytes(u50)
    # HP y MP. El campo 'stats' arranca en +102 de la ficha, asi que los
    # cuatro LE32 del principio son hp, hp_max, mp, mp_max (+102, +106,
    # +110, +114). Localizados buscando los 296 y 218 que el cliente mostraba
    # en pantalla con la plantilla sin tocar: eran los del personaje de otro
    # servidor, no los del jugador.
    st = bytearray(d['stats'])
    hp_val = 280 if (not p.habilidades and p.nivel == 1 and p.hp <= 205) else p.hp
    hp_max_val = 280 if (not p.habilidades and p.nivel == 1 and p.hp_max <= 205) else p.hp_max
    struct.pack_into('<IIII', st, 0, hp_val, hp_max_val, p.mp, p.mp_max)
    d['stats'] = bytes(st)
    if p.habilidades:
        sk = list(d['skills'])
        for i, (sid, nivel, exp) in enumerate(p.habilidades[:36]):
            sk[i] = {'skill_id': sid, 'level': nivel, 'level2': nivel,
                     'cero': b'\x00' * 4, 'exp': exp, 'idx': i + 1}
        for i in range(len(p.habilidades), 36):
            sk[i] = {'skill_id': 0, 'level': 0, 'level2': 0,
                     'cero': b'\x00' * 4, 'exp': 0, 'idx': 0}
        d['skills'] = sk
    return m.build(**d)


def _quests(p, base):
    m = Msg.registry[(0x0021, 's2c', 'privado')]
    if not p.quests:
        return struct.pack('<H', 0x0021) + base
    qs = [{'char_id': p.char_id, 'quest_id': q, 'paso': s, 'resto': b'\x00' * 11}
          for q, s in p.quests]
    return m.build(n=len(qs), quests=qs)


def _barra(p, base):
    m = Msg.registry[(0x005B, 's2c', 'privado')]
    if not p.barra:
        return struct.pack('<H', 0x005B) + base
    r = [{'usada': 1, 'magic_id': mid, 'resto': b'\x00' * 6} for mid in p.barra[:24]]
    r += [{'usada': 0, 'magic_id': 0, 'resto': b'\x00' * 6}] * (24 - len(r))
    return m.build(ranuras=r)
