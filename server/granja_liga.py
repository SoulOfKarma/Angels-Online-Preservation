"""Acceso y aislamiento de Farm (501), por liga y con retorno persistente."""
import functools
import pathlib
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


@functools.lru_cache(maxsize=1)
def coordenadas_de_parcela(plot_id: int):
    import sys
    tools = pathlib.Path(__file__).resolve().parent.parent / 'tools'
    if str(tools) not in sys.path:
        sys.path.append(str(tools))
    import mapa_del_cliente
    mapa = mapa_del_cliente.mapa(STAGE)
    pts = mapa.tags.get(plot_id) if mapa else None
    return tuple(pts[0]) if pts else None


@functools.lru_cache(maxsize=1)
def catalogo_cultivos():
    import house_services as hs
    return hs.xml_rows('crops.xml')


def info_cultivo(crop_id: int):
    cat = catalogo_cultivos()
    return cat.get(int(crop_id)) or cat.get(1)


def poblar_cultivos(ses):
    """Devuelve los paquetes de spawn (0x0008) de todos los cultivos de la liga."""
    g = liga_autorizada(ses)
    if not g:
        return []
    import login as _lg
    cultivos = cuentas.db_obtener_cultivos_gremio(g['guild_id'])
    pkgs = []
    for c in cultivos:
        coord = coordenadas_de_parcela(c['plot_id'])
        if not coord:
            continue
        c_info = info_cultivo(c['crop_id'])
        sprite = int(c_info.get('\u5916\u89c0\u7de8\u865f', 66908) or 66908)
        nombre = str(c_info.get('\u540d\u7a31', 'Crop'))
        eid = CROP_BASE_EID + int(c['plot_id'])
        pkgs.append(_lg.spawn_invocacion(eid, c['crop_id'], nombre, coord, sprite=sprite))
    return pkgs


def plantar(ses, plot_id: int, crop_id: int = 1):
    """Siembra un cultivo en la parcela especificada."""
    import time
    import clases
    p = getattr(ses, 'personaje', None)
    g = liga_autorizada(ses)
    if not p or not g:
        return False
    if not 1 <= plot_id <= 200:
        return False
    existente = cuentas.db_obtener_cultivo(g['guild_id'], plot_id)
    now = int(time.time())
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
    if coord:
        import login as _lg
        sprite = int(c_info.get('\u5916\u89c0\u7de8\u865f', 66908) or 66908)
        nombre = str(c_info.get('\u540d\u7a31', 'Crop'))
        eid = CROP_BASE_EID + plot_id
        spawn_pkt = _lg.spawn_invocacion(eid, crop_id, nombre, coord, sprite=sprite)
        ses.enviar(spawn_pkt)
    ses.enviar(clases.aviso(f"Planted {nombre} on plot {plot_id}!", tipo=0))
    return True


def regar(ses, entity_id: int, app_server=None):
    """C2S 0x014D: riega el cultivo seleccionado."""
    import time, clases
    p = getattr(ses, 'personaje', None)
    g = liga_autorizada(ses)
    if not p or not g:
        return
    plot_id = entity_id - CROP_BASE_EID
    c = cuentas.db_obtener_cultivo(g['guild_id'], plot_id)
    if not c:
        return
    now = int(time.time())
    if now >= c['marchita_en']:
        ses.enviar(clases.aviso("The produce has already withered.", tipo=0))
        return
    c_info = info_cultivo(c['crop_id'])
    max_riego = int(c_info.get('\u6f86\u6c34\u6b21\u6578', 15) or 15)
    if c['riego_count'] >= max_riego:
        ses.enviar(clases.aviso("This produce has reached its maximum watering limit.", tipo=0))
        return
    cuentas.db_actualizar_riego_cultivo(g['guild_id'], plot_id)
    import combate as _cb
    exp_ganada = 150 * max(1, int(getattr(p, 'nivel', 1) or 1))
    p.exp = max(int(getattr(p, 'exp', 0) or 0), _cb.exp_para_nivel(p.nivel)) + exp_ganada
    ses.enviar(_cb.exp_paquete(p.entity_id, exp_ganada))
    c_nom = c_info.get('\u540d\u7a31', 'Crop')
    ses.enviar(clases.aviso(f"Watered {c_nom} successfully (+{exp_ganada} EXP)!", tipo=0))


def abonar(ses, entity_id: int, app_server=None):
    """C2S 0x014E: abona el cultivo seleccionado."""
    import time, clases
    p = getattr(ses, 'personaje', None)
    g = liga_autorizada(ses)
    if not p or not g:
        return
    plot_id = entity_id - CROP_BASE_EID
    c = cuentas.db_obtener_cultivo(g['guild_id'], plot_id)
    if not c:
        return
    now = int(time.time())
    if now >= c['marchita_en']:
        ses.enviar(clases.aviso("The produce has already withered.", tipo=0))
        return
    c_info = info_cultivo(c['crop_id'])
    max_abono = int(c_info.get('\u65bd\u80a5\u6b21\u6578', 15) or 15)
    if c['abono_count'] >= max_abono:
        ses.enviar(clases.aviso("This produce has reached its maximum fertilizer limit.", tipo=0))
        return
    cuentas.db_actualizar_abono_cultivo(g['guild_id'], plot_id)
    import combate as _cb
    sk_exp_ganada = 100
    ses.enviar(_cb.skill_exp_paquete(p.entity_id, sk_exp_ganada))
    c_nom = c_info.get('\u540d\u7a31', 'Crop')
    ses.enviar(clases.aviso(f"Fertilized {c_nom} successfully (+{sk_exp_ganada} Skill EXP)!", tipo=0))


def cosechar(ses, entity_id: int, app_server=None):
    """C2S 0x014F: cosecha el cultivo seleccionado."""
    import time, clases, combate as _cb
    p = getattr(ses, 'personaje', None)
    g = liga_autorizada(ses)
    if not p or not g:
        return
    plot_id = entity_id - CROP_BASE_EID
    c = cuentas.db_obtener_cultivo(g['guild_id'], plot_id)
    if not c:
        return
    now = int(time.time())
    if now < c['madura_en']:
        rem_s = c['madura_en'] - now
        ses.enviar(clases.aviso(f"The produce is still growing ({rem_s} seconds remaining).", tipo=0))
        return
    if now >= c['marchita_en']:
        ses.enviar(clases.aviso("The produce has withered and cannot be harvested.", tipo=0))
        cuentas.db_eliminar_cultivo(g['guild_id'], plot_id)
        ses.enviar(_cb.despawn_monstruo(entity_id))
        return

    c_info = info_cultivo(c['crop_id'])
    item_recompensa = int(c_info.get('\u6536\u6210\u52d5\u614b\u8cc7\u6599', 9366) or 9366)
    cant_base = int(c_info.get('\u4fdd\u969c\u63a1\u6536\u91cf', 3) or 3)
    bonus = min(5, (c['riego_count'] + c['abono_count']) // 4)
    total_cant = cant_base + bonus

    cuentas.db_eliminar_cultivo(g['guild_id'], plot_id)
    ses.enviar(_cb.despawn_monstruo(entity_id))

    try:
        import app as _app_srv
        tocadas = []
        r = _app_srv._meter(ses, item_recompensa, total_cant)
        if r is not None:
            tocadas.append(r)
            ses.enviar(*_app_srv._refrescar(ses, tocadas))
            _app_srv._guardar_bolsa(ses, p.char_id)
        exp_ganada = 1000 * max(1, int(getattr(p, 'nivel', 1) or 1))
        p.exp = max(int(getattr(p, 'exp', 0) or 0), _cb.exp_para_nivel(p.nivel)) + exp_ganada
        ses.enviar(_cb.exp_paquete(p.entity_id, exp_ganada))
    except Exception:
        pass

    c_nom = c_info.get('\u540d\u7a31', 'Crop')
    ses.enviar(clases.aviso(f"Harvested {total_cant}x {c_nom}!", tipo=0))

