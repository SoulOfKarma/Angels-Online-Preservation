"""
Sistema de habilidades (Skills) y Hechizos (Spells / Magics) de Angels Online.

Gestiona:
1. Mapeo de ramas de combate, magia y soporte.
2. Hechizos iniciales (nivel 1) de cada rama de combate.
3. Calculo automatico del Job / Class ID segun la combinacion de habilidades equipadas.
4. Lectura de pergaminos / libros de habilidades (Skill Scrolls) desde content.db.
"""
import pathlib
import sqlite3

DB_PATH = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'

# Nombre en ingles de cada rama (ID 1..35)
NOMBRE_RAMA = {
    1: 'Life', 2: 'Wraith', 3: 'Chaos', 4: 'Earth', 5: 'Curse',
    6: 'Meditate', 7: 'Hit', 8: 'Staff Hit', 9: 'Sword', 10: 'Axe',
    11: 'Spear', 12: 'Enhance', 13: 'Grapple', 14: 'Shield', 15: 'Reserve',
    16: 'Finesse', 17: 'Longbow', 18: 'Snipe', 19: 'Eagle Eye',
    20: 'Collect', 21: 'Fishing', 22: 'Dig', 23: 'Lumber',
    24: 'Mechanism', 25: 'Drive', 26: 'Weapon', 27: 'Armor',
    28: 'Sew', 29: 'Technics', 30: 'Alchemy', 31: 'Cook',
    32: 'Mantle', 33: 'Garment', 34: 'Vestment', 35: 'Avatar', 36: 'Assault'
}

# Mapeo a nombre chino en content.db (magic.xml)
RAMA_A_CHINO = {
    1: '生命技能',   # Life
    2: '死靈技能',   # Wraith
    3: '混亂技能',   # Chaos
    4: '大地技能',   # Earth
    5: '吟咒技能',   # Curse
    6: '冥想技能',   # Meditate
    7: '魔導技能',   # Hit
    8: '法杖技能',   # Staff Hit
    9: '劍術技能',   # Sword
    10: '斧錘技能',  # Axe
    11: '槍術技能',  # Spear
    12: '強身技能',  # Enhance
    13: '格鬥技能',  # Grapple
    14: '盾防技能',  # Shield
    15: '蓄勁技能',  # Reserve
    16: '巧手技能',  # Finesse
    17: '弓箭技能',  # Longbow
    18: '狙擊技能',  # Snipe
    19: '鷹眼技能',  # Eagle Eye
    32: '影刃技能',  # Mantle
    35: '幻化技能',  # Avatar
    36: '奇襲技能',  # Assault
}

CHINO_A_RAMA = {v: k for k, v in RAMA_A_CHINO.items()}

# Hechizos iniciales de nivel 1 otorgados al equipar cada rama de combate
# Medidos directamente de content.db
HECHIZOS_INICIALES_RAMA = {
    1: [(1, 'Shock Wave I'), (2, 'Cure Spell I'), (3, 'Silver Shield I')],
    2: [(101, 'Poison Hit I'), (106, 'Soul Entangle I'), (109, 'Summon Skeleton I')],
    3: [(201, 'Magic Bomb I'), (202, 'Charming Blessing I'), (203, 'Sage Blessing I')],
    4: [(301, 'Flying Dart I'), (302, 'Earth Blessing I'), (303, 'Shining Charm I')],
    9: [(601, 'Slicing Hit I'), (602, 'Swiftness Song I'), (603, 'Injury Cure I')],
    10: [(701, 'Basic Beating I'), (702, 'Ferocious Song I'), (703, 'Fighting Shield I')],
    11: [(801, 'Basic Attack I'), (802, 'Bloody Song I'), (803, 'Endless Energy I')],
    17: [(901, 'Basic Shot I'), (902, 'Accurate Song I'), (903, 'Dodge Step I')],
    32: [(5401, 'Stab I'), (5406, 'Nimble I'), (5411, 'Poisoned Dagger I')],
}

_SCROLL_CACHE = {}


def nombre_rama(sid: int) -> str:
    return NOMBRE_RAMA.get(int(sid), f'Skill {sid}')


def hechizos_iniciales_de(skill_ids) -> list:
    """Devuelve [(magic_id, nombre)] de todos los hechizos iniciales de las ramas en skill_ids."""
    res = []
    vistos = set()
    for sid in skill_ids:
        sid_int = sid[0] if isinstance(sid, (list, tuple)) else int(sid)
        for mid, mname in HECHIZOS_INICIALES_RAMA.get(sid_int, []):
            if mid not in vistos:
                vistos.add(mid)
                res.append((mid, mname))
    return res


def hechizos_de_rama(sid: int) -> list:
    """Devuelve [(magic_id, nombre)] de la rama concreta que se acaba de equipar."""
    sid_int = int(sid)
    return list(HECHIZOS_INICIALES_RAMA.get(sid_int, []))


def hechizos_de_ramas_activas(skill_ids, solo_maximo: bool = True) -> list:
    """[(magic_id, nombre, rango)] de las ramas equipadas, leidos de content.db.

    No hay una lista fija: cada llamada mira la tabla magic actual, asi que
    un hechizo anadido despues entra la siguiente vez que se use el comando.
    Un rango alto que no trae rama propia hereda la de su grupo. Con
    solo_maximo se queda el rango mas alto de cada linea.
    """
    sids = set()
    for sid in skill_ids or []:
        sids.add(int(sid[0] if isinstance(sid, (list, tuple)) else sid))
    chinos = {RAMA_A_CHINO[s] for s in sids if s in RAMA_A_CHINO}
    if not chinos or not DB_PATH.exists():
        return []
    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute(
            'select id, name, "技能限制1", "群組編號", "法術等級" from magic'
        ).fetchall()
    finally:
        con.close()
    grupo_rama = {}
    for _mid, _name, restr, grupo, _rank in rows:
        if restr and grupo and str(grupo) not in grupo_rama:
            grupo_rama[str(grupo)] = str(restr).strip()
    mejor = {}
    for mid, name, restr, grupo, rank in rows:
        nom = str(name or '')
        if nom.lower().startswith('test'):
            continue
        rama = str(restr).strip() if restr else ''
        if not rama and grupo:
            rama = grupo_rama.get(str(grupo), '')
        if rama not in chinos:
            continue
        try:
            mid_i = int(mid)
            rk = int(rank or 1)
        except (TypeError, ValueError):
            continue
        if solo_maximo:
            clave = str(grupo) if grupo else 'id:%d' % mid_i
            prev = mejor.get(clave)
            if prev is None or rk > prev[0] or (rk == prev[0] and mid_i > prev[1]):
                mejor[clave] = (rk, mid_i, nom)
        else:
            mejor[mid_i] = (rk, mid_i, nom)
    return sorted((mid, nom, rk) for rk, mid, nom in mejor.values())


# LAS RANURAS DE RAMA DE HABILIDAD.
#
# De serie son SEIS: asi salen los seis personajes de data/cuentas.json y
# asi lo pinta el cliente. Encima de esas hay TRES mas, las que en el
# cliente oficial salen con "Reach Supreme Lv 1 to activate", "Reach
# Supreme Lv 20 to unlock" y "Unlocks at Supreme Lv 50" (textos 3656, 3657
# y 3658 de string.xml).
#
# Aqui no hay Supreme Level ni mision de por medio: se abren por NIVEL y
# ya, que es lo que se pidio.
RANURAS_BASE = 6
NIVELES_RANURA_EXTRA = (301, 351, 401)


def ranuras_de_habilidad(nivel: int) -> int:
    """Cuantas ramas puede llevar un personaje de ese nivel (6 a 9)."""
    n = int(nivel or 1)
    return RANURAS_BASE + sum(1 for corte in NIVELES_RANURA_EXTRA if n >= corte)


def ranura_que_se_abre(nivel: int) -> int:
    """La ranura que se estrena JUSTO a ese nivel, o 0 si no se estrena."""
    n = int(nivel or 1)
    for i, corte in enumerate(NIVELES_RANURA_EXTRA):
        if n == corte:
            return RANURAS_BASE + i + 1
    return 0


# CON QUE SE RELLENA UNA RANURA RECIEN ABIERTA.
#
# Se pone una rama que NO sea de combate a proposito, por dos razones: no
# toca la clase del personaje (calcular_class_id solo mira magias, armas y
# arco, asi que una de oficio no lo convierte en otra cosa) y se ve claro
# que es un hueco para ir a cambiarlo con el Skill Angel.
#
# Van en este orden y se coge la primera que no se lleve ya.
RAMAS_RELLENO = (20, 21, 22, 23, 31, 30, 29, 28, 27, 26, 25, 24)


def completar_ranuras_extra(habilidades, nivel, banco=None):
    """Open the extra skill slots this level has earned.

    Slot 7 at 301, slot 8 at 351, slot 9 at 401. A character who does not
    yet have the six base slots is left alone. Returns (habilidades, added).
    """
    habs = [tuple(h) if isinstance(h, (list, tuple)) else (int(h), 1, 0)
            for h in (habilidades or [])]
    if len(habs) < RANURAS_BASE:
        return habs, []
    banco = banco if isinstance(banco, dict) else {}
    added = []
    while len(habs) < ranuras_de_habilidad(nivel):
        sid = rama_de_relleno(habs)
        if not sid:
            break
        nv, xp = banco.get(sid, (1, 0))
        fila = (sid, nv, xp)
        habs.append(fila)
        added.append(fila)
    return habs, added


def rama_de_relleno(ya_llevadas) -> int:
    """La primera rama de oficio que ese personaje no tenga, o 0."""
    puestas = set()
    for h in (ya_llevadas or []):
        puestas.add(h[0] if isinstance(h, (list, tuple)) else int(h))
    for sid in RAMAS_RELLENO:
        if sid not in puestas:
            return sid
    return 0


def calcular_class_id(skill_ids) -> int:
    """Calcula el class_id (0..20 de class.xml) segun las habilidades equipadas."""
    ids = set()
    for s in skill_ids:
        ids.add(s[0] if isinstance(s, (list, tuple)) else int(s))

    tiene_magia = bool(ids & {1, 2, 3, 4})
    tiene_arma = bool(ids & {9, 10, 11, 32})
    tiene_arco = (17 in ids)

    # Clases hibridas (magia + armas/arco)
    if tiene_magia and tiene_arco:
        return 18  # MagicBowman
    if tiene_magia and tiene_arma:
        return 17  # M.Soldier
    # Multi-magia o mago puro
    if len(ids & {1, 2, 3, 4}) >= 2 or (tiene_magia and (8 in ids or 34 in ids or 5 in ids)):
        return 16  # Wizard Jr.

    # Clases puras de combate
    if 9 in ids:   return 7   # Swordsman
    if 10 in ids:  return 6   # Warrior
    if 11 in ids:  return 8   # Spearman
    if 17 in ids:  return 9   # Archer
    if 14 in ids:  return 5   # Protector

    # Clases puras de magia simple
    if 1 in ids:   return 1   # Priest
    if 2 in ids:   return 2   # Summoner
    if 3 in ids:   return 3   # Wizard
    if 4 in ids:   return 4   # Magician

    # Clases de produccion
    if 26 in ids:  return 10  # Weaponsmith
    if 27 in ids:  return 11  # Armorsmith
    if 28 in ids:  return 12  # Tailor
    if 29 in ids or 24 in ids: return 13  # Technician
    if 30 in ids:  return 14  # Alchemist
    if 31 in ids:  return 15  # Chef
    if 22 in ids:  return 19  # Miner
    if any(s in ids for s in (20, 21, 23, 25)): return 20  # Producer

    return 0  # Novice


def skill_de_magia(magic_id: int):
    """Devuelve el skill_id (1..35) de la rama a la que pertenece este hechizo/habilidad."""
    if not magic_id:
        return None
    mid = int(magic_id)
    if not DB_PATH.exists():
        return None
    try:
        con = sqlite3.connect(DB_PATH)
        row = con.execute('SELECT "技能限制1", "群組編號" FROM magic WHERE id = ?', (str(mid),)).fetchone()
        if row:
            if row[0]:
                con.close()
                return CHINO_A_RAMA.get(str(row[0]).strip())
            # Si un rango superior no tiene 技能限制1 explicito, heredar del grupo (ej. Frozen Trap II)
            if row[1]:
                row_grp = con.execute('SELECT "技能限制1" FROM magic WHERE "群組編號" = ? AND "技能限制1" IS NOT NULL LIMIT 1', (row[1],)).fetchone()
                if row_grp and row_grp[0]:
                    con.close()
                    return CHINO_A_RAMA.get(str(row_grp[0]).strip())
        con.close()
    except Exception:
        pass
    return None


def info_pergamino(item_id: int):
    """Devuelve informacion del pergamino/libro de habilidad desde content.db o None si no es scroll."""
    iid = int(item_id)
    if iid in _SCROLL_CACHE:
        return _SCROLL_CACHE[iid]

    if not DB_PATH.exists():
        return None

    try:
        con = sqlite3.connect(DB_PATH)
        row = None
        for tbl in ('item', 'item2', 'item3', 'item4', 'item5', 'item6', 'item7', 'item8'):
            try:
                row = con.execute(
                    f'SELECT "物品類別", "動態資料1", "技能限制1", "技能限制2", "技能限制3", "技能限制4", "技能限制5", "技能等限", "基本名稱", "物品等級" FROM {tbl} WHERE id = ?',
                    (str(iid),)
                ).fetchone()
                if row:
                    break
            except Exception:
                continue

        if not row:
            con.close()
            _SCROLL_CACHE[iid] = None
            return None

        cat = str(row[0] or '')
        dyn = str(row[1] or '').strip()
        sk_lims = [str(row[i] or '').strip() for i in range(2, 7)]
        lv_req = str(row[7] or '').strip()
        nombre_item = str(row[8] or '')
        char_lv_req = str(row[9] or '').strip()

        if cat != '卷軸' or not dyn or not dyn.isdigit():
            con.close()
            _SCROLL_CACHE[iid] = None
            return None

        mid = int(dyn)
        req_skills = [int(s) for s in sk_lims if s and s.isdigit()]
        req_lv = int(lv_req) if lv_req and lv_req.isdigit() else 1
        req_char_lv = int(char_lv_req) if char_lv_req and char_lv_req.isdigit() else 1

        # Consultar nombre del hechizo y su nivel en tabla magic
        mrow = con.execute('SELECT name, "法術等級" FROM magic WHERE id = ?', (str(mid),)).fetchone()
        con.close()

        mname = str(mrow[0]) if mrow and mrow[0] else nombre_item
        mlv = int(float(mrow[1])) if mrow and mrow[1] else 1

        info = {
            'item_id': iid,
            'nombre_item': nombre_item,
            'magic_id': mid,
            'magic_name': mname,
            'magic_level': mlv,
            'req_skills': req_skills,
            'req_skill': req_skills[0] if req_skills else 0,
            'req_level': req_lv,
            'req_char_lv': req_char_lv,
        }
        _SCROLL_CACHE[iid] = info
        return info
    except Exception:
        return None


_MAGIC_LV_CACHE = {}


def nivel_de_magia(magic_id: int) -> int:
    """Devuelve el nivel del hechizo (法術等級 de magic.xml), o 1."""
    if not magic_id:
        return 1
    mid = int(magic_id)
    if mid in _MAGIC_LV_CACHE:
        return _MAGIC_LV_CACHE[mid]
    if not DB_PATH.exists():
        return 1
    try:
        con = sqlite3.connect(DB_PATH)
        row = con.execute('SELECT "法術等級" FROM magic WHERE id = ?', (str(mid),)).fetchone()
        con.close()
        lv = int(float(row[0])) if row and row[0] else 1
        _MAGIC_LV_CACHE[mid] = lv
        return lv
    except Exception:
        return 1


# ------------------------------------------------- nombres de rama en comandos
# Hace falta porque los nombres LLEVAN ESPACIOS: "Staff Hit" y "Eagle Eye" son
# dos palabras. El comando /rama partia por espacios y cogia partes[1] y
# partes[2], asi que "rama Staff Hit Earth" acababa intentando cambiar "Staff"
# por "Hit", y "rama Hit Staff Hit" se quedaba en dos trozos y soltaba el
# cartel de uso. Aqui se parte probando TODOS los cortes y quedandose con el
# que deja dos nombres de rama de verdad.
_ALIAS_ANADIR = ('add', 'anadir', 'añadir', 'mas', 'más', '+')


def numero_de_rama(txt) -> int:
    """El id de una rama por numero o por nombre, o 0."""
    t = str(txt or '').strip()
    if not t:
        return 0
    if t.isdigit():
        n = int(t)
        return n if n in NOMBRE_RAMA else 0
    tl = ' '.join(t.lower().split())
    for sid, nom in NOMBRE_RAMA.items():
        if nom.lower() == tl:
            return sid
    for sid, nom in NOMBRE_RAMA.items():
        if nom.lower().startswith(tl):
            return sid
    return 0


def partir_argumentos_rama(resto: str):
    """('add', dentro) o (fuera, dentro) de lo que sigue a /rama, o None."""
    partes = (resto or '').split()
    if not partes:
        return None
    if partes[0].lower() in _ALIAS_ANADIR:
        dentro = ' '.join(partes[1:]).strip()
        return ('add', dentro) if numero_de_rama(dentro) else None
    if len(partes) < 2:
        return None
    # Se prueban todos los cortes. Se prefiere el que parte mas a la
    # izquierda y deja las dos mitades siendo ramas conocidas.
    for corte in range(1, len(partes)):
        izq = ' '.join(partes[:corte])
        der = ' '.join(partes[corte:])
        if numero_de_rama(izq) and numero_de_rama(der):
            return (izq, der)
    return None
