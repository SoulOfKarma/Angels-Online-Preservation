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
import pathlib
import random
import sqlite3
import struct
import time

ATAQUE_NORMAL = 656
OBJETIVO_FIJADO = 0x03060001
VIDA = 0                    # kind 0 del 0x0013: HP (o % en monstruos)
KIND_HP = 0                 # HP actual del jugador / % del monstruo
KIND_SP = 2                 # SP / esfuerzo del jugador
KIND_MP = 3                 # MP actual del jugador
KIND_EXP = 4                # EXP total acumulada del jugador
KIND_ESFUERZO = 2
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
                    'exp': _n(d.get('exp_value')) or 25,
                    'atk_range': _n(d.get('atk_range')) or 1,
                    'proj_ef': _n(d.get('投射特效')) or 0,
                    'move_speed': _n(d.get('move_speed')),
                    'move_range': _n(d.get('move_range')) or 6,
                }
    return _MON.get(npc_type)



_CURVA_NIVEL = None

def _cargar_curva_nivel():
    global _CURVA_NIVEL
    if _CURVA_NIVEL is None:
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        _CURVA_NIVEL = {}
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


def exp_para_nivel(nv: int) -> int:
    curva = _cargar_curva_nivel()
    return curva.get(nv, nv * 120)


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


def atributo(entity_id: int, valor: int, kind: int = VIDA) -> bytes:
    """Sub-mensaje 0x0013: un atributo de una entidad cambio."""
    return struct.pack('<HIBBI', 0x0013, entity_id, 1, kind, valor)


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


def parsear_ataque(cuerpo: bytes):
    """(tipo_de_ataque, entity del objetivo) del 0x0006 del mundo."""
    if len(cuerpo) < 4:
        return None
    tipo, objetivo = struct.unpack_from('<HH', cuerpo, 0)
    return (tipo, objetivo)


class Monstruo:
    """Un bicho vivo en el mapa."""

    def __init__(self, entity_id, npc_type, nombre, tile):
        self.entity_id = entity_id
        self.npc_type = npc_type
        self.nombre = nombre
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
        self.atk_range = d.get('atk_range', 1)
        self.proj_ef = d.get('proj_ef', 0)
        self.move_speed = d.get('move_speed', 50)
        self.move_range = d.get('move_range', 6)
        # Las Lilys no se mueven de su lugar pero atacan a distancia como arqueros
        self.es_estatico = ('lily' in nombre.lower() or self.move_speed == 0)
        self.muerto_en = None
        self.en_combate_con = None
        self.ultimo_ataque = 0.0

    @property
    def vivo(self):
        return self.hp > 0

    @property
    def porcentaje(self):
        return max(0, min(100, round(100 * self.hp / self.hp_max)))

    def recibir(self, ataque: int) -> int:
        """Aplica el dano y devuelve cuanto pego de verdad."""
        d = max(1, ataque - self.defensa)
        self.hp = max(0, self.hp - d)
        if not self.hp:
            self.muerto_en = time.time()
            self.en_combate_con = None
        return d

    def pegar(self) -> int:
        return max(1, self.atk + random.randint(-self.var, self.var))

    def toca_reaparecer(self) -> bool:
        return (not self.vivo and self.muerto_en
                and time.time() - self.muerto_en >= SEGUNDOS_REAPARICION)

    def revivir(self):
        self.hp = self.hp_max
        self.muerto_en = None
        self.tile = list(self.spawn_tile)
        self.tile_x = self.spawn_x
        self.tile_y = self.spawn_y
        self.en_combate_con = None
        self.ultimo_ataque = 0.0



def botin(nivel_monstruo: int = 1) -> int:
    """Cuanto oro suelta. Aplica el multiplicador de configuracion."""
    import configuracion
    base = random.randint(3, 8)
    return max(1, int(round(base * configuracion.TASA_ORO_BASE)))


_DROPS_CACHE = {}


def botin_items(npc_type: int) -> list:
    """Items que suelta el monstruo de drop_table con multiplicador de drops."""
    global _DROPS_CACHE
    if npc_type in _DROPS_CACHE:
        candidatos = _DROPS_CACHE[npc_type]
    else:
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        candidatos = []
        if db.exists():
            try:
                con = sqlite3.connect(db)
                mrow = con.execute('select drop_id from monster where id=?', (str(npc_type),)).fetchone()
                if mrow and mrow[0]:
                    did = str(mrow[0]).strip()
                    dt = con.execute('select * from drop_table where id=?', (did,)).fetchone()
                    if dt:
                        cols = [c[1] for c in con.execute('pragma table_info(drop_table)').fetchall()]
                        row_dict = dict(zip(cols, dt))
                        for i in range(1, 9):
                            it = row_dict.get(f'item{i}')
                            cnt = row_dict.get(f'count{i}')
                            if it and str(it).isdigit():
                                c_val = int(cnt) if cnt and str(cnt).isdigit() else 1
                                candidatos.append((int(it), c_val))
            except Exception:
                pass
        _DROPS_CACHE[npc_type] = candidatos

    import configuracion
    prob = min(0.95, 0.70 * configuracion.multiplicador_drop())
    drops = []
    if candidatos and random.random() < prob:
        drops.append(random.choice(candidatos))
    return drops


_MAGIC_CACHE = {}


def datos_magia(magic_id: int) -> dict:
    """Informacion del hechizo/skill desde magic.xml."""
    global _MAGIC_CACHE
    if magic_id in _MAGIC_CACHE:
        return _MAGIC_CACHE[magic_id]
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    res = {'id': magic_id, 'nombre': '', 'mp': 0, 'sp': COSTE_GOLPE,
           'efecto': EFECTO_GOLPE, 'hp': 0, 'cd_ms': 1000, 'dur_ms': 0,
           'es_auto': False, 'es_cura': False}
    if db.exists():
        try:
            con = sqlite3.connect(db)
            cols = [c[1] for c in con.execute('pragma table_info(magic)').fetchall()]
            row = con.execute('select * from magic where id=?', (str(magic_id),)).fetchone()
            if row:
                d = dict(zip(cols, row))
                res['nombre'] = d.get('name') or ''
                try: res['mp'] = int(float(d.get('消耗MP') or 0))
                except ValueError: res['mp'] = 0
                try: res['sp'] = int(float(d.get('消耗SP') or COSTE_GOLPE))
                except ValueError: res['sp'] = COSTE_GOLPE
                try: res['efecto'] = int(float(d.get('特效編號') or EFECTO_GOLPE))
                except ValueError: res['efecto'] = EFECTO_GOLPE
                try: res['hp'] = int(float(d.get('hp') or 0))
                except ValueError: res['hp'] = 0
                try: res['cd_ms'] = int(float(d.get('後置時間') or 1000))
                except ValueError: res['cd_ms'] = 1000
                try:
                    dur_val = int(float(d.get('持續時間') or 0))
                    res['dur_ms'] = (dur_val * 1000) if dur_val < 1000 else dur_val
                except ValueError: res['dur_ms'] = 0
                try: res['rango'] = int(float(d.get('射程') or 1))
                except ValueError: res['rango'] = 1

                target = str(d.get('對象') or '')
                desc = str(d.get('desc') or '')
                nom = res['nombre']
                act = str(d.get('施展動作') or '')
                res['accion'] = act
                hp_def = str(d.get('HP定義') or '')

                # Una habilidad de ataque tiene 攻擊型='是' o accion de ataque/disparo
                es_atk_flag = (d.get('攻擊型') == '是')
                res['es_ataque'] = (es_atk_flag or '攻擊' in act or '射擊' in act)
                # Curacion solo si NO es ataque ofensivo y tiene definicion de HP o nombre curativo
                res['es_cura'] = (not res['es_ataque'] and (
                    '數值' in hp_def or '最大值' in hp_def or
                    any(k in nom.lower() for k in ('heal', 'prayer', 'cure', 'recovery', 'sanctuary', 'tears'))
                ))
                res['es_auto'] = ('自己' in target or target == '自己')
        except Exception:
            pass
    _MAGIC_CACHE[magic_id] = res
    return res




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


def efecto_de_ataque(magic_id: int) -> int:
    """Devuelve el numero de efecto visual para este ataque o skill de magic.xml."""
    global _EFECTOS_CACHE
    if magic_id in _EFECTOS_CACHE:
        return _EFECTOS_CACHE[magic_id]
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


def ataque_estandar_arma(item_id: int) -> tuple:
    """Devuelve (magic_id, efecto_visual) segun el arma equipada."""
    global _WEAPON_ATTACK_CACHE
    if not item_id:
        return (656, 136)
    if item_id in _WEAPON_ATTACK_CACHE:
        return _WEAPON_ATTACK_CACHE[item_id]
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    res = (656, 136)
    if db.exists():
        try:
            con = sqlite3.connect(db)
            row = con.execute('select "物品類別" from item where id=?', (str(item_id),)).fetchone()
            if row and row[0]:
                cat = str(row[0])
                if '槍' in cat:   # Lanza / Spear (2 manos): Spear Hacking I
                    res = (809, 198)
                elif '錘' in cat:  # Maza / Martillo
                    res = (734, 138)
                elif '弓' in cat:  # Arco
                    res = (771, 140)
                elif '杖' in cat:  # Baculo / Baston
                    res = (807, 165)
                else:             # Espada, Daga, Hacha
                    res = (656, 136)
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


def numero_de_dano(atacante: int, objetivo: int, dano: int,
                   ataque: int = ATAQUE_NORMAL, efecto: int = EFECTO_GOLPE):
    """Sub-mensaje 0x0011 que dibuja el numero del golpe flotante en pantalla (fase 0x00 y fase 0x80)."""
    b0 = bytearray(23)
    b0[0] = efecto & 0xFF
    b0[1] = 0x00  # Fase 0: dibuja el numero de dano en pantalla
    struct.pack_into('<II', b0, 2, atacante, objetivo)
    struct.pack_into('<H', b0, 18, max(0, min(65535, dano)))
    b0[20] = 2
    struct.pack_into('<H', b0, 21, ataque & 0xFFFF)

    b1 = bytearray(23)
    b1[0] = efecto & 0xFF
    b1[1] = 0x80  # Fase 0x80: cierre del impacto con dano 0
    struct.pack_into('<II', b1, 2, atacante, objetivo)
    struct.pack_into('<H', b1, 18, 0)
    b1[20] = 2
    struct.pack_into('<H', b1, 21, ataque & 0xFFFF)

    return [struct.pack('<H', 0x0011) + bytes(b0), struct.pack('<H', 0x0011) + bytes(b1)]


def efecto_curacion(atacante: int, objetivo: int, cura_hp: int, efecto: int = 165):
    """Efecto visual de curacion 0x0011 sin golpe ofensivo (fase 0x00 y fase 0x80)."""
    b0 = bytearray(23)
    b0[0] = efecto & 0xFF
    b0[1] = 0x00
    struct.pack_into('<II', b0, 2, atacante, objetivo)
    struct.pack_into('<H', b0, 18, max(0, min(65535, cura_hp)))
    b0[20] = 1  # Tipo 1 (cura/verde)
    struct.pack_into('<H', b0, 21, 0)

    b1 = bytearray(23)
    b1[0] = efecto & 0xFF
    b1[1] = 0x80
    struct.pack_into('<II', b1, 2, atacante, objetivo)
    struct.pack_into('<H', b1, 18, 0)
    b1[20] = 1
    struct.pack_into('<H', b1, 21, 0)

    return [struct.pack('<H', 0x0011) + bytes(b0), struct.pack('<H', 0x0011) + bytes(b1)]


