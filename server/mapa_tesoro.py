"""Mapa del tesoro: las piezas "Lvl N Robber Lord Map Piece" y la pestana
TreMap del Quest Log.

Sacado de Angel.exe (REA, 11/11/2026):
- 0x012A (s2c; manejador 0x609600, en el indice 0x1A5 de la tabla, que es
  opcode + 0x7B: el del album 0x0156 esta en 0x1D1) copia el paquete (23
  bytes con el opcode) en el personaje (+0x488 el normal, +0x49F el
  especial) y repinta la ventana (0x609680). Confirmado en logs/proxy:
      [u16 0x012A][u32 tipo 0 normal | 1 especial][u32 mapa (0 = sin
      terminar)][u32 escenario][u32 piezas 0..10][u32 punto][u8 semilla]
  Con mapa 0 enseña "Unfinished treasure map." (722) y "N/10"; con mapa, el
  nombre de treasuremap.xml, "(escenario)" y la marca del punto.
- Textos del cliente: 718 "You have used a map piece.", 719
  "Congratulations. The treasure map is finished.", 720 "Unable to use more
  map pieces because the treasure map is finished.".

Lo que NO esta en el cliente y se decide aqui (sin capturas del oficial):
- el mapa sale al azar entre los TIPOS de tesoro de su nivel
  (TESOROS_POR_NIVEL, de la guia de la wiki "Treasure Maps": niveles 1..7;
  "Buried Place of Loot" es "Location of the Buried Swags" en el cliente).
  Los niveles 8..10 no estan en la guia: siguen la progresion de la tabla
  (SUPUESTO). Solo filas con escenario y un punto que sea TAG;
- vale cualquier nivel de pieza; el mapa es del nivel mas alto usado;
- al llegar a una casilla del TAG del punto en su escenario aparece el
  cofre (solo para el); al pulsarlo da la tabla de drop del mapa (掉寶資料)
  y el mapa se vacia.
"""
import random
import sqlite3
import struct
import pathlib

import tesoros

OPCODE = 0x012A
PIEZAS = {3081 + i: i + 1 for i in range(10)}      # item -> nivel
PIEZAS_POR_MAPA = 10
MSG_USADA, MSG_TERMINADO, MSG_YA_TERMINADO = 718, 719, 720
RADIO_TESORO = 1
TESOROS_POR_NIVEL = {
    1: ('Dusty Wooden Box', "Robber's Secret"),
    2: ('Dusty Wooden Box', "Robber's Secret", 'Trace-indicating Mark', 'Common Mound'),
    3: ("Robber's Secret", 'Trace-indicating Mark', 'Common Mound', 'Suspected Gravel Piles', "Collector's Cellar"),
    4: ('Common Mound', 'Suspected Gravel Piles', "Collector's Cellar", 'Location of the Buried Swags', 'Location of the Tumulus'),
    5: ("Collector's Cellar", 'Location of the Buried Swags', 'Location of the Tumulus', "The Antiquary's Collections", 'Old Luxurious Chest'),
    6: ("Collector's Cellar", 'Old Luxurious Chest', 'Legendary Jewel Box'),
    7: ('Legendary Jewel Box', 'Location of the Tumulus'),
    8: ('Delicate Antique Box', 'Legendary Jewel Box', "Merchant's Legacy"),
    9: ("Merchant's Legacy", 'Downfallen Warehouse', 'Downfallen Treasure'),
    10: ('Downfallen Treasure', "Ancient Magnate's Treasures", "Robber Lord's Fine Box"),
}


def estado(p):
    """El mapa normal del personaje (dict persistente en p.tesoro)."""
    t = getattr(p, 'tesoro', None)
    if not isinstance(t, dict):
        t = {}
    return {'mapa': int(t.get('mapa') or 0), 'escena': int(t.get('escena') or 0),
            'piezas': int(t.get('piezas') or 0), 'punto': int(t.get('punto') or 0),
            'semilla': int(t.get('semilla') or 0) & 0xFF, 'nivel': int(t.get('nivel') or 0)}


def paquete(t, tipo=0):
    # Como el oficial (logs/proxy: 0x012A de 21 bytes, p. ej. piezas=1 y
    # semilla 0x68): el manejador recibe el paquete CON el opcode.
    return struct.pack('<HIIIIIB', OPCODE, tipo, t['mapa'], t['escena'], t['piezas'],
                       t['punto'], t['semilla'])


def _aviso(msg_id, texto=''):
    import clases
    return clases.aviso(texto, tipo=0, msg_id=msg_id)


def _sortear_mapa(nivel, azar):
    """(mapa, escenario, punto) al azar entre los del nivel, con un punto
    que sea TAG del escenario."""
    import eventos
    cands = []
    nombres = TESOROS_POR_NIVEL.get(int(nivel), ())
    for m in tesoros.tabla():
        if m.get('nombre') not in nombres:
            continue
        for st in m.get('escenas') or ():
            tags = (eventos.del_stage(st) or {}).get('tags') or {}
            for pt in m.get('puntos') or ():
                if tags.get(str(pt)):
                    cands.append((int(m['id']), int(st), int(pt)))
    if not cands:
        return None
    # Primero el TIPO (uniforme) y luego su escenario y punto: si no, los
    # tipos con mas escenarios salian mucho mas.
    tipos = sorted({tesoros.de_id(c[0])['nombre'] for c in cands})
    tipo = tipos[azar.randint(0, len(tipos) - 1)]
    cands = [c for c in cands if tesoros.de_id(c[0])['nombre'] == tipo]
    return cands[azar.randint(0, len(cands) - 1)]


def usar_pieza(ses, ranura):
    """0x002E sobre una pieza. True si era una pieza (la haya usado o no)."""
    import recent_mall
    item = int((ses.inventario or {}).get(ranura) or 0)
    nivel = PIEZAS.get(item)
    if not nivel:
        return False
    p = ses.personaje
    t = estado(p)
    if t['mapa']:
        ses.enviar(_aviso(MSG_YA_TERMINADO))
        return True
    # Se aceptan piezas de cualquier nivel (sin el boton Delete, exigir el
    # mismo dejaba el mapa atascado): el mapa es del nivel mas alto usado.
    nuevo = dict(t, nivel=max(nivel, t['nivel'] if t['piezas'] else 0), piezas=t['piezas'] + 1)
    nivel = nuevo['nivel']
    if not t['piezas']:
        nuevo['semilla'] = random.randint(0, 255)
    terminado = nuevo['piezas'] >= PIEZAS_POR_MAPA
    if terminado:
        sorteo = _sortear_mapa(nivel, random)
        if sorteo:
            nuevo['mapa'], nuevo['escena'], nuevo['punto'] = sorteo
        else:
            terminado = False
            nuevo['piezas'] = PIEZAS_POR_MAPA - 1
    try:
        recent_mall.cambiar(ses, {ranura: 1}, [],
                            transaccion=lambda con, data: data.__setitem__('tesoro', nuevo))
    except Exception as e:
        import clases
        ses.enviar(clases.aviso(str(e) or 'The map piece could not be used.', tipo=0))
        return True
    p.tesoro = nuevo
    ses.enviar(_aviso(MSG_USADA), paquete(nuevo))
    if terminado:
        ses.enviar(_aviso(MSG_TERMINADO))
    return True


def _tirar_drop(drop_id, azar):
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    con = sqlite3.connect(db)
    try:
        cols = [c[1] for c in con.execute('pragma table_info(drop_table)')]
        r = con.execute('select * from drop_table where id=?', (str(drop_id),)).fetchone()
    finally:
        con.close()
    if not r:
        return []
    d = dict(zip(cols, r))

    def n(k, x=0):
        try:
            return int(float(d.get(k) or x))
        except (TypeError, ValueError):
            return x
    factor = max(1, n('factor', 100))
    filas = [(n('item%d' % i), max(1, n('count%d' % i, 1)), n('prob%d' % i))
             for i in range(1, 21) if n('item%d' % i) > 0]
    out = []
    for _ in range(max(1, n('count', 1))):
        x = azar.randint(1, factor)
        for it, cnt, pr in filas:
            x -= pr
            if x <= 0:
                out.append((it, cnt))
                break
    return out


# EL COFRE. Al llegar al punto aparece un cofre (寶箱圖形 de treasuremap.xml)
# que solo ve el dueno del mapa; al pulsarlo da el premio y se va (lo conto
# el usuario, jugado en el oficial). Es un objeto de mapa (0x000E) armado
# como los de las plantillas: entidad +0, pixel x/y +8/+12, sprite +34.
SPRITE_COFRE = 60153
_PLANTILLA_COFRE = bytes.fromhex(
    '40710404000000004b270000701300000000000027000000000000001a000000dc067aeb00000000000000')
_SIG_COFRE = [96_500_000]


def paquete_cofre(eid, tile, sprite):
    b = bytearray(_PLANTILLA_COFRE)
    struct.pack_into('<I', b, 0, eid)
    struct.pack_into('<II', b, 8, tile[0] * 32 + 16, tile[1] * 32 + 16)
    struct.pack_into('<H', b, 34, sprite)
    return struct.pack('<H', 0x000E) + bytes(b)


def al_llegar(ses):
    """Tras andar: en el punto del mapa terminado aparece su cofre."""
    import eventos
    p = ses.personaje
    t = estado(p) if p else None
    if not t or not t['mapa'] or p.stage != t['escena'] or getattr(ses, '_cofre_tesoro', None):
        return
    casillas = ((eventos.del_stage(t['escena']) or {}).get('tags') or {}).get(str(t['punto'])) or []
    cerca = [c for c in casillas if max(abs(p.tile_x - c[0]), abs(p.tile_y - c[1])) <= RADIO_TESORO]
    if not cerca:
        return
    m = tesoros.de_id(t['mapa']) or {}
    _SIG_COFRE[0] += 1
    eid = _SIG_COFRE[0]
    ses._cofre_tesoro = (eid, p.stage)
    import clases
    ses.enviar(paquete_cofre(eid, tuple(cerca[0]), int(m.get('sprite_cofre') or SPRITE_COFRE)),
               clases.aviso('You found %s! Open it.' % (m.get('nombre') or 'the treasure'), tipo=0))


def pulsar(ses, ent):
    """Clic sobre el cofre: el premio, fuera el cofre y el mapa vacio."""
    import recent_mall
    import combate
    cofre = getattr(ses, '_cofre_tesoro', None)
    p = ses.personaje
    if not cofre or int(ent) != cofre[0] or not p:
        return False
    t = estado(p)
    if not t['mapa'] or p.stage != cofre[1]:
        ses._cofre_tesoro = None
        return True
    m = tesoros.de_id(t['mapa']) or {}
    premios = _tirar_drop(m.get('drop'), random)
    vacio = {'mapa': 0, 'escena': 0, 'piezas': 0, 'punto': 0, 'semilla': 0, 'nivel': 0}
    try:
        recent_mall.cambiar(ses, {}, premios,
                            transaccion=lambda con, data: data.__setitem__('tesoro', vacio))
    except Exception as e:
        import clases
        ses.enviar(clases.aviso(str(e) or 'Your backpack is full.', tipo=0))
        return True
    p.tesoro = vacio
    ses._cofre_tesoro = None
    import clases
    ses.enviar(combate.despawn_monstruo(cofre[0]),
               clases.aviso('You opened %s!' % (m.get('nombre') or 'the treasure'), tipo=0),
               paquete(vacio))
    return True


def borrar(ses, cuerpo):
    """c2s 0x012A [u32 tipo]: el boton Delete de la pestana TreMap (visto en
    el log al pulsarlo). Vacia el mapa normal (tipo 0), lo guarda y avisa con
    el texto 721. El especial (tipo 1) no se lleva en el servidor."""
    import recent_mall
    import clases
    tipo = int.from_bytes(bytes(cuerpo or b'')[:4].ljust(4, bytes(1)), 'little')
    if tipo != 0 or not getattr(ses, 'personaje', None):
        return
    vacio = {'mapa': 0, 'escena': 0, 'piezas': 0, 'punto': 0, 'semilla': 0, 'nivel': 0}
    try:
        recent_mall.cambiar(ses, {}, [], transaccion=lambda con, data: data.__setitem__('tesoro', vacio))
    except Exception as e:
        ses.enviar(clases.aviso(str(e) or 'The treasure map could not be deleted.', tipo=0))
        return
    ses.personaje.tesoro = vacio
    ses._cofre_tesoro = None
    ses.enviar(paquete(vacio), _aviso(721))


def al_entrar(ses):
    """El estado del mapa al cargar el mapa (la ventana lo lee del personaje).
    El cofre de antes se queda en el otro mapa: hay que volver al punto."""
    ses._cofre_tesoro = None
    if getattr(ses, 'personaje', None):
        ses.enviar(paquete(estado(ses.personaje)))
