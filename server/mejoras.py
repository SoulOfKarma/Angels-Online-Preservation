"""Mejoras de equipo: morteros, martillos, piensos y gemas.

Todo lo que decide este modulo sale de los datos del cliente, no de tablas
escritas a mano. Cada objeto de mejora dice en su descripcion hasta que nivel
sirve y cuanto sube, y su categoria dice para que vale:

    強化道具   mortero de mejora, para armas, armaduras y escudos
    強化飼料   pienso de montura
    寵物強化   pienso de mascota
    打孔道具   martillo de perforar, el que abre el hueco de la gema
    寶石       la gema que se mete en ese hueco
    寵物寶石   gema de mascota

Ejemplo de lo que trae un mortero de 11 estrellas:

    Exclusively for enhancing gears under lvl 119. ...
    Weapon: Attack+6%, Spell Attack+6%
    Armor: Defense+3%, Spell Defense+3%
    Shield: Defense+3%, Spell Defense+3%

Y un pienso de montura:

    Feed for mounts under Lvl 209. Increases Attack by 8%, Spell Attack by 8%
    and Movement Speed by 2% ...

Y una gema:

    Weapon: Fire Attack +58,Attack +94
    Armor: HP +110,Defense +41
    Level Requirement: Level 100

De ahi salen el tope de nivel, los porcentajes por tipo de equipo y los bonos
absolutos de la gema. Si manana sale un mortero nuevo, funciona solo.

Lo que NO esta aqui es la conversacion con el cliente: que paquete manda el
juego al usar el mortero y cual contesta el servidor. Eso no se ha capturado
todavia, asi que este modulo es el motor -- las reglas y las cuentas -- y la
parte de red se enchufa cuando haya una captura.
"""
import pathlib
import json
import pathlib
import random
import re
import sqlite3

RAIZ = pathlib.Path(__file__).parent.parent
_DB = RAIZ / 'corpus' / 'content.db'
_TABLAS = ['item', 'item2', 'item3', 'item4', 'item5', 'item6', 'item7',
           'item8', 'item9']

# Hasta donde se puede mejorar una pieza.
MAX_MEJORA = 15
# Cuantos stats verdes caben en la entrada del inventario. Ver el comentario
# de inventario.MAX_EXTRAS: el sexto pisaria el contenedor de la pieza.
MAX_EXTRAS_ENTRADA = 5
# Los stats que solo da un tipo de pieza. Cuando no caben todos, estos se
# quedan: una montura sin velocidad o una mochila sin ranuras no se
# distinguirian de cualquier otra cosa.
EXCLUSIVOS = ('velocidad', 'peso', 'ranuras')

# Cuantos huecos de gema admite una pieza. Lo dijo el usuario: cinco.
MAX_HUECOS = 5

# Los carteles que manda el servidor real, de string.xml. Medidos el
# 29/09/2026 viendo que numero llega en cada caso.
MSG_MEJORA_OK = 1613      # "Succeed in intensifying %s."
MSG_MEJORA_FALLO = 1614   # "%s Failed to intensify"
MSG_HUECO_OK = 1603       # "%s Succeed in cutting a hole"
MSG_HUECO_FALLO = 1604    # "%s Fail to cut a hole"
MSG_HUECO_NIVEL = 1605    # "The level of the props for cutting are not high enough."
MSG_HUECO_TOPE = 1606     # "%s Unable to cut a hole because the upper limit..."
MSG_ATRIBUTOS_OK = 2137   # "%s Change the attribute succeeded."

# Las categorias, tal como vienen en 物品類別.
CAT_MORTERO = '強化道具'
CAT_PIENSO_MONTURA = '強化飼料'
CAT_PIENSO_MASCOTA = '寵物強化'
CAT_PERFORAR = '打孔道具'
CAT_GEMA = '寶石'
CAT_GEMA_MASCOTA = '寵物寶石'
# El "martillo verde": no mejora, REEMPLAZA los atributos extra por otros
# nuevos. Su descripcion lo dice: "Apply it to gear, rides or robots below
# level N to replace their additional attributes bonus with new attributes".
CAT_VERDE = '幸運骰'

CLASES = {
    CAT_MORTERO: 'mortero',
    CAT_PIENSO_MONTURA: 'pienso_montura',
    CAT_PIENSO_MASCOTA: 'pienso_mascota',
    CAT_PERFORAR: 'perforar',
    CAT_GEMA: 'gema',
    CAT_GEMA_MASCOTA: 'gema_mascota',
    CAT_VERDE: 'verde',
}

# Como se llama cada stat en las descripciones, y con que nombre se guarda.
_STATS = [
    ('spell attack', 'matk'), ('spell defense', 'mdef'),
    ('spell def', 'mdef'), ('movement speed', 'velocidad'),
    ('speed', 'velocidad'), ('attack power', 'atk'), ('attack', 'atk'),
    ('defense', 'dfs'), ('fire attack', 'atk_fuego'),
    ('fire defense', 'dfs_fuego'), ('agility', 'agilidad'),
    ('rigor', 'rigor'), ('hp', 'hp'), ('mp', 'mp'),
]
_TIPOS = {'weapon': 'arma', 'armor': 'armadura', 'shield': 'escudo'}

_CACHE = {}


def _fila(item_id):
    """(nombre, categoria, nivel, descripcion) del item, o None."""
    iid = str(int(item_id))
    if iid in _CACHE:
        return _CACHE[iid]
    fila = None
    if _DB.exists():
        con = sqlite3.connect(_DB)
        for t in _TABLAS:
            try:
                r = con.execute('select 基本名稱, 物品類別, 物品等級, 說明定義 '
                                'from %s where id=?' % t, (iid,)).fetchone()
            except sqlite3.OperationalError:
                continue
            if r:
                fila = r
                break
        con.close()
    _CACHE[iid] = fila
    return fila


_INDICE = None


def _indice():
    """{clase: [ids]} de TODOS los objetos de mejora, de una sola pasada.

    Antes cada consulta abria la base y recorria las nueve tablas por un solo
    id. Buscar "todas las gemas" salian trescientas mil consultas y tardaba
    minutos; asi es una por tabla.
    """
    global _INDICE
    if _INDICE is not None:
        return _INDICE
    _INDICE = {c: [] for c in CLASES.values()}
    if not _DB.exists():
        return _INDICE
    con = sqlite3.connect(_DB)
    marcas = ','.join('?' * len(CLASES))
    for t in _TABLAS:
        try:
            filas = con.execute(
                'select id, 基本名稱, 物品類別, 物品等級, 說明定義 from %s '
                'where 物品類別 in (%s)' % (t, marcas),
                list(CLASES)).fetchall()
        except sqlite3.OperationalError:
            continue
        for iid, nom, cat, lv, desc in filas:
            _CACHE.setdefault(str(iid), (nom, cat, lv, desc))
            _INDICE[CLASES[cat]].append(int(iid))
    con.close()
    return _INDICE


def ids_de_clase(clase: str):
    """Todos los ids de una clase: 'gema', 'mortero', 'pienso_montura'..."""
    return list(_indice().get(clase, []))


def clase_de(item_id) -> str:
    """'mortero', 'gema', 'pienso_montura'... o '' si no es de mejora."""
    f = _fila(item_id)
    return CLASES.get(f[1], '') if f else ''


def tope_nivel(item_id) -> int:
    """Hasta que nivel de equipo sirve, leido de la descripcion.

    Las descripciones dicen "under lvl 119", "under Lvl 209", "for rides
    under Lvl 39", "レベル259以下", "tingkat 39 ke bawah", "209級以下", etc.
    Se devuelve ese numero; 0 si no tiene restriccion de nivel (sirve para todo).
    """
    f = _fila(item_id)
    if not f or not f[3]:
        return 0
    desc = f[3]
    for patron in (
        r'under\s+lvl\s*(\d+)',
        r'below\s+level\s*(\d+)',
        r'under\s+level\s*(\d+)',
        r'below\s+lvl\s*(\d+)',
        r'lvl\s*(\d+)\s*or\s+below',
        r'level\s*(\d+)\s*or\s+below',
        r'(\d+)\s*[級级]\s*以下',
        r'等[級级]\s*(\d+)\s*以下',
        r'レベル\s*(\d+)\s*以下',
        r'tingkat\s+(\d+)\s+ke\s+bawah',
        r'dibawah\s+level\s+(\d+)',
        r'under\s*(\d+)\s*level',
    ):
        m = re.search(patron, desc, re.I)
        if m:
            return int(m.group(1))
    return 0


def nivel_requerido(item_id) -> int:
    """El nivel que la gema EXIGE al arma. 0 si no lo dice.

    Una gema de nivel 120 solo entra en equipo de 120 para arriba, nunca al
    reves: eso es lo que hace que una Purple Light Rune no se pueda meter en
    un arma de 110.
    """
    f = _fila(item_id)
    if not f or not f[3]:
        return 0
    m = re.search(r'level\s+requirement\s*:\s*level\s*(\d+)', f[3], re.I)
    return int(m.group(1)) if m else 0


def _leer_stats(trozo: str, porcentaje: bool):
    """Saca {stat: valor} de un trozo como 'Attack+6%, Spell Attack+6%'."""
    out = {}
    patron = r'([A-Za-z][A-Za-z ]*?)\s*\+?\s*(\d+)\s*%' if porcentaje \
        else r'([A-Za-z][A-Za-z ]*?)\s*\+\s*(\d+)'
    for nom, val in re.findall(patron, trozo):
        nom = nom.strip().lower()
        for etiqueta, clave in _STATS:
            if nom.endswith(etiqueta):
                out[clave] = int(val)
                break
    return out


def bonos_de(item_id):
    """Lo que sube ese objeto, por tipo de equipo.

    Devuelve {'arma': {...}, 'armadura': {...}, 'escudo': {...}} o, si la
    descripcion no separa por tipo -- como la del pienso de montura --, un
    solo {'todos': {...}}. Los morteros y los piensos van en POR CIENTO; las
    gemas, en valores absolutos.
    """
    f = _fila(item_id)
    if not f or not f[3]:
        return {}
    desc = f[3]
    cl = clase_de(item_id)
    pct = cl in ('mortero', 'pienso_montura', 'pienso_mascota')
    out = {}
    for linea in desc.split('\n'):
        m = re.match(r'\s*(Weapon|Armor|Shield)\s*[:：]\s*(.+)', linea, re.I)
        if m:
            stats = _leer_stats(m.group(2), pct)
            if stats:
                out[_TIPOS[m.group(1).lower()]] = stats
    if not out:
        # El pienso de montura lo dice en prosa, todo en la misma frase.
        stats = _leer_stats(desc, pct)
        if stats:
            out['todos'] = stats
    return out


# Lo que sube un mortero cuando su descripcion NO lo dice.
#
# Los de once estrellas para arriba lo escriben: "Weapon: Attack+6%, Spell
# Attack+6% / Armor: Defense+3%, Spell Defense+3%". Los de diez para abajo no
# dicen nada, y son 85 de los 92 que hay. Se les da lo mismo que declaran sus
# hermanos mayores, que es lo unico que respaldan los datos.
BONOS_POR_DEFECTO = {
    'arma': {'atk': 6, 'matk': 6},
    'armadura': {'dfs': 3, 'mdef': 3},
    'escudo': {'dfs': 3, 'mdef': 3},
    'montura': {'atk': 8, 'matk': 8, 'velocidad': 2},
}

# Y lo que sube un pienso de montura, que si lo dicen todos.
BONOS_MONTURA = {'atk': 8, 'matk': 8, 'velocidad': 2}

BONOS_MASCOTA = {'atk': 8, 'matk': 8, 'dfs': 5, 'mdef': 5, 'hp': 50}



def puede_perforar(item_id, nivel_equipo: int, tipo: str):
    """Si ese martillo puede abrir un hueco en esa pieza."""
    if clase_de(item_id) != 'perforar':
        return False, 'no es un martillo de perforar'
    tope = tope_nivel(item_id)
    # Nivel maximo de herramientas (40-star / tope >= 400): cubren todo el equipo endgame (410+)
    if tope and tope < 400 and nivel_equipo > tope:
        return False, ('sirve hasta nivel %d y la pieza es de %d'
                       % (tope, nivel_equipo))
    if tipo not in ('arma', 'armadura', 'escudo'):
        return False, 'solo se perforan armas, armaduras y escudos'
    return True, ''


def perforar(estado: dict, ranura, item_id, nivel_equipo: int, tipo: str,
             exito_seguro: bool = False, rng=None, bono_primer_hueco: float = 0.0):
    """Abre un hueco de gema. CUIDADO: fallar aqui cuesta caro.

    El martillo no se porta como el mortero. Su descripcion lo dice: "No
    damage to the gear if the piercing failed but former hole and diamond
    inside will vanish". O sea que la pieza no se rompe, pero el hueco que ya
    tenia -- y la gema que hubiera dentro -- desaparecen.
    """
    rng = rng or random
    st = estado.setdefault(int(ranura), {'veces': 0, 'gemas': [],
                                         'extra': {}, 'huecos': 0})
    st.setdefault('veces', 0)
    st.setdefault('gemas', [])
    st.setdefault('extra', {})
    st.setdefault('huecos', 0)
    ok, motivo = puede_perforar(item_id, nivel_equipo, tipo)
    if not ok:
        return False, motivo
    if st.get('huecos', 0) >= MAX_HUECOS:
        return False, 'la pieza ya tiene los %d huecos' % MAX_HUECOS
    # NO se puede abrir un hueco nuevo con el anterior vacio: hay que meterle
    # una gema primero. Lo dijo el usuario y encaja con que fallar se lleve
    # "el hueco anterior y la gema de dentro" -- si pudieras acumular huecos
    # vacios, esa frase no tendria sentido.
    if st.get('huecos', 0) > len(st['gemas']):
        return False, 'hay que engarzar una gema antes de abrir otro hueco'
    chance = probabilidad(st.get('huecos', 0))
    if st.get('huecos', 0) == 0:
        chance = min(1.0, chance + max(0.0, bono_primer_hueco))
    if exito_seguro or rng.random() < chance:
        st['huecos'] = st.get('huecos', 0) + 1
        return True, 'hueco abierto (%d)' % st['huecos']
    # Al fallar se pierde el ultimo hueco y lo que llevara dentro.
    if st.get('huecos', 0) > 0:
        st['huecos'] -= 1
        if st['gemas']:
            perdida = st['gemas'].pop()
            return False, 'fallo: se perdio el hueco y la gema %d' % perdida
        return False, 'fallo: se perdio el hueco anterior'
    return False, 'fallo, pero no habia ningun hueco que perder'


def engarzar(estado: dict, ranura, gema_id, nivel_equipo: int, tipo: str):
    """Mete una gema en un hueco libre."""
    st = estado.setdefault(int(ranura), {'veces': 0, 'gemas': [],
                                         'extra': {}, 'huecos': 0})
    st.setdefault('veces', 0)
    st.setdefault('gemas', [])
    st.setdefault('extra', {})
    st.setdefault('huecos', 0)
    libres = st.get('huecos', 0) - len(st['gemas'])
    ok, motivo = puede_engarzar(gema_id, nivel_equipo, tipo, libres)
    if not ok:
        return False, motivo
    st['gemas'].append(int(gema_id))
    return True, 'gema engarzada'


def puede_mejorar(item_id, nivel_equipo: int, tipo: str, veces: int):
    """(True, '') si ese objeto sirve para esa pieza, o (False, motivo)."""
    cl = clase_de(item_id)
    if not cl:
        return False, 'no es un objeto de mejora'
    if veces >= MAX_MEJORA:
        return False, 'ya esta al maximo (+%d)' % MAX_MEJORA
    tope = tope_nivel(item_id)
    # Nivel maximo de herramientas (40-star / tope >= 400): cubren todo el equipo endgame (410+)
    if tope and tope < 400 and nivel_equipo > tope:
        return False, ('sirve hasta nivel %d y la pieza es de %d'
                       % (tope, nivel_equipo))
    if cl == 'pienso_montura' and tipo != 'montura':
        return False, 'el pienso es solo para monturas y robots'
    if cl == 'pienso_mascota' and tipo != 'mascota':
        return False, 'ese pienso es solo para mascotas'
    if cl == 'mortero' and tipo not in ('arma', 'armadura', 'escudo', 'montura'):
        return False, 'el mortero es para armas, armaduras, escudos y monturas/robots'
    return True, ''


def puede_engarzar(gema_id, nivel_arma: int, tipo: str, huecos_libres: int):
    """Si esa gema entra en esa pieza."""
    if clase_de(gema_id) not in ('gema', 'gema_mascota'):
        return False, 'no es una gema'
    if huecos_libres < 1:
        return False, 'no hay ningun hueco libre'
    req = nivel_requerido(gema_id)
    if req and nivel_arma < req:
        return False, ('la gema es de nivel %d y la pieza es de %d: solo se '
                       'puede de ese nivel hacia arriba' % (req, nivel_arma))
    if tipo not in ('arma', 'armadura', 'escudo'):
        return False, 'las gemas van en armas, armaduras y escudos'
    return True, ''


def stats_de_mejora(item_id, tipo: str, veces: int):
    """Los porcentajes acumulados de llevar `veces` mejoras con ese objeto."""
    b = bonos_de(item_id)
    base = b.get(tipo) or b.get('todos')
    if not base:
        cl = clase_de(item_id)
        if cl == 'pienso_montura':
            base = BONOS_MONTURA
        elif cl == 'pienso_mascota':
            base = BONOS_MASCOTA
        elif cl == 'mortero':
            base = BONOS_POR_DEFECTO.get(tipo, {})
        else:
            base = {}
    return {k: v * veces for k, v in base.items()}


# Los rangos que el cuadro del juego enseña al usar el martillo verde:
# "Attack 0 (0-210), Defense 0 (0-210), Spell Attack 0 (0-210), Spell Defense
# 0 (0-210), Rigor 3 (0-54), Agility 0 (0-54), Movement Speed 37 (0-40)".
# Salen de una captura de pantalla, no de los datos: si dependen del nivel de
# la pieza, todavia no se sabe.
# Que stats reparte el martillo verde, POR TIPO DE PIEZA.
#
# Antes habia una sola tabla para todo y estaba mal por los dos lados: le
# daba ataque a unas botas y defensa a una espada, y no daba nunca ni vida ni
# mana, que son los dos que mas aparecen. Esto sale de contar los stats
# verdes de las entradas capturadas, agrupados por la categoria del item:
#
#   armas (劍 斧 刀 槍 弓箭 杖 影刃)  hp, mp, atk, matk, rigor -- ni una sola
#                                      vez defensa en 700 registros
#   armadura (衣服 頭飾 鞋子 手套)     hp, mp, dfs, mdef, agilidad -- nunca atk
#   montura (座騎)                     los de combate mas VELOCIDAD, que no
#                                      aparece en ninguna otra pieza
#   mochila (背包)                     hp, mp, dfs
#   capa (披風)                        hp, mp, dfs, mdef, agilidad
#   accesorio (飾品)                   dfs, mdef, rigor, agilidad
#
# Los topes son los mas altos vistos de cada uno. OJO: el rango de verdad
# sube con el nivel de la pieza -- en los 刀 el ataque va de 19 a 3794 segun
# el arma -- y esa relacion no esta resuelta. Aqui se usa el tope observado,
# que sirve para probar pero no es la formula del juego.
RANGOS_POR_TIPO = {
    'arma': {'hp': (0, 270), 'mp': (0, 253), 'atk': (0, 3794),
             'matk': (0, 519), 'rigor': (0, 230), 'agilidad': (0, 92)},
    'armadura': {'hp': (0, 240), 'mp': (0, 178), 'dfs': (0, 1051),
                 'mdef': (0, 137), 'agilidad': (0, 24)},
    # La velocidad va DELANTE: solo la dan las monturas y solo caben cinco.
    'montura': {'velocidad': (0, 40), 'atk': (0, 200), 'matk': (0, 105),
                'dfs': (0, 192), 'mdef': (0, 137), 'rigor': (0, 20),
                'agilidad': (0, 40)},
    # Una mochila da ademas PESO y RANURAS, que no los da ninguna otra
    # pieza. Medido en una Green Beetle Bag de nivel 45: peso hasta 278
    # y 9 casillas. El cuadro del juego los lista como "Maximum Weight"
    # y "Backpack slots".
    'mochila': {'hp': (0, 29), 'mp': (0, 32), 'dfs': (0, 22),
                'peso': (0, 278), 'ranuras': (0, 9)},
    'capa': {'hp': (0, 45), 'mp': (0, 31), 'dfs': (0, 23),
             'mdef': (0, 10), 'agilidad': (0, 6)},
    'accesorio': {'dfs': (0, 74), 'mdef': (0, 9), 'rigor': (0, 25),
                  'agilidad': (0, 20)},
}

CATEGORIAS_VERDE = {
    '劍': 'arma', '斧': 'arma', '刀': 'arma', '槍': 'arma',
    '弓箭': 'arma', '彈弓': 'arma', '杖': 'arma', '影刃': 'arma',
    '鎚': 'arma', '锤': 'arma', '釣竿': 'arma', '鐵鍬': 'arma',
    '衣服': 'armadura', '頭飾': 'armadura',
    '鞋子': 'armadura', '手套': 'armadura',
    '座騎': 'montura', '機甲': 'montura',
    '背包': 'mochila', '披風': 'capa',
    '飾品': 'accesorio', '徽章': 'accesorio',
}


# LOS RANGOS VERDES SALEN DE adv.xml, volcado por tools/verdes_de_adv_xml.py
# a plantillas/verdes.json. No hay formula: es una tabla de 2645 filas, por
# PARTE y NIVEL, con el minimo y el maximo de cada stat.
#
# Aqui hubo antes dos intentos de deducir una formula (primero un tope fijo
# por categoria, luego 5*nivel-60) y los dos estaban mal. Lo que los tumbo
# fue usar el mismo martillo en dos piezas y ver que daban rangos distintos.
#
# Comprobado contra el juego sin una sola discrepancia:
#   武器杖 nv300  HP 344, atk 2428, matk 697, agilidad 30
#   座騎 nv45     combate 17, rigor/agi 13, velocidad 14
#   座騎 nv90     combate 50, rigor/agi/velocidad 22
#   背包 nv45     defensa 24, peso 50-325, ranuras 10
TABLA_VERDES = (pathlib.Path(__file__).parent / 'plantillas' / 'verdes.json')

# La categoria de item.xml -> la parte de adv.xml, para lo que no necesita
# saber si es ligera, pesada o tunica.
PARTE_POR_CATEGORIA = {
    '劍': '武器刀劍', '刀': '武器刀劍',
    '斧': '武器斧鎚', '鎚': '武器斧鎚', '锤': '武器斧鎚',
    '弓箭': '武器弓彈', '彈弓': '武器弓彈', '槍': '武器槍',
    '杖': '武器杖', '影刃': '武器影刃',
    '釣竿': '武器杖', '鐵鍬': '武器斧鎚',
    '盾': '盾牌', '座騎': '座騎',
    '背包': '背包', '披風': '披風',
    '飾品': '飾品', '徽章': '飾品',
    '機甲': '機甲',
}

# Las que si lo necesitan: se les pega 袍, 輕 o 重 detras.
CATEGORIAS_CON_PESO = {
    '衣服': '衣服', '頭飾': '頭飾',
    '手套': '手套', '鞋子': '鞋子',
}
PESOS = ('袍', '輕', '重')     # tunica, ligera, pesada

_VERDES = {}


def _tabla_verdes():
    if _VERDES:
        return _VERDES
    try:
        _VERDES.update(json.loads(TABLA_VERDES.read_text(encoding='utf-8')))
    except Exception:
        pass
    return _VERDES


def _fila_verde(parte, nivel):
    """La fila de esa parte para ese nivel; adv.xml va de cinco en cinco."""
    t = _tabla_verdes().get(parte) or {}
    if not t:
        return None
    niveles = sorted(int(x) for x in t)
    elegido = niveles[0]
    for n in niveles:
        if n <= nivel:
            elegido = n
        else:
            break
    return t[str(elegido)]


def nivel_de_pieza(item_id):
    """El 物品等級 del item, que es con el que se entra en adv.xml."""
    import inventario as _inv
    try:
        return int(_inv.nivel_de_item(item_id) or 1)
    except Exception:
        return 1


def parte_de(item_id):
    """A que fila de adv.xml le toca esa pieza.

    Las armaduras se parten en tunica, ligera y pesada, y en item.xml solo
    esta la marca de tunica (身體袍). Las otras dos se distinguen por la
    proporcion entre su defensa y su defensa magica, que las separa de
    sobra: a nivel 80 la tunica va 64/64, la ligera 126/20 y la pesada
    190/18.
    """
    import inventario as _inv
    cat = _inv.categoria_item(item_id) or ''
    if cat in PARTE_POR_CATEGORIA:
        return PARTE_POR_CATEGORIA[cat]
    base = CATEGORIAS_CON_PESO.get(cat)
    if not base:
        return None
    d, m = _defensas(item_id)
    if not d and not m:
        return base + PESOS[1]
    razon = (d / m) if m else 99.0
    nivel = nivel_de_pieza(item_id)
    mejor, dist = None, None
    for peso in PESOS:
        f = _fila_verde(base + peso, nivel)
        if not f or not f.get('dfs') or not f.get('mdef'):
            continue
        r = f['dfs'][1] / max(1, f['mdef'][1])
        if dist is None or abs(r - razon) < dist:
            mejor, dist = base + peso, abs(r - razon)
    return mejor or (base + PESOS[1])


def _defensas(item_id):
    """(defensa, defensa magica) del propio objeto, de item.xml."""
    try:
        import sqlite3
        import inventario as _inv
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if not db.exists():
            return (0, 0)
        row = _inv.fila_item(sqlite3.connect(db), '"def", "mdef"', item_id)
        if not row:
            return (0, 0)
        return (int(row[0] or 0) if str(row[0] or '').isdigit() else 0,
                int(row[1] or 0) if str(row[1] or '').isdigit() else 0)
    except Exception:
        return (0, 0)


def rangos_verde(item_id):
    """Los rangos de stats verdes de esa pieza, tal cual los da el juego."""
    parte = parte_de(item_id)
    fila = _fila_verde(parte, nivel_de_pieza(item_id)) if parte else None
    if fila:
        res = {st: (v[0], v[1]) for st, v in fila.items() if v[1] > 0}
        if res:
            return res
    # Respaldo por tipo si no esta en la tabla adv.xml
    import inventario as _inv
    cat = _inv.categoria_item(item_id) or ''
    tipo = CATEGORIAS_VERDE.get(cat)
    if not tipo:
        r = _inv.ranura_equipo_de(item_id)
        if r in (10, 174): tipo = 'montura'
        elif r in (3, 4, 169, 170): tipo = 'arma'
        elif r in (8, 9, 173): tipo = 'accesorio'
        elif r == 14: tipo = 'mochila'
        elif r == 13: tipo = 'capa'
        elif r in (1, 2, 5, 6, 7, 168, 171, 172): tipo = 'armadura'
    if tipo and tipo in RANGOS_POR_TIPO:
        return RANGOS_POR_TIPO[tipo]
    return {}


def tirar_verde(rangos, todos: bool = False, rng=None):
    """El martillo verde: reparte stats al azar dentro de sus rangos.

    `rangos` es {stat: (minimo, maximo)}, que es lo que el cliente enseña en
    su cuadro: "Attack 0 (0-210), Rigor 3 (0-54)"...

    Con `todos` puesto sale el maximo de TODOS los stats a la vez, que es la
    bandera que se pidio para probar. Sin ella se sortea cada uno.
    """
    rng = rng or random
    out = {}
    for stat, (lo, hi) in rangos.items():
        out[stat] = hi if todos else rng.randint(lo, hi)
    # En la entrada solo caben CINCO. Con la bandera de "todos los stats"
    # salian siete y los dos ultimos se escribian encima del contenedor de
    # la pieza, lo que cerraba el cliente. Se quedan los cinco PRIMEROS de
    # la tabla, no los de numero mas alto: en una montura la velocidad vale
    # 40 y el ataque 200, asi que cortando por valor se perdia justo lo que
    # distingue a una montura.
    if len(out) > MAX_EXTRAS_ENTRADA:
        # Los que solo da una clase de pieza van primero: la velocidad es de
        # las monturas y el peso y las ranuras de las mochilas. Cortando por
        # el orden de la tabla se perdia justo lo que distingue a la pieza.
        orden = sorted(out, key=lambda k: (k not in EXCLUSIVOS,
                                           list(out).index(k)))
        out = {k: out[k] for k in orden[:MAX_EXTRAS_ENTRADA]}
    return out


def aplicar(estado: dict, ranura, item_id, nivel_equipo: int, tipo: str,
            exito_seguro: bool = False, rng=None, bono_cuarta_mejora: float = 0.0):
    """Usa un objeto de mejora sobre la pieza de esa ranura.

    `estado` es el diccionario de mejoras del personaje, {ranura: {...}}. Se
    modifica en el sitio y se devuelve (ok, mensaje).

    Si falla NO se rompe nada, que es lo que dicen todas las descripciones:
    "No damage to the gear if the enhancement fails but the number of times
    the gear can be enhanced decreases by 1". O sea que un fallo gasta un
    intento igual.
    """
    rng = rng or random
    st = estado.setdefault(int(ranura), {'veces': 0, 'gemas': [],
                                         'extra': {}, 'huecos': 0})
    st.setdefault('veces', 0)
    st.setdefault('gemas', [])
    st.setdefault('extra', {})
    st.setdefault('huecos', 0)
    ok, motivo = puede_mejorar(item_id, nivel_equipo, tipo, st['veces'])
    if not ok:
        return False, motivo
    chance = probabilidad(st['veces'])
    if st['veces'] == 3:
        chance = min(1.0, chance + max(0.0, bono_cuarta_mejora))
    if not exito_seguro and rng.random() >= chance:
        # AL FALLAR SE BAJA UN NIVEL. Lo dice la descripcion, aunque se leyo
        # mal la primera vez: "No damage to the gear if the enhancement fails
        # but the number of times the gear has been enhanced decreases by 1".
        # No son los intentos que quedan, es el +N.
        #
        # La captura del 29/09/2026 lo confirma. Sobre unas Boots Of Contempt:
        #     exito -> +6
        #     FALLO
        #     exito -> +6     <- volvio al 6, o sea que el fallo lo dejo en 5
        #     exito -> +7
        #     FALLO
        # Si el fallo no restara, el segundo exito habria dado +7.
        st['veces'] = max(0, st['veces'] - 1)
        return False, 'la mejora fallo y bajo a +%d' % st['veces']
    st['veces'] += 1
    return True, '+%d' % st['veces']


def probabilidad(veces: int) -> float:
    """Que probabilidad tiene el siguiente intento.

    No esta medida: no hay ninguna captura de un fallo. Se pone una curva que
    baja con el nivel de mejora, empezando en segura y llegando al 20% en la
    ultima. En cuanto haya numeros de verdad se cambia aqui y ya.
    """
    if veces <= 3:
        return 1.0
    return max(0.20, 1.0 - (veces - 3) * 0.07)


def pct_por_mejoras(tipo: str, veces: int) -> dict:
    """Los porcentajes que da llevar `veces` mejoras en una pieza de ese tipo.

    No hace falta saber con que mortero se hizo: la pieza solo guarda cuantas
    veces. Los porcentajes son los de BONOS_POR_DEFECTO, y el 6% de las armas
    esta comprobado contra el juego -- un arma a +15 con 19373 de ataque base
    enseñaba "+18885", que quitando el verde es el 90,05% de la base.
    """
    base = BONOS_POR_DEFECTO.get(tipo) or {}
    if tipo == 'montura':
        base = BONOS_MONTURA
    return {k: v * int(veces or 0) for k, v in base.items()}


def tipo_de_ranura(ranura, item_id=None):
    """'arma', 'escudo', 'montura' o 'armadura' segun donde este puesta.

    Si en la mano izquierda (ranura 4 o 170) se lleva un arma dual (espada o
    hacha) en lugar de un escudo, sus mejoras "+N" son de 'arma' (+6% atk/matk
    por mejora) para que el L.Atk coincida con el R.Atk.
    """
    if item_id:
        try:
            import inventario as _iv
            cat = _iv.categoria_item(int(item_id))
            if cat in ('座騎', '機甲'):
                return 'montura'
        except Exception:
            pass
    r = int(ranura)
    if r in (10, 174):
        return 'montura'
    if r == 3 or r == 169:
        return 'arma'
    if r == 4 or r == 170:
        if item_id:
            try:
                import inventario as _iv
                if _iv.es_arma_dual(int(item_id)) or _iv.ranura_equipo_de(int(item_id)) in (3, 169):
                    return 'arma'
            except Exception:
                pass
        return 'escudo'
    return 'armadura'
