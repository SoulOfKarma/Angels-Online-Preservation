"""
Inventario: mover items entre ranuras, equipar y desequipar.

Protocolo, establecido con capturas del servidor privado que llevan marca de
tiempo en los dos sentidos:

    C -> S  0x0012  [LE16 ranura_origen][LE16 ranura_destino]
    S -> C  0x001B  131 B, describe el movimiento
    S -> C  0x0042  105 B, los stats recalculados   (solo si cambia el equipo)

El 0x001B lleva tres bloques:

    [U8 01][8 bytes id de instancia][LE32 item_id]   el item que se movio
    [U8 01][LE32 char_id][LE16 ranura]               la ranura que lo recibe
    [U8 02][U8 01][LE32 char_id][LE16 ranura]        la ranura que queda vacia

Y los ordena por NUMERO DE RANURA ascendente, no por origen/destino. Por eso
hay dos disposiciones y los offsets cambian segun el caso:

    origen < destino:   vacia@4    item@12   recibe@45
    origen > destino:   item@4     recibe@37  vacia@123

Verificado reconstruyendo los 26 movimientos de una captura en la que el
jugador paseo la misma prenda por todo el inventario: los 26 salen byte a
byte identicos al mensaje real.

La ranura 2 es el cuerpo. Mover algo a la 2 lo equipa y sacarlo lo desequipa;
en ese caso hay que mandar tambien el 0x0042 con los stats. Se comprueba en el
quinto stat, que el cliente muestra como Dfs: 5 sin la ropa y 15 con ella.
"""
import json
import pathlib
import re
import sqlite3
import struct
import mascotas as _ms
import time

PLANTILLA = pathlib.Path(__file__).parent / 'plantillas' / 'inventario.json'
RANURA_CUERPO = 2           # la unica ranura de equipo MEDIDA en el trafico

# Primera ranura de la mochila. El cliente numera asi: el jugador saco la ropa
# del cuerpo (2) y el cliente pidio ponerla en la 20, que es la primera casilla
# del panel Prop; de ahi en adelante fue usando 21, 22... hasta la 44.
#
# Que todo lo menor a 20 sea equipo es INFERENCIA, no medicion: solo se vio la
# ranura 2. Se deja asi y no cableado al 2 porque el juego tiene mochilas
# equipables (y podria tener capas con ranuras), de modo que el equipo son
# varias casillas y la mochila puede crecer. Nada de esto supone un tamano
# maximo: el inventario es un diccionario de ranura a item.
PRIMERA_RANURA_BOLSA = 20

# El cliente reparte sus items en item, item2 ... item9, una por update.
# Consultando solo `item`, todo lo que vino en un update posterior quedaba
# como si no existiera: sin ranura, sin peso y sin bonos.
TABLAS_ITEM = ('item', 'item2', 'item3', 'item4', 'item5', 'item6',
               'item7', 'item8', 'item9')
_P = None


_PESOS = None


def peso_de(item_id: int) -> int:
    """El peso de un item, de la columna weight de item.xml."""
    global _PESOS
    if _PESOS is None:
        import sqlite3
        _PESOS = {}
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            try:
                con = sqlite3.connect(db)
                filas = []
                for _t in TABLAS_ITEM:
                    try:
                        filas += list(con.execute('select id, weight from %s' % _t))
                    except Exception:
                        continue
                for iid, w in filas:
                    try:
                        _PESOS[int(iid)] = int(float(w or 0))
                    except (TypeError, ValueError):
                        continue
                con.close()
            except Exception:
                pass
    return _PESOS.get(int(item_id or 0), 0)


def peso_total(bolsa) -> int:
    """Lo que pesa todo lo que se lleva encima."""
    return sum(peso_de(i) for r, i in (bolsa or {}).items()
               if r != RANURA_ORO)


_CORRELATIVO = [0x030000]


def instancia_nueva() -> bytes:
    """Un id de instancia de ocho bytes para un monton recien creado.

    En la captura son [u32 correlativo][u32 sello de tiempo]: al comprar dos
    cosas a la vez salen 215293 y 215294 con el MISMO sello, y al separar un
    monton la pila nueva se lleva 215300 con un sello posterior. O sea el
    numero es un contador global del servidor y el sello es el momento.
    """
    _CORRELATIVO[0] += 1
    return struct.pack('<II', _CORRELATIVO[0], int(time.time()))


def es_apilable(item_id: int) -> bool:
    """Si varias unidades de ese item comparten una sola casilla.

    Todo lo que no se equipa se apila: pociones, galletas, pasto magico. En
    la captura de Celestia se compran diez pociones rojas y ocupan UNA
    casilla con cantidad diez; nuestro inventario era {ranura: item_id} sin
    cantidades, asi que cada unidad pedia su propia casilla y al usar una se
    borraba el monton entero.
    """
    return not es_equipable(item_id)


# Que contenedor se esta tocando. Es el byte que va delante del id en el
# sub-mensaje que vacia una casilla, y lo destapo la captura de Edo City del
# 28/09/2026 al guardar en el banco: hasta entonces valia siempre 1 y se creia
# fijo.
#   1 + la ENTIDAD del personaje -> la mochila
#   2 + 252                      -> el almacen del banco
CONT_MOCHILA = 1
CONT_BANCO = 2
ID_BANCO = 252


def vaciar_ranura(dueno: int, ranura: int,
                  contenedor: int = CONT_MOCHILA) -> bytes:
    """0x001B que deja una casilla vacia.

    Medido al destruir un monton de pociones:
        01000000 | 02 | 01 | 1e010000 | 2900
    es decir [u32 n=1][u8 02 = vaciar][u8 contenedor][u32 dueno][u16 ranura].

    El byte del contenedor se creia fijo en 1. Al guardar algo en el banco el
    servidor real manda 02 y de dueno el 252 en vez de la entidad.
    """
    return struct.pack('<HIBBIH', 0x001B, 1, 2, contenedor, dueno, ranura)


def ranura_de_instancia(instancias, instancia: bytes, bolsa=None,
                        char_id: int = 0):
    """A que casilla corresponde ese id de instancia de ocho bytes.

    Al vender, el cliente NO manda la casilla: manda el id de instancia del
    monton, el mismo que le dimos en el 0x001A. Antes se leian esos bytes
    como si fueran el numero de casilla, nunca casaban con nada y la venta
    no sacaba nada del inventario ni pagaba: por eso daba 0.

    Tampoco sirve deducirlo del item: al separar un monton la pila nueva se
    lleva una instancia distinta, asi que dos casillas con el mismo item
    tienen ids diferentes. Hay que llevar el mapa casilla -> instancia.
    """
    for ranura, inst in (instancias or {}).items():
        if bytes(inst)[:8] == instancia[:8]:
            return int(ranura)
    # Respaldo: la derivacion vieja, instancia_de(char_id, item_id).
    #
    # La secuencia de entrada al mundo manda el inventario SIN instancias, y
    # entonces cada entrada cae en esa derivacion. El cliente se queda con
    # esos ocho bytes y los devuelve al vender, mientras que aqui se buscaba
    # solo en el mapa de instancias nuevas: no casaba ninguna y no se vendia
    # nada. Se reconocio comparando: el cliente mandaba ...5af6ad6a y
    # instancia_de(char, 2) termina exactamente en 5af6ad6a.
    if bolsa and char_id:
        for ranura, item_id in bolsa.items():
            if instancia_de(char_id, int(item_id)) == instancia[:8]:
                return int(ranura)
            if es_mascota(int(item_id)):
                _pi = 1000 + int(ranura)
                if struct.pack('<II', _pi, _pi) == instancia[:8]:
                    return int(ranura)
    return None


def es_equipo(ranura) -> bool:
    """Si esa ranura es del personaje (equipo regular 1..19 o Fashion 167..174) y no de la mochila."""
    try:
        r = int(ranura)
    except (ValueError, TypeError):
        return False
    # La 175 es la insignia. Sin incluirla aqui, una insignia puesta no
    # contaba como equipo y sus bonos no se sumaban a los stats: la Crystal
    # Badge declara +3484 de ataque y no daba ni uno.
    return (r < PRIMERA_RANURA_BOLSA) or (167 <= r <= 175)


def es_fashion(ranura) -> bool:
    """Si esa ranura corresponde a la pestaña de Fashion (167..174)."""
    try:
        r = int(ranura)
    except (ValueError, TypeError):
        return False
    return 167 <= r <= 174



def _plantillas():
    global _P
    if _P is None:
        _P = json.loads(PLANTILLA.read_text(encoding='utf-8'))
    return _P


def instancia_de(char_id: int, ranura_item: int) -> bytes:
    """Id de instancia de un item. Cada item que existe tiene el suyo.

    El servidor real usa 8 bytes que no sabemos como genera; lo unico que
    importa es que sea estable para un mismo item, porque el cliente lo usa
    para seguirle el rastro mientras se mueve. Se deriva de char_id y del
    item para que no cambie entre sesiones.
    """
    return struct.pack('<II', (char_id * 2654435761) & 0xFFFFFFFF,
                       (ranura_item * 40503 + 0x6AACB9EC) & 0xFFFFFFFF)


def movimiento(origen: int, destino: int, char_id: int, item_id: int,
               instancia: bytes) -> bytes:
    """Sub-mensaje 0x001B que describe mover un item de una ranura a otra."""
    p = _plantillas()
    sube = origen < destino
    caso = 'asc' if sube else 'desc'
    b = bytearray(bytes.fromhex(p[caso]))
    o = p['campos'][caso]
    struct.pack_into('<I', b, o['char1'], char_id)
    struct.pack_into('<H', b, o['ran1'], origen)
    b[o['inst']:o['inst'] + 8] = instancia[:8].ljust(8, b'\x00')
    struct.pack_into('<I', b, o['item'], item_id)
    struct.pack_into('<I', b, o['char2'], char_id)
    struct.pack_into('<H', b, o['ran2'], destino)
    # La durabilidad va tambien aqui. Sin esto, al mover un arma el cliente
    # la recibia con 0 y la mostraba rota en el acto, aunque siguiera
    # pegando igual: el dano lo calcula el servidor y la barra es cosa del
    # cliente. Va en el mismo sitio relativo que en el 0x001A, +45 del
    # bloque del item.
    if 'dur' in o:
        struct.pack_into('<I', b, o['dur'], durabilidad(item_id))
    if es_mascota(item_id):
        nombres_elfos = {3396: b"Water Elf\x00", 3397: b"Fire Elf\x00", 3398: b"Wind Elf\x00", 3399: b"Earth Elf\x00"}
        nom_pet = nombres_elfos.get(item_id, b"Pet\x00")
        it_pos = o['item']
        b[it_pos + 4:it_pos + 4 + len(nom_pet)] = nom_pet
    return struct.pack('<H', 0x001B) + bytes(b)


def _bonus(item_id: int) -> dict:
    """Lo que suma un item, leido de item.xml."""
    global _BON
    if _BON is None:
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        _BON = {}
        if db.exists():
            con = sqlite3.connect(db)
            _filas_b = []
            for _t in TABLAS_ITEM:
                try:
                    cols = [r[1] for r in con.execute('pragma table_info(%s)' % _t)]
                    has_hp = 'hp' in cols
                    has_mp = 'mp' in cols
                    hp_col = 'hp' if has_hp else '0'
                    mp_col = 'mp' if has_mp else '0'
                    # LA CARGA MAXIMA QUE SUMA LA PIEZA. Es la columna
                    # 負重, y no estaba: el tooltip del Hephaestus-Hedgehog
                    # Bag (item2 40757) promete "+25400(24000+1400) Maximum
                    # Weight" y el 24000 sale de ahi, pero el servidor solo
                    # sumaba la carga de las pasivas Mantle/Garment/Vestment
                    # sobre los 2000 de base, asi que la mochila no hacia
                    # nada. No esta en el mismo sitio en cada tabla, por eso
                    # se busca por nombre.
                    carga_col = '"負重"' if '負重' in cols else '0'
                    _filas_b += list(con.execute(
                        f"select id, def, accuracy, agility, atk_avg, matk, mdef, {hp_col}, {mp_col}, {carga_col} from {_t} "
                        "where id glob '[0-9]*'"))
                except Exception:
                    continue
            for i, d, ac, ag, av, ma, md, _hp, _mp, _cg in _filas_b:
                # Algunos valores vienen con decimales en item.xml.
                def _n(x):
                    try:
                        return int(float(x))
                    except (TypeError, ValueError):
                        return 0
                _BON[int(i)] = {'def': _n(d), 'accuracy': _n(ac),
                                'agility': _n(ag), 'atk': _n(av),
                                'matk': _n(ma), 'mdef': _n(md),
                                'hp': _n(_hp), 'mp': _n(_mp),
                                'carga': _n(_cg)}
    return _BON.get(item_id, {'def': 0, 'accuracy': 0, 'agility': 0, 'atk': 0, 'matk': 0, 'mdef': 0, 'hp': 0, 'mp': 0, 'carga': 0})


def bonos_de_habilidades(habilidades):
    """Lo que suman las habilidades: vida, mana, carga, barras de SP y stats.

    OJO: esta tabla esta escrita a mano, no sale de los datos del cliente.
    En `content.db` no hay ninguna tabla de habilidades -- la tabla `level`
    solo trae la experiencia que pide cada nivel de cada rama -- asi que
    estos numeros no estan verificados contra nada. El HP no lo da el arma
    (Sword no sube vida, cura): lo dan las pasivas, Enhance y Grapple.

    Se saco de dentro de stats() porque el tope de vida hacia falta en dos
    sitios y solo se calculaba en uno: el 0x0042 mandaba el maximo CON el
    bono y la ficha 0x0002 lo mandaba sin el. La ID Card decia 529/529
    mientras el HUD decia 529/1009, y como el servidor se quedaba con el
    529 se creia lleno y las pociones no curaban nada hasta que te pegaban.
    """
    base_atk = 7
    base_def = 6
    base_rigor = 7
    base_agi = 6
    base_matk = 5
    base_mdef = 5
    base_crit = 5
    crit_eff = 5
    load_max = 2000
    sp_max_bars = 2

    hp_bonus = 0
    mp_bonus = 0
    sk_atk = 0
    sk_def = 0
    sk_rigor = 0
    sk_agi = 0
    sk_matk = 0
    sk_mdef = 0

    if habilidades:
        for h in habilidades:
            sid = h[0] if isinstance(h, (list, tuple)) else h
            slv = h[1] if isinstance(h, (list, tuple)) and len(h) > 1 else 1
            extra = max(0, slv - 1)

            if sid == 9:      # Sword: +4 atk base, +1 atk y +1 rigor por nivel arriba de 1
                sk_atk += 4 + extra
                sk_rigor += extra
            elif sid == 10:   # Axe: +4 atk base, +1 atk por nivel, +8 rigor cada 10 niveles
                sk_atk += 4 + extra
                sk_rigor += 8 * (slv // 10)
            elif sid == 11:   # Spear: +4 atk base, +1 atk por nivel, +8 rigor cada 10 niveles
                sk_atk += 4 + extra
                sk_rigor += 8 * (slv // 10)
            elif sid == 12:   # Enhance: +2 def base, +24 hp (con=2), +1 def y +12 hp por nivel
                sk_def += 2 + extra
                hp_bonus += extra * 12
            elif sid == 13:   # Grapple: +4 rigor base, +1 atk, +1 rigor y +12 hp por nivel
                sk_rigor += 4 + extra
                sk_atk += extra
                hp_bonus += extra * 12
            elif sid == 14:   # Shield: +4 def base, +3 def por nivel
                sk_def += 4 + extra * 3
            elif sid == 15:   # Reserve: +2 atk base, +1 atk por nivel, +1 barra SP cada 25 niveles
                sk_atk += 2 + extra
                sp_max_bars += (slv // 25)
            elif sid == 16:   # Finesse: +4 agi base, +1 agi por nivel
                sk_agi += 4 + extra
            elif sid == 17:   # Longbow: +4 atk base, +1 atk por nivel, +8 rigor cada 10 niveles
                sk_atk += 4 + extra
                sk_rigor += 8 * (slv // 10)
            elif sid == 18:   # Snipe: +2 atk base, +1 atk por nivel
                sk_atk += 2 + extra
            elif sid == 19:   # Eagle Eye: +2 rigor, +2 agi base, +1 rigor y +1 agi por nivel
                sk_rigor += 2 + extra
                sk_agi += 2 + extra
            elif sid == 32:   # Mantle: +3 def, +1 agi, +60 carga
                sk_def += 3
                sk_agi += 1
                load_max += 60 + extra * 60
            elif sid == 33:   # Garment: +4 def, +72 carga
                sk_def += 4
                load_max += 72 + extra * 72
            elif sid == 34:   # Vestment: +2 def, +2 mdef, +48 carga
                sk_def += 2
                sk_mdef += 2
                load_max += 48 + extra * 48
            elif sid in (20, 21, 22, 23): # Collect, Fishing, Dig, Lumber: +2 atk
                sk_atk += 2
            elif sid in (1, 2, 3, 4):     # Magic elemental: +4 matk
                sk_matk += 4
            elif sid == 5:    # Curse: +2 matk, +1 matk por nivel
                sk_matk += 2 + extra
            elif sid == 6:    # Meditate: +2 mdef, +30 mp, +1 mdef y +15 mp por nivel
                sk_mdef += 2 + extra
                mp_bonus += 30 + extra * 15
            elif sid == 7:    # Hit: +2 matk, +1 matk y +5 mp por nivel
                sk_matk += 2 + extra
                mp_bonus += extra * 5
            elif sid == 8:    # Staff Hit: +2 atk, +1 matk, +1 mdef base, +1 atk/matk/rigor por nivel
                sk_atk += 2 + extra
                sk_matk += 1 + extra
                sk_mdef += 1
                sk_rigor += extra

    return {
        'atk': sk_atk, 'def': sk_def, 'rigor': sk_rigor, 'agi': sk_agi,
        'matk': sk_matk, 'mdef': sk_mdef,
        'hp': hp_bonus, 'mp': mp_bonus,
        'carga': load_max, 'barras_sp': sp_max_bars,
    }


def bonos_de_equipo(bolsa, mejoras: dict = None) -> dict:
    """Calcula la suma de atributos que otorgan los items equipados en la bolsa (Gear 1..10 y Fashion 167..174)."""
    eq = {'def': 0, 'accuracy': 0, 'agility': 0, 'atk_r': 0, 'atk_l': 0, 'matk': 0, 'mdef': 0, 'hp': 0, 'mp': 0, 'carga': 0}
    if not bolsa:
        return eq

    r_weap_atk = 0
    l_weap_atk = 0
    gen_atk = 0

    for ranura, item_id in bolsa.items():
        try:
            r = int(ranura)
            iid = int(item_id)
        except (ValueError, TypeError):
            continue
        if not es_equipo(r) or r == RANURA_ORO:
            continue
        x = dict(_bonus(iid))
        # LOS STATS DEL MARTILLO VERDE. Se guardaban y se enseñaban en el
        # tooltip, pero no entraban aqui, asi que no subian nada de verdad.
        # Los nombres son los nuestros y los de _bonus() no son los mismos:
        # 'rigor' es 'accuracy' y 'dfs' es 'def'.
        _ex = (mejoras or {}).get(r) or {}
        # EL "+N" TAMBIEN SUMA, y en porcentaje sobre la propia pieza. Se
        # llevaba la cuenta y se enseñaba en el tooltip, pero no entraba en
        # los stats. Sale de la cuenta del propio juego: un arma a +15 con
        # 19373 de ataque base enseñaba "+18885", y quitando el verde queda
        # el 90,05% de la base -- o sea un 6% por mejora, que es justo lo
        # que dice BONOS_POR_DEFECTO. El ataque magico da el 90,1%, igual.
        # La vida, el mana y el rigor no reciben nada: solo su verde.
        _veces = int(_ex.get('veces') or 0)
        if _veces:
            try:
                import mejoras as _mj
                _pct = _mj.pct_por_mejoras(_mj.tipo_de_ranura(r, iid), _veces)
            except Exception:
                _pct = {}
            for _k, _p in (_pct or {}).items():
                _orig = {'rigor': 'accuracy', 'dfs': 'def',
                         'agilidad': 'agility'}.get(_k, _k)
                _b = x.get('atk' if _orig == 'atk' else _orig, 0)
                if _b:
                    x[_orig] = _b + int(_b * _p / 100.0)
        # LAS GEMAS ENGARZADAS. Cada una da un stat distinto segun donde
        # este la pieza -- en un arma ataque magico y en una armadura
        # defensa magica, por ejemplo -- y eso lo dice jeweleffect.xml.
        for _g in (_ex.get('gemas') or []):
            if not _g:
                continue
            for _k, _v in bono_gema(_g, r, iid).items():
                _dest = {'rigor': 'accuracy', 'dfs': 'def',
                         'agilidad': 'agility', 'peso': 'carga'}.get(_k, _k)
                if _dest in ('def', 'accuracy', 'agility', 'matk', 'mdef',
                             'hp', 'mp', 'atk'):
                    x[_dest] = x.get(_dest, 0) + int(_v)
        for _k, _v in (_ex.get('extra') or {}).items():
            _dest = {'rigor': 'accuracy', 'dfs': 'def',
                     'agilidad': 'agility', 'peso': 'carga'}.get(_k, _k)
            if _dest in ('def', 'accuracy', 'agility', 'matk', 'mdef',
                         'hp', 'mp', 'atk', 'carga'):
                x[_dest] = x.get(_dest, 0) + int(_v)
        eq['def'] += x.get('def', 0)
        eq['accuracy'] += x.get('accuracy', 0)
        eq['agility'] += x.get('agility', 0)
        eq['matk'] += x.get('matk', 0)
        eq['mdef'] += x.get('mdef', 0)
        eq['hp'] += x.get('hp', 0)
        eq['mp'] += x.get('mp', 0)
        eq['carga'] += x.get('carga', 0)

        item_atk = x.get('atk', 0)

        if r == RANURA_DERECHA: # 3 (Arma Gear mano derecha: 1H, 2H, Shadow Blade, Arco, Honda -> R.Atk)
            r_weap_atk += item_atk + x.get('accuracy', 0)
        elif r == RANURA_IZQUIERDA: # 4 (Escudo / Arma Dual / Municion: Flechas o Bolitas en mano izquierda)
            if es_municion(iid):
                # Las flechas y bolitas en la ranura 4 suman su ataque al arco/honda (R.Atk)
                r_weap_atk += item_atk
            elif es_arma_dual(iid):
                l_weap_atk += item_atk + x.get('accuracy', 0)
            elif item_atk > 0:
                # El escudo solo da defensa, salvo que sea uno especial que declare ataque propio
                l_weap_atk += item_atk
        elif r == 169: # Arma Fashion (derecha / principal)
            r_weap_atk += item_atk
            # Solo si la ranura izquierda 170 esta vacia y lleva duales o arma en la 4 se suma en fashion
            if es_arma_dual(iid) and not (bolsa.get(170) or bolsa.get('170')) and (bolsa.get(4) or bolsa.get('4')) and es_arma_dual(int(bolsa.get(4) or bolsa.get('4') or 0)):
                l_weap_atk += item_atk
        elif r == 170: # Arma/Escudo Fashion (izquierda)
            if item_atk > 0:
                l_weap_atk += item_atk
        else:
            # Armaduras Gear (1, 2, 5, 6, 7, 8) y Prendas Fashion (167, 168, 171, 172, 173)
            # Si dan ataque, se suma a AMBOS (R.Atk y L.Atk)
            gen_atk += item_atk

    eq['atk_r'] = r_weap_atk + gen_atk
    eq['atk_l'] = l_weap_atk + gen_atk
    return eq


def vida_maxima(hp_max, habilidades, bolsa=None, mejoras=None, buffs=None, mp_max=0):
    """El tope de vida: el guardado mas las pasivas, el equipo y sus verdes."""
    eq_hp = bonos_de_equipo(bolsa, mejoras)['hp'] if bolsa else 0
    total = int(hp_max or 0) + bonos_de_habilidades(habilidades)['hp'] + eq_hp
    if buffs:
        now = time.time()
        for b_id, b_data in buffs.items():
            if isinstance(b_data, dict) and b_data.get('fin', 0) > now:
                if 'hp_pct' in b_data and b_data['hp_pct'] > 0:
                    total += int(round(total * (b_data['hp_pct'] / 100.0)))
                if 'hp_bonus' in b_data and b_data['hp_bonus'] > 0:
                    total += int(b_data['hp_bonus'])
                if 'mp_to_hp_pct' in b_data and b_data['mp_to_hp_pct'] > 0:
                    base_mp = mana_maximo(mp_max, habilidades, bolsa=bolsa, mejoras=mejoras)
                    total += int(round(base_mp * (b_data['mp_to_hp_pct'] / 100.0)))
    return total


def mana_maximo(mp_max, habilidades, bolsa=None, mejoras=None, buffs=None):
    """Igual que vida_maxima, para el mana."""
    eq_mp = bonos_de_equipo(bolsa, mejoras)['mp'] if bolsa else 0
    total = int(mp_max or 0) + bonos_de_habilidades(habilidades)['mp'] + eq_mp
    if buffs:
        now = time.time()
        for b_id, b_data in buffs.items():
            if isinstance(b_data, dict) and b_data.get('fin', 0) > now:
                if 'mp_pct' in b_data and b_data['mp_pct'] > 0:
                    total += int(round(total * (b_data['mp_pct'] / 100.0)))
                if 'mp_bonus' in b_data and b_data['mp_bonus'] > 0:
                    total += int(b_data['mp_bonus'])
    return total


_RESIDENT_MAGIC_CACHE = {}
_MAGIC_DATA_CACHE = {}


def resident_magic_de(item_id: int):
    """Devuelve el magic_id de la magia residente (常駐法術) de un item, o None."""
    global _RESIDENT_MAGIC_CACHE
    if not item_id:
        return None
    try:
        iid = int(item_id)
    except (ValueError, TypeError):
        return None
    if iid in _RESIDENT_MAGIC_CACHE:
        return _RESIDENT_MAGIC_CACHE[iid]
    import sqlite3
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if not db.exists():
        return None
    mid = None
    try:
        con = sqlite3.connect(db)
        cur = con.cursor()
        for t in ['item', 'item2', 'item3', 'item4', 'item5', 'item6', 'item7', 'item8', 'item9']:
            cur.execute(f'PRAGMA table_info({t})')
            cols = [c[1] for c in cur.fetchall()]
            col_res = next((c for c in cols if '常駐' in c), None)
            if col_res:
                row = cur.execute(f'SELECT "{col_res}" FROM {t} WHERE id=?', (str(iid),)).fetchone()
                if row and row[0]:
                    try:
                        mid = int(row[0])
                        break
                    except ValueError:
                        pass
    except Exception:
        pass
    _RESIDENT_MAGIC_CACHE[iid] = mid
    return mid


def datos_magia_residente(magic_id: int) -> dict:
    """Devuelve los atributos numericos (% dano, % mitigacion, prioridades) de un magic_id."""
    global _MAGIC_DATA_CACHE
    if not magic_id:
        return {}
    try:
        mid = int(magic_id)
    except (ValueError, TypeError):
        return {}
    if mid in _MAGIC_DATA_CACHE:
        return _MAGIC_DATA_CACHE[mid]
    import sqlite3
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    res = {}
    if db.exists():
        try:
            con = sqlite3.connect(db)
            cur = con.cursor()
            cur.execute('PRAGMA table_info(magic)')
            cols = [c[1] for c in cur.fetchall()]
            row = cur.execute('SELECT * FROM magic WHERE id=?', (str(mid),)).fetchone()
            if row:
                d = dict(zip(cols, row))
                def _to_int(k):
                    val = d.get(k)
                    if val is not None and str(val).isdigit():
                        return int(val)
                    return 0
                res = {
                    'id': mid,
                    'name': d.get('name', ''),
                    'high_pri': _to_int('高權位'),
                    'low_pri': _to_int('低權位'),
                    'mag_dmg': _to_int('魔法傷害'),
                    'phys_dmg': _to_int('物理傷害'),
                    'phys_mit': _to_int('物理傷害抵銷'),
                    'mag_mit': _to_int('魔法傷害抵銷'),
                    'res_ice': _to_int('res_ice'),
                    'res_fire': _to_int('res_fire'),
                    'res_elec': _to_int('res_elec'),
                    'res_poison': _to_int('res_poison'),
                }
        except Exception:
            pass
    _MAGIC_DATA_CACHE[mid] = res
    return res


def modificadores_porcentuales_equipo(bolsa) -> dict:
    """Calcula los modificadores porcentuales activos segun los items equipados en la bolsa.
    Aplica la regla de no acumulacion ('Cannot be stacked with similar effects'):
    - Si dos o mas items tienen el mismo grupo de prioridad (high_pri / 高權位),
      prevalece el mayor.
    - Entre fuentes distintas, las mitigaciones se calculan de manera compuesta multiplicativa.
    """
    res = {
        'mag_dmg_pct': 0,     # % extra a daño magico (+30% etc)
        'phys_dmg_pct': 0,    # % extra a daño fisico (+14% etc)
        'phys_mit_pct': 0,    # % total de mitigacion de daño fisico
        'mag_mit_pct': 0,     # % total de mitigacion de daño magico
        'phys_mit_mult': 1.0, # Multiplicador de dano fisico recibido (ej 0.7695)
        'mag_mit_mult': 1.0,  # Multiplicador de dano magico recibido (ej 0.81)
        'res_ice': 0,
        'res_fire': 0,
        'res_elec': 0,
        'res_poison': 0,
    }
    if not bolsa:
        return res

    grupos = {}
    for ranura, item_id in bolsa.items():
        if not es_equipo(ranura) or ranura == RANURA_ORO:
            continue
        try:
            iid = int(item_id)
        except (ValueError, TypeError):
            continue
        mid = resident_magic_de(iid)
        if not mid:
            continue
        md = datos_magia_residente(mid)
        if not md:
            continue

        hpri = md.get('high_pri') or mid
        if hpri not in grupos:
            grupos[hpri] = {
                'mag_dmg': 0, 'phys_dmg': 0,
                'phys_mit': 0, 'mag_mit': 0,
                'res_ice': 0, 'res_fire': 0, 'res_elec': 0, 'res_poison': 0
            }
        for k in ['mag_dmg', 'phys_dmg', 'phys_mit', 'mag_mit', 'res_ice', 'res_fire', 'res_elec', 'res_poison']:
            grupos[hpri][k] = max(grupos[hpri][k], md.get(k, 0))

    mult_phys = 1.0
    mult_mag = 1.0

    for g in grupos.values():
        res['mag_dmg_pct'] += g['mag_dmg']
        res['phys_dmg_pct'] += g['phys_dmg']
        res['res_ice'] += g['res_ice']
        res['res_fire'] += g['res_fire']
        res['res_elec'] += g['res_elec']
        res['res_poison'] += g['res_poison']

        if g['phys_mit'] > 0:
            mult_phys *= (1.0 - min(0.95, g['phys_mit'] / 100.0))
        if g['mag_mit'] > 0:
            mult_mag *= (1.0 - min(0.95, g['mag_mit'] / 100.0))

    res['phys_mit_mult'] = max(0.05, mult_phys)
    res['mag_mit_mult'] = max(0.05, mult_mag)
    res['phys_mit_pct'] = int(round((1.0 - res['phys_mit_mult']) * 100.0))
    res['mag_mit_pct'] = int(round((1.0 - res['mag_mit_mult']) * 100.0))
    return res



def stats(bolsa=None, habilidades: list = None,
          hp: int = None, hp_max: int = None,
          mp: int = None, mp_max: int = None,
          oro: int = None,
          buffs: dict = None,
          sp: int = None, sp_max: int = None,
          mejoras: dict = None) -> bytes:
    """Sub-mensaje 0x0042 con los stats del personaje segun lo que lleva puesto y habilidades pasivas.

    El array que empieza en +20 alterna valor base y valor efectivo:
        idx 0  ataque base      idx 1  R.Atk     idx 2  L.Atk
        idx 3  defensa base     idx 4  Dfs
        idx 5  Spl Atk base     idx 6  Spl Atk
        idx 7  Spl Dfs base     idx 8  Spl Dfs
        +56    Rigor (Acc) base / eff
        +60    Agility (Dodge) base / eff
        +64    Critical base / eff
        +68    SP bars current / max (1 barra = 1000 puntos)

    El efectivo es el base mas lo que suma cada pieza puesta y los bonus de
    habilidades pasivas segun el nivel de cada habilidad.
    """
    p = _plantillas()
    b = bytearray(bytes.fromhex(p['stats_sin_ropa']))

    _b = bonos_de_habilidades(habilidades)
    base_atk, base_def, base_rigor = 7, 6, 7
    base_agi, base_matk, base_mdef = 6, 5, 5
    base_crit = 5
    crit_eff = 5
    load_max = _b['carga']
    sp_max_bars = min(10, _b['barras_sp'])
    hp_bonus, mp_bonus = _b['hp'], _b['mp']
    sk_atk, sk_def, sk_rigor = _b['atk'], _b['def'], _b['rigor']
    sk_agi, sk_matk, sk_mdef = _b['agi'], _b['matk'], _b['mdef']

    c_atk_base = base_atk + sk_atk
    c_def_base = base_def + sk_def
    c_rigor_base = base_rigor + sk_rigor
    c_agi_base = base_agi + sk_agi
    c_matk_base = base_matk + sk_matk
    c_mdef_base = base_mdef + sk_mdef

    if sp_max is not None:
        sp_max_bars = min(10, max(sp_max_bars, sp_max))
    sp_max_pts = sp_max_bars * 1000
    if sp is not None:
        sp_pts = min(sp_max_pts, max(0, int(sp)))
    else:
        sp_pts = 0

    eq = bonos_de_equipo(bolsa, mejoras)
    # La carga que suman las piezas puestas (sobre todo la mochila) va aqui:
    # antes el tope eran solo los 2000 de base mas las pasivas de armadura.
    load_max += eq.get('carga', 0)
    eq_def = eq['def']
    eq_r_atk = eq['atk_r']
    eq_l_atk = eq['atk_l']
    eq_rigor = eq['accuracy']
    eq_agi = eq['agility']
    eq_matk = eq['matk']
    eq_mdef = eq['mdef']
    eq_hp = eq['hp']
    eq_mp = eq['mp']

    r_atk_eff = c_atk_base + eq_r_atk
    l_atk_eff = c_atk_base + eq_l_atk
    dfs_eff = c_def_base + eq_def
    matk_eff = c_matk_base + eq_matk
    mdef_eff = c_mdef_base + eq_mdef
    rigor_eff = c_rigor_base + eq_rigor
    agi_eff = c_agi_base + eq_agi

    hp_eff = hp if hp is not None else struct.unpack_from('<I', b, 0)[0]
    hp_max_eff = (hp_max + hp_bonus + eq_hp) if hp_max is not None else (struct.unpack_from('<I', b, 4)[0] + hp_bonus + eq_hp)
    mp_eff = mp if mp is not None else struct.unpack_from('<I', b, 8)[0]
    mp_max_eff = (mp_max + mp_bonus + eq_mp) if mp_max is not None else (struct.unpack_from('<I', b, 12)[0] + mp_bonus + eq_mp)

    if buffs:
        now = time.time()
        for b_id, b_data in buffs.items():
            if isinstance(b_data, dict) and b_data.get('fin', 0) > now:
                # 1. Multiplicadores porcentuales (% sobre stats totales equipados)
                if 'hp_pct' in b_data and b_data['hp_pct'] > 0:
                    hp_max_eff += int(round(hp_max_eff * (b_data['hp_pct'] / 100.0)))
                if 'mp_pct' in b_data and b_data['mp_pct'] > 0:
                    mp_max_eff += int(round(mp_max_eff * (b_data['mp_pct'] / 100.0)))
                if 'mp_to_hp_pct' in b_data and b_data['mp_to_hp_pct'] > 0:
                    # e.g. Shark Shift: +130% de Max MP se suma a Max HP
                    hp_max_eff += int(round(mp_max_eff * (b_data['mp_to_hp_pct'] / 100.0)))

                # 2. Transformaciones de combate cuerpo a cuerpo (近戰化 / Shark Shift)
                # Traspasa el poder magico (Spl Atk / Spl Dfs) transformado a ataque fisico R.Atk/L.Atk y defensa Dfs
                if b_data.get('es_melee_trans'):
                    trans_atk_pct = b_data.get('matk_pct', 150)
                    trans_atk = int(round(matk_eff * (trans_atk_pct / 100.0)))
                    r_atk_eff += trans_atk
                    l_atk_eff += trans_atk
                    trans_def_pct = b_data.get('mdef_pct', 200)
                    trans_def = int(round(mdef_eff * (trans_def_pct / 100.0)))
                    dfs_eff += trans_def
                else:
                    if 'matk_pct' in b_data and b_data['matk_pct'] > 0:
                        matk_eff += int(round(matk_eff * (b_data['matk_pct'] / 100.0)))
                    if 'mdef_pct' in b_data and b_data['mdef_pct'] > 0:
                        mdef_eff += int(round(mdef_eff * (b_data['mdef_pct'] / 100.0)))
                    if 'atk_pct' in b_data and b_data['atk_pct'] > 0:
                        r_atk_eff += int(round(r_atk_eff * (b_data['atk_pct'] / 100.0)))
                        l_atk_eff += int(round(l_atk_eff * (b_data['atk_pct'] / 100.0)))
                    if 'def_pct' in b_data and b_data['def_pct'] > 0:
                        dfs_eff += int(round(dfs_eff * (b_data['def_pct'] / 100.0)))

                # 3. Sumas directas
                if 'crit' in b_data:
                    crit_eff += b_data['crit']
                if 'def' in b_data:
                    dfs_eff += b_data['def']
                if 'atk' in b_data:
                    r_atk_eff += b_data['atk']
                    l_atk_eff += b_data['atk']
                if 'matk' in b_data:
                    matk_eff += b_data['matk']
                if 'mdef' in b_data:
                    mdef_eff += b_data['mdef']
                if 'hit' in b_data:
                    rigor_eff += b_data['hit']
                if 'eva' in b_data:
                    agi_eff += b_data['eva']
                if b_data.get('hp_bonus'):
                    hp_max_eff += b_data['hp_bonus']
                if b_data.get('mp_bonus'):
                    mp_max_eff += b_data['mp_bonus']

    # TODO lo que va aqui se recorta al rango del campo. Sin esto, un solo
    # numero fuera de sitio -- un debuff que deje un stat en negativo, o un
    # tope de vida desbordado -- levantaba un struct.error que se llevaba la
    # sesion entera por delante y al jugador se le quedaba el juego colgado.
    # Paso de verdad con la Eerie Curse, que resta 18432 de ataque.
    def _u32(v):
        return max(0, min(int(v or 0), 0xFFFFFFFF))

    def _u16(v):
        return max(0, min(int(v or 0), 0xFFFF))

    struct.pack_into('<I', b, 0, _u32(hp_eff))
    struct.pack_into('<I', b, 4, _u32(hp_max_eff))
    struct.pack_into('<I', b, 8, _u32(mp_eff))
    struct.pack_into('<I', b, 12, _u32(mp_max_eff))
    # En Angel.exe (sub_5EB130), +16 y +18 son los puntos actuales y maximos de SP
    # (*(_DWORD *)(v3 + 648) = *(_WORD *)(a2 + 18); *(_DWORD *)(v3 + 668) = *(_WORD *)(a2 + 20)).
    # Antes se escribia eq_load=0 aqui, borrando el SP del jugador en cada 0x0042.
    struct.pack_into('<HH', b, 16, _u16(sp_pts), _u16(sp_max_pts))
    struct.pack_into('<I', b, 20, _u32(c_atk_base))
    struct.pack_into('<I', b, 24, _u32(r_atk_eff))
    struct.pack_into('<I', b, 28, _u32(l_atk_eff))
    struct.pack_into('<I', b, 32, _u32(c_def_base))
    struct.pack_into('<I', b, 36, _u32(dfs_eff))
    struct.pack_into('<I', b, 40, _u32(c_matk_base))
    struct.pack_into('<I', b, 44, _u32(matk_eff))
    struct.pack_into('<I', b, 48, _u32(c_mdef_base))
    struct.pack_into('<I', b, 52, _u32(mdef_eff))
    struct.pack_into('<HH', b, 56, _u16(c_rigor_base), _u16(rigor_eff))
    struct.pack_into('<HH', b, 60, _u16(c_agi_base), _u16(agi_eff))
    struct.pack_into('<HH', b, 64, _u16(base_crit), _u16(crit_eff))
    struct.pack_into('<HH', b, 68, 0, 5)
    # Peso. El orden no es el que parecia: en la captura de Celestia los
    # offsets 92 y 96 llevan los dos el tope y el 100 lleva lo que se carga
    # ahora (sube de a uno segun se recoge botin). Antes escribiamos el oro
    # en el 100 y el cliente lo leia como peso, por eso la barra aparecia
    # llena. El oro no va aqui: viaja en la ranura 0 del inventario.
    tope = max(1, load_max)
    struct.pack_into('<III', b, 92, tope, tope, min(peso_total(bolsa), 0xFFFFFFFF))

    return struct.pack('<H', 0x0042) + bytes(b)


def dfs(sub: bytes) -> int:
    """El quinto stat del 0x0042, que el cliente muestra como Dfs."""
    return struct.unpack_from('<I', sub, 2 + 20 + 16)[0]


# --------------------------------------------------------------- 0x001A
# El inventario COMPLETO, que el servidor manda al entrar al mundo. Es el
# mensaje que permite ENTREGAR items; el 0x001B solo los mueve.
#
#     +0   LE32  CUANTAS ENTRADAS VIENEN
#     +4   las entradas, uno detras de otro, de tamano variable
#
# Cada entrada:
#     +0   U8    01
#     +1   8 B   id de instancia
#     +9   LE32  item_id
#     +33  U8    01
#     +34  LE32  char_id
#     +38  LE16  ranura
#     +40  LE32  cantidad
#
# Un item corriente ocupa 86 bytes y uno equipable 119, treinta y tres mas.
# No hay cola.
#
# Comprobado con los dos inventarios capturados:
#     2 items:  4 + 86 + 119                 = 209
#     8 items:  4 + 86 + 119*5 + 86*2        = 857
#
# Aqui se equivoco el primer intento: se tomo la cabecera por un "id de
# contenedor" porque valia 2 y habia dos items, y se dieron todas las entradas
# por iguales de 86 bytes, con lo que los 33 bytes de mas de la prenda pasaron
# por ser una cola del mensaje. Con dos items las cuentas cuadraban igual. Al
# entregar cinco, el cliente dejo de leer donde no debia y quedaron ranuras
# vacias en pantalla que el servidor creia ocupadas.

PLANTILLA_INI = pathlib.Path(__file__).parent / 'plantillas' / 'inventario_inicial.json'
RANURA_ORO = 0
ITEM_ORO = 1
RANURA_DERECHA = 3
RANURA_IZQUIERDA = 4
_BON = None
# Un item se lleva puesto si item.xml le marca alguna ranura de equipo. Antes
# se miraba la CATEGORIA contra una lista escrita a mano y se quedaba corta:
# Stick, Spear, Catapult, Cask y Sharp Knife no estaban, el tamano de sus
# entradas salia mal y el mensaje entero se desalineaba.
COLUMNAS_EQUIPO = ('右手裝備', '左手裝備', '頭部裝備', '飾品裝備', '身體裝備',
                   '手部裝備', '腳部裝備', '背部裝備', '寵物座騎裝備')
OFF_DURABILIDAD = 45   # dentro de la entrada; en item.xml la columna es 耐久
_PI = None
_CAT = None


def _plantilla_inicial():
    global _PI
    if _PI is None:
        _PI = json.loads(PLANTILLA_INI.read_text(encoding='utf-8'))
    return _PI


def _tabla():
    """{item_id: (se_lleva_puesto, durabilidad_maxima)} desde item.xml."""
    global _CAT
    if _CAT is None:
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        _CAT = {}
        if db.exists():
            con = sqlite3.connect(db)
            campos = ','.join(f'"{c}"' for c in COLUMNAS_EQUIPO)
            _filas_e = []
            for _t in TABLAS_ITEM:
                try:
                    _filas_e += list(con.execute(
                        f'select id,"耐久","物品類別",{campos} from {_t} '
                        "where id glob '[0-9]*'"))
                except Exception:
                    continue
            for fila in _filas_e:
                try:
                    d = int(fila[1]) if fila[1] else 0
                except ValueError:
                    d = 0
                es_eq = any(v == '是' for v in fila[3:]) or (fila[2] in ('寵物', '座騎', '紙娃娃', '機甲'))
                _CAT[int(fila[0])] = (es_eq, d, fila[2])
    return _CAT


def categoria_item(item_id: int) -> str:
    """Devuelve la categoria del item desde item.xml (ej. '寵物', '機甲', '座騎')."""
    info = _tabla().get(int(item_id or 0))
    return info[2] if info and len(info) > 2 else ''


def es_equipable(item_id: int) -> bool:
    """Si el item va en alguna de las casillas de equipo (0..10 o 167..174)."""
    if es_mascota(item_id):
        return True
    if ranura_equipo_de(item_id) is not None:
        return True
    return _tabla().get(item_id, (False, 0))[0]


def es_apilable(item_id: int) -> bool:
    """Si el item se puede acumular en una misma casilla (pociones, hojas, galletas, materiales, flechas y bolitas)."""
    if not item_id:
        return False
    if es_municion(item_id):
        return True
    if es_equipable(item_id):
        return False
    return True


def datos_mascota(item_id: int) -> dict:
    """Nombre y sprite de una mascota, sacados de item.xml.

    El sprite es el 動態資料1 y el nombre el 基本名稱. Se comprobo con las dos
    mascotas cuyo nombre no llegaba cortado en las capturas: la Battlemaid
    (item 20012, 動態資料1 3200) y la Hicalu (17060, 3474); en las dos el
    numero de item.xml es el mismo que viajaba en la entrada.
    """
    if item_id in _PET_DATOS:
        return _PET_DATOS[item_id]
    d = {'nombre': 'Pet', 'sprite': 0, 'estrellas': 1}
    try:
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            row = fila_item(sqlite3.connect(db), '"基本名稱", "動態資料1"',
                            item_id)
            if row:
                d = {'nombre': str(row[0] or 'Pet'),
                     'sprite': int(row[1]) if str(row[1] or '').isdigit()
                     else 0,
                     'estrellas': 1}
    except Exception:
        pass
    _PET_DATOS[item_id] = d
    return d


def es_mascota(item_id: int) -> bool:
    """Si el item es una mascota o huevo de mascota (categoria '寵物').
    
    NO confundir con '機甲' (armaduras/partes de robot como Shark Armor 5293)
    ni '座騎' (monturas como Gryphon 21404), que van en la ranura 9/10 pero
    tienen estructura de equipo normal y durabilidad."""
    if item_id in (3396, 3397, 3398, 3399):
        return True
    return categoria_item(item_id) == '寵物'


def es_certificado_sangre(item_id: int) -> int:
    """Devuelve 2 para Medium Blood Certificate (Lvl 35), 3 para Advanced (Lvl 55), o 0."""
    item_id = int(item_id or 0)
    if item_id in (3377, 20405, 22189, 76888):
        return 2
    if item_id in (3378, 22188, 76889):
        return 3
    try:
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            row = fila_item(sqlite3.connect(db), '"基本名稱", "動態資料1"', item_id)
            if row:
                nom = str(row[0] or '')
                d1 = str(row[1] or '')
                if 'Certificate' in nom or '血統證明書' in nom or 'Blood' in nom:
                    if d1 == '2':
                        return 2
                    elif d1 == '3':
                        return 3
    except Exception:
        pass
    return 0


_SLOT_CACHE = None
_PET_SPRITE_CACHE = {}
_PET_DATOS = {}

def fila_item(con, columnas: str, item_id: int):
    """Busca un item en TODAS las tablas de items, no solo en la primera.

    El cliente reparte sus items en item, item2 ... item9, una por update.
    Consultando solo `item`, cualquier cosa de un update posterior quedaba
    como si no existiera: sin ranura, sin peso y sin bonos.
    """
    for tabla in TABLAS_ITEM:
        try:
            fila = con.execute(
                'select %s from %s where id=?' % (columnas, tabla),
                (str(item_id),)).fetchone()
        except Exception:
            continue
        if fila:
            return fila
    return None


_VEL_MONTURA = {}


# Donde va el "+N" de las mejoras dentro de una entrada de equipo.
#
# MEDIDO el 29/09/2026 sobre unas Boots Of Contempt: el byte 83 fue 6 -> 5 al
# fallar una mejora, 5 -> 6 y 6 -> 7 al acertarlas, y 7 -> 6 al volver a
# fallar. Coincide con lo que decian los carteles. Se habia etiquetado como
# "intentos que quedan" y era el nivel de mejora.
OFF_MEJORA = 83


_VINCULACIONES = None


def vinculaciones_de(item_id):
    """Limite y activacion por equipo declarados por el cliente."""
    global _VINCULACIONES
    if _VINCULACIONES is None:
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        tabla = {}
        with sqlite3.connect(f'{db.as_uri()}?mode=ro', uri=True) as con:
            for nombre in TABLAS_ITEM:
                try:
                    filas = con.execute(
                        f'SELECT id, "綁定次數", "裝備綁定" FROM {nombre}')
                    for iid, limite, equipo in filas:
                        try:
                            tabla[int(iid)] = (max(0, int(limite or 0)), equipo == '是')
                        except (TypeError, ValueError):
                            continue
                except sqlite3.OperationalError:
                    continue
        _VINCULACIONES = tabla
    return _VINCULACIONES.get(int(item_id), (0, False))


def vincular_equipo(item_id, char_id, estado):
    """Consume una vinculacion una sola vez para el mismo propietario.

    El estado viaja con las mejoras de la pieza, no con el tipo de item.
    Una transferencia futura debe conservar este estado completo.
    """
    limite, al_equipar = vinculaciones_de(item_id)
    if not limite or not al_equipar:
        return False
    v = estado.get('vinculacion')
    if v and v.get('item_id') == item_id and v.get('dueno') == char_id:
        return False
    restantes = int(v['restantes']) if v and v.get('item_id') == item_id else limite
    if restantes <= 0:
        raise ValueError('El objeto no tiene vinculaciones disponibles')
    estado['vinculacion'] = {'item_id': item_id, 'dueno': char_id,
                             'restantes': restantes - 1}
    return True


def marcar_vinculacion(entrada, estado):
    v = (estado or {}).get('vinculacion')
    if not v:
        return entrada
    base = 6 if entrada[:2] == struct.pack('<H', 0x001B) else 0
    b = bytearray(entrada)
    if len(b) <= base + 58:
        return entrada
    if struct.unpack_from('<I', b, base + 9)[0] != v['item_id']:
        return entrada
    b[base + 57] = max(0, min(255, int(v['restantes'])))
    return bytes(b)


def marcar_mejora(entrada: bytes, veces: int) -> bytes:
    """Escribe el +N en una entrada ya armada.

    Sin esto el cliente no enseña ni el "+7" del nombre ni el "has been
    intensified ( N ) times" del tooltip, porque ese dato viaja en la propia
    entrada del inventario y no en ningun mensaje aparte.
    """
    # El offset es dentro de la ENTRADA, y lo que llega aqui es el paquete
    # entero: dos bytes de opcode y cuatro de cuenta por delante.
    base = 6 if entrada[:2] == struct.pack('<H', 0x001B) else 0
    if not veces or len(entrada) <= base + OFF_MEJORA:
        return entrada
    b = bytearray(entrada)
    b[base + OFF_MEJORA] = min(255, int(veces))
    return bytes(b)


# Los stats EXTRA de una pieza -- los que reparte el martillo verde -- viven
# en la propia entrada, desde el offset 11, en registros de cuatro bytes:
#
#     [u16 valor][u8 0][u8 id]
#
# MEDIDO el 29/09/2026 con nueve tiradas seguidas sobre las mismas Boots Of
# Contempt. Los ids se identificaron solos comparando cada valor con los
# rangos que el cuadro del juego enseñaba -- HP 0-272, MP 0-184, Defense
# 0-824, Spell Defense 0-145, Agility 0-27 --, porque cada numero solo cabia
# en uno de ellos. La tirada que dio "HP 53, MP 178" salio como dos registros,
# id 4 con 53 e id 12 con 178, que es lo que confirmo el mapa.
# El 11 de los volcados era un offset del CUERPO del log, que no lleva el
# opcode. Dentro de la entrada son 13.
OFF_EXTRAS = 13
TAM_EXTRA = 4
# CINCO, y no seis. Los stats verdes van en registros de 4 bytes a partir
# del 13, asi que el sexto caeria en el 33..36, que es justo donde vive el
# CONTENEDOR (01+entidad para la mochila, 02+252 para el banco). Un martillo
# verde que repartiera seis stats borraba el contenedor de la pieza y el
# cliente se cerraba con "This program will be terminated".
# En las capturas los huecos 0 a 4 salen cientos de veces cada uno (799, 692,
# 597, 393 y 360) y el quinto se desploma a 2, que son bytes del contenedor
# pareciendo un id. No hay sexto hueco.
MAX_EXTRAS = 5

# Los ids van de cuatro en cuatro. Los cinco primeros salieron de nueve
# tiradas sobre unas botas y los cuatro ultimos de trece sobre una montura,
# que ofrece otros stats: Attack 0-210, Defense 0-210, Spell Attack 0-210,
# Spell Defense 0-210, Rigor 0-54, Agility 0-54, Movement Speed 0-40. Otra
# vez cada valor solo cabia en un rango, y el 60 lo clavo: su maximo salio
# 40, que es justo el tope de la velocidad.
ID_EXTRA = {
    'hp': 4,
    'mp': 12,
    'atk': 32,
    'dfs': 40,
    'matk': 44,
    'mdef': 48,
    'rigor': 52,
    'agilidad': 56,
    'velocidad': 60,
    # Los dos de las MOCHILAS, medidos el 29/09/2026 en una Green Beetle Bag
    # (item 1869, nivel 45). El cuadro que enseña el juego antes de usar el
    # martillo lista "Maximum Weight" y "Backpack slots" junto a HP, MP y
    # Defense, y en la entrada salieron los ids 28 y 192 al lado del 40
    # (defensa) y el 12 (mana). El 192 llevaba dias apuntado como
    # desconocido: es el numero de casillas que suma la mochila.
    'peso': 28,
    'ranuras': 192,
}


def marcar_extras(entrada: bytes, extras: dict) -> bytes:
    """Escribe en la entrada los stats extra del martillo verde."""
    base = 6 if entrada[:2] == struct.pack('<H', 0x001B) else 0
    if not extras or len(entrada) < base + OFF_EXTRAS + TAM_EXTRA:
        return entrada
    b = bytearray(entrada)
    hueco = 0
    for nombre, valor in extras.items():
        sid = ID_EXTRA.get(nombre)
        if sid is None or not valor or hueco >= MAX_EXTRAS:
            continue
        o = base + OFF_EXTRAS + hueco * TAM_EXTRA
        if o + TAM_EXTRA > len(b):
            break
        struct.pack_into('<H', b, o, min(0xFFFF, int(valor)))
        b[o + 2] = 0
        b[o + 3] = sid
        hueco += 1
    return bytes(b)


def leer_extras(entrada: bytes) -> dict:
    """Lo contrario: saca los stats extra de una entrada."""
    base = 6 if entrada[:2] == struct.pack('<H', 0x001B) else 0
    por_id = {v: k for k, v in ID_EXTRA.items()}
    out = {}
    for h in range(MAX_EXTRAS):
        o = base + OFF_EXTRAS + h * TAM_EXTRA
        if o + TAM_EXTRA > len(entrada):
            break
        valor = struct.unpack_from('<H', entrada, o)[0]
        sid = entrada[o + 3]
        if valor and sid in por_id:
            out[por_id[sid]] = valor
    return out


def nivel_de_item(item_id: int) -> int:
    """El nivel de la pieza, de 物品等級. Cero si no lo declara.

    Lo usan las mejoras: cada mortero sirve "for gears under lvl N" y cada
    gema exige un nivel minimo al arma, asi que sin esto no se puede decir ni
    que si ni que no.
    """
    try:
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if not db.exists():
            return 0
        con = sqlite3.connect(db)
        fila = fila_item(con, '物品等級', item_id)
        con.close()
        return int(fila[0]) if fila and fila[0] else 0
    except Exception:
        return 0


def velocidad_de_montura(item_id: int) -> int:
    """El move_speed de una montura, en por ciento, o 0 si no lo es.

    Medido en Celestia quitando y poniendo la montura al mismo personaje: a
    pie 122, con la Earthy Piglet 226 y con la 40441 212. Las DOS declaran
    move_speed=60, asi que con esta columna sola no salen esos numeros: lo que
    aporta una montura depende de su propia instancia -- son mascotas con
    nivel --, y eso no viaja en item.xml. Se usa el porcentaje porque es lo
    unico que los datos del cliente sostienen; ver la nota de app.py.
    """
    if item_id in _VEL_MONTURA:
        return _VEL_MONTURA[item_id]
    v = 0
    if ranura_equipo_de(item_id) in (10, 174):
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            try:
                con = sqlite3.connect(db)
                fila = fila_item(con, 'move_speed', item_id)
                if fila and fila[0]:
                    v = int(float(fila[0]))
            except Exception:
                v = 0
    _VEL_MONTURA[item_id] = v
    return v


_DUAL_CACHE = {}
_FASHION_CACHE = {}


def es_item_fashion(item_id: int) -> bool:
    """Si el item pertenece a la categoria Fashion / Paper Doll (167..174)."""
    ranura_equipo_de(item_id)
    return _FASHION_CACHE.get(item_id, False)


def es_arma_dual(item_id: int) -> bool:
    """Si el arma se puede equipar en ambas manos (derecha e izquierda)."""
    ranura_equipo_de(item_id)
    return _DUAL_CACHE.get(item_id, False)


def es_ranura_valida(item_id: int, ranura: int) -> bool:
    """Verifica si un item puede colocarse en esa ranura especifica para evitar pisar armadura real con fashion."""
    if ranura == RANURA_INSIGNIA:
        # La 175 esta por encima del inicio de la mochila, asi que antes
        # pasaba por "mochila" sin mirar nada. Es la ranura de la insignia y
        # solo admite insignias.
        return ranura_equipo_de(item_id) == RANURA_INSIGNIA
    if ranura >= PRIMERA_RANURA_BOLSA: # >= 20 (mochila siempre valida)
        return True
    if es_mascota(item_id):
        # UNA MASCOTA NO ES UN ACCESORIO. item.xml las resuelve a la ranura 9,
        # que es el segundo Trinket, asi que desde que la 9 empezo a admitir
        # accesorios se podian equipar como si fueran un anillo. Tienen su
        # propia ranura, y ademas solo entran con 5 estrellas: la Battlemaid
        # de la captura iba por 0.1. Hasta saber el numero de esa ranura no
        # se equipan en ninguna, que es mejor que equiparlas en la que no es.
        return False
    target = ranura_equipo_de(item_id)
    if target is None:
        return False
    # Los accesorios valen en la 8 Y en la 9, los dos "Trinket". Se exigia
    # ranura == target, asi que arrastrar un anillo al segundo hueco daba
    # "ranura no valida" y el objeto se quedaba donde estaba.
    if ranura in RANURAS_ACCESORIO and target in RANURAS_ACCESORIO:
        return True
    # Pestaña Fashion (167..174):
    if es_fashion(ranura):
        if not es_item_fashion(item_id):
            return False
        if target == 169 and ranura in (169, 170) and es_arma_dual(item_id):
            return True
        return ranura == target
    # Pestaña Gear regular (1..10):
    else:
        if es_item_fashion(item_id):
            return False # Un item de Fashion NUNCA va en la pestaña de Gear!
        if target == 3 and ranura in (3, 4):
            return ranura == 3 or es_arma_dual(item_id)
        return ranura == target


# Donde va la insignia. MEDIDO el 29/09/2026: al ponerse una Purple Seashell
# Badge el servidor real la coloco en la 175, justo despues de las ranuras de
# Fashion (167..174). No es la 11 como se habia supuesto.
RANURA_INSIGNIA = 175

# Los accesorios tienen DOS ranuras, no una: los dos "Trinket" de la ventana.
# Se vio un Stealth Ring en la 9 mientras nuestro codigo mandaba todos los
# accesorios a la 8, y por eso la segunda no aceptaba nada.
RANURAS_ACCESORIO = (8, 9)


def ranuras_posibles(item_id: int):
    """Todas las ranuras donde cabe ese item, en orden de preferencia."""
    r = ranura_equipo_de(item_id)
    if r is None:
        return []
    if r in RANURAS_ACCESORIO:
        return list(RANURAS_ACCESORIO)
    return [r]


def ranura_libre_equipo(item_id: int, bolsa):
    """La ranura donde ponerlo: la primera suya que este libre.

    Si todas estan ocupadas devuelve la primera, que es la que se cambia.
    """
    posibles = ranuras_posibles(item_id)
    if not posibles:
        return None
    for r in posibles:
        if r not in bolsa:
            return r
    return posibles[0]


def ranura_equipo_de(item_id: int):
    """Devuelve la ranura de equipamiento donde se coloca el item, o None si no es equipable."""
    global _SLOT_CACHE, _DUAL_CACHE, _FASHION_CACHE
    if _SLOT_CACHE is None:
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        _SLOT_CACHE = {}
        _DUAL_CACHE = {}
        _FASHION_CACHE = {}
        if db.exists():
            con = sqlite3.connect(db)
            campos = ','.join(f'"{c}"' for c in COLUMNAS_EQUIPO)
            # Los items estan repartidos en item, item2 ... item9, una por
            # update del cliente. Mirando solo la primera, todo lo que vino
            # en un update posterior quedaba sin ranura y no se podia
            # equipar: la montura Galactic Moped, por ejemplo, vive en item5.
            filas = []
            for _tabla in ('item', 'item2', 'item3', 'item4', 'item5',
                           'item6', 'item7', 'item8', 'item9'):
                try:
                    filas += list(con.execute(
                        f'select id,"物品類別",{campos} from {_tabla} '
                        "where id glob '[0-9]*'"))
                except Exception:
                    continue
            for fila in filas:
                iid = int(fila[0])
                cat = str(fila[1] or '')
                rhand, lhand, head, acc, body, hands, feet, back, pet = [v == '是' for v in fila[2:]]
                if rhand and lhand:
                    # Solo Espadas (劍, 刀) y Hachas/Mazas (斧, 錘, 锤) o Fashion duales se pueden equipar en ambas manos.
                    # Shadow Blade (影刃) es de 1 mano (permite escudo en la 4), pero NO se puede llevar en duales.
                    if cat == '紙娃娃' or any(k in cat for k in ('劍', '刀', '斧', '錘', '锤')):
                        _DUAL_CACHE[iid] = True
                if cat == '紙娃娃':
                    _FASHION_CACHE[iid] = True
                    # Items de Fashion (Paper Doll) se equipan en las ranuras de la pestaña Fashion (167..174)
                    if head:
                        _SLOT_CACHE[iid] = 167
                    elif body:
                        _SLOT_CACHE[iid] = 168
                    elif rhand:
                        _SLOT_CACHE[iid] = 169
                    elif lhand:
                        _SLOT_CACHE[iid] = 170
                    elif hands:
                        _SLOT_CACHE[iid] = 171
                    elif feet:
                        _SLOT_CACHE[iid] = 172
                    elif back:
                        _SLOT_CACHE[iid] = 173
                    elif pet or cat == '座騎':
                        _SLOT_CACHE[iid] = 174
                elif cat == '座騎':
                    _SLOT_CACHE[iid] = 10
                elif cat == '寵物' or (pet and not (body or head or hands or feet or back or rhand or lhand)):
                    _SLOT_CACHE[iid] = 9
                elif rhand:
                    _SLOT_CACHE[iid] = 3
                elif lhand:
                    _SLOT_CACHE[iid] = 4
                elif body:
                    _SLOT_CACHE[iid] = 2
                elif head:
                    _SLOT_CACHE[iid] = 1
                elif hands:
                    _SLOT_CACHE[iid] = 5
                elif feet:
                    _SLOT_CACHE[iid] = 6
                elif back:
                    _SLOT_CACHE[iid] = 7
                elif acc:
                    _SLOT_CACHE[iid] = 8
                elif cat == '徽章':
                    # INSIGNIAS. No declaran ninguna columna de equipo, asi
                    # que se quedaban SIN RANURA: no se podian poner y por eso
                    # sus bonos no llegaban nunca, aunque los leyeramos bien
                    # (una Crystal Badge declara +3484 de ataque).
                    #
                    # Su ranura no se ha podido medir: en ninguna captura hay
                    # una insignia equipada. Se usa la 11, la siguiente libre
                    # despues de la montura, y se puede cambiar en un sitio.
                    _SLOT_CACHE[iid] = RANURA_INSIGNIA
    return _SLOT_CACHE.get(item_id)

_TWO_HAND_CACHE = {}
_CAT_ITEM_CACHE = None


def categoria_de(item_id: int) -> str:
    """Devuelve la categoria (物品類別) del item en item.xml."""
    global _CAT_ITEM_CACHE
    if not item_id:
        return ''
    iid = int(item_id)
    if _CAT_ITEM_CACHE is None:
        _CAT_ITEM_CACHE = {}
        f_json = pathlib.Path(__file__).parent / 'plantillas' / 'client_tables.json'
        if f_json.exists():
            try:
                raw = json.loads(f_json.read_text(encoding='utf-8'))
                for k, v in (raw.get('item_cats') or {}).items():
                    _CAT_ITEM_CACHE[int(k)] = str(v)
            except Exception:
                pass
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            try:
                con = sqlite3.connect(db)
                for _t in TABLAS_ITEM:
                    try:
                        cols = [r[1] for r in con.execute('pragma table_info(%s)' % _t)]
                        id_col = 'id' if 'id' in cols else '"\u7de8\u865f"'
                        for r_id, r_cat in con.execute(f'SELECT {id_col}, "\u7269\u54c1\u985e\u5225" FROM {_t}'):
                            if r_id and str(r_id).isdigit() and r_cat:
                                _CAT_ITEM_CACHE[int(r_id)] = str(r_cat)
                    except Exception:
                        continue
            except Exception:
                pass
    return _CAT_ITEM_CACHE.get(iid, '')


def es_arco(item_id: int) -> bool:
    """Si el arma es un arco (弓箭)."""
    cat = categoria_de(item_id)
    return '弓箭' in cat or '340弓' in cat


def es_honda(item_id: int) -> bool:
    """Si el arma es una honda / tirachinas / catapulta (彈弓)."""
    cat = categoria_de(item_id)
    return '彈弓' in cat


def es_flecha(item_id: int) -> bool:
    """Si el item es una flecha para arco (箭矢)."""
    cat = categoria_de(item_id)
    return '箭矢' in cat


def es_bala(item_id: int) -> bool:
    """Si el item es municion / bolitas para honda (彈藥 o 小鋼珠)."""
    cat = categoria_de(item_id)
    return '彈藥' in cat or '小鋼珠' in cat


def es_municion(item_id: int) -> bool:
    """Si el item es municion de arquero (flechas o bolitas de honda)."""
    return es_flecha(item_id) or es_bala(item_id)


def es_arma_dos_manos(item_id: int) -> bool:
    """Si el arma ocupa ambas manos y NO admite nada en la mano izquierda (Staff 杖, Spear 槍, etc.).
    Nota: Los arcos (弓箭) y hondas (彈弓) van en la mano derecha (3) pero SI admiten
    su municion correspondiente (flechas o bolitas) en la mano izquierda (4)."""
    global _TWO_HAND_CACHE
    if not item_id:
        return False
    iid = int(item_id)
    if iid in _TWO_HAND_CACHE:
        return _TWO_HAND_CACHE[iid]
    cat = categoria_de(iid)
    res = any(k in cat for k in ('槍', '杖', '雙手', '釣竿', '鐵鍬'))
    _TWO_HAND_CACHE[iid] = res
    return res


def compatibles_manos(rhand_id: int, lhand_id: int) -> bool:
    """Verifica si el item de la mano derecha (ranura 3) y el de la mano izquierda (ranura 4)
    pueden llevarse equipados al mismo tiempo:
      - Armas de 2 manos puras (Staff, Spear, etc.): no admiten nada en la 4.
      - Arco (弓箭) en la 3: solo admite Flechas (箭矢) en la 4.
      - Honda (彈弓) en la 3: solo admite Bolitas/Balas (彈藥 / 小鋼珠) en la 4.
      - Armas de 1 mano en la 3: admiten Escudo (盾) o arma dual en la 4, pero NO flechas ni bolitas."""
    if not rhand_id or not lhand_id:
        return True
    if es_arma_dos_manos(rhand_id):
        return False
    if es_arco(rhand_id):
        return es_flecha(lhand_id)
    if es_honda(rhand_id):
        return es_bala(lhand_id)
    if es_flecha(lhand_id) or es_bala(lhand_id):
        return False
    return True



def sprite_de_mascota(item_id: int) -> int:
    """Devuelve el ID de sprite (圖號1) de la mascota/huevo para invocarla."""
    global _PET_SPRITE_CACHE
    if item_id in _PET_SPRITE_CACHE:
        return _PET_SPRITE_CACHE[item_id]
    import sqlite3
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    sprite = 44069   # Default: Fire Elf Egg sprite
    if db.exists():
        try:
            con = sqlite3.connect(db)
            row = fila_item(con, '"動態資料1"', item_id)
            if row and row[0]:
                pet_id = str(row[0]).strip()
                import xml.etree.ElementTree as ET
                p_xml = pathlib.Path('f:/Ao Proyect/AO/data/game_xml/setting_full/setting/eng/pet.xml')
                if p_xml.exists():
                    tree = ET.parse(p_xml)
                    for elem in tree.getroot():
                        if elem.attrib.get('編號') == pet_id:
                            sp = elem.attrib.get('圖號1')
                            if sp and sp.isdigit():
                                sprite = int(sp)
                                break
        except Exception:
            pass
    _PET_SPRITE_CACHE[item_id] = sprite
    return sprite


def es_comida_mascota(item_id: int) -> bool:
    """Si el item es comida o suplemento exclusivo de mascota (Pet Cookies, Pet Can, Pet Feed)."""
    return item_id in (3374, 3375, 3376)


_RECOMPENSAS_CACHE = {}

def recompensas_caja(item_id: int):
    """Si el item es una caja de regalo o bolsa de la suerte (Elf Lucky Bag, Growth Boxes, etc.),
    devuelve lista de (item_id, cantidad) a entregar. Si no, devuelve None."""
    if es_comida_mascota(item_id):
        return None
    import sqlite3, random
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if not db.exists():
        return None
    try:
        con = sqlite3.connect(db)
        row = fila_item(con, '"動態資料1", "物品類別", "基本名稱"', item_id)
        if not row:
            return None
        drop_id = str(row[0]).strip() if row[0] else None
        cat = str(row[1] or '')
        name = str(row[2] or '')

        # Caso especial: Elf Lucky Bag / Elf Egg / 妖精蛋
        # Da una de las 4 mascotas elfos elementales
        if ('elf' in name.lower() and any(k in name.lower() for k in ('bag', 'lucky', 'egg'))) or '妖精' in name:
            mascotas_elfo = [3396, 3397, 3398, 3399]  # Water, Fire, Wind, Earth Elf Egg
            return [(random.choice(mascotas_elfo), 1)]

        # Solo procesar categorias de cajas / bolsas / huevos
        categorias_validas = ('紅包', '扭蛋', '禮物', '禮盒', '寶箱')
        es_bolsa = any(k in name.lower() for k in ('bag', 'lucky', 'egg', 'box', 'gift', 'chest', 'package', 'combine', 'set')) or cat in categorias_validas or any(k in name for k in ('福袋', '禮包', '蛋'))
        if not es_bolsa or not drop_id:
            return None

        dt = con.execute('select * from drop_table where id=?', (drop_id,)).fetchone()
        if not dt:
            return None
        cols = [c[1] for c in con.execute('pragma table_info(drop_table)').fetchall()]
        row_dict = dict(zip(cols, dt))
        rewards = []
        for i in range(1, 21):
            it = row_dict.get(f'item{i}')
            cnt = row_dict.get(f'count{i}')
            if it and str(it).strip() and str(it).isdigit():
                rewards.append((int(it), int(cnt) if cnt and str(cnt).isdigit() else 1))
        if not rewards:
            return None

        # Si incluye mascotas elfo, dar una de las 4 mascotas elfo
        mascotas_elfo = [3396, 3397, 3398, 3399]
        if any(r[0] in mascotas_elfo for r in rewards):
            return [(random.choice(mascotas_elfo), 1)]

        # Lucky Bags / Red Envelopes / Eggs dan 1 item aleatorio
        if cat in ('紅包', '扭蛋') or any(k in name.lower() for k in ('lucky', 'bag', 'egg')) or any(k in name for k in ('福袋', '蛋')):
            return [random.choice(rewards)]

        # Cajas de regalo (Growth Boxes, Combines, Sets) dan todo el contenido
        return rewards
    except Exception:
        return None


def durabilidad(item_id: int) -> int:
    """Durabilidad maxima que trae un item nuevo, de item.xml."""
    base = _tabla().get(item_id, (False, 0))[1]
    if not base:
        if es_mascota(item_id):
            return 100
        return 0
    import os
    try:
        factor = float(os.environ.get('AO_DURABILIDAD', '1'))
    except ValueError:
        factor = 1.0
    return max(0, min(int(base * factor), 0xFFFFFFFF))


def _entrada(char_id: int, ranura: int, item_id: int, cant: int,
             inst: bytes = None, dueno: int = None,
             mascota: dict = None) -> bytes:
    """Los bytes que describen lo que hay en una casilla.

    Son 86 para lo que no se equipa y 119 para lo que si. 'dueno' es la
    ENTIDAD del personaje, no su char_id: en la captura los dos numeros son
    distintos (286 y 282) y el que viaja aqui es el de la entidad. Si no se
    pasa se usa el char_id, que es lo que se hacia antes.
    """
    if dueno is None:
        dueno = char_id
    p = _plantilla_inicial()
    es_eq = es_equipable(item_id)
    e = bytearray(bytes.fromhex(p['equipable'] if es_eq else p['normal']))
    # El cuarto dato es el id de instancia del monton. Si no viene se deriva
    # del item, que es lo que se hacia siempre; pero dos montones del mismo
    # item comparten esa derivacion y el cliente los confunde al venderlos,
    # asi que quien lleve el mapa debe pasarlo.
    e[1:9] = (bytes(inst)[:8] if inst else instancia_de(char_id, item_id))
    struct.pack_into('<I', e, 9, item_id)
    struct.pack_into('<I', e, 34, dueno)
    struct.pack_into('<H', e, 38, ranura)
    struct.pack_into('<I', e, 40, cant)
    # La mascota manda sobre lo demas: varias salen tambien como
    # equipables en item.xml, y con el 'not es_eq' de antes se les
    # armaba la entrada de 119 y volviamos al cierre del cliente.
    if es_mascota(item_id):
        # Una mascota no cabe en los 86 bytes normales: son 231, con nombre,
        # nivel, vida, mana, experiencia, saciedad e intimidad dentro. Antes
        # se le escribian datos en el offset 13, que es donde viven los stats
        # verdes, y el cliente se cerraba al pasarle el raton por encima. El
        # mapa bueno esta en mascotas.OFF_ENTRADA, sacado de 63 entradas de
        # las capturas y comprobado contra las nueve fichas 0x0065.
        d = datos_mascota(item_id)
        base = bytearray(bytes.fromhex(p['mascota']))
        if (isinstance(mascota, dict)
                and (mascota.get('ranura') == ranura
                     or (mascota.get('ranura') is None
                         and mascota.get('item') == item_id))):
            est_pet = dict(mascota)
        else:
            import configuracion as _cf
            est_pet = _ms.recien_nacida(
                d['nombre'], d['sprite'],
                nivel=max(1, getattr(_cf, 'MASCOTA_NIVEL_INICIAL', 1)))
        inst_id = int(est_pet.get('instancia') or (1000 + int(ranura))) & 0xFFFFFFFF
        struct.pack_into('<II', base, 1, inst_id, inst_id)
        struct.pack_into('<I', base, 9, item_id)
        struct.pack_into('<I', base, 34, dueno)
        struct.pack_into('<H', base, 38, ranura)
        struct.pack_into('<I', base, 40, cant)
        base[51] = 0x91
        struct.pack_into('<I', base, 53, char_id if char_id else (dueno or 0))
        base[57] = 0
        base[58] = 0
        struct.pack_into('<H', base, 84, inst_id & 0xFFFF)
        return _ms.entrada(bytes(base), est_pet)
    else:
        struct.pack_into('<I', e, OFF_DURABILIDAD, durabilidad(item_id))
    if es_eq:
        # Donde esta puesta la prenda. Comparando el mismo NewbieHeavy
        # Costume en la mochila y en el cuerpo, lo unico que cambia ademas
        # de la casilla es esto:
        #     off 53  la entidad que la lleva, o cero si esta guardada
        #     off 57  el contenedor: 3 mochila, 2 cuerpo
        # Nosotros dejabamos los dos en cero, asi que el cliente nunca se
        # enteraba de que la prenda estaba PUESTA y seguia dibujando al
        # personaje en ropa interior.
        puesta = es_equipo(ranura)
        struct.pack_into('<I', e, 53, char_id if char_id else (dueno or 0))
        limite, al_equipar = vinculaciones_de(item_id)
        e[57] = min(255, max(0, limite - int(puesta and al_equipar)))
        e[58] = 1
        # Offset 51 (0x33) es el campo que le indica al cliente que esta entrada
        # mide 119 bytes (86 + 33 extra). NUNCA debe alterarse en un equipable.
        e[51] = 0x21
        # Y el servidor repite ahi los dieciseis bits bajos del numero de
        # instancia.
        struct.pack_into('<I', e, 84,
                         struct.unpack_from('<I', e, 1)[0] & 0xFFFF)
    return bytes(e)


def completo(char_id: int, items, dueno: int = None, mejoras=None,
             mascota: dict = None, mascotas: dict = None) -> bytes:
    """Sub-mensaje 0x001A con todo el inventario.

    items: iterable de (ranura, item_id[, cantidad[, instancia]]).

    `mejoras` es {ranura: {'veces': N, 'extra': {...}}}. SIN ESTO el "+N" y
    los stats verdes solo se veian mientras durase la sesion: actualizar_ranura
    los sellaba, pero este mensaje -- que es el que se manda AL ENTRAR -- no,
    asi que al reconectar el arma volvia a salir limpia aunque el servidor
    llevase la cuenta bien y la tuviera guardada en disco.
    """
    mejoras = mejoras or {}
    mascotas = mascotas or {}
    lista = []
    for it in sorted(items, key=lambda x: int(x[0])):
        ran = int(it[0])
        iid = int(it[1])
        cnt = int(it[2]) if len(it) > 2 else 1
        ins = it[3] if len(it) > 3 else None
        
        pet_spec = None
        if es_mascota(iid):
            if str(ran) in mascotas:
                pet_spec = mascotas[str(ran)]
            elif ran in mascotas:
                pet_spec = mascotas[ran]
            elif isinstance(mascota, dict) and (mascota.get('ranura') == ran or (mascota.get('ranura') is None and mascota.get('item') == iid)):
                pet_spec = mascota

        _e = _entrada(char_id, ran, iid, cnt, ins, dueno, mascota=pet_spec)
        if not es_mascota(iid):
            _m = mejoras.get(ran)
            _e = marcar_vinculacion(_e, _m)
            if _m and _m.get('veces'):
                _e = marcar_mejora(_e, _m['veces'])
            if _m and _m.get('extra'):
                _e = marcar_extras(_e, _m['extra'])
            if _m and (_m.get('huecos') or _m.get('gemas')):
                _e = marcar_huecos(_e, _m.get('huecos') or 0, _m.get('gemas'))
        lista.append(_e)
    fuera = struct.pack('<I', len(lista)) + b''.join(lista)
    return struct.pack('<H', 0x001A) + fuera


def almacen(char_id: int, items, dueno: int = None,
            tipo: int = 2) -> bytes:
    """Sub-mensaje 0x004E con el almacen del banco.

    El cuerpo es EL MISMO que el del 0x001A: un LE32 con el numero de
    entradas y detras esas entradas, de 86 bytes las corrientes y 119 las
    equipables. Se comprobo contra la captura de Edo City del 28/09/2026, en
    la que el servidor real contesta 824 bytes al elegir "I wish to use my own
    warehouse": ocho entradas, cuatro de 86 y cuatro de 119, que suman 820
    mas los cuatro de la cabecera.

    Antes se mandaba un 0x002B, que es otro mensaje: el cliente no abria nada
    y soltaba un aviso de la lista de amigos.

    El LE32 de la cabecera NO es solo la cuenta: lleva el tipo multiplicado
    por mil y la cuenta en las unidades. Las dos funciones del cliente que
    crean la ventana del banco -- las dos llaman a CreateBankWnd -- hacen
    `tipo = n / 1000` y `cuenta = n % 1000`, y solo abren cuando el tipo es 2
    o 3. Con tipo 0 rellenan la lista y nada mas.

    Por eso va TIPO 2. Mandandolo como cuenta pelada la ventana no se abria,
    ni vacia ni con un objeto dentro. En la captura del servidor real ese
    numero valia 8, o sea tipo 0: ahi la ventana ya debia estar creada por
    otro camino que no se ha llegado a ver.
    """
    lista = []
    for it in sorted(items, key=lambda x: int(x[0])):
        lista.append(entrada_banco(char_id, int(it[0]), int(it[1]),
                                   int(it[2]) if len(it) > 2 else 1,
                                   it[3] if len(it) > 3 else None, dueno))
    return (struct.pack('<HI', 0x004E, tipo * 1000 + len(lista))
            + b''.join(lista))


def banco_vaciar_ranura(ranura: int) -> bytes:
    """Sub-mensaje 0x001B que dice que una casilla del banco quedo vacia.

    Medido en la captura de Edo City: al arrastrar dentro del almacen el
    servidor real contesta SIEMPRE dos sub-mensajes, y este es el primero.
    Son doce bytes: la cuenta, un 02 de accion, los cinco del marcador
    02fc000000 que tambien llevan las entradas del almacen, y la casilla que
    se vacia.
    """
    return vaciar_ranura(ID_BANCO, ranura, CONT_BANCO)


def banco_poner(char_id: int, ranura: int, item_id: int, cant: int = 1,
                inst: bytes = None, dueno: int = None) -> bytes:
    """Sub-mensaje 0x001B con lo que queda en una casilla del banco.

    Es el segundo de los dos que contesta el servidor real al mover: la
    cuenta y detras la entrada, con el mismo formato de 86 o 119 bytes que
    usa el inventario. Los tamanos de la captura cuadran: 90 bytes cuando lo
    movido no se equipa y 123 cuando si.
    """
    return (struct.pack('<H', 0x001B) + struct.pack('<I', 1)
            + entrada_banco(char_id, ranura, item_id, cant, inst, dueno))


def entrada_banco(char_id: int, ranura: int, item_id: int, cant: int = 1,
                  inst: bytes = None, dueno: int = None) -> bytes:
    """Una entrada del almacen: la del inventario con tres campos cambiados.

    Comparando byte a byte una entrada nuestra con una de la captura, las
    unicas diferencias reales son estas tres (la cuarta es el numero de
    instancia, que el servidor real genera a su manera y nosotros derivamos):

      +33  el contenedor. En la mochila va 01 y la ENTIDAD del personaje; en
           el almacen va 02 y el 252, el mismo par que usa el sub-mensaje que
           vacia una casilla.
      +40  las unidades del monton. Se comprobo con las ocho entradas de la
           captura: 14, 1, 174, 1, 1, 1, 59 y 252, que son las cantidades que
           se ven en la ventana del almacen.
      +84  los dieciseis bits bajos del numero de instancia. En la mochila
           solo los lleva lo equipable; en el almacen los llevan todas.
    """
    return _entrada_marcada(char_id, ranura, item_id, cant, inst, dueno,
                            CONT_BANCO, ID_BANCO)


def entrada_recuperada(char_id: int, ranura: int, item_id: int, cant: int = 1,
                       inst: bytes = None, dueno: int = None) -> bytes:
    """La entrada de lo que vuelve del almacen a la mochila.

    Es una entrada de mochila normal, pero el servidor real le pone las
    unidades en el +40 y el eco de la instancia en el +84, que en las
    entradas corrientes de la bolsa no van. Medido en el 0x001B de 90 bytes
    con el que contesta al sacar algo del banco.
    """
    return _entrada_marcada(char_id, ranura, item_id, cant, inst, dueno,
                            CONT_MOCHILA, dueno if dueno else char_id)


def _entrada_marcada(char_id, ranura, item_id, cant, inst, dueno,
                     contenedor, ident) -> bytes:
    """La entrada de siempre con el contenedor, las unidades y el eco."""
    e = bytearray(_entrada(char_id, ranura, item_id, cant, inst, dueno))
    struct.pack_into('<BI', e, 33, contenedor, ident)
    e[40] = min(int(cant), 255)
    struct.pack_into('<H', e, 84, struct.unpack_from('<H', e, 1)[0])
    return bytes(e)


def banco_sacar(char_id: int, ranura: int, item_id: int, cant: int = 1,
                inst: bytes = None, dueno: int = None) -> bytes:
    """Sub-mensaje 0x001B con lo que llega a la mochila desde el almacen."""
    return (struct.pack('<H', 0x001B) + struct.pack('<I', 1)
            + entrada_recuperada(char_id, ranura, item_id, cant, inst, dueno))


def acuse_movimiento(ranura: int, accion: int = 0x0012) -> bytes:
    """0x0006 s2c: "hecho lo que pediste con esa casilla".

    Medido al equipar: el cliente manda 0x0012 [41][2] y lo primero que le
    llega de vuelta es 0x0006 con 12 00 29 00, o sea el opcode que se
    confirma y la casilla de origen; despues vienen el 0x001B y el 0x0042.
    Sin este acuse el cliente apunta el cambio en el panel de equipo y en
    los stats pero no redibuja al personaje: el equipo queda invisible.
    """
    return struct.pack('<HHH', 0x0006, accion, ranura)


def actualizar_ranuras(char_id: int, entradas, dueno: int = None,
                       mascota: dict = None) -> bytes:
    """0x001B con varias casillas de una vez.

    Es lo que manda el servidor al equipar: en la captura, mover la prenda
    de la casilla 41 al cuerpo devuelve UN 0x001B con dos entradas -- la
    prenda ya en la casilla 2 y la que llevaba puesta de vuelta en la 41 --
    y despues el 0x0042 con los stats. Antes se mandaban dos mensajes de
    movimiento con un formato antiguo que no lleva el estado de puesto.

    entradas: iterable de (ranura, item_id, cantidad, instancia).
    """
    lista = [_entrada(char_id, int(r), int(i), int(c), ins, dueno,
                      mascota=mascota)
             for r, i, c, ins in entradas]
    return (struct.pack('<HI', 0x001B, len(lista)) + b''.join(lista))


def actualizar_ranura(char_id: int, ranura: int, item_id: int, cant: int,
                      inst: bytes = None, dueno: int = None,
                      mascota: dict = None) -> bytes:
    """0x001B de 90 bytes: como queda UNA casilla.

    Es lo que manda el servidor real despues de comprar, vender, usar o
    separar: una linea por casilla tocada, no el inventario entero. Al
    reenviar el 0x001A completo el cliente se quedaba con lo que ya tenia
    pintado y los items vendidos seguian viendose en la mochila.
    """
    return (struct.pack('<HI', 0x001B, 1)
            + _entrada(char_id, ranura, item_id, cant, inst, dueno,
                       mascota=mascota))


# ------------------------------------------------- entrega de un item
# Para entregar items se manda cont1 (contenedor 1 = inventario/mochila).
# No se manda cont2 (que movia al equipo ranura 3 y vaciaba la 20).
PLANTILLA_ENTREGA = pathlib.Path(__file__).parent / 'plantillas' / 'entrega_item.json'
_PE = None


def _plantilla_entrega():
    global _PE
    if _PE is None:
        _PE = json.loads(PLANTILLA_ENTREGA.read_text(encoding='utf-8'))
    return _PE


def entregar(char_id: int, item_id: int, ranura: int):
    """Sub-mensaje 0x001B cont1 que mete un item en la mochila del inventario."""
    p = _plantilla_entrega()
    b = bytearray(bytes.fromhex(p['cont1']))
    b[5:13] = instancia_de(char_id, item_id)
    struct.pack_into('<I', b, 13, item_id)
    struct.pack_into('<I', b, 38, char_id)
    struct.pack_into('<H', b, 42, ranura)
    dur = durabilidad(item_id)
    if es_mascota(item_id):
        nombres_elfos = {3396: b"Water Elf\x00", 3397: b"Fire Elf\x00", 3398: b"Wind Elf\x00", 3399: b"Earth Elf\x00"}
        nom_pet = nombres_elfos.get(item_id, b"Pet\x00")
        b[17:17 + len(nom_pet)] = nom_pet
        struct.pack_into('<I', b, 48, 100)
        struct.pack_into('<I', b, 52, 100)
        struct.pack_into('<I', b, 56, 100)
        struct.pack_into('<I', b, 60, 1)
    else:
        struct.pack_into('<I', b, 48, dur)
    return [struct.pack('<H', 0x001B) + bytes(b)]


def efecto_consumible(item_id: int):
    """Devuelve dict con {'hp': X, 'mp': Y} si el item es un consumible/pocion/hierba, o None."""
    import sqlite3, re
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if not db.exists():
        return None
    try:
        con = sqlite3.connect(db)
        row = fila_item(con, '"動態資料1", "常駐法術", "物品類別", "基本名稱", "說明"', item_id)
        if not row:
            return None
        d1, mid, cat, name, desc = str(row[0] or ''), str(row[1] or ''), str(row[2] or ''), str(row[3] or ''), str(row[4] or '')
        # Un pergamino de habilidad, tarjeta, mascota, caja, etc., NUNCA es consumible de HP/MP
        import skills as _sk_check
        if _sk_check.info_pergamino(item_id):
            return None
        if es_advancement_stone(item_id) or es_skill_leveling_stone(item_id):
            return None
        if cat in ('卷軸', '卡片', '寵物', '紅包', '扭蛋', '禮物', '禮盒', '寶箱', '配方', '防禦塔', '訂單', '表情卡', '徽章', '座騎', '強化道具', '紙娃娃'):
            return None

        res = {}
        # 1. Si apunta a un registro en magic.xml via 常駐法術 o 動態資料1
        magic_id = mid if mid and mid.isdigit() else (d1 if d1 and d1.isdigit() else None)
        if magic_id:
            m_row = con.execute('select hp, mp from magic where id=?', (str(magic_id),)).fetchone()
            if m_row:
                if m_row[0] and str(m_row[0]).strip().isdigit() and int(m_row[0]) > 0:
                    res['hp'] = int(m_row[0])
                if m_row[1] and str(m_row[1]).strip().isdigit() and int(m_row[1]) > 0:
                    res['mp'] = int(m_row[1])
        # 2. Si no, parsear descripcion ("restore 40 hp", "increase 50 mp")
        if not res:
            m_mp = re.search(r'(?:increase|restore)\s*(\d+)\s*mp', desc, re.I)
            if m_mp:
                res['mp'] = int(m_mp.group(1))
            m_hp = re.search(r'(?:increase|restore)\s*(\d+)\s*hp', desc, re.I)
            if m_hp:
                res['hp'] = int(m_hp.group(1))
        # 3. Heuristica SOLO para categoria '一般' (pociones / comida comun)
        if not res and d1.isdigit() and int(d1) > 0 and cat in ('一般', ''):
            val = int(d1)
            if 'mp' in name.lower() or 'magic' in name.lower() or 'blue' in name.lower():
                res['mp'] = val
            elif 'hp' in name.lower() or 'red' in name.lower() or 'potion' in name.lower() or 'hierba' in name.lower() or 'biscuit' in name.lower():
                res['hp'] = val
        return res if res else None

    except Exception:
        return None


def es_tarjeta_coleccion(item_id: int) -> bool:
    """Si el item es una tarjeta/card de monstruo coleccionable."""
    import sqlite3
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if not db.exists():
        return False
    try:
        con = sqlite3.connect(db)
        r = fila_item(con, '"物品類別", "基本名稱"', item_id)
        if r:
            return r[0] == '卡片' or 'Card' in str(r[1] or '')
        return False
    except Exception:
        return False


def es_advancement_stone(item_id: int):
    """Devuelve el nivel objetivo si el item es una Advancement Stone, o None."""
    con_nivel = {
        81997: 300,
        71989: 290,
        71987: 280,
        40931: 220,
        40930: 210,
    }
    if item_id in con_nivel:
        return con_nivel[item_id]
    import sqlite3, re
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if db.exists():
        try:
            con = sqlite3.connect(db)
            r = fila_item(con, '"基本名稱"', item_id)
            con.close()
            if r and r[0]:
                m = re.search(r'Lv\s*(\d+)\s+Advancement\s+Stone', str(r[0]), re.I)
                if m:
                    return int(m.group(1))
        except Exception:
            pass
    return None


def es_skill_leveling_stone(item_id: int):
    """Devuelve el nivel de habilidad objetivo si es una Skill Leveling Stone, o None."""
    con_skill = {
        81998: 300,
        71990: 290,
        71988: 280,
        52204: 270,
        52203: 260,
        46571: 250,
        48600: 250,
        48453: 240,
        43265: 240,
        43264: 230,
        40933: 220,
        40932: 210,
        72057: 200,
        47204: 180,
        49526: 180,
        53482: 180,
        44042: 170,
        28583: 100,
    }
    if item_id in con_skill:
        return con_skill[item_id]
    import sqlite3, re
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if db.exists():
        try:
            con = sqlite3.connect(db)
            r = fila_item(con, '"基本名稱"', item_id)
            con.close()
            if r and r[0]:
                m = re.search(r'Lv\s*(\d+)\s+Skill\s+Leveling\s+Stone', str(r[0]), re.I)
                if m:
                    return int(m.group(1))
        except Exception:
            pass
    return None

# ---------------------------------------------------------------------------
# Creditos de rango
# ---------------------------------------------------------------------------
_INVERSION = None


def creditos_de(item_id: int) -> int:
    """Cuantos creditos de rango da 'invertir' este objeto, o 0 si no da.

    Sale de investitem.xml, que es la lista de los objetos que se entregan a
    cambio de creditos: 103 entradas, de 5 creditos los mas baratos (Obsidian
    Brick, Viburnum Strip) a 200 los mas caros. Algunas entradas traen ademas
    experiencia y otras solo creditos, por eso se lee atributo a atributo y no
    por posicion.

    Ojo con una cosa: el objeto que se vio dar 120.000 creditos de golpe en la
    captura del 28/09/2026 NO esta aqui. Es de un parche posterior al cliente
    del que salieron estos xml, igual que los articulos de las tiendas de Edo
    City.
    """
    global _INVERSION
    if _INVERSION is None:
        _INVERSION = {}
        f_json = pathlib.Path(__file__).parent / 'plantillas' / 'client_tables.json'
        if f_json.exists():
            try:
                raw = json.loads(f_json.read_text(encoding='utf-8'))
                for k, v in (raw.get('invest_items') or {}).items():
                    _INVERSION[int(k)] = int(v)
            except Exception:
                pass
        if not _INVERSION:
            f = (pathlib.Path(__file__).parent.parent / 'extracted_paks' / 'data1'
                 / 'setting' / 'eng' / 'investitem.xml')
            if f.exists():
                txt = f.read_text(encoding='utf-8', errors='replace')
                for trozo in re.findall(r'<投資物品[^>]*>', txt):
                    mid = re.search(r'編號="(\d+)"', trozo)
                    mcr = re.search(r'功勳="(\d+)"', trozo)
                    if mid and mcr:
                        _INVERSION[int(mid.group(1))] = int(mcr.group(1))
    return _INVERSION.get(int(item_id), 0)



# Los vales de experiencia, categoria 經驗卷. Son 188 en el cliente y cada
# uno dice a quien va y cuanto da, asi que no hace falta ninguna lista a
# mano: 動態資料1 es el destino y 動態資料2 la cantidad.
#
#   1  experiencia del personaje     "EXP Voucher"
#   2  experiencia de habilidad      "Skill Bonus Voucher"
#   3  honor / merito                "Honor Bonus Voucher"
#   4  experiencia de MASCOTA        "Pet Bonus Voucher"
#
# Medido con el 28939, que el juego describe como "increase the current
# pet's exp by 100,000,000" y que en la tabla es destino 4 con 100000000.
CAT_VALE = '\u7d93\u9a57\u5377'
VALE_PERSONAJE = 1
VALE_HABILIDAD = 2
VALE_HONOR = 3
VALE_MASCOTA = 4

_VALES = {}


def vale_de_exp(item_id: int):
    """(destino, cantidad) si el item es un vale de experiencia, o None."""
    item_id = int(item_id)
    if item_id in _VALES:
        return _VALES[item_id]
    r = None
    try:
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            fila = fila_item(sqlite3.connect(db),
                             '"物品類別", "動態資料1", "動態資料2"', item_id)
            if fila and str(fila[0] or '') == CAT_VALE:
                d1 = str(fila[1] or '')
                d2 = str(fila[2] or '')
                if d1.isdigit() and d2.lstrip('-').isdigit():
                    r = (int(d1), int(d2))
    except Exception:
        pass
    _VALES[item_id] = r
    return r


# Los consumibles que se usan SOBRE LA MASCOTA. El item lo dice el mismo, en
# 使用目標="目標寵物", asi que no hace falta ninguna lista:
#
#   3376  Pet Feed                 動態資料1=500   saciedad que da
#   3460  Pet's Double EXP Card    常駐法術=1866   buff de 1800 s y +100% exp
#
# Se devuelve lo que haga falta para aplicarlo sin volver a mirar la base.
OBJETIVO_MASCOTA = '\u76ee\u6a19\u5bf5\u7269'


def uso_en_mascota(item_id: int):
    """{'saciedad': N}, {'exp': N} o {'buff': id, 'segundos': N, 'exp_pct': N}, o None."""
    if es_certificado_sangre(item_id):
        return None
    try:
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if not db.exists():
            return None
        con = sqlite3.connect(db)
        fila = fila_item(con, '"使用目標", "動態資料1", "常駐法術", "基本名稱"', item_id)
        if not fila or str(fila[0] or '') != OBJETIVO_MASCOTA:
            return None
        hechizo = str(fila[2] or '')
        if hechizo.isdigit() and int(hechizo):
            r = con.execute('select 持續時間,經驗加倍 from magic where id=?',
                            (hechizo,)).fetchone()
            seg = int(r[0]) if r and str(r[0] or '').lstrip('-').isdigit() else 0
            pct = int(r[1]) if r and str(r[1] or '').lstrip('-').isdigit() else 0
            if int(hechizo) == 3796:
                return {'saciedad': 500}
            return {'buff': int(hechizo), 'segundos': max(0, seg), 'exp_pct': max(0, pct)}
        d1 = str(fila[1] or '')
        nom = str(fila[3] or '').lower()
        if d1.isdigit() and int(d1):
            val_d1 = int(d1)
            if 'exp' in nom or 'diamond' in nom or 'stone' in nom or val_d1 > 1000:
                return {'exp': val_d1}
            return {'saciedad': val_d1}
    except Exception:
        pass
    return None


# Los multiplicadores de experiencia y botin. Cada carta lleva un 常駐法術 y
# es el HECHIZO el que dice a que afecta y cuanto:
#
#   經驗加倍        experiencia del personaje
#   技能經驗加倍     experiencia de habilidad
#   掉寶加倍        botin
#
# El porcentaje es lo que SUMA: 100 es el doble y 400 es x5, que es el tope
# que existe. Y a quien va lo dice el ITEM en 使用目標: si pone 目標寵物 es
# para la mascota, y si no, para el personaje. Por eso el 3460 dobla la
# experiencia de la mascota y el 190 y el 2017 -- que usan el mismo tipo de
# hechizo, el 1830 -- doblan la del personaje.
BONO_EXP = 'exp'
BONO_SKILL = 'skill'
BONO_BOTIN = 'botin'

_BONOS = {}


def bonificador(item_id: int):
    """{'a': 'personaje'|'mascota', 'tipo': ..., 'pct': N, 'segundos': N}."""
    item_id = int(item_id)
    if item_id in _BONOS:
        return _BONOS[item_id]
    r = None
    try:
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            con = sqlite3.connect(db)
            fila = fila_item(con, '"使用目標", "常駐法術"', item_id)
            hechizo = str((fila or [None, None])[1] or '')
            if hechizo.isdigit() and int(hechizo):
                m = con.execute('select 持續時間,經驗加倍,技能經驗加倍,掉寶加倍 '
                                'from magic where id=?', (hechizo,)).fetchone()
                if m:
                    def _n(x):
                        return int(x) if str(x or '').isdigit() else 0
                    for col, tipo in ((1, BONO_EXP), (2, BONO_SKILL),
                                      (3, BONO_BOTIN)):
                        if _n(m[col]) > 0:
                            r = {'a': ('mascota'
                                       if str(fila[0] or '') == OBJETIVO_MASCOTA
                                       else 'personaje'),
                                 'tipo': tipo, 'pct': _n(m[col]),
                                 'segundos': _n(m[0]), 'hechizo': int(hechizo)}
                            break
    except Exception:
        pass
    _BONOS[item_id] = r
    return r


# LOS HUECOS Y SUS GEMAS, dentro de la misma entrada del inventario.
#
# Medido el 29/09/2026 perforando tres veces la misma pieza y comparando la
# entrada byte a byte. Solo cambiaron estos:
#
#   offset 82           el NUMERO DE HUECOS: fue 1 -> 2 -> 3
#   offsets 62, 66, 70  la gema de cada hueco, con el id del item
#
# Las gemas que salieron fueron 3113 Sapphire, 3118 Purple Gem y 3093 Ruby,
# las tres de categoria 寶石. Y las cuentas cuadran solas: 62 + 5 huecos de
# 4 bytes = 82, que es justo donde empieza el contador. O sea CINCO huecos,
# ni uno mas.
#
# EL ID VA EN U32, NO EN U16. Esto se escribia con u16 porque las tres gemas
# de aquella medida son de id bajo y con ellas los dos tamanios dan el mismo
# byte a byte. Pero el hueco mide CUATRO bytes -- lo prueba el paso de 62 a
# 66 a 70 y que 62 + 5*4 caiga justo en el contador -- y las gemas modernas
# no caben en dos:
#
#     Purple Spar Rune = 66354.  66354 & 0xFFFF = 818, que es un item oculto
#     que se llama literalmente "530 Quest Item".
#
# Y eso es lo que salia en el arma: cinco renglones de "530 Quest Item" en
# vez de la runa. El id guardado en la cuenta SIEMPRE fue el bueno (66354),
# solo se rompia al meterlo en el paquete, asi que el bono de la gema si se
# aplicaba. Era un fallo de lo que VE el jugador, no de lo que tiene.
#
# Escribir los cuatro bytes es ademas mas seguro que escribir dos: antes los
# dos de arriba se quedaban con lo que hubiera en la plantilla.
#
# Sin esto el cliente no dibujaba ningun sitio donde meter la gema, asi que
# el mortero de perforar abria el primer hueco, pedia una gema para seguir,
# y no habia forma de ponerla: la pieza se quedaba atascada.
OFF_GEMAS = 62
TAM_GEMA = 4
OFF_HUECOS = 82
MAX_HUECOS_ENTRADA = 5


def marcar_huecos(entrada: bytes, huecos: int, gemas=None) -> bytes:
    """Escribe en la entrada cuantos huecos tiene y que gema lleva cada uno."""
    base = 6 if entrada[:2] == struct.pack('<H', 0x001B) else 0
    if len(entrada) < base + OFF_HUECOS + 1:
        return entrada
    b = bytearray(entrada)
    n = max(0, min(MAX_HUECOS_ENTRADA, int(huecos or 0)))
    b[base + OFF_HUECOS] = n
    for i in range(MAX_HUECOS_ENTRADA):
        o = base + OFF_GEMAS + i * TAM_GEMA
        if o + TAM_GEMA > len(b):
            break
        g = (gemas or [])[i] if i < len(gemas or []) else 0
        struct.pack_into('<I', b, o, int(g or 0) & 0xFFFFFFFF)
    return bytes(b)


def leer_huecos(entrada: bytes):
    """(cuantos huecos, [gema de cada uno])."""
    base = 6 if entrada[:2] == struct.pack('<H', 0x001B) else 0
    if len(entrada) < base + OFF_HUECOS + 1:
        return (0, [])
    n = entrada[base + OFF_HUECOS]
    gemas = []
    for i in range(min(n, MAX_HUECOS_ENTRADA)):
        o = base + OFF_GEMAS + i * TAM_GEMA
        if o + TAM_GEMA > len(entrada):
            break
        gemas.append(struct.unpack_from('<I', entrada, o)[0])
    return (n, gemas)


# EL BONO DE LAS GEMAS. La gema lleva los NUMEROS en sus propias columnas y
# jeweleffect.xml dice QUE STAT da segun donde se engarce. El Broken Purple
# Lunar Rune (54573) lo enseña en su descripcion: en un arma da 1320 de
# ataque magico y en armadura o escudo 260 de defensa magica; en su fila de
# jeweleffect pone 魔攻 para el arma y 魔防 para todo lo demas, y en el item
# estan matk=1320 y mdef=260.
GEMAS = pathlib.Path(__file__).parent / 'plantillas' / 'gemas.json'

_GEM = {}
_GEM_VAL = {}


def _tabla_gemas():
    if _GEM:
        return _GEM
    try:
        _GEM.update(json.loads(GEMAS.read_text(encoding='utf-8')))
    except Exception:
        pass
    return _GEM


def _valores_gema(item_id: int) -> dict:
    """Los numeros que lleva la propia gema, de item.xml."""
    item_id = int(item_id)
    if item_id in _GEM_VAL:
        return _GEM_VAL[item_id]
    d = {}
    try:
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if db.exists():
            fila = fila_item(sqlite3.connect(db),
                             '"動態資料1", "atk_avg", "def", "matk", "mdef", '
                             '"hp", "mp", "accuracy", "agility"', item_id)
            if fila:
                nombres = ('efecto', 'atk', 'dfs', 'matk', 'mdef', 'hp', 'mp',
                           'rigor', 'agilidad')
                for k, v in zip(nombres, fila):
                    if str(v or '').isdigit():
                        d[k] = int(v)
    except Exception:
        pass
    _GEM_VAL[item_id] = d
    return d


# Las categorias de escudo. Todo lo demas que se lleve en la mano es un
# arma, aunque vaya en la ranura izquierda.
CATEGORIAS_ESCUDO = ('盾',)


def bono_gema(item_id: int, ranura: int, pieza: int = 0) -> dict:
    """{stat: valor} que aporta esa gema puesta en esa pieza.

    `pieza` es el item que lleva la gema. Hace falta porque la ranura sola
    no basta: la 4 es la mano izquierda, y ahi puede ir un ESCUDO o, con
    armas duales, otra ESPADA. Mirando solo la ranura, la misma runa daba
    1650 de ataque en la derecha y 630 de defensa en la izquierda, asi que
    con duales la mano izquierda perdia todo el ataque de sus gemas.
    """
    val = _valores_gema(item_id)
    efecto = val.get('efecto')
    if not efecto:
        return {}
    fila = _tabla_gemas().get(str(efecto))
    if not fila:
        return {}
    r = int(ranura)
    if r == RANURA_IZQUIERDA and pieza:
        # Decide la PIEZA, no la ranura: una espada en la izquierda cuenta
        # como arma.
        es_escudo = (categoria_item(pieza) or '') in CATEGORIAS_ESCUDO
        cuales = fila.get('escudo' if es_escudo else 'arma') or []
    elif r == RANURA_DERECHA:
        cuales = fila.get('arma') or []
    elif r == RANURA_IZQUIERDA:
        cuales = fila.get('escudo') or []
    else:
        equipo = fila.get('equipo') or {}
        cuales = equipo.get(str(r)) or equipo.get('2') or []
    out = {}
    for stat in cuales:
        v = val.get(stat)
        if v:
            out[stat] = out.get(stat, 0) + v
    return out


def sp_de_item(item_id: int) -> int:
    """Cuanto SP recupera ese objeto, o 0.

    El objeto no lleva el numero: lleva un 常駐法術 y es el HECHIZO el que
    trae la columna SP. El SP Power Scroll (3696) apunta al 1871, que tiene
    SP=2000 -- las "2 SP lamps" de su descripcion, porque una lampara son
    1000 puntos.
    """
    try:
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        if not db.exists():
            return 0
        con = sqlite3.connect(db)
        fila = fila_item(con, '"常駐法術"', item_id)
        h = str((fila or [None])[0] or '')
        if not h.isdigit() or not int(h):
            return 0
        r = con.execute('select SP from magic where id=?', (h,)).fetchone()
        return int(r[0]) if r and str(r[0] or '').isdigit() else 0
    except Exception:
        return 0
