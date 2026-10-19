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
    class_id: int = 0
    banco_habilidades: dict = field(default_factory=dict)   # {skill_id: [nivel, exp]}
    hechizos_aprendidos: set = field(default_factory=set)   # {magic_id, ...}
    stage: int = 51
    faction: str = "Heaven"
    nivel: int = 1
    exp: int = 0
    banco: dict = field(default_factory=dict)
    banco_oro: int = 0
    # Creditos de rango, los que la ficha muestra como "Credit:". Suben con
    # las quests y con los objetos de investitem.xml, que dan de cinco en
    # cinco los mas baratos.
    creditos: int = 0
    # El rango que enseña la ficha: 1 es "Growing Power" y 20 "God's
    # Mouthpiece", los nombres 1700 a 1719 de string.xml.
    rango: int = 1
    # La mascota activa, tal como la lee mascotas.leer(): nombre, nivel,
    # stats, saciedad... En vacio no hay ninguna invocada.
    mascota: dict = field(default_factory=dict)
    # Todas las mascotas del inventario: {str(ranura): dict_ficha}
    mascotas: dict = field(default_factory=dict)
    # Mejoras por casilla de equipo: {ranura: {'veces': N, 'huecos': N,
    # 'gemas': [ids], 'extra': {stat: valor}}}. Lo llena mejoras.py.
    mejoras: dict = field(default_factory=dict)
    # Las lamparas de SP. Se guardan: costaba un rato llenarlas y se perdian
    # al salir.
    sp: int = 0
    buffs: dict = field(default_factory=dict)
    # --- Los seis sistemas del README de RE:Angels Online ---
    # Al final de los campos a proposito: meterlos en medio corre todos los
    # que vengan despues si algo llega a construir la clase por posicion.
    album: dict = field(default_factory=dict)        # {categoria: valor}
    logros: list = field(default_factory=list)       # ids conseguidos
    cartas: list = field(default_factory=list)       # ids de carta
    permisos: list = field(default_factory=list)     # puertas abiertas para siempre ('stage:evento')
    estrellas: list = field(default_factory=list)    # [(nombre, nivel)]
    casa: dict = field(default_factory=dict)         # {'muebles': [ids]}
    apariencia: list = field(default_factory=lambda: [0, 0, 0, 8, 8])
    quest_kills: dict = field(default_factory=dict)  # {'qid_paso': count}
    cartas_canjes: list = field(default_factory=list)  # redeemed Card Book sets
    expiracion_puesto: float = 0.0                      # timestamp expiracion tarjeta de puesto (0 = permanente)
    emotes: set = field(default_factory=set)            # {emote_id, ...} adquiridos mediante tarjetas
    quick_emotes: dict = field(default_factory=lambda: {0: -1, 1: -1, 2: -1, 3: -1})  # {slot 0..3: emote_id o -1}


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


FLAGS_MAPA = 0x0205
RESTO_FLAGS_MAPA = b'\xff\x00\x00'
SIN_MAPA = 0x20
_SIN_MINIMAPA = None


def _mapas_sin_minimapa():
    """Los stage que stage.xml marca con 不顯示小地圖 (las instancias: Magic
    Kichen Path, Gulp Room, Olympus Tower...). Traen de radar el smap\004
    de Dawn Harbor como relleno, y el oficial los deja en negro."""
    global _SIN_MINIMAPA
    if _SIN_MINIMAPA is None:
        _SIN_MINIMAPA = set()
        try:
            import sqlite3
            db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
            con = sqlite3.connect(db)
            for (sid,) in con.execute('select id from stage where "不顯示小地圖" = ?', ('是',)):
                if str(sid).isdigit():
                    _SIN_MINIMAPA.add(int(sid))
            con.close()
        except Exception:
            pass
    return _SIN_MINIMAPA


def flags_de_mapa(stage, base=b''):
    """El 0x0014: flags de mapa. Con el bit 0x20 el cliente desactiva el mapa
    (minimapa y Scene Map en negro, sin puntos ni carteles); va en los mapas
    sin minimapa y en el resto el 0x0205 de la captura oficial."""
    flags = FLAGS_MAPA | (SIN_MAPA if int(stage or 0) in _mapas_sin_minimapa() else 0)
    # Mide 7 bytes: los flags y 'ff 00 00' detras (captura oficial). Con
    # solo los 4 de los flags el cliente leia de mas y se cerraba al entrar.
    resto = bytes(base[4:7]) if len(base) >= 7 else RESTO_FLAGS_MAPA
    return struct.pack('<HI', 0x0014, flags) + resto


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
    mando_quests = False
    for m in sec:
        op, base = m['opcode'], m['datos']
        if op == 0x0002:
            salida.append(_ficha(p, base))
            salida.append(_quests(p, b''))
            mando_quests = True
        elif op == 0x0021:
            if not mando_quests:
                salida.append(_quests(p, base))
                mando_quests = True
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
            salida.append(flags_de_mapa(getattr(p, 'stage', 0), base))
        elif op == 0x001D:
            # Atributos de entidad. La plantilla trae el entity_id del
            # personaje que se grabo, asi que habia que reescribirlo: se
            # estaban anunciando los atributos de una entidad ajena.
            b1d = bytearray(base)
            if len(b1d) >= 19 and b1d[4] == 3 and b1d[14] == 0x2A:
                struct.pack_into('<I', b1d, 15, 0)
            salida.append(struct.pack('<HI', 0x001D, p.entity_id) + bytes(b1d[4:]))
        elif op == 0x001A:
            # El inventario. Antes se mandaba la plantilla tal cual, o sea el
            # inventario del personaje que se grabo; ahora se arma con el del
            # jugador, asi que cada item aparece en su ranura.
            import inventario as _inv
            # Asegurar deed activa en slot 376 para WND_HOUSEINFO (Take Back sub_622D90 / Show)
            deed_activa = 10115
            if getattr(p, 'casa', None) and isinstance(p.casa, dict):
                deed_activa = int(p.casa.get('deed_id') or 10115)
            p.inventario[376] = deed_activa
            # Con la cantidad de cada cosa: el oro vive en la ranura 0 y su
            # item_id siempre es 1 (ITEM_ORO) y su cantidad es p.oro.
            # Con la cantidad REAL de cada casilla: aqui iba un 1 fijo, asi
            # que una pila de diez pociones se veia como una sola hasta que
            # algo mandara un refresco. El oro vive en la ranura 0 y su
            # cantidad es p.oro.
            _items = [(int(r), _inv.ITEM_ORO if int(r) == _inv.RANURA_ORO else int(it),
                       p.oro if int(r) == _inv.RANURA_ORO
                       else max(1, int((p.cantidades or {}).get(int(r), (p.cantidades or {}).get(str(r), 1)))))
                      for r, it in p.inventario.items()
                      # DE LA 167 EN ADELANTE es todo del personaje y se
                      # quedaba fuera de este filtro, que solo dejaba pasar
                      # hasta la 120 y las ocultas de mision. Como esto se
                      # manda al entrar y en CADA cambio de mapa, al cruzar un
                      # portal desaparecia del cliente aunque el servidor lo
                      # tuviera guardado en su sitio:
                      #   167..174  la ropa de fashion puesta
                      #   175       la insignia
                      #   176..275  la bolsa de Fashion (4 paginas de 25)
                      #   276..     las pestanas Card y Furniture de esa bolsa
                      #   616       la burbuja de chat puesta
                      #   617..666  la bolsa de burbujas de chat
                      if (int(r) == _inv.RANURA_ORO or (it and int(it) > 0))
                      and (int(r) <= 120 or 166 <= int(r) <= 666)]
            salida.append(_inv.completo(p.char_id, _items, p.entity_id,
                                        mejoras=getattr(p, 'mejoras', None),
                                        mascota=getattr(p, 'mascota', None),
                                        mascotas=getattr(p, 'mascotas', None)))

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
        elif op == 0x005C:
            import presencia as _pr
            salida.append(_pr.paquete_emotes_desbloqueados(getattr(p, 'emotes', None) or set()))
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
    salida += poblar(p.stage, player_level=p.nivel)
    # Atributos nativos iniciales del personaje (HP, MP, EXP bar)
    import combate as _cb_ini
    hp_val = 280 if (not p.habilidades and p.nivel == 1 and p.hp <= 205) else p.hp
    salida.append(_cb_ini.atributo(p.entity_id, hp_val, _cb_ini.KIND_HP))
    salida.append(_cb_ini.atributo(p.entity_id, p.mp, _cb_ini.KIND_MP))
    # AQUI SE MANDABA LA EXPERIENCIA EN EL HUECO DEL SP. KIND_EXP vale 4 y
    # KIND_SP tambien: son el mismo campo, y el 4 es el SP. Al entrar el
    # cliente recibia 322.674.302 "puntos de SP" -- la experiencia -- y la
    # barra de lamparas se quedaba muerta: por mucho que luego subiera de
    # 175 en 175, partia de un numero imposible.
    #
    # La experiencia YA va bien en el 0x001D de abajo, con los sub-campos
    # 29 a 32, que es como la manda el servidor real. Aqui va el SP, que al
    # entrar empieza a cero.
    # El SP guardado del personaje, no un cero fijo: si saliste con cinco
    # lamparas tienes que entrar con cinco.
    salida.append(_cb_ini.atributo(p.entity_id,
                                   max(0, int(getattr(p, 'sp', 0) or 0)),
                                   _cb_ini.KIND_SP))
    # La barra de experiencia necesita los cuatro valores en 64 bits (<BQ):
    #   kind 29: nivel (uint64 LE)
    #   kind 30: exp_base de la barra (0 en login de Celestia para que el % sea actual/siguiente)
    #   kind 31: exp requerida para el siguiente nivel (uint64 LE, sin recortar a 0xFFFFFFFF)
    #   kind 32: exp actual acumulada (uint64 LE, sin recortar a 0xFFFFFFFF)
    p.exp = max(int(p.exp or 0), _cb_ini.exp_para_nivel(p.nivel))
    exp_actual_ui, exp_siguiente_ui = _cb_ini.exp_para_barra(p.nivel, p.exp)
    _u64 = lambda v: max(0, min(int(v or 0), 0xFFFFFFFFFFFFFFFF))
    salida.append(
        struct.pack('<HIB', 0x001D, p.entity_id, 4)
        + struct.pack('<BQ', 29, _u64(p.nivel))
        + struct.pack('<BQ', 30, _u64(_cb_ini.exp_para_nivel(p.nivel)))
        + struct.pack('<BQ', 31, _u64(exp_siguiente_ui))
        + struct.pack('<BQ', 32, _u64(exp_actual_ui)))
    # Emotes rapidos (Alt+1..Alt+4) en ranuras 0..3:
    import presencia as _pr
    salida.append(_pr.paquete_quick_emotes(p.entity_id, getattr(p, 'quick_emotes', None) or {}))
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
    500: [],  # House Monster Room (vacía por defecto como en Global)
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
    sprite_id = sprite or SPRITES.get(npc_type) or sprite_de(npc_type, 42107)
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


def spawn_invocacion(entity_id: int, npc_type: int, nombre: str, tile, sprite: int = 0) -> bytes:
    """0x0008 medido en la captura del servidor oficial (mundo_200804_773798):
    Cuerpo de 64 bytes para invocaciones de Wraith (klass=38).
    """
    b = bytearray(64)
    struct.pack_into('<IIII', b, 0, entity_id, 0, tile[0], tile[1])
    n = str(nombre).encode('ascii', 'replace')[:16]
    b[16:16 + len(n)] = n
    b[32] = 0
    b[33] = 0
    struct.pack_into('<I', b, 34, int(sprite or 42142))
    struct.pack_into('<H', b, 38, 7)
    struct.pack_into('<I', b, 40, 38)  # klass 38 = invocacion de jugador
    b[44] = 1
    struct.pack_into('<H', b, 45, int(npc_type))
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
                if 'hex' not in e:
                    continue
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
        f_json = PLANTILLAS / 'client_tables.json'
        if f_json.exists():
            try:
                raw = json.loads(f_json.read_text(encoding='utf-8'))
                for k, v in (raw.get('npc_sprites') or {}).items():
                    _SPRITES_NPC[int(k)] = int(v)
            except Exception:
                pass
        if not _SPRITES_NPC:
            for raiz in (pathlib.Path(__file__).parent.parent / 'extracted_paks', pathlib.Path('G:/extracted_paks')):
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
                if 'Totem' in e.get('nombre', '') and 'hex' in e:
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
                                 e['tile'], e.get('sprite', 0),
                                 klass=e.get('klass', 199),
                                 direccion=e.get('dir', 6)))
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


def _map_object_spawn(entity_id: int, sprite: int, tile: tuple, direccion: int = 6,
                      mirror=None) -> bytes:
    """Arma un spawn de objeto de mapa (0x000E) como tornados, buzones o maquinas."""
    f = PLANTILLAS / 'portales.json'
    if not f.exists():
        return b''
    cfg = json.loads(f.read_text(encoding='utf-8'))
    base_hex = cfg.get('plantilla_hex')
    if not base_hex:
        return b''
    b = bytearray(bytes.fromhex(base_hex))
    if mirror is not None:
        # IGG sub_5EF410: wire flags bit 2 enables SP_ATTRIB_MIRROR
        # (0x00800000). Static single-view sprites ignore direction changes.
        flags = struct.unpack_from('<I', b, 4)[0]
        struct.pack_into('<I', b, 4, flags | 2 if mirror else flags & ~2)
    struct.pack_into('<I', b, 0, entity_id)
    struct.pack_into('<II', b, 8, tile[0] * 32 + 16, tile[1] * 32 + 16)
    b[33] = direccion & 0xFF
    struct.pack_into('<I', b, 34, sprite)
    return struct.pack('<H', 0x000E) + bytes(b)


# UNA SOLA TABLA de plantillas de mapa. Antes habia TRES listas
# paralelas -- esta, la de _nombre_entidad y la de la IA de monstruos --
# y cada mapa nuevo habia que anadirlo a las tres a mano. Fallo cuatro
# veces: el mapa se dibujaba pero salia SIN monstruos moviendose,
# porque la entrada se habia colado dos veces en la misma lista y
# faltaba en la de la IA. El Lyceum y el Fighting Palace NO van aqui:
# se tratan aparte y cada consumidor los anade si los necesita.
PLANTILLAS_POR_STAGE = {
    501 : 'league_farm.json',
    # Las dos primeras salas de Magic Kichen Path, la instancia a la
    # que se entra por el tornado de (250,171) de Lava Cave. Pobladas
    # desde una captura del cliente GLOBAL, cuyo 0x0008 mide 46 bytes
    # en vez de 62/63/64 -- ver tools/poblar_instancia_global.py.
    #
    # Los PORTALES de las dos salas NO salen de esa captura: salen de
    # map073.mpc y map074.mpc, que traen el grafo entero. De la captura
    # salieron mal -- la llegada anotada era el doble de la de verdad y
    # 73 <-> 74 se quedo sin enlazar. Ver tools/mapa_del_cliente.py y
    # tools/test_magic_kichen_path.py.
    #
    # La TERCERA sala (stage 75). El paso 74 -> 75 no es un portal: lo da
    # el Annoying Clerk al ganar su carrera de bajas (nodo 1000020 de su
    # arbol, CHANGE_MAP(75, 1)). Poblada desde el cliente sin las zonas de
    # evento: las oleadas y el Beelzebub los saca su temporizador.
    73  : 'magic_kichen_path.json',
    74  : 'magic_kichen_path_2.json',
    75  : 'magic_kichen_path_3.json',
    # GULP ROOM, los cuatro cuartos de la instancia de Underground Square.
    # Se entra por el tornado de (252,24) del 71, que llevaba meses anotado
    # con destino en null porque "no se cruzo". No habia que cruzarlo.
    #
    # ESTOS CUATRO NO SALEN DE NINGUNA CAPTURA. Ninguna sesion del proyecto
    # entro nunca al 76-79 -- se comprobo: de 1230 sesiones de mundo, cero
    # paquetes 0x0008 en esos mapas. Los monstruos son los generadores que
    # trae el propio .mpc del cliente. Ver tools/poblar_del_cliente.py, que
    # ademas contrasta el metodo con las 234 plantillas que SI salieron de
    # capturas: en 164 de ellas el total que declara el cliente es
    # EXACTAMENTE el que vio la captura.
    #
    # El 77 trae un solo monstruo a proposito: es el laberinto de tornados,
    # con 52 portales internos y nada mas.
    76  : 'gulp_room.json',
    77  : 'gulp_room_2.json',
    78  : 'gulp_room_3.json',
    79  : 'gulp_room_4.json',
    # LAS DOS INSTANCIAS DE BLUE OCEAN, en Atlantis. Se entra por el mismo
    # tornado, el de (294,14) del stage 90, que no viaja: abre el dialogo 3
    # del mapa y la opcion elegida decide si vas a la normal o a la Elite.
    # Mismo mapa de 325x199 las dos, con bichos distintos: Mermaid y Linberd
    # en la normal, Scale Captain y Merman en la Horrible.
    98  : 'lost_region.json',
    101 : 'horrible_lost_region.json',
    # LAS 26 INSTANCIAS QUE QUEDABAN, abiertas de una vez. Sus entradas
    # llevaban meses en portales.json con el destino en null y notas que
    # decian "NO SE CRUZO" o "identificada por descarte": 24 de ellas traian
    # el CHANGE_MAP escrito en el objeto del mapa del cliente desde el primer
    # dia, y las otras dos van por un menu de dialogo.
    #
    # Ninguna salio de una captura -- a una instancia no se entra a voluntad
    # para grabarla -- sino de los generadores del .mpc. Ver
    # tools/propagar_portales.py y tools/poblar_del_cliente.py, y el contraste
    # del metodo contra las 234 plantillas que si son capturas.
    97  : 'evil_ship.json',                 # Evil Ship, desde 96 Coral Vale. 123 bichos
    110 : 'limitless_tower.json',           # Limitless Tower, desde 107 Half-beast Hamlet. 271 bichos
    111 : 'cloud_top_land.json',            # Cloud-top Land, desde 109 Giant Wooden Stairs. 184 bichos
    127 : 'leviathans_bedroom.json',        # Leviathan's Bedroom, desde 126 Nightmare Palace. 584 bichos
    158 : 'poker_castle.json',              # Poker Castle, desde 157 Chocolate Forest. 415 bichos
    168 : 'dinosaur_arena.json',            # Dinosaur Arena, desde 167 Shilly Desert. 354 bichos
    176 : 'unknown_chambers.json',          # Unknown Chambers, desde 175 Ancient Tombs. 439 bichos
    199 : 'phoenix_palace.json',            # Phoenix Palace, desde 198 Butterfly Garden. 315 bichos
    216 : 'blizarro_castle.json',           # Blizarro Castle, desde 215 Silver Wing Cable Car Station. 373 bichos
    229 : 'mundo_warship.json',             # Mundo Warship, desde 228 Forbidden Sector. 520 bichos
    238 : 'jade_tassel_city.json',          # Jade Tassel City, desde 237 Ninja Land. 373 bichos
    252 : 'queen_bee_hideout.json',         # Queen Bee Hideout, desde 251 Buzzing Stopover. 512 bichos
    281 : 'floral_palace.json',             # Floral Palace, desde 280 Drip-drop Passage. 543 bichos
    292 : 'flamefang_sanctum.json',         # Flamefang Sanctum, desde 291 Fragrant Courtyard. 350 bichos
    302 : 'enchanted_sanctum.json',         # Enchanted Sanctum, desde 301 Reminiscence Cloister. 260 bichos
    313 : 'apocalypso.json',                # Apocalypso, desde 312 Chrono Ruins. 294 bichos
    325 : 'radiant_castle.json',            # Radiant Castle, desde 324 Royal Ruins. 211 bichos
    340 : 'leviathans_domain.json',         # Leviathan's Domain, desde 339 Peril Chasm. 340 bichos
    351 : 'nightmare_city.json',            # Nightmare City, desde 350 Forbidden Dusk. 277 bichos
    360 : 'galaxia_palace.json',            # Galaxia Palace, desde 359 Horizon Archives. 153 bichos
    369 : 'hadal_lair.json',                # Hadal Lair, desde 368 Deep Prison. 166 bichos
    387 : 'wintry_realm.json',              # Wintry Realm, desde 386 Frozen Region. 141 bichos
    395 : 'warring_realm.json',             # Warring Realm, desde 394 Champions' Arena. 166 bichos
    403 : 'dragons_lair.json',              # Dragon's Lair, desde 402 Seaside Grotto. 134 bichos
    411 : 'core_zone.json',                 # Core Zone, desde 410 Steely Circuit. 203 bichos
    413 : 'c_dinosaur_arena.json',          # Chaos-Dinosaur Arena, desde Rainbow Town. 375 bichos
    414 : 'c_end_time.json',                # Chaos-End Time, desde Rainbow Town. 310 bichos
    422 : 'secret_peak.json',
    # Estas dos no estaban ni anotadas en portales.json: su tornado falta
    # entero en el json, no es que estuviera en null. Salieron barriendo el
    # cliente en busca de tornados que el json no tuviera.
    145 : 'botti_palace.json',             # Botti Palace, desde 148 Season Garden
    263 : 'mahal_altar.json',              # Mahal Altar, desde 261 Siam Square
    264 : 'hell_mahal_altar.json',         # Hell Mahal Altar, desde 262 Hell Siam Square               # Secret Peak, desde 420 Bling Plaza. 235 bichos
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
    295 : 'starglow_path.json',
    296 : 'academia_woods.json',
    298 : 'coo_village.json',
    297 : 'mana_ruins.json',
    299 : 'ethereal_garden.json',
    300 : 'daydream_library.json',
    301 : 'reminiscence_cloister.json',
    306 : 'dial_desert.json',
    307 : 'greenfield.json',
    308 : 'rainbow_town.json',
    309 : 'antler_mesa.json',
    310 : 'carrotiso.json',
    311 : 'cogsville.json',
    312 : 'chrono_ruins.json',
    318 : 'emerald_coast.json',
    319 : 'whisper_lake.json',
    320 : 'twinkle_town.json',
    321 : 'cobalt_market.json',
    322 : 'grove_of_bliss.json',
    323 : 'twilight_mines.json',
    324 : 'royal_ruins.json',
    223 : 'steam_town.json',
    224 : 'yeeha_bar.json',
    225 : 'agysical_tunnel.json',
    226 : 'sunset_valley.json',
    227 : 'desolate_ruins.json',
    228 : 'forbidden_sector.json',
    354 : 'whispering_hill.json',
    355 : 'galaxia_square.json',
    356 : 'pristine_lake.json',
    357 : 'magma_field.json',
    358 : 'rolling_sands.json',
    359 : 'horizon_archives.json',
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
    334 : 'forsaken_crevasse.json',
    335 : 'specter_village.json',
    337 : 'crystal_quarry.json',
    336 : 'crystal_marsh.json',
    338 : 'shrouded_haven.json',
    339 : 'peril_chasm.json',
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
    258 : 'shuwa_market.json',
    318 : 'emerald_coast.json',
    363 : 'deep_trench.json',
    364 : 'ancient_rift.json',
    365 : 'desolate_city.json',
    366 : 'abyssal_arena.json',
    367 : 'poseidon_shrine.json',
    368 : 'deep_prison.json',
    397 : 'floating_station.json',
    398 : 'floral_alley.json',
    399 : 'majestic_mansion.json',
    400 : 'warm_villa.json',
    401 : 'verdant_shrine.json',
    402 : 'seaside_grotto.json',
    405 : 'sandy_heights.json',
    406 : 'wise_institute.json',
    407 : 'clank_oasis.json',
    408 : 'ironbone_works.json',
    409 : 'machinery_ruins.json',
    410 : 'steely_circuit.json',
    68  : 'fiery_path.json',
    69  : 'lava_cave.json',
    70  : 'flaming_door.json',
    71  : 'underground_square.json',
    72  : 'hell_palace.json',
    259 : 'bayan_village.json',
    260 : 'deserted_ruins.json',
    261 : 'siam_square.json',
    262 : 'hell_siam_square.json',
    274 : 'sylvan_chaos.json',
    275 : 'rusty_pipe_lane.json',
    276 : 'joaquin.json',
    277 : 'scrap_iron_works.json',
    381 : 'spring_garden.json',
    278 : 'sylvan_gardens.json',
    279 : 'paua_shell_harbor.json',
    280 : 'drip_drop_passage.json',
    383 : 'red_desert.json',
    382 : 'silent_lakeside.json',
    384 : 'chilly_village.json',
    385 : 'pink_woods.json',
    386 : 'frozen_region.json',
    389 : 'pier_lane.json',
    391 : 'bath_area.json',
    390 : 'busy_market.json',
    392 : 'manege.json',
    393 : 'garrison.json',
    394 : 'champions_arena.json',
    # Angel House Area y Angel Church, las dos salas que salen del Lyceum
    # por los tornados de (168,103) y (259,79). De la captura de Celestia
    # del 14/10/2026: Cupid en la primera y el tornado de vuelta en las dos.
    370 : 'angel_house_area.json',
    # Mystic Space: se entra por el trono de Sunshine Palace (286,168) con la
    # mision 988 en el paso 2 o 3, o hecha. Poblado desde map132.mpc.
    132 : 'mystic_space.json',
    # Training Palace (Training Hall A1/A2/A3 del menu de los Playground):
    # poblado desde los generadores del propio map044.mpc. Los tres
    # canales comparten mapa.
    44 : 'training_palace.json',
    144 : 'training_palace.json',
    244 : 'training_palace.json',
    80 : 'angel_church.json',
    118 : 'training_area_a.json',
    134 : 'training_area_b.json',
    135 : 'training_area_c.json',
    136 : 'training_area_d.json',
    416 : 'clink_harbor.json',
    417 : 'neon_sky_corridor.json',
    418 : 'black_market_district.json',
    419 : 'commercial_street.json',
    420 : 'bling_plaza.json',
    421 : 'ultimate_arena.json',
}


HOUSE_INTERACTIVE_IDS = tuple(
    [260300, 262501, 701, 702, 703, 720, 721, 723, 731]
    + list(range(500020, 500030))
)


def interactivos_casa(player_level=1):
    """Servicios IGG de default.mpc; posiciones de portales ya verificadas."""
    salida = portales_de(500)
    # 1. Main Room:
    # NPC 2603 with the house-maid visual from npc.obd (not placeholder n015).
    import house_services as hs
    salida.append(_npc_spawn(260300, 2603, "Maid Eilian", hs.MAID_TILE,
                             sprite=hs.MAID_SPRITE, klass=200, direccion=hs.MAID_DIRECTION))
    salida.append(_map_object_spawn(720, 60155, (27, 31)))
    for eid, (sprite, tile, _skill, _category, _note) in hs.PRODUCTION.items():
        salida.append(_map_object_spawn(eid, sprite, tile,
                                       mirror=hs.PRODUCTION_MIRROR.get(eid)))
    for eid in hs.RESOURCES:
        resource = hs.resource_for(eid, player_level)
        salida.append(objeto_de_mapa(resource))
        salida.append(objeto_nombrado(resource))

    # 2. Pet Room / Raise-a-Pet Room:
    # Buzon de pedidos. La maquina de pets es el huevo 60155 (entidad 720).
    salida.append(_map_object_spawn(721, 62358, hs.MAILBOX_TILE))
    # The Safe (objeto 60306) en (40, 26)
    salida.append(_map_object_spawn(723, 60306, (40, 26), mirror=False))

    # 3. Monster Room / Monster Hatching Room:
    # Monster Hatching Machine (objeto 60155) en (85, 31)
    salida.append(_map_object_spawn(731, 60155, (85, 31)))

    return salida


def poblar(stage: int, player_level=1):
    """NPC, monstruos, portales y totems propios del mapa."""
    if stage == 501:
        import granja_liga
        return [_map_object_spawn(granja_liga.PORTAL_ENTIDAD, 60001, granja_liga.PORTAL_TILE)]
    if stage == 500:
        return interactivos_casa(player_level)
    salida = npc_de_los_xml(stage)
    salida += portales_de(stage)
    try:
        import casas as _cs_pob
        if stage in _cs_pob.MAPAS_EXHIBICION:
            for _c_act in _cs_pob.casas_en_stage(stage):
                salida.append(_cs_pob.pkt_outdoor_house(
                    _c_act.outdoor_obj_id, _c_act.model_id,
                    _c_act.outdoor_px[0], _c_act.outdoor_px[1],
                    _c_act.house_name, _c_act.owner_name,
                    dir_rot=_c_act.outdoor_dir,
                    house_size_level=_c_act.size_level,
                    house_level=_c_act.level
                ))
    except Exception:
        log.exception('login.poblar: error al enviar casas exteriores')
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
            # 'apagado': generador que el cliente declara con cantidad 0 (lo
            # saca otra cosa o no sale). Se deja en la plantilla para el censo
            # pero no se manda: en el Training Palace salian Field Mouse y
            # Tree Spirit donde no tocaba.
            if e.get('apagado'):
                continue
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
        for item in PLAYGROUND_MONSTERS[stage]:
            eid, ntype, nom, tile = item[:4]
            sp = item[4] if len(item) > 4 else 0
            salida.append(_npc_spawn(eid, ntype, nom, tile, sprite=sp, klass=1))
        return salida
    f = PLANTILLAS / 'lyceum.json'
    if stage != 41 or not f.exists():
        return salida
    d = json.loads(f.read_text(encoding='utf-8'))
    # Las capturadas traen el cuerpo entero en 'hex'. Las que puso
    # tools/npcs_del_cliente.py (Porter Jade, BattlefieldAngel...) vienen en
    # el formato de los demas mapas y se arman igual que alli: sin esto el
    # servidor se caia al entrar en el Lyceum (KeyError 'hex').
    for e in d.get('spawns', []):
        if e.get('hex'):
            salida.append(struct.pack('<H', 0x0008) + bytes.fromhex(e['hex']))
        else:
            salida.append(_npc_spawn(e['entity_id'], e['npc_type'],
                                     e['nombre'], tuple(e['tile']),
                                     sprite=e.get('sprite', 0),
                                     klass=e.get('klass', 200),
                                     direccion=e.get('direccion'),
                                     visible=e.get('visible', 1)))
    # Los recursos del mapa: vetas de cobre, arboles, hierbas, madrigueras.
    for e in d.get('recursos', []):
        if 'hex' in e:
            salida.append(struct.pack('<H', 0x000E) + bytes.fromhex(e['hex']))
        else:
            salida.append(objeto_de_mapa(e))
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
    # Bit 0x80000000 permite que el cliente ejecute los botones de WND_HOUSEINFO (Show, Take Back, Decorate)
    # y valida la condicion (*(_DWORD *)(player + 480) & 0x80000000) en Angel.exe (sub_5BA840..sub_5BA8F0)
    d['flags'] = 0x80000000
    # En 0x0002, el mapa/stage real va en el offset 3953 (offset 3235 dentro de 'resto')
    r = bytearray(d['resto'])

    if len(r) >= 3239:
        struct.pack_into('<I', r, 3235, p.stage)
        # Suprimir dialogo molesto "Set Deal Password or not?" (*(_BYTE *)(v17 + 632) = 1)
        # El offset en a3 es 3937. Dado que 'resto' empieza en 718: 3937 - 718 = 3219.
        r[3219] = 1
        d['resto'] = bytes(r)
    nom = p.nombre.encode('ascii', 'replace')[:33]
    d['name_raw'] = nom + b'\x00' * (34 - len(nom))
    import combate as _cb_ficha
    p.exp = max(int(p.exp or 0), _cb_ficha.exp_para_nivel(p.nivel))
    exp_actual_ui, exp_siguiente_ui = _cb_ficha.exp_para_barra(p.nivel, p.exp)
    u50 = bytearray(d['unk_50'])
    if len(u50) >= 43:
        # En sub_5E9C90 (0x0002 de Angel.exe, donde u50[k] = a3 + 52 + k):
        #   u50[15:19] (a3 + 67): nivel (<I LE32)
        #   u50[19:27] (a3 + 71): exp_actual (<Q LE64 -> v17 + 1224)
        #   u50[27:35] (a3 + 79): exp_base   (<Q LE64 -> v17 + 1208, 0 en login)
        #   u50[35:43] (a3 + 87): exp_sig    (<Q LE64 -> v17 + 1216)
        u50[12:15] = b'\x00\x00\x00'
        struct.pack_into('<I', u50, 15, max(1, p.nivel))
        struct.pack_into('<Q', u50, 19, max(0, min(exp_actual_ui, 0xFFFFFFFFFFFFFFFF)))
        struct.pack_into('<Q', u50, 27, 0)
        struct.pack_into('<Q', u50, 35, max(0, min(exp_siguiente_ui, 0xFFFFFFFFFFFFFFFF)))
        # EL RANGO Y LOS CREDITOS, pegados el uno al otro.
        #
        # Estan en el offset 93 y 94 del 0x0002: un byte con el rango y un
        # LE32 con los creditos. Salieron comparando el relog del servidor
        # real con nuestra plantilla: alli el byte valia 17 y los creditos
        # 4.610.115, y en la nuestra 1 y 0 -- que es justo lo que la ficha
        # del juego enseñaba, "Rank 1 Growing Power" con los creditos bien.
        #
        # El rango NO se calcula de los creditos: los cortes entre uno y otro
        # no estan en ningun xml del cliente ni en los luas. Lo manda el
        # servidor y punto, asi que aqui se manda el que lleve el personaje.
        if len(u50) >= 48:
            u50[43] = max(1, min(20, getattr(p, 'rango', 1) or 1))
            struct.pack_into('<I', u50, 44,
                             (getattr(p, 'creditos', 0) or 0) & 0xFFFFFFFF)
        # APARIENCIA: los bytes 55..59 de la ficha (u50[5:10]) son los cinco
        # de la apariencia (genero, peinado, color...). Sin esto salia la de
        # la plantilla capturada, sin importar lo elegido al crear.
        _ap = getattr(p, 'apariencia', None)
        if _ap and len(_ap) >= 5:
            u50[5:10] = bytes(int(v) & 0xFF for v in _ap[:5])
        d['unk_50'] = bytes(u50)
    # HP y MP. El campo 'stats' arranca en +102 de la ficha (a3 + 104), asi que los
    # cuatro LE32 del principio son hp, hp_max, mp, mp_max (+102, +106,
    # +110, +114). En st[16:20] (a3 + 120 y a3 + 122) van sp_pts y sp_max_pts (<HH).
    st = bytearray(d['stats'])
    # El maximo va CON el bono de las pasivas, igual que en el 0x0042. Si no,
    # la ID Card enseñaba un tope distinto del que enseña la barra de arriba:
    # 529/529 en la card contra 529/1009 en el HUD.
    import inventario as _inv
    _mej = getattr(p, 'mejoras', None)
    _buf = getattr(p, 'buffs', None)
    hp_tope = _inv.vida_maxima(p.hp_max, p.habilidades, bolsa=p.inventario, mejoras=_mej, buffs=_buf, mp_max=p.mp_max)
    mp_tope = _inv.mana_maximo(p.mp_max, p.habilidades, bolsa=p.inventario, mejoras=_mej, buffs=_buf)
    hp_val = 280 if (not p.habilidades and p.nivel == 1 and p.hp <= 205) else min(p.hp, hp_tope)
    hp_max_val = 280 if (not p.habilidades and p.nivel == 1 and p.hp_max <= 205) else hp_tope
    struct.pack_into('<IIII', st, 0, hp_val, hp_max_val, min(p.mp, mp_tope), mp_tope)
    if len(st) >= 20:
        _b_sp = _inv.bonos_de_habilidades(p.habilidades)
        sp_max_pts = min(10, _b_sp['barras_sp']) * 1000
        sp_pts = max(0, min(int(getattr(p, 'sp', 0) or 0), sp_max_pts))
        struct.pack_into('<HH', st, 16, sp_pts, sp_max_pts)
    d['stats'] = bytes(st)
    if p.habilidades:
        sk = list(d['skills'])
        for i, (sid, nivel, exp) in enumerate(p.habilidades[:36]):
            req = _cb_ficha.exp_para_skill(nivel, sid)
            sexp = max(0, min(req, int(exp or 0)))
            sk[i] = {'skill_id': sid, 'level': nivel, 'level2': nivel,
                     'cero': struct.pack('<I', sexp & 0xFFFFFFFF),
                     'exp': req & 0xFFFFFFFF, 'idx': i + 1}
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
    if len(crudo) >= 0xd8:
        struct.pack_into('<I', crudo, 0xd4, int(p.char_id or 0))
    import cartas as _cartas
    _cartas.perfil(crudo, p)
    return bytes(crudo)


def _quests(p, base):
    m = Msg.registry[(0x0021, 's2c', 'privado')]
    if not p.quests:
        return struct.pack('<HI', 0x0021, 0)
    import misiones as _mis
    qs = []
    for q, s in p.quests:
        comp = _mis.mision_completada(p, q)
        paso_red = _mis.total_pasos_mision(q) if comp else max(0, s - 1)
        qs.append({'char_id': p.char_id, 'quest_id': q, 'paso': paso_red, 'resto': b'\x00' * 11})
    return m.build(n=len(qs), quests=qs)


def entrada_barra(x):
    """Normaliza una ranura de la barra a (tipo, id).

    El campo que se llamaba 'usada' es en realidad el TIPO: 1 es un hechizo
    y 2 es un OBJETO. Medido en un 0x005B real, donde la ranura 7 llevaba
    "02" con el id 47382, que es un mortero. Guardando solo el id, los
    objetos de la barra volvian marcados como hechizos y el cliente los
    quitaba al entrar.

    Se aceptan los dos formatos para no romper lo ya guardado: un numero
    suelto es un hechizo de toda la vida.
    """
    if isinstance(x, (list, tuple)):
        if len(x) >= 2:
            return int(x[0]), int(x[1])
        x = x[0] if x else 0
    x = int(x or 0)
    return (1 if x else 0), x


def _barra(p, base):
    m = Msg.registry[(0x005B, 's2c', 'privado')]
    if not p.barra:
        return struct.pack('<H', 0x005B) + base
    r = []
    for x in p.barra[:24]:
        tipo, mid = entrada_barra(x)
        r.append({'usada': tipo, 'magic_id': int(mid or 0), 'resto': bytes(4)})
    r += [{'usada': 0, 'magic_id': 0, 'resto': bytes(4)}] * (24 - len(r))
    return m.build(ranuras=r)
    # --- Los seis sistemas del README de RE:Angels Online ---
    # Van al FINAL del dataclass a proposito: insertarlos en medio corre
    # todos los campos que vengan despues para cualquier construccion por
    # posicion.
    album: dict = field(default_factory=dict)        # {categoria: valor}
    logros: list = field(default_factory=list)       # ids conseguidos
    cartas: list = field(default_factory=list)       # ids de carta
    permisos: list = field(default_factory=list)     # puertas abiertas para siempre ('stage:evento')
    estrellas: list = field(default_factory=list)    # [(nombre, nivel)]
    casa: dict = field(default_factory=dict)         # {'muebles': [ids]}
