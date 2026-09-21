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
KIND_MP = 2                 # MP actual del jugador (medido en 70/70 capturas de AngelWar)
KIND_SP = 4                 # Puntos de SP acumulados del jugador (0..max_sp*1000)
KIND_EXP = 4                # Alias retrocompatible
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
           'cast_time': 100, 'crit_rate': 0, 'phys_mit': 0, 'mag_mit': 0,
           'es_auto': False, 'es_cura': False, 'es_buff': False,
           'es_ataque': False, 'es_pasiva': False}
    if db.exists():
        try:
            con = sqlite3.connect(db)
            cols = [c[1] for c in con.execute('pragma table_info(magic)').fetchall()]
            row = con.execute('select * from magic where id=?', (str(magic_id),)).fetchone()
            if row:
                d = dict(zip(cols, row))
                res['nombre'] = d.get('name') or ''
                def _num(val, default=0):
                    try: return int(float(val)) if val is not None and str(val).strip() else default
                    except (ValueError, TypeError): return default

                res['mp'] = _num(d.get('消耗MP'), 0)
                res['cost_sp'] = _num(d.get('消耗SP燈') or d.get('cost_sp'), 0)
                res['sp'] = res['cost_sp']
                res['efecto'] = _num(d.get('特效編號'), EFECTO_GOLPE)
                res['hp'] = _num(d.get('hp'), 0)
                res['cd_ms'] = _num(d.get('後置時間'), 1000)
                dur_val = _num(d.get('持續時間'), 0)
                res['dur_ms'] = (dur_val * 1000) if (0 < dur_val < 1000) else dur_val
                res['cast_time'] = _num(d.get('前置時間'), 100)
                res['rango'] = _num(d.get('射程'), 1)
                res['crit_rate'] = _num(d.get('crit_rate'), 0)
                res['phys_mit'] = _num(d.get('物理傷害抵銷'), 0)
                res['mag_mit'] = _num(d.get('魔法傷害抵銷'), 0)

                target = str(d.get('對象') or '')
                desc = str(d.get('desc') or '')
                act = str(d.get('施展動作') or '')
                res['accion'] = act

                nom_l = res['nombre'].lower()
                desc_l = desc.lower()

                # Curacion directa solo si es un hechizo curativo real (ej. Cure Spell, Holy Light, Angel Prayer, Tears of Life)
                # Las habilidades basicas como Injury Cure son buffs con regeneracion, no curas directas verdes
                res['es_cura'] = (
                    any(k in nom_l for k in ('cure spell', 'holy light', 'angel prayer', 'tears of life')) or
                    ('restores hp' in desc_l and 'speed' not in desc_l and 'injury' not in nom_l and 'song' not in nom_l)
                ) and d.get('攻擊型') != '是'

                # Buff temporal (aumenta defensa, velocidad, critico, % reduccion de dano, etc.)
                res['es_buff'] = (
                    res['dur_ms'] > 0 or
                    target == '自己' or
                    res['crit_rate'] > 0 or
                    res['phys_mit'] > 0 or
                    ('within the effective time' in desc_l or 'increase' in desc_l or 'raises' in desc_l or 'enhances' in desc_l)
                ) and not (d.get('攻擊型') == '是' or 'harm' in desc_l) and not res['es_cura']

                # Habilidad ofensiva de ataque (dano a enemigo, estun, etc.)
                res['es_ataque'] = (not res['es_cura']) and (not res['es_buff']) and (
                    d.get('攻擊型') == '是' or
                    any(k in desc_l for k in ('attack', 'attacks', 'harm', 'laceration', 'damage', 'shoot', 'strike', 'repulse', 'stun', 'pierce')) or
                    any(k in nom_l for k in ('hit', 'attack', 'chop', 'beating', 'slash', 'wave', 'bomb', 'shot', 'thrust', 'strike', 'killing'))
                )

                # Se puede usar sobre uno mismo si es curacion o buff
                res['es_auto'] = res['es_cura'] or res['es_buff']

                res['es_pasiva'] = (
                    d.get('被動') == '是' or
                    (act in ('無動作', '', 'None') and not res['es_ataque'] and not res['es_cura'] and not res['es_auto']) or
                    any(k in nom_l for k in ('enhance', 'grapple', 'reserve', 'finesse', 'garment', 'mastery'))
                )
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


def confirmar_cast(target: int, x: int, y: int, tipo: int = 1) -> bytes:
    """0x0006 s2c: confirma el cast y dice sobre que casilla ocurre.

    Medido: 01 00 | dd 7c 0f 00 | 75 00 00 00 | cd 00 00 00 | 00 00
    es decir [u2 tipo][u4 target][u4 x][u4 y][u2 0]. Antes se armaba con un
    formato inventado de 15 bytes que no correspondia a nada.
    """
    return struct.pack('<HHIIIH', 0x0006, tipo & 0xFFFF, target, x, y, 0)


TIPO_GOLPE = 1
TIPO_GOLPE_ALT = 3
TIPO_MUERTE = 7


def ataque(source: int, target: int, animacion: int = 0,
           tipo: int = TIPO_GOLPE) -> bytes:
    """0x000A: un golpe de `source` sobre `target` con su animacion."""
    return struct.pack('<HIIHH', 0x000A, source, target,
                       tipo & 0xFFFF, animacion & 0xFFFF)


TIPO_DANO = 1
TIPO_DANO_ALT = 2      # aparece tambien un tipo 2 en la misma captura


def numero_flotante(entity_id: int, cantidad: int, tipo: int = TIPO_DANO) -> bytes:
    """0x000B: el numero que flota sobre `entity_id`. Mismo formato que exp_paquete."""
    return struct.pack('<HIBIH', 0x000B, entity_id, tipo,
                       max(0, min(0xFFFFFFFF, int(cantidad))), 0)


def numero_de_dano(atacante: int, objetivo: int, dano: int,
                   ataque: int = ATAQUE_NORMAL, efecto: int = EFECTO_GOLPE):
    """Sub-mensaje 0x0011 que dibuja el numero del golpe y reproduce el sprite de ataque (fase 0x00)."""
    b0 = bytearray(23)
    b0[0] = efecto & 0xFF
    b0[1] = 0x00  # Fase 0: dibuja el numero de dano en pantalla y reproduce la animacion
    struct.pack_into('<II', b0, 2, atacante, objetivo)
    struct.pack_into('<H', b0, 18, max(0, min(65535, dano)))
    b0[20] = 2
    struct.pack_into('<H', b0, 21, ataque & 0xFFFF)
    return struct.pack('<H', 0x0011) + bytes(b0)


def cierre_de_dano(atacante: int, objetivo: int,
                   ataque: int = ATAQUE_NORMAL, efecto: int = EFECTO_GOLPE):
    """Sub-mensaje 0x0011 fase 0x80 que concluye el impacto tras reproducir el efecto."""
    b1 = bytearray(23)
    b1[0] = efecto & 0xFF
    b1[1] = 0x80  # Fase 0x80: cierre del impacto con dano 0
    struct.pack_into('<II', b1, 2, atacante, objetivo)
    struct.pack_into('<H', b1, 18, 0)
    b1[20] = 2
    struct.pack_into('<H', b1, 21, ataque & 0xFFFF)
    return struct.pack('<H', 0x0011) + bytes(b1)


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
    """Opcode 0x0149 (329 decimal): animacion de cooldown global (GCD)."""
    return struct.pack('<HIIIIIIIIBBH', 0x0149, 1, 0, 500, 0, 0, 0, 0, 0, 5, 255, 255)


def efecto_magia_self_inicio(yo: int, ef: int, tipo: int, cast_time: int = 100) -> bytes:
    """Fase 0x00 del efecto visual 0x0011 de buff sobre si mismo."""
    b0 = bytearray(23)
    b0[0] = ef & 0xFF
    b0[1] = 0x00
    struct.pack_into('<II', b0, 2, yo, yo)
    struct.pack_into('<H', b0, 18, cast_time & 0xFFFF)
    b0[20] = 2
    struct.pack_into('<H', b0, 21, tipo & 0xFFFF)
    return struct.pack('<H', 0x0011) + bytes(b0)


def efecto_magia_self_fin(yo: int, ef: int, tipo: int) -> bytes:
    """Fase 0x80 del efecto visual 0x0011 de buff sobre si mismo."""
    b1 = bytearray(23)
    b1[0] = ef & 0xFF
    b1[1] = 0x80
    struct.pack_into('<II', b1, 2, yo, yo)
    struct.pack_into('<H', b1, 18, 0)
    b1[20] = 2
    struct.pack_into('<H', b1, 21, tipo & 0xFFFF)
    return struct.pack('<H', 0x0011) + bytes(b1)


def efecto_magia_self(yo: int, ef: int, tipo: int, cast_time: int = 100):
    """Efecto visual 0x0011 al castear un buff sobre si mismo (ambas fases retrocompatible)."""
    return [efecto_magia_self_inicio(yo, ef, tipo, cast_time),
            efecto_magia_self_fin(yo, ef, tipo)]
