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
# Lo que el servidor contesta al clic para FIJAR el objetivo. Es una constante:
# aparece igual (01 00 06 03) en todos los clics sobre monstruos de la captura.
# Sin esto el cliente no llega a mandar el 0x0006 y parece que no deja atacar.
OBJETIVO_FIJADO = 0x03060001
VIDA = 0                    # kind del 0x0013
SEGUNDOS_REAPARICION = 20
# Lo que le baja al atacante en cada golpe (kind 2 del 0x0013). En la captura
# iba de 864 a 861 y a 857: unas pocas unidades por golpe.
KIND_ESFUERZO = 2
COSTE_GOLPE = 4
_MON = None


def _datos(npc_type: int):
    """{hp, atk, var, def, exp} del monstruo, o None si no esta en monster.xml."""
    global _MON
    if _MON is None:
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        _MON = {}
        if db.exists():
            con = sqlite3.connect(db)
            for i, n, hp, a, v, d, ev in con.execute(
                    'select id,name,hp,atk_avg,atk_var,def,exp_value from monster '
                    "where id glob '[0-9]*'"):
                def _n(x):
                    try:
                        return int(float(x))
                    except (TypeError, ValueError):
                        return 0
                _MON[int(i)] = {'nombre': n, 'hp': _n(hp) or 1, 'atk': _n(a),
                                'var': _n(v), 'def': _n(d), 'exp': _n(ev) or 25}
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
        self.spawn_tile = list(tile)
        d = _datos(npc_type) or {'hp': 50, 'atk': 5, 'var': 1, 'def': 0}
        self.hp_max = d['hp']
        self.hp = d['hp']
        self.atk = d['atk']
        self.var = d['var']
        self.defensa = d['def']
        self.muerto_en = None

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
    res = {'id': magic_id, 'nombre': '', 'mp': 0, 'sp': COSTE_GOLPE, 'efecto': EFECTO_GOLPE, 'hp': 0, 'es_auto': False}
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
                target = str(d.get('對象') or '')
                res['es_auto'] = ('自己' in target or '自己' in str(d.get('desc') or ''))
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


def numero_de_dano(atacante: int, objetivo: int, dano: int,
                   ataque: int = ATAQUE_NORMAL, efecto: int = EFECTO_GOLPE):
    """Los dos 0x0011 que dibujan el numero del golpe."""
    def _uno(fase, valor):
        b = bytearray(23)
        b[0] = efecto
        b[1] = fase
        struct.pack_into('<II', b, 2, atacante, objetivo)
        struct.pack_into('<H', b, 18, valor)
        b[20] = 2
        struct.pack_into('<H', b, 21, ataque)
        return struct.pack('<H', 0x0011) + bytes(b)
    return [_uno(0x00, dano), _uno(0x80, 0)]
