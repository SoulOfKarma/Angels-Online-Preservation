"""Territory Area: paralelos del MPC asignados al territorio conquistado."""
import cuentas
import gremios

AREAS = (50, 100, 117, 377)
_SALAS = {}
PORTALES = {50: (146, 70), 100: (179, 17), 117: (179, 17), 377: (179, 17)}


def portal(stage):
    return {'entity': 70_700_000 + int(stage), 'tile': PORTALES[int(stage)],
            'destino': 16, 'llegada': (100, 100), 'salir_territorio': True}


def paquetes(stage):
    import login
    p = portal(stage)
    return [login._map_object_spawn(p['entity'], 60001, p['tile'])]


def territorio_de_area(stage, paralelo):
    stage, paralelo = int(stage), int(paralelo)
    if stage in (50, 100) and 0 <= paralelo < 8:
        return 200 + paralelo
    if stage == 117 and 0 <= paralelo < 4:
        return 204 + paralelo
    if stage == 377 and paralelo in (0, 1):
        return (205, 207)[paralelo]
    return None


def paralelo_de(stage, territorio):
    for par in range(8):
        if territorio_de_area(stage, par) == int(territorio):
            return par
    return None


def area_y_paralelo(tw_stage: int):
    """Devuelve (stage_area, paralelo) para el campo conquistado tw_stage (200..207)."""
    tw = int(tw_stage)
    if tw in (205, 207):
        return (377, 0 if tw == 205 else 1)
    if tw in (204, 206):
        return (117, tw - 204)
    if tw in (200, 201, 202, 203):
        return (50, tw - 200)
    return (50, 0)


def autorizado(ses, stage, paralelo=None):
    p = getattr(ses, 'personaje', None)
    g = gremios.obtener_gremio_de(p.char_id) if p else None
    if not g:
        return False
    if paralelo is None and getattr(ses, 'paralelo_actual', None) is None:
        propios = cuentas.db_obtener_territorios_de_gremio(g['guild_id'])
        candidato = paralelo_de(stage, propios[0]) if propios else None
        if candidato is None:
            return False
        ses.paralelo_actual = candidato
    par = (getattr(ses, 'paralelo_actual', 0) or 0) if paralelo is None else paralelo
    tw = territorio_de_area(stage, par)
    return tw is not None and cuentas.db_obtener_dueno_de_territorio(tw) == int(g['guild_id'])


def clave(ses, stage):
    return (int(stage), 'territory', int(getattr(ses, 'paralelo_actual', 0) or 0))


def sala(ses):
    from app import _SalaDelMundo
    key = clave(ses, ses.personaje.stage)
    return _SALAS.setdefault(key, _SalaDelMundo(ses.personaje.stage))


def salida(ses):
    from totem_war import TW_A_CAMPO
    tw = territorio_de_area(ses.personaje.stage, getattr(ses, 'paralelo_actual', 0))
    return TW_A_CAMPO.get(tw, 16)
