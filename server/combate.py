"""
Combate.

Protocolo, medido matando Slarms en el Lyceum:

    C -> S  0x0006  [LE16 ataque][LE16 entity del objetivo][12 bytes en cero]
                    656 con el golpe normal, 732 con una habilidad

    S -> C  0x0013  [LE32 entity][U8 1][U8 kind][LE32 valor]
                    kind 0 = vida en porcentaje (100 lleno, 0 muerto)
    S -> C  0x000A  [LE32 atacante][LE32 objetivo][LE32 dano]

Y al morir el monstruo llega el botin: NO cae al suelo (no hay 0x0050), entra
directo al inventario con su 0x001B y su aviso 0x000D.

Los datos de cada bicho salen de la tabla monster de content.db, buscando por
el npc_type que trae su NPC_SPAWN: Lily es el 7 (100 de vida, ataque 23+-2,
defensa 25) y Slarm el 19 (118 de vida, ataque 28+-2, defensa 25).
"""
import json
import logging
import pathlib
import random
import re
import sqlite3
import struct
import time

ATAQUE_NORMAL = 656
OBJETIVO_FIJADO = 0x03060001
VIDA = 0                    # kind 0 del 0x0013: HP (o % en monstruos)
KIND_HP = 0                 # HP actual del jugador / % del monstruo
KIND_MP = 2                 # MP actual del jugador (medido en 70/70 capturas de AngelWar)
KIND_TRANSFORM = 33         # Sprite temporal del personaje (forma transformada)
KIND_SP = 4                 # Puntos de SP acumulados del jugador (0..max_sp*1000)

# El SP siempre sube en multiplos de 25: en las capturas no hay ni una
# subida que no lo sea. Una lampara son 1000 puntos, segun el SP Power
# Scroll ("Increase 2000 SP ... recover 2 SP lamps").
SP_POR_GOLPE = 25
SP_POR_LAMPARA = 1000
KIND_EXP = 4                # Alias retrocompatible
# Creditos de rango. Medido el 28/09/2026 en la captura de Edo City: al usar
# uno de los objetos que dan creditos, el servidor real manda este mismo
# 0x0013 con el atributo 49 y el total acumulado, y detras un 0x0282 con la
# cantidad sumada escrita en ASCII ("120000"). El rango que se ve en la ficha
# del personaje sale de ese total; los cortes entre un rango y otro NO estan
# en los xml del cliente ni se han podido medir todavia.
KIND_CREDITO = 49
# ESTADO del personaje. Medido en Celestia (mundo_203502_844482 t=25.3): al
# pedir quedarse como alma (c2s 0x0016 accion 3) llega 0x0013 tipo 28 con
# 0x08000000 y un 0x000A (yo, 0, 0, 0). Es el bit que el cliente mira en
# +0x1e0 para la musica de muerto (005b36a0): el modo FANTASMA.
KIND_ESTADO = 28
ESTADO_FANTASMA = 0x08000000
# Rango del personaje (1..20, string.xml 1700..1719). En Angel.exe (sub_5FEB10,
# offset 16920 de la tabla de 0x0013 -> kind 51), mandar 0x0013 con kind 51
# actualiza en vivo tanto el requisito de rango (a2+1232) como el texto del
# rango en la ventana de estado (widget 853).
KIND_RANGO = 51
NOMBRES_RANGO = {
    1: "Growing Power",
    2: "Make a figure",
    3: "Belief Preacher",
    4: "Order Apostle",
    5: "Gospel Archangel",
    6: "Holy Dedicator",
    7: "God as Lawyer",
    8: "Rainbow Guide",
    9: "Gospel Sower",
    10: "Chief Justice",
    11: "Eden's Hope",
    12: "War Angel",
    13: "God as Judge",
    14: "Heavenly Hero",
    15: "Six-winged Angel",
    16: "Symbol of Might",
    17: "Order founder",
    18: "Star Ruler",
    19: "Holy Angel",
    20: "God's Mouthpiece",
}
# LOS CREDITOS QUE PIDE CADA RANGO, leidos de level.xml.
#
# Estaba escrito que "los cortes entre un rango y otro no se han encontrado:
# no estan en ningun xml del cliente". Si estan: son la columna 功勳 de
# level.xml, y hay EXACTAMENTE 20 valores, uno por rango.
#
# Cuadra con lo unico medido que habia: en la captura del 28/09/2026 el
# personaje tenia 4.610.115 creditos y la ficha decia "Order founder", que
# es el rango 17. La tabla pide 4.250.000 para el 17 y 6.380.000 para el
# 18, asi que 4.610.115 cae justo en el 17.
_CREDITOS_RANGO = None


def _tabla_creditos_rango() -> list:
    """Los 20 cortes de credito, del rango 1 al 20."""
    global _CREDITOS_RANGO
    if _CREDITOS_RANGO is not None:
        return _CREDITOS_RANGO
    _CREDITOS_RANGO = []
    # Primero la plantilla, que es lo unico que viaja en el repo:
    # extracted_paks NO esta publicado y sin esto los creditos salian 0
    # para todo el que clonara.
    f = pathlib.Path(__file__).parent / 'plantillas' / 'creditos_rango.json'
    if f.exists():
        try:
            cortes = (json.loads(f.read_text(encoding='utf-8')) or {}).get('cortes') or []
            if len(cortes) >= 20:
                _CREDITOS_RANGO = [int(x) for x in cortes[:20]]
                return _CREDITOS_RANGO
        except Exception:
            pass
    raiz = pathlib.Path(__file__).parent.parent / 'extracted_paks'
    for sub in sorted(raiz.glob('*/setting/level.xml'), reverse=True):
        try:
            txt = sub.read_text(encoding='utf-8-sig', errors='ignore')
        except OSError:
            continue
        vals = [int(v) for v in re.findall(r'<功勳>(\d+)</功勳>', txt)]
        if len(vals) >= 20:
            _CREDITOS_RANGO = vals[:20]
            break
    return _CREDITOS_RANGO


def creditos_de_rango(rango: int) -> int:
    """Los creditos con los que empieza ese rango, o 0 si no hay tabla."""
    t = _tabla_creditos_rango()
    n = max(1, min(20, int(rango or 1)))
    return t[n - 1] if len(t) >= n else 0


def rango_de_creditos(creditos: int) -> int:
    """El rango que corresponde a esos creditos."""
    t = _tabla_creditos_rango()
    if not t:
        return 1
    c = max(0, int(creditos or 0))
    r = 1
    for i, corte in enumerate(t, start=1):
        if c >= corte:
            r = i
    return r


COSTE_GOLPE = 4
SEGUNDOS_REAPARICION = 20
_MON = None


def _datos(npc_type: int):
    """{hp, atk, var, def, exp, atk_range, proj_ef, move_speed, move_range} del monstruo, o None si no esta en monster.xml."""
    global _MON
    if _MON is None:
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        _MON = {}
        if db.exists():
            con = sqlite3.connect(db)
            cols = [c[1] for c in con.execute('pragma table_info(monster)').fetchall()]
            for row in con.execute("select * from monster where id glob '[0-9]*'"):
                d = dict(zip(cols, row))
                def _n(x):
                    try:
                        return int(float(x))
                    except (TypeError, ValueError):
                        return 0
                mid = int(d['id'])
                _MON[mid] = {
                    'nombre': d.get('name') or '',
                    'hp': _n(d.get('hp')) or 1,
                    'atk': _n(d.get('atk_avg')),
                    'var': _n(d.get('atk_var')),
                    'def': _n(d.get('def')),
                    'mdef': _n(d.get('mdef')),
                    'matk': _n(d.get('matk')),
                    'exp': _n(d.get('exp_value')) or 25,
                    'atk_range': _n(d.get('atk_range')) or 1,
                    'proj_ef': _n(d.get('投射特效')) or 0,
                    'move_speed': _n(d.get('move_speed')),
                    'atk_speed': _n(d.get('atk_speed')) or 60,
                    'move_range': _n(d.get('move_range')) or 6,
                    # 主動: el RADIO en casillas al que ataca solo, sin que le
                    # peguen. Vacio = pasivo (Lily, Little Slarm). En las
                    # instancias casi todos lo llevan: Fire Mummy 5, Dark
                    # Protector y Earl Makice 12, Rock Slarm 5. Es el "Agr.
                    # Yes" de las tablas de la wiki.
                    'agro': max(0, _n(d.get('主動'))),
                    'res_lightning': _n(d.get('res_lightning')),
                    'res_fire': _n(d.get('res_fire')),
                    'res_ice': _n(d.get('res_ice')),
                    'res_corrosion': _n(d.get('res_corrosion')),
                    'res_body': _n(d.get('res_body')),
                    'res_mind': _n(d.get('res_mind')),
                    'thnd_atk': _n(d.get('雷電攻擊')),
                    'thnd_prob': _n(d.get('雷電機率')),
                    'fire_atk': _n(d.get('火焰攻擊')),
                    'fire_prob': _n(d.get('火焰機率')),
                    'ice_atk': _n(d.get('寒冰攻擊')),
                    'ice_prob': _n(d.get('寒冰機率')),
                    'rotten_atk': _n(d.get('腐蝕攻擊')),
                    'rotten_prob': _n(d.get('腐蝕機率')),
                }
    return _MON.get(npc_type)



_CURVA_NIVEL = None
_CURVA_SKILL = None
_CURVA_PET = None


def _cargar_curva_nivel():
    global _CURVA_NIVEL, _CURVA_SKILL, _CURVA_PET
    if _CURVA_NIVEL is None:
        _CURVA_NIVEL = {}
        _CURVA_SKILL = {}
        _CURVA_PET = {'A': {}, 'B': {}, 'C': {}, 'D': {}}
        f_json = pathlib.Path(__file__).parent / 'plantillas' / 'level_curves.json'
        if f_json.exists():
            try:
                raw = json.loads(f_json.read_text(encoding='utf-8'))
                for lv, v in (raw.get('curva_nivel') or {}).items():
                    _CURVA_NIVEL[int(lv)] = int(v)
                for k_sk, v in (raw.get('curva_skill') or {}).items():
                    lv_s, sid_s = k_sk.split(',')
                    _CURVA_SKILL[(int(lv_s), int(sid_s))] = int(v)
                for k_p, d_p in (raw.get('curva_pet') or {}).items():
                    if k_p in _CURVA_PET:
                        _CURVA_PET[k_p] = {int(lv): int(v) for lv, v in d_p.items()}
            except Exception:
                pass
        raiz = pathlib.Path(__file__).parent.parent
        if not _CURVA_NIVEL:
            for cand in (
                raiz / 'extracted_paks' / 'update26' / 'setting' / 'level.xml',
                pathlib.Path('G:/extracted_paks/update26/setting/level.xml'),
                raiz / 'extracted_paks' / 'UPDATE19' / 'setting' / 'level.xml',
                raiz / 'extracted_paks' / 'data1' / 'setting' / 'level.xml',
            ):
                if cand.exists():
                    try:
                        import xml.etree.ElementTree as ET
                        tree = ET.parse(cand)
                        for e in tree.getroot().findall('exp'):
                            lv = int(e.attrib.get('等級', 0) or 0)
                            if lv <= 0:
                                continue
                            if len(e) > 0 and e[0].text:
                                _CURVA_NIVEL[lv] = int(e[0].text)
                            for sid in range(1, 37):
                                if sid < len(e) and e[sid].text:
                                    try:
                                        _CURVA_SKILL[(lv, sid)] = int(e[sid].text)
                                    except ValueError:
                                        pass
                            for idx, k in ((38, 'A'), (39, 'B'), (40, 'C'), (41, 'D')):
                                if idx < len(e) and e[idx].text:
                                    try:
                                        _CURVA_PET[k][lv] = int(e[idx].text)
                                    except ValueError:
                                        pass
                        if _CURVA_NIVEL:
                            break
                    except Exception:
                        pass
        if not _CURVA_NIVEL:
            db = raiz / 'corpus' / 'content.db'
            if db.exists():
                try:
                    con = sqlite3.connect(db)
                    for lv, exp in con.execute('select level, exp_char from level'):
                        try:
                            _CURVA_NIVEL[int(lv)] = int(exp)
                        except ValueError:
                            pass
                except Exception:
                    pass
    return _CURVA_NIVEL or {}


def exp_para_skill(nv: int, sid: int = 1) -> int:
    """EXP requerida en level.xml para subir la habilidad `sid` (1..36) del nivel `nv` al `nv + 1`."""
    _cargar_curva_nivel()
    sid_i = max(1, min(36, int(sid or 1)))
    target_lv = max(2, min(NIVEL_MAXIMO, int(nv or 1) + 1))
    val = (_CURVA_SKILL or {}).get((target_lv, sid_i))
    if val is not None and val > 0:
        return int(val)
    val_1 = (_CURVA_SKILL or {}).get((target_lv, 1))
    if val_1 is not None and val_1 > 0:
        return int(val_1)
    return max(3, int(nv or 1) * 15)


def exp_para_mascota(nv: int, tipo: str = 'A') -> int:
    """EXP acumulada requerida en level.xml para una mascota de tipo A/B/C/D en nivel `nv`."""
    _cargar_curva_nivel()
    tabla = (_CURVA_PET or {}).get(str(tipo or 'A').upper()) or (_CURVA_PET or {}).get('A') or {}
    lv = max(1, min(NIVEL_MAXIMO, int(nv or 1)))
    if lv in tabla:
        return int(tabla[lv])
    return int(exp_para_nivel(lv) * 6 // 10)


# El tope de nivel. El juego tecnicamente llega a 600, pero la curva de
# level.xml acaba en 471 y de ahi en adelante no hay datos: se queda en 471,
# que es hasta donde se puede saber cuanta experiencia pide cada nivel.
NIVEL_MAXIMO = 471


def nivel_maximo() -> int:
    """El nivel mas alto al que se puede subir."""
    _cargar_curva_nivel()
    return min(600,max(_CURVA_NIVEL)) if _CURVA_NIVEL else NIVEL_MAXIMO


def exp_para_nivel(nv: int) -> int:
    """La experiencia ACUMULADA que pide ese nivel, sin recortar.

    NO se recorta a 0xFFFFFFFF aqui. Se hacia, y desde el nivel 299 en
    adelante devolvia siempre el mismo tope; el bucle que sube de nivel
    comparaba contra ese numero y, con la experiencia por encima, subia de
    nivel para siempre. El servidor se quedaba colgado al matar un bicho.
    El recorte va donde se empaqueta, que es donde hace falta.
    """
    curva = _cargar_curva_nivel()
    if nv in curva:
        return int(curva[nv])
    if not curva:
        return int(nv * 120)
    ultimo = max(curva)
    if nv > ultimo:
        # La curva de level.xml acaba en 471 y el tope del juego es 600. El
        # respaldo que habia (nivel * 120) daba 72.000 para el nivel 600,
        # o sea que se subia de golpe. Se extrapola con el salto de los dos
        # ultimos niveles, que es lo unico que se puede hacer sin datos.
        anterior = max(k for k in curva if k < ultimo)
        salto = int(curva[ultimo]) - int(curva[anterior])
        paso = max(1, salto // max(1, ultimo - anterior))
        return int(curva[ultimo]) + paso * (nv - ultimo)
    return int(nv * 120)


def exp_para_nivel_u32(nv: int) -> int:
    """Lo mismo, recortado para meterlo en un campo de 32 bits."""
    return min(exp_para_nivel(nv), 0xFFFFFFFF)


def exp_para_barra(nivel: int, exp: int) -> tuple:
    """(exp_actual, exp_siguiente) de 64 bits segun level.xml, sin truncar a 32 bits."""
    base = exp_para_nivel(nivel)
    siguiente = exp_para_nivel(nivel + 1)
    actual = max(base, int(exp or 0))
    if siguiente > 0:
        actual = min(actual, siguiente)
    return actual, siguiente



def calcular_exp(npc_type: int, buffs: dict = None) -> int:
    """Calcula la EXP de personaje ganada aplicando los multiplicadores de configuracion."""
    import configuracion
    d = _datos(npc_type) or {}
    base = d.get('exp', 35)
    mult = configuracion.multiplicador_exp(buffs)
    return max(1, int(round(base * mult)))


def calcular_skill_exp(buffs: dict = None) -> int:
    """Calcula la Skill EXP ganada aplicando los multiplicadores de configuracion."""
    import configuracion
    base = 6
    mult = configuracion.multiplicador_skill_exp(buffs)
    return max(1, int(round(base * mult)))


CODE_EQUIPAR = 1


def equipar_visual(entity_id: int, ranura: int, item_id: int) -> bytes:
    """0x001D code=1: le dice al cliente QUE lleva puesto en esa ranura.

    Sin esto el personaje se dibuja con la apariencia por defecto: en ropa
    interior y con un baston en la mano, sin importar lo que tenga equipado.
    Formato del spec: [u4 entidad][u1 cantidad][u1 code=1][u4 ranura][u4 item].
    Con item 0 se quita la pieza.
    """
    return (struct.pack('<HIB', 0x001D, entity_id, 1)
            + struct.pack('<BII', CODE_EQUIPAR, ranura, item_id))


def pct_dano_buffs(buffs, es_magico: bool, ahora: float = None) -> int:
    """El % de dano de salida que suman los buffs activos.

    Sale del 魔法傷害 y el 物理傷害 de magic.xml. Se leia desde siempre y no
    lo usaba nadie: un Soul Corral IV, que dice "Increase 10% spell damage",
    no cambiaba el golpe ni un punto. El equipo si contaba, porque va por
    otro camino, asi que la diferencia se notaba solo con los buffs puestos.

    Los caducados no suman, y varios activos se acumulan.
    """
    if not buffs:
        return 0
    clave = 'mag_dmg_pct' if es_magico else 'phys_dmg_pct'
    if ahora is None:
        ahora = time.time()
    total = 0
    for b in buffs.values():
        if isinstance(b, dict) and b.get('fin', 0) > ahora:
            total += b.get(clave, 0) or 0
    return total


def atributo(entity_id: int, valor: int, kind: int = VIDA) -> bytes:
    """Sub-mensaje 0x0013: un atributo de una entidad cambio.

    El valor se RECORTA al rango del campo. Por aqui pasan todos los
    atributos, y basta con que uno se salga -- la experiencia de un nivel
    alto son 25.478.672.000, que no caben en 32 bits -- para que el
    struct.error suba hasta el bucle de asyncio y tire la sesion. Paso al
    entrar al juego, antes de poder moverse.
    """
    _k = max(0, min(int(kind or 0), 0xFF))
    _v = max(0, min(int(valor or 0), 0xFFFFFFFF))
    return struct.pack('<HIBBI', 0x0013,
                       max(0, min(int(entity_id or 0), 0xFFFFFFFF)), 1,
                       _k, _v)


def empieza_ataque(atacante: int) -> bytes:
    """Sub-mensaje 0x000A que abre el ataque.

    Va con ceros: [atacante][0][0]. El dano NO va aqui -- se leyo mal al
    principio y se mandaba el dano en este mensaje, que el cliente ignora.
    El numero que se ve sale del 0x0011.
    """
    return struct.pack('<HIII', 0x000A, atacante, 0, 0)


def golpe(atacante: int, objetivo: int, dano: int) -> bytes:
    """Sub-mensaje 0x000A con atacante y objetivo (al fijar el blanco)."""
    return struct.pack('<HIII', 0x000A, atacante, objetivo, dano)


def fijar_objetivo(jugador: int, objetivo: int) -> bytes:
    """Sub-mensaje 0x000A que marca a quien se va a atacar."""
    return struct.pack('<HIII', 0x000A, jugador, objetivo, OBJETIVO_FIJADO)


def despawn_monstruo(entity_id: int) -> bytes:
    """Paquete opcode 0x0007: quitar entidad del mapa (despawn)."""
    return struct.pack('<HIB', 0x0007, entity_id, 0)


class AtaqueInfo(tuple):
    """Tupla de 2 elementos (tipo, objetivo) para compatibilidad total con `tipo, objetivo = d3`,
    que ademas expone tx, ty y flags como atributos para AOEs."""
    def __new__(cls, tipo, objetivo, tx=0, ty=0, flags=0):
        obj = super().__new__(cls, (tipo, objetivo))
        obj.tipo = tipo
        obj.objetivo = objetivo
        obj.tx = tx
        obj.ty = ty
        obj.flags = flags
        return obj


def parsear_ataque(cuerpo: bytes) -> AtaqueInfo:
    """Devuelve AtaqueInfo(tipo, objetivo, tx, ty, flags) desempaquetable como (tipo, objetivo)."""
    if len(cuerpo) < 6:
        return None
    if len(cuerpo) >= 16:
        tipo, objetivo, tx, ty, flags = struct.unpack_from('<HIIIH', cuerpo, 0)
        return AtaqueInfo(tipo, objetivo, tx, ty, flags)
    tipo, objetivo = struct.unpack_from('<HI', cuerpo, 0)
    return AtaqueInfo(tipo, objetivo, 0, 0, 0)


# La sesion que el servidor esta atendiendo ahora mismo (un solo hilo: o el
# paquete de un cliente o el tic de IA de un jugador). La pone app.py; la lee
# Monstruo.registrar_dano para saber de quien es cada golpe.
ATACANTE = [None]


def con_atacante(ses,callback):
    """Bind delayed hits to their caster, not the last socket/AI tick."""
    def ejecutar(*args,**kwargs):
        previous=ATACANTE[0]
        ATACANTE[0]=ses
        try:return callback(*args,**kwargs)
        finally:ATACANTE[0]=previous
    return ejecutar


def rehidratar_transformaciones(buffs):
    """Restore XML-derived modifiers in saved/legacy shape buffs, no recast."""
    for bid,entry in (buffs or {}).items():
        if not isinstance(entry,dict) or entry.get('fin',0)<=time.time():continue
        if not (entry.get('es_transform') or (entry.get('mag') or {}).get('es_transformacion')):continue
        mag=datos_magia(int(bid))
        if not mag.get('es_transformacion'):continue
        entry.pop('mp',None);entry.pop('hp',None)  # Spell costs are not max-stat bonuses.
        entry['mag']=mag;entry['es_transform']=True
        entry['trans_sprite']=mag.get('trans_sprite',0)
        entry['es_melee_trans']=bool(mag.get('es_melee_trans'))
        for key in ('atk_pct','def_pct','matk_pct','mdef_pct','hp_pct','mp_pct','mp_to_hp_pct'):
            if key in mag:entry[key]=mag[key]
        entry['atk_speed']=mag.get('atk_speed_bonus',0)
    return buffs


class Monstruo:
    """Un bicho vivo en el mapa."""

    def __init__(self, entity_id, npc_type, nombre, tile, sprite=0, stage=None):
        self.entity_id = entity_id
        self.npc_type = npc_type
        self.nombre = nombre
        self.stage = stage
        # El sprite que venia en la captura. Hace falta al REAPARECER: si no
        # se guarda, el monstruo se reconstruye sin el y cae en la tabla por
        # defecto, que es la del Slarm. Por eso las Wild Lily, los Forest
        # Monkey y los demas volvian a la vida convertidos en slimes.
        self.sprite = sprite
        self.tile = list(tile)
        self.tile_x = tile[0]
        self.tile_y = tile[1]
        self.spawn_tile = list(tile)
        self.spawn_x = tile[0]
        self.spawn_y = tile[1]
        d = _datos(npc_type) or {
            'hp': 50, 'atk': 5, 'var': 1, 'def': 0,
            'atk_range': 1, 'proj_ef': 0, 'move_speed': 50, 'move_range': 6
        }
        self.hp_max = d['hp']
        self.hp = d['hp']
        self.atk = d['atk']
        self.var = d['var']
        self.defensa = d['def']
        self.mdef = d.get('mdef', 0)
        self.matk = d.get('matk', 0)
        self.atk_range = d.get('atk_range', 1)
        self.proj_ef = d.get('proj_ef', 0)
        self.move_speed = d.get('move_speed', 50)
        self.atk_speed = d.get('atk_speed', 60)
        self.move_range = d.get('move_range', 6)
        self.agro = d.get('agro', 0)
        # Las Lilys no se mueven de su lugar pero atacan a distancia como arqueros
        self.es_estatico = ('lily' in nombre.lower() or self.move_speed == 0)
        self.muerto_en = None
        self.en_combate_con = None
        self.ultimo_ataque = 0.0
        # Efectos que le aplicaron los ataques del jugador. El stun y el
        # sangrado NO viajan por red: en la captura de Celestia, al pegar con
        # Basic Beating solo llega su 0x0011 y el cooldown, nunca el hechizo
        # 1045. Los lleva el servidor.
        self.aturdido_hasta = 0.0
        self.lento_hasta = 0.0
        self.sangra_hasta = 0.0
        self.sangra_cada = 0
        self.sangra_hp = 0
        self.sangra_ultimo = 0.0
        self.panico = False
        self.panico_hasta = 0.0
        self.debuffs = {}
        self.dano_jugador = 0
        self.dano_pet = 0
        self.res_lightning = d.get('res_lightning', 0)
        self.res_fire = d.get('res_fire', 0)
        self.res_ice = d.get('res_ice', 0)
        self.res_corrosion = d.get('res_corrosion', 0)
        self.res_body = d.get('res_body', 0)
        self.res_mind = d.get('res_mind', 0)
        self.thnd_atk = d.get('thnd_atk', 0)
        self.thnd_prob = d.get('thnd_prob', 0)
        self.fire_atk = d.get('fire_atk', 0)
        self.fire_prob = d.get('fire_prob', 0)
        self.ice_atk = d.get('ice_atk', 0)
        self.ice_prob = d.get('ice_prob', 0)
        self.rotten_atk = d.get('rotten_atk', 0)
        self.rotten_prob = d.get('rotten_prob', 0)
        self.captura_fallida_en = None

    def registrar_dano(self, cantidad: int, es_pet: bool = False):
        """Acumula el dano real infligido al monstruo (jugador/invocacion/charmed vs mascota)."""
        c = max(0, int(cantidad or 0))
        if c <= 0:
            return
        # Y de QUIEN es: el jugador de la sesion que se esta atendiendo (su
        # mascota e invocaciones cuentan para el). Con bichos compartidos lo
        # usa app._repartir_muerte para repartir exp, oro y botin.
        _a = ATACANTE[0]
        _cid = getattr(getattr(_a, 'personaje', None), 'char_id', None)
        if _cid is not None:
            if not isinstance(getattr(self, 'dano_por', None), dict):
                self.dano_por = {}
            self.dano_por[int(_cid)] = self.dano_por.get(int(_cid), 0) + c
        if es_pet:
            self.dano_pet = getattr(self, 'dano_pet', 0) + c
        else:
            self.dano_jugador = getattr(self, 'dano_jugador', 0) + c

    @property
    def vivo(self):
        return self.hp > 0

    @vivo.setter
    def vivo(self, val):
        if not val:
            self.hp = 0

    @property
    def porcentaje(self):
        return max(0, min(100, round(100 * self.hp / self.hp_max)))

    @property
    def aturdido(self):
        return time.time() < self.aturdido_hasta

    def aplicar_efecto(self, ef: dict):
        """Aplica el 轉嫁法術 de un ataque: stun, sangrado, veneno o ralentizacion."""
        if not ef or not ef.get('dur_ms'):
            return None
        # Resistencia del objetivo segun el tipo de debuff (體質型 vs res_body, 心靈型 vs res_mind):
        if ef.get('tipo_mente') or ef.get('estado') in ('panico', 'confuso', 'silencio'):
            res_val = getattr(self, 'res_mind', 0)
            if res_val > 0 and random.randint(1, 100) <= min(90, res_val):
                return None
        elif ef.get('tipo_cuerpo') or ef.get('estado') in ('aturdido', 'lento', 'inmovilizado', 'sangrado', 'veneno'):
            res_val = getattr(self, 'res_body', 0)
            if res_val > 0 and random.randint(1, 100) <= min(90, res_val):
                return None
        ahora = time.time()
        fin = ahora + ef['dur_ms'] / 1000.0
        if not hasattr(self, 'efectos_activos') or self.efectos_activos is None:
            self.efectos_activos = {}
        mid = ef.get('magia')
        if mid:
            self.efectos_activos[mid] = fin
        if ef.get('estado') in ('aturdido', 'congelado', 'inmovilizado',
                                'paralizado', 'atado'):
            self.aturdido_hasta = max(self.aturdido_hasta, fin)
            return 'aturdido'
        if ef.get('hp_tick', 0) < 0:
            self.sangra_hasta = max(self.sangra_hasta, fin)
            self.sangra_cada = max(1, ef.get('intervalo') or 1)
            dano_elem = ef.get('elem_dmg', 0)
            self.sangra_hp = abs(ef['hp_tick']) + dano_elem
            self.sangra_ultimo = ahora
            nom = ef.get('nombre', '').lower()
            return 'veneno' if ('poison' in nom or ef.get('estado') == '閃綠色') else 'sangrado'
        if ef.get('vel_mov', 0) < 0:
            self.lento_hasta = max(self.lento_hasta, fin)
            return 'lento'
        return 'efecto'

    def tick_sangrado(self):
        """Cuanto dano por sangrado toca ahora, o 0."""
        ahora = time.time()
        if ahora >= self.sangra_hasta or not self.sangra_hp:
            return 0
        if ahora - self.sangra_ultimo < self.sangra_cada:
            return 0
        self.sangra_ultimo = ahora
        d = min(self.hp, self.sangra_hp)
        self.registrar_dano(d, es_pet=False)
        self.hp = max(0, self.hp - d)
        if not self.hp:
            self.muerto_en = ahora
            self.en_combate_con = None
        return d


    @property
    def defensa_efectiva(self) -> int:
        d = self.defensa
        now = time.time()
        if hasattr(self, 'debuffs') and self.debuffs:
            for bid, bdata in list(self.debuffs.items()):
                if bdata.get('fin', 0) > now:
                    d += bdata.get('def_mod', 0)
                else:
                    self.debuffs.pop(bid, None)
        return max(0, d)

    @property
    def mdef_efectiva(self) -> int:
        d = self.mdef
        now = time.time()
        if hasattr(self, 'debuffs') and self.debuffs:
            for bid, bdata in list(self.debuffs.items()):
                if bdata.get('fin', 0) > now:
                    d += bdata.get('mdef_mod', 0)
                else:
                    self.debuffs.pop(bid, None)
        return max(0, d)

    def recibir(self, ataque: int, es_magico: bool = False, mult: float = 1.0, var_pct: float = 0.05, es_pet: bool = False) -> int:
        """Aplica el dano y devuelve cuanto pego de verdad."""
        now = time.time()
        mit_pct = 0
        if hasattr(self, 'debuffs') and self.debuffs:
            for bid, bdata in list(self.debuffs.items()):
                if bdata.get('fin', 0) > now:
                    mit_pct += (bdata.get('mag_mit_pct', 0) if es_magico else bdata.get('phys_mit_pct', 0))
                else:
                    self.debuffs.pop(bid, None)
        defensa_target = self.mdef_efectiva if es_magico else self.defensa_efectiva
        # LA DEFENSA SE APLICA DE DOS MANERAS Y VALE LA QUE MAS PEGUE.
        #
        # Habia una sola, la mitigacion suave con K=420, calibrada contra
        # bichos de nivel bajo: Death Mummy 3 (ATK 249) contra un Condor (DEF
        # 329) pega 140-143, y 249*420/749 da 140. Ahi clava.
        #
        # Pero esa curva se hunde cuando la defensa crece. Los bichos de
        # Specter Village son de nivel 300 y tienen 34.797 de MDEF: el factor
        # queda en 420/35217, un 1,2%. Un Forbidden Curse IV, que multiplica
        # por 8,25, pasaba de 470.068 a 5.606. En el juego original ese mismo
        # golpe hace unos 568.000, o sea CIEN VECES mas.
        #
        # Restando la defensa sale lo otro: 470.068 - 34.797 = 435.272, y con
        # el 15% de la montura 500.562, que es del orden de los 568.000 que se
        # midieron. Pero restar no sirve abajo: al Death Mummy le daria un
        # numero negativo.
        #
        # Las dos mediciones se cumplen quedandose con la mayor. Abajo gana la
        # mitigacion, arriba gana la resta, y no hace falta ninguna constante
        # que dependa del nivel.
        if defensa_target > 0:
            factor_def = 420.0 / (defensa_target + 420.0)
        else:
            factor_def = 1.0
        bruto = ataque * mult
        base_dano = max(1.0, bruto * factor_def, bruto - defensa_target)
        spread = 1.0 + random.uniform(-var_pct, var_pct)
        d = max(1, int(round(base_dano * spread)))
        if mit_pct != 0:
            d = max(1, int(round(d * (1.0 - mit_pct / 100.0))))
        self.registrar_dano(min(self.hp, d), es_pet=es_pet)
        self.hp = max(0, self.hp - d)
        if getattr(self, 'panico', False):
            self.panico = False
        if not self.hp:
            self.muerto_en = time.time()
            self.en_combate_con = None
            if hasattr(self, 'debuffs') and self.debuffs:
                self.debuffs.clear()
        return d

    def pegar(self) -> int:
        base = self.atk + random.randint(-self.var, self.var)
        now = time.time()
        atk_mod = 0
        dmg_pct = 0
        if hasattr(self, 'debuffs') and self.debuffs:
            for bid, bdata in list(self.debuffs.items()):
                if bdata.get('fin', 0) > now:
                    atk_mod += bdata.get('atk_mod', 0)
                    dmg_pct += bdata.get('phys_dmg_pct', 0)
                else:
                    self.debuffs.pop(bid, None)
        total = max(1, base + atk_mod)
        if dmg_pct != 0:
            total = max(1, int(round(total * (1.0 + dmg_pct / 100.0))))
        return total

    def toca_reaparecer(self) -> bool:
        return (not self.vivo and self.muerto_en
                and time.time() - self.muerto_en >= getattr(self,'daily_respawn',SEGUNDOS_REAPARICION))

    def revivir(self):
        """Vuelve a la vida cerca de su sitio, no clavado en el mismo punto."""
        import random as _r
        self.hp = self.hp_max
        self.muerto_en = None
        if getattr(self, 'es_estatico', False) or getattr(self, 'move_speed', 50) == 0 or getattr(self, 'move_range', 6) <= 0:
            self.tile_x = self.spawn_x
            self.tile_y = self.spawn_y
        else:
            radio = max(1, min(getattr(self, 'move_range', 0) or 0,
                               RANGO_PASEO_MIN))
            import transitable as _tr
            st = getattr(self, 'stage', None)
            candidato = None
            for _ in range(10):
                tx = max(0, self.spawn_x + _r.randint(-radio, radio))
                ty = max(0, self.spawn_y + _r.randint(-radio, radio))
                if ((st is None or _tr.se_pisa(st, tx, ty))
                        and (st not in (168, 176, 413) or _tr.linea_libre(st, (self.spawn_x, self.spawn_y), (tx, ty)))):
                    candidato = (tx, ty)
                    break
            if candidato:
                self.tile_x, self.tile_y = candidato
            else:
                self.tile_x, self.tile_y = self.spawn_x, self.spawn_y
        self.tile = [self.tile_x, self.tile_y]
        self.en_combate_con = None
        self.ultimo_ataque = 0.0
        self.volviendo_casa = False
        self.panico = False
        self.panico_hasta = 0.0
        self.dano_jugador = 0
        self.dano_pet = 0
        self.dano_por = {}
        if hasattr(self, 'debuffs') and self.debuffs:
            self.debuffs.clear()
        self.captura_fallida_en = None



_ORO_MONSTRUOS = None


def _tabla_oro() -> dict:
    """El oro por monstruo y por tramo, de plantillas/oro_monstruos.json."""
    global _ORO_MONSTRUOS
    if _ORO_MONSTRUOS is None:
        f = pathlib.Path(__file__).parent / 'plantillas' / 'oro_monstruos.json'
        try:
            _ORO_MONSTRUOS = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            _ORO_MONSTRUOS = {'por_monstruo': {}, 'por_tramo': {}}
    return _ORO_MONSTRUOS


def botin(nivel_monstruo: int = 1, npc_type: int = 0) -> int:
    """Cuanto oro suelta ese monstruo.

    Daba `random.randint(3, 8)` para TODOS, sin mirar cual era ni de que
    nivel: un bicho de Bearscape soltaba lo mismo que un Slarm del Lyceum.

    Ahora sale de serv_drop.xml, que trae por cada tabla de drop el oro
    medio (平均金錢) y cuanto varia (金錢變數). Hay 1.595 monstruos con su
    dato propio; el resto -- casi todo por encima del nivel 200, que es
    donde se acaba ese archivo -- usa la mediana de su tramo de diez
    niveles, y por arriba se extrapola. Ver tools/oro_de_monstruos.py.
    """
    import configuracion
    t = _tabla_oro()
    medio = var = 0
    fila = t.get('por_monstruo', {}).get(str(int(npc_type or 0)))
    if fila:
        medio, var = int(fila[0]), int(fila[1] if len(fila) > 1 else 0)
    else:
        # Tope al nivel: en karang_desert hay un monstruo con 4.294.967.295
        # (0xFFFFFFFF), que es un dato corrupto de la plantilla. Sin esto
        # caia en el ultimo tramo y soltaba casi dos millones de oro.
        nv = max(0, min(NIVEL_MAXIMO, int(nivel_monstruo or 1)))
        tramos = t.get('por_tramo') or {}
        if tramos:
            clave = str((nv // 10) * 10)
            if clave not in tramos:
                # Por encima de lo que hay, el ultimo; por debajo, el primero.
                claves = sorted(int(k) for k in tramos)
                clave = str(claves[-1] if nv > claves[-1] else claves[0])
            medio = int(tramos[clave])
            var = medio // 4
    if medio <= 0:
        medio, var = random.randint(3, 8), 0
    if var:
        medio = random.randint(max(1, medio - var), medio + var)
    return max(1, int(round(medio * configuracion.TASA_ORO_BASE)))


_DROPS_CACHE = {}
_DROPS_PLANTILLA = None
_MON_INFO_CACHE = {}
_DROP_OFICIAL_CACHE = {}

# En los XML de las dos instancias Chaos todos los monstruos vienen marcados
# con 王, incluidos los mobs comunes.  Esa marca sirve para sus inmunidades,
# pero no significa que todos tengan botin garantizado.  achievement.xml es
# mas preciso. En Dinosaur Arena los cuatro jefes de progresion se distinguen
# por sus cientos de millones de HP; en End Time los jefes 23709..23714 tienen
# a la vez marca 王 y drop_id propio. Ba'shin's Gaze es el guardian de ambas
# instancias y tambien conserva botin garantizado en sus dos variantes.
_MONSTRUOS_CHAOS = frozenset(range(23673, 23725)) | {23745, 23839}
_JEFES_CHAOS = frozenset({
    # Chaos-Dinosaur Arena
    23684, 23685, 23687, 23688, 23724,
    # Chaos-End Time
    23709, 23710, 23711, 23712, 23713, 23714, 23745, 23839,
})


_TIPOS_DE_TROPA = None


def es_de_tropa(npc_type: int) -> bool:
    """Si ese tipo sale en GRUPO (mas de 2 en un mismo mapa): monstruo comun.

    Muchas instancias marcan con 王 a casi todo -- Leviathan's Bedroom a 540
    bichos, Botti Palace a 422, la Dinosaur Arena a 350 -- y con eso todos
    soltaban botin al 100%, como un jefe, y llenaban la mochila. Un jefe sale
    uno (o dos) por mapa; lo que sale en tropa no lo es aunque lleve la marca.
    Se cuenta en las plantillas y en las zonas que saca el mapa por evento.
    """
    global _TIPOS_DE_TROPA
    if _TIPOS_DE_TROPA is None:
        import collections as _co
        import json as _js
        tropa = set()
        try:
            import login as _lg_t
            for f in set(_lg_t.PLANTILLAS_POR_STAGE.values()):
                try:
                    d = _js.loads((pathlib.Path(__file__).parent / 'plantillas' / f)
                                  .read_text(encoding='utf-8'))
                except Exception:
                    continue
                c = _co.Counter(int(e.get('npc_type') or 0) for e in d.get('spawns', [])
                                if e.get('monstruo') and not e.get('apagado'))
                tropa |= {t for t, n in c.items() if n > 2}
        except Exception:
            pass
        try:
            import eventos as _ev_t
            for d in _ev_t._datos()['stages'].values():
                for g in (d.get('generadores') or {}).values():
                    if int(g.get('cuantos') or 0) > 2:
                        tropa |= {int(t) for t in g.get('tipos') or []}
        except Exception:
            pass
        _TIPOS_DE_TROPA = frozenset(tropa)
    return int(npc_type or 0) in _TIPOS_DE_TROPA


def _cargar_drops_plantilla() -> dict:
    global _DROPS_PLANTILLA
    if _DROPS_PLANTILLA is None:
        p = pathlib.Path(__file__).parent / 'plantillas' / 'drops_monstruos.json'
        if p.exists():
            try:
                _DROPS_PLANTILLA = json.loads(p.read_text(encoding='utf-8'))
            except Exception as e:
                # Esto estuvo vacio mucho tiempo sin que se notara: `json`
                # no estaba importado, el NameError caia aqui y los 12.715
                # drops de la plantilla quedaban muertos en silencio. Si
                # vuelve a fallar, que al menos se vea en el log.
                logging.getLogger('combate').warning(
                    'no se pudo leer drops_monstruos.json (%s: %s); '
                    'los monstruos no van a soltar nada'
                    % (type(e).__name__, e))
                _DROPS_PLANTILLA = {}
        else:
            _DROPS_PLANTILLA = {}
    return _DROPS_PLANTILLA


_JEFES = None


def es_jefe(npc_type: int) -> bool:
    """Si ese monstruo es un jefe, segun la columna 王 de content.db.

    El juego marca asi a 1.513 monstruos, de los Speedy Automaton de nivel
    470 para abajo. No se deduce del nombre ni del nivel: lo dice el dato.
    """
    global _JEFES
    if _JEFES is None:
        _JEFES = set()
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            try:
                con = sqlite3.connect(db)
                for (mid,) in con.execute(
                        "select id from monster where 王 = '是'"):
                    try:
                        _JEFES.add(int(mid))
                    except (TypeError, ValueError):
                        continue
                con.close()
            except Exception as e:
                logging.getLogger('combate').warning(
                    'no se pudo leer que monstruos son jefes (%s: %s); '
                    'ninguno soltara botin garantizado', type(e).__name__, e)
    return int(npc_type or 0) in _JEFES


_NIVEL_ITEM = None


def _niveles_de_item() -> dict:
    """item_id -> nivel, de la columna 物品等級, TODOS de una vez.

    De una vez y no uno a uno a proposito: inventario.nivel_de_item() abre
    una conexion nueva a content.db en cada llamada, y comprobar los
    cuarenta items de una tabla de drops con eso tardaba lo suficiente como
    para que se notara el tiron la primera vez que muere cada clase de
    bicho. Son 60.000 filas y entran en memoria sin problema.
    """
    global _NIVEL_ITEM
    if _NIVEL_ITEM is not None:
        return _NIVEL_ITEM
    _NIVEL_ITEM = {}
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if not db.exists():
        return _NIVEL_ITEM
    try:
        con = sqlite3.connect(db)
        for t in ('item', 'item2', 'item3', 'item4', 'item5',
                  'item6', 'item7', 'item8', 'item9'):
            try:
                cols = [c[1] for c in con.execute('pragma table_info(%s)' % t)]
                if '物品等級' not in cols:
                    continue
                for iid, lv in con.execute(
                        'select id, "物品等級" from %s' % t):
                    try:
                        iid = int(iid)
                    except (TypeError, ValueError):
                        continue
                    if iid in _NIVEL_ITEM:
                        continue
                    try:
                        _NIVEL_ITEM[iid] = int(lv)
                    except (TypeError, ValueError):
                        continue
            except Exception:
                continue
        con.close()
    except Exception as e:
        logging.getLogger('combate').warning(
            'no se pudieron leer los niveles de los items (%s: %s); '
            'no se filtraran las tablas de drops heredadas por nombre',
            type(e).__name__, e)
    return _NIVEL_ITEM


def _nivel_item(item_id: int):
    """El nivel de ese item, o None si no lo declara."""
    return _niveles_de_item().get(int(item_id)) or None


def _nivel_plausible(lista_raw, nivel_monstruo: int) -> bool:
    """Si esa lista de drops pega con un bicho de ese nivel.

    Se usa solo para descartar las tablas heredadas por NOMBRE de un
    homonimo mucho mas debil. Se mira la MEDIANA y no el minimo, porque una
    tabla buena puede llevar sueltos un par de materiales de nivel bajo sin
    que eso la invalide.
    """
    niveles = []
    for par in lista_raw or []:
        if isinstance(par, (list, tuple)) and par:
            lv = _nivel_item(int(par[0]))
            if lv:
                niveles.append(lv)
    if not niveles:
        return True        # sin dato no se descarta nada
    niveles.sort()
    mediana = niveles[len(niveles) // 2]
    return mediana * 2 >= int(nivel_monstruo or 0)


# Tablas ponderadas originales de drop_table en content.db para los cuatro
# jefes de Nightmare Cave (Bloody Hook, Soul Puller, Violent Cat, Evil Chieftain):
# tres tiradas por muerte con ~98.15%–99.54% de peso para Dream Piece (3040).
_DROPS_PONDERADOS_JEFES = {
    420: (3, ((3040, 1, 981481), (5918, 1, 18519))),
    422: (3, ((3040, 1, 981481), (5919, 1, 18519))),
    424: (3, ((3040, 1, 990741), (5921, 1, 9259))),
    426: (3, ((3040, 1, 99537), (5920, 1, 463))),
}


def botin_items(npc_type: int, nombre: str = '', nivel: int = 0, buffs=None) -> list:
    """Items que suelta el monstruo de drops_monstruos.json o content.db con multiplicador de drops."""
    global _DROPS_CACHE, _MON_INFO_CACHE, _DROP_OFICIAL_CACHE
    _pond = _DROPS_PONDERADOS_JEFES.get(int(npc_type or 0))
    if _pond is not None:
        _tiradas, _entradas = _pond
        _pares = [(it, cnt) for it, cnt, _w in _entradas]
        _pesos = [_w for _it, _cnt, _w in _entradas]
        return list(random.choices(_pares, weights=_pesos, k=_tiradas))
    if npc_type in _DROPS_CACHE:
        candidatos = _DROPS_CACHE[npc_type]
    else:
        candidatos = []
        plantilla = _cargar_drops_plantilla()
        drops_por_id = plantilla.get('drops') or {}
        drops_por_nom = plantilla.get('por_nombre') or {}
        drops_por_nv = plantilla.get('por_nivel') or {}

        lista_raw = None
        tabla_oficial = False

        # Resolver primero el drop_id REAL. Las claves de la plantilla son
        # IDs de tablas, no npc_type; ambos numeros pueden coincidir por azar.
        mon_nom = nombre
        mon_nv = nivel
        mon_did = None
        if npc_type in _MON_INFO_CACHE:
            mon_did, db_nom, db_nv = _MON_INFO_CACHE[npc_type]
            if not mon_nom:
                mon_nom = db_nom
            if not mon_nv:
                mon_nv = db_nv
        else:
            db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
            if db.exists():
                try:
                    con = sqlite3.connect(db)
                    mrow = con.execute('select drop_id, name, level from monster where id=?', (str(npc_type),)).fetchone()
                    if mrow:
                        mon_did = str(mrow[0] or '').strip()
                        mon_nom = mon_nom or str(mrow[1] or '').strip()
                        mon_nv = mon_nv or int(mrow[2] or 1)
                        _MON_INFO_CACHE[npc_type] = (mon_did, mon_nom, mon_nv)
                        if mon_did:
                            lista_raw = drops_por_id.get(mon_did)
                            tabla_oficial = bool(lista_raw)
                        if not lista_raw and mon_did:
                            dt = con.execute('select * from drop_table where id=?', (mon_did,)).fetchone()
                            if dt:
                                cols = [c[1] for c in con.execute('pragma table_info(drop_table)').fetchall()]
                                row_dict = dict(zip(cols, dt))
                                for i in range(1, 21):
                                    it = row_dict.get(f'item{i}')
                                    cnt = row_dict.get(f'count{i}')
                                    if it and str(it).isdigit() and int(it) > 0:
                                        c_val = int(cnt) if cnt and str(cnt).isdigit() else 1
                                        candidatos.append((int(it), c_val))
                                tabla_oficial = bool(candidatos)
                except Exception:
                    pass

        # Compatibilidad con filas antiguas sin drop_id propio.
        if not lista_raw and not candidatos and not mon_did:
            lista_raw = drops_por_id.get(str(npc_type))
            tabla_oficial = bool(lista_raw)

        # 2. Fallback por nombre del monstruo en serv_drop.xml / drop.xml
        if not lista_raw and not candidatos and mon_nom:
            nom_k = mon_nom.strip().lower()
            lista_raw = drops_por_nom.get(nom_k)
            if not lista_raw:
                for pref in ('the ', 'violent ', 'wild ', 'mutated ', 'elite ', 'young ', 'giant '):
                    if nom_k.startswith(pref) and nom_k[len(pref):] in drops_por_nom:
                        lista_raw = drops_por_nom[nom_k[len(pref):]]
                        break
            if lista_raw:
                tabla_oficial = True
            # EL NOMBRE NO BASTA: hay bichos homonimos con cien niveles de
            # diferencia. El juego reusa nombres, y buscar la tabla de drops
            # por el nombre hace que el grande herede la del chico:
            #
            #   Dragon Soldier    nivel 414 -> items de nivel 89
            #   Blue Merman       nivel 384 -> items de nivel 89
            #   Magic Pumpkinman  nivel 300 -> items de nivel 15
            #   Spring Fairy      nivel 264 -> items de nivel 110
            #
            # Son cuatro en todo el juego, pero son justo los que te dejan
            # soltando basura a un bicho de nivel 400. Si lo que sale por el
            # nombre esta por debajo de la mitad del nivel del monstruo, no
            # vale y se pasa al cubo de nivel, que da equipo de su nivel.
            if lista_raw and mon_nv and not _nivel_plausible(lista_raw, mon_nv):
                lista_raw = None
                tabla_oficial = False

        # 3. Fallback por bucket de nivel para regiones nuevas (Forest, Desert, Candy, Floating, etc.)
        if not lista_raw and not candidatos and drops_por_nv:
            # El tope es 500, no 300: el bicho mas alto del juego es de 485.
            # Con el 300 todo lo de la ultima region (Clink Harbor va de 390
            # a 403) caia en el cubo de 300 y soltaba equipo de ese nivel.
            nv_b = max(0, min(500, ((int(mon_nv or 30) // 10) * 10)))
            for b_try in (nv_b, nv_b - 10, nv_b + 10, 60, 50):
                if str(b_try) in drops_por_nv and drops_por_nv[str(b_try)]:
                    lista_raw = drops_por_nv[str(b_try)]
                    break

        if lista_raw and not candidatos:
            for par in lista_raw:
                if isinstance(par, (list, tuple)) and len(par) >= 2:
                    candidatos.append((int(par[0]), max(1, int(par[1]))))

        _DROPS_CACHE[npc_type] = candidatos
        _DROP_OFICIAL_CACHE[npc_type] = tabla_oficial

    import configuracion
    drops = []
    if not candidatos:
        return drops
    # Los mapas Chaos marcan todos sus mobs con 王. Solo sus bosses oficiales
    # tienen botin al 100%; los demas pasan por la probabilidad normal. Fuera
    # de esos mapas se conserva el comportamiento previo de los jefes.
    jefe_garantizado = (npc_type in _JEFES_CHAOS if npc_type in _MONSTRUOS_CHAOS
                        else (es_jefe(npc_type) and not es_de_tropa(npc_type)))
    if jefe_garantizado:
        drops.append(random.choice(candidatos))
        return drops
    prob = min(0.95, 0.90 * configuracion.multiplicador_drop(buffs))
    if random.random() < prob:
        drops.append(random.choice(candidatos))
    return drops


_MAGIC_CACHE = {}


def _palabra(clave: str, texto: str) -> bool:
    """Si `clave` aparece como PALABRA, no como trozo de otra.

    Buscando 'harm' suelto, "Lava Charm" daba positivo y Erosion IV --
    que dice "Cannot be used with [Lava Charm]" -- dejaba de contar como
    buff. El servidor lo tomaba por ataque y pedia un objetivo, asi que el
    self buff no se podia lanzar.
    """
    import re as _re
    borde = chr(92) + 'b'
    return bool(_re.search(borde + _re.escape(clave) + borde,
                           texto or ''))


# Cuanto multiplica el ataque cada FORMULA de habilidad, para las que no
# traen 平均傷害. Medido con R.Atk 96663 en el proxy; son un punto por
# formula y el numero ya lleva restada la defensa del bicho.
RATIO_POR_FORMULA = {
    '40': 2.84,   # Strangle Strike IV: 274747
    '15': 0.76,   # Thunder Sword III:   73866
}
RATIO_FORMULA_DEFECTO = 1.0


def encontrar_sub_combate(mid: int, d: dict, tabla: dict):
    """Encuentra el subhechizo real de combate si el hechizo lanzador delega (TNT Arrow, Aparctias Shot, etc.)."""
    if not d or not tabla:
        return None
    form = str(d.get('公式') or '')
    p1 = d.get('動態參數1')
    hijo = d.get('轉嫁法術')
    hp = d.get('HP') or d.get('hp')

    if form == '7' and p1 and str(p1).isdigit() and int(p1) in tabla:
        return int(p1)
    if form == '63':
        if 16619 <= mid <= 16623 and (mid + 113) in tabla:
            return mid + 113
        if 13781 <= mid <= 13805 and (mid + 120) in tabla:
            return mid + 120
        if p1 and str(p1).isdigit() and int(p1) in tabla:
            return int(p1)
    if hijo and str(hijo).isdigit() and int(hijo) in tabla:
        h_d = tabla[int(hijo)]
        if not hp and (h_d.get('HP') or h_d.get('hp')):
            return int(hijo)
    return None


def datos_magia(magic_id: int) -> dict:
    """Informacion del hechizo/skill desde magic.xml."""
    global _MAGIC_CACHE
    if magic_id in _MAGIC_CACHE:
        return _MAGIC_CACHE[magic_id]
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    res = {'id': magic_id, 'nombre': '', 'mp': 0, 'sp': COSTE_GOLPE,
           'efecto': EFECTO_GOLPE, 'hp': 0, 'cd_ms': 1000, 'dur_ms': 0,
           'cast_time': 100, 'crit_rate': 0, 'phys_mit': 0, 'mag_mit': 0,
           'es_auto': False, 'es_cura': False, 'es_buff': False,
           'es_ataque': False, 'es_pasiva': False,
           'es_magia_visual': False}
    d = {}
    if db.exists():
        try:
            con = sqlite3.connect(db)
            cols = [c[1] for c in con.execute('pragma table_info(magic)').fetchall()]
            row = con.execute('select * from magic where id=?', (str(magic_id),)).fetchone()
            con.close()
            if row:
                for k_col, v_col in zip(cols, row):
                    if v_col is not None and str(v_col).strip() != '':
                        d[k_col] = v_col
        except Exception:
            pass
    d_xml = _magic_xml().get(int(magic_id or 0))
    if d_xml:
        d.update(d_xml)
    if d:
        try:
            res['nombre'] = d.get('名稱') or d.get('name') or ''
            def _num(val, default=0):
                try: return int(float(val)) if val is not None and str(val).strip() else default
                except (ValueError, TypeError): return default

            res['mp'] = _num(d.get('消耗MP'), 0)
            res['cost_sp'] = _num(d.get('消耗SP燈') or d.get('cost_sp'), 0)
            res['sp'] = res['cost_sp']
            res['sp_gana'] = _num(d.get('SP'), 0)
            # EL SP PUEDE VENIR DEL HECHIZO ENCADENADO. Bloodlust V (5680) no
            # trae SP: trae el sacrificio -- hp -6000 de vida MAXIMA durante
            # 300 s -- y encadena por 轉嫁法術 el 4650 con 轉嫁機率 100, que
            # es el que lleva SP 6000. Leyendo solo la columna del padre el
            # log decia "_dar_sp(Bloodlust V): sp_gana=0" y no daba nada.
            # Solo se toma si el hijo de verdad trae SP: hay miles de
            # encadenados de ataque (aturdir, sangrar, veneno) y esos no.
            # SIGILO Y TECNICAS DE ASESINO, de los propios datos:
            #   魔法狀態 = 潛行  -> el hechizo pone en sigilo (Sneak I..V)
            #   物理迴避        -> la esquiva que da mientras dura (75 en V)
            #   暗殺型 = 是      -> tecnica de asesino: solo se usa en sigilo
            # "Varios golpes individuales dentro del area": el hechizo marca la
            # zona y lo que cae sobre CADA objetivo es su encadenado
            # (轉嫁法術), con su propio efecto. Spear Shower V es el 13284 con
            # el efecto 511 y su hijo el 13374, que lleva el 493 -- las lanzas
            # que caen -- y los 3500 de poder del tooltip.
            res['multi_golpe_area'] = d.get('範圍多次單體攻擊') == '是'
            # 不能對玩家施放: el hechizo no se puede usar contra jugadores (71 en
            # magic.xml). Lo mira pvp_liga.atacar.
            res['no_jugadores'] = d.get('不能對玩家施放') == '是'
            res['hijo_area'] = _num(d.get('轉嫁法術'), 0) if res['multi_golpe_area'] else 0
            res['sigilo'] = d.get('魔法狀態') == '潛行'
            res['esquiva_fis'] = _num(d.get('物理迴避'), 0)
            res['asesino'] = d.get('暗殺型') == '是'
            res['sp_gana_prob'] = 100
            _hijo = _num(d.get('轉嫁法術'), 0)
            if not res['sp_gana'] and _hijo and _hijo != magic_id:
                _sp_hijo = datos_magia(_hijo).get('sp_gana', 0)
                if _sp_hijo > 0:
                    res['sp_gana'] = _sp_hijo
                    res['sp_gana_prob'] = _num(d.get('轉嫁機率'), 100) or 100
            res['efecto'] = _num(d.get('特效編號'), EFECTO_GOLPE)
            res['hp'] = _num(d.get('hp') if d.get('hp') is not None else d.get('HP'), 0)
            res['cd_ms'] = _num(d.get('後置時間'), 1000)
            dur_val = _num(d.get('持續時間'), 0)
            res['dur_ms'] = dur_val * 1000 if dur_val > 0 else 0
            res['cast_time'] = _num(d.get('前置時間'), 100)
            res['rango'] = _num(d.get('射程'), 1)
            res['crit_rate'] = _num(d.get('crit_rate') if d.get('crit_rate') is not None else (d.get('爆擊率') or d.get('重擊機率')), 0)
            res['phys_mit'] = _num(d.get('物理傷害抵銷'), 0)
            res['mag_mit'] = _num(d.get('魔法傷害抵銷'), 0)
            res['dano_base'] = _num(d.get('平均傷害'), 0)
            # EL 高權位 NO ES UNA MAGNITUD, ES UNA CATEGORIA.
            #
            # Se usaba de divisor del daño, y eso castigaba sin motivo a
            # los hechizos que no llevan el valor comun. Contados los 2210
            # hechizos con daño: el 55,5% vale 200, el 15% 201 y el 12,6%
            # 203 -- un 83% entre 200 y 204 -- y el resto son valores
            # sueltos (500, 381, 714, 792, 576...). No crece con el nivel:
            # Flying Dart I (nivel 1) y Berserk Cry I (nivel 206) valen los
            # dos 200.
            #
            # Dividiendo por el, Hyperspace V (381) pegaba 2,3 veces menos
            # que Earth Anger V (203) pese a pedir 42 niveles mas y 1.422
            # MP mas, y Rock Pillars (716) se quedaba a un tercio. Ahora el
            # divisor es fijo: el daño queda proporcional al 平均傷害, que
            # es justo el "Spell power" que el cliente enseña en el tooltip.
            #
            # Se deja en 200, el valor dominante, para no mover el daño del
            # 83% de los hechizos. El 高權位 de verdad sigue disponible en
            # priority_group por si algun dia se averigua que es.
            res['base_denom'] = DENOM_HECHIZO
            res['priority_group'] = _num(d.get('高權位'), 0)
            if not res['dano_base']:
                _f = str(d.get('公式') or '')
                _r = RATIO_POR_FORMULA.get(_f, RATIO_FORMULA_DEFECTO)
                res['dano_base'] = int(round(_r * res['base_denom']))
                res['ratio_formula'] = _r
            res['dano_var'] = _num(d.get('傷害變數'), 0)
            res['dano_coef'] = _num(d.get('傷害係數'), 0)
            res['formula'] = _num(d.get('公式'), 0)

            target = str(d.get('對象') or '')
            desc = str(d.get('desc') or d.get('說明') or '')
            act = str(d.get('施展動作') or '')
            res['accion'] = act
            # magic.xml distingue "施法動作" (cast) de "攻擊動作"
            # (ataque fisico). Ese dato decide el byte 20 del 0x0011.
            res['es_magia_visual'] = '\u65bd\u6cd5' in act
            res['target'] = target
            res['area'] = _num(d.get('範圍'), 0)
            res['es_terreno'] = (target == '地面')
            nom_l = res['nombre'].lower()
            desc_l = desc.lower()
            res['es_self_aoe'] = (target == '自己' and res['area'] > 0 and (d.get('攻擊型') == '是' or 'trap' in nom_l or 'trap' in desc_l))
            # AREA ALREDEDOR DEL OBJETIVO: los de ataque que se lanzan a un
            # enemigo (對象 角色) y traen 範圍 pegan a todos los que esten a
            # esa distancia de el. Shock Suit ("dealing DMG to all enemies
            # within range", 範圍 8), Arrow Fan, Earth Tremor... 568 en
            # magic.xml, y todos le daban solo al pinchado. La rama de area
            # de app.py ya centra en el bicho cuando lo hay. Fuera quedan los
            # que reparten a su manera: Chain Lightning (42) rebota, las
            # marcas (65) detonan y Wolf Spirit (38) sacrifica.
            res['es_aoe_objetivo'] = (target == '角色' and res['area'] > 0
                                      and d.get('攻擊型') == '是'
                                      and res['formula'] not in (38, 42, 65))
            res['es_aoe'] = res['es_terreno'] or res['es_self_aoe'] or res['es_aoe_objetivo']

            # Dimension Shift I..V (13595..13599, formula 7 con hijo 13600..13604 en 動態參數1):
            # hereda el radio (5) y el dano magico del sub-hechizo de impacto.
            if 13595 <= magic_id <= 13599:
                _sub_ds = _num(d.get('動態參數1'), 0)
                _d_sub = _magic_xml().get(_sub_ds) or {}
                if _d_sub:
                    res['area'] = max(res['area'], _num(_d_sub.get('範圍'), 5))
                    res['dano_base'] = _num(_d_sub.get('平均傷害'), res['dano_base'])
                    res['dano_var'] = _num(_d_sub.get('傷害變數'), res['dano_var'])
                    res['dano_coef'] = _num(_d_sub.get('傷害係數'), res['dano_coef'])
                    res['base_denom'] = _num(_d_sub.get('高權位'), res['base_denom']) or 200
                    res['sub_efecto'] = _num(_d_sub.get('特效編號'), 519)

            # Ember Brand I..V (13841..13845) & Holy Brand I..V (15241..15245) - Formula 65:
            # Fase 1: golpe individual (狀態參數: 13846..13850 / 15246..15250) + marca DoT (動態參數1: 13976..13980 / 15251..15255)
            # Fase 2 (si el enemigo ya tiene la marca activa): consume la marca y detona AOE (動態參數2: 14036..14040 / 15256..15260)
            if (res['formula'] == 65 and d.get('攻擊型') == '是') or (13841 <= magic_id <= 13845) or (15241 <= magic_id <= 15245):
                res['es_brand'] = True
                _b_hit = _num(d.get('狀態參數'), 0)
                _b_dot = _num(d.get('動態參數1'), 0)
                _b_aoe = _num(d.get('動態參數2'), 0)
                res['brand_hit_id'] = _b_hit
                res['brand_dot_id'] = _b_dot
                res['brand_aoe_id'] = _b_aoe
                _d_hit = _magic_xml().get(_b_hit) or {}
                if _d_hit:
                    res['dano_base'] = _num(_d_hit.get('平均傷害'), res['dano_base'])
                    res['dano_var'] = _num(_d_hit.get('傷害變數'), res['dano_var'])
                    res['dano_coef'] = _num(_d_hit.get('傷害係數'), res['dano_coef'])
                    res['base_denom'] = _num(_d_hit.get('高權位'), res['base_denom']) or 200
                    res['efecto'] = _num(_d_hit.get('特效編號'), res['efecto'])

            # Formula 65 tambien selecciona BUFFS al reutilizar (Meditate).
            # No son marcas ofensivas ni una recuperacion completa de mana.
            if res['formula'] == 65 and target == '自己' and d.get('攻擊型') != '是':
                res['reuso_base_id'] = _num(d.get('動態參數1'), 0)
                res['reuso_extra_id'] = _num(d.get('動態參數2'), 0)
                res['reuso_prob'] = max(0, min(100, _num(d.get('動態參數3'), 100)))

            # Deteccion de invocaciones (Summon Skeleton, Summon Mummy, Ghostly Swordsman, etc.)
            res['invoca_npc'] = _num(d.get('動態參數1'), 0)
            dur_inv = _num(d.get('動態參數2'), 0)
            res['dur_invoca'] = dur_inv if dur_inv > 0 else 3600
            # 'titan' ESTABA EN ESTA LISTA y no invocaba nada: se comia los
            # Titan Rage I-V, el Titan Tenacity y los Titan Rumble I-V, que
            # son auto-buffs de 10 minutos y 5 minutos. Marcados como
            # invocacion no llegaban a es_buff, asi que ni duraban ni
            # ponian su icono en la barra. De los 153 hechizos que llevan
            # 召喚型=是 ni uno se llama "titan": la palabra solo hacia dano.
            #
            # Y como red de seguridad, el 魔法狀態: un hechizo que declara
            # estado magico (魔法還擊 = devolver el golpe, por ejemplo) es un
            # buff, no una invocacion. Ninguna de las 153 invocaciones de
            # verdad trae ese campo, asi que no se pierde ninguna.
            is_real_summon = (
                d.get('召喚型') == '是' or
                any(nom_l.startswith(k) for k in ('summon ', 'lvl 60 summon', 'lvl 90 summon', 'lvl 120 summon')) or
                any(k in nom_l for k in ('ghostly swordsman', 'shadow clone', 'avatar', 'putridox', 'minotaur', 'leech', 'azrael', 'muncher', 'totem', '1otem'))
            ) and not d.get('魔法狀態') and not ('soul shield' in nom_l) and not res.get('es_brand') and not (13595 <= magic_id <= 13599) and (d.get('變身型') != '是') and not ('shift' in nom_l and target == '自己')
            res['es_invocacion'] = bool(res['invoca_npc'] > 0 and is_real_summon)
            # Formula29 is Avatar, not a self-buff. Parameter2 is clone power,
            # NOT summon lifetime; lifetime comes from duration like the tooltip.
            res['es_clon'] = res['formula']==29 and res['invoca_npc'] in (6269,6270)
            if res['es_clon']:
                res['es_invocacion'] = True
                res['clon_sustituto'] = res['invoca_npc']==6269
                res['clon_poder'] = _num(d.get('動態參數2'),0)
                res['dur_invoca'] = max(1,res['dur_ms']//1000)

            # Robos de HP y MP (Forbidden Curse / Formula 39 y Bloodthirst Arrow / Formula 24)
            if res['formula'] in (24, 39) or (5116 <= magic_id <= 5120) or ('forbidden curse' in nom_l) or ('bloodthirst arrow' in nom_l):
                res['drain_hp_pct'] = _num(d.get('動態參數2'), 30 if res['formula'] == 24 else 25)
                if res['formula'] == 24 or ('bloodthirst arrow' in nom_l):
                    res['drain_hp_prob'] = _num(d.get('動態參數1'), 80)
                else:
                    res['drain_mp_pct'] = _num(d.get('動態參數3'), 3)

            # RECUPERAR AL MATAR (Gnash y compania).
            #
            # No es el robo de Forbidden Curse: aquel saca un porcentaje del
            # DAÑO en cada golpe, y este solo devuelve algo SI EL GOLPE MATA.
            # Lo dice la propia descripcion: "If the attack kills the target,
            # the caster will recover some HP and MP".
            #
            # No vale la formula para reconocerlos -- Gnash es formula 5 y esa
            # la comparten 89 hechizos -- asi que se mira la descripcion, que
            # es lo unico que los separa. Son trece en total: los cinco Gnash,
            # dos Energy Flower, los cinco Skeletal Resurrection y el Wrath of
            # the Harmful Wind.
            #
            # Los porcentajes son 動態參數1 (HP) y 動態參數2 (MP), sobre el
            # MAXIMO del que lanza, no sobre el daño: Gnash I-IV dan 10 y 10,
            # y el V 15 y 15, que es justo lo que dice la wiki.
            #
            # Los Skeletal Resurrection llevan en 動態參數2 un ID DE HECHIZO
            # (16767 y siguientes), no un porcentaje, asi que se descartan los
            # valores que no parezcan tanto por ciento.
            if 'kills the target' in str(d.get('說明') or ''):
                _p1 = _num(d.get('動態參數1'), 0)
                _p2 = _num(d.get('動態參數2'), 0)
                if 0 < _p1 <= 100:
                    res['al_matar_hp_pct'] = _p1
                if 0 < _p2 <= 100:
                    res['al_matar_mp_pct'] = _p2

            # Saltos de rebote (Chain Lightning / Formula 42)
            if res['formula'] == 42 or (5226 <= magic_id <= 5230) or ('chain lightning' in nom_l):
                res['chain_jumps'] = _num(d.get('動態參數1'), 5)
                res['sub_spell'] = _num(d.get('轉嫁法術'), 0)

            if res['es_invocacion']:
                res['es_terreno'] = False
                res['es_self_aoe'] = False
                res['es_aoe'] = False

            # Wolf Spirit (Formula 38): Sacrifica un monstruo y otorga forma Wolf Spirit y bonos
            if res['formula'] == 38 or (16669 <= magic_id <= 16673):
                res['es_wolf_spirit'] = True
                res['es_ataque'] = False
                res['sub_buff_phys'] = _num(d.get('動態參數1'), 16792)
                res['sub_buff_spell'] = _num(d.get('動態參數2'), 16797)

            # Hechizo de encanto / control de monstruos (Shining Charm I..V, Creature Charm, etc.)
            # OJO: usar _palabra('charm', nom_l) para no confundir "Charming Blessing" con un hechizo de encanto!
            res['es_encanto'] = (d.get('魔法狀態') == '媚惑' or (_palabra('charm', nom_l) and 'lava charm' not in nom_l)) and not res['es_invocacion']

            # Hechizo de panico / miedo (Soul Entangle I..V, Crazy Roar I..XXVII, etc.)
            res['es_panico'] = (not res['es_invocacion']) and (
                d.get('魔法狀態') in ('恐懼', '恐慌') or
                'frighten' in desc_l or
                'fear' in desc_l or
                'panic' in desc_l
            )

            # Hechizo de transformacion / shapeshift (Wolf Shift, Bear Shift, Unicorn Shift, Shark Shift, etc.)
            res['es_transformacion'] = (not res['es_invocacion']) and (
                d.get('變身型') == '是' or
                ('shift' in nom_l and target == '自己')
            )
            if res['es_transformacion']:
                res['invoca_npc'] = 0
                res['es_invocacion'] = False

            res['trans_sprite'] = _num(d.get('動態參數1'), 0)
            res['def_bonus'] = _num(d.get('防禦力') or d.get('防禦') or d.get('def'), 0)
            res['atk_bonus'] = _num(d.get('攻擊力') or d.get('攻擊') or d.get('atk'), 0)
            res['matk_bonus'] = _num(d.get('matk') or d.get('magic_attack') or d.get('魔攻'), 0)
            res['mdef_bonus'] = _num(d.get('mdef') or d.get('magic_defend') or d.get('魔防'), 0)
            res['hit_bonus'] = _num(d.get('hit') or d.get('精準'), 0)
            res['eva_bonus'] = _num(d.get('dodge') or d.get('靈敏'), 0)
            res['move_speed_bonus'] = _num(d.get('move_speed') or d.get('移動速度'), 0)
            res['atk_speed_bonus'] = _num(d.get('atk_speed') or d.get('攻擊速度'), 0)
            res['crit_rate'] = _num(d.get('重擊機率') or d.get('爆擊率') or d.get('crit_rate'), 0)
            res['res_body'] = _num(d.get('res_body') or d.get('體質抵抗'), 0)
            res['res_mind'] = _num(d.get('res_mind') or d.get('心靈抵抗'), 0)
            res['res_elec'] = _num(d.get('res_lightning') or d.get('雷電防禦'), 0)
            res['res_fire'] = _num(d.get('res_fire') or d.get('火焰防禦'), 0)
            res['res_ice'] = _num(d.get('res_ice') or d.get('寒冰防禦'), 0)
            res['res_poison'] = _num(d.get('res_corrosion') or d.get('腐蝕防禦'), 0)
            res['atk_elec'] = _num(d.get('雷電攻擊'), 0)
            res['prob_elec'] = _num(d.get('雷電機率'), 0)
            res['atk_fire'] = _num(d.get('火焰攻擊'), 0)
            res['prob_fire'] = _num(d.get('火焰機率'), 0)
            res['atk_ice'] = _num(d.get('寒冰攻擊'), 0)
            res['prob_ice'] = _num(d.get('寒冰機率'), 0)
            res['atk_poison'] = _num(d.get('腐蝕攻擊'), 0)
            res['prob_poison'] = _num(d.get('腐蝕機率'), 0)
            res['tipo_cuerpo'] = (d.get('體質型') == '是')
            res['tipo_mente'] = (d.get('心靈型') == '是')
            # Definicion de HP / MP:
            #   '最大值'       -> bono plano a Max HP / Max MP (hp_bonus / mp_bonus)
            #   '最大值百分比' -> bono porcentual a Max HP / Max MP (hp_pct / mp_pct)
            #   '數值'         -> curacion / regeneracion por tick (NO sube el tope!)
            hp_def = str(d.get('HP定義') or '')
            mp_def = str(d.get('MP定義') or '')
            raw_hp_val = _num(d.get('hp') if d.get('hp') is not None else d.get('HP'), 0)
            raw_mp_val = _num(d.get('mp') if d.get('mp') is not None else d.get('MP'), 0)
            res['hp_bonus'] = raw_hp_val if hp_def == '最大值' else 0
            res['mp_bonus'] = raw_mp_val if mp_def == '最大值' else 0
            if '百分比' in hp_def or hp_def == '最大值百分比':
                res['hp_pct'] = raw_hp_val

            if res['es_transformacion']:
                res['es_melee_trans'] = (d.get('魔法狀態') == '近戰化' or 'shark' in nom_l)
                if res['es_melee_trans']:
                    res['matk_pct'] = _num(d.get('matk') or d.get('magic_attack') or d.get('魔攻'), 0)
                    res['mdef_pct'] = _num(d.get('mdef') or d.get('magic_defend') or d.get('魔防'), 0)
                    res['atk_pct'] = _num(d.get('atk') or d.get('攻擊力') or d.get('攻擊'), 0)
                    res['def_pct'] = _num(d.get('def') or d.get('防禦力') or d.get('防禦'), 0)
                else:
                    res['matk_pct'] = 0
                    res['mdef_pct'] = 0
                    res['atk_pct'] = 0
                    res['def_pct'] = 0

            if '百分比' in mp_def or mp_def == '最大值百分比':
                if res.get('es_transformacion') and res.get('es_melee_trans'):
                    res['mp_to_hp_pct'] = raw_mp_val
                else:
                    res['mp_pct'] = raw_mp_val

            # Auras de equipo (範圍效果光環 == '是', ej. Merlin's Circle, Guardian's Circle, Sacred Circle):
            # heredan sus bonos de stats del sub-hechizo indicado en 動態參數1.
            if d.get('範圍效果光環') == '是':
                _aura_sub_id = _num(d.get('動態參數1'), 0)
                _d_aura = _magic_xml().get(_aura_sub_id) or {}
                if _d_aura:
                    res['def_bonus'] = res['def_bonus'] or _num(_d_aura.get('防禦力') or _d_aura.get('防禦') or _d_aura.get('def'), 0)
                    res['atk_bonus'] = res['atk_bonus'] or _num(_d_aura.get('攻擊力') or _d_aura.get('攻擊') or _d_aura.get('atk'), 0)
                    res['matk_bonus'] = res['matk_bonus'] or _num(_d_aura.get('魔攻') or _d_aura.get('matk'), 0)
                    res['mdef_bonus'] = res['mdef_bonus'] or _num(_d_aura.get('魔防') or _d_aura.get('mdef'), 0)
                    res['hit_bonus'] = res['hit_bonus'] or _num(_d_aura.get('精準') or _d_aura.get('hit'), 0)
                    res['eva_bonus'] = res['eva_bonus'] or _num(_d_aura.get('靈敏') or _d_aura.get('dodge'), 0)
                    res['crit_rate'] = res['crit_rate'] or _num(_d_aura.get('爆擊率') or _d_aura.get('重擊機率'), 0)
                    res['phys_mit'] = res['phys_mit'] or _num(_d_aura.get('物理傷害抵銷'), 0)
                    res['mag_mit'] = res['mag_mit'] or _num(_d_aura.get('魔法傷害抵銷'), 0)
                    if str(_d_aura.get('HP定義') or '') == '最大值' and not res['hp_bonus']:
                        res['hp_bonus'] = _num(_d_aura.get('HP'), 0)
                    if str(_d_aura.get('MP定義') or '') == '最大值' and not res['mp_bonus']:
                        res['mp_bonus'] = _num(_d_aura.get('MP'), 0)

            _es_cast_redux_skill = (
                'casting time' in desc_l or 'cast time' in desc_l or
                any(k in nom_l for k in ('limit breaker', 'shadow meld', 'first path', 'third spirit', 'killer intent'))
            )
            res['cast_redux'] = _num(d.get('動態參數3'), 0) if _es_cast_redux_skill else 0
            if not res['cast_redux'] and 'limit breaker' in nom_l:
                lb_ranks = {'limit breaker i': 500, 'limit breaker ii': 600, 'limit breaker iii': 700, 'limit breaker iv': 800, 'limit breaker v': 1000}
                for k, v in lb_ranks.items():
                    if k in nom_l:
                        res['cast_redux'] = v
                        break

            res['atk_mod'] = _num(d.get('atk') or d.get('攻擊力') or d.get('攻擊'), 0)
            res['def_mod'] = _num(d.get('def') or d.get('防禦力') or d.get('防禦'), 0)
            res['matk_mod'] = _num(d.get('matk') or d.get('魔攻'), 0)
            res['mdef_mod'] = _num(d.get('mdef') or d.get('魔防'), 0)
            res['phys_dmg_pct'] = _num(d.get('物理傷害') or (_d_aura.get('物理傷害') if d.get('範圍效果光環') == '是' and _d_aura else 0), 0)
            res['mag_dmg_pct'] = _num(d.get('魔法傷害') or (_d_aura.get('魔法傷害') if d.get('範圍效果光環') == '是' and _d_aura else 0), 0)
            res['phys_mit_pct'] = _num(d.get('物理傷害抵銷') or (_d_aura.get('物理傷害抵銷') if d.get('範圍效果光環') == '是' and _d_aura else 0), 0)
            res['mag_mit_pct'] = _num(d.get('魔法傷害抵銷') or (_d_aura.get('魔法傷害抵銷') if d.get('範圍效果光環') == '是' and _d_aura else 0), 0)
            res['vel_mov_mod'] = _num(d.get('move_speed') or d.get('移動速度'), 0)

            # Buffs con triggers / procs al atacar o al recibir dano:
            # 1) Formulas 53, 54, 61, 62 (Blazing Sun, Mana Overflow, Spell Boost, Witch Ward, Brainjack,
            #    Flowing Water, Drifting Clouds, Tiger Arts, Twincore Blades, Mind's Eye, Blade Field,
            #    Sparrow, Owl, Eagle, Roc, Fighting Stance, Nimble Hands, Winged Accuracy, Guardian Shell, etc.)
            if res['formula'] in (53, 54, 61, 62):
                _ps = _num(d.get('動態參數1'), 0)
                _p2 = _num(d.get('動態參數2'), 25)
                _p3 = _num(d.get('動態參數3'), 10)
                _m_tr = re.search(r'(\d+)\s*(?:times|triggers)', desc_l)
                _max_u = int(_m_tr.group(1)) if _m_tr else (_p3 if _p3 > 0 else 10)
                _prob = max(25, _p2 if 0 < _p2 <= 100 else 30)
                if _ps > 0:
                    res['proc_spell'] = _ps
                    res['proc_prob'] = _prob
                    res['proc_max_uses'] = _max_u
                    res['proc_on_attack'] = True
                    res['proc_on_hit'] = True
            # 2) Formulas 47 y 48 activables (Erosion, Lava Charm, Blood Bond, Maim Shot, Osmose Arrow,
            #    Spearheart, Solar Power, Sage Slash, Colossal Might)
            elif res['formula'] in (47, 48) and res['dur_ms'] > 0:
                _ps = _num(d.get('動態參數2'), 0)
                _p1 = _num(d.get('動態參數1'), 30)
                _prob = 35 if (_p1 >= 100 and 'chance' in desc_l) else max(25, min(100, _p1 if _p1 > 0 else 30))
                if _ps > 0:
                    res['proc_spell'] = _ps
                    res['proc_prob'] = _prob
                    res['proc_max_uses'] = 0
                    res['proc_on_attack'] = True
                    res['proc_on_hit'] = True
            # 3) Estado '魔法還擊' (Fire Gathering, Punishing Shield, Spine Shell, Hell Shield, Energy Roar,
            #    Holy Prayer, Spirit's Blessing, Spiritual Energy, Soul Corral, Titan Rage, Life Vine,
            #    Cross Slash, Arrow Gravity, Raijin's Protection, Lotus Armor, Spike Shield, Divine Attend,
            #    Spike Armor, Passion Warcry, Arrow Wind, Mana Flow, Holy Guard, Titan Rumble, Wild Strike,
            #    Tactician's Return, Wrath Armor, Arrow Guard, Barbed Armor)
            elif d.get('魔法狀態') == '魔法還擊':
                _ps = _num(d.get('動態參數2'), 0)
                _max_u = _num(d.get('動態參數1'), 10)
                _prob = max(25, _num(d.get('動態參數3'), 30))
                if _ps > 0:
                    res['proc_spell'] = _ps
                    res['proc_prob'] = _prob
                    res['proc_max_uses'] = _max_u
                    res['proc_on_hit'] = True
                    res['proc_on_attack'] = False
            # 4) Estados '機率持續扣血' y '爆擊轉嫁' (Debilitating Thrust, Sniper Shot)
            elif d.get('魔法狀態') in ('機率持續扣血', '爆擊轉嫁'):
                _ps = _num(d.get('動態參數1'), 0)
                _prob = max(25, _num(d.get('動態參數2'), 30))
                if _ps > 0:
                    res['proc_spell'] = _ps
                    res['proc_prob'] = _prob
                    res['proc_max_uses'] = 0
                    res['proc_on_attack'] = True
                    res['proc_on_hit'] = False

            # Hechizo de debuff / maldicion a enemigos (Exhaustion Curse, Weak Curse, Blind Curse, Slow Curse, Tough Break, etc.)
            res['es_debuff'] = (not res['es_invocacion']) and (not res['es_encanto']) and (not res['es_panico']) and (not res.get('es_brand')) and (
                res['dur_ms'] > 0 and target != '自己' and (
                    res['atk_mod'] < 0 or
                    res['def_mod'] < 0 or
                    res['matk_mod'] < 0 or
                    res['mdef_mod'] < 0 or
                    res['phys_dmg_pct'] < 0 or
                    res['mag_dmg_pct'] < 0 or
                    res['phys_mit_pct'] < 0 or
                    res['mag_mit_pct'] < 0 or
                    res['vel_mov_mod'] < 0 or
                    'curse' in nom_l or
                    'melody' in nom_l or
                    d.get('魔法狀態') in ('閃紫色', '閃黃色', '暗灰色')
                )
            )

            # Curacion directa solo si es un hechizo curativo real (ej. Cure Spell, Holy Light, Angel Prayer, Tears of Life, Mighty Cure)
            res['es_cura'] = (not res['es_invocacion']) and (not res['es_encanto']) and (not res['es_panico']) and (not res['es_debuff']) and (not res.get('es_brand')) and (
                any(k in nom_l for k in ('cure spell', 'mighty cure', 'holy light', 'angel prayer', 'tears of life', "angel's tears")) or
                ('restores hp' in desc_l and 'speed' not in desc_l and 'injury' not in nom_l and 'song' not in nom_l)
            ) and d.get('攻擊型') != '是'

            # RECUPERACION INSTANTANEA DENTRO DE UN BUFF. Soul Discharge V es un
            # buff de 0 ms -- y con SU animacion, que es la buena -- que ademas
            # suma vida y mana al momento: "Recovers your HP and MP", hp 15000
            # y mp 12000 en VALOR FIJO (HP定義/MP定義 = 數值). Se probo pasarla
            # por el camino de las curas y recuperaba, pero con la animacion de
            # Cure Spell en vez de la suya. Asi que se queda como buff y app.py
            # aplica estos dos valores al ejecutarlo.
            # El MP va en 'mp_cura' y no en 'mp', que en este diccionario es lo
            # que CUESTA el hechizo (消耗MP).
            _instant = (target == '自己' and res['dur_ms'] == 0
                        and d.get('攻擊型') != '是' and not res['es_cura'])
            res['hp_cura_buff'] = (max(0, res['hp']) if _instant
                                   and d.get('HP定義') == '數值' else 0)
            res['mp_cura'] = (max(0, _num(d.get('mp'), 0)) if _instant
                              and d.get('MP定義') == '數值' else 0)

            # Buff temporal (aumenta defensa, velocidad, critico, % reduccion de dano, etc.)
            res['es_buff'] = (not res['es_invocacion']) and (not res['es_encanto']) and (not res['es_panico']) and (not res['es_debuff']) and (not res.get('es_brand')) and (
                res['dur_ms'] > 0 or
                target == '自己' or
                res['es_transformacion'] or
                res['crit_rate'] > 0 or
                res['phys_mit'] > 0 or
                ('within the effective time' in desc_l or 'increase' in desc_l or 'raises' in desc_l or 'enhances' in desc_l)
            ) and not (d.get('攻擊型') == '是' or _palabra('harm', desc_l)) and not res['es_cura']

            # Habilidad ofensiva de ataque (dano a enemigo, estun, etc.)
            res['es_ataque'] = (not res['es_invocacion']) and (not res['es_encanto']) and (not res['es_panico']) and (not res['es_debuff']) and (not res['es_cura']) and (not res['es_buff']) and (
                bool(res.get('es_brand')) or
                d.get('攻擊型') == '是' or
                any(k in desc_l for k in ('attack', 'attacks', 'harm', 'laceration', 'damage', 'shoot', 'strike', 'repulse', 'stun', 'pierce')) or
                any(k in nom_l for k in ('hit', 'attack', 'chop', 'beating', 'slash', 'wave', 'bomb', 'shot', 'thrust', 'strike', 'killing', 'brand'))
            )

            # Se puede usar sobre uno mismo si es curacion, buff, invocacion o self-aoe
            res['es_auto'] = res['es_cura'] or res['es_buff'] or res['es_invocacion'] or res['es_self_aoe']

            # La regla del nombre es para las ramas pasivas (Enhance, Grapple,
            # Reserve...), pero cogia tambien a "Mad ENHANCEment V", que es un
            # buff de 30 s: se marcaba pasiva, no se ejecutaba al pulsarla y
            # solo se apuntaba su enfriamiento. Algo con DURACION no es pasivo.
            res['es_pasiva'] = (not res['es_invocacion']) and (
                d.get('被動') == '是' or
                (act in ('無動作', '', 'None') and not res['es_ataque'] and not res['es_cura'] and not res['es_auto']) or
                (res['dur_ms'] <= 0 and
                 any(k in nom_l for k in ('enhance', 'grapple', 'reserve', 'finesse', 'garment', 'mastery')))
            )
            # Resolucion de subhechizo delegado para habilidades de combate de alto rango (TNT Arrow, Aparctias Shot, Steel Rain, etc.)
            sub_id = encontrar_sub_combate(magic_id, d, _magic_xml())
            if sub_id and sub_id != magic_id and sub_id in _magic_xml():
                res['sub_spell'] = sub_id
                sub_d = _magic_xml()[sub_id]
                sub_hp = _num(sub_d.get('hp') if sub_d.get('hp') is not None else sub_d.get('HP'), 0)
                if not res.get('hp') and sub_hp:
                    res['hp'] = sub_hp
                sub_area = _num(sub_d.get('影響範圍') or sub_d.get('範圍'), 0)
                if not res.get('area') and sub_area:
                    res['area'] = sub_area
                    res['es_aoe'] = True
                if not res.get('dano_base'):
                    sub_dano = _num(sub_d.get('平均傷害'), 0)
                    if sub_dano:
                        res['dano_base'] = sub_dano
        except Exception:
            pass
    _MAGIC_CACHE[magic_id] = res
    return res


# Stats oficiales extraidos directamente de monster.xml (update26/setting/eng/monster.xml)
STATS_INVOCACIONES_XML = {
    # Death's Head 1..5 (NPC 210..214) - Sprite 42142, sin habilidades activas
    210: {'nombre': "Death's Head 1", 'sprite': 42142, 'level': 4, 'hp': 162, 'atk': 54, 'def': 41, 'matk': 110, 'mdef': 21, 'accuracy': 32, 'agility': 24, 'move_speed': 70, 'atk_speed': 70, 'atk_range': 1, 'crit_rate': 5, 'skills': []},
    211: {'nombre': "Death's Head 2", 'sprite': 42142, 'level': 7, 'hp': 300, 'atk': 69, 'def': 59, 'matk': 110, 'mdef': 32, 'accuracy': 47, 'agility': 33, 'move_speed': 70, 'atk_speed': 70, 'atk_range': 1, 'crit_rate': 5, 'skills': []},
    212: {'nombre': "Death's Head 3", 'sprite': 42142, 'level': 13, 'hp': 458, 'atk': 102, 'def': 97, 'matk': 110, 'mdef': 55, 'accuracy': 77, 'agility': 51, 'move_speed': 70, 'atk_speed': 70, 'atk_range': 1, 'crit_rate': 5, 'skills': []},
    213: {'nombre': "Death's Head 4", 'sprite': 42142, 'level': 19, 'hp': 635, 'atk': 138, 'def': 139, 'matk': 110, 'mdef': 78, 'accuracy': 107, 'agility': 69, 'move_speed': 70, 'atk_speed': 70, 'atk_range': 1, 'crit_rate': 5, 'skills': []},
    214: {'nombre': "Death's Head 5", 'sprite': 42142, 'level': 25, 'hp': 1484, 'atk': 300, 'def': 331, 'matk': 150, 'mdef': 181, 'accuracy': 242, 'agility': 150, 'move_speed': 80, 'atk_speed': 80, 'atk_range': 1, 'crit_rate': 10, 'skills': []},
    # Death Mummy 1..5 (NPC 215..219) - Sprite 42143, sin habilidades activas
    215: {'nombre': 'Death Mummy 1', 'sprite': 42143, 'level': 27, 'hp': 888, 'atk': 164, 'def': 242, 'matk': 177, 'mdef': 109, 'accuracy': 147, 'agility': 93, 'move_speed': 75, 'atk_speed': 80, 'atk_range': 1, 'crit_rate': 5, 'skills': []},
    216: {'nombre': 'Death Mummy 2', 'sprite': 42143, 'level': 33, 'hp': 1091, 'atk': 205, 'def': 306, 'matk': 177, 'mdef': 132, 'accuracy': 177, 'agility': 111, 'move_speed': 80, 'atk_speed': 80, 'atk_range': 1, 'crit_rate': 5, 'skills': []},
    217: {'nombre': 'Death Mummy 3', 'sprite': 42143, 'level': 39, 'hp': 1303, 'atk': 249, 'def': 378, 'matk': 177, 'mdef': 155, 'accuracy': 207, 'agility': 129, 'move_speed': 80, 'atk_speed': 80, 'atk_range': 1, 'crit_rate': 5, 'skills': []},
    218: {'nombre': 'Death Mummy 4', 'sprite': 42143, 'level': 45, 'hp': 1523, 'atk': 297, 'def': 457, 'matk': 177, 'mdef': 178, 'accuracy': 237, 'agility': 147, 'move_speed': 80, 'atk_speed': 80, 'atk_range': 1, 'crit_rate': 5, 'skills': []},
    219: {'nombre': 'Death Mummy 5', 'sprite': 42143, 'level': 51, 'hp': 2616, 'atk': 536, 'def': 846, 'matk': 237, 'mdef': 293, 'accuracy': 387, 'agility': 237, 'move_speed': 95, 'atk_speed': 90, 'atk_range': 1, 'crit_rate': 10, 'skills': []},
    # Death Leech 1..5 (NPC 220..225) - Sprite 42144, habilidades [2062..2066]
    220: {'nombre': 'Death Leech 1', 'sprite': 42144, 'level': 53, 'hp': 1830, 'atk': 418, 'def': 477, 'matk': 356, 'mdef': 209, 'accuracy': 277, 'agility': 171, 'move_speed': 85, 'atk_speed': 70, 'atk_range': 1, 'crit_rate': 5, 'skills': [2062]},
    221: {'nombre': 'Death Leech 2', 'sprite': 42144, 'level': 59, 'hp': 2068, 'atk': 485, 'def': 558, 'matk': 402, 'mdef': 232, 'accuracy': 307, 'agility': 189, 'move_speed': 85, 'atk_speed': 70, 'atk_range': 1, 'crit_rate': 5, 'skills': [2063]},
    222: {'nombre': 'Death Leech 3', 'sprite': 42144, 'level': 65, 'hp': 2313, 'atk': 558, 'def': 649, 'matk': 449, 'mdef': 255, 'accuracy': 337, 'agility': 207, 'move_speed': 90, 'atk_speed': 70, 'atk_range': 1, 'crit_rate': 5, 'skills': [2064]},
    223: {'nombre': 'Death Leech 4', 'sprite': 42144, 'level': 71, 'hp': 2566, 'atk': 639, 'def': 749, 'matk': 496, 'mdef': 278, 'accuracy': 367, 'agility': 225, 'move_speed': 90, 'atk_speed': 70, 'atk_range': 1, 'crit_rate': 5, 'skills': [2065]},
    225: {'nombre': 'Death Leech 5', 'sprite': 42144, 'level': 77, 'hp': 3818, 'atk': 1036, 'def': 1243, 'matk': 730, 'mdef': 393, 'accuracy': 517, 'agility': 315, 'move_speed': 105, 'atk_speed': 80, 'atk_range': 3, 'crit_rate': 10, 'skills': [2066]},
    # Azrael 1..5 (NPC 226..230) - Sprite 42145, habilidades [2067..2071]
    226: {'nombre': 'Azrael 1', 'sprite': 42145, 'level': 79, 'hp': 2912, 'atk': 722, 'def': 899, 'matk': 558, 'mdef': 309, 'accuracy': 391, 'agility': 249, 'move_speed': 90, 'atk_speed': 80, 'atk_range': 3, 'crit_rate': 15, 'skills': [2067]},
    227: {'nombre': 'Azrael 2', 'sprite': 42145, 'level': 85, 'hp': 3179, 'atk': 819, 'def': 1025, 'matk': 606, 'mdef': 332, 'accuracy': 420, 'agility': 267, 'move_speed': 90, 'atk_speed': 80, 'atk_range': 3, 'crit_rate': 15, 'skills': [2068]},
    228: {'nombre': 'Azrael 3', 'sprite': 42145, 'level': 91, 'hp': 3452, 'atk': 925, 'def': 1165, 'matk': 654, 'mdef': 355, 'accuracy': 448, 'agility': 285, 'move_speed': 90, 'atk_speed': 80, 'atk_range': 3, 'crit_rate': 15, 'skills': [2069]},
    229: {'nombre': 'Azrael 4', 'sprite': 42145, 'level': 97, 'hp': 3731, 'atk': 1041, 'def': 1319, 'matk': 702, 'mdef': 378, 'accuracy': 477, 'agility': 303, 'move_speed': 90, 'atk_speed': 80, 'atk_range': 3, 'crit_rate': 15, 'skills': [2070]},
    230: {'nombre': 'Azrael 5', 'sprite': 42145, 'level': 103, 'hp': 5120, 'atk': 1720, 'def': 2073, 'matk': 942, 'mdef': 477, 'accuracy': 623, 'agility': 393, 'move_speed': 110, 'atk_speed': 90, 'atk_range': 3, 'crit_rate': 20, 'skills': [2071]},
    # Soul Eater 1..5 (NPC 5014..5018) - Sprite 42732, habilidades [3291..3295]
    5014: {'nombre': 'Soul Eater 1', 'sprite': 42732, 'level': 103, 'hp': 22535, 'atk': 837, 'def': 1813, 'matk': 669, 'mdef': 665, 'accuracy': 527, 'agility': 321, 'move_speed': 125, 'atk_speed': 70, 'atk_range': 1, 'crit_rate': 5, 'skills': [3291]},
    5015: {'nombre': 'Soul Eater 2', 'sprite': 42732, 'level': 115, 'hp': 25185, 'atk': 1101, 'def': 2459, 'matk': 898, 'mdef': 755, 'accuracy': 587, 'agility': 357, 'move_speed': 125, 'atk_speed': 70, 'atk_range': 1, 'crit_rate': 5, 'skills': [3292]},
    5016: {'nombre': 'Soul Eater 3', 'sprite': 42732, 'level': 127, 'hp': 28300, 'atk': 1325, 'def': 2974, 'matk': 1060, 'mdef': 1120, 'accuracy': 648, 'agility': 393, 'move_speed': 125, 'atk_speed': 70, 'atk_range': 1, 'crit_rate': 5, 'skills': [3293]},
    5017: {'nombre': 'Soul Eater 4', 'sprite': 42732, 'level': 139, 'hp': 31415, 'atk': 1549, 'def': 3489, 'matk': 1222, 'mdef': 1234, 'accuracy': 709, 'agility': 429, 'move_speed': 125, 'atk_speed': 70, 'atk_range': 1, 'crit_rate': 5, 'skills': [3294]},
    5018: {'nombre': 'Soul Eater 5', 'sprite': 42732, 'level': 151, 'hp': 47211, 'atk': 2785, 'def': 6373, 'matk': 2149, 'mdef': 1834, 'accuracy': 1025, 'agility': 615, 'move_speed': 135, 'atk_speed': 80, 'atk_range': 1, 'crit_rate': 10, 'skills': [3295]},
    # Demon 1..5 (NPC 7875..7879) - Sprite 43157, ataque basico
    7875: {'nombre': 'Demon 1', 'sprite': 43157, 'level': 126, 'hp': 45000, 'atk': 3600, 'def': 4200, 'matk': 1650, 'mdef': 2950, 'accuracy': 1040, 'agility': 635, 'move_speed': 110, 'atk_speed': 120, 'atk_range': 2, 'crit_rate': 5, 'skills': []},
    7876: {'nombre': 'Demon 2', 'sprite': 43157, 'level': 134, 'hp': 52000, 'atk': 4000, 'def': 5400, 'matk': 1760, 'mdef': 3150, 'accuracy': 1100, 'agility': 670, 'move_speed': 110, 'atk_speed': 120, 'atk_range': 2, 'crit_rate': 5, 'skills': []},
    7877: {'nombre': 'Demon 3', 'sprite': 43157, 'level': 142, 'hp': 58000, 'atk': 4590, 'def': 6100, 'matk': 1860, 'mdef': 3300, 'accuracy': 1160, 'agility': 700, 'move_speed': 110, 'atk_speed': 120, 'atk_range': 2, 'crit_rate': 5, 'skills': []},
    7878: {'nombre': 'Demon 4', 'sprite': 43157, 'level': 150, 'hp': 64000, 'atk': 5160, 'def': 6900, 'matk': 1970, 'mdef': 3470, 'accuracy': 1220, 'agility': 740, 'move_speed': 110, 'atk_speed': 120, 'atk_range': 2, 'crit_rate': 5, 'skills': []},
    7879: {'nombre': 'Demon 5', 'sprite': 43157, 'level': 158, 'hp': 70000, 'atk': 5790, 'def': 7740, 'matk': 2070, 'mdef': 3600, 'accuracy': 1280, 'agility': 780, 'move_speed': 110, 'atk_speed': 120, 'atk_range': 2, 'crit_rate': 5, 'skills': []},
    # Demon Lord (NPC 12553) - Sprite 43163
    12553: {'nombre': 'Demon Lord', 'sprite': 43163, 'level': 192, 'hp': 280000, 'atk': 12000, 'def': 8200, 'matk': 9800, 'mdef': 4100, 'accuracy': 2800, 'agility': 910, 'move_speed': 110, 'atk_speed': 120, 'atk_range': 2, 'crit_rate': 5, 'skills': []},
    # Ghostly Swordsman 1..5 (NPC 17144..17148) - Sprite 43692
    17144: {'nombre': 'Ghostly Swordsman 1', 'sprite': 43692, 'level': 210, 'hp': 411919, 'atk': 18583, 'def': 9298, 'matk': 10026, 'mdef': 5177, 'accuracy': 2560, 'agility': 905, 'move_speed': 100, 'atk_speed': 95, 'atk_range': 2, 'crit_rate': 5, 'skills': []},
    17145: {'nombre': 'Ghostly Swordsman 2', 'sprite': 43692, 'level': 220, 'hp': 470764, 'atk': 21238, 'def': 10626, 'matk': 11458, 'mdef': 5916, 'accuracy': 2926, 'agility': 1034, 'move_speed': 100, 'atk_speed': 95, 'atk_range': 2, 'crit_rate': 5, 'skills': [8342]},
    17146: {'nombre': 'Ghostly Swordsman 3', 'sprite': 43692, 'level': 230, 'hp': 529610, 'atk': 23893, 'def': 11954, 'matk': 12890, 'mdef': 6656, 'accuracy': 3292, 'agility': 1163, 'move_speed': 100, 'atk_speed': 95, 'atk_range': 2, 'crit_rate': 5, 'skills': [8342]},
    17147: {'nombre': 'Ghostly Swordsman 4', 'sprite': 43692, 'level': 240, 'hp': 588456, 'atk': 26548, 'def': 13283, 'matk': 14323, 'mdef': 7396, 'accuracy': 3658, 'agility': 1293, 'move_speed': 100, 'atk_speed': 95, 'atk_range': 2, 'crit_rate': 5, 'skills': [8342, 8343]},
    17148: {'nombre': 'Ghostly Swordsman 5', 'sprite': 43692, 'level': 250, 'hp': 647301, 'atk': 29202, 'def': 14611, 'matk': 15755, 'mdef': 8135, 'accuracy': 4023, 'agility': 1422, 'move_speed': 100, 'atk_speed': 95, 'atk_range': 2, 'crit_rate': 5, 'skills': [8342, 8343]},
    # Putridox 1..5 (NPC 20351..20355) - Sprite 110412
    20351: {'nombre': 'Putridox I', 'sprite': 110412, 'level': 260, 'hp': 1100000, 'atk': 59000, 'def': 40500, 'matk': 37500, 'mdef': 19750, 'accuracy': 6200, 'agility': 3000, 'move_speed': 110, 'atk_speed': 120, 'atk_range': 3, 'crit_rate': 5, 'skills': [8351]},
    20352: {'nombre': 'Putridox II', 'sprite': 110412, 'level': 270, 'hp': 1200000, 'atk': 62000, 'def': 42000, 'matk': 39000, 'mdef': 20500, 'accuracy': 6600, 'agility': 3000, 'move_speed': 110, 'atk_speed': 120, 'atk_range': 3, 'crit_rate': 5, 'skills': [8351]},
    20353: {'nombre': 'Putridox III', 'sprite': 110412, 'level': 280, 'hp': 1300000, 'atk': 65000, 'def': 43500, 'matk': 40500, 'mdef': 21250, 'accuracy': 7000, 'agility': 3000, 'move_speed': 110, 'atk_speed': 120, 'atk_range': 3, 'crit_rate': 5, 'skills': [8351]},
    20354: {'nombre': 'Putridox IV', 'sprite': 110412, 'level': 290, 'hp': 1400000, 'atk': 68000, 'def': 45000, 'matk': 42000, 'mdef': 22000, 'accuracy': 7400, 'agility': 3000, 'move_speed': 110, 'atk_speed': 120, 'atk_range': 3, 'crit_rate': 5, 'skills': [8351, 14252]},
    20355: {'nombre': 'Putridox V', 'sprite': 110412, 'level': 300, 'hp': 1600000, 'atk': 74000, 'def': 48000, 'matk': 45000, 'mdef': 23500, 'accuracy': 8200, 'agility': 3000, 'move_speed': 110, 'atk_speed': 120, 'atk_range': 3, 'crit_rate': 5, 'skills': [8351, 14252]},
    # Minotaur 1..4 (NPC 21938..21941) - Sprite 110953 / 110954
    21938: {'nombre': 'Minotaur I', 'sprite': 110953, 'level': 280, 'hp': 1400000, 'atk': 68000, 'def': 43500, 'matk': 40500, 'mdef': 21250, 'accuracy': 5600, 'agility': 2800, 'move_speed': 80, 'atk_speed': 80, 'atk_range': 2, 'crit_rate': 10, 'skills': [20040]},
    21939: {'nombre': 'Minotaur II', 'sprite': 110953, 'level': 290, 'hp': 1500000, 'atk': 71000, 'def': 45000, 'matk': 42000, 'mdef': 22000, 'accuracy': 5800, 'agility': 2900, 'move_speed': 90, 'atk_speed': 90, 'atk_range': 2, 'crit_rate': 10, 'skills': [20041]},
    21940: {'nombre': 'Minotaur III', 'sprite': 110954, 'level': 300, 'hp': 1600000, 'atk': 74000, 'def': 46500, 'matk': 43500, 'mdef': 22750, 'accuracy': 6000, 'agility': 3000, 'move_speed': 100, 'atk_speed': 100, 'atk_range': 2, 'crit_rate': 10, 'skills': [20042]},
    21941: {'nombre': 'Minotaur IV', 'sprite': 110954, 'level': 310, 'hp': 1700000, 'atk': 77000, 'def': 48000, 'matk': 45000, 'mdef': 23500, 'accuracy': 6200, 'agility': 3100, 'move_speed': 110, 'atk_speed': 110, 'atk_range': 2, 'crit_rate': 10, 'skills': [20043, 20066]},
    # Earth Titan 1..4 (NPC 23528..23531) - Sprite 111388 / 111389
    23528: {'nombre': 'Earth Titan I', 'sprite': 111388, 'level': 310, 'hp': 1700000, 'atk': 77000, 'def': 48000, 'matk': 45000, 'mdef': 23500, 'accuracy': 6200, 'agility': 3100, 'move_speed': 80, 'atk_speed': 80, 'atk_range': 2, 'crit_rate': 10, 'skills': [20064]},
    23529: {'nombre': 'Earth Titan II', 'sprite': 111388, 'level': 320, 'hp': 1800000, 'atk': 80000, 'def': 49500, 'matk': 46500, 'mdef': 24250, 'accuracy': 6400, 'agility': 3200, 'move_speed': 90, 'atk_speed': 90, 'atk_range': 2, 'crit_rate': 10, 'skills': [20065]},
    23530: {'nombre': 'Earth Titan III', 'sprite': 111389, 'level': 330, 'hp': 1900000, 'atk': 83000, 'def': 51000, 'matk': 48000, 'mdef': 25000, 'accuracy': 6600, 'agility': 3300, 'move_speed': 100, 'atk_speed': 100, 'atk_range': 2, 'crit_rate': 10, 'skills': [20066]},
    23531: {'nombre': 'Earth Titan IV', 'sprite': 111389, 'level': 340, 'hp': 2000000, 'atk': 86000, 'def': 52500, 'matk': 49500, 'mdef': 25750, 'accuracy': 6800, 'agility': 3400, 'move_speed': 110, 'atk_speed': 110, 'atk_range': 2, 'crit_rate': 10, 'skills': [20067, 20068]},
}


def datos_invocacion(npc_type: int) -> dict:
    """Obtiene los datos base del monstruo invocado desde la tabla monster."""
    if npc_type in STATS_INVOCACIONES_XML:
        return dict(STATS_INVOCACIONES_XML[npc_type])
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if not db.exists():
        return {'nombre': 'Summon', 'sprite': 42142, 'hp': 200, 'atk': 50, 'def': 30, 'move_speed': 70, 'atk_speed': 70, 'atk_range': 1, 'skills': []}
    try:
        con = sqlite3.connect(db)
        r = con.execute('SELECT name, sprite_id, hp, atk_avg, def, move_speed, atk_speed, atk_range, matk, mdef, level, accuracy, agility, crit_rate, 攻擊法術1, 攻擊法術2 FROM monster WHERE id = ?', (str(npc_type),)).fetchone()
        con.close()
        if r:
            sks = []
            for sk_idx in (14, 15):
                val = r[sk_idx]
                if val is not None and str(val).strip().isdigit() and int(val) > 0:
                    sks.append(int(val))
            nom_raw = str(r[0] or 'Summon')
            # Repair only damaged Big5 pairs. A plain English "V" is
            # already rank5: replacing it with "III" mislabels every Star V.
            for k_b5, k_num in (('\ufffdT', ' I'), ('\ufffdU', ' II'), ('\ufffdV', ' III'), ('\ufffdW', ' IV'), ('\ufffdX', ' V')):
                nom_raw = nom_raw.replace(k_b5, k_num)
            nom_limpio = nom_raw.encode('ascii', 'ignore').decode('ascii').strip() or 'Summon'
            if '1otem' in nom_limpio:
                nom_limpio = nom_limpio.replace('1otem', 'Totem')

            es_totem = 'totem' in nom_limpio.lower()
            spd_mov = 0 if es_totem else int(r[5] or 70)
            rango_atk = max(10, int(r[7] or 1)) if es_totem else int(r[7] or 1)

            return {
                'nombre': nom_limpio,
                'sprite': int(r[1] or 42142),
                'hp': max(50, int(r[2] or 160)),
                'atk': max(10, int(r[3] or 50)),
                'def': max(5, int(r[4] or 20)),
                'move_speed': spd_mov,
                'atk_speed': int(r[6] or 70),
                'atk_range': rango_atk,
                'matk': int(r[8] or 0),
                'mdef': int(r[9] or 0),
                'level': int(r[10] or 1),
                'accuracy': int(r[11] or 50),
                'agility': int(r[12] or 50),
                'crit_rate': int(r[13] or 5),
                'skills': sks,
            }
    except Exception:
        pass
    return {'nombre': 'Summon', 'sprite': 42142, 'hp': 200, 'atk': 50, 'def': 30, 'move_speed': 70, 'atk_speed': 70, 'atk_range': 1, 'matk': 50, 'mdef': 30, 'level': 1, 'crit_rate': 5, 'skills': []}






# --------------------------------------------------------------- 0x0011
# El numero de dano que sale en pantalla. Sin esto el cliente hace el gesto de
# atacar y no muestra nada: el 0x000A y el 0x0013 llevan la cuenta, pero lo
# que el jugador VE viene de aqui.
#
#     +0   U8    efecto visual
#     +1   U8    fase: 0x00 el golpe, 0x80 el cierre (con dano 0)
#     +2   LE32  atacante
#     +6   LE32  objetivo
#     +10  8 bytes en cero
#     +18  LE16  el dano que se dibuja
#     +20  U8    2
#     +21  LE16  el ataque usado (656 el normal)
#
# Medido: van siempre de a dos, primero la fase 0x00 con el dano y despues la
# 0x80 con cero.
EFECTO_GOLPE = 0x94
_EFECTOS_CACHE = {}


# Los ataques no solo hacen dano: magic.xml los encadena con OTRO hechizo,
# el "transferido" (轉嫁法術), con su probabilidad (轉嫁機率). Medido:
#
#   601 Slicing Hit I   -> 1040 Sliced Hit I    100%  sangrado, -2 HP cada 2s por 10s
#   701 Basic Beating I -> 1045 Basic Beat I     10%  ATURDE 2s (魔法狀態=暈眩)
#   801 Basic Attack I  -> 1050 Basic Attack I   20%
#   901 Basic Shot I    -> 1055 Basic Shot I     30%
#   604 Tendon Chop I   -> 1041 Tendon Chop I         ralentiza, 移動速度 -10 por 5s
#
# El estado va en 魔法狀態: 暈眩 aturdir, 冰凍 congelar, 定身 inmovilizar,
# 沉默 silenciar, 麻痺 paralizar, 捆綁 atar, 恐懼 miedo, 封招 sellar skills.
ESTADOS = {
    '暈眩': 'aturdido', '冰凍': 'congelado', '定身': 'inmovilizado',
    '沉默': 'silenciado', '麻痺': 'paralizado', '捆綁': 'atado',
    '恐懼': 'miedo', '封招': 'sellado', '反彈': 'reflejo',
}


_MAGIC_XML = None


def _magic_xml():
    """magic.xml crudo, indexado por numero. content.db no sirve para esto:
    se construyo de una version sin las columnas 轉嫁法術 / 魔法狀態."""
    global _MAGIC_XML, _EFECTOS_DISPONIBLES
    if _MAGIC_XML is not None:
        return _MAGIC_XML
    import re as _re
    _MAGIC_XML = {}
    f_json = pathlib.Path(__file__).parent / 'plantillas' / 'client_tables.json'
    if f_json.exists():
        try:
            raw = json.loads(f_json.read_text(encoding='utf-8'))
            for k, v in (raw.get('magic_xml') or {}).items():
                _MAGIC_XML[int(k)] = v
            if _EFECTOS_DISPONIBLES is None and raw.get('efectos_disponibles'):
                _EFECTOS_DISPONIBLES = set(int(x) for x in raw['efectos_disponibles'])
            if _MAGIC_XML:
                return _MAGIC_XML
        except Exception:
            pass
    for raiz in (pathlib.Path(__file__).parent.parent / 'extracted_paks', pathlib.Path('G:/extracted_paks')):
        for pak in ('update26', 'UPDATE18', 'data1'):
            f = raiz / pak / 'setting' / 'eng' / 'magic.xml'
            if not f.exists():
                continue
            for l in f.read_text(encoding='utf-8', errors='replace').splitlines():
                m = _re.search(r'編號="(\d+)"', l)
                if m:
                    _MAGIC_XML[int(m.group(1))] = dict(
                        _re.findall(r'(\S+?)="([^"]*)"', l))
            if _MAGIC_XML:
                return _MAGIC_XML
    return _MAGIC_XML


def buff_al_reutilizar(magic_id, buffs, ahora=None, azar=None):
    """Resolver el hijo de un buff condicional sin tocar marcas ofensivas.

    Primer uso: parametro 1. Con ese efecto aun activo: parametro 2 segun
    la probabilidad del parametro 3. Se conservan coste/cadencia del padre.
    El id del hijo se usa para los iconos y su expiracion, dejando al buff
    base coexistir con la recuperacion periodica del segundo uso.
    """
    padre = datos_magia(int(magic_id))
    base = int(padre.get('reuso_base_id') or 0)
    extra = int(padre.get('reuso_extra_id') or 0)
    if not base:
        return padre
    ahora = time.time() if ahora is None else ahora
    activo = (buffs or {}).get(base) or (buffs or {}).get(str(base))
    activo = isinstance(activo, dict) and activo.get('fin', 0) > ahora
    lanzar = azar if azar is not None else random.randint
    seleccionado = (extra if activo and extra and lanzar(1, 100) <= padre.get('reuso_prob', 100)
                    else base)
    resultado = dict(datos_magia(seleccionado))
    for campo in ('mp', 'cost_sp', 'cd_ms', 'cast_time'):
        if campo in padre:
            resultado[campo] = padre[campo]
    return resultado


def combo_de(magic_id: int):
    """{'golpes', 'intervalo_ms', 'dano'} si el ataque pega varias veces.

    Hay DOS formas de combo en magic.xml:

    1. Directa, en el propio hechizo: 連擊次數 golpes y 連擊間隔 ms entre
       cada uno. Cross Chop I (605) trae 連擊次數=2 y 連擊間隔=200, que es
       el "121 x2" de la wiki.
    2. Encadenada, via 轉嫁法術 a un hijo marcado 單體多次攻擊, donde el
       numero de golpes es 動態參數2 del padre. Asi funciona Strangle Strike.
    """
    tabla = _magic_xml()
    d = tabla.get(int(magic_id or 0))
    if not d:
        return None
    def _n(v, x=0):
        try: return int(float(v)) if v not in (None, '') else x
        except (TypeError, ValueError): return x
    golpes = _n(d.get('連擊次數'))
    if golpes > 1:
        return {'golpes': golpes,
                'intervalo_ms': _n(d.get('連擊間隔'), 200),
                'dano': _n(d.get('HP'))}
    ef = efecto_secundario(magic_id)
    if ef and ef.get('golpes', 1) > 1:
        _int_ms = min(250, max(120, _n(tabla.get(ef['magia'], {}).get('命中時間'), 200)))
        return {'golpes': ef['golpes'],
                'intervalo_ms': _int_ms,
                'dano': ef.get('dano_golpe', 0),
                'es_ricochet': ef.get('es_ricochet', False)}
    return None


# Las AoE de combo (Bullet Arrow, Steel Rain, Sword of Kings...) sueltan TODOS
# sus golpes durante la animacion, que es una sola. Con el 連擊間隔 de
# magic.xml (250 ms) los 12 golpes de Bullet Arrow V tardaban 3 s, mucho mas
# lentos que en el juego (lo noto el usuario el 20/10/2026). Se comprimen para
# que la rafaga entera quepa en DURACION_RAFAGA_AOE.
DURACION_RAFAGA_AOE = 1.2


def separacion_aoe(combo) -> float:
    """Segundos entre golpes de una AoE de combo."""
    if not combo or combo.get('golpes', 1) <= 1:
        return 0.2
    golpes = int(combo['golpes'])
    sep = max(0.06, combo.get('intervalo_ms', 200) / 1000.0)
    return max(0.06, min(sep, DURACION_RAFAGA_AOE / max(1, golpes - 1)))


def cura_por_tics(magic_id: int):
    """Tics de HP/MP de una habilidad con duracion e intervalo.

    Injury Cure I (603) es 對象="自己" HP="15" 作用間隔="5" 持續時間="11":
    quince de vida cada cinco segundos durante once. Earth Blessing (302)
    usa 對象="角色" y Energy Source (305) restaura MP, asi que tambien se
    reconocen objetivos de personaje y el campo MP.
    """
    d = _magic_xml().get(int(magic_id or 0))
    if not d or str(d.get('對象') or '').strip() not in ('自己', '角色'):
        return None
    def _n(v, x=0):
        try: return int(float(v)) if v not in (None, '') else x
        except (TypeError, ValueError): return x
    hp = _n(d.get('HP'))
    mp = _n(d.get('MP'))
    intervalo = _n(d.get('作用間隔'))
    dur = _n(d.get('持續時間'))
    if (hp <= 0 and mp <= 0) or intervalo <= 0 or dur <= 0:
        return None
    # El primer tic es al lanzarla: en 11 s con intervalo de 5 caben
    # tres (0, 5 y 10), no dos.
    return {'hp': max(0, hp), 'mp': max(0, mp),
            'intervalo': intervalo, 'dur_ms': dur * 1000,
            'tics': max(1, dur // intervalo + 1)}


def efecto_secundario(magic_id: int):
    """{'magia', 'prob', 'estado', 'dur_ms', 'hp_tick', ...} o None.

    Es el hechizo que el ataque encadena por 轉嫁法術 y con que probabilidad.
    De ahi salen el sangrado de Slicing Hit, el aturdimiento de Basic Beating
    y la ralentizacion de Tendon Chop.
    """
    tabla = _magic_xml()
    d = tabla.get(int(magic_id or 0))
    if not d:
        return None
    def _n(v, x=0):
        try: return int(float(v)) if v not in (None, '') else x
        except (TypeError, ValueError): return x
    sub_id = encontrar_sub_combate(magic_id, d, tabla)
    hijo = _n(d.get('轉嫁法術'))
    if not hijo and sub_id and sub_id != magic_id:
        sub_d = tabla.get(sub_id, {})
        hijo = _n(sub_d.get('轉嫁法術'))
    if not hijo:
        return None
    h = tabla.get(hijo, {})
    # Los ataques en combo encadenan un hijo marcado 單體多次攻擊 o usan formula 40/36/42 / Combo Hit en descripcion.
    desc_padre = str(d.get('說明') or '').lower()
    desc_hijo = str(h.get('說明') or '').lower()
    sub_d = tabla.get(sub_id, {}) if (sub_id and sub_id != magic_id) else {}
    desc_sub = str(sub_d.get('說明') or '').lower()
    es_ricochet = (str(sub_d.get('公式') or '') == '42' or str(d.get('公式') or '') == '42' or
                   'ricochet' in desc_padre or 'ricochet' in desc_sub)
    es_combo_multi = (
        h.get('單體多次攻擊') == '是' or
        str(d.get('公式') or '') in ('40', '36', '42') or
        str(sub_d.get('公式') or '') in ('40', '36', '42') or
        'combo' in desc_padre or
        'combo' in desc_hijo or
        'combo' in desc_sub or
        es_ricochet
    )
    golpes = 0
    if str(d.get('公式') or '') == '36':
        golpes = _n(d.get('動態參數1'))
    elif str(d.get('公式') or '') == '40':
        golpes = _n(d.get('動態參數2'))
    elif str(sub_d.get('公式') or '') == '42':
        golpes = _n(sub_d.get('動態參數1'))
    elif str(d.get('公式') or '') == '42':
        golpes = _n(d.get('動態參數1'))
    if not golpes:
        golpes = _n(d.get('動態參數2')) or _n(d.get('動態參數1')) or _n(sub_d.get('動態參數2')) or _n(sub_d.get('動態參數1'))
    if not golpes:
        for txt in (desc_padre, desc_hijo, desc_sub):
            m_cb = re.search(r'combo\s*(?:hit|number|count)?\s*[:：]?\s*(\d+)', txt)
            if m_cb:
                golpes = int(m_cb.group(1))
                break
            m_cb = re.search(r'ricochets?\s*(\d+)', txt)
            if m_cb:
                golpes = int(m_cb.group(1))
                break
            m_cb = re.search(r'(\d+)\s*(?:combo|hit|hits)', txt)
            if m_cb:
                golpes = int(m_cb.group(1))
                break
    golpes = max(1, golpes) if es_combo_multi else 1

    elem_dmg = max(_n(h.get('雷電攻擊')), _n(h.get('火焰攻擊')), _n(h.get('寒冰攻擊')), _n(h.get('腐蝕攻擊')))
    sub_deb = _n(h.get('動態參數2')) if (_n(h.get('動態參數2')) in tabla) else 0

    return {'magia': hijo, 'prob': _n(h.get('轉嫁機率') or d.get('轉嫁機率') or 100),
            'nombre': h.get('名稱', ''),
            'golpes': max(1, golpes),
            'dano_golpe': _n(h.get('HP')) if es_combo_multi else 0,
            'es_ricochet': es_ricochet,
            'estado': ESTADOS.get(h.get('魔法狀態', ''), h.get('魔法狀態', '')),
            'dur_ms': _n(h.get('持續時間')) * 1000,
            'hp_tick': _n(h.get('HP')),
            'elem_dmg': elem_dmg,
            'sub_debuff': sub_deb,
            'intervalo': _n(h.get('作用間隔')),
            'vel_mov': _n(h.get('移動速度'))}


_EFECTOS_DISPONIBLES = None


def efecto_existe(numero: int) -> bool:
    """Si el cliente tiene el sprite de ese 特效編號.

    Los efectos viven en shape/magic/<numero>/*.shp, uno por numero. Sirve
    para no mandar efectos que el cliente no puede dibujar: comprobado que
    136 (Slicing Hit), 141 (Ferocious Song), 146 (Injury Cure) y 175
    (Fighting Shield) estan ahi con sus sprites.
    """
    global _EFECTOS_DISPONIBLES
    if _EFECTOS_DISPONIBLES is None:
        _magic_xml()
    if _EFECTOS_DISPONIBLES is None:
        _EFECTOS_DISPONIBLES = set()
        for raiz in (pathlib.Path(__file__).parent.parent / 'extracted_paks', pathlib.Path('G:/extracted_paks')):
            d = raiz / 'data1' / 'shape' / 'magic'
            if d.is_dir():
                for sub in d.iterdir():
                    if sub.is_dir() and sub.name.isdigit():
                        _EFECTOS_DISPONIBLES.add(int(sub.name))
    return not _EFECTOS_DISPONIBLES or int(numero) in _EFECTOS_DISPONIBLES


def efecto_de_ataque(magic_id: int) -> int:
    """Devuelve el numero de efecto visual para este ataque o skill de magic.xml."""
    global _EFECTOS_CACHE
    if magic_id in _EFECTOS_CACHE:
        return _EFECTOS_CACHE[magic_id]

    # Doomsday Bomb usa la animacion de explosion 195 (en lugar de 63 que es Poison Hit)
    if (196 <= magic_id <= 200) or (1262 <= magic_id <= 1266) or (4676 <= magic_id <= 4680):
        _EFECTOS_CACHE[magic_id] = 195
        return 195

    d_xml = _magic_xml().get(int(magic_id or 0))
    if d_xml and str(d_xml.get('特效編號', '')).isdigit():
        val = int(d_xml['特效編號'])
        _EFECTOS_CACHE[magic_id] = val
        return val

    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if db.exists():
        try:
            con = sqlite3.connect(db)
            row = con.execute('select "特效編號" from magic where id=?', (str(magic_id),)).fetchone()
            if row and row[0] and str(row[0]).isdigit():
                val = int(row[0])
                _EFECTOS_CACHE[magic_id] = val
                return val
        except Exception:
            pass
    _EFECTOS_CACHE[magic_id] = EFECTO_GOLPE
    return EFECTO_GOLPE


_WEAPON_ATTACK_CACHE = {}


# Cuanto pesa el "Stance power" de una habilidad en el golpe.
#
# El Stance power ES el campo `hp` de magic.xml: Slicing Hit I tiene 50 y el
# tooltip dice "Stance power: 50"; Advance Chop V tiene 325 y dice 325. Todas
# las habilidades de ataque llevan ademas 公式=15, que es su id de formula.
#
# Se suma al ataque, no se multiplica, y esto es lo medido: en Celestia, con
# R.Atk 57650, un Advance Chop V (stance 325) hizo 689.459 y 689.808 de dano
# mientras que un golpe BASICO hizo 780.680 a 781.453. Si la habilidad
# llevara un multiplicador interno tendria que haber pegado mucho mas fuerte,
# y pego menos. Con 57650 de ataque, sumar 325 no se nota -- que es justo lo
# que se ve.
#
# A nivel bajo si se nota: con R.Atk 68, un Slicing Hit I pasa de 39 a 66 de
# dano contra un Slarm, un 70% mas.
#
# Queda como constante para poder subirlo si en el juego se siente flojo. En
# 1.0 es la suma pura, que es lo unico que respalda la medicion.
PESO_STANCE = 2

# Divisor fijo del daño de hechizo. Ver la nota del 高權位 mas abajo.
DENOM_HECHIZO = 200


def stance_de(magic_id: int) -> int:
    """El Stance power de esa habilidad, del campo `hp` de magic.xml."""
    return abs(int(datos_magia(magic_id).get('hp', 0) or 0))


def ataque_con_stance(ataque: int, magic_id: int = 0) -> int:
    """El ataque total de un golpe: el R.Atk mas el Stance de la habilidad."""
    if not magic_id:
        return int(ataque)
    return int(round(ataque + stance_de(magic_id) * PESO_STANCE))


def ataque_estandar_arma(item_id: int) -> tuple:
    """(magic_id, efecto) del ataque basico segun el arma equipada.

    Se deriva de los datos, no de una lista a mano: la habilidad del arma
    sale de su categoria en item.xml y el ataque basico es el hechizo de
    nivel 1 de esa rama en magic.xml, con su 特效編號.

    La tabla escrita a mano que habia antes daba (809, 198) para la lanza, y
    el efecto 198 NO EXISTE en shape/magic: por eso con lanza no se veia
    ningun efecto. El correcto es Basic Attack I (801) con el efecto 157.
    """
    global _WEAPON_ATTACK_CACHE
    if item_id in _WEAPON_ATTACK_CACHE:
        return _WEAPON_ATTACK_CACHE[item_id]
    res = (656, 136)          # sin arma: pelea a mano limpia
    try:
        import clases as _cl
        sid = _cl.skill_de_item(item_id) if item_id else None
        hech = _cl.hechizos_iniciales([sid]) if sid else []
        if hech:
            magia = hech[0][0]
            ef = efecto_de_ataque(magia)
            if efecto_existe(ef):
                res = (magia, ef)
    except Exception:
        pass
    _WEAPON_ATTACK_CACHE[item_id] = res
    return res


def exp_paquete(entidad: int, exp_valor: int, kind: int = 1) -> bytes:
    """Sub-mensaje 0x000B nativo para EXP (kind=1) o Skill EXP (kind=4)."""
    return struct.pack('<HIBIH', 0x000B, entidad, kind, exp_valor, 0)


def skill_exp_paquete(jugador_id: int, exp_valor: int) -> bytes:
    """Sub-mensaje 0x000B nativo que muestra '[Skill] has obtained X Exp.' en el cliente."""
    return struct.pack('<HIBIH', 0x000B, jugador_id, 4, exp_valor, 0)


def muerte_monstruo(monstruo_id: int, jugador_id: int) -> bytes:
    """Sub-mensaje 0x000A de evento de muerte (tipo 7)."""
    return struct.pack('<HIII', 0x000A, monstruo_id, jugador_id, 7)


# El numero que se ve flotar sobre quien recibe el golpe NO viaja en 0x0011
# (ese mensaje es el "cast": sprite, duracion, animacion y spell_id). Va en un
# 0x000B propio, dirigido a la entidad que RECIBE, con el formato que ya usaba
# exp_paquete(). Medido en logs/proxy/mundo_152251_735154_s2c.bin, donde la
# secuencia de un golpe es:
#
#   0x0013 [monstruo] code=1 arg=100   vida antes, en porcentaje
#   0x000A [yo][monstruo] tipo anim    el golpe
#   0x0013 [monstruo] code=1 arg=0     vida despues
#   0x000B [monstruo] tipo=1 dano=46   <-- el numero
#   0x000A [monstruo][yo] 07 00 00 00  muerte
#   0x001D [yo] code=0x20 valor        experiencia
#   0x0007 [monstruo] 02               desaparece
# 0x000A no es "[atacante][0][0]": son 12 bytes
#     [u4 source][u4 target][u2 tipo][u2 animacion]
# Medido en mundo_152251_735154_s2c.bin. Tipos vistos: 1 y 3 en los golpes,
# 7 en la muerte (con animacion 0). Las animaciones varian por golpe (634,
# 951, 1410), asi que el campo es el efecto a reproducir, no el dano.
# Mandar el dano ahi -- que es lo que se hacia -- deja el tipo en un valor
# sin sentido y el cliente reproduce cualquier cosa.
_GRUPOS = None


def _cargar_grupos():
    """magic.xml (via corpus/content.db): grupo -> hechizos, y hechizo -> grupo."""
    global _GRUPOS
    if _GRUPOS is not None:
        return _GRUPOS
    por_grupo, de_hechizo = {}, {}
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if db.exists():
        try:
            con = sqlite3.connect(db)
            for mid, gru in con.execute(
                    'select id, 群組編號 from magic where 群組編號 is not null'):
                try:
                    n, g = int(mid), int(float(gru))
                except (TypeError, ValueError):
                    continue
                por_grupo.setdefault(g, []).append(n)
                de_hechizo[n] = g
            con.close()
        except Exception:
            pass
    _GRUPOS = (por_grupo, de_hechizo)
    return _GRUPOS


def grupo_de(magic_id: int):
    """Los hechizos que comparten cooldown con `magic_id`, el incluido.

    El servidor real no manda el cooldown por habilidad de clase sino por
    GRUPO de hechizo (群組編號 de magic.xml). Al usar Slicing Hit I llegan
    0x001D code=3 con 601, 612, 623, 634 y 645 -- los cinco niveles de
    Slicing Hit -- y 2570 en adelante, que es Mangle: todo el grupo 1201.
    Medido en logs/proxy/mundo_152251_735154, t=118.71.
    """
    por_grupo, de_hechizo = _cargar_grupos()
    g = de_hechizo.get(magic_id)
    if g is None:
        return [magic_id]
    return sorted(por_grupo.get(g, [magic_id]))


# La animacion que viaja en el 0x000A. En Celestia se midieron 1480 (0x05c8)
# y 1410 (0x0582) para el mismo Swordsman en sesiones distintas, y 951 para el
# golpe del monstruo. NO es el 特效編號 del hechizo ni ningun campo de item.xml
# que se haya encontrado: se probaron 常駐法術, 動態資料1 y 動態資料2 y no
# coinciden. Queda como constante hasta poder medirlo con varias armas.
# Formula de dano: dano = ataque * K / (K + defensa). Despejada de medidas
# contra el mismo monstruo con distintas armas. OJO: solo vale para niveles
# bajos. A nivel 118 la relacion es LINEAL en la defensa (ver docs) y esta
# formula se queda muy corta; hace falta rehacerla con datos de ese rango.
K_DEFENSA = 33

# La variacion del golpe es minima: seis golpes seguidos al mismo monstruo en
# Chocolate Forest dieron 103530, 103548, 103551, 103577 y 103585, un 0.05%.
VARIACION_DANO = 0.97

# Probabilidad, por golpe y por habilidad, de ganar un punto de skill exp.
# Medido: 8 avisos en 18 golpes con cinco habilidades candidatas.
PROB_SKILL_EXP = 0.55

# Cuanto se alejan los monstruos de su punto de aparicion al pasear, y con
# que probabilidad dan un paso EN CADA TICK de la IA (300 ms). Era 0.22 con
# ticks de 1,2 s; al hacer el bucle cuatro veces mas fino hubo que dividirla
# para que no pasearan cuatro veces mas. En monster.xml el Little Slarm trae
# move_range=2 y apenas se despega del sitio.
RANGO_PASEO_MIN = 9
PROB_PASEO = 0.055

# Hasta cuantas casillas te persigue un monstruo al que le pegaste. Son
# PASIVOS: no agroan por cercania, solo si los atacas.
RANGO_PERDER_AGRO = 18

# Oro base que suelta un monstruo, antes del multiplicador del servidor.
TASA_ORO_BASE = 5

# Lo que aporta cada fuente de velocidad de ataque, en tanto por uno.
# El valor de Swiftness Song sale de 攻擊速度 en magic.xml: la I trae 5 y la
# V trae 15, que es el 15% que se midio. Finesse aporta un 10% fijo por
# tener la habilidad ("increases attack speed" en skill.xml, sin numero).
VELOCIDAD_FINESSE = 0.10
SKILL_FINESSE = 16
TOPE_VELOCIDAD = 0.60


def bono_velocidad(buffs=None, habilidades=None) -> float:
    """Suma de los bonos de velocidad de ataque, en tanto por uno."""
    import time as _t
    pct = 0.0
    ahora = _t.time()
    for mid, b in (buffs or {}).items():
        if not isinstance(b, dict) or b.get('fin', 0) <= ahora:
            continue
        # Field/album/house bonuses share this dictionary with native spells.
        # Their named keys have no magic.xml entry and must not break attacks.
        d = _magic_xml().get(int(mid), {}) if str(mid).isdigit() else {}
        try:
            v = float(d.get('攻擊速度') or 0)
        except (TypeError, ValueError):
            v = 0
        pct += v / 100.0
    for h in (habilidades or ()):
        sid = h[0] if isinstance(h, (list, tuple)) else h
        if sid == SKILL_FINESSE:
            pct += VELOCIDAD_FINESSE
    return min(TOPE_VELOCIDAD, pct)


# Minimo entre golpes del jugador. NO es el metronomo: el ritmo lo marca el
# cliente, que pide un golpe cuando termina su animacion. Medido en Celestia:
# el cliente manda el 0x0016 cada 1481..1501 ms (muy estable) y el servidor
# responde con el 0x000A cada 1554..1685 ms, es decir no filtra nada. En otra
# sesion sin buffs el ciclo salio en 1.6..1.8 s.
#
# Esto estuvo en 2.30 s, calculado como si el servidor mandara el ritmo, y era
# mas largo que lo que pide el cliente: se rechazaba uno de cada dos golpes y
# el ciclo real salia a ~3 s. Eso es lo que se sentia como "la piensa antes de
# atacar" al llegar al lado del bicho.
#
# El valor es un piso de seguridad por debajo de todo lo medido (1481 ms menos
# un margen), para no comerse peticiones ni con jitter de red.
# Bajado de 1.37 a 1.15 con el log del propio juego: el cliente pedia golpes
# a los 1.073 y 1.111 s y el minimo le quedaba en 1.165, asi que se perdian
# por cincuenta milisegundos. El piso tiene que quedar POR DEBAJO de lo que
# pide el cliente, nunca al lado.
CADENCIA_ATAQUE = 1.15


def dano_recibido(ataque: int, defensa: int, elem_atk: int = 0, elem_def: int = 0) -> int:
    """Dano que recibe el jugador, ya reducido por su defensa fisica y elemental."""
    def_eff = max(0, defensa)
    if ataque > def_eff:
        d = ataque - def_eff
    else:
        d = max(1, int(round(ataque * 0.05)))
    if elem_atk > 0:
        elem_d = max(0, elem_atk - max(0, elem_def))
        d += elem_d
    return max(1, d)


# Cada cuanto pega un monstruo, en segundos. Medido en las capturas:
#   Slarm  (攻擊速度 90) -> 835 ms      Lily (30) -> 1121 ms
#   Earth Elf            -> 1023 ms     Death Mummy -> 672 ms
# Con esos dos puntos sale una recta: ms = 1264 - 4.77 * velocidad.
# Antes se usaba 2.0 s fijo para todos, el doble de lento que el real y sin
# distinguir un bicho rapido de uno lento.
CADENCIA_MONSTRUO_BASE = 1.264
CADENCIA_MONSTRUO_PENDIENTE = 0.00477
CADENCIA_MONSTRUO_MIN = 0.40

# Paseo de los monstruos. En la captura del Angel Lyceum de Celestia hay 239
# bichos moviendose a la vez: cada uno da un paso cada 5.6 s de mediana (3.6 a
# 7.7 s), y el paso es de UNA A TRES casillas por eje, no de una sola. La
# velocidad que declara el 0x0005 es 75, no 50. Con un paso de una casilla y
# velocidad 50 el mapa se veia quieto comparado con el suyo.
PASO_PASEO_MAX = 3
VELOCIDAD_PASEO = 75
SEGUNDOS_ENTRE_PASEOS = 5.6

# Cuanto tarda un monstruo en recorrer una casilla, y cuanto descansa entre
# un paso y el siguiente. El paseo se programaba con una probabilidad por
# tick: cada bicho tenia la misma posibilidad de arrancar en cualquier
# momento, asi que se movian a tirones -- un paso, una pausa larga, otro
# paso. Ahora cada uno lleva su propio reloj: cuando termina de caminar sale
# de nuevo casi enseguida, y el movimiento se ve continuo.
SEGUNDOS_POR_CASILLA = 0.34
PAUSA_PASEO_MIN = 0.15
PAUSA_PASEO_MAX = 0.90

# Segundos entre el 0x000A del monstruo y su numero de dano. El campo de
# animacion del 0x000A es la duracion en milisegundos: un bicho con animacion
# 951 manda su 0x000B a los 951..1118 ms, y otro con 774 a los 783..786 ms.
# Antes el dano del monstruo se aplicaba en el acto mientras el cliente aun
# reproducia el golpe, por eso los numeros no cuadraban con la animacion.
def retraso_golpe_monstruo(m) -> float:
    """Tiempo hasta el impacto visual del monstruo.

    La cadencia controla cuando puede empezar el siguiente ataque; no cuanto
    tarda en llegar el dano. Usar la cadencia aqui dejaba el golpe del Slarm
    pendiente durante 2 segundos, bastante despues de su animacion de 740 ms.
    """
    return max(0.1, anim_de_monstruo(getattr(m, 'nombre', '')) / 1000.0)


def alcance_arma(item_id: int = 0) -> int:
    """Desde cuantas casillas se puede pegar con esa arma.

    Sale del 射程 del hechizo de ataque basico del arma: punos, sable y hacha
    tienen 1, la lanza 2 y el arco 12. Es la regla de siempre -- guerreros de
    cerca, arqueros de lejos -- pero leida de los datos en vez de escrita a
    mano. Antes se usaba 1 para todo ataque normal.
    """
    magia, _ = ataque_estandar_arma(item_id)
    d = _magic_xml().get(int(magia), {})
    try:
        return max(1, int(float(d.get('射程') or 1)))
    except (TypeError, ValueError):
        return 1


# Segundos entre golpes de cada monstruo, MEDIDOS en el trafico. Van aparte
# de la animacion, que es otra cosa: la Lily se anima en 1009 ms pero pega
# cada 1400-1530, y el Slarm se anima en 740 y pega cada 798.
#
#   Slarm            798 ms   (una muestra)
#   Lily            1411 y 1530 ms
#   Death's Head 1  1305 ms
#
# El Slarm se deja en 2.00 a proposito: a su ritmo real resulta injugable
# aqui, y el usuario pidio ese valor probando en el juego. Lo que no este en
# esta tabla usa su animacion como ritmo.
CADENCIA_POR_MONSTRUO = {
    'Slarm': 2.00,
    'Lily': 1.47,
    "Death's Head": 1.305,
}


def cadencia_monstruo(m) -> float:
    """Segundos entre golpes de ese monstruo: su animacion, y nada mas.

    Lo medido es que el campo de animacion del 0x000A ES el ciclo: un bicho
    con animacion 951 manda su golpe cada 951 ms y su numero de dano justo
    951 ms despues. Asi que el ciclo sale de ANIM_POR_MONSTRUO y se acabo.

    Aqui habia ademas un escalado por el atk_speed de monster.xml,
    `1 - atk_speed / 200`, que me invente. El Slarm tiene atk_speed 90, asi
    que con 1500 de animacion pegaba cada 825 ms: seguia siendo demasiado
    rapido por mucho que se subiera el numero. No se sabe que unidad es el
    atk_speed ni como se traduce a milisegundos, asi que hasta tener una
    medicion no se usa para nada.

    Para un bicho nuevo o un jefe, se le pone su entrada en
    ANIM_POR_MONSTRUO y ese es su ciclo en milisegundos.
    """
    nombre = getattr(m, 'nombre', '') or ''
    for clave, val in CADENCIA_POR_MONSTRUO.items():
        if clave.lower() in nombre.lower():
            return max(CADENCIA_MONSTRUO_MIN, val)
    return max(CADENCIA_MONSTRUO_MIN, anim_de_monstruo(nombre) / 1000.0)


# Segundos entre golpes segun el arma, por su habilidad:
#   9 espada, 10 hacha/martillo, 11 lanza, 17 arco, 30 daga, 8 baston.
# El usuario lo describio asi jugando: la espada marca el ritmo normal, y la
# lanza, la daga y el baston van a esa misma velocidad de una mano; el hacha
# es la lenta. Lo que no este aqui usa CADENCIA_ATAQUE.
CADENCIA_POR_ARMA = {
    9: CADENCIA_ATAQUE,          # espada
    30: CADENCIA_ATAQUE,         # daga
    # La lanza va un poco mas rapida que la espada, y el baston se queda con
    # la velocidad que tenia la lanza. Probado en el juego.
    11: CADENCIA_ATAQUE * 0.87,  # lanza
    8: CADENCIA_ATAQUE,          # baston
    10: CADENCIA_ATAQUE * 1.30,  # hacha y martillo: la mas lenta
    17: CADENCIA_ATAQUE * 1.15,  # arco
}


def cadencia_ataque(buffs=None, habilidades=None, duales=False,
                    item_id: int = 0) -> float:
    """Minimo entre golpes, ya con la velocidad de ataque aplicada.

    Con dos armas se usaba un minimo mas largo -- el golpe mas los dos
    numeros -- y el personaje se quedaba parado esperando despues de que la
    animacion habia terminado. El ciclo dual lo lleva el cliente, asi que
    aqui va el mismo piso que con una sola arma.
    """
    base = CADENCIA_ATAQUE
    if item_id:
        try:
            import clases as _cl
            base = CADENCIA_POR_ARMA.get(_cl.skill_de_item(item_id), base)
        except Exception:
            pass
    return base * (1.0 - bono_velocidad(buffs, habilidades))


# Pausa entre el final del ciclo dual y el golpe siguiente.
RESPIRO_DUALES = 0.0

# Segundos entre el 0x000A del golpe y el 0x000B con el numero.
#
# Los 664 ms medidos en Chocolate Forest son CON dos bonos de velocidad de
# ataque puestos: Swiftness Song V (15%) y Finesse (10%). Se restan del base,
# no se multiplican: 664 / (1 - 0.25) = 885 ms de tiempo base.
#
# Comprobacion: nuestro servidor medido dio 775 ms con Finesse sola, y
# 885 * (1 - 0.10) = 796. Encaja.
RETRASO_DANO = 0.885

def retraso_golpe(buffs=None, habilidades=None) -> float:
    """Segundos hasta el numero de dano, ya con la velocidad de ataque."""
    return RETRASO_DANO * (1.0 - bono_velocidad(buffs, habilidades))


RETRASO_SEGUNDA_MANO = 0.70


ANIM_GOLPE = 1480
# Animacion del 0x000A de cada monstruo al pegar, medida en Celestia
# (mundo_181419_370379): el Slarm usa 740 y la Lily 1009. No coincide con
# el 投射特效 de monster.xml (la Lily tiene 50008 ahi), asi que por ahora
# es una tabla por nombre con un valor por defecto.
# La animacion de un monstruo es tambien su ciclo de ataque en milisegundos.
# El 740 del Slarm venia de una estimacion vieja, no de una medicion, y le
# salian golpes cada 0.74 s: demasiado rapido. Los unicos valores medidos de
# verdad en el trafico son 951, 774 y 832, con ciclos de 920 a 1140 ms, asi
# que el Slarm usa el valor por defecto hasta que se mida el suyo.
# El Slarm va a 1500, el mismo ciclo que el del jugador: con el 951 medido
# en otros bichos seguia pegando demasiado rapido. Lo pidio el usuario tras
# probarlo en el juego.
# La ANIMACION de cada monstruo, medida en el trafico: el Slarm manda 740 y
# el Death's Head 832, los dos con tipo 1. Es el dibujo que reproduce el
# cliente y no tiene nada que ver con cada cuanto pega.
#
# Estuvieron mezclados: para frenar al Slarm se subio este numero a 2000, y
# eso le mandaba al cliente una animacion que no existe. Ahora la animacion
# va aqui y el ritmo en CADENCIA_POR_MONSTRUO.
ANIM_POR_MONSTRUO = {'Slarm': 740, "Death's Head": 832, 'Lily': 1009}
# Para un bicho que no este en la tabla: 951, que es el valor mas comun
# de los medidos.
ANIM_MONSTRUO = 951


def anim_de_monstruo(nombre: str) -> int:
    for clave, val in ANIM_POR_MONSTRUO.items():
        if clave.lower() in (nombre or '').lower():
            return val
    return ANIM_MONSTRUO


# Animacion del 0x000A segun con que se pegue. Medido en Celestia:
#   sin arma (punos)      666
#   dos armas (duales)    832
#   espada               1480
#   hacha           951 y 1009
# Las duales NO pegan dos veces: en la captura cada golpe manda un solo
# 0x000B. Lo unico que cambia es la animacion y el ataque total.
ANIM_SIN_ARMA = 666
ANIM_DUALES = 832


# Con animacion 0 el cliente reproduce la que corresponde al arma que tiene
# puesta, que es la que conoce el. Forzar un numero concreto le hace usar OTRA
# animacion: mandando 1480 con cualquier arma, el golpe se veia acelerado y
# sin relacion con lo equipado.
#
# Los valores reales existen -- Celestia manda 1287 con su arma de nivel 118,
# y en otras capturas 666, 832 y 1480 -- pero no se encontro de donde salen:
# no estan en magic.xml (1480 es "Collected Cake") ni en ninguna columna de
# item.xml. Hasta saberlo, dejar que el cliente elija es mas fiel que
# imponerle una animacion equivocada.
# ---- ANIMACION DEL GOLPE: PARA PROBAR A MANO ----------------------------
# Numero que va en el 0x000A. Con 0 elige el cliente segun el arma equipada.
# Valores vistos en capturas de Celestia: 666, 832, 1287, 1480.
#
# Se puede poner uno por tipo de arma, porque la lanza (dos manos) no se
# mueve igual que un sable ni que dos dagas. Cambiar y reiniciar el servidor.
# 0 = NO se impone ninguna animacion y el cliente reproduce la del arma que
# lleva puesta. Es lo que hace el servidor real: en mundo_032752 los 21
# golpes del jugador salen con animacion 0.
#
# Estuvo en 1500 fijo, y por eso la lanza y el baston -- que son a dos manos
# -- atacaban con la animacion de duales y ni siquiera se veia el arma. El
# numero solo hace falta si se quiere forzar una animacion concreta para
# probar algo.
ANIM_POR_DEFECTO = 0
ANIM_SIN_ARMA_TEST = 0      # a mano limpia
ANIM_DUALES_TEST = 0        # dos armas de una mano
ANIM_DOS_MANOS_TEST = 0     # lanza, o cualquier arma a dos manos
# Tipo y animacion del 0x000A segun la habilidad del arma. MEDIDO en las
# capturas siguiendo los cambios de equipo dentro de cada sesion:
#
#   lanza  (Serphyna's Crime, se equipa en t=71.88)  -> tipo 2, animacion 827
#   espada y daga                                    -> tipo 3, animacion 1480
#
# La animacion no es una duracion: la lanza pega mas lento que la espada y
# sin embargo su numero es menor. Es el identificador de la animacion que el
# cliente reproduce, y por eso hay que mandar el que corresponde al arma: con
# el de la espada la lanza atacaba como si llevara dos armas y ni se veia.
#
#   9 espada, 10 hacha, 11 lanza, 17 arco, 30 daga, 8 baston
GOLPE_POR_SKILL = {
    9: (3, 1480),
    30: (3, 1480),
    11: (2, 827),
    8: (2, 951),     # baston: medido con el Walking Stick del mago
}
GOLPE_POR_DEFECTO = (3, 1480)
ANIM_POR_SKILL = {}
# -------------------------------------------------------------------------


def golpe_de_arma(item_id: int = 0, duales: bool = False) -> tuple:
    """(tipo, animacion) del 0x000A para el arma que se lleva puesta.

    Con dos armas de una mano el servidor real manda tipo 2 y una animacion
    cercana a 830, igual que la lanza; con una sola arma, tipo 3.
    """
    if duales:
        return (2, 832)
    try:
        import clases as _cl
        sid = _cl.skill_de_item(item_id) if item_id else None
        if sid in GOLPE_POR_SKILL:
            return GOLPE_POR_SKILL[sid]
    except Exception:
        pass
    return GOLPE_POR_DEFECTO


def anim_de_arma(item_id: int = 0, duales: bool = False,
                 ciclo_ms: int = 0) -> int:
    """Animacion del 0x000A, que ES la duracion del ciclo en milisegundos.

    Por defecto vale lo que dure el ciclo de ataque de verdad (`ciclo_ms`).
    Estaba fija en 1500 mientras el jugador pegaba cada 1100 ms, asi que el
    cliente se quedaba siempre en medio de una animacion y no dejaba lanzar
    habilidades. Las constantes de prueba de abajo siguen mandando si se les
    pone un valor.
    """
    if duales and ANIM_DUALES_TEST:
        return ANIM_DUALES_TEST
    if not item_id:
        return ANIM_SIN_ARMA_TEST or ANIM_POR_DEFECTO
    try:
        import clases as _cl
        if ANIM_DOS_MANOS_TEST and _cl.es_dos_manos(item_id):
            return ANIM_DOS_MANOS_TEST
        sid = _cl.skill_de_item(item_id)
        if sid in ANIM_POR_SKILL:
            return ANIM_POR_SKILL[sid]
    except Exception:
        pass
    return ANIM_POR_DEFECTO


def confirmar_cast(target: int, x: int, y: int, *args, **kwargs) -> bytes:
    """0x0006 s2c: confirma el cast y dice sobre que casilla ocurre.

    Medido en Celestia: 01 00 | target [u4] | x [u4] | y [u4] | 00 00 [u2]
    Status es SIEMPRE 1 (0x0001 = aceptado/exito).
    """
    return struct.pack('<HHIIIH', 0x0006, 1, target, x, y, 0)


def efecto_aura_objetivo(atacante: int, objetivo: int, x: int, y: int, magic_id: int) -> bytes:
    """0x0011 fase 0x80: activa el aura / efecto visual del debuff sobre el objetivo en sus coordenadas (x, y).

    Medido en Celestia: 00 80 | atacante | objetivo | x (u4) | y (u4) | 00 00 | 00 | magic_id (u2).
    """
    b = bytearray(23)
    b[0] = 0x00
    b[1] = 0x80
    struct.pack_into('<IIII', b, 2, atacante, objetivo, x, y)
    b[18] = 0
    b[19] = 0
    b[20] = 0
    struct.pack_into('<H', b, 21, magic_id & 0xFFFF)
    return struct.pack('<H', 0x0011) + bytes(b)


TIPO_GOLPE = 1
TIPO_GOLPE_ALT = 3
TIPO_MUERTE = 7


def ataque(source: int, target: int, animacion: int = 0,
           tipo: int = TIPO_GOLPE) -> bytes:
    """0x000A: el golpe. [u4 origen][u4 objetivo][u2 tipo][u2 animacion].

    El tipo y la animacion van de la mano. Cruzando todas las capturas, el
    servidor real solo manda estas combinaciones:

        tipo 0 con animacion 0        245 veces
        tipo 3 con 1287, 1410 o 1480   40 veces
        tipo 2 con 827                  4 veces

    Nunca manda tipo 3 con animacion 0, que es justo lo que mandabamos
    nosotros desde que se dejo la animacion en cero. Asi que si no hay
    animacion, el tipo tambien va en cero.

    (Y el numero de animacion NO depende del arma: con la misma espada
    aparece 0, 1287 y 827 en sesiones distintas, y con la daga 1480 y 1410.
    Depende del estado del personaje, no de lo que lleve en la mano.)
    """
    return struct.pack('<HIIHH', 0x000A, source, target, tipo, animacion)


# El tipo del 0x000B distingue el golpe normal del CRITICO: en
# mundo_181419_370379 los golpes de 45..92 llegan con tipo 1 y los de 98 y 101
# con tipo 2, que es el numero con la estrella naranja.
TIPO_DANO = 1
TIPO_DANO_CRITICO = 2
TIPO_DANO_ALT = 2      # alias historico

# LOS NUMEROS DE RECUPERACION TIENEN SU PROPIO TIPO, y no son daño.
# Medido cruzando 0x000B con el 0x0013 que le sigue en diez capturas:
#
#   tipo 3  MP  el numero AZUL. Se vio con 6400 al usar Rejuvenation.
#   tipo 4  HP  el numero VERDE. El HP sube 4916 veces y baja 46, asi que
#               no hay duda. Se vio con 8000.
#   tipo 7  SP  el de las lamparas.
#
# El 4 estaba puesto como "DoT (veneno / sangrado)", que es justo lo
# contrario: por eso las curaciones se veian como si fueran daño. El
# sangrado usa el tipo 1 como cualquier otro daño.
TIPO_CURA_MP = 3
TIPO_CURA_HP = 4
TIPO_CURA_SP = 7
TIPO_DANO_ESTADO = 1   # el DoT es daño normal, no el 4

# La vida que se paga por ganar SP (Hot Blooded, Bloody Storm) usa el MISMO
# tipo que el daño. Se ve blanca y no roja porque el numero cae sobre uno
# mismo, no sobre el enemigo: el color lo decide el cliente segun de quien
# sea la entidad, no el tipo.
#
# MEDIDO: con 138344 de vida maxima, Bloody Storm V (hp=-9) mando 12450, y
# el 9% de 138344 son 12451. Salio 32 veces con ese numero.
TIPO_COSTE_VIDA = TIPO_DANO


def numero_flotante(entity_id: int, cantidad: int, tipo: int = TIPO_DANO) -> bytes:
    """0x000B: el numero que flota sobre `entity_id`. Mismo formato que exp_paquete."""
    return struct.pack('<HIBIH', 0x000B, entity_id, tipo,
                       max(0, min(0xFFFFFFFF, int(cantidad))), 0)


def calcular_cast_time(base_cast_time: int, buffs: dict = None, habilidades: list = None, es_magia: bool = True) -> int:
    """Calcula el tiempo de casteo efectivo (en ms) aplicando:
    1. Reducciones planas de buffs activos (First Path, Third Spirit, Limit Breaker, Shadow Meld, Killer Intent, etc.).
    2. Reduccion del 50% de la habilidad pasiva Curse Spell (ID 5).
    Formula oficial:
      ct = max(100, base - flat_reductions)
      if tiene_curse and es_magia:
          ct = max(100, ct * 0.5)
    """
    ct = base_cast_time
    if buffs:
        now = time.time()
        max_redux = 0
        for b_data in buffs.values():
            if isinstance(b_data, dict) and b_data.get('fin', 0) > now:
                r = b_data.get('cast_redux', 0)
                if r > max_redux:
                    max_redux = r
        if max_redux > 0:
            ct = max(100, ct - max_redux)

    if es_magia and habilidades:
        tiene_curse = False
        for h in habilidades:
            sid = h[0] if isinstance(h, (list, tuple)) else h
            if sid == 5:
                tiene_curse = True
                break
        if tiene_curse:
            ct = max(100, int(round(ct * 0.5)))

    return max(100, ct)


def efecto_level_up(yo: int, es_skill: bool = False,
                    es_rango: bool = False) -> bytes:
    """Opcode 0x0020: la banderola de Level Up sobre el jugador.

    effect_id = 1  nivel de personaje
    effect_id = 2  nivel de habilidad (skill)
    effect_id = 3  RANGO

    El 3 sale de que common.obd tiene TRES banderolas, no dos, y las tres
    comparten el arte lvup02 cambiado de color:

        secuencia 302  "升級效果-LEVEL UP旗幟"         lvup02-1/2/3
        secuencia 70   "升級效果-LEVEL UP旗幟(技能)"   lvup02-4/5/6
        secuencia 71   "升級效果-LEVEL UP旗幟(階級)"   lvup02-7/8/9

    La del rango es la 71 (階級 = rango), que es la verde que se veia. Hay
    ademas una 743 "PEERAGE UP旗幟" con arte propio (peup02-1/2/3), pero
    esos sprites NO estan en ningun pak: solo existen los lvup02-1..9. Por
    eso el rango se queda con la verde.
    """
    effect_id = 3 if es_rango else (2 if es_skill else 1)
    return struct.pack('<HIHI', 0x0020, yo, effect_id, yo)


def numero_de_dano(atacante: int, objetivo: int, dano: int = 0,
                   ataque: int = ATAQUE_NORMAL, efecto: int = EFECTO_GOLPE,
                   cast_time: int = 100, es_magia: bool = False,
                   tile_x: int = 0, tile_y: int = 0):
    """0x0011 fase 0x00: reproduce el EFECTO del ataque sobre el objetivo.

    El offset 18 es el CAST TIME, no el dano.
    Medido en Celestia: efecto va en 12 bits (byte 0 es low byte, byte 1 es high nibble).
    Offset 20: 1 para magias ofensivas a distancia (reproduce cast de manos/circulo), 2 para fisicos.
    Offset 21-22: magic_id / tipo de ataque.
    Offsets 10-17: tile_x y tile_y cuando es ground AOE o self AOE.
    """
    b0 = bytearray(23)
    b0[0] = efecto & 0xFF
    b0[1] = (efecto >> 8) & 0x0F
    struct.pack_into('<II', b0, 2, atacante, objetivo)
    if tile_x or tile_y:
        struct.pack_into('<II', b0, 10, tile_x, tile_y)
    struct.pack_into('<H', b0, 18, max(0, min(65535, cast_time)))
    b0[20] = 1 if es_magia else 2
    struct.pack_into('<H', b0, 21, ataque & 0xFFFF)
    return struct.pack('<H', 0x0011) + bytes(b0)


def cierre_de_dano(atacante: int, objetivo: int,
                   ataque: int = ATAQUE_NORMAL, efecto: int = EFECTO_GOLPE,
                   es_magia: bool = False,
                   tile_x: int = 0, tile_y: int = 0):
    """Sub-mensaje 0x0011 fase 0x80 que concluye el impacto tras reproducir el efecto."""
    b1 = bytearray(23)
    b1[0] = efecto & 0xFF
    b1[1] = 0x80 | ((efecto >> 8) & 0x0F)  # Fase 0x80 + high nibble del efecto
    struct.pack_into('<II', b1, 2, atacante, objetivo)
    if tile_x or tile_y:
        struct.pack_into('<II', b1, 10, tile_x, tile_y)
    struct.pack_into('<H', b1, 18, 0)
    b1[20] = 1 if es_magia else 2
    struct.pack_into('<H', b1, 21, ataque & 0xFFFF)
    return struct.pack('<H', 0x0011) + bytes(b1)


def efecto_cristal_captura(atacante: int, objetivo: int,
                           x: int = 0, y: int = 0):
    """Icy Trap del intento, tanto si la captura acierta como si falla.

    ``magic.xml`` confirma que el efecto 36 pertenece a Icy Trap. El efecto
    19 usado antes pertenece a Fire Trap y no debe formar parte de la
    captura. Se mandan ambas fases sin alterar HP ni estado del monstruo.
    """
    return [
        numero_de_dano(atacante, objetivo, dano=0, ataque=0, efecto=36,
                       cast_time=0, es_magia=True, tile_x=x, tile_y=y),
        cierre_de_dano(atacante, objetivo, ataque=0, efecto=36,
                       es_magia=True, tile_x=x, tile_y=y),
    ]


def efecto_captura(atacante: int, objetivo: int, x: int = 0, y: int = 0,
                   subtipo: int = 16979):
    """Absorcion de una captura conseguida hacia el jugador.

    Se envia despues de Icy Trap y solamente cuando el sorteo acierta.
    """
    return [
        numero_de_dano(atacante, objetivo, dano=0, ataque=0, efecto=302,
                       cast_time=0, es_magia=True, tile_x=x, tile_y=y),
        cierre_de_dano(atacante, objetivo, ataque=0, efecto=302,
                       es_magia=True, tile_x=x, tile_y=y),
    ]



def efecto_curacion_inicio(atacante: int, objetivo: int, cura_hp: int, efecto: int = 165) -> bytes:
    """Fase 0x00 de curacion 0x0011."""
    b0 = bytearray(23)
    b0[0] = efecto & 0xFF
    b0[1] = 0x00
    struct.pack_into('<II', b0, 2, atacante, objetivo)
    struct.pack_into('<H', b0, 18, max(0, min(65535, cura_hp)))
    b0[20] = 1  # Tipo 1 (cura/verde)
    struct.pack_into('<H', b0, 21, 0)
    return struct.pack('<H', 0x0011) + bytes(b0)


def efecto_curacion_fin(atacante: int, objetivo: int, efecto: int = 165) -> bytes:
    """Fase 0x80 de curacion 0x0011."""
    b1 = bytearray(23)
    b1[0] = efecto & 0xFF
    b1[1] = 0x80
    struct.pack_into('<II', b1, 2, atacante, objetivo)
    struct.pack_into('<H', b1, 18, 0)
    b1[20] = 1
    struct.pack_into('<H', b1, 21, 0)
    return struct.pack('<H', 0x0011) + bytes(b1)


def efecto_curacion(atacante: int, objetivo: int, cura_hp: int, efecto: int = 165):
    """Efecto visual de curacion 0x0011 sin golpe ofensivo (fase 0x00 y fase 0x80)."""
    return [efecto_curacion_inicio(atacante, objetivo, cura_hp, efecto),
            efecto_curacion_fin(atacante, objetivo, efecto)]


def efecto_recuperacion_mp(atacante: int, objetivo: int, rec_mp: int, efecto: int = 69):
    """Efecto visual de recuperacion MP 0x0011 (fase 0x00 y fase 0x80)."""
    b0 = bytearray(23)
    b0[0] = efecto & 0xFF
    b0[1] = 0x00
    struct.pack_into('<II', b0, 2, atacante, objetivo)
    struct.pack_into('<H', b0, 18, max(0, min(65535, rec_mp)))
    b0[20] = 1
    struct.pack_into('<H', b0, 21, 360)

    b1 = bytearray(23)
    b1[0] = efecto & 0xFF
    b1[1] = 0x80
    struct.pack_into('<II', b1, 2, atacante, objetivo)
    struct.pack_into('<H', b1, 18, 0)
    b1[20] = 1
    struct.pack_into('<H', b1, 21, 360)

    return [struct.pack('<H', 0x0011) + bytes(b0), struct.pack('<H', 0x0011) + bytes(b1)]


def gcd_paquete() -> bytes:
    """Opcode 0x0149: el cooldown global (GCD).

    Comparado byte a byte con el que manda Celestia: era identico salvo el
    offset 28, donde el real lleva 72 y nosotros mandabamos 0. Se manda en
    cada uso de habilidad, asi que un GCD mal formado es candidato a que el
    cliente no deje lanzar ninguna.
    """
    return struct.pack('<HIIIIIIIIBBH', 0x0149, 1, 0, 500, 0, 0, 0, 0, 72, 5, 255, 255)


def efecto_magia_self_inicio(yo: int, ef: int, tipo: int, cast_time: int = 100,
                             objetivo: int = None, es_magia: bool = False) -> bytes:
    """Fase 0x00 del efecto visual 0x0011 de un buff.

    +2 es QUIEN lo lanza (hace la animacion de lanzar) y +6 sobre QUIEN cae.
    Con `objetivo` se lo pone a otro; sin el, a uno mismo."""
    b0 = bytearray(23)
    b0[0] = ef & 0xFF
    b0[1] = (ef >> 8) & 0x0F
    struct.pack_into('<II', b0, 2, yo, yo if objetivo is None else objetivo)
    struct.pack_into('<H', b0, 18, cast_time & 0xFFFF)
    b0[20] = 1 if es_magia else 2
    struct.pack_into('<H', b0, 21, tipo & 0xFFFF)
    return struct.pack('<H', 0x0011) + bytes(b0)


def efecto_magia_self_cierre(yo: int, ef: int, tipo: int,
                             tile_x: int = 0, tile_y: int = 0) -> bytes:
    """Tercera linea del 0x0011, solo en las curaciones.

    Injury Cure manda una fase 0x80 extra con anim=0, ademas de la normal con
    anim=2. A diferencia de las otras dos, esta SI lleva la casilla del
    jugador en los campos de posicion. Medido en mundo_204956_255129 t=416.59:
    92 80 | 1e010000 | 1e010000 | 86000000 | 57000000 | 0000 | 00 | 5b02
    """
    b = bytearray(23)
    b[0] = ef & 0xFF
    b[1] = 0x80 | ((ef >> 8) & 0x0F)
    struct.pack_into('<II', b, 2, yo, yo)
    struct.pack_into('<II', b, 10, tile_x, tile_y)
    struct.pack_into('<H', b, 18, 0)
    b[20] = 0
    struct.pack_into('<H', b, 21, tipo & 0xFFFF)
    return struct.pack('<H', 0x0011) + bytes(b)


def entidad_aliada(entidad: int, a: int = 30, b: int = 15) -> bytes:
    """0x0006: le dice al cliente que esa entidad pasa a ser ALIADA.

    Es lo que faltaba para que el Shining Charm quedara bien. Mandando
    solo el buff y el dueño, el cliente seguia tratando al bicho como
    enemigo: lo apuntaba y pedia el golpe dos veces por segundo, y el
    servidor tenia que rechazarlo uno a uno.

    MEDIDO en mundo_234602_153654_orden.jsonl, lanzando Shining Charm I
    (303) sobre la entidad 1025332 ("Burning Criminal"). El servidor real
    contesta, por este orden:

        s2c 0x0013  el HP del bicho al 100%
        s2c 0x0013  el MP que le costo al jugador
        s2c 0x0006  010034a50f001e0000000f0000000000   <- ESTE
        s2c 0x0011  el efecto visual, con el 303 detras
        s2c 0x001D  kind 3, cooldown 2000
        s2c 0x001D  kind 4, duracion 600494 ms (el 持續時間=600 del xml)

    La forma es [u16 1][u32 entidad][u32 30][u32 15][u16 0]. El 30 y el 15
    NO se han identificado: no son el nivel del bicho (83) ni sus rangos de
    movimiento y ataque (6 y 1) ni su casilla. Hay una sola muestra, asi
    que van tal cual salieron y por eso son parametros.
    """
    return struct.pack('<HHIIIH', 0x0006, 1, int(entidad) & 0xFFFFFFFF,
                       int(a) & 0xFFFFFFFF, int(b) & 0xFFFFFFFF, 0)


def efecto_magia_self_fin(yo: int, ef: int, tipo: int, objetivo: int = None,
                          es_magia: bool = False) -> bytes:
    """Fase 0x80 del efecto visual 0x0011 de un buff (ver el de inicio)."""
    b1 = bytearray(23)
    b1[0] = ef & 0xFF
    b1[1] = 0x80 | ((ef >> 8) & 0x0F)
    struct.pack_into('<II', b1, 2, yo, yo if objetivo is None else objetivo)
    struct.pack_into('<H', b1, 18, 0)
    b1[20] = 1 if es_magia else 2
    struct.pack_into('<H', b1, 21, tipo & 0xFFFF)
    return struct.pack('<H', 0x0011) + bytes(b1)


def efecto_magia_self(yo: int, ef: int, tipo: int, cast_time: int = 100):
    """Efecto visual 0x0011 al castear un buff sobre si mismo (ambas fases retrocompatible)."""
    return [efecto_magia_self_inicio(yo, ef, tipo, cast_time),
            efecto_magia_self_fin(yo, ef, tipo)]


_ITEM_PROC_CACHE = {}


def _fila_magia_dict(con, mid: int) -> dict:
    d = {}
    try:
        cols = [c[1] for c in con.execute('pragma table_info(magic)').fetchall()]
        row = con.execute('select * from magic where id=?', (str(mid),)).fetchone()
        if row:
            for k_col, v_col in zip(cols, row):
                if v_col is not None and str(v_col).strip() != '':
                    d[k_col] = v_col
    except Exception:
        pass
    d_xml = _magic_xml().get(int(mid or 0))
    if d_xml:
        d.update(d_xml)
    return d


def proc_de_item(item_id: int) -> dict:
    """Devuelve la definicion del proc Formula 47 (常駐法術) de un item equipado, o {}."""
    global _ITEM_PROC_CACHE
    if not item_id:
        return {}
    iid = int(item_id)
    if iid in _ITEM_PROC_CACHE:
        return _ITEM_PROC_CACHE[iid]
    res = {}
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if db.exists():
        try:
            import inventario as _iv
            con = sqlite3.connect(db)
            row = _iv.fila_item(con, '"常駐法術","物品類別"', iid)
            if row and row[0] and str(row[0]).strip().isdigit():
                res_mid = int(str(row[0]).strip())
                d = _fila_magia_dict(con, res_mid)
                if d and str(d.get('公式') or '') == '47':
                    prob_s = str(d.get('動態參數1') or '10').strip()
                    proc_id_s = str(d.get('動態參數2') or '').strip()
                    if proc_id_s.isdigit():
                        proc_id = int(proc_id_s)
                        prob = int(float(prob_s)) if prob_s else 10
                        weap_req = str(d.get('武器限制') or d.get('裝備限制1') or '').strip()
                        trig_atk = str(d.get('法術觸發1') or '') == '1'
                        trig_sk = str(d.get('法術觸發2') or '') == '1'
                        proc_d = _fila_magia_dict(con, proc_id)
                        # Si el hechizo intermedio es Formula 49 (verificador de arma equipada),
                        # recoge su restriccion de arma y salta al hechizo de efecto real en 動態參數2!
                        if str(proc_d.get('公式') or '') == '49':
                            if not weap_req:
                                weap_req = str(proc_d.get('裝備限制1') or proc_d.get('武器限制') or '').strip()
                            sub_id_s = str(proc_d.get('動態參數2') or '').strip()
                            if sub_id_s.isdigit():
                                proc_id = int(sub_id_s)
                                proc_d = _fila_magia_dict(con, proc_id)
                        proc_mag = datos_magia(proc_id)
                        hp_def = str(proc_d.get('HP定義') or '')
                        mp_def = str(proc_d.get('MP定義') or '')
                        hp_val = int(float(proc_d.get('hp') or proc_d.get('HP') or 0)) if str(proc_d.get('hp') or proc_d.get('HP') or '').lstrip('-').isdigit() else 0
                        mp_val = int(float(proc_d.get('mp') or proc_d.get('MP') or 0)) if str(proc_d.get('mp') or proc_d.get('MP') or '').lstrip('-').isdigit() else 0
                        atk_val = int(float(proc_d.get('atk') or proc_d.get('攻擊') or proc_d.get('攻擊力') or 0)) if str(proc_d.get('atk') or proc_d.get('攻擊') or proc_d.get('攻擊力') or '').lstrip('-').isdigit() else 0
                        if atk_val and not proc_mag.get('atk_bonus'):
                            proc_mag = dict(proc_mag)
                            proc_mag['atk_bonus'] = atk_val
                        res = {
                            'res_id': res_mid,
                            'proc_id': proc_id,
                            'prob': max(1, min(100, prob)),
                            'weap_req': weap_req,
                            'trig_atk': trig_atk or (not trig_sk),
                            'trig_sk': trig_sk,
                            'hp_cura': hp_val if hp_def == '數值' and hp_val > 0 else 0,
                            'mp_cura': mp_val if mp_def == '數值' and mp_val > 0 else 0,
                            'dur_ms': int(proc_mag.get('dur_ms') or 0),
                            'efecto': int(proc_mag.get('efecto') or 251),
                            'mag': proc_mag,
                        }
        except Exception:
            pass
    _ITEM_PROC_CACHE[iid] = res
    return res


def procs_de_equipo(bolsa: dict, es_skill: bool = False) -> list:
    """Lista de procs Formula 47 activos en el equipo del personaje que cumplen la restriccion de arma."""
    if not bolsa:
        return []
    import inventario as _iv
    arma_id = int(bolsa.get(3) or bolsa.get('3') or 0)
    arma_cat = _iv.categoria_item(arma_id) if arma_id else ''
    activos = []
    for r, iid in bolsa.items():
        try:
            rn = int(r)
        except (TypeError, ValueError):
            continue
        if not _iv.es_equipo(rn) or not iid:
            continue
        pinfo = proc_de_item(int(iid))
        if not pinfo:
            continue
        if es_skill and not pinfo.get('trig_sk'):
            continue
        if (not es_skill) and not pinfo.get('trig_atk'):
            continue
        wreq = pinfo.get('weap_req') or ''
        if wreq:
            # Mapear sinonimos de categoria de arma (e.g. 劍/刀, 斧/錘, 弓/弓箭)
            if wreq == '劍' and not any(k in arma_cat for k in ('劍', '刀')):
                continue
            elif wreq == '斧' and not any(k in arma_cat for k in ('斧', '錘', '锤')):
                continue
            elif wreq == '槍' and '槍' not in arma_cat:
                continue
            elif wreq == '弓' and '弓' not in arma_cat:
                continue
            elif wreq == '杖' and '杖' not in arma_cat:
                continue
            elif wreq == '影刃' and '影刃' not in arma_cat:
                continue
            elif wreq not in arma_cat:
                continue
        activos.append(pinfo)
    return activos

