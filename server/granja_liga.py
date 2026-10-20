"""Acceso y aislamiento de Farm (501), por liga y con retorno persistente."""
import functools
import pathlib
import struct
import time
import cuentas
import gremios

STAGE = 501
NIVEL_MINIMO = 6
PORTAL_ENTIDAD = 70_050_001
PORTAL_TILE = (97, 8)  # farm.mpc: objeto 60001, evento 1 -> LEAVE_FARM.
_SALAS = {}


@functools.lru_cache(maxsize=1)
def llegada():
    import sys
    tools = pathlib.Path(__file__).resolve().parent.parent / 'tools'
    if str(tools) not in sys.path:
        sys.path.append(str(tools))
    import mapa_del_cliente
    mapa = mapa_del_cliente.mapa(STAGE)
    points = mapa.tags.get(255) if mapa else None
    if not points:
        raise ValueError('Falta el TAG de entrada de farm.mpc')
    return tuple(points[0])


def liga_autorizada(ses):
    p = getattr(ses, 'personaje', None)
    g = gremios.obtener_gremio_de(p.char_id) if p else None
    return g if g and int(g['nivel']) >= NIVEL_MINIMO else None


def clave(ses):
    g = liga_autorizada(ses)
    if g:
        return (STAGE, 'league', int(g['guild_id']))
    return (STAGE, 'unauthorized', int(getattr(ses.personaje, 'char_id', 0)))


def sala(ses):
    from eventos_mundo import EstadoDeMapa
    key = clave(ses)
    if key not in _SALAS:
        _SALAS[key] = EstadoDeMapa(STAGE)
    return _SALAS[key]


def guardar_retorno(ses):
    p = ses.personaje
    if p.stage == STAGE:
        return
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            con.execute('INSERT OR REPLACE INTO liga_farm_retorno '
                        '(char_id, guild_id, stage, x, y) VALUES (?, ?, ?, ?, ?)',
                        (p.char_id, liga_autorizada(ses)['guild_id'], p.stage, p.tile_x, p.tile_y))
            con.commit()
        finally:
            con.close()


def retorno(ses):
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            row = con.execute('SELECT stage, x, y FROM liga_farm_retorno WHERE char_id=?',
                              (ses.personaje.char_id,)).fetchone()
        finally:
            con.close()
    return tuple(int(n) for n in row) if row and int(row[0]) != STAGE else (41, 186, 69)


CROP_BASE_EID = 70_500_000


def coordenadas_de_parcela(plot_id: int):
    return _parcelas().get(int(plot_id))


@functools.lru_cache(maxsize=1)
def catalogo_cultivos():
    import house_services as hs
    return hs.xml_rows('crops.xml')


def info_cultivo(crop_id: int):
    cat = catalogo_cultivos()
    return cat.get(int(crop_id)) or {}


def paquete_cultivo(entity_id, crop_id, nombre, tile, sprite, maduro=False):
    """s2c 0x015D: un cultivo de la granja (sacado con REA el 19/10/2026).

    El manejador del cliente (FUN_005f68f0) crea la entidad con la misma
    cabecera que el NPC del 0x0008 (FUN_005ef410: id, flags, x, y, nombre,
    sprite...) y le pone la clase 0x80002004, que es la que hace que al
    pinchar en ella se abra la ventana de la granja (CreateFarmControl,
    FUN_00673820) con Regar / Abonar / Cosechar. Despues lee dos campos
    propios: el byte del +43 del cuerpo (+0x208 de la entidad; los cursores
    de la granja lo miran como == 1, aqui "listo para cosechar") y el u32 del
    +44 (+0x20c), que es el id de crops.xml con el que indexa su tabla.

    El u16 del +38 va a cero: si no, el cliente le pone otro cursor antes de
    llegar a la rama del cultivo.
    """
    b = bytearray(48)
    # LA POSICION VA EN PIXELES. El 0x015D y el 0x000E crean la entidad con la
    # misma rutina (FUN_005ef410; el manejador del 0x000E, 005ef5c0, es solo
    # esa llamada), y los 2.711 0x000E capturados del oficial llevan pixeles
    # en +8/+12. Con casillas, las 70 parcelas salian en la esquina (54,36)
    # PIXELES del mapa y en la granja no se veia nada (20/10/2026).
    px = _pixel_de_casilla().get((int(tile[0]), int(tile[1])),
                                 (int(tile[0]) * 32 + 16, int(tile[1]) * 32 + 16))
    # EL CULTIVO, AL CENTRO DE LA PARCELA. La tierra se ancla en la esquina de
    # arriba del rombo y la planta en su base: en la misma posicion la planta
    # salia en la esquina (visto el 20/10/2026). La parcela mide 3 casillas.
    dy = 0 if int(sprite or 0) in (SPRITE_TIERRA, SPRITE_TIERRA_MOJADA) else DESPLAZAMIENTO_CULTIVO_Y
    struct.pack_into('<IIII', b, 0, int(entity_id), 0, int(px[0]), int(px[1]) + dy)
    n = str(nombre).encode('latin-1', 'replace')[:16]
    b[16:16 + len(n)] = n
    struct.pack_into('<I', b, 34, int(sprite or 66908))
    b[43] = 1 if maduro else 0
    # REA 00673820 -> 0058f030: este valor se reenvia en 014D/014E/014F.
    # Es la instancia seleccionada, no el indice del catalogo de semillas.
    struct.pack_into('<I', b, 44, parcela_de_entidad(entity_id) or 0)
    return struct.pack('<H', 0x015D) + bytes(b)


def poblar_cultivos(ses):
    """Devuelve los paquetes de spawn (0x0008) de todos los cultivos de la liga."""
    g = liga_autorizada(ses)
    if not g:
        return []
    import login as _lg
    cultivos = cuentas.db_obtener_cultivos_gremio(g['guild_id'])
    # En la granja no hay NPC: solo la tierra de las parcelas y el tornado
    # de salida. El "Farming Clerk" que habia aqui era inventado.
    pkgs = paquetes_parcelas(mojadas={int(c['plot_id']) for c in cultivos
                                      if time.time() < c['marchita_en']
                                      and int(c.get('riego_count') or 0) > 0},
                             ocupadas={int(c['plot_id']) for c in cultivos
                                       if time.time() < c['marchita_en']})
    for c in cultivos:
        if time.time() >= c['marchita_en']:
            continue
        coord = coordenadas_de_parcela(c['plot_id'])
        if not coord:
            continue
        c_info = info_cultivo(c['crop_id'])
        sprite = sprite_de_etapa(c['crop_id'], c['sembrado_en'], c['madura_en'])
        nombre = str(c['char_name'])
        eid = CROP_BASE_EID + int(c['plot_id'])
        pkgs.append(paquete_cultivo(eid, c['crop_id'], nombre, coord, sprite,
                                    maduro=time.time() >= c['madura_en']))
        from farm_mecanicas import paquete_estado_cultivo
        pkgs.append(paquete_estado_cultivo(c))
        from farm_mecanicas import programar_cultivo
        programar_cultivo(ses, c['plot_id'], c['crop_id'], c['sembrado_en'], c['madura_en'], c['marchita_en'])
    return pkgs


_SEMILLAS = {}
CAT_SEMILLA = '農場種子'      # 農場種子
PARCELAS = range(1, 201)                      # TAG 1..200 de farm.mpc
PARCELAS_CULTIVO = range(1, 71)               # 60005; las 130 restantes son 60035.
RADIO_PARCELA = 4


def cultivo_de_semilla(item_id: int):
    """El cultivo (id de crops.xml) que planta ese item, o None si no es semilla.

    Las semillas del cliente son de categoria 農場種子 y formula de uso 26, con
    el cultivo en 動態資料1: War Rose Seed 24113 -> 6, Lvl 1 Warfruit Seed
    24380 -> 50, etc.
    """
    item_id = int(item_id)
    if item_id not in _SEMILLAS:
        r = None
        try:
            import sqlite3
            import inventario as _inv
            db = pathlib.Path(__file__).resolve().parent.parent / 'corpus' / 'content.db'
            con = sqlite3.connect(db)
            try:
                fila = _inv.fila_item(con, '"物品類別", "動態資料1"', item_id)
            finally:
                con.close()
            if fila and str(fila[0] or '') == CAT_SEMILLA and str(fila[1] or '').isdigit():
                r = int(fila[1])
        except Exception:
            r = None
        _SEMILLAS[item_id] = r
    return _SEMILLAS[item_id]


@functools.lru_cache(maxsize=1)
def _parcelas():
    """{plot_id: (x, y)} de los TAG 1..200 de farm.mpc."""
    import sys
    tools = pathlib.Path(__file__).resolve().parent.parent / 'tools'
    if str(tools) not in sys.path:
        sys.path.append(str(tools))
    import mapa_del_cliente
    mapa = mapa_del_cliente.mapa(STAGE)
    salida = {}
    for plot in PARCELAS:
        pts = mapa.tags.get(plot) if mapa else None
        if pts:
            salida[plot] = tuple(pts[0])
    return salida


PARCELA_BASE_EID = 70_600_000


@functools.lru_cache(maxsize=1)
def _pixel_de_casilla():
    """{(x, y) casilla de la parcela: (px, py)} EXACTOS del objeto del .mpc.

    La casilla del TAG esta redondeada y se desvia hasta 15 pixeles del
    centro real de la parcela: puestas por casilla, las 70 salian torcidas
    (visto en el juego el 20/10/2026). La x del .mpc vale tal cual y la y se
    cuenta desde ABAJO del mapa, asi que se le da la vuelta con el alto."""
    import sys
    tools = pathlib.Path(__file__).resolve().parent.parent / 'tools'
    if str(tools) not in sys.path:
        sys.path.append(str(tools))
    import mapa_del_cliente
    m = mapa_del_cliente.mapa(STAGE)
    if not m:
        return {}
    return {tuple(o['tile']): (int(o['px'][0]), m.alto * 32 - int(o['px'][1]))
            for o in m.objetos if o['id'] in (60005, 60035)}


@functools.lru_cache(maxsize=1)
def _objetos_parcela():
    """{plot_id: (sprite, px)}: la TIERRA de cada parcela. farm.mpc trae 200
    objetos (130 del 60035 y 70 del 60005) y caen uno a uno en las casillas
    de los TAG 1..200; el servidor no los mandaba y la granja salia pelada."""
    import sys
    tools = pathlib.Path(__file__).resolve().parent.parent / 'tools'
    if str(tools) not in sys.path:
        sys.path.append(str(tools))
    import mapa_del_cliente
    m = mapa_del_cliente.mapa(STAGE)
    por_tile = {tuple(o['tile']): o for o in (m.objetos if m else [])
                if o['id'] in (60035, 60005)}
    return {plot: (por_tile[t]['id'], tuple(por_tile[t]['px']))
            for plot, t in _parcelas().items() if t in por_tile}


# La TIERRA de las parcelas. server.obd del cliente: los objetos de granja son
# de la clase SERV_CLASS_FARMOBJ -- 66901 "土地原型" (tierra), 66902 "土地乾裂"
# (seca y agrietada, la que se ve en los videos del oficial), 66903 "土地濕潤"
# (regada), 66904..66907 crecimiento / marchito / brote / siembra y 66908 en
# adelante los cultivos de crops.xml. Los 60005/60035 que el .mpc pone en esas
# casillas son "TAG01"/"TAG03" con SP_ATTRIB_HIDE: marcadores invisibles.
SPRITE_TIERRA = 66902
# 66903 "土地濕潤": la tierra REGADA. Se pone al regar y vuelve a la seca
# cuando el cultivo se cosecha del todo o se marchita.
SPRITE_TIERRA_MOJADA = 66903


# Cuanto mas abajo va la planta que la tierra. Cabeceras SHP (UPDATE8.PAK):
# la tierra 23-060-RU0 mide 193x98 con el anclaje en (96,48), el CENTRO del
# rombo; las plantas lo llevan en la BASE (girasol 27-083-2U0 80x115 ancla
# (39,114); siembra 23-060-WU0 68x41 ancla (32,22)). Con los mismos pixeles
# la base de la planta ya cae en el centro de la parcela: el +48 de antes la
# bajaba media parcela y salia fuera.
DESPLAZAMIENTO_CULTIVO_Y = 0

# Etapas de crecimiento (server.obd): 66907 播種 siembra, 66906 發芽 brote,
# 66904 生長 creciendo y, ya madura, el 外觀編號 del crops.xml (el fruto).
SPRITE_SIEMBRA, SPRITE_BROTE, SPRITE_CRECIENDO = 66907, 66906, 66904
SIEMBRA_SEGUNDOS = 5


def cambios_de_etapa(sembrado, madura):
    """Instantes en que el cultivo cambia de sprite: brote, creciendo, maduro."""
    # La siembra (un monticulo) dura poco: enseguida sale el brote, que es
    # lo que se reconoce como planta; creciendo desde la mitad.
    d = max(0, int(madura) - int(sembrado))
    return [int(sembrado) + min(SIEMBRA_SEGUNDOS, d // 3), int(sembrado) + d // 2, int(madura)]


def sprite_de_etapa(crop_id, sembrado, madura, ahora=None):
    import time
    ahora = time.time() if ahora is None else ahora
    brote, creciendo, maduro = cambios_de_etapa(sembrado, madura)
    if ahora >= maduro:
        return int(info_cultivo(crop_id).get('外觀編號') or 66908)
    if ahora >= creciendo:
        return SPRITE_CRECIENDO
    if ahora >= brote:
        return SPRITE_BROTE
    return SPRITE_SIEMBRA


def paquete_tierra(plot, mojada=False):
    """La tierra de UNA parcela, seca o regada."""
    tile = _parcelas().get(int(plot))
    if not tile:
        return b''
    return paquete_cultivo(PARCELA_BASE_EID + int(plot), 0, '', tile,
                           SPRITE_TIERRA_MOJADA if mojada else SPRITE_TIERRA)


def paquetes_parcelas(ocupadas=(), mojadas=()):
    """La tierra de las 70 parcelas (PARCELAS_CULTIVO): s2c 0x015D con el
    sprite de tierra, entidad PARCELA_BASE_EID + N. Es permanente: el cultivo
    va en su propia entidad (CROP_BASE_EID + N) encima. Antes eran la misma y
    al plantar la parcela desaparecia. El +44 sale N en las dos (el indice de
    la ficha del 0x015F)."""
    return [paquete_cultivo(PARCELA_BASE_EID + plot, 0, '', tile,
                            SPRITE_TIERRA_MOJADA if plot in mojadas else SPRITE_TIERRA)
            for plot, tile in sorted(_parcelas().items()) if plot in PARCELAS_CULTIVO]


def parcela_de_entidad(eid):
    """La parcela N de la tierra (PARCELA_BASE_EID+N) o de su cultivo (CROP_BASE_EID+N)."""
    eid = int(eid or 0)
    for base in (PARCELA_BASE_EID, CROP_BASE_EID):
        if eid - base in PARCELAS_CULTIVO:
            return eid - base
    return None


def parcela_libre_cercana(ses):
    """La parcela libre mas cercana al jugador (a RADIO_PARCELA casillas), o None."""
    import time
    g = liga_autorizada(ses)
    p = ses.personaje
    if not g:
        return None
    ocupadas = {int(c['plot_id']) for c in cuentas.db_obtener_cultivos_gremio(g['guild_id'])
                if int(time.time()) < int(c.get('marchita_en', 0) or 0)}
    candidatas = []
    for plot, (x, y) in _parcelas().items():
        if plot not in PARCELAS_CULTIVO:
            continue
        d = max(abs(x - p.tile_x), abs(y - p.tile_y))
        if d <= RADIO_PARCELA and plot not in ocupadas:
            candidatas.append((d, plot))
    return min(candidatas)[1] if candidatas else None


def plantar_semilla(ses, crop_id: int, objetivo=None) -> bool:
    """Planta con una semilla de la mochila. True si se planto (y hay que gastarla)."""
    import clases
    p = ses.personaje
    if int(getattr(p, 'stage', 0)) != STAGE:
        ses.enviar(clases.aviso('Seeds can only be planted in your league farm.', tipo=0))
        return False
    if not liga_autorizada(ses):
        ses.enviar(clases.aviso('Your league must reach level 6 to use the farm.', tipo=0))
        return False
    plot = parcela_de_entidad(objetivo) if objetivo else None
    if plot is None:
        plot = parcela_libre_cercana(ses)
    if plot is None:
        ses.enviar(clases.aviso('Stand next to an empty plot of farmland to plant.', tipo=0))
        return False
    return plantar(ses, plot, crop_id)


def plantar(ses, plot_id: int, crop_id: int = 1):
    """Siembra un cultivo en la parcela especificada."""
    import time
    import clases
    p = getattr(ses, 'personaje', None)
    g = liga_autorizada(ses)
    if not p or not g or int(getattr(p, 'stage', 0)) != STAGE:
        return False
    coord = coordenadas_de_parcela(plot_id)
    if plot_id not in PARCELAS_CULTIVO or not coord or max(abs(coord[0] - p.tile_x), abs(coord[1] - p.tile_y)) > RADIO_PARCELA:
        return False
    if not info_cultivo(crop_id):
        return False
    existente = cuentas.db_obtener_cultivo(g['guild_id'], plot_id)
    now = int(time.time())
    if any(c['char_id'] == p.char_id and now < c['marchita_en']
           for c in cuentas.db_obtener_cultivos_gremio(g['guild_id'])):
        ses.enviar(clases.aviso('Harvest your previous crop before planting another seed.', tipo=0))
        return False
    if existente:
        if now < existente['marchita_en']:
            ses.enviar(clases.aviso("This plot of land already has a crop growing.", tipo=0))
            return False
    c_info = info_cultivo(crop_id)
    dur_madura = int(c_info.get('\u719f\u6210\u6642\u9593', 180) or 180)
    madura_en = now + dur_madura
    marchita_en = now + dur_madura * 3
    cuentas.db_guardar_cultivo(g['guild_id'], plot_id, p.char_id, p.nombre,
                               crop_id, now, madura_en, marchita_en)
    coord = coordenadas_de_parcela(plot_id)
    nombre = str(c_info.get('\u540d\u7a31', 'Crop')).strip()
    if coord:
        import login as _lg
        # Recien plantado: la siembra, no el fruto (ese sale al madurar).
        sprite = SPRITE_SIEMBRA
        eid = CROP_BASE_EID + plot_id
        spawn_pkt = paquete_cultivo(eid, crop_id, p.nombre, coord, sprite)
        from farm_mecanicas import difundir, programar_cultivo, paquete_estado_cultivo
        import combate as _cb_pl
        # Por si quedaba un cultivo viejo con ese id; la tierra no se toca.
        difundir(ses, _cb_pl.despawn_monstruo(eid), spawn_pkt,
                 paquete_estado_cultivo(cuentas.db_obtener_cultivo(g['guild_id'], plot_id)))
        programar_cultivo(ses, plot_id, crop_id, now, madura_en, marchita_en)
    ses.enviar(clases.aviso(f"Planted {nombre} on plot {plot_id}!", tipo=0))
    return True


def regar(ses, entity_id: int, app_server=None):
    from farm_mecanicas import accion
    return accion(ses, entity_id, 'water')


def abonar(ses, entity_id: int, app_server=None):
    from farm_mecanicas import accion
    return accion(ses, entity_id, 'fertilize')


def cosechar(ses, entity_id: int, app_server=None):
    from farm_mecanicas import accion
    return accion(ses, entity_id, 'harvest')

