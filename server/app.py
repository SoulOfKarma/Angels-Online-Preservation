"""
Servidor Angels Online -- capa de transporte.

Estado: el TRANSPORTE funciona y esta validado contra capturas reales.
La LOGICA DE JUEGO no existe todavia (ver docs/05_SERVIDOR.md).

Uso:
    python server/app.py [--host 127.0.0.1] [--port 16768]
"""
import asyncio
import argparse
import os
import logging
import logging.handlers
import math
import random
import sys
import pathlib
import collections
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'proto'))

from session import Session
from login import Personaje, secuencia
from grabador import Grabador
import cuentas
import login_server
from codec import Msg
import messages  # noqa
import gm
import struct
import transitable as _transitable

log = logging.getLogger('app')

# Angel Raphael. Es el unico NPC tras cuyo dialogo el servidor real manda el
# atributo que habilita la eleccion de clase.
ENTIDAD_MAESTRO_CLASE = 19
MAPA_DEL_TUTORIAL = 51      # los entity_id del tutorial solo valen aqui
# Donde revive quien muere sin checkpoint: el Angel Lyceum, junto a los NPC.
# Medido en Celestia: al elegir "Return to Angel Lyceum" aparece en (173,91).
# Con checkpoint de Cupido el punto cambia y queda al lado de Cupido.
REVIVIR_LYCEUM = (173, 91)


_PORTALES = None


def critico_jugador(ses) -> int:
    """El Critical del personaje (en %), de su hoja de stats."""
    try:
        import struct as _s
        return _s.unpack_from('<H', _stats_ses(ses), 66 + 2)[0]
    except Exception:
        return 5


def defensa_jugador(ses) -> int:
    """El Dfs del personaje, leido de su hoja de stats."""
    try:
        import struct as _s
        return _s.unpack_from('<I', _stats_ses(ses), 38)[0]
    except Exception:
        return 0


def defensas_elementales_jugador(ses) -> dict:
    """Las defensas de resistencia y elementales del personaje, leidas del 0x0042."""
    try:
        import struct as _s
        raw = _stats_ses(ses)
        return {
            'stamina': _s.unpack_from('<H', raw, 70 + 2)[0],
            'soul': _s.unpack_from('<H', raw, 74 + 2)[0],
            'thnd': _s.unpack_from('<H', raw, 76 + 2)[0],
            'fire': _s.unpack_from('<H', raw, 80 + 2)[0],
            'ice': _s.unpack_from('<H', raw, 84 + 2)[0],
            'rotten': _s.unpack_from('<H', raw, 88 + 2)[0],
        }
    except Exception:
        return {'stamina': 5, 'soul': 5, 'thnd': 0, 'fire': 0, 'ice': 0, 'rotten': 0}


def skills_arma_ses(ses):
    """Las habilidades de arma de lo equipado."""
    import clases as _cl
    return _cl.skills_de_equipo(getattr(ses, 'inventario', None))


# Cuanto se le perdona al cliente que se adelante al pedir el siguiente
# golpe basico, como fraccion de la cadencia. Con 0.20 sobre 1.15 s entran
# los que piden a partir de 0.92, que son los que se veian en el log
# (1.03, 1.05, 1.10). Lo que llegue antes de eso sigue fuera.
MARGEN_CADENCIA = 0.20


def lleva_duales_ses(ses):
    """Si el personaje pelea con DOS armas de mano (el escudo no cuenta)."""
    import clases as _cl
    return _cl.lleva_duales(getattr(ses, 'inventario', None))


def _portales():
    """La tabla de tornados de plantillas/portales.json."""
    global _PORTALES
    import json
    if _PORTALES is None:
        f = pathlib.Path(__file__).parent / 'plantillas' / 'portales.json'
        _PORTALES = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {
            'msg': 5801, 'opciones': [], 'radio': 2, 'mapas': {}}
    return _PORTALES


# LOS MAPAS QUE TIENEN PLANTILLA. Es login.PLANTILLAS_POR_STAGE mas los dos
# que se tratan aparte. Estaba escrito a mano en tres sitios distintos y ya
# se pago caro una vez: cada copia que se olvidaba dejaba un mapa entero sin
# IA. Aqui esta una sola vez.
MAPAS_APARTE = {41: 'lyceum.json'}
# Hasta donde piensa un monstruo. Mas alla de esto el jugador no lo ve -- su
# radio de vision son 38 casillas, medido -- asi que gastarle IA no sirve de
# nada. Ver el bucle de IA, que corre diez veces por segundo.
RADIO_IA = 48

_INSTANCIAS = None


def es_instancia(stage) -> bool:
    """Si ese mapa es una INSTANCIA de las que el cliente llama dinamicas.

    stage.xml las marca con 動態空間=是 y 平行空間=15: quince copias del mapa,
    repartidas por equipo. Dentro de una instancia los bichos NO REAPARECEN:
    se limpia y se queda limpia hasta que sales y vuelves a entrar, que es
    cuando el servidor te da una copia nueva. Lo describio el usuario
    jugando, y encaja con lo que declara el cliente.

    Aqui las copias por equipo no estan: cada sesion arma sus propios
    monstruos con _monstruos_de() al cambiar de mapa, asi que un jugador ya
    tiene su mapa para el solo y al salir y volver se le rehace entero. Lo
    que faltaba era no resucitarlos mientras esta dentro.
    """
    global _INSTANCIAS
    if _INSTANCIAS is None:
        import json
        f = pathlib.Path(__file__).parent / 'plantillas' / 'instancias.json'
        d = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
        _INSTANCIAS = {int(k) for k, v in (d.get('mapas') or {}).items()
                       if v.get('dinamica')}
    return int(stage or 0) in _INSTANCIAS
# DONDE APARECE EL JUGADOR al entrar a cada Training Area por el dialogo del
# Terra Keeper. La casilla es (136,72) en las cuatro, leida del minimapa en el
# cliente oficial. Estaba en (202,109), que es la casilla de VUELTA -- donde
# se aparece en Mysterious Garden al salir -- y por eso el jugador entraba en
# el sitio equivocado.
DESTINOS_ENTRENAMIENTO = {
    7505: (135, (136, 72), 'Training Area C'),
    7506: (136, (136, 72), 'Training Area D'),
    7507: (118, (136, 72), 'Training Area A'),
    7508: (134, (136, 72), 'Training Area B'),
}
ETAPAS_ENTRENAMIENTO = frozenset(destino[0]
                                 for destino in DESTINOS_ENTRENAMIENTO.values())
ENTIDAD_SALIDA_ENTRENAMIENTO_B = 0x06380409
EVENTO_SALIDA_ENTRENAMIENTO_A = bytes.fromhex('ef020a5003')
RETORNO_ENTRENAMIENTO = (22, (201, 108), 'Mysterious Garden')


def mapas_poblados():
    import login as _lgp
    return {**_lgp.PLANTILLAS_POR_STAGE, **MAPAS_APARTE}


ITEM_SUPERWING = 25832
_ANGELS_GO = None


def _angels_go():
    """La tabla de destinos del Angels GO!, de plantillas/angels_go.json.

    Es el 編號 de jumpmap.xml del cliente. Medido tres veces en Celestia --
    los ids 120, 119 y 109 -- y las tres la casilla de llegada fue
    exactamente la que declara esa tabla, asi que vale entera sin medir
    destino por destino.
    """
    global _ANGELS_GO
    import json
    if _ANGELS_GO is None:
        f = pathlib.Path(__file__).parent / 'plantillas' / 'angels_go.json'
        _ANGELS_GO = (json.loads(f.read_text(encoding='utf-8')).get('destinos', {})
                      if f.exists() else {})
    return _ANGELS_GO


# Las CUATRO facciones de verdad, por su codigo en la ficha. El 5 es
# "Heaven", que es con lo que se sale del Lyceum antes de elegir, y el 0 es
# "Neutrally": ninguno de los dos es una faccion, son el estado de no tener.
FACCIONES_REALES = (1, 2, 3, 4)   # Aurora, Beasts, Steel, Shadow


def tiene_faccion(p) -> bool:
    """Si el personaje pertenece a una de las cuatro facciones.

    Medido en Celestia: un personaje de nivel 12 con la ficha en "Heaven"
    NO puede usar las Superwing. Hay que elegir faccion en el Graduation
    Palace primero.
    """
    import login as _lgf
    if p is None:
        return False
    return (_lgf.CODIGO_FACCION.get(getattr(p, 'faction', ''), 5)
            in FACCIONES_REALES)


def _ranura_de_item(ses, item_id: int):
    """La primera casilla de la mochila que lleva ese item, o None."""
    for r, iid in sorted(getattr(ses, 'inventario', {}).items()):
        if int(iid) == int(item_id) and int(r) >= 20:
            return int(r)
    return None



def _estatuas(stage):
    """Las estatuas que teletransportan de plantillas/portales.json.

    Mecanismo medido en Seaside Grotto, y distinto de todo lo demas. No es el
    0x0016 de los portales internos de Lost Trail ni el menu de los de
    Bearscape: aqui hay que HABLARLE al objeto.

        c2s 0x0005 [u32 entidad][u16 0]   <- clic sobre la estatua
        s2c 0x0012 con el mensaje y dos opciones, Yes y No
        c2s 0x000B [0a]                   <- se elige la primera, Yes
        s2c 0x0003 [u32 yo][u32 x][u32 y] <- y aparece al otro lado

    El 0x0a es 10, que es PRIMERA_OPCION, o sea el indice 0: la opcion "Yes".
    Se confirmo contando: el 0x000B aparece en las cinco veces que hubo salto
    y falta en las tres que no. Antes se habia mirado el 0x000F, que resulta
    ser un latido -- sale 95 veces por sesion -- y no tenia nada que ver.

    El mensaje avisa de que forzar la barrera cuesta vida, y el usuario lo
    confirmo en el juego.
    """
    return (_portales().get('teletransportes_por_dialogo') or {}).get(str(stage)) or []


def _estatua_con_entidad(stage, ent):
    """La estatua cuyo id coincide, o None. Compara por ENTIDAD y no por
    casilla, porque el clic llega con la entidad y nuestro servidor reenvia
    los objetos con su id original."""
    for e in _estatuas(stage):
        if ent in ((e.get('estatuas') or {}).get('entidades') or []):
            return e
    return None


def _dialogo_de_estatua(e):
    """El 0x0012 tal como lo manda el servidor real: cabecera de nueve bytes,
    luego los ids de opcion y luego las acciones."""
    ops = list(e.get('opciones') or [])
    acc = list(e.get('acciones') or [0] * len(ops))
    b = bytearray(9)
    struct.pack_into('<I', b, 0, int(e['msg']))
    b[7] = len(ops)
    for o in ops:
        b += struct.pack('<I', int(o))
    for a in acc[:len(ops)]:
        b += struct.pack('<I', int(a))
    return struct.pack('<H', 0x0012) + bytes(b)


def _portal_en(stage, tx, ty):
    """El tornado que se esta pisando, o None."""
    cfg = _portales()
    for por in cfg.get('mapas', {}).get(str(stage), []):
        # TORNADO ANOTADO PERO SIN MEDIR. Los que llevan a una instancia estan
        # en el json para no perder su casilla y su entidad, pero con destino
        # en null. Devolverlos haria que el servidor intentara viajar al stage
        # None. Se saltan hasta que alguien capture el cruce.
        #
        # PERO los que PREGUNTAN tambien tienen el destino en null, y a
        # proposito: el suyo lo decide la opcion que elija el jugador, no el
        # tornado. Se colaban en este filtro y por eso los dos portales con
        # menu que hay -- el de Shuwa Market a Siam Square y el de Bayan
        # Village -- no abrian el cuadro NUNCA: el servidor ni siquiera los
        # encontraba al pisarlos.
        if por.get('destino') is None and not por.get('preguntar'):
            continue
        # Radio propio si lo trae. El radio 1 global pide estar justo encima,
        # y eso no vale para todos: el tornado de Mushroom hacia Jade Vale
        # dispara desde dos casillas antes -- medido, el jugador se quedo en
        # (6,238) y el tornado esta en (5,240).
        # El radio que DECLARA el portal manda, aunque sea 1. Antes habia un
        # max(2, ...) que lo pisaba, y con eso se rompia el unico portal que
        # pide radio 1: el de Majestic Mansion a Floral Alley, en (19,171).
        # La llegada desde Floral Alley es (21,169), a dos casillas, asi que
        # subido a 2 el jugador aparecia DENTRO del tornado de vuelta. Con el
        # 1 que pide queda fuera. El minimo se sigue aplicando a los que no
        # declaran ninguno.
        r = por['radio'] if por.get('radio') else max(2, cfg.get('radio', 2))
        # Algunas puertas dibujan el tornado fuera de los limites caminables.
        # En ese caso el arte usa ``tile`` y la zona pisable ``trigger_tile``.
        trigger = por.get('trigger_tile') or por['tile']
        if abs(trigger[0] - tx) <= r and abs(trigger[1] - ty) <= r:
            return por
    return None


def _nombre_entidad(ses, entity_id: int) -> str:
    """El nombre del NPC del mapa, para buscarle su dialogo."""
    totems_lyceum = {
        41: 'Aurora Totem', 150: 'Aurora Totem',
        43: 'Iron Totem', 121: 'Iron Totem',
        44: 'Dark City Totem', 122: 'Dark City Totem',
        45: 'Breeze Totem', 120: 'Breeze Totem',
    }
    if entity_id in totems_lyceum:
        return totems_lyceum[entity_id]
    # Los totems del Fighting Palace se mandan como objetos de mapa y su
    # entity_id lo asigna poblar(), asi que no puede ir escrito a mano.
    import login as _lg
    if entity_id in _lg.TOTEMS_PUESTOS:
        return _lg.TOTEMS_PUESTOS[entity_id]
    if entity_id in (2603, 260300):
        return 'Maid Eilian'
    if entity_id in (2604, 500004):
        return 'Pet Care Machine'
    if entity_id in (2605, 500005):
        return 'Monster Hatching Machine'

    if getattr(ses, 'personaje', None):
        st = ses.personaje.stage
        p_name = _lg.PLANTILLAS_POR_STAGE.get(st)
        if p_name:
            import json
            f_tmpl = pathlib.Path(__file__).parent / 'plantillas' / p_name
            if f_tmpl.exists():
                try:
                    d_tmpl = json.loads(f_tmpl.read_text(encoding='utf-8'))
                    for e in d_tmpl.get('spawns', []):
                        if e.get('entity_id') == entity_id and e.get('nombre'):
                            return e['nombre']
                except Exception:
                    pass

    import dialogos as _dlg
    info = _dlg.info_npc(entity_id)
    if info and info.get('nombre'):
        return info['nombre']

    # Si es un NPC de quest de los xmls (entity_id >= 900)
    f_mapas = pathlib.Path(__file__).parent / 'plantillas' / 'npc_por_mapa.json'
    if f_mapas.exists() and entity_id >= 900 and getattr(ses, 'personaje', None):
        import json
        d_mapas = json.loads(f_mapas.read_text(encoding='utf-8')).get('mapas', {})
        st_npcs = d_mapas.get(str(ses.personaje.stage), [])
        idx = entity_id - 900
        if 0 <= idx < len(st_npcs):
            return st_npcs[idx].get('nombre', '')
    return ''


def _monstruos_de(stage: int):
    """Los monstruos vivos del mapa, por entity_id."""
    import json
    import combate
    import login as _lg
    plantillas = pathlib.Path(__file__).parent / 'plantillas'
    # Cada mapa poblado tiene su plantilla. El West Playground trae 150
    # monstruos de seis clases, asi que su IA sale de aqui igual que la del
    # Lyceum: pasean, persiguen, pegan y reaparecen.
    por_stage = mapas_poblados()
    nombre = por_stage.get(stage)
    bichos = {}
    if nombre:
        f = plantillas / nombre
        if f.exists():
            d = json.loads(f.read_text(encoding='utf-8'))
            bichos = {e['entity_id']: combate.Monstruo(e['entity_id'], e['npc_type'],
                                                     e['nombre'], e['tile'],
                                                     e.get('sprite', 0), stage=stage)
                    for e in d.get('spawns', []) if e.get('monstruo') and not e.get('apagado')}
    # Los mapas sin plantilla o cuya plantilla no traiga monstruos usan la lista escrita a mano
    if not bichos and stage in _lg.PLAYGROUND_MONSTERS:
        bichos = {}
        for item in _lg.PLAYGROUND_MONSTERS[stage]:
            eid, ntype, nom, tile = item[:4]
            sp = item[4] if len(item) > 4 else (_lg.sprite_de(ntype, 42107) if ntype == 224 else _lg.sprite_de(ntype, 0))
            bichos[eid] = combate.Monstruo(eid, ntype, nom, tile, sprite=sp, stage=stage)
    return bichos


_PRECIOS = None


def _cargar_precios():
    """{item_id: (precio_lista, precio_venta)} de las NUEVE tablas de item.

    Antes esto solo miraba la tabla `item`, que es item.xml a secas. Todo el
    equipo de verdad vive en item2..item9 (el Hephaestus-Hedgehog Bag es el
    40757 de item2), asi que esas consultas devolvian 0, el max(1, ...) lo
    convertia en 1 y la tienda pagaba un oro por cualquier cosa.

    La columna de venta es 收購價格 ("precio de compra" visto desde la
    tienda) y NO esta en la misma posicion en cada tabla -- en `item` cae en
    la 4 y en `item3` en la 60 -- asi que se busca por nombre, no por
    indice. Cuando la tabla no la trae se usa la mitad del precio de lista,
    que es lo que hacia la version vieja.
    """
    global _PRECIOS
    if _PRECIOS is not None:
        return _PRECIOS
    import sqlite3
    import inventario as _iv_p
    _PRECIOS = {}
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if not db.exists():
        return _PRECIOS
    try:
        con = sqlite3.connect(db)
    except Exception:
        return _PRECIOS

    def _n(x):
        try:
            return int(float(x))
        except (TypeError, ValueError):
            return 0

    for tabla in _iv_p.TABLAS_ITEM:
        try:
            cols = [r[1] for r in con.execute('pragma table_info(%s)' % tabla)]
        except Exception:
            continue
        if 'price' not in cols:
            continue
        venta = '收購價格' if '收購價格' in cols else None
        sel = 'select id, price, %s from %s' % (
            ('"%s"' % venta) if venta else 'NULL', tabla)
        try:
            filas = list(con.execute(sel + " where id glob '[0-9]*'"))
        except Exception:
            continue
        for iid, pr, vt in filas:
            lista = _n(pr)
            v = _n(vt)
            if not lista and not v:
                continue
            ant = _PRECIOS.get(int(iid), (0, 0))
            _PRECIOS[int(iid)] = (lista or ant[0], v or ant[1])
    con.close()
    return _PRECIOS


def _precio_item(item_id: int) -> int:
    """Precio de lista del item, mirando las nueve tablas."""
    lista, venta = _cargar_precios().get(int(item_id or 0), (0, 0))
    if lista > 0:
        return lista
    if venta > 0:
        return venta * 2
    return 0


# Lo que descuenta la tienda sobre el precio de lista al comprar. La Red
# Potion 1 tiene price 40 en item.xml; el cliente la enseña a 35 en la
# ventana de compra (40 * 7/8) y Celestia cobro 34 en las dos capturas
# (476 por catorce, 680 por veinte). Se usa el 7/8 que muestra el cliente
# para que la cuenta le cuadre al jugador.
DESCUENTO_COMPRA = 7 / 8


def _precio_compra(item_id: int) -> int:
    """Lo que cuesta comprar ese item en una tienda."""
    import configuracion as _conf
    flag = getattr(_conf, 'FLAG_ORO', None)
    if flag is None:
        flag = getattr(_conf, 'COMPRAS_1_DE_ORO', False)
    if flag:
        return 1
    precio = _precio_item(item_id)
    if precio <= 0:
        return 1
    return max(1, int(precio * DESCUENTO_COMPRA))


def _precio_venta(item_id: int) -> int:
    """Lo que paga la tienda por ese item.

    Sale de la columna 收購價格, que es distinta del precio de lista: la Red
    Potion 1 vale 40 de lista y 12 de venta, y son justo los numeros de la
    captura (once pociones dieron 132 de oro). El equipo no suele traerla,
    y para ese se usa la mitad del precio de lista.
    """
    lista, venta = _cargar_precios().get(int(item_id or 0), (0, 0))
    if venta > 0:
        return venta
    if lista > 0:
        return max(1, lista // 2)
    return 1


# Ultima casilla utilizable de la mochila base (pestaña Prop: 5x5 = 25 ranuras,
# de la 20 a la 44 inclusive). Con mochila equipada en ranura 7/8 se habilitan
# ademas las bolsas extra (hasta la 120).
TOPE_SIN_MOCHILA = 44
TOPE_CON_MOCHILA = 120


def _tope_bolsa(bolsa) -> int:
    """Hasta que casilla se puede guardar, segun si hay mochila puesta."""
    b = bolsa or {}
    hay = b.get(7) is not None or b.get(8) is not None
    return TOPE_CON_MOCHILA if hay else TOPE_SIN_MOCHILA


def _ranura_libre(bolsa, desde=20, hasta=None):
    """Primera casilla vacia de la mochila o rango, o None si esta llena."""
    limite = hasta if hasta is not None else _tope_bolsa(bolsa)
    for r in range(desde, limite + 1):
        if r not in bolsa:
            return r
    return None


def _final_tutorial(ses, addr):
    """Ultimo paso: entrega el set y las cajas, y manda al Angel Lyceum."""
    import clases
    import inventario as inv
    bolsa = getattr(ses, 'inventario', None)
    if bolsa is None or not ses.personaje.habilidades:
        return
    cid = ses.personaje.char_id
    ids = [h[0] for h in ses.personaje.habilidades]
    for ranura, item_id in clases.premio_final(ids):
        if ranura in bolsa:
            ranura = _ranura_libre(bolsa)
        bolsa[ranura] = item_id
        ses.enviar(clases.aviso(_nombre_item(item_id), tipo=0,
                                msg_id=clases.MSG_ITEM))
        ses.enviar(*inv.entregar(cid, item_id, ranura))
    ses.enviar(inv.stats(bolsa, mejoras=_mejoras_de(ses)))
    # Y al Lyceum.
    ses.personaje.stage = clases.STAGE_LYCEUM
    ses.personaje.tile_x, ses.personaje.tile_y = clases.TILE_LYCEUM
    ses.monstruos = _monstruos_de(clases.STAGE_LYCEUM)
    ses.enviar(clases.cambiar_mapa(clases.STAGE_LYCEUM))
    if getattr(ses, 'usuario', None):
        cuentas.guardar_inventario(ses.usuario, cid, bolsa,
                                   _cantidades(ses))
        cuentas.guardar_mapa(ses.usuario, cid, clases.STAGE_LYCEUM,
                             *clases.TILE_LYCEUM)
    log.info(f"[{addr}] tutorial terminado: set completo, "
             f"{len(clases.cajas_de(ids)) + 1} cajas y al Angel Lyceum")


def _premio(srv, ses, addr, etapa):
    """Entrega lo que da ese tramo del tutorial: items y oro."""
    import clases
    import inventario as inv
    r = clases.RECOMPENSAS.get(etapa)
    if not r or getattr(ses, 'inventario', None) is None:
        return
    cid = ses.personaje.char_id
    nuevos = False
    for ranura, item_id in r['items']:
        if ranura not in ses.inventario:
            ses.inventario[ranura] = item_id
            ses.enviar(clases.aviso(_nombre_item(item_id), tipo=0,
                                    msg_id=clases.MSG_ITEM))
            ses.enviar(*inv.entregar(cid, item_id, ranura))
            nuevos = True
    if r['oro']:
        ses.oro = getattr(ses, 'oro', 0) + r['oro']
        if ses.personaje:
            ses.personaje.oro = ses.oro
        nuevos = True
        log.info(f"[{addr}] tutorial: +{r['oro']} de oro (total {ses.oro})")
    if nuevos:
        # El oro si necesita el inventario entero: su cantidad vive en la
        # entrada de la ranura 0 y no hay un mensaje de "cambio de oro"
        # identificado.
        if r['oro']:
            ses.enviar(inv.completo(
                cid, _con_oro(ses), _dueno(ses),
                getattr(ses.personaje, 'mejoras', None)
                if ses.personaje else None))
        if getattr(ses, 'usuario', None):
            cuentas.guardar_inventario(ses.usuario, cid, ses.inventario,
                                   _cantidades(ses))
        log.info(f"[{addr}] tutorial: entregado el premio de la etapa {etapa}")


def _cantidades(ses) -> dict:
    """Cuantas unidades hay en cada casilla. La casilla que no esta aqui
    lleva una sola."""
    c = getattr(ses, 'cantidades', None)
    if c is None:
        c = {}
        ses.cantidades = c
    return c


def _cant_de(ses, ranura: int) -> int:
    return max(1, int(_cantidades(ses).get(int(ranura), 1)))


def _instancias(ses) -> dict:
    """El id de instancia de ocho bytes de cada casilla ocupada."""
    m = getattr(ses, 'instancias', None)
    if m is None:
        m = {}
        ses.instancias = m
    return m


def _inst(ses, ranura: int) -> bytes:
    """La instancia de esa casilla, creandola la primera vez."""
    import inventario as inv
    m = _instancias(ses)
    r = int(ranura)
    if r not in m:
        m[r] = inv.instancia_nueva()
    return m[r]


def _mover_inst(ses, origen: int, destino: int):
    """La instancia Y LAS MEJORAS viajan con el item al cambiar de casilla.

    Las mejoras se guardan por CASILLA, no por objeto. Mientras el arma no
    se moviera daba igual, pero en cuanto se quitaba del cuerpo y caia en la
    mochila, el "+N" y los stats verdes se quedaban en la casilla vieja y la
    pieza aparecia limpia. Aqui se mueven con ella, y si la casilla de
    destino ya tenia algo se INTERCAMBIAN, que es lo que hace el juego al
    arrastrar una pieza encima de otra.
    """
    o, d = int(origen), int(destino)
    m = _instancias(ses)
    v = m.pop(o, None)
    w = m.pop(d, None)
    if v is not None:
        m[d] = v
    if w is not None:
        m[o] = w
    mej = getattr(ses.personaje, 'mejoras', None) if ses.personaje else None
    if mej is None:
        return
    # Migracion de objetos que ya estaban equipados antes de este cambio.
    # La bolsa ya fue movida por el caller; la pieza de origen esta en d.
    import inventario as _iv
    if _iv.es_equipo(o) and d in ses.inventario:
        estado = mej.get(o, {})
        if _iv.vincular_equipo(int(ses.inventario[d]), ses.personaje.char_id, estado):
            mej[o] = estado
    a = mej.pop(o, None)
    b = mej.pop(d, None)
    if a is not None:
        mej[d] = a
    if b is not None:
        mej[o] = b


def _meter(ses, item_id: int, n: int = 1, pet_metadata: dict = None) -> int:
    """Mete n unidades en la mochila y devuelve la casilla que las lleva.

    Si el item se apila y ya hay un monton suyo, se suma ahi en vez de
    ocupar una casilla nueva. Si es no-apilable (muebles, equipo, mascotas),
    asigna casillas individuales independientes con id de instancia unico.
    """
    import inventario as inv
    item_id = int(item_id)
    if inv.es_item_oculto(item_id):
        log.warning(f"Intento de meter item oculto de mision {item_id} en la mochila visible bloqueado")
        return None
    bolsa = ses.inventario
    n = max(1, int(n))
    if inv.es_apilable(item_id):
        for ranura, it in bolsa.items():
            r = int(ranura)
            if r == inv.RANURA_ORO or int(it) != item_id:
                continue
            if inv.es_equipo(r):
                continue
            _cantidades(ses)[r] = _cant_de(ses, r) + n
            return r
        r = _ranura_libre(bolsa)
        if r is None:
            return None
        bolsa[r] = item_id
        _instancias(ses)[r] = inv.instancia_nueva()
        if n > 1:
            _cantidades(ses)[r] = n
        return r

    import casas as _cs_m
    es_deed = _cs_m.es_deed_item(item_id) or inv.categoria_item(item_id) == '房屋'
    es_mueble = bool(not es_deed and (_cs_m.item_a_mueble(item_id) is not None or inv.categoria_item(item_id) in ('傢俱', '家具')))
    if es_mueble:
        primera_ranura = None
        for _ in range(n):
            r = _ranura_libre(bolsa, desde=_cs_m.SLOT_FURN_INI, hasta=_cs_m.SLOT_FURN_FIN)
            if r is None:
                r = _ranura_libre(bolsa)
            if r is None:
                break
            if primera_ranura is None:
                primera_ranura = r
            bolsa[r] = item_id
            _instancias(ses)[r] = inv.instancia_nueva()
            _cantidades(ses).pop(r, None)
        return primera_ranura

    r = _ranura_libre(bolsa)
    if r is None:
        return None
    bolsa[r] = item_id
    _instancias(ses)[r] = inv.instancia_nueva()
    if n > 1:
        _cantidades(ses)[r] = n
    p_ses = getattr(ses, 'personaje', None)
    if p_ses:
        if getattr(p_ses, 'mejoras', None) and r in p_ses.mejoras:
            p_ses.mejoras.pop(r, None)
        if inv.es_mascota(item_id):
            import mascotas as _ms_new, configuracion as _cf_new
            d_pet = inv.datos_mascota(item_id)
            if not hasattr(p_ses, 'mascotas') or not isinstance(p_ses.mascotas, dict):
                p_ses.mascotas = {}
            p_nom = (pet_metadata.get('nombre') if pet_metadata else None) or (pet_metadata.get('captured_name') if pet_metadata else None) or d_pet['nombre']
            p_st = max(1, int((pet_metadata.get('estrellas') if pet_metadata else None) or d_pet.get('estrellas') or 1))
            p_rg = int((pet_metadata.get('rango') if pet_metadata else None) or 1)
            p_mid = int((pet_metadata.get('npc_type') if pet_metadata else None) or 0)
            f_new = _ms_new.recien_nacida(
                p_nom, d_pet['sprite'],
                nivel=max(1, getattr(_cf_new, 'MASCOTA_NIVEL_INICIAL', 1)),
                estrellas=p_st,
                rango=p_rg,
                npc_type=p_mid
            )
            f_new['ranura'] = r
            f_new['item'] = item_id
            f_new['instancia'] = 1000 + int(r)
            f_new['fuera'] = False
            if pet_metadata and isinstance(pet_metadata, dict):
                f_new.update(pet_metadata)
            p_ses.mascotas[str(r)] = f_new
            if not getattr(p_ses, 'mascota', None) or p_ses.mascota.get('ranura') == r:
                p_ses.mascota = f_new
    return r


def _sacar(ses, ranura: int, n: int = 1) -> int:
    """Quita n unidades de esa casilla y devuelve cuantas quito de verdad."""
    ranura = int(ranura)
    bolsa = ses.inventario
    if ranura not in bolsa:
        return 0
    hay = _cant_de(ses, ranura)
    quita = min(hay, max(1, int(n)))
    if quita >= hay:
        del bolsa[ranura]
        _cantidades(ses).pop(ranura, None)
        _instancias(ses).pop(ranura, None)
        p_ses = getattr(ses, 'personaje', None)
        if p_ses:
            if getattr(p_ses, 'mejoras', None):
                p_ses.mejoras.pop(ranura, None)
            if getattr(p_ses, 'mascotas', None) and isinstance(p_ses.mascotas, dict):
                p_ses.mascotas.pop(str(ranura), None)
                p_ses.mascotas.pop(ranura, None)
            if isinstance(getattr(p_ses, 'mascota', None), dict) and p_ses.mascota.get('ranura') == ranura:
                p_ses.mascota = None
    else:
        _cantidades(ses)[ranura] = hay - quita
    return quita


def _cant_total_item(ses, item_id: int) -> int:
    """Cantidad acumulada de un item en todas las ranuras validas de la mochila."""
    bolsa = getattr(ses, 'inventario', {}) or {}
    max_r = _tope_bolsa(bolsa)
    return sum(_cant_de(ses, r) for r, it in bolsa.items() if int(it) == int(item_id) and 20 <= int(r) <= max_r)


def _consumir_item_total(ses, item_id: int, n: int) -> list:
    """Consume n unidades repartidas entre las ranuras de la mochila y devuelve las ranuras tocadas."""
    bolsa = getattr(ses, 'inventario', {}) or {}
    max_r = _tope_bolsa(bolsa)
    tocadas = []
    restante = int(n)
    for r in range(20, max_r + 1):
        if int(bolsa.get(r, 0)) == int(item_id):
            hay = _cant_de(ses, r)
            quitar = min(hay, restante)
            _sacar(ses, r, quitar)
            tocadas.append(r)
            restante -= quitar
            if restante <= 0:
                break
    return tocadas


def _obtener_receta_exchange(recipe_id: int):
    """Obtiene los materiales requeridos y las recompensas de exchange.xml."""
    import house_services
    rows = house_services.xml_rows('exchange.xml')
    r = rows.get(int(recipe_id))
    if not r:
        return None
    materiales = []
    for i in range(1, 10):
        m_id = r.get(f'\u6750\u6599{i}') or r.get(f'材料{i}')
        m_cnt = r.get(f'\u6750\u6599{i}\u6578\u91cf') or r.get(f'材料{i}數量') or '1'
        if m_id and int(m_id) > 0:
            materiales.append((int(m_id), int(m_cnt)))
    premios = []
    for i in range(1, 10):
        p_id = r.get(f'\u734e\u8cde{i}') or r.get(f'獎賞{i}')
        p_cnt = r.get(f'\u734e\u8cde{i}\u6578\u91cf') or r.get(f'獎賞{i}數量') or '1'
        if p_id and int(p_id) > 0:
            premios.append((int(p_id), int(p_cnt)))
    return {'id': recipe_id, 'materiales': materiales, 'premios': premios}


def _con_oro(ses):
    """El inventario con la cantidad de cada casilla."""
    import inventario as inv
    out = []
    for ranura, item_id in ses.inventario.items():
        r = int(ranura)
        if r != inv.RANURA_ORO and (not item_id or int(item_id) <= 0):
            continue
        if r == inv.RANURA_ORO:
            out.append((r, int(item_id), getattr(ses, 'oro', 0), _inst(ses, r)))
        else:
            out.append((r, int(item_id), _cant_de(ses, r), _inst(ses, r)))
    return out


def _dueno(ses):
    """El char_id del personaje que posee el inventario (necesario para la comprobacion
    de vinculacion de equipo con residual times 0 en Angel.exe)."""
    p = getattr(ses, 'personaje', None)
    return getattr(p, 'char_id', None) or getattr(ses, 'char_id', None) or 4980


def _refrescar(ses, ranuras, con_oro=False):
    """Los 0x001B de las casillas que cambiaron.

    El servidor real no reenvia el inventario entero tras comprar, vender o
    usar algo: manda una linea por casilla tocada. Con el 0x001A completo el
    cliente se quedaba con lo que ya tenia pintado y los items vendidos
    seguian apareciendo en la mochila.
    """
    import inventario as inv
    cid = ses.personaje.char_id if ses.personaje else 4980
    fuera = []
    if con_oro:
        fuera.append(inv.actualizar_ranura(cid, inv.RANURA_ORO, 1,
                                           getattr(ses, 'oro', 0),
                                           _inst(ses, inv.RANURA_ORO),
                                           _dueno(ses)))
    mascotas_map = getattr(ses.personaje, 'mascotas', {}) if ses.personaje else {}
    _masc = getattr(ses.personaje, 'mascota', None) if ses.personaje else None
    for r in sorted(set(int(x) for x in ranuras if x is not None)):
        if r in ses.inventario:
            p_data = None
            es_pet = inv.es_mascota(int(ses.inventario[r]))
            if es_pet:
                p_data = mascotas_map.get(str(r)) or mascotas_map.get(r)
                if not p_data and _masc and (_masc.get('ranura') == r or (_masc.get('ranura') is None and _masc.get('item') == int(ses.inventario[r]))):
                    p_data = _masc
            _linea = inv.actualizar_ranura(cid, r, int(ses.inventario[r]),
                                           _cant_de(ses, r), _inst(ses, r),
                                           _dueno(ses), mascota=p_data)
            if not es_pet:
                # El "+N" de las mejoras viaja DENTRO de la entrada, en el byte
                # 83. Si no se escribe, el cliente no enseña ni el "+7" pegado al
                # nombre ni el "has been intensified ( N ) times" del tooltip,
                # por mucho que el servidor lleve la cuenta.
                _mej = (getattr(ses.personaje, 'mejoras', None) or {}).get(r) if ses.personaje else None
                if ses.personaje and inv.es_equipo(r):
                    estado = _mej if _mej is not None else {}
                    if inv.vincular_equipo(int(ses.inventario[r]), cid, estado):
                        ses.personaje.mejoras[r] = estado
                        _mej = estado
                        if getattr(ses, 'usuario', None):
                            cuentas.guardar_mejoras(ses.usuario, cid, ses.personaje.mejoras)
                _linea = inv.marcar_caducidad_mercenario(_linea, _mej)
                _linea = inv.marcar_vinculacion(_linea, _mej)
                if _mej and _mej.get('veces'):
                    _linea = inv.marcar_mejora(_linea, _mej['veces'])
                # Y los stats del martillo verde, que van en la misma entrada en
                # registros de cuatro bytes desde el offset 13.
                if _mej and _mej.get('extra'):
                    _linea = inv.marcar_extras(_linea, _mej['extra'])
                # Y LOS HUECOS con sus gemas, que van en el 82 y del 62 al 81.
                # Sin esto el cliente no dibujaba donde meter la gema, asi que
                # tras abrir el primer hueco la pieza se quedaba atascada.
                if _mej and (_mej.get('huecos') or _mej.get('gemas')):
                    _linea = inv.marcar_huecos(_linea, _mej.get('huecos') or 0,
                                               _mej.get('gemas'))
            fuera.append(_linea)
        else:
            dueno = ses.personaje.entity_id if ses.personaje else cid
            fuera.append(inv.vaciar_ranura(dueno, r))
    if ses.personaje and getattr(ses, 'usuario', None):
        mejoras = getattr(ses.personaje, 'mejoras', {})
        if any(v.get('vinculacion') for v in mejoras.values()):
            cuentas.guardar_mejoras(ses.usuario, cid, mejoras)
    return fuera


def _entrada_item_puesto(ses, ranura: int, cantidad: int) -> bytes:
    """Devuelve los (85 + extra_len) bytes de la ficha de un item para S2C 0x0032.

    En Angel.exe (FUN_00604710, 0x604965), cada entrada de venta del puesto
    lleva 20 bytes de cabecera (<8sIII: instancia, cantidad, precio, item_id)
    seguidos directamente del cuerpo de item que parsea FUN_00514d50 (la
    entrada de 0x001B sin los 7 primeros bytes de cabecera/sub-opcode).
    """
    paquetes = _refrescar(ses, [int(ranura)], con_oro=False)
    if not paquetes or len(paquetes[0]) < 15:
        return b'\x00' * 85
    cuerpo_item = bytearray(paquetes[0][7:])
    struct.pack_into('<I', cuerpo_item, 4, max(1, int(cantidad)))
    return bytes(cuerpo_item)


def _paquete_vista_puesto(vendedor) -> bytes:
    """Construye S2C 0x0032 (FUN_00604710) con las pestanas Sell y Buy del puesto."""
    puesto = getattr(vendedor, 'puesto', None) or {}
    p_vend = getattr(vendedor, 'personaje', None)
    nombre = getattr(p_vend, 'nombre', '') or 'Stall'
    nom_b = nombre.encode('latin-1', 'replace')[:16].ljust(17, b'\x00')
    bolsa = getattr(vendedor, 'inventario', {}) or {}

    ventas_limpias = []
    for v in list(puesto.get('ventas') or []):
        r = int(v['ranura'])
        if bolsa.get(r) != v['item_id']:
            continue
        hay = _cant_de(vendedor, r)
        if hay <= 0:
            continue
        v['cantidad'] = min(int(v['cantidad']), hay)
        if v['cantidad'] > 0:
            ventas_limpias.append(v)
    puesto['ventas'] = ventas_limpias

    compras_limpias = [
        c for c in (puesto.get('compras') or [])
        if int(c.get('cantidad', 0)) > 0 and int(c.get('item_id', 0)) > 0
    ]
    puesto['compras'] = compras_limpias

    buf = bytearray(struct.pack('<H17sII', 0x0032, nom_b,
                                len(ventas_limpias), len(compras_limpias)))
    for v in ventas_limpias:
        buf += struct.pack('<8sIII', v['instancia'], int(v['cantidad']),
                           int(v['precio']), int(v['item_id']))
        buf += _entrada_item_puesto(vendedor, v['ranura'], v['cantidad'])
    for c in compras_limpias:
        iid = int(c['item_id'])
        buf += struct.pack('<IIIII', iid, 0, int(c['cantidad']),
                           int(c['precio']), iid)
    return bytes(buf)


def _cerrar_puesto(ses, avisar_dueno: bool = True):
    """Cierra el puesto de venta del jugador y avisa a los demas en su mapa."""
    tenia = getattr(ses, 'puesto', None)
    ses.puesto = None
    if avisar_dueno and getattr(ses, 'personaje', None):
        ses.enviar(struct.pack('<H', 0x0031))
    if tenia and getattr(ses, 'personaje', None):
        try:
            import presencia as _pres
            _pres.notificar_cierre_puesto(ses)
        except Exception:
            log.exception('presencia: fallo al notificar cierre de puesto')



def _mejoras_de(ses):
    """Las mejoras del personaje de esa sesion, o None.

    Existe para que NINGUNA llamada a inventario.completo() se quede sin
    ellas: habia seis repartidas por el fichero que mandaban el inventario
    entero sin el "+N" ni los stats verdes, y bastaba con que saltara una
    para que el arma volviera a salir limpia en el cliente.
    """
    p = getattr(ses, 'personaje', None)
    return getattr(p, 'mejoras', None) if p else None


def _guardar_bolsa(ses, cid):
    """Guarda inventario, cantidades, mejoras y mascota juntos.

    Las mejoras se guardaban solo al mejorar. Como ahora viajan con el item
    al cambiar de casilla, hay que dejarlas en disco tambien al moverlo: si
    no, se quitaba el arma, se salia, y volvia con las mejoras en la casilla
    de antes.
    """
    if getattr(ses, 'usuario', None) and getattr(ses, 'personaje', None):
        cuentas.guardar_mejoras(ses.usuario, cid,
                                getattr(ses.personaje, 'mejoras', None))
        cuentas.guardar_mascota(ses.usuario, cid,
                                getattr(ses.personaje, 'mascota', None),
                                getattr(ses.personaje, 'mascotas', None))
    if getattr(ses, 'usuario', None):
        cuentas.guardar_inventario(ses.usuario, cid, ses.inventario,
                                   _cantidades(ses))


def _nombre_item(item_id: int) -> str:
    """Nombre del item para el cartel de 'obtuviste X'."""
    try:
        import misiones as _mis_nom
        return _mis_nom.nombre_item(int(item_id))
    except Exception:
        return f'Item{item_id}'


# ---------------------------------------------------------------------------
# Comando de GM para dar objetos
# ---------------------------------------------------------------------------
# Los ids salen de items.html, el catalogo que lleva el repo. El comando no
# inventa protocolo: reutiliza lo que ya usa el botin -- _meter para poner en
# la mochila, _refrescar para el 0x001B de la casilla y clases.aviso para el
# cartel de "obtuviste X".


def _item_existe(item_id: int) -> bool:
    """Si ese id existe en alguna de las tablas de items del cliente."""
    if int(item_id) == 83266:
        return True
    import sqlite3
    import inventario as _iv
    db = pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'
    if not db.exists():
        return False
    try:
        con = sqlite3.connect(db)
        r = _iv.fila_item(con, 'id', item_id)
        con.close()
        return r is not None
    except Exception:
        return False


def _gm_dar_item(ses, item_id: int, n: int = 1) -> str:
    """Mete n unidades del item en la mochila de esa sesion."""
    import clases as _cl
    import inventario as _iv_gm
    if getattr(ses, 'inventario', None) is None or not getattr(ses, 'personaje', None):
        return 'no hay personaje en el mundo todavia'
    item_id = int(item_id)
    n = max(1, min(9999, int(n)))
    if not _item_existe(item_id):
        return 'el item %d no existe' % item_id
    # LAS MASCOTAS TIRAN EL CLIENTE. Su entrada de inventario mide 235 bytes
    # -- se vio al abrir un huevo en el servidor real -- y nuestro
    # constructor solo sabe hacer las de 86 y 119. Dandole una mascota, el
    # cliente recibe algo a medias y se cierra. Se niega hasta que la entrada
    # de 235 este descifrada.
    ranuras_antes = set(ses.inventario.keys())
    ranura = _meter(ses, item_id, n)
    if ranura is None:
        return 'la mochila esta llena'
    ranuras_ahora = set(ses.inventario.keys())
    ranuras_refrescar = sorted(list(ranuras_ahora - ranuras_antes) or [ranura])
    nom = _nombre_item(item_id)
    cartel = nom if n == 1 else '%dx %s' % (n, nom)
    ses.enviar(_cl.aviso(cartel, tipo=0, msg_id=_cl.MSG_ITEM))
    ses.enviar(*_refrescar(ses, ranuras_refrescar))
    _guardar_bolsa(ses, ses.personaje.char_id)

    return 'dado %dx %s (%d) en la casilla %d' % (n, nom, item_id, ranura)


# Las primeras palabras que valen como comando sin la barra delante. Tiene
# que llevar TODAS las que entiende _gm_parsear: lo que falte aqui no llega
# nunca, porque el cliente se come la barra.
PALABRAS_GM = frozenset((
    'item', 'give', 'i', 'help',
    'rama', 'skill', 'branch',
    'estacion', 'season', 'modo',
    'rango', 'rank',
    'sistemas', 'album', 'logros', 'cartas', 'estrellas', 'casa',
    'level', 'lvl', 'lv', 'levelall', 'lvlall',
    'skills', 'spells', 'skillsall', 'learnall', 'skillall', 'skills5', 'skill5',
    'clearskills', 'clearskill',
    'pet', 'mascota',
    'emote', 'e', 'emocion',
    'ball', 'baile', 'fiesta',
))


def _gm_texto(cuerpo: bytes):
    """Saca un posible comando ASCII de un paquete C->S.

    El opcode del chat no se conoce, asi que se husmea en los cuatro offsets
    donde puede empezar el texto. Solo se da por bueno si empieza por barra o
    si la primera palabra es una de las del comando: asi un paquete binario
    cualquiera no se confunde con un comando.

    OJO con la barra: el cliente SE LA COME. Al escribir "/rama add Life" lo
    que llega es "rama add Life" pelado, medido en el log del 05/10/2026:

        0x0001 sin esquema (14B): 72 61 6d 61 20 61 64 64 20 4c 69 66 65 00

    Por eso la lista de palabras es la que manda de verdad, y antes solo
    tenia item/give/i/help: ni rama, ni estacion, ni rango entraban nunca.
    Ahora sale de PALABRAS_GM, que esta pegada a los comandos que conoce
    _gm_parsear para que no se vuelvan a separar.
    """
    if not cuerpo:
        return None
    for off in (0, 1, 2, 4):
        if len(cuerpo) <= off:
            continue
        trozo = cuerpo[off:]
        nul = trozo.find(b'\x00')
        if nul >= 0:
            trozo = trozo[:nul]
        trozo = trozo.strip(b'\r\n\t ')
        if not trozo or not all((32 <= b < 127) or b in (9, 10, 13) for b in trozo):
            continue
        t = trozo.decode('ascii').strip()
        if t.startswith('/'):
            return t
        # SIN BARRA la cosa es delicada: este husmeo corre sobre TODOS los
        # paquetes del cliente y, si acierta, se traga el paquete entero.
        # Pasaba justo eso al vender: el 0x0028 lleva ids de instancia, que
        # salen correlativos desde 0x030000, y uno de cada 256 empieza por
        # el byte 0x69 seguido de 0x00 -- o sea la cadena "i", que estaba en
        # PALABRAS_GM como atajo de /item. El paquete se consumia, no se
        # vendia nada y al jugador le salia "usage: /item <id> [qty]" en el
        # chat. Lo mismo le podia pasar a cualquier otro paquete.
        #
        # Asi que sin barra hace falta mucho mas: una palabra de la lista
        # de tres letras o mas, y que el texto sea TODO el cuerpo (lo
        # que venga detras del NUL tiene que ser relleno a ceros). Un
        # comando de verdad cumple las dos; un id de instancia no cumple
        # ninguna. Tres, y no una: /pet y /lvl tienen que entrar, pero la
        # "i" suelta de un id de instancia no.
        primera = (t.lower().split() or [''])[0]
        if len(primera) < 3 or primera not in PALABRAS_GM:
            continue
        resto = cuerpo[off:]
        nul2 = resto.find(b'\x00')
        if nul2 >= 0 and any(resto[nul2:]):
            continue
        return t
    return None


def _gm_parsear(texto: str):
    """('item', id, cantidad), ('help',), ('err', motivo) o None."""
    t = texto.strip()
    if t.startswith('/'):
        t = t[1:]
    partes = t.split()
    if not partes:
        return None
    cmd = partes[0].lower()
    if cmd == 'help':
        return ('help',)
    if cmd in ('sistemas', 'album', 'logros', 'cartas', 'estrellas', 'casa'):
        # /sistemas            el estado de los seis
        # /album <categoria> <valor>   pone valor a mano, para probar
        # /logros              los que cumple ahora mismo
        return ('sistemas', cmd, partes[1:] if len(partes) > 1 else [])
    if cmd in ('rama', 'skill', 'branch'):
        # /rama <fuera> <dentro>  cambia una rama por otra
        # /rama add <dentro>      anade una rama sin quitar ninguna
        #
        # Existe porque la restriccion de "Unable to learn at the same
        # time" (texto 714 de string.xml) es SOLO del selector del
        # cliente: el servidor no comprueba nada al recibir el 0x002F
        # contenedor 10, acepta la pareja que le manden. Desde aqui se
        # elige sin pasar por el selector.
        # OJO: los nombres de rama llevan espacios ("Staff Hit", "Eagle
        # Eye"), asi que no sirve coger partes[1] y partes[2]. Se parte
        # probando todos los cortes, en skills.partir_argumentos_rama.
        import skills as _sk_arg
        _args = _sk_arg.partir_argumentos_rama(' '.join(partes[1:]))
        if _args is None:
            return ('err', 'usage: /rama <fuera|add> <dentro>   '
                           '(por nombre o por numero)')
        return ('rama', _args[0], _args[1])
    if cmd in ('estacion', 'season', 'modo'):
        if len(partes) < 2:
            return ('err', 'usage: /estacion <normal|navidad|halloween|sakura|verano>')
        return ('estacion', partes[1].lower())
    if cmd in ('rango', 'rank'):
        if len(partes) < 2:
            return ('rango', 0)  # 0 = subir +1 rango
        try:
            return ('rango', int(partes[1], 0))
        except ValueError:
            return ('err', 'usage: /rango [1..20]')
    if cmd in ('level', 'lvl', 'lv', 'levelall', 'lvlall',
               'skills', 'spells', 'skillsall', 'learnall', 'skillall', 'skills5', 'skill5',
               'clearskills', 'clearskill',
               'pet', 'mascota'):
        import gm as _gm
        return _gm.parsear(texto)
    if cmd in ('emote', 'e', 'emocion'):
        if len(partes) < 2:
            return ('err', 'usage: /emote <id 0..36> | /emote unlock <id> | /emote unlockall | /emote list')
        sub = partes[1].lower()
        if sub in ('unlockall', 'all'):
            return ('emote_unlockall',)
        if sub == 'list':
            return ('emote_list',)
        if sub in ('unlock', 'learn') and len(partes) >= 3:
            try:
                eid = int(partes[2], 0)
                return ('emote_unlock', eid)
            except ValueError:
                return ('err', 'el id de emote debe ser un numero')
        try:
            emo_id = int(partes[1], 0)
        except ValueError:
            return ('err', 'el id de emote debe ser un numero')
        return ('emote', emo_id)
    if cmd not in ('item', 'give', 'i'):
        return None
    if len(partes) < 2:
        return ('err', 'usage: /item <id> [qty]')
    try:
        iid = int(partes[1], 0)
    except ValueError:
        return ('err', 'el id tiene que ser un numero')
    cant = 1
    if len(partes) >= 3:
        try:
            cant = int(partes[2], 0)
        except ValueError:
            return ('err', 'la cantidad tiene que ser un numero')
    return ('item', iid, cant)


def _probar_gm(ses, cuerpo, addr) -> bool:
    """True si el paquete era un comando de GM y ya se contesto."""
    import clases as _cl
    texto = _gm_texto(cuerpo)
    if not texto:
        return False
    leido = _gm_parsear(texto)
    if leido is None:
        return False
    if leido[0] == 'help':
        ses.enviar(_cl.aviso(
            'GM: /item <id> [qty] | /level <n> | /levelall <n> | /skills [lv] | /skillsall [lv] | /skills5 | /clearskills | '
            '/pet level|exp|path|evolve | /rango [1..20] | '
            '/estacion <normal|navidad|halloween|sakura|verano> | /emote <0..36> | /emote unlock <id> | /emote unlockall | /emote list',
            tipo=0, msg_id=_cl.MSG_TEXTO))
        log.info('[%s] GM help' % (addr,))
        return True
    if leido[0] == 'emote' and ses.personaje:
        import inventario as _iv_emo
        emo_id = max(0, min(36, int(leido[1])))
        if not _iv_emo.puede_usar_emocion(ses.personaje, emo_id):
            ses.enviar(_cl.aviso("You have not unlocked this expression yet.", tipo=0, msg_id=_cl.MSG_TEXTO))
            return True
        import presencia as _pr_emo
        _pr_emo.notificar_emocion(ses, emo_id)
        log.info(f"[{addr}] GM emote {emo_id} reproducido por {ses.personaje.nombre}")
        return True
    if leido[0] == 'emote_unlock' and ses.personaje:
        emo_id = max(0, min(36, int(leido[1])))
        emotes = getattr(ses.personaje, 'emotes', None)
        if emotes is None:
            emotes = set()
            ses.personaje.emotes = emotes
        emotes.add(emo_id)
        if getattr(ses, 'usuario', None):
            cuentas.guardar_emotes(ses.usuario, ses.personaje.char_id, emotes)
        import presencia as _pr_emo
        ses.enviar(
            _cl.aviso(f"Emote {emo_id} unlocked!", tipo=0, msg_id=_cl.MSG_TEXTO),
            _pr_emo.paquete_emotes_desbloqueados(emotes)
        )
        _pr_emo.notificar_emocion(ses, emo_id)
        log.info(f"[{addr}] GM desbloqueo emote {emo_id} para {ses.personaje.nombre}")
        return True
    if leido[0] == 'emote_unlockall' and ses.personaje:
        emotes = getattr(ses.personaje, 'emotes', None)
        if emotes is None:
            emotes = set()
            ses.personaje.emotes = emotes
        for i in range(37):
            emotes.add(i)
        if getattr(ses, 'usuario', None):
            cuentas.guardar_emotes(ses.usuario, ses.personaje.char_id, emotes)
        import presencia as _pr_emo
        ses.enviar(
            _cl.aviso("All 37 emotes unlocked!", tipo=0, msg_id=_cl.MSG_TEXTO),
            _pr_emo.paquete_emotes_desbloqueados(emotes)
        )
        log.info(f"[{addr}] GM desbloqueo todos los emotes para {ses.personaje.nombre}")
        return True
    if leido[0] == 'emote_list' and ses.personaje:
        adquiridos = sorted(getattr(ses.personaje, 'emotes', None) or [])
        ses.enviar(_cl.aviso(f"Basic: 0..11 | Acquired: {adquiridos}", tipo=0, msg_id=_cl.MSG_TEXTO))
        return True
    if leido[0] == 'err':
        ses.enviar(_cl.aviso(leido[1], tipo=0, msg_id=_cl.MSG_TEXTO))
        log.info('[%s] GM %s' % (addr, leido[1]))
        return True
    if leido[0] == 'estacion':
        import cliente_local as _cl_loc
        m_ap = _cl_loc.aplicar_modo_estacion(leido[1])
        ses.enviar(_cl.aviso(f'Estacion cambiada a: {m_ap.upper()} (reentra al mapa para verla)', tipo=0))
        log.info('[%s] GM estacion -> %s' % (addr, m_ap))
        return True
    if leido[0] == 'sistemas' and ses.personaje:
        import album as _alb, logros as _lg, cartas as _ct
        import estrellas as _es, casas as _cs, tesoros as _ts
        _p = ses.personaje
        _que, _args = leido[1], leido[2]
        if getattr(_p, 'album', None) is None:
            _p.album = {}
        if _que == 'album' and len(_args) >= 2:
            _p.album[_args[0]] = int(_args[1])
        _res = _alb.resumen(_p.album)
        _bon = _alb.bonos(_p.album)
        _nuevos = _lg.comprobar(_p, getattr(_p, 'logros', None) or [],
                                stats={'hp_max': getattr(_p, 'hp_max', 0),
                                       'mp_max': getattr(_p, 'mp_max', 0)})
        lineas = [
            'Album: total %d (nv %d), bonos %s'
            % (_res['total']['valor'], _res['total']['nivel'],
               ', '.join('%s %s' % (k, v) for k, v in sorted(_bon.items())[:5]) or '-'),
            'Logros: %d de %d, %d puntos; cumple %d sin reclamar'
            % (len(getattr(_p, 'logros', None) or []), len(_lg.tabla()),
               _lg.puntos_de(getattr(_p, 'logros', None) or []), len(_nuevos)),
            'Cartas: %d de %d, %d estrellas'
            % (_ct.resumen(getattr(_p, 'cartas', None) or [])['total']['tengo'],
               len(_ct.tabla()), _ct.estrellas_de(getattr(_p, 'cartas', None) or [])),
            'Estrellas: %d puestas, bonos %s'
            % (len(getattr(_p, 'estrellas', None) or []),
               _es.bonos(getattr(_p, 'estrellas', None) or []) or '-'),
            'Casa: %d muebles, %d puntos de decoracion'
            % (len((getattr(_p, 'casa', None) or {}).get('muebles') or []),
               _cs.puntos_de((getattr(_p, 'casa', None) or {}).get('muebles') or [])),
            'Tesoros: %d mapas pueden salir en este escenario'
            % len(_ts.en_escena(getattr(_p, 'stage', 0) or 0)),
        ]
        if _que == 'casa' and _args and _args[0].lower() in ('resetball', 'reset_ball', 'ballreset', 'reset'):
            import casas as _cs_rb
            _c_rb = _cs_rb.obtener_o_crear_casa(_p.char_id, _p.nombre, raw_data=getattr(_p, 'casa', None))
            _c_rb.ball_cooldown_until = 0
            _c_rb.ball_active = False
            _c_rb.ball_end_time = 0
            _p.casa = _c_rb.serializar()
            if getattr(ses, 'usuario', None):
                cuentas.guardar_casa(ses.usuario, _p.char_id, _c_rb)
            ses.enviar(_cl.aviso("House ball cooldown has been reset! You can host a ball now.", tipo=7, msg_id=_cl.MSG_TEXTO))
            return True
        if _que == 'logros' and _nuevos:
            for _l in _nuevos:
                _lg.otorgar(getattr(_p, 'logros', None) or [], _l)
            lineas.append('Reclamados %d logros.' % len(_nuevos))
            if getattr(ses, 'usuario', None):
                cuentas.guardar_sistemas(ses.usuario, _p.char_id, _p)
        ses.enviar(*[_cl.aviso(x, tipo=0) for x in lineas])
        log.info('[%s] /%s -> %s' % (addr, _que, ' | '.join(lineas)))
        return True

    if leido[0] == 'rama' and ses.personaje:
        import clases as _cl_rm
        import skills as _sk_rm
        _p = ses.personaje

        def _num_rama(txt):
            """El numero de una rama, por numero o por nombre."""
            t = str(txt).strip()
            if t.isdigit():
                return int(t)
            tl = t.lower()
            for sid, nom in _cl_rm.NOMBRE_RAMA.items():
                if nom.lower() == tl:
                    return sid
            for sid, nom in _cl_rm.NOMBRE_RAMA.items():
                if nom.lower().startswith(tl):
                    return sid
            return 0

        _dentro = _num_rama(leido[2])
        if not _dentro or _dentro not in _cl_rm.NOMBRE_RAMA:
            ses.enviar(_cl.aviso('No conozco la rama "%s".' % leido[2], tipo=0))
            return True
        _habs = list(_p.habilidades or [])
        if any(h[0] == _dentro for h in _habs):
            ses.enviar(_cl.aviso('Ya llevas %s.' % _sk_rm.nombre_rama(_dentro), tipo=0))
            return True
        if not hasattr(_p, 'banco_habilidades') or _p.banco_habilidades is None:
            _p.banco_habilidades = {}
        _nv, _xp = _p.banco_habilidades.get(_dentro, (1, 0))

        _anade = str(leido[1]).lower() in ('add', 'anadir', 'mas', '+')
        if _anade:
            # Una ranura DE MAS, de las tres que se abren por nivel
            # (301, 351 y 401). El tope sale de skills.ranuras_de_habilidad.
            _tope_rm = _sk_rm.ranuras_de_habilidad(getattr(_p, 'nivel', 1) or 1)
            if len(_habs) >= _tope_rm:
                _falta = next((c for c in _sk_rm.NIVELES_RANURA_EXTRA
                               if (getattr(_p, 'nivel', 1) or 1) < c), None)
                ses.enviar(_cl.aviso(
                    'Ya llevas %d ranuras, que es tu tope.%s' % (
                        _tope_rm,
                        (' La siguiente se abre a nivel %d.' % _falta) if _falta else ''),
                    tipo=0))
                return True
            _habs.append((_dentro, _nv, _xp))
            _fuera = 0
        else:
            _fuera = _num_rama(leido[1])
            _pos = next((k for k, h in enumerate(_habs) if h[0] == _fuera), None)
            if _pos is None:
                ses.enviar(_cl.aviso('No llevas la rama "%s".' % leido[1], tipo=0))
                return True
            _p.banco_habilidades[_fuera] = [_habs[_pos][1], _habs[_pos][2]]
            _habs[_pos] = (_dentro, _nv, _xp)

        _p.habilidades = _habs
        _p.class_id = _sk_rm.calcular_class_id([h[0] for h in _p.habilidades])
        _salida_rm = [
            _cl.aviso(_sk_rm.nombre_rama(_dentro), tipo=7, msg_id=424),
            _stats_ses(ses),
            _cl.arbol(_p.habilidades, banco=_p.banco_habilidades),
        ]
        if _fuera:
            _salida_rm.insert(1, _cl.aviso(_sk_rm.nombre_rama(_fuera), tipo=7, msg_id=423))
        for _nid, _nom in (_sk_rm.hechizos_de_rama(_dentro) or []):
            _salida_rm.append(struct.pack('<HIB', 0x001D, _p.entity_id, 1)
                              + struct.pack('<BII', _cl.KIND_HECHIZO, _nid, 1))
            _salida_rm.append(_cl.aviso(_nom, tipo=7, msg_id=_cl.MSG_HECHIZO))
        ses.enviar(*_salida_rm)
        if getattr(ses, 'usuario', None):
            cuentas.guardar_habilidades(ses.usuario, _p.char_id, _p.habilidades)
            cuentas.guardar_clase(ses.usuario, _p.char_id, _p.class_id)
            cuentas.guardar_banco_habilidades(ses.usuario, _p.char_id, _p.banco_habilidades)
        log.info('[%s] /rama: %s -> %s (%d ramas, clase %d)'
                 % (addr, _sk_rm.nombre_rama(_fuera) if _fuera else 'add',
                    _sk_rm.nombre_rama(_dentro), len(_habs), _p.class_id))
        return True

    if leido[0] == 'rango' and ses.personaje:
        import combate as _cb
        _rk_arg = leido[1]
        _rk_act = max(1, min(20, int(getattr(ses.personaje, 'rango', 1) or 1)))
        _rk_new = min(20, _rk_act + 1) if _rk_arg <= 0 else max(1, min(20, _rk_arg))
        ses.personaje.rango = _rk_new
        _tit = _cb.NOMBRES_RANGO.get(_rk_new, f'Rank {_rk_new}')
        # Los creditos que pide el rango nuevo, de la tabla de level.xml.
        # Con max() para no quitarle a nadie los que ya llevaba de sobra.
        _cred_rk = max(int(getattr(ses.personaje, 'creditos', 0) or 0),
                       _cb.creditos_de_rango(_rk_new))
        ses.personaje.creditos = _cred_rk
            # NO se manda efecto visual aqui. El 251 que habia no existe:
            # los efectos magicos viven en shape/magic/<n>/ y de 224 que
            # hay, el 251 no esta, asi que el cliente lo tiraba.
            #
            # La banderola la dibuja el CLIENTE solo al recibir KIND_RANGO,
            # y usa la vieja de common.obd secuencia 71,
            # "升級效果-LEVEL UP旗幟(階級)", que reaprovecha el arte del
            # subir de nivel (lvup02-7/8/9) en verde. La buena es la 743,
            # "升級效果-PEERAGE UP旗幟". Cambiarla es tocar el cliente, no
            # el servidor: desde aqui no se elige.
        ses.enviar(
            _cb.atributo(ses.personaje.entity_id, _rk_new, _cb.KIND_RANGO),
            _cb.atributo(ses.personaje.entity_id, _cred_rk, _cb.KIND_CREDITO),
            _cb.efecto_level_up(ses.personaje.entity_id, es_rango=True),
            _cl.aviso(f'Rank promoted to Lv.{_rk_new}: {_tit}!', tipo=0),
        )
        if getattr(ses, 'usuario', None):
            cuentas.guardar_rango(ses.usuario, ses.personaje.char_id, _rk_new, _cred_rk)
        log.info('[%s] GM rango -> %d (%s)' % (addr, _rk_new, _tit))
        return True
    if leido[0] in ('level', 'levelall', 'skills', 'skillsall', 'skills5', 'clearskills', 'skilllevel', 'pet', 'ball'):
        import gm as _gm
        msg = _gm.aplicar(ses, leido)
        log.info('[%s] GM %s' % (addr, msg))
        return True
    _, iid, cant = leido
    msg = _gm_dar_item(ses, iid, cant)
    if not msg.startswith('dado '):
        ses.enviar(_cl.aviso(msg, tipo=0, msg_id=_cl.MSG_TEXTO))
    log.info('[%s] GM %s' % (addr, msg))
    return True


def _pet_ficha(ses, ranura):
    """La ficha guardada de la mascota de esa casilla, creandola si no hay.

    Los stats de combate salen de petattrib segun su sprite y nivel, y las
    3 habilidades salen de petskill.xml.
    """
    import inventario as inv
    import mascotas as _ms
    item_id = ses.inventario.get(ranura)
    if not item_id:
        return None
    d = inv.datos_mascota(item_id)
    if not hasattr(ses.personaje, 'mascotas') or not isinstance(ses.personaje.mascotas, dict):
        ses.personaje.mascotas = {}

    # Buscar si ya existe la ficha de esta ranura
    f = ses.personaje.mascotas.get(str(ranura)) or ses.personaje.mascotas.get(ranura)
    if not f:
        legacy_m = getattr(ses.personaje, 'mascota', None)
        if legacy_m and isinstance(legacy_m, dict) and (legacy_m.get('ranura') == ranura or (legacy_m.get('ranura') is None and legacy_m.get('item') == item_id)):
            f = legacy_m

    if f and f.get('item') and int(f.get('item')) != int(item_id):
        # Si por algun motivo habia otra especie guardada en esta ranura y no evoluciono de ella, validar sprite
        pass

    if f:
        f['ranura'] = ranura
        f['item'] = item_id
        f['instancia'] = 1000 + int(ranura)
        sp_cur = int(f.get('sprite') or 0)
        if sp_cur <= 0 or sp_cur >= 35001:
            f['sprite'] = int(d.get('sprite') or 3049)
        if not f.get('tipo'):
            f['tipo'] = _ms.ficha_de_sprite(f.get('sprite')).get('tipo', 0) or int(d.get('tipo') or 0)
        if not f.get('skills'):
            f['skills'] = list(_ms.skills_de(f.get('sprite'), f.get('nivel', 1)))
        if 'estrellas' not in f or not f['estrellas']:
            f['estrellas'] = max(1, int(d.get('estrellas') or 1))
        ses.personaje.mascotas[str(ranura)] = f
        cur_active = getattr(ses.personaje, 'mascota', None)
        if not cur_active or not cur_active.get('fuera') or cur_active.get('ranura') == ranura:
            ses.personaje.mascota = f
        return f

    import configuracion as _cf
    f = _ms.recien_nacida(d['nombre'], d['sprite'],
                          nivel=max(1, getattr(_cf, 'MASCOTA_NIVEL_INICIAL', 1)),
                          estrellas=max(1, int(d.get('estrellas') or 1)))
    f['ranura'] = ranura
    f['item'] = item_id
    f['instancia'] = 1000 + int(ranura)
    f['fuera'] = False
    ses.personaje.mascotas[str(ranura)] = f
    cur_active = getattr(ses.personaje, 'mascota', None)
    if not cur_active or not cur_active.get('fuera') or cur_active.get('ranura') == ranura:
        ses.personaje.mascota = f
    return f


def _pet_subir(ficha, nivel):
    """Pone la mascota a ese nivel y le recalcula los stats.

    Los stats no se guardan sueltos: se vuelven a sacar de petattrib con el
    nivel nuevo, que es como los da el juego.
    """
    import mascotas as _ms
    ficha['nivel'] = max(1, int(nivel))
    ficha.update(_ms.stats_de(ficha.get('sprite'), ficha['nivel']))
    return ficha


def _pet_alternar(ses, addr, ranura):
    """Saca la mascota al mundo, o la guarda si ya estaba fuera.

    Secuencia medida en Celestia (mundo_143747 pkts 43290..43300 y 44011..44016):
      Al sacar:
        1. 0x001D (yo, kind=0x2A, pet_eid)
        2. 0x0013 (pet_eid, kind=0x3F, 0)
        3. 0x0065 (armar(f))
        4. 0x001B (actualizar_ranura con fuera=1 e instancia=(inst, inst))
        5. 0x0050 (entidad_mundo con x=p.tile_x, y=p.tile_y, instancia=(inst, inst))
        6. 0x0065 (armar(f), ya con pet_inst1/pet_inst2 fijados por el 0x0050)
        7. 0x0013 (pet_eid, kind=0x00, hp)
      Al guardar:
        1. 0x0007 (quitar(pet_eid))
        2. 0x001D (paquete_orden(yo, 0x0B))
        3. 0x001D (enlazar(yo, 0))
        4. 0x001B (actualizar_ranura con fuera=0)
    """
    import struct as _st
    import combate as _cb
    import mascotas as _ms
    f = _pet_ficha(ses, ranura)
    f['fuera'] = not f.get('fuera')
    p = ses.personaje
    if not f['fuera']:
        if f.get('entidad'):
            ses.enviar(_ms.quitar(f['entidad']))
            ses.enviar(_ms.paquete_orden(p.entity_id, 0x0B))
            ses.enviar(_ms.enlazar(p.entity_id, 0))
            ses.enviar(_ms.quitar(f['entidad']))
            import presencia as _pr
            _pr.notificar_mascota_despawn(ses, f['entidad'])
        f['entidad'] = None
        ses.pet_entity_id = None
        log.info('[%s] mascota guardada: %s' % (addr, f.get('nombre')))
        ses.enviar(*_refrescar(ses, [ranura]))
        _guardar_bolsa(ses, p.char_id)
        return

    # Despawnear cualquier otra mascota que estuviera fuera previamente
    old_eid = getattr(ses, 'pet_entity_id', None)
    if old_eid:
        ses.enviar(_ms.quitar(old_eid))
        ses.enviar(_ms.paquete_orden(p.entity_id, 0x0B))
        ses.enviar(_ms.enlazar(p.entity_id, 0))
        ses.enviar(_ms.quitar(old_eid))
        import presencia as _pr
        _pr.notificar_mascota_despawn(ses, old_eid)
        ses.pet_entity_id = None

    if getattr(p, 'mascotas', None):
        for _r_str, _other_pet in p.mascotas.items():
            if _r_str != str(ranura) and isinstance(_other_pet, dict) and _other_pet.get('fuera'):
                _other_pet['fuera'] = False
                _other_pet['entidad'] = None
                _other_r = _other_pet.get('ranura')
                if _other_r is not None:
                    ses.enviar(*_refrescar(ses, [_other_r]))

    # Cada vez que sale es una entidad NUEVA
    p.mascota = f
    f['entidad'] = _pet_siguiente_entidad(ses)
    f['instancia'] = int(f.get('instancia') or (1000 + int(ranura)))
    ses.pet_entity_id = f['entidad']
    px = getattr(p, 'tile_x', 0)
    py = getattr(p, 'tile_y', 0)
    f['x'] = px
    f['y'] = py
    f['proximo_paso'] = 0.0
    ses.pet_tile = [px, py]
    est = dict(f)
    est.update({'x': px, 'y': py,
                'dueno': p.entity_id, 'dueno_nombre': p.nombre,
                'tipo': f.get('tipo', 0)})
    pkgs_spawn = [
        _ms.enlazar(p.entity_id, f['entidad']),
        _st.pack('<HIBBI', 0x0013, f['entidad'], 1, 0x3F, 0),
        _ms.armar(f),
        *_refrescar(ses, [ranura]),
        _ms.entidad_mundo(_pet_plantilla(), est),
        _ms.armar(f),
        _cb.atributo(f['entidad'], _ms.hp_eff(f), _cb.KIND_HP)
    ]
    if int(f.get('saciedad', 0)) > 100:
        pkgs_spawn.append(_st.pack('<HIBBII', 0x001D, f['entidad'], 1, 4, 3796, max(60000, (int(f['saciedad']) - 100) * 60000)))
    ses.enviar(*pkgs_spawn)
    import presencia as _pr
    _pr.notificar_mascota_spawn(ses)
    _guardar_bolsa(ses, p.char_id)
    log.info('[%s] mascota fuera: %s (entidad %d en %d,%d)'
             % (addr, f.get('nombre'), f['entidad'], px, py))


_PET_ENT = [0x105000]


def _pet_siguiente_entidad(ses):
    _PET_ENT[0] += 1
    return _PET_ENT[0]


_PET_PL = [None]


def _pet_plantilla():
    if _PET_PL[0] is None:
        import json as _json
        import inventario as _iv
        _PET_PL[0] = bytes.fromhex(_json.loads(
            _iv.PLANTILLA_INI.read_text(encoding='utf-8'))['mascota_mundo'])
    return _PET_PL[0]


def _usar_mejora(ses, addr, ranura, objetivo) -> bool:
    """Usa un objeto de mejora sobre la pieza de otra casilla.

    Devuelve True si el paquete era eso y ya se contesto.

    Lo que manda el servidor real, medido el 29/09/2026 sobre una montura:
    la entrada del equipo actualizada (0x001B), el cartel del resultado
    (0x000D), la pila del objeto gastada (0x001B), los stats (0x0042) y el
    peso (0x0013). Los carteles son de string.xml:

        1613  "Succeed in intensifying %s."      mortero o pienso, con exito
        1614  "%s Failed to intensify"           fallo
        2137  "%s Change the attribute succeeded."   el martillo verde

    En el de exito el %s es el nombre CON su "+N" pegado detras, tal cual:
    "Onyx- Galactic Moped+4".
    """
    import clases as _cl
    import inventario as _iv
    import mejoras as _mj
    import configuracion as _cf

    item = ses.inventario.get(ranura)
    clase = _mj.clase_de(item)
    if not clase:
        return False
    pieza = ses.inventario.get(objetivo)
    if not pieza:
        return False

    p = ses.personaje
    if getattr(p, 'mejoras', None) is None:
        p.mejoras = {}
    nivel_pieza = _iv.nivel_de_item(pieza) if hasattr(_iv, 'nivel_de_item') else 0
    tipo = _tipo_de_pieza(pieza, objetivo)
    seguro = getattr(_cf, 'MEJORAS_SIEMPRE_EXITO', False)
    _buffs_eilian = getattr(p, 'buffs', {}) or {}
    blessing = _buffs_eilian.get('eilian_blessing') or next(
        (_buffs_eilian[bid] for bid in (2295, 2294, 2293, 2292) if bid in _buffs_eilian), {})
    if not isinstance(blessing, dict) or blessing.get('fin', 0) <= time.time():
        blessing = {}

    if _iv.es_mascota(pieza):
        import mascotas as _ms_app
        f_pet = _pet_ficha(ses, objetivo)
        if f_pet:
            nom_it_l = (_nombre_item(item) or '').lower()
            if 'star-up' in nom_it_l or 'star up' in nom_it_l or item in (5902, 5903, 3379):
                incremento = 10 if ('card' in nom_it_l or item in (5902, 5903)) else 1
                nueva_st = _ms_app.subir_estrella(f_pet, incremento)
                veces_pet = int(f_pet.get('mejoras') or 0)
                ok, msg = True, 'star level -> %0.1f' % (nueva_st / 10.0)
            else:
                ok, veces_pet = _ms_app.mejorar_mascota(f_pet)
                msg = 'mejora mascota +%d (star %0.1f)' % (veces_pet, f_pet.get('estrellas', 1) / 10.0) if ok else 'tope de 15 mejoras alcanzado'
        else:
            ok, msg = False, 'mascota no encontrada'
    elif clase == 'verde':
        # El martillo verde no sube nada: REEMPLAZA los atributos extra por
        # otros nuevos, sorteados dentro de sus rangos. Los rangos son los
        # que el cliente enseña en su cuadro; con la bandera puesta sale el
        # maximo de todos a la vez.
        est = p.mejoras.setdefault(int(objetivo), {'veces': 0, 'gemas': [],
                                                   'extra': {}, 'huecos': 0})
        est.setdefault('veces', 0)
        est.setdefault('gemas', [])
        est.setdefault('extra', {})
        est.setdefault('huecos', 0)
        tope_v = _mj.tope_nivel(item)
        if tope_v and tope_v < 400 and nivel_pieza > tope_v:
            ok, msg = False, 'sirve hasta nivel %d' % tope_v
        else:
            # Los rangos salen de la PIEZA que se mejora, no de una tabla
            # fija: que stats da lo dice su categoria (un arma nunca da
            # defensa) y hasta cuanto lo dice su nivel. Aqui seguia la tabla
            # plana de antes, asi que una montura de nivel 22 ofrecia lo
            # mismo que una de 70.
            est['extra'] = _mj.tirar_verde(
                _mj.rangos_verde(pieza),
                todos=getattr(_cf, 'MARTILLO_VERDE_TODOS_LOS_STATS', False))
            ok, msg = True, 'atributos nuevos: %s' % est['extra']
    elif clase == 'perforar':
        ok, msg = _mj.perforar(p.mejoras, objetivo, item, nivel_pieza, tipo,
                               exito_seguro=seguro,
                               bono_primer_hueco=blessing.get('pierce_first_pct', 0) / 100.0)
    elif clase in ('gema', 'gema_mascota'):
        ok, msg = _mj.engarzar(p.mejoras, objetivo, item, nivel_pieza, tipo)
    else:
        ok, msg = _mj.aplicar(p.mejoras, objetivo, item, nivel_pieza, tipo,
                              exito_seguro=seguro,
                              bono_cuarta_mejora=blessing.get('enhance_fourth_pct', 0) / 100.0)

    nombre = _nombre_item(pieza)
    veces = (p.mejoras.get(objetivo) or {}).get('veces', 0)
    if clase == 'perforar':
        if ok:
            msg_id = _mj.MSG_HUECO_OK
        elif 'nivel' in msg:
            msg_id = _mj.MSG_HUECO_NIVEL
        elif 'huecos' in msg:
            msg_id = _mj.MSG_HUECO_TOPE
        else:
            msg_id = _mj.MSG_HUECO_FALLO
        cartel = _cl.aviso(nombre, tipo=7, msg_id=msg_id)
    elif ok and _iv.es_mascota(pieza):
        _v_pet = locals().get('veces_pet', 0)
        cartel = _cl.aviso('%s+%d' % (nombre, _v_pet) if _v_pet > 0 else nombre,
                           tipo=7, msg_id=_mj.MSG_MEJORA_OK)
    elif ok and clase in ('mortero', 'pienso_montura', 'pienso_mascota'):
        # El %s del 1613 lleva el "+N" pegado: "Onyx- Galactic Moped+4".
        cartel = _cl.aviso('%s+%d' % (nombre, veces), tipo=7,
                           msg_id=_mj.MSG_MEJORA_OK)
    elif ok:
        cartel = _cl.aviso(nombre, tipo=7, msg_id=_mj.MSG_ATRIBUTOS_OK)
    else:
        cartel = _cl.aviso(nombre, tipo=7, msg_id=_mj.MSG_MEJORA_FALLO)

    # El objeto se gasta pase lo que pase: todas las descripciones dicen que
    # un fallo no rompe la pieza pero si consume el intento.
    quedan = ses.cantidades.get(ranura, 1) - 1
    if quedan > 0:
        ses.cantidades[ranura] = quedan
    else:
        ses.inventario.pop(ranura, None)
        ses.cantidades.pop(ranura, None)

    salida = list(_refrescar(ses, [objetivo]))
    salida.append(cartel)
    salida.extend(_refrescar(ses, [ranura]))
    salida.append(_stats_ses(ses))

    # Solo mandar 0x0065 si la mascota mejorada esta invocada en el mundo
    if _iv.es_mascota(pieza):
        import mascotas as _ms_app
        import combate as _cb_app
        import struct as _st_app
        f_pet = _pet_ficha(ses, objetivo)
        if f_pet:
            if getattr(p, 'mascotas', None) is not None:
                p.mascotas[str(objetivo)] = f_pet
            if f_pet.get('fuera') and f_pet.get('entidad'):
                pet_eid_m = int(f_pet['entidad'])
                st_m = max(1, int(f_pet.get('estrellas') or _ms_app.calcular_estrellas_total(_ms_app.bonos_de_ficha(f_pet))))
                salida.append(_ms_app.armar(f_pet))
                salida.append(_cb_app.atributo(pet_eid_m, _ms_app.hp_eff(f_pet), _cb_app.KIND_HP))
                salida.append(_st_app.pack('<HIBBI', 0x0013, pet_eid_m, 1, 0x42, st_m))
                if int(f_pet.get('saciedad', 0)) > 100:
                    salida.append(_st_app.pack('<HIBBII', 0x001D, pet_eid_m, 1, 4, 3796, max(60000, (int(f_pet['saciedad']) - 100) * 60000)))
            if getattr(ses, 'usuario', None):
                cuentas.guardar_mascota(ses.usuario, p.char_id, f_pet, getattr(p, 'mascotas', None))

    ses.enviar(*salida)
    _guardar_bolsa(ses, p.char_id)
    # Y las mejoras, que iban SOLO en memoria: al reconectar se perdia todo
    # lo mejorado. Se guardan aqui, que es el unico sitio que las toca.
    if getattr(ses, 'usuario', None):
        cuentas.guardar_mejoras(ses.usuario, p.char_id, p.mejoras)
    log.info('[%s] mejora: %s (%s) sobre %s -> %s'
             % (addr, _nombre_item(item), clase, nombre, msg))
    return True


def _tipo_de_pieza(item_id, ranura):
    """'arma', 'armadura', 'escudo', 'montura' o 'mascota'."""
    import inventario as _iv
    if _iv.es_mascota(item_id):
        return 'mascota'
    cat = _iv.categoria_item(item_id)
    if cat in ('座騎', '機甲'):
        return 'montura'
    r = _iv.ranura_equipo_de(item_id) or ranura
    if r in (10, 174):
        return 'montura'
    if r in (3, 169):
        return 'arma'
    if r in (4, 170):
        return 'arma' if _iv.es_arma_dual(item_id) else 'escudo'
    return 'armadura'


def _coste_vida(ses, yo, mag, addr=''):
    """Cobra la vida que cuesta una habilidad de las que dan SP.

    El campo 'hp' de esas habilidades es un PORCENTAJE del maximo, no un
    numero plano, y viene en negativo. Lo dicen sus descripciones:
      Bloody Storm V   hp = -9   -> "Reduce 9% HP, Increase 1000SP"
      Hot Blooded V    hp = -5   -> "Reduces HP to gain 2 SP"
    El codigo lo trataba como una curacion plana, asi que en vez de
    costarte el 9% te curaba diez puntos.
    """
    import combate as _cb
    pct = (mag or {}).get('hp', 0)
    if pct >= 0 or not (mag or {}).get('sp_gana') or not ses.personaje:
        return []
    tope = _vida_max(ses.personaje)
    vida = getattr(ses.personaje, 'hp', None)
    if not tope or vida is None:
        return []
    coste = max(1, int(round(tope * abs(pct) / 100.0)))
    # Nunca mata: como poco deja un punto.
    coste = min(coste, max(0, vida - 1))
    if coste <= 0:
        return []
    ses.personaje.hp -= coste
    log.info('[%s] %s cuesta %d de vida (%d%% de %d)'
             % (addr, mag.get('nombre', '?'), coste, abs(pct), tope))
    return [_cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP),
            _cb.numero_flotante(yo, coste, _cb.TIPO_COSTE_VIDA)]


def _u32(v) -> int:
    """Recorta un numero al rango de un campo de 32 bits.

    La experiencia de un nivel alto son 25.478.672.000 y no cabe. Cada vez
    que uno de estos se escapaba, el struct.error subia hasta el bucle de
    asyncio y tiraba la sesion: al jugador se le caia el juego al matar un
    bicho o al entrar.
    """
    try:
        return max(0, min(int(v or 0), 0xFFFFFFFF))
    except (TypeError, ValueError):
        return 0


def _sp_por_golpe(ses) -> int:
    """SP de un impacto segun el rango de Reserve."""
    import combate as _cb
    res_rank = 1
    p = getattr(ses, 'personaje', None)
    for h in getattr(p, 'habilidades', None) or []:
        if (h[0] if isinstance(h, (list, tuple)) else h) == 15:
            res_rank = h[1] if isinstance(h, (list, tuple)) and len(h) > 1 else 1
            break
    return _cb.SP_POR_GOLPE * (2 + res_rank // 50)


def _sumar_sp(ses, yo, cantidad, addr='') -> int:
    """Suma SP y refresca las barras visibles al cruzar una lampara."""
    import combate as _cb, inventario as _iv
    p = getattr(ses, 'personaje', None)
    if not p:
        return 0
    _, tope = _max_sp_info(p)
    antes = max(0, int(getattr(ses, 'sp', 0) or 0))
    despues = min(tope, antes + max(0, int(cantidad or 0)))
    if despues == antes:
        return 0
    ses.sp = despues
    p.sp = despues
    paquetes = [_cb.atributo(yo, despues, _cb.KIND_SP)]
    if antes // _cb.SP_POR_LAMPARA != despues // _cb.SP_POR_LAMPARA:
        bars, _ = _max_sp_info(p)
        paquetes.append(_iv.stats(
            getattr(ses, 'inventario', None), getattr(p, 'habilidades', None),
            hp=p.hp, hp_max=p.hp_max, mp=p.mp, mp_max=p.mp_max,
            oro=getattr(ses, 'oro', getattr(p, 'oro', 0)),
            buffs=getattr(p, 'buffs', None), sp=despues, sp_max=bars,
            mejoras=_mejoras_de(ses)))
    ses.enviar(*paquetes)
    log.debug('[%s] SP %d -> %d (+%d)', addr, antes, despues, despues - antes)
    return despues - antes


def _dar_sp(ses, yo, mag, addr=''):
    """Suma el SP que REGALA una habilidad, si es que regala alguno.

    Son dos columnas distintas del hechizo y se llamaban igual:
        消耗SP燈   lo que CUESTA   (Strangle Strike V: 2000, o sea 2 lamparas)
        SP         lo que DA       (Bloody Storm: 1000, Energy Recharge: 500
                                    a 2000 a cambio de vida)
    Solo se leia la primera, asi que un guerrero no tenia de donde sacar SP
    salvo pegando, y los pergaminos y los buffs de recarga no hacian nada.
    """
    import combate as _cb
    da = (mag or {}).get('sp_gana', 0)
    # Se apunta SIEMPRE, tambien cuando no da nada: asi el log dice si la
    # habilidad llego hasta aqui o si se quedo por el camino, que es justo
    # lo que no se sabia.
    log.debug('[%s] _dar_sp(%s): sp_gana=%s sp_actual=%s'
              % (addr, (mag or {}).get('nombre', '?'), da,
                 getattr(ses, 'sp', None)))
    if not getattr(ses, 'personaje', None):
        return
    antes = max(0, int(getattr(ses, 'sp', 0) or 0))
    ganado = 0
    # Si el SP viene del hechizo encadenado, lleva su probabilidad (轉嫁機率).
    _prob = int((mag or {}).get('sp_gana_prob', 100) or 100)
    if da > 0 and _prob < 100 and random.randint(1, 100) > _prob:
        da = 0
    if da > 0:
        for _p in _coste_vida(ses, yo, mag, addr):
            ses.enviar(_p)
        ganado = _sumar_sp(ses, yo, da, addr)
        if not ganado:
            ses.enviar(_cb.atributo(yo, getattr(ses, 'sp', 0) or 0,
                                    _cb.KIND_SP), _stats_ses(ses))
    if ganado:
        log.info('[%s] %s da %d de SP: %d -> %d'
                 % (addr, mag.get('nombre', '?'), ganado, antes, ses.sp))


# El tope de lamparas son DIEZ. Reserve da una cada 25 niveles empezando
# desde dos, lo que a nivel 300 daria catorce, pero el juego no pasa de
# diez. Sin este tope la barra pedia 14.000 puntos para llenarse.
MAX_LAMPARAS_SP = 10


def _max_sp_info(p):
    """Devuelve (lamparas, puntos maximos). Una lampara son 1000 puntos.

    Reserve (15) da una lampara cada 25 niveles sobre las dos de partida,
    con el tope de MAX_LAMPARAS_SP.
    """
    res_rank = 1
    if p and getattr(p, 'habilidades', None):
        for h in p.habilidades:
            sid = h[0] if isinstance(h, (list, tuple)) else h
            if sid == 15:
                res_rank = h[1] if isinstance(h, (list, tuple)) and len(h) > 1 else 1
                break
    bars = min(MAX_LAMPARAS_SP, 2 + (res_rank // 25))
    return bars, bars * 1000


def _recuperar_al_matar(ses, yo, mag, addr=''):
    """Lo que devuelven Gnash y compania CUANDO el golpe mata.

    No es el robo de Forbidden Curse, que saca un porcentaje del dano en
    cada golpe: esto solo entra si el objetivo muere, y el porcentaje es
    sobre el MAXIMO del que lanza. Gnash I-IV dan 10% de HP y de MP, y el
    V un 15%, que es lo que dice la wiki.

    Devuelve los sub-mensajes, para que quien mate los mande con el resto.
    """
    import combate as _cb
    if not ses.personaje or not mag:
        return []
    hp_pct = mag.get('al_matar_hp_pct', 0) or 0
    mp_pct = mag.get('al_matar_mp_pct', 0) or 0
    if not hp_pct and not mp_pct:
        return []
    fuera = []
    p = ses.personaje
    if hp_pct:
        tope = _vida_max(p)
        gana = max(1, int(round(tope * hp_pct / 100.0)))
        antes = p.hp
        p.hp = min(tope, p.hp + gana)
        if p.hp != antes:
            fuera.append(_cb.atributo(yo, p.hp, _cb.KIND_HP))
            fuera.append(_cb.numero_flotante(yo, p.hp - antes, _cb.TIPO_CURA_HP))
    if mp_pct:
        tope = _mana_max(p, getattr(ses, 'inventario', None))
        gana = max(1, int(round(tope * mp_pct / 100.0)))
        antes = p.mp
        p.mp = min(tope, p.mp + gana)
        if p.mp != antes:
            fuera.append(_cb.atributo(yo, p.mp, _cb.KIND_MP))
            fuera.append(_cb.numero_flotante(yo, p.mp - antes, _cb.TIPO_CURA_MP))
    if fuera:
        log.info('[%s] %s al matar: +%d%% HP, +%d%% MP (HP %d, MP %d)'
                 % (addr, mag.get('nombre', '?'), hp_pct, mp_pct, p.hp, p.mp))
    return fuera


def _grupo_en_sala(ses):
    """Los del grupo de ese jugador que estan en su misma sala (el incluido)."""
    try:
        import equipos as _eq_g
        presentes = [ses] + _companeros(ses)
        return [s for s in _eq_g.grupo_de(ses) if s in presentes] or [ses]
    except Exception:
        return [ses]


def _repartir_muerte(ses, m):
    """Quien se lleva que cuando muere un bicho: [(sesion, fraccion, botin)].

    Como lo describio el usuario, jugando en el oficial:
      * en GRUPO, la exp y el oro se dividen entre los del grupo que esten en
        la sala, y el botin le toca a uno al azar;
      * SIN grupo, si pegaron varios, la exp y el oro van segun el dano que
        hizo cada uno y el botin se lo lleva el que mas pego.
    El dano por jugador lo apunta Monstruo.registrar_dano (dano_por, por
    char_id) con combate.ATACANTE, que es la sesion que se esta atendiendo.
    """
    presentes = [ses] + _companeros(ses)
    por_cid = {int(s.personaje.char_id): s for s in presentes if getattr(s, 'personaje', None)}
    dano = {int(c): int(d) for c, d in (getattr(m, 'dano_por', None) or {}).items()
            if int(c) in por_cid and int(d) > 0}
    m.dano_por = {}
    grupo = _grupo_en_sala(ses)
    if len(grupo) > 1:
        quien = random.choice(grupo)
        return [(s, 1.0 / len(grupo), s is quien) for s in grupo]
    if ses.personaje and int(ses.personaje.char_id) not in dano:
        dano[int(ses.personaje.char_id)] = 1
    if len(dano) > 1:
        total = float(sum(dano.values()))
        mejor = max(dano, key=dano.get)
        return [(por_cid[c], d / total, c == mejor) for c, d in dano.items()]
    return [(ses, 1.0, True)]


# =========================================================================
# INVOCACION DE ELEMENTAL LORDS EN PLAYGROUNDS (East 42 y West 43)
# =========================================================================
STAGES_PLAYGROUND = {42, 43}

ELFOS_A_LORDS = {
    1: (15, 'Wind Lord'),
    2: (16, 'Fire Lord'),
    3: (17, 'Water Lord'),
    4: (18, 'Earth Lord'),
}

FRASES_LORDS_SPAWN = {
    15: "Feel the wrath of the howling gale!",
    16: "Tremble before the blazing inferno!",
    17: "Drown in the depths of the icy tide!",
    18: "The ancient earth trembles with my fury!",
}

FRASES_LORDS_DEFEAT = {
    15: "The Wind Lord has been dispelled into the breeze!",
    16: "The Fire Lord's flames have been extinguished!",
    17: "The Water Lord has dissolved back into the tide!",
    18: "The Earth Lord has crumbled to dust!",
}

_SIG_LORD_PLAYGROUND = [97_000_000]


def _obtener_conteo_elfos(ses):
    """Devuelve el diccionario de bajas de elfos para la sala compartida o la sesion."""
    sala = _sala_de(ses)
    if sala is not None:
        if not hasattr(sala, 'conteo_elfos'):
            sala.conteo_elfos = {}
        return sala.conteo_elfos
    if not hasattr(ses, 'conteo_elfos_playground'):
        ses.conteo_elfos_playground = {}
    return ses.conteo_elfos_playground


def _invocar_lord_playground(ses, lord_type: int, lord_nombre: str, m_muerto, addr):
    """Genera e invoca al Elemental Lord en la posicion donde murio el elfo."""
    import combate as _cb
    import login as _lg
    import clases as _cl

    st = ses.personaje.stage if ses.personaje else 42
    nombre_mapa = {42: 'East Playground', 43: 'West Playground'}.get(st, f'Playground ({st})')

    orig_x, orig_y = m_muerto.tile_x, m_muerto.tile_y
    spawn_pos = (orig_x, orig_y)
    if not _transitable.se_pisa(st, orig_x, orig_y):
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            nx, ny = orig_x + dx, orig_y + dy
            if _transitable.se_pisa(st, nx, ny):
                spawn_pos = (nx, ny)
                break

    _SIG_LORD_PLAYGROUND[0] += 1
    lord_eid = _SIG_LORD_PLAYGROUND[0]

    nombre, sprite = _monstruo_bd(lord_type)
    if not nombre or nombre == '?':
        nombre = lord_nombre

    lord = _cb.Monstruo(lord_eid, lord_type, nombre, list(spawn_pos), sprite, stage=st)
    lord.generado = True
    lord.es_lord_playground = True

    if ses.monstruos is None:
        ses.monstruos = {}
    ses.monstruos[lord_eid] = lord

    sala = _sala_de(ses)
    if sala is not None and getattr(sala, 'monstruos', None) is not None:
        sala.monstruos[lord_eid] = lord

    sp_pkg = _lg._npc_spawn(lord_eid, lord_type, nombre, spawn_pos, sprite=sprite, klass=1)

    aviso_texto = f"The {nombre} has appeared in {nombre_mapa} ({spawn_pos[0]}, {spawn_pos[1]})!"
    aviso_pkg = _cl.aviso(aviso_texto, tipo=0, msg_id=_cl.MSG_TEXTO)

    frase_lord = FRASES_LORDS_SPAWN.get(lord_type, "Feel the elemental power!")
    chat_pkg = _decir(lord_eid, nombre, frase_lord)

    paquetes = [sp_pkg, aviso_pkg, chat_pkg]
    ses.enviar_inmediato(*paquetes)
    for comp in _companeros(ses):
        try:
            comp.enviar_inmediato(*paquetes)
        except Exception:
            pass

    log.info(f"[{addr}] ¡{nombre} invocado en {nombre_mapa} {spawn_pos} (eid={lord_eid})!")
    return lord


def _procesar_baja_elfo_playground(ses, m, addr):
    """Cuenta bajas de Elfos elementales en Playground (42/43) e invoca al Lord correspondiente."""
    if not ses.personaje:
        return
    st = getattr(ses.personaje, 'stage', None)
    if st not in STAGES_PLAYGROUND:
        return
    if m.npc_type not in ELFOS_A_LORDS:
        return

    import configuracion as _cfg
    kills_necesarias = max(1, int(getattr(_cfg, 'KILLS_ELFOS_PARA_LORD', 10)))
    max_activos = max(1, int(getattr(_cfg, 'MAX_LORDS_ACTIVOS_POR_ELEMENTO', 1)))

    lord_type, lord_nombre = ELFOS_A_LORDS[m.npc_type]

    monstruos_mapa = ses.monstruos or {}
    activos = sum(
        1 for b in monstruos_mapa.values()
        if getattr(b, 'npc_type', None) == lord_type and getattr(b, 'vivo', False)
    )

    conteo = _obtener_conteo_elfos(ses)

    if activos >= max_activos:
        log.info(f"[{addr}] Elfo {m.nombre} derrotado en stage {st}, pero ya hay {activos} {lord_nombre} activo(s).")
        conteo[m.npc_type] = min(conteo.get(m.npc_type, 0), kills_necesarias - 1)
        return

    conteo[m.npc_type] = conteo.get(m.npc_type, 0) + 1
    actual = conteo[m.npc_type]

    log.info(f"[{addr}] Elfo {m.nombre} derrotado en stage {st} ({actual}/{kills_necesarias} para invocar a {lord_nombre})")

    if actual >= kills_necesarias:
        conteo[m.npc_type] = 0
        _invocar_lord_playground(ses, lord_type, lord_nombre, m, addr)


def _procesar_muerte_lord_playground(ses, m, addr):
    """Notifica la caida de un Elemental Lord en Playground."""
    import clases as _cl
    frase_derrota = FRASES_LORDS_DEFEAT.get(
        m.npc_type,
        f"The {m.nombre} has been defeated!"
    )
    aviso_pkg = _cl.aviso(frase_derrota, tipo=0, msg_id=_cl.MSG_TEXTO)
    ses.enviar_inmediato(aviso_pkg)
    for comp in _companeros(ses):
        try:
            comp.enviar_inmediato(aviso_pkg)
        except Exception:
            pass
    log.info(f"[{addr}] {m.nombre} (eid={m.entity_id}) ha sido derrotado en Playground.")


def _despawn_monstruo_muerto(ses, m, objetivo):
    """Manda el despawn del monstruo al jugador y a sus companeros, y limpia si fue generado."""
    import combate as _cb
    pkt = _cb.despawn_monstruo(objetivo)
    ses.enviar_inmediato(pkt)
    for _comp in _companeros(ses):
        try:
            _comp.enviar_inmediato(pkt)
        except Exception:
            pass
    if getattr(m, 'generado', False):
        if ses.monstruos:
            ses.monstruos.pop(objetivo, None)
        _s = _sala_de(ses)
        if _s is not None and getattr(_s, 'monstruos', None):
            _s.monstruos.pop(objetivo, None)


def _procesar_muerte_monstruo(ses, m, yo, addr, espera=0.0):
    """Procesa respawn, EXP, subida de nivel, oro y drops cuando un monstruo es derrotado."""
    import combate as _cb
    import clases as _cl
    import inventario as _iv
    import struct
    import asyncio
    objetivo = m.entity_id
    yo_muerte = yo

    if ses.personaje and ses.personaje.stage == 57 and m.npc_type == 224:
        ses.slarm_kills = getattr(ses, 'slarm_kills', 0) + 1
        log.info(f"[{addr}] Little Slarm derrotado en Fighting Palace ({ses.slarm_kills}/2)")

    if ses.personaje and getattr(ses.personaje, 'stage', None) in STAGES_PLAYGROUND:
        if m.npc_type in ELFOS_A_LORDS:
            _procesar_baja_elfo_playground(ses, m, addr)
        elif getattr(m, 'es_lord_playground', False) or m.npc_type in (15, 16, 17, 18):
            _procesar_muerte_lord_playground(ses, m, addr)

    if ses.personaje:
        import misiones as _mis_muerte
        _mis_muerte.registrar_baja_monstruo(ses, m.npc_type, getattr(m, 'nombre', None), en_combate_real=True)
        # La baja cuenta para las misiones de todo el grupo que este en la sala.
        for _s_gb in _grupo_en_sala(ses):
            if _s_gb is not ses:
                try:
                    _mis_muerte.registrar_baja_monstruo(_s_gb, m.npc_type, getattr(m, 'nombre', None), en_combate_real=True)
                    _s_gb.volcar()
                except Exception:
                    log.exception('baja de mision de un companero')
        _eventos_al_morir(ses, m, addr)
        for _s_gb in _grupo_en_sala(ses):
            if _s_gb is not ses:
                try:
                    _eventos_al_morir(_s_gb, m, getattr(_s_gb, 'addr', addr))
                    _s_gb.volcar()
                except Exception:
                    log.exception('evento de muerte para companero')
        # La carrera de bajas (NPCKILLGAME): cada baja cuenta en la variable 8.
        import eventos_mundo as _evm_k
        _est_k = _evm_k.estado_de(ses)
        _jk = getattr(_est_k, 'juego_matar', None)
        if _jk and time.time() < _jk.get('fin', 0) and _est_k.stage == ses.personaje.stage:
            _est_k.sumar_variable(0, 8, 1)
            _n_k = _est_k.variable(0, 8)
            if _n_k % 10 == 0:
                log.info(f"[{addr}] NPCKILLGAME: {_n_k} bajas")
            _marcador_carrera(ses, _est_k)
            if _n_k >= META_CARRERA:
                _terminar_carrera(ses, addr, _est_k, gana=True)
        ses.volcar()

    if getattr(m, 'encantado', False):
        m.encantado = False
        m.charmed_objetivo = None
        if getattr(ses, 'monstruo_encantado', None) == m:
            ses.monstruo_encantado = None
        ses.enviar(
            struct.pack('<HIBBII', 0x001D, objetivo, 1, 4, 303, 0),
            struct.pack('<HIBBI', 0x0013, objetivo, 1, 0x3c, 0)
        )

    if getattr(m, 'efectos_activos', None):
        for emid in list(m.efectos_activos.keys()):
            ses.enviar(struct.pack('<HIBBII', 0x001D, objetivo, 1, 4, emid, 0))
        m.efectos_activos.clear()

    _muerte = (_cb.atributo(objetivo, 0, _cb.VIDA),
               _cb.muerte_monstruo(objetivo, yo),
               _cb.ataque(yo, 0, 0, 0))
    _espera_muerte = espera
    try:
        _bucle = asyncio.get_event_loop()
        _bucle.call_later(_espera_muerte,
                          lambda p=_muerte: ses.enviar_inmediato(*p))
        _bucle.call_later(_espera_muerte + 2.5,
                          lambda: _despawn_monstruo_muerto(ses, m, objetivo))
    except Exception:
        ses.enviar(*_muerte)
        _despawn_monstruo_muerto(ses, m, objetivo)

    def _respawn():
        # ENABLE_GENERATOR: mientras la zona siga encendida, cada baja se
        # repone con uno nuevo de esa zona. Es lo que hace las oleadas de la
        # sala 2 de la Magic Kichen Path: los Rock Slarm de las zonas 75, 90
        # y 91 salen sin parar hasta las 45 bajas (evento 102), que las apaga
        # y saca al Rock God Mendun.
        _zona = getattr(m, 'zona_generador', None)
        if getattr(m, 'generado', False) and _zona is not None and ses.personaje:
            import eventos_mundo as _evm_r
            _est = _evm_r.estado_de(ses)
            if (_est.stage == ses.personaje.stage
                    and _zona in getattr(_est, 'generadores_activos', set())):
                _generar_zona(ses, addr, _est.stage, _zona, cuantos=1)
            return
        # En una instancia lo que matas se queda muerto. Salvo durante la
        # carrera del Annoying Clerk: el pasillo se repone mientras dura.
        if es_instancia(getattr(ses.personaje, 'stage', 0) if ses.personaje
                        else 0):
            import eventos_mundo as _evm_rc
            _jrc = getattr(_evm_rc.estado_de(ses), 'juego_matar', None)
            if not (_jrc and time.time() < _jrc.get('fin', 0)):
                return
        if getattr(m, 'generado', False):
            return            # lo saco un evento (GENERATE): no vuelve solo
        # Bichos compartidos: si quien lo mato ya no esta en ese mapa, que lo
        # reviva el bucle de quien siga alli (el aviso le llega a todos).
        if (ses.monstruos or {}).get(objetivo) is not m:
            return
        if not getattr(m, 'vivo', False):
            m.revivir()
            import login as _lg
            _sp_pkg = _lg._npc_spawn(
                objetivo, m.npc_type, m.nombre, (m.tile_x, m.tile_y),
                sprite=getattr(m, 'sprite', 0), klass=1)
            ses.enviar_inmediato(_sp_pkg)
            for _comp in _companeros(ses):
                try:
                    _comp.enviar_inmediato(_sp_pkg)
                except Exception:
                    pass
            log.info(f"[{addr}] monstruo {m.nombre} (entidad {objetivo}) reaparecio en ({m.tile_x}, {m.tile_y})")

    try:
        asyncio.get_event_loop().call_later(_cb.SEGUNDOS_REAPARICION, _respawn)
    except Exception:
        pass

    def _premiar(ses, fraccion=1.0, con_botin=True):
        """La exp, el oro y el botin de UN jugador por esta muerte.

        `fraccion` es su parte de la exp y del oro; `con_botin`, si le toca
        el botin del bicho (el de mision lo saca cada uno). Lo reparte
        _repartir_muerte entre quienes pelearon."""
        yo = ses.personaje.entity_id if ses.personaje else yo_muerte
        buffs = ses.personaje.buffs if ses.personaje else {}
        exp_ganada = _cb.calcular_exp(m.npc_type, buffs)
        if fraccion < 1.0:
            exp_ganada = max(1, int(round(exp_ganada * fraccion)))
        sk_exp_ganada = _cb.calcular_skill_exp(buffs)

        # El oro depende del BICHO: su tabla de serv_drop.xml si la tiene, y si
        # no la mediana de su tramo de nivel. Antes se llamaba sin argumentos y
        # por eso todos soltaban lo mismo.
        oro = _cb.botin(getattr(m, 'nivel', 0) or 0, getattr(m, 'npc_type', 0) or 0)
        if fraccion < 1.0:
            oro = int(oro * fraccion)
        ses.oro = getattr(ses, 'oro', 0) + oro
        if ses.personaje:
            ses.personaje.oro = ses.oro

        salida_combate = []
        cid = ses.personaje.char_id if ses.personaje else 4980

        if ses.personaje:
            p = ses.personaje
            f_pet = getattr(p, 'mascota', None)
            pet_fuera = bool(f_pet and f_pet.get('fuera'))

            # Reparto proporcional de EXP segun el % de dano hecho por cada bando:
            #   - Bando del jugador (dano_jugador): Jugador + Invocaciones + Monstruos encantados (Earth) + sangrados/reflejos
            #   - Bando de la mascota (dano_pet): Mascota (solo si esta invocada y ataco)
            dano_jug = max(0, int(getattr(m, 'dano_jugador', 0) or 0))
            dano_pet = max(0, int(getattr(m, 'dano_pet', 0) or 0)) if pet_fuera else 0
            m.dano_jugador = 0
            m.dano_pet = 0

            dano_tot = dano_jug + dano_pet
            if dano_tot > 0:
                pct_jug = dano_jug / float(dano_tot)
                pct_pet = dano_pet / float(dano_tot)
            else:
                pct_jug = 1.0
                pct_pet = 0.0

            exp_jug = max(1, int(round(exp_ganada * pct_jug))) if pct_jug > 0 else 0
            exp_pet = max(1, int(round(exp_ganada * pct_pet))) if (pct_pet > 0 and pet_fuera) else 0

            _u64 = lambda v: max(0, min(int(v or 0), 0xFFFFFFFFFFFFFFFF))
            if exp_jug > 0:
                p.exp = max(int(p.exp or 0), _cb.exp_para_nivel(p.nivel)) + exp_jug
                subio_nivel = False
                # ESTE BUCLE COLGABA EL SERVIDOR. exp_para_nivel() recortaba a
                # 0xFFFFFFFF, asi que del nivel 299 en adelante devolvia siempre el
                # mismo numero; con la experiencia por encima de ese tope la
                # condicion no dejaba de cumplirse nunca y subia de nivel para
                # siempre. Ahora la curva va sin recortar, hay tope de nivel, y
                # ademas un limite de vueltas por si algun dia la curva llega rota.
                _tope_nivel = _cb.nivel_maximo()
                for _ in range(1000):
                    if p.nivel >= _tope_nivel:
                        break
                    exp_siguiente = _cb.exp_para_nivel(p.nivel + 1)
                    if exp_siguiente > 0 and p.exp >= exp_siguiente:
                        p.nivel += 1
                        p.hp_max += 25
                        p.mp_max += 15
                        subio_nivel = True
                    else:
                        break
                exp_actual_ui, exp_siguiente_ui = _cb.exp_para_barra(p.nivel, p.exp)
                if subio_nivel:
                    p.hp = _vida_max(p)
                    p.mp = _mana_max(p, ses.inventario)
                    salida_combate.append(_cl.aviso(f"Level Up! Reached Level {p.nivel}!", tipo=0, msg_id=_cl.MSG_TEXTO))
                    salida_combate.append(_cb.atributo(yo, p.hp, _cb.KIND_HP))
                    salida_combate.append(_cb.atributo(yo, p.mp, _cb.KIND_MP))
                    salida_combate.append(
                        struct.pack('<HIB', 0x001D, yo, 4) +
                        struct.pack('<BQ', 29, _u64(p.nivel)) +
                        struct.pack('<BQ', 30, max(0, int(_cb.exp_para_nivel(p.nivel)))) +
                        struct.pack('<BQ', 31, _u64(exp_siguiente_ui)) +
                        struct.pack('<BQ', 32, _u64(exp_actual_ui))
                    )
                    salida_combate.append(_cb.efecto_level_up(yo, es_skill=False))
                    salida_combate.append(_stats_ses(ses))
                    # Las tres ranuras de rama extra se abren por NIVEL (301,
                    # 351 y 401), sin Supreme Level ni mision. Aqui solo se
                    # avisa: la ranura ya esta disponible, se llena eligiendo
                    # una rama.
                    import skills as _sk_rn
                    _nueva_ranura = _sk_rn.ranura_que_se_abre(p.nivel)
                    if (_nueva_ranura
                            and len(p.habilidades or []) >= _sk_rn.RANURAS_BASE
                            and len(p.habilidades or []) < _nueva_ranura):
                        # Se rellena sola con una rama de OFICIO, que no cambia
                        # la clase, para que la ranura se vea y se pueda ir a
                        # cambiarla con el Skill Angel. El comando /rama sigue
                        # valiendo para ponerle otra cosa directamente.
                        _relleno = _sk_rn.rama_de_relleno(p.habilidades)
                        if _relleno:
                            if not getattr(p, 'banco_habilidades', None):
                                p.banco_habilidades = {}
                            _nv_rl, _xp_rl = p.banco_habilidades.get(_relleno, (1, 0))
                            p.habilidades = list(p.habilidades or []) + [(_relleno, _nv_rl, _xp_rl)]
                            p.class_id = _sk_rn.calcular_class_id([h[0] for h in p.habilidades])
                            salida_combate.append(_cl.aviso(
                                _sk_rn.nombre_rama(_relleno), tipo=7, msg_id=424))
                            salida_combate.append(
                                _cl.arbol(p.habilidades, banco=p.banco_habilidades))
                            for _nid, _nom in (_sk_rn.hechizos_de_rama(_relleno) or []):
                                salida_combate.append(
                                    struct.pack('<HIB', 0x001D, yo, 1)
                                    + struct.pack('<BII', _cl.KIND_HECHIZO, _nid, 1))
                                salida_combate.append(
                                    _cl.aviso(_nom, tipo=7, msg_id=_cl.MSG_HECHIZO))
                            if getattr(ses, 'usuario', None):
                                cuentas.guardar_clase(ses.usuario, p.char_id, p.class_id)
                                cuentas.guardar_banco_habilidades(
                                    ses.usuario, p.char_id, p.banco_habilidades)
                        salida_combate.append(_cl.aviso(
                            'Skill slot %d unlocked (%s). Change it at the Skill Angel.'
                            % (_nueva_ranura, _sk_rn.nombre_rama(_relleno) if _relleno else '-'),
                            tipo=0, msg_id=_cl.MSG_TEXTO))
                        log.info('[%s] %s abre la ranura de rama %d al nivel %d, '
                                 'rellenada con %s'
                                 % (addr, p.nombre, _nueva_ranura, p.nivel,
                                    _sk_rn.nombre_rama(_relleno) if _relleno else 'nada'))
                    log.info(f"[{addr}] {p.nombre} SUBIO A NIVEL {p.nivel} (enviado 0x001D y efecto 0x0020 red banner)!")

                salida_combate.append(_cl.aviso_doble(_cl.MSG_EXP,
                                                      str(exp_jug),
                                                      str(exp_jug), tipo=0))
                salida_combate.append(
                    struct.pack('<HIBBQ', 0x001D, yo, 1, 32, _u64(exp_actual_ui)))

            if getattr(ses, 'usuario', None):
                cuentas.guardar_progreso(ses.usuario, p.char_id, p.nivel, p.exp,
                                         p.hp, p.mp, p.habilidades,
                                         hp_max=p.hp_max, mp_max=p.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)
                cuentas.guardar_oro(ses.usuario, p.char_id, ses.oro)

            # La mascota solo gana EXP si participo en el combate (exp_pet > 0, proporcional a su % de dano)
            if pet_fuera and exp_pet > 0:
                import mascotas as _ms
                _sp_antes = f_pet.get('sprite')
                _sub_p = _ms.dar_exp(f_pet, exp_pet)
                _r_pet = f_pet.get('ranura')
                if _r_pet is not None and getattr(p, 'mascotas', None) is not None:
                    p.mascotas[str(_r_pet)] = f_pet
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_mascota(ses.usuario, p.char_id, f_pet, getattr(p, 'mascotas', None))
                salida_combate.append(_ms.armar(f_pet))
                if _sub_p > 0:
                    if _r_pet is not None:
                        salida_combate.extend(_refrescar(ses, [_r_pet]))
                    pet_eid = getattr(ses, 'pet_entity_id', None) or f_pet.get('entidad')
                    if pet_eid and f_pet.get('sprite') != _sp_antes:
                        old_eid = int(pet_eid)
                        salida_combate.extend([
                            _ms.quitar(old_eid),
                            _ms.enlazar(yo, 0),
                        ])
                        pet_eid = _pet_siguiente_entidad(ses)
                        f_pet['entidad'] = pet_eid
                        ses.pet_entity_id = pet_eid
                        _est_p = dict(f_pet)
                        _est_p.update({
                            'entidad': pet_eid,
                            'x': f_pet.get('x', p.tile_x + 1),
                            'y': f_pet.get('y', p.tile_y),
                            'dueno': yo,
                            'dueno_nombre': p.nombre,
                            'tipo': f_pet.get('tipo', 0),
                        })
                        salida_combate.extend([
                            _ms.entidad_mundo(_pet_plantilla(), _est_p),
                            _ms.enlazar(yo, pet_eid),
                            _ms.armar(f_pet),
                        ])
                    if pet_eid:
                        salida_combate.append(_cb.atributo(int(pet_eid), _ms.hp_eff(f_pet), _cb.KIND_HP))
                        if int(f_pet.get('saciedad', 0)) > 100:
                            salida_combate.append(struct.pack('<HIBBII', 0x001D, int(pet_eid), 1, 4, 3796, max(60000, (int(f_pet['saciedad']) - 100) * 60000)))

        salida_combate.append(_cl.aviso(f'{oro} Gold', tipo=0, msg_id=_cl.MSG_ITEM))

        drops = (_cb.botin_items(m.npc_type, nombre=getattr(m, 'nombre', ''), nivel=getattr(m, 'nivel', 0))
                 if con_botin else [])
        if ses.personaje:
            import misiones as _mis_drop
            drops_mis = _mis_drop.verificar_botin_mision(ses, m.npc_type, getattr(m, 'nombre', ''))
            if drops_mis:
                drops = list(drops) + list(drops_mis)
        bolsa = getattr(ses, 'inventario', {})
        max_ranura = _tope_bolsa(bolsa)

        tocadas_botin = []
        for item_drop, cant in drops:
            cant = max(1, int(cant))
            if _iv.es_item_oculto(item_drop):
                import misiones as _mis_sl
                slot_oc = _mis_sl.slot_oculto_para_item(ses, item_drop)
                bolsa[slot_oc] = item_drop
                _instancias(ses)[slot_oc] = _iv.instancia_nueva()
                _cant_actual = int(_cantidades(ses).get(int(slot_oc), 0))
                _cantidades(ses)[slot_oc] = _cant_actual + cant
                _cantidades(ses)[str(slot_oc)] = _cant_actual + cant
                tocadas_botin.append(slot_oc)
                salida_combate.append(_cl.aviso(_nombre_item(item_drop), tipo=0, msg_id=_cl.MSG_ITEM))
                continue

            apila = None
            if _iv.es_apilable(item_drop):
                for s_r, it_id in bolsa.items():
                    if 20 <= s_r <= max_ranura and it_id == item_drop:
                        apila = s_r
                        break
            if apila is None and not any(r not in bolsa for r in range(20, max_ranura + 1)):
                log.info(f"[{addr}] inventario lleno (limite={max_ranura}), drop {item_drop} ignorado silenciosamente")
                continue

            tocadas_botin.append(_meter(ses, item_drop, cant))
            salida_combate.append(_cl.aviso(_nombre_item(item_drop), tipo=0, msg_id=_cl.MSG_ITEM))

        salida_combate.extend(_refrescar(ses, tocadas_botin, con_oro=True))
        if ses.personaje and tocadas_botin:
            import misiones as _mis_col
            pkgs_rec = _mis_col.verificar_progreso_recoleccion(ses, [d[0] for d in drops])
            salida_combate.extend(pkgs_rec)
        try:
            asyncio.get_event_loop().call_later(
                _espera_muerte,
                lambda p=tuple(salida_combate): ses.enviar_inmediato(*p))
        except Exception:
            ses.enviar(*salida_combate)
        if ses.personaje and getattr(ses, 'usuario', None):
            cuentas.guardar_inventario(ses.usuario, cid, bolsa, _cantidades(ses))

        log.info(f"[{addr}] mato un {m.nombre} (entidad {objetivo}); +{exp_ganada} exp, +{oro} oro, {len(drops)} items")

    for _s_pr, _fr_pr, _bot_pr in _repartir_muerte(ses, m):
        try:
            _premiar(_s_pr, _fr_pr, _bot_pr)
        except Exception:
            log.exception('[%s] no se pudo premiar a un participante', addr)



# La salida del Lyceum. "Quit the training" con Angels' Tutor lleva al
# Graduation Palace, y alli cada Angel de faccion manda a su ciudad. Los dos
# puntos estan MEDIDOS en la ficha 0x0002 que llega tras cada cambio de mapa:
# Graduation Palace (26,7) y Breeze Woods (321,97), que es el (321,98) que se
# ve en el minimapa.
# Velocidad a la que camina el personaje, en el campo 'speed' del 0x0005.
# Estaba escrita a mano en 110 dentro del manejador de movimiento. Se puede
# subir con AO_VELOCIDAD mientras no haya monturas; el valor original del
# juego es 110, y los monstruos caminan a 75.
VELOCIDAD_JUGADOR = int(os.environ.get('AO_VELOCIDAD', '110'))

# La montura va en la ranura 10 y sube la velocidad del 0x0005. Medido en
# Celestia con el mismo personaje, quitandola y volviendola a poner:
#
#   sin montura              122
#   con Earthy Piglet (36400) 226
#   con "MAX 200"    (40441)  212
#
# OJO, la columna move_speed de item.xml NO basta: las dos monturas de arriba
# la tienen en 60 y dan velocidades distintas, y la que mas agility declara es
# la mas LENTA. Ademas, al quitar la 40441 los stats bajaron 2400 de HP y 2000
# de MP, cuando su fila dice hp=1720 y mp=1540. O sea que lo que aporta una
# montura depende de SU INSTANCIA -- son mascotas con nivel propio -- y eso no
# esta en item.xml, asi que con los datos del cliente no se puede reproducir el
# numero exacto.
#
# Aqui se aplica el move_speed como porcentaje, que es lo unico sostenible con
# lo que hay: es la forma correcta, aunque el numero no salga clavado al de
# Celestia hasta que sepamos modelar el nivel de la montura.
RANURA_MONTURA = 10

# Bono de montura, en por ciento, que PISA el move_speed del item. A peticion
# del usuario: el Gryphon declara 50 y aqui se usa 150. Poner 0 para respetar
# lo que diga item.xml.
#
# El campo del 0x0005 es U16, no un byte: en las capturas hay jugadores de
# Celestia moviendose a 260 y a 283, asi que 275 (110 x 2,5) entra de sobra en
# lo que el cliente maneja de verdad. El tope de 1000 es solo para que una
# variable de entorno mal puesta no mande un numero absurdo.
BONO_MONTURA = int(os.environ.get('AO_MONTURA_BONO', '150'))


def _velocidad_de(ses) -> int:
    """Velocidad del 0x0005, con monturas y buffs activos de movimiento."""
    base = VELOCIDAD_JUGADOR
    try:
        import inventario as _inv
        bolsa = getattr(ses, 'inventario', None) or {}
        ahora = time.time()
        bono_buff = 0.0
        for buff in (getattr(getattr(ses, 'personaje', None), 'buffs', None) or {}).values():
            if not isinstance(buff, dict) or buff.get('fin', 0) <= ahora:
                continue
            mag = buff.get('mag')
            if isinstance(mag, dict):
                bono_buff += float(mag.get('move_speed_bonus', 0) or 0)
        # LA MONTURA DE FASHION NO QUITA VELOCIDAD.
        #
        # La ranura 174 es la montura de la pestaña Fashion y la 10 la de
        # verdad. Antes se miraba la 174 PRIMERO y, si habia algo, se usaba
        # esa y ya: `bolsa.get(174) or bolsa.get(RANURA_MONTURA)`.
        #
        # Lo de fashion es aspecto, no montura. La Shamrock Goldfish, el item
        # 77099, es de categoria 紙娃娃 y su move_speed viene VACIO, asi que
        # velocidad_de_montura devolvia 0 y se caia a la velocidad de a pie.
        # Ponerse el aspecto te dejaba andando y quitarselo te la devolvia.
        #
        # Ahora SUMAN. Hay monturas de fashion que si dan velocidad, y en el
        # juego se acumula con la de la montura de verdad; las que no dan
        # nada, como la Shamrock Goldfish, suman cero y se quedan en aspecto.
        ms_real = _inv.velocidad_de_montura(bolsa.get(RANURA_MONTURA) or 0)
        ms_moda = _inv.velocidad_de_montura(bolsa.get(174) or 0)
        if not ms_real and not ms_moda and not bono_buff:
            return base
        # BONO_MONTURA pisa lo que diga item.xml, pero solo para la montura de
        # verdad: lo que aporte el aspecto se suma encima tal cual.
        if BONO_MONTURA and ms_real:
            ms_real = BONO_MONTURA
        ms = ms_real + ms_moda + bono_buff
        return max(1, min(1000, int(round(base * (100 + ms) / 100.0))))
    except Exception:
        return base

# Donde deja el Angel de una ciudad al mandarte de vuelta: al lado de
# Director Wolay, en el Angel Lyceum. La casilla la midio el usuario.
TILE_VUELTA_LYCEUM = (128, 62)

STAGE_GRADUACION = 58
TILE_GRADUACION = (26, 7)

# Las otras tres ciudades salen del "Birth Place" de jumpmap.xml, que es el
# punto analogo; solo el de Breeze Woods esta medido en el juego.
# El nombre que el cliente ENSEÑA en el campo Faction no es el de la ciudad.
# En stage.xml cada ciudad trae su faccion en chino: Aurora 光明 (luz), Dark
# City 黑暗 (oscuridad), Breeze Woods 大地 (tierra) e Iron Castle 渾沌 (caos).
# El unico confirmado en el juego es el de Breeze Woods, que sale como
# "Beasts"; los otros tres son la traduccion mas probable y hay que
# comprobarlos eligiendo esas facciones.
# Que faccion da cada ciudad. YA NO SE ADIVINA: sale de los datos del
# cliente. jumpmap.xml mete cada ciudad en su "territorio de faccion"
# (jumpmapclass.xml: 14 Aurora, 15 Shadow, 16 Beasts, 17 Steel) y ahi no hay
# ambiguedad posible.
#
#   stage  3 Aurora City    categoria 14  -> Aurora
#   stage 26 Dark City      categoria 15  -> Shadow
#   stage 29 Breeze Woods   categoria 16  -> Beasts   <- coincide con lo medido
#   stage 38 Iron Castle    categoria 17  -> Steel
#
# Antes aqui habia 'Holy', 'Evil' y 'Chaos', que nos inventamos: esos nombres
# NO EXISTEN en el cliente. Los suyos son los de string.xml 1031..1035.
NOMBRE_DE_FACCION = {
    'Breeze Woods': 'Beasts',
    'Aurora': 'Aurora',
    'Dark City': 'Shadow',
    'Iron Castle': 'Steel',
}

# Donde deja el Angel del Graduation Palace al elegir faccion: AL LADO del
# Angel de la ciudad, no en la entrada. Comprobado en las dos que tenemos
# capturadas:
#
#   Breeze Woods   BreezeWood Angel en (325,97)  -> deja en (321,97)   4 casillas
#   Aurora City    Aurora Angel     en (188,183) -> deja en (191,182)   3 casillas
#   Iron Castle    IronCastle Angel en (64,161)  -> deja en (68,163)    4 casillas
#   Dark City      Dark City Angel  en (313,69)  -> deja en (309,69)    4 casillas
#
# Las dos caen a tres o cuatro casillas del angel y en su misma fila. Aurora
# City es el stage 3, confirmado por captura el 23/09/2026; su casilla la dio
# el usuario probando en el juego.
#
# LAS CUATRO ESTAN MEDIDAS (23/09/2026). Los dos stage que quedaban a ojo, el
# 38 de Iron Castle y el 26 de Dark City, resultaron correctos; las casillas
# las dio el usuario probando en el juego. La regla se cumple en las cuatro:
# te dejan AL LADO del Angel de la ciudad, a tres o cuatro casillas y en su
# misma fila. Cuando se capturen, la casilla se saca buscando a su
# Angel en la plantilla y poniendose a su lado, que es la pauta de las otras
# dos.
CIUDAD_DE_FACCION = {
    "Breeze Woods": (29, (321, 97)),
    "Aurora": (3, (191, 182)),
    "Iron Castle": (38, (68, 163)),
    "Dark City": (26, (309, 69)),
}


def _ya_registrado(ses) -> bool:
    """Si el personaje ya se registro con el Angel de su ciudad o el Angel Tutor.

    Se sabe porque la mision de registro (130 en Breeze Woods) ya no esta
    pendiente: al registrarse se marca completada y se dan las dos
    siguientes. En el Angel Lyceum (41, 141, 241), se considera registrado si
    ya completo Quest 101 o tiene activa/completa Quest 102.
    """
    import dialogos as _dlg
    import misiones as _mis
    p = getattr(ses, 'personaje', None)
    if not p:
        return False
    st = getattr(p, 'stage', 0)
    if st in (41, 141, 241):
        fac = getattr(p, 'faction', 'Heaven') or 'Heaven'
        return bool(_mis.mision_completada(p, 101) or _mis.tiene_mision(p, 102)
                    or _mis.mision_completada(p, 102)
                    or fac in ('Aurora', 'Dark', 'Iron', 'Shadow', 'Steel', 'Beasts', 'Graduated'))
    cfg = _dlg.ANGEL_DE_CIUDAD.get(st)
    if not cfg:
        return False
    q = cfg['mision_registro']
    for qid, paso in (p.quests or []):
        if qid == q:
            return paso > 0
    return True


def _tutor_en_progreso(ses) -> bool:
    """Si el personaje esta cursando la firma de profesores (Quest 101) con el Angel Tutor."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return False
    import misiones as _mis
    st, pa, comp = _mis.estado_mision(p, 101)
    return bool(st and not comp and pa < 4)


def _es_graduado(ses) -> bool:
    """Si el personaje ya completo el entrenamiento / se graduo del Angel Lyceum."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return False
    fac = getattr(p, 'faction', 'Heaven') or 'Heaven'
    if fac not in ('Heaven', 'Neutral', 'Neutrally'):
        return True
    import misiones as _mis
    if _mis.mision_completada(p, 102) or _mis.tiene_mision(p, 103) or _mis.mision_completada(p, 103):
        return True
    return False
# Las ranuras de equipo cuyo contenido se le anuncia al cliente para que
# dibuje al personaje. Medido: el servidor real manda una linea por cada una
# de la 1 a la 7 y la 10, con el item o con 0 si esta vacia.
RANURAS_VISIBLES = (1, 2, 3, 4, 5, 6, 7, 10)


def _apariencia(ses):
    """Los 0x001D code 1 que le dicen al cliente que lleva puesto en cada ranura.
    No cruza las ranuras de Gear con las de Fashion para evitar glitches visuales en la UI.
    """
    import combate as _cb
    p = getattr(ses, 'personaje', None)
    if not p:
        return []
    bolsa = getattr(ses, 'inventario', None) or {}
    ent = p.entity_id
    out = []
    # 1. Ranuras de equipo regular (1..7, 10)
    for r in RANURAS_VISIBLES:
        out.append(_cb.equipar_visual(ent, r, int(bolsa.get(r, 0) or 0)))
    # 2. Ranuras de Fashion (167..174): TODAS, con 0 las vacias. Mandando
    # solo las ocupadas, al quitarse una pieza nadie le decia al cliente que
    # esa ranura habia quedado vacia, y la seguia pintando encima del
    # personaje y en su casilla de la ventana (salia repetida).
    for r in range(167, 175):
        out.append(_cb.equipar_visual(ent, r, int(bolsa.get(r, 0) or 0)))
    return out


def _viajar_dentro_del_mapa(ses, addr, por, motivo=''):
    """Un portal que lleva a OTRO punto del MISMO mapa.

    Medido en Forbidden Sector el 24/09/2026, seis cruces entre sus dos
    tubos de teletransporte, el 116703 en (226,143) y el 116707 en (197,75).
    En 1401 segundos de sesion no viajo NI UN 0x000C: el mapa no se recarga.
    Lo que manda el servidor real es:

        s2c 0x0016  [u32 entidad][u8 direccion]   hacia donde queda mirando
        s2c 0x0012  siete bytes a cero            cierra el cuadro
        s2c 0x0003  [u32 entidad][u32 x][u32 y]   lo recoloca

    Ojo con el 0x0012: aqui son SIETE ceros, no los nueve de dialogos.FIN.

    La direccion salio 5 al aparecer en el extremo norte y 1 en el sur, asi
    que va por portal en el campo 'direccion'; si no lo trae, no se manda.
    """
    lleg = por['llegada']
    yo = ses.personaje.entity_id
    fuera = []
    # NO TODOS LOS SALTOS INTERNOS MANDAN LO MISMO. Los de Forbidden Sector y
    # Lost Trail traen el 0x0016 y el 0x0012; el de vuelta de las estatuas de
    # Seaside Grotto no trae ninguno de los dos -- se busco en toda la sesion
    # y no hay ni un 0x0016 -- y lo unico que llega es el 0x0003. Los portales
    # asi se marcan con solo_0003.
    if not por.get('solo_0003'):
        d = por.get('direccion')
        if d is not None:
            fuera.append(struct.pack('<HIB', 0x0016, yo, int(d)))
        fuera.append(struct.pack('<H', 0x0012) + bytes(7))
    fuera.append(struct.pack('<HIII', 0x0003, yo, lleg[0], lleg[1]))
    ses.personaje.tile_x, ses.personaje.tile_y = lleg
    if ses.personaje.stage == 500 and not getattr(ses, 'house_furnishing', False):
        import login as _lg_house
        fuera.extend(_lg_house.interactivos_casa(player_level=ses.personaje.nivel))
    ses.enviar(*fuera)
    # Si la casilla de llegada cae dentro del radio de OTRO portal del mismo
    # mapa, se marca como pisada: si no, el jugador rebotaria al primer paso.
    _en = _portal_en(ses.personaje.stage, *lleg)
    ses.portal_pisado = tuple(_en['tile']) if _en else None
    if getattr(ses, 'usuario', None):
        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id,
                             ses.personaje.stage, *lleg)
    log.info(f"[{addr}] portal interno: sigue en stage "
             f"{ses.personaje.stage}, ahora en {lleg} {motivo}")


def _sincronizar_cambio_mapa(ses, stage_id: int, x: int = None, y: int = None):
    """Actualiza el estado del servidor y manda solo 0x000C (cambiar mapa).

    Todo lo demas (poblar, habilidades, stats) lo hace el handler de 0x0009
    cuando el cliente contesta que ya cargo el mapa. Antes se mandaba TODO
    aqui y luego otra vez en 0x0009, duplicando cientos de paquetes y
    crasheando al cliente en mapas pesados como Raging Reefs (400+ spawns).
    """
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    if getattr(ses, 'puesto', None):
        _cerrar_puesto(ses, avisar_dueno=True)
    import clases as _cl
    p.stage = stage_id
    if x is not None and y is not None:
        p.tile_x, p.tile_y = x, y
    ses.monstruos = _monstruos_de(stage_id)
    ses.mapa_cambiado_en = time.time()

    # Unico paquete: decirle al cliente "carga este mapa"
    ses.enviar(_cl.cambiar_mapa(stage_id))

    if getattr(ses, 'usuario', None):
        cuentas.guardar_mapa(ses.usuario, p.char_id, stage_id, p.tile_x, p.tile_y)


def _viajar_por_portal(ses, addr, por, motivo=''):
    """Manda al jugador por un tornado que no pregunta."""
    dst, lleg = por.get('destino'), por.get('llegada')
    # Red de seguridad: sin destino o sin casilla no se viaja. Quien llama
    # tiene que haberlo filtrado antes, pero el manejador del CLIC no lo
    # hacia y la sesion se caia al desempaquetar un None.
    if dst is None or not lleg:
        log.debug(f"[{addr}] portal {por.get('tile')} sin destino: no se viaja")
        return
    # MISMO MAPA: no se recarga nada, solo se recoloca al personaje.
    if dst == getattr(ses.personaje, 'stage', None):
        _viajar_dentro_del_mapa(ses, addr, por, motivo)
        return
    _en_llegada = _portal_en(dst, *lleg)
    ses.portal_pisado = tuple(_en_llegada['tile']) if _en_llegada else None
    _sincronizar_cambio_mapa(ses, dst, lleg[0], lleg[1])
    log.info(f"[{addr}] portal directo: stage {dst} tile {lleg} {motivo}")


def _armar_portal_al_llegar(ses, addr, destino_tile, casillas):
    """Dispara el portal cuando el paso TERMINA encima de un tornado.

    El servidor solo mira la casilla que el cliente dice ocupar, y eso deja un
    agujero: si el ultimo tramo de la ruta acaba justo sobre el tornado, el
    cliente camina hasta alli, se queda quieto y NO vuelve a mandar nada, asi
    que nunca llegamos a verlo encima y el portal no dispara.

    Medido en Celestia, saliendo de Sunshine Palace: el ultimo MOVE_REQ vino
    desde (19,10), a SIETE casillas del tornado, con destino (13,6), que esta a
    una. Despues no mando nada mas y el cambio de mapa llego 0,9 s despues.

    No vale con mirar el destino del paso y viajar en el acto: el primer
    waypoint llega a estar a 21 casillas, asi que el jugador se teletransportaria
    desde media pantalla. Lo que se hace es ARMAR el viaje para dentro de lo
    que tarde en andar ese tramo; cualquier movimiento nuevo lo cancela, asi
    que si cambia de idea a mitad de camino no viaja.
    """
    import asyncio
    _cancelar_portal_armado(ses)
    por = _portal_en(ses.personaje.stage, *destino_tile)
    if por is None:
        return
    # Igual que arriba: mientras siga marcado como pisado no se vuelve a
    # armar, sin ventana de tiempo. La marca se borra sola al salir del radio.
    if getattr(ses, 'portal_pisado', None) == tuple(por['tile']):
        return
    vel = max(1, _velocidad_de(ses))
    espera = min(5.0, max(0.2, casillas * 25.0 / vel))

    def _saltar():
        ses.portal_armado = None
        try:
            if ses.personaje:
                p_act = _portal_en(ses.personaje.stage, *destino_tile)
                if p_act:
                    if ses.personaje.stage == 500 and p_act.get('entity') == 701:
                        c_vis = _casa_actual(ses)
                        if c_vis and c_vis.owner_id != ses.personaje.char_id:
                            _salir_de_casa(ses, addr)
                            return
                    if p_act.get('preguntar'):
                        import dialogos as _dlg
                        _cfg = _portales()
                        _ops = p_act.get('opciones') or _cfg['opciones']
                        sub = _dlg.armar_linea(p_act.get('msg') or _cfg['msg'], 0, _ops,
                                               acciones=p_act.get('acciones'))
                        ses.dlg_ent = p_act.get('entity', 0)
                        ses.dlg_guion = [sub[2:]]
                        ses.dlg_paso = 1
                        ses.dlg_val = 0
                        ses.dlg_portal = p_act
                        ses.enviar(sub)
                    else:
                        _viajar_por_portal(ses, addr, p_act, '(al terminar el paso)')
        except Exception:
            log.exception('fallo el portal armado')

    try:
        ses.portal_armado = asyncio.get_event_loop().call_later(espera, _saltar)
    except Exception:
        ses.portal_armado = None


def _cancelar_portal_armado(ses):
    h = getattr(ses, 'portal_armado', None)
    if h is not None:
        try:
            h.cancel()
        except Exception:
            pass
        ses.portal_armado = None


def _entrar_a_casa(ses, addr, casa):
    """Enter the client's special stage-500 parallel space safely."""
    import casas as _cs
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    if p.stage != _cs.STAGE_HOUSE:
        ses.house_return_pos = (p.stage, (p.tile_x, p.tile_y))
    try:
        import presencia as _pres
        _pres.salir(ses, avisar=True)
    except Exception:
        log.exception('casas: no se pudo dejar la presencia exterior')
    ses.casa_visitando = casa
    ses.house_transition = getattr(ses, 'house_transition', 0) + 1
    ses.house_room_ready = False
    ses.house_furnishing = False
    ses.house_furnish_pending = False
    p.stage = _cs.STAGE_HOUSE
    p.tile_x, p.tile_y = 42, 80
    ses.monstruos = {}
    ses.mapa_cambiado_en = time.time()
    # Stage 500 is intentionally not persisted as the character's normal
    # location.  A reconnect returns to the exterior instead of getting
    # trapped in a house whose session instance no longer exists.
    ses.enviar(_cs.pkt_cambiar_mapa_house(
        _cs.STAGE_HOUSE, casa.exterior_table_id, casa.size_level))


def _salir_de_casa(ses, addr):
    ses.house_room_ready = False
    prev = getattr(ses, 'house_return_pos', None)
    if not prev:
        prev = (41, (192, 175))
    ses.casa_visitando = None
    ses.house_furnishing = False
    ses.house_furnish_pending = False
    dst_stage, dst_tile = prev
    _viajar_por_portal(ses, addr, {'destino': dst_stage, 'llegada': dst_tile}, motivo='saliendo de la casa')


def _paquetes_ocultar_interactivos_casa():
    """Despawn de Maid, maquinas y portales para el modo decoracion."""
    import combate as _cb_house
    # Los NPC y mascotas nacen con 0x0008 y salen con 0x0007.
    npc_ids = [260300, 260400, 260500, 262501, 262502]
    npc_ids.extend(range(8101, 8110))
    npc_ids.extend(range(8201, 8207))
    salida = [_cb_house.despawn_monstruo(eid) for eid in npc_ids]
    # IGG sub_5F0350: 0x000F actualiza un objeto NOMBRADO (46 bytes),
    # no lo elimina. Un <HI> provoca lecturas fuera del paquete. 0x0007
    # (sub_5ECA40) elimina cualquier entidad, incluidos objetos de mapa.
    import house_services as _hs_hide
    obj_ids = [701, 702, 703, 720, 721, 723, 731]
    obj_ids.extend(_hs_hide.PRODUCTION)
    obj_ids.extend(_hs_hide.RESOURCES)
    salida.extend(_cb_house.despawn_monstruo(eid) for eid in obj_ids)
    return salida


def _ocultar_interactivos_casa(ses):
    ses.enviar(*_paquetes_ocultar_interactivos_casa())


def _mostrar_interactivos_casa(ses):
    """Restaura las entidades fijas al abandonar el editor."""
    import login as _lg_house
    ses.enviar(*_lg_house.interactivos_casa(player_level=ses.personaje.nivel))


def _casa_paquetes_decorar(ses, casa):
    """Open editor, then trigger IGG sub_66C880(..., 1) via slot update.

    0x013E creates the widgets but does not fill owner/icon. The inventory
    arrived before those widgets existed, so resend the equipped deed AFTER
    opening them. House name (+7) remains independent of the owner's name.
    """
    import casas
    slot = casas.SLOT_DEED
    ses.inventario[slot] = casa.deed_id
    ses.personaje.inventario[slot] = casa.deed_id
    # 0x001B updates the slot but does NOT call sub_66C880(..., 1).
    # 0x001A has the same entry layout; its handler upserts (no clear) and
    # performs the owner/icon refresh. Send just the deed, not the whole bag.
    refresh = [struct.pack('<H', 0x001A) + packet[2:]
               for packet in _refrescar(ses, [slot])]
    return [casas.pkt_enter_furnish_mode(casa.house_name or casa.owner_name,
                                        casa.placed_furniture), *refresh]


def _casa_salir_editor(ses, addr):
    """A delayed Leave must never eject a subsequently reopened editor."""
    import casas
    ses.house_furnishing = False
    ses.house_furnish_pending = False
    ses.enviar(casas.pkt_leave_furnish_mode())
    generation = getattr(ses, 'house_transition', 0)
    def finish():
        p = getattr(ses, 'personaje', None)
        if (p and p.stage == casas.STAGE_HOUSE
                and not getattr(ses, 'house_furnishing', False)
                and not getattr(ses, 'house_furnish_pending', False)
                and getattr(ses, 'house_transition', 0) == generation):
            _salir_de_casa(ses, addr)
    asyncio.get_event_loop().call_later(0.3, finish)


def _salir_de_casa_despues_dialogo(ses, addr):
    """Cambia de mapa una vez que el cliente ya proceso el FIN del dialogo."""
    p = getattr(ses, 'personaje', None)
    if p is not None and p.stage == 500 and not getattr(ses, 'house_furnishing', False):
        _salir_de_casa(ses, addr)



def _casa_actual(ses):
    import casas
    p = ses.personaje
    return getattr(ses, 'casa_visitando', None) or casas.obtener_o_crear_casa(
        p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))


def _casa_click(ses, ent):
    """Resolve house-local IDs before map/global portal lookup."""
    if not ses.personaje or ses.personaje.stage != 500:
        return False
    import house_services as hs, dialogos, clases
    names = {260300: ('Maid Eilian', hs.MAID_PORTRAIT),
             720: ('Pet Care Machine', 0),
             721: ("Suft's Mailbox", 60241),
             723: ('The Safe', 60306),
             731: ('Monster Hatching Machine', 0),
             262501: ("Suft's Mailbox", 60241)}
    if ent not in names and ent not in hs.PRODUCTION:
        return False
    # An old portal dialogue must not turn a later Maid "Leave" into travel.
    ses.dlg_portal = None
    c = _casa_actual(ses)
    if getattr(ses, 'house_furnishing', False):
        return True
    if ent in hs.PRODUCTION:
        _sprite, tile, skill, category, note = hs.PRODUCTION[ent]
        if c.owner_id != ses.personaje.char_id:
            ses.enviar(dialogos.armar_linea(7873, 0, []))
        elif not c.cleanliness:
            ses.enviar(dialogos.armar_linea(7923, 0, []))
        elif c.level < 2:
            ses.enviar(dialogos.armar_linea(7871, 0, []))
        elif not any(int(h[0]) == skill and int(h[1]) > 0
                     for h in ses.personaje.habilidades):
            ses.enviar(clases.aviso('', tipo=7, msg_id=note))
        else:
            # IGG sub_606950 registered at 1968+16*0x4B; body is one byte.
            ses.house_make_station = ent
            ses.enviar(struct.pack('<HB', 0x004B, category))
        return True
    name, face = names[ent]
    if ent in (2603, 260300) and c.owner_id != ses.personaje.char_id:
        c.check_daily_reset()
        if ses.personaje.char_id not in c.voted_users_today:
            g = [dialogos.armar_linea(7897, face, [7898, 7899])[2:]]
        else:
            g = [dialogos.armar_linea(7922, face, [7899])[2:]]
    elif ent != 260300 and (c.owner_id != ses.personaje.char_id or not c.cleanliness):
        g = [dialogos.armar_linea(7873 if c.owner_id != ses.personaje.char_id else 7923, face, [])[2:]]
    else:
        g = dialogos.propio(name, entidad=0, val=face,
                           cleanliness=c.cleanliness, house_level=c.level)
    if g:
        ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g, 1
        ses.dlg_val = face
        ses.enviar(dialogos.linea_de(g, 0, ses.personaje.nombre))
    return True


def _casa_submit_order(ses, option):
    """One owned order: exact receipt/products and XML rewards, no fake payment."""
    import house_services as hs, dialogos, clases, combate, inventario
    from producer_orders import apply_delivery, reward_progress
    p = getattr(ses, 'personaje', None)
    if (option not in hs.ORDER_CATEGORIES or not p or p.stage != 500
            or getattr(ses, 'dlg_ent', None) != 721):
        return False
    c = _casa_actual(ses)
    def reply(message):
        line = dialogos.armar_linea(message, 0, [7850])
        ses.dlg_guion, ses.dlg_paso, ses.dlg_val = [line[2:]], 1, 0
        ses.enviar(line)
    if c.owner_id != p.char_id:
        reply(7873)
        return True
    if not c.cleanliness or getattr(ses, 'house_furnishing', False):
        reply(7923)
        return True
    if c.level < 4:
        reply(7852)
        return True
    plan = hs.producer_order_plan(option, ses.inventario, _cantidades(ses),
                                  _tope_bolsa(ses.inventario))
    if not plan:
        reply(7860)
        return True
    row, slots = plan
    consumption = [(s, ses.inventario[s], amount, _cant_de(ses, s)) for s, amount in slots]
    rewards = dict(exp=int(row.get('經驗值') or 0), oro=int(row.get('金錢') or 0),
                   creditos=int(row.get('功勳值') or 0))
    snapshot = dict(inventario={str(s): i for s, i in ses.inventario.items()},
                    cantidades={str(s): n for s, n in _cantidades(ses).items()})
    preview, _ = apply_delivery(snapshot, consumption, rewards)
    bonus = None
    bonus_item = int(row.get('額外獎賞') or 0)
    if bonus_item and random.random() * 100 < float(row.get('獎賞機率') or 0):
        future = {int(s): i for s, i in preview['inventario'].items()}
        dest = next((s for s, i in future.items()
                     if 20 <= s <= _tope_bolsa(future) and i == bonus_item
                     and inventario.es_apilable(bonus_item)), None)
        if dest is None:
            dest = _ranura_libre(future)
        if dest is None:
            reply(7860)
            return True
        bonus = (dest, bonus_item, int(row.get('獎賞數量') or 1))
    try:
        if getattr(ses, 'usuario', None):
            after, touched = cuentas.confirmar_entrega_productor(
                ses.usuario, p.char_id, consumption, rewards, bonus)
        else:
            after, touched = apply_delivery(snapshot, consumption, rewards, bonus)
    except Exception:
        log.exception('house: producer delivery rejected without consumption')
        reply(7860)
        return True
    # No await between planning, commit and applying these validated slot deltas.
    consumed_all = {slot for slot, item, amount, expected in consumption if amount == expected}
    for key in touched:
        slot = int(key)
        if key in after['inventario']:
            item = after['inventario'][key]
            if slot not in ses.inventario or slot in consumed_all:
                _instancias(ses)[slot] = inventario.instancia_nueva()
                p.mejoras.pop(slot, None)
            ses.inventario[slot] = item
            p.inventario[slot] = item
            _cantidades(ses)[slot] = int(after['cantidades'].get(key, 1))
        else:
            ses.inventario.pop(slot, None)
            p.inventario.pop(slot, None)
            _cantidades(ses).pop(slot, None)
            _instancias(ses).pop(slot, None)
            p.mejoras.pop(slot, None)
    progress = reward_progress(
        dict(exp=p.exp, oro=ses.oro, creditos=p.creditos, nivel=p.nivel,
             rango=p.rango, hp_max=p.hp_max, mp_max=p.mp_max), rewards,
        combate.exp_para_nivel, combate.nivel_maximo(), combate.rango_de_creditos)
    old_level, old_rank = p.nivel, p.rango
    for key, value in progress.items():
        setattr(p, key, value)
    ses.oro = p.oro
    actual, following = combate.exp_para_barra(p.nivel, p.exp)
    ses.enviar(*_refrescar(ses, [int(s) for s in touched], con_oro=True),
               struct.pack('<HIB', 0x001D, p.entity_id, 4)
               + struct.pack('<BQ', 29, p.nivel)
               + struct.pack('<BQ', 30, combate.exp_para_nivel(p.nivel))
               + struct.pack('<BQ', 31, following) + struct.pack('<BQ', 32, actual),
               combate.atributo(p.entity_id, p.creditos, combate.KIND_CREDITO),
               combate.atributo(p.entity_id, p.rango, combate.KIND_RANGO), _stats_ses(ses))
    if p.nivel > old_level:
        ses.enviar(combate.efecto_level_up(p.entity_id))
    if p.rango > old_rank:
        ses.enviar(combate.efecto_level_up(p.entity_id, es_rango=True))
    for amount, message in ((rewards['exp'], clases.MSG_EXP),
                            (rewards['oro'], clases.MSG_PAGO), (rewards['creditos'], 642)):
        if amount:
            ses.enviar(clases.aviso(str(amount), tipo=0, msg_id=message))
    reply(7859)
    return True


def _casa_tick_limpieza(ses, now=None, flush=False):
    import casas
    p = getattr(ses, 'personaje', None)
    if p is None:
        return
    now = time.monotonic() if now is None else now
    previous = getattr(ses, 'house_online_tick', None)
    if getattr(ses, 'house_online_character', None) != p.char_id:
        previous = None
        ses.house_online_character = p.char_id
    ses.house_online_tick = now
    if previous is None:
        return
    # Count the owner's connection, including time spent outside their house.
    c = casas.obtener_o_crear_casa(p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
    changed = c.avanzar_tiempo_conectado(max(0.0, now - previous))
    if changed or flush:
        p.casa = c.serializar()
        if getattr(ses, 'usuario', None):
            cuentas.guardar_casa(ses.usuario, p.char_id, c)
    if changed:
        lv, prev, nxt = casas.info_nivel(c.calcular_magia())
        ses.enviar_inmediato(casas.pkt_house_info(
            lv, c.calcular_magia(), nxt, prev, c.bonus_pct, c.cleanliness,
            c.votes_total, c.votes_today, c.visitors_total,
            int(p.char_id not in c.voted_users_today), casas.rango_casa(c),
            10 if c.is_open else 1))


def _casa_invocar_mercenario(ses, tx=0, ty=0):
    import house_services as hs, combate, clases, login
    p = ses.personaje
    contract = (getattr(p, 'buffs', {}) or {}).get(2254) or {}
    now = time.time()
    if contract.get('fin', 0) <= now:
        ses.enviar(clases.aviso("Activate a Mercenary Token first.", tipo=0))
        return
    if now - getattr(ses, 'mercenary_last_cast', 0) < hs.TOKEN_COOLDOWN:
        ses.enviar(clases.aviso("Summon Mercenary can be used every 3 minutes.", tipo=0))
        return
    row = hs.mercenary_for(p.nivel)
    if not row:
        return
    info = hs.summon_stats(row)
    old = getattr(ses, 'invocacion', None)
    if old:
        ses.enviar(combate.despawn_monstruo(old['entity_id']))
        import presencia
        presencia.notificar_invocacion_despawn(ses, old['entity_id'])
    eid = p.entity_id + 8000
    if max(abs(tx - p.tile_x), abs(ty - p.tile_y)) > 12 or not tx or not ty:
        tx, ty = p.tile_x + 1, p.tile_y
    ses.invocacion = dict(info, entity_id=eid, npc_type=row['id'],
                         hp_max=info['hp'], defensa=info['def'],
                         tile_x=tx, tile_y=ty, expira=min(contract['fin'], now + 3600),
                         es_mercenario=True, stage=p.stage,
                         objetivo=None, ultimo_ataque=0.0, proximo_paso=0.0)
    ses.mercenary_last_cast = now
    for slot, item in ses.inventario.items():
        if item == 10581 and p.mejoras.get(slot, {}).get('mercenary_token_deadline') == contract['fin']:
            p.mejoras[slot]['mercenary_next_summon'] = now + hs.TOKEN_COOLDOWN
            _guardar_bolsa(ses, p.char_id)
            break
    spawn = login.spawn_invocacion(eid, row['id'], info['nombre'], (tx, ty), sprite=info['sprite'])
    hp = combate.atributo(eid, 100, combate.KIND_HP)
    ses.enviar(spawn, hp,
               struct.pack('<HIBBI', 0x0013, p.entity_id, 1, 0x3d, eid),
               struct.pack('<HIBBI', 0x0013, eid, 1, 0x3c, p.entity_id),
               struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 3, 2254, 180000))
    import presencia
    presencia.notificar_invocacion_spawn(ses, ses.invocacion, spawn, hp)




def _casa_sincronizar_token(ses):
    """Expire real inventory tokens; never grant a permanent summon skill."""
    import house_services as hs, combate
    p = ses.personaje
    now = time.time()
    touched = []
    if not getattr(ses, 'house_mercenary_migrated', False):
        legacy_fin = (p.buffs.get(2254) or {}).get('fin', 0)
        if legacy_fin > now and 10581 not in ses.inventario.values():
            slot = _meter(ses, 10581, 1)
            if slot is not None:
                p.mejoras.setdefault(slot, {})['mercenary_token_deadline'] = legacy_fin
                touched.append(slot)
            else:
                return  # Retry when there is room, without extending the contract.
        ses.house_mercenary_migrated = True
    for slot, item in list(ses.inventario.items()):
        if item != 10581:
            continue
        meta = p.mejoras.setdefault(slot, {})
        if not meta.get('mercenary_token_deadline'):
            # Preserve the remaining contract time of pre-fix characters.
            legacy = (p.buffs.get(2254) or {}).get('fin', 0)
            meta['mercenary_token_deadline'] = legacy if legacy > now else now + hs.TOKEN_SECONDS
            touched.append(slot)
        if meta['mercenary_token_deadline'] <= now:
            _sacar(ses, slot, _cant_de(ses, slot))
            p.mejoras.pop(slot, None)
            touched.append(slot)
    if touched:
        ses.enviar_inmediato(*_refrescar(ses, touched))
        _guardar_bolsa(ses, p.char_id)
    summon = getattr(ses, 'invocacion', None)
    if summon and summon.get('es_mercenario') and (summon.get('stage') != p.stage or summon['expira'] <= now):
        ses.enviar_inmediato(combate.despawn_monstruo(summon['entity_id']))
        import presencia
        presencia.notificar_invocacion_despawn(ses, summon['entity_id'])
        ses.invocacion = None
    if not getattr(ses, 'house_mercenary_skill_removed', False):
        ses.enviar_inmediato(struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 9, 2254, 0))
        ses.house_mercenary_skill_removed = True


def _casa_usar_token(ses, slot):
    import house_services as hs, clases
    p = ses.personaje
    if p.nivel < 30:
        ses.enviar(clases.aviso("Mercenary Token requires level 30.", tipo=0))
        return
    _casa_sincronizar_token(ses)
    if ses.inventario.get(slot) != 10581:
        return
    meta = p.mejoras[slot]
    fin = meta['mercenary_token_deadline']
    ses.mercenary_last_cast = meta.get('mercenary_next_summon', 0) - hs.TOKEN_COOLDOWN
    p.buffs[2254] = dict(fin=fin, nombre='Mercenary Token', icono=10794)
    ses.enviar(struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 4, 2254,
                           max(0, int((fin - time.time()) * 1000))))
    _casa_invocar_mercenario(ses)

def _intentar_captura_monstruo(ses, target_entity, addr='?'):
    """Resolve a pending Poke Egg against one clicked monster.

    Returns True when a capture cursor was active, even if the target was
    invalid, so that the same click is never also treated as a normal attack.
    """
    pending = getattr(ses, 'captura_pendiente', None)
    if not pending:
        return False
    ses.captura_pendiente = None

    import house_services as _hs_cap
    import clases as _cl_cap
    import combate as _cb_cap

    if time.time() - float(pending.get('time') or 0) > 30.0:
        ses.enviar(_cl_cap.aviso('The Poke Egg selection expired.', tipo=7,
                                 msg_id=_cl_cap.MSG_TEXTO))
        return True
    slot = int(pending.get('slot', -1))
    item_id = int(pending.get('item', 0))
    strengths = _hs_cap.capture_eggs()
    if ((getattr(ses, 'inventario', {}) or {}).get(slot) != item_id
            or item_id not in strengths):
        ses.enviar(_cl_cap.aviso('The Poke Egg is no longer available.', tipo=7,
                                 msg_id=_cl_cap.MSG_TEXTO))
        return True

    monster = (getattr(ses, 'monstruos', {}) or {}).get(int(target_entity))
    if monster is None or not getattr(monster, 'vivo', False):
        ses.enviar(_cl_cap.aviso('Select a living monster to capture.', tipo=7,
                                 msg_id=_cl_cap.MSG_TEXTO))
        return True

    output_item = _hs_cap.capturable_monsters().get(int(monster.npc_type))
    if not output_item:
        ses.enviar(_cl_cap.aviso('This pet cannot be captured.', tipo=7,
                                 msg_id=_cl_cap.MSG_TEXTO))
        return True

    if getattr(monster, 'captura_fallida_en', None):
        ses.enviar(_cl_cap.aviso(
            'This monster has already escaped a capture attempt.', tipo=7,
            msg_id=_cl_cap.MSG_TEXTO))
        return True


    # El monstruo debe estar debilitado y el jugador debe haberlo golpeado primero
    p = getattr(ses, 'personaje', None)
    p_eid = getattr(p, 'entity_id', None) or getattr(ses, 'entity_id', None) or 1
    char_id = getattr(p, 'char_id', None)
    pet_eid = getattr(ses, 'pet_entity_id', None)
    ident_cap = _hs_cap.captured_monster_identity(monster.npc_type)
    player_level = int(getattr(p, 'nivel', 0) or 0)
    monster_level = int(ident_cap.get('nivel') or 0)
    if player_level and monster_level and player_level <= monster_level:
        ses.enviar(_cl_cap.aviso(
            'Your level must be higher than the monster level to capture it.',
            tipo=7, msg_id=_cl_cap.MSG_TEXTO))
        return True

    dano_por = getattr(monster, 'dano_por', None)
    if not isinstance(dano_por, dict):
        dano_por = {}
    in_combat = getattr(monster, 'en_combate_con', None) in (p_eid, pet_eid)
    dealt_damage = (
        (char_id is not None and dano_por.get(int(char_id), 0) > 0)
        or in_combat
        or (getattr(monster, 'dano_jugador', 0) > 0 and not dano_por)
        or (getattr(monster, 'dano_pet', 0) > 0 and not dano_por)
    )

    if monster.hp >= monster.hp_max or not dealt_damage:
        ses.enviar(_cl_cap.aviso('You must attack and weaken the monster before capturing it!', tipo=7,
                                 msg_id=_cl_cap.MSG_TEXTO))
        return True

    # Monster Eggs are individual objects. If the used stack will remain,
    # reserve another backpack cell before consuming or rolling.
    if _cant_de(ses, slot) > 1 and _ranura_libre(ses.inventario) is None:
        ses.enviar(_cl_cap.aviso('Your backpack is full.', tipo=7,
                                 msg_id=_cl_cap.MSG_TEXTO))
        return True

    chance = _hs_cap.capture_chance(strengths[item_id], max(1, monster.hp),
                                    monster.hp_max, npc_type=monster.npc_type)
    _sacar(ses, slot, 1)
    touched = [slot]

    # Visual de captura: el personaje realiza la animacion de lanzamiento hacia el monstruo.
    # No se envia ningun efecto de dano ni veneno (efecto 63) sobre el monstruo.
    # NOTE: Never send confirmar_cast (0x0006) here, as that opcode puts
    # the client into a waiting cast state and locks character movement.
    anim_pkts = _cb_cap.efecto_captura(
        p_eid, monster.entity_id, monster.tile_x, monster.tile_y, item_id)
    ses.enviar(*anim_pkts)
    for companion in _companeros(ses):
        try:
            companion.enviar(*anim_pkts)
        except Exception:
            pass

    success = random.random() * 100.0 < chance
    if success:
        import mascotas as _ms_cap
        rango, rango_nom = _ms_cap.sortear_rango()
        short_name = _ms_cap.abreviar_nombre_pet(monster.nombre)
        captured_tipo = int(getattr(monster, 'sprite', 0) or ident_cap.get('sprite') or 0)
        pet_meta = {
            'nombre': short_name,
            'npc_type': int(monster.npc_type),
            'rango': rango,
            'rango_nombre': rango_nom,
            'captured_name': short_name,
            'captured_tipo': captured_tipo,
        }
        destination = _meter(ses, output_item, 1, pet_metadata=pet_meta)
        if destination is not None:
            touched.append(destination)
            p_ses = getattr(ses, 'personaje', None)
            if p_ses and getattr(p_ses, 'mascotas', None):
                ficha = p_ses.mascotas.get(str(destination))
                if ficha:
                    _ms_cap.aplicar_rango(ficha, rango=rango)
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mascota(ses.usuario, p_ses.char_id, ficha, p_ses.mascotas)

        # Al capturar con exito, el monstruo se stunea brevemente y luego se
        # desvanece del mapa sin reproducir animacion de muerte (muerte_monstruo).
        # Hacia el personaje se reproduce el efecto visual de captura.
        capture_started = time.time()
        capture_stun_seconds = 1.3
        monster.hp = 0
        monster.muerto_en = capture_started
        monster.capturado_en = capture_started
        monster.aturdido_hasta = capture_started + capture_stun_seconds
        monster.en_combate_con = None
        monster.dano_por = {}
        stun_pkt = struct.pack('<HIBBII', 0x001D, monster.entity_id, 1, 4,
                               1045, int(capture_stun_seconds * 1000))
        ses.enviar(stun_pkt)
        for companion in _companeros(ses):
            try:
                companion.enviar(stun_pkt)
            except Exception:
                pass

        def _capture_despawn(eid=monster.entity_id, captured_at=capture_started):
            if getattr(monster, 'capturado_en', None) != captured_at:
                return
            packets = (
                struct.pack('<HIBBII', 0x001D, eid, 1, 4, 1045, 0),
                _cb_cap.despawn_monstruo(eid),
            )
            ses.enviar_inmediato(*packets)
            for companion in _companeros(ses):
                try:
                    companion.enviar_inmediato(*packets)
                except Exception:
                    pass
            # Dynamically generated monsters have no ordinary map respawn.
            if getattr(monster, 'generado', False):
                (getattr(ses, 'monstruos', {}) or {}).pop(eid, None)
                room = _sala_de(ses)
                if room is not None and getattr(room, 'monstruos', None):
                    room.monstruos.pop(eid, None)

        def _capture_respawn(eid=monster.entity_id):
            if getattr(monster, 'generado', False):
                return
            if (getattr(ses, 'monstruos', {}) or {}).get(eid) is not monster:
                return
            if not getattr(monster, 'vivo', False):
                monster.revivir()
                import login as _lg_cap
                sp_pkg = _lg_cap._npc_spawn(
                    eid, monster.npc_type, monster.nombre, (monster.tile_x, monster.tile_y),
                    sprite=getattr(monster, 'sprite', 0), klass=1)
                ses.enviar_inmediato(sp_pkg)
                for comp in _companeros(ses):
                    try:
                        comp.enviar_inmediato(sp_pkg)
                    except Exception:
                        pass
                log.info('[%s] captured monster %s (eid=%s) respawned at (%s, %s)',
                         addr, monster.nombre, eid, monster.tile_x, monster.tile_y)

        try:
            import asyncio as _aio_capture
            try:
                loop = _aio_capture.get_running_loop()
            except RuntimeError:
                loop = _aio_capture.get_event_loop()
            loop.call_later(capture_stun_seconds, _capture_despawn)
            loop.call_later(capture_stun_seconds + _cb_cap.SEGUNDOS_REAPARICION, _capture_respawn)
        except Exception:
            _capture_despawn()
        ses.enviar(_cl_cap.aviso(
            f'Capture successful! You obtained {rango_nom}-{monster.nombre} ({_nombre_item(output_item)}).',
            tipo=7, msg_id=_cl_cap.MSG_TEXTO))
        log.info('[%s] captured %s (npc=%s, rank=%s) with item %s at %.1f%%',
                 addr, monster.nombre, monster.npc_type, rango_nom, item_id, chance)
    else:
        monster.captura_fallida_en = time.time()
        ses.enviar(_cl_cap.aviso('Capture failed.', tipo=7, msg_id=_cl_cap.MSG_TEXTO))
        log.info('[%s] failed capture of %s (npc=%s) with item %s at %.1f%%',
                 addr, monster.nombre, monster.npc_type, item_id, chance)

    ses.enviar(*_refrescar(ses, sorted(set(touched))))
    if getattr(ses, 'personaje', None):
        _guardar_bolsa(ses, ses.personaje.char_id)
    return True


def _casa_tick_monstruos(ses):
    """Materialize the real Monster Egg currently occupying each unlocked slot."""
    p = getattr(ses, 'personaje', None)
    if not p or p.stage != 500 or not getattr(ses, 'house_room_ready', False):
        return
    import house_services as hs, casas, combate, login
    c = _casa_actual(ses)
    now = time.time()
    active = getattr(ses, 'house_egg_entities', None)
    if active is None:
        active = ses.house_egg_entities = {}
    enabled = (c.owner_id == p.char_id and c.cleanliness > 0
               and not getattr(ses, 'house_furnishing', False))
    limit = casas.ranuras_mobgen_validas(c.level) if enabled else 0
    eggs = hs.monster_eggs()
    dirty = False
    for slot in range(487, 497):
        item = (getattr(ses, 'inventario', {}) or {}).get(slot)
        row = eggs.get(item)
        valid = bool(row and slot < 487 + limit)
        uid = str(_inst(ses, slot)) if valid else ''
        # Per-item metadata already travels with _mover_inst and is saved by
        # guardar_mejoras. Network instance IDs are regenerated on reconnect.
        metadata = getattr(p, 'mejoras', {}) or {}
        egg_state = metadata.get(slot) or {}
        deadline = egg_state.get('house_egg_deadline') if valid else None
        if valid and deadline is None and int(row.get('持續時間') or 0) > 0:
            deadline = now + int(row['持續時間']) * 60
            if not isinstance(getattr(p, 'mejoras', None), dict):
                p.mejoras = {}
            p.mejoras.setdefault(slot, {})['house_egg_deadline'] = deadline
            dirty = True
        if deadline is not None and deadline <= now:
            valid = False
        old = active.get(slot)
        if old and (not valid or old['uid'] != uid):
            ses.enviar_inmediato(combate.despawn_monstruo(old['eid']))
            (getattr(ses, 'monstruos', {}) or {}).pop(old['eid'], None)
            active.pop(slot, None)
            old = None
        if not valid:
            continue
        if old:
            monster = (getattr(ses, 'monstruos', {}) or {}).get(old['eid'])
            if monster and monster.vivo:
                continue
            interval = int(row.get('動態資料2') or 0)
            if monster and (not interval or now - (getattr(monster, 'muerto_en', None) or now) < max(3, interval)):
                continue
        npc = int(row.get('動態資料1') or 0)
        mobrow = hs.xml_rows('monster.xml').get(npc)
        if not mobrow:
            continue
        # New IDs avoid cached dead entities swallowing the next spawn.
        seq = getattr(ses, 'house_egg_sequence', 0) + 1
        ses.house_egg_sequence = seq
        eid = 120000000 + seq
        tile = (83 + (slot - 487) * 5, 23)
        monster = combate.Monstruo(eid, npc, mobrow['名稱'], tile, sprite=int(mobrow['圖號']))
        monster.house_egg = True
        monster.generado = True  # the egg, not the normal map respawner, owns its lifecycle.
        if getattr(ses, 'monstruos', None) is None:
            ses.monstruos = {}
        ses.monstruos[eid] = monster
        if old:
            ses.monstruos.pop(old['eid'], None)
        active[slot] = dict(eid=eid, uid=uid)
        ses.enviar_inmediato(login._npc_spawn(eid, npc, mobrow['名稱'], tile,
                                            sprite=int(mobrow['圖號']), klass=1))
    if dirty:
        _guardar_bolsa(ses, p.char_id)

def _casa_fabricar(ses, recipe_id):
    """Run one XML recipe; the client requests the next queued unit after 0x4C."""
    import house_services as hs, clases
    station_id = getattr(ses, 'house_make_station', None)
    station = hs.PRODUCTION.get(station_id)
    if not station or not ses.personaje or ses.personaje.stage != 500:
        return
    c = _casa_actual(ses)
    row = hs.recipe(recipe_id)
    if row and row.get('參考掉寶') == '是':
        ses.enviar(struct.pack('<H', 0x004D), clases.aviso(
            "This recipe's random reward table is not reconstructed yet; no materials were used.", tipo=0))
        return
    if (not row or c.owner_id != ses.personaje.char_id or c.level < 2
            or not c.cleanliness or getattr(ses, 'house_furnishing', False)):
        ses.enviar(struct.pack('<H', 0x004D))
        return
    skill = station[2]
    required_skill = int(row.get('技能1') or 0)
    required_level = int(row.get('等級1') or 0)
    if required_skill != skill or not any(
            int(h[0]) == skill and int(h[1]) >= required_level
            for h in ses.personaje.habilidades):
        ses.enviar(struct.pack('<H', 0x004D))
        return
    task = getattr(ses, 'house_make_task', None)
    if task and not task.cancelled():
        return
    def finish():
        ses.house_make_task = None
        if (not getattr(ses, 'conectado', True) or ses.personaje.stage != 500
                or getattr(ses, 'house_make_station', None) != station_id):
            return
        current = _casa_actual(ses)
        if not current.cleanliness or current.level < 2 or getattr(ses, 'house_furnishing', False):
            ses.enviar_inmediato(struct.pack('<H', 0x004D))
            return
        from collections import Counter
        needed = Counter()
        for i in range(1, 7):
            it, qty = int(row.get('原料%d' % i) or 0), int(row.get('數量%d' % i) or 0)
            if it and qty:
                needed[it] += qty
        plan = []
        for it, qty in needed.items():
            for slot, item in sorted(ses.inventario.items()):
                if not 20 <= slot <= _tope_bolsa(ses.inventario) or item != it:
                    continue
                take = min(qty, _cant_de(ses, slot))
                plan.append((slot, take))
                qty -= take
                if qty == 0:
                    break
            if qty:
                ses.enviar_inmediato(struct.pack('<H', 0x004D),
                    clases.aviso("You don't have enough crafting materials.", tipo=0))
                return
        result_id = int(row.get('物品編號') or 0)
        import inventario
        if (not result_id or (_ranura_libre(ses.inventario) is None
                and not (inventario.es_apilable(result_id) and result_id in ses.inventario.values())
                and not any(_cant_de(ses, slot) == qty for slot, qty in plan))):
            ses.enviar_inmediato(struct.pack('<H', 0x004D))
            return
        touched = [slot for slot, _ in plan]
        for slot, qty in plan:
            _sacar(ses, slot, qty)
        success = random.randrange(100) < int(row.get('成功機率') or 100)
        if success:
            slot = _meter(ses, result_id, int(row.get('製作數量') or 1))
            touched.append(slot)
        _guardar_bolsa(ses, ses.personaje.char_id)
        ses.enviar_inmediato(*_refrescar(ses, touched),
                            struct.pack('<HBI', 0x004C, int(success), recipe_id))
    delay = max(0.1, int(row.get('製作時間') or 1))
    ses.house_make_task = asyncio.get_event_loop().call_later(delay, finish)

def _casa_buff_diario(ses, addr):
    import clases as _cl, casas as _cs_b, time as _time, dialogos as _dlg_b
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    c = getattr(ses, 'casa_visitando', None) or _cs_b.obtener_o_crear_casa(
        p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
    if c.owner_id != p.char_id or c.cleanliness <= 0:
        return
    lv = max(1, min(15, _cs_b.nivel_de_magia(c.calcular_magia())))

    hoy = _time.strftime('%Y-%m-%d')
    if c.last_blessing_day == hoy or getattr(p, 'ultimo_house_buff', None) == hoy:
        ses.enviar(_dlg_b.armar_linea(7921, _dlg_b.MAID_PORTRAIT, []), struct.pack('<H', 0x0012) + _dlg_b.FIN)
        return

    if lv < 4:
        ses.enviar(_dlg_b.armar_linea(7920, _dlg_b.MAID_PORTRAIT, []), struct.pack('<H', 0x0012) + _dlg_b.FIN)
        return

    import house_services as _hs_b
    profile = _hs_b.blessing_profile(lv)
    tier = profile['tier']
    msg_id = 7919

    p.ultimo_house_buff = hoy
    c.last_blessing_day = hoy
    dur_ms = profile['duration_seconds'] * 1000
    pfin = _time.time() + (dur_ms / 1000.0)
    magic_id = 2291 + tier
    p.buffs.pop('eilian_blessing', None)
    p.buffs.pop(7903, None)
    p.buffs[magic_id] = dict(profile, **{
        'fin': pfin,
        'nombre': f"Maid Eilian's Blessing {tier}",
        'magic_id': magic_id,
        'tier': tier,
        'icono': 10829,
    })
    p.casa = c.serializar()
    if getattr(ses, 'usuario', None):
        cuentas.guardar_casa(ses.usuario, p.char_id, c)
        cuentas.guardar_progreso(ses.usuario, p.char_id, p.nivel, p.exp,
            p.hp, p.mp, p.habilidades, buffs=p.buffs)
    ses.enviar(struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 4, magic_id, dur_ms))
    ses.enviar(_dlg_b.armar_linea(msg_id, _dlg_b.MAID_PORTRAIT, []), struct.pack('<H', 0x0012) + _dlg_b.FIN)
    ses.enviar(_cl.aviso(f"Received Maid Eilian's Blessing {tier} for equipment enhancement (3 hours).", tipo=7, msg_id=_cl.MSG_TEXTO))


def _casa_recibir_token(ses, addr):
    import clases as _cl, casas as _cs_tk, time as _time, dialogos as _dlg_tk
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    c = getattr(ses, 'casa_visitando', None) or _cs_tk.obtener_o_crear_casa(
        p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
    if c.owner_id != p.char_id or c.cleanliness <= 0:
        return
    lv = max(1, min(15, _cs_tk.nivel_de_magia(c.calcular_magia())))

    if lv < 2:
        ses.enviar(_dlg_tk.armar_linea(7926, _dlg_tk.MAID_PORTRAIT, []), struct.pack('<H', 0x0012) + _dlg_tk.FIN)
        return

    hoy = _time.strftime('%Y-%m-%d')
    # The map's original grant has no daily flag. Do not duplicate a live
    # token or replace an 8-hour entitlement with another token.
    misplaced = next((r for r, it in (getattr(ses, 'inventario', {}) or {}).items()
                      if it == 10581 and 11 <= r < 20), None)
    if misplaced is not None:
        visible = _ranura_libre(ses.inventario)
        if visible is None:
            ses.enviar(_dlg_tk.armar_linea(7917, _dlg_tk.MAID_PORTRAIT, []))
            return
        ses.inventario[visible] = ses.inventario.pop(misplaced)
        _cantidades(ses)[visible] = _cantidades(ses).pop(misplaced, 1)
        _mover_inst(ses, misplaced, visible)
        ses.enviar(*_refrescar(ses, [misplaced, visible]))
        _guardar_bolsa(ses, p.char_id)
        return
    if (10581 in (getattr(ses, 'inventario', {}) or {}).values()
            or (getattr(p, 'buffs', {}).get(2254) or {}).get('fin', 0) > _time.time()):
        ses.enviar(_cl.aviso("You already have a Mercenary Token or an active contract.", tipo=0))
        return
    ranura_libre = _meter(ses, 10581, 1)
    if ranura_libre is None:
        ses.enviar(_dlg_tk.armar_linea(7917, _dlg_tk.MAID_PORTRAIT, []), struct.pack('<H', 0x0012) + _dlg_tk.FIN)
        return

    p.ultimo_mercenary_token = hoy
    import house_services as hs
    p.mejoras.setdefault(ranura_libre, {})['mercenary_token_deadline'] = _time.time() + hs.TOKEN_SECONDS
    ses.enviar(*_refrescar(ses, [ranura_libre]))
    _guardar_bolsa(ses, p.char_id)
    ses.enviar(_dlg_tk.armar_linea(7918, _dlg_tk.MAID_PORTRAIT, []), struct.pack('<H', 0x0012) + _dlg_tk.FIN)
    ses.enviar(_cl.aviso("Received Mercenary Token from Maid Eilian!", tipo=7, msg_id=_cl.MSG_TEXTO))


def _casa_abrir_pets(ses, addr):
    import casas as _cs, mascotas as _ms
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    c = getattr(ses, 'casa_visitando', None) or _cs.obtener_o_crear_casa(p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
    lv = _cs.nivel_de_magia(c.calcular_magia())
    valid_slots = _cs.ranuras_mascotas_validas(lv)
    slots_ref = list(range(477, 477 + valid_slots))
    salida = _refrescar(ses, slots_ref)
    salida.append(_cs.pkt_pet_slot_wnd(True, valid_slots, c.pet_radio))
    ses.enviar(*salida)


def _casa_abrir_mobgen(ses, addr):
    import casas as _cs
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    c = getattr(ses, 'casa_visitando', None) or _cs.obtener_o_crear_casa(p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
    lv = _cs.nivel_de_magia(c.calcular_magia())
    valid_slots = _cs.ranuras_mobgen_validas(lv)
    slots_ref = list(range(487, 487 + valid_slots))
    ses.enviar(_cs.pkt_mobgen_slot_wnd(True, valid_slots), *_refrescar(ses, slots_ref))


def _casa_limpiar(ses, addr, item_id, count, clean_amount):
    import casas as _cs, clases as _cl, cuentas as _cta
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    c = getattr(ses, 'casa_visitando', None) or _cs.obtener_o_crear_casa(p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
    if c.cleanliness >= 1000:
        ses.enviar(_cl.aviso("The house is already spotless!", tipo=7, msg_id=_cl.MSG_TEXTO))
        return
    r = _ranura_de_item(ses, item_id)
    if r is None or _cant_de(ses, r) < count:
        ses.enviar(_cl.aviso(f"Need {count}x {_nombre_item(item_id)} to clean!", tipo=7, msg_id=_cl.MSG_TEXTO))
        return
    _sacar(ses, r, count)
    ses.enviar(*_refrescar(ses, [r]))
    c.cleanliness = min(1000, c.cleanliness + clean_amount)
    if getattr(ses, 'usuario', None):
        _cta.guardar_casa(ses.usuario, c.owner_id, c)
    lv, prev_m, next_m = _cs.info_nivel(c.calcular_magia())
    rank = _cs.rango_casa(c)
    v_rem = 1 if (p.char_id not in c.voted_users_today) else 0
    ses.enviar(_cs.pkt_house_info(lv, c.calcular_magia(), next_m, prev_m, c.bonus_pct, c.cleanliness, c.votes_total, c.votes_today, c.visitors_total, v_rem, rank, 10 if c.is_open else 1))
    ses.enviar(_cl.aviso(f"House cleaned! Cleanliness is now {c.cleanliness}.", tipo=7, msg_id=_cl.MSG_TEXTO))


def _casa_abrir_voto(ses, addr):
    import casas as _cs
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    c = getattr(ses, 'casa_visitando', None) or _cs.obtener_o_crear_casa(p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
    ses.enviar(_cs.pkt_open_cast_vote(c.owner_name))


def _casa_ver_notas(ses, addr):
    import casas as _cs
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    c = getattr(ses, 'casa_visitando', None) or _cs.obtener_o_crear_casa(p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
    notes = c.vote_notes[:5]
    ses.enviar(_cs.pkt_view_vote_notes(0, len(c.vote_notes), notes))


def _casa_hitparade(ses, addr):
    import casas as _cs
    res = _cs.ranking_hitparade(31, 0)
    ses.enviar(_cs.pkt_hitparade_data(31, 0, len(res), res))


def _aplicar_efectos(ses, addr, efectos, motivo=''):
    """Obedece los efectos que devuelve el interprete de eventos.

    server/eventos.py lee la logica de los .mpc y devuelve EFECTOS; no toca
    nada. Esta funcion es la que si toca, y a proposito no obedece todo: solo
    lo que se sabe hacer SIN inventarse un paquete. Lo demas se cuenta en el
    registro, que es como se ve que falta.

    LO QUE QUEDA FUERA Y POR QUE. El grande es 52 CHANGE_STATICOBJ, el que
    abre las puertas de las instancias. Se sabe lo que quiere decir -- pon el
    objeto N en el TAG T -- y donde cae el TAG, pero no como se le dice al
    cliente: de los 23 objetos que usan los mapas solo UNO tiene cuerpo
    capturado, y los demas los dibuja el cliente por su cuenta desde el .mpc,
    asi que no tienen id de entidad del servidor al que referirse. Mandar un
    0x000E rearmado es justo lo que login.objeto_de_mapa avisa que no
    equivale: los objetos reconstruidos no coinciden byte a byte con los que
    mandaba el servidor original. Hace falta UNA captura abriendo una puerta
    con el cliente oficial y el proxy puesto; hasta entonces el efecto se
    apunta en el estado y se registra, pero no se manda nada.

    Tampoco se obedece 25 BEGIN_MESSAGE todavia: el numero que trae es de los
    dialogos DEL MAPA -- el segundo xml del .mpc -- y la plantilla de eventos
    no los lleva, solo el numero.
    """
    import eventos as _ev
    import eventos_mundo as _evm
    if not efectos:
        return
    estado = _evm.estado_de(ses)
    p = ses.personaje
    sin_hacer = []
    for ef in efectos:
        que = ef[0]
        try:
            if que == 'dar':
                tocadas = []
                import clases as _cl
                import inventario as _iv_ef
                for item, cant in ef[1]:
                    iid = int(item)
                    # Los tokens de mision NO van a la mochila, pero tampoco
                    # se tiran: van a las ranuras ocultas 497..556. Ahi los
                    # lee la condicion QUESTITEM para saber si ya van 30 y
                    # ahi los lee el HUD para el "X/30". Descartandolos, la
                    # 901 se quedaba en 0/30 por muchos dragones que cayeran.
                    if _iv_ef.es_item_oculto(iid) or _ev.es_objeto_de_mision(iid):
                        _dar_token_oculto(ses, addr, iid, int(cant))
                        continue
                    r = _meter(ses, iid, int(cant))
                    if r is not None:
                        tocadas.append(r)
                        try:
                            ses.enviar(_cl.aviso(_nombre_item(iid), tipo=0, msg_id=_cl.MSG_ITEM))
                        except Exception:
                            pass
                if tocadas:
                    ses.enviar(*_refrescar(ses, tocadas))
                    if ses.personaje:
                        import misiones as _mis_col
                        pkgs_rec = _mis_col.verificar_progreso_recoleccion(ses, [ses.inventario.get(r) for r in tocadas])
                        if pkgs_rec:
                            ses.enviar(*pkgs_rec)
            elif que == 'quitar':
                tocadas = []
                for item, cant in ef[1]:
                    if _ev.es_objeto_de_mision(int(item)):
                        _quitar_token_oculto(ses, addr, int(item), int(cant))
                        continue
                    r = _ranura_de_item(ses, int(item))
                    if r is not None:
                        _sacar(ses, r, int(cant))
                        tocadas.append(r)
                if tocadas:
                    ses.enviar(*_refrescar(ses, tocadas))
            elif que == 'oro':
                if p:
                    p.oro = max(0, int(p.oro or 0) + int(ef[1]))
                    ses.enviar(*_refrescar(ses, [], con_oro=True))
            elif que == 'paso':
                # EL PASO VIENE EN LA NUMERACION DEL CLIENTE, que empieza en
                # 0; la del servidor empieza en 1. Es la misma conversion que
                # hace misiones.avanzar_paso al reves con su `paso - 1`.
                import misiones as _mis
                qid = int(ef[1])
                paso_servidor = int(ef[2]) + 1
                if not _mis.tiene_mision(p, qid):
                    _mis.aceptar_mision(ses, qid)
                # Y solo si CAMBIA. Un evento de pisar salta cada vez que te
                # paras encima, y sin esto el cartel se repetia en cada paso.
                if _mis.obtener_paso_actual(p, qid) != paso_servidor:
                    _mis.avanzar_paso(ses, qid, paso_servidor)
            elif que == 'matar_para_avanzar':
                # KILLTO_NEXTSTEP(mision, paso, objeto oculto, por baja,
                # probabilidad, cuantos para completar), tal como lo firma el
                # eventdef. Lo hace entero aqui, con los datos del mapa:
                #
                #   si la mision va por ese paso, con esa probabilidad, suma
                #   'por baja' del objeto oculto (a las ranuras 497..556, que
                #   es de donde el HUD saca el "X/N"); y al llegar al total,
                #   pasa al paso siguiente.
                #
                # Antes se lo pasaba al contador viejo de misiones.py con el
                # bicho en 0, y como esas entradas salieron rotas del
                # compilador, no contaba nada: 97 cacerias atascadas en 0.
                # Los 531 usos del juego llevan objeto oculto y dan 1 por baja.
                import misiones as _mis
                qid, paso_c, item, por, prob, total = (int(x) for x in ef[1:7])
                if p and _mis.obtener_paso_actual(p, qid) == paso_c + 1:
                    ahora = 0
                    _r = _ranura_oculta_de(ses, item)
                    if _r is not None:
                        ahora = int((p.cantidades or {}).get(_r, 1))
                    if ahora < total and (prob >= 100 or random.randint(1, 100) <= prob):
                        _dar_token_oculto(ses, addr, item, max(1, por))
                        ahora += max(1, por)
                    if ahora >= total:
                        # paso_c es el del CLIENTE (empieza en 0); el servidor
                        # cuenta desde 1, asi que el siguiente es paso_c + 2.
                        _mis.avanzar_paso(ses, qid, paso_c + 2)
                        log.info('[%s] mision %d: %d/%d, pasa al paso %d'
                                 % (addr, qid, ahora, total, paso_c + 2))
            elif que in ('nota', 'chat', 'chat_npc'):
                import clases as _cl
                textos = ef[1] if que == 'chat_npc' else (
                    ef[2] if que == 'chat' else [ef[1]])
                # Los textos de los eventos de mapa son de msg.xml (el 64958
                # de la lava es "Too hot!"), y el 0x000D solo entiende los
                # numeros de string.xml: mandado tal cual no salia nada. Se
                # resuelve aqui y va como texto libre.
                import dialogos as _dlg_t
                _msgs_t = _dlg_t._cargar_msg_dict()
                textos = [int(x) for x in (textos if isinstance(textos, list) else [textos]) if x]
                if que == 'chat' and textos and p:
                    # CHAT(tipo, msg1..msg5): el JUGADOR lo dice, con su
                    # bocadillo -- asi sale en el oficial el "Too hot!" de la
                    # lava y el "Terrible! Too many Monsters..." de la sala 1
                    # (en la Global llegan como 0x0017 con su entidad). De
                    # varios mensajes se dice uno al azar.
                    _txt = _msgs_t.get(random.choice(textos))
                    _quien = _jefe_que_habla(ses) if 'temporizador' in motivo else None
                    if _txt and _quien is not None:
                        _hablar_monstruo(ses, _quien, _txt)
                    elif _txt:
                        _hablar_jugador(ses, _txt)
                    textos = []
                for msg in textos:
                    _txt = _msgs_t.get(int(msg))
                    if _txt:
                        ses.enviar(_cl.aviso(_txt, tipo=0, msg_id=_cl.MSG_TEXTO))
                    else:
                        ses.enviar(_cl.aviso('', tipo=0, msg_id=int(msg)))
            elif que == 'variable':
                modo, mapa, var, valor = ef[1], ef[2], ef[3], ef[4]
                if modo == 'poner':
                    estado.poner_variable(mapa, var, valor)
                elif modo == 'sumar':
                    estado.sumar_variable(mapa, var, valor)
                else:
                    estado.sumar_variable(mapa, var, -valor)
            elif que == 'temporizador':
                # ENABLE_TIMER(tag, 1/0). El temporizador es un objeto del mapa
                # (60002, SERV_CLASS_TIMER) con su periodo y sus veces: cada
                # periodo suma una vez y dispara su evento, que mira
                # TIMER_COUNTER. En la sala 3 de la Magic Kichen Path son las
                # tres oleadas cada 60 s y el Beelzebub en la tercera.
                _arrancar_temporizador(ses, addr, estado, int(ef[1]), bool(int(ef[2] or 0)))
            elif que == 'viajar':
                # CHANGE_MAP(mapa, tag): la llegada es la primera casilla del
                # TAG en el mapa de destino. Asi llevan los objetos de mision a
                # otro mapa para seguirla.
                dst, tag = int(ef[1]), int(ef[2])
                cas = _ev.casillas_de_tag(dst, tag)
                if cas and p:
                    _viajar_por_portal(ses, addr, {'destino': dst, 'llegada': tuple(cas[0])},
                                       motivo='por un evento del mapa%s' % motivo)
            elif que == 'ir_a_tag':
                cas = _ev.casillas_de_tag(estado.stage, int(ef[1]))
                if cas and p:
                    _viajar_dentro_del_mapa(ses, addr, {'llegada': tuple(cas[0])},
                                            motivo='por un evento del mapa%s' % motivo)
            elif que == 'dialogo':
                _dialogo_del_mapa(ses, addr, estado.stage, int(ef[1]))
            elif que == 'salir_de_casa':
                _salir_de_casa(ses, addr)
            elif que == 'casa_buff_diario':
                _casa_buff_diario(ses, addr)
            elif que == 'casa_abrir_pets':
                _casa_abrir_pets(ses, addr)
            elif que == 'casa_abrir_mobgen':
                _casa_abrir_mobgen(ses, addr)
            elif que == 'casa_limpiar':
                _casa_limpiar(ses, addr, int(ef[1]), int(ef[2]), int(ef[3]))
            elif que == 'casa_abrir_voto':
                _casa_abrir_voto(ses, addr)
            elif que == 'casa_ver_notas':
                _casa_ver_notas(ses, addr)
            elif que == 'casa_hitparade':
                _casa_hitparade(ses, addr)
            elif que == 'generar':
                # UNO por GENERATE. Los mapas repiten la accion para sacar
                # varios: en 201 disparadores aparece el mismo GENERATE(tag)
                # repetido y solo en 5 las repeticiones coinciden con la
                # cantidad de la zona; la sala 3 de la Magic Kichen Path pide
                # diez GENERATE(75) por oleada. Sacando la zona entera en cada
                # uno salian 300 monstruos donde el mapa pide 10.
                _generar_zona(ses, addr, estado.stage, int(ef[1]), cuantos=1)
            elif que == 'juego_matar':
                # NPCKILLGAME. La carrera de la sala 2 de la Magic Kichen Path:
                # "limpia mas enemigos que los del Evil Lyceum en 10 minutos".
                # Ningun evento cuenta las bajas ni corta el tiempo: lo hacia
                # el servidor. Aqui cada baja del jugador suma a la variable 8
                # del mapa (la que mira el nodo 1000003: mas de 50 gana) y a
                # los 10 minutos se abre la raiz que cierra el juego (61102),
                # que decide si pasas al mapa 75 o vuelves.
                if int(ef[1] or 0):
                    fin = time.time() + DURACION_JUEGO_MATAR
                    estado.juego_matar = {'fin': fin, 'rivales': [], 'ultimo_marcador': 0}
                    _marcador_carrera(ses, estado)
                    try:
                        import asyncio as _aio_tc
                        _aio_tc.get_event_loop().call_later(
                            TIC_CARRERA, lambda _f=fin, _e=estado: _tic_carrera(ses, addr, _e, _f))
                    except Exception:
                        log.exception('no se pudo arrancar la carrera')

                    def _fin_juego(_ses=ses, _st=estado.stage, _fin=fin):
                        import dialogos_mapa as _dm_j
                        import eventos_mundo as _evm_j
                        _e = _evm_j.estado_de(_ses)
                        _j = getattr(_e, 'juego_matar', None)
                        if (not _ses.personaje or _e.stage != _st or not _j
                                or _j.get('fin') != _fin):
                            return
                        _nodo = _dm_j.nodo_fin_de_juego(_st)
                        log.info('[%s] fin del NPCKILLGAME en %s: %d bajas, nodo %s',
                                 addr, _st, _e.variable(0, 8), _nodo)
                        # Se acabo el tiempo: fuera la marca de "carrera en
                        # marcha" (la zona que genera la raiz que la empieza,
                        # la 103). Con ella viva la raiz de cierre diria "el
                        # juego sigue"; sin ella cae en el "You fail".
                        _quitar_marcas_de_carrera(_ses, _st)
                        _ventana_carrera(_ses, _e, abrir=False)
                        if _nodo:
                            _recorrer_dialogo_mapa(_ses, addr, _st, _nodo)
                    try:
                        import asyncio as _aio_j
                        _aio_j.get_event_loop().call_later(DURACION_JUEGO_MATAR, _fin_juego)
                    except Exception:
                        log.exception('no se pudo programar el fin del NPCKILLGAME')
                else:
                    if getattr(estado, 'juego_matar', None):
                        _ventana_carrera(ses, estado, abrir=False)
                    estado.juego_matar = None
                log.info('[%s] evento%s: NPCKILLGAME %s', addr, motivo, ef[1])
            elif que == 'npc':
                # MAKE_NPC(tipo, ?, ?, segundos, tag): pone un NPC en el TAG un
                # rato. Son los Hell Rival del Evil Lyceum de la carrera.
                _rv = _hacer_npc(ses, addr, estado.stage, int(ef[1]), int(ef[4]), int(ef[5]))
                _jr = getattr(estado, 'juego_matar', None)
                if _rv and _jr and time.time() < _jr.get('fin', 0):
                    _jr.setdefault('rivales', []).append(_rv)
            elif que == 'generador':
                # ENABLE_GENERATOR(zona, 1 enciende / 0 apaga). Al encender
                # salen los de la zona y, mientras siga encendida, se reponen
                # al morir (ver _respawn en _procesar_muerte_monstruo).
                zona, encender = int(ef[1]), bool(int(ef[2] or 0))
                activos = estado.__dict__.setdefault('generadores_activos', set())
                if encender and zona not in activos:
                    activos.add(zona)
                    _generar_zona(ses, addr, estado.stage, zona)
                elif not encender:
                    activos.discard(zona)
                log.info('[%s] evento%s: generador %d %s', addr, motivo, zona,
                         'encendido' if encender else 'apagado')
            elif que == 'propiedad' and p:
                # ADD_PROPERTY / SET_PROPERTY sobre HP (0) o MP (2). La lava de
                # la Magic Kichen Path es esto: evento 666 al pisarla,
                # ADD_PROPERTY(0, -150) y el aviso 64958. No baja de 1: morir
                # por un evento de mapa no esta hecho y dejaria al personaje a
                # 0 sin la secuencia de muerte.
                import eventos as _ev_p
                import combate as _cb_p
                modo, atr, val = ef[1], int(ef[2]), int(ef[3])
                if atr in (_ev_p.ATR_HP, _ev_p.ATR_MP):
                    campo, tope = (('hp', 'hp_max') if atr == _ev_p.ATR_HP
                                   else ('mp', 'mp_max'))
                    act = int(getattr(p, campo, 0) or 0)
                    nuevo = act + val if modo == 'sumar' else val
                    # El tope es el que ensena el cliente (con equipo y
                    # pasivas), no el p.hp_max guardado: con ese, a quien
                    # tenia 585k de vida la lava lo dejaba en su vida base.
                    maximo = (_vida_max(p) if atr == _ev_p.ATR_HP else _mana_max(p)) \
                        or int(getattr(p, tope, 0) or 0) or nuevo
                    nuevo = max(1 if atr == _ev_p.ATR_HP else 0, min(maximo, nuevo))
                    setattr(p, campo, nuevo)
                    kind = _cb_p.KIND_HP if atr == _ev_p.ATR_HP else _cb_p.KIND_MP
                    ses.enviar(_cb_p.atributo(p.entity_id, nuevo, kind))
                    # El numero flotando encima, como un golpe: con 700k de
                    # vida, 150 no mueven la barra y la regeneracion los
                    # repone en un segundo, asi que sin esto "no hacia dano".
                    if atr == _ev_p.ATR_HP and nuevo < act:
                        ses.enviar(_cb_p.numero_flotante(p.entity_id, act - nuevo))
                    log.info('[%s] evento%s: %s %d -> %d', addr, motivo, campo, act, nuevo)
                else:
                    sin_hacer.append('propiedad %d' % atr)
            elif que == 'objeto_estatico':
                estado.objetos[int(ef[1])] = int(ef[2])
                _cambiar_objeto_de_mapa(ses, addr, estado, int(ef[1]), int(ef[2]))
            else:
                sin_hacer.append(que)
        except Exception:
            log.exception('[%s] fallo al aplicar el efecto %s', addr, ef)
    if sin_hacer:
        log.debug('[%s] evento%s: efectos que aun no se obedecen: %s',
                  addr, motivo, sorted(set(sin_hacer)))


def _sigilo_activo(ses, ahora=None):
    """Si el jugador sigue en sigilo (Sneak). Caduca solo por tiempo."""
    return (ahora or time.time()) < float(getattr(ses, 'sigilo_hasta', 0) or 0)


def _romper_sigilo(ses, addr, motivo=''):
    """Saca al jugador del sigilo y le quita el icono y la animacion.

    Es el mismo 0x001D de fin de estado que se manda al caducar un buff
    (tipo 4 con duracion 0), con el id del Sneak que lo puso.
    """
    if not _sigilo_activo(ses):
        return
    ses.sigilo_hasta = 0
    mid = int(getattr(ses, 'sigilo_mid', 0) or 0)
    p = getattr(ses, 'personaje', None)
    if mid and p:
        ses.enviar(struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 4, mid, 0))
    log.info('[%s] sale del sigilo %s', addr, motivo)


_RECURSOS_POR_STAGE = {}


DURACION_JUEGO_MATAR = 600        # "in 10 minutes", msg 64941
_SIG_NPC_EVENTO = [111_000_000]


def _hacer_npc(ses, addr, stage, npc_type, segundos, tag):
    """MAKE_NPC: un NPC de evento en el TAG, que se va solo pasado el rato."""
    import eventos as _ev_n
    import login as _lg_n
    cas = _ev_n.casillas_de_tag(stage, tag)
    if not cas or not ses.personaje:
        return
    nombre = 'NPC'
    sprite = 0
    try:
        import sqlite3 as _sq
        con = _sq.connect(pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db')
        r = con.execute('select name, sprite_id from npc where id=?', (str(int(npc_type)),)).fetchone()
        con.close()
        if r:
            nombre = r[0] or nombre
            sprite = int(r[1] or 0)
    except Exception:
        pass
    _SIG_NPC_EVENTO[0] += 1
    eid = _SIG_NPC_EVENTO[0]
    # Con su sprite del npc.xml (el Hell Rival es el 42336). Sin el, salia
    # el 40001 por defecto y los rivales de la carrera no se veian.
    # Como MONSTRUO (klass 1): a los NPC de clase 199 el cliente no les anima
    # el 0x0005 y los rivales de la carrera tienen que andar hasta sus presas.
    ses.enviar(_lg_n._npc_spawn(eid, npc_type, nombre, tuple(cas[0]), sprite=sprite, klass=1))
    log.info('[%s] MAKE_NPC %s (%d) en el tag %d %s, %ds', addr, nombre, npc_type,
             tag, tuple(cas[0]), segundos)
    if segundos > 0:
        try:
            import asyncio as _aio_n
            import combate as _cb_n
            _aio_n.get_event_loop().call_later(
                segundos, lambda: ses.enviar_inmediato(_cb_n.despawn_monstruo(eid)))
        except Exception:
            pass
    return {'eid': eid, 'tile': list(cas[0]), 'nombre': nombre,
            'hasta': time.time() + segundos if segundos > 0 else None}


# LOS RIVALES DE LA CARRERA. Los Hell Rival (NPC 2135) que saca el Annoying
# Clerk son alumnos del Evil Lyceum que compiten por las mismas bajas: cada
# uno ELIGE el bicho mas cercano, VA ANDANDO hasta el (pasos cortos, como los
# monstruos, bordeando paredes) y solo al llegar lo tumba. Su cuenta va en la
# variable 9 del mapa. Antes se mandaba el movimiento y la muerte en el mismo
# tic, con un salto de hasta 14 casillas que el cliente no anima: el rival se
# quedaba quieto y los bichos caian "con la mente".
# El ritmo no esta medido (no hay captura de la carrera): tras cada baja el
# rival descansa DESCANSO_RIVAL segundos.
RADIO_RIVAL = 14
RADIO_TORNADO = 2
TIC_CARRERA = 1.0
PASOS_RIVAL = 3
VELOCIDAD_RIVAL = 100
DESCANSO_RIVAL = (4.0, 9.0)


def _tic_carrera(ses, addr, estado, fin):
    """Un tic de la carrera: cada rival anda hacia su presa o la tumba."""
    import combate as _cb_c
    import transitable as _tr_c
    j = getattr(estado, 'juego_matar', None)
    if (not ses.personaje or not j or j.get('fin') != fin or time.time() >= fin
            or j.get('terminada')):
        return
    import eventos_mundo as _evm_c
    if _evm_c.estado_de(ses) is estado:
        MOVE = Msg.registry[(0x0005, 's2c', '*')]
        ahora = time.time()
        bichos = ses.monstruos or {}
        cazados = {r.get('presa') for r in j.get('rivales') or [] if r.get('presa')}
        for r in j.get('rivales') or []:
            if r.get('hasta') and ahora >= r['hasta']:
                continue
            if ahora < r.get('libre_en', 0):
                continue
            m = bichos.get(r.get('presa'))
            if m is None or not getattr(m, 'vivo', False):
                r['presa'] = None
                libres = [b for b in bichos.values()
                          if getattr(b, 'vivo', False) and not getattr(b, 'generado', False)
                          and getattr(b, 'en_combate_con', None) is None
                          and b.entity_id not in cazados
                          and max(abs(b.tile_x - r['tile'][0]), abs(b.tile_y - r['tile'][1])) <= RADIO_RIVAL]
                if not libres:
                    continue
                m = min(libres, key=lambda b: max(abs(b.tile_x - r['tile'][0]), abs(b.tile_y - r['tile'][1])))
                r['presa'] = m.entity_id
                cazados.add(m.entity_id)
            dist = max(abs(m.tile_x - r['tile'][0]), abs(m.tile_y - r['tile'][1]))
            if dist > 1:
                nx, ny = _tr_c.avanzar(estado.stage, r['tile'], (m.tile_x, m.tile_y),
                                       PASOS_RIVAL, parar_a=1)
                if (nx, ny) != tuple(r['tile']):
                    ses.enviar(MOVE.build(entity_id=r['eid'], cur_x=r['tile'][0] * 32,
                                          cur_y=r['tile'][1] * 32, dst_x=nx * 32, dst_y=ny * 32,
                                          speed=VELOCIDAD_RIVAL))
                    r['tile'] = [nx, ny]
                    continue
                if dist > 2:
                    r['presa'] = None        # no hay camino: a por otro
                    continue
            # Al lado: lo tumba.
            r['presa'] = None
            r['libre_en'] = ahora + random.uniform(*DESCANSO_RIVAL)
            m.hp = 0
            m.muerto_en = ahora
            ses.enviar(_cb_c.ataque(r['eid'], m.entity_id, 0),
                       _cb_c.atributo(m.entity_id, 0, _cb_c.VIDA),
                       _cb_c.muerte_monstruo(m.entity_id, r['eid']))
            estado.sumar_variable(0, 9, 1)
            _marcador_carrera(ses, estado)
            if estado.variable(0, 9) >= META_CARRERA:
                _terminar_carrera(ses, addr, estado, gana=False)
                ses.volcar()
                return
            _eid_m = m.entity_id
            try:
                import asyncio as _aio_c
                _aio_c.get_event_loop().call_later(
                    2.5, lambda e=_eid_m: ses.enviar_inmediato(_cb_c.despawn_monstruo(e)))
                _aio_c.get_event_loop().call_later(
                    _cb_c.SEGUNDOS_REAPARICION, lambda mm=m: _revivir_en_carrera(ses, estado, fin, mm))
            except Exception:
                pass
        ses.volcar()
    try:
        import asyncio as _aio_c
        _aio_c.get_event_loop().call_later(TIC_CARRERA, lambda: _tic_carrera(ses, addr, estado, fin))
    except Exception:
        pass


def _revivir_en_carrera(ses, estado, fin, m):
    """Durante la carrera los bichos del pasillo vuelven (en una instancia, si
    no, lo muerto se queda muerto y no habria cincuenta que matar)."""
    j = getattr(estado, 'juego_matar', None)
    if not j or j.get('fin') != fin or time.time() >= fin or getattr(m, 'vivo', False):
        return
    if (ses.monstruos or {}).get(m.entity_id) is not m:
        return
    import login as _lg_c
    m.revivir()
    ses.enviar_inmediato(_lg_c._npc_spawn(m.entity_id, m.npc_type, m.nombre, (m.tile_x, m.tile_y),
                                          sprite=getattr(m, 'sprite', 0), klass=1))


# La ventana del marcador (WND_NPCKILLGAME, el "006-055" rosa y azul del
# oficial). La abre y la rellena el s2c 0x0134, 0060cf40 leido con REA:
# [u8 1 abre / 0 cierra][u32 numero rosa (iconos 12754.., ventanas
# 0x326a-c)][u32 numero azul (iconos 12900.., ventanas 0x3267-9)], tres
# cifras cada uno. El rosa es el nuestro.
VENTANA_CARRERA = 0x0134


def _ventana_carrera(ses, estado, abrir=True):
    nuestras = estado.variable(0, 8) if abrir else 0
    rivales = estado.variable(0, 9) if abrir else 0
    ses.enviar(struct.pack('<HBII', VENTANA_CARRERA, 1 if abrir else 0,
                           min(999, max(0, nuestras)), min(999, max(0, rivales))))
    ses._ventana_carrera = abrir


# La carrera la gana el PRIMERO que llega a 50 bajas: si eres tu, pasas a la
# sala 3; si llegan antes los del Evil Lyceum, pierdes y hay que salir de la
# instancia y repetir. (Lo de "mas de 50" del arbol del cliente es la
# comprobacion del Clerk, no la meta: medido en el oficial por el usuario.)
META_CARRERA = 50


def _terminar_carrera(ses, addr, estado, gana):
    import dialogos_mapa as _dm_t
    j = getattr(estado, 'juego_matar', None)
    if not j or j.get('terminada'):
        return
    j['terminada'] = True
    st = estado.stage
    log.info('[%s] carrera en %s: %s (%d - %d)', addr, st, 'GANA' if gana else 'PIERDE',
             estado.variable(0, 8), estado.variable(0, 9))
    _ventana_carrera(ses, estado)
    if gana:
        nodo = _dm_t.nodo_de_victoria(st)
    else:
        # Sin la marca de "carrera en marcha" la raiz de cierre cae en su
        # rama de derrota (1000002: "You fail", zona 102 y fuera).
        _quitar_marcas_de_carrera(ses, st)
        nodo = _dm_t.nodo_fin_de_juego(st)
    if nodo:
        _recorrer_dialogo_mapa(ses, addr, st, nodo)
    else:
        estado.juego_matar = None
        _ventana_carrera(ses, estado, abrir=False)


def _quitar_marcas_de_carrera(ses, stage):
    import combate as _cb_q
    import dialogos_mapa as _dm_q
    zonas = _dm_q.zonas_de_inicio_de_juego(stage)
    for m in list((ses.monstruos or {}).values()):
        if (getattr(m, 'generado', False) and getattr(m, 'vivo', False)
                and getattr(m, 'zona_generador', None) in zonas):
            m.hp = 0
            m.vivo = False
            m.muerto_en = time.time()
            ses.enviar(_cb_q.despawn_monstruo(m.entity_id))


def _marcador_carrera(ses, estado):
    """El marcador: tus bajas, las del Evil Lyceum y lo que queda."""
    import clases as _cl_m
    j = getattr(estado, 'juego_matar', None)
    if not j:
        return
    _ventana_carrera(ses, estado)
    if time.time() - j.get('ultimo_marcador', 0) < 30:
        return
    j['ultimo_marcador'] = time.time()
    queda = max(0, int(j['fin'] - time.time()))
    ses.enviar(_cl_m.aviso('Race: you %d - Evil Lyceum %d (first to 50 wins) - %d:%02d left'
                           % (estado.variable(0, 8), estado.variable(0, 9), queda // 60, queda % 60),
                           tipo=0, msg_id=_cl_m.MSG_TEXTO))


def _arrancar_temporizador(ses, addr, estado, tag, encender):
    import asyncio as _aio_t
    import eventos as _ev_t
    import eventos_mundo as _evm_t
    t = estado.temporizador(tag)
    if not encender:
        t[0] = False
        return
    cfg = ((_ev_t.del_stage(estado.stage) or {}).get('temporizadores') or {}).get(str(tag))
    t[0], t[1] = True, 0
    if not cfg:
        log.info('[%s] ENABLE_TIMER %s en %s: no hay objeto temporizador', addr, tag, estado.stage)
        return
    periodo, veces, evento = max(1, int(cfg['periodo'] or 1)), int(cfg['veces'] or 0), int(cfg['evento'])
    # Un token por arranque: si el evento lo vuelve a encender, el tic del
    # arranque anterior ve que ya no es el suyo y se para.
    token = object()
    del t[2:]
    t.append(token)
    log.info('[%s] temporizador %s en %s: cada %ds, %d veces, evento %s',
             addr, tag, estado.stage, periodo, veces, evento)

    def _tic():
        if not ses.personaje:
            return
        _e = _evm_t.estado_de(ses)
        if _e is not estado:
            # Fuera de la sala. Si es una instancia que sigue viva (ver
            # eventos_mundo._CORRIDAS) el temporizador espera a que vuelva;
            # si no, se acabo.
            _t0 = estado.temporizadores.get(int(tag))
            _viva = any(estado in c['estados'].values()
                        for c in _evm_t._CORRIDAS.values())
            if _viva and _t0 and _t0[0] and len(_t0) >= 3 and _t0[2] is token:
                _aio_t.get_event_loop().call_later(periodo, _tic)
            return
        _t = _e.temporizadores.get(int(tag))
        if not _t or not _t[0] or len(_t) < 3 or _t[2] is not token:
            return
        _t[1] += 1
        efs = _ev_t.ejecutar(estado.stage, evento, _ev_t.NINGUNO, _evm_t.ContextoSesion(ses))
        log.info('[%s] temporizador %s: vez %d -> %s', addr, tag, _t[1], [x[0] for x in efs])
        if efs:
            _aplicar_efectos(ses, addr, efs, ' (temporizador %s)' % tag)
        if not veces or _t[1] < veces:
            _aio_t.get_event_loop().call_later(periodo, _tic)
        else:
            _t[0] = False
    try:
        _aio_t.get_event_loop().call_later(periodo, _tic)
    except Exception:
        log.exception('no se pudo programar el temporizador')


_MATERIALES = None


def _material(mid):
    global _MATERIALES
    if _MATERIALES is None:
        try:
            import json as _js
            _MATERIALES = _js.loads((pathlib.Path(__file__).parent / 'plantillas'
                                     / 'materiales.json').read_text(encoding='utf-8'))['materiales']
        except Exception:
            _MATERIALES = {}
    return _MATERIALES.get(str(int(mid)))


_VETAS_POR_STAGE = None
# Lo que dura la recoleccion de los recursos del mundo, compartido entre todos
# los jugadores como en el juego: {(stage, entidad): [sacadas, agotada_en]}.
# Las de instancia van en el estado de la sesion (cada uno tiene la suya).
_VETAS_MUNDO = {}
# Los textos del cliente (setting/eng/string.xml) para recolectar.
MSG_EMPIEZA_RECOLECCION = 345   # "Begin collecting."
MSG_SIN_MATERIAL = 347          # "There is no material for collection. Please wait..."
MSG_SIN_HERRAMIENTA = 359       # "Unable to collect without proper equipment."
MSG_RECOLECTAR_MONTADO = 573    # "Unable to collect when you are riding."
MSG_RECOLECTAR_LEJOS = 574      # "Unable to collect because the distance is too far."
ACCION_RECOLECTAR = 9           # tipo del 0x000A, medido en la Global
# Ranuras de la herramienta de cada 裝備限制 de material.xml. La wiki, en las
# cuatro habilidades: Collect "a pair of gloves or a robot", Dig "a mine pick
# or a robot", Lumber "an axe or a robot", Fishing "a rod or a robot".
RANURAS_HERRAMIENTA = {'手套': (5, 171), '鐵鍬': (3, 4), '斧': (3, 4), '釣竿': (3, 4)}
DISTANCIA_RECOLECCION = 6       # casillas


def _veta_de(stage, ent):
    """(material, px) de la veta con esa entidad, o (None, None).

    En las instancias el material va en el propio recurso
    (objetos_de_instancia.py); en el resto de mapas, en la tabla 'vetas' de
    materiales.json, que casa cada veta de la plantilla con su objeto del .mpc.
    """
    global _VETAS_POR_STAGE
    r = next((x for x in _recursos_de_plantilla(stage)
              if int(x.get('entity_id', 0)) == int(ent)), None)
    if r is None:
        return None, None
    if isinstance(r.get('material'), int):
        return r['material'], r.get('px')
    # Un objeto con evento propio (estatua, altar, palanca) no es una veta. La
    # tabla 'vetas' casa por id de entidad, y al rehacer los objetos de una
    # instancia las estatuas de Lost Region heredaron ids que antes eran
    # vetas: al pulsarlas salia "Unable to collect when you are riding".
    if r.get('evento'):
        return None, None
    if _VETAS_POR_STAGE is None:
        _material(0)
        try:
            import json as _js
            _VETAS_POR_STAGE = _js.loads((pathlib.Path(__file__).parent / 'plantillas'
                                          / 'materiales.json').read_text(encoding='utf-8')).get('vetas') or {}
        except Exception:
            _VETAS_POR_STAGE = {}
    mid = (_VETAS_POR_STAGE.get(str(int(stage))) or {}).get(str(int(ent)))
    return (int(mid), r.get('px')) if mid else (None, None)


def _herramienta_para(ses, herramienta):
    """(puede, msg_id si no puede, % de velocidad de recoleccion)."""
    import inventario as _iv_h
    bolsa = ses.inventario or {}
    montura = int(bolsa.get(10) or bolsa.get(174) or 0)
    cat_m = _iv_h.categoria_item(montura) if montura else ''
    if cat_m == '座騎':
        return False, MSG_RECOLECTAR_MONTADO, 0
    velocidad = sum(_iv_h.velocidad_recoleccion(int(bolsa.get(r) or 0))
                    for r in range(1, 11) if bolsa.get(r))
    if cat_m == '機甲':
        return True, None, velocidad
    ranuras = RANURAS_HERRAMIENTA.get(herramienta)
    if not ranuras:
        return True, None, velocidad
    if any(_iv_h.categoria_item(int(bolsa.get(r) or 0)) == herramienta for r in ranuras):
        return True, None, velocidad
    return False, MSG_SIN_HERRAMIENTA, 0


def _cuenta_de_veta(ses, stage, ent, mat):
    """La lista [sacadas, agotada_en] de esa veta, ya repuesta si toca."""
    if int(stage) == 500:
        # Private houses must not share depletion with every other stage-500
        # session. A level change also selects a different material tier.
        import house_services as hs
        vetas = ses.__dict__.setdefault('house_resource_state', {})
        clave = (_casa_actual(ses).owner_id, int(ent),
                 hs.resource_for(int(ent), ses.personaje.nivel)['material'])
    elif es_instancia(stage):
        import eventos_mundo as _evm_r
        vetas = _evm_r.estado_de(ses).__dict__.setdefault('vetas', {})
        clave = int(ent)
    else:
        vetas, clave = _VETAS_MUNDO, (int(stage), int(ent))
    c = vetas.setdefault(clave, [0, 0.0])
    if not isinstance(c, list):
        c = vetas[clave] = [int(c), 0.0]
    # 重置時間: lo que tarda en reponerse una vez agotada (720 s el Flint Ore).
    if (mat['limite'] and c[0] >= mat['limite'] and c[1]
            and time.time() - c[1] >= int(mat.get('reponer') or 0)):
        c[0], c[1] = 0, 0.0
    return c


def _parar_recoleccion(ses, avisar_cliente=True):
    rc = getattr(ses, 'recoleccion', None)
    ses.recoleccion = None
    if rc and avisar_cliente and ses.personaje:
        ses.enviar(struct.pack('<HIII', 0x000A, ses.personaje.entity_id, 0, 0))


def _recolectar(ses, addr, stage, ent):
    """Pulsar una veta, arbol, hierba, madriguera o banco de peces.

    COMO LO HACE EL SERVIDOR REAL, medido en la Global sobre el mismo Flint
    Ore de la Magic Kichen Path (material 153, 採集時間 30):

        C 0x0005  [veta]                         el clic
        S 0x000D  345 "Begin collecting."
        S 0x000A  [yo][veta] 9 [ms]              la accion y la barra
        ... a los ms ...
        S 0x001B  el Flint a la bolsa (el monton sube 5 -> 6 -> 7)
        S 0x001D  [yo] 01 05 [veta] [ms]         la barra otra vez
        ... y asi cada ms hasta que se mueve o se agota.

    Alli fueron 13500 ms para los 30 s del material: el tiempo baja con la
    velocidad de recoleccion del equipo (採集速度; el Samurai Kappa Robot
    trae 19). Si va montado: 573. Sin la herramienta de su 裝備限制 (guantes
    para hierbas y madrigueras -- la carne y las pieles --, pala para vetas,
    hacha para arboles, cana para peces) ni robot: 359.
    """
    mid, px = _veta_de(stage, ent)
    if int(stage) == 500 and ses.personaje:
        import house_services as hs
        if ent in hs.RESOURCES:
            resource = hs.resource_for(ent, ses.personaje.nivel)
            mid, px = resource['material'], resource['px']
    if not mid or not ses.personaje:
        return False
    mat = _material(mid)
    if not mat:
        return False
    import clases as _cl_r
    p = ses.personaje
    puede, msg, velocidad = _herramienta_para(ses, mat.get('herramienta'))
    if not puede:
        ses.enviar(_cl_r.aviso('', tipo=7, msg_id=msg))
        log.info('[%s] veta %s (%s): no puede recolectar (msg %s)', addr, ent, mat['nombre'], msg)
        return True
    if px and max(abs(int(px[0]) // 32 - int(getattr(p, 'tile_x', 0) or 0)),
                  abs(int(px[1]) // 32 - int(getattr(p, 'tile_y', 0) or 0))) > DISTANCIA_RECOLECCION:
        ses.enviar(_cl_r.aviso('', tipo=7, msg_id=MSG_RECOLECTAR_LEJOS))
        return True
    cuenta = _cuenta_de_veta(ses, stage, ent, mat)
    if mat['limite'] and cuenta[0] >= mat['limite']:
        ses.enviar(_cl_r.aviso('', tipo=7, msg_id=MSG_SIN_MATERIAL))
        return True
    ms = int(max(1, int(mat.get('tiempo') or 1)) * 1000 * max(10, 100 - velocidad) / 100)
    ms = max(1000, min(ms, 0xFFFF))
    token = object()
    ses.recoleccion = {'ent': int(ent), 'stage': stage, 'token': token}
    ses.enviar(_cl_r.aviso('', tipo=7, msg_id=MSG_EMPIEZA_RECOLECCION),
               struct.pack('<HIIHH', 0x000A, p.entity_id, int(ent), ACCION_RECOLECTAR, ms))
    log.info('[%s] recolectando %s (%s, material %s) en %s: %d ms, velocidad %d%%',
             addr, ent, mat['nombre'], mid, stage, ms, velocidad)

    def _tic():
        rc = getattr(ses, 'recoleccion', None)
        if not rc or rc.get('token') is not token or not ses.personaje:
            return
        if ses.personaje.stage != stage:
            ses.recoleccion = None
            return
        try:
            seguir = _sacar_de_veta(ses, addr, stage, ent, mat, mid)
            if seguir:
                ses.enviar(struct.pack('<HIBBII', 0x001D, ses.personaje.entity_id, 1, 5,
                                       int(ent), ms))
                import asyncio as _aio_r
                _aio_r.get_event_loop().call_later(ms / 1000.0, _tic)
            else:
                _parar_recoleccion(ses)
            ses.volcar()
        except Exception:
            ses.recoleccion = None
            log.exception('recoleccion')
    try:
        import asyncio as _aio_r
        _aio_r.get_event_loop().call_later(ms / 1000.0, _tic)
    except Exception:
        log.exception('no se pudo programar la recoleccion')
    return True


def _sacar_de_veta(ses, addr, stage, ent, mat, mid):
    """Una vuelta de la barra: tira el dado y mete lo que salga. Devuelve si
    se puede seguir (queda material y cabe en la bolsa)."""
    import clases as _cl_r
    cuenta = _cuenta_de_veta(ses, stage, ent, mat)
    if mat['limite'] and cuenta[0] >= mat['limite']:
        ses.enviar(_cl_r.aviso('', tipo=7, msg_id=MSG_SIN_MATERIAL))
        return False
    cuenta[0] += 1
    if mat['limite'] and cuenta[0] >= mat['limite']:
        cuenta[1] = time.time()
    total = sum(pr for _it, pr in mat['items']) + int(mat.get('no_produce') or 0)
    tirada = random.randint(1, max(1, total))
    dado = None
    for it, pr in mat['items']:
        tirada -= pr
        if tirada <= 0:
            dado = it
            break
    if dado is not None:
        r = _meter(ses, int(dado), 1)
        if r is None:
            ses.enviar(_cl_r.aviso('Your backpack is full.', tipo=0))
            cuenta[0] -= 1
            return False
        ses.enviar(*_refrescar(ses, [r]))
        ses.enviar(_cl_r.aviso(_nombre_item(int(dado)), tipo=0, msg_id=_cl_r.MSG_ITEM))
        try:
            import misiones as _mis_col
            pkgs = _mis_col.verificar_progreso_recoleccion(ses, [ses.inventario.get(r)])
            if pkgs:
                ses.enviar(*pkgs)
        except Exception:
            log.exception('progreso de recoleccion')
        _guardar_bolsa(ses, ses.personaje.char_id)
    log.info('[%s] veta %s (%s) en %s: %s, %d/%d', addr, ent, mat['nombre'], stage,
             dado, cuenta[0], mat['limite'])
    return not (mat['limite'] and cuenta[0] >= mat['limite'])


_RECURSOS_COMPLETOS = {}
# Ids de los objetos que se cambian en vivo. Banda propia: 50M monstruos,
# 60M+stage*100k objetos de mapa (llega a 99M con el stage 399), 80M
# presencia, 96M monstruos generados. Por encima de todo eso.
_SIG_OBJETO_CAMBIADO = [110_000_000]


def _recursos_de_plantilla(stage):
    """Los recursos de la plantilla del mapa, tal cual (con 'crudo')."""
    if int(stage) == 500:
        import house_services as hs
        return [dict(entity_id=eid, sprite=sprite, tile=tile,
                     px=(tile[0] * 32 + 16, tile[1] * 32 + 16), material=material)
                for eid, (sprite, tile, material) in hs.RESOURCES.items()]
    import login as _lg_r
    if stage not in _RECURSOS_COMPLETOS:
        rec = []
        f = _lg_r.PLANTILLAS_POR_STAGE.get(stage)
        if f:
            try:
                import json as _js
                rec = _js.loads((pathlib.Path(__file__).parent / 'plantillas' / f)
                                .read_text(encoding='utf-8')).get('recursos') or []
            except Exception:
                rec = []
        _RECURSOS_COMPLETOS[stage] = rec
    return _RECURSOS_COMPLETOS[stage]


def _cambiar_objeto_de_mapa(ses, addr, estado, tag, sprite):
    """CHANGE_STATICOBJ(tag, sprite): el objeto de esa casilla pasa a ser otro.

    COMO LO HACE EL SERVIDOR REAL, medido en las capturas Global de la Magic
    Kichen Path y leido en el cliente con REA: el cliente solo mira el sprite
    al CREAR un objeto (005b85d0 busca por id y, si ya existe, lo devuelve
    tal cual), asi que no se puede "cambiar" uno. Se quita con 0x0007 (lo
    atiende 005eca40: busca la entidad y la borra) y se manda otro 0x000E con
    un id nuevo y el sprite nuevo. En la Global, en la casilla (102,10), la
    barrera llega como 60308 en una sesion y como 60302 en otra, cada vez con
    su propio id.

    De los objetos que hay en las casillas del TAG se cambia el que NO lleva
    evento: en esas casillas comparten sitio la barrera (sin evento) y un
    60094 con su evento 110..112, y en la Global el 60094 se queda.
    """
    import eventos as _ev
    import combate as _cb
    cas = {tuple(c) for c in (_ev.casillas_de_tag(estado.stage, tag) or [])}
    recs = [r for r in _recursos_de_plantilla(estado.stage)
            if r.get('crudo') and tuple(r.get('tile') or ()) in cas]
    if not recs:
        log.info('[%s] CHANGE_STATICOBJ(%d, %d) en el mapa %d: no hay objeto '
                 'de mapa en ese tag', addr, tag, sprite, estado.stage)
        return
    cambiar = [r for r in recs if not r.get('evento')] or recs
    puestos = estado.__dict__.setdefault('puestos', {})   # eid original -> (eid, sprite)
    salida = []
    for r in cambiar:
        orig = int(r['entity_id'])
        eid_act, spr_act = puestos.get(orig, (orig, int(r['sprite'])))
        if spr_act == sprite:
            continue
        _SIG_OBJETO_CAMBIADO[0] += 1
        nuevo = _SIG_OBJETO_CAMBIADO[0]
        b = bytearray(bytes.fromhex(r['crudo'])[:43])
        struct.pack_into('<I', b, 0, nuevo)
        struct.pack_into('<H', b, 34, sprite)
        salida.append(_cb.despawn_monstruo(eid_act))
        salida.append(struct.pack('<H', 0x000E) + bytes(b))
        puestos[orig] = (nuevo, sprite)
        log.info('[%s] mapa %d, tag %d: objeto %d (%d) -> %d (%d)', addr,
                 estado.stage, tag, eid_act, spr_act, nuevo, sprite)
    if salida:
        ses.enviar(*salida)
        # La puerta se abre para todos los que esten en la sala, no solo
        # para quien la abre (al restaurar, _espejando: solo para el que entra).
        if not getattr(ses, '_espejando', False):
            for s in _companeros(ses):
                try:
                    s.enviar_sin_espejo(*salida)
                    s.volcar()
                except Exception:
                    pass


def _recurso_con_entidad(stage, ent):
    """La casilla del objeto de mapa con ese id de entidad, o None.

    Los objetos de mapa ("recursos") los manda el servidor desde la plantilla
    del mapa con su entity_id y su casilla; con la casilla se sabe que evento
    tiene en el .mpc.
    """
    import login as _lg_r
    if stage not in _RECURSOS_POR_STAGE:
        idx = {}
        f = _lg_r.PLANTILLAS_POR_STAGE.get(stage)
        if f:
            try:
                import json as _js
                d = _js.loads((pathlib.Path(__file__).parent / 'plantillas' / f)
                              .read_text(encoding='utf-8'))
                for r in d.get('recursos') or []:
                    if not r.get('entity_id'):
                        continue
                    if r.get('tile'):
                        idx[int(r['entity_id'])] = tuple(r['tile'])
                    elif r.get('px'):
                        # Los de las capturas solo traen el pixel: el tornado
                        # del East Playground hacia el Training Palace (102059)
                        # se pulsaba y no se encontraba su casilla, asi que su
                        # evento no saltaba nunca.
                        idx[int(r['entity_id'])] = (int(r['px'][0]) // 32,
                                                    int(r['px'][1]) // 32)
            except Exception:
                pass
        _RECURSOS_POR_STAGE[stage] = idx
    return _RECURSOS_POR_STAGE[stage].get(int(ent))


_MONSTRUOS_BD = None
_SIG_GENERADO = [96_000_000]
TOPE_GENERADOS = 30


def _monstruo_bd(npc_type):
    """(nombre, sprite) de monster.xml, via corpus/content.db."""
    global _MONSTRUOS_BD
    if _MONSTRUOS_BD is None:
        import sqlite3
        _MONSTRUOS_BD = {}
        try:
            con = sqlite3.connect(str(pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db'))
            for i, spr, nom in con.execute('select id, sprite_id, name from monster'):
                if str(i).isdigit():
                    _MONSTRUOS_BD[int(i)] = (nom or '?', int(spr) if str(spr or '').isdigit() else 0)
            con.close()
        except Exception:
            log.exception('no pude leer monster de content.db')
    return _MONSTRUOS_BD.get(int(npc_type), ('?', 0))


# PUNTOS DE ZONA CORREGIDOS. El primer Hicalu Machine de Lost Region (zona
# 150, lo saca la estatua de (62,38)) trae en el map098.mpc el punto (20,52),
# a 45 casillas de su estatua, y salia lejos. En Horrible Lost Region la misma
# zona esta en (63,40), junto a la estatua; aqui se le pone ese mismo sitio.
# Las otras dos estatuas de los dos mapas ya caen al lado de su jefe.
PUNTOS_DE_ZONA = {
    (98, 150): [[63, 40]],
}


def _generar_zona(ses, addr, stage, tag, cuantos=None):
    """GENERATE(tag): saca los monstruos de esa zona de generador.

    Es lo que hacen los objetos de mision: en la 262, acercarse a la estatua
    del mono con la mision en curso genera el bicho de la zona 66, y al
    matarlo cae el objeto y avanza el paso. Se marcan como generados para que
    no reaparezcan solos al morir: solo vuelven si el evento los vuelve a
    pedir.
    """
    import eventos as _ev_g
    g = ((_ev_g.del_stage(stage) or {}).get('generadores') or {}).get(str(tag))
    if g and (int(stage), int(tag)) in PUNTOS_DE_ZONA:
        g = dict(g, puntos=PUNTOS_DE_ZONA[(int(stage), int(tag))])
    if not g or not g.get('tipos') or not g.get('puntos') or not ses.personaje:
        log.debug('[%s] GENERATE %s en %s: la zona no esta en la plantilla', addr, tag, stage)
        return
    if ses.monstruos is None:
        ses.monstruos = {}
    n = max(1, min(TOPE_GENERADOS, int(cuantos or g.get('cuantos') or 1)))
    # Se sigue por el PUNTO SIGUIENTE a los ya ocupados. Los mapas piden un
    # GENERATE por monstruo (cuantos=1) y cada llamada empezaba otra vez por
    # el primer punto: los tres Blood Pillar de la zona 110 de la sala 3, que
    # van en (251,156), (172,164) y (138,139), salian los tres en el primero.
    ya = sum(1 for _m in ses.monstruos.values()
             if getattr(_m, 'zona_generador', None) == int(tag) and getattr(_m, 'vivo', False))
    for i in range(ya, ya + n):
        npc_type = int(g['tipos'][i % len(g['tipos'])])
        tile = list(g['puntos'][i % len(g['puntos'])])
        eid = _SIG_GENERADO[0]
        _SIG_GENERADO[0] += 1
        _poner_generado(ses, eid, npc_type, tile, int(tag))
    log.info('[%s] GENERATE zona %s en %s: %d x %s', addr, tag, stage, n, g['tipos'])


def _decir(eid, nombre, texto):
    """s2c 0x0017: alguien DICE algo, con su bocadillo encima.

    Leido en el cliente con REA (005f1590, la entrada 0x17 de la tabla de
    005e5350): [u32 entidad][nombre, 17 bytes][texto ASCIIZ]. Escribe la
    linea en el chat (00632f20 con el nombre) y, si la entidad esta en
    pantalla, le abre el bocadillo. En la Global, el CHAT de la lava de la
    Magic Kichen Path ("Too hot!", 64958) llega justo asi, como 0x0017 con la
    entidad y el nombre del propio jugador.
    """
    n = (nombre or '').encode('latin-1', 'replace')[:16]
    return (struct.pack('<HI', 0x0017, int(eid)) + n + bytes(17 - len(n))
            + (texto or '').encode('latin-1', 'replace')[:200] + b'\x00')


def _hablar_jugador(ses, texto):
    """El jugador dice algo: el y los que lo ven (con su id publico)."""
    p = ses.personaje
    ses.enviar(_decir(p.entity_id, p.nombre, texto))
    try:
        import presencia as _pr_h
        clave = getattr(ses, '_mapa_presencia', None)
        if clave is not None:
            pkt = _decir(_pr_h.entidad_de(ses), p.nombre, texto)
            for s in _pr_h._vivas(clave):
                if s is not ses:
                    _pr_h._mandar(s, pkt)
    except Exception:
        log.debug('chat a los demas', exc_info=True)


def _jefe_que_habla(ses):
    """El jefe vivo de la sala mas cercano al jugador; si no hay ninguno, el
    ultimo monstruo que saco un evento. None si no hay nadie."""
    import combate as _cb_j
    p = ses.personaje
    vivos = [m for m in (ses.monstruos or {}).values() if getattr(m, 'vivo', False)]
    if not vivos or not p:
        return None
    jefes = [m for m in vivos if _cb_j.es_jefe(m.npc_type)]
    if jefes:
        return min(jefes, key=lambda m: max(abs(m.tile_x - p.tile_x), abs(m.tile_y - p.tile_y)))
    gen = [m for m in vivos if getattr(m, 'generado', False)]
    return max(gen, key=lambda m: m.entity_id) if gen else None
def _hablar_monstruo(ses, m, texto):
    """Un bicho dice algo (le llega a todos los de la sala por _espejar)."""
    ses.enviar(_decir(m.entity_id, getattr(m, 'nombre', '') or '', texto))


# Lo que dicen los jefes al aparecer. Son frases del string.xml del cliente
# (1890-1899, las de los jefes de instancia) que ningun evento del mapa
# nombra: las suelta el servidor. Solo se ponen las que se pueden atribuir:
#   888 Guard Fasit      1891 "You are impolite. Let me show you my power!"
#                        (captura del oficial, sala 1 de la Magic Kichen Path)
#   817 Rock God Mendun  1894 "...unless there are no air holes to provide me
#                        with sufficient energy!!" (los Air Holes son de su sala)
FRASE_AL_SALIR = {888: 1891, 817: 1894}
_STRINGS = None


def _texto_string(sid):
    """Un texto de setting/eng/string.xml por numero."""
    global _STRINGS
    if _STRINGS is None:
        _STRINGS = {}
        try:
            import re as _re_s
            ruta = (pathlib.Path(__file__).parent.parent / 'extracted_paks' / 'update26'
                    / 'setting' / 'eng' / 'string.xml')
            for k, v in _re_s.findall(r'編號="(\d+)" 文字="([^"]*)"',
                                       ruta.read_text(encoding='utf-8', errors='replace')):
                _STRINGS[int(k)] = v
        except Exception:
            log.debug('string.xml', exc_info=True)
    return _STRINGS.get(int(sid), '')


def _poner_generado(ses, eid, npc_type, tile, zona):
    """Crea y manda un bicho generado por evento (las antorchas encendidas de
    la sala 1 de la Magic Kichen Path son bichos asi)."""
    import combate as _cb_g
    import login as _lg_g
    nombre, sprite = _monstruo_bd(npc_type)
    _st = getattr(getattr(ses, 'personaje', None), 'stage', None)
    m = _cb_g.Monstruo(eid, npc_type, nombre, list(tile), sprite, stage=_st)
    m.generado = True
    m.zona_generador = int(zona)
    if ses.monstruos is None:
        ses.monstruos = {}
    ses.monstruos[eid] = m
    ses.enviar(_lg_g._npc_spawn(eid, npc_type, nombre, tuple(tile), sprite=sprite, klass=1))
    frase = _texto_string(FRASE_AL_SALIR.get(int(npc_type), 0)) if int(npc_type) in FRASE_AL_SALIR else ''
    if frase:
        _hablar_monstruo(ses, m, frase)
    return m


# --------------------------------------------------------------------------
# SALAS DE INSTANCIA COMPARTIDAS
#
# En una instancia los bichos no son de la sesion sino de la SALA: cuelgan
# del estado de la sala en su corrida (eventos_mundo._CORRIDAS), que es la
# misma para todo el grupo. Todos los del grupo que entran en la sala usan
# ese mismo dict como ses.monstruos, asi que lo que uno mata esta muerto para
# todos y lo que se queda a medias se queda a medias aunque se salga y se
# vuelva.
#
# Lo que el servidor manda sobre esos bichos (moverse, golpes, vida, muerte,
# aparecer) sale por ses.enviar de quien lo provoca; Session.enviar se lo
# pasa a _espejar, que se lo reenvia a los demas de la sala. Lo que lleve el
# id propio del jugador se cambia por su id publico (presencia.entidad_de),
# que es con el que los demas lo ven.
# --------------------------------------------------------------------------

# opcode -> desplazamientos de las entidades dentro del cuerpo
_ENTIDADES_DEL_PAQUETE = {
    0x0005: (0,), 0x0007: (0,), 0x0008: (0,), 0x000B: (0,), 0x0013: (0,),
    0x001D: (0,), 0x000A: (0, 4), 0x0011: (2, 6), 0x0017: (0,),
}


class _SalaDelMundo:
    """Los bichos de un mapa abierto, los mismos para todos los que esten en
    el (en las instancias la sala es el EstadoDeMapa de la corrida)."""

    def __init__(self, stage):
        self.stage = stage
        self.monstruos = None
        self.sesiones = []


_SALAS_DEL_MUNDO = {}


def _sala_para(ses):
    """La sala que le toca al entrar en su mapa actual."""
    st = int(ses.personaje.stage)
    if es_instancia(st):
        import eventos_mundo as _evm_s
        return _evm_s.estado_de(ses)
    return _SALAS_DEL_MUNDO.setdefault(st, _SalaDelMundo(st))


def _sala_de(ses):
    """La sala COMPARTIDA en la que esta ahora, o None."""
    e = getattr(ses, '_sala', None)
    p = getattr(ses, 'personaje', None)
    if (e is None or p is None or e.monstruos is None or e.stage != p.stage
            or ses.monstruos is not e.monstruos):
        return None
    return e


def _companeros(ses):
    """Los OTROS jugadores que estan ahora en la misma sala compartida."""
    e = _sala_de(ses)
    if e is None:
        return []
    vivos = [s for s in e.sesiones
             if s is not ses and not getattr(s, 'cerrada', False)
             and getattr(s, 'personaje', None) is not None
             and getattr(s, '_sala', None) is e
             and s.monstruos is e.monstruos]
    return vivos


def _difundir_en_sala(ses, *pkts):
    for comp in _companeros(ses):
        try:
            comp.enviar(*pkts)
        except Exception:
            pass


def _entidades_propias(ses):
    """Las entidades que son de ese jugador: el, su mascota y sus invocaciones."""
    p = getattr(ses, 'personaje', None)
    ids = {int(p.entity_id)} if p else set()
    if getattr(ses, 'pet_entity_id', None):
        ids.add(int(ses.pet_entity_id))
    for k in ('invocacion', 'invocacion2'):
        inv = getattr(ses, k, None)
        if inv and inv.get('entity_id'):
            ids.add(int(inv['entity_id']))
    enc = getattr(ses, 'monstruo_encantado', None)
    if enc is not None:
        ids.add(int(enc.entity_id))
    return ids


def _espejar(ses, submsgs):
    """Reenvia a los demas de la sala lo que se acaba de mandar sobre sus bichos."""
    if getattr(ses, '_espejando', False):
        return
    # LA TRANSFORMACION PROPIA, a quien te ve. Hay media docena de sitios que
    # se mandan el 0x0013 KIND_TRANSFORM (al lanzarla, al caducar, al cambiar
    # de mapa, al reconectar...) y no todos avisaban a presencia: los demas te
    # seguian viendo sin transformar. Aqui se cogen todos.
    try:
        import combate as _cb_tf
        _yo_tf = int(getattr(ses.personaje, 'entity_id', 0) or 0)
        for sm in submsgs:
            if (isinstance(sm, (bytes, bytearray)) and len(sm) >= 12
                    and sm[:2] == b'\x13\x00'
                    and struct.unpack_from('<I', sm, 2)[0] == _yo_tf
                    and sm[7] == _cb_tf.KIND_TRANSFORM):
                import presencia as _pr_tf
                _pr_tf.notificar_transformacion(ses, struct.unpack_from('<I', sm, 8)[0])
    except Exception:
        log.debug('transformacion a presencia', exc_info=True)
    otros = _companeros(ses)
    if not otros:
        return
    bichos = ses.monstruos or {}
    yo = int(getattr(ses.personaje, 'entity_id', 0) or 0)
    import presencia as _pr_e
    publico = _pr_e.entidad_de(ses)
    salen = []
    for sm in submsgs:
        if not isinstance(sm, (bytes, bytearray)) or len(sm) < 6:
            continue
        offs = _ENTIDADES_DEL_PAQUETE.get(struct.unpack_from('<H', sm, 0)[0])
        if not offs:
            continue
        ents = [struct.unpack_from('<I', sm, 2 + o)[0] for o in offs if len(sm) >= 6 + o]
        if not any(x in bichos for x in ents):
            continue
        b = bytearray(sm)
        for o in offs:
            if len(b) >= 6 + o and struct.unpack_from('<I', b, 2 + o)[0] == yo:
                struct.pack_into('<I', b, 2 + o, publico)
        salen.append(bytes(b))
    if not salen:
        return
    for s in otros:
        try:
            s.enviar_sin_espejo(*salen)
            s.volcar()
        except Exception:
            log.debug('no se pudo reenviar a un companero', exc_info=True)


def _entrar_en_sala(ses, addr):
    """En el 0x0009 de una sala de instancia: se engancha a los bichos de la
    sala (los crea la primera vez) y, si la sala ya tenia historia, le pone al
    cliente al dia: lo muerto fuera, lo generado dentro, cada bicho en su
    sitio y con su vida, y los objetos cambiados (puertas, barreras)."""
    import eventos_mundo as _evm_r
    import combate as _cb_r
    import login as _lg_r
    p = ses.personaje
    # Los flags de mapa de ESTE stage: en las instancias el minimapa y el
    # Scene Map van en negro (bit 0x20), como en el oficial; si no, salia el
    # radar de Dawn Harbor que stage.xml les pone de relleno, con los puntos
    # de los bichos y los carteles de los minerales encima.
    ses.enviar(_lg_r.flags_de_mapa(getattr(p, 'stage', 0)))
    e = _sala_para(ses)
    # Si se fue de la sala con la carrera en marcha, la ventana no se queda.
    if getattr(ses, '_ventana_carrera', False):
        _jc = getattr(e, 'juego_matar', None)
        if not _jc or time.time() >= _jc.get('fin', 0):
            _ventana_carrera(ses, e, abrir=False)
    e.sesiones = [s for s in e.sesiones
                  if s is not ses and getattr(s, '_sala', None) is e
                  and not getattr(s, 'cerrada', False)
                  and getattr(getattr(s, 'personaje', None), 'stage', None) == e.stage]
    e.sesiones.append(ses)
    ses._sala = e
    ses.espejo = _espejar
    if e.monstruos is None:
        e.monstruos = ses.monstruos if ses.monstruos is not None else _monstruos_de(p.stage)
        ses.monstruos = e.monstruos
        e.por_restaurar = False
        return
    ses.monstruos = e.monstruos
    e.por_restaurar = False
    MOVE = Msg.registry[(0x0005, 's2c', '*')]
    vivos_en_sala = set()
    for s in e.sesiones:
        vivos_en_sala |= _entidades_propias(s)
    fuera, dentro = [], []
    for eid, m in list(e.monstruos.items()):
        if not getattr(m, 'vivo', False):
            if not getattr(m, 'generado', False):
                fuera.append(_cb_r.despawn_monstruo(eid))
            continue
        if getattr(m, 'en_combate_con', None) not in vivos_en_sala:
            m.en_combate_con = None
        if getattr(m, 'generado', False):
            dentro.append(_lg_r._npc_spawn(eid, m.npc_type, m.nombre, (m.tile_x, m.tile_y),
                                           sprite=getattr(m, 'sprite', 0), klass=1))
        else:
            st = tuple(getattr(m, 'spawn_tile', None) or (m.tile_x, m.tile_y))
            if (m.tile_x, m.tile_y) != st:
                dentro.append(MOVE.build(entity_id=eid, cur_x=st[0] * 32, cur_y=st[1] * 32,
                                         dst_x=m.tile_x * 32, dst_y=m.tile_y * 32, speed=200))
        if 0 < getattr(m, 'porcentaje', 100) < 100:
            dentro.append(_cb_r.atributo(eid, m.porcentaje))
    ses._espejando = True
    try:
        if fuera:
            ses.enviar(*fuera)
        if dentro:
            ses.enviar(*dentro)
        if hasattr(e, 'objetos'):
            e.__dict__['puestos'] = {}
            for tag, sprite in list(e.objetos.items()):
                _cambiar_objeto_de_mapa(ses, addr, e, int(tag), int(sprite))
    finally:
        ses._espejando = False
    log.info('[%s] sala %d: %d bichos muertos, %d al dia, %d objetos, '
             '%d jugador(es) dentro', addr, e.stage, len(fuera), len(dentro),
             len(getattr(e, 'objetos', None) or {}), len(e.sesiones))


def _dialogo_del_mapa(ses, addr, stage, nodo):
    """BEGIN_MESSAGE(nodo): abre el dialogo del arbol del mapa en ese nodo."""
    _recorrer_dialogo_mapa(ses, addr, stage, nodo)


def _recorrer_dialogo_mapa(ses, addr, stage, nodo):
    """Recorre el arbol de dialogo del mapa desde `nodo` y lo muestra.

    En cada nodo: si alguna de sus ramas se cumple se salta a ella sin
    mostrarlo (es lo que hace el cliente con las ramas: el nodo es solo la
    pregunta); si no, se muestra su mensaje, se apuntan sus acciones y se
    sigue por "siguiente". Se para en el primer nodo con OPCIONES: el cuadro
    sale con ellas y la eleccion la atiende el 0x000B (ses.dlg_mapa).

    Las acciones se ejecutan DESPUES de mandar el texto, porque entre ellas
    hay viajes (CHANGE_MAP, GOTO_TAG) y el cuadro se perderia.

    POR QUE. El Annoying Clerk de la sala 2 de la Magic Kichen Path es la
    unica forma de llegar a la sala 3: su dialogo pregunta, y al aceptar
    empieza la carrera de bajas contra el Evil Lyceum. Antes solo se sabia
    mostrar la cadena de mensajes de un nodo sin opciones, y el cuadro salia
    con NULL.
    """
    import dialogos as _dl
    import dialogos_mapa as _dm
    import eventos as _ev_d
    import eventos_mundo as _evm_d
    p = ses.personaje
    if not p:
        return False
    arbol = _dm._arbol(stage)
    ctx = _evm_d.ContextoSesion(ses)
    k, visto = str(int(nodo)), set()
    mensajes, efectos, opciones, cara = [], [], None, None
    while k and k != '0' and k not in visto and len(mensajes) < 8:
        visto.add(k)
        n = arbol.get(k)
        if n is None:
            break
        salto = None
        for rama in n.get('r', ()):
            if _dm._cumple(rama, ctx):
                salto = rama.get('ir')
                break
        if salto:
            k = str(salto)
            continue
        if n.get('m'):
            mensajes.append(int(n['m']))
            cara = cara or n.get('c')
        for num, parms in n.get('a', ()):
            ef = _ev_d.traducir(num, parms)
            if ef is None:
                log.debug('[%s] dialogo %s/%s: accion %s sin traducir',
                          addr, stage, k, _ev_d.nombre_accion(num))
            elif ef[0] != 'parar':
                efectos.append(ef)
        if n.get('o'):
            opciones = [(int(o[0]), int(o[1])) for o in n['o']]
            break
        k = str(n['s']) if n.get('s') else None
    if not mensajes:
        log.debug('[%s] dialogo del mapa %s/%s: sin mensajes', addr, stage, nodo)
        if efectos:
            _aplicar_efectos(ses, addr, efectos, ' (dialogo %s)' % nodo)
        return bool(efectos)
    # Sin retrato si el nodo no trae uno (la antorcha, las tablillas): en el
    # oficial esos cuadros salen sin personaje. Con 3 salia una chica.
    cara = cara or 0
    g = [_dl.armar_linea(mid, cara, [])[2:] for mid in mensajes[:-1]]
    g.append(_dl.armar_linea(mensajes[-1], cara,
                             [o[0] for o in opciones] if opciones else [])[2:])
    ses.dlg_ent, ses.dlg_guion, ses.dlg_paso, ses.dlg_val = p.entity_id, g, 1, cara
    ses.dlg_mapa = ({'stage': stage, 'opciones': opciones, 'guion': g}
                    if opciones else None)
    ses.enviar(_dl.linea_de(g, 0, p.nombre))
    log.info('[%s] dialogo del mapa %s/%s: %s%s', addr, stage, nodo, mensajes,
             ' opciones %s' % [o[0] for o in opciones] if opciones else '')
    if efectos:
        _aplicar_efectos(ses, addr, efectos, ' (dialogo %s)' % nodo)
    return True


OCULTA_PRIMERA, OCULTA_ULTIMA = 497, 556


def _ranura_oculta_de(ses, item_id):
    inv = ses.personaje.inventario
    for r in range(OCULTA_PRIMERA, OCULTA_ULTIMA + 1):
        if inv.get(r) == item_id:
            return r
    return None


def _dar_token_oculto(ses, addr, item_id, cant=1):
    """Suma un token de mision en las ranuras ocultas y lo pinta en el HUD.

    Si ya hay una ranura con ese token se suma ahi; si no, la primera libre.
    Se evitan las que misiones.py reserva para sus cacerias (497 + quest % 60)
    de las misiones que lleva el personaje, para no pisarse con ellas.
    """
    import inventario as _inv
    p = ses.personaje
    if not p:
        return
    cant_de = p.cantidades if p.cantidades is not None else {}
    p.cantidades = cant_de
    r = _ranura_oculta_de(ses, item_id)
    if r is None:
        reservadas = {OCULTA_PRIMERA + (int(q) % 60) for q, _pa in (p.quests or [])}
        libres = [x for x in range(OCULTA_PRIMERA, OCULTA_ULTIMA + 1)
                  if not p.inventario.get(x)]
        r = next((x for x in libres if x not in reservadas),
                 libres[0] if libres else None)
        if r is None:
            log.warning('[%s] no queda ranura oculta para el token %s', addr, item_id)
            return
        p.inventario[r] = item_id
        cant_de[r] = 0
    cant_de[r] = int(cant_de.get(r, 0)) + max(1, cant)
    # Mantener quest_kills sincronizado con la cantidad real del token
    if hasattr(p, 'quest_kills') and isinstance(p.quest_kills, dict):
        try:
            import misiones as _mis_sync
            _mis_sync._cargar_db()
            for _q_s, _pa_s in (p.quests or []):
                _c_tok = (_mis_sync.OBJETIVOS_CACERIA.get((_q_s, _pa_s), {}) or {}).get('token_id')
                if not _c_tok:
                    _c_tok = (_mis_sync._CACERIAS.get(f"{_q_s}_{_pa_s}", {}) or {}).get('token_id')
                if _c_tok == item_id:
                    p.quest_kills[f"{_q_s}_{_pa_s}"] = cant_de[r]
                    p.quest_kills[(_q_s, _pa_s)] = cant_de[r]
                    if hasattr(ses, 'quest_kills') and isinstance(ses.quest_kills, dict):
                        ses.quest_kills[f"{_q_s}_{_pa_s}"] = cant_de[r]
                        ses.quest_kills[(_q_s, _pa_s)] = cant_de[r]
        except Exception:
            pass
    dueno = getattr(ses, 'entity_id', p.char_id)
    entrada = _inv.entrada_recuperada(p.char_id, r, item_id, cant=cant_de[r], dueno=dueno)
    ses.enviar(struct.pack('<HI', 0x001B, 1) + entrada)
    _guardar_bolsa(ses, p.char_id)
    log.info('[%s] token de mision %s -> ranura oculta %d (ahora %d)',
             addr, item_id, r, cant_de[r])


def _quitar_token_oculto(ses, addr, item_id, cant=1):
    """Resta un token de las ranuras ocultas; si llega a 0, vacia la ranura."""
    import inventario as _inv
    p = ses.personaje
    r = _ranura_oculta_de(ses, item_id) if p else None
    if r is None:
        return
    queda = int((p.cantidades or {}).get(r, 1)) - max(1, cant)
    dueno = getattr(ses, 'entity_id', p.char_id)
    if queda > 0:
        p.cantidades[r] = queda
        ses.enviar(struct.pack('<HI', 0x001B, 1)
                   + _inv.entrada_recuperada(p.char_id, r, item_id, cant=queda, dueno=dueno))
    else:
        p.inventario.pop(r, None)
        (p.cantidades or {}).pop(r, None)
        ses.enviar(_inv.vaciar_ranura(dueno, r))
    _guardar_bolsa(ses, p.char_id)


def _mapa_de_paso(m, stage):
    """El stage con el que se mira por donde anda ese bicho, o 0 = sin limites.

    Uno de cada doce bichos aparece en una casilla que NO se pisa: los del
    agua, los de la lava y los que vuelan. A esos no se les aplica: si no,
    se quedarian clavados o saldrian a tierra y no volverian."""
    v = getattr(m, '_anda_por_tierra', None)
    if v is None:
        sx, sy = getattr(m, 'spawn_x', m.tile_x), getattr(m, 'spawn_y', m.tile_y)
        v = m._anda_por_tierra = _transitable.se_pisa(stage, sx, sy)
    return stage if v else 0


_OBJETO_MAGIA = {}


def _objeto_de_magia(magic_id):
    """El 對象 de magic.xml: 自己 (uno mismo), 角色 (un personaje que se
    elige), 隊伍 (el grupo, en un radio de 範圍 casillas), 地面, 屍體."""
    mid = int(magic_id or 0)
    if mid not in _OBJETO_MAGIA:
        v = ''
        try:
            import sqlite3 as _sq_o
            con = _sq_o.connect(pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db')
            r = con.execute('select "對象" from magic where id=?', (str(mid),)).fetchone()
            con.close()
            v = (r[0] or '') if r else ''
        except Exception:
            pass
        _OBJETO_MAGIA[mid] = v
    return _OBJETO_MAGIA[mid]


def _receptores_de_buff(ses, magic_id, objetivo, area):
    """A QUIEN MAS le llega un buff, ademas de (o en vez de) quien lo lanza.

    Devuelve (otras_sesiones, tambien_a_mi). Antes un buff iba siempre al que
    lo lanzaba o a su mascota: pinchar a otro jugador y lanzarle un buff te
    lo ponia a ti, y los de grupo (Sweeping Attack V: 對象 隊伍, 範圍 12) solo
    te llegaban a ti.
      隊伍  -> tu y los de tu grupo que esten en tu mapa a `area` casillas;
      角色  -> si el objetivo es otro jugador (su id publico), solo el.
    """
    import presencia as _pr_b
    clave = getattr(ses, '_mapa_presencia', None)
    otros = [s for s in (_pr_b._vivas(clave) if clave is not None else [])
             if s is not ses and getattr(s, 'personaje', None)]
    obj = _objeto_de_magia(magic_id)
    p = ses.personaje
    # 自己 CON RADIO: se lanza sobre uno mismo y alcanza a los jugadores de
    # alrededor, esten o no en el grupo (Glorify V: 自己, 範圍 8, "Enshrouds
    # nearby allies"). Lo del grupo es solo para 隊伍 y las auras.
    if obj == '自己' and int(area or 0) > 0:
        r = int(area)
        return [s for s in otros
                if max(abs(s.personaje.tile_x - p.tile_x), abs(s.personaje.tile_y - p.tile_y)) <= r], True
    if obj == '隊伍':
        import equipos as _eq_b
        grupo = [s for s in _eq_b.grupo_de(ses) if s in otros]
        r = int(area or 0) or 12
        return [s for s in grupo
                if max(abs(s.personaje.tile_x - p.tile_x), abs(s.personaje.tile_y - p.tile_y)) <= r], True
    if obj in ('角色', '') and objetivo:
        for s in otros:
            if _pr_b.entidad_de(s) == int(objetivo):
                return [s], False
    return [], True


_MAPEO_BUFF = (('matk_pct', 'matk_pct'), ('mdef_pct', 'mdef_pct'), ('atk_pct', 'atk_pct'),
               ('def_pct', 'def_pct'), ('hp_pct', 'hp_pct'), ('mp_pct', 'mp_pct'),
               ('mp_to_hp_pct', 'mp_to_hp_pct'), ('move_speed_bonus', 'move_speed_bonus'),
               ('atk_speed_bonus', 'atk_speed'), ('crit_rate', 'crit'), ('phys_mit', 'mit'),
               ('mag_mit', 'mag_mit'), ('def_bonus', 'def'), ('atk_bonus', 'atk'),
               ('matk_bonus', 'matk'), ('mdef_bonus', 'mdef'), ('hit_bonus', 'hit'),
               ('eva_bonus', 'eva'), ('mag_dmg_pct', 'mag_dmg_pct'),
               ('phys_dmg_pct', 'phys_dmg_pct'), ('hp_bonus', 'hp_bonus'),
               ('mp_bonus', 'mp_bonus'), ('cast_redux', 'cast_redux'),
               ('res_body', 'res_body'), ('res_mind', 'res_mind'),
               ('res_elec', 'res_lightning'), ('res_fire', 'res_fire'),
               ('res_ice', 'res_ice'), ('res_poison', 'res_corrosion'))


def _entrada_de_buff(mag, dur_s):
    """La entrada de p.buffs para un hechizo, igual que la arma el lanzamiento
    normal (los bonos con los nombres que leen los stats)."""
    e = dict(mag)
    e.pop('mp', None)
    e.pop('hp', None)
    e['fin'] = time.time() + dur_s
    e['mag'] = mag
    e['es_transform'] = False
    for de, a in _MAPEO_BUFF:
        if mag.get(de):
            e[a] = mag.get(de)
    return e


_AURAS = {}


def _hijo_de_aura(magic_id):
    """Si es un AURA (範圍效果光環), el hechizo de grupo que reparte (動態參數1)."""
    mid = int(magic_id or 0)
    if mid not in _AURAS:
        hijo = None
        try:
            import sqlite3 as _sq_a
            con = _sq_a.connect(pathlib.Path(__file__).parent.parent / 'corpus' / 'content.db')
            r = con.execute('select "範圍效果光環", "動態參數1" from magic where id=?', (str(mid),)).fetchone()
            con.close()
            if r and r[0] == '是' and str(r[1] or '').isdigit():
                hijo = int(r[1])
        except Exception:
            pass
        _AURAS[mid] = hijo
    return _AURAS[mid]


PULSO_AURA = 5.0


def _pulso_aura(ses, aura_id, hijo_id, fin):
    """LAS AURAS DE GRUPO. Sweeping Attack V (5655) es un aura de 300 s sobre
    quien la lanza, y reparte su hechizo de grupo, Sweeping Attack V (4891:
    隊伍, 範圍 12, 10 s), a los del grupo que esten a su alcance; es el segundo
    icono que sale. Mientras dure el aura se renueva cada PULSO_AURA s, asi
    que al alejarse o deshacer el grupo se acaba solo ("Effect vanishes when
    you wander out of range or if the team is disbanded")."""
    import combate as _cb_a
    import equipos as _eq_a
    p = getattr(ses, 'personaje', None)
    act = (getattr(p, 'buffs', None) or {}).get(int(aura_id)) if p else None
    if not act or act.get('fin') != fin or time.time() >= fin:
        return
    grupo = _eq_a.grupo_de(ses)
    if len(grupo) > 1:
        mag_h = _cb_a.datos_magia(hijo_id) or {}
        r = int(mag_h.get('area') or 12)
        dur_ms = int(mag_h.get('dur_ms') or 10000)
        clave = getattr(ses, '_mapa_presencia', None)
        for s in grupo:
            q = getattr(s, 'personaje', None)
            if (q is None or getattr(s, '_mapa_presencia', None) != clave
                    or max(abs(q.tile_x - p.tile_x), abs(q.tile_y - p.tile_y)) > r):
                continue
            try:
                _buff_a_otro(s, hijo_id, _entrada_de_buff(mag_h, dur_ms / 1000.0), dur_ms, mag_h)
            except Exception:
                log.exception('pulso de aura')
    try:
        asyncio.get_event_loop().call_later(PULSO_AURA, lambda: _pulso_aura(ses, aura_id, hijo_id, fin))
    except Exception:
        pass


def _buff_a_otro(s, tipo, entrada, dur_ms, mag, lanzador=None, ef=0):
    """Pone el buff a otro jugador: su icono, su ficha y su caducidad.

    En SU pantalla el que hace la animacion de lanzar es `lanzador` (con su
    id publico) y a el solo le cae el efecto, como el Sage Blessing del
    oficial. Antes se le mandaba como si lo lanzara el mismo."""
    import combate as _cb_o
    p2 = s.personaje
    if p2 is None:
        return
    if lanzador is not None and ef:
        try:
            import presencia as _pr_o
            pub = _pr_o.entidad_de(lanzador)
            s.enviar_inmediato(
                _cb_o.efecto_magia_self_inicio(pub, ef, tipo, objetivo=p2.entity_id),
                _cb_o.efecto_magia_self_fin(pub, ef, tipo, objetivo=p2.entity_id))
        except Exception:
            log.debug('efecto del buff ajeno', exc_info=True)
    if not getattr(p2, 'buffs', None):
        p2.buffs = {}
    e = dict(entrada)
    e['fin'] = time.time() + (dur_ms / 1000.0 if dur_ms > 0 else 300.0)
    p2.buffs[int(tipo)] = e
    yo2 = p2.entity_id
    if mag.get('hp_bonus') or mag.get('hp_pct'):
        p2.hp = _vida_max(p2, s.inventario)
    if mag.get('mp_bonus') or mag.get('mp_pct'):
        p2.mp = _mana_max(p2, s.inventario)
    s.enviar_inmediato(struct.pack('<HIBBII', 0x001D, yo2, 1, 4, int(tipo), max(0, int(dur_ms))),
                       _cb_o.atributo(yo2, p2.hp, _cb_o.KIND_HP),
                       _cb_o.atributo(yo2, p2.mp, _cb_o.KIND_MP),
                       _stats_ses(s))

    def _caduca(fin=e['fin']):
        if not s.personaje:
            return
        act = (getattr(s.personaje, 'buffs', None) or {}).get(int(tipo))
        if not act or act.get('fin') != fin:
            return
        s.personaje.buffs.pop(int(tipo), None)
        s.personaje.hp = min(s.personaje.hp, _vida_max(s.personaje, s.inventario))
        s.personaje.mp = min(s.personaje.mp, _mana_max(s.personaje, s.inventario))
        s.enviar_inmediato(struct.pack('<HIBBII', 0x001D, s.personaje.entity_id, 1, 4, int(tipo), 0),
                           _cb_o.atributo(s.personaje.entity_id, s.personaje.hp, _cb_o.KIND_HP),
                           _cb_o.atributo(s.personaje.entity_id, s.personaje.mp, _cb_o.KIND_MP),
                           _stats_ses(s))
    if dur_ms > 0:
        try:
            asyncio.get_event_loop().call_later(dur_ms / 1000.0, _caduca)
        except Exception:
            pass


def _se_ve_paso(stage, desde, hasta):
    """Si un monstruo tiene paso recto hasta el jugador: no se tira a por
    quien esta al otro lado de una pared (ver transitable.py)."""
    return _transitable.linea_libre(stage, tuple(desde), tuple(hasta))


def _casillas_del_tramo(desde, hasta):
    """Las casillas de la recta desde -> hasta, sin la de salida (esa ya se
    piso al llegar a ella) y con la de llegada.

    En cada paso en diagonal entran tambien las dos esquinas: las lineas de
    disparo suelen ir en diagonal (la del evento 151 de la sala 2 de la Magic
    Kichen Path es x+y = 399) y andando en la otra diagonal se pasa de 398 a
    400 sin tocar ninguna de sus casillas.
    """
    (x0, y0), (x1, y1) = desde, hasta
    n = max(abs(x1 - x0), abs(y1 - y0))
    if n == 0:
        return [(x1, y1)]
    salida, prev = [], (x0, y0)
    for k in range(1, n + 1):
        c = (x0 + round((x1 - x0) * k / n), y0 + round((y1 - y0) * k / n))
        if c == prev:
            continue
        if c[0] != prev[0] and c[1] != prev[1]:
            for esq in ((c[0], prev[1]), (prev[0], c[1])):
                if esq not in salida:
                    salida.append(esq)
        if c not in salida:
            salida.append(c)
        prev = c
    return salida


def _evento_de_casilla(stage, tile):
    try:
        import eventos as _ev_c
        return _ev_c.evento_en(stage, tile[0], tile[1])
    except Exception:
        return None


def _choques_al_llegar(ses, addr, st, llegada, token, vistos):
    """CHOCAR: los objetos (tornados, estatuas...) saltan al TOCARLOS, no hace
    falta pararse justo encima. Los TORNADOS (60001) saltan al llegar a
    RADIO_TORNADO casillas, como los de portales.json: el del East Playground
    al Training Palace casi nunca abria el menu porque habia que pararse justo
    encima. El resto de objetos, al estar al lado. Un tornado no vuelve a
    saltar hasta que el jugador sale de su radio; los que ya estan en
    portales.json los resuelve su propio radio y se saltan. Si mientras
    andaba pidio otro movimiento, no se hace nada (lo hara el nuevo)."""
    p = ses.personaje
    if (not p or p.stage != st or getattr(ses, '_token_choque', None) is not token
            or (p.tile_x, p.tile_y) != tuple(llegada)
            or getattr(ses, 'house_furnishing', False)):
        return
    import eventos as _ev_ch
    objs = (_ev_ch.del_stage(st) or {}).get('objetos') or {}
    antes = getattr(ses, '_tornado_cerca', None)
    ahora = None
    for dx in range(-RADIO_TORNADO, RADIO_TORNADO + 1):
        for dy in range(-RADIO_TORNADO, RADIO_TORNADO + 1):
            if not (dx or dy):
                continue
            cv = (p.tile_x + dx, p.tile_y + dy)
            o = objs.get('%d,%d' % cv)
            if not o:
                continue
            es_tornado = int(o[1]) == 60001
            if not es_tornado and max(abs(dx), abs(dy)) > 1:
                continue
            if _portal_en(st, *cv):
                continue
            if es_tornado:
                ahora = (st, cv)
                if antes == ahora:
                    continue           # ya salto y no se ha ido
            if o[0] in vistos:
                continue
            vistos.add(o[0])
            _eventos_al_pisar(ses, addr, cv, solo_chocar=True)
    ses._tornado_cerca = ahora
    try:
        ses.volcar()
    except Exception:
        pass


def _eventos_al_pisar(ses, addr, tile, solo_chocar=False):
    """Dispara el evento del mapa de la casilla en la que se acaba de parar.

    Va DESPUES de _armar_portal_al_llegar y no en su lugar: los portales se
    siguen resolviendo con portales.json, que esta medido uno a uno. Si el
    evento de esa casilla era solo un portal, los efectos de viaje salen
    igual pero no se obedecen, que es lo que hace que no se pisen entre si.
    """
    if not ses.personaje:
        return
    try:
        import eventos_mundo as _evm
        efectos = _evm.al_pisar(ses, tile, solo_chocar=solo_chocar)
        # Si esta casilla ya es un portal de portales.json, el viaje lo hace el
        # portal (medido uno a uno). Si no lo es, el viaje es de un objeto de
        # mision -- de los que te llevan a otro mapa para seguirla -- y se hace.
        if _portal_en(ses.personaje.stage, *tile):
            efectos = [e for e in efectos if e[0] not in ('viajar', 'ir_a_tag')]
        if efectos:
            _aplicar_efectos(ses, addr, efectos, ' al pisar %s' % (tuple(tile),))
    except Exception:
        log.exception('fallo el evento al pisar')


def _eventos_al_morir(ses, monstruo, addr):
    """El evento del mapa que cuelga del bicho que acaba de morir.

    Aqui estan los botines de mision, que es lo que faltaba. El mapa los
    tiene escritos uno a uno; el de Dense Forest, por ejemplo:

        evento 502, al morir en grupo
          si QUEST_STEP(502, 0) y BAGITEM(181, =, 0)
          y EMPTYSLOT_COUNT(>, 0) y PROB100(5)
          -> CREATE_ITEM(181, 1)

    o sea el Mushroom de The Reivers, al 5%, solo si no llevas ya uno y te
    queda hueco. Nada de eso estaba escrito en el servidor y por eso el
    diario se quedaba en 0/1 por mucho que mataras.

    Tambien se repasan los eventos que se comprueban solos -- los de disparo
    0 --, porque son los que miran si una zona se ha quedado sin bichos y es
    justo ahora cuando puede haber pasado.
    """
    if not ses.personaje:
        return
    try:
        import eventos_mundo as _evm
        efectos = _evm.al_morir_monstruo(ses, monstruo)
        if efectos:
            _aplicar_efectos(ses, addr, efectos,
                             ' al morir %s' % getattr(monstruo, 'nombre', '?'))
        ef_pend = _evm.pendientes(ses)
        if ef_pend:
            _aplicar_efectos(ses, addr, ef_pend,
                             ' pendientes tras morir %s' % getattr(monstruo, 'nombre', '?'))
    except Exception:
        log.exception('fallo el evento al morir el monstruo')


def _cerrar_viaje(ses, addr, stage, tile, nombre_dest):
    """Ejecuta lo que dejo pendiente un dialogo al cerrarse el cuadro.

    Medido en la captura: al confirmar la faccion quedan DOS lineas mas de
    dialogo, y solo cuando se cierra el cuadro llegan las misiones y el
    cambio de mapa. Todo eso va junto y en este orden.
    """
    import clases as _cl, time as _tm
    p = ses.personaje
    if not p:
        return
    paquetes = []

    # Las misiones: primero la de registro de la ciudad y despues la 103
    # marcada como completada.
    fac = getattr(ses, 'misiones_al_llegar', None)
    if fac:
        ses.misiones_al_llegar = None
        qreg = _cl.QUEST_POR_FACCION.get(fac)
        if qreg:
            if qreg not in [x[0] for x in (p.quests or [])]:
                p.quests = list(p.quests or []) + [(qreg, 0)]
            paquetes += [_cl.mision(p.char_id, qreg, 0),
                         _cl.aviso(_cl.nombre_de_quest(qreg), tipo=0,
                                   msg_id=_cl.MSG_QUEST)]
        paquetes.append(_cl.mision(p.char_id, _cl.QUEST_ELEGIR_PAIS, 1,
                                   int(_tm.time())))

    # La faccion se aplica al llegar, que es cuando el cliente la cambia.
    nueva = getattr(ses, 'faccion_al_llegar', None)
    if nueva:
        ses.faccion_al_llegar = None
        p.faction = nueva
        if getattr(ses, 'usuario', None):
            cuentas.guardar_faccion(ses.usuario, p.char_id, nueva)
        log.info(f"[{addr}] faccion al llegar: {nueva}")

    if paquetes:
        ses.enviar(*paquetes)
    _sincronizar_cambio_mapa(ses, stage, tile[0], tile[1])
    log.info(f"[{addr}] al cerrarse el dialogo: {nombre_dest} "
             f"(stage {stage}) casilla {tile}")


def _vida_max(p, bolsa=None) -> int:
    """El tope de vida que el cliente enseña: el guardado mas lo que dan las
    pasivas, el equipo (gear y fashion) y los buffs activos."""
    import inventario as inv
    b = bolsa
    if b is None:
        b = getattr(p, 'inventario', None)
    if b is None and hasattr(p, 'ses'):
        b = getattr(p.ses, 'inventario', None)
    return inv.vida_maxima(getattr(p, 'hp_max', 0),
                           getattr(p, 'habilidades', None), bolsa=b,
                           mejoras=getattr(p, 'mejoras', None),
                           buffs=getattr(p, 'buffs', None),
                           mp_max=getattr(p, 'mp_max', 0))


def _mana_max(p, bolsa=None) -> int:
    """El tope de mana que el cliente enseña: el guardado mas lo que dan las
    pasivas, el equipo (gear y fashion) y los buffs activos."""
    import inventario as inv
    b = bolsa
    if b is None:
        b = getattr(p, 'inventario', None)
    if b is None and hasattr(p, 'ses'):
        b = getattr(p.ses, 'inventario', None)
    return inv.mana_maximo(getattr(p, 'mp_max', 0),
                           getattr(p, 'habilidades', None), bolsa=b,
                           mejoras=getattr(p, 'mejoras', None),
                           buffs=getattr(p, 'buffs', None))


def _cb_alcance(ses) -> int:
    """Desde cuantas casillas llega el arma que se lleva puesta."""
    import combate as _cb
    arma = ses.inventario.get(3, 0) if getattr(ses, 'inventario', None) else 0
    return _cb.alcance_arma(arma)


def _stats_ses(ses):
    """Genera el paquete 0x0042 con stats completos del personaje."""
    import inventario as inv
    p = getattr(ses, 'personaje', None)
    bolsa = getattr(ses, 'inventario', None)
    habs = p.habilidades if p else None
    hp = p.hp if p else None
    hp_max = p.hp_max if p else None
    mp = p.mp if p else None
    mp_max = p.mp_max if p else None
    oro = getattr(ses, 'oro', 0)
    buffs = getattr(p, 'buffs', None)
    bars, max_pts = _max_sp_info(p)
    sp = getattr(ses, 'sp', None)
    if sp is None and p is not None:
        sp = max(0, int(getattr(p, 'sp', 0) or 0))
        ses.sp = sp
    return inv.stats(bolsa, habs, hp=hp, hp_max=hp_max, mp=mp, mp_max=mp_max,
                     oro=oro, buffs=buffs, sp=sp, sp_max=bars,
                     mejoras=getattr(p, 'mejoras', None) if p else None)


def _otorgar_skill_exp(ses, p, yo, arma_puesta=0, magic_id=0, accion=None):
    """Otorga Skill EXP en cada impacto de ataque o uso de habilidad activa (buff/cura/spell)."""
    if not p or not getattr(p, 'habilidades', None):
        return []
    import configuracion, cuentas, clases as _cl, combate as _cb, inventario as _iv
    pkgs = []
    mult = configuracion.multiplicador_skill_exp()
    exp_ganada = max(1, int(round(1 * mult)))

    SKILLS_PRODUCTOR = {20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31}

    # Las habilidades de arma de TODO lo equipado, no solo de la ranura del
    # arma: un Protector con hacha y escudo entrena Axe y Shield, y asi sale
    # en las capturas de Celestia.
    skills_arma = _cl.skills_de_equipo(getattr(ses, 'inventario', None))
    if not skills_arma and arma_puesta:
        sid_a = _cl.skill_de_item(arma_puesta)
        if sid_a:
            skills_arma = {sid_a}

    nuevas_habs = []
    subio_alguna = False
    # Suben TODAS las habilidades del personaje, no solo la del arma. En las
    # capturas de Celestia aparecen Reserve, Finesse, Grapple, Garment,
    # Enhance y Sword con recuentos parecidos (23, 23, 23, 21, 20, 19 sobre
    # 2824 golpes), asi que cada una tira su propia probabilidad por golpe.
    # El valor base es 1: los "100 Exp" de la captura son el multiplicador de
    # ese servidor.
    # Que habilidades pueden subir con esta accion. Un espadachin no sube
    # Cook ni Fishing por pegarle a un monstruo: cada habilidad tiene su
    # actividad, declarada en skill.xml (ver clases.ACCION_POR_SKILL).
    mag_branch = _cl.skill_de_magia(magic_id) if magic_id else None
    if accion is None:
        if mag_branch in (1, 2, 3, 4, 5, 6, 7, 8, 34, 35, 36) or (8 in skills_arma) or (magic_id and not skills_arma):
            accion = 'magia'
        elif 17 in skills_arma or mag_branch == 17:
            accion = 'distancia'      # con arco
        else:
            accion = 'melee'
    # skills_arma va adentro: es lo que arrastra Shield con espada o hacha,
    # y Snipe y Eagle Eye con arco.
    candidatas = _cl.skills_que_suben(accion, skills_arma)
    if mag_branch:
        candidatas.add(mag_branch)
    for h in p.habilidades:
        sid, slv, sexp = h[0], h[1], h[2]
        if sid not in candidatas or random.random() >= _cb.PROB_SKILL_EXP:
            nuevas_habs.append((sid, slv, sexp))
            continue
        sexp += exp_ganada
        max_lv = (p.nivel + 11) if sid in SKILLS_PRODUCTOR else p.nivel
        # La experiencia que pide cada nivel sale de level.xml por rama (sid 1..36).
        req = max(1, _cl.exp_requerida_skill(slv, sid))
        while sexp >= req and slv < max_lv:
            sexp -= req
            slv += 1
            req = max(1, _cl.exp_requerida_skill(slv, sid))
            subio_alguna = True
            pkgs.append(_cb.efecto_level_up(yo, es_skill=True))
            pkgs.append(_cl.aviso_doble(_cl.MSG_SKILL_SUBE, _cl.nombre(sid)))
        if slv >= max_lv:
            sexp = min(sexp, req)
        # La skill exp va como TEXTO en un 0x000D de dos cadenas, no como
        # 0x000B: ese mensaje dibuja un numero flotante, y mandandolo con el
        # numero de la habilidad aparecia un "9" verde junto al dano.
        pkgs.append(_cl.aviso_doble(_cl.MSG_SKILL_EXP, _cl.nombre(sid),
                                    str(exp_ganada)))
        # 0x001D code=0 (sub_5FEC40 en Angel.exe): actualiza dword_14388[i] (exp actual de la skill)
        pkgs.append(struct.pack('<HIBBII', 0x001D, yo, 1, 0, sid, sexp & 0xFFFFFFFF))
        nuevas_habs.append((sid, slv, sexp))

    p.habilidades = nuevas_habs
    if subio_alguna:
        # Los porcentajes se actualizan con los 0x001D individuales; el arbol
        # completo solo hace falta cuando cambia el rango de una habilidad.
        pkgs.append(_cl.arbol(p.habilidades))
    if magic_id:
        pkgs.extend((_cb.atributo(yo, getattr(ses, 'sp', 0) or 0,
                                  _cb.KIND_SP),
                     _stats_ses(ses)))

    if getattr(ses, 'usuario', None):
        cuentas.guardar_progreso(ses.usuario, p.char_id, p.nivel, p.exp,
                                 p.hp, p.mp, p.habilidades,
                                 hp_max=p.hp_max, mp_max=p.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)
    return pkgs


def _ejecutar_proc_subhechizo(ses, yo, m, sub_id: int, addr=None) -> list:
    """Ejecuta el sub-hechizo disparado por un buff con trigger (ej. Sun Strike de Blazing Sun,
    debuff de Erosion, buff de Spell Boost, golpe de Fire Gathering, cura MP de Witch Ward, etc.)."""
    import combate as _cb
    import inventario as _iv
    p = getattr(ses, 'personaje', None)
    if not p or getattr(ses, 'muerto', False) or not sub_id:
        return []
    pkgs = []
    d_sub = _cb._magic_xml().get(int(sub_id)) or {}
    smag = _cb.datos_magia(int(sub_id))
    ef_proc = int(smag.get('efecto') or 251)
    targ_type = str(d_sub.get('對象') or '')
    es_ofensivo = (
        d_sub.get('攻擊型') == '是' or
        int(float(d_sub.get('平均傷害') or 0)) > 0 or
        (int(float(d_sub.get('HP') or 0)) > 0 and str(d_sub.get('HP定義') or '') != '最大值' and targ_type != '自己')
    )

    # Caso 1: Proc beneficioso sobre el propio jugador (Spell Boost, Witch Ward, Lava Charm, Flowing Water, etc.)
    if not es_ofensivo and not smag.get('es_debuff') and not _cb.efecto_secundario(int(sub_id)):
        pkgs.append(_cb.efecto_magia_self_fin(yo, ef_proc, int(sub_id)))
        hp_def_s = str(d_sub.get('HP定義') or '')
        mp_def_s = str(d_sub.get('MP定義') or '')
        raw_hp_s = int(float(d_sub.get('HP') or 0))
        raw_mp_s = int(float(d_sub.get('MP') or 0))
        dur_s_ms = int(smag.get('dur_ms') or 0)
        if hp_def_s == '數值' and raw_hp_s > 0:
            ticks_h = max(1, dur_s_ms // 1000) if 0 < dur_s_ms <= 5000 else 1
            hc = raw_hp_s * ticks_h
            p.hp = min(_vida_max(p, ses.inventario), p.hp + hc)
            pkgs.append(_cb.atributo(yo, p.hp, _cb.KIND_HP))
            pkgs.append(_cb.numero_flotante(yo, hc, _cb.TIPO_CURA_HP))
        if mp_def_s == '數值' and raw_mp_s > 0:
            ticks_m = max(1, dur_s_ms // 1000) if 0 < dur_s_ms <= 5000 else 1
            mc = raw_mp_s * ticks_m
            p.mp = min(_mana_max(p, ses.inventario), p.mp + mc)
            pkgs.append(_cb.atributo(yo, p.mp, _cb.KIND_MP))
            pkgs.append(_cb.numero_flotante(yo, mc, _cb.TIPO_CURA_MP))

        tiene_bono_buff = any(smag.get(k) for k in (
            'def_bonus', 'atk_bonus', 'matk_bonus', 'mdef_bonus', 'hit_bonus', 'eva_bonus',
            'crit_rate', 'hp_bonus', 'mp_bonus', 'phys_dmg_pct', 'mag_dmg_pct',
            'phys_mit', 'mag_mit', 'move_speed_bonus', 'atk_speed_bonus'
        ))
        if dur_s_ms > 0 and tiene_bono_buff:
            if not hasattr(p, 'buffs') or p.buffs is None:
                p.buffs = {}
            pfin = time.time() + (dur_s_ms / 1000.0)
            b_proc = dict(smag)
            b_proc.pop('mp', None)
            b_proc.pop('hp', None)
            b_proc['fin'] = pfin
            b_proc['mag'] = smag
            if smag.get('crit_rate'):
                b_proc['crit'] = smag['crit_rate']
            if smag.get('def_bonus'):
                b_proc['def'] = smag['def_bonus']
            if smag.get('atk_bonus'):
                b_proc['atk'] = smag['atk_bonus']
            if smag.get('matk_bonus'):
                b_proc['matk'] = smag['matk_bonus']
            if smag.get('mdef_bonus'):
                b_proc['mdef'] = smag['mdef_bonus']
            if smag.get('hit_bonus'):
                b_proc['hit'] = smag['hit_bonus']
            if smag.get('eva_bonus'):
                b_proc['eva'] = smag['eva_bonus']
            if smag.get('phys_dmg_pct'):
                b_proc['phys_dmg_pct'] = smag['phys_dmg_pct']
            if smag.get('mag_dmg_pct'):
                b_proc['mag_dmg_pct'] = smag['mag_dmg_pct']
            if smag.get('hp_bonus'):
                b_proc['hp_bonus'] = smag['hp_bonus']
            if smag.get('mp_bonus'):
                b_proc['mp_bonus'] = smag['mp_bonus']
            p.buffs[int(sub_id)] = b_proc
            if smag.get('hp_bonus'):
                p.hp = min(_vida_max(p, ses.inventario), p.hp + int(smag['hp_bonus']))
                pkgs.append(_cb.atributo(yo, p.hp, _cb.KIND_HP))
                pkgs.append(_cb.numero_flotante(yo, int(smag['hp_bonus']), _cb.TIPO_CURA_HP))
            if smag.get('mp_bonus'):
                p.mp = min(_mana_max(p, ses.inventario), p.mp + int(smag['mp_bonus']))
                pkgs.append(_cb.atributo(yo, p.mp, _cb.KIND_MP))
                pkgs.append(_cb.numero_flotante(yo, int(smag['mp_bonus']), _cb.TIPO_CURA_MP))
            pkgs.append(struct.pack('<HIBBII', 0x001D, yo, 1, 4, int(sub_id), dur_s_ms))
            pkgs.append(_stats_ses(ses))

            def _expirar_sub_buff(sk_id=int(sub_id), fin=pfin):
                if not ses.personaje:
                    return
                b_act = getattr(ses.personaje, 'buffs', None)
                act = b_act.get(sk_id) if b_act else None
                if not act or act.get('fin') != fin:
                    return
                b_act.pop(sk_id, None)
                ses.personaje.hp = min(ses.personaje.hp, _vida_max(ses.personaje, ses.inventario))
                ses.personaje.mp = min(ses.personaje.mp, _mana_max(ses.personaje, ses.inventario))
                ses.enviar_inmediato(
                    struct.pack('<HIBBII', 0x001D, yo, 1, 4, sk_id, 0),
                    _cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP),
                    _cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP),
                    _stats_ses(ses),
                )
            try:
                asyncio.get_event_loop().call_later(dur_s_ms / 1000.0, _expirar_sub_buff)
            except Exception:
                pass
        return pkgs

    # Caso 2: Proc ofensivo o debuff sobre el monstruo / area alrededor (Sun Strike, Mana Overflow, Erosion, Fire Gathering, etc.)
    blancos_proc = []
    area_p = int(smag.get('area') or 0)
    if area_p > 0:
        cx_p = p.tile_x if targ_type == '自己' or not m else m.tile_x
        cy_p = p.tile_y if targ_type == '自己' or not m else m.tile_y
        rad_p = max(4, area_p)
        for bm in list((getattr(ses, 'monstruos', None) or {}).values()):
            if getattr(bm, 'vivo', False) and not getattr(bm, 'encantado', False):
                if max(abs(bm.tile_x - cx_p), abs(bm.tile_y - cy_p)) <= rad_p:
                    blancos_proc.append(bm)
        if m and getattr(m, 'vivo', False) and not getattr(m, 'encantado', False) and m not in blancos_proc:
            blancos_proc.append(m)
    elif m and getattr(m, 'vivo', False) and not getattr(m, 'encantado', False):
        blancos_proc.append(m)

    if not blancos_proc:
        return pkgs

    es_mag_p = int(float(d_sub.get('平均傷害') or 0)) > 0 or str(d_sub.get('公式') or '') in ('4', '5', '6', '7', '17')
    st_bin = _iv.stats(ses.inventario, p.habilidades, buffs=getattr(p, 'buffs', None), mejoras=_mejoras_de(ses))
    atk_pow = struct.unpack_from('<I', st_bin, 2 + 44)[0] if es_mag_p else struct.unpack_from('<I', st_bin, 2 + 20 + 4)[0]
    if not es_mag_p:
        stance_p = _cb.stance_de(int(sub_id))
        atk_pow += int(round(stance_p * _cb.PESO_STANCE))
        mult_p = 1.0
        var_p = 0.03
        if smag.get('dano_coef', 0) > 0:
            mult_p *= (smag['dano_coef'] / 100.0)
    else:
        dano_base_p = int(float(d_sub.get('平均傷害') or 0)) or smag.get('dano_base', 0)
        denom_p = smag.get('base_denom', 200) or 200
        mult_p = (dano_base_p / float(denom_p)) if dano_base_p > 0 else 1.0
        var_p = 0.05
        if smag.get('dano_coef', 0) > 0:
            mult_p *= (smag['dano_coef'] / 100.0)
    mods_eq_p = _iv.modificadores_porcentuales_equipo(ses.inventario)
    _clave_pct_p = 'mag_dmg_pct' if es_mag_p else 'phys_dmg_pct'
    if mods_eq_p.get(_clave_pct_p, 0) > 0:
        mult_p *= (1.0 + mods_eq_p[_clave_pct_p] / 100.0)
    _pct_b_p = _cb.pct_dano_buffs(getattr(p, 'buffs', None), es_mag_p)
    if _pct_b_p:
        mult_p *= (1.0 + _pct_b_p / 100.0)
    ef_sec = _cb.efecto_secundario(int(sub_id))
    dur_debuff = int(smag.get('dur_ms') or 0)

    for bm in blancos_proc:
        if not getattr(bm, 'vivo', False):
            continue
        if es_ofensivo:
            dano_p = bm.recibir(atk_pow, es_magico=es_mag_p, mult=mult_p, var_pct=var_p)
            pkgs.extend([
                _cb.numero_de_dano(yo, bm.entity_id, dano_p, ataque=int(sub_id), efecto=ef_proc, cast_time=0, es_magia=es_mag_p),
                _cb.cierre_de_dano(yo, bm.entity_id, ataque=int(sub_id), efecto=ef_proc, tile_x=bm.tile_x, tile_y=bm.tile_y),
                _cb.numero_flotante(bm.entity_id, dano_p, _cb.TIPO_DANO),
                _cb.atributo(bm.entity_id, bm.porcentaje if bm.hp > 0 else 0),
            ])
            if bm.hp <= 0 or not bm.vivo:
                bm.hp = 0
                _procesar_muerte_monstruo(ses, bm, yo, addr, espera=0.05)
                continue
        if ef_sec:
            bm.aplicar_efecto(ef_sec)
        if dur_debuff > 0 and (
            smag.get('def_mod', 0) < 0 or smag.get('mdef_mod', 0) < 0 or
            smag.get('atk_mod', 0) < 0 or smag.get('matk_mod', 0) < 0 or
            (ef_sec and ef_sec.get('dur_ms'))
        ):
            if not es_ofensivo:
                pkgs.append(_cb.efecto_magia_self_fin(bm.entity_id, ef_proc, int(sub_id)))
            pkgs.append(struct.pack('<HIBBII', 0x001D, bm.entity_id, 1, 4, int(sub_id), dur_debuff))
    return pkgs


def _procesar_triggers_buffs(ses, yo, m, addr=None, en_ataque=True) -> list:
    """Revisa los buffs activos del jugador y dispara sus triggers al atacar (en_ataque=True)
    o al recibir un golpe de un monstruo (en_ataque=False)."""
    import combate as _cb
    p = getattr(ses, 'personaje', None)
    if not p or getattr(ses, 'muerto', False) or not getattr(p, 'buffs', None):
        return []
    ahora = time.time()
    pkgs = []
    for bid, bdata in list(p.buffs.items()):
        if not isinstance(bdata, dict) or bdata.get('fin', 0) <= ahora:
            continue
        sub_id = int(bdata.get('proc_spell') or 0)
        if not sub_id:
            continue
        if en_ataque and not bdata.get('proc_on_attack'):
            continue
        if not en_ataque and not bdata.get('proc_on_hit'):
            continue
        prob = float(bdata.get('proc_prob') or 30.0)
        if random.random() * 100.0 < prob:
            pkgs.extend(_ejecutar_proc_subhechizo(ses, yo, m, sub_id, addr=addr))
            if int(bdata.get('usos_restantes') or 0) > 0:
                bdata['usos_restantes'] = int(bdata['usos_restantes']) - 1
                if bdata['usos_restantes'] <= 0:
                    p.buffs.pop(bid, None)
                    p.hp = min(p.hp, _vida_max(p, ses.inventario))
                    p.mp = min(p.mp, _mana_max(p, ses.inventario))
                    pkgs.extend([
                        struct.pack('<HIBBII', 0x001D, yo, 1, 4, int(bid), 0),
                        _cb.atributo(yo, p.hp, _cb.KIND_HP),
                        _cb.atributo(yo, p.mp, _cb.KIND_MP),
                        _stats_ses(ses),
                    ])

        # Wolf's Claw (16802..16806): Se activa cuando el enemigo tiene menos del 20% de HP
        wc_sub = int(bdata.get('wolf_claw_sub') or 0)
        if wc_sub and en_ataque and m and getattr(m, 'vivo', False):
            hp_cur = getattr(m, 'hp', 0)
            hp_max = max(1, getattr(m, 'hp_max', 1))
            if (hp_cur / hp_max) < 0.20:
                pkgs.extend(_ejecutar_proc_subhechizo(ses, yo, m, wc_sub, addr=addr))
                if int(bdata.get('usos_restantes') or 0) > 0:
                    bdata['usos_restantes'] = int(bdata['usos_restantes']) - 1
                    if bdata['usos_restantes'] <= 0:
                        p.buffs.pop(bid, None)
                        pkgs.extend([
                            struct.pack('<HIBBII', 0x001D, yo, 1, 4, int(bid), 0),
                            _cb.atributo(yo, 0, _cb.KIND_TRANSFORM),
                            _stats_ses(ses),
                        ])
                        try:
                            import presencia as _pres
                            _pres.notificar_transformacion(ses, 0)
                        except Exception:
                            pass
    return pkgs


class Servidor:
    def __init__(self, host, port, fport=21238, wport=None):
        self.host, self.port, self.fport = host, port, fport
        # puerto del servidor de MUNDO, al que se redirige tras el login
        self.wport = wport or (port + 1)
        self.desconocidos = collections.Counter()
        self.sesiones = 0
        self.mundos = []          # sesiones de mundo vivas, para el GM
        # Traspaso login -> mundo. Son dos conexiones TCP distintas: cuando
        # el cliente pide entrar (0x0006) anotamos aca que personaje eligio,
        # y la conexion de mundo que llega despues lo levanta. Se indexa por
        # IP porque el puerto de origen cambia entre las dos conexiones.
        self.pendientes = {}

    async def _patrulla_lyceum(self, ses):
        """Mueve a los House Pickets periodicamente para que patrullen el Angel Lyceum,
        y gestiona el respawn de monstruos y movimiento de la mascota."""
        rutas = [
            (5, [(94, 55), (94, 61)]),
            (6, [(123, 53), (128, 53)]),
            (7, [(145, 81), (150, 81)]),
            (12, [(145, 71), (145, 77)]),
            (16, [(217, 75), (211, 75)]),
        ]
        estado = {eid: 0 for eid, _ in rutas}
        MOVE = Msg.registry[(0x0005, 's2c', '*')]
        try:
            while True:
                await asyncio.sleep(5)
                if not getattr(ses, 'personaje', None):
                    continue

                # 1. Patrulla de House Pickets en Angel Lyceum
                if ses.personaje.stage == 41:
                    for eid, pts in rutas:
                        idx = estado[eid]
                        nxt = 1 - idx
                        cur_t = pts[idx]
                        dst_t = pts[nxt]
                        estado[eid] = nxt
                        msg = MOVE.build(
                            entity_id=eid,
                            cur_x=cur_t[0] * 32,
                            cur_y=cur_t[1] * 32,
                            dst_x=dst_t[0] * 32,
                            dst_y=dst_t[1] * 32,
                            speed=50
                        )
                        ses.enviar(msg)

                # 2. Respawn de monstruos caidos. En las instancias no:
                # se limpian y se quedan limpias hasta salir y volver.
                monstruos = getattr(ses, 'monstruos', {})
                import login as _lg
                _en_instancia = es_instancia(
                    getattr(getattr(ses, 'personaje', None), 'stage', 0))
                for mid, m in list(monstruos.items()):
                    if not _en_instancia and m.toca_reaparecer():
                        m.revivir()
                        _sp_pkg = _lg._npc_spawn(m.entity_id, m.npc_type, m.nombre, (m.tile_x, m.tile_y), sprite=getattr(m, 'sprite', 0), klass=1)
                        ses.enviar(_sp_pkg)
                        for _comp in _companeros(ses):
                            try:
                                _comp.enviar_inmediato(_sp_pkg)
                            except Exception:
                                pass
                        log.info(f"monstruo {m.nombre} (eid={m.entity_id}) reaparecio en ({m.tile_x}, {m.tile_y})")

                # 3. Mascotas en patio de Raise-a-Pet Room (stage 500)
                if ses.personaje.stage == 500:
                    import casas as _cs_pet_loop, random as _rnd_pet, login as _lg_pet_loop
                    import configuracion as _cfg_p, mascotas as _ms_p, clases as _cl_p, inventario as _iv_p
                    _c_pet_loop = getattr(ses, 'casa_visitando', None) or _cs_pet_loop.obtener_o_crear_casa(ses.personaje.char_id, ses.personaje.nombre)
                    if _c_pet_loop:
                        if _c_pet_loop.owner_id == ses.personaje.char_id:
                            for _sl in range(477, 487):
                                _sl_str = str(_sl)
                                if _sl in ses.inventario:
                                    _it_p = ses.inventario[_sl]
                                    if _sl_str not in _c_pet_loop.care_pets:
                                        _sp_sync = _iv_p.sprite_de_mascota(_it_p)
                                        _nom_sync = _nombre_item(_it_p)
                                        _pm_sync = getattr(ses.personaje, 'mascotas', {}) or {}
                                        _fp_sync = _pm_sync.get(_sl_str) or {}
                                        if _fp_sync.get('nombre'):
                                            _nom_sync = _fp_sync['nombre']
                                        if _fp_sync.get('tipo'):
                                            _sp_sync = _fp_sync['tipo']
                                        _c_pet_loop.care_pets[_sl_str] = {
                                            'item_id': _it_p,
                                            'name': _nom_sync,
                                            'sprite': _sp_sync,
                                            'slot': _sl,
                                            'time': int(time.time()),
                                            'tile': [36, 28]
                                        }
                                        _peid_new = 8101 + (_sl - 477)
                                        ses.enviar(_lg_pet_loop._npc_spawn(_peid_new, 1, _nom_sync, (36, 28), sprite=_sp_sync, klass=200, direccion=6))
                                elif _sl_str in _c_pet_loop.care_pets:
                                    _c_pet_loop.care_pets.pop(_sl_str, None)
                                    _peid_del = 8101 + (_sl - 477)
                                    ses.enviar(struct.pack('<HIB', 0x0007, int(_peid_del), 0))

                        base_exp = getattr(_cfg_p, 'EXP_BASE_PET_ROOM_TICK', 15)
                        mult_exp = getattr(_cfg_p, 'MULTIPLICADOR_EXP_PET', 1.0)
                        exp_ganada = int(base_exp * mult_exp)

                        for s_id, p_info in list(_c_pet_loop.care_pets.items()):
                            try:
                                p_slot = int(s_id)
                                p_eid = 8101 + (p_slot - 477)
                                cur_pt = p_info.get('tile') or [36, 28]
                                import transitable as _tr_pet
                                dx = _rnd_pet.choice([-1, 0, 1])
                                dy = _rnd_pet.choice([-1, 0, 1])
                                nxt_x = max(32, min(40, cur_pt[0] + dx))
                                nxt_y = max(25, min(31, cur_pt[1] + dy))
                                if (nxt_x != cur_pt[0] or nxt_y != cur_pt[1]) and _tr_pet.se_pisa(500, nxt_x, nxt_y):
                                    nxt_pt = [nxt_x, nxt_y]
                                    p_info['tile'] = nxt_pt
                                    msg_walk = MOVE.build(
                                        entity_id=p_eid,
                                        cur_x=cur_pt[0] * 32,
                                        cur_y=cur_pt[1] * 32,
                                        dst_x=nxt_pt[0] * 32,
                                        dst_y=nxt_pt[1] * 32,
                                        speed=40
                                    )
                                    ses.enviar(msg_walk)
                                if _rnd_pet.random() < 0.35:
                                    _p_frases = [
                                        "I'm training hard for my master!",
                                        "Master's house is so cozy and warm~",
                                        "Sleeping and eating here is paradise!",
                                        "Look at me stretch and run!",
                                        "I will become the strongest pet ever!",
                                        "Yay! Training makes me happy!"
                                    ]
                                    ses.enviar(_decir(p_eid, p_info.get('name') or 'Pet', _rnd_pet.choice(_p_frases)))

                                if exp_ganada > 0 and _c_pet_loop.owner_id == ses.personaje.char_id:
                                    p_mascs = getattr(ses.personaje, 'mascotas', None)
                                    if p_mascs is None:
                                        ses.personaje.mascotas = {}
                                        p_mascs = ses.personaje.mascotas
                                    ficha = p_mascs.get(str(p_slot))
                                    if not ficha and p_slot in ses.inventario:
                                        it_id = ses.inventario[p_slot]
                                        d_pet = _iv_p.datos_mascota(it_id)
                                        ficha = _ms_p.recien_nacida(
                                            d_pet['nombre'], d_pet['sprite'],
                                            nivel=max(1, getattr(_cfg_p, 'MASCOTA_NIVEL_INICIAL', 1)),
                                            estrellas=max(1, int(d_pet.get('estrellas') or 1))
                                        )
                                        ficha['ranura'] = p_slot
                                        ficha['item'] = it_id
                                        ficha['instancia'] = 1000 + int(p_slot)
                                        ficha['fuera'] = False
                                        p_mascs[str(p_slot)] = ficha
                                    if ficha:
                                        sp_antes = ficha.get('sprite')
                                        subidos = _ms_p.dar_exp(ficha, exp_ganada)
                                        if subidos > 0:
                                            nom_p = p_info.get('name') or ficha.get('nombre') or 'Pet'
                                            ses.enviar(
                                                _cl_p.aviso(f"{nom_p} reached Level {ficha['nivel']}!", tipo=7, msg_id=_cl_p.MSG_TEXTO),
                                                struct.pack('<HIB', 0x001D, p_eid, 4),
                                                *_refrescar(ses, [p_slot])
                                            )
                                            if ficha.get('sprite') != sp_antes or (ficha.get('tipo') and ficha['tipo'] != p_info.get('sprite')):
                                                new_sp = ficha.get('tipo') or _iv_p.sprite_de_mascota(ficha.get('item', 0)) or ficha.get('sprite')
                                                p_info['sprite'] = new_sp
                                                ses.enviar(
                                                    struct.pack('<HIB', 0x0007, int(p_eid), 0),
                                                    _lg_pet_loop._npc_spawn(p_eid, 1, nom_p, (cur_pt[0], cur_pt[1]), sprite=new_sp, klass=200, direccion=6)
                                                )
                                        if getattr(ses, 'usuario', None):
                                            cuentas.guardar_mascota(ses.usuario, ses.personaje.char_id, ficha, ses.personaje.mascotas)
                            except Exception:
                                pass

                out = ses.drenar()
                if out and getattr(ses, 'writer', None):
                    try:
                        if getattr(ses, 'grab', None):
                            ses.grab.salida(out)
                        ses.writer.write(out)
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.debug(f"patrulla lyceum detenida: {e}")

    async def _bucle_regeneracion(self, ses):
        """Regeneracion pasiva de HP y MP.

        Sentado (tecla Insert) el tick es cada segundo; de pie hay que llevar
        dos segundos quieto y fuera de combate, y el tick es cada dos.

        Cuanto se recupera lo decide configuracion.regenera(): un porcentaje
        del maximo que sube con el nivel, no una cantidad fija. Antes eran +6
        MP y +12 HP siempre, y a nivel 300, con 121.440 de MP, eso son cinco
        horas y media de estar quieto para llenar la barra.
        """
        import combate as _cb
        import configuracion
        try:
            while getattr(ses, 'conectado', True):
                await asyncio.sleep(1.0)
                p = getattr(ses, 'personaje', None)
                if not p:
                    continue

                try:
                    _casa_tick_limpieza(ses)
                    _casa_sincronizar_token(ses)
                    _casa_tick_monstruos(ses)
                except Exception:
                    log.exception('casas: error al contar tiempo conectado')
                yo = p.entity_id
                sentado = getattr(ses, 'sentado', False)
                ahora = time.time()
                ultimo_mov = getattr(ses, 'ultimo_movimiento', 0)
                ultimo_comb = getattr(ses, 'ultimo_combate', 0)
                en_combate = (ahora - ultimo_comb) < 4.0

                toca_regen = False
                if sentado:
                    toca_regen = True
                else:
                    if (ahora - ultimo_mov) >= 2.0 and not en_combate:
                        ultimo_tick = getattr(ses, 'ultimo_regen_tick', 0)
                        if (ahora - ultimo_tick) >= 2.0:
                            toca_regen = True
                            ses.ultimo_regen_tick = ahora

                if toca_regen:
                    pkgs = []
                    bolsa_pj = getattr(ses, 'inventario', None)
                    eff_hp_max = _vida_max(p, bolsa=bolsa_pj)
                    eff_mp_max = _mana_max(p, bolsa=bolsa_pj)
                    # Lo que se recupera es un PORCENTAJE del maximo y sube
                    # con el nivel. Con la cantidad plana de antes, +6 MP por
                    # tick, un personaje de nivel 300 tardaba cinco horas y
                    # media en llenar su barra.
                    _nv = getattr(p, 'nivel', 1) or 1
                    if p.mp < eff_mp_max:
                        rec_mp = configuracion.regenera(eff_mp_max, _nv,
                                                        sentado, False)
                        p.mp = min(eff_mp_max, p.mp + rec_mp)
                        pkgs.append(_cb.atributo(yo, p.mp, _cb.KIND_MP))
                    if p.hp < eff_hp_max:
                        rec_hp = configuracion.regenera(eff_hp_max, _nv,
                                                        sentado, True)
                        p.hp = min(eff_hp_max, p.hp + rec_hp)
                        pkgs.append(_cb.atributo(yo, p.hp, _cb.KIND_HP))

                    if pkgs:
                        ses.enviar_inmediato(*pkgs)
                        if getattr(ses, 'usuario', None):
                            cuentas.guardar_progreso(ses.usuario, p.char_id, p.nivel, p.exp,
                                                     p.hp, p.mp, p.habilidades,
                                                     hp_max=p.hp_max, mp_max=p.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)

                # --- Decaimiento periodico de saciedad (60s) y ganancia/perdida de intimidad (180s) ---
                f_pet = getattr(p, 'mascota', None)
                if isinstance(f_pet, dict) and f_pet.get('fuera'):
                    import mascotas as _ms_reg
                    import clases as _cl_reg
                    ult_sac = float(f_pet.get('ultimo_tick_saciedad') or ahora)
                    ult_int = float(f_pet.get('ultimo_tick_intimidad') or ahora)
                    if 'ultimo_tick_saciedad' not in f_pet:
                        f_pet['ultimo_tick_saciedad'] = ahora
                    if 'ultimo_tick_intimidad' not in f_pet:
                        f_pet['ultimo_tick_intimidad'] = ahora
                    cambio_pet = False
                    avisos_pet = []
                    sac_antes = int(f_pet.get('saciedad', 100))
                    # Cada 60s pierde 1 de Satiation; si ya esta en 0, pierde 1 de Intimacy (piso 40)
                    if (ahora - ult_sac) >= 60.0:
                        f_pet['ultimo_tick_saciedad'] = ahora
                        if sac_antes > 0:
                            f_pet['saciedad'] = max(0, sac_antes - 1)
                            cambio_pet = True
                        else:
                            int_ant = int(f_pet.get('intimidad', 60))
                            if int_ant > 40:
                                f_pet['intimidad'] = max(40, int_ant - 1)
                                avisos_pet.append(_cl_reg.aviso('1', tipo=7, msg_id=965))
                                cambio_pet = True
                    # Cada 180s (3 min) estando con el jugador y con saciedad > 0 GANA +1 de Intimacy
                    if (ahora - ult_int) >= 180.0:
                        f_pet['ultimo_tick_intimidad'] = ahora
                        if int(f_pet.get('saciedad', 0)) > 0:
                            int_ant = int(f_pet.get('intimidad', 60))
                            if int_ant < 100:
                                f_pet['intimidad'] = min(100, int_ant + 1)
                                avisos_pet.append(_cl_reg.aviso('1', tipo=7, msg_id=966))
                                cambio_pet = True
                    if cambio_pet:
                        _r_p = f_pet.get('ranura')
                        pkgs_pet_dec = [_ms_reg.armar(f_pet)]
                        pkgs_pet_dec.extend(avisos_pet)
                        if _r_p is not None:
                            if getattr(p, 'mascotas', None) is not None:
                                p.mascotas[str(_r_p)] = f_pet
                            pkgs_pet_dec.extend(_refrescar(ses, [_r_p]))
                        pet_eid = getattr(ses, 'pet_entity_id', None) or f_pet.get('entidad')
                        sac_ahora = int(f_pet.get('saciedad', 0))
                        if pet_eid:
                            if sac_antes > 100 and sac_ahora <= 100:
                                # Quitar icono de buff 3796 (Pet's Satiation) y actualizar HP efectivo cuando baja a <= 100
                                pkgs_pet_dec.append(struct.pack('<HIBBII', 0x001D, int(pet_eid), 1, 4, 3796, 0))
                                pkgs_pet_dec.append(_cb.atributo(int(pet_eid), _ms_reg.hp_eff(f_pet), _cb.KIND_HP))
                            elif sac_ahora > 100:
                                pkgs_pet_dec.append(struct.pack('<HIBBII', 0x001D, int(pet_eid), 1, 4, 3796, max(60000, (sac_ahora - 100) * 60000)))
                        ses.enviar_inmediato(*pkgs_pet_dec)
                        if getattr(ses, 'usuario', None):
                            cuentas.guardar_mascota(ses.usuario, p.char_id, f_pet, getattr(p, 'mascotas', None))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.debug(f"bucle de regeneracion detenido: {e}")

    async def cliente(self, reader, writer, rol='mundo'):
        addr = writer.get_extra_info('peername')
        self.sesiones += 1
        ses = Session(addr)
        ses.rol = rol
        ses.puerto = self.port if rol == 'login' else self.wport
        ses.writer = writer
        grab = Grabador(addr, self.port if rol == 'login' else self.wport, ses.key)
        ses.grab = grab
        if rol == 'mundo':
            # Para que el comando de GM por consola o por data/gm.txt sepa a
            # quien darle el item: se usa la ultima sesion de mundo que tenga
            # personaje dentro.
            self.mundos.append(ses)
        ses.patrulla_task = asyncio.create_task(self._patrulla_lyceum(ses)) if rol == 'mundo' else None
        ses.regen_task = asyncio.create_task(self._bucle_regeneracion(ses)) if rol == 'mundo' else None
        log.info(f"[{addr}] conectado ({rol})  clave={ses.key.hex(' ')}")
        log.info(f"[{addr}] grabando sesion -> logs/sesiones/{ses.grab.base}_*.bin")
        ses.enviar_hello()
        primero = ses.drenar()
        ses.grab.salida(primero)
        writer.write(primero)
        await writer.drain()
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                grab.entrada(data)
                for opcode, cuerpo in ses.alimentar(data):
                    ses.vistos[opcode] += 1
                    grab.submensaje('c2s', opcode, cuerpo)
                    m, d = ses.parsear(opcode, cuerpo)
                    if m is None:
                        self.desconocidos[opcode] += 1
                        log.debug(f"[{addr}] 0x{opcode:04X} sin esquema "
                                  f"({len(cuerpo)}B): {cuerpo[:24].hex(' ')}")
                    else:
                        log.debug(f"[{addr}] {m.name} {d if d else '(no parsea)'}")
                    # el dispatcher corre igual: un opcode sin esquema puede
                    # necesitar respuesta (la autenticacion es el caso tipico)
                    try:
                        import combate as _cb_at
                        _cb_at.ATACANTE[0] = ses
                        self.manejar(ses, opcode, m, d, addr, cuerpo)
                    except Exception:
                        log.exception(f"[{addr}] error procesando opcode 0x{opcode:04X}")
                salida = ses.drenar()
                if salida:
                    grab.salida(salida)
                    writer.write(salida)
                    await writer.drain()

        except (ConnectionResetError, ConnectionAbortedError, ConnectionError, asyncio.IncompleteReadError, OSError):
            pass
        finally:
            try:
                _casa_tick_limpieza(ses, flush=True)
            except Exception:
                log.exception('casas: error al guardar el tiempo conectado')
            if ses in self.mundos:
                self.mundos.remove(ses)
            try:
                _cerrar_puesto(ses, avisar_dueno=False)
            except Exception:
                pass
            try:
                import presencia as _pres
                _pres.salir(ses)
            except Exception:
                log.exception('presencia: fallo al salir')
            try:
                import casas as _cs_dis, cuentas as _cta_dis, struct as _st_dis, clases as _cl_dis
                if getattr(ses, 'personaje', None):
                    # Si el propio personaje estaba dentro de una casa (stage 500), devolverlo al exterior antes de guardar
                    if ses.personaje.stage == 500:
                        prev = getattr(ses, 'house_return_pos', None)
                        if prev and prev[0] != 500:
                            ses.personaje.stage, (ses.personaje.tile_x, ses.personaje.tile_y) = prev
                        else:
                            _fac = getattr(ses.personaje, 'faccion', None) or getattr(ses.personaje, 'faction', '')
                            _ciudades = {'Aurora': (3, (150, 105)), 'Beasts': (26, (140, 150)), 'Steel': (29, (150, 120)), 'Shadow': (38, (150, 120))}
                            ses.personaje.stage, (ses.personaje.tile_x, ses.personaje.tile_y) = _ciudades.get(_fac, (41, (244, 30)))
                        if getattr(ses, 'usuario', None):
                            _cta_dis.guardar_mapa(ses.usuario, ses.personaje.char_id, ses.personaje.stage, ses.personaje.tile_x, ses.personaje.tile_y)
                            _cta_dis.guardar_posicion(ses.usuario, ses.personaje.char_id, ses.personaje.tile_x, ses.personaje.tile_y)

                    _c_act = _cs_dis.obtener_o_crear_casa(ses.personaje.char_id, ses.personaje.nombre)
                    if _c_act and _c_act.is_open:
                        out_stage = _c_act.outdoor_stage
                        out_eid = _c_act.outdoor_obj_id
                        _cs_dis.retirar_casa_outdoor(_c_act)
                        _c_act.is_open = False
                        ses.personaje.casa = _c_act.serializar()
                        if getattr(ses, 'usuario', None):
                            _cta_dis.guardar_casa(ses.usuario, ses.personaje.char_id, _c_act)
                        # Expulsar de inmediato a cualquier invitado dentro de esta casa para que no quede atrapado
                        for s in list(self.mundos):
                            if s is not ses and getattr(s, 'personaje', None) and getattr(s.personaje, 'stage', None) == 500:
                                if getattr(s, 'casa_visitando', None) is _c_act or getattr(s, 'casa_visitando_owner', None) == ses.personaje.char_id:
                                    try:
                                        _salir_de_casa(s, s.addr)
                                        s.enviar(_cl_dis.aviso("The house owner has logged out. Returned outdoors.", tipo=7, msg_id=_cl_dis.MSG_TEXTO))
                                    except Exception:
                                        pass
                        if out_stage and out_eid:
                            _despawn = _st_dis.pack('<HIB', 0x0007, int(out_eid), 0)
                            for s in list(self.mundos):
                                if s is not ses and getattr(s, 'personaje', None) and getattr(s.personaje, 'stage', None) == out_stage:
                                    try:
                                        s.enviar(_despawn)
                                    except Exception:
                                        pass
            except Exception:
                log.exception('casas: fallo al retirar casa en desconexion')
            try:
                import equipos as _eq
                _eq.salir(ses)
            except Exception:
                log.exception('equipos: fallo al salir del grupo')
            try:
                # Quien va solo y se desconecta pierde su instancia; la de un
                # grupo sigue mientras el grupo exista.
                import eventos_mundo as _evm_x
                _evm_x._CORRIDAS.pop(('solo', int(getattr(ses.personaje, 'char_id', 0) or 0)), None)
                _evm_x._olvidar_corridas_de_grupos_deshechos()
            except Exception:
                pass
            if getattr(ses, 'patrulla_task', None):
                ses.patrulla_task.cancel()
            if getattr(ses, 'regen_task', None):
                ses.regen_task.cancel()
            # Guardar donde quedo el personaje y su progreso/buffs, para que al
            # volver a entrar conserve su posicion, HP/MP, SP y buffs activos.
            if getattr(ses, 'personaje', None) and getattr(ses, 'usuario', None):
                try:
                    p_fin = ses.personaje
                    if p_fin.stage == 500:
                        prev = getattr(ses, 'house_return_pos', None)
                        if prev and prev[0] != 500:
                            p_fin.stage, (p_fin.tile_x, p_fin.tile_y) = prev
                        else:
                            _fac = getattr(p_fin, 'faccion', None) or getattr(p_fin, 'faction', '')
                            _ciudades = {'Aurora': (3, (150, 105)), 'Beasts': (26, (140, 150)), 'Steel': (29, (150, 120)), 'Shadow': (38, (150, 120))}
                            p_fin.stage, (p_fin.tile_x, p_fin.tile_y) = _ciudades.get(_fac, (41, (244, 30)))
                        cuentas.guardar_mapa(ses.usuario, p_fin.char_id, p_fin.stage, p_fin.tile_x, p_fin.tile_y)
                    cuentas.guardar_posicion(ses.usuario, p_fin.char_id,
                                             p_fin.tile_x,
                                             p_fin.tile_y)
                    cuentas.guardar_progreso(ses.usuario, p_fin.char_id,
                                             p_fin.nivel, p_fin.exp,
                                             p_fin.hp, p_fin.mp,
                                             p_fin.habilidades,
                                             hp_max=p_fin.hp_max, mp_max=p_fin.mp_max,
                                             sp=getattr(ses, 'sp', None),
                                             buffs=getattr(p_fin, 'buffs', None))
                    log.info(f"[{addr}] posicion y progreso guardados: "
                             f"({p_fin.tile_x},{p_fin.tile_y})")
                except Exception as e:
                    log.warning(f"[{addr}] no se pudo guardar la posicion: {e}")
            base, nc, ns = grab.cerrar()
            log.info(f"[{addr}] desconectado. opcodes vistos: "
                     f"{dict(ses.vistos.most_common(8))}")
            log.info(f"[{addr}] sesion grabada: {nc} B del cliente, "
                     f"{ns} B del servidor -> logs/sesiones/{base}_*.bin")
            if self.desconocidos:
                log.warning(f"[{addr}] opcodes SIN ESQUEMA que mando el cliente: "
                            f"{ {f'0x{k:04X}': v for k, v in self.desconocidos.items()} }")
            writer.close()

    def _sincronizar_ranura_pet_room(self, ses, org, dst, it):
        """Sincroniza las casillas afectadas del patio de crianza (477..486).

        Se reconstruye desde el inventario ya movido, en vez de aplicar el
        movimiento una segunda vez.  Asi funcionan tambien los swaps entre
        dos casillas del propio panel y una llamada repetida es idempotente.
        """
        p = getattr(ses, 'personaje', None)
        if not p:
            return
        import inventario as _iv_pr, clases as _cl_pr
        _c_pr = _casa_actual(ses)
        if not _c_pr or _c_pr.owner_id != p.char_id:
            return

        cambio = False
        p_mascs = getattr(p, 'mascotas', None)
        if p_mascs is None:
            p.mascotas = {}
            p_mascs = p.mascotas
        afectados = sorted({r for r in (org, dst) if 477 <= r <= 486})
        import mascotas as _ms_init, configuracion as _cfg_init, login as _lg_pr

        for slot in afectados:
            key = str(slot)
            previo = _c_pr.care_pets.get(key) or _c_pr.care_pets.get(slot)
            _c_pr.care_pets.pop(slot, None)  # normaliza claves legacy enteras
            item_actual = (getattr(ses, 'inventario', {}) or {}).get(slot)

            if item_actual is None:
                if previo:
                    _c_pr.care_pets.pop(key, None)
                    cambio = True
                    if p.stage == 500:
                        ses.enviar(struct.pack('<HIB', 0x0007, 8101 + (slot - 477), 0))
                    ses.enviar(_cl_pr.aviso("Retrieved pet from the Pet Room.", tipo=7,
                                            msg_id=_cl_pr.MSG_TEXTO))
                continue

            sp = _iv_pr.sprite_de_mascota(item_actual)
            d_p = _iv_pr.datos_mascota(item_actual)
            pet_id = int(d_p.get('sprite') or 3049)
            nom = _nombre_item(item_actual)
            ficha = p_mascs.get(key) or p_mascs.get(slot)
            if not ficha:
                ficha = _ms_init.recien_nacida(
                    d_p.get('nombre') or nom, pet_id,
                    nivel=max(1, getattr(_cfg_init, 'MASCOTA_NIVEL_INICIAL', 1)),
                    estrellas=max(1, int(d_p.get('estrellas') or 1)))
            ficha['ranura'] = slot
            ficha['item'] = item_actual
            ficha['instancia'] = 1000 + slot
            ficha['fuera'] = False
            sp_cur = int(ficha.get('sprite') or 0)
            if sp_cur <= 0 or sp_cur >= 35001:
                ficha['sprite'] = pet_id
            if not ficha.get('tipo') or ficha.get('tipo') == 44069:
                ficha['tipo'] = sp
            if ficha.get('nombre'):
                nom = ficha['nombre']
            p_mascs.pop(slot, None)
            p_mascs[key] = ficha

            mismo = bool(previo and int(previo.get('item_id') or 0) == int(item_actual)
                         and previo.get('name') == nom
                         and int(previo.get('sprite') or 0) == int(sp))
            tile = list((previo or {}).get('tile') or [36, 28])
            _c_pr.care_pets[key] = {
                'item_id': item_actual, 'name': nom, 'sprite': sp,
                'slot': slot, 'time': int((previo or {}).get('time') or time.time()),
                'tile': tile,
            }
            if not mismo:
                cambio = True
                if p.stage == 500:
                    pet_eid = 8101 + (slot - 477)
                    if previo:
                        ses.enviar(struct.pack('<HIB', 0x0007, pet_eid, 0))
                    ses.enviar(_lg_pr._npc_spawn(
                        pet_eid, 1, nom, (tile[0], tile[1]),
                        sprite=sp, klass=200, direccion=6))
                ses.enviar(_cl_pr.aviso(
                    f"{nom} is now resting and training in the Pet Room!",
                    tipo=7, msg_id=_cl_pr.MSG_TEXTO))
            if getattr(ses, 'usuario', None):
                cuentas.guardar_mascota(ses.usuario, p.char_id, ficha, p_mascs)

        if cambio:
            p.casa = _c_pr.serializar()
            if getattr(ses, 'usuario', None):
                cuentas.guardar_casa(ses.usuario, p.char_id, _c_pr)

    def _procesar_chat_mundo(self, ses, texto, addr, portrait_selector=None):
        """Procesa chat local, canales globales (Broadcast, Trade, Super Broadcast) con consumo de items y formato de color."""
        p = getattr(ses, 'personaje', None)
        if not p or not texto:
            return
        import clases as _cl
        txt_lower = texto.lower()

        # 1. Super Broadcast (% o /sb o /super, o ventana 0x0128 canal 11)
        es_sb = False
        msg_sb = ''
        if texto.startswith('%'):
            es_sb = True
            msg_sb = texto[1:].strip()
        elif txt_lower.startswith(('/sb ', '/super ')):
            es_sb = True
            msg_sb = texto.split(' ', 1)[1].strip()

        if es_sb:
            if not msg_sb:
                return
            max_r = _tope_bolsa(getattr(ses, 'inventario', {}))
            slot_sb = next((s for s, it in ses.inventario.items() if 20 <= s <= max_r and int(it) in (2003, 8658, 79739)), None)
            if slot_sb is None:
                ses.enviar(_cl.aviso("You need Super Broadcasting to send messages in this channel.", tipo=7, msg_id=_cl.MSG_TEXTO))
                return
            _sacar(ses, slot_sb, 1)
            ses.enviar(*_refrescar(ses, [slot_sb]))
            _guardar_bolsa(ses, p.char_id)
            if portrait_selector is None:
                _appearance = getattr(p, 'apariencia', None) or [0]
                _portrait_selector = int(_appearance[0]) & 1 if _appearance else 0
            else:
                _portrait_selector = int(portrait_selector) & 1
            # Official global packets carry entity 0; the visual selector,
            # not a possibly unrelated map entity, chooses the portrait.
            anuncio = _cl.chat_super_broadcast(
                0, p.nombre, msg_sb, _portrait_selector)
            for s in list(self.mundos):
                if getattr(s, 'personaje', None):
                    s.enviar(anuncio)
            log.info('[%s] %s [Super Broadcast]: %s', addr, p.nombre, msg_sb)
            return

        # 2. Public / Broadcast Channel (! o & o /b o /broadcast o /shout)
        es_bc = False
        msg_bc = ''
        if texto.startswith(('!', '&')):
            es_bc = True
            msg_bc = texto[1:].strip()
        elif txt_lower.startswith(('/b ', '/broadcast ', '/shout ')):
            es_bc = True
            msg_bc = texto.split(' ', 1)[1].strip()

        if es_bc:
            if not msg_bc:
                return
            max_r = _tope_bolsa(getattr(ses, 'inventario', {}))
            slot_bc = next((s for s, it in ses.inventario.items() if 20 <= s <= max_r and int(it) in (2002, 79738)), None)
            if slot_bc is None:
                ses.enviar(_cl.aviso("You need Broadcasting to send messages in this channel.", tipo=7, msg_id=_cl.MSG_TEXTO))
                return
            _sacar(ses, slot_bc, 1)
            ses.enviar(*_refrescar(ses, [slot_bc]))
            _guardar_bolsa(ses, p.char_id)
            anuncio = _cl.chat_broadcast(0, p.nombre, msg_bc)
            for s in list(self.mundos):
                if getattr(s, 'personaje', None):
                    s.enviar(anuncio)
            log.info('[%s] %s [Broadcast]: %s', addr, p.nombre, msg_bc)
            return

        # 3. Trade Channel ($ o @ o /trade o /t)
        es_tr = False
        msg_tr = ''
        if texto.startswith(('$', '@')):
            es_tr = True
            msg_tr = texto[1:].strip()
        elif txt_lower.startswith(('/trade ', '/t ')):
            es_tr = True
            msg_tr = texto.split(' ', 1)[1].strip()

        if es_tr:
            if not msg_tr:
                return
            max_r = _tope_bolsa(getattr(ses, 'inventario', {}))
            slot_tr = next((s for s, it in ses.inventario.items() if 20 <= s <= max_r and int(it) in (2002, 79738)), None)
            if slot_tr is None:
                ses.enviar(_cl.aviso("You need Broadcasting to send messages in the Trade channel.", tipo=7, msg_id=_cl.MSG_TEXTO))
                return
            _sacar(ses, slot_tr, 1)
            ses.enviar(*_refrescar(ses, [slot_tr]))
            _guardar_bolsa(ses, p.char_id)
            anuncio = _cl.chat_trade(0, p.nombre, msg_tr)
            for s in list(self.mundos):
                if getattr(s, 'personaje', None):
                    s.enviar(anuncio)
            log.info('[%s] %s [Trade]: %s', addr, p.nombre, msg_tr)
            return

        # 4. Chat normal / local
        _hablar_jugador(ses, texto)
        if p.stage == 500:
            for s in list(self.mundos):
                if s is not ses and getattr(s, 'personaje', None) and s.personaje.stage == 500:
                    if getattr(s, 'casa_visitando', None) is getattr(ses, 'casa_visitando', None):
                        s.enviar(_decir(p.entity_id, p.nombre, texto))
        log.info('[%s] %s dice: %s', addr, p.nombre, texto[:120])

    def _activar_baile_casa(self, ses, ticket_id, ranura=None):
        """Activa una fiesta/baile de casa con anuncios, cuenta atras y premios."""
        import casas as _cs, clases as _cl, cuentas as _cta
        p = getattr(ses, 'personaje', None)
        if not p:
            return
        _c = _cs.obtener_o_crear_casa(p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
        if p.stage != _cs.STAGE_HOUSE and not _c.is_open:
            ses.enviar(_cl.aviso("Ball Tickets can only be used inside your house or when displayed outdoors.", tipo=7, msg_id=_cl.MSG_TEXTO))
            return
        now = int(time.time())
        if _c.ball_active:
            ses.enviar(_cl.aviso("A house ball is already active!", tipo=7, msg_id=_cl.MSG_TEXTO))
            return
        if now < _c.ball_cooldown_until:
            rem_s = _c.ball_cooldown_until - now
            if rem_s > 3600:
                rem_str = f"{max(1, int(rem_s / 3600))}h"
            elif rem_s > 60:
                rem_str = f"{max(1, int(rem_s / 60))}m"
            else:
                rem_str = f"{rem_s}s"
            ses.enviar(_cl.aviso(f"Ball cooldown active ({rem_str} remaining).", tipo=7, msg_id=_cl.MSG_TEXTO))
            return
        if not _c.iniciar_baile(ticket_id, now=now):
            ses.enviar(_cl.aviso("Unable to start house ball.", tipo=7, msg_id=_cl.MSG_TEXTO))
            return
        if ranura is not None and ranura in ses.inventario:
            _sacar(ses, ranura, 1)
            ses.enviar(*_refrescar(ses, [ranura]))
            _guardar_bolsa(ses, p.char_id)
        p.casa = _c.serializar()
        if getattr(ses, 'usuario', None):
            _cta.guardar_casa(ses.usuario, p.char_id, _c)

        import configuracion as _cfg_bl
        prep_s = int(getattr(_cfg_bl, 'TIEMPO_PREPARACION_BAILE_SEGUNDOS', 10))
        t_str = f"{prep_s} seconds" if prep_s < 60 else f"{prep_s // 60} minutes"
        h_x, h_y = (_c.outdoor_px[0] // 32, _c.outdoor_px[1] // 32) if _c.is_open else (42, 80)
        anuncio = f"There will be a ball in {p.nombre}({h_x},{h_y})'s house after {t_str}. All players are welcome to join the ball."
        for s in list(self.mundos):
            if getattr(s, 'personaje', None):
                s.enviar(
                    _cl.aviso(f"/c#FFD700[House Ball] {anuncio}/c*", tipo=7, msg_id=_cl.MSG_TEXTO)
                )
        asyncio.create_task(self._secuencia_baile(ses, _c, p.nombre, h_x, h_y, prep_s))

    def _participantes_casa(self, c_obj, ses_host):
        """Devuelve las sesiones de jugadores presentes en la casa o anfitrion."""
        participantes = []
        for s in list(self.mundos):
            p = getattr(s, 'personaje', None)
            if not p:
                continue
            if s is ses_host:
                participantes.append(s)
                continue
            if p.stage == 500:
                c_vis = getattr(s, 'casa_visitando', None)
                if c_vis is None or getattr(c_vis, 'owner_id', None) == c_obj.owner_id:
                    participantes.append(s)
        return participantes

    async def _secuencia_baile(self, ses_host, c_obj, host_name, h_x, h_y, prep_s=10):
        """Secuencia temporizada de la fiesta: avisos, cuenta atras y recompensas."""
        import clases as _cl, combate as _cb, cuentas, random as _rnd, configuracion as _cfg_b
        # Espera previa hasta los ultimos 30 segundos
        if prep_s > 30:
            if prep_s >= 180:
                await asyncio.sleep(60)
                if not c_obj.ball_active:
                    return
                msg2m = f"{host_name}'s ball will start in 2 minutes."
                for s in list(self.mundos):
                    if getattr(s, 'personaje', None):
                        s.enviar(_cl.aviso(msg2m, tipo=7, msg_id=_cl.MSG_TEXTO))

                await asyncio.sleep(60)
                if not c_obj.ball_active:
                    return
                msg1m = f"{host_name}'s ball will start in 1 minute."
                for s in list(self.mundos):
                    if getattr(s, 'personaje', None):
                        s.enviar(_cl.aviso(msg1m, tipo=7, msg_id=_cl.MSG_TEXTO))

                await asyncio.sleep(30)
            else:
                await asyncio.sleep(max(0, prep_s - 30))
            if not c_obj.ball_active:
                return

        # Contador visual rojito (0x01af) de los ultimos 30 segundos (estilo Magic Kitchen Path)
        segundos_cd = min(30, max(1, prep_s))
        for sec in range(segundos_cd, 0, -1):
            if not c_obj.ball_active:
                pkt_hide = struct.pack('<HBII', 0x01af, 0, 0, 0)
                for s in self._participantes_casa(c_obj, ses_host):
                    s.enviar(pkt_hide)
                return
            pkt_tick = struct.pack('<HBII', 0x01af, 1, 0, sec)
            for s in self._participantes_casa(c_obj, ses_host):
                s.enviar(pkt_tick)
            await asyncio.sleep(1)

        # Ocultar contador al llegar a 0
        pkt_hide = struct.pack('<HBII', 0x01af, 0, 0, 0)
        for s in self._participantes_casa(c_obj, ses_host):
            s.enviar(pkt_hide)

        if not c_obj.ball_active:
            return

        # Comienza el baile
        start_msg = "The ball is starting now! Enjoy!"
        candy_ids = list(range(10569, 10581))
        participantes = self._participantes_casa(c_obj, ses_host)
        for s in participantes:
            p = getattr(s, 'personaje', None)
            if not p:
                continue
            s.enviar(
                _cl.aviso(f"/c#FFD700[House Ball] {start_msg}/c*", tipo=7, msg_id=_cl.MSG_TEXTO)
            )
            # Party Candy para anfitrion y visitantes en la casa
            candy_choice = _rnd.choice(candy_ids)
            slot_dest = _meter(s, candy_choice, 1)
            if slot_dest is not None:
                s.enviar(
                    _cl.aviso(f"Received {_nombre_item(candy_choice)}!", tipo=7, msg_id=_cl.MSG_TEXTO),
                    *_refrescar(s, [slot_dest])
                )
                _guardar_bolsa(s, p.char_id)

            # Bono de EXP o Skill EXP SOLO para el anfitrion que tiro la ball
            if s is ses_host and c_obj.ball_mult > 1.0:
                salida_host = []
                if getattr(c_obj, 'ball_type', 1) == 2:
                    mult = getattr(c_obj, 'ball_mult', 1.5)
                    base_sk = max(10, int(p.nivel * 5 * mult))
                    skills_arma = _cl.skills_de_equipo(getattr(ses_host, 'inventario', None))
                    candidatas = _cl.skills_que_suben('melee', skills_arma) | _cl.skills_que_suben('magia', skills_arma) | _cl.skills_que_suben('distancia', skills_arma)
                    nuevas_h = []
                    for h in (p.habilidades or []):
                        sid, slv, sexp = h[0], h[1], h[2]
                        if sid in candidatas or not candidatas:
                            sexp += base_sk
                            req = max(1, _cl.exp_requerida_skill(slv, sid))
                            while sexp >= req and slv < p.nivel:
                                sexp -= req
                                slv += 1
                                req = max(1, _cl.exp_requerida_skill(slv, sid))
                                salida_host.append(_cb.efecto_level_up(p.entity_id, es_skill=True))
                                salida_host.append(_cl.aviso_doble(_cl.MSG_SKILL_SUBE, _cl.nombre(sid)))
                            salida_host.append(_cl.aviso_doble(_cl.MSG_SKILL_EXP, _cl.nombre(sid), str(base_sk)))
                        nuevas_h.append((sid, slv, sexp))
                    p.habilidades = nuevas_h
                    if getattr(ses_host, 'usuario', None):
                        cuentas.guardar_habilidades(ses_host.usuario, p.char_id, p.habilidades)
                    salida_host.append(_cl.arbol_habilidades(p.char_id, p.habilidades))
                else:
                    exp_bonus = int(p.nivel * 500 * c_obj.ball_mult)
                    _subir_exp(s, exp_bonus, salida_host)
                if salida_host:
                    s.enviar(*salida_host)

        # Duracion del baile activo
        dur_baile = int(getattr(_cfg_b, 'DURACION_BAILE_SEGUNDOS', 60))
        await asyncio.sleep(dur_baile)

        # Termina el baile: aviso NORMAL solo para los que estan dentro de la casa / anfitrion
        c_obj.ball_active = False
        c_obj.ball_end_time = int(time.time())
        msg_fin = "[House Ball] The ball has ended! Thank you for participating."
        for s in self._participantes_casa(c_obj, ses_host):
            s.enviar(_cl.aviso(msg_fin, tipo=7, msg_id=_cl.MSG_TEXTO))
        p_host = getattr(ses_host, 'personaje', None)
        if p_host and getattr(ses_host, 'usuario', None):
            p_host.casa = c_obj.serializar()
            cuentas.guardar_casa(ses_host.usuario, p_host.char_id, c_obj)

    def manejar(self, ses, opcode, m, d, addr, cuerpo=b''):
        """Login: responde MOTD + personajes + redirect. Mundo: entra al juego."""
        # COMANDO DE GM.
        # Requiere la barra '/' para no interceptar palabras de chat normales (como 'item').
        # Con barra el cliente AO envia 0x0001 (sin la barra). En 0x000E se exige que empiece con '/'.
        _es_cmd_gm = False
        if ses.rol == 'mundo' and getattr(ses, 'personaje', None):
            if opcode == 0x0001:
                _es_cmd_gm = True
            elif opcode == 0x000E and cuerpo and cuerpo.lstrip(b' \t\r\n').startswith(b'/'):
                _es_cmd_gm = True
        if _es_cmd_gm and _probar_gm(ses, cuerpo, addr):
            return

        # Si el comando con barra no era de GM, pasarlo a procesar como comando de chat (/sb, /b, /trade, etc.)
        if opcode == 0x0001 and ses.rol == 'mundo' and getattr(ses, 'personaje', None) and cuerpo:
            _txt_cmd = cuerpo.split(b'\x00', 1)[0].decode('latin-1', 'replace').strip()
            if _txt_cmd:
                self._procesar_chat_mundo(ses, '/' + _txt_cmd, addr)
            return

        # Canales de chat globales (0x0128: Public=2, Trade=10 con Broadcasting 2002; Super BC=11 con Super Broadcasting 2003/8658)
        if opcode == 0x0128 and ses.rol == 'mundo' and getattr(ses, 'personaje', None) and cuerpo:
            canal = cuerpo[4] if len(cuerpo) > 4 else 0
            txt = cuerpo[5:].split(b'\x00', 1)[0].decode('latin-1', 'replace').strip() if len(cuerpo) > 5 else ''
            if txt:
                if canal in (11, 13, 15, 16):
                    portrait_sel = None
                    if len(txt) >= 2 and txt[0] in ('0', '1'):
                        portrait_sel = int(txt[0])
                        txt = txt[1:].strip()
                    if txt:
                        if portrait_sel is not None:
                            self._procesar_chat_mundo(ses, '%' + txt, addr, portrait_selector=portrait_sel)
                        else:
                            self._procesar_chat_mundo(ses, '%' + txt, addr)
                elif canal == 10:
                    self._procesar_chat_mundo(ses, '$' + txt, addr)
                elif canal == 2:
                    self._procesar_chat_mundo(ses, '!' + txt, addr)
                else:
                    self._procesar_chat_mundo(ses, txt, addr)
            return

        # Canales de grupo/liga/matrimonio (0x0126: League=4, Team=5, Marriage=14 — NO gastan Broadcasting)
        if opcode == 0x0126 and ses.rol == 'mundo' and getattr(ses, 'personaje', None) and cuerpo:
            import clases as _cl_priv
            p = ses.personaje
            canal = cuerpo[4] if len(cuerpo) > 4 else 0
            txt = ''
            if len(cuerpo) > 9:
                txt = cuerpo[9:].split(b'\x00', 1)[0].decode('latin-1', 'replace').strip()
            if not txt and len(cuerpo) > 5:
                txt = cuerpo[5:].split(b'\x00', 1)[0].decode('latin-1', 'replace').strip()
            if txt:
                if canal == 5:
                    pkt = _cl_priv.chat_team(getattr(p, 'entity_id', 0) or 0, p.nombre, txt)
                    destinos = {ses}
                    for comp in _companeros(ses):
                        if getattr(comp, 'personaje', None):
                            destinos.add(comp)
                    for s in destinos:
                        s.enviar(pkt)
                    log.info('[%s] %s [Team]: %s', addr, p.nombre, txt)
                elif canal == 4:
                    pkt = _cl_priv.chat_league(getattr(p, 'entity_id', 0) or 0, p.nombre, txt)
                    for s in list(self.mundos):
                        if getattr(s, 'personaje', None):
                            s.enviar(pkt)
                    if ses not in self.mundos:
                        ses.enviar(pkt)
                    log.info('[%s] %s [League]: %s', addr, p.nombre, txt)
                elif canal == 14:
                    pkt = _cl_priv.chat_marriage(getattr(p, 'entity_id', 0) or 0, p.nombre, txt)
                    for s in list(self.mundos):
                        if getattr(s, 'personaje', None):
                            s.enviar(pkt)
                    if ses not in self.mundos:
                        ses.enviar(pkt)
                    log.info('[%s] %s [Marriage]: %s', addr, p.nombre, txt)
                elif canal == 10:
                    self._procesar_chat_mundo(ses, '$' + txt, addr)
                elif canal == 2:
                    self._procesar_chat_mundo(ses, '!' + txt, addr)
                else:
                    self._procesar_chat_mundo(ses, txt, addr)
            return

        # Canal Battle / Jabaly (0x0133 -> S2C 0x0139 — NO gasta Broadcasting)
        if opcode == 0x0133 and ses.rol == 'mundo' and getattr(ses, 'personaje', None) and cuerpo:
            import clases as _cl_bat
            p = ses.personaje
            txt = cuerpo.split(b'\x00', 1)[0].decode('latin-1', 'replace').strip()
            if txt:
                pkt = _cl_bat.chat_battle(p.nombre, txt)
                for s in list(self.mundos):
                    if getattr(s, 'personaje', None):
                        s.enviar(pkt)
                if ses not in self.mundos:
                    ses.enviar(pkt)
                log.info('[%s] %s [Battle]: %s', addr, p.nombre, txt)
            return

        # Susurro privado / Whisper (0x0127 -> S2C 0x0127 — NO gasta Broadcasting)
        if opcode == 0x0127 and ses.rol == 'mundo' and getattr(ses, 'personaje', None) and len(cuerpo) > 23:
            import clases as _cl_wh
            p = ses.personaje
            receptor = cuerpo[4:21].split(b'\x00', 1)[0].decode('latin-1', 'replace').strip()
            txt = cuerpo[23:].split(b'\x00', 1)[0].decode('latin-1', 'replace').strip()
            if receptor and txt:
                dest_ses = next(
                    (s for s in list(self.mundos)
                     if getattr(s, 'personaje', None)
                     and s.personaje.nombre.lower() == receptor.lower()),
                    None
                )
                if dest_ses is None and p.nombre.lower() == receptor.lower():
                    dest_ses = ses
                if dest_ses is not None:
                    pkt = _cl_wh.chat_whisper(p.nombre, dest_ses.personaje.nombre, txt, err_code=0)
                    ses.enviar(pkt)
                    if dest_ses is not ses:
                        dest_ses.enviar(pkt)
                else:
                    ses.enviar(_cl_wh.chat_whisper(p.nombre, receptor, txt, err_code=1))
                log.info('[%s] %s -> %s [Whisper]: %s', addr, p.nombre, receptor, txt)
            return

        # EL CHAT. Lo que se escribe sin barra llega como c2s 0x000E: el texto y un NUL.
        if opcode == 0x000E and ses.rol == 'mundo' and getattr(ses, 'personaje', None) and cuerpo:
            _txt_chat = cuerpo.split(b'\x00', 1)[0].decode('latin-1', 'replace').strip()
            if _txt_chat:
                self._procesar_chat_mundo(ses, _txt_chat, addr)
            return
        if opcode == 0x0002 and ses.rol == 'login':
            usuario = login_server.usuario_de_auth(cuerpo)
            ses.usuario = usuario
            cuentas.guardar_muestra_auth(cuerpo, f"usuario='{usuario}' desde {addr}")
            cuenta, motivo = cuentas.validar(usuario, cuerpo)
            if cuenta is None:
                log.warning(f"[{addr}] LOGIN RECHAZADO usuario='{usuario}': {motivo}")
                codigo_error = (
                    login_server.ERROR_PASSWORD_INCORRECTA
                    if 'contrasena incorrecta' in motivo
                    else login_server.ERROR_GENERICO
                )
                ses.enviar_crudo(login_server.respuesta_error(codigo_error))
                return
            log.info(f"[{addr}] LOGIN usuario='{usuario}' aceptado ({motivo})")
            # Solo lo que este guardado de verdad. Nada inventado.
            lista = list(cuenta.get('personajes', []))[:3]
            import os as _o
            # Ajustables para bisecar: los tres unicos campos que todavia
            _ran = int(_o.environ.get('AO_RANURAS', 3))
            _sub = int(_o.environ.get('AO_SUBCANAL', 2))
            _fac = _o.environ.get('AO_FACCION')
            _cls = _o.environ.get('AO_CLASE')
            # El cliente se CONGELA sin intentar ninguna conexion, asi que el
            # bloqueo es local -- muy probablemente la carga del mapa. Con
            # AO_MAPA se puede probar otro stage_id sin recrear el personaje.
            _mapa = _o.environ.get('AO_MAPA')
            if _mapa is not None:
                for _p in lista:
                    _p['stage_id'] = int(_mapa)
            if _fac is not None:
                for _p in lista:
                    _p['faction'] = _fac
            if _cls is not None:
                for _p in lista:
                    _p['class_id'] = int(_cls)
            if _o.environ.get('AO_BLOQUE_REAL'):
                # Manda el bloque de cuenta CAPTURADO tal cual, sin generar
                # nada. Si con los bytes literales de un servidor que
                # funcionaba el cliente tampoco entra, el bloque queda
                # descartado de forma concluyente.
                import struct as _s
                _b = (pathlib.Path(__file__).parent / 'plantillas'
                      / 'login_bloque_real.bin').read_bytes()
                ses.enviar_crudo(_s.pack('<HH', len(_b) + 2, 0x0000) + _b)
                log.warning(f"[{addr}] usando el BLOQUE REAL capturado "
                            f"({len(_b)} B), no el generado")
            else:
                ses.enviar_crudo(login_server.respuesta_login(
                    lista, cuenta=usuario, ranuras=_ran, subcanal=_sub))
            log.info(f"[{addr}] ranuras={_ran} subcanal={_sub} "
                     f"faccion={_fac or 'la del pj'} mapa={_mapa or 'el del pj'}")
            log.info(f"[{addr}] ranuras: {len(lista)} con personaje, "
                     f"{3 - len(lista)} libres")
            import os as _os
            # Diagnostico: con AO_REDIRECT_AL_LOGIN=1 el redirect apunta al
            # MISMO puerto del login. Si aparece una SEGUNDA conexion, el
            # cliente si actua sobre el redirect y el problema esta en la
            # sesion de mundo. Si no aparece, lo esta ignorando.
            # El redirect NO va aca. Se manda como respuesta a 0x0006, que es
            # el pedido de ENTRAR AL MUNDO. Mandarlo apenas llega el AUTH hace
            # que el cliente lo reciba antes de pedir entrar, lo descarte, y
            # despues quede esperando una respuesta que nunca llega -- que es
            # exactamente el congelamiento que veniamos persiguiendo.
            log.info(f"[{addr}] lista enviada; esperando 0x0006 para entrar")
            # NO cerrar la conexion de login aca. Se probo y el cliente
            # muestra "The connection with the server has been interrupted":
            # trata el cierre como caida. La nota del proyecto anterior sobre
            # "cerrar el socket de login" describia un cierre PREMATURO como
            # causa de aborto, no un cierre necesario. Mal interpretada.
            return

        if opcode == 0x0003 and ses.rol == 'login':
            import personajes, pathlib as _pl
            d = personajes.parsear_creacion(cuerpo)
            if not d['nombre']:
                log.warning(f"[{addr}] CREAR: nombre vacio, se ignora")
                return
            cta = cuentas.cargar()['cuentas'].get(ses.usuario) or {'personajes': []}
            usados = {x.get('char_id', 0) for x in cta.get('personajes', [])}
            nuevo = personajes.personaje_nuevo(
                d['nombre'], d['ranura'], max(usados or [1000]) + 1,
                elegidos=d.get('elegidos'))
            log.info(f"[{addr}] CREAR: elegido (bytes +1..+5) = "
                     f"{bytes(d.get('elegidos') or []).hex(' ')} -> "
                     f"apariencia={nuevo['apariencia']}")
            personajes.guardar(ses.usuario, nuevo, cuentas.ARCHIVO)
            ses.enviar(personajes.respuesta_creacion(d['ranura'], nuevo))
            log.info(f"[{addr}] PERSONAJE CREADO '{nuevo['nombre']}' "
                     f"ranura={d['ranura']} id={nuevo['char_id']} "
                     f"nivel={nuevo['nivel']} mapa={nuevo['stage_id']} -> guardado")
            return

        if opcode == 0x0004 and ses.rol == 'login':
            # BORRAR PERSONAJE. Medido en Celestia (login_032338_580015):
            #   C2S 0x0004  [u8 unk][PIN de 33 bytes]
            #   S2C 0x0002  [2 bytes][LE32 char_id]
            #   y la lista de personajes otra vez
            # Alli el borrado queda en espera ocho horas (28799 s en la
            # lista); aqui se borra en el acto, que es lo util para probar.
            import login_server as _ls
            ranura = cuerpo[0] if cuerpo else 0
            char_id = cuentas.borrar_personaje(ses.usuario, ranura)
            if char_id is None:
                # Se contesta igual con la lista: sin respuesta el cliente
                # se queda esperando con la pantalla en negro.
                log.warning(f"[{addr}] BORRAR: no hay personaje en la ranura {ranura}")
            else:
                ses.enviar(struct.pack('<HHI', 0x0002, 0, char_id))
            ses.enviar_crudo(_ls.respuesta_login(
                cuentas.lista_de_personajes(ses.usuario)[:3], cuenta=ses.usuario))
            if char_id is not None:
                log.info(f"[{addr}] PERSONAJE BORRADO: ranura {ranura} "
                         f"char_id {char_id} (sin espera)")
            return

        if opcode == 0x0006 and ses.rol == 'login':
            # ENTRAR AL MUNDO. El cuerpo trae la ruta del sprite del personaje
            # elegido, por ejemplo "\chr\i263g\20263_Wait.spr".
            import os as _o2
            _pt = self.port if _o2.environ.get('AO_REDIRECT_AL_LOGIN') else self.wport
            ranura = cuerpo[0] if cuerpo else 0
            txt = bytes(c if 32 <= c < 127 else 46 for c in cuerpo[:40]).decode()
            cta = cuentas.cargar()['cuentas'].get(ses.usuario) or {}
            nombre = next((x['nombre'] for x in cta.get('personajes', [])
                           if x.get('ranura') == ranura), '?')
            self.pendientes[addr[0]] = (ses.usuario, ranura)
            log.info(f"[{addr}] ENTRAR AL MUNDO ranura={ranura} -> '{nombre}'")
            log.info(f"[{addr}] 0x0006 sprite: {txt}")
            ses.enviar(login_server.redirect(self.host, _pt))
            log.info(f"[{addr}] redirigido a {self.host}:{_pt}")
            return

        if opcode == 0x0002 and not ses.entity_id:
            # El cliente se autentico. Entra al mundo.
            # No se validan credenciales: el bloque de 16 B no esta descifrado.
            # Se guarda el AUTH crudo para poder deducir su formato despues.
            if d and d.get('credenciales'):
                cuentas.guardar_muestra_auth(d['credenciales'], f"desde {addr}")
            usuario, ranura = self.pendientes.get(addr[0], (None, 0))
            if usuario is None:
                log.warning(f"[{addr}] conexion de mundo sin 0x0006 previo; "
                            f"no se sabe que personaje cargar")
                return
            cuenta = cuentas.cargar()['cuentas'].get(usuario) or {}
            p = cuentas.personaje_de(cuenta, ranura)
            # La sesion de MUNDO es otra conexion TCP: no paso por el handler
            # de login, asi que no tiene ses.usuario. Sin esto, guardar el
            # inventario fallaba en silencio y todo volvia a su sitio al
            # reconectar.
            ses.usuario = usuario
            if p is None:
                log.warning(f"[{addr}] la ranura {ranura} de '{usuario}' "
                            f"esta vacia")
                return
            ses.entity_id = p.entity_id
            ses.personaje = p
            for sub in secuencia(p):
                ses.enviar(sub)
            # El inventario va dentro de la secuencia de entrada: el 0x001A
            # se arma con el del personaje, asi que cada item ya sale en su
            # ranura y no hay que corregir nada despues.
            import inventario as inv
            # La MISMA referencia, no una copia: con dict(p.inventario) se
            # trabajaba sobre una copia y al recargar el mapa la secuencia
            # volvia a leer p.inventario, que seguia sin los items entregados.
            # De ahi que los regalos solo aparecieran al reconectar.
            ses.inventario = p.inventario
            ses.cantidades = p.cantidades
            ses.oro = p.oro
            ses.monstruos = _monstruos_de(p.stage)
            try:
                _entrar_en_sala(ses, addr)
            except Exception:
                log.exception('no se pudo entrar en la sala del mapa al conectar')
            bars, max_pts = _max_sp_info(p)
            # Ver arriba: empieza a cero, no al maximo.
            # El SP viene del personaje guardado. Empieza a cero solo la
            # primera vez: se gana peleando y se conserva al salir.
            ses.sp = getattr(ses, 'sp', None)
            if ses.sp is None:
                ses.sp = max(0, int(getattr(p, 'sp', 0) or 0))
            ses.enviar(inv.stats(ses.inventario, p.habilidades,
                                 hp=p.hp, hp_max=p.hp_max,
                                 mp=p.mp, mp_max=p.mp_max,
                                 oro=p.oro, buffs=getattr(p, 'buffs', None),
                                 sp=ses.sp, sp_max=bars,
                                 mejoras=_mejoras_de(ses)))
            import combate as _cb
            ses.enviar(_cb.atributo(p.entity_id, ses.sp, _cb.KIND_SP))
            if getattr(p, 'buffs', None):
                _now_b = time.time()
                for _b_id, _b_data in list(p.buffs.items()):
                    if isinstance(_b_data, dict):
                        _rem_s = _b_data.get('fin', 0) - _now_b
                        if _rem_s > 0:
                            ses.enviar(struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 4, int(_b_id), int(_rem_s * 1000)))
                            if _b_data.get('es_transform') and (_b_data.get('trans_sprite') or _b_data.get('mag', {}).get('trans_sprite')):
                                _ts = _b_data.get('trans_sprite') or _b_data.get('mag', {}).get('trans_sprite')
                                ses.enviar(_cb.atributo(p.entity_id, _ts, _cb.KIND_TRANSFORM))
                        else:
                            p.buffs.pop(_b_id, None)

            # Expiracion de tarjeta de puesto (Stall Card) temporal activa:
            if getattr(p, 'expiracion_puesto', 0) > 0:
                _rem_puesto = p.expiracion_puesto - time.time()
                if _rem_puesto <= 0:
                    if inv.RANURA_PUESTO in ses.inventario:
                        del ses.inventario[inv.RANURA_PUESTO]
                        _cantidades(ses).pop(inv.RANURA_PUESTO, None)
                    p.expiracion_puesto = 0.0
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_inventario(ses.usuario, p.char_id, ses.inventario,
                                                   _cantidades(ses), expiracion_puesto=0.0)
                else:
                    def _expirar_tarjeta_login(ses_ref=ses, exp_ts=p.expiracion_puesto):
                        if (getattr(ses_ref, 'personaje', None) and
                            getattr(ses_ref.personaje, 'expiracion_puesto', 0) == exp_ts and
                            inv.RANURA_PUESTO in getattr(ses_ref, 'inventario', {})):
                            del ses_ref.inventario[inv.RANURA_PUESTO]
                            _cantidades(ses_ref).pop(inv.RANURA_PUESTO, None)
                            ses_ref.personaje.expiracion_puesto = 0.0
                            import clases as _c
                            ses_ref.enviar(_c.aviso("Your Stall Card has expired.", tipo=7, msg_id=_c.MSG_TEXTO),
                                           *_refrescar(ses_ref, [inv.RANURA_PUESTO]))
                            if getattr(ses_ref, 'usuario', None):
                                cuentas.guardar_inventario(ses_ref.usuario, ses_ref.personaje.char_id,
                                                           ses_ref.inventario, _cantidades(ses_ref),
                                                           expiracion_puesto=0.0)
                    asyncio.get_event_loop().call_later(_rem_puesto, _expirar_tarjeta_login)
            # Creditos de rango. Van en su propio 0x0013, igual que los manda
            # el servidor real al usar un objeto que los sube. El rango de la
            # ficha lo decide el cliente a partir de este total.
            import configuracion as _cf
            _cred = p.creditos or getattr(_cf, 'CREDITOS_INICIALES', 0)
            # El rango va en la ficha, no en un atributo: se fija ANTES de
            # armar la secuencia, en login._ficha(). Aqui solo se asegura de
            # que el personaje lo lleve puesto.
            if not getattr(p, 'rango', 0):
                p.rango = getattr(_cf, 'RANGO_INICIAL', 1)
            ses.enviar(_cb.atributo(p.entity_id, p.rango, _cb.KIND_RANGO))
            if _cred:
                p.creditos = _cred
                ses.enviar(_cb.atributo(p.entity_id, _cred, _cb.KIND_CREDITO))
            # El arbol de habilidades tambien al entrar, no solo al elegir
            # clase: si no, al reconectar el panel vuelve a salir lleno de
            # interrogantes.
            if p.habilidades:
                import clases as _cl
                # Las ranuras de rama que ya le tocan por nivel (301, 351 y
                # 401) y todavia no tiene. Va AQUI ademas de en el subir de
                # nivel porque quien ya paso esos niveles nunca dispararia
                # aquel aviso, y se quedaria sin sus ranuras para siempre.
                import skills as _sk_in
                _tope_in = _sk_in.ranuras_de_habilidad(getattr(p, 'nivel', 1) or 1)
                _puestas = 0
                # Solo se rellenan las ranuras EXTRA. A quien todavia no
                # tenga sus seis de base no se le toca: ese aun esta por
                # elegir clase y llenarselas de oficios seria destrozarlo.
                if len(p.habilidades) < _sk_in.RANURAS_BASE:
                    _tope_in = 0
                while len(p.habilidades) < _tope_in:
                    _rl = _sk_in.rama_de_relleno(p.habilidades)
                    if not _rl:
                        break
                    if not getattr(p, 'banco_habilidades', None):
                        p.banco_habilidades = {}
                    _nv_in, _xp_in = p.banco_habilidades.get(_rl, (1, 0))
                    p.habilidades = list(p.habilidades) + [(_rl, _nv_in, _xp_in)]
                    _puestas += 1
                if _puestas:
                    p.class_id = _sk_in.calcular_class_id([h[0] for h in p.habilidades])
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_habilidades(ses.usuario, p.char_id, p.habilidades)
                        cuentas.guardar_clase(ses.usuario, p.char_id, p.class_id)
                        cuentas.guardar_banco_habilidades(
                            ses.usuario, p.char_id, getattr(p, 'banco_habilidades', None))
                    log.info('[%s] %s entra con %d ranura(s) de rama nueva(s) '
                             'por nivel %d: %s'
                             % (addr, p.nombre, _puestas, p.nivel,
                                ', '.join(_sk_in.nombre_rama(h[0])
                                          for h in p.habilidades[-_puestas:])))
                ses.enviar(_cl.arbol(p.habilidades, banco=getattr(p, 'banco_habilidades', None)))
                _ids = [h[0] for h in p.habilidades]
                _hech = _cl.hechizos_iniciales(_ids)
                _todos_hech = [n for n, _ in _hech]
                if getattr(p, 'hechizos_aprendidos', None):
                    _todos_hech = sorted(set(_todos_hech) | set(p.hechizos_aprendidos))
                if _todos_hech:
                    ses.enviar(*_cl.otorgar_hechizos(
                        p.entity_id, _todos_hech))
            # Y que el cliente dibuje al personaje con lo que lleva puesto.
            ses.enviar(*_apariencia(ses))
            try:
                import presencia as _pres
                _pres.entrar(ses, p.stage)
            except Exception:
                log.exception('presencia: fallo al entrar al mapa en login')
            # Iniciar tarea asincrona de IA para que los monstruos paseen por el mapa y ataquen
            async def _ia_monstruos():
                import random, time
                import combate as _cb
                import inventario as _iv
                import mascotas as _ms
                TICK_IA = 0.1
                # La probabilidad de pasear sale del tick: un paso cada 5.6 s
                # de mediana, que es lo medido en el Lyceum de Celestia.
                PROB_PASO = TICK_IA / _cb.SEGUNDOS_ENTRE_PASEOS
                MOVE = Msg.registry[(0x0005, 's2c', '*')]
                try:
                    while getattr(ses, 'personaje', None):
                        # Cada 100 ms. Las cadencias de los monstruos van de
                        # 672 a 1120 ms: con un bucle de 300 ms un bicho de
                        # 1.0 s acababa pegando cada 1.2 s y a saltos, que es
                        # lo que se veia con las Lilys (lentas y no fluidas).
                        await asyncio.sleep(TICK_IA)
                        p = getattr(ses, 'personaje', None)
                        if not p:
                            continue
                        _cb.ATACANTE[0] = ses
                        ahora = time.time()
                        yo = p.entity_id
                        f_pet = getattr(p, 'mascota', None) if ses.personaje else None
                        pet_eid = getattr(ses, 'pet_entity_id', None)

                        if getattr(ses, 'muerto', False):
                            # Un jugador muerto no recibe mas golpes: si no,
                            # la IA lo seguia matando y la ventana de muerte
                            # se reabria una y otra vez.
                            continue

                        # --- Invocacion(es) del jugador (Wraith summon & Duo Summon) ---
                        inv_list = []
                        if getattr(ses, 'invocacion', None):
                            inv_list.append(('invocacion', ses.invocacion))
                        if getattr(ses, 'invocacion2', None):
                            inv_list.append(('invocacion2', ses.invocacion2))

                        for inv_key, inv in inv_list:
                            if ahora >= inv.get('expira', 0) or inv.get('hp', 0) <= 0:
                                ses.enviar(_cb.atributo(inv['entity_id'], 0, _cb.KIND_HP),
                                           _cb.despawn_monstruo(inv['entity_id']),
                                           struct.pack('<HIBBI', 0x0013, yo, 1, 0x3d, 0))
                                import presencia as _pr
                                _pr.notificar_invocacion_despawn(ses, inv['entity_id'])
                                setattr(ses, inv_key, None)
                                log.info(f"[{addr}] invocacion {inv.get('nombre')} expirada/despawned")
                            else:
                                targ = inv.get('objetivo')
                                if targ and (not getattr(targ, 'vivo', False) or targ.hp <= 0 or getattr(targ, 'encantado', False)):
                                    inv['objetivo'] = None
                                    targ = None

                                if not targ and (inv.get('move_speed', 50) or 0) <= 0:
                                    # Totem estático auto-adquiere cualquier monstruo hostil cercano dentro de su rango
                                    for cand_m in list(getattr(ses, 'monstruos', {}).values()):
                                        if cand_m and getattr(cand_m, 'vivo', False) and cand_m.hp > 0 and not getattr(cand_m, 'encantado', False):
                                            if max(abs(inv['tile_x'] - cand_m.tile_x), abs(inv['tile_y'] - cand_m.tile_y)) <= inv.get('atk_range', 10):
                                                inv['objetivo'] = cand_m
                                                targ = cand_m
                                                break

                                if targ:
                                    dist_tx = abs(inv['tile_x'] - targ.tile_x)
                                    dist_ty = abs(inv['tile_y'] - targ.tile_y)
                                    dist_t = max(dist_tx, dist_ty)
                                    r_inv = max(1, inv.get('atk_range', 1))
                                    if dist_t > 15:
                                        inv['objetivo'] = None
                                    elif dist_t <= r_inv:
                                        cad_inv = max(0.65, min(1.0, 1.264 - 0.00477 * inv.get('atk_speed', 80)))
                                        if ahora - inv.get('ultimo_ataque', 0) >= cad_inv:
                                            inv['ultimo_ataque'] = ahora
                                            skills_inv = inv.get('skills', [])
                                            es_totem_inv = (inv.get('move_speed', 50) or 0) <= 0
                                            usa_skill = bool(skills_inv) if es_totem_inv else (skills_inv and (random.random() < 0.45))
                                            crit_rate = inv.get('crit_rate', 5)
                                            es_crit = (random.randint(1, 100) <= crit_rate)
                                            mult_inv = 1.5 if es_crit else 1.0

                                            d_mag_inv = {}
                                            if usa_skill:
                                                atk_magic = random.choice(skills_inv)
                                                d_mag_inv = _cb.datos_magia(atk_magic) or {}
                                                atk_efecto = _cb.efecto_de_ataque(atk_magic) or d_mag_inv.get('efecto', 148)
                                                pow_atk = max(inv['atk'], inv.get('matk', 0))
                                                dano_base = d_mag_inv.get('dano_base') or (pow_atk + int(round(_cb.stance_de(atk_magic) * _cb.PESO_STANCE)))
                                                mult_inv *= 1.2
                                                es_mag = True
                                            else:
                                                atk_magic = 656
                                                atk_efecto = 0
                                                dano_base = inv['atk']
                                                es_mag = False

                                            dano_inv = targ.recibir(dano_base, es_magico=es_mag, mult=mult_inv)
                                            anim_inv = _cb.anim_de_monstruo(inv.get('nombre', '')) or 832
                                            tipo_dmg = _cb.TIPO_DANO_CRITICO if es_crit else _cb.TIPO_DANO
                                            if getattr(targ, 'en_combate_con', None) is None:
                                                targ.en_combate_con = yo

                                            pkgs_inv_hit = [_cb.ataque(inv['entity_id'], targ.entity_id, anim_inv)]
                                            if usa_skill:
                                                pkgs_inv_hit.extend([
                                                    _cb.numero_de_dano(inv['entity_id'], targ.entity_id, dano_inv, ataque=atk_magic, efecto=atk_efecto),
                                                    _cb.cierre_de_dano(inv['entity_id'], targ.entity_id, ataque=atk_magic, efecto=atk_efecto),
                                                ])
                                                _ef_inv = _cb.efecto_secundario(atk_magic)
                                                if _ef_inv and random.random() * 100 < _ef_inv.get('prob', 0):
                                                    targ.aplicar_efecto(_ef_inv)
                                                    _mid_inv = _ef_inv.get('magia', atk_magic)
                                                    _dur_inv = _ef_inv.get('dur_ms', 10000)
                                                    pkgs_inv_hit.append(struct.pack('<HIBBII', 0x001D, targ.entity_id, 1, 4, _mid_inv, _dur_inv))
                                            pkgs_inv_hit.append(_cb.numero_flotante(targ.entity_id, dano_inv, tipo=tipo_dmg))

                                            if targ.hp <= 0:
                                                targ.hp = 0
                                                inv['objetivo'] = None
                                                pkgs_inv_hit.append(_cb.atributo(targ.entity_id, 0, _cb.VIDA))
                                                ses.enviar_inmediato(*pkgs_inv_hit)
                                                _procesar_muerte_monstruo(ses, targ, yo, addr, espera=0.1)
                                            else:
                                                pkgs_inv_hit.append(_cb.atributo(targ.entity_id, targ.porcentaje))
                                                ses.enviar_inmediato(*pkgs_inv_hit)
                                    else:
                                        if (inv.get('move_speed', 50) or 0) > 0 and ahora >= inv.get('proximo_paso', 0):
                                            dx = targ.tile_x - inv['tile_x']
                                            dy = targ.tile_y - inv['tile_y']
                                            dist_t = max(abs(dx), abs(dy))
                                            r_inv = inv.get('atk_range', 1)
                                            pasos_dar = min(max(1, dist_t - r_inv), 3)
                                            stx = (1 if dx > 0 else (-1 if dx < 0 else 0)) * pasos_dar
                                            sty = (1 if dy > 0 else (-1 if dy < 0 else 0)) * pasos_dar
                                            cur_x, cur_y = inv['tile_x'] * 32, inv['tile_y'] * 32
                                            inv['tile_x'] += stx
                                            inv['tile_y'] += sty
                                            dst_x, dst_y = inv['tile_x'] * 32, inv['tile_y'] * 32
                                            _pasos = max(abs(stx), abs(sty)) or 1
                                            spd = inv.get('move_speed', 50) or 50
                                            inv['proximo_paso'] = ahora + (_pasos * 32.0 / spd)
                                            _mv_inv = MOVE.build(entity_id=inv['entity_id'],
                                                                 cur_x=cur_x, cur_y=cur_y,
                                                                 dst_x=dst_x, dst_y=dst_y,
                                                                 speed=spd)
                                            ses.enviar(_mv_inv)
                                            import presencia as _pr
                                            _pr.notificar_invocacion_movimiento(ses, inv['entity_id'], _mv_inv)
                                else:
                                    if (inv.get('move_speed', 50) or 0) <= 0:
                                        continue
                                    # Seguir al jugador si no tiene objetivo
                                    _off_inv_x = -1 if inv_key == 'invocacion2' else 1
                                    p_dx = (p.tile_x + _off_inv_x) - inv['tile_x']
                                    p_dy = p.tile_y - inv['tile_y']
                                    p_dist = max(abs(p_dx), abs(p_dy))
                                    if p_dist > 15:
                                        inv['tile_x'] = p.tile_x + _off_inv_x
                                        inv['tile_y'] = p.tile_y
                                        cur_x, cur_y = inv['tile_x'] * 32, inv['tile_y'] * 32
                                        _mv_inv = MOVE.build(entity_id=inv['entity_id'],
                                                             cur_x=cur_x, cur_y=cur_y,
                                                             dst_x=cur_x, dst_y=cur_y,
                                                             speed=inv.get('move_speed', 50) or 50)
                                        ses.enviar(_mv_inv)
                                        import presencia as _pr
                                        _pr.notificar_invocacion_movimiento(ses, inv['entity_id'], _mv_inv)
                                    elif p_dist > 2 and ahora >= inv.get('proximo_paso', 0):
                                        pasos_dar = min(p_dist - 2, 3)
                                        stx = (1 if p_dx > 0 else (-1 if p_dx < 0 else 0)) * pasos_dar
                                        sty = (1 if p_dy > 0 else (-1 if p_dy < 0 else 0)) * pasos_dar
                                        cur_x, cur_y = inv['tile_x'] * 32, inv['tile_y'] * 32
                                        inv['tile_x'] += stx
                                        inv['tile_y'] += sty
                                        dst_x, dst_y = inv['tile_x'] * 32, inv['tile_y'] * 32
                                        _pasos = max(abs(stx), abs(sty)) or 1
                                        spd = inv.get('move_speed', 50) or 50
                                        inv['proximo_paso'] = ahora + (_pasos * 32.0 / spd)
                                        _mv_inv = MOVE.build(entity_id=inv['entity_id'],
                                                             cur_x=cur_x, cur_y=cur_y,
                                                             dst_x=dst_x, dst_y=dst_y,
                                                             speed=spd)
                                        ses.enviar(_mv_inv)
                                        import presencia as _pr
                                        _pr.notificar_invocacion_movimiento(ses, inv['entity_id'], _mv_inv)

                        # LOS QUE ESTAN LEJOS NO SE PIENSAN. Este bucle corre
                        # cada TICK_IA, o sea diez veces por segundo, y antes
                        # recorria TODOS los monstruos del mapa. Mientras los
                        # mapas tenian 200 o 300 bichos se aguantaba; las
                        # instancias traen 584 en Leviathan's Bedroom y 524 en
                        # Gulp Room 4, y eso son casi seis mil vueltas por
                        # segundo por jugador. Se noto en cuanto se entro a
                        # Dinosaur Arena: el juego iba a tirones.
                        #
                        # El jugador no ve mas alla de 38 casillas -- esta
                        # medido, es el radio que usa tools/cobertura_mapa.py
                        # para barrer un mapa -- asi que lo que pase a 48 no
                        # lo puede notar. Se saltan SOLO los que ademas no
                        # estan peleando ni encantados: un bicho que te
                        # persigue te sigue persiguiendo aunque te alejes.
                        _px = getattr(ses.personaje, 'tile_x', 0) if ses.personaje else 0
                        _py = getattr(ses.personaje, 'tile_y', 0) if ses.personaje else 0
                        # SALA DE INSTANCIA COMPARTIDA (ver _espejar): los
                        # bichos son los mismos para todo el grupo. El que
                        # pelea con un companero lo lleva el bucle de ese
                        # companero, y los paseos y el sangrado de los que
                        # estan sueltos, uno solo (el "conductor"); si no,
                        # se moverian y sangrarian dos veces.
                        _comp_ia = _companeros(ses)
                        _ajenos_ia = set()
                        for _s_c in _comp_ia:
                            _ajenos_ia |= _entidades_propias(_s_c)
                        # Cada bicho suelto lo conduce el de id mas bajo que
                        # lo tenga a la vista (RADIO_IA): en un mapa abierto
                        # el "primero" puede estar en la otra punta.
                        _menores_ia = [(_s_c.personaje.tile_x, _s_c.personaje.tile_y)
                                       for _s_c in _comp_ia if id(_s_c) < id(ses)]

                        def _conduce_ia_de(mm, _men=_menores_ia):
                            return not any(max(abs(mm.tile_x - _x), abs(mm.tile_y - _y)) <= RADIO_IA
                                           for _x, _y in _men)
                        for m in list((ses.monstruos or {}).values()):

                            if not getattr(m, 'vivo', True):
                                continue
                            if _ajenos_ia and (getattr(m, 'en_combate_con', None) in _ajenos_ia
                                               or m.entity_id in _ajenos_ia):
                                continue

                            if (not getattr(m, 'en_combate_con', None)
                                    and not getattr(m, 'encantado', False)
                                    and max(abs(m.tile_x - _px),
                                            abs(m.tile_y - _py)) > RADIO_IA):
                                continue

                            # Monstruo encantado (Charmed / Shining Charm de Earth): aliado del jugador
                            if getattr(m, 'encantado', False):
                                if ahora >= getattr(m, 'encantado_expira', 0):
                                    m.encantado = False
                                    m.charmed_objetivo = None
                                    if getattr(ses, 'monstruo_encantado', None) == m:
                                        ses.monstruo_encantado = None
                                    ses.enviar(
                                        struct.pack('<HIBBII', 0x001D, m.entity_id, 1, 4, 303, 0),
                                        struct.pack('<HIBBI', 0x0013, m.entity_id, 1, 0x3c, 0)
                                    )
                                    log.info(f"[{addr}] encanto sobre {m.nombre} expirado")
                                else:
                                    ch_targ = getattr(m, 'charmed_objetivo', None)
                                    if ch_targ and (not getattr(ch_targ, 'vivo', False) or ch_targ.hp <= 0 or getattr(ch_targ, 'encantado', False)):
                                        m.charmed_objetivo = None
                                        ch_targ = None

                                    if ch_targ:
                                        dtx = abs(m.tile_x - ch_targ.tile_x)
                                        dty = abs(m.tile_y - ch_targ.tile_y)
                                        dt = max(dtx, dty)
                                        r_m = max(1, getattr(m, 'atk_range', 1))
                                        if dt <= r_m:
                                            if ahora - getattr(m, 'ultimo_ataque', 0) >= _cb.cadencia_monstruo(m):
                                                m.ultimo_ataque = ahora
                                                dano_ch = max(5, m.pegar() - getattr(ch_targ, 'defensa', 0) // 2)
                                                ch_targ.registrar_dano(min(ch_targ.hp, dano_ch), es_pet=False)
                                                ch_targ.hp = max(0, ch_targ.hp - dano_ch)
                                                anim_m = _cb.anim_de_monstruo(m.nombre)
                                                if ch_targ.hp <= 0:
                                                    ch_targ.hp = 0
                                                    m.charmed_objetivo = None
                                                    ses.enviar_inmediato(
                                                        _cb.ataque(m.entity_id, ch_targ.entity_id, anim_m),
                                                        _cb.numero_de_dano(m.entity_id, ch_targ.entity_id, dano_ch, ataque=656, efecto=148),
                                                        _cb.cierre_de_dano(m.entity_id, ch_targ.entity_id, ataque=656, efecto=148),
                                                        _cb.numero_flotante(ch_targ.entity_id, dano_ch),
                                                        _cb.atributo(ch_targ.entity_id, 0, _cb.VIDA)
                                                    )
                                                    _procesar_muerte_monstruo(ses, ch_targ, yo, addr, espera=0.1)
                                                else:
                                                    ses.enviar_inmediato(
                                                        _cb.ataque(m.entity_id, ch_targ.entity_id, anim_m),
                                                        _cb.numero_de_dano(m.entity_id, ch_targ.entity_id, dano_ch, ataque=656, efecto=148),
                                                        _cb.cierre_de_dano(m.entity_id, ch_targ.entity_id, ataque=656, efecto=148),
                                                        _cb.numero_flotante(ch_targ.entity_id, dano_ch),
                                                        _cb.atributo(ch_targ.entity_id, ch_targ.porcentaje)
                                                    )
                                        else:
                                            if ahora >= getattr(m, 'proximo_paso', 0):
                                                dx = ch_targ.tile_x - m.tile_x
                                                dy = ch_targ.tile_y - m.tile_y
                                                dist_t = max(abs(dx), abs(dy))
                                                pasos_dar = min(max(1, dist_t - r_m), 3)
                                                _nx, _ny = _transitable.avanzar(
                                                    _mapa_de_paso(m, p.stage), (m.tile_x, m.tile_y),
                                                    (ch_targ.tile_x, ch_targ.tile_y), pasos_dar, parar_a=r_m)
                                                stx, sty = _nx - m.tile_x, _ny - m.tile_y
                                                cur_x, cur_y = m.tile_x * 32, m.tile_y * 32
                                                m.tile_x += stx
                                                m.tile_y += sty
                                                m.tile[0], m.tile[1] = m.tile_x, m.tile_y
                                                dst_x, dst_y = m.tile_x * 32, m.tile_y * 32
                                                _pasos = max(abs(stx), abs(sty)) or 1
                                                spd = m.move_speed or _cb.VELOCIDAD_PASEO
                                                _mv_ch = MOVE.build(entity_id=m.entity_id,
                                                                    cur_x=cur_x, cur_y=cur_y,
                                                                    dst_x=dst_x, dst_y=dst_y,
                                                                    speed=spd)
                                                ses.enviar(_mv_ch)
                                                import presencia as _pr
                                                _pr.notificar_invocacion_movimiento(ses, m.entity_id, _mv_ch)
                                    else:
                                        p_dx = p.tile_x - m.tile_x
                                        p_dy = p.tile_y - m.tile_y
                                        p_dist = max(abs(p_dx), abs(p_dy))
                                        if p_dist > 2 and ahora >= getattr(m, 'proximo_paso', 0):
                                            pasos_dar = min(p_dist - 2, 3)
                                            _nx, _ny = _transitable.avanzar(
                                                _mapa_de_paso(m, p.stage), (m.tile_x, m.tile_y),
                                                (p.tile_x, p.tile_y), pasos_dar, parar_a=2)
                                            stx, sty = _nx - m.tile_x, _ny - m.tile_y
                                            cur_x, cur_y = m.tile_x * 32, m.tile_y * 32
                                            m.tile_x += stx
                                            m.tile_y += sty
                                            m.tile[0], m.tile[1] = m.tile_x, m.tile_y
                                            dst_x, dst_y = m.tile_x * 32, m.tile_y * 32
                                            _pasos = max(abs(stx), abs(sty)) or 1
                                            spd = m.move_speed or _cb.VELOCIDAD_PASEO
                                            m.proximo_paso = ahora + (_pasos * 32.0 / spd)
                                            _mv_ch = MOVE.build(entity_id=m.entity_id,
                                                                  cur_x=cur_x, cur_y=cur_y,
                                                                  dst_x=dst_x, dst_y=dst_y,
                                                                  speed=spd)
                                            ses.enviar(_mv_ch)
                                            import presencia as _pr
                                            _pr.notificar_invocacion_movimiento(ses, m.entity_id, _mv_ch)
                                continue

                            # El sangrado / veneno le resta vida aunque nadie lo toque,
                            # y un monstruo aturdido no se mueve ni ataca.
                            _sang = (m.tick_sangrado()
                                     if getattr(m, 'en_combate_con', None) is not None or _conduce_ia_de(m)
                                     else 0)
                            if _sang:
                                ses.enviar(_cb.numero_flotante(m.entity_id, _sang, tipo=_cb.TIPO_DANO),
                                           _cb.atributo(m.entity_id, m.porcentaje))
                                if not m.vivo:
                                    _procesar_muerte_monstruo(ses, m, yo, addr, espera=0.0)
                                    continue
                            if m.aturdido:
                                continue

                            if getattr(m, 'panico', False):
                                if ahora >= getattr(m, 'panico_hasta', 0):
                                    m.panico = False
                                else:
                                    m.en_combate_con = None
                                    if ahora >= getattr(m, 'proximo_paso', 0):
                                        p_dx = m.tile_x - p.tile_x
                                        p_dy = m.tile_y - p.tile_y
                                        stride = random.randint(2, 4)
                                        dir_x = 1 if p_dx > 0 else (-1 if p_dx < 0 else random.choice([-1, 1]))
                                        dir_y = 1 if p_dy > 0 else (-1 if p_dy < 0 else random.choice([-1, 1]))
                                        new_x = max(0, m.tile_x + dir_x * stride)
                                        new_y = max(0, m.tile_y + dir_y * stride)
                                        # Huyendo tampoco cruza paredes.
                                        new_x, new_y = _transitable.avanzar(
                                            _mapa_de_paso(m, p.stage), (m.tile_x, m.tile_y), (new_x, new_y), stride)
                                        cur_x, cur_y = m.tile_x * 32, m.tile_y * 32
                                        _pasos = max(abs(new_x - m.tile_x), abs(new_y - m.tile_y)) or 1
                                        m.tile_x = new_x
                                        m.tile_y = new_y
                                        m.tile[0], m.tile[1] = new_x, new_y
                                        dst_x, dst_y = new_x * 32, new_y * 32
                                        spd = int((m.move_speed or 50) * 1.25)
                                        m.proximo_paso = ahora + (_pasos * 32.0 / spd)
                                        ses.enviar(MOVE.build(entity_id=m.entity_id,
                                                              cur_x=cur_x, cur_y=cur_y,
                                                              dst_x=dst_x, dst_y=dst_y,
                                                              speed=spd))
                                    continue

                            dist_x = abs(m.tile_x - p.tile_x)
                            dist_y = abs(m.tile_y - p.tile_y)
                            dist = max(dist_x, dist_y)

                            # AGRO. Cada monstruo trae en monster.xml su 主動:
                            # el radio en casillas al que se te tira encima
                            # sin que le pegues. La mayoria de los de mapa
                            # abierto lo tienen vacio y son PASIVOS -- por eso
                            # el agro "por cercania" para todos salio mal: en
                            # el Lyceum se camina entre ellos sin que
                            # reaccionen --, pero los de las instancias casi
                            # todos lo llevan (Fire Mummy 5, Earl Makice 12).
                            if (getattr(m, 'en_combate_con', None) is None
                                    and getattr(m, 'agro', 0) > 0
                                    and dist <= m.agro
                                    and not getattr(ses, 'muerto', False)
                                    and not _sigilo_activo(ses, ahora)
                                    and _se_ve_paso(_mapa_de_paso(m, ses.personaje.stage), (m.tile_x, m.tile_y),
                                                    (p.tile_x, p.tile_y))):
                                m.en_combate_con = yo

                            # 1. Monstruo en combate (jugador, mascota, invocacion o charmed)
                            targ_eid = getattr(m, 'en_combate_con', None)
                            if targ_eid is not None:
                                targ_x, targ_y = None, None
                                targ_valido = False

                                if targ_eid == yo:
                                    targ_x, targ_y = p.tile_x, p.tile_y
                                    targ_valido = not getattr(ses, 'muerto', False)
                                elif f_pet and f_pet.get('fuera') and pet_eid and targ_eid == pet_eid:
                                    targ_x, targ_y = f_pet.get('x', p.tile_x), f_pet.get('y', p.tile_y)
                                    targ_valido = (f_pet.get('hp', 1) > 0)
                                elif getattr(ses, 'invocacion', None) and targ_eid == ses.invocacion.get('entity_id'):
                                    itile = [ses.invocacion.get('tile_x', p.tile_x), ses.invocacion.get('tile_y', p.tile_y)]
                                    targ_x, targ_y = itile[0], itile[1]
                                    targ_valido = (ses.invocacion.get('hp', 1) > 0)
                                elif getattr(ses, 'invocacion2', None) and targ_eid == ses.invocacion2.get('entity_id'):
                                    itile = [ses.invocacion2.get('tile_x', p.tile_x), ses.invocacion2.get('tile_y', p.tile_y)]
                                    targ_x, targ_y = itile[0], itile[1]
                                    targ_valido = (ses.invocacion2.get('hp', 1) > 0)
                                elif getattr(ses, 'monstruo_encantado', None) and targ_eid == ses.monstruo_encantado.entity_id:
                                    targ_x, targ_y = ses.monstruo_encantado.tile_x, ses.monstruo_encantado.tile_y
                                    targ_valido = getattr(ses.monstruo_encantado, 'vivo', False)
                                else:
                                    m.en_combate_con = None

                                if targ_valido and targ_x is not None:
                                    d_targ = max(abs(m.tile_x - targ_x), abs(m.tile_y - targ_y))
                                    if d_targ > _cb.RANGO_PERDER_AGRO:
                                        m.en_combate_con = None
                                        log.debug(f"[{addr}] {m.nombre} pierde el agro a {d_targ} casillas")
                                        continue

                                    r_atk = max(1, getattr(m, 'atk_range', 1))
                                    # No pega hasta LLEGAR: el servidor le pone
                                    # la casilla nueva al mandar el 0x0005 y en
                                    # pantalla todavia va andando; pegando ya,
                                    # se le veia atacar desde lejos (los Goat
                                    # Demon del Training Palace).
                                    if d_targ <= r_atk and ahora >= getattr(m, 'proximo_paso', 0):
                                        if ahora - getattr(m, 'ultimo_ataque', 0) >= _cb.cadencia_monstruo(m):
                                            m.ultimo_ataque = ahora
                                            if targ_eid == yo:
                                                def_targ = defensa_jugador(ses)
                                                def_elem = defensas_elementales_jugador(ses)
                                                thnd_d = max(0, getattr(m, 'thnd_atk', 0) - def_elem['thnd'])
                                                fire_d = max(0, getattr(m, 'fire_atk', 0) - def_elem['fire'])
                                                ice_d = max(0, getattr(m, 'ice_atk', 0) - def_elem['ice'])
                                                rot_d = max(0, getattr(m, 'rotten_atk', 0) - def_elem['rotten'])
                                                elem_tot = thnd_d + fire_d + ice_d + rot_d
                                                suyo = _cb.dano_recibido(m.pegar(), def_targ, elem_atk=elem_tot, elem_def=0)
                                            elif f_pet and targ_eid == pet_eid:
                                                b_st_def = _ms.bonos_de_ficha(f_pet)
                                                b_bf_def = _ms.bonos_buffs(f_pet)
                                                def_targ = int(f_pet.get('dfs', 50)) + int(b_st_def.get('dfs', 0)) + int(b_bf_def.get('dfs', 0))
                                                if int(f_pet.get('saciedad', 0)) > 100:
                                                    def_targ = int(round(def_targ * 1.4))
                                                elem_tot = getattr(m, 'thnd_atk', 0) + getattr(m, 'fire_atk', 0) + getattr(m, 'ice_atk', 0) + getattr(m, 'rotten_atk', 0)
                                                suyo = _cb.dano_recibido(m.pegar(), def_targ, elem_atk=elem_tot, elem_def=0)
                                            else:
                                                def_targ = 100
                                                suyo = _cb.dano_recibido(m.pegar(), def_targ)
                                            # En sigilo se esquiva: Sneak V da
                                            # un 75% (物理迴避). Un golpe esquivado
                                            # hace 0; no hay paquete de "Miss"
                                            # medido y no se inventa uno.
                                            if (targ_eid == yo and _sigilo_activo(ses, ahora)
                                                    and random.randint(1, 100) <= int(getattr(ses, 'sigilo_esquiva', 0) or 0)):
                                                suyo = 0
                                            if targ_eid == yo and suyo:
                                                bolsa_yo = getattr(ses, 'inventario', None)
                                                if bolsa_yo:
                                                    mods_eq = _iv.modificadores_porcentuales_equipo(bolsa_yo)
                                                    mult_mit = mods_eq.get('phys_mit_mult', 1.0)
                                                    if mult_mit < 1.0:
                                                        suyo = max(1, int(round(suyo * mult_mit)))
                                                if ses.personaje and getattr(ses.personaje, 'buffs', None):
                                                    for b_data in ses.personaje.buffs.values():
                                                        if isinstance(b_data, dict) and b_data.get('fin', 0) > ahora and 'mit' in b_data:
                                                            suyo = max(1, int(round(suyo * (1.0 - b_data['mit'] / 100.0))))
                                            elif f_pet and targ_eid == pet_eid:
                                                b_bf_mit = _ms.bonos_buffs(f_pet).get('phys_mit_pct', 0)
                                                if b_bf_mit > 0:
                                                    suyo = max(1, int(round(suyo * (1.0 - b_bf_mit / 100.0))))
                                            ef_atk = m.proj_ef if m.proj_ef > 0 else 148

                                            ses.enviar(_cb.ataque(m.entity_id, targ_eid, _cb.anim_de_monstruo(m.nombre)))

                                            def _impacto(m=m, suyo=suyo, ef_atk=ef_atk, teid=targ_eid):
                                                if not getattr(m, 'vivo', False):
                                                    return
                                                if getattr(m, 'en_combate_con', None) != teid:
                                                    return
                                                if teid == yo:
                                                    pj = getattr(ses, 'personaje', None)
                                                    if not pj or getattr(ses, 'muerto', False):
                                                        return
                                                    ahora_imp = time.time()
                                                    # Demonic Counter (5156..5160), Particle Refraction (13670..13674) y Rebound Spell (5131..5135):
                                                    # reducen/reflejan parte del dano recibido al atacante sin repetir la animacion de casteo.
                                                    _dc_bid = next((
                                                        bid for bid, b in (pj.buffs or {}).items()
                                                        if (5156 <= int(bid) <= 5160 or 13670 <= int(bid) <= 13674 or 5131 <= int(bid) <= 5135)
                                                        and isinstance(b, dict) and b.get('fin', 0) > ahora_imp
                                                    ), None)
                                                    if _dc_bid is not None:
                                                        _bid_i = int(_dc_bid)
                                                        if 5156 <= _bid_i <= 5160:
                                                            _dc_pct = 0.20 + 0.02 * (_bid_i - 5155)
                                                        elif 13670 <= _bid_i <= 13674:
                                                            _dc_pct = 0.14 + 0.02 * (_bid_i - 13669)
                                                        else:
                                                            _dc_pct = 0.20 + 0.03 * (_bid_i - 5130)
                                                        refl = max(1, int(round(suyo * _dc_pct)))
                                                        suyo = max(1, suyo - refl)
                                                        m.registrar_dano(min(m.hp, refl), es_pet=False)
                                                        m.hp = max(0, m.hp - refl)
                                                        ses.enviar_inmediato(
                                                            _cb.numero_flotante(m.entity_id, refl),
                                                            _cb.atributo(m.entity_id, m.porcentaje if m.hp > 0 else 0)
                                                        )
                                                        if m.hp <= 0:
                                                            m.hp = 0
                                                            _procesar_muerte_monstruo(ses, m, yo, addr, espera=0.1)

                                                    # Shock Absorber (13675..13679): convierte un % del dano recibido en MP
                                                    _sa_bid = next((
                                                        bid for bid, b in (pj.buffs or {}).items()
                                                        if 13675 <= int(bid) <= 13679 and isinstance(b, dict) and b.get('fin', 0) > ahora_imp
                                                    ), None)

                                                    pj.hp = max(0, pj.hp - suyo)
                                                    pkgs_imp_yo = [
                                                        _cb.numero_de_dano(m.entity_id, yo, suyo, ataque=656, efecto=ef_atk),
                                                        _cb.numero_flotante(yo, suyo),
                                                        _cb.atributo(yo, pj.hp, _cb.KIND_HP),
                                                    ]
                                                    if _sa_bid is not None and pj.hp > 0:
                                                        _sa_pct = 0.12 + 0.02 * (int(_sa_bid) - 13674)
                                                        _mp_rec = max(1, int(round(suyo * _sa_pct)))
                                                        pj.mp = min(_mana_max(pj, ses.inventario), pj.mp + _mp_rec)
                                                        pkgs_imp_yo.append(_cb.atributo(yo, pj.mp, _cb.KIND_MP))
                                                        pkgs_imp_yo.append(_cb.numero_flotante(yo, _mp_rec, _cb.TIPO_CURA_MP))

                                                    if pj.hp <= 0:
                                                        ses.enviar_inmediato(*pkgs_imp_yo)
                                                        ses.enviar_inmediato(
                                                            _cb.ataque(yo, m.entity_id, 0, _cb.TIPO_MUERTE),
                                                            _cb.atributo(yo, 0, _cb.KIND_HP))
                                                        ses.muerto = True
                                                        m.en_combate_con = None
                                                    else:
                                                        if getattr(m, 'vivo', False) and m.hp > 0:
                                                            pkgs_imp_yo.extend(_procesar_triggers_buffs(ses, yo, m, addr=addr, en_ataque=False))
                                                        ses.enviar_inmediato(*pkgs_imp_yo)
                                                elif f_pet and teid == pet_eid:
                                                    dano_base = max(1, int(round(suyo / 3.5))) if int(f_pet.get('saciedad', 0)) > 100 else suyo
                                                    f_pet['hp'] = max(0, int(f_pet.get('hp', 100)) - dano_base)
                                                    if f_pet['hp'] <= 0:
                                                        # Si muere la mascota, baja su intimidad (-10 puntos, pero nunca menos de 40 para que no escape) y se guarda
                                                        import clases as _cl_pm
                                                        f_pet['intimidad'] = max(40, int(f_pet.get('intimidad', 60)) - 10)
                                                        f_pet['fuera'] = False
                                                        f_pet['entidad'] = 0
                                                        f_pet['hp'] = max(1, int(f_pet.get('hp_max') or 100))
                                                        ses.pet_entity_id = None
                                                        ses.pet_objetivo = None
                                                        m.en_combate_con = yo
                                                        _r_p = f_pet.get('ranura')
                                                        pkgs_pet_muerte = [
                                                            _cb.numero_de_dano(m.entity_id, pet_eid, suyo, ataque=656, efecto=ef_atk),
                                                            _cb.numero_flotante(pet_eid, suyo),
                                                            _ms.quitar(pet_eid),
                                                            _ms.enlazar(yo, 0),
                                                            _ms.armar(f_pet),
                                                            _cl_pm.aviso('10', tipo=7, msg_id=965),
                                                        ]
                                                        if _r_p is not None:
                                                            if getattr(ses.personaje, 'mascotas', None) is not None:
                                                                ses.personaje.mascotas[str(_r_p)] = f_pet
                                                            pkgs_pet_muerte.extend(_refrescar(ses, [_r_p]))
                                                        ses.enviar_inmediato(*pkgs_pet_muerte)
                                                        if getattr(ses, 'usuario', None) and ses.personaje:
                                                            cuentas.guardar_mascota(ses.usuario, ses.personaje.char_id, f_pet, getattr(ses.personaje, 'mascotas', None))
                                                    else:
                                                        ses.enviar_inmediato(
                                                            _cb.numero_de_dano(m.entity_id, pet_eid, suyo, ataque=656, efecto=ef_atk),
                                                            _cb.numero_flotante(pet_eid, suyo),
                                                            _cb.atributo(pet_eid, _ms.hp_eff(f_pet), _cb.KIND_HP),
                                                            _ms.armar(f_pet))
                                                elif getattr(ses, 'invocacion', None) and teid == ses.invocacion.get('entity_id'):
                                                    ses.invocacion['hp'] = max(0, ses.invocacion.get('hp', 1) - suyo)
                                                    ses.enviar_inmediato(
                                                        _cb.numero_de_dano(m.entity_id, teid, suyo, ataque=656, efecto=ef_atk),
                                                        _cb.numero_flotante(teid, suyo),
                                                        _cb.atributo(teid, int(100 * ses.invocacion['hp'] / max(1, ses.invocacion['hp_max'])), _cb.KIND_HP)
                                                    )
                                                    if ses.invocacion['hp'] <= 0:
                                                        ses.enviar_inmediato(_cb.despawn_monstruo(teid))
                                                        ses.invocacion = None
                                                        m.en_combate_con = yo
                                                elif getattr(ses, 'invocacion2', None) and teid == ses.invocacion2.get('entity_id'):
                                                    ses.invocacion2['hp'] = max(0, ses.invocacion2.get('hp', 1) - suyo)
                                                    ses.enviar_inmediato(
                                                        _cb.numero_de_dano(m.entity_id, teid, suyo, ataque=656, efecto=ef_atk),
                                                        _cb.numero_flotante(teid, suyo),
                                                        _cb.atributo(teid, int(100 * ses.invocacion2['hp'] / max(1, ses.invocacion2['hp_max'])), _cb.KIND_HP)
                                                    )
                                                    if ses.invocacion2['hp'] <= 0:
                                                        ses.enviar_inmediato(_cb.despawn_monstruo(teid))
                                                        ses.invocacion2 = None
                                                        m.en_combate_con = yo

                                            try:
                                                asyncio.get_event_loop().call_later(
                                                    _cb.retraso_golpe_monstruo(m), _impacto)
                                            except Exception:
                                                _impacto()
                                    else:
                                        if not getattr(m, 'es_estatico', False):
                                            if ahora < getattr(m, 'proximo_paso', 0):
                                                continue
                                            dx = targ_x - m.tile_x
                                            dy = targ_y - m.tile_y
                                            dist_t = max(abs(dx), abs(dy))
                                            pasos_dar = min(max(1, dist_t - r_atk), 3)
                                            # Bordeando paredes (transitable.py):
                                            # antes iba en linea recta y las
                                            # cruzaba. Si no hay por donde, se
                                            # queda quieto en su lado.
                                            _nx, _ny = _transitable.avanzar(
                                                _mapa_de_paso(m, ses.personaje.stage), (m.tile_x, m.tile_y),
                                                (targ_x, targ_y), pasos_dar, parar_a=r_atk)
                                            step_x, step_y = _nx - m.tile_x, _ny - m.tile_y
                                            if not step_x and not step_y:
                                                m.proximo_paso = ahora + 0.5
                                                continue
                                            cur_x, cur_y = m.tile_x * 32, m.tile_y * 32
                                            m.tile_x += step_x
                                            m.tile_y += step_y
                                            m.tile[0], m.tile[1] = m.tile_x, m.tile_y
                                            dst_x, dst_y = m.tile_x * 32, m.tile_y * 32
                                            _pasos = max(abs(step_x), abs(step_y)) or 1
                                            spd = m.move_speed or _cb.VELOCIDAD_PASEO
                                            if getattr(m, 'debuffs', None):
                                                for deb in m.debuffs.values():
                                                    if deb.get('vel_mov_mod'):
                                                        spd = max(10, spd + deb['vel_mov_mod'])
                                            m.proximo_paso = ahora + (_pasos * 32.0 / spd)
                                            ses.enviar(MOVE.build(entity_id=m.entity_id,
                                                                  cur_x=cur_x, cur_y=cur_y,
                                                                  dst_x=dst_x, dst_y=dst_y,
                                                                  speed=spd))
                                    continue
                            # 2. Monstruo libre: pasear, salvo los estaticos
                            if getattr(m, 'es_estatico', False) or not _conduce_ia_de(m):
                                continue
                            if ahora < getattr(m, 'proximo_paso', 0):
                                continue
                            _n = _cb.PASO_PASEO_MAX
                            dx = random.randint(-_n, _n)
                            dy = random.randint(-_n, _n)
                            if dx == 0 and dy == 0:
                                dx = random.choice((-1, 1))
                            new_x = m.tile_x + dx
                            new_y = m.tile_y + dy
                            _rango = max(m.move_range, _cb.RANGO_PASEO_MIN)
                            if (abs(new_x - m.spawn_x) > _rango or abs(new_y - m.spawn_y) > _rango):
                                new_x = m.spawn_x + random.randint(-_rango, _rango)
                                new_y = m.spawn_y + random.randint(-_rango, _rango)
                            new_x = max(0, new_x)
                            new_y = max(0, new_y)
                            # Solo a donde se llega andando en linea recta
                            # sin pisar pared; si no, este paseo se salta.
                            if not _transitable.linea_libre(_mapa_de_paso(m, ses.personaje.stage),
                                                            (m.tile_x, m.tile_y), (new_x, new_y)):
                                m.proximo_paso = ahora + random.uniform(_cb.PAUSA_PASEO_MIN,
                                                                        _cb.PAUSA_PASEO_MAX)
                                continue
                            _pasos = max(abs(new_x - m.tile_x), abs(new_y - m.tile_y)) or 1
                            m.proximo_paso = (ahora + _pasos * _cb.SEGUNDOS_POR_CASILLA
                                              + random.uniform(_cb.PAUSA_PASEO_MIN, _cb.PAUSA_PASEO_MAX))
                            cur_x, cur_y = m.tile_x * 32, m.tile_y * 32
                            m.tile_x = new_x
                            m.tile_y = new_y
                            m.tile[0], m.tile[1] = new_x, new_y
                            dst_x, dst_y = new_x * 32, new_y * 32
                            ses.enviar(MOVE.build(entity_id=m.entity_id,
                                                  cur_x=cur_x, cur_y=cur_y,
                                                  dst_x=dst_x, dst_y=dst_y,
                                                  speed=m.move_speed or _cb.VELOCIDAD_PASEO))
                        # --- IA DE MASCOTA AUTONOMA (Combate activo / Ayuda / Skills / Self-Buffs) ---
                        f_pet = getattr(p, 'mascota', None) if ses.personaje else None
                        pet_eid = getattr(ses, 'pet_entity_id', None)
                        if f_pet and f_pet.get('fuera') and pet_eid:
                            modo_pet = getattr(p, 'mascota_orden', 1)  # 0=Help, 1=Active, 2=Safe
                            if 'x' not in f_pet or 'y' not in f_pet:
                                _pt = getattr(ses, 'pet_tile', [p.tile_x + 1, p.tile_y])
                                f_pet['x'] = _pt[0]
                                f_pet['y'] = _pt[1]
                            pet_x = f_pet['x']
                            pet_y = f_pet['y']
                            pet_targ = getattr(ses, 'pet_objetivo', None)
                            # El encantado cuenta como muerto para la
                            # mascota: es aliado y no se le pega.
                            if pet_targ and (not getattr(pet_targ, 'vivo', False)
                                             or pet_targ.hp <= 0
                                             or getattr(pet_targ, 'encantado', False)):
                                pet_targ = None
                                ses.pet_objetivo = None

                            if modo_pet == 2:  # Safe (🕊️): PASIVO TOTAL, NUNCA ATACA, solo sigue
                                pet_targ = None
                                ses.pet_objetivo = None
                            elif modo_pet == 0:  # Help (🤝): SOLO ataca al enemigo con el que master o pet estan en combate
                                if not pet_targ and ses.monstruos:
                                    cands = []
                                    m_list = list(ses.monstruos.values()) if isinstance(ses.monstruos, dict) else (ses.monstruos or [])
                                    for m_cand in m_list:
                                        if getattr(m_cand, 'vivo', True) and getattr(m_cand, 'hp', 0) > 0 and not getattr(m_cand, 'encantado', False):
                                            d_pm = max(abs(m_cand.tile_x - p.tile_x), abs(m_cand.tile_y - p.tile_y))
                                            if getattr(m_cand, 'en_combate_con', None) in (yo, pet_eid):
                                                cands.append((d_pm, m_cand))
                                    if cands:
                                        cands.sort(key=lambda x: x[0])
                                        pet_targ = cands[0][1]
                                        ses.pet_objetivo = pet_targ
                            elif modo_pet == 1:  # Active (⚔️): Busca y ataca agresivamente a cualquier monstruo cercano
                                if not pet_targ and ses.monstruos:
                                    cands = []
                                    m_list = list(ses.monstruos.values()) if isinstance(ses.monstruos, dict) else (ses.monstruos or [])
                                    for m_cand in m_list:
                                        if getattr(m_cand, 'vivo', True) and getattr(m_cand, 'hp', 0) > 0 and not getattr(m_cand, 'encantado', False):
                                            d_pm = max(abs(m_cand.tile_x - p.tile_x), abs(m_cand.tile_y - p.tile_y))
                                            if d_pm <= 10:
                                                cands.append((d_pm, m_cand))
                                    if cands:
                                        cands.sort(key=lambda x: x[0])
                                        pet_targ = cands[0][1]
                                        ses.pet_objetivo = pet_targ
                            else:
                                pet_targ = None
                                ses.pet_objetivo = None

                            # --- Self-Buffs y Curaciones autonomas de la mascota (Demon Surge, Endless Energy, Fighting Shield, Life Blessing, Cure Spell, etc.) ---
                            if modo_pet != 2:
                                sks_pet_all = f_pet.get('skills') or list(_ms.skills_de(f_pet.get('sprite', 3001), int(f_pet.get('nivel', 1))))
                                cd_pet = f_pet.setdefault('cd_skills', {})
                                b_act_pet = _ms.buffs_activos_de(f_pet, ahora=ahora)
                                if ahora - f_pet.get('ultimo_cast_buff', 0) >= 1.5:
                                    for sk_p_id in [int(s) for s in sks_pet_all if s and int(s) > 0]:
                                        if ahora < cd_pet.get(sk_p_id, 0):
                                            continue
                                        sk_p_mag = _cb.datos_magia(sk_p_id)
                                        # 1. Habilidad de Buff de la mascota (Demon Surge, Feral Beast Fury, Ferity Strength, Endless Energy, Life Blessing, etc.)
                                        if sk_p_mag.get('es_buff') and not sk_p_mag.get('es_ataque') and not sk_p_mag.get('es_cura'):
                                            if sk_p_id in b_act_pet:
                                                continue
                                            dur_ms_p = max(10000, int(sk_p_mag.get('dur_ms') or 30000))
                                            cd_ms_p = max(5000, int(sk_p_mag.get('cd_ms') or dur_ms_p))
                                            cd_pet[sk_p_id] = ahora + (cd_ms_p / 1000.0)
                                            f_pet['ultimo_cast_buff'] = ahora
                                            fin_p = ahora + (dur_ms_p / 1000.0)
                                            b_entry_p = dict(sk_p_mag)
                                            b_entry_p.pop('mp', None)
                                            b_entry_p.pop('hp', None)
                                            b_entry_p['fin'] = fin_p
                                            b_entry_p['mag'] = sk_p_mag
                                            if sk_p_mag.get('crit_rate'):
                                                b_entry_p['crit'] = sk_p_mag.get('crit_rate')
                                            if sk_p_mag.get('phys_mit'):
                                                b_entry_p['mit'] = sk_p_mag.get('phys_mit')
                                            if sk_p_mag.get('mag_mit'):
                                                b_entry_p['mag_mit'] = sk_p_mag.get('mag_mit')
                                            if sk_p_mag.get('def_bonus'):
                                                b_entry_p['def'] = sk_p_mag.get('def_bonus')
                                            if sk_p_mag.get('atk_bonus'):
                                                b_entry_p['atk'] = sk_p_mag.get('atk_bonus')
                                            if sk_p_mag.get('matk_bonus'):
                                                b_entry_p['matk'] = sk_p_mag.get('matk_bonus')
                                            if sk_p_mag.get('mdef_bonus'):
                                                b_entry_p['mdef'] = sk_p_mag.get('mdef_bonus')
                                            if sk_p_mag.get('mag_dmg_pct'):
                                                b_entry_p['mag_dmg_pct'] = sk_p_mag.get('mag_dmg_pct')
                                            if sk_p_mag.get('phys_dmg_pct'):
                                                b_entry_p['phys_dmg_pct'] = sk_p_mag.get('phys_dmg_pct')
                                            if sk_p_mag.get('hp_bonus'):
                                                b_entry_p['hp_bonus'] = sk_p_mag.get('hp_bonus')
                                            if sk_p_mag.get('mp_bonus'):
                                                b_entry_p['mp_bonus'] = sk_p_mag.get('mp_bonus')
                                            f_pet.setdefault('buffs', {})[sk_p_id] = dict(b_entry_p)
                                            if not hasattr(p, 'buffs') or p.buffs is None:
                                                p.buffs = {}
                                            p.buffs[sk_p_id] = dict(b_entry_p)
                                            if sk_p_mag.get('hp_bonus') or sk_p_mag.get('hp_pct'):
                                                f_pet['hp'] = int(f_pet.get('hp_max') or 100)
                                                p.hp = _vida_max(p, ses.inventario)
                                            if sk_p_mag.get('mp_bonus') or sk_p_mag.get('mp_pct'):
                                                f_pet['mp'] = int(f_pet.get('mp_max') or 100)
                                                p.mp = _mana_max(p, ses.inventario)
                                            ef_p_bf = int(sk_p_mag.get('efecto') or 251)
                                            ses.enviar_inmediato(
                                                _cb.efecto_magia_self_inicio(int(pet_eid), ef_p_bf, sk_p_id, cast_time=100),
                                                _cb.efecto_magia_self_fin(int(pet_eid), ef_p_bf, sk_p_id),
                                                struct.pack('<HIBBII', 0x001D, int(pet_eid), 1, 4, sk_p_id, dur_ms_p),
                                                struct.pack('<HIBBII', 0x001D, yo, 1, 4, sk_p_id, dur_ms_p),
                                                _cb.atributo(int(pet_eid), _ms.hp_eff(f_pet), _cb.KIND_HP),
                                                _cb.atributo(yo, p.hp, _cb.KIND_HP),
                                                _cb.atributo(yo, p.mp, _cb.KIND_MP),
                                                _ms.armar(f_pet),
                                                _stats_ses(ses),
                                            )
                                            def _expirar_pet_self_buff(bid=sk_p_id, f_ts=fin_p):
                                                pj_cur = getattr(ses, 'personaje', None)
                                                if not pj_cur:
                                                    return
                                                fp_cur = getattr(pj_cur, 'mascota', None)
                                                peid_cur = getattr(ses, 'pet_entity_id', None)
                                                pkgs_exp_p = []
                                                if isinstance(fp_cur, dict) and isinstance(fp_cur.get('buffs'), dict):
                                                    act_p = fp_cur['buffs'].get(bid)
                                                    if act_p and act_p.get('fin') == f_ts:
                                                        fp_cur['buffs'].pop(bid, None)
                                                        if peid_cur and fp_cur.get('fuera'):
                                                            pkgs_exp_p.append(struct.pack('<HIBBII', 0x001D, int(peid_cur), 1, 4, bid, 0))
                                                            pkgs_exp_p.append(_cb.atributo(int(peid_cur), _ms.hp_eff(fp_cur), _cb.KIND_HP))
                                                            pkgs_exp_p.append(_ms.armar(fp_cur))
                                                if getattr(pj_cur, 'buffs', None):
                                                    act_j = pj_cur.buffs.get(bid)
                                                    if act_j and act_j.get('fin') == f_ts:
                                                        pj_cur.buffs.pop(bid, None)
                                                        pj_cur.hp = min(pj_cur.hp, _vida_max(pj_cur, ses.inventario))
                                                        pj_cur.mp = min(pj_cur.mp, _mana_max(pj_cur, ses.inventario))
                                                        pkgs_exp_p.extend([
                                                            struct.pack('<HIBBII', 0x001D, yo, 1, 4, bid, 0),
                                                            _cb.atributo(yo, pj_cur.hp, _cb.KIND_HP),
                                                            _cb.atributo(yo, pj_cur.mp, _cb.KIND_MP),
                                                            _stats_ses(ses),
                                                        ])
                                                if pkgs_exp_p:
                                                    ses.enviar_inmediato(*pkgs_exp_p)
                                            try:
                                                asyncio.get_event_loop().call_later(dur_ms_p / 1000.0, _expirar_pet_self_buff)
                                            except Exception:
                                                pass
                                            log.info(f"[{addr}] mascota {f_pet.get('nombre')} lanzo buff {sk_p_id} ({sk_p_mag.get('nombre')}, dur={dur_ms_p}ms)")
                                            break
                                        # 2. Habilidad de Curacion de la mascota (Cure Spell, Mighty Cure, Angel's Tears)
                                        elif sk_p_mag.get('es_cura'):
                                            pet_herida = int(f_pet.get('hp', 100)) < int(int(f_pet.get('hp_max') or 100) * 0.85)
                                            jug_herido = p.hp < int(_vida_max(p, ses.inventario) * 0.85)
                                            if not pet_herida and not jug_herido:
                                                continue
                                            cd_ms_p = max(3000, int(sk_p_mag.get('cd_ms') or 5000))
                                            cd_pet[sk_p_id] = ahora + (cd_ms_p / 1000.0)
                                            f_pet['ultimo_cast_buff'] = ahora
                                            cura_p = max(30, abs(int(sk_p_mag.get('hp') or 150)))
                                            ef_p_c = int(sk_p_mag.get('efecto') or 165)
                                            pkgs_c_p = []
                                            if pet_herida:
                                                f_pet['hp'] = min(int(f_pet.get('hp_max') or 100), int(f_pet.get('hp') or 100) + cura_p)
                                                pkgs_c_p.extend([
                                                    _cb.efecto_curacion_inicio(int(pet_eid), int(pet_eid), cura_p, efecto=ef_p_c),
                                                    _cb.efecto_curacion_fin(int(pet_eid), int(pet_eid), efecto=ef_p_c),
                                                    _cb.numero_flotante(int(pet_eid), cura_p, _cb.TIPO_CURA_HP),
                                                    _cb.atributo(int(pet_eid), _ms.hp_eff(f_pet), _cb.KIND_HP),
                                                    _ms.armar(f_pet),
                                                ])
                                            if jug_herido:
                                                p.hp = min(_vida_max(p, ses.inventario), p.hp + cura_p)
                                                pkgs_c_p.extend([
                                                    _cb.efecto_curacion_inicio(int(pet_eid), yo, cura_p, efecto=ef_p_c),
                                                    _cb.efecto_curacion_fin(int(pet_eid), yo, efecto=ef_p_c),
                                                    _cb.numero_flotante(yo, cura_p, _cb.TIPO_CURA_HP),
                                                    _cb.atributo(yo, p.hp, _cb.KIND_HP),
                                                ])
                                            if pkgs_c_p:
                                                ses.enviar_inmediato(*pkgs_c_p)
                                            log.info(f"[{addr}] mascota {f_pet.get('nombre')} lanzo curacion {sk_p_id} ({sk_p_mag.get('nombre')}, +{cura_p} HP)")
                                            break

                            if pet_targ and modo_pet != 2:
                                dx_p = pet_targ.tile_x - pet_x
                                dy_p = pet_targ.tile_y - pet_y
                                dist_pet = max(abs(dx_p), abs(dy_p))
                                r_pet = 2
                                b_star = _ms.bonos_de_ficha(f_pet)
                                b_bf_atk = _ms.bonos_buffs(f_pet)
                                sac_buff = int(f_pet.get('saciedad', 0)) > 100
                                agi_total = int(f_pet.get('agilidad', 15)) + int(b_star.get('agilidad', 0)) + int(b_bf_atk.get('agilidad', 0))
                                if sac_buff:
                                    agi_total = int(round(agi_total * 1.2))
                                cadencia_pet = max(0.95 if sac_buff else 1.15, min(1.55, 1.55 - agi_total * 0.002))
                                if b_bf_atk.get('atk_speed'):
                                    cadencia_pet = max(0.75, cadencia_pet * (1.0 - min(0.40, b_bf_atk['atk_speed'] / 100.0)))
                                if dist_pet <= r_pet:
                                    if ahora - f_pet.get('ultimo_ataque', 0) >= cadencia_pet:
                                        f_pet['ultimo_ataque'] = ahora
                                        pet_targ.en_combate_con = pet_eid  # El monstruo enfoca a la mascota
                                        sks = f_pet.get('skills') or list(_ms.skills_de(f_pet.get('sprite', 3001), int(f_pet.get('nivel', 1))))
                                        cd_pet = f_pet.setdefault('cd_skills', {})
                                        sk_cands = [
                                            int(s) for s in sks
                                            if s and int(s) > 0
                                            and (_cb.datos_magia(int(s)).get('es_ataque') or _cb.datos_magia(int(s)).get('es_debuff'))
                                            and ahora >= cd_pet.get(int(s), 0)
                                        ]
                                        sk_usada = random.choice(sk_cands) if sk_cands and random.random() < 0.65 else None
                                        base_atk_pet = int(f_pet.get('atk', 100)) + int(b_star.get('atk', 0)) + int(b_bf_atk.get('atk', 0))
                                        base_matk_pet = int(f_pet.get('matk', 100)) + int(b_star.get('matk', 0)) + int(b_bf_atk.get('matk', 0))
                                        if sac_buff:
                                            base_atk_pet = int(round(base_atk_pet * 1.4))
                                            base_matk_pet = int(round(base_matk_pet * 1.4))
                                        if b_bf_atk.get('phys_dmg_pct'):
                                            base_atk_pet = int(round(base_atk_pet * (1.0 + b_bf_atk['phys_dmg_pct'] / 100.0)))
                                        if b_bf_atk.get('mag_dmg_pct'):
                                            base_matk_pet = int(round(base_matk_pet * (1.0 + b_bf_atk['mag_dmg_pct'] / 100.0)))

                                        if sk_usada:
                                            sk_datos = _cb.datos_magia(sk_usada)
                                            cd_sk_atk = max(1000, int(sk_datos.get('cd_ms') or 2000))
                                            cd_pet[sk_usada] = ahora + (cd_sk_atk / 1000.0)
                                            ef_pet = sk_datos.get('efecto') or 101
                                            dano_pet = max(25, int(base_matk_pet * 2.2) - (getattr(pet_targ, 'mdef', 0) // 3))
                                            pet_targ.registrar_dano(min(pet_targ.hp, dano_pet), es_pet=True)
                                            pet_targ.hp = max(0, pet_targ.hp - dano_pet)
                                            ses.enviar_inmediato(
                                                _cb.numero_de_dano(pet_eid, pet_targ.entity_id, dano_pet, ataque=sk_usada, efecto=ef_pet),
                                                _cb.cierre_de_dano(pet_eid, pet_targ.entity_id, ataque=sk_usada, efecto=ef_pet),
                                                _cb.numero_flotante(pet_targ.entity_id, dano_pet),
                                                _cb.atributo(pet_targ.entity_id, pet_targ.porcentaje if pet_targ.hp > 0 else 0)
                                            )
                                            _combo_p = _cb.combo_de(sk_usada)
                                            if _combo_p and _combo_p.get('golpes', 1) > 1:
                                                _golpes = _combo_p['golpes']
                                                _sep_p = max(0.05, _combo_p.get('intervalo_ms', 200) / 1000.0)
                                                for _gk in range(1, _golpes):
                                                    def _pet_subgolpe(k_dmg=dano_pet):
                                                        if not getattr(pet_targ, 'vivo', False) or pet_targ.hp <= 0:
                                                            return
                                                        pet_targ.hp = max(0, pet_targ.hp - k_dmg)
                                                        ses.enviar_inmediato(
                                                            _cb.numero_de_dano(pet_eid, pet_targ.entity_id, k_dmg, ataque=sk_usada, efecto=ef_pet),
                                                            _cb.cierre_de_dano(pet_eid, pet_targ.entity_id, ataque=sk_usada, efecto=ef_pet),
                                                            _cb.numero_flotante(pet_targ.entity_id, k_dmg),
                                                            _cb.atributo(pet_targ.entity_id, pet_targ.porcentaje if pet_targ.hp > 0 else 0)
                                                        )
                                                        if pet_targ.hp <= 0:
                                                            _procesar_muerte_monstruo(ses, pet_targ, yo, addr, espera=0.1)
                                                    try:
                                                        asyncio.get_event_loop().call_later(_sep_p * _gk, _pet_subgolpe)
                                                    except Exception:
                                                        pass
                                        else:
                                            dano_pet = max(10, int(base_atk_pet * 1.2) - (getattr(pet_targ, 'defensa', 0) // 3))
                                            pet_targ.registrar_dano(min(pet_targ.hp, dano_pet), es_pet=True)
                                            pet_targ.hp = max(0, pet_targ.hp - dano_pet)
                                            ses.enviar_inmediato(
                                                _cb.numero_de_dano(pet_eid, pet_targ.entity_id, dano_pet, ataque=0, efecto=0),
                                                _cb.cierre_de_dano(pet_eid, pet_targ.entity_id, ataque=0, efecto=0),
                                                _cb.numero_flotante(pet_targ.entity_id, dano_pet),
                                                _cb.atributo(pet_targ.entity_id, pet_targ.porcentaje if pet_targ.hp > 0 else 0)
                                            )
                                        if pet_targ.hp <= 0:
                                            pet_targ.hp = 0
                                            ses.pet_objetivo = None
                                            _procesar_muerte_monstruo(ses, pet_targ, yo, addr, espera=0.1)
                                else:
                                    if ahora >= f_pet.get('proximo_paso', 0):
                                        spd_p = 140 if int(f_pet.get('saciedad', 0)) > 100 else 105
                                        pasos_dar = min(max(1, dist_pet - 1), 4)
                                        cur_px, cur_py = pet_x * 32, pet_y * 32
                                        nx_p, ny_p = pet_x, pet_y
                                        for _ in range(pasos_dar):
                                            if nx_p < pet_targ.tile_x: nx_p += 1
                                            elif nx_p > pet_targ.tile_x: nx_p -= 1
                                            if ny_p < pet_targ.tile_y: ny_p += 1
                                            elif ny_p > pet_targ.tile_y: ny_p -= 1
                                        f_pet['x'] = nx_p
                                        f_pet['y'] = ny_p
                                        ses.pet_tile = [nx_p, ny_p]
                                        dst_px, dst_py = nx_p * 32, ny_p * 32
                                        f_pet['proximo_paso'] = ahora + (32.0 * pasos_dar / float(spd_p))
                                        _p_mv = MOVE.build(entity_id=pet_eid, cur_x=cur_px, cur_y=cur_py, dst_x=dst_px, dst_y=dst_py, speed=spd_p)
                                        ses.enviar(_p_mv)
                                        import presencia as _pr
                                        _pr.notificar_mascota_movimiento(ses, pet_eid, _p_mv)
                            else:
                                dp_x = p.tile_x - pet_x
                                dp_y = p.tile_y - pet_y
                                dist_jug = max(abs(dp_x), abs(dp_y))
                                spd_p = 140 if int(f_pet.get('saciedad', 0)) > 100 else 105
                                if dist_jug > 15:
                                    f_pet['x'] = p.tile_x + 1
                                    f_pet['y'] = p.tile_y
                                    ses.pet_tile = [f_pet['x'], f_pet['y']]
                                    cur_px, cur_py = f_pet['x'] * 32, f_pet['y'] * 32
                                    _p_mv = MOVE.build(entity_id=pet_eid, cur_x=cur_px, cur_y=cur_py, dst_x=cur_px, dst_y=cur_py, speed=spd_p)
                                    ses.enviar(
                                        struct.pack('<HIII', 0x0003, pet_eid, f_pet['x'], f_pet['y']),
                                        _p_mv
                                    )
                                    import presencia as _pr
                                    _pr.notificar_mascota_movimiento(ses, pet_eid, _p_mv)
                                elif dist_jug > 1 and ahora >= f_pet.get('proximo_paso', 0):
                                    pasos_dar = min(dist_jug - 1, 4)
                                    cur_px, cur_py = pet_x * 32, pet_y * 32
                                    nx_j, ny_j = pet_x, pet_y
                                    for _ in range(pasos_dar):
                                        if nx_j < p.tile_x: nx_j += 1
                                        elif nx_j > p.tile_x: nx_j -= 1
                                        if ny_j < p.tile_y: ny_j += 1
                                        elif ny_j > p.tile_y: ny_j -= 1
                                    f_pet['x'] = nx_j
                                    f_pet['y'] = ny_j
                                    ses.pet_tile = [nx_j, ny_j]
                                    dst_px, dst_py = nx_j * 32, ny_j * 32
                                    f_pet['proximo_paso'] = ahora + (32.0 * pasos_dar / float(spd_p))
                                    _p_mv = MOVE.build(entity_id=pet_eid, cur_x=cur_px, cur_y=cur_py, dst_x=dst_px, dst_y=dst_py, speed=spd_p)
                                    ses.enviar(_p_mv)
                                    import presencia as _pr
                                    _pr.notificar_mascota_movimiento(ses, pet_eid, _p_mv)

                        # AL FINAL DE CADA TICK, A LA RED. Sin esto el paseo
                        # se quedaba en el buffer hasta que el cliente mandaba
                        # algo, o sea que los monstruos solo se movian cuando
                        # se movia el jugador. Los golpes si se veian porque
                        # usan enviar_inmediato, que ya volcaba.
                        ses.volcar()
                except Exception:
                    # Estaba en 'pass': si algo fallaba UNA vez la tarea
                    # moria en silencio y todos los monstruos del mapa se
                    # quedaban quietos para siempre, sin dejar rastro en el
                    # log. Ahora se anota y la IA se vuelve a levantar.
                    log.exception(f"[{addr}] la IA de monstruos fallo, "
                                  f"se reinicia")
                    if getattr(ses, 'personaje', None):
                        asyncio.get_event_loop().call_later(
                            1.0, lambda: asyncio.create_task(_ia_monstruos()))

            asyncio.create_task(_ia_monstruos())
            log.info(f"[{addr}] entro al mundo: '{p.nombre}' entidad={p.entity_id} "
                     f"char_id={p.char_id} tile=({p.tile_x},{p.tile_y})")
            log.info(f"[{addr}] (credenciales NO validadas: formato aun sin descifrar)")
            return

        # EQUIPOS. Los dos opcodes salen de una captura del Global con tres
        # cuentas montando un grupo de verdad; ver server/equipos.py.
        if opcode == 0x0017 and ses.rol == 'mundo' and cuerpo:
            import equipos as _eq
            nombre = cuerpo.split(bytes(1))[0].decode('ascii', 'replace').strip()

            def _por_nombre(n):
                for s in self.mundos:
                    p2 = getattr(s, 'personaje', None)
                    if p2 is not None and (getattr(p2, 'nombre', '') or '') == n:
                        return s
                return None
            ok, por_que = _eq.invitar(ses, nombre, _por_nombre)
            log.info("[%s] invita a '%s': %s", addr, nombre,
                     'cartel mandado' if ok else por_que)
            return

        if opcode == 0x0018 and ses.rol == 'mundo':
            import equipos as _eq
            cod = cuerpo[0] if cuerpo else 0
            log.info('[%s] grupo, accion %d: %s', addr, cod,
                     _eq.accion(ses, cod, cuerpo))
            return

        if opcode == 0x0002 and ses.entity_id:
            # El cliente cargo la escena del mapa nuevo y avisa que esta listo
            p = getattr(ses, 'personaje', None)
            if p:
                import login as _lg, clases as _cl, inventario as inv, combate as _cb
                ses.monstruos = _monstruos_de(p.stage)
                ses.enviar(*_lg.poblar(p.stage))
                # PRESENCIA: aqui, y no al mandar el 0x000C, porque hasta
                # este momento el cliente no tiene el mapa cargado y los
                # spawns que lleguen antes se pierden.
                try:
                    import presencia as _pres
                    _pres.entrar(ses, p.stage)
                except Exception:
                    log.exception('presencia: fallo al entrar al mapa')
                if getattr(p, 'habilidades', None):
                    ses.enviar(_cl.arbol(p.habilidades, banco=getattr(p, 'banco_habilidades', None)))
                    _ids = [h[0] for h in p.habilidades]
                    _hech = _cl.hechizos_iniciales(_ids)
                    _todos_hech = [n for n, _ in _hech]
                    if getattr(p, 'hechizos_aprendidos', None):
                        _todos_hech = sorted(set(_todos_hech) | set(p.hechizos_aprendidos))
                    if _todos_hech:
                        ses.enviar(*_cl.otorgar_hechizos(p.entity_id, _todos_hech))
                bars, max_pts = _max_sp_info(p)
                # El SP viene del personaje guardado. Empieza a cero solo la
                # primera vez: se gana peleando y se conserva al salir.
                ses.sp = getattr(ses, 'sp', None)
                if ses.sp is None:
                    ses.sp = max(0, int(getattr(p, 'sp', 0) or 0))
                b = getattr(ses, 'inventario', None) or getattr(p, 'inventario', None) or {}
                eff_hp_max = _vida_max(p, bolsa=b)
                eff_mp_max = _mana_max(p, bolsa=b)
                p.hp = min(eff_hp_max, max(1, p.hp))
                p.mp = min(eff_mp_max, max(0, p.mp))
                p.exp = max(int(p.exp or 0), _cb.exp_para_nivel(p.nivel))
                exp_actual_ui, exp_sig = _cb.exp_para_barra(p.nivel, p.exp)
                _u64 = lambda v: max(0, min(int(v or 0), 0xFFFFFFFFFFFFFFFF))
                yo = p.entity_id
                salida = [
                    _cb.atributo(yo, p.hp, _cb.KIND_HP),
                    _cb.atributo(yo, p.mp, _cb.KIND_MP),
                    _cb.atributo(yo, ses.sp, _cb.KIND_SP),
                    struct.pack('<HIB', 0x001D, yo, 4) +
                    struct.pack('<BQ', 29, _u64(p.nivel)) +
                    struct.pack('<BQ', 30, max(0, int(_cb.exp_para_nivel(p.nivel)))) +
                    struct.pack('<BQ', 31, _u64(exp_sig)) +
                    struct.pack('<BQ', 32, _u64(exp_actual_ui)),
                    inv.stats(b, p.habilidades,
                              hp=p.hp, hp_max=p.hp_max,
                              mp=p.mp, mp_max=p.mp_max,
                              oro=getattr(ses, 'oro', p.oro), buffs=getattr(p, 'buffs', None),
                              sp=ses.sp, sp_max=bars, mejoras=_mejoras_de(ses)),
                    *_apariencia(ses)
                ]
                # Restauracion de buffs activos al entrar al mundo (relog)
                now_t = time.time()
                if getattr(p, 'buffs', None):
                    for b_id, b_data in list(p.buffs.items()):
                        if isinstance(b_data, dict):
                            rem_s = b_data.get('fin', 0) - now_t
                            if rem_s > 0:
                                rem_ms = int(rem_s * 1000)
                                salida.append(struct.pack('<HIBBII', 0x001D, yo, 1, 4, int(b_id), rem_ms))
                                _ts = b_data.get('trans_sprite') or b_data.get('mag', {}).get('trans_sprite')
                                if b_data.get('es_transform') and _ts:
                                    salida.append(_cb.atributo(yo, _ts, _cb.KIND_TRANSFORM))
                                def _expirar_login(sk_id=int(b_id), fin=b_data['fin']):
                                    buffs_act = getattr(p, 'buffs', None)
                                    act = buffs_act.get(sk_id) if buffs_act else None
                                    if not act or act.get('fin') != fin:
                                        return
                                    buffs_act.pop(sk_id, None)
                                    p.hp = min(p.hp, _vida_max(p, bolsa=b))
                                    p.mp = min(p.mp, _mana_max(p, bolsa=b))
                                    pks = [
                                        struct.pack('<HIBBII', 0x001D, yo, 1, 4, sk_id, 0),
                                        _cb.atributo(yo, p.hp, _cb.KIND_HP),
                                        _cb.atributo(yo, p.mp, _cb.KIND_MP),
                                    ]
                                    if act.get('es_transform'):
                                        pks.append(_cb.atributo(yo, 0, _cb.KIND_TRANSFORM))
                                    pks.append(_stats_ses(ses))
                                    ses.enviar_inmediato(*pks)
                                asyncio.get_event_loop().call_later(rem_s, _expirar_login)
                            else:
                                p.buffs.pop(b_id, None)
                f_pet = getattr(p, 'mascota', None)
                if isinstance(f_pet, dict) and f_pet.get('fuera'):
                    import mascotas as _pet
                    if not f_pet.get('entidad'):
                        f_pet['entidad'] = _pet_siguiente_entidad(ses)
                    _r_p = int(f_pet.get('ranura') if f_pet.get('ranura') is not None else 20)
                    f_pet['instancia'] = 1000 + _r_p
                    px_pet = (p.tile_x or 80) + 1
                    py_pet = (p.tile_y or 80)
                    f_pet['x'] = px_pet
                    f_pet['y'] = py_pet
                    f_pet['proximo_paso'] = 0.0
                    ses.pet_entity_id = f_pet['entidad']
                    ses.pet_tile = [px_pet, py_pet]
                    est_pet = dict(f_pet)
                    est_pet.update({
                        'x': px_pet, 'y': py_pet,
                        'dueno': yo, 'dueno_nombre': p.nombre,
                        'tipo': f_pet.get('tipo', 0),
                    })
                    salida.extend([
                        _pet.enlazar(yo, f_pet['entidad']),
                        struct.pack('<HIBBI', 0x0013, yo, 1, 0x3F, f_pet['entidad']),
                        _pet.armar(f_pet),
                        *_refrescar(ses, [_r_p]),
                        _pet.entidad_mundo(_pet_plantilla(), est_pet),
                        _pet.armar(f_pet),
                        _cb.atributo(f_pet['entidad'], _pet.hp_eff(f_pet), _cb.KIND_HP),
                    ])
                    if int(f_pet.get('saciedad', 0)) > 100:
                        salida.append(struct.pack('<HIBBII', 0x001D, f_pet['entidad'], 1, 4, 3796, max(60000, (int(f_pet['saciedad']) - 100) * 60000)))
                try:
                    import casas as _cs_pop
                    _c_own = _cs_pop.obtener_o_crear_casa(p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
                    if p.stage in _cs_pop.MAPAS_EXHIBICION:
                        for _c_act in _cs_pop.casas_en_stage(p.stage):
                            salida.append(_cs_pop.pkt_outdoor_house(
                                _c_act.outdoor_obj_id, _c_act.model_id,
                                _c_act.outdoor_px[0], _c_act.outdoor_px[1],
                                _c_act.house_name, _c_act.owner_name,
                                dir_rot=_c_act.outdoor_dir,
                                house_size_level=_c_act.size_level,
                                house_level=_c_act.level
                            ))
                    if p.stage != 500:
                        _lv, _prev_m, _next_m = _cs_pop.info_nivel(_c_own.calcular_magia())
                        _rnk = _cs_pop.rango_casa(_c_own)
                        _v_rem = 1 if (p.char_id not in _c_own.voted_users_today) else 0
                        _ui_st = 10 if _c_own.is_open else 1
                        salida.append(_cs_pop.pkt_house_info(_lv, _c_own.calcular_magia(), _next_m, _prev_m,
                                                            _c_own.bonus_pct, _c_own.cleanliness,
                                                            _c_own.votes_total, _c_own.votes_today,
                                                            _c_own.visitors_total, _v_rem, _rnk,
                                                            _ui_st))
                        salida.append(_cs_pop.pkt_house_name(_c_own.house_name))
                except Exception:
                    log.exception('casas: fallo al sincronizar casas exteriores/info')
                if p.stage == 500:
                    try:
                        import casas as _cs_in
                        _c_cur = getattr(ses, 'casa_visitando', None)
                        if not _c_cur:
                            _c_cur = _cs_in.obtener_o_crear_casa(p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
                            ses.casa_visitando = _c_cur
                        if (getattr(ses, 'house_furnish_pending', False)
                                and _c_cur.owner_id == p.char_id):
                            salida.extend(_paquetes_ocultar_interactivos_casa())
                            salida.extend(_casa_paquetes_decorar(ses, _c_cur))
                            ses.house_furnish_pending = False
                            ses.house_furnishing = True
                        else:
                            salida.append(_cs_in.pkt_visit_furniture_sync(
                                _c_cur.placed_furniture))
                        _lv, _prev_m, _next_m = _cs_in.info_nivel(_c_cur.calcular_magia())
                        _rnk = _cs_in.rango_casa(_c_cur)
                        _v_rem = 1 if (p.char_id not in _c_cur.voted_users_today) else 0
                        salida.append(_cs_in.pkt_house_info(_lv, _c_cur.calcular_magia(), _next_m, _prev_m,
                                                            _c_cur.bonus_pct, _c_cur.cleanliness,
                                                            _c_cur.votes_total, _c_cur.votes_today,
                                                            _c_cur.visitors_total, _v_rem, _rnk,
                                                            10 if _c_cur.is_open else 1))
                        salida.append(_cs_in.pkt_house_name(_c_cur.house_name))
                    except Exception:
                        log.exception('casas: fallo al enviar estado interior de casa')
                ses.enviar(*salida)
                log.info(f"[{addr}] 0x0002 mapa {p.stage} sincronizado para {p.nombre}")
            return

        # --- combate -----------------------------------------------------
        if opcode == 0x0006 and ses.rol == 'mundo' and cuerpo:
            import combate as _cb
            # Un muerto no pega ni recibe. El cliente sigue repitiendo el
            # ataque con la ventana de muerte abierta, y cada uno hacia que
            # el monstruo contraatacara: por eso seguian saliendo numeros de
            # dano sobre el cadaver.
            if getattr(ses, 'muerto', False) or getattr(ses, 'puesto', None):
                return
            d3 = _cb.parsear_ataque(cuerpo)
            if not d3:
                return
            tipo, objetivo = d3
            tx = getattr(d3, 'tx', 0)
            ty = getattr(d3, 'ty', 0)
            yo = ses.entity_id or 1001

            bichos = getattr(ses, 'monstruos', None) or {}
            m = bichos.get(objetivo)
            arma_puesta = ses.inventario.get(3, 0) if ses.inventario else 0

            mag = _cb.datos_magia(tipo) if tipo != _cb.ATAQUE_NORMAL else {}
            if tipo == 2254 and ses.personaje:
                slot = next((r for r, item in ses.inventario.items() if item == 10581), None)
                if slot is not None:
                    _casa_usar_token(ses, slot)
                return
            es_invocacion = bool(mag.get('es_invocacion'))
            es_terreno = (bool(mag.get('es_terreno')) or (objetivo == 0 and tipo != _cb.ATAQUE_NORMAL)) and not es_invocacion
            es_self_aoe = bool(mag.get('es_self_aoe')) and not es_invocacion
            es_aoe = (es_terreno or es_self_aoe or bool(mag.get('es_aoe'))) and not es_invocacion

            # Comprobacion de alcance
            if es_terreno and ses.personaje:
                _rango_aoe = max(1, mag.get('rango', 12))
                _d = max(abs(tx - ses.personaje.tile_x), abs(ty - ses.personaje.tile_y))
                if _d > _rango_aoe + 2:
                    log.info(f"[{addr}] AOE TERRENO RECHAZADO por alcance: {_d} casillas y el hechizo llega a {_rango_aoe}. "
                             f"jugador ({ses.personaje.tile_x},{ses.personaje.tile_y}) target ({tx},{ty})")
                    return
            elif not es_self_aoe and m is not None and ses.personaje:
                # UN ENCANTADO ES UN ALIADO: no se le pega.
                #
                # El Shining Charm de Earth te pone al bicho de tu lado, y
                # aun asi el golpe basico y las habilidades le entraban y le
                # hacian dano. El servidor ya sabia que estaba encantado --
                # lo mira dos lineas mas abajo para no mandarle las
                # invocaciones encima -- pero no impedia atacarlo, y en los
                # AoE si se filtraba. Aqui se suelta el objetivo y se deja
                # pasar el golpe, para que el cliente no se quede trabado
                # esperando respuesta.
                if getattr(m, 'encantado', False):
                    if getattr(ses, 'objetivo_actual', None) == objetivo:
                        ses.objetivo_actual = None
                    # Se avisa UNA vez por bicho. El cliente no se entera de
                    # que el encantado es aliado y sigue pidiendo el golpe
                    # dos veces por segundo, asi que esto inundaba el log.
                    # Que el cliente deje de apuntarle hace falta saber que
                    # manda el servidor real al encantar, y no hay ni una
                    # captura de Shining Charm entre las 1.214 que tenemos.
                    _avisados = getattr(ses, '_encanto_avisado', None)
                    if _avisados is None:
                        _avisados = set()
                        ses._encanto_avisado = _avisados
                    if objetivo not in _avisados:
                        _avisados.add(objetivo)
                        log.info('[%s] no se ataca al %s: esta encantado y es '
                                 'aliado' % (addr, getattr(m, 'nombre', '?')))
                    return
                # La invocacion y el aliado encantado fijan el objetivo de inmediato si no es un aliado
                if not getattr(m, 'encantado', False):
                    if getattr(ses, 'invocacion', None):
                        ses.invocacion['objetivo'] = m
                    if getattr(ses, 'invocacion2', None):
                        ses.invocacion2['objetivo'] = m
                    if getattr(ses, 'monstruo_encantado', None) and getattr(ses.monstruo_encantado, 'vivo', False):
                        ses.monstruo_encantado.charmed_objetivo = m

                # El alcance sale del arma o de la habilidad, no es 1 fijo:
                # con sable es 1 casilla, con lanza 2 y con arco 12.
                if tipo != _cb.ATAQUE_NORMAL:
                    _rango_arma = max(1, mag.get('rango', 1))
                else:
                    _rango_arma = _cb.alcance_arma(arma_puesta)
                _d = max(abs(m.tile_x - ses.personaje.tile_x),
                         abs(m.tile_y - ses.personaje.tile_y))
                if _d > _rango_arma + 1:
                    log.info(f"[{addr}] GOLPE RECHAZADO por alcance: {_d} "
                             f"casillas y el arma llega a {_rango_arma}. "
                             f"jugador ({ses.personaje.tile_x},"
                             f"{ses.personaje.tile_y}) bicho "
                             f"({m.tile_x},{m.tile_y})")
                    return

            # Ya en rango: cadencia y cooldown
            if m is not None and not es_aoe:
                _obj_act = getattr(ses, 'objetivo_actual', None)
                # Antes, si no habia objetivo fijado, el golpe basico se
                # tiraba a la basura. El objetivo lo fija el 0x0016 accion
                # 0x0c, que el cliente solo repite cada ~1,5 s, asi que
                # cuando el golpe llegaba primero se perdia y el personaje
                # se quedaba "pensandolo" hasta el siguiente reenvio. Con
                # habilidades no pasaba porque esta comprobacion era solo
                # para el ataque normal.
                #
                # No hace falta rechazarlo: la comprobacion de alcance de
                # aqui arriba ya corrio para este mismo bicho y se habria
                # vuelto si estuviera lejos, que era justo de lo que esto
                # pretendia proteger. Asi que se adopta el objetivo y se
                # pega ya.
                if _obj_act is None and tipo == _cb.ATAQUE_NORMAL:
                    ses.objetivo_actual = objetivo
                    _obj_act = objetivo
                if _obj_act != objetivo:
                    ses.objetivo_actual = objetivo

            _ahora_atk = time.time()

            # SIGILO. Las tecnicas de asesino (暗殺型) solo se usan en sigilo, y
            # en sigilo SOLO se usan ellas: es lo que dice Sneak ("Only
            # assassination techniques may be used in stealth mode") y lo que
            # dice Assassination ("Only usable in stealth mode"). Por eso
            # Assassination tiene 1 s de enfriamiento: se encadena DENTRO del
            # sigilo, no lo rompe. Cualquier otra cosa -- un golpe normal u
            # otra habilidad -- te saca de el.
            _en_sigilo = _sigilo_activo(ses, _ahora_atk)
            if mag.get('asesino') and not _en_sigilo:
                log.info(f"[{addr}] {mag.get('nombre')} RECHAZADA: es tecnica de "
                         f"asesino y no estas en sigilo")
                return
            # Solo lo rompe ATACAR: un golpe normal o una habilidad ofensiva que
            # no sea de asesino. Los buffs sobre uno mismo no: el cliente deja
            # lanzarlos en sigilo, y rompiendolo con ellos pasaba esto --
            # Sneak, a los 2 s Energy Accumulation (un buff de SP), sigilo roto
            # y Assassination rechazada.
            _ofensiva = (tipo == _cb.ATAQUE_NORMAL) or bool(mag.get('es_ataque'))
            if _en_sigilo and _ofensiva and not mag.get('asesino'):
                _romper_sigilo(ses, addr, f"por atacar con {mag.get('nombre') or 'un golpe normal'}")

            if tipo != _cb.ATAQUE_NORMAL:
                _cd = max(0.0, mag.get('cd_ms', 0) / 1000.0)
                _usos = getattr(ses, 'ultimo_uso', None)
                if _usos is None:
                    _usos = {}
                    ses.ultimo_uso = _usos
                _espera = _ahora_atk - _usos.get(tipo, 0)
                if _espera < _cd:
                    log.info(f"[{addr}] HABILIDAD {tipo} RECHAZADA: pidio a "
                             f"los {_espera:.3f}s y su cooldown es {_cd:.3f}s")
                    return
                _usos[tipo] = _ahora_atk
            else:
                _cad = _cb.cadencia_ataque(
                    getattr(ses.personaje, 'buffs', None) if ses.personaje else None,
                    getattr(ses.personaje, 'habilidades', None) if ses.personaje else None,
                    duales=lleva_duales_ses(ses),
                    item_id=arma_puesta)
                _espera = _ahora_atk - getattr(ses, 'ultimo_golpe', 0)
                # El cliente pide el siguiente golpe con su propio reloj y
                # llega adelantado por poco: en el log sale pidiendo a 1.03
                # y 1.10 cuando el minimo es 1.15. Tirarlo costaba carisimo,
                # porque el cliente no reintenta enseguida sino a los ~1,5 s
                # y el golpe acababa saliendo a los 2,5 en vez de a 1,15.
                #
                # Asi que si va adelantado por poco se acepta, pero se
                # APUNTA LA DEUDA: ultimo_golpe se deja en el futuro, en el
                # instante que le tocaba, con lo que el siguiente espera lo
                # que no espero este. El ritmo medio sigue siendo la
                # cadencia exacta, solo se mueve la fase. Los golpes que
                # llegan muy pronto se siguen rechazando.
                _margen = _cad * MARGEN_CADENCIA
                if _espera < _cad - _margen:
                    log.info(f"[{addr}] GOLPE RECHAZADO por cadencia: pidio a "
                             f"los {_espera:.3f}s y el minimo es {_cad:.3f}s")
                    return
                if _espera < _cad:
                    ses.ultimo_golpe = _ahora_atk + (_cad - _espera)
                else:
                    ses.ultimo_golpe = _ahora_atk

            # Si es Invocacion (Summon Skeleton, Mummy, Leech, Azrael, Demon, etc.)
            if es_invocacion:
                if getattr(ses, 'sentado', False):
                    ses.sentado = False
                    ses.enviar(struct.pack('<HIII', 0x000A, yo, 0, 0))

                mp_coste = mag.get('mp', 0)
                if ses.personaje and mp_coste > 0:
                    if ses.personaje.mp < mp_coste:
                        log.info(f"[{addr}] MP insuficiente ({ses.personaje.mp}/{mp_coste}) para invocacion {tipo}")
                        return
                    ses.personaje.mp = max(0, ses.personaje.mp - mp_coste)
                    ses.enviar(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))

                cost_sp = mag.get('cost_sp', 0)
                if cost_sp > 0:
                    if getattr(ses, 'sp', 0) < cost_sp:
                        log.info(f"[{addr}] SP insuficiente ({getattr(ses, 'sp', 0)}/{cost_sp}) para invocacion {tipo}")
                        return
                    ses.sp -= cost_sp
                    if ses.personaje:
                        ses.personaje.sp = ses.sp
                    ses.enviar(_cb.atributo(yo, ses.sp, _cb.KIND_SP), _stats_ses(ses))
                _dar_sp(ses, yo, mag, addr)

                cd_ms = mag.get('cd_ms', 2000)
                cast_time = _cb.calcular_cast_time(
                    mag.get('cast_time', 2000),
                    buffs=getattr(ses.personaje, 'buffs', {}),
                    habilidades=getattr(ses.personaje, 'habilidades', None),
                    es_magia=True
                )
                ef = _cb.efecto_de_ataque(tipo) or mag.get('efecto', 9)

                # Comprobar si tiene el buff Duo Summon (5136..5140) activo
                duo_summon_activo = False
                if ses.personaje and getattr(ses.personaje, 'buffs', None):
                    _now_ds = time.time()
                    for _bid, _bdata in list(ses.personaje.buffs.items()):
                        try:
                            _bid_int = int(_bid)
                        except (TypeError, ValueError):
                            continue
                        if 5136 <= _bid_int <= 5140:
                            if not isinstance(_bdata, dict) or _bdata.get('fin', _now_ds + 1) > _now_ds:
                                duo_summon_activo = True
                                break

                if duo_summon_activo:
                    if getattr(ses, 'invocacion', None) and not getattr(ses, 'invocacion2', None):
                        summon_slot = 'invocacion2'
                        summon_eid = yo + 8001 if ses.invocacion.get('entity_id') != yo + 8001 else yo + 8000
                    elif not getattr(ses, 'invocacion', None):
                        summon_slot = 'invocacion'
                        _eid2 = ses.invocacion2.get('entity_id') if getattr(ses, 'invocacion2', None) else 0
                        summon_eid = yo + 8000 if _eid2 != yo + 8000 else yo + 8001
                    else:
                        old_eid = ses.invocacion['entity_id']
                        ses.enviar(_cb.atributo(old_eid, 0, _cb.KIND_HP),
                                   _cb.despawn_monstruo(old_eid))
                        ses.invocacion = ses.invocacion2
                        summon_slot = 'invocacion2'
                        summon_eid = yo + 8000 if ses.invocacion.get('entity_id') != yo + 8000 else yo + 8001
                else:
                    if getattr(ses, 'invocacion', None):
                        old_eid = ses.invocacion['entity_id']
                        ses.enviar(_cb.atributo(old_eid, 0, _cb.KIND_HP),
                                   _cb.despawn_monstruo(old_eid),
                                   struct.pack('<HIBBI', 0x0013, yo, 1, 0x3d, 0))
                        ses.invocacion = None
                    if getattr(ses, 'invocacion2', None):
                        old_eid2 = ses.invocacion2['entity_id']
                        ses.enviar(_cb.atributo(old_eid2, 0, _cb.KIND_HP),
                                   _cb.despawn_monstruo(old_eid2),
                                   struct.pack('<HIBBI', 0x0013, yo, 1, 0x3d, 0))
                        ses.invocacion2 = None
                    summon_slot = 'invocacion'
                    summon_eid = yo + 8000

                npc_t = mag.get('invoca_npc')
                info_inv = _cb.datos_invocacion(npc_t)

                # Coordenadas donde se invoca: si es totem, siempre a los pies del jugador; sino tx, ty o al lado
                es_totem = 'totem' in str(info_inv.get('nombre', '')).lower() or (info_inv.get('move_speed', 70) or 0) <= 0
                if es_totem and ses.personaje:
                    stx, sty = ses.personaje.tile_x, ses.personaje.tile_y
                elif tx > 0 and ty > 0 and ses.personaje and max(abs(tx - ses.personaje.tile_x), abs(ty - ses.personaje.tile_y)) <= 14:
                    stx, sty = tx, ty
                else:
                    _off_sx = -1 if summon_slot == 'invocacion2' else 1
                    stx = (ses.personaje.tile_x + _off_sx) if ses.personaje else tx
                    sty = ses.personaje.tile_y if ses.personaje else ty

                dur_s = mag.get('dur_invoca', 3600)
                setattr(ses, summon_slot, {
                    'entity_id': summon_eid,
                    'npc_type': npc_t,
                    'nombre': info_inv['nombre'],
                    'sprite': info_inv['sprite'],
                    'hp': info_inv['hp'],
                    'hp_max': info_inv['hp'],
                    'atk': info_inv['atk'],
                    'defensa': info_inv['def'],
                    'matk': info_inv.get('matk', 0),
                    'mdef': info_inv.get('mdef', 0),
                    'level': info_inv.get('level', 1),
                    'accuracy': info_inv.get('accuracy', 50),
                    'agility': info_inv.get('agility', 50),
                    'crit_rate': info_inv.get('crit_rate', 5),
                    'atk_range': 8 if es_totem else info_inv.get('atk_range', 1),
                    'move_speed': 0 if es_totem else info_inv.get('move_speed', 70),
                    'atk_speed': info_inv.get('atk_speed', 70),
                    'skills': info_inv.get('skills', []),
                    'tile_x': stx,
                    'tile_y': sty,
                    'expira': time.time() + dur_s,
                    'objetivo': None,
                    'ultimo_ataque': 0.0,
                    'proximo_paso': 0.0,
                })

                import login as _lg
                spawn_pkg = _lg.spawn_invocacion(summon_eid, npc_t, info_inv['nombre'], (stx, sty), sprite=info_inv['sprite'])
                hp_pkg = _cb.atributo(summon_eid, 100, _cb.KIND_HP)
                # Confirmar cast sobre el suelo (target=0, stx, sty) para que el ataud NO salga sobre la cabeza del jugador
                atk_confirm = _cb.confirmar_cast(0, stx, sty)

                # Paquetes iniciales: confirmacion al suelo, efecto del ataud unicamente en (stx, sty), GCD
                ses.enviar(
                    atk_confirm,
                    _cb.numero_de_dano(yo, 0, 0, ataque=tipo, efecto=ef, cast_time=cast_time, es_magia=True, tile_x=stx, tile_y=sty),
                    _cb.gcd_paquete()
                )

                def _fin_invoca():
                    if not ses.personaje or getattr(ses, 'muerto', False):
                        return
                    pkgs_inv = [
                        _cb.cierre_de_dano(yo, 0, ataque=tipo, efecto=ef, es_magia=True, tile_x=stx, tile_y=sty),
                        struct.pack('<HIBBI', 0x0013, yo, 1, 0x3d, summon_eid),
                        struct.pack('<HIBBII', 0x001D, yo, 1, 0x2a, summon_eid, 0),
                        spawn_pkg,
                        hp_pkg,
                        struct.pack('<HIBBI', 0x0013, summon_eid, 1, 0x3c, yo),
                    ]
                    if cd_ms > 0:
                        _sk_ids_copia = _cb.grupo_de(tipo)
                        for sk_id in _sk_ids_copia:
                            pkgs_inv.append(struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, cd_ms))
                        asyncio.get_event_loop().call_later(cd_ms / 1000.0, lambda: ses.enviar_inmediato(*[
                            struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, 0) for sk_id in _sk_ids_copia
                        ]))

                    pkgs_inv.extend(_otorgar_skill_exp(ses, ses.personaje, yo, magic_id=tipo))
                    ses.enviar_inmediato(*pkgs_inv)
                    import presencia as _pr
                    _pr.notificar_invocacion_spawn(ses, getattr(ses, 'invocacion', None) or getattr(ses, 'invocacion2', None), spawn_pkg, hp_pkg)

                _ret_inv = max(0.14, min(2.5, cast_time / 1000.0))
                asyncio.get_event_loop().call_later(_ret_inv, _fin_invoca)

                if getattr(ses, 'usuario', None):
                    cuentas.guardar_progreso(ses.usuario, ses.personaje.char_id,
                                             ses.personaje.nivel, ses.personaje.exp,
                                             ses.personaje.hp, ses.personaje.mp,
                                             ses.personaje.habilidades,
                                             hp_max=ses.personaje.hp_max, mp_max=ses.personaje.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)
                log.info(f"[{addr}] invocacion {info_inv['nombre']} (npc_type {npc_t}, sprite {info_inv['sprite']}) invocada para jugador {yo} en ({stx},{sty})")
                return

            # Si es AOE (Ground AOE o Self AOE), ejecutarlo directamente
            if es_aoe:
                if getattr(ses, 'sentado', False):
                    ses.sentado = False
                    ses.enviar(struct.pack('<HIII', 0x000A, yo, 0, 0))

                cost_sp = mag.get('cost_sp', 0)
                if cost_sp > 0:
                    if getattr(ses, 'sp', 0) < cost_sp:
                        log.info(f"[{addr}] SP insuficiente ({getattr(ses, 'sp', 0)}/{cost_sp}) para AOE {tipo}")
                        return
                    ses.sp -= cost_sp
                    if ses.personaje:
                        ses.personaje.sp = ses.sp
                    ses.enviar(_cb.atributo(yo, ses.sp, _cb.KIND_SP), _stats_ses(ses))
                _dar_sp(ses, yo, mag, addr)

                mp_coste = mag.get('mp', 0)
                if ses.personaje and mp_coste > 0:
                    if ses.personaje.mp < mp_coste:
                        log.info(f"[{addr}] MP insuficiente ({ses.personaje.mp}/{mp_coste}) para AOE {tipo}")
                        return
                    ses.personaje.mp = max(0, ses.personaje.mp - mp_coste)
                    ses.enviar(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))

                cd_ms = mag.get('cd_ms', 1000)
                if cd_ms > 0 and ses.personaje:
                    _sk_ids_copia = _cb.grupo_de(tipo)
                    cd_pkgs = [struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, cd_ms)
                               for sk_id in _sk_ids_copia]
                    ses.enviar(*cd_pkgs, _cb.gcd_paquete())
                    try:
                        asyncio.get_event_loop().call_later(cd_ms / 1000.0,
                            lambda ids=_sk_ids_copia: ses.enviar_inmediato(*[
                                struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, 0)
                                for sk_id in ids
                            ]))
                    except Exception:
                        pass

                import skills as _sk_mod
                import inventario as _iv
                is_magic_skill = bool(_sk_mod.skill_de_magia(tipo) in (1, 2, 3, 4))
                ef = _cb.efecto_de_ataque(tipo)
                cast_time = _cb.calcular_cast_time(
                    mag.get('cast_time', 100),
                    buffs=getattr(ses.personaje, 'buffs', {}),
                    habilidades=getattr(ses.personaje, 'habilidades', None),
                    es_magia=is_magic_skill
                )

                if es_self_aoe:
                    target_ent = yo
                    cx = ses.personaje.tile_x if ses.personaje else 0
                    cy = ses.personaje.tile_y if ses.personaje else 0
                    tile_ef_x = 0
                    tile_ef_y = 0
                elif m is not None:
                    target_ent = m.entity_id
                    cx = m.tile_x
                    cy = m.tile_y
                    tile_ef_x = 0
                    tile_ef_y = 0
                else:
                    target_ent = 0
                    cx = tx
                    cy = ty
                    if (cx <= 0 or cy <= 0) and ses.personaje:
                        _px, _py = ses.personaje.tile_x, ses.personaje.tile_y
                        _cercanos = [b for b in bichos.values() if b.vivo and max(abs(b.tile_x - _px), abs(b.tile_y - _py)) <= max(12, mag.get('rango', 12))]
                        if _cercanos:
                            _b_min = min(_cercanos, key=lambda b: max(abs(b.tile_x - _px), abs(b.tile_y - _py)))
                            cx, cy = _b_min.tile_x, _b_min.tile_y
                        else:
                            cx, cy = _px, _py
                    tile_ef_x = cx
                    tile_ef_y = cy

                area = max(1, mag.get('area', 1))
                # Si es de "varios golpes individuales en el area", lo que se ve
                # caer sobre cada objetivo es su hechizo hijo: Spear Shower V
                # marca la zona con el 511 y las lanzas son el 493 del 13374.
                # Sin esto solo salian los numeros de dano, sin las lanzas.
                _hijo_area = int(mag.get('hijo_area') or 0)
                _ef_hijo_id = _cb.efecto_de_ataque(_hijo_area) if _hijo_area else 0

                def _ef_hijo(eid):
                    if not _hijo_area or not _ef_hijo_id:
                        return ()
                    return (_cb.numero_de_dano(yo, eid, dano=0, ataque=_hijo_area,
                                               efecto=_ef_hijo_id, cast_time=0,
                                               es_magia=is_magic_skill),
                            _cb.cierre_de_dano(yo, eid, ataque=_hijo_area,
                                               efecto=_ef_hijo_id,
                                               es_magia=is_magic_skill))
                _ef2 = _cb.efecto_secundario(tipo)

                def _fin_aoe(enviar_cierre=True):
                    if not ses.personaje or getattr(ses, 'muerto', False):
                        return
                    if enviar_cierre:
                        ses.enviar_inmediato(
                            _cb.cierre_de_dano(yo, target_ent, ataque=tipo, efecto=ef,
                                               es_magia=is_magic_skill, tile_x=tile_ef_x, tile_y=tile_ef_y)
                        )

                    # Dimension Shift (13595..13599): Teletransportacion instantanea (en tiles!) y explosion electrica de impacto
                    if 13595 <= tipo <= 13599 and cx > 0 and cy > 0 and ses.personaje:
                        ses.personaje.tile_x, ses.personaje.tile_y = cx, cy
                        MOVE_P = Msg.registry[(0x0005, 's2c', '*')]
                        _ef_ds = mag.get('sub_efecto', 519)
                        _sub_id = 13600 + (tipo - 13595)
                        ses.enviar_inmediato(
                            struct.pack('<HIII', 0x0003, yo, cx, cy),
                            MOVE_P.build(entity_id=yo, cur_x=cx * 32, cur_y=cy * 32, dst_x=cx * 32, dst_y=cy * 32, speed=1000),
                            _cb.numero_de_dano(yo, yo, dano=0, ataque=_sub_id, efecto=_ef_ds, cast_time=0, es_magia=True),
                            _cb.cierre_de_dano(yo, yo, ataque=_sub_id, efecto=_ef_ds, es_magia=True),
                        )

                    blancos = [b for b in bichos.values() if b.vivo and max(abs(b.tile_x - cx), abs(b.tile_y - cy)) <= area]

                    if blancos:
                        habs = ses.personaje.habilidades if ses.personaje else None
                        buffs_activos = getattr(ses.personaje, 'buffs', None)
                        st = _iv.stats(ses.inventario, habs, buffs=buffs_activos, mejoras=_mejoras_de(ses))
                        if is_magic_skill:
                            ataque = struct.unpack_from('<I', st, 2 + 44)[0]
                            dano_base = mag.get('dano_base', 0)
                            denom = mag.get('base_denom', 200) or 200
                            mult_spell = (dano_base / float(denom)) if dano_base > 0 else 1.0
                            coef = mag.get('dano_coef', 0)
                            if coef > 0:
                                mult_spell *= (coef / 100.0)
                            dano_var = mag.get('dano_var', 0)
                            var_pct = min(0.15, max(0.02, dano_var / float(denom))) if dano_var > 0 else 0.05
                        else:
                            ataque = struct.unpack_from('<I', st, 2 + 20 + 4)[0]
                            stance = _cb.stance_de(tipo)
                            dano_extra = int(round(stance * _cb.PESO_STANCE))
                            ataque += dano_extra
                            denom = mag.get('base_denom', 200) or 200
                            dano_base = mag.get('dano_base', 0)
                            _cb_aoe_info = _cb.combo_de(tipo)
                            es_combo_aoe = bool(_cb_aoe_info and _cb_aoe_info.get('golpes', 1) > 1)
                            if es_combo_aoe:
                                mult_spell = 1.2
                            else:
                                mult_spell = 1.35
                            coef = mag.get('dano_coef', 0)
                            if coef > 0:
                                mult_spell *= (coef / 100.0)
                            var_pct = 0.03

                        mods_eq = _iv.modificadores_porcentuales_equipo(ses.inventario)
                        _clave_pct = 'mag_dmg_pct' if is_magic_skill else 'phys_dmg_pct'
                        if mods_eq.get(_clave_pct, 0) > 0:
                            mult_spell *= (1.0 + mods_eq[_clave_pct] / 100.0)
                        _pct_buffs = _cb.pct_dano_buffs(buffs_activos, is_magic_skill)
                        if _pct_buffs:
                            mult_spell *= (1.0 + _pct_buffs / 100.0)

                        extra_crit = 0
                        if buffs_activos:
                            now = time.time()
                            for b_id, b_data in list(buffs_activos.items()):
                                if isinstance(b_data, dict) and b_data.get('fin', 0) > now and 'crit' in b_data:
                                    extra_crit += b_data['crit']
                        crit_prob = min(0.90, (critico_jugador(ses) + extra_crit) / 100.0)

                        _combo_aoe = _cb.combo_de(tipo)
                        _formula_str = str(mag.get('formula') or mag.get('公式') or '')
                        es_ricochet = bool(_combo_aoe and _combo_aoe.get('es_ricochet'))
                        es_barrage = (_formula_str == '36') or bool(_combo_aoe and not es_ricochet and 'random' in mag.get('desc', '').lower())

                        if es_barrage:
                            # Rafaga aleatoria en area (Steel Rain, Sword of Kings, Quake Spear, Flaming Blade Rain, etc.)
                            # Distribuye N golpes aleatorios entre los enemigos vivos del area.
                            _golpes_aoe = _combo_aoe.get('golpes', 1) if _combo_aoe else 1
                            _sep_aoe = max(0.08, _combo_aoe.get('intervalo_ms', 200) / 1000.0) if _combo_aoe else 0.2
                            vivos_ini = [b for b in blancos if getattr(b, 'vivo', False) and not getattr(b, 'encantado', False)]
                            if vivos_ini:
                                b_primero = random.choice(vivos_ini)
                                es_crit = (random.random() < crit_prob)
                                mult_crit = 1.5 if es_crit else 1.0
                                dano = b_primero.recibir(ataque, es_magico=is_magic_skill, mult=mult_spell * mult_crit, var_pct=var_pct)
                                pkg_debuff = []
                                if _ef2 and random.randint(1, 100) <= _ef2.get('prob', 100):
                                    b_primero.aplicar_efecto(_ef2)
                                    if _ef2.get('magia') and _ef2.get('dur_ms'):
                                        pkg_debuff.append(struct.pack('<HIBBII', 0x001D, b_primero.entity_id, 1, 4, _ef2['magia'], _ef2['dur_ms']))
                                    if _ef2.get('sub_debuff'):
                                        pkg_debuff.append(struct.pack('<HIBBII', 0x001D, b_primero.entity_id, 1, 4, _ef2['sub_debuff'], _ef2.get('dur_ms', 5000)))
                                _tipo_num = _cb.TIPO_DANO_CRITICO if es_crit else _cb.TIPO_DANO
                                ses.enviar_inmediato(
                                    _cb.atributo(b_primero.entity_id, b_primero.porcentaje),
                                    _cb.numero_flotante(b_primero.entity_id, dano, _tipo_num),
                                    *pkg_debuff
                                )
                                if not b_primero.vivo:
                                    _procesar_muerte_monstruo(ses, b_primero, yo, addr, espera=0.0)
                                elif b_primero.en_combate_con != yo:
                                    b_primero.en_combate_con = yo

                            for _gk in range(1, _golpes_aoe):
                                def _subgolpe_barrage(k_idx=_gk):
                                    if not ses.personaje or getattr(ses, 'muerto', False):
                                        return
                                    vivos = [b for b in blancos if getattr(b, 'vivo', False) and not getattr(b, 'encantado', False)]
                                    if not vivos:
                                        return
                                    tgt = random.choice(vivos)
                                    _c_k = random.random() < crit_prob
                                    _mult_k = mult_spell * (1.5 if _c_k else 1.0)
                                    _d_k = tgt.recibir(ataque, es_magico=is_magic_skill, mult=_mult_k, var_pct=var_pct)
                                    if not _d_k:
                                        return
                                    _tipo_num_k = _cb.TIPO_DANO_CRITICO if _c_k else _cb.TIPO_DANO
                                    ses.enviar_inmediato(
                                        _cb.atributo(tgt.entity_id, tgt.porcentaje),
                                        _cb.numero_flotante(tgt.entity_id, _d_k, _tipo_num_k), *_ef_hijo(tgt.entity_id),
                                    )
                                    if not tgt.vivo:
                                        _procesar_muerte_monstruo(ses, tgt, yo, addr, espera=0.0)
                                    elif tgt.en_combate_con != yo:
                                        tgt.en_combate_con = yo
                                try:
                                    asyncio.get_event_loop().call_later(_sep_aoe * _gk, _subgolpe_barrage)
                                except Exception:
                                    pass

                        elif es_ricochet:
                            # Tornado AoE inicial que golpea a todos + rebotes individuales (Windbreaker Arrow I..V)
                            for b in blancos:
                                if not b.vivo or getattr(b, 'encantado', False):
                                    continue
                                es_crit = (random.random() < crit_prob)
                                mult_crit = 1.5 if es_crit else 1.0
                                dano = b.recibir(ataque, es_magico=is_magic_skill, mult=mult_spell * mult_crit, var_pct=var_pct)
                                pkg_debuff = []
                                if _ef2 and random.randint(1, 100) <= _ef2.get('prob', 100):
                                    b.aplicar_efecto(_ef2)
                                    if _ef2.get('magia') and _ef2.get('dur_ms'):
                                        pkg_debuff.append(struct.pack('<HIBBII', 0x001D, b.entity_id, 1, 4, _ef2['magia'], _ef2['dur_ms']))
                                    if _ef2.get('sub_debuff'):
                                        pkg_debuff.append(struct.pack('<HIBBII', 0x001D, b.entity_id, 1, 4, _ef2['sub_debuff'], _ef2.get('dur_ms', 5000)))
                                _tipo_num = _cb.TIPO_DANO_CRITICO if es_crit else _cb.TIPO_DANO
                                ses.enviar_inmediato(
                                    _cb.atributo(b.entity_id, b.porcentaje),
                                    _cb.numero_flotante(b.entity_id, dano, _tipo_num), *_ef_hijo(b.entity_id),
                                    *pkg_debuff
                                )
                                if not b.vivo:
                                    _procesar_muerte_monstruo(ses, b, yo, addr, espera=0.0)
                                elif b.en_combate_con != yo:
                                    b.en_combate_con = yo

                            _golpes_aoe = _combo_aoe.get('golpes', 1) if _combo_aoe else 1
                            _sep_aoe = max(0.08, _combo_aoe.get('intervalo_ms', 200) / 1000.0) if _combo_aoe else 0.2
                            for _gk in range(1, _golpes_aoe + 1):
                                def _subgolpe_ricochet(k_idx=_gk):
                                    if not ses.personaje or getattr(ses, 'muerto', False):
                                        return
                                    vivos = [b for b in blancos if getattr(b, 'vivo', False) and not getattr(b, 'encantado', False)]
                                    if not vivos:
                                        return
                                    tgt = random.choice(vivos)
                                    _c_k = random.random() < crit_prob
                                    _mult_k = mult_spell * (1.5 if _c_k else 1.0)
                                    _d_k = tgt.recibir(ataque, es_magico=is_magic_skill, mult=_mult_k, var_pct=var_pct)
                                    if not _d_k:
                                        return
                                    _tipo_num_k = _cb.TIPO_DANO_CRITICO if _c_k else _cb.TIPO_DANO
                                    ses.enviar_inmediato(
                                        _cb.atributo(tgt.entity_id, tgt.porcentaje),
                                        _cb.numero_flotante(tgt.entity_id, _d_k, _tipo_num_k), *_ef_hijo(tgt.entity_id),
                                    )
                                    if not tgt.vivo:
                                        _procesar_muerte_monstruo(ses, tgt, yo, addr, espera=0.0)
                                    elif tgt.en_combate_con != yo:
                                        tgt.en_combate_con = yo
                                try:
                                    asyncio.get_event_loop().call_later(_sep_aoe * _gk, _subgolpe_ricochet)
                                except Exception:
                                    pass

                        else:
                            for b in blancos:
                                if not b.vivo or getattr(b, 'encantado', False):
                                    continue
                                es_crit = (random.random() < crit_prob)
                                mult_crit = 1.5 if es_crit else 1.0
                                dano = b.recibir(ataque, es_magico=is_magic_skill, mult=mult_spell * mult_crit, var_pct=var_pct)
                                pkg_debuff = []
                                if _ef2 and random.randint(1, 100) <= _ef2.get('prob', 100):
                                    b.aplicar_efecto(_ef2)
                                    if _ef2.get('magia') and _ef2.get('dur_ms'):
                                        pkg_debuff.append(struct.pack('<HIBBII', 0x001D, b.entity_id, 1, 4, _ef2['magia'], _ef2['dur_ms']))
                                    if _ef2.get('sub_debuff'):
                                        pkg_debuff.append(struct.pack('<HIBBII', 0x001D, b.entity_id, 1, 4, _ef2['sub_debuff'], _ef2.get('dur_ms', 5000)))
                                _tipo_num = _cb.TIPO_DANO_CRITICO if es_crit else _cb.TIPO_DANO
                                ses.enviar_inmediato(
                                    _cb.atributo(b.entity_id, b.porcentaje),
                                    _cb.numero_flotante(b.entity_id, dano, _tipo_num), *_ef_hijo(b.entity_id),
                                    *pkg_debuff
                                )
                                if not b.vivo:
                                    _procesar_muerte_monstruo(ses, b, yo, addr, espera=0.0)
                                elif b.en_combate_con != yo:
                                    b.en_combate_con = yo

                            if _combo_aoe and _combo_aoe.get('golpes', 1) > 1:
                                _golpes_aoe = _combo_aoe['golpes']
                                _sep_aoe = max(0.08, _combo_aoe.get('intervalo_ms', 200) / 1000.0)
                                for _gk in range(1, _golpes_aoe):
                                    def _subgolpe_aoe(k_idx=_gk):
                                        if not ses.personaje or getattr(ses, 'muerto', False):
                                            return
                                        vivos = [b for b in blancos if getattr(b, 'vivo', False) and not getattr(b, 'encantado', False)]
                                        if not vivos:
                                            return
                                        for tgt in vivos:
                                            _c_k = random.random() < crit_prob
                                            _mult_k = mult_spell * (1.5 if _c_k else 1.0)
                                            _d_k = tgt.recibir(ataque, es_magico=is_magic_skill, mult=_mult_k, var_pct=var_pct)
                                            if not _d_k:
                                                continue
                                            _tipo_num_k = _cb.TIPO_DANO_CRITICO if _c_k else _cb.TIPO_DANO
                                            ses.enviar_inmediato(
                                                _cb.atributo(tgt.entity_id, tgt.porcentaje),
                                                _cb.numero_flotante(tgt.entity_id, _d_k, _tipo_num_k), *_ef_hijo(tgt.entity_id),
                                            )
                                            if not tgt.vivo:
                                                _procesar_muerte_monstruo(ses, tgt, yo, addr, espera=0.0)
                                            elif tgt.en_combate_con != yo:
                                                tgt.en_combate_con = yo
                                    try:
                                        asyncio.get_event_loop().call_later(_sep_aoe * _gk, _subgolpe_aoe)
                                    except Exception:
                                        pass

                        _b_proc_t = next((b for b in blancos if getattr(b, 'vivo', False)), blancos[0])
                        _pkgs_tr_aoe = _procesar_triggers_buffs(ses, yo, _b_proc_t, addr=addr, en_ataque=True)
                        if _pkgs_tr_aoe:
                            ses.enviar_inmediato(*_pkgs_tr_aoe)

                    ses.enviar_inmediato(*_otorgar_skill_exp(ses, ses.personaje, yo, magic_id=tipo))

                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_progreso(ses.usuario, ses.personaje.char_id,
                                                 ses.personaje.nivel, ses.personaje.exp,
                                                 ses.personaje.hp, ses.personaje.mp,
                                                 ses.personaje.habilidades,
                                                 hp_max=ses.personaje.hp_max, mp_max=ses.personaje.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)

                if cast_time <= 0:
                    ses.enviar(
                        _cb.confirmar_cast(target_ent, cx, cy),
                        _cb.numero_de_dano(yo, target_ent, dano=0, ataque=tipo, efecto=ef,
                                           cast_time=0, es_magia=is_magic_skill,
                                           tile_x=tile_ef_x, tile_y=tile_ef_y),
                        _cb.cierre_de_dano(yo, target_ent, ataque=tipo, efecto=ef,
                                           es_magia=is_magic_skill, tile_x=tile_ef_x, tile_y=tile_ef_y)
                    )
                    _fin_aoe(enviar_cierre=False)
                else:
                    ses.enviar(
                        _cb.confirmar_cast(target_ent, cx, cy),
                        _cb.numero_de_dano(yo, target_ent, dano=0, ataque=tipo, efecto=ef,
                                           cast_time=cast_time, es_magia=is_magic_skill,
                                           tile_x=tile_ef_x, tile_y=tile_ef_y)
                    )
                    ret_aoe = max(0.1, cast_time / 1000.0)
                    try:
                        asyncio.get_event_loop().call_later(ret_aoe, _fin_aoe)
                    except Exception:
                        _fin_aoe()

                log.info(f"[{addr}] AOE {tipo} ({mag.get('nombre')}) ejecutado en ({cx},{cy}) radio={area} cast_time={cast_time}ms")
                return

            # Si se uso una habilidad de ataque sin objetivo fijado y NO es AOE, auto-fijar el monstruo mas cercano
            if m is None and not es_aoe and tipo != _cb.ATAQUE_NORMAL and ses.personaje:
                mag_check = _cb.datos_magia(tipo)
                if mag_check.get('es_ataque'):
                    r_max = max(2, mag_check.get('rango', 1))
                    cands = [b for b in bichos.values() if b.vivo and max(abs(b.tile_x - ses.personaje.tile_x), abs(b.tile_y - ses.personaje.tile_y)) <= r_max]
                    if cands:
                        m = min(cands, key=lambda b: max(abs(b.tile_x - ses.personaje.tile_x), abs(b.tile_y - ses.personaje.tile_y)))
                        objetivo = m.entity_id

            if m is None:
                # Habilidad activa sobre uno mismo (F1, F2, F3, buffs o curaciones)
                if tipo != _cb.ATAQUE_NORMAL or objetivo == yo:
                    mag = _cb.datos_magia(tipo)
                    # Si es una habilidad pasiva, ignorar (no se castea activamente en la barra)
                    if mag.get('es_pasiva'):
                        return
                    # Si es una habilidad de ataque, no se puede autocastear
                    if mag.get('es_ataque'):
                        log.info(f"[{addr}] HABILIDAD {tipo} SIN OBJETIVO: el "
                                 f"cliente pidio '{mag.get('nombre')}' con "
                                 f"objetivo {objetivo}, que no es ningun "
                                 f"monstruo de este mapa, y no hay ninguno a "
                                 f"tiro. No se hace nada.")
                        return

                    # Si estaba sentado, levantarse antes de ejecutar habilidad
                    if getattr(ses, 'sentado', False):
                        ses.sentado = False
                        ses.enviar(struct.pack('<HIII', 0x000A, yo, 0, 0))

                    cost_sp = mag.get('cost_sp', 0)
                    if cost_sp > 0:
                        if getattr(ses, 'sp', 0) < cost_sp:
                            log.info(f"[{addr}] SP insuficiente ({getattr(ses, 'sp', 0)}/{cost_sp}) para habilidad {tipo}")
                            return
                        ses.sp -= cost_sp
                        if ses.personaje:
                            ses.personaje.sp = ses.sp
                        ses.enviar(_cb.atributo(yo, ses.sp, _cb.KIND_SP), _stats_ses(ses))
                    _dar_sp(ses, yo, mag, addr)

                    mp_coste = mag.get('mp', 0)
                    if ses.personaje and mp_coste > 0:
                        if ses.personaje.mp < mp_coste:
                            log.info(f"[{addr}] MP insuficiente ({ses.personaje.mp}/{mp_coste}) para habilidad {tipo}")
                            return
                        ses.personaje.mp = max(0, ses.personaje.mp - mp_coste)

                    ef = _cb.efecto_de_ataque(tipo)
                    cd_ms = mag.get('cd_ms', 2000)
                    dur_ms = mag.get('dur_ms', 0)
                    cast_time = _cb.calcular_cast_time(
                        mag.get('cast_time', 100),
                        buffs=getattr(ses.personaje, 'buffs', {}),
                        habilidades=getattr(ses.personaje, 'habilidades', None),
                        es_magia=True
                    )
                    import clases as _cl
                    import inventario as _iv
                    import mascotas as _ms

                    f_pet_cast = getattr(ses.personaje, 'mascota', None) if ses.personaje else None
                    pet_eid_cast = getattr(ses, 'pet_entity_id', None) or (f_pet_cast.get('entidad') if isinstance(f_pet_cast, dict) else None)
                    pet_out_cast = bool(isinstance(f_pet_cast, dict) and f_pet_cast.get('fuera') and pet_eid_cast)
                    es_target_pet = bool(pet_out_cast and objetivo == int(pet_eid_cast) and not mag.get('es_transformacion'))

                    # 1a. Curacion POR TICS (Injury Cure: 15 HP cada 5 s
                    # durante 11; Earth Blessing: 對象="角色").
                    _tic = _cb.cura_por_tics(tipo)
                    if _tic and ses.personaje:
                        def _curar_tic(n=0, a_pet=es_target_pet):
                            if not ses.personaje or getattr(ses, 'muerto', False):
                                return
                            pkgs_tic = []
                            if a_pet:
                                fp_t = getattr(ses.personaje, 'mascota', None)
                                peid_t = getattr(ses, 'pet_entity_id', None)
                                if isinstance(fp_t, dict) and fp_t.get('fuera') and peid_t and _tic['hp'] > 0:
                                    antes_hp_p = int(fp_t.get('hp') or 0)
                                    tope_hp_p = int(fp_t.get('hp_max') or 100)
                                    fp_t['hp'] = min(tope_hp_p, antes_hp_p + _tic['hp'])
                                    san_p = fp_t['hp'] - antes_hp_p
                                    if san_p > 0:
                                        pkgs_tic.extend((
                                            _cb.numero_flotante(int(peid_t), san_p, _cb.TIPO_CURA_HP),
                                            _cb.atributo(int(peid_t), _ms.hp_eff(fp_t), _cb.KIND_HP),
                                            _ms.armar(fp_t),
                                        ))
                            else:
                                antes_hp = ses.personaje.hp
                                antes_mp = ses.personaje.mp
                                hp_tope = _vida_max(ses.personaje, ses.inventario)
                                mp_tope = _mana_max(ses.personaje, ses.inventario)
                                ses.personaje.hp = min(
                                    hp_tope,
                                    ses.personaje.hp + _tic['hp'])
                                ses.personaje.mp = min(
                                    mp_tope,
                                    ses.personaje.mp + _tic['mp'])
                                sanado_hp = ses.personaje.hp - antes_hp
                                sanado_mp = ses.personaje.mp - antes_mp
                                log.debug(
                                    f"[{addr}] {mag.get('nombre')} tic "
                                    f"{n + 1}/{_tic['tics']}: "
                                    f"HP {antes_hp}->{ses.personaje.hp}/{hp_tope} "
                                    f"(+{sanado_hp}), MP {antes_mp}->"
                                    f"{ses.personaje.mp}/{mp_tope} (+{sanado_mp})")
                                if sanado_hp > 0:
                                    pkgs_tic.extend((
                                        _cb.numero_flotante(yo, sanado_hp,
                                                            _cb.TIPO_CURA_HP),
                                        _cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP)))
                                if sanado_mp > 0:
                                    pkgs_tic.extend((
                                        _cb.numero_flotante(yo, sanado_mp,
                                                            _cb.TIPO_CURA_MP),
                                        _cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP)))
                            if pkgs_tic:
                                ses.enviar_inmediato(*pkgs_tic)
                            if n + 1 < _tic['tics']:
                                try:
                                    asyncio.get_event_loop().call_later(
                                        _tic['intervalo'],
                                        lambda: _curar_tic(n + 1, a_pet=a_pet))
                                except Exception:
                                    pass
                        _curar_tic()
                        _detalle_tics = []
                        if _tic['hp']:
                            _detalle_tics.append(f"{_tic['hp']} HP")
                        if _tic['mp']:
                            _detalle_tics.append(f"{_tic['mp']} MP")
                        log.info(f"[{addr}] {mag.get('nombre')}: recupera "
                                 f"{' y '.join(_detalle_tics)} x{_tic['tics']} "
                                 f"cada {_tic['intervalo']}s (target_pet={es_target_pet})")

                    # 2. Habilidad de curacion real (Cure Spell de mago, Holy Light, etc.)
                    if mag.get('es_cura') and ses.personaje and not _tic:
                        cura = max(10, abs(mag.get('hp', 0)))
                        # A otro jugador (角色 con el pinchado) o en area a los
                        # del grupo (自己/隊伍 con radio), como los buffs.
                        _otros_c, _a_mi_c = (([], True) if es_target_pet
                                             else _receptores_de_buff(ses, tipo, objetivo, mag.get('area')))
                        for _s_c in _otros_c:
                            try:
                                _p_c = _s_c.personaje
                                _p_c.hp = min(_vida_max(_p_c, _s_c.inventario), _p_c.hp + cura)
                                import presencia as _pr_cu
                                _pub_c = _pr_cu.entidad_de(ses)
                                _s_c.enviar_inmediato(
                                    _cb.efecto_curacion_inicio(_pub_c, _p_c.entity_id, cura, efecto=ef),
                                    _cb.efecto_curacion_fin(_pub_c, _p_c.entity_id, efecto=ef),
                                    _cb.numero_flotante(_p_c.entity_id, cura, _cb.TIPO_CURA_HP),
                                    _cb.atributo(_p_c.entity_id, _p_c.hp, _cb.KIND_HP))
                            except Exception:
                                log.exception('curar a otro jugador')
                        if not _a_mi_c and _otros_c:
                            import presencia as _pr_cv
                            _vis_c = _pr_cv.entidad_de(_otros_c[0])
                            ses.enviar(_cb.efecto_curacion_inicio(yo, _vis_c, cura, efecto=ef),
                                       _cb.efecto_curacion_fin(yo, _vis_c, efecto=ef),
                                       _cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP), _cb.gcd_paquete())
                            if cd_ms > 0:
                                ses.enviar(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, cd_ms))
                                asyncio.get_event_loop().call_later(
                                    cd_ms / 1000.0,
                                    lambda: ses.enviar_inmediato(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, 0)))
                            log.info(f"[{addr}] {mag.get('nombre')} cura {cura} a "
                                     f"{[s.personaje.nombre for s in _otros_c]}")
                            return
                        if es_target_pet:
                            f_pet_cast['hp'] = min(int(f_pet_cast.get('hp_max') or 100), int(f_pet_cast.get('hp') or 100) + cura)
                            targ_cura_vis = int(pet_eid_cast)
                        else:
                            ses.personaje.hp = min(_vida_max(ses.personaje), ses.personaje.hp + cura)
                            targ_cura_vis = yo
                            # Y el MP, si lo cura (Soul Discharge V: +12000).
                            _mp_c = int(mag.get('mp_cura') or 0)
                            if _mp_c > 0:
                                ses.personaje.mp = min(_mana_max(ses.personaje),
                                                       ses.personaje.mp + _mp_c)
                        ses.enviar(_cb.efecto_curacion_inicio(yo, targ_cura_vis, cura, efecto=ef), _cb.gcd_paquete())

                        def _fin_cura():
                            if ses.personaje:
                                pkgs_fin = [
                                    _cb.efecto_curacion_fin(yo, targ_cura_vis, efecto=ef),
                                    _cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP),
                                ]
                                if es_target_pet and isinstance(f_pet_cast, dict) and f_pet_cast.get('fuera') and pet_eid_cast:
                                    pkgs_fin.extend([
                                        _cb.numero_flotante(int(pet_eid_cast), cura, _cb.TIPO_CURA_HP),
                                        _cb.atributo(int(pet_eid_cast), _ms.hp_eff(f_pet_cast), _cb.KIND_HP),
                                        _ms.armar(f_pet_cast),
                                    ])
                                else:
                                    pkgs_fin.extend([
                                        _cb.numero_flotante(yo, cura, _cb.TIPO_CURA_HP),
                                        _cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP),
                                    ])
                                if cd_ms > 0:
                                    pkgs_fin.append(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, cd_ms))
                                    asyncio.get_event_loop().call_later(cd_ms / 1000.0, lambda: ses.enviar_inmediato(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, 0)))
                                pkgs_fin.extend(_otorgar_skill_exp(ses, ses.personaje, yo, magic_id=tipo))
                                ses.enviar_inmediato(*pkgs_fin)
                                if getattr(ses, 'usuario', None):
                                    cuentas.guardar_progreso(ses.usuario, ses.personaje.char_id,
                                                             ses.personaje.nivel, ses.personaje.exp,
                                                             ses.personaje.hp, ses.personaje.mp,
                                                             ses.personaje.habilidades,
                                                             hp_max=ses.personaje.hp_max, mp_max=ses.personaje.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)
                        asyncio.get_event_loop().call_later(max(0.1, cast_time / 1000.0), _fin_cura)
                        log.info(f"[{addr}] habilidad curativa {tipo} curó {cura} HP (target_pet={es_target_pet})")
                    else:
                        # 2. Buff activo / habilidad sobre el objetivo elegido (el propio jugador O la mascota por separado)
                        targ_confirm = int(pet_eid_cast) if es_target_pet else yo
                        # A otro jugador o a todo el grupo (ver _receptores_de_buff).
                        _otros_b, _a_mi_b = (([], True) if (es_target_pet or mag.get('es_transformacion')
                                                            or not mag.get('es_buff'))
                                             else _receptores_de_buff(ses, tipo, objetivo, mag.get('area')))
                        if not _a_mi_b and _otros_b:
                            import presencia as _pr_tc
                            targ_confirm = _pr_tc.entidad_de(_otros_b[0])
                        tx_conf = f_pet_cast.get('x', ses.personaje.tile_x) if es_target_pet else ses.personaje.tile_x
                        ty_conf = f_pet_cast.get('y', ses.personaje.tile_y) if es_target_pet else ses.personaje.tile_y
                        atk_confirm = _cb.confirmar_cast(targ_confirm, tx_conf, ty_conf)
                        ses.enviar(
                            _cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP),
                            atk_confirm,
                            # Lanza el que lo lanza (yo); le cae a targ_confirm.
                            _cb.efecto_magia_self_inicio(yo, ef, tipo, cast_time=cast_time,
                                                         objetivo=targ_confirm),
                        )

                        # Si es transformacion y ya la tenia activa, re-castear reinstaura su forma humana
                        if mag.get('es_transformacion') and tipo in getattr(ses.personaje, 'buffs', {}):
                            ses.personaje.buffs.pop(tipo, None)
                            ses.personaje.hp = min(ses.personaje.hp, _vida_max(ses.personaje, ses.inventario))
                            ses.personaje.mp = min(ses.personaje.mp, _mana_max(ses.personaje, ses.inventario))
                            ses.enviar(
                                _cb.efecto_magia_self_fin(yo, ef, tipo),
                                struct.pack('<HIBBII', 0x001D, yo, 1, 4, tipo, 0),
                                _cb.atributo(yo, 0, _cb.KIND_TRANSFORM),
                                _cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP),
                                _cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP),
                                _stats_ses(ses)
                            )
                            try:
                                import presencia as _pres
                                _pres.notificar_transformacion(ses, 0)
                            except Exception:
                                pass
                            log.info(f"[{addr}] transformacion {tipo} ({mag.get('nombre')}) cancelada / reinstaurada")
                            return

                        # Si habia otra transformacion activa, limpiarla
                        if mag.get('es_transformacion') and getattr(ses.personaje, 'buffs', None):
                            for prev_bid, prev_bdata in list(ses.personaje.buffs.items()):
                                if prev_bdata.get('es_transform'):
                                    ses.personaje.buffs.pop(prev_bid, None)
                                    prev_ef = prev_bdata.get('efecto') or prev_bdata.get('mag', {}).get('efecto', ef)
                                    ses.enviar(
                                        _cb.efecto_magia_self_fin(yo, prev_ef, prev_bid),
                                        struct.pack('<HIBBII', 0x001D, yo, 1, 4, prev_bid, 0),
                                        _cb.atributo(yo, 0, _cb.KIND_TRANSFORM)
                                    )
                                    try:
                                        import presencia as _pres
                                        _pres.notificar_transformacion(ses, 0)
                                    except Exception:
                                        pass

                        # Registrar buff UNICAMENTE en el objetivo seleccionado (jugador o mascota)
                        if ses.personaje:
                            if not hasattr(ses.personaje, 'buffs') or ses.personaje.buffs is None:
                                ses.personaje.buffs = {}
                            # Exclusion mutua por grupo de prioridad (高權位, ej. Blazing Sun vs Mana Overflow = 887,
                            # Erosion vs Lava Charm vs Brainjack = 577, o distintos rangos I..V del mismo buff)
                            _pg = int(mag.get('priority_group') or 0)
                            if _pg > 0 and not mag.get('es_transformacion'):
                                _dict_b_obj = f_pet_cast.setdefault('buffs', {}) if (es_target_pet and isinstance(f_pet_cast, dict)) else ses.personaje.buffs
                                for prev_bid, prev_bdata in list(_dict_b_obj.items()):
                                    if int(prev_bid) != int(tipo) and isinstance(prev_bdata, dict) and int(prev_bdata.get('priority_group') or 0) == _pg:
                                        _dict_b_obj.pop(prev_bid, None)
                                        ses.enviar(struct.pack('<HIBBII', 0x001D, targ_confirm, 1, 4, int(prev_bid), 0))

                            buff_dur_s = (dur_ms / 1000.0) if dur_ms > 0 else 300.0
                            buff_entry = dict(mag)
                            # OJO: mag['mp'] es el coste de mana de lanzar el hechizo y mag['hp'] puede ser un tick;
                            # no deben quedar como 'mp'/'hp' planos en buff_entry o inflaran el Max MP/HP!
                            buff_entry.pop('mp', None)
                            buff_entry.pop('hp', None)
                            buff_entry['fin'] = time.time() + buff_dur_s
                            buff_entry['mag'] = mag
                            buff_entry['es_transform'] = mag.get('es_transformacion', False)
                            if mag.get('trans_sprite'):
                                buff_entry['trans_sprite'] = int(mag['trans_sprite'])
                            if mag.get('es_melee_trans'):
                                buff_entry['es_melee_trans'] = True
                            if mag.get('matk_pct'):
                                buff_entry['matk_pct'] = mag.get('matk_pct')
                            if mag.get('mdef_pct'):
                                buff_entry['mdef_pct'] = mag.get('mdef_pct')
                            if mag.get('atk_pct'):
                                buff_entry['atk_pct'] = mag.get('atk_pct')
                            if mag.get('def_pct'):
                                buff_entry['def_pct'] = mag.get('def_pct')
                            if mag.get('hp_pct'):
                                buff_entry['hp_pct'] = mag.get('hp_pct')
                            if mag.get('mp_pct'):
                                buff_entry['mp_pct'] = mag.get('mp_pct')
                            if mag.get('mp_to_hp_pct'):
                                buff_entry['mp_to_hp_pct'] = mag.get('mp_to_hp_pct')
                            if mag.get('move_speed_bonus'):
                                buff_entry['move_speed_bonus'] = mag.get('move_speed_bonus')
                            if mag.get('atk_speed_bonus'):
                                buff_entry['atk_speed'] = mag.get('atk_speed_bonus')
                            if mag.get('proc_max_uses', 0) > 0:
                                buff_entry['usos_restantes'] = int(mag['proc_max_uses'])
                            if mag.get('crit_rate'):
                                buff_entry['crit'] = mag.get('crit_rate')
                            if mag.get('phys_mit'):
                                buff_entry['mit'] = mag.get('phys_mit')
                            if mag.get('mag_mit'):
                                buff_entry['mag_mit'] = mag.get('mag_mit')
                            if mag.get('def_bonus'):
                                buff_entry['def'] = mag.get('def_bonus')
                            if mag.get('atk_bonus'):
                                buff_entry['atk'] = mag.get('atk_bonus')
                            if mag.get('matk_bonus'):
                                buff_entry['matk'] = mag.get('matk_bonus')
                            if mag.get('mdef_bonus'):
                                buff_entry['mdef'] = mag.get('mdef_bonus')
                            if mag.get('hit_bonus'):
                                buff_entry['hit'] = mag.get('hit_bonus')
                            if mag.get('eva_bonus'):
                                buff_entry['eva'] = mag.get('eva_bonus')
                            if mag.get('mag_dmg_pct'):
                                buff_entry['mag_dmg_pct'] = mag.get('mag_dmg_pct')
                            if mag.get('phys_dmg_pct'):
                                buff_entry['phys_dmg_pct'] = mag.get('phys_dmg_pct')
                            if mag.get('hp_bonus'):
                                buff_entry['hp_bonus'] = mag.get('hp_bonus')
                            if mag.get('mp_bonus'):
                                buff_entry['mp_bonus'] = mag.get('mp_bonus')
                            if mag.get('cast_redux'):
                                buff_entry['cast_redux'] = mag.get('cast_redux')
                            if mag.get('res_body'):
                                buff_entry['res_body'] = mag.get('res_body')
                            if mag.get('res_mind'):
                                buff_entry['res_mind'] = mag.get('res_mind')
                            if mag.get('res_elec'):
                                buff_entry['res_lightning'] = mag.get('res_elec')
                            if mag.get('res_fire'):
                                buff_entry['res_fire'] = mag.get('res_fire')
                            if mag.get('res_ice'):
                                buff_entry['res_ice'] = mag.get('res_ice')
                            if mag.get('res_poison'):
                                buff_entry['res_corrosion'] = mag.get('res_poison')
                            if es_target_pet and isinstance(f_pet_cast, dict):
                                f_pet_cast.setdefault('buffs', {})[tipo] = dict(buff_entry)
                            elif _a_mi_b:
                                ses.personaje.buffs[tipo] = buff_entry
                            for _s_b in _otros_b:
                                try:
                                    _buff_a_otro(_s_b, tipo, buff_entry, dur_ms, mag,
                                                 lanzador=ses, ef=ef)
                                except Exception:
                                    log.exception('buff a otro jugador')
                            if _otros_b:
                                log.info('[%s] %s tambien a %s', addr, mag.get('nombre'),
                                         [s.personaje.nombre for s in _otros_b])
                            # Aura de grupo: reparte su hechizo hijo (ver _pulso_aura).
                            _hijo_a = None if es_target_pet else _hijo_de_aura(tipo)
                            if _hijo_a and _a_mi_b:
                                _fin_a = buff_entry['fin']
                                asyncio.get_event_loop().call_later(
                                    max(0.2, cast_time / 1000.0),
                                    lambda _h=_hijo_a, _f=_fin_a: _pulso_aura(ses, tipo, _h, _f))
                                log.info('[%s] aura %s: reparte %s al grupo', addr,
                                         mag.get('nombre'), _hijo_a)

                        def _fin_buff():
                            if not ses.personaje or getattr(ses, 'muerto', False):
                                return
                            pkgs_buff = [
                                _cb.efecto_magia_self_fin(yo, ef, tipo, objetivo=targ_confirm),
                            ]
                            if cd_ms > 0:
                                pkgs_buff.append(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, cd_ms))
                                asyncio.get_event_loop().call_later(cd_ms / 1000.0, lambda: ses.enviar_inmediato(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, 0)))

                            if dur_ms > 0:
                                if es_target_pet and isinstance(f_pet_cast, dict) and f_pet_cast.get('fuera') and pet_eid_cast:
                                    if mag.get('hp_bonus') or mag.get('hp_pct'):
                                        f_pet_cast['hp'] = int(f_pet_cast.get('hp_max') or 100)
                                    if mag.get('mp_bonus') or mag.get('mp_pct'):
                                        f_pet_cast['mp'] = int(f_pet_cast.get('mp_max') or 100)
                                    pkgs_buff.extend([
                                        struct.pack('<HIBBII', 0x001D, int(pet_eid_cast), 1, 4, tipo, dur_ms),
                                        _cb.atributo(int(pet_eid_cast), _ms.hp_eff(f_pet_cast), _cb.KIND_HP),
                                        _ms.armar(f_pet_cast),
                                    ])
                                elif not _a_mi_b:
                                    pass          # era para otro jugador: ya lo tiene
                                else:
                                    pkgs_buff.append(struct.pack('<HIBBII', 0x001D, yo, 1, 4, tipo, dur_ms))
                                    if mag.get('es_transformacion') or mag.get('hp_bonus') or mag.get('hp_pct'):
                                        ses.personaje.hp = _vida_max(ses.personaje, ses.inventario)
                                        if mag.get('hp_bonus'):
                                            pkgs_buff.append(_cb.numero_flotante(yo, int(mag['hp_bonus']), _cb.TIPO_CURA_HP))
                                    if mag.get('mp_bonus') or mag.get('mp_pct'):
                                        ses.personaje.mp = _mana_max(ses.personaje, ses.inventario)
                                        if mag.get('mp_bonus'):
                                            pkgs_buff.append(_cb.numero_flotante(yo, int(mag['mp_bonus']), _cb.TIPO_CURA_MP))
                                    pkgs_buff.append(_cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP))
                                    pkgs_buff.append(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))
                                    if mag.get('es_transformacion') and mag.get('trans_sprite'):
                                        pkgs_buff.append(_cb.atributo(yo, mag['trans_sprite'], _cb.KIND_TRANSFORM))
                                        try:
                                            import presencia as _pres
                                            _pres.notificar_transformacion(ses, mag['trans_sprite'])
                                        except Exception:
                                            pass
                                pkgs_buff.append(_stats_ses(ses))

                                def _expirar_buff(sk_id=tipo,
                                                  fin=buff_entry['fin'],
                                                  a_pet=es_target_pet):
                                    if not ses.personaje:
                                        return
                                    pkgs_expirar = []
                                    if a_pet:
                                        fp_exp = getattr(ses.personaje, 'mascota', None)
                                        peid_exp = getattr(ses, 'pet_entity_id', None)
                                        if isinstance(fp_exp, dict) and isinstance(fp_exp.get('buffs'), dict):
                                            act_p = fp_exp['buffs'].get(sk_id)
                                            if act_p and act_p.get('fin') == fin:
                                                fp_exp['buffs'].pop(sk_id, None)
                                                if peid_exp and fp_exp.get('fuera'):
                                                    pkgs_expirar.extend([
                                                        struct.pack('<HIBBII', 0x001D, int(peid_exp), 1, 4, sk_id, 0),
                                                        _cb.atributo(int(peid_exp), _ms.hp_eff(fp_exp), _cb.KIND_HP),
                                                        _ms.armar(fp_exp),
                                                    ])
                                    else:
                                        buffs_activos = getattr(ses.personaje, 'buffs', None)
                                        actual = buffs_activos.get(sk_id) if buffs_activos else None
                                        if actual and actual.get('fin') == fin:
                                            buffs_activos.pop(sk_id, None)
                                            ses.personaje.hp = min(ses.personaje.hp, _vida_max(ses.personaje, ses.inventario))
                                            ses.personaje.mp = min(ses.personaje.mp, _mana_max(ses.personaje, ses.inventario))
                                            pkgs_expirar.extend([
                                                struct.pack('<HIBBII', 0x001D, yo, 1, 4,
                                                            sk_id, 0),
                                                _cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP),
                                                _cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP),
                                            ])
                                            if actual.get('es_transform'):
                                                pkgs_expirar.append(
                                                    _cb.atributo(yo, 0,
                                                                 _cb.KIND_TRANSFORM))
                                                try:
                                                    import presencia as _pres
                                                    _pres.notificar_transformacion(ses, 0)
                                                except Exception:
                                                    pass
                                            pkgs_expirar.append(_stats_ses(ses))
                                    if pkgs_expirar:
                                        ses.enviar_inmediato(*pkgs_expirar)
                                asyncio.get_event_loop().call_later(dur_ms / 1000.0, _expirar_buff)

                            # Recuperacion instantanea de un buff de 0 ms (Soul
                            # Discharge V: +15000 HP y +12000 MP). Va aqui, con el
                            # resto del buff, para que salga con SU animacion.
                            _hc = int(mag.get('hp_cura_buff') or 0)
                            _mc = int(mag.get('mp_cura') or 0)
                            if (_hc or _mc) and ses.personaje:
                                if _hc:
                                    ses.personaje.hp = min(_vida_max(ses.personaje),
                                                           ses.personaje.hp + _hc)
                                    pkgs_buff.extend([
                                        _cb.numero_flotante(yo, _hc, _cb.TIPO_CURA_HP),
                                        _cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP)])
                                if _mc:
                                    ses.personaje.mp = min(_mana_max(ses.personaje),
                                                           ses.personaje.mp + _mc)
                                    pkgs_buff.extend([
                                        _cb.numero_flotante(yo, _mc, _cb.TIPO_CURA_MP),
                                        _cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP)])
                                log.info('[%s] %s recupera %d HP y %d MP'
                                         % (addr, mag.get('nombre'), _hc, _mc))
                            pkgs_buff.extend(_otorgar_skill_exp(ses, ses.personaje, yo, magic_id=tipo))
                            ses.enviar_inmediato(*pkgs_buff)

                        _ret_buff = max(0.14, min(1.0, cast_time / 1000.0))
                        asyncio.get_event_loop().call_later(_ret_buff, _fin_buff)

                        if getattr(ses, 'usuario', None):
                            cuentas.guardar_progreso(ses.usuario, ses.personaje.char_id,
                                                     ses.personaje.nivel, ses.personaje.exp,
                                                     ses.personaje.hp, ses.personaje.mp,
                                                     ses.personaje.habilidades,
                                                     hp_max=ses.personaje.hp_max, mp_max=ses.personaje.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)
                        log.info(f"[{addr}] buff {tipo} ({mag.get('nombre')}) ejecutado (efecto {ef}, dur={dur_ms}ms, cd={cd_ms}ms)")
                        # Sneak: entra en sigilo lo que dure el buff, con su esquiva.
                        if mag.get('sigilo') and dur_ms > 0:
                            ses.sigilo_hasta = time.time() + dur_ms / 1000.0
                            ses.sigilo_mid = tipo
                            ses.sigilo_esquiva = int(mag.get('esquiva_fis') or 0)
                            log.info(f"[{addr}] entra en sigilo {dur_ms // 1000}s "
                                     f"(esquiva {ses.sigilo_esquiva}%)")
                    return
                log.debug(f"[{addr}] ataque a la entidad {objetivo}: no es un monstruo conocido")
                return

            if not m.vivo:
                return

            mag = _cb.datos_magia(tipo) if tipo != _cb.ATAQUE_NORMAL else {}

            # Si el objetivo es un monstruo encantado (aliado), no se le ataca ni con golpe basico ni magia hostil
            if getattr(m, 'encantado', False):
                if not mag.get('es_wolf_spirit') and (tipo == _cb.ATAQUE_NORMAL or not mag.get('es_encanto')):
                    log.info(f"[{addr}] ataque rechazado: {m.nombre} es un aliado encantado")
                    return

            # Wolf Spirit (16669..16673): Sacrifica al monstruo y otorga forma Wolf Spirit y bonos
            if tipo != _cb.ATAQUE_NORMAL and mag.get('es_wolf_spirit'):
                mp_coste = mag.get('mp', 0)
                if ses.personaje and mp_coste > 0:
                    if ses.personaje.mp < mp_coste:
                        log.info(f"[{addr}] MP insuficiente para Wolf Spirit {tipo}")
                        return
                    ses.personaje.mp = max(0, ses.personaje.mp - mp_coste)
                    ses.enviar(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))

                cd_ms = mag.get('cd_ms', 1000)
                if cd_ms > 0 and ses.personaje:
                    _sk_ids_copia = _cb.grupo_de(tipo)
                    cd_pkgs = [struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, cd_ms)
                               for sk_id in _sk_ids_copia]
                    ses.enviar(*cd_pkgs, _cb.gcd_paquete())
                    try:
                        asyncio.get_event_loop().call_later(cd_ms / 1000.0,
                            lambda ids=_sk_ids_copia: ses.enviar_inmediato(*[
                                struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, 0)
                                for sk_id in ids
                            ]))
                    except Exception:
                        pass

                # Sacrificar el monstruo objetivo
                m.recibir(m.hp)
                ef = mag.get('efecto', 714)
                cast_time = _cb.calcular_cast_time(mag.get('cast_time', 1000), es_magia=True)

                es_mag_m = getattr(m, 'matk', 0) > getattr(m, 'atk', 0)
                sub_id = mag.get('sub_buff_spell', 16801) if es_mag_m else mag.get('sub_buff_phys', 16796)
                sub_mag = _cb.datos_magia(sub_id) or {}
                dur_ms = int(sub_mag.get('dur_ms') or 1800000)
                buff_entry = dict(sub_mag)
                buff_entry['fin'] = time.time() + (dur_ms / 1000.0)
                buff_entry['es_transform'] = True
                buff_entry['trans_sprite'] = 42146
                buff_entry['atk'] = sub_mag.get('atk_bonus', 0)
                buff_entry['def'] = sub_mag.get('def_bonus', 0)
                buff_entry['matk'] = sub_mag.get('matk_bonus', 0)
                buff_entry['mdef'] = sub_mag.get('mdef_bonus', 0)
                rank_uses = {16669: 5, 16670: 6, 16671: 7, 16672: 8, 16673: 10}.get(tipo, 5)
                buff_entry['usos_restantes'] = rank_uses
                buff_entry['wolf_claw_sub'] = 16802 + (tipo - 16669 if 16669 <= tipo <= 16673 else 0)
                if ses.personaje:
                    ses.personaje.buffs = getattr(ses.personaje, 'buffs', {}) or {}
                    ses.personaje.buffs[tipo] = buff_entry

                def _expirar_wolf_spirit():
                    if not ses.personaje:
                        return
                    ses.personaje.buffs.pop(tipo, None)
                    ses.enviar_inmediato(
                        struct.pack('<HIBBII', 0x001D, yo, 1, 4, tipo, 0),
                        _cb.atributo(yo, 0, _cb.KIND_TRANSFORM),
                        _stats_ses(ses)
                    )
                    try:
                        import presencia as _pres
                        _pres.notificar_transformacion(ses, 0)
                    except Exception:
                        pass
                asyncio.get_event_loop().call_later(dur_ms / 1000.0, _expirar_wolf_spirit)

                ses.enviar(
                    _cb.confirmar_cast(objetivo, m.tile_x, m.tile_y),
                    _cb.numero_de_dano(yo, objetivo, dano=0, ataque=tipo, efecto=ef, cast_time=cast_time),
                    _cb.despawn_monstruo(m.entity_id),
                    _cb.atributo(yo, 42146, _cb.KIND_TRANSFORM),
                    struct.pack('<HIBBII', 0x001D, yo, 1, 4, tipo, dur_ms),
                    _stats_ses(ses),
                )
                try:
                    import presencia as _pres
                    _pres.notificar_transformacion(ses, 42146)
                except Exception:
                    pass
                log.info(f"[{addr}] Wolf Spirit activado para {yo}: monstruo {m.nombre} sacrificado")
                return

            # Hechizo de encanto (Shining Charm I..V de Earth)
            if tipo != _cb.ATAQUE_NORMAL and mag.get('es_encanto'):
                mp_coste = mag.get('mp', 0)
                if ses.personaje and mp_coste > 0:
                    if ses.personaje.mp < mp_coste:
                        log.info(f"[{addr}] MP insuficiente ({ses.personaje.mp}/{mp_coste}) para encanto {tipo}")
                        return
                    ses.personaje.mp = max(0, ses.personaje.mp - mp_coste)
                    ses.enviar(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))

                cd_ms = mag.get('cd_ms', 1000)
                if cd_ms > 0 and ses.personaje:
                    _sk_ids_copia = _cb.grupo_de(tipo)
                    cd_pkgs = [struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, cd_ms)
                               for sk_id in _sk_ids_copia]
                    ses.enviar(*cd_pkgs, _cb.gcd_paquete())
                    try:
                        asyncio.get_event_loop().call_later(cd_ms / 1000.0,
                            lambda ids=_sk_ids_copia: ses.enviar_inmediato(*[
                                struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, 0)
                                for sk_id in ids
                            ]))
                    except Exception:
                        pass

                dur_s = max(10, mag.get('dur_ms', 600000) // 1000)
                dur_ms = dur_s * 1000
                m.encantado = True
                m.encantado_expira = time.time() + dur_s
                m.en_combate_con = None
                m.charmed_objetivo = None
                ses.monstruo_encantado = m

                if getattr(ses, 'invocacion', None) and ses.invocacion.get('objetivo') == m:
                    ses.invocacion['objetivo'] = None
                if getattr(ses, 'invocacion2', None) and ses.invocacion2.get('objetivo') == m:
                    ses.invocacion2['objetivo'] = None
                for _ob in (ses.monstruos or {}).values():
                    if getattr(_ob, 'charmed_objetivo', None) == m:
                        _ob.charmed_objetivo = None
                # Y SOLTARLO DE QUIEN YA LO TENIA APUNTADO.
                #
                # Los filtros de "no ataques a un encantado" miran el
                # estado al ELEGIR blanco, asi que si el jugador o la
                # mascota ya lo tenian fijado antes de encantarlo seguian
                # dandole. Por eso se veia seguir pegandole al bicho recien
                # encantado aunque no se pudiera elegir de nuevo.
                if getattr(ses, 'objetivo_actual', None) == m.entity_id:
                    ses.objetivo_actual = None
                if getattr(ses, 'pet_objetivo', None) == m:
                    ses.pet_objetivo = None

                ef = mag.get('efecto', 64)
                cast_time = _cb.calcular_cast_time(
                    mag.get('cast_time', 1000),
                    buffs=getattr(ses.personaje, 'buffs', {}),
                    habilidades=getattr(ses.personaje, 'habilidades', None),
                    es_magia=True
                )

                ses.enviar(
                    _cb.confirmar_cast(objetivo, m.tile_x, m.tile_y),
                    _cb.numero_de_dano(yo, objetivo, dano=0, ataque=tipo, efecto=ef, cast_time=cast_time),
                )
                def _fin_encanto():
                    ses.enviar_inmediato(
                        _cb.cierre_de_dano(yo, objetivo, ataque=tipo, efecto=ef),
                        # El 0x0006 es lo que hace que el CLIENTE lo trate
                        # como aliado y deje de apuntarle. Sin el, seguia
                        # pidiendo el golpe dos veces por segundo y el
                        # servidor lo rechazaba uno a uno. Medido en
                        # mundo_234602_153654_orden.jsonl.
                        _cb.entidad_aliada(m.entity_id),
                        struct.pack('<HIBBII', 0x001D, m.entity_id, 1, 4, tipo, dur_ms),
                        struct.pack('<HIBBI', 0x0013, m.entity_id, 1, 0x3c, yo),
                        _cb.efecto_aura_objetivo(yo, objetivo, m.tile_x, m.tile_y, tipo),
                    )
                asyncio.get_event_loop().call_later(max(0.14, cast_time / 1000.0), _fin_encanto)
                ses.enviar(*_otorgar_skill_exp(ses, ses.personaje, yo, magic_id=tipo))

                if getattr(ses, 'usuario', None):
                    cuentas.guardar_progreso(ses.usuario, ses.personaje.char_id,
                                             ses.personaje.nivel, ses.personaje.exp,
                                             ses.personaje.hp, ses.personaje.mp,
                                             ses.personaje.habilidades,
                                             hp_max=ses.personaje.hp_max, mp_max=ses.personaje.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)
                log.info(f"[{addr}] encanto {tipo} ({mag.get('nombre')}) exitoso sobre {m.nombre} (dur={dur_s}s)")
                return

            # Hechizo de control de masas por miedo / panico (Soul Entangle, Crazy Roar, etc.)
            if tipo != _cb.ATAQUE_NORMAL and mag.get('es_panico'):
                cost_sp = mag.get('cost_sp', 0)
                if cost_sp > 0:
                    if getattr(ses, 'sp', 0) < cost_sp:
                        log.info(f"[{addr}] SP insuficiente ({getattr(ses, 'sp', 0)}/{cost_sp}) para panico {tipo}")
                        return
                    ses.sp -= cost_sp
                    if ses.personaje:
                        ses.personaje.sp = ses.sp
                    ses.enviar(_cb.atributo(yo, ses.sp, _cb.KIND_SP), _stats_ses(ses))
                _dar_sp(ses, yo, mag, addr)

                mp_coste = mag.get('mp', 0)
                if ses.personaje and mp_coste > 0:
                    if ses.personaje.mp < mp_coste:
                        log.info(f"[{addr}] MP insuficiente ({ses.personaje.mp}/{mp_coste}) para panico {tipo}")
                        return
                    ses.personaje.mp = max(0, ses.personaje.mp - mp_coste)
                    ses.enviar(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))

                cd_ms = mag.get('cd_ms', 1000)
                if cd_ms > 0 and ses.personaje:
                    _sk_ids_copia = _cb.grupo_de(tipo)
                    cd_pkgs = [struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, cd_ms)
                               for sk_id in _sk_ids_copia]
                    ses.enviar(*cd_pkgs, _cb.gcd_paquete())
                    try:
                        asyncio.get_event_loop().call_later(cd_ms / 1000.0,
                            lambda ids=_sk_ids_copia: ses.enviar_inmediato(*[
                                struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, 0)
                                for sk_id in ids
                            ]))
                    except Exception:
                        pass

                dur_s = max(2, mag.get('dur_ms', 6000) // 1000)
                dur_ms = dur_s * 1000
                m.panico = True
                m.panico_hasta = time.time() + dur_s
                m.en_combate_con = None
                m.charmed_objetivo = None

                ef = mag.get('efecto', 10)
                cast_time = _cb.calcular_cast_time(
                    mag.get('cast_time', 2000),
                    buffs=getattr(ses.personaje, 'buffs', {}),
                    habilidades=getattr(ses.personaje, 'habilidades', None),
                    es_magia=True
                )

                ses.enviar(
                    _cb.confirmar_cast(objetivo, m.tile_x, m.tile_y),
                    _cb.numero_de_dano(yo, objetivo, dano=0, ataque=tipo, efecto=ef, cast_time=cast_time),
                )
                def _fin_panico():
                    ses.enviar_inmediato(
                        _cb.cierre_de_dano(yo, objetivo, ataque=tipo, efecto=ef),
                        struct.pack('<HIBBII', 0x001D, m.entity_id, 1, 4, tipo, dur_ms),
                        _cb.efecto_aura_objetivo(yo, objetivo, m.tile_x, m.tile_y, tipo),
                    )
                asyncio.get_event_loop().call_later(max(0.14, cast_time / 1000.0), _fin_panico)
                ses.enviar(*_otorgar_skill_exp(ses, ses.personaje, yo, magic_id=tipo))

                if getattr(ses, 'usuario', None):
                    cuentas.guardar_progreso(ses.usuario, ses.personaje.char_id,
                                             ses.personaje.nivel, ses.personaje.exp,
                                             ses.personaje.hp, ses.personaje.mp,
                                             ses.personaje.habilidades,
                                             hp_max=ses.personaje.hp_max, mp_max=ses.personaje.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)
                log.info(f"[{addr}] panico {tipo} ({mag.get('nombre')}) exitoso sobre {m.nombre} (dur={dur_s}s)")
                return

            # Hechizo de maldicion / debuff a enemigo (Exhaustion Curse, Weak Curse, Slow Curse, etc.)
            if tipo != _cb.ATAQUE_NORMAL and mag.get('es_debuff'):
                cost_sp = mag.get('cost_sp', 0)
                if cost_sp > 0:
                    if getattr(ses, 'sp', 0) < cost_sp:
                        log.info(f"[{addr}] SP insuficiente ({getattr(ses, 'sp', 0)}/{cost_sp}) para maldicion {tipo}")
                        return
                    ses.sp -= cost_sp
                    if ses.personaje:
                        ses.personaje.sp = ses.sp
                    ses.enviar(_cb.atributo(yo, ses.sp, _cb.KIND_SP), _stats_ses(ses))
                _dar_sp(ses, yo, mag, addr)

                mp_coste = mag.get('mp', 0)
                if ses.personaje and mp_coste > 0:
                    if ses.personaje.mp < mp_coste:
                        log.info(f"[{addr}] MP insuficiente ({ses.personaje.mp}/{mp_coste}) para maldicion {tipo}")
                        return
                    ses.personaje.mp = max(0, ses.personaje.mp - mp_coste)
                    ses.enviar(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))

                cd_ms = mag.get('cd_ms', 1000)
                if cd_ms > 0 and ses.personaje:
                    _sk_ids_copia = _cb.grupo_de(tipo)
                    cd_pkgs = [struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, cd_ms)
                               for sk_id in _sk_ids_copia]
                    ses.enviar(*cd_pkgs, _cb.gcd_paquete())
                    try:
                        asyncio.get_event_loop().call_later(cd_ms / 1000.0,
                            lambda ids=_sk_ids_copia: ses.enviar_inmediato(*[
                                struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, 0)
                                for sk_id in ids
                            ]))
                    except Exception:
                        pass

                dur_s = max(5, mag.get('dur_ms', 20000) // 1000)
                dur_ms = dur_s * 1000
                if not hasattr(m, 'debuffs') or m.debuffs is None:
                    m.debuffs = {}
                m.debuffs[tipo] = {
                    'fin': time.time() + dur_s,
                    'atk_mod': mag.get('atk_mod', 0),
                    'phys_dmg_pct': mag.get('phys_dmg_pct', 0),
                    'def_mod': mag.get('def_mod', 0),
                    'phys_mit_pct': mag.get('phys_mit_pct', 0),
                    'vel_mov_mod': mag.get('vel_mov_mod', 0),
                }
                if getattr(m, 'en_combate_con', None) is None:
                    m.en_combate_con = yo

                ef = mag.get('efecto', 73)
                import clases as _c
                cast_time = _cb.calcular_cast_time(
                    mag.get('cast_time', 800),
                    buffs=getattr(ses.personaje, 'buffs', {}),
                    habilidades=getattr(ses.personaje, 'habilidades', None),
                    es_magia=True
                )

                ses.enviar(
                    _cb.confirmar_cast(objetivo, m.tile_x, m.tile_y),
                    _cb.numero_de_dano(yo, objetivo, dano=0, ataque=tipo, efecto=ef, cast_time=cast_time),
                )
                def _fin_curse():
                    ses.enviar_inmediato(
                        _cb.cierre_de_dano(yo, objetivo, ataque=tipo, efecto=ef),
                        struct.pack('<HIBBII', 0x001D, m.entity_id, 1, 4, tipo, dur_ms),
                        _cb.efecto_aura_objetivo(yo, objetivo, m.tile_x, m.tile_y, tipo),
                    )
                asyncio.get_event_loop().call_later(max(0.14, cast_time / 1000.0), _fin_curse)
                ses.enviar(*_otorgar_skill_exp(ses, ses.personaje, yo, magic_id=tipo))

                if getattr(ses, 'usuario', None):
                    cuentas.guardar_progreso(ses.usuario, ses.personaje.char_id,
                                             ses.personaje.nivel, ses.personaje.exp,
                                             ses.personaje.hp, ses.personaje.mp,
                                             ses.personaje.habilidades,
                                             hp_max=ses.personaje.hp_max, mp_max=ses.personaje.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)
                log.info(f"[{addr}] maldicion {tipo} ({mag.get('nombre')}) exitosa sobre {m.nombre} (dur={dur_s}s)")
                return

            # El dano sale del ataque del jugador mas bonos pasivos menos defensa del bicho
            import inventario as _iv
            import skills as _sk_mod
            habs = ses.personaje.habilidades if ses.personaje else None
            buffs_activos = getattr(ses.personaje, 'buffs', None)
            st = _iv.stats(ses.inventario, habs, buffs=buffs_activos, mejoras=_mejoras_de(ses))
            is_magic_skill = bool(tipo != _cb.ATAQUE_NORMAL and (_sk_mod.skill_de_magia(tipo) in (1, 2, 3, 4)))
            if is_magic_skill:
                ataque = struct.unpack_from('<I', st, 2 + 44)[0]
            else:
                ataque = struct.unpack_from('<I', st, 2 + 20 + 4)[0]

            # Si se usa una habilidad activa (ej. Slicing Hit, Basic Beating, etc.)
            dano_extra = 0
            if tipo != _cb.ATAQUE_NORMAL:
                mag = _cb.datos_magia(tipo)
                cost_sp = mag.get('cost_sp', 0)
                if cost_sp > 0:
                    if getattr(ses, 'sp', 0) < cost_sp:
                        log.info(f"[{addr}] SP insuficiente ({getattr(ses, 'sp', 0)}/{cost_sp}) para habilidad {tipo}")
                        return
                    ses.sp -= cost_sp
                    if ses.personaje:
                        ses.personaje.sp = ses.sp
                    ses.enviar(_cb.atributo(yo, ses.sp, _cb.KIND_SP), _stats_ses(ses))
                _dar_sp(ses, yo, mag, addr)

                mp_coste = mag.get('mp', 0)
                if ses.personaje and mp_coste > 0:
                    if ses.personaje.mp < mp_coste:
                        log.info(f"[{addr}] MP insuficiente ({ses.personaje.mp}/{mp_coste}) para habilidad {tipo}")
                        return
                    ses.personaje.mp = max(0, ses.personaje.mp - mp_coste)
                    ses.enviar(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))
                # El Stance power de la habilidad, ponderado por
                # PESO_STANCE (ver combate.py: la medicion dice que se suma
                # tal cual, sin multiplicador).
                dano_extra = int(round(_cb.stance_de(tipo) * _cb.PESO_STANCE))
                atk_magic = tipo
                atk_efecto = _cb.efecto_de_ataque(tipo)
                # Enviar cooldown de TODAS las habilidades (kind=3) igual que el servidor real
                # El servidor real manda kind=3 con cd_ms para cada skill al usar una habilidad
                cd_ms = mag.get('cd_ms', 1000)
                if cd_ms > 0 and ses.personaje:
                    # El cooldown NO va por habilidad de clase (Sword, Enhance,
                    # Grapple...) sino por GRUPO de hechizo: al usar Slicing
                    # Hit I el servidor real manda 601, 612, 623, 634, 645 y
                    # la familia Mangle, que comparten el 群組編號 1201.
                    # Mandarlo con los ids de clase no hacia nada porque esos
                    # ids no estan en la barra.
                    _sk_ids_copia = _cb.grupo_de(tipo)
                    cd_pkgs = [struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, cd_ms)
                               for sk_id in _sk_ids_copia]
                    ses.enviar(*cd_pkgs, _cb.gcd_paquete())
                    try:
                        asyncio.get_event_loop().call_later(cd_ms / 1000.0,
                            lambda ids=_sk_ids_copia: ses.enviar_inmediato(*[
                                struct.pack('<HIBBII', 0x001D, yo, 1, 3, sk_id, 0)
                                for sk_id in ids
                            ]))
                    except Exception:
                        pass
                elif cd_ms > 0:
                    ses.enviar(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, cd_ms), _cb.gcd_paquete())
                    try:
                        asyncio.get_event_loop().call_later(cd_ms / 1000.0, lambda: ses.enviar_inmediato(struct.pack('<HIBBII', 0x001D, yo, 1, 3, tipo, 0)))
                    except Exception:
                        pass

            else:
                atk_magic, atk_efecto = _cb.ataque_estandar_arma(arma_puesta)

            # Probabilidad de golpe critico (base 5% + bonus de Ferocious Song / buffs)
            extra_crit = 0
            if buffs_activos:
                now = time.time()
                for b_id, b_data in list(buffs_activos.items()):
                    if isinstance(b_data, dict) and b_data.get('fin', 0) > now and 'crit' in b_data:
                        extra_crit += b_data['crit']
            # El Critical del personaje, no un 5 fijo: con Critical 11 la
            # probabilidad es 11%, no 5%.
            crit_prob = min(0.90, (critico_jugador(ses) + extra_crit) / 100.0)
            es_crit = (random.random() < crit_prob)

            # Ember Brand (13841..13845) / Holy Brand (15241..15245) / Formula 65:
            # Fase 1 golpea y marca al enemigo; Fase 2 detona la explosion AOE (14036..14040, radio 5, efecto 546)
            _brand_detona = False
            _brand_prev_id = 0
            _brand_aoe_mag = None
            if tipo != _cb.ATAQUE_NORMAL and mag.get('es_brand'):
                if mag.get('brand_aoe_id'):
                    _brand_aoe_mag = _cb.datos_magia(mag['brand_aoe_id'])
                _now_br = time.time()
                _ef_act = getattr(m, 'efectos_activos', None) or {}
                for _b_cand in (mag.get('brand_dot_id', 0), *range(13976, 13981), *range(15251, 15256)):
                    if _b_cand and _ef_act.get(_b_cand, 0) > _now_br:
                        _brand_detona = True
                        _brand_prev_id = _b_cand
                        break
                if _brand_detona and _brand_aoe_mag and _brand_aoe_mag.get('efecto'):
                    atk_efecto = _brand_aoe_mag['efecto']


            mult_spell = 1.0
            var_pct = 0.05
            if is_magic_skill:
                # Daño Magico oficial de AO: (SA - SD) * (平均傷害 / 高權位)
                _mag_ref = _brand_aoe_mag if (_brand_detona and _brand_aoe_mag) else mag
                dano_base = _mag_ref.get('dano_base', 0)
                denom = _mag_ref.get('base_denom', 200) or 200
                if dano_base > 0:
                    mult_spell = dano_base / float(denom)
                else:
                    mult_spell = 1.0
                dano_var = _mag_ref.get('dano_var', 0)
                if dano_var > 0:
                    var_pct = min(0.15, max(0.02, dano_var / float(denom)))
                coef = _mag_ref.get('dano_coef', 0)
                if coef > 0:
                    mult_spell *= (coef / 100.0)
            else:
                # Daño Fisico de AO: (R.Atk + Stance Power * PESO_STANCE) * Multiplicadores - DEF
                if tipo != _cb.ATAQUE_NORMAL:
                    _cb_data = _cb.combo_de(tipo)
                    es_combo_skill = bool(_cb_data and _cb_data.get('golpes', 1) > 1)
                    if es_combo_skill:
                        mult_spell = 1.2
                    else:
                        mult_spell = 1.35

                    # Boss penalty para Rapidfire (reduccion al 50% frente a Jefes)
                    is_rapidfire = bool(5766 <= tipo <= 5770 or 5957 <= tipo <= 5961 or 'Rapidfire' in mag.get('nombre', ''))
                    if is_rapidfire and m and _cb.es_jefe(getattr(m, 'npc_type', 0)):
                        mult_spell *= 0.5

                    coef = mag.get('dano_coef', 0)
                    if coef > 0:
                        mult_spell *= (coef / 100.0)
                else:
                    mult_spell = 1.0
                var_pct = 0.03

            # Modificadores porcentuales del equipo (ej. +30% spell damage de Snow Queen's Cufflink)
            mods_eq = _iv.modificadores_porcentuales_equipo(ses.inventario)
            _clave_pct = 'mag_dmg_pct' if is_magic_skill else 'phys_dmg_pct'
            if mods_eq.get(_clave_pct, 0) > 0:
                mult_spell *= (1.0 + mods_eq[_clave_pct] / 100.0)

            # Y el de los BUFFS activos (Fury Attack, Soul Corral, etc.)
            _pct_buffs = _cb.pct_dano_buffs(
                getattr(ses.personaje, 'buffs', None), is_magic_skill)
            if _pct_buffs:
                mult_spell *= (1.0 + _pct_buffs / 100.0)

            # Guardamos el multiplicador base (habilidad + equipo + buffs, sin el critico del 1er golpe)
            # para que todos los golpes de un combo (Strangle Strike, Cross Chop, etc.) peguen con el
            # mismo multiplicador y cada golpe tire su propio critico independiente.
            mult_base_combo = mult_spell
            if es_crit:
                mult_spell = mult_base_combo * 1.5

            total_atk = ataque + (0 if is_magic_skill else dano_extra)
            dano = m.recibir(total_atk, es_magico=is_magic_skill, mult=mult_spell, var_pct=var_pct)
            if tipo != _cb.ATAQUE_NORMAL:
                log.info(f"[{addr}] habilidad {tipo} ({'magica' if is_magic_skill else 'fisica'}): "
                         f"{'Spl Atk' if is_magic_skill else 'R.Atk'} {total_atk} * mult {mult_spell:.3f}"
                         f"{' (critico)' if es_crit else ''} -> {dano} de dano "
                         f"al {m.nombre} ({m.hp}/{m.hp_max})")
            # El ataque puede encadenar otro hechizo (轉嫁法術): Slicing Hit
            # sangra al 100%, Poison Hit envenena al 100%, Basic Beating aturde,
            # Tendon Chop ralentiza, o Ember/Holy Brand aplica/consume la marca.
            _ef2 = _cb.efecto_secundario(tipo) if tipo != _cb.ATAQUE_NORMAL else None
            _pkg_debuff_m = []
            if tipo != _cb.ATAQUE_NORMAL and mag.get('es_brand'):
                if not _brand_detona:
                    _b_dot_id = mag.get('brand_dot_id', 0)
                    _d_dot_xml = _cb._magic_xml().get(_b_dot_id) or {}
                    _dur_dot_ms = int(float(_d_dot_xml.get('持續時間') or 14)) * 1000
                    _hp_dot = int(float(_d_dot_xml.get('HP') or -200))
                    _int_dot = int(float(_d_dot_xml.get('作用間隔') or 2))
                    _ef_brand = {
                        'magia': _b_dot_id,
                        'prob': 100,
                        'nombre': _d_dot_xml.get('名稱', 'Brand'),
                        'estado': 'sangrado',
                        'dur_ms': _dur_dot_ms,
                        'hp_tick': _hp_dot,
                        'intervalo': _int_dot,
                    }
                    m.aplicar_efecto(_ef_brand)
                    if _b_dot_id:
                        _pkg_debuff_m.append(struct.pack('<HIBBII', 0x001D, m.entity_id, 1, 4, _b_dot_id, _dur_dot_ms))
                        _pkg_debuff_m.append(_cb.efecto_aura_objetivo(yo, objetivo, m.tile_x, m.tile_y, _b_dot_id))
                        def _expirar_brand_m(eid=m.entity_id, deb_id=_b_dot_id):
                            if getattr(m, 'efectos_activos', None):
                                m.efectos_activos.pop(deb_id, None)
                            ses.enviar_inmediato(struct.pack('<HIBBII', 0x001D, eid, 1, 4, deb_id, 0))
                        try:
                            asyncio.get_event_loop().call_later(_dur_dot_ms / 1000.0, _expirar_brand_m)
                        except Exception:
                            pass
                else:
                    if getattr(m, 'efectos_activos', None) and _brand_prev_id:
                        m.efectos_activos.pop(_brand_prev_id, None)
                        _pkg_debuff_m.append(struct.pack('<HIBBII', 0x001D, m.entity_id, 1, 4, _brand_prev_id, 0))
                    _ef2 = _cb.efecto_secundario(mag.get('brand_aoe_id', 0))
            if _ef2 and random.random() * 100 < _ef2.get('prob', 0):
                _aplicado = m.aplicar_efecto(_ef2)
                if _aplicado:
                    dur_ms = _ef2.get('dur_ms', 10000)
                    mid = _ef2.get('magia', tipo)
                    _pkg_debuff_m.append(struct.pack('<HIBBII', 0x001D, m.entity_id, 1, 4, mid, dur_ms))
                    _pkg_debuff_m.append(_cb.efecto_aura_objetivo(yo, objetivo, m.tile_x, m.tile_y, mid))
                    _sub_deb_id = _ef2.get('sub_debuff')
                    if _sub_deb_id:
                        _pkg_debuff_m.append(struct.pack('<HIBBII', 0x001D, m.entity_id, 1, 4, _sub_deb_id, dur_ms))
                        _pkg_debuff_m.append(_cb.efecto_aura_objetivo(yo, objetivo, m.tile_x, m.tile_y, _sub_deb_id))
                        try:
                            asyncio.get_event_loop().call_later(dur_ms / 1000.0, lambda eid=m.entity_id, did=_sub_deb_id: ses.enviar_inmediato(struct.pack('<HIBBII', 0x001D, eid, 1, 4, did, 0)))
                        except Exception:
                            pass
                    def _expirar_debuff_m(eid=m.entity_id, deb_id=mid):
                        if getattr(m, 'efectos_activos', None):
                            m.efectos_activos.pop(deb_id, None)
                        ses.enviar_inmediato(struct.pack('<HIBBII', 0x001D, eid, 1, 4, deb_id, 0))
                    try:
                        asyncio.get_event_loop().call_later(dur_ms / 1000.0, _expirar_debuff_m)
                    except Exception:
                        pass
                    log.info(f"[{addr}] {m.nombre}: {_aplicado} por "
                             f"{_ef2.get('nombre')} (mid={mid}, {dur_ms}ms)")
            # Marcar al monstruo en combate con el jugador
            # Forbidden Curse: absorber HP y MP del daño infligido
            _pkgs_drain = []
            if tipo != _cb.ATAQUE_NORMAL and dano > 0 and ses.personaje:
                _hp_drain = mag.get('drain_hp_pct', 0)
                _mp_drain = mag.get('drain_mp_pct', 0)
                if _hp_drain > 0:
                    _prob_drain = mag.get('drain_hp_prob', 100)
                    if random.random() * 100.0 < _prob_drain:
                        _hp_gain = max(1, int(round(dano * (_hp_drain / 100.0))))
                        ses.personaje.hp = min(_vida_max(ses.personaje),
                                              ses.personaje.hp + _hp_gain)
                        _pkgs_drain.append(_cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP))
                        _pkgs_drain.append(_cb.numero_flotante(yo, _hp_gain,
                                                               _cb.TIPO_CURA_HP))
                if _mp_drain > 0:
                    _mp_gain = max(1, int(round(dano * (_mp_drain / 100.0))))
                    ses.personaje.mp = min(_mana_max(ses.personaje),
                                          ses.personaje.mp + _mp_gain)
                    _pkgs_drain.append(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))
                    # El mana absorbido tambien tiene su numero, en AZUL.
                    _pkgs_drain.append(_cb.numero_flotante(yo, _mp_gain,
                                                           _cb.TIPO_CURA_MP))

            # --- Procs de Trinkets / Equipo (Formula 47: Sword-Shiny Flower Basket, Scripts, etc.) ---
            if dano > 0 and ses.personaje:
                _procs_eq = _cb.procs_de_equipo(ses.inventario, es_skill=(tipo != _cb.ATAQUE_NORMAL))
                for _pinfo in _procs_eq:
                    if random.random() * 100.0 < _pinfo.get('prob', 10):
                        _pid = int(_pinfo['proc_id'])
                        _pef = int(_pinfo.get('efecto') or 251)
                        _pdur = int(_pinfo.get('dur_ms') or 0)
                        _pmag = _pinfo.get('mag') or {}
                        if _pinfo.get('hp_cura', 0) > 0:
                            _hc = int(_pinfo['hp_cura'])
                            ses.personaje.hp = min(_vida_max(ses.personaje), ses.personaje.hp + _hc)
                            _pkgs_drain.append(_cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP))
                            _pkgs_drain.append(_cb.numero_flotante(yo, _hc, _cb.TIPO_CURA_HP))
                        if _pinfo.get('mp_cura', 0) > 0:
                            _mc = int(_pinfo['mp_cura'])
                            ses.personaje.mp = min(_mana_max(ses.personaje), ses.personaje.mp + _mc)
                            _pkgs_drain.append(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))
                            _pkgs_drain.append(_cb.numero_flotante(yo, _mc, _cb.TIPO_CURA_MP))
                        _pkgs_drain.append(_cb.efecto_magia_self_fin(yo, _pef, _pid))
                        if _pdur > 0:
                            if not hasattr(ses.personaje, 'buffs') or ses.personaje.buffs is None:
                                ses.personaje.buffs = {}
                            _pfin = time.time() + (_pdur / 1000.0)
                            _b_proc = dict(_pmag)
                            _b_proc.pop('mp', None)
                            _b_proc.pop('hp', None)
                            _b_proc['fin'] = _pfin
                            _b_proc['mag'] = _pmag
                            if _pmag.get('crit_rate'):
                                _b_proc['crit'] = _pmag.get('crit_rate')
                            if _pmag.get('def_bonus'):
                                _b_proc['def'] = _pmag.get('def_bonus')
                            if _pmag.get('atk_bonus'):
                                _b_proc['atk'] = _pmag.get('atk_bonus')
                            if _pmag.get('matk_bonus'):
                                _b_proc['matk'] = _pmag.get('matk_bonus')
                            if _pmag.get('mdef_bonus'):
                                _b_proc['mdef'] = _pmag.get('mdef_bonus')
                            if _pmag.get('phys_dmg_pct'):
                                _b_proc['phys_dmg_pct'] = _pmag.get('phys_dmg_pct')
                            if _pmag.get('mag_dmg_pct'):
                                _b_proc['mag_dmg_pct'] = _pmag.get('mag_dmg_pct')
                            ses.personaje.buffs[_pid] = _b_proc
                            _pkgs_drain.append(struct.pack('<HIBBII', 0x001D, yo, 1, 4, _pid, _pdur))
                            _pkgs_drain.append(_stats_ses(ses))
                            def _expirar_proc(sk_id=_pid, fin=_pfin):
                                b_act = getattr(ses.personaje, 'buffs', None) if ses.personaje else None
                                act = b_act.get(sk_id) if b_act else None
                                if not act or act.get('fin') != fin:
                                    return
                                b_act.pop(sk_id, None)
                                ses.enviar_inmediato(
                                    struct.pack('<HIBBII', 0x001D, yo, 1, 4, sk_id, 0),
                                    _stats_ses(ses),
                                )
                            try:
                                asyncio.get_event_loop().call_later(_pdur / 1000.0, _expirar_proc)
                            except Exception:
                                pass

                # --- Triggers de Buffs activos al atacar (Blazing Sun, Mana Overflow, Erosion, Spell Boost, etc.) ---
                _pkgs_drain.extend(_procesar_triggers_buffs(ses, yo, m, addr=addr, en_ataque=True))

            m.en_combate_con = yo
            m.ultimo_ataque = time.time()
            if not getattr(m, 'encantado', False):
                if getattr(ses, 'invocacion', None):
                    ses.invocacion['objetivo'] = m
                if getattr(ses, 'invocacion2', None):
                    ses.invocacion2['objetivo'] = m
                if getattr(ses, 'monstruo_encantado', None) and getattr(ses.monstruo_encantado, 'vivo', False):
                    ses.monstruo_encantado.charmed_objetivo = m

            # Acumulacion de SP (303 puntos base + bono de Reserve)
            bars, max_pts = _max_sp_info(ses.personaje)
            res_rank = 1
            if ses.personaje and getattr(ses.personaje, 'habilidades', None):
                for h in ses.personaje.habilidades:
                    if (h[0] if isinstance(h, (list, tuple)) else h) == 15:
                        res_rank = h[1] if isinstance(h, (list, tuple)) and len(h) > 1 else 1
                        break
            sp_gain = _cb.SP_POR_GOLPE * (2 + res_rank // 50)
            ant_bars = getattr(ses, 'sp', 0) // 1000
            ses.sp = min(max_pts, getattr(ses, 'sp', 0) + sp_gain)
            ses.personaje.sp = ses.sp
            curr_bars = ses.sp // 1000
            pkgs_sp = [_cb.atributo(yo, ses.sp, _cb.KIND_SP)]
            if curr_bars != ant_bars:
                pkgs_sp.append(_iv.stats(ses.inventario, ses.personaje.habilidades,
                                         hp=ses.personaje.hp, hp_max=ses.personaje.hp_max,
                                         mp=ses.personaje.mp, mp_max=ses.personaje.mp_max,
                                         oro=ses.personaje.oro, buffs=buffs_activos,
                                         sp=ses.sp, sp_max=bars,
                                         mejoras=_mejoras_de(ses)))

            ses.esfuerzo = max(0, getattr(ses, 'esfuerzo', 900) - _cb.COSTE_GOLPE)
            pkgs_sk = _otorgar_skill_exp(ses, ses.personaje, yo, arma_puesta=arma_puesta,
                                         magic_id=tipo if tipo != _cb.ATAQUE_NORMAL else 0)

            _tipo_golpe, _anim_golpe = _cb.golpe_de_arma(
                arma_puesta, duales=lleva_duales_ses(ses))
            _cierre_skill = None
            cast_time = _cb.calcular_cast_time(
                max(100, mag.get('cast_time', 100)),
                buffs=buffs_activos,
                habilidades=getattr(ses.personaje, 'habilidades', None),
                es_magia=is_magic_skill
            )
            if tipo != _cb.ATAQUE_NORMAL:
                if is_magic_skill:
                    salida_golpe = [
                        _cb.confirmar_cast(objetivo, m.tile_x, m.tile_y),
                        _cb.numero_de_dano(yo, objetivo, dano, tipo, efecto=atk_efecto,
                                           cast_time=cast_time, es_magia=True),
                    ]
                    _cierre_skill = _cb.cierre_de_dano(yo, objetivo, tipo,
                                                       efecto=atk_efecto, es_magia=True)
                else:
                    salida_golpe = [
                        _cb.confirmar_cast(objetivo, m.tile_x, m.tile_y),
                        _cb.numero_de_dano(yo, objetivo, dano, tipo, efecto=atk_efecto,
                                           cast_time=cast_time, es_magia=False),
                        _cb.ataque(yo, objetivo, _anim_golpe, _tipo_golpe),
                    ]
                    _cierre_skill = _cb.cierre_de_dano(yo, objetivo, tipo,
                                                       efecto=atk_efecto, es_magia=False)
            else:
                salida_golpe = [
                    _cb.ataque(yo, objetivo, _anim_golpe, _tipo_golpe),
                ]
            # Si FLECHAS_INFINITAS es False en configuracion.py y ataca con arco u honda,
            # descuenta 1 flecha/bolita de la ranura 4. Por defecto es True (municion infinita como en el Global).
            #
            # El import va AQUI y no se fia del `_cf` de mas arriba: dentro de
            # manejar() solo se liga en una rama que no siempre se pasa, y sin
            # el, esta linea reventaba con UnboundLocalError en CADA golpe.
            # Como esta antes del ses.enviar(), se perdia el ataque entero: ni
            # animacion, ni numero de dano, ni muerte del bicho.
            import configuracion as _cf_mun
            if not getattr(_cf_mun, 'FLECHAS_INFINITAS', True) and (_iv.es_arco(arma_puesta) or _iv.es_honda(arma_puesta)):
                _bolsa_am = getattr(ses, 'inventario', None) or {}
                if 4 in _bolsa_am and _iv.es_municion(_bolsa_am[4]):
                    _q_am = _cant_de(ses, 4) - 1
                    if _q_am > 0:
                        _cantidades(ses)[4] = _q_am
                    else:
                        _bolsa_am.pop(4, None)
                        _cantidades(ses).pop(4, None)
                    salida_golpe.extend(_refrescar(ses, [4]))
            ses.enviar(*salida_golpe)
            _tipo_num = _cb.TIPO_DANO_CRITICO if es_crit else _cb.TIPO_DANO
            _duales = lleva_duales_ses(ses)
            if _duales and tipo == _cb.ATAQUE_NORMAL:
                _d2 = m.recibir(total_atk) if m.vivo else 0
                _crit2 = random.random() < crit_prob
                if _crit2:
                    _d2 = int(round(_d2 * 1.5))
                _tipo2 = _cb.TIPO_DANO_CRITICO if _crit2 else _cb.TIPO_DANO
                _pkgs_dano = (*( (_cierre_skill,) if _cierre_skill else () ),
                              _cb.atributo(objetivo, m.porcentaje),
                              _cb.numero_flotante(objetivo, dano, _tipo_num),
                              *_pkg_debuff_m,
                              *_pkgs_drain,
                              *pkgs_sk, *pkgs_sp)
                _pkgs_dano2 = ((_cb.atributo(objetivo, m.porcentaje),
                                _cb.numero_flotante(objetivo, _d2, _tipo2))
                               if _d2 else
                               (_cb.atributo(objetivo, m.porcentaje),))
            else:
                _pkgs_dano = (*( (_cierre_skill,) if _cierre_skill else () ),
                              _cb.atributo(objetivo, m.porcentaje),
                              _cb.numero_flotante(objetivo, dano, _tipo_num),
                              *_pkg_debuff_m,
                              *_pkgs_drain,
                              *pkgs_sk, *pkgs_sp)
                _pkgs_dano2 = None
            _ret = 0.0
            try:
                bucle = asyncio.get_event_loop()
                if tipo != _cb.ATAQUE_NORMAL:
                    _ret = max(0.1, cast_time / 1000.0)
                else:
                    _ret = _cb.retraso_golpe(buffs_activos,
                                             getattr(ses.personaje, 'habilidades', None))
                bucle.call_later(_ret,
                                 lambda p=_pkgs_dano: ses.enviar_inmediato(*p))
                if _pkgs_dano2:
                    bucle.call_later(
                        _ret + _cb.RETRASO_SEGUNDA_MANO,
                        lambda p=_pkgs_dano2: ses.enviar_inmediato(*p))

                # Ember Brand / Holy Brand / Formula 65: detonar explosion AOE (14036..14040, radio 5, efecto 546)
                # sobre los enemigos circundantes y reproducir el efecto visual de explosion en area
                if mag.get('es_brand') and _brand_aoe_mag:
                    _area_br = max(1, _brand_aoe_mag.get('area', 5))
                    _cx_br, _cy_br = m.tile_x, m.tile_y
                    _aoe_id = int(mag.get('brand_aoe_id') or tipo)
                    _aoe_ef = int(_brand_aoe_mag.get('efecto') or atk_efecto or 546)
                    _ef2_aoe = _cb.efecto_secundario(_aoe_id) or _ef2
                    def _detonar_brand_aoe():
                        if not ses.personaje or getattr(ses, 'muerto', False):
                            return
                        # Reproducir el efecto visual de la explosion AOE sobre el epicentro
                        ses.enviar_inmediato(
                            _cb.numero_de_dano(yo, m.entity_id, 0, ataque=_aoe_id, efecto=_aoe_ef,
                                               cast_time=0, es_magia=is_magic_skill, tile_x=_cx_br, tile_y=_cy_br),
                            _cb.cierre_de_dano(yo, m.entity_id, ataque=_aoe_id, efecto=_aoe_ef,
                                               es_magia=is_magic_skill, tile_x=_cx_br, tile_y=_cy_br),
                        )
                        for _bm in list(bichos.values()):
                            if _bm.entity_id == m.entity_id or not _bm.vivo or getattr(_bm, 'encantado', False):
                                continue
                            if max(abs(_bm.tile_x - _cx_br), abs(_bm.tile_y - _cy_br)) <= _area_br:
                                _c_br = random.random() < crit_prob
                                _d_br = _bm.recibir(total_atk, es_magico=is_magic_skill, mult=mult_base_combo * (1.5 if _c_br else 1.0), var_pct=var_pct)
                                _pkgs_br = [
                                    _cb.numero_de_dano(yo, _bm.entity_id, _d_br, ataque=_aoe_id, efecto=_aoe_ef,
                                                       cast_time=0, es_magia=is_magic_skill),
                                    _cb.cierre_de_dano(yo, _bm.entity_id, ataque=_aoe_id, efecto=_aoe_ef,
                                                       es_magia=is_magic_skill),
                                    _cb.atributo(_bm.entity_id, _bm.porcentaje),
                                    _cb.numero_flotante(_bm.entity_id, _d_br, _cb.TIPO_DANO_CRITICO if _c_br else _cb.TIPO_DANO),
                                ]
                                if _ef2_aoe and random.random() * 100 < _ef2_aoe.get('prob', 100):
                                    _bm.aplicar_efecto(_ef2_aoe)
                                    if _ef2_aoe.get('magia') and _ef2_aoe.get('dur_ms'):
                                        _pkgs_br.append(struct.pack('<HIBBII', 0x001D, _bm.entity_id, 1, 4, _ef2_aoe['magia'], _ef2_aoe['dur_ms']))
                                ses.enviar_inmediato(*_pkgs_br)
                                if not _bm.vivo:
                                    _procesar_muerte_monstruo(ses, _bm, yo, addr, espera=0.0)
                                elif _bm.en_combate_con != yo:
                                    _bm.en_combate_con = yo
                    bucle.call_later(_ret + (0.05 if _brand_detona else 0.25), _detonar_brand_aoe)

                # EL COMBO. Strangle Strike V pega NUEVE veces y el IV seis;
                # todos los golpes usan mult_base_combo (habilidad + equipo + buffs)
                # y cada golpe tira su propio critico independiente (* 1.5).
                _combo = (_cb.combo_de(tipo)
                          if tipo != _cb.ATAQUE_NORMAL else None)
                if _combo and _combo.get('golpes', 1) > 1:
                    _sep = max(0.05, _combo.get('intervalo_ms', 200) / 1000.0)
                    for _k in range(1, _combo['golpes']):
                        def _golpe(n=_k):
                            if not getattr(m, 'vivo', False):
                                return
                            _c = random.random() < crit_prob
                            _mult_k = mult_base_combo * (1.5 if _c else 1.0)
                            _d = m.recibir(total_atk, es_magico=is_magic_skill, mult=_mult_k, var_pct=var_pct)
                            if not _d:
                                return
                            _sumar_sp(ses, yo, _sp_por_golpe(ses), addr)
                            ses.enviar_inmediato(
                                _cb.atributo(objetivo, m.porcentaje),
                                _cb.numero_flotante(
                                    objetivo, _d,
                                    _cb.TIPO_DANO_CRITICO if _c
                                    else _cb.TIPO_DANO))
                            if m.hp <= 0 or not getattr(m, 'vivo', True):
                                m.hp = 0
                                try:
                                    _procesar_muerte_monstruo(ses, m, yo, addr)
                                except Exception:
                                    log.exception(
                                        '[%s] fallo al matar con el combo'
                                        % addr)
                        bucle.call_later(_ret + _sep * _k, _golpe)
                    log.info('[%s] %s: combo de %d golpes cada %d ms'
                             % (addr, mag.get('nombre', tipo),
                                _combo['golpes'],
                                _combo.get('intervalo_ms', 200)))
            except Exception:
                ses.enviar(*_pkgs_dano)
                if _pkgs_dano2:
                    ses.enviar(*_pkgs_dano2)
            # Chain Lightning: rebote a objetivos cercanos
            _chain_jumps = mag.get('chain_jumps', 0) if tipo != _cb.ATAQUE_NORMAL else 0
            if _chain_jumps > 0 and ses.monstruos:
                _sub_spell_id = mag.get('sub_spell', 0)
                _sub_mag = _cb.datos_magia(_sub_spell_id) if _sub_spell_id else {}
                _sub_efecto = _cb.efecto_de_ataque(_sub_spell_id) if _sub_spell_id else 305
                _sub_dano_base = _sub_mag.get('dano_base', 0)
                _sub_denom = _sub_mag.get('base_denom', 200) or 200
                _sub_rango = max(6, _sub_mag.get('rango', 6))
                _crit_prob_chain = crit_prob

                def _hacer_chain_bounce(prev_eid=m.entity_id,
                                        prev_x=m.tile_x, prev_y=m.tile_y):
                    if not ses.personaje or getattr(ses, 'muerto', False):
                        return
                    blancos_usados = {prev_eid}
                    _prev_x, _prev_y = prev_x, prev_y
                    _prev_eid = prev_eid
                    habs = ses.personaje.habilidades if ses.personaje else None
                    buffs_act = getattr(ses.personaje, 'buffs', None)
                    st = _iv.stats(ses.inventario, habs, buffs=buffs_act, mejoras=_mejoras_de(ses))
                    ataque_j = struct.unpack_from('<I', st, 2 + 44)[0]
                    _sub_mult = ((_sub_dano_base / float(_sub_denom))
                                 if _sub_dano_base > 0 else 1.0)
                    for _salto in range(_chain_jumps):
                        mejor = None
                        mejor_dist = 999
                        for mb in (ses.monstruos or {}).values():
                            # Igual que arriba: el rebote no salta a un aliado.
                            if (mb.entity_id in blancos_usados or not mb.vivo
                                    or getattr(mb, 'encantado', False)):
                                continue
                            dist = max(abs(mb.tile_x - _prev_x),
                                       abs(mb.tile_y - _prev_y))
                            if dist <= _sub_rango and dist < mejor_dist:
                                mejor = mb
                                mejor_dist = dist
                        if mejor is None:
                            break
                        blancos_usados.add(mejor.entity_id)
                        _crit_j = random.random() < _crit_prob_chain
                        _mult_j = 1.5 if _crit_j else 1.0
                        dano_j = mejor.recibir(ataque_j, es_magico=True,
                                               mult=_sub_mult * _mult_j,
                                               var_pct=0.05)
                        _tipo_j = (_cb.TIPO_DANO_CRITICO if _crit_j
                                   else _cb.TIPO_DANO)
                        ses.enviar_inmediato(
                            _cb.numero_de_dano(
                                _prev_eid, mejor.entity_id, dano_j,
                                _sub_spell_id or tipo, efecto=_sub_efecto,
                                cast_time=0, es_magia=True),
                            _cb.cierre_de_dano(
                                _prev_eid, mejor.entity_id,
                                ataque=_sub_spell_id or tipo,
                                efecto=_sub_efecto, es_magia=True),
                            _cb.atributo(mejor.entity_id, mejor.porcentaje),
                            _cb.numero_flotante(mejor.entity_id, dano_j,
                                                _tipo_j),
                        )
                        if not mejor.vivo:
                            _procesar_muerte_monstruo(ses, mejor, yo, addr,
                                                      espera=0.0)
                        else:
                            if mejor.en_combate_con != yo:
                                mejor.en_combate_con = yo
                                mejor.ultimo_ataque = 0
                        _prev_eid = mejor.entity_id
                        _prev_x = mejor.tile_x
                        _prev_y = mejor.tile_y
                    log.info(f"[{addr}] Chain Lightning: "
                             f"{len(blancos_usados) - 1} rebotes")

                try:
                    _chain_delay = _ret + 0.3
                    asyncio.get_event_loop().call_later(
                        _chain_delay, _hacer_chain_bounce)
                except Exception:
                    _hacer_chain_bounce()
            if m.vivo:
                # El monstruo no contraataca desde aqui. Solo se lo marca en
                # combate y la IA le da el turno cuando le toca segun su
                # cadencia. Antes habia DOS caminos que le hacian pegar -- este
                # y la IA -- y cuando coincidian soltaba dos golpes casi al
                # mismo tiempo, que es lo que se veia con las Lilys.
                if m.en_combate_con != yo:
                    m.en_combate_con = yo
                    # Que conteste en el tick siguiente, no dentro de un
                    # ciclo entero. El golpe sale ya y el dano llega cuando
                    # termina la animacion, asi que no pega instantaneo: lo
                    # que se quitaba era la espera muerta de antes.
                    m.ultimo_ataque = 0
                log.debug(f"[{addr}] pego {dano} al {m.nombre} "
                          f"({m.porcentaje}%), contraataque procesado")
                return


            # --- Monstruo Muerto: Avisar muerte, Despawn con animacion, Respawn, EXP y Botin ---
            # Gnash y compania devuelven HP y MP solo SI el golpe mata, asi
            # que va aqui y no con el robo de Forbidden Curse, que entra en
            # todos los golpes.
            _cura_matar = _recuperar_al_matar(ses, yo, mag, addr)
            if _cura_matar:
                ses.enviar(*_cura_matar)
            _procesar_muerte_monstruo(ses, m, yo, addr, espera=_ret)
            return

        # --- el cliente pide el mapa nuevo -------------------------------
        # Tras un 0x000C el cliente contesta con un 0x0009 vacio y espera la
        # secuencia de entrada otra vez, ya con la ficha en el mapa nuevo.
        if opcode == 0x0009 and ses.rol == 'mundo' and ses.personaje:
            import inventario as _iv2
            import clases as _cl2
            import combate as _cb2
            import login as _lg2
            p = ses.personaje
            ses.monstruos = _monstruos_de(p.stage)
            # Cargar la secuencia completa oficial del nuevo mapa (aparicion, capas, barra, stats, spawns y atributos)
            for sub in _lg2.secuencia(p):
                ses.enviar(sub)
            try:
                _entrar_en_sala(ses, addr)
            except Exception:
                log.exception('no se pudo entrar en la sala del mapa')
            ses.enviar(_stats_ses(ses))
            if p.habilidades:
                _ids = [h[0] for h in p.habilidades]
                # OJO: el arbol lleva nivel y experiencia de cada
                # habilidad, asi que hay que pasarle p.habilidades entero.
                # Pasando solo los ids, arbol() pone nivel 1 y exp 0 y el
                # panel salia reseteado a 0.00% despues de cada cambio de
                # mapa o de revivir.
                ses.enviar(_cl2.arbol(p.habilidades))
                _hech = _cl2.hechizos_iniciales(_ids)
                _todos_hech = [n for n, _ in _hech]
                if getattr(p, 'hechizos_aprendidos', None):
                    _todos_hech = sorted(set(_todos_hech) | set(p.hechizos_aprendidos))
                if _todos_hech:
                    ses.enviar(*_cl2.otorgar_hechizos(p.entity_id, _todos_hech))
            for _inv_attr, _off_x in (('invocacion', 1), ('invocacion2', -1)):
                inv = getattr(ses, _inv_attr, None)
                if inv and inv.get('es_mercenario'):
                    setattr(ses, _inv_attr, None)
                    continue
                if inv:
                    inv['tile_x'] = p.tile_x + _off_x
                    inv['tile_y'] = p.tile_y
                    inv['objetivo'] = None
                    ses.enviar(
                        struct.pack('<HIBBI', 0x0013, p.entity_id, 1, 0x3d, inv['entity_id']),
                        struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 0x2a, inv['entity_id'], 0),
                        _lg2.spawn_invocacion(inv['entity_id'], inv['npc_type'], inv['nombre'], (inv['tile_x'], inv['tile_y']), sprite=inv['sprite']),
                        _cb2.atributo(inv['entity_id'], 100, _cb2.KIND_HP),
                        struct.pack('<HIBBI', 0x0013, inv['entity_id'], 1, 0x3c, p.entity_id)
                    )

            # Re-spawn de la mascota activa al cambiar de mapa
            f_pet = getattr(p, 'mascota', None)
            if isinstance(f_pet, dict) and f_pet.get('fuera'):
                import mascotas as _pet
                f_pet['entidad'] = _pet_siguiente_entidad(ses)
                _r_p = int(f_pet.get('ranura') if f_pet.get('ranura') is not None else 20)
                f_pet['instancia'] = 1000 + _r_p
                px_pet = (p.tile_x or 80) + 1
                py_pet = (p.tile_y or 80)
                f_pet['x'] = px_pet
                f_pet['y'] = py_pet
                f_pet['proximo_paso'] = 0.0
                ses.pet_entity_id = f_pet['entidad']
                ses.pet_tile = [px_pet, py_pet]
                est_pet = dict(f_pet)
                est_pet.update({
                    'x': px_pet, 'y': py_pet,
                    'dueno': p.entity_id, 'dueno_nombre': p.nombre,
                    'tipo': f_pet.get('tipo', 0),
                })
                _pkgs_pet = [
                    _pet.enlazar(p.entity_id, f_pet['entidad']),
                    struct.pack('<HIBBI', 0x0013, p.entity_id, 1, 0x3F, f_pet['entidad']),
                    _pet.armar(f_pet),
                    *_refrescar(ses, [_r_p]),
                    _pet.entidad_mundo(_pet_plantilla(), est_pet),
                    _pet.armar(f_pet),
                    _cb2.atributo(f_pet['entidad'], max(1, int(f_pet.get('hp') or f_pet.get('hp_max') or 1)), _cb2.KIND_HP),
                ]
                if f_pet.get('saciedad', 0) > 100:
                    _pkgs_pet.append(struct.pack('<HIBBII', 0x001D, f_pet['entidad'], 1, 4, 3796, 3436877059))
                ses.enviar(*_pkgs_pet)
                import presencia as _pr
                _pr.notificar_mascota_spawn(ses)

            # Restauracion de buffs activos tras cambio de mapa
            now_t = time.time()
            if getattr(p, 'buffs', None):
                for b_id, b_data in list(p.buffs.items()):
                    if isinstance(b_data, dict):
                        rem_s = b_data.get('fin', 0) - now_t
                        if rem_s > 0:
                            rem_ms = int(rem_s * 1000)
                            pkgs_rest = [struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 4, int(b_id), rem_ms)]
                            if b_data.get('es_transform') and b_data.get('mag', {}).get('trans_sprite'):
                                pkgs_rest.append(_cb2.atributo(p.entity_id, b_data['mag']['trans_sprite'], _cb2.KIND_TRANSFORM))
                            ses.enviar(*pkgs_rest)
                            def _expirar_restaurado(sk_id=int(b_id), fin=b_data['fin']):
                                buffs_act = getattr(p, 'buffs', None)
                                act = buffs_act.get(sk_id) if buffs_act else None
                                if not act or act.get('fin') != fin:
                                    return
                                buffs_act.pop(sk_id, None)
                                pks = [struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 4, sk_id, 0)]
                                if act.get('es_transform'):
                                    pks.append(_cb2.atributo(p.entity_id, 0, _cb2.KIND_TRANSFORM))
                                pks.append(_stats_ses(ses))
                                ses.enviar_inmediato(*pks)
                            asyncio.get_event_loop().call_later(rem_s, _expirar_restaurado)
                        else:
                            p.buffs.pop(b_id, None)

            ses.portal_pisado = None
            ses.mapa_cambiado_en = time.time()
            try:
                import presencia as _pres
                _pres.entrar(ses, p.stage)
            except Exception:
                log.exception('presencia: fallo al entrar al mapa en 0x0009')

            # Sincronizacion de housing en cambio de mapa
            try:
                import casas as _cs_s
                if p.stage == 500:
                    ses.house_room_ready = True
                    _c_cur = getattr(ses, 'casa_visitando', None)
                    if not _c_cur:
                        _c_cur = _cs_s.obtener_o_crear_casa(p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
                        ses.casa_visitando = _c_cur
                    if getattr(ses, 'house_furnish_pending', False) and _c_cur.owner_id == p.char_id:
                        _ocultar_interactivos_casa(ses)
                        ses.enviar(*_casa_paquetes_decorar(ses, _c_cur))
                        ses.house_furnishing = True
                        ses.house_furnish_pending = False
                    else:
                        ses.enviar(_cs_s.pkt_visit_furniture_sync(_c_cur.placed_furniture))
                    _lv, _prev_m, _next_m = _cs_s.info_nivel(_c_cur.calcular_magia())
                    _rnk = _cs_s.rango_casa(_c_cur)
                    _v_rem = 1 if (p.char_id not in _c_cur.voted_users_today) else 0
                    ses.enviar(_cs_s.pkt_house_info(_lv, _c_cur.calcular_magia(), _next_m, _prev_m,
                                                    _c_cur.bonus_pct, _c_cur.cleanliness,
                                                    _c_cur.votes_total, _c_cur.votes_today,
                                                    _c_cur.visitors_total, _v_rem, _rnk,
                                                    10 if _c_cur.is_open else 1))
                    ses.enviar(_cs_s.pkt_house_name(_c_cur.house_name))
                    if _c_cur.owner_id == p.char_id:
                        import inventario as _iv_load
                        for _sl in range(477, 487):
                            _sl_str = str(_sl)
                            if _sl in ses.inventario:
                                _it_p = ses.inventario[_sl]
                                if _sl_str not in _c_cur.care_pets:
                                    _sp_sync = _iv_load.sprite_de_mascota(_it_p)
                                    _nom_sync = _nombre_item(_it_p)
                                    _pm_sync = getattr(p, 'mascotas', {}) or {}
                                    _fp_sync = _pm_sync.get(_sl_str) or {}
                                    if _fp_sync.get('nombre'):
                                        _nom_sync = _fp_sync['nombre']
                                    if _fp_sync.get('tipo'):
                                        _sp_sync = _fp_sync['tipo']
                                    _c_cur.care_pets[_sl_str] = {
                                        'item_id': _it_p,
                                        'name': _nom_sync,
                                        'sprite': _sp_sync,
                                        'slot': _sl,
                                        'time': int(time.time()),
                                        'tile': [36, 28]
                                    }
                            elif _sl_str in _c_cur.care_pets:
                                _c_cur.care_pets.pop(_sl_str, None)
                    import login as _lg_pet_sp
                    for _sid, _p_inf in list(_c_cur.care_pets.items()):
                        try:
                            _pslot = int(_sid)
                            _peid = 8101 + (_pslot - 477)
                            _psp = _p_inf.get('sprite') or 44033
                            _pnom = _p_inf.get('name') or 'Pet'
                            _pt = _p_inf.get('tile') or [36, 28]
                            ses.enviar(_lg_pet_sp._npc_spawn(_peid, 1, _pnom, (_pt[0], _pt[1]), sprite=_psp, klass=200, direccion=6))
                        except Exception:
                            pass
                elif p.stage in _cs_s.MAPAS_EXHIBICION:
                    _c_own = _cs_s.obtener_o_crear_casa(p.char_id, p.nombre, raw_data=getattr(p, 'casa', None))
                    _lv, _prev_m, _next_m = _cs_s.info_nivel(_c_own.calcular_magia())
                    _rnk = _cs_s.rango_casa(_c_own)
                    _v_rem = 1 if (p.char_id not in _c_own.voted_users_today) else 0
                    _ui_st = 10 if _c_own.is_open else 1
                    ses.enviar(_cs_s.pkt_house_info(_lv, _c_own.calcular_magia(), _next_m, _prev_m,
                                                    _c_own.bonus_pct, _c_own.cleanliness,
                                                    _c_own.votes_total, _c_own.votes_today,
                                                    _c_own.visitors_total, _v_rem, _rnk,
                                                    _ui_st))
                    ses.enviar(_cs_s.pkt_house_name(_c_own.house_name))
            except Exception:
                log.exception('casas: fallo al sincronizar housing en 0x0009')

            log.info(f"[{addr}] mapa cargado exitosamente: stage {p.stage} "
                     f"tile ({p.tile_x},{p.tile_y})")
            return

        # --- comprar en una tienda ---------------------------------------
        # La ventana la abre el cliente solo; aqui solo se atiende la compra.
        # --- compra en tienda NPC ---------------------------------------
        # Medido en Celestia al comprar diez pociones rojas y diez azules de
        # una sola vez:
        #     02000000 | 42000000 0a000000 | 43000000 0a000000
        # o sea [u32 n] y luego n veces [u32 item_id][u32 cantidad]. Antes se
        # leia UN solo item por mensaje, por eso no se podia comprar mas de
        # una cosa a la vez ni llevarse varias unidades.
        if opcode == 0x0027 and ses.rol == 'mundo' and cuerpo and len(cuerpo) >= 4:
            import clases as _c
            import inventario as _iv
            if getattr(ses, 'inventario', None) is None:
                return
            n_items = struct.unpack_from('<I', cuerpo, 0)[0]
            pedido = []
            off = 4
            for _ in range(min(n_items, 64)):
                if off + 8 > len(cuerpo):
                    break
                item_id, cant = struct.unpack_from('<II', cuerpo, off)
                off += 8
                if item_id and cant:
                    pedido.append((item_id, min(int(cant), 9999)))
            if not pedido:
                return

            total_pedido = sum(_precio_compra(i) * c for i, c in pedido)
            if getattr(ses, 'oro', 0) < total_pedido:
                log.warning(f"[{addr}] compra rechazada: cuesta {total_pedido} y hay "
                            f"{getattr(ses, 'oro', 0)}")
                return
            cid = ses.personaje.char_id if ses.personaje else 4980

            # El cartel del oro va primero y luego uno por item, igual que en
            # la captura: "680Gold" y despues cada nombre.
            tocadas = []
            avisos = []
            total = 0
            for item_id, cant in pedido:
                _r = _meter(ses, item_id, cant)
                if _r is None:
                    log.warning(f"[{addr}] compra: no entra {item_id} x{cant}, "
                                f"la mochila esta llena")
                    avisos.append(_c.aviso('Your backpack is full.', tipo=0))
                    break
                total += _precio_compra(item_id) * cant
                tocadas.append(_r)
                avisos.append(_c.aviso(_nombre_item(item_id), tipo=0,
                                       msg_id=_c.MSG_ITEM))
            if not tocadas:
                if avisos:
                    ses.enviar(*avisos)
                return
            ses.oro -= total
            if ses.personaje:
                ses.personaje.oro = ses.oro
            ses.enviar(*_refrescar(ses, tocadas, con_oro=True),
                       _c.aviso(f'{total} Gold', tipo=0, msg_id=_c.MSG_PAGO),
                       *avisos)
            _guardar_bolsa(ses, cid)
            if getattr(ses, 'usuario', None):
                cuentas.guardar_oro(ses.usuario, cid, ses.oro)
            log.info(f"[{addr}] compra: {pedido} por {total}; "
                     f"quedan {ses.oro} de oro")
            return

        # --- venta a tienda NPC ------------------------------------------
        # Medido al vender 5 de una pila y 6 de otra:
        #     02000000 | 6b480300 2e23b26a 05000000 | 6c480300 2e23b26a 06000000
        # o sea [u32 n] y luego n veces [u32 instancia][u32 sello][u32 cant].
        # Los OCHO primeros bytes son el id de instancia del item, no el
        # numero de casilla: leerlos como casilla no casaba nunca, no se
        # sacaba nada del inventario y la venta pagaba 0.
        if opcode == 0x0028 and ses.rol == 'mundo' and cuerpo and ses.personaje:
            import clases as _c
            import inventario as _iv
            bolsa = getattr(ses, 'inventario', {})
            cid = ses.personaje.char_id
            if len(cuerpo) < 4:
                return
            n_items = struct.unpack_from('<I', cuerpo, 0)[0]
            oro_ganado = 0
            tocadas = []
            off = 4
            for _ in range(min(n_items, 64)):
                if off + 12 > len(cuerpo):
                    break
                inst = cuerpo[off:off + 8]
                cant = struct.unpack_from('<I', cuerpo, off + 8)[0]
                off += 12
                ranura = _iv.ranura_de_instancia(_instancias(ses), inst,
                                                 bolsa, cid)
                if ranura is None or _iv.es_equipo(ranura):
                    log.warning(f"[{addr}] venta: instancia {inst.hex()} "
                                f"no esta en la mochila")
                    continue
                it_id = bolsa[ranura]
                vendidas = _sacar(ses, ranura, cant)
                if not vendidas:
                    continue
                ganancia = _precio_venta(it_id) * vendidas
                oro_ganado += ganancia
                tocadas.append(ranura)
                log.info(f"[{addr}] vendio {it_id} x{vendidas} de la casilla "
                         f"{ranura} por {ganancia} de oro")
            if not oro_ganado:
                return
            ses.oro = min(2000000000, getattr(ses, 'oro', 0) + oro_ganado)
            ses.personaje.oro = ses.oro
            ses.enviar(*_refrescar(ses, tocadas, con_oro=True),
                       _c.aviso(f"{oro_ganado} Gold", tipo=0, msg_id=_c.MSG_ITEM))
            _guardar_bolsa(ses, cid)
            if getattr(ses, 'usuario', None):
                cuentas.guardar_oro(ses.usuario, cid, ses.oro)
            return

        # --- puestos de venta entre jugadores (Stalls: 0x0022..0x0026) ----
        # Desensamblado en Angel.exe:
        #   C2S 0x0022 (0x619A60): salestart (Set Stall + Hawk + Sell/Buy tabs)
        #   C2S 0x0023 (0x61A250): saleclose (Close Stall)
        #   C2S 0x0024 (0x61A2D0): ver puesto de otro jugador -> S2C 0x0032
        #   C2S 0x0025 (0x61B8B0): comprar de la pestana Sell -> S2C 0x0033
        #   C2S 0x0026 (0x61BD90): vender a la pestana Buy   -> S2C 0x004A
        if opcode == 0x0022 and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 61:
            if getattr(ses, 'muerto', False) or getattr(ses, 'puesto', None):
                return
            import inventario as _iv
            import presencia as _pres
            bolsa = getattr(ses, 'inventario', {})
            cid = ses.personaje.char_id
            n_sell, n_buy, _ent_pkt = struct.unpack_from('<III', cuerpo, 0)
            hawk_raw = cuerpo[12:61].split(b'\x00', 1)[0]
            hawk = hawk_raw.decode('latin-1', 'replace').strip()
            if not hawk:
                hawk = f"{ses.personaje.nombre}'s Stall"

            off = 61
            ventas = []
            ranuras_usadas = set()
            ranuras_max = _iv.limite_ranuras_puesto(bolsa)
            for _ in range(min(int(n_sell), ranuras_max)):
                if off + 16 > len(cuerpo):
                    break
                inst8, cant, precio = struct.unpack_from('<8sII', cuerpo, off)
                off += 16
                if cant <= 0 or precio <= 0:
                    continue
                ranura = _iv.ranura_de_instancia(_instancias(ses), inst8, bolsa, cid)
                if (ranura is None or _iv.es_equipo(ranura)
                        or ranura == _iv.RANURA_ORO or ranura in ranuras_usadas):
                    log.warning(f"[{addr}] puesto 0x0022: instancia {inst8.hex()} no valida (ranura={ranura})")
                    continue
                ranura = int(ranura)
                hay = _cant_de(ses, ranura)
                if hay <= 0:
                    continue
                cant_real = min(int(cant), hay)
                _instancias(ses)[ranura] = inst8
                ranuras_usadas.add(ranura)
                ventas.append({
                    'instancia': inst8,
                    'ranura': ranura,
                    'item_id': int(bolsa[ranura]),
                    'cantidad': cant_real,
                    'precio': min(int(precio), 2000000000),
                })

            compras = []
            for _ in range(min(int(n_buy), ranuras_max)):
                if off + 16 > len(cuerpo):
                    break
                item_id, _cero, cant, precio = struct.unpack_from('<IIII', cuerpo, off)
                off += 16
                if item_id <= 0 or cant <= 0 or precio <= 0:
                    continue
                compras.append({
                    'item_id': int(item_id),
                    'cantidad': min(int(cant), 9999),
                    'precio': min(int(precio), 2000000000),
                })

            if not ventas and not compras:
                return

            if getattr(ses, 'recoleccion', None):
                _parar_recoleccion(ses)
            if getattr(ses, 'sentado', False):
                ses.sentado = False

            pos_x = int(getattr(ses.personaje, 'tile_x', 0) or 0)
            pos_y = int(getattr(ses.personaje, 'tile_y', 0) or 0)
            ses.puesto = {
                'hawk': hawk,
                'ventas': ventas,
                'compras': compras,
                'posicion': (pos_x, pos_y),
            }

            # S2C 0x0030 (FUN_00603f60): confirma apertura al dueno (salestartok)
            pkt_ok = bytearray(struct.pack('<HII', 0x0030, len(ventas), len(compras)))
            for v in ventas:
                pkt_ok += struct.pack('<8sII', v['instancia'], v['cantidad'], v['precio'])
            for c in compras:
                pkt_ok += struct.pack('<IIII', c['item_id'], 0, c['cantidad'], c['precio'])
            ses.enviar(bytes(pkt_ok))
            _pres.notificar_puesto(ses)
            log.info(f"[{addr}] puesto abierto '{hawk}': {len(ventas)} en venta, {len(compras)} en compra")
            return

        if opcode == 0x0023 and ses.rol == 'mundo' and ses.personaje:
            _cerrar_puesto(ses, avisar_dueno=True)
            log.info(f"[{addr}] puesto cerrado")
            return

        if opcode == 0x0024 and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 4:
            import clases as _c
            import presencia as _pres
            target_eid = struct.unpack_from('<I', cuerpo, 0)[0]
            vendedor = _pres.sesion_por_entidad(ses, target_eid)
            if vendedor is None and ses.personaje.entity_id == target_eid:
                vendedor = ses
            if not vendedor or not getattr(vendedor, 'puesto', None) or not getattr(vendedor, 'personaje', None):
                ses.enviar(_c.aviso('That stall is no longer open.', tipo=0))
                return
            ses.enviar(_paquete_vista_puesto(vendedor))
            log.info(f"[{addr}] viendo puesto de {vendedor.personaje.nombre} (eid={target_eid})")
            return

        if opcode == 0x0025 and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 8:
            import copy as _copy
            import clases as _c
            import inventario as _iv
            import presencia as _pres
            target_eid, n_items = struct.unpack_from('<II', cuerpo, 0)
            vendedor = _pres.sesion_por_entidad(ses, target_eid)
            if (not vendedor or vendedor is ses
                    or not getattr(vendedor, 'puesto', None)
                    or not getattr(vendedor, 'personaje', None)):
                ses.enviar(_c.aviso('That stall is no longer open.', tipo=0))
                return

            puesto = vendedor.puesto
            ventas = puesto.get('ventas') or []
            bolsa_vend = getattr(vendedor, 'inventario', {})
            cid_comp = ses.personaje.char_id
            cid_vend = vendedor.personaje.char_id

            tocadas_comp = []
            tocadas_vend = []
            avisos_comp = []
            avisos_vend = []
            pkts_0033 = []
            oro_total = 0

            off = 8
            for _ in range(min(int(n_items), 50)):
                if off + 12 > len(cuerpo):
                    break
                inst8, cant_pedida = struct.unpack_from('<8sI', cuerpo, off)
                off += 12
                if cant_pedida <= 0:
                    continue
                v = next((x for x in ventas if x['instancia'] == inst8 and x['cantidad'] > 0), None)
                if not v:
                    continue
                r_vend = int(v['ranura'])
                item_id = int(v['item_id'])
                if bolsa_vend.get(r_vend) != item_id:
                    v['cantidad'] = 0
                    continue
                disp = min(int(v['cantidad']), _cant_de(vendedor, r_vend))
                cant_real = min(int(cant_pedida), disp)
                if cant_real <= 0:
                    continue
                precio_u = int(v['precio'])
                costo = cant_real * precio_u
                if getattr(ses, 'oro', 0) < costo:
                    avisos_comp.append(_c.aviso('Not enough Gold.', tipo=0))
                    break

                # Comprobar espacio antes de transferir
                if not (_iv.es_apilable(item_id) and any(
                        int(it) == item_id and int(rk) != _iv.RANURA_ORO and not _iv.es_equipo(int(rk))
                        for rk, it in ses.inventario.items())):
                    if _ranura_libre(ses.inventario) is None:
                        avisos_comp.append(_c.aviso('Your backpack is full.', tipo=0))
                        break

                mej_copia = None
                pet_copia = None
                if not _iv.es_apilable(item_id):
                    mej_orig = (getattr(vendedor.personaje, 'mejoras', None) or {}).get(r_vend)
                    if mej_orig:
                        mej_copia = _copy.deepcopy(mej_orig)
                    mascotas_vend = getattr(vendedor.personaje, 'mascotas', None) or {}
                    pet_orig = mascotas_vend.get(str(r_vend)) or mascotas_vend.get(r_vend)
                    if pet_orig:
                        pet_copia = _copy.deepcopy(pet_orig)

                sacadas = _sacar(vendedor, r_vend, cant_real)
                if sacadas <= 0:
                    continue
                r_comp = _meter(ses, item_id, sacadas)
                if r_comp is None:
                    # Revertir si por alguna razon no cupo
                    _meter(vendedor, item_id, sacadas)
                    break

                if mej_copia is not None:
                    if getattr(ses.personaje, 'mejoras', None) is None:
                        ses.personaje.mejoras = {}
                    ses.personaje.mejoras[int(r_comp)] = mej_copia
                if pet_copia is not None:
                    if not hasattr(ses.personaje, 'mascotas') or not isinstance(ses.personaje.mascotas, dict):
                        ses.personaje.mascotas = {}
                    pet_copia['ranura'] = int(r_comp)
                    pet_copia['item'] = item_id
                    pet_copia['instancia'] = 1000 + int(r_comp)
                    pet_copia['fuera'] = False
                    pet_copia['entidad'] = None
                    ses.personaje.mascotas[str(r_comp)] = pet_copia

                costo_real = sacadas * precio_u
                ses.oro = max(0, getattr(ses, 'oro', 0) - costo_real)
                ses.personaje.oro = ses.oro
                vendedor.oro = min(2000000000, getattr(vendedor, 'oro', 0) + costo_real)
                vendedor.personaje.oro = vendedor.oro
                oro_total += costo_real

                v['cantidad'] = max(0, int(v['cantidad']) - sacadas)
                tocadas_comp.append(int(r_comp))
                tocadas_vend.append(r_vend)
                pkts_0033.append(struct.pack('<H8sI', 0x0033, inst8, sacadas))
                nom_it = _nombre_item(item_id)
                avisos_comp.append(_c.aviso(
                    nom_it if sacadas == 1 else f'{sacadas}x {nom_it}',
                    tipo=0, msg_id=_c.MSG_ITEM))
                avisos_vend.append(_c.aviso(
                    f"Sold {sacadas}x {nom_it} for {costo_real} Gold.", tipo=0))

            puesto['ventas'] = [x for x in ventas if int(x.get('cantidad', 0)) > 0]

            if not tocadas_comp:
                if avisos_comp:
                    ses.enviar(*avisos_comp)
                return

            ses.enviar(*_refrescar(ses, tocadas_comp, con_oro=True),
                       _c.aviso(f'{oro_total} Gold', tipo=0, msg_id=_c.MSG_PAGO),
                       *avisos_comp,
                       _paquete_vista_puesto(vendedor))
            _guardar_bolsa(ses, cid_comp)
            if getattr(ses, 'usuario', None):
                cuentas.guardar_oro(ses.usuario, cid_comp, ses.oro)

            vendedor.enviar(*pkts_0033,
                            *_refrescar(vendedor, tocadas_vend, con_oro=True),
                            *avisos_vend)
            vendedor.volcar()
            _guardar_bolsa(vendedor, cid_vend)
            if getattr(vendedor, 'usuario', None):
                cuentas.guardar_oro(vendedor.usuario, cid_vend, vendedor.oro)
            log.info(f"[{addr}] compro en puesto de {vendedor.personaje.nombre} por {oro_total} de oro")
            return

        if opcode == 0x0026 and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 8:
            import clases as _c
            import inventario as _iv
            import presencia as _pres
            target_eid, n_items = struct.unpack_from('<II', cuerpo, 0)
            comprador = _pres.sesion_por_entidad(ses, target_eid)
            if (not comprador or comprador is ses
                    or not getattr(comprador, 'puesto', None)
                    or not getattr(comprador, 'personaje', None)):
                ses.enviar(_c.aviso('That stall is no longer open.', tipo=0))
                return

            puesto = comprador.puesto
            compras = puesto.get('compras') or []
            cid_vend = ses.personaje.char_id
            cid_comp = comprador.personaje.char_id

            tocadas_vend = []
            tocadas_comp = []
            avisos_vend = []
            avisos_comp = []
            pkts_004a = []
            oro_total = 0

            off = 8
            for _ in range(min(int(n_items), 50)):
                if off + 8 > len(cuerpo):
                    break
                item_id, cant_ofrecida = struct.unpack_from('<II', cuerpo, off)
                off += 8
                if item_id <= 0 or cant_ofrecida <= 0:
                    continue
                c_entry = next((x for x in compras
                                if int(x['item_id']) == int(item_id) and int(x['cantidad']) > 0), None)
                if not c_entry:
                    continue
                precio_u = int(c_entry['precio'])
                if precio_u <= 0:
                    continue

                # Buscar ranuras de mochila del visitante que tengan ese item_id
                ranuras_disp = [
                    int(r) for r, it in sorted(ses.inventario.items())
                    if int(it) == int(item_id) and int(r) != _iv.RANURA_ORO and not _iv.es_equipo(int(r))
                ]
                total_en_bolsa = sum(_cant_de(ses, r) for r in ranuras_disp)
                max_pagable = getattr(comprador, 'oro', 0) // precio_u
                cant_real = min(int(cant_ofrecida), int(c_entry['cantidad']),
                                total_en_bolsa, max_pagable)
                if cant_real <= 0:
                    if max_pagable <= 0:
                        avisos_vend.append(_c.aviso('The stall owner does not have enough Gold.', tipo=0))
                    continue

                # Comprobar espacio en la mochila del dueno del puesto
                if not (_iv.es_apilable(item_id) and any(
                        int(it) == int(item_id) and int(rk) != _iv.RANURA_ORO and not _iv.es_equipo(int(rk))
                        for rk, it in comprador.inventario.items())):
                    if _ranura_libre(comprador.inventario) is None:
                        avisos_vend.append(_c.aviso("The stall owner's backpack is full.", tipo=0))
                        break

                por_sacar = cant_real
                sacadas_total = 0
                for r_v in ranuras_disp:
                    if por_sacar <= 0:
                        break
                    s = _sacar(ses, r_v, por_sacar)
                    if s > 0:
                        por_sacar -= s
                        sacadas_total += s
                        tocadas_vend.append(r_v)

                if sacadas_total <= 0:
                    continue

                r_c = _meter(comprador, int(item_id), sacadas_total)
                if r_c is None:
                    _meter(ses, int(item_id), sacadas_total)
                    break

                tocadas_comp.append(int(r_c))
                costo_real = sacadas_total * precio_u
                comprador.oro = max(0, getattr(comprador, 'oro', 0) - costo_real)
                comprador.personaje.oro = comprador.oro
                ses.oro = min(2000000000, getattr(ses, 'oro', 0) + costo_real)
                ses.personaje.oro = ses.oro
                oro_total += costo_real

                c_entry['cantidad'] = max(0, int(c_entry['cantidad']) - sacadas_total)
                pkts_004a.append(struct.pack('<HIII', 0x004A, int(item_id), 0, sacadas_total))
                nom_it = _nombre_item(int(item_id))
                avisos_vend.append(_c.aviso(
                    f"Sold {sacadas_total}x {nom_it} for {costo_real} Gold.", tipo=0))
                avisos_comp.append(_c.aviso(
                    nom_it if sacadas_total == 1 else f'{sacadas_total}x {nom_it}',
                    tipo=0, msg_id=_c.MSG_ITEM))

            puesto['compras'] = [x for x in compras if int(x.get('cantidad', 0)) > 0]

            if not tocadas_vend:
                if avisos_vend:
                    ses.enviar(*avisos_vend)
                return

            ses.enviar(*_refrescar(ses, tocadas_vend, con_oro=True),
                       _c.aviso(f'{oro_total} Gold', tipo=0, msg_id=_c.MSG_ITEM),
                       *avisos_vend,
                       _paquete_vista_puesto(comprador))
            _guardar_bolsa(ses, cid_vend)
            if getattr(ses, 'usuario', None):
                cuentas.guardar_oro(ses.usuario, cid_vend, ses.oro)

            comprador.enviar(*pkts_004a,
                             *_refrescar(comprador, tocadas_comp, con_oro=True),
                             _c.aviso(f'{oro_total} Gold', tipo=0, msg_id=_c.MSG_PAGO),
                             *avisos_comp)
            comprador.volcar()
            _guardar_bolsa(comprador, cid_comp)
            if getattr(comprador, 'usuario', None):
                cuentas.guardar_oro(comprador.usuario, cid_comp, comprador.oro)
            log.info(f"[{addr}] vendio al puesto de {comprador.personaje.nombre} por {oro_total} de oro")
            return

        # --- separar un monton en dos -------------------------------------
        # Medido al sacar una pocion de una pila de seis:
        #     0b | 2b00 | 2900 | 01000000
        # o sea [u8 contenedor][u16 casilla destino][u16 casilla origen]
        # [u32 cantidad]. La pila nueva estrena id de instancia: en la
        # captura la de origen sigue con 215293 y la nueva sale con 215300.
        # ---------------- Los seis sistemas del README ----------------
        # Los opcodes salen de desensamblar las nativas de Lua
        # (tools/opcodes_de_nativas.py):
        #
        #     opencollectionbook  0x0032      sendcollect  0x0033
        #
        # El CUERPO de cada uno todavia no esta medido, asi que esto lee lo
        # que puede y, sobre todo, no se traga el paquete en silencio: si
        # llega algo que no encaja, lo dice en el log con los bytes. Sin
        # eso no hay forma de ir ajustandolo.
        # Los dos son SUBTIPOS del 0x0016, no opcodes sueltos: el cliente
        # los manda como [u16 0x0016][u8 subtipo][u32 dato], que es lo que
        # arma la funcion 0x614DA0 de Angel.exe. Aqui se atiende el 0x0016
        # y se mira el subtipo.
        if (opcode == 0x0016 and ses.rol == 'mundo' and ses.personaje
                and len(cuerpo) >= 1 and cuerpo[0] in (0x32, 0x33)):
            _sub_al = cuerpo[0]
            _dato_al = struct.unpack_from('<I', cuerpo, 1)[0] if len(cuerpo) >= 5 else 0
            import album as _alb
            _p_al = ses.personaje
            if getattr(_p_al, 'album', None) is None:
                _p_al.album = {}
            if _sub_al == 0x32:
                log.info('[%s] album: abrir (0x0016/0x32) -> %s'
                         % (addr, _alb.resumen(_p_al.album)['total']))
                return
            # Subtipo 0x33: meter una pieza. El u32 que acompana es, por
            # lo que hace sendcollect en el binario, un u16 leido del
            # objeto que esta en la casilla de soltar. Se toma como ranura
            # y, si no cuadra, se registra con los bytes en vez de callar.
            _ran = _dato_al & 0xFFFF
            _bolsa_al = getattr(ses, 'inventario', None) or {}
            _it_al = _bolsa_al.get(_ran)
            _cat = _alb.categoria_de(_it_al) if _it_al else ''
            if not _it_al or not _cat:
                log.info('[%s] album: la ranura %d no tiene nada que entre '
                         '(item %s, cuerpo %s)'
                         % (addr, _ran, _it_al, cuerpo.hex()))
                return
            _val = _alb.valor_de(_it_al)
            _p_al.album[_cat] = int(_p_al.album.get(_cat, 0)) + _val
            _bolsa_al.pop(_ran, None)
            _cantidades(ses).pop(_ran, None)
            ses.enviar(*_refrescar(ses, [_ran]), _stats_ses(ses))
            if getattr(ses, 'usuario', None):
                _guardar_bolsa(ses, _p_al.char_id)
                cuentas.guardar_sistemas(ses.usuario, _p_al.char_id, _p_al)
            log.info('[%s] album: item %d a %s (+%d, ahora %d); bonos %s'
                     % (addr, _it_al, _cat, _val, _p_al.album[_cat],
                        _alb.bonos(_p_al.album)))
            return

        if opcode == 0x002F and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 9:
            import inventario as _iv
            # El primer byte es el CONTENEDOR, y el mismo mensaje sirve para
            # cosas distintas:
            #   11 = la mochila, y entonces esto parte un monton en dos
            #   10 = el panel de hechizos del mago: equipar una rama y
            #        descargar otra. Medido: el cliente manda
            #        0a 0600 0000 03000000 y el servidor contesta con el
            #        aviso 424 ("Chaos" equipado), el 423 ("Meditate"
            #        descargado), los stats, el arbol de habilidades y un
            #        0x001D codigo 9 por cada hechizo nuevo, con su aviso
            #        425. Eso todavia no esta implementado aqui.
            # No mirabamos este byte, asi que un cambio de hechizo entraba
            # por el camino de partir pilas del inventario.
            _contenedor = cuerpo[0]
            if _contenedor == 10:
                # Cambio de rama de habilidad (Skill Angel). Medido: [u8 10][u32 la que se
                # descarga][u32 la que se equipa].
                import clases as _cl2
                import skills as _sk
                _fuera, _dentro = struct.unpack_from('<II', cuerpo, 1)
                _p = ses.personaje
                _habs = list(_p.habilidades or [])
                _pos = next((k for k, h in enumerate(_habs) if h[0] == _fuera), None)
                if _pos is None:
                    log.warning(f"[{addr}] cambio de rama: no se lleva la "
                                f"{_fuera} ({_sk.nombre_rama(_fuera)})")
                    return

                # Guardar el progreso de la rama que sale en el banco de habilidades
                if not hasattr(_p, 'banco_habilidades') or _p.banco_habilidades is None:
                    _p.banco_habilidades = {}
                _p.banco_habilidades[_fuera] = [_habs[_pos][1], _habs[_pos][2]]

                # Recuperar progreso previo de la rama que entra si ya la habia entrenado
                _nv_rec, _exp_rec = _p.banco_habilidades.get(_dentro, (1, 0))
                _habs[_pos] = (_dentro, _nv_rec, _exp_rec)
                _p.habilidades = _habs
                _p.class_id = _sk.calcular_class_id([h[0] for h in _p.habilidades])

                # El orden es el del servidor real: primero aviso de la que entra,
                # luego la que sale, stats, arbol, y 0x001D + aviso por cada hechizo nuevo.
                _salida = [
                    _cl2.aviso(_sk.nombre_rama(_dentro), tipo=7, msg_id=424),
                    _cl2.aviso(_sk.nombre_rama(_fuera), tipo=7, msg_id=423),
                    _stats_ses(ses),
                    _cl2.arbol(_p.habilidades, banco=_p.banco_habilidades),
                ]
                _nuevos = _sk.hechizos_de_rama(_dentro)
                if _nuevos:
                    for _nid, _nom in _nuevos:
                        _salida.append(struct.pack('<HIB', 0x001D, _p.entity_id, 1) + struct.pack('<BII', _cl2.KIND_HECHIZO, _nid, 1))
                        _salida.append(_cl2.aviso(_nom, tipo=7, msg_id=_cl2.MSG_HECHIZO))

                ses.enviar(*_salida)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_habilidades(ses.usuario, _p.char_id, _p.habilidades)
                    cuentas.guardar_clase(ses.usuario, _p.char_id, _p.class_id)
                    cuentas.guardar_banco_habilidades(ses.usuario, _p.char_id, _p.banco_habilidades)
                log.info(f"[{addr}] cambio de rama: fuera "
                         f"{_sk.nombre_rama(_fuera)}, dentro "
                         f"{_sk.nombre_rama(_dentro)} (Lv {_nv_rec}) "
                         f"-> clase={_p.class_id} ({len(_nuevos)} hechizos iniciales)")
                return
            if _contenedor == 16:
                # Click derecho en casilla del BANCO (usebankitem) -> Retirar a la mochila
                import inventario as _iv3
                _ori = struct.unpack_from('<I', cuerpo, 1)[0]
                _p = ses.personaje
                _bolsa = getattr(ses, 'inventario', {})
                if _p.banco is None:
                    _p.banco = {}
                if _ori in _p.banco:
                    _d = _ranura_libre(_bolsa, desde=20)
                    if _d is None:
                        log.info(f"[{addr}] mochila llena, no se puede sacar del banco")
                        return
                    _v = _p.banco.pop(_ori)
                    _it, _cn = _v if isinstance(_v, (list, tuple)) else (_v, 1)
                    _bolsa[_d] = _it
                    if _cn > 1:
                        ses.cantidades[_d] = _cn
                    ses.enviar(
                        _iv3.banco_sacar(_p.char_id, _d, _it, _cn, dueno=_p.entity_id),
                        _iv3.banco_vaciar_ranura(_ori),
                        _stats_ses(ses)
                    )
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_banco(ses.usuario, _p.char_id, _p.banco)
                        _guardar_bolsa(ses, _p.char_id)
                    log.info(f"[{addr}] banco click derecho: sacado item {_it} (x{_cn}) de banco {_ori} a mochila {_d}")
                else:
                    log.warning(f"[{addr}] banco click derecho: casilla {_ori} no esta en banco {_p.banco}")
                return

            if _contenedor == 17:
                # Click derecho en casilla de la MOCHILA con banco abierto (usecharitem) -> Depositar al banco
                import inventario as _iv3
                _ori = struct.unpack_from('<I', cuerpo, 1)[0]
                _p = ses.personaje
                _bolsa = getattr(ses, 'inventario', {})
                if _p.banco is None:
                    _p.banco = {}
                if _ori in _bolsa and _ori >= 20:
                    _d = next((k for k in range(1, 49) if k not in _p.banco), None)
                    if _d is None:
                        log.info(f"[{addr}] banco lleno, no se guarda")
                        return
                    _it = _bolsa.pop(_ori)
                    _cn = ses.cantidades.pop(_ori, 1)
                    _p.banco[_d] = (_it, _cn)
                    ses.enviar(
                        _iv3.vaciar_ranura(_p.entity_id, _ori),
                        _stats_ses(ses),
                        _iv3.banco_poner(_p.char_id, _d, _it, _cn, dueno=_p.entity_id)
                    )
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_banco(ses.usuario, _p.char_id, _p.banco)
                        _guardar_bolsa(ses, _p.char_id)
                    log.info(f"[{addr}] banco click derecho: guardado item {_it} (x{_cn}) de mochila {_ori} en banco {_d}")
                else:
                    log.warning(f"[{addr}] banco click derecho: casilla {_ori} no es de mochila o no existe")
                return

            if _contenedor in (14, 23):
                # Arrastre dentro del banco, o entre banco y mochila
                import inventario as _iv3
                _ori, _dst = struct.unpack_from('<II', cuerpo, 1)
                _p = ses.personaje
                _bolsa = getattr(ses, 'inventario', {})
                if _p.banco is None:
                    _p.banco = {}

                # 1. Movimiento / intercambio DENTRO del banco (Bank -> Bank)
                if _ori in _p.banco and 1 <= _dst <= 48:
                    if _dst in _p.banco:
                        _v_ori = _p.banco[_ori]
                        _v_dst = _p.banco[_dst]
                        _p.banco[_ori] = _v_dst
                        _p.banco[_dst] = _v_ori
                        _it1, _cn1 = _v_ori if isinstance(_v_ori, (list, tuple)) else (_v_ori, 1)
                        _it2, _cn2 = _v_dst if isinstance(_v_dst, (list, tuple)) else (_v_dst, 1)
                        ses.enviar(
                            _iv3.banco_poner(_p.char_id, _dst, _it1, _cn1, dueno=_p.entity_id),
                            _iv3.banco_poner(_p.char_id, _ori, _it2, _cn2, dueno=_p.entity_id)
                        )
                        log.info(f"[{addr}] banco: swap casilla {_ori} ({_it1}) <-> {_dst} ({_it2})")
                    else:
                        _v = _p.banco.pop(_ori)
                        _it, _cn = _v if isinstance(_v, (list, tuple)) else (_v, 1)
                        _p.banco[_dst] = (_it, _cn)
                        ses.enviar(
                            _iv3.banco_vaciar_ranura(_ori),
                            _iv3.banco_poner(_p.char_id, _dst, _it, _cn, dueno=_p.entity_id)
                        )
                        log.info(f"[{addr}] banco: mover item {_it} de casilla {_ori} a {_dst}")
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_banco(ses.usuario, _p.char_id, _p.banco)
                    return

                # 2. De MOCHILA a BANCO por arrastre (Mochila -> Bank)
                if _ori in _bolsa and _ori >= 20:
                    _d = _dst if (1 <= _dst <= 48 and _dst not in _p.banco) else next(
                        (k for k in range(1, 49) if k not in _p.banco), None)
                    if _d is not None:
                        _it = _bolsa.pop(_ori)
                        _cn = ses.cantidades.pop(_ori, 1)
                        _p.banco[_d] = (_it, _cn)
                        ses.enviar(
                            _iv3.vaciar_ranura(_p.entity_id, _ori),
                            _stats_ses(ses),
                            _iv3.banco_poner(_p.char_id, _d, _it, _cn, dueno=_p.entity_id)
                        )
                        if getattr(ses, 'usuario', None):
                            cuentas.guardar_banco(ses.usuario, _p.char_id, _p.banco)
                            _guardar_bolsa(ses, _p.char_id)
                        log.info(f"[{addr}] banco: guardado item {_it} de mochila {_ori} en banco {_d}")
                        return

                # 3. De BANCO a MOCHILA por arrastre (Bank -> Mochila)
                if _ori in _p.banco:
                    _d = _dst if (_dst >= 20 and _dst not in _bolsa) else _ranura_libre(_bolsa, desde=20)
                    if _d is not None:
                        _v = _p.banco.pop(_ori)
                        _it, _cn = _v if isinstance(_v, (list, tuple)) else (_v, 1)
                        _bolsa[_d] = _it
                        if _cn > 1:
                            ses.cantidades[_d] = _cn
                        ses.enviar(
                            _iv3.banco_sacar(_p.char_id, _d, _it, _cn, dueno=_p.entity_id),
                            _iv3.banco_vaciar_ranura(_ori),
                            _stats_ses(ses)
                        )
                        if getattr(ses, 'usuario', None):
                            cuentas.guardar_banco(ses.usuario, _p.char_id, _p.banco)
                            _guardar_bolsa(ses, _p.char_id)
                        log.info(f"[{addr}] banco: sacado item {_it} de banco {_ori} a mochila {_d}")
                        return

                log.warning(f"[{addr}] banco: movimiento {_ori} -> {_dst} no resuelto. Bolsa: {sorted(_bolsa)}, Banco: {sorted(_p.banco)}")
                return

            if _contenedor == 41:
                # HitParade ranking request
                import casas as _cs_hp
                _rtype = cuerpo[1] if len(cuerpo) > 1 else 31
                _page = struct.unpack_from('<I', cuerpo, 2)[0] if len(cuerpo) >= 6 else 0
                _res = _cs_hp.ranking_hitparade(_rtype, _page)
                ses.enviar(_cs_hp.pkt_hitparade_data(_rtype, _page, len(_res), _res))
                return

            if _contenedor == 42:
                # Billboard ranking request
                import casas as _cs_bb
                _btype = cuerpo[1] if len(cuerpo) > 1 else 0
                _res = _cs_bb.ranking_billboard(_btype)
                ses.enviar(_cs_bb.pkt_billboard_data(_btype, len(_res), _res))
                return

            if _contenedor != 11:
                log.info(f"[{addr}] 0x002F con contenedor {_contenedor}: no es "
                         f"la mochila ni el panel de hechizos, se ignora "
                         f"(cuerpo {cuerpo.hex()})")
                return
            destino, origen = struct.unpack_from('<HH', cuerpo, 1)
            cuantas = struct.unpack_from('<I', cuerpo, 5)[0]
            bolsa = getattr(ses, 'inventario', {})
            if origen not in bolsa or destino in bolsa or cuantas < 1:
                log.warning(f"[{addr}] separar invalido: {origen} -> {destino} "
                            f"x{cuantas}")
                return
            hay = _cant_de(ses, origen)
            if cuantas >= hay:
                log.warning(f"[{addr}] separar: piden {cuantas} y hay {hay}")
                return
            item_id = bolsa[origen]
            _cantidades(ses)[origen] = hay - cuantas
            bolsa[destino] = item_id
            _instancias(ses)[destino] = _iv.instancia_nueva()
            if cuantas > 1:
                _cantidades(ses)[destino] = cuantas
            cid = ses.personaje.char_id
            ses.enviar(*_refrescar(ses, [origen, destino]))
            _guardar_bolsa(ses, cid)
            log.info(f"[{addr}] separadas {cuantas} de {item_id}: casilla "
                     f"{origen} ({hay} -> {hay - cuantas}) y casilla {destino}")
            return

        # --- Banco: 0x0038 (depositar oro o drop mochila -> banco) ---
        if opcode == 0x0038 and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 8:
            import inventario as _iv3
            arg1, arg2, arg3 = struct.unpack_from('<HHI', cuerpo, 0)
            _p = ses.personaje
            if _p.banco is None:
                _p.banco = {}

            if arg1 == 0 and arg2 == 0:
                # Depositar oro al banco (setsplitmoneynum)
                monto = min(int(arg3), getattr(ses, 'oro', 0))
                if monto > 0:
                    ses.oro -= monto
                    _p.oro = ses.oro
                    _p.banco_oro = getattr(_p, 'banco_oro', 0) + monto
                    ses.enviar(
                        _iv3.actualizar_ranura(_p.char_id, _iv3.RANURA_ORO, _iv3.ITEM_ORO,
                                               _inst(ses, _iv3.RANURA_ORO), _p.entity_id, cantidad=ses.oro),
                        _stats_ses(ses),
                        _iv3.banco_poner(_p.char_id, 0, _iv3.ITEM_ORO, cant=_p.banco_oro, dueno=_p.entity_id)
                    )
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_oro(ses.usuario, _p.char_id, ses.oro)
                        cuentas.guardar_banco_oro(ses.usuario, _p.char_id, _p.banco_oro)
                    log.info(f"[{addr}] banco: depositado {monto} oro. Mochila: {ses.oro}, Banco: {_p.banco_oro}")
                return

            # Arrastrar objeto de la mochila al banco (dropbankitem)
            _bolsa = getattr(ses, 'inventario', {})
            _desde_bolsa = arg1
            if _desde_bolsa in _bolsa and _desde_bolsa >= 20:
                _d = arg2 if (1 <= arg2 <= 48 and arg2 not in _p.banco) else next(
                    (k for k in range(1, 49) if k not in _p.banco), None)
                if _d is None:
                    log.info(f"[{addr}] banco lleno, no se guarda")
                    return
                _it = _bolsa.pop(_desde_bolsa)
                _cn = ses.cantidades.pop(_desde_bolsa, 1)
                _p.banco[_d] = (_it, _cn)
                ses.enviar(
                    _iv3.vaciar_ranura(_p.entity_id, _desde_bolsa),
                    _stats_ses(ses),
                    _iv3.banco_poner(_p.char_id, _d, _it, _cn, dueno=_p.entity_id)
                )
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_banco(ses.usuario, _p.char_id, _p.banco)
                    _guardar_bolsa(ses, _p.char_id)
                log.info(f"[{addr}] banco: guardado item {_it} (x{_cn}) de mochila {_desde_bolsa} en banco {_d}")
            return

        # --- Banco: 0x0039 (retirar oro o drop banco -> mochila) ---
        if opcode == 0x0039 and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 8:
            import inventario as _iv3
            arg1, arg2, arg3 = struct.unpack_from('<HHI', cuerpo, 0)
            _p = ses.personaje
            if _p.banco is None:
                _p.banco = {}

            if arg1 == 0 and arg2 == 0:
                # Retirar oro del banco a la mochila (setsplitmoneynum)
                banco_oro_actual = getattr(_p, 'banco_oro', 0)
                monto = min(int(arg3), banco_oro_actual)
                if monto > 0:
                    _p.banco_oro -= monto
                    ses.oro = min(2000000000, getattr(ses, 'oro', 0) + monto)
                    _p.oro = ses.oro
                    ses.enviar(
                        _iv3.actualizar_ranura(_p.char_id, _iv3.RANURA_ORO, _iv3.ITEM_ORO,
                                               _inst(ses, _iv3.RANURA_ORO), _p.entity_id, cantidad=ses.oro),
                        _stats_ses(ses),
                        _iv3.banco_poner(_p.char_id, 0, _iv3.ITEM_ORO, cant=_p.banco_oro, dueno=_p.entity_id)
                    )
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_oro(ses.usuario, _p.char_id, ses.oro)
                        cuentas.guardar_banco_oro(ses.usuario, _p.char_id, _p.banco_oro)
                    log.info(f"[{addr}] banco: retirado {monto} oro. Mochila: {ses.oro}, Banco: {_p.banco_oro}")
                return

            # Arrastrar objeto del banco a la mochila (dropcharitem)
            _bolsa = getattr(ses, 'inventario', {})
            if arg1 in _p.banco:
                _d = arg2 if (arg2 >= 20 and arg2 not in _bolsa) else _ranura_libre(_bolsa, desde=20)
                if _d is None:
                    log.info(f"[{addr}] mochila llena, no se puede sacar del banco")
                    return
                _v = _p.banco.pop(arg1)
                _it, _cn = _v if isinstance(_v, (list, tuple)) else (_v, 1)
                _bolsa[_d] = _it
                if _cn > 1:
                    ses.cantidades[_d] = _cn
                ses.enviar(
                    _iv3.banco_sacar(_p.char_id, _d, _it, _cn, dueno=_p.entity_id),
                    _iv3.banco_vaciar_ranura(arg1),
                    _stats_ses(ses)
                )
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_banco(ses.usuario, _p.char_id, _p.banco)
                    _guardar_bolsa(ses, _p.char_id)
                log.info(f"[{addr}] banco: sacado item {_it} (x{_cn}) de banco {arg1} a mochila {_d}")
            return

        # --- destruir un monton entero (papelera) ------------------------
        # Medido: c2s 0x0013 = [u16 casilla][u32 item_id], y el servidor
        # contesta con el 0x001B corto que deja la casilla vacia. Nuestro
        # codigo escuchaba el 0x004C, que el cliente no manda nunca.
        if opcode == 0x0013 and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 6:
            import inventario as _iv
            ranura, item_id = struct.unpack_from('<HI', cuerpo, 0)
            bolsa = getattr(ses, 'inventario', {})
            if ranura not in bolsa or int(bolsa[ranura]) != int(item_id):
                log.warning(f"[{addr}] destruir: la casilla {ranura} no tiene "
                            f"el item {item_id}")
                return
            cuantas = _cant_de(ses, ranura)
            _sacar(ses, ranura, cuantas)
            cid = ses.personaje.char_id
            ses.enviar(_iv.vaciar_ranura(ses.personaje.entity_id, ranura))
            _guardar_bolsa(ses, cid)
            log.info(f"[{addr}] destruido: item {item_id} x{cuantas} de la "
                     f"casilla {ranura}")
            return

        # --- Descartar / Destruir item del inventario (papelera) ---------
        if opcode == 0x004C and ses.rol == 'mundo' and ses.personaje and cuerpo:
            import inventario as _iv
            import clases as _c
            slot = cuerpo[0]
            bolsa = getattr(ses, 'inventario', {})
            cid = ses.personaje.char_id
            if slot in bolsa:
                item_del = bolsa[slot]
                del bolsa[slot]
                nom_it = _nombre_item(item_del)
                ses.enviar(_iv.completo(cid, _con_oro(ses), _dueno(ses), _mejoras_de(ses)),
                           _c.aviso(f"Destroyed {nom_it}", tipo=7, msg_id=_c.MSG_TEXTO))
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa,
                                   _cantidades(ses))
                log.info(f"[{addr}] item destruido en ranura {slot}: {item_del} ({nom_it})")
            return

        # IGG 0x0130 is Card Book Exchange (sub_6229C0), NOT inventory drag.
        if opcode == 0x0130 and ses.rol == 'mundo' and ses.personaje and cuerpo:
            import cartas as _cartas
            _cartas.canjear(ses, cuerpo, _meter, _refrescar)
            return

        # --- eleccion de clase -----------------------------------------
        # La ventana la abre el cliente solo; lo unico que llega es esto.
        if opcode == 0x003A and ses.rol == 'mundo' and cuerpo:
            import clases
            ids = clases.parsear_eleccion(cuerpo)
            if not ids:
                return
            # La clase se elige UNA vez. Sin esto se le puede volver a hablar
            # al NPC y cambiarla cuantas veces se quiera.
            if ses.personaje and ses.personaje.habilidades:
                actual = ', '.join(clases.nombre(h[0])
                                   for h in ses.personaje.habilidades)
                log.warning(f"[{addr}] ya tiene clase ({actual}); se ignora el "
                            f"intento de cambiarla")
                return
            salida = []
            for sid in ids:
                salida.append(clases.aviso(clases.nombre(sid), tipo=7, msg_id=clases.MSG_HABILIDAD))
            # El arbol completo. Sin el, el panel de habilidades del cliente
            # sale lleno de interrogantes: no conoce las otras treinta.
            salida.append(clases.arbol(ids))
            # Los tres hechizos de nivel 1 del arma, que son los que el
            # cliente pone en F1..F3. En la captura llegan justo despues del
            # arbol, tres 0x000D seguidos con id de mensaje 425.
            hechizos = clases.hechizos_iniciales(ids)
            for _, nom in hechizos:
                salida.append(clases.aviso(nom, tipo=7,
                                           msg_id=clases.MSG_HECHIZO))
            # El 0x000D de arriba solo escribe "Learn X" en el chat. Los
            # iconos no salen hasta que llega este 0x001D.
            if hechizos and ses.personaje:
                salida.extend(clases.otorgar_hechizos(
                    ses.personaje.entity_id, [n for n, _ in hechizos]))

            # Entregar lo que da la clase y anotar el class_id. Ambas cosas
            # estan medidas del servidor real AngelWar, no deducidas.
            import inventario as _iv
            regalo = clases.regalo(ids)
            cid = ses.personaje.char_id if ses.personaje else 4980
            if regalo and getattr(ses, 'inventario', None) is not None:
                for ranura, item_id in regalo:
                    ses.inventario[int(ranura)] = int(item_id)
                items_vistos = set()
                for ranura, item_id in regalo:
                    if item_id not in items_vistos:
                        items_vistos.add(item_id)
                        salida.append(clases.aviso(_nombre_item(item_id), tipo=0, msg_id=clases.MSG_ITEM))
                salida.append(_iv.completo(cid, _con_oro(ses), _dueno(ses), _mejoras_de(ses)))

            # Actualizar stats para Swordsman: Max HP = 304, MP = 154
            if ses.personaje:
                if 9 in ids:  # Swordsman
                    ses.personaje.hp_max = 304
                    ses.personaje.hp = 304
                bars, max_pts = _max_sp_info(ses.personaje)
                # Un personaje recien hecho tampoco empieza con la barra
                # llena: el SP se gana peleando.
                # El SP viene del personaje guardado. Empieza a cero solo la
                # primera vez: se gana peleando y se conserva al salir.
                ses.sp = getattr(ses, 'sp', None)
                if ses.sp is None:
                    ses.sp = max(0, int(getattr(p, 'sp', 0) or 0))
                salida.append(_iv.stats(
                    ses.inventario, [(sid, 1, 0) for sid in ids],
                    hp=ses.personaje.hp, hp_max=ses.personaje.hp_max,
                    mp=ses.personaje.mp, mp_max=ses.personaje.mp_max,
                    oro=ses.personaje.oro,
                    sp=ses.sp, sp_max=bars,
                    mejoras=_mejoras_de(ses)))
                import combate as _cb
                salida.append(_cb.atributo(ses.personaje.entity_id, ses.sp, _cb.KIND_SP))

            ses.enviar(*salida)

            if ses.personaje:
                ses.personaje.habilidades = [(sid, 1, 0) for sid in ids]
                if hechizos:
                    ses.personaje.barra = [n for n, _ in hechizos]
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_habilidades(
                        ses.usuario, ses.personaje.char_id,
                        ses.personaje.habilidades)
                    cuentas.guardar_oro(ses.usuario, cid, ses.personaje.oro)
                    cuentas.guardar_inventario(ses.usuario, cid, ses.inventario,
                                   _cantidades(ses))
                    cuentas.guardar_barra(ses.usuario, cid, ses.personaje.barra)
                    cuentas.guardar_progreso(
                        ses.usuario, cid, ses.personaje.nivel, ses.personaje.exp,
                        ses.personaje.hp, ses.personaje.mp, ses.personaje.habilidades,
                        ses.personaje.hp_max, ses.personaje.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)

            log.info(f"[{addr}] CLASE ELEGIDA: "
                     + ', '.join(f'{clases.nombre(i)}({i})' for i in ids)
                     + (f" | hechizos: {', '.join(n for _, n in hechizos)}"
                        if hechizos
                        else " | SIN hechizos de nivel 1 para esa rama"))

            _cid = clases.class_id(ids[0])
            if _cid is not None and ses.personaje and getattr(ses, 'usuario', None):
                cuentas.guardar_clase(ses.usuario, ses.personaje.char_id, _cid)
                log.info(f"[{addr}] class_id {_cid} guardado")
            return

        if opcode == 0x0044 and ses.rol == 'mundo' and len(cuerpo) >= 7:
            # Asignacion de hotkey en la barra (F1..F8, 1..8)
            slot = cuerpo[1]
            # El byte 2 es el TIPO: 1 hechizo, 2 OBJETO, 0 vaciar. Se
            # tiraba, asi que los objetos de la barra volvian marcados como
            # hechizos y el cliente los quitaba al entrar.
            tipo = cuerpo[2]
            mid = struct.unpack_from('<I', cuerpo, 3)[0]
            if ses.personaje:
                while len(ses.personaje.barra) <= slot:
                    ses.personaje.barra.append(0)
                ses.personaje.barra[slot] = [tipo, mid] if mid else 0
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_barra(ses.usuario, ses.personaje.char_id, ses.personaje.barra)
            log.info(f"[{addr}] barra slot {slot}: "
                     f"{'objeto' if tipo == 2 else 'hechizo'} {mid}")
            return

        # --- equipar y desequipar --------------------------------------
        # 0x0012 del cliente es MOVER UN ITEM, no hablar con un NPC: eso se
        # confundio al principio porque el cuerpo "02 00 14 00" aparecia
        # despues de hacer clic cerca de un NPC. Con marca de tiempo quedo
        # claro: lo que contesta el servidor es el contenido del contenedor
        # (0x001B) y los stats recalculados (0x0042), no un dialogo.
        if opcode == 0x0036 and ses.rol == 'mundo' and len(cuerpo) == 4:
            _casa_fabricar(ses, struct.unpack_from('<I', cuerpo)[0])
            return

        if opcode == 0x0037 and ses.rol == 'mundo':
            _task = getattr(ses, 'house_make_task', None)
            if _task:
                _task.cancel()
                ses.house_make_task = None
            return

        if opcode == 0x0012 and ses.rol == 'mundo' and len(cuerpo) >= 4:
            import inventario as inv
            org, dst = struct.unpack_from('<HH', cuerpo, 0)
            bolsa = getattr(ses, 'inventario', None)
            if bolsa is None:
                return
            if org not in bolsa:
                log.warning(f"[{addr}] mover {org} -> {dst}: la ranura {org} esta vacia")
                return
            it_org = bolsa[org]
            if 477 <= dst <= 496:
                import casas as _cs_slots, house_services as _hs_slots
                _c_slots = _casa_actual(ses) if ses.personaje else None
                _valid_slot = bool(_c_slots and ses.personaje.stage == 500
                    and _c_slots.owner_id == ses.personaje.char_id
                    and not getattr(ses, 'house_furnishing', False))
                if dst < 487:
                    _valid_slot = (_valid_slot and inv.es_mascota(it_org)
                        and dst < 477 + _cs_slots.ranuras_mascotas_validas(_c_slots.level))
                else:
                    _valid_slot = (_valid_slot and it_org in _hs_slots.monster_eggs()
                        and dst < 487 + _cs_slots.ranuras_mobgen_validas(_c_slots.level))
                if not _valid_slot:
                    ses.enviar(*_refrescar(ses, [org, dst]))
                    return
            if not inv.es_ranura_valida(it_org, dst):
                log.warning(f"[{addr}] mover {org} -> {dst}: ranura no valida para item {it_org}")
                ses.enviar(*_refrescar(ses, [org]))
                return
            # Si intenta poner un arma dual (espada o hacha) en la mano izquierda (4), exige Finesse (skill 16)
            if dst == 4 and inv.es_arma_dual(it_org):
                _tiene_finesse = any((h[0] if isinstance(h, (list, tuple)) else h) == 16 for h in (getattr(ses.personaje, 'habilidades', None) or []))
                if not _tiene_finesse:
                    import clases as _clf
                    ses.enviar(_clf.aviso("Requires Finesse skill to dual-wield weapons.", tipo=0), *_refrescar(ses, [org]))
                    return
            cid = ses.personaje.char_id if ses.personaje else 4980
            if inv.es_equipo(dst):
                estado_org = (ses.personaje.mejoras or {}).get(org) if ses.personaje else None
                if not inv.puede_equipar(it_org, cid, estado_org):
                    import clases as _clf
                    ses.enviar(_clf.aviso("Unable to equip the equipment.", tipo=0), *_refrescar(ses, [org]))
                    return
            # Si equipa un arma/municion en la 3 o 4 incompatible con la otra mano
            # (ej. Staff/Spear con escudo, o Arco con escudo en vez de flechas, o Honda con flechas en vez de bolitas),
            # desequipar la otra mano a la mochila conservando su cantidad.
            _extra_tocadas = []
            if dst == 3 and 4 in bolsa and org != 4 and not inv.compatibles_manos(it_org, bolsa[4]):
                _lib_lh = _ranura_libre(bolsa, desde=20)
                if _lib_lh is None:
                    import clases as _clf
                    ses.enviar(_clf.aviso("Your backpack is full.", tipo=0), *_refrescar(ses, [org]))
                    return
                _it_lh = bolsa.pop(4)
                bolsa[_lib_lh] = _it_lh
                _c_lh = _cantidades(ses).pop(4, 1)
                if _c_lh > 1:
                    _cantidades(ses)[_lib_lh] = _c_lh
                _mover_inst(ses, 4, _lib_lh)
                _extra_tocadas.extend([4, _lib_lh])
            elif dst == 4 and 3 in bolsa and org != 3 and not inv.compatibles_manos(bolsa[3], it_org):
                _lib_rh = _ranura_libre(bolsa, desde=20)
                if _lib_rh is None:
                    import clases as _clf
                    ses.enviar(_clf.aviso("Your backpack is full.", tipo=0), *_refrescar(ses, [org]))
                    return
                _it_rh = bolsa.pop(3)
                bolsa[_lib_rh] = _it_rh
                _c_rh = _cantidades(ses).pop(3, 1)
                if _c_rh > 1:
                    _cantidades(ses)[_lib_rh] = _c_rh
                _mover_inst(ses, 3, _lib_rh)
                _extra_tocadas.extend([3, _lib_rh])
            if dst in bolsa:
                it_dst = bolsa[dst]
                if not inv.es_ranura_valida(it_dst, org):
                    log.warning(f"[{addr}] swap {org} <-> {dst}: ranura {org} no valida para item {it_dst}")
                    ses.enviar(*_refrescar(ses, [org, dst]))
                    return
                if inv.es_equipo(org):
                    estado_dst = (ses.personaje.mejoras or {}).get(dst) if ses.personaje else None
                    if not inv.puede_equipar(it_dst, cid, estado_dst):
                        import clases as _clf
                        ses.enviar(_clf.aviso("Unable to equip the equipment.", tipo=0), *_refrescar(ses, [org, dst]))
                        return
                # Intercambio (swap) entre ranuras ocupadas
                bolsa[org] = it_dst
                bolsa[dst] = it_org
                _c_org = _cant_de(ses, org)
                _c_dst = _cant_de(ses, dst)
                _cantidades(ses)[org] = _c_dst
                _cantidades(ses)[dst] = _c_org
                _mover_inst(ses, org, 0xFFFF)
                _mover_inst(ses, dst, org)
                _mover_inst(ses, 0xFFFF, dst)
                if ses.personaje:
                    for _r_eq in (dst, org):
                        if inv.es_equipo(_r_eq) and _r_eq in bolsa:
                            _estado_eq = ses.personaje.mejoras.get(_r_eq, {})
                            if inv.vincular_equipo(int(bolsa[_r_eq]), cid, _estado_eq):
                                ses.personaje.mejoras[_r_eq] = _estado_eq
                                if getattr(ses, 'usuario', None):
                                    cuentas.guardar_mejoras(ses.usuario, cid, ses.personaje.mejoras)
                _masc_p = getattr(ses.personaje, 'mascota', None) if ses.personaje else None
                if isinstance(_masc_p, dict):
                    if _masc_p.get('ranura') == org:
                        _masc_p['ranura'] = dst
                    elif _masc_p.get('ranura') == dst:
                        _masc_p['ranura'] = org
                # El registro persistente de mascotas tambien sigue el swap.
                # Sin esto, dos mascotas del Raise-a-Pet Room intercambiaban
                # los items visibles pero conservaban la ficha/nombre de la
                # casilla anterior.
                _mascs_swap = getattr(ses.personaje, 'mascotas', None) if ses.personaje else None
                if isinstance(_mascs_swap, dict):
                    _f_org = _mascs_swap.pop(str(org), None)
                    _f_dst = _mascs_swap.pop(str(dst), None)
                    if _f_org:
                        _f_org['ranura'] = dst
                        _mascs_swap[str(dst)] = _f_org
                    if _f_dst:
                        _f_dst['ranura'] = org
                        _mascs_swap[str(org)] = _f_dst
                # Las dos casillas en UN solo mensaje, con el estado de
                # puesto de cada una, que es lo que hace el servidor real.
                salida = [inv.acuse_movimiento(org),
                          inv.actualizar_ranuras(cid, [
                    (dst, it_org, _c_org, _inst(ses, dst)),
                    (org, it_dst, _c_dst, _inst(ses, org)),
                ], _dueno(ses), mascota=_masc_p, mejoras=getattr(ses.personaje, 'mejoras', None),
                mascotas=getattr(ses.personaje, 'mascotas', None))]
                if isinstance(_masc_p, dict) and _masc_p.get('fuera'):
                    import mascotas as _ms_swp
                    salida.append(_ms_swp.armar(_masc_p))
                if _extra_tocadas:
                    salida.extend(_refrescar(ses, _extra_tocadas))
                if inv.es_equipo(org) or inv.es_equipo(dst):
                    if ses.personaje:
                        import combate as _cb
                        _max_h = _vida_max(ses.personaje, bolsa=bolsa)
                        if ses.personaje.hp > _max_h:
                            ses.personaje.hp = _max_h
                        _max_m = _mana_max(ses.personaje, bolsa=bolsa)
                        if ses.personaje.mp > _max_m:
                            ses.personaje.mp = _max_m
                        salida.append(_cb.atributo(ses.personaje.entity_id, ses.personaje.hp, _cb.KIND_HP))
                        salida.append(_cb.atributo(ses.personaje.entity_id, ses.personaje.mp, _cb.KIND_MP))
                    salida.append(_stats_ses(ses))
                    salida.extend(_apariencia(ses))
                ses.enviar(*salida)
                if inv.es_equipo(org) or inv.es_equipo(dst):
                    import presencia as _pr
                    _pr.notificar_equipo(ses)
                if ses.personaje and getattr(ses, 'usuario', None):
                    _guardar_bolsa(ses, ses.personaje.char_id)
                self._sincronizar_ranura_pet_room(ses, org, dst, it_org)
                self._sincronizar_ranura_pet_room(ses, dst, org, it_dst)
                log.info(f"[{addr}] swap ranuras {org} ({it_org}) <-> {dst} ({it_dst})")
                return

            it = bolsa.pop(org)
            bolsa[dst] = it
            _c_org = _cantidades(ses).pop(org, 1)
            _cantidades(ses)[dst] = _c_org
            _mover_inst(ses, org, dst)
            _masc_p = getattr(ses.personaje, 'mascota', None) if ses.personaje else None
            if isinstance(_masc_p, dict) and _masc_p.get('ranura') == org:
                _masc_p['ranura'] = dst
            if getattr(ses.personaje, 'mascotas', None):
                _f_mv = ses.personaje.mascotas.pop(str(org), None) or ses.personaje.mascotas.pop(org, None)
                if isinstance(_f_mv, dict):
                    _f_mv['ranura'] = dst
                    ses.personaje.mascotas[str(dst)] = _f_mv
            salida = [inv.acuse_movimiento(org)]
            salida.extend(_refrescar(ses, [org, dst] + _extra_tocadas))
            if isinstance(_masc_p, dict) and _masc_p.get('fuera') and _masc_p.get('ranura') == dst:
                import mascotas as _ms_mv
                salida.append(_ms_mv.armar(_masc_p))
            if inv.es_equipo(org) or inv.es_equipo(dst):
                if ses.personaje:
                    import combate as _cb
                    _max_h = _vida_max(ses.personaje, bolsa=bolsa)
                    if ses.personaje.hp > _max_h:
                        ses.personaje.hp = _max_h
                    _max_m = _mana_max(ses.personaje, bolsa=bolsa)
                    if ses.personaje.mp > _max_m:
                        ses.personaje.mp = _max_m
                    salida.append(_cb.atributo(ses.personaje.entity_id, ses.personaje.hp, _cb.KIND_HP))
                    salida.append(_cb.atributo(ses.personaje.entity_id, ses.personaje.mp, _cb.KIND_MP))
                salida.append(_stats_ses(ses))
                salida.extend(_apariencia(ses))
            ses.enviar(*salida)
            if inv.es_equipo(org) or inv.es_equipo(dst):
                import presencia as _pr
                _pr.notificar_equipo(ses)
            if ses.personaje and getattr(ses, 'usuario', None):
                _guardar_bolsa(ses, ses.personaje.char_id)
            self._sincronizar_ranura_pet_room(ses, org, dst, it)
            log.info(f"[{addr}] item {it}: ranura {org} -> {dst}"
                     + ("  (cambia el equipo)"
                        if inv.es_equipo(org) or inv.es_equipo(dst) else ""))
            return

        # --- usar item (clic derecho) --------------------------------
        # C -> S 0x002E [U8 ranura][LE32 target]
        # Usar / equipar lo que hay en una casilla. Medido: [u32 casilla][u8 0].
        # ANGELS GO! -- el teletransporte de las Superwing.
        #   C -> S 0x0151 [u32 id]
        # El id es el 編號 de jumpmap.xml, NO un stage: la tabla trae 355
        # destinos con su escenario y su casilla. Medido tres veces en
        # Celestia (ids 120, 119 y 109) y las tres la llegada fue la que
        # declara esa tabla.
        #
        # La respuesta se bifurca, y las dos ramas estan medidas:
        #   mismo mapa  0x0012, 0x001B, 0x0042, 0x0013, 0x0003  (sin 0x000C)
        #   otro mapa   0x0012, 0x001B, 0x0042, 0x0013, 0x0007, 0x000C
        if opcode == 0x0151 and ses.rol == 'mundo' and len(cuerpo) >= 4:
            import clases as _cgo
            if not ses.personaje:
                return
            ido = struct.unpack_from('<I', cuerpo, 0)[0]
            d = _angels_go().get(str(ido))
            if d is None:
                log.warning(f"[{addr}] Angels GO! a un destino que no esta "
                            f"en jumpmap.xml: {ido}")
                return
            dst, lleg = int(d['stage']), list(d['tile'])
            ranura = _ranura_de_item(ses, ITEM_SUPERWING)
            if ranura is None:
                log.info(f"[{addr}] Angels GO! sin Superwing en la mochila")
                return
            _sacar(ses, ranura, 1)
            yo = ses.personaje.entity_id
            salida = [struct.pack('<H', 0x0012) + bytes(7)]
            salida += _refrescar(ses, [ranura])
            salida.append(_stats_ses(ses))
            ses.personaje.tile_x, ses.personaje.tile_y = lleg
            if dst == ses.personaje.stage:
                # MISMO MAPA: el salto se hace entero con el 0x0003 y el
                # cliente no recarga nada.
                salida.append(struct.pack('<HIII', 0x0003, yo, lleg[0], lleg[1]))
                ses.enviar(*salida)
                # Si cae dentro de un tornado, se marca pisado para no viajar
                # al primer paso, igual que al llegar por portal.
                _en = _portal_en(dst, *lleg)
                ses.portal_pisado = tuple(_en['tile']) if _en else None
            else:
                # OTRO MAPA: se cierra como un tornado.
                salida.append(struct.pack('<HIB', 0x0007, yo, 1))
                ses.personaje.stage = dst
                ses.monstruos = _monstruos_de(dst)
                _en = _portal_en(dst, *lleg)
                ses.portal_pisado = tuple(_en['tile']) if _en else None
                ses.mapa_cambiado_en = time.time()
                salida.append(_cgo.cambiar_mapa(dst))
                ses.enviar(*salida)
            cid = ses.personaje.char_id
            _guardar_bolsa(ses, cid)
            if getattr(ses, 'usuario', None):
                cuentas.guardar_mapa(ses.usuario, cid, dst, *lleg)
            log.info(f"[{addr}] Angels GO! id {ido} -> stage {dst} tile "
                     f"{lleg} ({d.get('punto') or 'sin nombre'}), "
                     f"Superwing de la casilla {ranura}")
            return

        # MASCOTA: pedir su ficha (0x015E) y darle ordenes (0x003E).
        #
        # Medido el 29/09/2026. Al 0x015E el servidor real contesta con el
        # 0x0065 de 200 bytes, que es la ficha entera; al 0x003E con un
        # 0x001D del JUGADOR -- no de la mascota -- con el tipo 0x11 y el
        # modo dentro. Se vieron los modos 0, 1, 2 y 4.
        if opcode == 0x015E and ses.rol == 'mundo' and ses.personaje:
            import mascotas as _ms
            import inventario as _iv
            import mejoras as _mj
            import combate as _cb_15e
            ficha = getattr(ses.personaje, 'mascota', None)
            if not ficha and getattr(ses, 'inventario', None):
                for r, iid in ses.inventario.items():
                    if _iv.es_mascota(iid):
                        ficha = _pet_ficha(ses, r)
                        break
            if ficha:
                r = ficha.get('ranura')
                veces = (ses.personaje.mejoras.get(r) or {}).get('veces', 0) if getattr(ses.personaje, 'mejoras', None) and r is not None else 0
                f_env = _ms.aplicar_mejoras(ficha, _mj.stats_de_mejora(ficha.get('item', 0), 'mascota', veces)) if veces > 0 else ficha
                pkgs_15e = [_ms.armar(f_env)]
                pet_eid_15e = getattr(ses, 'pet_entity_id', None) or f_env.get('entidad')
                if f_env.get('fuera') and pet_eid_15e:
                    pkgs_15e.append(_cb_15e.atributo(int(pet_eid_15e), _ms.hp_eff(f_env), _cb_15e.KIND_HP))
                    if int(f_env.get('saciedad', 0)) > 100:
                        pkgs_15e.append(struct.pack('<HIBBII', 0x001D, int(pet_eid_15e), 1, 4, 3796, max(60000, (int(f_env['saciedad']) - 100) * 60000)))
                ses.enviar(*pkgs_15e)
                log.info('[%s] ficha de la mascota %s' % (addr, ficha.get('nombre')))
            return

        if opcode == 0x003E and ses.rol == 'mundo' and ses.personaje and cuerpo:
            import mascotas as _ms
            modo = cuerpo[0]
            # EL MISMO MENSAJE HACE DOS COSAS. Con 0, 1 o 2 es una orden;
            # con 4, 5 o 6 es la respuesta al cuadro de crianza, que el
            # cliente saca de su petaspect.xml sin pedirsela al servidor.
            if _ms.es_respuesta_crianza(modo):
                f = getattr(ses.personaje, 'mascota', None)
                if not f:
                    return
                # No se sabe QUE escena salio -- el cliente la elige y no la
                # manda -- asi que se apunta la respuesta y se suma cero.
                # Para cuadrar el valor habria que ver la escena.
                _suma, _total = _ms.responder_crianza(f, None, modo)
                ent = f.get('entidad') or ses.personaje.entity_id
                ses.enviar(_ms.efecto(ses.personaje.entity_id, ent))
                ses.enviar(_ms.armar(f))
                log.info('[%s] crianza: opcion %d, crianza %+d -> %d'
                         % (addr, _ms.opcion_de(modo), _suma, _total))
                return
            ses.personaje.mascota_orden = modo
            ses.pet_objetivo = None
            ses.enviar(_ms.paquete_orden(ses.personaje.entity_id, modo))
            log.info('[%s] orden a la mascota: %d' % (addr, modo))
            return

        # RENOMBRAR LA MASCOTA: c2s 0x003D, el cuerpo es el nombre pelado.
        # Medido en mundo_022355_871035: se mando "Battlemaids" y luego "Battle",
        # y el servidor contesto UNICAMENTE con s2c 0x001B (_refrescar casilla).
        # Enviar s2c 0x003D despacha en Angel.exe a FUN_005a25a0 (Mail/correo)
        # y crashea con fallo de puntero nulo. Tampoco se debe reenviar 0x0050
        # (crear entidad) porque corrompe la tabla de entidades del cliente.
        if opcode == 0x003D and ses.rol == 'mundo' and ses.personaje and cuerpo:
            import mascotas as _ms
            ficha = getattr(ses.personaje, 'mascota', None) or {}
            nom = _ms.nombre_pedido(cuerpo)
            if (not ficha or not isinstance(ficha, dict)) and getattr(ses.personaje, 'mascotas', None):
                for _m in ses.personaje.mascotas.values():
                    if isinstance(_m, dict):
                        ficha = _m
                        break
            if isinstance(ficha, dict) and nom:
                nom = nom[:_ms.LARGO_NOMBRE].strip()
                ficha['nombre'] = nom
                ficha['renombrada'] = True
                ses.personaje.mascota = ficha
                r = ficha.get('ranura')
                if getattr(ses.personaje, 'mascotas', None) and r is not None:
                    ses.personaje.mascotas[str(r)] = ficha

                # Medido en mundo_022355_871035: la respuesta a c2s 0x003D es
                # UNICAMENTE el 0x001B de la casilla. Enviar 0x003D o 0x0050
                # provoca un crash de puntero nulo en Angel.exe.
                if r is not None:
                    ses.enviar(*_refrescar(ses, [r]))
                _guardar_bolsa(ses, ses.personaje.char_id)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_mascota(ses.usuario, ses.personaje.char_id, ficha, ses.personaje.mascotas)
                log.info('[%s] mascota renombrada a %s (actualizado en casilla %s)' % (addr, nom, r))
            return

        # The client emits 0x0132 (<II>) instead of 0x002E (<BI>) for slots above 255 (sub_61B000).
        # This includes card registration (276..325), furniture (326..425),
        # chat bubble equip/unequip (616) and chat bubble bag (617..666).
        if opcode == 0x0132 and ses.rol == 'mundo' and ses.personaje:
            if len(cuerpo) == 8:
                _ranura_card, _param_card = struct.unpack('<II', cuerpo)
                if _param_card == 0:
                    import cartas as _cartas
                    if _cartas.carta_de_item(getattr(ses, 'inventario', {}).get(_ranura_card)):
                        if _cartas.registrar(ses, _ranura_card, _sacar, _refrescar):
                            return
            # Si no es un registro de carta, se procesa como 0x002E para ranuras > 255
            # (por ejemplo, burbujas de chat 616..666).
            opcode = 0x002E

        # Housing opcodes C2S 0x0136..0x0142
        if opcode == 0x0139 and ses.rol == 'mundo' and ses.personaje:
            # closehouse (C2S 313 / 0x0139): Take Back outdoor house.
            # Verified in the 2026-10-16 Global proxy capture.
            import casas as _cs, cuentas as _cta, combate as _cb
            _c = _cs.obtener_o_crear_casa(
                ses.personaje.char_id, ses.personaje.nombre,
                raw_data=getattr(ses.personaje, 'casa', None))
            _old_eid = _c.outdoor_obj_id
            _old_stage = _c.outdoor_stage
            _cs.retirar_casa_outdoor(_c)
            _c.is_open = False
            ses.personaje.casa = _c.serializar()
            if getattr(ses, 'usuario', None):
                _cta.guardar_casa(ses.usuario, ses.personaje.char_id, _c)
            ses.enviar(_cs.pkt_open_close_state(False))
            if _old_eid:
                _despawn = _cb.despawn_monstruo(_old_eid)
                _difundir_en_sala(ses, _despawn)
                if _old_stage:
                    for s in list(self.mundos):
                        if s is not ses and getattr(s, 'personaje', None) and getattr(s.personaje, 'stage', None) == _old_stage:
                            try:
                                s.enviar(_despawn)
                            except Exception:
                                pass
                ses.enviar(_despawn)
            _lv, _prev_m, _next_m = _cs.info_nivel(_c.calcular_magia())
            _rnk = _cs.rango_casa(_c)
            _v_rem = 1 if ses.personaje.char_id not in _c.voted_users_today else 0
            ses.enviar(_cs.pkt_house_info(
                _lv, _c.calcular_magia(), _next_m, _prev_m, _c.bonus_pct,
                _c.cleanliness, _c.votes_total, _c.votes_today,
                _c.visitors_total, _v_rem, _rnk, 1))
            ses.enviar(_cs.pkt_house_name(_c.house_name))
            log.info('[%s] house closed by %s', addr, ses.personaje.nombre)
            return

        if opcode == 0x0137 and ses.rol == 'mundo' and ses.personaje:
            # registryhouse (C2S 311 / 0x0137): Show outdoor house in exhibition map
            import casas as _cs, clases as _cl, cuentas as _cta
            _ok, _motivo = _cs.validar_posicion_outdoor(
                ses.personaje.stage, ses.personaje.tile_x, ses.personaje.tile_y,
                exclude_cid=ses.personaje.char_id)
            if not _ok:
                ses.enviar(_cl.aviso(_motivo, tipo=7))
                return
            _pwd = ''
            if len(cuerpo) >= 37:
                _pwd = cuerpo[4:37].split(b'\x00', 1)[0].decode('latin-1', 'replace')
            elif len(cuerpo) > 0:
                _pwd = cuerpo.decode('latin-1', 'replace').strip('\x00')
            _c = _cs.obtener_o_crear_casa(ses.personaje.char_id, ses.personaje.nombre, raw_data=getattr(ses.personaje, 'casa', None))
            _c.password_md5 = _pwd
            _px_x = int(ses.personaje.tile_x * 32)
            _px_y = int(ses.personaje.tile_y * 32)
            _cs.registrar_casa_outdoor(_c, ses.personaje.stage, _px_x, _px_y, dir_rot=0)
            ses.personaje.casa = _c.serializar()
            if getattr(ses, 'usuario', None):
                _cta.guardar_casa(ses.usuario, ses.personaje.char_id, _c)
            ses.enviar(_cs.pkt_open_close_state(True))
            _pkt_out = _cs.pkt_outdoor_house(_c.outdoor_obj_id, _c.model_id, _px_x, _px_y, _c.house_name, ses.personaje.nombre, house_size_level=_c.size_level, house_level=_c.level)
            ses.enviar(_pkt_out)
            _difundir_en_sala(ses, _pkt_out)
            _lv, _prev_m, _next_m = _cs.info_nivel(_c.calcular_magia())
            _rnk = _cs.rango_casa(_c)
            _v_rem = 1 if (ses.personaje.char_id not in _c.voted_users_today) else 0
            ses.enviar(_cs.pkt_house_info(_lv, _c.calcular_magia(), _next_m, _prev_m, _c.bonus_pct, _c.cleanliness, _c.votes_total, _c.votes_today, _c.visitors_total, _v_rem, _rnk, 10))
            ses.enviar(_cs.pkt_house_name(_c.house_name))
            log.info('[%s] house opened by %s at stage %d (%d, %d)',
                     addr, ses.personaje.nombre, ses.personaje.stage, _px_x, _px_y)
            return

        if opcode == 0x0136 and ses.rol == 'mundo' and ses.personaje:
            # furnishhouse (C2S 310 / 0x0136): Decorate button clicked.
            # Body is the deed item id (u32).  Verified in the Global capture.
            import casas as _cs, clases as _cl
            _c = getattr(ses, 'casa_visitando', None) or _cs.obtener_o_crear_casa(
                ses.personaje.char_id, ses.personaje.nombre,
                raw_data=getattr(ses.personaje, 'casa', None))
            if _c.is_open:
                ses.enviar(_cl.aviso("Cannot decorate while house is on display. Please take it back first.", tipo=7))
                return
            if _c.owner_id != ses.personaje.char_id:
                ses.enviar(_cl.aviso("Only the owner can decorate this house.", tipo=7))
                return
            if getattr(ses, 'house_furnish_pending', False):
                return  # wait for 0x0009, never send a second map load
            if ses.personaje.stage != _cs.STAGE_HOUSE:
                _entrar_a_casa(ses, addr, _c)
                ses.house_furnish_pending = True
            else:
                ses.house_transition = getattr(ses, 'house_transition', 0) + 1
                ses.casa_visitando = _c
                ses.house_furnishing = True
                _ocultar_interactivos_casa(ses)
                ses.enviar(*_casa_paquetes_decorar(ses, _c))
            log.info('[%s] house furnish mode: owner=%s furniture=%d',
                     addr, ses.personaje.nombre, len(_c.placed_furniture))
            return

        if opcode == 0x0138 and ses.rol == 'mundo' and ses.personaje:
            # leavefurnish (C2S 312 / 0x0138), no body. Boton Leave del editor de decoracion.
            # Salir del modo decoracion y regresar al exterior de donde vino el jugador.
            # NO enviar pkt_visit_furniture_sync (0x013F) aqui: WND_FURNITURELIST ya fue destruida
            # por Lua (OnLeaveFurnish) y sub_66C020 crashea con access violation en el cliente.
            import casas as _cs
            _casa_salir_editor(ses, addr)
            return

        if opcode == 0x013A and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 4:
            # tryentryhouse (C2S 314 / 0x013A)
            import casas as _cs, clases as _cl
            _target_eid = struct.unpack_from('<I', cuerpo, 0)[0]
            _c = _cs.casa_por_obj(_target_eid)
            if not _c:
                _c = _cs.obtener_o_crear_casa(ses.personaje.char_id, ses.personaje.nombre, raw_data=getattr(ses.personaje, 'casa', None))
            if _c.owner_id != ses.personaje.char_id and _c.password_md5:
                _pwd_sent = cuerpo[4:].decode('latin-1', 'replace').strip('\x00') if len(cuerpo) > 4 else ''
                if not _pwd_sent:
                    ses.enviar(_cs.pkt_request_password(_target_eid))
                    return
                if _pwd_sent != _c.password_md5:
                    ses.enviar(_cl.aviso("Incorrect house password!", tipo=7))
                    return
            if _c.owner_id != ses.personaje.char_id:
                _c.visitors_total += 1
            _entrar_a_casa(ses, addr, _c)
            ses.enviar(_cs.pkt_visit_furniture_sync(_c.placed_furniture))
            _lv, _prev_m, _next_m = _cs.info_nivel(_c.calcular_magia())
            _rnk = _cs.rango_casa(_c)
            _v_rem = 1 if (ses.personaje.char_id not in _c.voted_users_today) else 0
            ses.enviar(_cs.pkt_house_info(_lv, _c.calcular_magia(), _next_m, _prev_m, _c.bonus_pct, _c.cleanliness, _c.votes_total, _c.votes_today, _c.visitors_total, _v_rem, _rnk, 10 if _c.is_open else 1))
            ses.enviar(_cs.pkt_house_name(_c.house_name))
            log.info(f"[{addr}] {ses.personaje.nombre} entered house of {_c.owner_name}")
            return

        if opcode == 0x013B and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 21:
            # savefurniture
            import casas as _cs, cuentas as _cta, clases as _cl
            _c = getattr(ses, 'casa_visitando', None)
            if (_c is None or _c.owner_id != ses.personaje.char_id
                    or _c.is_open
                    or ses.personaje.stage != _cs.STAGE_HOUSE
                    or not getattr(ses, 'house_furnishing', False)):
                log.warning('[%s] savefurniture fuera de una sesion de decoracion valida', addr)
                return
            _f_cnt = struct.unpack_from('<I', cuerpo, 0)[0]
            _cap = (_cs.CAPACIDAD_MUEBLES[_c.size_level]
                    if _c.size_level < len(_cs.CAPACIDAD_MUEBLES) else 35)
            if _f_cnt > _cap + 2:
                log.warning('[%s] savefurniture invalido: count=%d body=%d cap=%d',
                            addr, _f_cnt, len(cuerpo), _cap)
                ses.enviar(_cl.aviso("The furniture layout was not saved: invalid data.", tipo=0))
                return
            try:
                _nom_raw, _entries = _cs.parse_save_layout(cuerpo)
            except ValueError as _err:
                log.warning('[%s] savefurniture invalido: %s', addr, _err)
                ses.enviar(_cl.aviso("The furniture layout was not saved: invalid data.", tipo=0))
                return
            for _entry in _entries:
                if not _cs.item_a_mueble(_entry['item_id']):
                    log.warning('[%s] savefurniture rechazo item no-mueble %d',
                                addr, _entry['item_id'])
                    ses.enviar(_cl.aviso("The furniture layout contains an invalid item.", tipo=0))
                    return
            _ordinary = [e for e in _entries
                         if not _cs.es_escena_item(e['item_id'])
                         and not _cs.es_estilo_exterior_item(e['item_id'])]
            if len(_ordinary) > _cap:
                ses.enviar(_cl.aviso(f"Exceeded furniture capacity for this house size ({_cap})!", tipo=0))
                return
            if sum(1 for e in _entries if _cs.es_escena_item(e['item_id'])) > 1:
                return
            if sum(1 for e in _entries if _cs.es_estilo_exterior_item(e['item_id'])) > 1:
                return
            _uids = [e['item_uid'] for e in _entries if e['item_uid']]
            if len(_uids) != len(set(_uids)):
                log.warning('[%s] savefurniture rechazo UIDs duplicados', addr)
                return

            # Reconcile the placed list with the dedicated Furniture bag.
            # This makes Save atomic and prevents both duplication and loss.
            _old_entries = list(_c.placed_furniture)
            _old_counts = collections.Counter(e['item_id'] for e in _old_entries)
            _new_counts = collections.Counter(e['item_id'] for e in _entries)
            _add = _new_counts - _old_counts
            _remove = _old_counts - _new_counts
            _free_defaults = {9954: 1, 14660: 1}
            _need = collections.Counter()
            for _iid, _qty in _add.items():
                _gratis = min(_qty, _free_defaults.get(_iid, 0)) if _old_counts[_iid] == 0 else 0
                if _qty > _gratis:
                    _need[_iid] = _qty - _gratis
            _furn_slots = list(range(_cs.SLOT_FURN_INI, _cs.SLOT_FURN_FIN + 1)) + list(range(20, 121))
            _available = collections.Counter()
            for _slot in _furn_slots:
                if _slot in ses.inventario:
                    _available[int(ses.inventario[_slot])] += _cant_de(ses, _slot)
            if any(_available[_iid] < _qty for _iid, _qty in _need.items()):
                log.warning('[%s] savefurniture intento colocar muebles no poseidos: %s',
                            addr, dict(_need - _available))
                ses.enviar(_cl.aviso("The furniture layout was not saved: missing item.", tipo=7, msg_id=_cl.MSG_TEXTO))
                return
            _consume_plan = []
            for _iid, _qty in _need.items():
                _left = _qty
                for _slot in _furn_slots:
                    if _left <= 0:
                        break
                    if int(ses.inventario.get(_slot, 0)) != _iid:
                        continue
                    _take = min(_left, _cant_de(ses, _slot))
                    _consume_plan.append((_slot, _take))
                    _left -= _take
            _return_entries = []
            _remaining_remove = _remove.copy()
            for _entry in _old_entries:
                _iid = _entry['item_id']
                if _remaining_remove[_iid] > 0:
                    _remaining_remove[_iid] -= 1
                    if _iid not in _free_defaults:
                        _return_entries.append(_entry)
            _occupied = sum(1 for s in range(_cs.SLOT_FURN_INI, _cs.SLOT_FURN_FIN + 1)
                            if s in ses.inventario)
            _slots_freed = sum(1 for s, n in _consume_plan
                               if n >= _cant_de(ses, s) and _cs.SLOT_FURN_INI <= s <= _cs.SLOT_FURN_FIN)
            if _occupied - _slots_freed + len(_return_entries) > 100:
                ses.enviar(_cl.aviso("The Furniture bag needs more free slots.", tipo=7, msg_id=_cl.MSG_TEXTO))
                return

            _inv_before = dict(ses.inventario)
            _qty_before = dict(_cantidades(ses))
            _inst_before = dict(_instancias(ses))
            _touched = set()
            try:
                for _slot, _take in _consume_plan:
                    _sacar(ses, _slot, _take)
                    _touched.add(_slot)
                for _entry in _return_entries:
                    _slot = next((s for s in range(_cs.SLOT_FURN_INI,
                                                   _cs.SLOT_FURN_FIN + 1)
                                  if s not in ses.inventario), None)
                    if _slot is None:
                        _slot = _ranura_libre(ses.inventario)
                    if _slot is None:
                        raise RuntimeError('Furniture bag unexpectedly full')

                    ses.inventario[_slot] = _entry['item_id']
                    _cantidades(ses).pop(_slot, None)
                    _uid = int(_entry.get('item_uid') or 0)
                    _instancias(ses)[_slot] = struct.pack('<Q', _uid) if _uid else bytes(8)
                    _touched.add(_slot)
                if _nom_raw and any(ch.isalnum() for ch in _nom_raw):
                    _c.house_name = _nom_raw[:16].strip()
                _c.placed_furniture = _entries
                ses.personaje.casa = _c.serializar()
                if getattr(ses, 'usuario', None):
                    _cta.guardar_casa_e_inventario(
                        ses.usuario, ses.personaje.char_id, _c,
                        ses.inventario, _cantidades(ses),
                        getattr(ses.personaje, 'mejoras', None))
            except Exception:
                ses.inventario.clear()
                ses.inventario.update(_inv_before)
                _cantidades(ses).clear()
                _cantidades(ses).update(_qty_before)
                _instancias(ses).clear()
                _instancias(ses).update(_inst_before)
                _c.placed_furniture = _old_entries
                ses.personaje.casa = _c.serializar()
                log.exception('[%s] savefurniture rollback', addr)
                ses.enviar(_cl.aviso("The furniture layout could not be saved.", tipo=0))
                return
            if _touched:
                ses.enviar(*_refrescar(ses, sorted(_touched)))
            _lv, _prev_m, _next_m = _cs.info_nivel(_c.calcular_magia())
            _rnk = _cs.rango_casa(_c)
            _v_rem = 1 if (ses.personaje.char_id not in _c.voted_users_today) else 0
            ses.enviar(_cs.pkt_house_info(_lv, _c.calcular_magia(), _next_m, _prev_m, _c.bonus_pct, _c.cleanliness, _c.votes_total, _c.votes_today, _c.visitors_total, _v_rem, _rnk, 10 if _c.is_open else 1))
            ses.enviar(_cs.pkt_house_name(_c.house_name))
            log.info(f"[{addr}] saved {len(_entries)} furniture items for {_c.house_name} (magic: {_c.calcular_magia()}, lv: {_lv})")
            return

        if opcode == 0x013C and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 4:
            # IGG sub_6235D0 sends <H 0x013C, I ticket_id> for Ball Tickets.
            import casas as _cs, cuentas as _cta, clases as _cl
            _c = _cs.obtener_o_crear_casa(ses.personaje.char_id, ses.personaje.nombre, raw_data=getattr(ses.personaje, 'casa', None))
            _value = struct.unpack_from('<I', cuerpo, 0)[0]
            if _value in _cs.BALL_TICKETS:
                _slot = _ranura_de_item(ses, _value)
                self._activar_baile_casa(ses, _value, _slot)
                return
            else:
                _c.options = _value
            ses.personaje.casa = _c.serializar()
            if getattr(ses, 'usuario', None):
                _cta.guardar_casa(ses.usuario, ses.personaje.char_id, _c)
            return

        if opcode == 0x013D and ses.rol == 'mundo' and ses.personaje:
            # Furniture Egg Machine.  The packet layout is verified, but the
            # reward formula is not.  Never consume five real items using a
            # guessed random table.
            import casas as _cs, clases as _cl
            ses.enviar(_cl.aviso(
                "Furniture recycling is disabled until its original reward table is verified; no items were consumed.",
                tipo=0))
            return

        if opcode == 0x013E and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 4:
            # sethousepetradio
            import casas as _cs, cuentas as _cta
            _c = _cs.obtener_o_crear_casa(ses.personaje.char_id, ses.personaje.nombre, raw_data=getattr(ses.personaje, 'casa', None))
            _c.pet_radio = struct.unpack_from('<I', cuerpo, 0)[0]
            ses.personaje.casa = _c.serializar()
            if getattr(ses, 'usuario', None):
                _cta.guardar_casa(ses.usuario, ses.personaje.char_id, _c)
            return

        if opcode == 0x013F and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 1:
            # trycastvote
            import casas as _cs, clases as _cl, cuentas as _cta
            _c = getattr(ses, 'casa_visitando', None) or _cs.obtener_o_crear_casa(ses.personaje.char_id, ses.personaje.nombre, raw_data=getattr(ses.personaje, 'casa', None))
            _c.check_daily_reset()
            _cid = int(ses.personaje.char_id)
            if _cid in _c.voted_users_today:
                ses.enviar(_cl.aviso("You have already voted for this house today!", tipo=0))
                return
            _c.voted_users_today.add(_cid)
            _c.votes_today += 1
            _c.votes_total += 1
            _txt = cuerpo.decode('latin-1', 'replace').strip('\x00').strip()
            if _txt:
                _c.vote_notes.insert(0, {
                    'sender_id': _cid,
                    'sender_name': ses.personaje.nombre,
                    'timestamp': int(time.time()),
                    'text': _txt[:132]
                })
                if len(_c.vote_notes) > 50:
                    _c.vote_notes = _c.vote_notes[:50]
            if getattr(ses, 'usuario', None):
                _cta.guardar_casa(ses.usuario, _c.owner_id, _c)
            _lv, _prev_m, _next_m = _cs.info_nivel(_c.calcular_magia())
            _rnk = _cs.rango_casa(_c)
            ses.enviar(_cs.pkt_house_info(_lv, _c.calcular_magia(), _next_m, _prev_m, _c.bonus_pct, _c.cleanliness, _c.votes_total, _c.votes_today, _c.visitors_total, 0, _rnk, 10 if _c.is_open else 1))
            ses.enviar(_cl.aviso("Thank you for voting!", tipo=0))
            return

        if opcode == 0x0140 and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 2:
            # votenotechangepage
            import casas as _cs
            _page = struct.unpack_from('<H', cuerpo, 0)[0]
            _c = getattr(ses, 'casa_visitando', None) or _cs.obtener_o_crear_casa(ses.personaje.char_id, ses.personaje.nombre, raw_data=getattr(ses.personaje, 'casa', None))
            _start = _page * 5
            _notes = _c.vote_notes[_start:_start + 5]
            ses.enviar(_cs.pkt_view_vote_notes(_page, len(_c.vote_notes), _notes))
            return

        if opcode in (0x0141, 0x0142) and ses.rol == 'mundo' and ses.personaje:
            # trygotosenderhouse / gotobillboardhouse
            import casas as _cs, clases as _cl
            if opcode == 0x0141:
                if len(cuerpo) != 38:
                    return
                _target_owner_id = struct.unpack_from('<I', cuerpo, 1)[0]
            else:
                if len(cuerpo) != 7:
                    return
                _target_owner_id = struct.unpack_from('<I', cuerpo, 3)[0]
            _c = _cs.obtener_o_crear_casa(_target_owner_id, f"Owner_{_target_owner_id}")
            _c.visitors_total += 1
            _entrar_a_casa(ses, addr, _c)
            ses.enviar(_cs.pkt_visit_furniture_sync(_c.placed_furniture))
            _lv, _prev_m, _next_m = _cs.info_nivel(_c.calcular_magia())
            _rnk = _cs.rango_casa(_c)
            _v_rem = 1 if (ses.personaje.char_id not in _c.voted_users_today) else 0
            ses.enviar(_cs.pkt_house_info(_lv, _c.calcular_magia(), _next_m, _prev_m, _c.bonus_pct, _c.cleanliness, _c.votes_total, _c.votes_today, _c.visitors_total, _v_rem, _rnk, 10 if _c.is_open else 1))
            ses.enviar(_cs.pkt_house_name(_c.house_name))
            return

        # WND_EXCHANGE (sendExchange Lua: opcode 0x0160 o 0x0148)
        if opcode in (0x0160, 0x0148) and ses.rol == 'mundo' and ses.personaje and len(cuerpo) >= 4:
            import clases as _cl
            if len(cuerpo) >= 8:
                rec_id, veces = struct.unpack_from('<II', cuerpo, 0)
            else:
                rec_id = struct.unpack_from('<I', cuerpo, 0)[0]
                veces = 1
            veces = max(1, min(100, int(veces)))
            receta = _obtener_receta_exchange(rec_id)
            if not receta:
                ses.enviar(_cl.aviso("Invalid exchange recipe.", tipo=7, msg_id=_cl.MSG_TEXTO))
                return
            # Verificar materiales
            falta = False
            for mat_id, mat_cnt in receta['materiales']:
                req_tot = mat_cnt * veces
                if _cant_total_item(ses, mat_id) < req_tot:
                    falta = True
                    break
            if falta:
                ses.enviar(_cl.aviso("You don't have enough materials for this exchange.", tipo=7, msg_id=_cl.MSG_TEXTO))
                return
            # Consumir materiales
            tocadas = []
            for mat_id, mat_cnt in receta['materiales']:
                tocadas.extend(_consumir_item_total(ses, mat_id, mat_cnt * veces))
            # Entregar recompensas
            for rew_id, rew_cnt in receta['premios']:
                tot_rew = rew_cnt * veces
                dest = _meter(ses, rew_id, tot_rew)
                if dest is not None:
                    tocadas.append(dest)
            if tocadas:
                ses.enviar(*_refrescar(ses, list(set(tocadas))))
            _guardar_bolsa(ses, ses.personaje.char_id)
            ses.enviar(_cl.aviso("Exchange successful!", tipo=7, msg_id=_cl.MSG_TEXTO))
            log.info(f"[{addr}] Exchange recipe {rec_id} x{veces} completed successfully.")
            return

        if opcode == 0x002E and ses.rol == 'mundo' and len(cuerpo) >= 4:
            import inventario as inv
            import clases as _c
            # DOS FORMAS del mismo mensaje. Cuando el cuerpo trae CINCO bytes
            # es "usar la casilla X SOBRE la casilla Y": un byte de origen y
            # un LE32 de destino. Es lo que manda el juego al hacer clic
            # derecho en un mortero y luego clic izquierdo en el equipo.
            # Medido el 29/09/2026: "252b000000" es la casilla 37 sobre la 43.
            objetivo = None
            bolsa = getattr(ses, 'inventario', None)
            if bolsa is None:
                return
            if len(cuerpo) == 8:
                ranura, target_raw = struct.unpack_from('<II', cuerpo, 0)
                objetivo = target_raw if target_raw != 0 else None
            elif len(cuerpo) == 5:
                if cuerpo[4] == 0 and cuerpo[0] not in bolsa and struct.unpack_from('<I', cuerpo, 0)[0] in bolsa:
                    ranura = struct.unpack_from('<I', cuerpo, 0)[0]
                else:
                    ranura = cuerpo[0]
                    objetivo = struct.unpack_from('<I', cuerpo, 1)[0]
            else:
                ranura = struct.unpack_from('<I', cuerpo, 0)[0]
            if ranura not in bolsa:
                _r_alt = _ranura_de_item(ses, ranura)
                if _r_alt is not None and _r_alt in bolsa:
                    ranura = _r_alt
                else:
                    return

            # Poke Egg (XML formula 19): activate the target cursor.  Some
            # client builds include the entity in this same 0x002E; others
            # send the monster afterwards in the regular 0x0005 click.
            import house_services as _hs_capture
            if int(bolsa[ranura]) in _hs_capture.capture_eggs():
                ses.captura_pendiente = {
                    'slot': int(ranura),
                    'item': int(bolsa[ranura]),
                    'time': time.time(),
                }
                if objetivo:
                    _intentar_captura_monstruo(ses, int(objetivo), addr)
                else:
                    ses.enviar(_c.aviso(
                        'Click the monster you want to capture.', tipo=7,
                        msg_id=_c.MSG_TEXTO))
                return

            # SACAR O GUARDAR LA MASCOTA. Medido el 29/09/2026: el juego
            # manda "2100000000", o sea la casilla 33 con destino cero, que
            # es donde estaba la Battlemaid. No es una mejora ni se equipa:
            # la mascota SIGUE EN LA MOCHILA y lo que pasa es que aparece
            # como criatura al lado del jugador. Se vio entrar y salir tres
            # veces sin moverse de la casilla 33.
            if (inv.es_mascota(bolsa[ranura]) and ses.personaje
                    and not objetivo):
                _pet_alternar(ses, addr, ranura)
                return

            # MEJORAS: morteros, martillos, piensos y gemas (incluyendo desde la barra F1-F12).
            if ses.personaje:
                import mejoras as _mj_2e
                _clase_m = _mj_2e.clase_de(bolsa[ranura])
                if _clase_m:
                    _obj_m = objetivo if (objetivo is not None and objetivo in bolsa) else None
                    if _obj_m is None:
                        if _clase_m in ('pienso_mascota', 'gema_mascota'):
                            _f_m = getattr(ses.personaje, 'mascota', None)
                            if _f_m and _f_m.get('ranura') in bolsa:
                                _obj_m = _f_m.get('ranura')
                        elif _clase_m == 'pienso_montura':
                            if 10 in bolsa:
                                _obj_m = 10
                    if _obj_m is not None and _obj_m in bolsa:
                        _res = _usar_mejora(ses, addr, ranura, _obj_m)
                        if _res:
                            return
            item_id = bolsa[ranura]
            cid = ses.personaje.char_id if ses.personaje else 4980

            # Caso 0: objeto que da CREDITOS DE RANGO.
            #
            # Va delante de todo lo demas porque son materiales, y sin esto
            # caerian en el caso de consumible o se quedarian sin hacer nada.
            # La secuencia es la que manda el servidor real al usar uno: el
            # 0x0013 con el atributo 49 y el total acumulado, y detras un
            # 0x0282 con lo que se acaba de sumar escrito en ASCII.
            # Caso 0: OBJETO QUE RECUPERA SP (SP Power Scroll y compania).
            #
            # El objeto no trae el numero: trae un 常駐法術 y es el HECHIZO
            # el que lleva la columna SP. El 3696 apunta al 1871, que tiene
            # SP=2000 -- las "2 SP lamps" de su descripcion, porque una
            # lampara son 1000 puntos. No se detectaba de ninguna forma, asi
            # que el objeto ni se gastaba ni hacia nada.
            # Caso 0: CERTIFICADOS DE SANGRE / PET EVOLUTION CERTIFICATES (Medium & Advanced)
            _cert_etapa = inv.es_certificado_sangre(item_id)
            if _cert_etapa and ses.personaje:
                import mascotas as _mscert
                import clases as _clcert
                import combate as _cbcert
                _f_pet = None
                if objetivo is not None and objetivo in bolsa and inv.es_mascota(bolsa[objetivo]):
                    _f_pet = _pet_ficha(ses, objetivo)
                if not _f_pet:
                    _f_pet = getattr(ses.personaje, 'mascota', None)
                if not _f_pet:
                    ses.enviar(_clcert.aviso('You do not have an active pet to evolve.', tipo=0))
                    return

                _ok_evo, _msg_evo = _mscert.aplicar_certificado(_f_pet, _cert_etapa)
                if not _ok_evo:
                    ses.enviar(_clcert.aviso(_msg_evo, tipo=0))
                    return

                # Consumir 1 certificado
                _queda = ses.cantidades.get(ranura, 1) - 1
                if _queda > 0:
                    ses.cantidades[ranura] = _queda
                else:
                    ses.inventario.pop(ranura, None)
                    ses.cantidades.pop(ranura, None)

                _r_pet_c = _f_pet.get('ranura')
                if _r_pet_c is not None and getattr(ses.personaje, 'mascotas', None) is not None:
                    ses.personaje.mascotas[str(_r_pet_c)] = _f_pet
                _guardar_bolsa(ses, cid)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_mascota(ses.usuario, cid, _f_pet, getattr(ses.personaje, 'mascotas', None))

                salida_cert = list(_refrescar(ses, [ranura, _r_pet_c]))
                if _f_pet.get('fuera') and _f_pet.get('entidad'):
                    salida_cert.append(_mscert.armar(_f_pet))
                salida_cert.append(_clcert.aviso(_msg_evo, tipo=7, msg_id=_clcert.MSG_TEXTO))

                pet_eid = getattr(ses, 'pet_entity_id', None) or _f_pet.get('entidad')
                if pet_eid and _f_pet.get('fuera'):
                    yo = ses.personaje.entity_id
                    salida_cert.extend([
                        _mscert.quitar(int(pet_eid)),
                        _mscert.enlazar(yo, 0)
                    ])
                    new_eid = _pet_siguiente_entidad(ses)
                    _f_pet['entidad'] = new_eid
                    ses.pet_entity_id = new_eid
                    _est = dict(_f_pet)
                    _ptile = getattr(ses, 'pet_tile', [ses.personaje.tile_x, ses.personaje.tile_y])
                    _est.update({
                        'entidad': new_eid,
                        'x': _ptile[0],
                        'y': _ptile[1],
                        'dueno': yo,
                        'dueno_nombre': ses.personaje.nombre,
                        'tipo': _f_pet.get('tipo', 0)
                    })
                    salida_cert.extend([
                        _mscert.entidad_mundo(_pet_plantilla(), _est),
                        _mscert.enlazar(yo, new_eid),
                        _mscert.armar(_f_pet),
                        _cbcert.atributo(new_eid, _mscert.hp_eff(_f_pet), _cbcert.KIND_HP),
                    ])
                    if int(_f_pet.get('saciedad', 0)) > 100:
                        salida_cert.append(struct.pack('<HIBBII', 0x001D, new_eid, 1, 4, 3796, max(60000, (int(_f_pet['saciedad']) - 100) * 60000)))

                ses.enviar(*salida_cert)
                log.info(f"[{addr}] mascota evoluciono con certificado etapa {_cert_etapa}: {_f_pet.get('nombre')}")
                return

            _nom_item_l = (_nombre_item(item_id) or '').lower()
            if ('star-up' in _nom_item_l or 'star up' in _nom_item_l or item_id in (5902, 5903, 3379)) and ses.personaje:
                import clases as _clst
                import mascotas as _msst
                import combate as _cbst
                _f = None
                if objetivo is not None and objetivo in bolsa and inv.es_mascota(bolsa[objetivo]):
                    _f = _pet_ficha(ses, objetivo)
                if not _f:
                    _f = getattr(ses.personaje, 'mascota', None)
                if not _f:
                    ses.enviar(_clst.aviso('You do not have an active pet.', tipo=0))
                    return
                _st_sub = 10 if ('card' in _nom_item_l or item_id in (5902, 5903)) else 1
                _nueva_st = _msst.subir_estrella(_f, _st_sub)
                _queda = ses.cantidades.get(ranura, 1) - 1
                if _queda > 0:
                    ses.cantidades[ranura] = _queda
                else:
                    ses.inventario.pop(ranura, None)
                    ses.cantidades.pop(ranura, None)
                _r_pet = _f.get('ranura')
                if _r_pet is not None and getattr(ses.personaje, 'mascotas', None) is not None:
                    ses.personaje.mascotas[str(_r_pet)] = _f
                salida_st = list(_refrescar(ses, [ranura] + ([_r_pet] if _r_pet is not None else [])))
                if _f.get('fuera') and _f.get('entidad'):
                    _peid_st = int(_f['entidad'])
                    salida_st.append(_msst.armar(_f))
                    salida_st.append(_cbst.atributo(_peid_st, _msst.hp_eff(_f), _cbst.KIND_HP))
                    salida_st.append(struct.pack('<HIBBI', 0x0013, _peid_st, 1, 0x42, max(1, int(_nueva_st))))
                    if int(_f.get('saciedad', 0)) > 100:
                        salida_st.append(struct.pack('<HIBBII', 0x001D, _peid_st, 1, 4, 3796, max(60000, (int(_f['saciedad']) - 100) * 60000)))
                salida_st.append(_clst.aviso(f"Pet star level upgraded! ({_nueva_st / 10.0:.1f} Stars)", tipo=7, msg_id=_clst.MSG_TEXTO))
                ses.enviar(*salida_st)
                _guardar_bolsa(ses, cid)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_mascota(ses.usuario, cid, _f, getattr(ses.personaje, 'mascotas', None))
                log.info(f"[{addr}] estrella de mascota {_f.get('nombre')} subio a {_nueva_st} (Star Level {_nueva_st/10.0:.1f})")
                return

            _sp_item = inv.sp_de_item(item_id)
            if _sp_item > 0 and ses.personaje:
                import combate as _cbsp
                yo = ses.personaje.entity_id
                _bars, _tope = _max_sp_info(ses.personaje)
                _antes = getattr(ses, 'sp', 0) or 0
                _ganado = _sumar_sp(ses, yo, _sp_item, addr)
                _queda = ses.cantidades.get(ranura, 1) - 1
                if _queda > 0:
                    ses.cantidades[ranura] = _queda
                else:
                    ses.inventario.pop(ranura, None)
                    ses.cantidades.pop(ranura, None)
                ses.enviar(_cbsp.numero_flotante(yo, _ganado,
                                                 _cbsp.TIPO_CURA_SP))
                ses.enviar(*_refrescar(ses, [ranura]))
                _guardar_bolsa(ses, cid)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_progreso(
                        ses.usuario, cid, ses.personaje.nivel,
                        ses.personaje.exp, ses.personaje.hp, ses.personaje.mp,
                        ses.personaje.habilidades,
                        hp_max=ses.personaje.hp_max,
                        mp_max=ses.personaje.mp_max, sp=ses.sp,
                        buffs=getattr(ses.personaje, 'buffs', None))
                log.info('[%s] %s: +%d de SP (%d -> %d)'
                         % (addr, _nombre_item(item_id), _sp_item,
                            _antes, ses.sp))
                return

            # --- House System Consumables ---
            # 1. Liquid Soap / Soap Powder
            if item_id in (10603, 15163, 20077, 10626, 10627) and ses.personaje:
                import casas as _cs_soap, clases as _cl_soap, cuentas as _cta_soap
                _c = _cs_soap.obtener_o_crear_casa(ses.personaje.char_id, ses.personaje.nombre, raw_data=getattr(ses.personaje, 'casa', None))
                if _c.cleanliness >= 1000:
                    ses.enviar(_cl_soap.aviso("Your house is already sparkling clean!", tipo=0))
                    return
                _clean_map = _cs_soap.SOAP_CLEAN
                _add_clean = _clean_map.get(item_id, 100 if item_id == 10627 else 500)
                _c.cleanliness = min(1000, _c.cleanliness + _add_clean)
                ses.personaje.casa = _c.serializar()
                if getattr(ses, 'usuario', None):
                    _cta_soap.guardar_casa(ses.usuario, ses.personaje.char_id, _c)
                _sacar(ses, ranura, 1)
                ses.enviar(*_refrescar(ses, [ranura]))
                _guardar_bolsa(ses, cid)
                # Actualizar buff de bono extra por limpieza arriba de 500
                ses.personaje.buffs.pop('house_clean_bonus', None)
                # Enviar siempre pkt_house_info para actualizar la ventana House Info inmediatamente
                _lv, _prev_m, _next_m = _cs_soap.info_nivel(_c.calcular_magia())
                _rnk = _cs_soap.rango_casa(_c)
                _v_rem = 1 if (ses.personaje.char_id not in _c.voted_users_today) else 0
                ses.enviar(_cs_soap.pkt_house_info(_lv, _c.calcular_magia(), _next_m, _prev_m, _c.bonus_pct, _c.cleanliness, _c.votes_total, _c.votes_today, _c.visitors_total, _v_rem, _rnk, 10 if _c.is_open else 1))
                ses.enviar(_cl_soap.aviso(f"House cleanliness restored to {_c.cleanliness}!", tipo=7, msg_id=_cl_soap.MSG_TEXTO))
                log.info(f"[{addr}] used soap {item_id}: house cleanliness now {_c.cleanliness} (bonus={_c.bonus_pct}%)")
                return

            # 1b. House Deeds (10115, 10116, 10117, 17934..17937, 20076)
            if item_id in (10115, 10116, 10117, 17934, 17935, 17936, 17937, 20076) and ses.personaje:
                import casas as _cs_deed, clases as _cl_deed, cuentas as _cta_deed
                _c = _cs_deed.obtener_o_crear_casa(ses.personaje.char_id, ses.personaje.nombre, raw_data=getattr(ses.personaje, 'casa', None))
                if _c.deed_id == item_id:
                    ses.inventario[_cs_deed.SLOT_DEED] = item_id
                    ses.personaje.inventario[_cs_deed.SLOT_DEED] = item_id
                    ses.enviar(*_refrescar(ses, [_cs_deed.SLOT_DEED]))
                    return
                # Do not resize the scene while it is being used, or orphan
                # furniture when switching to a smaller house.
                if ses.personaje.stage == _cs_deed.STAGE_HOUSE:
                    ses.enviar(_cl_deed.aviso("Leave the house before changing its deed.", tipo=0))
                    return
                _candidate = _cs_deed.CasaData(_c.owner_id, _c.owner_name, item_id)
                _placed = sum(not _cs_deed.es_escena_item(f['item_id'])
                              and not _cs_deed.es_estilo_exterior_item(f['item_id'])
                              for f in _c.placed_furniture)
                if _placed > _candidate.capacidad_maxima:
                    ses.enviar(_cl_deed.aviso(
                        "Remove furniture before switching to this smaller house.", tipo=0))
                    return
                old_deed = _c.deed_id
                _c.deed_id = item_id
                ses.personaje.casa = _c.serializar()
                if ranura != 376:
                    if old_deed and old_deed != item_id:
                        ses.inventario[ranura] = old_deed
                        if getattr(ses.personaje, 'inventario', None):
                            ses.personaje.inventario[ranura] = old_deed
                    else:
                        _sacar(ses, ranura, 1)
                ses.inventario[376] = item_id
                if getattr(ses.personaje, 'inventario', None):
                    ses.personaje.inventario[376] = item_id
                ses.enviar(*_refrescar(ses, [ranura, 376]))
                if getattr(ses, 'usuario', None):
                    _cta_deed.guardar_casa(ses.usuario, ses.personaje.char_id, _c)
                    _guardar_bolsa(ses, ses.personaje.char_id)
                # Si la casa esta colocada afuera, actualizar su aspecto y tamano en vivo
                if _c.is_open and _c.outdoor_stage:
                    _pkt_out = _cs_deed.pkt_outdoor_house(
                        _c.outdoor_obj_id, _c.model_id,
                        _c.outdoor_px[0], _c.outdoor_px[1],
                        _c.house_name, ses.personaje.nombre,
                        dir_rot=_c.outdoor_dir,
                        house_size_level=_c.size_level,
                        house_level=_c.level
                    )
                    ses.enviar(_pkt_out)
                    _difundir_en_sala(ses, _pkt_out)
                _lv, _prev_m, _next_m = _cs_deed.info_nivel(_c.calcular_magia())
                _rnk = _cs_deed.rango_casa(_c)
                _v_rem = 1 if (ses.personaje.char_id not in _c.voted_users_today) else 0
                ses.enviar(_cs_deed.pkt_house_info(_lv, _c.calcular_magia(), _next_m, _prev_m,
                                                  _c.bonus_pct, _c.cleanliness,
                                                  _c.votes_total, _c.votes_today,
                                                  _c.visitors_total, _v_rem, _rnk,
                                                  10 if _c.is_open else 1))
                ses.enviar(_cl_deed.aviso(f"House upgraded to {_nombre_item(item_id)}! Capacity: {_c.capacidad_maxima}", tipo=7, msg_id=_cl_deed.MSG_TEXTO))
                log.info(f"[{addr}] used deed {item_id}: house size_level now {_c.size_level}, model {_c.model_id}")
                return

            # 2. Ball Tickets & Party Candies
            import casas as _cs_ball
            if item_id in _cs_ball.BALL_TICKETS and ses.personaje:
                self._activar_baile_casa(ses, item_id, ranura)
                return

            if 10569 <= item_id <= 10580 and ses.personaje:
                _sacar(ses, ranura, 1)
                p = ses.personaje
                if not hasattr(p, 'buffs') or not isinstance(p.buffs, dict):
                    p.buffs = {}
                p.buffs[f'party_candy_{item_id}'] = {
                    'item_id': item_id,
                    'fin': int(time.time()) + 7200,
                    'tipo': 'party_candy'
                }
                dur_ms = 7200 * 1000
                ses.enviar(
                    *_refrescar(ses, [ranura]),
                    struct.pack('<HIBBII', 0x001D, p.entity_id, 1, 4, item_id, dur_ms)
                )
                _guardar_bolsa(ses, p.char_id)
                return

            # 3. Furniture Hammer (11114..11121)
            if item_id in range(11114, 11122) and ses.personaje:
                import clases as _cl_hm
                ses.enviar(_cl_hm.aviso(
                    "Furniture Hammers are not enabled yet; no item was consumed.",
                    tipo=0))
                return

            # 5. Mercenary Token (10581)
            if item_id == 10581 and ses.personaje:
                _casa_usar_token(ses, ranura)
                return

            # Caso 0: CONSUMIBLE DE MASCOTA (使用目標="目標寵物").
            #
            # El propio item dice que va a la mascota, asi que no hay lista
            # a mano. Dos medidos:
            #   3376 Pet Feed              動態資料1=500  -> saciedad
            #   3460 Pet's Double EXP Card 常駐法術=1866 -> 1800 s, +100% exp
            _pet_uso = inv.uso_en_mascota(item_id)
            if _pet_uso and ses.personaje:
                import clases as _clp
                import mascotas as _msp
                import combate as _cb_pu
                _f = None
                if objetivo is not None and objetivo in bolsa and inv.es_mascota(bolsa[objetivo]):
                    _f = _pet_ficha(ses, objetivo)
                if not _f:
                    _f = getattr(ses.personaje, 'mascota', None)
                if not _f and bolsa:
                    for _r_b, _iid_b in bolsa.items():
                        if inv.es_mascota(_iid_b):
                            _f = _pet_ficha(ses, _r_b)
                            break
                if not _f:
                    ses.enviar(_clp.aviso('no tienes ninguna mascota', tipo=0))
                    return
                _avisos_pu = []
                _sp_ant_pu = _f.get('sprite')
                _sub_pu = 0
                if 'saciedad' in _pet_uso:
                    _sac_ant = int(_f.get('saciedad', 0))
                    _int_ant = int(_f.get('intimidad', 60))
                    _val, _puede = _msp.alimentar(_f, _pet_uso['saciedad'])
                    _diff_sac = max(0, _val - _sac_ant)
                    _diff_int = max(0, int(_f.get('intimidad', 60)) - _int_ant)
                    if _diff_sac > 0:
                        _avisos_pu.append(_clp.aviso(str(_diff_sac), tipo=7, msg_id=969))
                    if _diff_int > 0:
                        _avisos_pu.append(_clp.aviso(str(_diff_int), tipo=7, msg_id=966))
                    _txt = 'saciedad %d' % _val
                elif 'exp' in _pet_uso:
                    _sub_pu = _msp.dar_exp(_f, _pet_uso['exp'])
                    _txt = '+%d exp (%d niveles -> nv %d)' % (_pet_uso['exp'], _sub_pu, _f.get('nivel', 1))
                else:
                    _msp.poner_buff_exp(_f, _pet_uso['segundos'],
                                        _pet_uso['exp_pct'])
                    _txt = ('x%.1f de experiencia durante %d s'
                            % (1 + _pet_uso['exp_pct'] / 100.0,
                               _pet_uso['segundos']))
                _queda = ses.cantidades.get(ranura, 1) - 1
                if _queda > 0:
                    ses.cantidades[ranura] = _queda
                else:
                    ses.inventario.pop(ranura, None)
                    ses.cantidades.pop(ranura, None)
                _r_pet = _f.get('ranura')
                if _r_pet is not None and getattr(ses.personaje, 'mascotas', None) is not None:
                    ses.personaje.mascotas[str(_r_pet)] = _f
                salida_pet = list(_refrescar(ses, [ranura] + ([_r_pet] if _r_pet is not None else [])))
                salida_pet.extend(_avisos_pu)
                salida_pet.append(_msp.armar(_f))
                pet_eid = getattr(ses, 'pet_entity_id', None) or _f.get('entidad')
                if pet_eid and _f.get('fuera'):
                    yo_pu = ses.personaje.entity_id
                    if _sub_pu > 0 and _f.get('sprite') != _sp_ant_pu:
                        old_eid_pu = int(pet_eid)
                        salida_pet.extend([
                            _msp.quitar(old_eid_pu),
                            _msp.enlazar(yo_pu, 0),
                        ])
                        pet_eid = _pet_siguiente_entidad(ses)
                        _f['entidad'] = pet_eid
                        ses.pet_entity_id = pet_eid
                        _est_pu = dict(_f)
                        _est_pu.update({
                            'entidad': pet_eid,
                            'x': _f.get('x', ses.personaje.tile_x + 1),
                            'y': _f.get('y', ses.personaje.tile_y),
                            'dueno': yo_pu,
                            'dueno_nombre': ses.personaje.nombre,
                            'tipo': _f.get('tipo', 0),
                        })
                        salida_pet.extend([
                            _msp.entidad_mundo(_pet_plantilla(), _est_pu),
                            _msp.enlazar(yo_pu, pet_eid),
                            _msp.armar(_f),
                        ])
                    salida_pet.append(_cb_pu.atributo(int(pet_eid), _msp.hp_eff(_f), _cb_pu.KIND_HP))
                    if int(_f.get('saciedad', 0)) > 100:
                        salida_pet.append(struct.pack('<HIBBII', 0x001D, int(pet_eid), 1, 4, 3796, max(60000, (int(_f['saciedad']) - 100) * 60000)))
                    if _pet_uso.get('buff') and _pet_uso.get('segundos'):
                        salida_pet.append(struct.pack('<HIBBII', 0x001D, int(pet_eid), 1, 4, int(_pet_uso['buff']), int(_pet_uso['segundos']) * 1000))
                ses.enviar(*salida_pet)
                _guardar_bolsa(ses, cid)
                if getattr(ses, 'usuario', None) and ses.personaje:
                    cuentas.guardar_mascota(ses.usuario, cid, _f, getattr(ses.personaje, 'mascotas', None))
                log.info('[%s] a la mascota %s: %s'
                         % (addr, _f.get('nombre'), _txt))
                return


            # Caso 0: VALE DE EXPERIENCIA (categoria 經驗卷).
            #
            # Son 188 en el cliente y cada uno lleva a quien va y cuanto da:
            # 動態資料1 es el destino (1 personaje, 2 habilidad, 3 honor,
            # 4 MASCOTA) y 動態資料2 la cantidad. El 28939 que se probo es
            # del 4 con 100.000.000, y el juego lo describe como "increase
            # the current pet's exp by 100,000,000".
            _vale = inv.vale_de_exp(item_id)
            if _vale and ses.personaje:
                _dest, _cuanto = _vale
                if _dest == inv.VALE_MASCOTA:
                    import mascotas as _msv
                    import combate as _cbv
                    _f = getattr(ses.personaje, 'mascota', None)
                    if not _f:
                        import clases as _clv
                        ses.enviar(_clv.aviso('no tienes ninguna mascota',
                                              tipo=0))
                        return
                    _sp_ant_v = _f.get('sprite')
                    _sub = _msv.dar_exp(_f, _cuanto)
                    _queda = ses.cantidades.get(ranura, 1) - 1
                    if _queda > 0:
                        ses.cantidades[ranura] = _queda
                    else:
                        ses.inventario.pop(ranura, None)
                        ses.cantidades.pop(ranura, None)
                    _r_pet = _f.get('ranura')
                    if _r_pet is not None and getattr(ses.personaje, 'mascotas', None) is not None:
                        ses.personaje.mascotas[str(_r_pet)] = _f
                    salida_v = list(_refrescar(ses, [ranura] + ([_r_pet] if _r_pet is not None else [])))
                    salida_v.append(_msv.armar(_f))
                    pet_eid_v = getattr(ses, 'pet_entity_id', None) or _f.get('entidad')
                    if _f.get('fuera') and pet_eid_v:
                        yo_v = ses.personaje.entity_id
                        if _sub > 0 and _f.get('sprite') != _sp_ant_v:
                            old_eid_v = int(pet_eid_v)
                            salida_v.extend([
                                _msv.quitar(old_eid_v),
                                _msv.enlazar(yo_v, 0),
                            ])
                            pet_eid_v = _pet_siguiente_entidad(ses)
                            _f['entidad'] = pet_eid_v
                            ses.pet_entity_id = pet_eid_v
                            _est_v = dict(_f)
                            _est_v.update({
                                'entidad': pet_eid_v,
                                'x': _f.get('x', ses.personaje.tile_x + 1),
                                'y': _f.get('y', ses.personaje.tile_y),
                                'dueno': yo_v,
                                'dueno_nombre': ses.personaje.nombre,
                                'tipo': _f.get('tipo', 0),
                            })
                            salida_v.extend([
                                _msv.entidad_mundo(_pet_plantilla(), _est_v),
                                _msv.enlazar(yo_v, pet_eid_v),
                                _msv.armar(_f),
                            ])
                        salida_v.append(_cbv.atributo(int(pet_eid_v), _msv.hp_eff(_f), _cbv.KIND_HP))
                        if int(_f.get('saciedad', 0)) > 100:
                            salida_v.append(struct.pack('<HIBBII', 0x001D, int(pet_eid_v), 1, 4, 3796, max(60000, (int(_f['saciedad']) - 100) * 60000)))
                    ses.enviar(*salida_v)
                    _guardar_bolsa(ses, cid)
                    if getattr(ses, 'usuario', None) and ses.personaje:
                        cuentas.guardar_mascota(ses.usuario, cid, _f, getattr(ses.personaje, 'mascotas', None))
                    log.info('[%s] vale de mascota: +%d exp, %s sube %d '
                             'nivel(es) hasta %d'
                             % (addr, _cuanto, _f.get('nombre'), _sub,
                                _f.get('nivel')))
                    return
                # Los otros tres destinos todavia no se aplican; se dice en
                # el log para no perderlos de vista.
                log.info('[%s] vale de experiencia sin implementar: '
                         'destino %d, %d puntos' % (addr, _dest, _cuanto))


            # Consumible custom: Medalla de ascenso de rango (+1 rango por uso)
            import configuracion as _cf_rk
            if int(item_id) == int(getattr(_cf_rk, 'ITEM_MEDALLA_RANGO', 83266)) and ses.personaje:
                import combate as _cb
                import clases as _cl_rk
                _rango_act = max(1, min(20, int(getattr(ses.personaje, 'rango', 1) or 1)))
                if _rango_act >= 20:
                    ses.enviar(_cl_rk.aviso("You have already reached the maximum Rank (20 - God's Mouthpiece)!", tipo=0))
                    return
                _nuevo_rango = _rango_act + 1
                ses.personaje.rango = _nuevo_rango
                # Igual que en el comando de GM: el rango nuevo trae sus
                # creditos, y no se le quitan a quien ya tuviera mas.
                _cred_md = max(int(getattr(ses.personaje, 'creditos', 0) or 0),
                               _cb.creditos_de_rango(_nuevo_rango))
                ses.personaje.creditos = _cred_md
                _queda_rk = _cantidades(ses).get(ranura, 1) - 1
                if _queda_rk > 0:
                    _cantidades(ses)[ranura] = _queda_rk
                else:
                    bolsa.pop(ranura, None)
                    _cantidades(ses).pop(ranura, None)
                _titulo_rk = _cb.NOMBRES_RANGO.get(_nuevo_rango, f"Rank {_nuevo_rango}")
                salida_rk = list(_refrescar(ses, [ranura]))
                salida_rk.append(_cb.atributo(ses.personaje.entity_id, _nuevo_rango, _cb.KIND_RANGO))
                salida_rk.append(_cb.atributo(ses.personaje.entity_id, _cred_md, _cb.KIND_CREDITO))
                salida_rk.append(_cb.efecto_level_up(ses.personaje.entity_id, es_rango=True))
                # Ver la nota del rango por GM: el 251 no existe y la
                # banderola la pone el cliente al recibir KIND_RANGO.
                salida_rk.append(_cl_rk.aviso(f"Rank promoted to Lv.{_nuevo_rango}: {_titulo_rk}!", tipo=0))
                ses.enviar(*salida_rk)
                _guardar_bolsa(ses, cid)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_rango(ses.usuario, cid, _nuevo_rango, _cred_md)
                log.info(f"[{addr}] medalla de rango ({item_id}): rango {_rango_act} -> {_nuevo_rango} ({_titulo_rk})")
                return

            _cred = inv.creditos_de(item_id)
            if _cred and ses.personaje:
                import combate as _cb
                ses.personaje.creditos = (ses.personaje.creditos or 0) + _cred
                _queda = ses.cantidades.get(ranura, 1) - 1
                if _queda > 0:
                    ses.cantidades[ranura] = _queda
                else:
                    bolsa.pop(ranura, None)
                    ses.cantidades.pop(ranura, None)
                salida = list(_refrescar(ses, [ranura]))
                salida.append(_cb.atributo(ses.personaje.entity_id,
                                           ses.personaje.creditos,
                                           _cb.KIND_CREDITO))
                # El cuerpo real lleva DOS ceros detras del numero, no uno:
                # medido "013132303030300000" para 120000.
                salida.append(struct.pack('<HB', 0x0282, 1)
                              + str(_cred).encode('ascii') + b'\x00\x00')
                log.info(f"[{addr}] creditos de rango: +{_cred} "
                         f"(total {ses.personaje.creditos})")
                ses.enviar(*salida)
                _guardar_bolsa(ses, cid)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_rango(ses.usuario, cid, getattr(ses.personaje, 'rango', 1), ses.personaje.creditos)
                return

            # Caso 1: Item equipable (clic derecho)
            if inv.es_equipo(ranura):
                # Ya esta puesto -> desequipar a la bolsa
                if ranura == inv.RANURA_BURBUJA:
                    dst = _ranura_libre(bolsa, desde=inv.PRIMERA_RANURA_BURBUJA_BOLSA, hasta=inv.ULTIMA_RANURA_BURBUJA_BOLSA)
                    if dst is None:
                        dst = _ranura_libre(bolsa, desde=20, hasta=120)
                else:
                    dst = _ranura_libre(bolsa, desde=20)
                if dst is None:
                    import clases as _clf_u
                    ses.enviar(_clf_u.aviso("Your backpack is full.", tipo=0))
                    return
                it = bolsa.pop(ranura)
                bolsa[dst] = it
                _c_un = _cantidades(ses).pop(ranura, 1)
                if _c_un > 1:
                    _cantidades(ses)[dst] = _c_un
                _mover_inst(ses, ranura, dst)
                # Sin acuse: en la captura el 0x002E (usar) no recibe
                # ninguno, solo el 0x0012 de arrastrar.
                salida = list(_refrescar(ses, [ranura, dst]))
                salida.append(_stats_ses(ses))
                salida.extend(_apariencia(ses))
                if ses.personaje:
                    import combate as _cb
                    _max_h = _vida_max(ses.personaje, bolsa=bolsa)
                    if ses.personaje.hp > _max_h:
                        ses.personaje.hp = _max_h
                    _max_m = _mana_max(ses.personaje, bolsa=bolsa)
                    if ses.personaje.mp > _max_m:
                        ses.personaje.mp = _max_m
                    salida.append(_cb.atributo(ses.personaje.entity_id, ses.personaje.hp, _cb.KIND_HP))
                    salida.append(_cb.atributo(ses.personaje.entity_id, ses.personaje.mp, _cb.KIND_MP))
                ses.enviar(*salida)
                import presencia as _pr
                _pr.notificar_equipo(ses)
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa,
                                   _cantidades(ses))
                log.info(f"[{addr}] desequipar: item {it} ({ranura}) -> bolsa ({dst})")
                return

            # Caso 1.0: TARJETAS DE PUESTO (STALL CARDS).
            # En Angel.exe, useextrasaleslot (0x584550) manda C2S 0x002E con la ranura.
            # Los vales consumibles (491..493, 2701..2711, 15715..15717, 79745..79760)
            # y las tarjetas directas (511..513, 2725..2733, 15718..15720) equipan la tarjeta
            # en la ranura 166 (RANURA_PUESTO) para desbloquear puestos de 10 a 50 ranuras (sub_5C3860 / sub_5C39B0).
            tarjeta_equipar = inv.resolver_tarjeta_puesto(item_id)
            if tarjeta_equipar is not None:
                if getattr(ses, 'puesto', None):
                    ses.enviar(_c.aviso('Cannot use this item while running a stall.', tipo=7, msg_id=_c.MSG_TEXTO))
                    return
                _sacar(ses, ranura, 1)
                ses.inventario[inv.RANURA_PUESTO] = tarjeta_equipar
                _cantidades(ses)[inv.RANURA_PUESTO] = 1
                _instancias(ses)[inv.RANURA_PUESTO] = inv.instancia_nueva()

                dur_s = inv.duracion_tarjeta_puesto(tarjeta_equipar)
                expira_ts = 0.0
                if dur_s > 0:
                    expira_ts = time.time() + dur_s
                    if ses.personaje:
                        ses.personaje.expiracion_puesto = expira_ts
                    def _expirar_tarjeta(ses_ref=ses, exp_ts=expira_ts):
                        if (getattr(ses_ref, 'personaje', None) and
                            getattr(ses_ref.personaje, 'expiracion_puesto', 0) == exp_ts and
                            inv.RANURA_PUESTO in getattr(ses_ref, 'inventario', {})):
                            del ses_ref.inventario[inv.RANURA_PUESTO]
                            _cantidades(ses_ref).pop(inv.RANURA_PUESTO, None)
                            ses_ref.personaje.expiracion_puesto = 0.0
                            ses_ref.enviar(_c.aviso("Your Stall Card has expired.", tipo=7, msg_id=_c.MSG_TEXTO),
                                           *_refrescar(ses_ref, [inv.RANURA_PUESTO]))
                            if getattr(ses_ref, 'usuario', None):
                                cuentas.guardar_inventario(ses_ref.usuario, ses_ref.personaje.char_id,
                                                           ses_ref.inventario, _cantidades(ses_ref),
                                                           expiracion_puesto=0.0)
                    asyncio.get_event_loop().call_later(dur_s, _expirar_tarjeta)
                else:
                    if ses.personaje:
                        ses.personaje.expiracion_puesto = 0.0

                nom_item_usado = _nombre_item(item_id)
                salida = [_c.aviso(f'You used {nom_item_usado}!', tipo=7, msg_id=_c.MSG_TEXTO)]
                salida.extend(_refrescar(ses, [ranura, inv.RANURA_PUESTO]))
                ses.enviar(*salida)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa, _cantidades(ses),
                                               expiracion_puesto=expira_ts)
                log.info(f"[{addr}] tarjeta de puesto activada: {item_id} -> {tarjeta_equipar} en ranura {inv.RANURA_PUESTO} (duracion {dur_s}s)")
                return

            # Caso 1.0b: TARJETAS DE EXPRESION / EMOCION (EMOTE CARDS).
            # Items como 3262 (Wait), 3263 (Follow), 3274 (Cry), 3280 (Love), etc.
            # Categoria '表情卡', con el id de emote en '動態資料1'.
            if inv.es_tarjeta_emocion(item_id):
                emo_id = inv.emote_de_tarjeta(item_id)
                if emo_id is None:
                    emo_id = 0
                emotes_actuales = getattr(ses.personaje, 'emotes', None)
                if emotes_actuales is None:
                    emotes_actuales = set()
                    ses.personaje.emotes = emotes_actuales
                if emo_id in emotes_actuales:
                    ses.enviar(_c.aviso("You have already learned this expression.", tipo=7, msg_id=_c.MSG_TEXTO))
                    return
                _sacar(ses, ranura, 1)
                emotes_actuales.add(emo_id)
                import presencia as _pr_emo
                _pr_emo.notificar_emocion(ses, emo_id)
                nom_item_usado = _nombre_item(item_id)
                salida = [
                    _c.aviso(f"Learned expression: {nom_item_usado}!", tipo=7, msg_id=_c.MSG_TEXTO),
                    _pr_emo.paquete_emotes_desbloqueados(emotes_actuales),
                    *_refrescar(ses, [ranura]),
                ]
                ses.enviar(*salida)
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa, _cantidades(ses))
                    cuentas.guardar_emotes(ses.usuario, cid, emotes_actuales)
                log.info(f"[{addr}] tarjeta de expresion aprendida: item {item_id} -> emote {emo_id} (ranura {ranura})")
                return

            eq_slot = inv.ranura_equipo_de(item_id)
            if eq_slot is not None:
                estado_org = (ses.personaje.mejoras or {}).get(ranura) if ses.personaje else None
                if not inv.puede_equipar(item_id, cid, estado_org):
                    import clases as _clf_e
                    ses.enviar(_clf_e.aviso("Unable to equip the equipment.", tipo=0))
                    return
                _tiene_finesse = any((h[0] if isinstance(h, (list, tuple)) else h) == 16 for h in (getattr(ses.personaje, 'habilidades', None) or []))
                # Si es un arma dual de fashion y 169 ya esta ocupado pero 170 esta libre:
                if eq_slot == 169 and (169 in bolsa) and (170 not in bolsa) and inv.es_arma_dual(item_id):
                    dst = 170
                elif eq_slot == 3 and (3 in bolsa) and (4 not in bolsa) and inv.es_arma_dual(item_id) and _tiene_finesse and inv.es_arma_dual(bolsa[3]):
                    dst = 4
                else:
                    # Los accesorios tienen DOS ranuras, los dos "Trinket" de
                    # la ventana: la 8 y la 9. Se mandaban todos a la 8, asi
                    # que el segundo hueco no aceptaba nada y el jugador no
                    # podia ponerse dos anillos.
                    dst = inv.ranura_libre_equipo(item_id, bolsa) or eq_slot
                # Si se equipa un arma/municion en la 3 o 4 incompatible con la otra mano:
                # Desequipar la otra mano a la bolsa conservando su cantidad
                _extra_tocadas_2e = []
                if dst == 3 and 4 in bolsa and not inv.compatibles_manos(item_id, bolsa[4]):
                    libre = _ranura_libre(bolsa, desde=20)
                    if libre is None:
                        import clases as _clf_e
                        ses.enviar(_clf_e.aviso("Your backpack is full.", tipo=0))
                        return
                    it_lhand = bolsa.pop(4)
                    bolsa[libre] = it_lhand
                    _c_lh2 = _cantidades(ses).pop(4, 1)
                    if _c_lh2 > 1:
                        _cantidades(ses)[libre] = _c_lh2
                    _mover_inst(ses, 4, libre)
                    _extra_tocadas_2e.extend([4, libre])
                    log.info(f"[{addr}] mano derecha incompatible con izquierda: desequipando mano izquierda {it_lhand} -> bolsa {libre}")
                elif dst == 4 and 3 in bolsa and not inv.compatibles_manos(bolsa[3], item_id):
                    libre = _ranura_libre(bolsa, desde=20)
                    if libre is None:
                        import clases as _clf_e
                        ses.enviar(_clf_e.aviso("Your backpack is full.", tipo=0))
                        return
                    it_rhand = bolsa.pop(3)
                    bolsa[libre] = it_rhand
                    _c_rh2 = _cantidades(ses).pop(3, 1)
                    if _c_rh2 > 1:
                        _cantidades(ses)[libre] = _c_rh2
                    _mover_inst(ses, 3, libre)
                    _extra_tocadas_2e.extend([3, libre])
                    log.info(f"[{addr}] mano izquierda incompatible con derecha: desequipando mano derecha {it_rhand} -> bolsa {libre}")

                if dst in bolsa:
                    # Reemplazar equipo actual (swap con lo puesto, conservando cantidades e instancias)
                    it_eq = bolsa[dst]
                    bolsa[ranura] = it_eq
                    bolsa[dst] = item_id
                    _c_org2 = _cant_de(ses, ranura)
                    _c_dst2 = _cant_de(ses, dst)
                    if _c_dst2 > 1:
                        _cantidades(ses)[ranura] = _c_dst2
                    else:
                        _cantidades(ses).pop(ranura, None)
                    if _c_org2 > 1:
                        _cantidades(ses)[dst] = _c_org2
                    else:
                        _cantidades(ses).pop(dst, None)
                    _mover_inst(ses, ranura, 0xFFFF)
                    _mover_inst(ses, dst, ranura)
                    _mover_inst(ses, 0xFFFF, dst)
                    log.info(f"[{addr}] reemplazar equipo: item {item_id} -> {dst}, sacando {it_eq} -> {ranura}")
                else:
                    it = bolsa.pop(ranura)
                    bolsa[dst] = it
                    _c_eq = _cantidades(ses).pop(ranura, 1)
                    if _c_eq > 1:
                        _cantidades(ses)[dst] = _c_eq
                    _mover_inst(ses, ranura, dst)
                    log.info(f"[{addr}] equipar directo: item {it} -> ranura {dst}")

                # Sin acuse: en la captura el 0x002E (usar) no recibe
                # ninguno, solo el 0x0012 de arrastrar.
                salida = list(_refrescar(ses, [ranura, dst] + _extra_tocadas_2e))
                salida.append(_stats_ses(ses))
                salida.extend(_apariencia(ses))
                if ses.personaje:
                    import combate as _cb
                    _max_h = _vida_max(ses.personaje, bolsa=bolsa)
                    if ses.personaje.hp > _max_h:
                        ses.personaje.hp = _max_h
                    _max_m = _mana_max(ses.personaje, bolsa=bolsa)
                    if ses.personaje.mp > _max_m:
                        ses.personaje.mp = _max_m
                    salida.append(_cb.atributo(ses.personaje.entity_id, ses.personaje.hp, _cb.KIND_HP))
                    salida.append(_cb.atributo(ses.personaje.entity_id, ses.personaje.mp, _cb.KIND_MP))

                ses.enviar(*salida)
                import presencia as _pr
                _pr.notificar_equipo(ses)
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa,
                                   _cantidades(ses))
                return

            # Caso 2: Comida de mascota (Pet Cookies, Pet Can, Pet Feed) - Solo si hay mascota activa
            if inv.es_comida_mascota(item_id) and (9 in bolsa):
                _sacar(ses, ranura, 1)
                salida = [
                    _c.aviso("Fed pet! Hunger satiated (up to 500/100 buffer).", tipo=7, msg_id=_c.MSG_TEXTO),
                    *_refrescar(ses, [ranura]),
                ]
                ses.enviar(*salida)
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa,
                                   _cantidades(ses))
                log.info(f"[{addr}] comida de mascota usada: {item_id} (ranura {ranura})")
                return

            # Caso 3: Cajas de regalo / Growth Boxes (drop_table)
            recompensas = inv.recompensas_caja(item_id)
            if recompensas:
                # Se gasta UNA caja, no la pila entera, y lo que sale se
                # apila con lo que ya hubiera.
                _sacar(ses, ranura, 1)
                log.info(f"[{addr}] abriendo caja {item_id} de ranura {ranura}: "
                         f"{len(recompensas)} tipos de items")
                salida = []
                tocadas = [ranura]
                for rew_id, cant in recompensas:
                    tocadas.append(_meter(ses, rew_id, max(1, int(cant))))
                    salida.append(_c.aviso(_nombre_item(rew_id), tipo=0, msg_id=_c.MSG_ITEM))
                salida.extend(_refrescar(ses, tocadas))
                ses.enviar(*salida)
                if ses.personaje and getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa,
                                   _cantidades(ses))
                return

            # Caso 4: Pergaminos de habilidad / Libros de hechizo (Scrolls)
            try:
                scroll_info = _c.info_pergamino(item_id)
            except Exception:
                scroll_info = None

            if scroll_info and ses.personaje:
                req_skills = scroll_info.get('req_skills') or ([scroll_info['req_skill']] if scroll_info.get('req_skill') else [])
                req_lv = scroll_info.get('req_level', 1)
                mid = scroll_info.get('magic_id')
                mnombre = scroll_info.get('magic_name', 'Spell')
                mlv = scroll_info.get('magic_level', 1)

                # Verificar si el personaje tiene alguna de las ramas requeridas (equipadas o en banco)
                habs_pj = list(ses.personaje.habilidades or [])
                banco = getattr(ses.personaje, 'banco_habilidades', {}) or {}
                for bh_id, bh_val in banco.items():
                    bh_lv = bh_val[0] if isinstance(bh_val, (list, tuple)) else bh_val
                    habs_pj.append((int(bh_id), int(bh_lv), 0))

                hab_encontrada = None
                if req_skills:
                    for h in habs_pj:
                        hid = h[0] if isinstance(h, (list, tuple)) else h
                        hlv = h[1] if isinstance(h, (list, tuple)) and len(h) > 1 else 1
                        if hid in req_skills:
                            if hlv >= req_lv or ses.personaje.nivel >= req_lv:
                                hab_encontrada = h
                                break
                            elif hab_encontrada is None:
                                hab_encontrada = False
                else:
                    hab_encontrada = True

                if hab_encontrada is None:
                    nombres_req = [_c.nombre_de_rama(s) for s in req_skills]
                    ses.enviar(_c.aviso(f"You must learn/equip {', '.join(nombres_req[:3])} to learn this.", tipo=7, msg_id=_c.MSG_TEXTO))
                    return

                if hab_encontrada is False:
                    ses.enviar(_c.aviso(f"Skill Lv {req_lv} required to learn {mnombre}.", tipo=7, msg_id=_c.MSG_TEXTO))
                    return

                # Si ya lo conoce
                if not hasattr(ses.personaje, 'hechizos_aprendidos') or ses.personaje.hechizos_aprendidos is None:
                    ses.personaje.hechizos_aprendidos = set()
                if mid in ses.personaje.hechizos_aprendidos:
                    ses.enviar(
                        _c.aviso(f"You have already learned {mnombre}.", tipo=7, msg_id=_c.MSG_TEXTO),
                        struct.pack('<HIB', 0x001D, ses.personaje.entity_id, 1) + struct.pack('<BII', _c.KIND_HECHIZO, mid, mlv)
                    )
                    return

                # Consumir 1 pergamino
                _sacar(ses, ranura, 1)
                yo = ses.personaje.entity_id

                salida = [
                    struct.pack('<HIB', 0x001D, yo, 1) + struct.pack('<BII', _c.KIND_HECHIZO, mid, mlv),
                    _c.aviso(mnombre, tipo=7, msg_id=_c.MSG_HECHIZO),
                    *_refrescar(ses, [ranura])
                ]
                ses.enviar(*salida)
                ses.personaje.hechizos_aprendidos.add(mid)

                if getattr(ses, 'usuario', None):
                    cuentas.guardar_hechizos(ses.usuario, cid, list(ses.personaje.hechizos_aprendidos))
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa, _cantidades(ses))
                log.info(f"[{addr}] pergamino usado: {item_id} -> aprendio {mid} ({mnombre} Lv {mlv})")
                return

            # Caso 4.5: Ring of Angel Wings (Item 1905) - Regresa al checkpoint de Cupido
            if item_id == 1905 and ses.personaje:
                _sacar(ses, ranura, 1)
                _pj = ses.personaje
                dst = getattr(_pj, 'checkpoint_stage', None) or _pj.stage
                cx = getattr(_pj, 'checkpoint_x', None) or _pj.tile_x
                cy = getattr(_pj, 'checkpoint_y', None) or _pj.tile_y
                lleg = [cx, cy]
                yo = _pj.entity_id
                salida = [struct.pack('<H', 0x0012) + bytes(7)]
                salida += list(_refrescar(ses, [ranura]))
                salida.append(_stats_ses(ses))
                _pj.tile_x, _pj.tile_y = lleg
                import clases as _cgo
                if dst == _pj.stage:
                    salida.append(struct.pack('<HIII', 0x0003, yo, lleg[0], lleg[1]))
                    ses.enviar(*salida)
                else:
                    salida.append(struct.pack('<HIB', 0x0007, yo, 1))
                    _pj.stage = dst
                    ses.monstruos = _monstruos_de(dst)
                    ses.mapa_cambiado_en = time.time()
                    salida.append(_cgo.cambiar_mapa(dst))
                    ses.enviar(*salida)
                cid = _pj.char_id
                _guardar_bolsa(ses, cid)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_mapa(ses.usuario, cid, dst, *lleg)
                log.info(f"[{addr}] Ring of Angel Wings usado: teletransporte al checkpoint stage {dst} tile {lleg}")
                return

            # Caso 4.9: OBJETOS QUE BUFEAN. VA ANTES QUE LOS CONSUMIBLES, y
            # no es un detalle: efecto_consumible() lee el hp y el mp de la
            # fila de magia y los toma por una pocion, asi que la Kyrio Angel
            # Magic Stone "curaba" 12000 de vida, se gastaba y no bufeaba
            # nada. El hp de esa fila no es una cura: es +12000 al MAXIMO. El buff esta en la columna
            # 常駐法術 del item, que es un id de magic, y datos_magia() ya
            # parsea esa fila entera. Son 9.349 items. Se reusa la
            # maquinaria de buffs que ya tienen los hechizos: el mismo
            # diccionario personaje.buffs, los mismos paquetes de efecto y
            # el mismo temporizador de expiracion.
            import bolsas as _bol0
            _bf = _bol0.buff_de(item_id, time.time()) if ses.personaje else None
            if _bf:
                import combate as _cb
                _mid_buff, _entrada, _dur = _bf
                if True:
                    _yo = ses.personaje.entity_id
                    _ef = _entrada['mag'].get('efecto', 0)
                    # (el 'if True' es para no reindentar el bloque entero)
                    # 使用不扣 ("usar sin descontar"): hay 2.069 objetos que
                    # NO desaparecen al usarlos, y la piedra es uno. Se usa,
                    # se queda en la mochila y se vuelve a usar cuando se
                    # acaba el buff. Gastarla le borraba el objeto al jugador.
                    if _bol0.se_gasta(item_id):
                        _sacar(ses, ranura, 1)
                    ses.personaje.buffs[_mid_buff] = _entrada
                    # EL ICONO DE ABAJO es el 0x001D de kind 4, con el id
                    # del hechizo y los milisegundos que dura. Sin el, el
                    # buff se aplicaba de verdad -- los stats subian -- pero
                    # el jugador solo veia la animacion y nada mas, sin
                    # forma de saber cuanto le quedaba. Esta documentado en
                    # combate.py: "s2c 0x001D kind 4, duracion 600494 ms".
                    # LA SECUENCIA ENTERA, en el orden de la captura que
                    # documenta combate.py: el efecto visual, luego el
                    # 0x001D de kind 3 con el enfriamiento y luego el de
                    # kind 4 con la duracion. Al principio solo se mandaba
                    # el kind 4 y el icono salia pero SIN cuenta atras.
                    _cd = int(_entrada['mag'].get('cd_ms') or 0)
                    _sal = []
                    if _cd > 0:
                        _sal.append(struct.pack('<HIBBII', 0x001D, _yo, 1, 3,
                                                _mid_buff, _cd))
                        asyncio.get_event_loop().call_later(
                            _cd / 1000.0,
                            lambda b=_mid_buff: ses.enviar_inmediato(
                                struct.pack('<HIBBII', 0x001D,
                                            ses.personaje.entity_id,
                                            1, 3, b, 0)))
                    _sal.append(struct.pack('<HIBBII', 0x001D, _yo, 1, 4,
                                            _mid_buff, _dur))
                    # Y la vida y el mana al tope nuevo, como hace el hechizo
                    # cuando el buff sube los maximos: si no, se queda con la
                    # barra a medias sobre un maximo mas grande.
                    if _entrada.get('hp_bonus'):
                        ses.personaje.hp = _vida_max(ses.personaje,
                                                     ses.inventario)
                        _sal.append(_cb.atributo(_yo, ses.personaje.hp,
                                                 _cb.KIND_HP))
                    if _entrada.get('mp_bonus'):
                        ses.personaje.mp = _mana_max(ses.personaje,
                                                     ses.inventario)
                        _sal.append(_cb.atributo(_yo, ses.personaje.mp,
                                                 _cb.KIND_MP))
                    _sal.extend(_refrescar(ses, [ranura]))
                    _sal.append(_stats_ses(ses))
                    ses.enviar(*_sal)

                    def _fin_buff_item(bid=_mid_buff, fin=_entrada['fin']):
                        p2 = getattr(ses, 'personaje', None)
                        if p2 is None:
                            return
                        b2 = (p2.buffs or {}).get(bid)
                        if not b2 or b2.get('fin', 0) > fin + 0.5:
                            return      # se renovo: este temporizador no vale
                        p2.buffs.pop(bid, None)
                        try:
                            # apagar el icono: el mismo 0x001D con 0 ms
                            ses.enviar_inmediato(
                                struct.pack('<HIBBII', 0x001D,
                                            p2.entity_id, 1, 4, bid, 0),
                                _stats_ses(ses))
                        except Exception:
                            pass
                    if _dur > 0:
                        asyncio.get_event_loop().call_later(
                            _dur / 1000.0, _fin_buff_item)
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_inventario(ses.usuario, cid, bolsa,
                                                   _cantidades(ses))
                    log.info('[%s] %s da el buff %s durante %ds',
                             addr, item_id, _mid_buff, _dur // 1000)
                    return

            # Caso 5: Consumibles (Pociones HP/MP, Hierba Magica 1228, Biscuits 2, etc.)
            ef_con = inv.efecto_consumible(item_id)
            if ef_con and ses.personaje:
                # Una unidad del monton. Antes se borraba la casilla entera:
                # con una sola galleta daba igual, pero con una pila de diez
                # desaparecian las diez de un mordisco.
                _sacar(ses, ranura, 1)
                salida = []
                yo = ses.personaje.entity_id
                import combate as _cb
                bolsa_p = getattr(ses, 'inventario', None)
                if 'hp' in ef_con:
                    curado = ef_con['hp']
                    ses.personaje.hp = min(_vida_max(ses.personaje, bolsa=bolsa_p), ses.personaje.hp + curado)
                    salida.append(_cb.atributo(yo, ses.personaje.hp, _cb.KIND_HP))
                    salida.append(_cb.numero_flotante(yo, curado, tipo=_cb.TIPO_CURA_HP))
                if 'mp' in ef_con:
                    rec_mp = ef_con['mp']
                    ses.personaje.mp = min(_mana_max(ses.personaje, bolsa=bolsa_p), ses.personaje.mp + rec_mp)
                    salida.append(_cb.atributo(yo, ses.personaje.mp, _cb.KIND_MP))
                    salida.append(_cb.numero_flotante(yo, rec_mp, tipo=_cb.TIPO_CURA_MP))
                salida.extend(_refrescar(ses, [ranura]))
                # Y los stats, que es lo que refresca las barras del panel.
                salida.append(_stats_ses(ses))
                ses.enviar(*salida)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_progreso(ses.usuario, cid, ses.personaje.nivel, ses.personaje.exp,
                                             ses.personaje.hp, ses.personaje.mp,
                                             hp_max=ses.personaje.hp_max, mp_max=ses.personaje.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa,
                                   _cantidades(ses))
                log.info(f"[{addr}] consumible usado: {item_id} (ranura {ranura}) -> {ef_con}")
                return

            # Caso 5b: BOLSAS DE LA SUERTE, HUEVOS Y REGALOS.
            # Son 22.055 items entre las categorias 紅包 y 禮物 y hasta
            # ahora no hacian nada al usarlos. Lo que sale esta en la
            # columna 動態資料1 del propio item: o apunta a una fila de
            # drop_table y se sortea con sus pesos, o apunta a un item
            # suelto y se da ese. Ver server/bolsas.py.
            import bolsas as _bol
            if _bol.es_bolsa(item_id):
                premio = _bol.abrir(item_id)
                if not premio:
                    # Tabla vacia: NO se gasta la bolsa. Mas vale que se la
                    # quede a que la pierda a cambio de nada.
                    ses.enviar(_c.aviso('Nothing inside.', tipo=7,
                                        msg_id=_c.MSG_TEXTO))
                    log.warning('[%s] la bolsa %s no tiene nada que dar',
                                addr, item_id)
                    return
                premio_id, premio_n = premio
                _sacar(ses, ranura, 1)
                destino = _meter(ses, premio_id, premio_n)
                nom_premio = _nombre_item(premio_id)
                tocadas = [ranura] + ([destino] if destino is not None else [])
                salida = [_c.aviso('You got %s x%d!' % (nom_premio, premio_n),
                                   tipo=7, msg_id=_c.MSG_TEXTO)]
                salida.extend(_refrescar(ses, tocadas))
                ses.enviar(*salida)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa,
                                               _cantidades(ses))
                log.info('[%s] bolsa %s abierta -> %s x%d (%s)',
                         addr, item_id, premio_id, premio_n, nom_premio)
                return

            # Caso 6: genuine Card Book cards. Validation and consumption
            # must commit together; an English name containing Card is not
            # sufficient to consume an item (EXP cards are other systems).
            import cartas as _cartas
            if ses.personaje and not objetivo and _cartas.registrar(
                    ses, ranura, _sacar, _refrescar):
                return

            # Caso 7: Advancement Stone (subir nivel del personaje instantaneamente)
            target_lv = inv.es_advancement_stone(item_id)
            if target_lv and ses.personaje:
                p = ses.personaje
                yo = p.entity_id
                import combate as _cb, clases as _cl
                if p.nivel >= target_lv:
                    ses.enviar(_cl.aviso(f"Your level ({p.nivel}) is already at or above Level {target_lv}.", tipo=7, msg_id=_cl.MSG_TEXTO))
                    return
                _sacar(ses, ranura, 1)
                p.nivel = target_lv
                p.exp = _cb.exp_para_nivel(p.nivel)
                p.hp_max = max(p.hp_max, 500 + p.nivel * 25)
                p.mp_max = max(p.mp_max, 300 + p.nivel * 15)
                p.hp = _vida_max(p)
                p.mp = _mana_max(p)
                exp_actual_ui, exp_sig = _cb.exp_para_barra(p.nivel, p.exp)
                _u64 = lambda v: max(0, min(int(v or 0), 0xFFFFFFFFFFFFFFFF))

                salida = [
                    _cl.aviso(f"Level Up! Advanced to Level {p.nivel}!", tipo=7, msg_id=_cl.MSG_TEXTO),
                    _cb.atributo(yo, p.hp, _cb.KIND_HP),
                    _cb.atributo(yo, p.mp, _cb.KIND_MP),
                    struct.pack('<HIB', 0x001D, yo, 4) +
                    struct.pack('<BQ', 29, _u64(p.nivel)) +
                    struct.pack('<BQ', 30, max(0, int(_cb.exp_para_nivel(p.nivel)))) +
                    struct.pack('<BQ', 31, _u64(exp_sig)) +
                    struct.pack('<BQ', 32, _u64(exp_actual_ui)),
                    _cb.efecto_level_up(yo, es_skill=False),
                    *_refrescar(ses, [ranura]),
                    _stats_ses(ses)
                ]
                ses.enviar(*salida)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_progreso(ses.usuario, cid, p.nivel, p.exp,
                                             p.hp, p.mp, p.habilidades,
                                             hp_max=p.hp_max, mp_max=p.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa, _cantidades(ses))
                log.info(f"[{addr}] {p.nombre} uso Advancement Stone {item_id} -> SUBIO A NIVEL {p.nivel}!")
                return

            # Caso 8: Skill Leveling Stone (subir todas las habilidades a X nivel)
            target_sk_lv = inv.es_skill_leveling_stone(item_id)
            if target_sk_lv and ses.personaje:
                p = ses.personaje
                yo = p.entity_id
                import clases as _cl
                _sacar(ses, ranura, 1)
                nuevas_habs = []
                for h in (p.habilidades or []):
                    sid = h[0] if isinstance(h, (list, tuple)) else h
                    slv = h[1] if isinstance(h, (list, tuple)) and len(h) > 1 else 1
                    nuevo_slv = max(slv, target_sk_lv)
                    nuevas_habs.append((sid, nuevo_slv, 0))
                p.habilidades = nuevas_habs

                if hasattr(p, 'banco_habilidades') and p.banco_habilidades:
                    for bh_id, bh_val in list(p.banco_habilidades.items()):
                        bh_lv = bh_val[0] if isinstance(bh_val, (list, tuple)) else bh_val
                        p.banco_habilidades[bh_id] = (max(bh_lv, target_sk_lv), 0)

                salida = [
                    _cl.aviso(f"All skills raised to Level {target_sk_lv}!", tipo=7, msg_id=_cl.MSG_TEXTO),
                    _cl.arbol(p.habilidades, banco=getattr(p, 'banco_habilidades', None)),
                ]
                _ids = [h[0] for h in p.habilidades]
                _hech = _cl.hechizos_iniciales(_ids)
                _todos_hech = [n for n, _ in _hech]
                if getattr(p, 'hechizos_aprendidos', None):
                    _todos_hech = sorted(set(_todos_hech) | set(p.hechizos_aprendidos))
                if _todos_hech:
                    salida.extend(_cl.otorgar_hechizos(yo, _todos_hech))
                for h in p.habilidades:
                    salida.append(struct.pack('<HIBBII', 0x001D, yo, 1, 53, h[0], 0))
                salida.extend(_refrescar(ses, [ranura]))
                salida.append(_stats_ses(ses))
                ses.enviar(*salida)

                if getattr(ses, 'usuario', None):
                    cuentas.guardar_progreso(ses.usuario, cid, p.nivel, p.exp,
                                             p.hp, p.mp, p.habilidades,
                                             hp_max=p.hp_max, mp_max=p.mp_max, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)
                    cuentas.guardar_inventario(ses.usuario, cid, bolsa, _cantidades(ses))
                log.info(f"[{addr}] {p.nombre} uso Skill Leveling Stone {item_id} -> HABILIDADES SUBIDAS A NIVEL {target_sk_lv}!")
                return

            log.info(f"[{addr}] usar item {item_id} (ranura {ranura}): sin accion")
            return

        # --- escena / mapa de radar (Scene Map) -------------------------
        # 0x012D C2S: el cliente abre la ventana de mini-mapa/escena.
        # El servidor responde con una cabecera 0x0062 (entidad de zona) y
        # luego entradas 0x0061 para cada NPC/entidad de interes, terminando
        # con un 0x0061 de un solo byte 0x00.
        if opcode == 0x012D and ses.rol == 'mundo':
            # Usar un entity_id de zona generico basado en el stage del jugador
            stage_z = getattr(ses.personaje, 'stage', 41) if ses.personaje else 41
            zona_eid = 0x000F3000 + stage_z  # entidad de zona ficticia por mapa
            ses.enviar(struct.pack('<HI', 0x0062, zona_eid),
                       struct.pack('<HB', 0x0061, 0x00))
            log.debug(f"[{addr}] escena (0x012D) respondida para stage {stage_z}")
            return

        # 0x012B C2S: radar de NPCs cercanos (5 bytes: 02 00 00 00 00).
        # El servidor responde con 0x0062 + lista de entidades 0x0061 + 0x00.
        # Cada entrada 0x0061 tiene: [U8 kind=1][LE32 eid][LE32 v1][LE32 v2][24 bytes cero]
        if opcode == 0x012B and ses.rol == 'mundo':
            stage_z = getattr(ses.personaje, 'stage', 41) if ses.personaje else 41
            zona_eid = 0x000F3000 + stage_z
            pkgs_radar = [struct.pack('<HI', 0x0062, zona_eid)]
            # Agregar al jugador como entidad del radar
            if ses.personaje:
                yo = ses.personaje.entity_id
                radar_entry = (
                    struct.pack('<H', 0x0061) +
                    struct.pack('<B', 0x01) +  # kind=1 (jugador)
                    struct.pack('<I', yo) +
                    struct.pack('<I', ses.personaje.nivel) +
                    struct.pack('<I', 100) +  # HP%
                    b'\x00' * 24
                )
                pkgs_radar.append(radar_entry)
            # Terminador
            pkgs_radar.append(struct.pack('<HB', 0x0061, 0x00))
            ses.enviar(*pkgs_radar)
            log.debug(f"[{addr}] radar (0x012B) respondido para stage {stage_z}")
            return

        # --- salida de Training Area A -------------------------------
        if (opcode == 0x000D and ses.rol == 'mundo' and ses.personaje
                and ses.personaje.stage == 118 and len(cuerpo) == 9
            and struct.unpack_from('<I', cuerpo, 0)[0] == ses.personaje.entity_id
            and cuerpo[4:] == EVENTO_SALIDA_ENTRENAMIENTO_A):
            _st_retorno, _tile_retorno, _nombre_retorno = RETORNO_ENTRENAMIENTO
            _cerrar_viaje(ses, addr, _st_retorno, _tile_retorno, _nombre_retorno)
            return

        # --- dialogo con los NPC -------------------------------------
        # Secuencia establecida con una captura con marca de tiempo:
        #   0x0005 [LE32 entity] clic   ->  0x0012 primera linea
        #   0x000B [01] siguiente       ->  0x0012 linea siguiente
        #   ... y al terminar, un 0x0012 de nueve ceros que cierra el cuadro.
        if opcode == 0x0005 and ses.rol == 'mundo' and len(cuerpo) >= 4:
            import dialogos
            ent = struct.unpack_from('<I', cuerpo, 0)[0]
            if _casa_click(ses, ent):
                return
            if (ses.personaje
                    and ses.personaje.stage in ETAPAS_ENTRENAMIENTO
                    and ent == ENTIDAD_SALIDA_ENTRENAMIENTO_B):
                _st_retorno, _tile_retorno, _nombre_retorno = RETORNO_ENTRENAMIENTO
                _cerrar_viaje(ses, addr, _st_retorno, _tile_retorno,
                              _nombre_retorno)
                return
            # ESTATUA QUE TELETRANSPORTA. Va lo primero porque no es un NPC ni
            # un monstruo: es un objeto de mapa, y el resto del manejador ni
            # lo reconoceria.
            if ses.personaje:
                _est = _estatua_con_entidad(ses.personaje.stage, ent)
                if _est is not None:
                    ses.dlg_estatua = _est
                    ses.dlg_ent = None
                    ses.enviar(_dialogo_de_estatua(_est))
                    log.info(f"[{addr}] estatua {ent}: se ofrece el salto a "
                             f"{_est.get('llegada')}")
                    return

                # OBJETO DE MISION QUE SE PULSA: la estela, la tumba, el nido...
                # Es un objeto de mapa con su evento, y el evento dice que pasa
                # (dar la mision, avanzarla, mostrar un dialogo, llevarte a
                # otro mapa). El servidor ya los mandaba -- 81 de los 83 de
                # mision --, pero al pulsarlos solo miraba si eran NPC o
                # portal, asi que no pasaba nada.
                _tile_obj = _recurso_con_entidad(ses.personaje.stage, ent)
                # VETA (objeto MATOBJ con su material de material.xml). No se
                # pide la casilla: las vetas de los mapas abiertos vienen de
                # capturas y en la plantilla solo traen el px.
                if ses.personaje.stage == 500:
                    import house_services as _hs_gather
                    if ent in _hs_gather.RESOURCES:
                        _c_gather = _casa_actual(ses)
                        if (_c_gather.owner_id != ses.personaje.char_id
                                or not _c_gather.cleanliness or _c_gather.level < 2
                                or getattr(ses, 'house_furnishing', False)):
                            ses.enviar(dialogos.armar_linea(7871, 0, []))
                            return
                if _recolectar(ses, addr, ses.personaje.stage, ent):
                    return
                if _tile_obj is not None:
                    try:
                        import eventos_mundo as _evm_p
                        _ef_obj = _evm_p.al_pulsar(ses, _tile_obj)
                        if _portal_en(ses.personaje.stage, *_tile_obj):
                            _ef_obj = [e for e in _ef_obj if e[0] not in ('viajar', 'ir_a_tag')]
                        if _ef_obj:
                            _aplicar_efectos(ses, addr, _ef_obj, ' al pulsar el objeto %s' % ent)
                            return
                    except Exception:
                        log.exception('evento del objeto pulsado')

                # PORTAL / TORNADO QUE TELETRANSPORTA (objeto de mapa, clic directo)
                stg = str(ses.personaje.stage)
                cfg_p = _portales()
                portal_match = None
                for por in cfg_p.get('mapas', {}).get(stg, []):
                    if por.get('entity') == ent:
                        portal_match = por
                        break
                if not portal_match:
                    for s_k, plist in cfg_p.get('mapas', {}).items():
                        for por in plist:
                            if por.get('entity') == ent:
                                portal_match = por
                                break
                        if portal_match:
                            break
                if portal_match:
                    if ses.personaje.stage == 500 and (portal_match.get('entity') == 701 or ent == 701):
                        c_vis = _casa_actual(ses)
                        if c_vis and c_vis.owner_id != ses.personaje.char_id:
                            _salir_de_casa(ses, addr)
                            return
                    if portal_match.get('destino') is None and not portal_match.get('preguntar'):
                        log.debug(f"[{addr}] clic en tornado {ent}: sin destino, no viaja")
                        return
                    if portal_match.get('preguntar'):
                        import dialogos as _dlg
                        _ops = portal_match.get('opciones') or cfg_p['opciones']
                        sub = _dlg.armar_linea(portal_match.get('msg') or cfg_p['msg'], 0, _ops,
                                               acciones=portal_match.get('acciones'))
                        ses.dlg_ent = ent
                        ses.dlg_guion = [sub[2:]]
                        ses.dlg_paso = 1
                        ses.dlg_val = 0
                        ses.dlg_portal = portal_match
                        ses.enviar(sub)
                        log.info(f"[{addr}] clic en tornado {ent}: abriendo menu de portal")
                        return
                    else:
                        _viajar_por_portal(ses, addr, portal_match, f"(clic en tornado {ent})")
                        return
            # Si ya se cumplio lo que pedia el tramo actual, se avanza ANTES
            # de hablar: en el juego, en cuanto llevas el examen encima
            # Raphael te suelta el "Good for you!" y no repite lo anterior.
            if ses.personaje and ses.personaje.stage == MAPA_DEL_TUTORIAL and ent in dialogos.NOMBRE_POR_ENTIDAD:
                import clases as _c
                _sig = ses.personaje.tutorial + 1
                _req = _c.REQUISITO_ETAPA.get(_sig)
                if (_req and _sig < dialogos.etapas(ent)
                        and _req in (getattr(ses, 'inventario', {}) or {}).values()):
                    ses.personaje.tutorial = _sig
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_tutorial(ses.usuario,
                                                 ses.personaje.char_id, _sig)
                    log.info(f"[{addr}] tutorial: cumplido el requisito, "
                             f"pasa a la etapa {_sig}")
            # Clic en un MONSTRUO: hay que contestar con su vida. Eso es lo
            # que hace el servidor real y lo que le dice al cliente que ese
            # objetivo se puede atacar; sin la respuesta el cliente ni siquiera
            # llega a mandar el 0x0006 y parecia que "no deja atacar".
            import combate as _cb0
            _m = (getattr(ses, 'monstruos', None) or {}).get(ent)
            if _m is not None:
                if _intentar_captura_monstruo(ses, ent, addr):
                    return
                # El clic sobre un monstruo ES el ataque basico: el cliente no
                # manda ningun 0x0006 para pegar sin habilidad. Medido en
                # mundo_154337_948959, t=3.08:
                #   C2S 0x0005 [target][00 00]
                #   S2C 0x0013 [monstruo] vida actual
                #   S2C 0x000A [yo][monstruo] tipo=3 anim=1480
                #   S2C 0x0013 + 0x000B con el numero
                # Antes se contestaba fijando el objetivo y se esperaba un
                # 0x0006 que nunca llegaba, asi que el golpe basico no existia.
                # El clic SOLO selecciona: se contesta con la vida del
                # monstruo y nada mas. El golpe lo pide el cliente aparte,
                # con el 0x0016 accion 0x0c, y lo repite solo cada ~1,5 s.
                # Atacar tambien aqui hacia que cada clic disparara DOS
                # golpes con 15 ms de diferencia, y por eso el personaje
                # pegaba al doble de velocidad.
                # Objetivo nuevo: se limpia el cooldown para que el primer
                # golpe salga enseguida. Si no, el clic cae dentro de la
                # cadencia del objetivo anterior y el personaje "lo piensa"
                # antes de empezar a pegar.
                if getattr(ses, 'objetivo_actual', None) != ent:
                    ses.objetivo_actual = ent
                if not getattr(_m, 'encantado', False):
                    if getattr(ses, 'invocacion', None):
                        ses.invocacion['objetivo'] = _m
                    if getattr(ses, 'monstruo_encantado', None) and getattr(ses.monstruo_encantado, 'vivo', False):
                        ses.monstruo_encantado.charmed_objetivo = _m
                ses.enviar(_cb0.atributo(ent, _m.porcentaje if getattr(_m, 'vivo', False) else 0))
                # El clic sobre un monstruo vivo ataca con golpe basico respetando alcance y cadencia.
                # Como ultimo_golpe NO se resetea a 0, si este clic llega junto a un 0x0016
                # la cadencia de _atacar descarta el segundo sin duplicar golpes.
                if getattr(_m, 'vivo', False) and not getattr(_m, 'encantado', False) and not getattr(ses, 'muerto', False) and getattr(ses, 'personaje', None):
                    self.manejar(ses, 0x0006, m, d, addr,
                                 struct.pack('<HI', _cb0.ATAQUE_NORMAL, ent))
                return



            # Los dialogos del tutorial van por entity_id (19 Raphael, 20
            # Interface Tutor, 21 Angel Aide) y esos numeros SE REPITEN en
            # otros mapas: en el Lyceum la 19 es el Magic Seller, la 20 el Bao
            # Clerk y la 21 Michael, y les salia el dialogo del tutorial. Solo
            # valen en Guide Palace.
            # En Fighting Palace (stage 57):
            if ses.personaje and ses.personaje.stage == 57:
                # Por NOMBRE: los entity_id los asigna poblar() y ya no son
                # el 500 fijo de antes.
                _nom_ent = _nombre_entidad(ses, ent)
                if _nom_ent == 'Angel Raphael':
                    kills = getattr(ses, 'slarm_kills', 0)
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    g_fp = dialogos.guion_fighting_palace(kills, nom)
                    ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g_fp, 0
                    ses.dlg_val = 5
                    ses.enviar(dialogos.linea_de(g_fp, 0, nom))
                    ses.dlg_paso = 1
                    log.info(f"[{addr}] Angel Raphael (Fighting Palace, kills={kills}): linea 1 de {len(g_fp)}")
                    return
                # Totems de facciones en Fighting Palace:
                totems_fp = {'Iron Totem': 5138, 'Dark City Totem': 5137,
                             'Aurora Totem': 5136, 'Breeze Totem': 5139}
                if _nom_ent in totems_fp:
                    sub_totem = dialogos.armar_linea(totems_fp[_nom_ent], 4, [])
                    ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, [sub_totem[2:]], 1
                    ses.dlg_val = 4
                    ses.enviar(sub_totem)
                    log.info(f"[{addr}] Totem {_nom_ent} ({ent}) en Fighting Palace")
                    return
                log.debug(f"[{addr}] clic en la entidad {ent} en stage 57: sin dialogo")
                return

            if ses.personaje and ses.personaje.stage != MAPA_DEL_TUTORIAL:
                # Fuera del tutorial, cada NPC tiene su propia linea, sacada
                # de msg.xml por su nombre.
                faccion = ses.personaje.faction if ses.personaje else "Heaven"
                import misiones as _mis
                _st_ent = _mis.stage_de_entidad(ent) or None
                if not _st_ent:
                    if 121600 <= ent <= 121699: _st_ent = 3     # Aurora City
                    elif 121700 <= ent <= 121725: _st_ent = 5   # Cherry Village
                    elif 121765 <= ent <= 121775: _st_ent = 15  # Mysterious Wetland
                    elif 121799 <= ent <= 121811: _st_ent = 21  # Dragon Graveyard
                    elif 121812 <= ent <= 121832: _st_ent = 22  # Mysterious Garden
                    elif 121833 <= ent <= 121849: _st_ent = 23  # Dense Forest
                    elif 121850 <= ent <= 121919: _st_ent = 26  # Dark City
                    elif 121920 <= ent <= 121999: _st_ent = 29  # Breeze Woods
                    elif 122040 <= ent <= 122063: _st_ent = 35  # Memory Cave
                    elif 122064 <= ent <= 122085: _st_ent = 36  # Gebuer Vale
                    elif 122086 <= ent <= 122199: _st_ent = 38  # Iron Castle
                    elif 122295 <= ent <= 122305: _st_ent = 69  # Lava Cave
                    elif 122306 <= ent <= 122315: _st_ent = 70  # Flaming Door
                    elif 122355 <= ent <= 122404 or (30080 <= ent <= 30083): _st_ent = 88  # Palm Base
                    elif 122408 <= ent <= 122415 or (30112 <= ent <= 30115): _st_ent = 90  # Blue Ocean
                    elif 122460 <= ent <= 122495 or (30336 <= ent <= 30339): _st_ent = 104  # Waterfall Camp
                    elif 122585 <= ent <= 122610 or (30608 <= ent <= 30611): _st_ent = 121  # Desert Racetrack
                    elif 122730 <= ent <= 122760 or (31008 <= ent <= 31011): _st_ent = 146  # Airship Station
                    elif 122761 <= ent <= 122789: _st_ent = 151  # Mushroom Village
                    elif 122790 <= ent <= 122799: _st_ent = 152  # Building Blocks County
                    elif 122800 <= ent <= 122820 or (31120 <= ent <= 31123): _st_ent = 153  # Building Blocks City
                    elif 122890 <= ent <= 122925 or (31280 <= ent <= 31283): _st_ent = 163  # Hoca Village
                    elif 123000 <= ent <= 123030 or (31392 <= ent <= 31395): _st_ent = 170  # Pharaoh Village
                    else: _st_ent = None

                if _st_ent and ses.personaje and (not getattr(ses.personaje, 'stage', 0) or ses.personaje.stage != _st_ent):
                    ses.personaje.stage = _st_ent

                _nom_ent = _nombre_entidad(ses, ent) or ''
                if not _nom_ent:
                    log.debug(f"[{addr}] clic en entidad {ent} sin nombre registrado")
                    return

                g_quest = None
                if ses.personaje:
                    proc, tipo_proc, datos_proc = _mis.interactuar_npc(ses, _nom_ent, entidad=ent)
                    if proc:
                        if tipo_proc in ('completada', 'avanzada'):
                            qid_proc = datos_proc.get('qid')
                            paso_proc = datos_proc.get('paso') or datos_proc.get('nuevo_paso', 1)
                            nom2 = ses.personaje.nombre if ses.personaje else 'Jugador'
                            g_mis = dialogos.guion_de_mision(
                                qid_proc, _nom_ent, jugador=nom2, entidad=ent,
                                completada=(tipo_proc == 'completada'),
                                paso=paso_proc, tipo_evento=tipo_proc
                            )
                            dp = dialogos.propio(_nom_ent, faccion=faccion, jugador=nom2, entidad=ent, graduado=_es_graduado(ses))
                            if _nom_ent.lower() in ('aurora angel', 'dark city angel', 'ironcastle angel', 'breezewood angel'):
                                g_comp = dp if dp else g_mis
                            else:
                                g_comp = g_mis if g_mis else dp
                            if g_comp:
                                ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g_comp, 1
                                ses.dlg_val = struct.unpack_from('<H', g_comp[0], 4)[0] if len(g_comp[0]) >= 6 else 4
                                ses.enviar(dialogos.linea_de(g_comp, 0, nom2))
                                log.info(f"[{addr}] Quest {qid_proc} {tipo_proc} con {_nom_ent}")
                            return
                        elif tipo_proc in ('incompleta', 'recoleccion_incompleta', 'caceria_incompleta'):
                            qid_proc = datos_proc.get('qid')
                            paso_proc = datos_proc.get('paso', 1)
                            nom2 = ses.personaje.nombre if ses.personaje else 'Jugador'
                            # Primero el arbol de dialogo del MAPA, que dice la
                            # linea exacta de este NPC en este paso; si no la
                            # tiene, la que se deduce del bloque de la mision.
                            # Asi Bella Bulu dice "consigue 20 Microcoins..." y
                            # no la frase de Matia mandandote a buscarla.
                            g_prog = None
                            _cara_m = dialogos.val_por_entidad(ent)
                            try:
                                import dialogos_mapa as _dm
                                import eventos_mundo as _evm_d
                                _lm = _dm.lineas_sin_accion(
                                    getattr(ses.personaje, 'stage', 0), _cara_m,
                                    _evm_d.ContextoSesion(ses))
                                if _lm:
                                    _cara_m, _msgs_m = _lm
                                    g_prog = [dialogos.armar_linea(mid, _cara_m, [])[2:]
                                              for mid in _msgs_m]
                                    log.info(f"[{addr}] {_nom_ent}: linea del arbol del mapa {_msgs_m}")
                            except Exception:
                                log.exception('arbol de dialogo del mapa')
                            if not g_prog:
                                g_prog = dialogos.guion_de_mision(
                                    qid_proc, _nom_ent, jugador=nom2, entidad=ent,
                                    en_progreso=True, paso=paso_proc, tipo_evento=tipo_proc
                                )
                            if g_prog:
                                ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g_prog, 1
                                ses.dlg_val = _cara_m
                                ses.enviar(dialogos.linea_de(g_prog, 0, nom2))
                                log.info(f"[{addr}] {_nom_ent}: recordatorio de mision {qid_proc} en curso a {nom2}")
                                return
                            return

                    # 2. Si no habia mision activa con este NPC, comprobar si ofrece misiones disponibles.
                    # Los profesores y docentes de Angel Lyceum no auto-asignan disponibles[0],
                    # sino que presentan su propio menu interactivo para que el jugador elija el curso.
                    _nom_lower = (_nom_ent or '').strip().lower()
                    _npcs_con_menu_cursos = (
                        'battle professor', 'magic professor', 'mine professor',
                        'weapon lecturer', 'armor lecturer', 'sewing lecturer',
                        'art lecturer', 'cooking lecturer', 'michael'
                    )
                    stg_act = _st_ent or (getattr(ses.personaje, 'stage', 0) if ses.personaje else 0)
                    if _nom_lower in _npcs_con_menu_cursos:
                        disponibles = []
                    else:
                        disponibles = _mis.misiones_disponibles_npc(ses.personaje, _nom_ent, stage=stg_act, entidad=ent)
                    if disponibles:
                        nom2 = ses.personaje.nombre if ses.personaje else 'Jugador'
                        # La primera que tenga guion de oferta: las del registro
                        # del BreezeWood Angel (130, 136, 140) no lo tienen, y
                        # quedandose con ellas el NPC nunca llegaba a la 558.
                        qid_ofrecer = next(
                            (q for q in disponibles
                             if dialogos.guion_de_mision(q, _nom_ent, jugador=nom2,
                                                         entidad=ent, completada=False)),
                            disponibles[0])
                        flujo = dialogos.info_flujo_mision(qid_ofrecer)
                        # Comprobar nivel requerido
                        req_lvl = _mis.info_mision(qid_ofrecer).get('nivel')
                        if flujo and flujo.get('rechazo_nivel'):
                            import re as _re_lvl
                            txt_r = dialogos._cargar_msg_dict().get(flujo['rechazo_nivel'], '')
                            m_lvl = _re_lvl.search(r'level\s+(?:is\s+not\s+|isn\'t\s+yet\s+|must\s+be\s+at\s+least\s+)?(?:/c\$2)?(\d+)', txt_r, _re_lvl.I)
                            if m_lvl:
                                req_lvl = int(m_lvl.group(1))
                        lvl_act = getattr(ses.personaje, 'nivel', 1)
                        if req_lvl and lvl_act < req_lvl and flujo and flujo.get('rechazo_nivel'):
                            # Rechazo por nivel insuficiente
                            sub_r = dialogos.armar_linea(flujo['rechazo_nivel'], dialogos.val_por_entidad(ent), [], strings=[nom2])
                            ses.dlg_ent = ent
                            ses.dlg_guion = [sub_r[2:]]
                            ses.dlg_paso = 1
                            ses.dlg_val = dialogos.val_por_entidad(ent)
                            ses.enviar(sub_r)
                            log.info(f"[{addr}] {_nom_ent}: nivel insuficiente ({lvl_act} < {req_lvl}) para mision {qid_ofrecer}")
                            return

                        g_ofrecer = dialogos.guion_de_mision(qid_ofrecer, _nom_ent, jugador=nom2, entidad=ent, completada=False)
                        if g_ofrecer:
                            tiene_opciones = any(dialogos.opciones_de(l) for l in g_ofrecer) or bool(flujo.get('ops_prop') or flujo.get('ops_preg'))
                            if not tiene_opciones:
                                # Misión sin opciones interactivas de aceptación (ej: Quest 100 con Director Wolay):
                                # Asignación directa. Se acepta de inmediato para que el cliente reciba 0x0022 y 0x000D (Alt+Q).
                                _mis.aceptar_mision(ses, qid_ofrecer)
                                ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g_ofrecer, 1
                                ses.dlg_val = dialogos.val_por_entidad(ent)
                                ses.dlg_quest_ofrecida = None
                                ses.dlg_quest_fase = None
                                ses.enviar(dialogos.linea_de(g_ofrecer, 0, nom2))
                                log.info(f"[{addr}] {_nom_ent} asigno directamente mision {qid_ofrecer} a {nom2}")
                                return
                            else:
                                ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g_ofrecer, 1
                                ses.dlg_val = dialogos.val_por_entidad(ent)
                                ses.dlg_quest_ofrecida = qid_ofrecer
                                ses.dlg_quest_fase = 'interes'
                                ses.enviar(dialogos.linea_de(g_ofrecer, 0, nom2))
                                log.info(f"[{addr}] {_nom_ent} ofrece mision {qid_ofrecer} a {nom2}")
                                return
                _en_prog = _tutor_en_progreso(ses)
                _reg = _ya_registrado(ses)
                _es_grad = _es_graduado(ses)
                if _nom_ent == 'Director Wolay' and ses.personaje:
                    _en_prog = bool(_mis.tiene_mision(ses.personaje, 100) and not _mis.mision_completada(ses.personaje, 100))
                    _reg = bool(_mis.mision_completada(ses.personaje, 100) or _mis.tiene_mision(ses.personaje, 101) or _reg)

                _clean_house = None
                _house_lvl = None
                if ses.personaje:
                    try:
                        import casas as _cs_d
                        _c_cur = getattr(ses, 'casa_visitando', None)
                        if not _c_cur:
                            _c_cur = _cs_d.obtener_o_crear_casa(ses.personaje.char_id, ses.personaje.nombre, raw_data=getattr(ses.personaje, 'casa', None))
                        if _c_cur:
                            _clean_house = int(getattr(_c_cur, 'cleanliness', 0))
                            _house_lvl = _cs_d.nivel_de_magia(_c_cur.calcular_magia())
                    except Exception:
                        pass

                g2 = dialogos.propio(
                        _nom_ent, faccion=faccion,
                        jugador=getattr(ses.personaje, 'nombre', '') if ses.personaje else '',
                        visto_michael=bool(getattr(ses.personaje, 'hablo_michael', False)
                                           if ses.personaje else False),
                        stage=getattr(ses.personaje, 'stage', 0) if ses.personaje else 0,
                        registrado=_reg,
                        entidad=ent,
                        en_progreso=_en_prog,
                        graduado=_es_grad,
                        cleanliness=_clean_house,
                        house_level=_house_lvl)

                # El dialogo del ARBOL DEL MAPA cuando el NPC tiene uno que
                # hace algo (opciones, acciones, ramas). Solo en instancias,
                # donde los NPC van guionados por el mapa, o si no hay otro:
                # en las ciudades manda dialogos.propio(), que ya funciona.
                if ses.personaje:
                    try:
                        import dialogos_mapa as _dm_c
                        _st_c = getattr(ses.personaje, 'stage', 0)
                        if (es_instancia(_st_c) and _st_c != 500) or not g2:
                            _ret_c = dialogos.val_por_entidad(ent)
                            _raiz_c = _dm_c.raiz_interactiva(_st_c, _ret_c)
                            # Con la carrera (NPCKILLGAME) en marcha, el que la
                            # organiza contesta con la raiz que la cierra
                            # (61102 en la sala 2 de la Magic Kichen Path): con
                            # mas de 50 bajas "You win!" y te pasa al 75, y si
                            # no "The game is in progress... make more effort".
                            # Antes volvia a salir su presentacion (10001) y no
                            # habia forma de cobrar la victoria.
                            import eventos_mundo as _evm_cc
                            _jm_c = getattr(_evm_cc.estado_de(ses), 'juego_matar', None)
                            if _jm_c and time.time() < _jm_c.get('fin', 0):
                                _fin_c = _dm_c.nodo_fin_de_juego(_st_c)
                                if _fin_c and _dm_c._arbol(_st_c).get(str(_fin_c), {}).get('c') == _ret_c:
                                    _raiz_c = _fin_c
                            if _raiz_c and _recorrer_dialogo_mapa(ses, addr, _st_c, _raiz_c):
                                log.info(f"[{addr}] {_nom_ent}: dialogo del arbol del mapa ({_raiz_c})")
                                return
                    except Exception:
                        log.exception('dialogo del arbol del mapa')

                if g2:
                    nom2 = ses.personaje.nombre if ses.personaje else 'Jugador'
                    ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g2, 1
                    ses.dlg_val = struct.unpack_from('<H', g2[0], 4)[0] if len(g2[0]) >= 6 else 4
                    ses.enviar(dialogos.linea_de(g2, 0, nom2))
                    log.info(f"[{addr}] dialogo de {_nom_ent} (val={ses.dlg_val})")
                    return

                log.debug(f"[{addr}] clic en la entidad {ent} ({_nom_ent}): sin dialogo")
                return
            # En Guide Palace (stage 51):
            inv_items = list((getattr(ses, 'inventario', {}) or {}).values())
            has_exam = (1386 in inv_items)
            bolsa = getattr(ses, 'inventario', {}) or {}
            # Guantes (5) o Zapatos (6) que Raphael ensena a equiparse en la etapa 1:
            has_gloves_or_shoes = bool(bolsa.get(5) or bolsa.get(6))

            if ent == 19:  # Raphael
                if has_exam:
                    etapa = 3
                elif ses.personaje and ses.personaje.tutorial >= 2:
                    etapa = 2
                elif ses.personaje and ses.personaje.tutorial >= 1 and has_gloves_or_shoes:
                    etapa = 2
                elif (ses.personaje and ses.personaje.habilidades):
                    etapa = 1
                else:
                    etapa = 0
            elif ent == 21:  # Angel Aide
                if has_exam:
                    etapa = 2  # 5047 (Good for you!)
                elif (ses.personaje and (ses.personaje.tutorial >= 2 or getattr(ses, 'oro', 0) >= 10)):
                    etapa = 1  # 5022 con menu: 5045 Buy / 5046 Quit
                else:
                    etapa = 0  # 5022 sin menu (0 opciones)
            else:  # 20 Interface Tutor
                etapa = 0

            g = dialogos.guion_etapa(ent, etapa)
            if not g:
                log.debug(f"[{addr}] clic en la entidad {ent}: sin dialogo conocido")
                return
            nom = ses.personaje.nombre if ses.personaje else 'Jugador'
            ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ent, g, 0
            ses.dlg_val = 3 if ent == 19 else (2 if ent == 20 else 52)
            ses.enviar(dialogos.linea_de(g, 0, nom))
            ses.dlg_paso = 1
            log.info(f"[{addr}] dialogo con la entidad {ent} (etapa {etapa}): "
                     f"linea 1 de {len(g)}")
            return

        # La eleccion en un dialogo del arbol del mapa (_recorrer_dialogo_mapa).
        # Solo si el cuadro abierto sigue siendo ese: si despues se abrio
        # otro, dlg_guion ya no es el mismo y lo atiende quien lo abrio.
        _dlm = getattr(ses, 'dlg_mapa', None)
        if (opcode == 0x000B and ses.rol == 'mundo' and _dlm
                and getattr(ses, 'dlg_guion', None) is _dlm.get('guion')):
            import dialogos as _dlg_m
            _v = d.get('valor', 1) if d else 1
            if _dlg_m.es_opcion(_v):
                ses.dlg_mapa = None
                _i = _dlg_m.indice_opcion(_v)
                _ops = _dlm.get('opciones') or []
                _sig = _ops[_i][1] if 0 <= _i < len(_ops) else 0
                ses.dlg_ent = None
                ses.enviar(struct.pack('<H', 0x0012) + _dlg_m.FIN)
                log.info(f"[{addr}] dialogo del mapa: opcion {_i} -> nodo {_sig}")
                if _sig and ses.personaje:
                    _recorrer_dialogo_mapa(ses, addr, _dlm['stage'], _sig)
                return

        if opcode == 0x000B and ses.rol == 'mundo' and getattr(ses, 'dlg_estatua', None):
            import dialogos as _dlg_e
            _est = ses.dlg_estatua
            ses.dlg_estatua = None
            _v = d.get('valor', 0) if d else 0
            _i = _dlg_e.indice_opcion(_v) if _dlg_e.es_opcion(_v) else -1
            ses.enviar(struct.pack('<H', 0x0012) + _dlg_e.FIN)
            if _i != 0 or not ses.personaje or not _est.get('llegada'):
                log.info(f"[{addr}] estatua: se responde que no (opcion {_i})")
                return
            _x, _y = _est['llegada']
            ses.personaje.tile_x, ses.personaje.tile_y = _x, _y
            ses.enviar(struct.pack('<HIII', 0x0003,
                                   ses.personaje.entity_id, _x, _y))
            log.info(f"[{addr}] estatua: aceptado, salta a ({_x},{_y})")
            return

        if opcode == 0x000B and ses.rol == 'mundo' and getattr(ses, 'dlg_ent', None):
            import dialogos
            ent, paso = ses.dlg_ent, getattr(ses, 'dlg_paso', 0)
            g = getattr(ses, 'dlg_guion', None) or []
            # Elegir una opcion del cuadro, no pasar de linea.
            _v = d.get('valor', 1) if d else 1
            if dialogos.es_opcion(_v):
                # Se buscan las opciones en la ULTIMA linea del guion que
                # tenga, no en la de 'paso - 1'. Una respuesta puede ser
                # varias lineas -- la de dejar el entrenamiento son dos, el
                # 10123 suelto y el 10124 con las opciones -- y mirando solo
                # una caia en la que no tiene ninguna.
                _ops = []
                for _l in reversed(g[:paso] if 0 < paso <= len(g) else g):
                    _ops = dialogos.opciones_de(_l)
                    if _ops:
                        break
                _i = dialogos.indice_opcion(_v)
                import dialogos as _dlg_mod
                _el = _ops[_i] if 0 <= _i < len(_ops) else None
                if _el is None and (_v in _ops or _v > 100):
                    _el = _v
                val = getattr(ses, 'dlg_val', 4)
                if _el is None:
                    # Sin opcion que corresponda no hay nada que hacer: se
                    # cierra el cuadro. Antes se seguia de largo y el
                    # servidor reventaba comparando None con un numero, lo
                    # que tiraba la conexion del jugador.
                    log.warning(f"[{addr}] opcion {_v} sin correspondencia "
                                f"(hay {len(_ops)} opciones); se cierra el "
                                f"dialogo")
                    ses.dlg_ent = None
                    ses.enviar(struct.pack('<H', 0x0012) + dialogos.FIN)
                    return

                # Opciones de mision interactiva (Interes [Ayudar/Salir] o Propuesta [Aceptar/Rechazar])
                if getattr(ses, 'dlg_quest_ofrecida', None):
                    qid_ofrecida = ses.dlg_quest_ofrecida
                    fase = getattr(ses, 'dlg_quest_fase', 'interes')
                    val = getattr(ses, 'dlg_val', 4)
                    flujo = dialogos.info_flujo_mision(qid_ofrecida)
                    nom2 = ses.personaje.nombre if ses.personaje else 'Jugador'

                    if fase == 'interes':
                        if _i == 0:  # Eligió la primera opción: "Tell me how I can help." / "About help"
                            # Mostrar la propuesta detallada de la misión (con páginas de historia si tiene)
                            ses.dlg_quest_fase = 'propuesta'
                            lineas_prop = []
                            for m_hist in flujo.get('historia', []):
                                lineas_prop.append(dialogos.armar_linea(m_hist, val, [], strings=[nom2])[2:])
                            line_final = dialogos.armar_linea(flujo['propuesta'], val, flujo.get('ops_prop', []), strings=[nom2])
                            lineas_prop.append(line_final[2:])
                            ses.dlg_guion = lineas_prop
                            ses.dlg_paso = 1
                            ses.enviar(dialogos.linea_de(lineas_prop, 0, nom2))
                            log.info(f"[{addr}] {nom2} mostro interes en mision {qid_ofrecida}; mostrando historia/propuesta ({len(lineas_prop)} paginas)")
                            return
                        else:  # Eligió "Leave." / "I quit."
                            ses.dlg_quest_ofrecida = None
                            ses.dlg_quest_fase = None
                            ses.dlg_ent = None
                            ses.enviar(struct.pack('<H', 0x0012) + dialogos.FIN)
                            log.info(f"[{addr}] {nom2} no mostro interes en mision {qid_ofrecida}")
                            return

                    elif fase == 'propuesta':
                        if _i == 0:  # Eligió "Ok" / Aceptar misión
                            ses.dlg_quest_ofrecida = None
                            ses.dlg_quest_fase = None
                            import misiones as _mis_op
                            _mis_op.aceptar_mision(ses, qid_ofrecida)
                            log.info(f"[{addr}] {nom2} ACEPTÓ la mision {qid_ofrecida} de {_nombre_entidad(ses, ent)}")
                            # Si hay diálogo de despedida/buena suerte (base + 8), mostrarlo
                            if flujo.get('exito'):
                                line_exito = dialogos.armar_linea(flujo['exito'], val, [], strings=[nom2])
                                ses.dlg_guion = [line_exito[2:]]
                                ses.dlg_paso = 1
                                ses.enviar(line_exito)
                            else:
                                ses.dlg_ent = None
                                ses.enviar(struct.pack('<H', 0x0012) + dialogos.FIN)
                            return
                        else:  # Eligió "It sounds dangerous. I'm leaving." / Rechazar
                            ses.dlg_quest_ofrecida = None
                            ses.dlg_quest_fase = None
                            ses.dlg_ent = None
                            ses.enviar(struct.pack('<H', 0x0012) + dialogos.FIN)
                            log.info(f"[{addr}] {nom2} rechazo la propuesta de mision {qid_ofrecida}")
                            return

                # Casos especiales de opciones en Guide Palace:
                # 1. Interface Tutor: 5241 ("OK") -> Inicia explicacion paso a paso
                if _el == 5241:
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    ses.dlg_ent = ent
                    ses.dlg_guion = g
                    ses.dlg_paso = 2
                    ses.enviar(dialogos.linea_de(g, 1, nom))
                    log.info(f"[{addr}] Interface Tutor: explicacion iniciada (linea 5243)")
                    return

                # 2. Raphael: 5008 ("I'm ready") -> Inicia fase de equipamiento
                if _el == 5008:
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    ses.dlg_ent = ent
                    ses.dlg_guion = g
                    ses.dlg_paso = 3
                    ses.enviar(dialogos.linea_de(g, 2, nom))
                    log.info(f"[{addr}] Raphael: jugador listo, inicia fase de equipo (linea 5014)")
                    return

                # 3. Raphael: 5011 ("Yes." confirmar abandono del tutorial)
                if _el == 5011:
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    submsg_5013 = dialogos.armar_linea(5013, 3, [], strings=[nom])
                    submsg_fin = struct.pack('<H', 0x0012) + dialogos.FIN
                    ses.enviar(submsg_5013, submsg_fin)
                    ses.dlg_ent = None
                    import clases as _cl3
                    ses.personaje.stage = 41
                    ses.personaje.tile_x, ses.personaje.tile_y = (152, 74)
                    ses.monstruos = _monstruos_de(41)
                    ses.enviar(_cl3.cambiar_mapa(41))
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mapa(ses.usuario, ses.personaje.char_id, 41, 152, 74)
                    log.info(f"[{addr}] Raphael: abandono tutorial -> enviado a Angel Lyceum (41)")
                    return

                # Opciones especiales de Angel Lyceum (firmas, cursos y graduacion):
                if _el in (11509, 11809, 10635):
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    import misiones as _mis_sig
                    if _el == 11509:
                        _mis_sig.avanzar_paso(ses, 101, 2)
                        sub_msg = dialogos.armar_linea(11511, 4, [])
                    elif _el == 11809:
                        _mis_sig.avanzar_paso(ses, 101, 3)
                        sub_msg = dialogos.armar_linea(11811, 4, [])
                    else:
                        _mis_sig.avanzar_paso(ses, 101, 4)
                        sub_msg = dialogos.armar_linea(10637, 4, [])
                    sub_fin = struct.pack('<H', 0x0012) + dialogos.FIN
                    ses.enviar(sub_msg, sub_fin)
                    ses.dlg_ent = None
                    log.info(f"[{addr}] Firma de profesor ({_el}) para Quest 101 entregada a {nom}")
                    return

                # Aceptacion directa de lecciones y cursos desde los menus de los profesores
                _mapa_lecciones = {
                    11514: 115, 11515: 116, 11516: 117,
                    11814: 118, 11815: 119, 11816: 120,
                    10618: 106, 10619: 107, 10620: 108, 10621: 109,
                    11003: 110, 11103: 111, 11203: 112, 11303: 113, 11403: 114,
                }
                if _el in _mapa_lecciones:
                    q_leccion = _mapa_lecciones[_el]
                    import misiones as _mis_lec
                    _mis_lec.aceptar_mision(ses, q_leccion)
                    ses.dlg_ent = None
                    ses.enviar(struct.pack('<H', 0x0012) + dialogos.FIN)
                    log.info(f"[{addr}] Leccion {q_leccion} aceptada mediante opcion {_el}")
                    return

                # Evaluacion de Michael para Top Student Training (Quest 123)
                if _el == 12308:
                    import misiones as _mis_mich
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    puntos = _mis_mich.obtener_token_mision(ses, 1394)
                    if puntos < 15:
                        sub_msg = dialogos.armar_linea(12310, 1, [], strings=[nom])
                        ses.enviar(sub_msg, struct.pack('<H', 0x0012) + dialogos.FIN)
                        ses.dlg_ent = None
                    else:
                        _mis_mich.aceptar_mision(ses, 123)
                        lineas_m = [
                            dialogos.armar_linea(12311, 1, [])[2:],
                            dialogos.armar_linea(12312, 1, [])[2:],
                            dialogos.armar_linea(12313, 1, [])[2:],
                            dialogos.armar_linea(12314, 1, [])[2:],
                            dialogos.armar_linea(12315, 1, [])[2:],
                        ]
                        ses.dlg_ent = ent
                        ses.dlg_guion = lineas_m
                        ses.dlg_paso = 1
                        ses.dlg_val = 1
                        ses.enviar(dialogos.linea_de(lineas_m, 0, nom))
                    log.info(f"[{addr}] Solicitud de Top Student Training (puntos={puntos})")
                    return

                # Confirmacion de graduacion con Angels' Tutor
                if _el == 10119:
                    if _es_graduado(ses):
                        ses.enviar(dialogos.armar_linea(11512, 2, []), struct.pack('<H', 0x0012) + dialogos.FIN)
                        ses.dlg_ent = None
                        log.info(f"[{addr}] Graduacion rechazada: el personaje ya esta graduado")
                        return
                    import misiones as _mis_grad
                    puntos = _mis_grad.obtener_token_mision(ses, 1394)
                    if puntos >= 5:
                        _mis_grad.completar_mision(ses, 102)
                        if ses.personaje:
                            ses.personaje.faction = "Graduated"
                            if getattr(ses, 'usuario', None):
                                cuentas.guardar_faccion(ses.usuario,
                                                        ses.personaje.char_id, "Graduated")
                        ses.enviar(struct.pack('<H', 0x0012) + dialogos.FIN)
                        ses.dlg_ent = None
                        _sincronizar_cambio_mapa(ses, STAGE_GRADUACION,
                                                 TILE_GRADUACION[0], TILE_GRADUACION[1])
                        log.info(f"[{addr}] Graduacion completada (puntos={puntos}) -> enviado a Graduation Palace ({STAGE_GRADUACION})")
                    else:
                        sub_msg = dialogos.armar_linea(10122, 2, [])
                        ses.enviar(sub_msg, struct.pack('<H', 0x0012) + dialogos.FIN)
                        ses.dlg_ent = None
                        log.info(f"[{addr}] Intento de graduacion rechazado por falta de creditos ({puntos}/5)")
                    return

                # Aceptacion de inscripcion de novato con Angels' Tutor (Quest 101)
                if _el == 10135 and ses.personaje:
                    if _es_graduado(ses):
                        ses.enviar(dialogos.armar_linea(11512, 2, []), struct.pack('<H', 0x0012) + dialogos.FIN)
                        ses.dlg_ent = None
                        log.info(f"[{addr}] Inscripcion rechazada: el personaje ya esta graduado")
                        return
                    import misiones as _mis_tut
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    if not _mis_tut.tiene_mision(ses.personaje, 101) and not _mis_tut.mision_completada(ses.personaje, 101):
                        _mis_tut.aceptar_mision(ses, 101)
                        if _mis_tut.tiene_mision(ses.personaje, 100):
                            _mis_tut.completar_mision(ses, 100)
                    sub_msg = dialogos.armar_linea(10103, 2, [])
                    sub_fin = struct.pack('<H', 0x0012) + dialogos.FIN
                    ses.enviar(sub_msg, sub_fin)
                    ses.dlg_ent = None
                    log.info(f"[{addr}] Angels' Tutor: {nom} acepto Quest 101 (Freshman signing)")
                    return

                if 121600 <= ent <= 121699: _st_ent = 3     # Aurora City
                elif 121700 <= ent <= 121799: _st_ent = 5   # Cherry Village
                elif 121800 <= ent <= 121849: _st_ent = 22  # Mysterious Garden
                elif 121850 <= ent <= 121919: _st_ent = 26  # Dark City
                elif 121920 <= ent <= 121999: _st_ent = 29  # Breeze Woods
                elif 122040 <= ent <= 122063: _st_ent = 35  # Memory Cave
                elif 122064 <= ent <= 122085: _st_ent = 36  # Gebuer Vale
                elif 122086 <= ent <= 122199: _st_ent = 38  # Iron Castle
                elif 122295 <= ent <= 122305: _st_ent = 69  # Lava Cave
                elif 122306 <= ent <= 122315: _st_ent = 70  # Flaming Door
                elif 122355 <= ent <= 122404 or (30080 <= ent <= 30083): _st_ent = 88  # Palm Base
                elif 122408 <= ent <= 122415 or (30112 <= ent <= 30115): _st_ent = 90  # Blue Ocean
                elif 122460 <= ent <= 122495 or (30336 <= ent <= 30339): _st_ent = 104  # Waterfall Camp
                elif 122585 <= ent <= 122610 or (30608 <= ent <= 30611): _st_ent = 121  # Desert Racetrack
                elif 122730 <= ent <= 122760 or (31008 <= ent <= 31011): _st_ent = 146  # Airship Station
                elif 122761 <= ent <= 122789: _st_ent = 151  # Mushroom Village
                elif 122790 <= ent <= 122799: _st_ent = 152  # Building Blocks County
                elif 122800 <= ent <= 122820 or (31120 <= ent <= 31123): _st_ent = 153  # Building Blocks City
                elif 122890 <= ent <= 122925 or (31280 <= ent <= 31283): _st_ent = 163  # Hoca Village
                elif 123000 <= ent <= 123030 or (31392 <= ent <= 31395): _st_ent = 170  # Pharaoh Village
                else: _st_ent = None

                if _st_ent and ses.personaje and (not getattr(ses.personaje, 'stage', 0) or ses.personaje.stage != _st_ent):
                    ses.personaje.stage = _st_ent

                # VIAJE POR DIALOGO. Hay NPC que preguntan a donde quieres
                # ir en vez de mandarte por un tornado: el primero medido es
                # Brin, en Shuwa Market, que lleva a Siam Square. Va antes de
                # respuesta_a porque lo que toca no es contestar otra linea
                # sino cambiar de mapa.
                _viaje = dialogos.VIAJES_POR_OPCION.get(
                    (getattr(ses.personaje, 'stage', 0) if ses.personaje
                     else 0, _el))
                if _viaje and ses.personaje:
                    _st, _tile = _viaje
                    ses.enviar(struct.pack('<H', 0x0012) + dialogos.FIN)
                    _viajar_por_portal(ses, addr,
                                       {'destino': _st, 'llegada': _tile},
                                       motivo='por el dialogo de %s'
                                       % _nombre_entidad(ses, ent))
                    return

                if _casa_submit_order(ses, _el):
                    return
                _fac_actual = getattr(ses.personaje, 'faction', 'Heaven') if ses.personaje else 'Heaven'
                submsgs = dialogos.respuesta_a(
                    _el, entidad=ent, val=val,
                    nombre=_nombre_entidad(ses, ent),
                    stage=getattr(ses.personaje, 'stage', 0)
                    if ses.personaje else 0,
                    nivel=getattr(ses.personaje, 'nivel', 0)
                    if ses.personaje else 0,
                    faccion=_fac_actual,
                    graduado=_es_graduado(ses)) if _el else (struct.pack('<H', 0x0012) + dialogos.FIN,)
                # El almacen se arma AQUI, no en dialogos.py, porque hay que
                # leer lo que el personaje tiene guardado. dialogos.py devuelve
                # un 0x004E vacio de marcador y se sustituye por el de verdad.
                if ses.personaje and any(m[:2] == struct.pack('<H', 0x004E) for m in submsgs):
                    import inventario as _inv
                    _bco = dict(ses.personaje.banco or {})
                    # Slot 0 SIEMPRE representa el dinero depositado en el banco
                    _bco_oro = getattr(ses.personaje, 'banco_oro', 0)
                    _guardado = [(0, _inv.ITEM_ORO, _bco_oro)]
                    for r, v in sorted(_bco.items()):
                        if int(r) == 0:
                            continue
                        # (objeto, cantidad). En memoria es tupla, pero al
                        # volver de cuentas.db llega como LISTA, y solo se
                        # miraba la tupla: int([item, n]) reventaba al abrir
                        # el almacen de cualquier personaje recien cargado.
                        if isinstance(v, (tuple, list)):
                            _guardado.append((int(r), int(v[0]), int(v[1]) if len(v) > 1 else 1))
                        else:
                            _guardado.append((int(r), int(v), 1))
                    _real = _inv.almacen(ses.personaje.char_id, _guardado,
                                         ses.personaje.entity_id)
                    submsgs = tuple(_real if m[:2] == struct.pack('<H', 0x004E) else m
                                    for m in submsgs)

                # Solo la PRIMERA linea de dialogo. El cliente espera una,
                # pide "siguiente" con 0x000B valor 1, y recien entonces le
                # llega la que sigue. Medido: al elegir "Quit the training"
                # el servidor manda el 10123, el cliente contesta 01, y
                # despues llega el 10124 con las opciones. Mandando las dos
                # de golpe el cuadro se quedaba sin hacer nada.
                _dialogo_visto = False
                _envio = []
                for _p in submsgs:
                    _es_dlg = len(_p) > 2 and _p[:2] == struct.pack('<H', 0x0012)
                    if _es_dlg and _dialogo_visto:
                        continue
                    if _es_dlg:
                        _dialogo_visto = True
                    _envio.append(_p)
                ses.enviar(*_envio)



                # Elecciones especiales
                if _el in DESTINOS_ENTRENAMIENTO and ses.personaje:
                    _st_area, _tile_area, _nombre_area = DESTINOS_ENTRENAMIENTO[_el]
                    ses.viaje_pendiente = (_st_area, _tile_area, _nombre_area)
                elif _el == 10125 and ses.personaje:
                    if _es_graduado(ses):
                        ses.enviar(dialogos.armar_linea(11512, 2, []), struct.pack('<H', 0x0012) + dialogos.FIN)
                        ses.dlg_ent = None
                        log.info(f"[{addr}] Abandono rechazado: el personaje ya esta graduado")
                        return
                    # "Quit the training": el traslado NO va aqui. Medido:
                    # al decir que si el servidor manda el 10127, el cliente
                    # pide la linea siguiente, llega el cierre del cuadro y
                    # RECIEN ENTONCES el cambio de mapa. Mandandolo en este
                    # momento el traslado caia en mitad del dialogo y el
                    # cuadro se quedaba colgado.
                    import misiones as _mis_quit
                    if _mis_quit.tiene_mision(ses.personaje, 102):
                        _mis_quit.completar_mision(ses, 102)
                    elif _mis_quit.tiene_mision(ses.personaje, 101):
                        _mis_quit.completar_mision(ses, 101)
                        if _mis_quit.tiene_mision(ses.personaje, 102):
                            _mis_quit.completar_mision(ses, 102)
                    ses.viaje_pendiente = (STAGE_GRADUACION, TILE_GRADUACION,
                                           'Graduation Palace')
                    ses.personaje.faction = "Graduated"
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_faccion(ses.usuario,
                                                ses.personaje.char_id, "Graduated")
                    log.info(f"[{addr}] {ses.personaje.nombre} confirmo dejar "
                             f"el entrenamiento; viaja al cerrarse el dialogo")
                elif _el == 10235 and ses.personaje:
                    # Confirmar la faccion. Se decide por el NOMBRE del NPC,
                    # no por su id: antes habia una lista de ids de totems
                    # escrita a mano y los cuatro Angeles del Graduation
                    # Palace no estaban en ella, asi que confirmar con
                    # cualquiera de ellos asignaba Aurora por defecto.
                    _nom_npc = _nombre_entidad(ses, ent) or ''
                    FACCION_POR_NOMBRE = {
                        'Aurora': "Aurora",
                        'Dark City': "Dark City",
                        'Iron': "Iron Castle",
                        'Breeze': "Breeze Woods",
                    }
                    nueva_fac = "Aurora"
                    for _clave, _fac in FACCION_POR_NOMBRE.items():
                        if _clave.lower() in _nom_npc.lower():
                            nueva_fac = _fac
                            break
                    else:
                        log.warning(f"[{addr}] confirmar faccion con "
                                    f"'{_nom_npc}': no se reconoce, se usa "
                                    f"Aurora")
                    import clases as _cl5
                    _pj = ses.personaje
                    _pj.faction = nueva_fac
                    # Y al aceptar te lleva a la ciudad de esa faccion. El
                    # traslado faltaba: se quedaba en el Graduation Palace.
                    _dst, _tile = CIUDAD_DE_FACCION.get(nueva_fac,
                                                        CIUDAD_DE_FACCION["Aurora"])
                    # El viaje espera a que se cierre el cuadro, igual que el
                    # del Graduation Palace. Medido: se elige "Yes", pasan
                    # dos lineas mas, llegan las misiones y RECIEN ENTONCES
                    # el cambio de mapa.
                    # La faccion se aplica AL LLEGAR a la ciudad, que es
                    # cuando el cliente la cambia de "Heaven" a la suya. Y lo
                    # que se guarda es el nombre de la FACCION, no el de la
                    # ciudad: el campo pasa a decir "Beasts", no "Breeze
                    # Woods".
                    _fac_nombre = NOMBRE_DE_FACCION.get(nueva_fac, nueva_fac)
                    ses.viaje_pendiente = (_dst, _tile, _fac_nombre)
                    ses.faccion_al_llegar = _fac_nombre
                    # Se completa "Choosing country" y se da la de registro
                    # de esa ciudad, como en la captura: primero el 0x0022 de
                    # la nueva mision y despues el de la 103 con el paso 1 y
                    # el sello de la hora.
                    # Las misiones se mandan JUNTO CON EL VIAJE, al
                    # cerrarse el cuadro; aqui todavia quedan dos lineas de
                    # dialogo por delante.
                    ses.misiones_al_llegar = nueva_fac
                    log.info(f"[{addr}] {_pj.nombre} eligio {nueva_fac}: "
                             f"viaja al stage {_dst} casilla {_tile} cuando "
                             f"se cierre el dialogo")
                elif _el == 5747 and ses.personaje:
                    # Cupid: fija donde se revive.
                    #
                    # Dos cosas estaban mal. Se guardaba en spawn_stage/
                    # spawn_x/spawn_y y al revivir se leia checkpoint_stage/
                    # checkpoint_x/checkpoint_y, o sea otros campos: el
                    # checkpoint no hacia nada. Y ademas fijaba siempre el
                    # Lyceum en (138,60) aunque hablaras con el Cupid del
                    # East o del West. Ahora queda donde estas parado, que es
                    # justo al lado del Cupid con el que hablaste.
                    _pj = ses.personaje
                    _pj.checkpoint_stage = _pj.stage
                    _pj.checkpoint_x, _pj.checkpoint_y = _pj.tile_x, _pj.tile_y
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_checkpoint(ses.usuario, _pj.char_id,
                                                   _pj.stage, _pj.tile_x, _pj.tile_y)
                    log.info(f"[{addr}] {_pj.nombre} fijo el punto de revivir "
                             f"con Cupid: mapa {_pj.stage} casilla "
                             f"({_pj.tile_x},{_pj.tile_y})")
                elif 5802 <= _el <= 5806 and ses.personaje:
                    # East Playground A1..A5
                    _sincronizar_cambio_mapa(ses, 42, 11, 113)
                    log.info(f"[{addr}] East Portal: al East Playground (stage 42)")
                elif (getattr(ses, 'dlg_portal', None)
                      and str(_el) in (ses.dlg_portal.get('destinos') or {})
                      and ses.personaje):
                    if ses.personaje.stage == 500 and _el in (7889, 7890):
                        _c_chk = _casa_actual(ses)
                        if _c_chk and _c_chk.owner_id != ses.personaje.char_id:
                            log.info(f"[{addr}] Visitor {ses.personaje.nombre} tried to enter owner private room {_el}, blocked.")
                            return
                    # DESTINO PROPIO DEL PORTAL. Antes cada menu de portal
                    # habia que escribirlo a mano aqui con su rango de ids;
                    # asi el nudo de Teddy Amusement, que manda a dos puntos
                    # del MISMO mapa, no se podia expresar. Ahora el portal
                    # trae {'destinos': {'<id de opcion>': {...}}} y se
                    # resuelve solo.
                    _d = ses.dlg_portal['destinos'][str(_el)]
                    _falso = dict(ses.dlg_portal)
                    _falso['destino'] = _d.get('destino', ses.personaje.stage)
                    _falso['llegada'] = _d['llegada']
                    _falso['direccion'] = _d.get('direccion')
                    _viajar_por_portal(ses, addr, _falso,
                                       'por la opcion %d' % _el)
                elif _el in (7891, 7899) and ses.personaje:
                    # I'm leaving / Leave
                    import dialogos as _dlg_close
                    ses.enviar_inmediato(struct.pack('<H', 0x0012) + _dlg_close.FIN)
                    es_portal_salida = (getattr(ses, 'dlg_portal', None) is not None or
                                       getattr(ses, 'dlg_ent', None) == 701)
                    ses.dlg_ent = None
                    ses.dlg_guion = None
                    ses.dlg_paso = 0
                    ses.dlg_portal = None
                    if ses.personaje.stage == 500 and es_portal_salida:
                        asyncio.get_event_loop().call_later(
                            0.75, _salir_de_casa_despues_dialogo, ses, addr)
                elif _el == 7894 and ses.personaje:
                    # Cancelar salida de la casa / Stay a bit longer
                    import dialogos as _dlg_close
                    ses.enviar(struct.pack('<H', 0x0012) + _dlg_close.FIN)
                elif _el == 7898 and ses.personaje:
                    # Maid Eilian: Votar por la casa visitada (Vote)
                    import casas as _cs_vt, cuentas as _cta_vt, dialogos as _dlg_vt, clases as _cl_vt
                    _c_vt = getattr(ses, 'casa_visitando', None) or _cs_vt.obtener_o_crear_casa(
                        ses.personaje.char_id, ses.personaje.nombre, raw_data=getattr(ses.personaje, 'casa', None))
                    _c_vt.check_daily_reset()
                    _cid = int(ses.personaje.char_id)
                    if _cid in _c_vt.voted_users_today:
                        ses.enviar(_dlg_vt.armar_linea(7922, _dlg_vt.MAID_PORTRAIT, [7899]),
                                   struct.pack('<H', 0x0012) + _dlg_vt.FIN)
                    else:
                        _c_vt.voted_users_today.add(_cid)
                        _c_vt.votes_today += 1
                        _c_vt.votes_total += 1
                        if getattr(ses, 'usuario', None):
                            _cta_vt.guardar_casa(ses.usuario, _c_vt.owner_id, _c_vt)
                        _lv, _prev_m, _next_m = _cs_vt.info_nivel(_c_vt.calcular_magia())
                        _rnk = _cs_vt.rango_casa(_c_vt)
                        ses.enviar(_cs_vt.pkt_house_info(
                            _lv, _c_vt.calcular_magia(), _next_m, _prev_m,
                            _c_vt.bonus_pct, _c_vt.cleanliness,
                            _c_vt.votes_total, _c_vt.votes_today,
                            _c_vt.visitors_total, 0, _rnk,
                            10 if _c_vt.is_open else 1))
                        ses.enviar(_cl_vt.aviso("Thank you for voting!", tipo=0))
                        ses.enviar_inmediato(struct.pack('<H', 0x0012) + _dlg_vt.FIN)
                elif _el == 7912 and ses.personaje:
                    # Bendicion diaria de Maid Eilian
                    _casa_buff_diario(ses, addr)
                elif _el == 7910 and ses.personaje:
                    # Mercenary Token de Maid Eilian
                    _casa_recibir_token(ses, addr)
                elif _el in (7901, 7916) and ses.personaje:
                    # Limpieza de casa con Maid Eilian: requiere Soap Powder o Liquid Soap
                    import casas as _cs_cln, cuentas as _cta_cln, dialogos as _dlg_cln
                    SOAP_ITEMS = _cs_cln.SOAP_CLEAN
                    bolsa = getattr(ses, 'inventario', {}) or {}
                    ranura_soap = None
                    boost = 0
                    for r, it in sorted(bolsa.items()):
                        if it in SOAP_ITEMS:
                            ranura_soap = r
                            boost = SOAP_ITEMS[it]
                            break
                    if ranura_soap is not None:
                        _sacar(ses, ranura_soap, 1)
                        ses.enviar(*_refrescar(ses, [ranura_soap]))
                        _c_cln = getattr(ses, 'casa_visitando', None) or _cs_cln.obtener_o_crear_casa(
                            ses.personaje.char_id, ses.personaje.nombre, raw_data=getattr(ses.personaje, 'casa', None))
                        _c_cln.cleanliness = min(1000, _c_cln.cleanliness + boost)
                        ses.personaje.casa = _c_cln.serializar()
                        ses.personaje.buffs.pop('house_clean_bonus', None)
                        if getattr(ses, 'usuario', None):
                            _cta_cln.guardar_casa(ses.usuario, ses.personaje.char_id, _c_cln)
                        _lv, _prev_m, _next_m = _cs_cln.info_nivel(_c_cln.calcular_magia())
                        _rnk = _cs_cln.rango_casa(_c_cln)
                        _v_rem = 1 if (ses.personaje.char_id not in _c_cln.voted_users_today) else 0
                        ses.enviar(_cs_cln.pkt_house_info(_lv, _c_cln.calcular_magia(), _next_m, _prev_m,
                                                          _c_cln.bonus_pct, _c_cln.cleanliness,
                                                          _c_cln.votes_total, _c_cln.votes_today,
                                                          _c_cln.visitors_total, _v_rem, _rnk,
                                                          10 if _c_cln.is_open else 1))
                        # Maid Eilian contesta: "Bravo. Eilian loves to clean." (msg 7916)
                        ses.enviar(_dlg_cln.armar_linea(7916, _dlg_cln.MAID_PORTRAIT, []), struct.pack('<H', 0x0012) + _dlg_cln.FIN)
                        log.info(f"[{addr}] Casa limpiada con exito (cleanliness={_c_cln.cleanliness}) usando soap {bolsa.get(ranura_soap, 0)}")
                    else:
                        # No tiene jabon: "Master, please buy some Soap Powder for me. I can't clean the house without it." (msg 7915)
                        ses.enviar(_dlg_cln.armar_linea(7915, _dlg_cln.MAID_PORTRAIT, []), struct.pack('<H', 0x0012) + _dlg_cln.FIN)
                        log.info(f"[{addr}] Intento de limpieza de casa sin Soap Powder ni Liquid Soap")
                elif _el == 7876 and ses.personaje:
                    # Activate Raise-a-Pet Room
                    if not _dialogo_visto:
                        import dialogos as _dlg_pet
                        ses.enviar(struct.pack('<H', 0x0012) + _dlg_pet.FIN)
                    _casa_abrir_pets(ses, addr)
                    log.info(f"[{addr}] Pet Care Machine activated via dialog 7876")
                elif _el == 7884 and ses.personaje:
                    # Use Monster Hatching Machine
                    import dialogos as _dlg_mob
                    ses.enviar(struct.pack('<H', 0x0012) + _dlg_mob.FIN)
                    _casa_abrir_mobgen(ses, addr)
                    log.info(f"[{addr}] Monster Hatching Machine activated via dialog 7884")
                elif 5807 <= _el <= 5811 and ses.personaje:
                    # West Playground A1..A5
                    _sincronizar_cambio_mapa(ses, 43, 186, 27)
                    log.info(f"[{addr}] West Portal: al West Playground (stage 43)")
                elif _el in (20002, 30002, 40002, 50002) and ses.personaje:
                    import misiones as _mis
                    import clases as _cl
                    # 1. Guia de la ciudad (Explorer Lim, Risker Zalfer, Pioneer Ocadon, Explorer Gulin)
                    if ent in _mis.GUIAS_CIUDAD:
                        _st_g, _q_con, _nom_g, _ = _mis.GUIAS_CIUDAD[ent]
                        if _mis.tiene_mision(ses.personaje, _q_con) and not _mis.mision_completada(ses.personaje, _q_con):
                            _mis.completar_mision(ses, _q_con, exp=1500, oro=500)
                            log.info(f"[{addr}] {ses.personaje.nombre} completo mision {_q_con} con {_nom_g}")
                        else:
                            ses.enviar(_cl.aviso(f"{_nom_g}: Welcome to our city, Angel!", tipo=0, msg_id=_cl.MSG_TEXTO))
                    # 2. Block Envoy (Mushroom Village)
                    elif ent == 122784 or 'Block Envoy' in (_nombre_entidad(ses, ent) or ''):
                        _st_m142, _pa142, _comp142 = _mis.estado_mision(ses.personaje, _mis.QUEST_EDEN_NEEDS_HELP)
                        if not _st_m142 or _pa142 <= 1:
                            if not _st_m142:
                                _mis.aceptar_mision(ses, _mis.QUEST_EDEN_NEEDS_HELP)
                            _mis.avanzar_paso(ses, _mis.QUEST_EDEN_NEEDS_HELP, 2)
                            ses.enviar(_cl.aviso("Quest [Eden Needs Help]: Defeat 100 Young Witches or Crystal Envoys!", tipo=0, msg_id=_cl.MSG_TEXTO))
                        elif _pa142 == 3:
                            _mis.avanzar_paso(ses, _mis.QUEST_EDEN_NEEDS_HELP, 4)
                            ses.enviar(_cl.aviso("Quest [Eden Needs Help]: Report to Guerrilla Leader Mola in Building Blocks County!", tipo=0, msg_id=_cl.MSG_TEXTO))
                            _sincronizar_cambio_mapa(ses, 152, 132, 95)
                    # 3. Guerrilla Leader Mola (Building Blocks County)
                    elif ent == 122793 or 'Mola' in (_nombre_entidad(ses, ent) or '') or 'Guerrilla' in (_nombre_entidad(ses, ent) or ''):
                        _st_m142, _pa142, _ = _mis.estado_mision(ses.personaje, _mis.QUEST_EDEN_NEEDS_HELP)
                        _st_m143, _pa143, _ = _mis.estado_mision(ses.personaje, _mis.QUEST_FINAL_LINE)
                        if _st_m142 and _pa142 == 4:
                            _mis.completar_mision(ses, _mis.QUEST_EDEN_NEEDS_HELP, exp=50000, oro=20000)
                            _mis.aceptar_mision(ses, _mis.QUEST_FINAL_LINE)
                            _mis.avanzar_paso(ses, _mis.QUEST_FINAL_LINE, 1)
                            ses.enviar(_cl.aviso("Quest [The Final Line]: Defeat 100 Fireball Babies or Flower Thorn Babies!", tipo=0, msg_id=_cl.MSG_TEXTO))
                        elif _st_m143:
                            if _pa143 == 2:
                                _mis.avanzar_paso(ses, _mis.QUEST_FINAL_LINE, 3)
                                ses.enviar(_cl.aviso("Quest [The Final Line]: Defeat 100 Dog Fighters!", tipo=0, msg_id=_cl.MSG_TEXTO))
                            elif _pa143 == 4:
                                _mis.avanzar_paso(ses, _mis.QUEST_FINAL_LINE, 5)
                                ses.enviar(_cl.aviso("Quest [The Final Line]: Report to Lord Kahn in Building Blocks City!", tipo=0, msg_id=_cl.MSG_TEXTO))
                                _sincronizar_cambio_mapa(ses, 153, 51, 136)
                    # 4. Lord Kahn (Building Blocks City)
                    elif ent == 122809 or 'Kahn' in (_nombre_entidad(ses, ent) or ''):
                        _st_m143, _pa143, _ = _mis.estado_mision(ses.personaje, _mis.QUEST_FINAL_LINE)
                        if _st_m143 and _pa143 == 5:
                            _mis.completar_mision(ses, _mis.QUEST_FINAL_LINE, exp=100000, oro=50000, creditos_honor=50)
                            _mis.aceptar_mision(ses, 144)
                            _mis.avanzar_paso(ses, 144, 1)
                            ses.enviar(_cl.aviso("Quest [Recapturing Eden]: Accepted from Lord Kahn!", tipo=0, msg_id=_cl.MSG_TEXTO))
                    # 5. Angel de Ciudad: Registro (Opcion 2)
                    elif _el in _dlg_mod.CIUDAD_POR_OPCION and _el % 10000 == 2:
                        _pjr = ses.personaje
                        _cfgr = _dlg_mod.ANGEL_DE_CIUDAD[_dlg_mod.CIUDAD_POR_OPCION[_el]]
                        _q_reg = _cfgr['mision_registro']
                        _nuevas_q = (_cfgr['mision_conocer'], _cfgr['mision_nivel'])
                        _mis.completar_mision(ses, _q_reg, exp=500, oro=200)
                        for _q in _nuevas_q:
                            if not _mis.tiene_mision(_pjr, _q) and not _mis.mision_completada(_pjr, _q):
                                _mis.aceptar_mision(ses, _q)
                        log.info(f"[{addr}] {_pjr.nombre} se registro con el Angel de su ciudad: misiones {_nuevas_q}, la {_q_reg} completada")
                elif (_el in _dlg_mod.CIUDAD_POR_OPCION
                      and _el % 10000 == 3 and ses.personaje):
                    # Angel de Ciudad: The mission of the Angel Protector (Opcion 3)
                    import misiones as _mis
                    import clases as _cl
                    _cfgr = _dlg_mod.ANGEL_DE_CIUDAD[_dlg_mod.CIUDAD_POR_OPCION[_el]]
                    _q_niv = _cfgr['mision_nivel']
                    _q_con = _cfgr['mision_conocer']
                    _pj = ses.personaje
                    _rango_act = getattr(_pj, 'rango', 1)
                    if not _mis.tiene_mision(_pj, _q_con) and not _mis.mision_completada(_pj, _q_con):
                        _mis.aceptar_mision(ses, _q_con)
                    if not _mis.tiene_mision(_pj, _q_niv) and not _mis.mision_completada(_pj, _q_niv):
                        _mis.aceptar_mision(ses, _q_niv)
                    if _mis.tiene_mision(_pj, _q_niv) and not _mis.mision_completada(_pj, _q_niv):
                        if _pj.nivel >= 20 and _rango_act >= 2:
                            _mis.completar_mision(ses, _q_niv, exp=10000, oro=5000, creditos_honor=20)
                            ses.enviar(_cl.aviso("Quest Completed! Talk to Paradise Angel to journey into Eden.", tipo=0, msg_id=_cl.MSG_TEXTO))
                            log.info(f"[{addr}] {_pj.nombre} completo mision de nivel {_q_niv}")
                elif (_el in _dlg_mod.CIUDAD_POR_OPCION
                      and _el % 10000 == 18 and ses.personaje):
                    # Angel de Ciudad: Volver al Angel Lyceum (Opcion 18)
                    ses.viaje_pendiente = (41, (152, 74), 'Angel Lyceum')
                    log.info(f"[{addr}] {ses.personaje.nombre} pidio volver al Angel Lyceum desde su ciudad")
                elif _el == 14303 and ses.personaje:
                    import misiones as _mis
                    import clases as _cl
                    if not _mis.tiene_mision(ses.personaje, _mis.QUEST_FINAL_LINE):
                        _mis.aceptar_mision(ses, _mis.QUEST_FINAL_LINE)
                        _mis.avanzar_paso(ses, _mis.QUEST_FINAL_LINE, 1)
                        ses.enviar(_cl.aviso("Quest [The Final Line]: Defeat 100 Fireball Babies or Flower Thorn Babies!", tipo=0, msg_id=_cl.MSG_TEXTO))
                elif _el == 14402 and ses.personaje:
                    import misiones as _mis
                    import clases as _cl
                    if not _mis.tiene_mision(ses.personaje, 144):
                        _mis.aceptar_mision(ses, 144)
                        _mis.avanzar_paso(ses, 144, 1)
                        ses.enviar(_cl.aviso("Quest [Recapturing Eden]: Accepted from Lord Kahn!", tipo=0, msg_id=_cl.MSG_TEXTO))
                elif (_el in _dlg_mod.CIUDAD_POR_OPCION
                      and _el % 10000 == 18 and ses.personaje):
                    # "Send me back to the Angel Lyceum" del Angel de una
                    # ciudad. Medido: contesta con el 50019 y el cambio de
                    # mapa llega al cerrarse el cuadro, no en el acto.
                    ses.viaje_pendiente = (41, TILE_VUELTA_LYCEUM,
                                           'Angel Lyceum')
                    log.info(f"[{addr}] {ses.personaje.nombre} vuelve al "
                             f"Angel Lyceum cuando se cierre el dialogo")
                elif _el == 5080 and ses.personaje:
                    import misiones as _mis
                    # 1. Paradise Angel (lleva a Mushroom Village en Eden y otorga Quest 142)
                    if ent in _mis.PARADISE_ANGELS or 'Paradise' in (_nombre_entidad(ses, ent) or ''):
                        if not _mis.tiene_mision(ses.personaje, _mis.QUEST_EDEN_NEEDS_HELP):
                            _mis.aceptar_mision(ses, _mis.QUEST_EDEN_NEEDS_HELP)
                            _mis.avanzar_paso(ses, _mis.QUEST_EDEN_NEEDS_HELP, 1)
                        _sincronizar_cambio_mapa(ses, 151, 195, 146)
                        log.info(f"[{addr}] Paradise Angel: {ses.personaje.nombre} enviado a Mushroom Village (stage 151)")
                    elif ent == 122784 or 'Block Envoy' in (_nombre_entidad(ses, ent) or ''):
                        # Block Envoy: viaje a Building Blocks County
                        _sincronizar_cambio_mapa(ses, 152, 132, 95)
                        log.info(f"[{addr}] Block Envoy: {ses.personaje.nombre} enviado a Building Blocks County (stage 152)")
                    else:
                        # Director Wolay: retorno a la ciudad de faccion elegida
                        CIUDAD_POR_FACCION = {
                            NOMBRE_DE_FACCION[c]: CIUDAD_DE_FACCION[c]
                            for c in CIUDAD_DE_FACCION if c in NOMBRE_DE_FACCION
                        }
                        st_dest, tile_dest = CIUDAD_POR_FACCION.get(
                            ses.personaje.faction, CIUDAD_DE_FACCION["Aurora"])
                        _sincronizar_cambio_mapa(ses, st_dest, tile_dest[0], tile_dest[1])
                        log.info(f"[{addr}] Director Wolay: retorno a {ses.personaje.faction} (stage {st_dest})")
                elif _el == 5058 and ses.personaje:
                    # Raphael (Fighting Palace): Repetir explicacion
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    g_rep = dialogos.guion_fighting_palace(0, nom)
                    ses.dlg_ent = ent
                    ses.dlg_guion = g_rep
                    ses.dlg_paso = 1
                    ses.dlg_val = 5
                    ses.enviar(dialogos.linea_de(g_rep, 0, nom))
                    log.info(f"[{addr}] Raphael (Fighting Palace): repitiendo explicacion de combate")
                    return
                elif _el == 5063 and ses.personaje:
                    # Raphael (Fighting Palace): "I'm ready to go to the Angel Lyceum."
                    # Manda la linea 5065 y luego teletransporta a Angel Lyceum (stage 41)
                    nom = ses.personaje.nombre if ses.personaje else 'Jugador'
                    submsg_5065 = dialogos.armar_linea(5065, 5, [])
                    submsg_fin = struct.pack('<H', 0x0012) + dialogos.FIN
                    ses.enviar(submsg_5065, submsg_fin)
                    ses.dlg_ent = None
                    _sincronizar_cambio_mapa(ses, 41, 152, 74)
                    log.info(f"[{addr}] Raphael (Fighting Palace): combate completado -> teletransportado a Angel Lyceum (41)")
                    return
                elif ses.personaje:
                    # Comprobar si la opcion elegida corresponde a aceptar una quest
                    _qid_cand = None
                    if getattr(ses, 'dlg_quest_opciones', None) and _el in ses.dlg_quest_opciones:
                        _qid_cand = ses.dlg_quest_opciones[_el]

                    if _qid_cand:
                        import misiones as _mis_opt
                        if _mis_opt.info_mision(_qid_cand):
                            if not _mis_opt.tiene_mision(ses.personaje, _qid_cand) or _mis_opt.es_repetible(_qid_cand):
                                _mis_opt.aceptar_mision(ses, _qid_cand)

                termina = any(
                    m.endswith(dialogos.FIN) or struct.unpack_from('<H', m, 0)[0] in (0x0034, 0x002B, 0x001D)
                    for m in submsgs if len(m) >= 2
                )
                if termina:
                    ses.dlg_ent = None
                    # El cuadro se cierra aqui mismo, asi que lo que dejo
                    # pedido la opcion -- el viaje, la faccion y las misiones
                    # -- se hace ahora. Antes quedaba apuntado para un cierre
                    # que ya habia pasado y el personaje no se movia.
                    _v2 = getattr(ses, 'viaje_pendiente', None)
                    if _v2 and ses.personaje:
                        ses.viaje_pendiente = None
                        _st2, _tile2, _nom2 = _v2
                        _cerrar_viaje(ses, addr, _st2, _tile2, _nom2)
                else:
                    ses.dlg_ent = ent
                    # TODAS las lineas de dialogo de la respuesta, no solo la
                    # primera. Guardando una sola, una respuesta de varias
                    # lineas se quedaba trunca: al elegir "Quit the training"
                    # el guion quedaba en [10123] y el "siguiente" cerraba el
                    # cuadro en vez de mandar el 10124 con las opciones.
                    ses.dlg_guion = [m[2:] for m in submsgs
                                     if len(m) > 2
                                     and struct.unpack_from('<H', m, 0)[0] == 0x0012]
                    ses.dlg_paso = 1
                    if len(submsgs[0]) >= 8:
                        ses.dlg_val = struct.unpack_from('<H', submsgs[0], 6)[0]
                log.info(f"[{addr}] eligio la opcion {_i + 1}"
                         + (f" (dialogo {_el})" if _el else ""))
                return
            nom = ses.personaje.nombre if ses.personaje else 'Jugador'
            # Entrega de guantes y zapatos en Raphael antes de mostrar la linea 5015 (paso == 3 en tramo 1):
            if ent == 19 and paso == 3 and len(g) >= 7 and struct.unpack_from('<I', g[3], 0)[0] == 5015:
                cid = ses.personaje.char_id if ses.personaje else 4980
                ses.inventario = getattr(ses, 'inventario', {}) or {}
                import inventario as _iv
                import clases as _cls
                s_glov = _ranura_libre(ses.inventario, desde=20)
                ses.inventario[s_glov] = 28
                s_shoe = _ranura_libre(ses.inventario, desde=s_glov + 1)
                ses.inventario[s_shoe] = 30
                ses.enviar(*_iv.entregar(cid, 28, s_glov),
                           *_iv.entregar(cid, 30, s_shoe),
                           _iv.completo(cid, _con_oro(ses), _dueno(ses), _mejoras_de(ses)),
                           _cls.aviso("Students' Gloves\x00Students' shoes", tipo=0, msg_id=493))
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_inventario(ses.usuario, cid, ses.inventario,
                                   _cantidades(ses))
                log.info(f"[{addr}] Raphael: entregados guantes (slot {s_glov}) y zapatos (slot {s_shoe})")

            # El cliente manda el 0x000B repetido -- en la captura llegan dos
            # seguidos con 210 ms de diferencia -- y el servidor REAL contesta
            # al primero con la linea y al segundo cerrando el cuadro. Se
            # probo ignorar el repetido cuando la linea tiene opciones y fue
            # un invento: aqui se reproduce lo medido, que es cerrar.
            # Michael da la mision "Choosing country" JUSTO ANTES de su
            # ultima linea, no al cerrarse el cuadro. Medido: el 0x0022 llega
            # a los 53.05 y el 10134 a los 53.23, y el cierre recien a los
            # 54.29.
            if (ses.personaje and paso == len(g) - 1
                    and _nombre_entidad(ses, ent) == 'Michael'
                    and not getattr(ses.personaje, 'hablo_michael', False)):
                import clases as _cl7
                ses.personaje.hablo_michael = True
                _q = _cl7.QUEST_ELEGIR_PAIS
                if _q not in [x[0] for x in (ses.personaje.quests or [])]:
                    ses.personaje.quests = list(ses.personaje.quests or []) + [(_q, 0)]
                ses.enviar(_cl7.mision(ses.personaje.char_id, _q, 0),
                           _cl7.aviso(_cl7.nombre_de_quest(_q), tipo=0,
                                      msg_id=_cl7.MSG_QUEST))
                log.info(f"[{addr}] Michael: mision {_q} "
                         f"'{_cl7.nombre_de_quest(_q)}'; los Angeles de "
                         f"faccion pasan a su segundo dialogo")

            ses.enviar(dialogos.linea_de(g, paso, nom))
            if paso < len(g):
                ses.dlg_paso = paso + 1
                log.debug(f"[{addr}] dialogo {ent}: linea {paso + 1}")
            else:
                ses.dlg_ent = None
                if getattr(ses, 'dlg_quest_ofrecida', None):
                    _q_auto = ses.dlg_quest_ofrecida
                    ses.dlg_quest_ofrecida = None
                    ses.dlg_quest_fase = None
                    import misiones as _mis_auto
                    _mis_auto.aceptar_mision(ses, _q_auto)
                # Viaje aplazado: el traslado que dejo pedido una opcion del
                # dialogo se hace AHORA, cuando el cuadro se cierra. Es el
                # orden del servidor real: 10127, cierre, y despues el
                # cambio de mapa.
                # Hablar con Michael desbloquea el segundo dialogo de los
                # cuatro Angeles de faccion.
                _viaje = getattr(ses, 'viaje_pendiente', None)
                if _viaje and ses.personaje:
                    ses.viaje_pendiente = None
                    _st, _tile, _nom_dest = _viaje
                    _cerrar_viaje(ses, addr, _st, _tile, _nom_dest)
                    return
                # Fin de dialogo en Guide Palace (stage 51):
                if ses.personaje and ses.personaje.stage == MAPA_DEL_TUTORIAL:
                    if ent == 19:
                        ultimo_id = struct.unpack_from('<I', g[-1], 0)[0] if g else 0
                        if ultimo_id == 5005:
                            # Fin de tramo 0 -> abrir ventana de seleccion de clase (0x001D kind=12)
                            pkg_prof = struct.pack('<HIBBII', 0x001D, ent, 1, 12, 0, 0)
                            ses.enviar(pkg_prof)
                            log.info(f"[{addr}] Raphael: fin tramo 0 -> abierta ventana de seleccion de clase")
                        elif ultimo_id == 5018:
                            # Fin de fase de equipo
                            ses.personaje.tutorial = 1
                            if getattr(ses, 'usuario', None):
                                cuentas.guardar_tutorial(ses.usuario, ses.personaje.char_id, 1)
                            log.info(f"[{addr}] Raphael: fin fase de equipo (etapa 1)")
                        elif ultimo_id == 5043:
                            # Fin de fase de compra de bienes -> dar 10 de oro
                            ses.personaje.tutorial = 2
                            if getattr(ses, 'usuario', None):
                                cuentas.guardar_tutorial(ses.usuario, ses.personaje.char_id, 2)
                            if getattr(ses, 'oro', 0) < 10:
                                ses.oro = 10
                                ses.personaje.oro = 10
                                import clases as _cls
                                import inventario as _iv
                                bars, max_pts = _max_sp_info(ses.personaje)
                                ses.enviar(struct.pack('<HIBBI', 0x0013, ses.personaje.entity_id, 1, 6, 10),
                                           _cls.aviso("10 Gold", tipo=0, msg_id=_cls.MSG_PAGO),
                                           _iv.completo(ses.personaje.char_id, _con_oro(ses), None,
                                               _mejoras_de(ses)),
                                           _iv.stats(ses.inventario, ses.personaje.habilidades,
                                                     hp=ses.personaje.hp, hp_max=ses.personaje.hp_max,
                                                     mp=ses.personaje.mp, mp_max=ses.personaje.mp_max,
                                                     oro=10, sp=getattr(ses, 'sp', None), sp_max=bars,
                                                     mejoras=_mejoras_de(ses)))
                                if getattr(ses, 'usuario', None):
                                    cuentas.guardar_oro(ses.usuario, ses.personaje.char_id, 10)
                            log.info(f"[{addr}] Raphael: fin etapa 2 -> 10 de oro otorgados")
                        elif ultimo_id in (5047, 5054):
                            # Fin de tramo 3 (examen completado) -> consumir examen y teletransportar a Fighting Palace (57)
                            slot_1386 = next((s for s, it in ses.inventario.items() if it == 1386), None)
                            if slot_1386 is not None:
                                del ses.inventario[slot_1386]
                            import inventario as _iv
                            import clases as _cls
                            ses.enviar(_iv.completo(ses.personaje.char_id, _con_oro(ses), None,
                                               _mejoras_de(ses)))
                            ses.personaje.tutorial = 3
                            if getattr(ses, 'usuario', None):
                                cuentas.guardar_inventario(ses.usuario, ses.personaje.char_id, ses.inventario,
                                   _cantidades(ses))
                                cuentas.guardar_tutorial(ses.usuario, ses.personaje.char_id, 3)
                            _sincronizar_cambio_mapa(ses, 57, 216, 37)
                            log.info(f"[{addr}] Raphael: examen completado -> teletransportado a Fighting Palace (57)")
                        else:
                            log.info(f"[{addr}] Raphael: dialogo terminado (ultimo_id={ultimo_id})")
                    else:
                        log.info(f"[{addr}] dialogo con la entidad {ent} terminado")
                else:
                    log.info(f"[{addr}] dialogo con la entidad {ent} terminado")
            return

        if opcode == 0x0007 and ses.rol == 'mundo' and cuerpo:
            log.debug(f"[{addr}] se gira hacia la direccion {cuerpo[0]}")
            return

        # --- Acciones de personaje: Sentarse / Levantarse con tecla Insert (0x0016) ---
        if opcode == 0x0016 and ses.rol == 'mundo' and len(cuerpo) >= 5:
            # [u1 accion][u4 parametro]. Antes se leia un u32 desde el offset
            # 0, que da bien para las acciones chicas (2 revivir, 4 sentarse)
            # porque los bytes altos son cero, pero rompe la 0x0c.
            accion = cuerpo[0]
            parametro = struct.unpack_from('<I', cuerpo, 1)[0]
            if accion == 1 and ses.personaje and not getattr(ses, 'muerto', False):
                # EMOTE / EMOCION (Alt+E o ranuras de acceso rapido).
                # Angel.exe FUN_00614DA0(1, AppData) manda C2S 0x0016 [01] [LE32 emote_id].
                # Se responde y difunde con S2C 0x0019 [LE32 entity_id][U8 emote_id] (FUN_005f2200).
                import inventario as _iv_emo
                if not _iv_emo.puede_usar_emocion(ses.personaje, parametro):
                    import clases as _cl_emo
                    ses.enviar(_cl_emo.aviso("You have not unlocked this expression yet.", tipo=7, msg_id=_cl_emo.MSG_TEXTO))
                    return
                import presencia as _pr_emo
                _pr_emo.notificar_emocion(ses, parametro)
                log.info(f"[{addr}] emote {parametro} usado por {ses.personaje.nombre}")
                return
            if accion == 6 and ses.personaje:
                # ASIGNAR / QUITAR EMOTE RAPIDO (Alt+1..Alt+4).
                # Angel.exe FUN_00578E60 (dropemot) y FUN_00578EF0 (dropxquickemot)
                # mandan C2S 0x0016 [06] [LE32 val].
                # val = (slot << 16) | (emote_id & 0xFFFF).
                # slot va de 0 a 3 (Alt+1..Alt+4).
                # Si emote_id == 0xFFFF, la ranura se vacio / quito.
                slot = (parametro >> 16) & 0xFFFF
                emo_id = parametro & 0xFFFF
                if 0 <= slot <= 3:
                    if getattr(ses.personaje, 'quick_emotes', None) is None:
                        ses.personaje.quick_emotes = {0: -1, 1: -1, 2: -1, 3: -1}
                    if emo_id == 0xFFFF or emo_id == 0xFFFFFFFF:
                        ses.personaje.quick_emotes[slot] = -1
                        log.info(f"[{addr}] emote rapido Alt+{slot+1} quitado")
                    else:
                        ses.personaje.quick_emotes[slot] = emo_id
                        log.info(f"[{addr}] emote rapido Alt+{slot+1} asignado a emote {emo_id}")
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_quick_emotes(ses.usuario, ses.personaje.char_id, ses.personaje.quick_emotes)
                return
            if accion == 0x0C and ses.personaje and not getattr(ses, 'muerto', False):
                # ATAQUE BASICO. El cliente NO manda 0x0006 para pegar sin
                # habilidad ni espera a que se le conteste un clic: manda este
                # 0x0016 y lo repite solo cada ~1,5 s mientras dure el combate.
                # Medido en Celestia, mundo_201655_173169 t=40.4.
                import combate as _cb5
                self.manejar(ses, 0x0006, m, d, addr,
                             struct.pack('<HI', _cb5.ATAQUE_NORMAL, parametro))
                return
            if accion == 2 and ses.personaje and getattr(ses, 'muerto', False):
                # "Return to Angel Lyceum to revive". La ventana la abre el
                # cliente al morir y contesta con este 0x0016 [02 00 00 00 00];
                # el servidor solo tiene que revivir y cambiar el mapa.
                # Medido en Celestia, mundo_190339_977913 t=684.51.
                p2 = ses.personaje
                rev_x = getattr(p2, 'checkpoint_x', 0) or REVIVIR_LYCEUM[0]
                rev_y = getattr(p2, 'checkpoint_y', 0) or REVIVIR_LYCEUM[1]
                p2.hp = _vida_max(p2)
                p2.mp = _mana_max(p2)
                p2.stage = getattr(p2, 'checkpoint_stage', 0) or 41
                p2.tile_x, p2.tile_y = rev_x, rev_y
                ses.muerto = False
                _sincronizar_cambio_mapa(ses, p2.stage, rev_x, rev_y)
                if getattr(ses, 'usuario', None):
                    cuentas.guardar_progreso(ses.usuario, p2.char_id,
                                             p2.nivel, p2.exp, p2.hp, p2.mp, sp=getattr(ses, "sp", None), buffs=getattr(ses.personaje, "buffs", None) if ses.personaje else None)
                log.info(f"[{addr}] revive en stage {p2.stage} ({rev_x},{rev_y})")
                return
            if accion == 4 and ses.personaje:
                if getattr(ses, 'puesto', None):
                    return
                yo = ses.personaje.entity_id
                ses.sentado = not getattr(ses, 'sentado', False)
                act_code = 8 if ses.sentado else 0
                ses.enviar(struct.pack('<HIII', 0x000A, yo, 0, act_code))
                log.info(f"[{addr}] personaje {'se sento' if ses.sentado else 'se levanto'} (accion={act_code})")
                return
            if accion == 8 and ses.personaje:
                # ABANDONAR / BORRAR MISION (game.deletequest en Angel.exe 0x584ae0 -> 0x614da0)
                qid_borrar = parametro
                import misiones as _mis_del
                _mis_del.abandonar_mision(ses, qid_borrar)
                return
            if accion == 0x0D and ses.personaje and not getattr(ses, 'muerto', False):
                # WEAPON SWITCH (Alt+~ / Boton [ I ] [ II ])
                # Intercambia el conjunto de armas activo (ranuras 3 y 4)
                # con el conjunto de reserva Set II (ranuras 11 y 12).
                bolsa = getattr(ses, 'inventario', None)
                if bolsa is not None:
                    cants = _cantidades(ses)
                    cid = ses.personaje.char_id

                    # 1. Swap ranura 3 (Main Weapon) <-> 11 (Main Weapon II)
                    it3 = bolsa.pop(3, None) if 3 in bolsa else bolsa.pop('3', None)
                    it11 = bolsa.pop(11, None) if 11 in bolsa else bolsa.pop('11', None)
                    c3 = cants.pop(3, None) if 3 in cants else cants.pop('3', None)
                    c11 = cants.pop(11, None) if 11 in cants else cants.pop('11', None)
                    if it3 is not None:
                        bolsa[11] = it3
                    if it11 is not None:
                        bolsa[3] = it11
                    if c3 is not None and c3 > 1:
                        cants[11] = c3
                    if c11 is not None and c11 > 1:
                        cants[3] = c11
                    _mover_inst(ses, 3, 11)

                    # 2. Swap ranura 4 (Offhand/Shield/Ammo) <-> 12 (Offhand II)
                    it4 = bolsa.pop(4, None) if 4 in bolsa else bolsa.pop('4', None)
                    it12 = bolsa.pop(12, None) if 12 in bolsa else bolsa.pop('12', None)
                    c4 = cants.pop(4, None) if 4 in cants else cants.pop('4', None)
                    c12 = cants.pop(12, None) if 12 in cants else cants.pop('12', None)
                    if it4 is not None:
                        bolsa[12] = it4
                    if it12 is not None:
                        bolsa[4] = it12
                    if c4 is not None and c4 > 1:
                        cants[12] = c4
                    if c12 is not None and c12 > 1:
                        cants[4] = c12
                    _mover_inst(ses, 4, 12)

                    # 3. Guardar cambios en base de datos
                    _guardar_bolsa(ses, cid)
                    if getattr(ses, 'usuario', None):
                        cuentas.guardar_mejoras(ses.usuario, cid, ses.personaje.mejoras)

                    # 4. Respuesta oficial Celestia:
                    # s2c 0x0016 [0d 00 00]
                    ack_switch = struct.pack('<H', 0x0016) + b'\x0d\x00\x00'
                    salida = [ack_switch]

                    # Refrescar las 4 casillas con sus 0x001B
                    salida.extend(_refrescar(ses, [3, 4, 11, 12]))

                    # Recalcular stats y ajustar limites de HP/MP
                    import combate as _cb
                    _max_h = _vida_max(ses.personaje, bolsa=bolsa)
                    if ses.personaje.hp > _max_h:
                        ses.personaje.hp = _max_h
                    _max_m = _mana_max(ses.personaje, bolsa=bolsa)
                    if ses.personaje.mp > _max_m:
                        ses.personaje.mp = _max_m
                    salida.append(_cb.atributo(ses.personaje.entity_id, ses.personaje.hp, _cb.KIND_HP))
                    salida.append(_cb.atributo(ses.personaje.entity_id, ses.personaje.mp, _cb.KIND_MP))

                    salida.append(_stats_ses(ses))
                    salida.extend(_apariencia(ses))

                    ses.enviar(*salida)

                    # Notificar a los demas jugadores para que vean el cambio de arma
                    import presencia as _pr
                    _pr.notificar_equipo(ses)

                    log.info(f"[{addr}] switch de armas (Alt+~): mano der {it11} <-> {it3}, mano izq {it12} <-> {it4}")
                return

        if opcode == 0x0004 and d:
            ses.ultimo_movimiento = time.time()
            if getattr(ses, 'puesto', None):
                ACK = Msg.registry[(0x006D, 's2c', '*')]
                MOVE = Msg.registry[(0x0005, 's2c', '*')]
                p = getattr(ses, 'personaje', None)
                pos = (ses.puesto.get('posicion')
                       or ((p.tile_x if p else d['cur_x'] // 32),
                           (p.tile_y if p else d['cur_y'] // 32)))
                if p:
                    p.tile_x, p.tile_y = pos[0], pos[1]
                yo = p.entity_id if p else (ses.entity_id or 1001)
                tx, ty = pos[0] * 32, pos[1] * 32
                ses.enviar(ACK.build(),
                           MOVE.build(entity_id=yo, cur_x=tx, cur_y=ty, dst_x=tx, dst_y=ty,
                                      speed=_velocidad_de(ses)))
                log.info(f"[{addr}] movimiento bloqueado: puesto de venta abierto en {pos}")
                return
            # Moverse corta la recoleccion, igual que levanta al sentado.
            if getattr(ses, 'recoleccion', None) and d.get('path'):
                _parar_recoleccion(ses)
            if getattr(ses, 'sentado', False):
                ses.sentado = False
                if ses.personaje:
                    ses.enviar(struct.pack('<HIII', 0x000A, ses.personaje.entity_id, 0, 0))
            MOVE = Msg.registry[(0x0005, 's2c', '*')]
            ACK = Msg.registry[(0x006D, 's2c', '*')]
            # RUTA VACIA: el cliente avisa de que esta parado y no tiene por
            # donde salir. Antes se salia de aqui sin contestar nada y el
            # cliente se quedaba esperando el acuse para siempre: eso era el
            # "stuck" que solo se arreglaba reconectando. El acuse va igual.
            if not d.get('path'):
                ses.enviar(ACK.build())
                if ses.personaje:
                    ses.personaje.tile_x = d['cur_x'] // 32
                    ses.personaje.tile_y = d['cur_y'] // 32
                log.warning(f"[{addr}] el cliente dice que no puede moverse "
                            f"desde ({d['cur_x'] // 32},{d['cur_y'] // 32})")
                return
            # EL PRIMER TRAMO, NO EL ULTIMO. El cliente manda la ruta entera
            # ya esquivada -- con sus curvas para rodear agua y acantilados --
            # y espera que se le confirme tramo a tramo. Confirmando el ultimo
            # se le mandaba en LINEA RECTA hasta el final, cortando por encima
            # del agua y del vacio; al terminar quedaba dentro de una zona
            # intransitable, desde donde su buscador de rutas ya no encontraba
            # salida y empezaba a mandar rutas vacias. Por eso se trababa
            # siempre en los puentes y en las orillas.
            # Medido en Celestia: de 325 rutas de dos o mas tramos, en 291 el
            # servidor devuelve el PRIMER waypoint y en NINGUNA el ultimo.
            dst = d['path'][0]
            ses.enviar(ACK.build(),
                       MOVE.build(entity_id=ses.entity_id or 1001,
                                  cur_x=d['cur_x'], cur_y=d['cur_y'],
                                  dst_x=dst['x'], dst_y=dst['y'],
                                  speed=_velocidad_de(ses)))
            # Y EL MISMO PASO A LOS DEMAS DEL MAPA, con la entidad publica
            # del jugador en vez de la suya: los entity_id se repiten entre
            # sesiones y reenviarlo tal cual haria que un jugador moviera al
            # otro en la pantalla de un tercero.
            try:
                import presencia as _pres
                _pres.mover(ses, d['cur_x'], d['cur_y'], dst['x'], dst['y'],
                            _velocidad_de(ses))
            except Exception:
                log.exception('presencia: fallo al reenviar el paso')
            # Anotar donde queda. Las coordenadas del cliente van en pixeles y
            # el tile mide 32: 2640 -> 82 y 2672 -> 83, que es justo el punto
            # de aparicion de Guide Palace. Se guarda al desconectar, no en
            # cada paso, para no escribir en disco varias veces por segundo.
            if ses.personaje:
                _ox, _oy = d['cur_x'] // 32, d['cur_y'] // 32
                # MOVIMIENTO EN VUELO DEL MAPA ANTERIOR. El viaje puede
                # dispararse por temporizador -- el portal que se arma al
                # terminar el paso --, no solo al contestar un paquete, asi
                # que los movimientos que el cliente ya tenia mandados llegan
                # DESPUES del cambio de mapa y traen casillas del mapa viejo.
                # Aceptandolos se pisaba la posicion recien puesta: el
                # personaje acababa en el stage nuevo con la casilla del
                # anterior. Asi es como quedo en Jade Vale (stage 13) con la
                # (6,241), que es el tornado de Mushroom Forest, fuera de la
                # zona jugable y sin poder moverse.
                _dt = time.time() - getattr(ses, 'mapa_cambiado_en', 0)
                _lejos = max(abs(_ox - (ses.personaje.tile_x or 0)),
                             abs(_oy - (ses.personaje.tile_y or 0)))
                if _dt < 3.0 and _lejos > 15:
                    log.info(f"[{addr}] descartado un movimiento del mapa "
                             f"anterior: dice estar en ({_ox},{_oy}) y acaba "
                             f"de llegar a ({ses.personaje.tile_x},"
                             f"{ses.personaje.tile_y})")
                    return
                ses.personaje.tile_x = dst['x'] // 32
                ses.personaje.tile_y = dst['y'] // 32
                _armar_portal_al_llegar(
                    ses, addr, (ses.personaje.tile_x, ses.personaje.tile_y),
                    max(abs(ses.personaje.tile_x - _ox),
                        abs(ses.personaje.tile_y - _oy)))
                # Y el evento del mapa de esa casilla, si lo hay. Va DESPUES
                # del portal y no en su lugar: los portales siguen saliendo
                # de portales.json, que esta medido uno a uno.
                # Todas las casillas del tramo, no solo la de llegada: los
                # disparadores suelen ser una LINEA que se cruza (el evento
                # 200 de la Magic Kichen Path, que saca a Guard Fasit y los
                # Mud Lords con las antorchas encendidas), y si el tramo la
                # atravesaba sin pararse encima no saltaba. Un mismo evento
                # salta una sola vez por tramo: la lava de la sala 1 son
                # varias casillas seguidas y quita 150 al pasar, no por cada
                # una.
                _st_paso = ses.personaje.stage
                _vistos = set()
                for _cas in _casillas_del_tramo((_ox, _oy),
                                                (ses.personaje.tile_x, ses.personaje.tile_y)):
                    if not ses.personaje or ses.personaje.stage != _st_paso:
                        break
                    _evc = _evento_de_casilla(_st_paso, _cas)
                    if _evc is None or _evc in _vistos:
                        continue
                    _vistos.add(_evc)
                    _eventos_al_pisar(ses, addr, _cas)
                # CHOCAR al llegar (ver _choques_al_llegar). Se espera lo que
                # tarda en andar el tramo: el servidor le pone la casilla de
                # destino al recibir el 0x0004 y, si se mirara ya, el menu del
                # tornado salia al empezar a andar, con el personaje todavia
                # lejos en pantalla.
                if ses.personaje and ses.personaje.stage == _st_paso:
                    _tok_ch = object()
                    ses._token_choque = _tok_ch
                    _dist_px = math.hypot((ses.personaje.tile_x - _ox) * 32,
                                          (ses.personaje.tile_y - _oy) * 32)
                    _espera_ch = _dist_px / max(1, _velocidad_de(ses))
                    _llegada_ch = (ses.personaje.tile_x, ses.personaje.tile_y)
                    _vistos_ch = set(_vistos)
                    try:
                        asyncio.get_event_loop().call_later(
                            _espera_ch, lambda: _choques_al_llegar(
                                ses, addr, _st_paso, _llegada_ch, _tok_ch, _vistos_ch))
                    except Exception:
                        _choques_al_llegar(ses, addr, _st_paso, _llegada_ch, _tok_ch, _vistos_ch)

                # Si el movimiento termina LEJOS del objetivo, se lo suelta:
                # atacabas, te ibas, y al pararte el personaje seguia pegandole
                # al bicho. Caminar HACIA el no lo suelta, que es lo que pasa
                # cuando uno clica un enemigo lejano y se acerca.
                _obj = getattr(ses, 'objetivo_actual', None)
                if _obj:
                    _bi = (getattr(ses, 'monstruos', None) or {}).get(_obj)
                    if _bi is not None:
                        _alc = _cb_alcance(ses)
                        _dist_antes = max(abs(_bi.tile_x - _ox),
                                          abs(_bi.tile_y - _oy))
                        _dist_ahora = max(abs(_bi.tile_x - ses.personaje.tile_x),
                                          abs(_bi.tile_y - ses.personaje.tile_y))
                        if _dist_ahora > 20 or (_dist_ahora > _dist_antes and _dist_ahora > _alc + 1):
                            ses.objetivo_actual = None
                            log.info(f"[{addr}] objetivo soltado: te alejaste a "
                                     f"{_dist_ahora} casillas del {_bi.nombre}")
                        elif _dist_ahora <= _alc + 1 and getattr(_bi, 'vivo', False) and not getattr(ses, 'muerto', False):
                            import combate as _cb_mv
                            self.manejar(ses, 0x0006, m, d, addr,
                                         struct.pack('<HI', _cb_mv.ATAQUE_NORMAL, _obj))
                import clases as _cl3
                # Portales: un solo camino, el de plantillas/portales.json.
                # Antes habia otro bloque con areas enormes (tx<=32 y ty>=126
                # es un cuadrante entero del Lyceum) que abria el dialogo con
                # val=4, o sea CON retrato de NPC, y que ademas teletransportaba
                # sin preguntar desde media pantalla de distancia.
                # Se evalua con la posicion ACTUAL que informa el cliente,
                # no con el destino del movimiento: si no, al hacer clic hacia
                # el tornado el dialogo saltaba de inmediato, con el personaje
                # todavia a media pantalla.
                # Se mira el portal en la casilla DE LLEGADA y, si ahi no
                # hay, en la de salida. Antes solo se miraba la de salida:
                # si hacias clic directo encima del tornado no pasaba nada
                # hasta que te movieras otra vez. Mirar solo la de llegada
                # tampoco sirve -- por eso estaba asi -- porque al clicar
                # hacia el tornado desde lejos el dialogo saltaba de
                # inmediato, con el personaje todavia a media pantalla; eso
                # lo cubre el radio 1, que exige estar encima.
                # SOLO la casilla donde el cliente dice que esta AHORA. Se
                # probo mirar tambien la de destino para que funcionara
                # clicando encima del tornado, y fue un error: al clicarlo
                # desde lejos el viaje salia en el acto, sin caminar. El
                # cliente informa su posicion mientras camina, asi que al
                # pisarlo de verdad llega igual.
                cur_tx, cur_ty = d['cur_x'] // 32, d['cur_y'] // 32
                dst_tx, dst_ty = dst['x'] // 32, dst['y'] // 32
                _por = _portal_en(ses.personaje.stage, cur_tx, cur_ty)
                if not _por:
                    dist_to_dst = max(abs(cur_tx - dst_tx), abs(cur_ty - dst_ty))
                    if dist_to_dst <= 3:
                        _por = _portal_en(ses.personaje.stage, dst_tx, dst_ty)
                if getattr(ses, 'house_furnishing', False):
                    _por = None

                # LA MARCA DURA MIENTRAS SE SIGA ENCIMA. Antes se borraba a
                # los 2 segundos de cambiar de mapa, y ahi estaba el rebote: si
                # la casilla de llegada cae dentro del radio del tornado de
                # vuelta, pasados esos 2 segundos la marca se iba, el siguiente
                # paso volvia a encontrarlo y sacaba al jugador del mapa sin
                # dejarlo andar. No hace falta caducarla: cuando el jugador
                # sale del radio, _ahora vale None y se borra sola.
                _antes = getattr(ses, 'portal_pisado', None)
                _ahora = tuple(_por['tile']) if _por else None
                ses.portal_pisado = _ahora
                if _ahora is not None and _ahora == _antes:
                    _por = None       # ya estaba encima: no reabrir
                if _por is not None and not _por.get('preguntar'):
                    # CANDADO DEL PORTAL: el evento del cliente lleva una
                    # condicion de variable de mapa (EVENT_COND 29) y si no
                    # se cumple saca un dialogo en vez de viajar. El tornado
                    # de (340,204) de la sala 1 de la Magic Kichen Path no deja
                    # pasar hasta que muere el jefe que pone la variable 3.
                    _cand = _por.get('requiere_variable')
                    if _cand:
                        import eventos_mundo as _evm_cd
                        _est_cd = _evm_cd.estado_de(ses)
                        if _est_cd.variable(0, int(_cand['var'])) != int(_cand.get('valor', 1)):
                            if _cand.get('dialogo'):
                                _dialogo_del_mapa(ses, addr, ses.personaje.stage, int(_cand['dialogo']))
                            return
                    # Vuelta directa: acercarse y listo, sin menu.
                    _cancelar_portal_armado(ses)
                    _viajar_por_portal(ses, addr, _por)
                    return
                if _por is not None:
                    if ses.personaje.stage == 500 and _por.get('entity') == 701:
                        c_vis = _casa_actual(ses)
                        if c_vis and c_vis.owner_id != ses.personaje.char_id:
                            _cancelar_portal_armado(ses)
                            _salir_de_casa(ses, addr)
                            return
                    import dialogos as _dlg
                    _cfg = _portales()
                    # Cada tornado puede traer su propio menu: el del
                    # Lyceum al West ofrece A1..A5 del West y el del
                    # East los suyos.
                    _ops = _por.get('opciones') or _cfg['opciones']
                    # El mensaje tambien puede ser propio del portal: el
                    # del Lyceum usa el 5801 global, pero el nudo de
                    # Teddy Amusement trae el suyo, el 513008.
                    sub = _dlg.armar_linea(_por.get('msg') or _cfg['msg'],
                                           0, _ops,
                                           acciones=_por.get('acciones'))
                    ses.dlg_ent = _por['entity']
                    ses.dlg_guion = [sub[2:]]
                    ses.dlg_paso = 1
                    ses.dlg_val = 0
                    ses.dlg_portal = _por
                    ses.enviar(sub)
                    log.info(f"[{addr}] portal en {_por['tile']}: pregunta destino")
            log.debug(f"[{addr}] movimiento ({d['cur_x']},{d['cur_y']}) -> "
                      f"({dst['x']},{dst['y']}) via {d['n']} waypoints")

    async def archivos(self, reader, writer):
        """File server (fport en server.xml). Todavia no responde: graba lo que
        el cliente pide, que es justo lo que hace falta para implementarlo."""
        addr = writer.get_extra_info('peername')
        log.info(f"[archivos {addr}] conectado")
        grab = Grabador(addr, self.fport, bytes(16))
        import archivos
        from framing import HDR, decode_header, submessages, build_frame, pack_submessages, SEQ_HELLO
        # El servidor de archivos tambien manda HELLO al conectar. Se comprobo
        # contra una captura real: frame 0 con seq=0xFFFF y 134 bytes, igual
        # que login y mundo. El mio no mandaba nada hasta que le pedian algo,
        # asi que el cliente esperaba un handshake que nunca llegaba.
        _ph = pathlib.Path(__file__).parent / 'plantillas' / 'hello_archivos.bin'
        if _ph.exists():
            _hf = build_frame(_ph.read_bytes(), SEQ_HELLO)
            grab.salida(_hf)
            writer.write(_hf)
            await writer.drain()
            log.info("[archivos %s] HELLO enviado (%s B)", addr, len(_hf))
        buf, seq = bytearray(), 1
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                grab.entrada(data)
                buf.extend(data)
                while len(buf) >= HDR:
                    h = decode_header(buf, 0)
                    if h['length'] == 0 or h['length'] > 0x10000:
                        del buf[0]; continue
                    if len(buf) < h['wire']:
                        break
                    cuerpo = bytes(buf[HDR:h['wire']]); del buf[:h['wire']]
                    for op, b in submessages(cuerpo[:h['length']])[0]:
                        nom = archivos.nombre_pedido(b)
                        if not nom:
                            # El binario dice que la direccion del MUNDO sale
                            # de +96/+112 de la entrada de servidor, que es el
                            # par fip/fport del server.xml -- o sea ESTE puerto.
                            # Si llega algo que no es un pedido de archivo,
                            # probablemente sea la sesion de mundo.
                            log.warning(f"[archivos {addr}] 0x{op:04X} {len(b)}B "
                                        f"NO es pedido de archivo: {b[:32].hex(' ')}")
                            log.warning(f"[archivos {addr}] ¿es la sesion de MUNDO "
                                        f"llegando por fport?")
                            continue
                        log.info(f"[archivos {addr}] 0x{op:04X} pide '{nom}'")
                        resp = build_frame(
                            pack_submessages([archivos.respuesta_avatar(b)]), seq)
                        seq = 1 if seq >= 0x7FFE else seq + 1
                        grab.salida(resp)
                        writer.write(resp)
                        await writer.drain()
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            base, nc, ns = grab.cerrar()
            log.info(f"[archivos {addr}] desconectado -> logs/sesiones/{base}_*.bin")
            writer.close()

    def _sesion_mundo(self):
        """La ultima sesion de mundo con personaje dentro, o None."""
        for s in reversed(self.mundos):
            if (getattr(s, 'personaje', None)
                    and getattr(s, 'inventario', None) is not None):
                return s
        return None

    def _gm_ejecutar_linea(self, linea: str) -> str:
        """Ejecuta un comando venido de la consola o de data/gm.txt."""
        import clases as _cl
        leido = _gm_parsear(linea)
        if leido is None:
            t = linea.strip()
            return ('GM no entiendo: %s  (prueba: item <id> [cant])' % t) if t else ''
        if leido[0] == 'help':
            return 'GM: item <id> [cant]'
        if leido[0] == 'err':
            return 'GM %s' % leido[1]
        ses = self._sesion_mundo()
        if ses is None:
            return 'GM: no hay personaje en el mundo todavia'
        if leido[0] != 'item':
            cuerpo = linea.strip().encode('ascii', 'replace') + b'\x00'
            _probar_gm(ses, cuerpo, 'consola')
            return 'GM sent'
        _, iid, cant = leido
        msg = _gm_dar_item(ses, iid, cant)
        if not msg.startswith('dado '):
            try:
                ses.enviar(_cl.aviso(msg, tipo=7, msg_id=_cl.MSG_TEXTO))
            except Exception:
                pass
        return 'GM %s' % msg

    async def _consola_gm(self):
        """Lee comandos de la consola del servidor, si la hay."""
        loop = asyncio.get_running_loop()
        try:
            if not sys.stdin or not sys.stdin.isatty():
                return
        except Exception:
            return
        while True:
            try:
                linea = await loop.run_in_executor(None, sys.stdin.readline)
            except Exception:
                return
            if linea == '':
                return
            msg = self._gm_ejecutar_linea(linea)
            if msg:
                log.info(msg)

    async def _cola_gm(self):
        """Comandos por archivo: data/gm.txt, una linea por comando.

        Es la via que funciona siempre. La consola solo sirve si el servidor
        se arranco desde una terminal, y dentro del juego depende de que el
        cuerpo del paquete de chat se pueda husmear.
        """
        ruta = pathlib.Path(__file__).parent.parent / 'data' / 'gm.txt'
        while True:
            await asyncio.sleep(0.5)
            try:
                if not ruta.exists():
                    continue
                texto = ruta.read_text(encoding='utf-8', errors='replace')
                if not texto.strip():
                    continue
                ruta.write_text('', encoding='utf-8')
                for linea in texto.splitlines():
                    msg = self._gm_ejecutar_linea(linea)
                    if msg:
                        log.info(msg)
            except Exception as e:
                log.debug('cola GM: %s', e)

    async def correr(self):
        import functools
        srv = await asyncio.start_server(
            functools.partial(self.cliente, rol='login'), self.host, self.port)
        log.info(f"servidor de LOGIN en {self.host}:{self.port}")
        wsrv = await asyncio.start_server(
            functools.partial(self.cliente, rol='mundo'), self.host, self.wport)
        log.info(f"servidor de MUNDO en {self.host}:{self.wport}")
        tareas = [srv.serve_forever(), wsrv.serve_forever()]
        try:
            fsrv = await asyncio.start_server(self.archivos, self.host, self.fport)
            log.info(f"servidor de archivos en {self.host}:{self.fport}")
            tareas.append(fsrv.serve_forever())
        except OSError as e:
            log.warning(f"no se pudo abrir el puerto de archivos {self.fport}: {e}")
        log.info("server.xml del cliente ya apunta aca (ip=127.0.0.1 port=16768)")
        log.info("GM: /item <id> [qty]  /level <n>  /levelall <n>  (also console or data/gm.txt)")
        tareas.append(gm.consola(self))
        tareas.append(gm.cola(self))
        tareas.append(cuentas.tarea_backup_periodico())

        # SEÑUELOS: el binario muestra que la ip y el puerto del mundo NO
        # salen del redirect sino de la lista de servidores (sub_51A370 los
        # lee de +64 y +80 de una entrada de 372 bytes). Para saber a donde
        # intenta ir el cliente de verdad, se abren los puertos vecinos y se
        # registra cualquier conexion.
        async def senuelo(r, w, p):
            a = w.get_extra_info('peername')
            log.warning("*** EL CLIENTE CONECTO AL PUERTO %s (desde %s) ***", p, a)
            try:
                d = await asyncio.wait_for(r.read(4096), 3)
                log.warning("    mando %s bytes: %s", len(d), d[:48].hex(' ') if d else '(nada)')
            except asyncio.TimeoutError:
                log.warning("    se quedo esperando respuesta")
            w.close()

        usados = {self.port, self.wport, self.fport}
        # Se agregan los valores POR DEFECTO que trae el binario
        #   dword_91AA6C = 6768   y   dword_91AA80 = 1234
        # mas los puertos de mundo vistos en capturas reales.
        for pu in (list(range(16760, 16790)) + [1234, 6768, 21237, 21239]
                   + list(range(24125, 24160)) + list(range(29995, 30012))):
            if pu in usados:
                continue
            try:
                # Escuchar en TODAS las interfaces, no solo loopback: si el
                # cliente intenta conectar a la IP de red en vez de a
                # 127.0.0.1, un senuelo atado solo a loopback no lo ve y el
                # cliente se queda colgado esperando (que es lo que pasa).
                sx = await asyncio.start_server(
                    functools.partial(senuelo, p=pu), '0.0.0.0', pu)
                tareas.append(sx.serve_forever())
            except OSError:
                pass
        log.info("senuelos abiertos en los puertos vecinos")
        log.info("las sesiones se graban en logs/sesiones/ para poder analizarlas")
        # Sincronizar el cliente local (C:\AO\Angels Online):
        #   1. Crea backups .bak de update26.pak, START.EXE y reg.ini si no existen
        #   2. Aplica MODO_ESTACION ('normal' por defecto, quitando Navidad) en update26.pak y map/map041.mpc
        #   3. Registra e inyecta el consumible custom 83266 (Rank Promotion Medal, sprite 8921) en item9.xml
        #   4. Levanta los servidores locales FTP (2121) y HTTP auxiliar para el launcher START.EXE
        try:
            import cliente_local as _cl_loc
            _modo_est = _cl_loc.aplicar_modo_estacion()
            # La pantalla del logo de arranque. Se intenta en cada arranque
            # porque si el juego esta abierto el .pak esta bloqueado y hay
            # que dejarlo para la proxima.
            import configuracion as _cf_logo
            if getattr(_cf_logo, 'QUITAR_LOGO_ARRANQUE', True):
                _cl_loc.quitar_logo_arranque()
            if getattr(_cf_logo, 'RAMAS_SIN_EXCLUSION', True):
                _cl_loc.quitar_exclusion_ramas()
            _cl_loc.parchear_launcher()
            _srvs_launcher = await _cl_loc.iniciar_servidores_launcher()
            for _sl in _srvs_launcher:
                tareas.append(_sl.serve_forever())
            log.info(f"cliente local sincronizado (modo estacion: {_modo_est}, item 83266 activo)")
        except Exception as _e_loc:
            log.warning(f"no se pudo sincronizar cliente local: {_e_loc}")

        # El GM: por consola si se arranco desde una terminal, y por
        # data/gm.txt siempre.
        tareas.append(self._consola_gm())
        tareas.append(self._cola_gm())
        await asyncio.gather(*tareas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=16768)
    ap.add_argument('--wport', type=int, default=16769,
                    help='puerto del servidor de mundo (destino del redirect)')
    ap.add_argument('--fport', type=int, default=21238,
                    help='puerto del servidor de archivos (fport en server.xml)')
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()
    # El log iba SOLO a la consola, asi que en cuanto pasaba algo raro habia
    # que pedirle al usuario que copiara y pegara lineas a mano. Ahora ademas
    # se escribe en logs/hestia.log, que rota a los 20 MB y guarda tres.
    _fmt = logging.Formatter(
        '%(asctime)s [%(name)s] %(levelname)s: %(message)s')
    _nivel = logging.DEBUG if a.verbose else logging.INFO
    _raiz = logging.getLogger()
    _raiz.setLevel(_nivel)
    _con = logging.StreamHandler()
    _con.setFormatter(_fmt)
    _raiz.addHandler(_con)
    try:
        _dir = pathlib.Path(__file__).parent.parent / 'logs'
        _dir.mkdir(parents=True, exist_ok=True)
        _fh = logging.handlers.RotatingFileHandler(
            _dir / 'hestia.log', maxBytes=20 * 1024 * 1024, backupCount=3,
            encoding='utf-8')
        _fh.setFormatter(_fmt)
        _raiz.addHandler(_fh)
    except Exception as _e:
        log.warning('no se pudo abrir el log de fichero: %s', _e)
    try:
        asyncio.run(Servidor(a.host, a.port, a.fport, a.wport).correr())
    except KeyboardInterrupt:
        log.info("detenido")


if __name__ == '__main__':
    main()
