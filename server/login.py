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
    # Cuantas unidades hay en cada casilla. La que no esta aqui lleva una.
    cantidades: dict = field(default_factory=dict)  # {ranura: cantidad}
    # Donde revive, fijado con Cupid. En cero = el punto por defecto.
    # Si ya hablo con Michael en el Graduation Palace: los Angeles de
    # faccion cambian de dialogo.
    hablo_michael: bool = False
    checkpoint_stage: int = 0
    checkpoint_x: int = 0
    checkpoint_y: int = 0
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
            # Con la cantidad REAL de cada casilla: aqui iba un 1 fijo, asi
            # que una pila de diez pociones se veia como una sola hasta que
            # algo mandara un refresco. El oro vive en la ranura 0 y su
            # cantidad es p.oro.
            _items = [(int(r), _inv.ITEM_ORO if int(r) == _inv.RANURA_ORO else int(it),
                       p.oro if int(r) == _inv.RANURA_ORO
                       else max(1, int((p.cantidades or {}).get(int(r), 1))))
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


def _monster_spawn(entity_id, npc_type, nombre, tile, sprite=0):
    """Arma un NPC_SPAWN (0x0008) de un monstruo.

    El sprite va TAL COMO SE CAPTURO. Antes salia de una tabla escrita a
    mano con seis tipos y todo lo demas caia en el 42107, que es el del
    Slarm: por eso en el Dense Forest las Wild Lily, los Nest Tree Elf, los
    Forest Monkey y los dos jefes aparecian todos como Slarms.
    """
    b = bytearray(63)
    struct.pack_into('<IIII', b, 0, entity_id, 0, tile[0], tile[1])
    n = str(nombre).encode('ascii', 'replace')[:16]
    b[16:16 + len(n)] = n
    SPRITES = {19: 42107, 7: 42041, 1: 42055, 2: 42056, 3: 42057, 4: 42058, 224: 42107}
    sprite_id = sprite or SPRITES.get(npc_type, 42107)
    b[32] = 0
    b[33] = 4 if npc_type == 19 else 1
    # EL SPRITE ES U32, NO U16. Lo escribiamos en 16 bits y cualquier sprite
    # por encima de 65535 salia truncado: el Saddy de Emerald Coast es el
    # 110564 y se convertia en 45028. Comprobado en los bytes de Celestia,
    # donde los offsets 34..37 traen e4 af 01 00, que es el 110564 entero.
    # El _npc_spawn de al lado ya lo hacia bien; eran las dos funciones
    # escribiendo el mismo campo con distinto tamano.
    struct.pack_into('<I', b, 34, sprite_id)
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


def objeto_de_mapa(r) -> bytes:
    """Un 0x000E armado desde sus datos: vetas, arboles, madrigueras, totems.

    El mensaje mide 43 bytes en los dos servidores y sus campos estan en el
    mismo sitio, comprobado contra los 158 recursos del Lyceum: el id en el
    0, la capa en el 4, la posicion en PIXELES en el 8 y el 12, y el sprite
    en el 34.
    """
    # SI HAY CRUDO, SE MANDA TAL CUAL. Rearmar por campos parecia
    # equivalente y no lo es: comprobado contra Seaside Grotto, los objetos
    # reconstruidos NO coinciden byte a byte con los que mandaba el servidor
    # original -- en unos difiere un byte y en otros trece. El cuerpo lleva
    # informacion que no sabemos leer, y al rearmarlo se perdia. El usuario
    # lo vio en pantalla antes que la comparacion: las estatuas salian con
    # la base bien y el resto mal.
    if r.get('crudo'):
        crudo = bytes.fromhex(r['crudo'])[:43]
        if len(crudo) == 43:
            return struct.pack('<H', 0x000E) + crudo
    b = bytearray(43)
    struct.pack_into('<I', b, 0, int(r['entity_id']))
    struct.pack_into('<I', b, 4, int(r.get('capa', 0)))
    struct.pack_into('<II', b, 8, int(r['px'][0]), int(r['px'][1]))
    # Los offsets 16..31 son un bloque libre: casi siempre ceros, pero en
    # algunos recursos llevan su nombre en texto ("Copper(M)").
    medio = bytes.fromhex(r.get('medio', ''))[:16]
    b[16:16 + len(medio)] = medio
    b[32] = int(r.get('marca', 0)) & 0xFF
    b[33] = int(r.get('orient', 6)) & 0xFF
    struct.pack_into('<H', b, 34, int(r['sprite']))
    cola = bytes.fromhex(r.get('cola', ''))[:7]
    b[36:36 + len(cola)] = cola
    return struct.pack('<H', 0x000E) + bytes(b)


def objeto_nombrado(r):
    """El 0x000F: el cartel con el NOMBRE del recurso, o None si no se capturo.

    Es el mismo mensaje que el 0x000E y con los mismos campos en los mismos
    sitios, con dos diferencias: en los offsets 16..31 -- donde el 0x000E lleva
    un relleno constante -- va el NOMBRE en ascii, y mide 44 bytes en vez de
    43. Comprobado entidad por entidad en las capturas: para un mismo recurso
    los dos mensajes solo se distinguen en esos 16 bytes y en el 32.

    Mandando solo el 0x000E el recurso se dibuja pero no tiene cartel: el
    cliente no tiene de donde sacar el nombre. Por eso al pasar el raton por
    una veta no salia "Bone Den(L)" como en Celestia.
    """
    nombre = r.get('nombre_visible')
    if not nombre:
        return None
    # Las plantillas viejas (lyceum) guardan el 0x000E entero en 'hex' en vez
    # de sus campos sueltos; de ahi salen la posicion y el sprite.
    px, spr = r.get('px'), r.get('sprite')
    if (px is None or spr is None) and r.get('hex'):
        crudo = bytes.fromhex(r['hex'])
        if px is None:
            px = list(struct.unpack_from('<II', crudo, 8))
        if spr is None:
            spr = struct.unpack_from('<H', crudo, 34)[0]
    if px is None or spr is None:
        return None
    b = bytearray(44)
    struct.pack_into('<I', b, 0, int(r['entity_id']))
    struct.pack_into('<I', b, 4, int(r.get('estado', r.get('capa', 0))))
    struct.pack_into('<II', b, 8, int(px[0]), int(px[1]))
    n = str(nombre).encode('ascii', 'replace')[:16]
    b[16:16 + len(n)] = n
    b[32] = int(r.get('marca_nombre', r.get('marca', 0))) & 0xFF
    b[33] = int(r.get('orient', 6)) & 0xFF
    struct.pack_into('<H', b, 34, int(spr))
    cola = bytes.fromhex(r.get('cola_nombre', ''))[:8]
    b[36:36 + len(cola)] = cola
    return struct.pack('<H', 0x000F) + bytes(b)


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
               direccion=None, visible=1):
    """Arma un NPC_SPAWN (0x0008) desde cero, para los NPC y monstruos.

    `direccion` va en el byte 33. Celestia manda 6 ahi en todos sus NPC y
    nosotros mandabamos 0: por eso Angel Raphael miraba a la derecha en vez
    de al frente. Los totems del Lyceum, que se ven bien orientados, tambien
    llevan 6. El 0x0016 rotate no sirve para esto: se probaron los ocho
    valores y el NPC no gira.
    """
    if klass == 1:
        return _monster_spawn(entity_id, npc_type, nombre, tile, sprite)
    b = bytearray(63)
    # El offset 4 decide si el nombre queda flotando sobre la entidad. En la
    # captura vale 1 SOLO en los NPC de verdad (Cupid); los totems y todos
    # los monstruos llevan 0 y su nombre se ve al pasar el raton o en el
    # mapa de escena. Mandabamos 1 para todo, asi que los totems tenian el
    # cartel pegado encima.
    struct.pack_into('<IIII', b, 0, entity_id, visible, tile[0], tile[1])
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


# UNA SOLA TABLA de plantillas de mapa. Antes habia TRES listas
# paralelas -- esta, la de _nombre_entidad y la de la IA de monstruos --
# y cada mapa nuevo habia que anadirlo a las tres a mano. Fallo cuatro
# veces: el mapa se dibujaba pero salia SIN monstruos moviendose,
# porque la entrada se habia colado dos veces en la misma lista y
# faltaba en la de la IA. El Lyceum y el Fighting Palace NO van aqui:
# se tratan aparte y cada consumidor los anade si los necesita.
PLANTILLAS_POR_STAGE = {
    2   : 'riprap_coast.json',
    3   : 'aurora_city.json',
    4   : 'dawn_harbor.json',
    5   : 'cherry_village.json',
    6   : 'spike_farm.json',
    7   : 'sunflower_plain.json',
    8   : 'crashing_hillock.json',
    9   : 'south_mirror_lake.json',
    11  : 'thunder_ruins.json',
    12  : 'north_mirror_lake.json',
    13  : 'jade_vale.json',
    15  : 'mysterious_wetland.json',
    16  : 'thorn_wasteland.json',
    17  : 'quiet_vale.json',
    18  : 'mushroom_forest.json',
    19  : 'fungus_forest_south.json',
    20  : 'foggy_forest.json',
    21  : 'dragon_graveyard.json',
    22  : 'mysterious_garden.json',
    23  : 'dense_forest.json',
    245 : 'sweet_orchard.json',
    246 : 'fruity_village.json',
    247 : 'jade_garden.json',
    248 : 'luscious_grange.json',
    249 : 'branch_way.json',
    250 : 'lost_trail.json',
    251 : 'buzzing_stopover.json',
    25  : 'fungus_forest_north.json',
    27  : 'deity_palace_ruins.json',
    28  : 'megalith_plain.json',
    29  : 'breeze_woods.json',
    30  : 'cryptic_moon_swamp.json',
    345 : 'hidden_grove.json',
    346 : 'forest_of_whispers.json',
    347 : 'teddy_amusement.json',
    349 : 'foodie_paradise.json',
    350 : 'forbidden_dusk.json',
    102 : 'river_valley.json',
    103 : 'secret_den.json',
    104 : 'waterfall_camp.json',
    105 : 'noisy_rain_forest.json',
    106 : 'ancient_glide_river.json',
    107 : 'half_beast_hamlet.json',
    108 : 'clouding_forest.json',
    109 : 'giant_wooden_stairs.json',
    151 : 'mushroom_village.json',
    152 : 'building_blocks_county.json',
    153 : 'building_blocks_city.json',
    154 : 'fruit_town.json',
    155 : 'chocolate_village.json',
    157 : 'chocolate_forest.json',
    156 : 'strawberry_garden.json',
    36  : 'gebuer_vale.json',
    222 : 'goldhill.json',
    285 : 'brilliant_boneyard.json',
    286 : 'ivory_forest.json',
    288 : 'whitefang_village.json',
    287 : 'razorex_temple.json',
    289 : 'sleepy_spring.json',
    290 : 'transient_waters.json',
    291 : 'fragrant_courtyard.json',
    223 : 'steam_town.json',
    224 : 'yeeha_bar.json',
    225 : 'agysical_tunnel.json',
    226 : 'sunset_valley.json',
    227 : 'desolate_ruins.json',
    228 : 'forbidden_sector.json',
    354 : 'whispering_hill.json',
    33  : 'burning_desert.json',
    37  : 'wishing_tear.json',
    38  : 'iron_castle.json',
    39  : 'cactus_plain.json',
    120 : 'crescent_valley.json',
    121 : 'desert_racetrack.json',
    122 : 'ghost_village.json',
    123 : 'troop_outpost.json',
    124 : 'ancient_front.json',
    125 : 'fantastic_sand_city.json',
    126 : 'nightmare_palace.json',
    169 : 'karang_desert.json',
    170 : 'pharaoh_village.json',
    171 : 'niro_river.json',
    172 : 'dune_oasis.json',
    173 : 'cave_of_falling_sand.json',
    174 : 'goldbrick_road.json',
    175 : 'ancient_tombs.json',
    34  : 'scrap_iron_village.json',
    32  : 'shadowy_path.json',
    26  : 'dark_city.json',
    31  : 'bottomless_pit.json',
    333 : 'ancient_landing_abyston.json',
    14  : 'degula_maze.json',
    35  : 'memory_cave.json',
    209 : 'feather_leaf_forest.json',
    210 : 'snowball_village.json',
    212 : 'radiant_cave.json',
    214 : 'subzero_market.json',
    215 : 'silver_wing_cable_car_station.json',
    213 : 'iceberg_lake.json',
    211 : 'illusory_maze.json',
    137 : 'vine_front.json',
    138 : 'roam_battlefield.json',
    139 : 'sky_pumice.json',
    140 : 'winding_flower_corridor.json',
    146 : 'airship_station.json',
    147 : 'bouleuterion.json',
    148 : 'season_garden.json',
    42  : 'east_playground.json',
    43  : 'west_playground.json',
    58  : 'graduation_palace.json',
    67  : 'sad_abyss.json',
    84  : 'blue_sea.json',
    85  : 'colorful_coral_reefs.json',
    86  : 'golden_beach.json',
    87  : 'puqi_village.json',
    88  : 'palm_base.json',
    89  : 'wave_harbor.json',
    90  : 'blue_ocean.json',
    91  : 'sunken_ruins.json',
    92  : 'shining_coast.json',
    93  : 'dream_ocean.json',
    94  : 'raging_reefs.json',
    95  : 'quiet_ocean.json',
    96  : 'coral_vale.json',
    128 : 'dragon_field.json',
    129 : 'hermit_wetland.json',
    130 : 'flower_corridor.json',
    131 : 'sunshine_palace.json',
    161 : 'lost_cove.json',
    162 : 'rock_forest.json',
    163 : 'hoca_village.json',
    164 : 'rex_point.json',
    165 : 'raven_riverpoint.json',
    166 : 'hunters_ridge.json',
    167 : 'shilly_desert.json',
    192 : 'port_cherube.json',
    193 : 'emerald_shores.json',
    195 : 'hazelnut_ridge.json',
    194 : 'angelic_cave.json',
    196 : 'gaia_valley.json',
    197 : 'dyna_city.json',
    198 : 'butterfly_garden.json',
    231 : 'samara_woods.json',
    232 : 'edo_city.json',
    233 : 'joy_festival.json',
    235 : 'hot_spring_resort.json',
    237 : 'ninja_land.json',
    234 : 'sakura_valley.json',
    236 : 'fox_shrine.json',
    257 : 'mariam_waterway.json',
    318 : 'emerald_coast.json',
    363 : 'deep_trench.json',
    397 : 'floating_station.json',
    398 : 'floral_alley.json',
    399 : 'majestic_mansion.json',
    400 : 'warm_villa.json',
    401 : 'verdant_shrine.json',
    402 : 'seaside_grotto.json',
    416 : 'clink_harbor.json',
    417 : 'neon_sky_corridor.json',
    418 : 'black_market_district.json',
    419 : 'commercial_street.json',
    420 : 'bling_plaza.json',
    421 : 'ultimate_arena.json',
}


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
    # Los dos playgrounds, sacados de capturas de Celestia recorriendo el mapa
    # entero. Se reconstruyen desde los DATOS con nuestros propios
    # constructores, no se reenvian sus bytes.
    _pg = PLANTILLAS_POR_STAGE
    f43 = PLANTILLAS / _pg[stage] if stage in _pg else None
    if f43 is not None and f43.exists():
        d43 = json.loads(f43.read_text(encoding='utf-8'))
        for e in d43['spawns']:
            # El sprite va TAL COMO SE CAPTURO. Antes no se pasaba, asi que
            # los NPC salian con el generico: Cupid aparecia dibujado como
            # Angel Michael y los totems igual. El suyo es 40006 para Cupid y
            # 60241 para los cuatro totems.
            salida.append(_npc_spawn(e['entity_id'], e['npc_type'],
                                     e['nombre'], tuple(e['tile']),
                                     sprite=e.get('sprite', 0),
                                     klass=e.get('klass', 200),
                                     direccion=e.get('direccion'),
                                     visible=e.get('visible', 1)))
            if 'Totem' in e['nombre']:
                TOTEMS_PUESTOS[e['entity_id']] = e['nombre']
        for r in d43.get('recursos', []):
            salida.append(objeto_de_mapa(r))
            # Y su cartel, si se capturo: sin el 0x000F el recurso se ve pero
            # no tiene nombre al pasar el raton.
            _cartel = objeto_nombrado(r)
            if _cartel is not None:
                salida.append(_cartel)
        log.info('Playground %d: %d spawns (%d monstruos) y %d recursos',
                 stage, len(d43['spawns']),
                 sum(1 for e in d43['spawns'] if e.get('monstruo')),
                 len(d43.get('recursos', [])))
        return salida
    if stage in PLAYGROUND_MONSTERS and stage not in _pg:
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


# El numero de cada faccion tal como lo lee el cliente en la ficha. El unico
# MEDIDO es el de Breeze Woods (2) contra el de sin faccion (5); los otros
# tres son suposicion y hay que comprobarlos eligiendo esas facciones.
# El codigo que va en el offset 62 de la ficha. Es el indice de la faccion en
# string.xml, que las lista seguidas a partir del 1030:
#
#   1030 Neutrally   1031 Aurora   1032 Beasts   1033 Steel   1034 Shadow   1035 Heaven
#
# O sea codigo = id - 1030. Los DOS valores que teniamos medidos encajan:
# Beasts sale 2 y Heaven sale 5, que es justo lo que manda Celestia. Antes
# aqui habia 'Holy', 'Evil' y 'Chaos', inventados por nosotros, y ademas con
# los codigos 3 y 4 cruzados: el 3 es Steel (Iron Castle) y el 4 Shadow
# (Dark City), no al reves.
CODIGO_FACCION = {
    'Heaven': 5, 'Graduated': 5, 'Neutral': 5, 'Neutrally': 5,
    'Aurora': 1,        # Aurora City
    'Beasts': 2,        # Breeze Woods, medido
    'Steel': 3,         # Iron Castle
    'Shadow': 4,        # Dark City
}


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
    # El maximo va CON el bono de las pasivas, igual que en el 0x0042. Si no,
    # la ID Card enseñaba un tope distinto del que enseña la barra de arriba:
    # 529/529 en la card contra 529/1009 en el HUD.
    import inventario as _inv
    hp_tope = _inv.vida_maxima(p.hp_max, p.habilidades)
    mp_tope = _inv.mana_maximo(p.mp_max, p.habilidades)
    hp_val = 280 if (not p.habilidades and p.nivel == 1 and p.hp <= 205) else p.hp
    hp_max_val = 280 if (not p.habilidades and p.nivel == 1 and p.hp_max <= 205) else hp_tope
    struct.pack_into('<IIII', st, 0, hp_val, hp_max_val, p.mp, mp_tope)
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
    crudo = bytearray(m.build(**d))
    # La FACCION va en el offset 60 de la ficha (62 contando el opcode).
    # Comparando la ficha del mismo personaje antes y despues de elegir
    # faccion, de 4096 bytes solo cambian seis: la casilla, dos de otra cosa
    # y este, que pasa de 5 (Heaven) a 2 (Beasts, la de Breeze Woods).
    # Nunca lo escribiamos, asi que el cliente seguia mostrando "Heaven"
    # aunque el servidor tuviera guardada la faccion correcta.
    if len(crudo) > 62:
        crudo[62] = CODIGO_FACCION.get(getattr(p, 'faction', ''), 5)
    return bytes(crudo)


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
