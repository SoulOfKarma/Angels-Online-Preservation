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
import struct
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
                for iid, w in con.execute('select id, weight from item'):
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


def vaciar_ranura(dueno: int, ranura: int) -> bytes:
    """0x001B que deja una casilla vacia.

    Medido al destruir un monton de pociones:
        01000000 | 02 | 01 | 1e010000 | 2900
    es decir [u32 n=1][u8 02 = vaciar][u8 01][u32 dueno][u16 ranura].
    """
    return struct.pack('<HIBBIH', 0x001B, 1, 2, 1, dueno, ranura)


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
    return None


def es_equipo(ranura: int) -> bool:
    """Si esa ranura es del personaje (equipo) y no de la mochila."""
    return ranura < PRIMERA_RANURA_BOLSA


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
            for i, d, ac, ag, av in con.execute(
                    'select id, def, accuracy, agility, atk_avg from item '
                    "where id glob '[0-9]*'"):
                # Algunos valores vienen con decimales en item.xml.
                def _n(x):
                    try:
                        return int(float(x))
                    except (TypeError, ValueError):
                        return 0
                _BON[int(i)] = {'def': _n(d), 'accuracy': _n(ac),
                                'agility': _n(ag), 'atk': _n(av)}
    return _BON.get(item_id, {'def': 0, 'accuracy': 0, 'agility': 0, 'atk': 0})


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


def vida_maxima(hp_max, habilidades):
    """El tope de vida de verdad: el guardado mas lo que dan las pasivas."""
    return int(hp_max or 0) + bonos_de_habilidades(habilidades)['hp']


def mana_maximo(mp_max, habilidades):
    """El tope de mana de verdad."""
    return int(mp_max or 0) + bonos_de_habilidades(habilidades)['mp']



def stats(bolsa=None, habilidades: list = None,
          hp: int = None, hp_max: int = None,
          mp: int = None, mp_max: int = None,
          oro: int = None,
          buffs: dict = None,
          sp: int = None, sp_max: int = None) -> bytes:
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
    sp_max_bars = _b['barras_sp']
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
        sp_max_bars = max(sp_max_bars, sp_max)
    if sp is not None:
        sp_bars_current = min(sp_max_bars, max(0, sp // 1000))
    else:
        sp_bars_current = sp_max_bars

    if buffs:
        now = time.time()
        for b_id, b_data in buffs.items():
            if isinstance(b_data, dict) and b_data.get('fin', 0) > now and 'crit' in b_data:
                crit_eff += b_data['crit']

    eq_def = 0
    eq_r_atk = 0
    eq_l_atk = 0
    eq_rigor = 0
    eq_agi = 0
    eq_load = 0

    if bolsa:
        for ranura, item_id in bolsa.items():
            if not es_equipo(ranura) or ranura == RANURA_ORO:
                continue
            x = _bonus(item_id)
            eq_def += x.get('def', 0)
            eq_rigor += x.get('accuracy', 0)
            eq_agi += x.get('agility', 0)
            if ranura == RANURA_DERECHA:
                eq_r_atk += x.get('atk', 0) + x.get('accuracy', 0)
            elif ranura == RANURA_IZQUIERDA:
                eq_l_atk += x.get('atk', 0) + x.get('accuracy', 0)

    r_atk_eff = c_atk_base + eq_r_atk
    l_atk_eff = c_atk_base + eq_l_atk
    dfs_eff = c_def_base + eq_def
    rigor_eff = c_rigor_base + eq_rigor
    agi_eff = c_agi_base + eq_agi

    hp_eff = hp if hp is not None else struct.unpack_from('<I', b, 0)[0]
    hp_max_eff = (hp_max + hp_bonus) if hp_max is not None else (struct.unpack_from('<I', b, 4)[0] + hp_bonus)
    mp_eff = mp if mp is not None else struct.unpack_from('<I', b, 8)[0]
    mp_max_eff = (mp_max + mp_bonus) if mp_max is not None else (struct.unpack_from('<I', b, 12)[0] + mp_bonus)

    struct.pack_into('<I', b, 0, hp_eff)
    struct.pack_into('<I', b, 4, hp_max_eff)
    struct.pack_into('<I', b, 8, mp_eff)
    struct.pack_into('<I', b, 12, mp_max_eff)
    struct.pack_into('<HH', b, 16, eq_load, load_max)
    struct.pack_into('<I', b, 20, c_atk_base)
    struct.pack_into('<I', b, 24, r_atk_eff)
    struct.pack_into('<I', b, 28, l_atk_eff)
    struct.pack_into('<I', b, 32, c_def_base)
    struct.pack_into('<I', b, 36, dfs_eff)
    struct.pack_into('<I', b, 40, c_matk_base)
    struct.pack_into('<I', b, 44, c_matk_base)
    struct.pack_into('<I', b, 48, c_mdef_base)
    struct.pack_into('<I', b, 52, c_mdef_base)
    struct.pack_into('<HH', b, 56, c_rigor_base, rigor_eff)
    struct.pack_into('<HH', b, 60, c_agi_base, agi_eff)
    struct.pack_into('<HH', b, 64, base_crit, crit_eff)
    struct.pack_into('<HH', b, 68, sp_bars_current, sp_max_bars)
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
            for fila in con.execute(
                    f'select id,"耐久","物品類別",{campos} from item '
                    "where id glob '[0-9]*'"):
                try:
                    d = int(fila[1]) if fila[1] else 0
                except ValueError:
                    d = 0
                es_eq = any(v == '是' for v in fila[3:]) or (fila[2] == '寵物')
                _CAT[int(fila[0])] = (es_eq, d)
    return _CAT


def es_equipable(item_id: int) -> bool:
    """Si el item va en alguna de las casillas de equipo (0..9). Las mascotas van en ranura 9."""
    if es_mascota(item_id):
        return True
    return _tabla().get(item_id, (False, 0))[0]


def es_apilable(item_id: int) -> bool:
    """Si el item se puede acumular en una misma casilla (pociones, hojas, galletas, materiales)."""
    if not item_id or es_equipable(item_id):
        return False
    return True


def es_mascota(item_id: int) -> bool:
    """Si el item es una mascota o huevo de mascota."""
    if item_id in (3396, 3397, 3398, 3399):
        return True
    return ranura_equipo_de(item_id) == 9


_SLOT_CACHE = None
_PET_SPRITE_CACHE = {}

def ranura_equipo_de(item_id: int):
    """Devuelve la ranura de equipamiento donde se coloca el item, o None si no es equipable."""
    global _SLOT_CACHE
    if _SLOT_CACHE is None:
        import sqlite3
        db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
        _SLOT_CACHE = {}
        if db.exists():
            con = sqlite3.connect(db)
            campos = ','.join(f'"{c}"' for c in COLUMNAS_EQUIPO)
            for fila in con.execute(
                    f'select id,"物品類別",{campos} from item '
                    "where id glob '[0-9]*'"):
                iid = int(fila[0])
                cat = fila[1]
                rhand, lhand, head, acc, body, hands, feet, back, pet = [v == '是' for v in fila[2:]]
                if cat == '寵物' or pet:
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
    return _SLOT_CACHE.get(item_id)

_TWO_HAND_CACHE = {}

def es_arma_dos_manos(item_id: int) -> bool:
    """Si el arma requiere ambas manos (Lanza, Arco, etc.)."""
    global _TWO_HAND_CACHE
    if not item_id:
        return False
    if item_id in _TWO_HAND_CACHE:
        return _TWO_HAND_CACHE[item_id]
    import sqlite3
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    res = False
    if db.exists():
        try:
            con = sqlite3.connect(db)
            row = con.execute('select "物品類別" from item where id=?', (str(item_id),)).fetchone()
            if row and row[0]:
                cat = str(row[0])
                res = any(k in cat for k in ('槍', '弓', '雙手'))
        except Exception:
            pass
    _TWO_HAND_CACHE[item_id] = res
    return res



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
            row = con.execute('select "動態資料1" from item where id=?', (str(item_id),)).fetchone()
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
        row = con.execute('select "動態資料1", "物品類別", "基本名稱" from item where id=?', (str(item_id),)).fetchone()
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
             inst: bytes = None, dueno: int = None) -> bytes:
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
    if es_mascota(item_id):
        # Formatear datos de mascota para que no crashee el tooltip y no se
        # vea muerta
        nombres_elfos = {3396: b"Water Elf\x00", 3397: b"Fire Elf\x00",
                         3398: b"Wind Elf\x00", 3399: b"Earth Elf\x00"}
        nom_pet = nombres_elfos.get(item_id, b"Pet\x00")
        e[13:13 + len(nom_pet)] = nom_pet
        struct.pack_into('<I', e, OFF_DURABILIDAD, 100)
        struct.pack_into('<I', e, OFF_DURABILIDAD + 4, 100)
        struct.pack_into('<I', e, OFF_DURABILIDAD + 8, 100)
        struct.pack_into('<I', e, OFF_DURABILIDAD + 12, 1)
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
        struct.pack_into('<I', e, 53, dueno if puesta else 0)
        e[57] = 2 if puesta else 3
        e[58] = 1
        # Y el servidor repite ahi los dieciseis bits bajos del numero de
        # instancia.
        struct.pack_into('<I', e, 84,
                         struct.unpack_from('<I', e, 1)[0] & 0xFFFF)
    return bytes(e)


def completo(char_id: int, items, dueno: int = None) -> bytes:
    """Sub-mensaje 0x001A con todo el inventario.

    items: iterable de (ranura, item_id[, cantidad[, instancia]]).
    """
    lista = []
    for it in sorted(items, key=lambda x: int(x[0])):
        lista.append(_entrada(char_id, int(it[0]), int(it[1]),
                              int(it[2]) if len(it) > 2 else 1,
                              it[3] if len(it) > 3 else None, dueno))
    fuera = struct.pack('<I', len(lista)) + b''.join(lista)
    return struct.pack('<H', 0x001A) + fuera


def acuse_movimiento(ranura: int, accion: int = 0x0012) -> bytes:
    """0x0006 s2c: "hecho lo que pediste con esa casilla".

    Medido al equipar: el cliente manda 0x0012 [41][2] y lo primero que le
    llega de vuelta es 0x0006 con 12 00 29 00, o sea el opcode que se
    confirma y la casilla de origen; despues vienen el 0x001B y el 0x0042.
    Sin este acuse el cliente apunta el cambio en el panel de equipo y en
    los stats pero no redibuja al personaje: el equipo queda invisible.
    """
    return struct.pack('<HHH', 0x0006, accion, ranura)


def actualizar_ranuras(char_id: int, entradas, dueno: int = None) -> bytes:
    """0x001B con varias casillas de una vez.

    Es lo que manda el servidor al equipar: en la captura, mover la prenda
    de la casilla 41 al cuerpo devuelve UN 0x001B con dos entradas -- la
    prenda ya en la casilla 2 y la que llevaba puesta de vuelta en la 41 --
    y despues el 0x0042 con los stats. Antes se mandaban dos mensajes de
    movimiento con un formato antiguo que no lleva el estado de puesto.

    entradas: iterable de (ranura, item_id, cantidad, instancia).
    """
    lista = [_entrada(char_id, int(r), int(i), int(c), ins, dueno)
             for r, i, c, ins in entradas]
    return (struct.pack('<HI', 0x001B, len(lista)) + b''.join(lista))


def actualizar_ranura(char_id: int, ranura: int, item_id: int, cant: int,
                      inst: bytes = None, dueno: int = None) -> bytes:
    """0x001B de 90 bytes: como queda UNA casilla.

    Es lo que manda el servidor real despues de comprar, vender, usar o
    separar: una linea por casilla tocada, no el inventario entero. Al
    reenviar el 0x001A completo el cliente se quedaba con lo que ya tenia
    pintado y los items vendidos seguian viendose en la mochila.
    """
    return (struct.pack('<HI', 0x001B, 1)
            + _entrada(char_id, ranura, item_id, cant, inst, dueno))


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
        row = con.execute('select "動態資料1", "常駐法術", "物品類別", "基本名稱", "說明" from item where id=?', (str(item_id),)).fetchone()
        if not row:
            return None
        d1, mid, cat, name, desc = str(row[0] or ''), str(row[1] or ''), str(row[2] or ''), str(row[3] or ''), str(row[4] or '')
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
        # 3. Heuristica si no habia magic row
        if not res and d1.isdigit() and int(d1) > 0:
            val = int(d1)
            if 'mp' in name.lower() or 'magic' in name.lower() or 'blue' in name.lower():
                res['mp'] = val
            else:
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
        r = con.execute('select "物品類別", "基本名稱" from item where id=?', (str(item_id),)).fetchone()
        if r:
            return r[0] == '卡片' or 'Card' in str(r[1] or '')
        return False
    except Exception:
        return False

