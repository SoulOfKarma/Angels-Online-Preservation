"""Mascotas: el bloque de estado que el cliente usa para su ficha.

Todo lo de aqui sale de una captura del 29/09/2026 en la que se invoco una
mascota, se compro otra y se habilito una tercera. Los opcodes que aparecen:

    c2s 0x015E  [u8]        invocar o guardar la mascota
    c2s 0x003E  [u8]        orden a la mascota (atacar, seguir...)
    c2s 0x012D  (vacio)     abrir la lista de la tienda -> s2c 0x005F
    c2s 0x012B  [u32]       comprar -> s2c 0x0062 (oro) + 0x0061 (item)
    s2c 0x0065  200 bytes   ESTADO DE LA MASCOTA, que es lo que hay aqui
    s2c 0x0062  4 bytes     el oro que queda
    s2c 0x0061              el objeto comprado

El 0x0065 se mando setenta y tres veces en esa sesion: es el que pinta la
ficha. Su formato se saco comparando los bytes contra la ficha que el juego
enseñaba en ese momento -- una Battlemaid de nivel 246 con 37.550 de HP,
12.100 de ataque, 15.755 de defensa, 3.137 de ataque magico, 4.431 de defensa
magica, 1.947 de rigor, 1.127 de agilidad, 462 de saciedad y 78 de intimidad.
Todos esos numeros aparecieron, y por eso el mapa de abajo no es una
suposicion.

Cada stat viaja DOS VECES seguidas, en +83/+87, +91/+95 y asi. Es el valor
base y el efectivo, que es justo lo que la ventana enseña en sus dos
columnas: "Atk 12100" y "T.Atk 0".

Los dos u32 de +8 y +12 valen los dos la INSTANCIA del item en la mochila
(1167 para la Battlemaid, el mismo numero que lleva su entrada), y el u16 de
+16 es el sprite, que tambien esta en el +131 de la entrada. Se vio en
mundo_022355_871035, sacando y guardando la misma mascota.

El MP actual no esta aqui, pero si en la entrada del inventario, en el +127.
"""
import json
import pathlib
import struct

TAM = 200

# Donde vive cada cosa dentro del bloque.
OFF = {
    'entidad': 0,
    'tipo': 4,
    'instancia': 8,      # la del item en la mochila, repetida en el 12
    'sprite': 16,        # u16
    'nombre': 18,        # ASCIIZ
    'nivel': 31,
    'exp': 35,
    'exp_max': 51,
    'hp': 59,
    'mp': 63,
    'hp_max': 71,
    'mp_max': 79,
    'atk': 83,
    'dfs': 91,
    'matk': 99,
    'mdef': 107,
    'rigor': 115,
    'agilidad': 123,
    'saciedad': 177,     # u16
    'intimidad': 179,    # u8
    'estrellas': 196,    # u32 (1 = 0.1 estrellas)
}

# Los que van repetidos: primero el base y cuatro bytes despues el efectivo.
DOBLES = ('atk', 'dfs', 'matk', 'mdef', 'rigor', 'agilidad')

# Defensas elementales por defecto en Celestia (T.Atk/Dfs, F.Atk/Dfs, I.Atk/Dfs, R.Atk/Dfs)
DEFENSAS_ELEM_BASE = (0, 0, 60, 60, 0, 0, 60, 60, 0, 0, 60, 60, 0, 0, 60, 60)

# Cuanta saciedad hace falta para que la mascota mejore. Lo dice el Pet Feed:
# "Increases the satiation degree by 500. (The pet can enhance its abilities
# after the satiation degree is more than 100.)"
SACIEDAD_PARA_MEJORAR = 100
SACIEDAD_MAXIMA = 1000
SACIEDAD_POR_PIENSO = 500


def leer(cuerpo: bytes) -> dict:
    """Desmonta un 0x0065 en un diccionario."""
    if len(cuerpo) < TAM:
        return {}
    d = {}
    for campo, off in OFF.items():
        if campo == 'nombre':
            d[campo] = cuerpo[off:off + 13].split(b'\0')[0].decode(
                'latin1', 'replace')
        elif campo in ('saciedad', 'sprite'):
            d[campo] = struct.unpack_from('<H', cuerpo, off)[0]
        elif campo == 'intimidad':
            d[campo] = cuerpo[off]
        elif campo in ('exp', 'exp_max'):
            d[campo] = struct.unpack_from('<Q', cuerpo, off)[0]
        else:
            d[campo] = struct.unpack_from('<I', cuerpo, off)[0]
    d['skills'] = list(struct.unpack_from('<3H', cuerpo, 171))
    return d


_PET_STAR_TABLE = {}

def cargar_pet_star():
    global _PET_STAR_TABLE
    if _PET_STAR_TABLE:
        return _PET_STAR_TABLE
    import json, re
    f_json = pathlib.Path(__file__).parent / 'plantillas' / 'pet_star.json'
    if f_json.exists():
        try:
            raw = json.loads(f_json.read_text(encoding='utf-8'))
            for k, v in raw.items():
                _PET_STAR_TABLE[int(k)] = v
            if _PET_STAR_TABLE:
                return _PET_STAR_TABLE
        except Exception:
            pass
    base_dir = pathlib.Path(__file__).parent.parent / 'extracted_paks'
    files = list(base_dir.glob('**/pet_star.xml')) if base_dir.exists() else []
    def _up_num(p):
        m = re.search(r'update(\d+)', str(p), re.IGNORECASE)
        return int(m.group(1)) if m else 0
    files.sort(key=_up_num, reverse=True)
    for p in files:
        if p.exists():
            try:
                import xml.etree.ElementTree as ET
                tree = ET.parse(p)
                root = tree.getroot()
                for node in root.findall('寵物星等'):
                    idx = int(node.get('星等編號', 0))
                    if idx:
                        _PET_STAR_TABLE[idx] = {
                            'hp': int(node.get('HP', 0)),
                            'mp': int(node.get('MP', 0)),
                            'atk': int(node.get('攻擊', 0)),
                            'dfs': int(node.get('防禦', 0)),
                            'matk': int(node.get('魔攻', 0)),
                            'mdef': int(node.get('魔防', 0)),
                            'rigor': int(node.get('精準', 0)),
                            'agilidad': int(node.get('靈敏', 0)),
                        }
                if _PET_STAR_TABLE:
                    _PET_STAR_TABLE[1] = {'hp': 3, 'mp': 2, 'atk': 4, 'dfs': 2, 'matk': 2, 'mdef': 2, 'rigor': 2, 'agilidad': 1}
                    break
            except Exception:
                pass
    return _PET_STAR_TABLE

STATS_BONO = ('hp', 'mp', 'atk', 'dfs', 'matk', 'mdef', 'rigor', 'agilidad')


def estrella_de_bono(valor: int, stat_key: str) -> int:
    """Equivalente exacto de sub_716B10 en Angel.exe: busca en pet_star.xml
    el nivel de estrella (1..80) que corresponde al bono verde de ese stat."""
    v = int(valor or 0)
    if v <= 0:
        return 0
    tabla = cargar_pet_star()
    res = 1
    for i in range(1, 81):
        req = (tabla.get(i) or {}).get(stat_key, 0)
        if req <= v:
            res = i
        else:
            break
    return res


def calcular_estrellas_total(bonos: dict) -> int:
    """Media entera de las estrellas de los 8 stats (medido en las 5 mascotas de mundo_130439)."""
    if not bonos:
        return 1
    total = sum(estrella_de_bono(bonos.get(k, 0), k) for k in STATS_BONO)
    return max(1, total // 8)


def rangos_bonos_de(sprite: int) -> dict:
    """Devuelve {stat: (lo, hi)} de pet.xml para los stats que esa mascota tiene."""
    d = ficha_de_sprite(sprite)
    out = {}
    for k in STATS_BONO:
        lo = d.get(f'{k}_min')
        hi = d.get(f'{k}_max')
        if lo is not None and hi is not None and int(hi) > 0:
            out[k] = (int(lo), int(hi))
    if out:
        return out
    # Si es un huevo (原型) y aun no tiene rangos en su propia fila, mirar su primera evolucion
    for r_key in ('rama1', 'rama2'):
        r_sp = d.get(r_key)
        if r_sp:
            dr = ficha_de_sprite(r_sp)
            for k in STATS_BONO:
                lo = dr.get(f'{k}_min')
                hi = dr.get(f'{k}_max')
                if lo is not None and hi is not None and int(hi) > 0:
                    out[k] = (int(lo), int(hi))
            if out:
                return out
    # Si es una mascota 頂階 sin rangos propios, buscar otra de su misma clase (寵物類型)
    clase = d.get('clase') or TIPO_POR_DEFECTO
    for v in _tabla().values():
        if v.get('clase') == clase:
            for k in STATS_BONO:
                lo = v.get(f'{k}_min')
                hi = v.get(f'{k}_max')
                if lo is not None and hi is not None and int(hi) > 0:
                    out[k] = (int(lo), int(hi))
            if out:
                return out
    return {'hp': (51, 62), 'mp': (28, 34), 'atk': (27, 33), 'dfs': (23, 43)}


def sortear_bonos(sprite: int) -> dict:
    """Sortea los bonos verdes iniciales dentro del rango [lo, hi] de pet.xml."""
    import random
    rangos = rangos_bonos_de(sprite)
    return {k: random.randint(min(lo, hi), max(lo, hi)) for k, (lo, hi) in rangos.items()}


def bonos_estrellas(nivel_estrella: int, sprite: int = None, estado: dict = None) -> dict:
    """Devuelve los bonos verdes de una mascota.
    Si `estado` ya tiene `bonos` por stat (varia segun la mascota), usa esos."""
    if isinstance(estado, dict) and isinstance(estado.get('bonos'), dict):
        return estado['bonos']
    st = max(1, int(nivel_estrella or 1))
    if sprite:
        d = ficha_de_sprite(sprite)
        if d.get('etapa') == '原型' and st <= 1 and not (isinstance(estado, dict) and estado.get('mejoras')):
            return {}
        rangos = rangos_bonos_de(sprite)
        tabla = cargar_pet_star()
        fila_st = tabla.get(st, {})
        out = {}
        for idx_k, (k, (lo, hi)) in enumerate(rangos.items()):
            # Escalar segun el nivel de estrella manteniendo variacion entre stats
            var_st = max(1, min(80, st + ((idx_k % 3) - 1 if st > 1 else 0)))
            v_star = (tabla.get(var_st) or fila_st).get(k, 0)
            out[k] = max(lo, v_star) if st > 1 else (lo + hi) // 2
        return out
    if st <= 1:
        return {}
    tabla = cargar_pet_star()
    return tabla.get(st, {})


def bonos_de_ficha(estado: dict) -> dict:
    """Obtiene o inicializa el diccionario de bonos por stat de la mascota."""
    if not isinstance(estado, dict):
        return {}
    bonos = estado.get('bonos')
    if isinstance(bonos, dict):
        return bonos
    sp = int(estado.get('sprite') or 0)
    st = max(1, int(estado.get('estrellas') or 1))
    mej = int(estado.get('mejoras') or 0)
    d = ficha_de_sprite(sp)
    if d.get('etapa') == '原型' and st <= 1 and mej <= 0:
        return {}
    calc = bonos_estrellas(st, sprite=sp, estado=estado)
    if calc:
        estado['bonos'] = calc
    return calc


def totales(estado: dict) -> dict:
    """Los ocho stats TOTALES de la mascota (base + bono verde), los del
    tooltip: "Maximum MP 2074 (1541 + 533)". Los usa el Pet Amplify."""
    if not isinstance(estado, dict):
        return {}
    b = bonos_de_ficha(estado)
    base = {'hp': estado.get('hp_max') or estado.get('hp'), 'mp': estado.get('mp_max') or estado.get('mp')}
    for k in ('atk', 'dfs', 'matk', 'mdef', 'rigor', 'agilidad'):
        base[k] = estado.get(k)
    return {k: int(v or 0) + int(b.get(k, 0)) for k, v in base.items()}


def uid_cliente(estado: dict) -> int:
    """El id con el que el cliente conoce a la mascota (el +8 del 0x0065)."""
    inst = estado.get('instancia') if isinstance(estado, dict) else None
    if not inst and isinstance(estado, dict) and estado.get('ranura') is not None:
        inst = 1000 + int(estado['ranura'])
    return int(inst or 0) & 0xFFFFFFFF


def buffs_activos_de(estado: dict, ahora: float = None) -> dict:
    """Devuelve y limpia los buffs activos en estado['buffs'] cuyo 'fin' > ahora."""
    if not isinstance(estado, dict):
        return {}
    raw = estado.get('buffs')
    if not isinstance(raw, dict) or not raw:
        return {}
    import time as _t
    now = ahora if ahora is not None else _t.time()
    activos = {}
    for k, b in list(raw.items()):
        try:
            sk_id = int(k)
        except (ValueError, TypeError):
            raw.pop(k, None)
            continue
        if isinstance(b, dict) and float(b.get('fin') or 0) > now:
            activos[sk_id] = b
        else:
            raw.pop(k, None)
    return activos


def bonos_buffs(estado: dict, h_max_base: int = 0, m_max_base: int = 0) -> dict:
    """Calcula los bonos planos y porcentuales de los buffs activos sobre la mascota."""
    activos = buffs_activos_de(estado)
    out = {
        'hp_flat': 0, 'hp_pct': 0,
        'mp_flat': 0, 'mp_pct': 0,
        'atk': 0, 'dfs': 0, 'matk': 0, 'mdef': 0,
        'rigor': 0, 'agilidad': 0,
        'phys_dmg_pct': 0, 'mag_dmg_pct': 0,
        'phys_mit_pct': 0, 'mag_mit_pct': 0,
        'crit': 0, 'atk_speed': 0, 'move_speed': 0,
    }
    if not activos:
        return out
    for sk_id, b in activos.items():
        mag = b.get('mag') if isinstance(b.get('mag'), dict) else b
        out['hp_flat'] += int(b.get('hp_bonus') or mag.get('hp_bonus') or 0)
        out['hp_pct'] += int(b.get('hp_pct') or mag.get('hp_pct') or 0)
        out['mp_flat'] += int(b.get('mp_bonus') or mag.get('mp_bonus') or 0)
        out['mp_pct'] += int(b.get('mp_pct') or mag.get('mp_pct') or 0)
        out['atk'] += int(b.get('atk') or mag.get('atk_bonus') or 0)
        out['dfs'] += int(b.get('def') or mag.get('def_bonus') or 0)
        out['matk'] += int(b.get('matk') or mag.get('matk_bonus') or 0)
        out['mdef'] += int(b.get('mdef') or mag.get('mdef_bonus') or 0)
        out['phys_dmg_pct'] += int(b.get('phys_dmg_pct') or mag.get('phys_dmg_pct') or 0)
        out['mag_dmg_pct'] += int(b.get('mag_dmg_pct') or mag.get('mag_dmg_pct') or 0)
        out['phys_mit_pct'] += int(b.get('mit') or mag.get('phys_mit') or 0)
        out['mag_mit_pct'] += int(b.get('mag_mit') or mag.get('mag_mit') or 0)
        out['crit'] += int(b.get('crit') or mag.get('crit_rate') or 0)
        out['atk_speed'] += int(b.get('atk_speed_bonus') or mag.get('atk_speed_bonus') or 0)
        out['move_speed'] += int(b.get('move_speed_bonus') or mag.get('move_speed_bonus') or 0)
    if h_max_base > 0 and out['hp_pct'] > 0:
        out['hp_total'] = out['hp_flat'] + int(round(h_max_base * (out['hp_pct'] / 100.0)))
    else:
        out['hp_total'] = out['hp_flat']
    if m_max_base > 0 and out['mp_pct'] > 0:
        out['mp_total'] = out['mp_flat'] + int(round(m_max_base * (out['mp_pct'] / 100.0)))
    else:
        out['mp_total'] = out['mp_flat']
    return out


def paquetes_buffs(estado: dict, pet_eid: int = None) -> list:
    """Construye los paquetes 0x001D (kind=4) de todos los buffs activos en la mascota.
    Como sub_60ADC0 (0x0065) borra la lista de iconos de buff de WND_PET_INFO, estos
    paquetes se envian justo despues de cualquier 0x0065 para mantener los iconos visibles."""
    if not isinstance(estado, dict) or not estado.get('fuera'):
        return []
    eid = int(pet_eid or estado.get('entidad') or 0)
    if eid <= 0:
        return []
    import time as _t
    ahora = _t.time()
    pkgs = []
    sac = int(estado.get('saciedad') or 0)
    if sac > 100:
        dur_sac_ms = max(60000, (sac - 100) * 60000)
        pkgs.append(struct.pack('<HIBBII', 0x001D, eid, 1, 4, 3796, dur_sac_ms))
    b_exp = estado.get('buff_exp')
    if isinstance(b_exp, dict) and float(b_exp.get('fin') or 0) > ahora:
        rem_exp_ms = max(1000, int((float(b_exp['fin']) - ahora) * 1000))
        pkgs.append(struct.pack('<HIBBII', 0x001D, eid, 1, 4, int(b_exp.get('id') or 1866), rem_exp_ms))
    for sk_id, b in buffs_activos_de(estado, ahora=ahora).items():
        rem_ms = max(1000, int((float(b.get('fin') or 0) - ahora) * 1000))
        pkgs.append(struct.pack('<HIBBII', 0x001D, eid, 1, 4, int(sk_id), rem_ms))
    return pkgs


def hp_max_eff(estado: dict) -> int:
    """Devuelve el HP maximo efectivo de la mascota (incluyendo bono de estrella, Pet's Satiation > 100 y buffs activos)."""
    if not isinstance(estado, dict):
        return 127
    b_star = bonos_de_ficha(estado)
    hp_max = max(1, int(estado.get('hp_max') or estado.get('hp') or 127))
    val = hp_max + int(b_star.get('hp', 0))
    if int(estado.get('saciedad') or 0) > 100:
        val = int(round(val * 3.5))
    b_bf = bonos_buffs(estado, h_max_base=val)
    val += int(b_bf.get('hp_total', 0))
    return max(1, val)


def hp_eff(estado: dict) -> int:
    """Devuelve el HP actual efectivo de la mascota (escalado con estrella, Pet's Satiation > 100 y buffs activos)."""
    if not isinstance(estado, dict):
        return 127
    b_star = bonos_de_ficha(estado)
    hp_max = max(1, int(estado.get('hp_max') or estado.get('hp') or 127))
    hp = max(1, int(estado.get('hp') or hp_max))
    val = hp + int(b_star.get('hp', 0))
    h_max_s = hp_max + int(b_star.get('hp', 0))
    if int(estado.get('saciedad') or 0) > 100:
        val = int(round(val * 3.5))
        h_max_s = int(round(h_max_s * 3.5))
    b_bf = bonos_buffs(estado, h_max_base=h_max_s)
    val += int(b_bf.get('hp_total', 0))
    return max(1, min(hp_max_eff(estado), val))


def armar(estado: dict) -> bytes:
    """El 0x0065 con el estado de una mascota (sub_60ADC0 en Angel.exe)."""
    b = bytearray(TAM)
    nv = max(1, int(estado.get('nivel') or 1))
    sp = int(estado.get('sprite') or 0)
    b_star = bonos_de_ficha(estado)
    st_lvl = max(1, int(estado.get('estrellas') or calcular_estrellas_total(b_star)))
    mej = max(0, int(estado.get('mejoras') or 0))

    hp_max = max(1, int(estado.get('hp_max') or estado.get('hp') or 127))
    hp = max(1, int(estado.get('hp') or hp_max))
    mp_max = max(0, int(estado.get('mp_max') or estado.get('mp') or 70))
    mp = max(0, int(estado.get('mp') if estado.get('mp') is not None else mp_max))
    exp = max(0, int(estado.get('exp') or 0))
    exp_max = max(1, int(estado.get('exp_max') or exp_para_subir(nv, sp)))

    satiado = int(estado.get('saciedad') or 0) > 100
    h_eff = hp + int(b_star.get('hp', 0))
    m_eff = mp + int(b_star.get('mp', 0))
    h_max_eff = hp_max + int(b_star.get('hp', 0))
    m_max_eff = mp_max + int(b_star.get('mp', 0))
    if satiado:
        h_max_eff = int(round(h_max_eff * 3.5))
        m_max_eff = int(round(m_max_eff * 3.5))
        h_eff = min(h_max_eff, int(round(h_eff * 3.5)))
        m_eff = min(m_max_eff, int(round(m_eff * 3.5)))

    b_bf = bonos_buffs(estado, h_max_base=h_max_eff, m_max_base=m_max_eff)
    h_max_eff += int(b_bf.get('hp_total', 0))
    m_max_eff += int(b_bf.get('mp_total', 0))
    h_eff = min(h_max_eff, h_eff + int(b_bf.get('hp_total', 0)))
    m_eff = min(m_max_eff, m_eff + int(b_bf.get('mp_total', 0)))

    for campo, off in OFF.items():
        v = estado.get(campo)
        if v is None:
            continue
        if campo == 'nombre':
            nom = str(v).encode('latin1', 'replace')[:12]
            b[off:off + len(nom)] = nom
        elif campo in ('saciedad', 'sprite'):
            struct.pack_into('<H', b, off, min(0xFFFF, max(0, int(v))))
        elif campo == 'intimidad':
            b[off] = min(0xFF, max(0, int(v)))
        elif campo in ('exp', 'exp_max', 'hp', 'mp', 'hp_max', 'mp_max'):
            continue
        else:
            base_v = int(v)
            eff_v = base_v + int(b_star.get(campo, 0))
            if satiado and campo in DOBLES:
                if campo in ('atk', 'matk', 'dfs', 'mdef'):
                    eff_v = int(round(eff_v * 1.4))
                elif campo in ('rigor', 'agilidad'):
                    eff_v = int(round(eff_v * 1.2))
            if campo in DOBLES:
                eff_v += int(b_bf.get(campo, 0))
                if campo == 'atk' and b_bf.get('phys_dmg_pct'):
                    eff_v = int(round(eff_v * (1.0 + b_bf['phys_dmg_pct'] / 100.0)))
                elif campo == 'matk' and b_bf.get('mag_dmg_pct'):
                    eff_v = int(round(eff_v * (1.0 + b_bf['mag_dmg_pct'] / 100.0)))
            struct.pack_into('<I', b, off, base_v & 0xFFFFFFFF)
            if campo in DOBLES:
                struct.pack_into('<I', b, off + 4, max(0, eff_v) & 0xFFFFFFFF)

    # La instancia del item en la mochila se repite en +8 y +12
    inst_raw = estado.get('instancia')
    if not inst_raw and estado.get('ranura') is not None:
        inst_raw = 1000 + int(estado['ranura'])
    inst = int(inst_raw or 0) & 0xFFFFFFFF
    struct.pack_into('<II', b, 8, inst, inst)

    # Nivel y experiencia en 64 bits (+35 exp, +43 flag=1, +51 exp_max)
    struct.pack_into('<I', b, 31, nv)
    struct.pack_into('<QQQ', b, 35, exp, 1, exp_max)

    # Vida y mana actuales + base + maximos (+59..+83)
    struct.pack_into('<IIIIII', b, 59, h_eff, m_eff, hp_max, h_max_eff, mp_max, m_max_eff)

    # Resistencias elementales (+131..+163) y Sta / Soul (+163..+171)
    # Si la mascota tiene mejoras (+N), sus defensas elementales efectivas suben +N (sub_63EF40)
    elem_vals = list(DEFENSAS_ELEM_BASE)
    if mej > 0:
        for idx_def in (3, 7, 11, 15):
            elem_vals[idx_def] = min(0xFFFF, elem_vals[idx_def] + mej)
    struct.pack_into('<16H', b, 131, *elem_vals)
    struct.pack_into('<4H', b, 163, STA_BASE, STA_BASE, SOUL_BASE, SOUL_BASE)

    # Las 3 habilidades de la mascota (+171..+177)
    sks = estado.get('skills') or skills_de(sp, nv)
    if len(sks) >= 3:
        struct.pack_into('<3H', b, 171,
                         int(sks[0] or 0) & 0xFFFF,
                         int(sks[1] or 0) & 0xFFFF,
                         int(sks[2] or 0) & 0xFFFF)

    # Byte 190 (a2+192 en sub_60ADC0 -> dword_1434C): contador de mejoras (+N) en WND_PET_INFO
    b[190] = min(255, mej)
    # Estrellas (+196, 1 = Star Level 0.1)
    struct.pack_into('<I', b, 196, st_lvl & 0xFFFFFFFF)
    return struct.pack('<H', 0x0065) + bytes(b)


def alimentar(estado: dict, cantidad: int = SACIEDAD_POR_PIENSO) -> tuple:
    """El Pet Feed normal: sube la saciedad (hasta 600) y recupera intimidad."""
    antes = int(estado.get('saciedad', 0))
    estado['saciedad'] = min(SACIEDAD_MAXIMA, antes + cantidad)
    estado['intimidad'] = min(100, int(estado.get('intimidad', 60)) + 5)
    return estado['saciedad'], estado['saciedad'] >= SACIEDAD_PARA_MEJORAR


def aplicar_mejoras(estado: dict, pct: dict) -> dict:
    """Suma a la ficha los porcentajes que den los Improved Pet Feed.

    `pct` es lo que devuelve mejoras.stats_de_mejora(), o sea {'atk': 24} para
    tres piensos del 8%. Se devuelve una copia con los numeros ya subidos,
    para mandarla en el 0x0065 sin tocar la ficha guardada.
    """
    out = dict(estado)
    for stat, p in (pct or {}).items():
        if stat in OFF and stat not in ('nombre', 'entidad', 'tipo'):
            out[stat] = int(round(out.get(stat, 0) * (1 + p / 100.0)))
    return out


# Las ordenes que se le dan, del c2s 0x003E. El servidor real contesta con un
# 0x001D del JUGADOR -- no de la mascota -- con el tipo 0x11 y el modo dentro.
# Medidos 0, 1, 2 y 4 en la captura; los nombres son lo que hacen segun se
# vio, y el 4 no se llego a identificar.
ORDEN_QUIETA = 0
ORDEN_SEGUIR = 1
ORDEN_ATACAR = 2
KIND_ORDEN = 0x11


def paquete_orden(entidad_jugador: int, modo: int) -> bytes:
    """El 0x001D que confirma la orden.

    Medido: "1e010000 01 11 01 0000 0000 0000" para la orden 1 del jugador
    0x11e. Los seis ceros del final van siempre.
    """
    return (struct.pack('<HIBB', 0x001D, entidad_jugador, 1, KIND_ORDEN)
            + struct.pack('<B', modo & 0xFF) + bytes(7))


# ---------------------------------------------------------------------------
# La entrada del inventario, que es distinta de la ficha de arriba.
#
# Una mascota ocupa 231 bytes en la mochila, contra los 86 de un objeto normal
# y los 119 de uno que se equipa. Hasta ahora se le mandaba una de 86 y el
# cliente se cerraba al pasarle el raton por encima: leia una ficha que no
# estaba entera.
#
# El mapa sale de 51 entradas distintas de las capturas, cruzadas contra los
# 0x0065 de nueve mascotas (Battlemaid, Hicalu, Fire Elf, Heady Dragon, Civet
# Guardian, los dos huevos...). Cada campo de abajo cuadro en las 41 entradas
# cuyo 0x0065 tambien estaba en la captura; los que no cuadraron en todas no
# estan aqui.
#
# Lo que la entrada NO lleva: los stats de combate. Ataque, defensa, rigor y
# agilidad solo viajan en el 0x0065, cuando se abre la ventana de la mascota.
# Aqui solo va lo que se ve sin abrirla.
TAM_ENTRADA = 231

OFF_ENTRADA = {
    'hp': 86,
    'exp': 90,
    'exp_max': 98,
    'nombre': 106,      # 12 bytes, no 16 como en el 0x0065
    'hp_max': 119,
    'mp': 123,          # el MP actual (a3+122 -> v6+184 en sub_514180)
    'mp_max': 127,      # el MP maximo (a3+126 -> v6+188 en sub_514180)
    'sprite': 131,      # u16; es el 動態資料1 del item
    'nivel': 133,
    'saciedad': 137,    # u16
    'intimidad': 139,   # u8
}
LARGO_NOMBRE = 12
_U16 = ('sprite', 'saciedad')

OFF_BONUS_ENTRADA = {
    'hp': 148,
    'mp': 152,
    'atk': 156,
    'dfs': 160,
    'matk': 164,
    'mdef': 168,
    'rigor': 172,
    'agilidad': 176,
}


def subir_estrella(ficha: dict, cantidad: int = 1) -> int:
    """Sube el nivel de estrella de la mascota (1..80, 10 = 1.0 estrellas, 80 = 8.0 estrellas)
    actualizando los bonos verdes especificos de los stats que esa mascota posee."""
    import random
    sp = int(ficha.get('sprite') or 0)
    bonos = dict(ficha.get('bonos') or {})
    if cantidad <= 0:
        return int(ficha.get('estrellas') or calcular_estrellas_total(bonos))
    tabla = cargar_pet_star()
    if not bonos:
        bonos = sortear_bonos(sp)
    # Una pet de fusion conserva los bonos de su principal. No decidir que
    # atributos puede mejorar por los rangos prestados de otra especie.
    for k in STATS_BONO:
        cur_val = int(bonos.get(k, 0))
        if cur_val <= 0:
            continue
        cur_st = max(1, estrella_de_bono(cur_val, k))
        if cur_st >= 80:
            continue
        # Pequeña variacion por stat si se sube con Star-up Card (+10)
        delta = max(1, cantidad + (random.randint(-1, 1) if cantidad >= 5 else 0))
        new_st = min(80, cur_st + delta)
        req_lo = (tabla.get(new_st) or {}).get(k, cur_val + 1)
        req_hi = (tabla.get(min(80, new_st + 1)) or {}).get(k, req_lo + 5)
        if req_hi > req_lo + 1:
            bonos[k] = max(cur_val, random.randint(req_lo, req_hi - 1))
        else:
            bonos[k] = max(cur_val, req_lo)
    ficha['bonos'] = bonos
    # La cifra general debe describir los bonos resultantes, no subir por
    # separado cuando solo seis de los ocho atributos han crecido.
    nuevo = calcular_estrellas_total(bonos)
    ficha['estrellas'] = nuevo
    return nuevo


def mejorar_mascota(ficha: dict) -> tuple:
    """Aplica un Improved Pet Feed (寵物強化): sube el contador de intensificacion (+1..+15,
    que el cliente muestra como 'has been intensified ( N ) times' en e[83] y +N en defensas
    elementales) y mejora los bonos verdes de los stats especificos de la mascota."""
    import random
    sp = int(ficha.get('sprite') or 0)
    mej = int(ficha.get('mejoras') or 0)
    if mej >= 15:
        return False, mej
    mej += 1
    ficha['mejoras'] = mej
    rangos = rangos_bonos_de(sp)
    bonos = dict(ficha.get('bonos') or {})
    if not bonos:
        bonos = sortear_bonos(sp)
    # Generar los bonos que faltan no sustituye el efecto del primer pienso.
    # Conservamos la politica de incrementos existente hasta verificar la
    # formula oficial; no presentar estos coeficientes como datos del XML.
    for k, (lo, hi) in rangos.items():
        inc = max(1, random.randint(max(1, lo // 2), max(2, hi // 2)))
        bonos[k] = int(bonos.get(k, 0)) + inc
    ficha['bonos'] = bonos
    ficha['estrellas'] = calcular_estrellas_total(bonos)
    return True, mej


def entrada(plantilla: bytes, estado: dict) -> bytes:
    """Escribe la parte de mascota sobre una entrada de inventario.

    `plantilla` son los 231 bytes ya rellenos con lo comun a cualquier objeto
    (instancia, item, dueño, casilla, cantidad). Aqui solo se añade lo que es
    de la mascota.
    """
    e = bytearray(plantilla)
    if len(e) != TAM_ENTRADA:
        e = (e + bytes(TAM_ENTRADA))[:TAM_ENTRADA]
    nv = max(1, int(estado.get('nivel') or 1))
    sp = int(estado.get('sprite') or 0)
    b_star = bonos_de_ficha(estado)
    st_lvl = max(1, int(estado.get('estrellas') or calcular_estrellas_total(b_star)))
    for campo, off in OFF_ENTRADA.items():
        v = estado.get(campo)
        if v is None:
            continue
        if campo == 'nombre':
            nom = str(v).encode('latin1', 'replace')[:LARGO_NOMBRE]
            e[off:off + LARGO_NOMBRE] = nom + bytes(LARGO_NOMBRE - len(nom))
        elif campo in _U16:
            struct.pack_into('<H', e, off, min(0xFFFF, max(0, int(v))))
        elif campo == 'intimidad':
            e[off] = min(0xFF, max(0, int(v)))
        elif campo in ('exp', 'exp_max'):
            val_q = int(v) if int(v or 0) > 0 else (exp_para_subir(nv, sp) if campo == 'exp_max' else 0)
            struct.pack_into('<Q', e, off, max(0, val_q))
        elif campo in ('hp_max', 'mp_max'):
            val_eff = int(v) + int(b_star.get('hp' if campo == 'hp_max' else 'mp', 0))
            if int(estado.get('saciedad') or 0) > 100:
                val_eff = int(round(val_eff * 3.5))
            struct.pack_into('<I', e, off, int(val_eff) & 0xFFFFFFFF)
        elif campo in ('hp', 'mp'):
            val_eff = int(v) + int(b_star.get('hp' if campo == 'hp' else 'mp', 0))
            if int(estado.get('saciedad') or 0) > 100:
                val_eff = int(round(val_eff * 3.5))
            struct.pack_into('<I', e, off, int(val_eff) & 0xFFFFFFFF)
        else:
            struct.pack_into('<I', e, off, int(v) & 0xFFFFFFFF)
    # Byte 83 (a3+82 en sub_514180 / sub_644B40 / sub_63EF40): numero de veces que la mascota
    # ha sido intensificada con Improved Pet Feed (0 al comprarla; >0 enseña "has been intensified ( N ) times")
    e[83] = max(0, min(255, int(estado.get('mejoras') or 0)))
    # Byte 118: 1 si la mascota esta invocada (fuera), 0 si esta guardada
    e[118] = 1 if estado.get('fuera') else 0
    # Offsets 148..180: bonos verdes de cada stat (0 si la mascota no tiene bono en ese stat)
    for stat_k, off_b in OFF_BONUS_ENTRADA.items():
        bono_val = int(b_star.get(stat_k, 0)) & 0xFFFFFFFF
        struct.pack_into('<I', e, off_b, bono_val)
    # Offset 222: nivel de estrellas general (1 = 0.1 estrellas)
    struct.pack_into('<I', e, 222, st_lvl & 0xFFFFFFFF)
    # Offset 226: ID del monstruo capturado en monster.xml (para sub_514940 / Antetype: %s)
    npc_mid = int(estado.get('npc_type') or 0) & 0xFFFFFFFF
    struct.pack_into('<I', e, 226, npc_mid)
    # Offset 230: Rango / calidad de la mascota (sub_5148F0: 1=Common, 2=Good, 3=Rare, 4=Awesome/Top, 5=Super)
    rango_val = max(0, min(5, int(estado.get('rango') or (1 if npc_mid else 0))))
    e[230] = rango_val
    return bytes(e)


RANGO_NOMBRES = {
    1: 'Common',
    2: 'Good',
    3: 'Rare',
    4: 'Awesome',
    5: 'Super',
}

def sortear_rango() -> tuple:
    """Sortea solamente la calidad: estrellas y bonos son independientes."""
    import random
    roll = random.random() * 100.0
    if roll < 60.0:
        rango = 1
    elif roll < 84.0:
        rango = 2
    elif roll < 94.0:
        rango = 3
    elif roll < 98.0:
        rango = 4
    else:
        rango = 5
    return rango, RANGO_NOMBRES[rango]


def aplicar_rango(ficha: dict, rango: int = 1, st: int = None, mult: float = None) -> dict:
    """Aplica la etiqueta de calidad sin alterar stats, bonos ni estrellas."""
    ficha['rango'] = int(rango or 1)
    ficha['rango_nombre'] = RANGO_NOMBRES.get(ficha['rango'], 'Common')
    return ficha


def abreviar_nombre_pet(nombre: str) -> str:
    """Formatea el nombre para los 12 bytes del campo de apodo en el paquete de inventario."""
    if not nombre:
        return 'Pet'
    s_nom = str(nombre).strip()
    if len(s_nom) <= 12:
        return s_nom
    reemplazos = {
        'Purple Evil Cat': 'Purple Cat',
        'Flaming Evil Cat': 'Flaming Cat',
        'Sky Winged Bird': 'Sky Bird',
        'Earth Winged Bird': 'Earth Bird',
        'Giant Rotten Bird': 'Rotten Bird',
        'Magic Pumpkinman': 'Pumpkinman',
        'Mutated Chimera': 'Chimera',
        'Twin-head Chimera': 'Twin Chimera',
        'Mutated Pink Fruit': 'Pink Fruit',
        'Mutated Hornet': 'Mut. Hornet',
        'Mutant Earth Elf': 'Mutant Elf',
    }
    if s_nom in reemplazos:
        return reemplazos[s_nom]
    parts = s_nom.split()
    if len(parts) >= 3:
        short = f"{parts[0]} {parts[-1]}"
        if len(short) <= 12:
            return short
    elif len(parts) == 2 and parts[0] in ('Mutated', 'Mutant'):
        if len(parts[1]) <= 12:
            return parts[1]
    return s_nom[:12].strip()


def recien_nacida(nombre: str, sprite: int, nivel: int = 1,
                  hp: int = 127, mp: int = 70, estrellas: int = 1,
                  rango: int = 1, npc_type: int = 0) -> dict:
    """Una mascota de ese sprite, con su tipo, nombre y stats de pet.xml.

    El 'tipo' (el 圖號1) es imprescindible: dejandolo en cero el cliente no
    sabe que mascota es y la ventana sale sin nivel y sin dibujo.
    """
    d = ficha_de_sprite(sprite)
    nv = max(1, int(nivel or 1))
    # Al comprar un huevo (原型), nace con 0 mejoras y sin bonos verdes (bonos={});
    # si nace ya evolucionada o es de etapa mayor, sortea sus bonos propios de pet.xml.
    es_huevo = (d.get('etapa') == '原型')
    es_capturada = int(npc_type or 0) > 0
    # A diferencia de un huevo de tienda, una mascota capturada ya nace con
    # sus ocho bonos verdes. Su Star Level es la media de pet_star.xml, no
    # una cifra fabricada a partir de Common/Good/Rare/Awesome/Super.
    bonos_ini = sortear_bonos(sprite) if es_capturada or not es_huevo else {}
    st = calcular_estrellas_total(bonos_ini) if bonos_ini else max(1, int(estrellas or 1))
    final_nombre = nombre if nombre and nombre != 'Pet' else (d.get('nombre') or nombre or 'Pet')
    f = {'nombre': final_nombre, 'sprite': sprite,
         'tipo': d.get('tipo', 0), 'nivel': nv,
         'hp': hp, 'hp_max': hp, 'mp': mp, 'mp_max': mp,
         'exp': 0, 'exp_max': exp_para_subir(nv, sprite),
         'saciedad': 100, 'intimidad': 60,
         'estrellas': st,
         'rango': int(rango or 1),
         'npc_type': int(npc_type or 0),
         'mejoras': 0,
         'bonos': bonos_ini,
         'skills': list(skills_de(sprite, nv))}
    # Los stats de combate salen de petattrib. Sin esto la ventana de la
    # mascota sale entera en blanco, que es lo que pasaba: se creia que el
    # cliente los calculaba solo y no lo hace.
    f.update(stats_de(sprite, nv))
    return f


# ---------------------------------------------------------------------------
# La mascota como criatura del mundo: el s2c 0x0050.
#
# Medido el 29/09/2026 en mundo_022355_871035. Sacando y guardando la misma
# Battlemaid tres veces solo cambiaron ocho bytes de los 103: la entidad, las
# dos coordenadas y el trozo del nombre que se acorto al renombrarla. Todo lo
# demas es fijo y va en la plantilla.
#
# No confundirlo con el 0x0008, que es el spawn de un NPC y tiene otro mapa:
# alli el sprite esta en el 34 y aqui en el 45.
TAM_MUNDO = 103

OFF_MUNDO = {
    'entidad': 0,
    'x': 8,
    'y': 12,
    'nombre': 16,       # 13 bytes
    'tipo': 34,
    'sprite': 45,       # u16
    'instancia': 63,    # la del item en la mochila, repetida en el 67 (a2+65 en Angel.exe)
    'entidad2': 71,     # la suya otra vez (a2+73 en Angel.exe)
    'dueno': 75,        # LA ENTIDAD DEL JUGADOR (a2+77 en Angel.exe)
    'dueno_nombre': 79,  # 16 bytes (a2+81..97 en Angel.exe)
}
LARGO_NOMBRE_MUNDO = 13
LARGO_DUENO = 16


def entidad_mundo(plantilla: bytes, estado: dict) -> bytes:
    """El 0x0050 que pinta la mascota al lado del jugador."""
    b = bytearray(plantilla)
    if len(b) != TAM_MUNDO:
        b = (b + bytes(TAM_MUNDO))[:TAM_MUNDO]
    for campo, off in OFF_MUNDO.items():
        v = estado.get(campo)
        if v is None:
            continue
        if campo in ('nombre', 'dueno_nombre'):
            largo = (LARGO_NOMBRE_MUNDO if campo == 'nombre'
                     else LARGO_DUENO)
            t = str(v).encode('latin1', 'replace')[:largo]
            b[off:off + largo] = t + bytes(largo - len(t))
        elif campo == 'sprite':
            struct.pack_into('<H', b, off, int(v) & 0xFFFF)
        else:
            struct.pack_into('<I', b, off, int(v) & 0xFFFFFFFF)
    # La instancia y la entidad van repetidas.
    inst_raw = estado.get('instancia')
    if inst_raw is None and estado.get('ranura') is not None:
        inst_raw = 1000 + int(estado['ranura'])
    if inst_raw is not None:
        inst_v = int(inst_raw) & 0xFFFFFFFF
        struct.pack_into('<II', b, 63, inst_v, inst_v)
    if estado.get('entidad') is not None:
        struct.pack_into('<I', b, 71, int(estado['entidad']) & 0xFFFFFFFF)
    if estado.get('dueno') is not None:
        struct.pack_into('<I', b, 75, int(estado['dueno']) & 0xFFFFFFFF)
    # Offset 53 (a2+55 -> v5+996 en sub_607C90): nivel de estrellas sobre la cabeza al pasar el raton
    b_star_m = bonos_de_ficha(estado)
    st_lvl_m = max(1, int(estado.get('estrellas') or calcular_estrellas_total(b_star_m)))
    struct.pack_into('<I', b, 53, st_lvl_m & 0xFFFFFFFF)
    # Offset 95: HP efectivo de la mascota en el mundo
    hp_val = hp_eff(estado) & 0xFFFFFFFF
    struct.pack_into('<I', b, 95, hp_val)
    return struct.pack('<H', 0x0050) + bytes(b)


# Renombrar: c2s 0x003D, y el cuerpo es el nombre y nada mas. Se vio poner
# "Battlemaids" y luego "Battle"; el servidor contesta remandando la entrada
# del inventario, que es donde vive el nombre. Mientras no se le ponga uno,
# el nombre es el de su clase, que es el 基本名稱 del item.
def nombre_pedido(cuerpo: bytes) -> str:
    """Saca el nombre del c2s 0x003D."""
    return cuerpo.split(b'\0')[0].decode('latin1', 'replace').strip()


def paquete_renombrar(pet_eid: int, nombre: str, resultado: int = 0) -> bytes:
    """OBSOLETO / NO ENVIAR: En Angel.exe el opcode 0x003D despacha a FUN_005a25a0
    (sistema de Correo/Mail) y causa crash por puntero nulo al desreferenciar
    [ecx + 0x15130]. Medido en capturas oficiales (mundo_022355_871035), la respuesta
    a c2s 0x003D es UNICAMENTE el s2c 0x001B de la casilla del inventario.
    """
    nom_bytes = str(nombre or '').encode('latin1', 'replace')[:LARGO_NOMBRE] + b'\x00'
    total_len = 72 + len(nom_bytes)
    hdr = struct.pack('<HHHH', 0x003D, total_len, 0, resultado & 0xFFFF)
    cuerpo = struct.pack('<I', int(pet_eid or 0) & 0xFFFFFFFF) + bytes(58) + struct.pack('<H', 0) + nom_bytes
    return hdr + cuerpo


# ---------------------------------------------------------------------------
# Los stats de combate. NO los calcula el cliente: viajan en el 0x0065 y si
# van a cero la ventana de la mascota sale entera en blanco.
#
# Salen de la tabla petattrib, que va por (tipo de mascota, nivel). El enlace
# item -> tipo NO esta en el cliente: no hay ninguna columna en item.xml ni
# ninguna otra tabla que lo lleve. Asi que aqui va lo MEDIDO, por sprite:
#
#   3049  Fire Elf Egg   輔助回復型   los ocho numeros de la ventana cuadran
#                                     con la wiki: 100/105 de vida y mana,
#                                     28 de ataque, 10 de defensa, 18 y 19
#                                     de magia, 15 de rigor y 15 de agilidad
#   3200  Battlemaid     強攻型       nivel 217: 16057 de vida, 7772 de mana
#
# Lo que no este aqui cae en el tipo medio, que es lo menos daniño.
#
# OJO con dos nombres: 'accuracy' de la tabla es el RIGOR de la ventana, y
# 'atk_avg' es el ataque. Se comprobo con el Elf Egg, donde los ocho valores
# coinciden uno a uno.
# La tabla de mascotas sale de pet.xml de los paks, volcada por
# tools/pets_de_pet_xml.py. Antes habia aqui dos sprites a mano y todo lo
# demas caia en un tipo por defecto, que es por lo que las mascotas salian
# con los stats de otra. Ahora son las 1751 del cliente.
#
# De cada una interesa:
#   tipo     el 圖號1, que va en el +4 del 0x0065. DEJANDOLO EN CERO el
#            cliente no sabe que mascota es y la ventana sale sin nivel y
#            sin dibujo
#   clase    el 寵物類型, con el que se buscan sus stats en petattrib
#   rama1/2  las dos evoluciones posibles: la 1 es la "mean" del arbol de
#            la wiki y la 2 la "nice"
#   crianza  el 條件成長值 que hace falta para pasar de etapa
TABLA = pathlib.Path(__file__).parent / 'plantillas' / 'mascotas.json'
TABLA_SKILLS = pathlib.Path(__file__).parent / 'plantillas' / 'petskills.json'
TIPO_POR_DEFECTO = '平均型'

# Sta y Soul salen fijos en todas las fichas vistas y no estan en petattrib.
STA_BASE = 30
SOUL_BASE = 60

_MASC = {}
_TABLA = {}
_SKILLS = {}


def _tabla():
    """{sprite: {...}} de pet.xml, leido una sola vez."""
    if _MASC:
        return _MASC
    try:
        for k, v in json.loads(TABLA.read_text(encoding='utf-8')).items():
            _MASC[int(k)] = v
    except Exception:
        pass
    return _MASC


def _petskills():
    """{table_id: [lv1..lv26]} de petskill.xml, leido una sola vez."""
    if _SKILLS:
        return _SKILLS
    try:
        for k, v in json.loads(TABLA_SKILLS.read_text(encoding='utf-8')).items():
            _SKILLS[int(k)] = v
    except Exception:
        pass
    return _SKILLS


def ficha_de_sprite(sprite) -> dict:
    return _tabla().get(int(sprite or 0)) or {}


def skills_de(sprite, nivel: int = 1) -> tuple:
    """Devuelve los 3 magic_id de la mascota segun su sprite y nivel.

    En pet.xml cada mascota declara hasta tres tablas (技能1..3階級表) que
    cruzan contra petskill.xml. El escalon sube cada 10 niveles (nivel // 10,
    con minimo 1 y maximo 26), comprobado contra todas las mascotas de las
    capturas de Celestia (niveles 1, 20, 66, 86, 94, 217 y 246).
    """
    d = ficha_de_sprite(sprite)
    tablas = _petskills()
    rango = max(1, min(26, int(nivel or 1) // 10)) - 1
    out = []
    for k in ('sk1', 'sk2', 'sk3'):
        tid = d.get(k)
        fila = tablas.get(int(tid)) if tid else None
        out.append(int(fila[rango]) if fila and 0 <= rango < len(fila) else 0)
    return tuple(out)


def _petattrib():
    """{(clase, nivel): fila} leido de una vez (primero petattrib.json de update26, y si no, content.db)."""
    if _TABLA:
        return _TABLA
    f_json = pathlib.Path(__file__).parent / 'plantillas' / 'petattrib.json'
    if f_json.exists():
        try:
            raw = json.loads(f_json.read_text(encoding='utf-8'))
            for clase, d_lv in raw.items():
                for lv_s, vals in d_lv.items():
                    if len(vals) >= 8:
                        _TABLA[(clase, int(lv_s))] = {
                            'hp_max': int(vals[0]), 'mp_max': int(vals[1]),
                            'atk': int(vals[2]), 'dfs': int(vals[3]),
                            'matk': int(vals[4]), 'mdef': int(vals[5]),
                            'rigor': int(vals[6]), 'agilidad': int(vals[7]),
                        }
            if _TABLA:
                return _TABLA
        except Exception:
            pass
    import sqlite3
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if not db.exists():
        return _TABLA
    try:
        con = sqlite3.connect(db)
        for f in con.execute('select 寵物類型,level,hp,mp,atk_avg,def,matk,'
                             'mdef,accuracy,agility from petattrib'):
            try:
                _TABLA[(f[0], int(f[1]))] = {
                    'hp_max': int(f[2]), 'mp_max': int(f[3]),
                    'atk': int(f[4]), 'dfs': int(f[5]), 'matk': int(f[6]),
                    'mdef': int(f[7]), 'rigor': int(f[8]),
                    'agilidad': int(f[9])}
            except (TypeError, ValueError):
                continue
    except Exception:
        pass
    return _TABLA


def tipo_de(sprite) -> str:
    """La clase de petattrib de esa mascota, segun pet.xml."""
    return ficha_de_sprite(sprite).get('clase') or TIPO_POR_DEFECTO


def stats_de(sprite, nivel: int) -> dict:
    """Los stats que le tocan a esa mascota a ese nivel."""
    nv = max(1, int(nivel or 1))
    t = _petattrib().get((tipo_de(sprite), nv))
    d = dict(t) if t else {}
    if 'hp_max' in d:
        d['hp'] = d['hp_max']
    if 'mp_max' in d:
        d['mp'] = d['mp_max']
    d['exp_max'] = exp_para_subir(nv, sprite)
    d['skills'] = list(skills_de(sprite, nv))
    return d


# ---------------------------------------------------------------------------
# EVOLUCION. Una mascota no "sube de forma": cambia de tipo en petattrib, y
# con el tipo le cambian los ocho stats de golpe. Eso se comprobo cruzando
# el arbol del Elf Egg de la wiki contra la tabla, nivel a nivel:
#
#   nivel 15  Naughty Elf  408/304  atk 99  dfs 111  ->  魔攻型
#             Flying Guy   375/304  atk 95  dfs  85  ->  輔助回復型
#   nivel 55  Night Queen 1696/1204 atk 402 dfs 503  ->  魔攻型
#             Night Devil 1833/1066 atk 416 dfs 503  ->  遠程攻擊型
#             Elf Queen   1558/1204 atk 388 dfs 458  ->  輔助回復型
#
# Los cinco cuadran exactos, asi que la rama ES el tipo.
#
# Cuando evoluciona lo dicen los certificados: el Medium Blood Certificate a
# nivel 35 y el Advanced a nivel 55. Hacia DONDE lo dice el trato acumulado
# que se le haya dado con los Teach Pet -- strictly, softly o fondly -- que
# el juego suma por dentro. Un huevo de fusion (Fusion Pet Egg) no pasa por
# esto; las de monstruo si.
#
# LO QUE FALTA: cuanto suma cada Teach Pet y donde vive ese contador. Sin eso
# no se puede decidir la rama sola, y hay que capturarlo.
NIVEL_MEDIO = 35
NIVEL_AVANZADO = 55
NIVEL_PRIMERA_RAMA = 15

TRATOS = ('strictly', 'softly', 'fondly')

# rama -> tipo de petattrib, para el arbol del Elf Egg.
# Las ramas ya no se escriben a mano: cada mascota de pet.xml lleva las
# suyas en 升階變化1 y 升階變化2. La 1 es la "mean" del arbol de la wiki y la
# 2 la "nice". El Elf Egg (3181) va a Naughty Elf (3183) o a Flying Guy
# (3182), y de ahi a Fiend Lily / Incubus y a Night Queen / Night Devil.
RAMA_MEAN = 'rama1'
RAMA_NICE = 'rama2'


def ramas_de(sprite):
    """Las dos evoluciones posibles: (mean, nice). None donde no haya."""
    d = ficha_de_sprite(sprite)
    return (d.get('rama1'), d.get('rama2'))


def crianza_necesaria(sprite):
    """El 條件成長值 que pide esa etapa para pasar a la siguiente."""
    return ficha_de_sprite(sprite).get('crianza')


# Las cinco etapas, y cuales evolucionan. Contado sobre las 1751:
#
#   原型  147   huevo          2 ramas
#   初階  256   primera forma  2 ramas
#   中階  475   forma media    2 ramas
#   高階  585   forma final    SIN ramas -- aqui acaba la cadena normal
#   頂階  288   UNICA          SIN ramas -- las fusion y las de monstruo,
#                              que no evolucionan nunca. La Battlemaid es
#                              una de estas.
#
# O sea que una mascota normal hace tres evoluciones (huevo -> 初階 -> 中階
# -> 高階) eligiendo rama cada vez, y una 頂階 nace ya en su forma final.
ETAPA_UNICA = '頂階'
ETAPA_FINAL = '高階'


def evoluciona(sprite) -> bool:
    """Si esa mascota tiene a donde evolucionar."""
    return any(ramas_de(sprite))


def es_unica(sprite) -> bool:
    """Las 頂階: fusion y monstruo, que no pasan por ninguna evolucion."""
    return ficha_de_sprite(sprite).get('etapa') == ETAPA_UNICA


def evolucionar(ficha: dict, rama: str) -> dict:
    """Pasa la mascota a una de sus dos ramas.

    `rama` es 'mean' o 'nice'. Cambia el sprite, y con el cambian solos el
    nombre, el tipo y la clase de petattrib, porque todo eso sale de la
    tabla. El nivel y la experiencia no se tocan.
    """
    mean, nice = ramas_de(ficha.get('sprite'))
    destino = mean if rama == 'mean' else nice
    if not destino:
        return ficha
    es_capturada = int(ficha.get('npc_type') or 0) > 0
    nombre_actual = ficha.get('nombre')
    es_renombrada = bool(ficha.get('renombrada'))
    nombre_capturado = ficha.get('captured_name')

    ficha['sprite'] = int(destino)
    d = ficha_de_sprite(destino)
    ficha['tipo'] = d.get('tipo', 0)
    ficha.update(stats_de(ficha['sprite'], ficha.get('nivel', 1)))
    ficha['skills'] = list(skills_de(ficha['sprite'], ficha.get('nivel', 1)))

    # Preservar el nombre de la mascota:
    # 1. Si el jugador le cambio el nombre (renombrada), se mantiene SIEMPRE.
    # 2. Si es una pet capturada, su nombre por defecto es el de la especie capturada (captured_name).
    # 3. Solo si es una pet normal sin renombrar adopta el nombre de la nueva etapa.
    if es_renombrada and nombre_actual:
        ficha['nombre'] = nombre_actual
    elif es_capturada:
        if not nombre_capturado:
            import house_services as _hs_cap
            ident = _hs_cap.captured_monster_identity(ficha['npc_type'])
            nombre_capturado = abreviar_nombre_pet(ident['nombre'])
            ficha['captured_name'] = nombre_capturado
        ficha['nombre'] = nombre_capturado or nombre_actual
    elif d.get('nombre') and not es_renombrada:
        ficha['nombre'] = d['nombre']

    # En la evolucion avanzada (sin mas ramas) adopta la apariencia (tipo/sprite)
    # original capturada, conservando el arquetipo de stats/skills de catch.xml.
    if es_capturada and not any(ramas_de(destino)):
        tipo_capturado = int(ficha.get('captured_tipo') or 0)
        if not tipo_capturado:
            import house_services as _hs_cap
            ident = _hs_cap.captured_monster_identity(ficha['npc_type'])
            tipo_capturado = int(ident['sprite'] or 0)
        if tipo_capturado:
            ficha['tipo'] = tipo_capturado
            ficha['captured_tipo'] = tipo_capturado
    # Al evolucionar, actualizar o sortear los bonos verdes propios de la nueva etapa
    nuevos_bonos = sortear_bonos(ficha['sprite'])
    bonos_ant = ficha.get('bonos') or {}
    for k, v in nuevos_bonos.items():
        bonos_ant[k] = max(int(bonos_ant.get(k, 0)), v)
    # Limpiar stats que no pertenezcan a la nueva etapa si aun estaban en 0
    ficha['bonos'] = {k: v for k, v in bonos_ant.items() if v > 0}
    ficha['estrellas'] = calcular_estrellas_total(ficha['bonos'])
    return ficha


# Quitar del mundo. Medido: al guardar la mascota el servidor manda un
# s2c 0x0007 de cinco bytes con SU entidad. Es el mismo mensaje que se usa
# para cualquier criatura que desaparece -- de las seis entidades que lo
# recibieron en la captura, tres habian salido antes con un 0x0008.
# Sin esto la mascota se quedaba pegada en pantalla y no habia forma de
# guardarla.
def quitar(entidad: int, modo: int = 1) -> bytes:
    return struct.pack('<HIB', 0x0007, int(entidad) & 0xFFFFFFFF, modo & 0xFF)


# Y el enlace jugador -> mascota, que va en un 0x001D del JUGADOR con el
# tipo 0x2a y la entidad de la mascota dentro:
#     "1e010000 01 2a c4501000 0000 0000"
KIND_MASCOTA = 0x2A


def enlazar(entidad_jugador: int, entidad_mascota: int) -> bytes:
    return (struct.pack('<HIBB', 0x001D, int(entidad_jugador) & 0xFFFFFFFF,
                        1, KIND_MASCOTA)
            + struct.pack('<I', int(entidad_mascota) & 0xFFFFFFFF)
            + bytes(4))


# ---------------------------------------------------------------------------
# CRIANZA. De petaspect.xml, volcado a plantillas/crianza.json.
#
# El juego va sacando escenas ("se pone a dar vueltas alrededor de su dueño")
# con tres opciones cada una, y cada opcion suma un valor que va de -3 a +3.
# El texto de la primera lo dice sin rodeos: "las acciones del dueño afectaran
# la direccion de crecimiento del pet". Ese acumulado es lo que decide a cual
# de las dos ramas evoluciona.
#
# El umbral es el 條件成長值 de cada mascota, que en todas las vistas vale 10.
#
# CONFIRMADO el 29/09/2026 con tres mascotas y nueve evoluciones seguidas en
# el proxy, y pet.xml acerto las nueve:
#
#   3085 Elf Egg -> 3087 Naughty Elf -> 3091 Fiend Lily -> 3096 Night Queen
#        las tres por la RAMA 1, y esa es la rama "mean" del arbol de la wiki.
#        Su rama 2 son Flying Guy, Incubus y Succubus, que es la "nice".
#   15828 -> 15830 -> 15834 -> 15839, las tres por la rama 2.
#   13590 -> 13591 (rama 1) -> 13594 (rama 2) -> 13598 (rama 1), alternando.
#
# O sea: 升階變化1 es la mean y 升階變化2 la nice, y la rama se ELIGE -- el
# porcino alterna entre las dos dentro de la misma cadena.
#
# Y OJO CON EL UMBRAL: ese huevo tenia 條件成長值=2, no 10. Varia por mascota,
# asi que hay que leerlo de la tabla y no dar por bueno ningun numero fijo.
#
# Lo que sigue sin medir es la rama 1: hace falta criar una en negativo.
#
# Aparte, los NOMBRES de pet.xml no siempre son los que enseña el servidor:
# el 15828 sale ahi como "Guardian Egg" y el juego lo llamaba "Oasis Egg", y
# el 15830 es "Blue Egg" contra "Violet Pixie". Los sprites y las ramas si
# cuadran, que es lo que importa; los nombres cambian entre versiones.
CRIANZA = pathlib.Path(__file__).parent / 'plantillas' / 'crianza.json'
UMBRAL_CRIANZA = 10

_CRIA = {}


def situaciones():
    """{numero: {'tipo', 'texto', 'opciones': [{'texto','valor'}]}}."""
    if _CRIA:
        return _CRIA
    try:
        _CRIA.update(json.loads(CRIANZA.read_text(encoding='utf-8')))
    except Exception:
        pass
    return _CRIA


def criar(ficha: dict, valor: int) -> int:
    """Suma a la mascota el valor de la opcion elegida y lo devuelve."""
    ficha['crianza'] = int(ficha.get('crianza', 0)) + int(valor)
    return ficha['crianza']


def rama_por_crianza(ficha: dict):
    """Que rama le toca segun lo criada que este.

    El umbral es el 條件成長值 de la propia mascota, y NO es siempre 10: en
    lo medido salieron 2, 0, 6 y hasta -4. Por eso es una comparacion suelta
    contra ese numero y no un "mas o menos N".

    Con la crianza por encima del umbral va a la rama 2 y por debajo a la 1.
    Esto encaja con lo capturado -- un huevo criado en positivo (intimidad
    41) fue a la rama 2 -- pero las seis evoluciones que se vieron no traen
    el contador de crianza a la vista, asi que el sentido de la comparacion
    es lo unico de aqui que no esta comprobado del todo.
    """
    # /pet path stores the branch by hand. While it is set it wins over the
    # raise score, because the raise window never reports which scene came up.
    forzada = ficha.get('rama')
    if forzada in (RAMA_MEAN_NOMBRE, RAMA_NICE_NOMBRE):
        return forzada
    tope = crianza_necesaria(ficha.get('sprite'))
    if tope is None:
        tope = UMBRAL_CRIANZA
    v = int(ficha.get('crianza', 0))
    return RAMA_NICE_NOMBRE if v >= int(tope) else RAMA_MEAN_NOMBRE


RAMA_MEAN_NOMBRE = 'mean'
RAMA_NICE_NOMBRE = 'nice'


# ---------------------------------------------------------------------------
# EXPERIENCIA. La que hace falta para pasar del nivel N al N+1 es
#
#     exp_max = redondear(36 * N^1.5)
#
# Sale de 23 fichas capturadas, de nivel 1 a 246, y da los 23 numeros
# EXACTOS, sin un solo punto de error:
#
#     nivel 1 -> 36      nivel 66 -> 19303     nivel 150 -> 66136
#     nivel 2 -> 102     nivel 102 -> 37085    nivel 246 -> 138901
#
# Ojo: NO es la tabla 寵物A/B/C/D de level.xml. Esa pide billones por nivel y
# no cuadra con ninguna ficha; se probo y se descarto. Y aunque pet.xml diga
# que cada mascota usa una tabla distinta, todas las capturadas comparten el
# mismo exp_max a igual nivel, asi que la curva es una sola.
FACTOR_EXP = 36
_PET_EXP_TABLES = {}


def cargar_tablas_exp():
    global _PET_EXP_TABLES
    if _PET_EXP_TABLES:
        return _PET_EXP_TABLES
    import json, re, xml.etree.ElementTree as ET
    f_json = pathlib.Path(__file__).parent / 'plantillas' / 'level_curves.json'
    if f_json.exists():
        try:
            raw = json.loads(f_json.read_text(encoding='utf-8'))
            for tag, d in (raw.get('pet_exp_tables') or {}).items():
                _PET_EXP_TABLES[tag] = {int(lv): int(v) for lv, v in d.items()}
            if _PET_EXP_TABLES:
                return _PET_EXP_TABLES
        except Exception:
            pass
    base_dir = pathlib.Path(__file__).parent.parent / 'extracted_paks'
    files = list(base_dir.glob('**/level.xml')) if base_dir.exists() else []
    def _up_num(p):
        m = re.search(r'update(\d+)', str(p), re.IGNORECASE)
        return int(m.group(1)) if m else 0
    files.sort(key=_up_num, reverse=True)
    if files and files[0].exists():
        try:
            tree = ET.parse(files[0])
            for node in tree.getroot():
                lv = int(node.attrib.get('等級', 0))
                if not lv:
                    continue
                for c in node:
                    tag = c.tag
                    if tag not in _PET_EXP_TABLES:
                        _PET_EXP_TABLES[tag] = {}
                    try:
                        _PET_EXP_TABLES[tag][lv] = int(c.text.strip())
                    except Exception:
                        pass
        except Exception:
            pass
    return _PET_EXP_TABLES


def exp_para_subir(nivel: int, sprite: int = None) -> int:
    """La experiencia que pide ese nivel para pasar al siguiente segun level.xml."""
    n = max(1, int(nivel or 1))
    tablas = cargar_tablas_exp()
    tabla_nom = '寵物A'
    if sprite:
        d = ficha_de_sprite(sprite)
        exp_tipo = str(d.get('exp_tipo') or d.get('經驗等級表') or '')
        if 'B' in exp_tipo:
            tabla_nom = '寵物B'
        elif 'C' in exp_tipo:
            tabla_nom = '寵物C'
        elif 'D' in exp_tipo:
            tabla_nom = '寵物D'
    t = tablas.get(tabla_nom, {})
    if (n + 1) in t and n in t:
        diff = t[n + 1] - t[n]
        if diff > 0:
            return diff
    return int(round(FACTOR_EXP * n * (n ** 0.5)))


def nivel_maximo(sprite) -> int:
    """El nivel mas alto que petattrib tiene para la clase de esa mascota.

    Sin esto, un vale de 100 millones la mandaba al nivel 545, que no existe
    en la tabla: stats_de() devolvia vacio y la mascota se quedaba con los
    stats de nivel 1 pese a marcar nivel 545.
    """
    clase = tipo_de(sprite)
    niveles = [n for (c, n) in _petattrib() if c == clase]
    return max(niveles) if niveles else 471


def multiplicador_exp(ficha: dict, ahora=None) -> float:
    """Cuanto multiplica la experiencia la Double EXP Card que este puesta.

    La carta (item 3460) no da experiencia: pone el hechizo 1866, que dura
    1800 segundos y lleva 經驗加倍=100, o sea un +100%. De ahi salen los
    "30 M." de su nombre y el doble de su descripcion.
    """
    import time
    b = ficha.get('buff_exp')
    if not b:
        return 1.0
    ahora = time.time() if ahora is None else ahora
    if ahora >= b.get('hasta', 0):
        ficha.pop('buff_exp', None)
        return 1.0
    return 1.0 + (b.get('pct', 0) / 100.0)


def poner_buff_exp(ficha: dict, segundos: int, pct: int, ahora=None) -> dict:
    """Arranca el contador de la carta de experiencia doble."""
    import time
    ahora = time.time() if ahora is None else ahora
    ficha['buff_exp'] = {'hasta': ahora + max(0, int(segundos)),
                         'pct': int(pct)}
    return ficha['buff_exp']


def dar_exp(ficha: dict, cantidad: int, ahora=None) -> int:
    """Suma experiencia y sube de nivel lo que haga falta.

    Devuelve cuantos niveles subio. Los stats se recalculan con el nivel
    nuevo, que es como los da el juego: no se guardan sueltos.
    """
    subidos = 0
    cantidad = int(max(0, int(cantidad)) * multiplicador_exp(ficha, ahora))
    ficha['exp'] = int(ficha.get('exp', 0)) + cantidad
    maximo = nivel_maximo(ficha.get('sprite'))
    sp = ficha.get('sprite')
    while True:
        if int(ficha.get('nivel', 1)) >= maximo:
            ficha['exp'] = 0
            break
        tope = exp_para_subir(ficha.get('nivel', 1), sp)
        if ficha['exp'] < tope:
            break
        ficha['exp'] -= tope
        ficha['nivel'] = int(ficha.get('nivel', 1)) + 1
        subidos += 1
    ficha['exp_max'] = exp_para_subir(ficha.get('nivel', 1), sp)
    if subidos:
        nv = ficha['nivel']
        # Comprobar evolucion en nivel 15 SOLO para huevos (原型 -> 初階)
        if evoluciona(ficha.get('sprite')):
            etapa = ficha_de_sprite(ficha.get('sprite')).get('etapa')
            if etapa == '原型' and nv >= NIVEL_PRIMERA_RAMA:
                evolucionar(ficha, rama_por_crianza(ficha))
        ficha.update(stats_de(ficha.get('sprite'), ficha['nivel']))
    return subidos


def aplicar_certificado(ficha: dict, etapa_cert: int) -> tuple:
    """Aplica Medium Blood Certificate (etapa_cert=2, lvl 35) o Advanced (etapa_cert=3, lvl 55).

    Devuelve (exito, mensaje).
    """
    sprite = ficha.get('sprite')
    if not evoluciona(sprite):
        return False, "This pet cannot evolve any further."

    etapa = ficha_de_sprite(sprite).get('etapa')
    nv = int(ficha.get('nivel', 1))

    if etapa_cert == 2:
        if nv < NIVEL_MEDIO:
            return False, f"Pet must be Level {NIVEL_MEDIO} or higher to use Medium Blood Certificate."
        if etapa not in ('初階', '原型'):
            return False, "This certificate can only be used on a first-stage pet."
        evolucionar(ficha, rama_por_crianza(ficha))
        return True, f"Your pet evolved to {ficha.get('nombre')}!"
    elif etapa_cert == 3:
        if nv < NIVEL_AVANZADO:
            return False, f"Pet must be Level {NIVEL_AVANZADO} or higher to use Advanced Blood Certificate."
        if etapa not in ('中階', '初階'):
            return False, "This certificate can only be used on a medium-stage pet."
        evolucionar(ficha, rama_por_crianza(ficha))
        return True, f"Your pet evolved to {ficha.get('nombre')}!"
    return False, "Invalid certificate."


# ---------------------------------------------------------------------------
# LA RESPUESTA AL CUADRO DE CRIANZA. Va por el MISMO c2s 0x003E que las
# ordenes, y lo que las separa es el valor:
#
#     0, 1, 2   ordenes: quieta, seguir, atacar. El servidor contesta con un
#               0x001D del jugador con el tipo 0x11.
#     4, 5, 6   las TRES OPCIONES del cuadro, en el orden en que salen. El
#               servidor contesta con un 0x000A, que es la estrellita que
#               aparece sobre la mascota.
#
# Medido el 29/09/2026: en una captura casi vacia se respondio al cuadro dos
# veces y aparecieron un 6 y un 5, uno por respuesta. En el total de las
# capturas salen 3, 20 y 3 para las ordenes y 24, 18 y 8 para las opciones.
#
# El texto del cuadro NO viaja: lo saca el cliente de su petaspect.xml. Se
# comprobo palabra por palabra con la escena 5, que es la que salio en
# pantalla ("put it's head out when its owner wasn't watching it") con sus
# valores 0, -1 y +1 en ese orden.
PRIMERA_OPCION_CRIANZA = 4
EFECTO_CRIANZA = 0x029A


def es_respuesta_crianza(valor: int) -> bool:
    return PRIMERA_OPCION_CRIANZA <= int(valor) <= PRIMERA_OPCION_CRIANZA + 2


def opcion_de(valor: int) -> int:
    """De 4, 5 o 6 al indice 0, 1 o 2 de la escena."""
    return int(valor) - PRIMERA_OPCION_CRIANZA


def responder_crianza(ficha: dict, escena, valor: int):
    """Aplica la opcion elegida y devuelve (sumado, total).

    `escena` es una de las de situaciones(). Si no se sabe cual salio -- el
    servidor no la manda, la elige el cliente -- se suma 0 y solo se apunta
    la respuesta.
    """
    i = opcion_de(valor)
    suma = 0
    if escena and 0 <= i < len(escena.get('opciones') or []):
        suma = int(escena['opciones'][i].get('valor') or 0)
    return suma, criar(ficha, suma)


def efecto(entidad_origen: int, entidad_destino: int,
           cual: int = EFECTO_CRIANZA) -> bytes:
    """El s2c 0x000A: la estrellita sobre la mascota al responder.

    Medido: "00511000 e8780f00 0100 9a02" -- dos entidades, un uno y el
    numero del efecto.
    """
    return (struct.pack('<HII', 0x000A, int(entidad_origen) & 0xFFFFFFFF,
                        int(entidad_destino) & 0xFFFFFFFF)
            + struct.pack('<HH', 1, int(cual) & 0xFFFF))
