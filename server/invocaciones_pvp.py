"""Targeting PvP aislado de la IA PvE y de los combos del jugador."""
import random
import struct


def tick(ses, inv, ahora):
    import app
    import combate
    import presencia
    import pvp_liga
    import transitable
    from codec import Msg

    if getattr(ses, 'desconectado', False) or getattr(ses, 'mapa_cargando', False):
        return False
    if inv.get('clon_sustituto'):
        return True  # Defensive substitute never acquires an offensive target.
    p = ses.personaje
    alcance = max(1, int(inv.get('atk_range', 1)))
    origen = (inv['tile_x'], inv['tile_y'])
    candidatos = []
    for otro in presencia._vivas(presencia.clave_de_mapa(ses, p.stage)):
        if otro is ses or getattr(otro, 'desconectado', False) or getattr(otro, 'mapa_cargando', False):
            continue
        q = otro.personaje
        distancia = max(abs(q.tile_x-origen[0]), abs(q.tile_y-origen[1]))
        if (inv.get('move_speed', 50) or 0) <= 0 and distancia > alcance:
            continue
        if (distancia <= max(alcance, 10)
                and max(abs(q.tile_x-p.tile_x), abs(q.tile_y-p.tile_y)) <= 15
                and not pvp_liga._por_que_no(ses, otro)):
            candidatos.append((distancia, q.char_id, otro))
    if not candidatos:
        inv.pop('objetivo_pvp', None)
        return False
    _, _, otro = min(candidatos, key=lambda c: (c[0], c[1]))
    q = otro.personaje
    inv['objetivo_pvp'] = q.char_id
    destino = (q.tile_x, q.tile_y)
    distancia = max(abs(destino[0]-origen[0]), abs(destino[1]-origen[1]))
    if distancia > alcance:
        speed = inv.get('move_speed', 50) or 0
        if speed > 0 and ahora-inv.get('ultimo_movimiento_pvp', 0) >= 0.3:
            final = transitable.avanzar(p.stage, origen, destino, 1, parar_a=alcance)
            if final != origen:
                pkt = Msg.registry[(0x0005, 's2c', '*')].build(
                    entity_id=inv['entity_id'], cur_x=origen[0]*32, cur_y=origen[1]*32,
                    dst_x=final[0]*32, dst_y=final[1]*32, speed=speed)
                ses.enviar(pkt)
                presencia.notificar_invocacion_movimiento(ses, inv['entity_id'], pkt)
                inv['tile_x'], inv['tile_y'] = final
                inv['ultimo_movimiento_pvp'] = ahora
        return True
    if not transitable.linea_libre(p.stage, origen, destino):
        return True
    cadencia = inv.get('cadencia') or max(0.65, min(1.0, 1.264-0.00477*inv.get('atk_speed', 80)))
    if ahora-inv.get('ultimo_ataque', 0) < cadencia:
        return True
    tipo, magia, efecto, mult = 656, False, 0, 1.0
    habilidades = [t for t in inv.get('skills', [])
                   if not (combate.datos_magia(t) or {}).get('no_jugadores')]
    if habilidades and ((inv.get('move_speed', 50) or 0) <= 0 or random.random() < 0.45):
        tipo = random.choice(habilidades)
        datos = combate.datos_magia(tipo) or {}
        magia = True
        efecto = combate.efecto_de_ataque(tipo) or datos.get('efecto', 148)
        mult = (float(datos.get('dano_base') or 200) /
                float(datos.get('base_denom') or 200))
        mult *= float(datos.get('dano_coef') or 100)/100
    stats = app._stats_ses(otro)
    defensa = struct.unpack_from('<I', stats, 54 if magia else 38)[0]
    ataque = inv.get('matk', inv.get('atk', 0)) if magia else inv.get('atk', 0)
    critico = random.random()*100 < inv.get('crit_rate', 5)
    if critico:
        mult *= 1.5
    dano = pvp_liga.dano_pvp(ataque, defensa, mult, 0.03)
    dano = max(1, int(dano*pvp_liga.mitigacion(otro, magia)))
    inv['ultimo_ataque'] = ahora
    pvp_liga._aplicar(ses, otro, dano, critico, True, tipo, efecto, magia,
                      origen_eid=inv['entity_id'])
    return True
