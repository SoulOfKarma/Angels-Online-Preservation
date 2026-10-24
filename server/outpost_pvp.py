"""Permanent faction PvP in Outpost Battlefield 47/48; no timed-war rewards.

Portal events 901..906 and arrival tags come from original map047/map048.mpc.
Event 905 chooses an original field landing; 906 returns to the player's city,
not the last conditional branch in the editor (which would always be Iron).
"""
import random

MAPAS = (47, 48)
CIUDADES = {1: 3, 2: 29, 3: 38, 4: 26}
FACCION_BASE = {901: 1, 902: 4, 903: 2, 904: 3}


def es_mapa(stage):
    return int(stage or 0) in MAPAS


def al_salir(ses):
    """Clear this mode before another map enables its own PvP mode."""
    import totem_war
    p = getattr(ses, 'personaje', None)
    if p and not es_mapa(p.stage) and getattr(ses, 'outpost_modo_pvp', False):
        ses.enviar(totem_war.modo_pvp(p.entity_id, False))
        ses.outpost_modo_pvp = False


def al_entrar(ses):
    import totem_war
    p = getattr(ses, 'personaje', None)
    if p and es_mapa(p.stage):
        ses.outpost_modo_pvp = True
        ses.enviar(totem_war.modo_pvp(p.entity_id, True))


def resolver_portal(ses, portal):
    """Return a fresh resolved portal, or None if its faction disallows it."""
    import clases, eventos, totem_war
    p = ses.personaje
    if not es_mapa(p.stage):
        return None
    event = int(portal.get('outpost_evento', 0))
    faction = totem_war.codigo_faccion(p)
    if event in FACCION_BASE and faction != FACCION_BASE[event]:
        ses.enviar(clases.aviso('This portal leads to another faction\'s base.', tipo=0))
        return None
    if event == 906:
        destination, tag = CIUDADES.get(faction, 41), 1
    elif event == 905 or event in FACCION_BASE:
        destination, tag = p.stage, int(portal['outpost_tag'])
    else:
        return None
    tiles = eventos.casillas_de_tag(destination, tag)
    if not tiles:
        ses.enviar(clases.aviso('Missing original portal arrival. No travel performed.', tipo=0))
        return None
    # The original field tag has 24 landings; do not funnel every entry to one.
    tile = random.choice(tiles) if event == 905 else tiles[0]
    result = dict(portal, destino=destination, llegada=tuple(tile))
    return result
