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


def stats(bolsa=None) -> bytes:
    """Sub-mensaje 0x0042 con los stats ya recalculados segun el equipo.

    El array que empieza en +20 alterna valor base y valor efectivo:

        idx 0  ataque base      idx 1  R.Atk     idx 2  L.Atk
        idx 3  defensa base     idx 4  Dfs

    El efectivo es el base mas lo que suma cada pieza puesta. Verificado
    contra la sesion capturada: la defensa pasa de 12 a 28 al ponerse la
    prenda (+10), los guantes (+3) y los zapatos (+3), y cada Sabre sube su
    mano en 27. Los tres saltos aparecen en el trafico uno a uno.

    bolsa: {ranura: item_id}. Sin ella se devuelve la plantilla tal cual.
    """
    p = _plantillas()
    b = bytearray(bytes.fromhex(p['stats_sin_ropa']))
    if bolsa is None:
        return struct.pack('<H', 0x0042) + bytes(b)
    base_atk = struct.unpack_from('<I', b, 20)[0]
    base_def = struct.unpack_from('<I', b, 20 + 12)[0]
    suma_def = 0
    mano = {RANURA_DERECHA: 0, RANURA_IZQUIERDA: 0}
    for ranura, item_id in bolsa.items():
        if not es_equipo(ranura) or ranura == RANURA_ORO:
            continue
        x = _bonus(item_id)
        suma_def += x['def']
        if ranura in mano:
            mano[ranura] = x['atk'] + x['accuracy']
    struct.pack_into('<I', b, 20 + 4, base_atk + mano[RANURA_DERECHA])
    struct.pack_into('<I', b, 20 + 8, base_atk + mano[RANURA_IZQUIERDA])
    struct.pack_into('<I', b, 20 + 16, base_def + suma_def)
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
                    f'select id,"耐久",{campos} from item '
                    "where id glob '[0-9]*'"):
                try:
                    d = int(fila[1]) if fila[1] else 0
                except ValueError:
                    d = 0
                _CAT[int(fila[0])] = (any(fila[2:]), d)
    return _CAT


def es_equipable(item_id: int) -> bool:
    """Si el item se lleva puesto. Decide el tamano de su entrada: 119 o 86."""
    return _tabla().get(item_id, (False, 0))[0]


def durabilidad(item_id: int) -> int:
    """Durabilidad maxima ("Hardiness" en el cliente). 0 = no la gasta.

    Va en el offset +45 de la entrada. Se encontro comparando dos entradas
    equipables de la misma captura: el Cask (584), que en item.xml tiene 耐久
    180, lleva 180 justo ahi, y el Sabre (10), que no tiene esa columna,
    lleva 0. Es el unico byte en que las dos entradas difieren.
    """
    base = _tabla().get(item_id, (False, 0))[1]
    if not base:
        return 0
    # Con AO_DURABILIDAD se puede subir (o bajar) la de todo lo que entrega
    # el servidor. Es una palanca de este servidor, no algo del juego: con 10
    # las armas del kit salen con 300 en vez de 30 y tardan diez veces mas en
    # romperse. Hoy no cambia nada porque nada gasta durabilidad todavia.
    import os
    try:
        factor = float(os.environ.get('AO_DURABILIDAD', '1'))
    except ValueError:
        factor = 1.0
    return max(0, min(int(base * factor), 0xFFFFFFFF))


def completo(char_id: int, items) -> bytes:
    """Sub-mensaje 0x001A con todo el inventario.

    items: iterable de (ranura, item_id) o (ranura, item_id, cantidad).
    """
    p = _plantilla_inicial()
    normal = bytes.fromhex(p['normal'])
    equip = bytes.fromhex(p['equipable'])
    lista = []
    for it in sorted(items):
        ranura, item_id = it[0], it[1]
        cant = it[2] if len(it) > 2 else 1
        e = bytearray(equip if es_equipable(item_id) else normal)
        e[1:9] = instancia_de(char_id, item_id)
        struct.pack_into('<I', e, 9, item_id)
        struct.pack_into('<I', e, 34, char_id)
        struct.pack_into('<H', e, 38, ranura)
        struct.pack_into('<I', e, 40, cant)
        struct.pack_into('<I', e, OFF_DURABILIDAD, durabilidad(item_id))
        lista.append(bytes(e))
    fuera = struct.pack('<I', len(lista)) + b''.join(lista)
    return struct.pack('<H', 0x001A) + fuera


# ------------------------------------------------- entrega de un item
# Para REGALAR un item no sirve el 0x001A: el cliente solo lo lee al entrar al
# mundo, asi que los items aparecian en el chat ("Obtain Students' Gloves")
# pero el panel seguia vacio hasta salir y volver a entrar. Lo que refresca en
# caliente son DOS mensajes 0x001B, uno por contenedor:
#
#     contenedor 1  123 bytes
#     contenedor 2  131 bytes
#
# En los dos: +4 marca 01, +5 instancia de 8 bytes, +13 item_id LE32,
# +38 char_id LE32, +42 ranura LE16, +49 durabilidad LE32.
PLANTILLA_ENTREGA = pathlib.Path(__file__).parent / 'plantillas' / 'entrega_item.json'
_PE = None


def _plantilla_entrega():
    global _PE
    if _PE is None:
        _PE = json.loads(PLANTILLA_ENTREGA.read_text(encoding='utf-8'))
    return _PE


def entregar(char_id: int, item_id: int, ranura: int):
    """Los dos sub-mensajes 0x001B que meten un item en el inventario."""
    p = _plantilla_entrega()
    salida = []
    for clave in ('cont1', 'cont2'):
        b = bytearray(bytes.fromhex(p[clave]))
        b[5:13] = instancia_de(char_id, item_id)
        struct.pack_into('<I', b, 13, item_id)
        struct.pack_into('<I', b, 38, char_id)
        struct.pack_into('<H', b, 42, ranura)
        struct.pack_into('<I', b, 49, durabilidad(item_id))
        salida.append(struct.pack('<H', 0x001B) + bytes(b))
    return salida
