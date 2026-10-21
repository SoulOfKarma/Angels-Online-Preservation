"""Bolsas de la suerte, huevos y regalos: que al abrirlos salga algo.

Son 22.055 items entre las dos categorias que usa el juego -- 紅包, que es
"sobre rojo" y agrupa las lucky bags y los huevos, y 禮物, que son los
regalos -- y hasta ahora ninguno hacia nada al usarlo.

DONDE ESTA EL CONTENIDO. En la columna 動態資料1 del propio item, cuando
apunta a una fila de drop_table: se tira entre sus items con sus pesos. Son
3.818 de los 22.055.

COMO SE SUPO. El Angel Treasure Lucky Bag, el item 3733, tiene 動態資料1=698,
y la fila 698 de drop_table se llama literalmente "Angel Treasure Lucky Bag".
Sus pesos suman 1000, que es exactamente su columna `factor`, asi que el
sorteo es un peso simple sobre el factor. Y hay una segunda confirmacion que
no depende de nada de esto: la descripcion del item lista los premios en
texto -- "Open it to get one of the following things randomly: Stealth Ring,
Swift Ring, Power Ring, Ice Magic Cat, Fiery Nightwolf, Beast God of Forest,
Marmot..." -- y son, en ese orden, los item1, item2, item3, item4, item5,
item6 y item7 de la fila 698.

LOS OTROS 18.199 NO SE ABREN, Y ES A PROPOSITO. En ellos el 動態資料1 no
apunta a ninguna tabla, y el primer intento dio por hecho que entonces era
el id del item que sale. ERA FALSO, y lo destapo el usuario con un caso
concreto: el Kyrio Angel Magic Stone sellado (60534) tiene 動態資料1=22430,
pero al desellarlo NO sale el item 22430 -- que es "Transform into Cactus" --
sino el 63816, que es la piedra sin sellar. El numero existe como item, pero
eso no prueba nada: casi cualquier numero de ese rango existe como item.

Se probaron y se descartaron dos lecturas mas: que fuera el gemelo con el
mismo nombre base (de doce items "Sealed" mirados, el 動態資料1 no apuntaba
al gemelo en NINGUNO) y que fuera una fila de exchange.xml (las filas
existen -- el fichero tiene 22.684 -- pero su premio y su material no son el
item esperado en ninguno de los cuatro casos probados).

Asi que hasta saber que es ese numero, esas bolsas se dejan sin abrir. Mas
vale que no hagan nada a que den el item equivocado.

EL FACTOR NO SIEMPRE SE RESPETA. Hay tablas cuyos pesos no suman su factor;
en esas se sortea sobre la suma real, que es lo unico que no se puede
equivocar. Si una tabla no tiene ni un item utilizable, la bolsa NO se gasta:
mas vale que el jugador se quede con ella que perderla a cambio de nada.
"""
import logging
import pathlib
import random
import re
import sqlite3

log = logging.getLogger('bolsas')

CAT_BOLSA = '紅包'       # sobre rojo: lucky bags y huevos
CAT_REGALO = '禮物'      # regalos
COL_NOMBRE = '基本名稱'
COL_CATEGORIA = '物品類別'
COL_DINAMICO = '動態資料1'
TABLAS_ITEM = ('item', 'item2', 'item3', 'item4', 'item5',
               'item6', 'item7', 'item8', 'item9')

_CACHE = None


def _db():
    return pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'


def _cargar():
    """item_id -> ('tabla', id) o ('item', id). Todo de una vez.

    De una vez porque abrir content.db por cada uso costaria un tiron, y son
    22.000 filas que entran en memoria sin despeinarse.
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    _CACHE = {}
    db = _db()
    if not db.exists():
        return _CACHE
    try:
        con = sqlite3.connect(db)
        tablas = {str(r[0]) for r in con.execute('select id from drop_table')}
        for t in TABLAS_ITEM:
            cols = [c[1] for c in con.execute('pragma table_info(%s)' % t)]
            if COL_CATEGORIA not in cols or COL_DINAMICO not in cols:
                continue
            for iid, cat, din in con.execute(
                    'select id, "%s", "%s" from %s where "%s" in (?, ?)'
                    % (COL_CATEGORIA, COL_DINAMICO, t, COL_CATEGORIA),
                    (CAT_BOLSA, CAT_REGALO)):
                d = str(din or '').strip()
                try:
                    clave = int(iid)
                except (TypeError, ValueError):
                    continue
                if clave in _CACHE or not d or d == '0':
                    continue
                if d in tablas:
                    _CACHE[clave] = ('tabla', d)
                # Si no es una tabla NO se guarda: ver la nota de arriba.
        con.close()
    except Exception as e:
        log.warning('no se pudo leer el contenido de las bolsas (%s: %s); '
                    'no se abrira ninguna', type(e).__name__, e)
    return _CACHE


_CACHE_EXTRA = None
_DROPS_EXTRA = None


def _cargar_drops_extra():
    global _DROPS_EXTRA
    if _DROPS_EXTRA is not None:
        return _DROPS_EXTRA
    _DROPS_EXTRA = {}
    p = pathlib.Path(__file__).parent / 'plantillas' / 'drops_bolsas.json'
    if p.exists():
        try:
            import json
            _DROPS_EXTRA = json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:
            log.warning('no se pudo cargar drops_bolsas.json (%s: %s)', type(e).__name__, e)
    return _DROPS_EXTRA


def _cargar_extra():
    global _CACHE_EXTRA
    if _CACHE_EXTRA is not None:
        return _CACHE_EXTRA
    _CACHE_EXTRA = {}
    drops_extra = _cargar_drops_extra()
    if not drops_extra:
        return _CACHE_EXTRA
    db = _db()
    if not db.exists():
        return _CACHE_EXTRA
    try:
        con = sqlite3.connect(db)
        cache_base = _cargar()
        tablas_db = {str(r[0]) for r in con.execute('select id from drop_table')}
        openable_cats = (CAT_BOLSA, CAT_REGALO, '扭蛋', '禮盒', '寶箱')
        for t in TABLAS_ITEM:
            cols = [c[1] for c in con.execute('pragma table_info(%s)' % t)]
            if COL_CATEGORIA not in cols or COL_DINAMICO not in cols:
                continue
            for iid, cat, din in con.execute(
                    'select id, "%s", "%s" from %s where "%s" in (?, ?, ?, ?, ?)'
                    % (COL_CATEGORIA, COL_DINAMICO, t, COL_CATEGORIA),
                    openable_cats):
                d = str(din or '').strip()
                try:
                    clave = int(iid)
                except (TypeError, ValueError):
                    continue
                if clave in cache_base or clave in _CACHE_EXTRA or not d or d == '0':
                    continue
                # Si no estaba en el drop_table de content.db pero esta en drops_bolsas.json
                # o es de una categoria extendida (扭蛋, 禮盒, 寶箱) que esta en drop_table
                if d not in tablas_db and (d in drops_extra or (d.isdigit() and int(d) in drops_extra)):
                    _CACHE_EXTRA[clave] = ('tabla', d)
                elif cat in ('扭蛋', '禮盒', '寶箱') and d in tablas_db:
                    _CACHE_EXTRA[clave] = ('tabla', d)
        con.close()
    except Exception as e:
        log.warning('no se pudo cargar cache extra de bolsas (%s: %s)', type(e).__name__, e)
    return _CACHE_EXTRA


# Items especiales de mision que se abren con probabilidad (Earth Fruit, Fire Heart)
OBJETOS_MISION_OPENABLES = {
    12603: {  # Earth Fruit
        'recompensa': 12604,  # Elite Core
        'prob': 0.50,        # 50% de probabilidad al abrir
        'nombre_recompensa': 'Elite Core',
        'msg_exito': 'You got Elite Core x1!',
        'msg_fallo': 'The Earth Fruit did not contain an Elite Core.',
        'qid': 976,
    },
    8396: {   # Fire Heart
        'recompensa': 8397,   # Mutant Element
        'prob': 0.40,        # 40% segun serv_drop.xml
        'nombre_recompensa': 'Mutant Element',
        'msg_exito': 'You got Mutant Element x1!',
        'msg_fallo': 'The Fire Heart crumbled to ash.',
        'qid': 912,
    }
}


# Piedras magicas selladas: al hacer clic derecho se desellan a su version activa
PIEDRAS_SELLADAS = {
    35533: 35530,  # Grand Angel Magic Stone
    40530: 40533,  # Exu Angel Magic Stone
    58143: 58146,  # Virt Angel Magic Stone
    60534: 63816,  # Kyrio Angel Magic Stone
    63813: 63816,  # Kyrio Angel Magic Stone
    64974: 64977,  # Opha Angel Magic Stone
    66633: 66636,  # Cheru Angel Magic Stone
    69931: 69934,  # Sera Angel Magic Stone
    72572: 72575,  # Singing Angel Magic Stone
    75122: 75125,  # Angel Magic Stone
    78143: 78146,  # Meteor Angel Magic Stone
    81301: 81304,  # Starfall Angel Magic Stone
}


# ---------------------------------------------------------------------------
# REGALOS SIN TABLA: LO QUE DICE SU DESCRIPCION
#
# El 動態資料1 de esos regalos es un id de monster.xml (la Enchanted-Cozy Xmas
# Suitcase (F), 50794, apunta al 19596 "附魔-暖愛聖誕淑女服飾衣箱", que es la
# propia caja) y su 掉寶編號 es una tabla de caida que el cliente NO trae: era
# del servidor oficial. Lo unico que queda es la descripcion, que lista el
# contenido: "Requires 6 slots and above to open. Open to get: A, B, C..." da
# TODO; "Open it to get one of the following things" / "a chance to get" da
# UNO al azar. Son 1.766 regalos asi (21/10/2026, reporte del usuario).
#
# Los nombres se buscan como 原型名稱 + 基本名稱. Si hay varios objetos con el
# mismo nombre (variantes de chico/chica, de nivel...), se toma el de id mas
# cercano a la caja: salen en el mismo lote. Si un nombre no se encuentra, o
# es una mascota, la caja no se abre (mejor que dar algo a medias).
# ---------------------------------------------------------------------------

_DESCRITOS = None
_POR_NOMBRE = None
_CAT = {}


def _cargar_descripciones():
    global _DESCRITOS, _POR_NOMBRE
    if _DESCRITOS is not None:
        return _DESCRITOS
    _DESCRITOS, _POR_NOMBRE = {}, {}
    db = _db()
    if not db.exists():
        return _DESCRITOS
    try:
        con = sqlite3.connect(db)
        for t in TABLAS_ITEM:
            cols = [c[1] for c in con.execute('pragma table_info(%s)' % t)]
            if '說明定義' not in cols:
                continue
            for iid, pref, base, cat, desc in con.execute(
                    'select id, "原型名稱", "基本名稱", "物品類別", "說明定義" from %s' % t):
                try:
                    iid = int(iid)
                except (TypeError, ValueError):
                    continue
                nombre = ((pref or '') + (base or '')).strip().lower()
                if nombre:
                    _POR_NOMBRE.setdefault(nombre, []).append(iid)
                _CAT[iid] = cat
                if cat in (CAT_BOLSA, CAT_REGALO) and desc:
                    _DESCRITOS[iid] = desc
        con.close()
    except Exception:
        log.exception('no se pudieron leer las descripciones de los regalos')
    return _DESCRITOS


_RE_LISTA = re.compile(r'open[^:\n]{0,60}:\s*(.*)', re.S | re.I)


def contenido_descrito(item_id: int):
    """('todo' | 'uno', [(item, cantidad)], casillas pedidas) o None."""
    import html
    iid = int(item_id or 0)
    desc = _cargar_descripciones().get(iid)
    if not desc:
        return None
    desc = html.unescape(desc)
    m = _RE_LISTA.search(desc)
    if not m:
        return None
    cabecera = desc[:m.start(1)].lower()
    modo = 'uno' if re.search(r'one of|chance|randomly|random', cabecera) else 'todo'
    texto = re.sub(r'/c\$\d|/c\*', '', m.group(1))          # colores del cliente
    texto = re.split(r'\n\s*\n|\(', texto)[0]
    premios = []
    for trozo in re.split(r'\n|,|\band\b', texto):
        trozo = trozo.strip(' .;-\t')
        if not trozo:
            continue
        cant = 1
        mc = re.search(r'\s*[x×*]\s*(\d+)$', trozo)
        if mc:
            cant, trozo = int(mc.group(1)), trozo[:mc.start()].strip()
        cands = _POR_NOMBRE.get(trozo.lower())
        if not cands:
            return None
        elegido = min(cands, key=lambda c: abs(c - iid))
        if _CAT.get(elegido) == '寵物':
            return None
        premios.append((elegido, cant))
    if not premios:
        return None
    mh = re.search(r'requires (\d+) slots', desc, re.I)
    huecos = int(mh.group(1)) if mh else (1 if modo == 'uno' else len(premios))
    return modo, premios, huecos


def es_bolsa(item_id: int) -> bool:
    iid = int(item_id or 0)
    return iid in _cargar() or iid in _cargar_extra()


_TABLA_CACHE = {}


def _sorteo(tabla_id):
    """(item, cuantos) de esa tabla, por peso. None si no hay nada que dar."""
    if tabla_id in _TABLA_CACHE:
        opciones = _TABLA_CACHE[tabla_id]
    else:
        opciones = []
        db = _db()
        if db.exists():
            try:
                con = sqlite3.connect(db)
                cols = [c[1] for c in con.execute(
                    'pragma table_info(drop_table)')]
                fila = con.execute('select * from drop_table where id=?',
                                   (str(tabla_id),)).fetchone()
                con.close()
                if fila:
                    r = dict(zip(cols, fila))
                    for i in range(1, 41):
                        it = r.get('item%d' % i)
                        if not it or not str(it).isdigit() or int(it) <= 0:
                            continue
                        ct = r.get('count%d' % i)
                        pr = r.get('prob%d' % i)
                        opciones.append((
                            int(it),
                            int(ct) if ct and str(ct).isdigit() else 1,
                            int(pr) if pr and str(pr).isdigit() else 1))
            except Exception:
                log.debug('no se pudo leer la tabla %s', tabla_id,
                          exc_info=True)
        if not opciones:
            drops_extra = _cargar_drops_extra()
            raw_ops = drops_extra.get(str(tabla_id)) or drops_extra.get(int(tabla_id) if str(tabla_id).isdigit() else -1)
            if raw_ops:
                opciones = [(int(it), int(ct), int(pr)) for it, ct, pr in raw_ops]
        _TABLA_CACHE[tabla_id] = opciones
    if not opciones:
        return None
    total = sum(p for _i, _c, p in opciones)
    if total <= 0:
        it, ct, _p = random.choice(opciones)
        return (it, ct)
    tirada = random.randrange(total)
    for it, ct, p in opciones:
        if tirada < p:
            return (it, ct)
        tirada -= p
    it, ct, _p = opciones[-1]
    return (it, ct)


def abrir(item_id: int):
    """Que sale de esa bolsa: (item, cuantos), o None si no se puede abrir."""
    iid = int(item_id or 0)
    que = _cargar().get(iid) or _cargar_extra().get(iid)
    if not que:
        return None
    clase, valor = que
    return _sorteo(valor)


# ---------------------------------------------------------------------------
# OBJETOS QUE BUFEAN
#
# El buff de un item esta en su columna 常駐法術 ("hechizo permanente"), que
# es un id de magic, y la fila de magic lo trae TODO. La Kyrio Angel Magic
# Stone sin sellar (63816) apunta a la magia 20834:
#
#     objetivo uno mismo, 3600 s de duracion, HP max +12000, MP max +9600,
#     defensa +4000, ataque magico +2800, precision +100, agilidad +100,
#     velocidad +16, no se pierde al morir, no acumula con otra igual
#
# Y no hay que interpretarla a mano: combate.datos_magia() ya parsea esa fila
# entera y devuelve es_buff, dur_ms y los _bonus. Son 13.185 items con ese
# campo, asi que el mecanismo es uno solo para todos.
# ---------------------------------------------------------------------------

COL_HECHIZO = '常駐法術'      # el buff que aplica
COL_NO_GASTA = '使用不扣'    # "usar sin descontar"
_BUFFS = None
_NO_GASTAN = None


def _cargar_buffs():
    global _BUFFS
    if _BUFFS is not None:
        return _BUFFS
    _BUFFS = {}
    if _NO_GASTAN is None:
        globals()['_NO_GASTAN'] = set()
    db = _db()
    if not db.exists():
        return _BUFFS
    try:
        con = sqlite3.connect(db)
        for t in TABLAS_ITEM:
            cols = [c[1] for c in con.execute('pragma table_info(%s)' % t)]
            if COL_HECHIZO not in cols:
                continue
            for iid, mid in con.execute(
                    'select id, "%s" from %s where "%s" is not null '
                    'and "%s" <> "" and "%s" <> "0"'
                    % (COL_HECHIZO, t, COL_HECHIZO, COL_HECHIZO, COL_HECHIZO)):
                try:
                    i, m = int(iid), int(mid)
                except (TypeError, ValueError):
                    continue
                if i not in _BUFFS and m > 0:
                    _BUFFS[i] = m
        # Y los que NO se gastan al usarlos. La piedra es uno: se usa, se
        # queda en la mochila y se vuelve a usar cuando se acaba el buff.
        _NO_GASTAN.clear()
        for t in TABLAS_ITEM:
            cols = [c[1] for c in con.execute('pragma table_info(%s)' % t)]
            if COL_NO_GASTA not in cols:
                continue
            for (iid,) in con.execute(
                    'select id from %s where "%s" = ?' % (t, COL_NO_GASTA),
                    ('是',)):
                try:
                    _NO_GASTAN.add(int(iid))
                except (TypeError, ValueError):
                    continue
        con.close()
    except Exception as e:
        log.warning('no se pudieron leer los hechizos de los items '
                    '(%s: %s); ningun objeto bufeara', type(e).__name__, e)
    return _BUFFS


def hechizo_de(item_id: int):
    """El id de magic que aplica ese item al usarlo, o None."""
    return _cargar_buffs().get(int(item_id or 0))


# Como se traduce la fila de magic al diccionario de buffs del personaje.
# Las claves de la izquierda son las que devuelve combate.datos_magia() y
# las de la derecha las que lee la funcion de stats del servidor.
EQUIVALENCIAS = (('def_bonus', 'def'), ('atk_bonus', 'atk'),
                 ('matk_bonus', 'matk'), ('mdef_bonus', 'mdef'),
                 ('hit_bonus', 'hit'), ('eva_bonus', 'eva'),
                 ('hp_bonus', 'hp_bonus'), ('mp_bonus', 'mp_bonus'))


def buff_de(item_id, ahora=0.0):
    """La entrada de personaje.buffs que deja ese item, o None.

    La VELOCIDAD no va como clave suelta: _velocidad_de() la saca de
    buff['mag']['move_speed_bonus'], asi que basta con guardar la fila de
    magic entera, que ademas hace falta para los procs.
    """
    import combate as _cb
    mid = hechizo_de(item_id)
    if not mid:
        return None
    mag = _cb.datos_magia(mid)
    if not mag or not mag.get('es_buff'):
        return None
    dur = int(mag.get('dur_ms') or 0)
    entrada = {'fin': ahora + dur / 1000.0, 'mag': mag, 'de_item': int(item_id)}
    for origen, destino in EQUIVALENCIAS:
        if mag.get(origen):
            entrada[destino] = mag[origen]
    return mid, entrada, dur


def se_gasta(item_id) -> bool:
    """Si el objeto desaparece al usarlo.

    La columna 使用不扣 ("usar sin descontar") marca los que NO. La Kyrio
    Angel Magic Stone es uno: se usa, se queda en la mochila y se vuelve a
    usar cuando se acaba el buff. Gastarla era un error que se cargaba el
    objeto del jugador.
    """
    _cargar_buffs()
    return int(item_id or 0) not in (_NO_GASTAN or set())
