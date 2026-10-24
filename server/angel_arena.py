"""Persisted elimination matches on original map tags 100..105.

The modern spectator XML (8067..8089) identifies finals/4/8/16 arenas;
32/16/8/4/2/1 arrival sets exist in all three MPCs. Match assignment and
timeout policy are explicit configurable compatibility rules, not captured
official server code.
"""
import math
import random
import time


def habilitada(r):
    return bool(r and r.get('formato_arena') == 'eliminatorias')


def activos(r):
    return [cid for cid, m in r['miembros'].items() if not m['espectador']]


def motivo(r, a, b):
    arena = r.get('arena')
    if not arena:
        return 'Arena is awaiting the registration/start tick'
    if time.time() < arena['listos']:
        return 'Arena countdown'
    for duelo in arena['duelos']:
        if a in duelo['jugadores'] and b in duelo['jugadores']:
            return '' if not duelo.get('resuelto') else 'This match has ended'
    return 'Players belong to different Arena matches'


def casilla(r, cid):
    arena = r.get('arena')
    if not arena:
        return None
    import eventos
    centros = eventos.casillas_de_tag(r['stage'], arena['tag'])
    for i, duelo in enumerate(arena['duelos']):
        if cid in duelo['jugadores']:
            x, y = centros[i]
            # Adjacent to original tag, with separate positions for opponents.
            return x + (-1 if duelo['jugadores'].index(cid) == 0 else 1), y
    return None


def _preparar(r, ids):
    import competiciones as c
    now = time.time()
    n = 2**max(1, math.ceil(math.log2(max(2, len(ids)))))
    tag = 105-int(math.log2(n//2))
    # Distribute byes over separate matches instead of pairing empty slots.
    parejas = [[cid] for cid in ids[:n//2]]
    parejas += [[] for _ in range(n//2-len(parejas))]
    for i, cid in enumerate(ids[n//2:]):
        parejas[i].append(cid)
    cfg = r['arena_config']
    segundos = min(cfg['ronda_segundos'], max(1, (r['fin']-now)/max(1, math.log2(n))))
    r['arena'] = {'tag': tag, 'tamano': n, 'listos': now+cfg['cuenta_segundos'],
                  'fin': now+segundos,
                  'duelos': [{'jugadores': p, 'resuelto': len(p)<2,
                              'ganador': p[0] if len(p)==1 else None} for p in parejas]}
    c._guardar(r)
    c.anunciar('Angel Arena: top %d, countdown %d seconds.' % (n, cfg['cuenta_segundos']))
    sesiones = {str(s.personaje.char_id): s for s in c._sesiones()
                if s.personaje.stage == r['stage']}
    for cid in ids:
        if cid in sesiones:
            if getattr(sesiones[cid],'mapa_cargando',False):
                sesiones[cid]._competicion_revivir = True
            else:
                c._revivir(sesiones[cid])
            c._viajar(sesiones[cid], r, r['miembros'][cid])
            c.al_entrar(sesiones[cid])


def tick(r):
    import competiciones as c
    if not habilitada(r) or c.fase(r) != 'combate':
        return
    now = time.time()
    if not r.get('arena'):
        presentes = {str(s.personaje.char_id) for s in c._sesiones()
                     if s.personaje.stage == r['stage'] and not getattr(s, 'desconectado', False)}
        ids = []
        for cid in activos(r):
            if cid in presentes:
                ids.append(cid)
            else:
                r['miembros'][cid]['espectador'] = True
                r['miembros'][cid]['sin_puesto'] = True
        random.Random(r['id']).shuffle(ids)
        if not ids:
            c.terminar(r['stage'], 'empty round')
            return
        _preparar(r, ids)
    arena = r['arena']
    changed = False
    for duelo in arena['duelos']:
        if duelo['resuelto']:
            continue
        vivos = [cid for cid in duelo['jugadores'] if not r['miembros'][cid]['espectador']]
        if len(vivos) < 2:
            duelo.update(resuelto=True, ganador=vivos[0] if vivos else None)
            changed = True
        elif now >= arena['fin']:
            # No arbitrary HP/level tie-break or invented winner.
            duelo.update(resuelto=True, ganador=None)
            for cid in vivos:
                r['miembros'][cid]['espectador'] = True
                r['miembros'][cid]['sin_puesto'] = True
                r['eliminados'].append(cid)
            changed = True
    if changed:
        c._guardar(r)
        for ses in c._sesiones():
            if ses.personaje.stage == r['stage']:
                c.al_entrar(ses)
    if now < arena['listos']:
        return
    if all(d['resuelto'] for d in arena['duelos']):
        winners = [d['ganador'] for d in arena['duelos'] if d['ganador']]
        if len(winners) <= 1:
            r['campeon'] = winners[0] if winners else None
            c.terminar(r['stage'], 'last survivor' if winners else 'no survivors')
        else:
            _preparar(r, winners)


def esperando(r):
    return (not r.get('arena') or time.time() < r['arena']['listos']) if habilitada(r) else False


def abrir_menu(ses, addr):
    import app
    import competiciones as c
    m = c._miembro(c.ronda(ses.personaje.stage), ses)
    if m and not m['espectador']:
        c.aviso(ses, 'Active competitors cannot use spectator teleports. Use the exit to withdraw.')
        import dialogos
        g = [dialogos.armar_linea(8067, 0, [8072])[2:]]
        ses.dlg_ent, ses.dlg_guion, ses.dlg_paso = ses.personaje.entity_id, g, 1
        ses.dlg_mapa = {'stage':ses.personaje.stage, 'opciones':[(8072,0)], 'guion':g}
        ses.enviar(dialogos.linea_de(g, 0, ses.personaje.nombre))
    else:
        app._recorrer_dialogo_mapa(ses, addr, ses.personaje.stage, 8067)


def opcion(ses, opcion):
    import app
    import competiciones as c
    import eventos
    p = ses.personaje
    if p.stage not in c.ARENAS:
        return False
    if opcion == 8072:
        c.abandonar(ses, p.stage)
        app._sincronizar_cambio_mapa(ses, 114, 22, 36)
        return True
    tags = {8068:2, 8074:3, 8075:4, 8077:5, 8078:6, 8079:7, 8080:8,
            8081:9, 8082:10, 8083:11, 8084:12, 8085:13, 8086:14, 8087:15, 8088:16}
    if opcion not in tags:
        return False
    m = c._miembro(c.ronda(p.stage), ses)
    if m and not m['espectador']:
        c.aviso(ses, 'Only spectators can change observation areas.')
        return True
    tiles = eventos.casillas_de_tag(p.stage, tags[opcion])
    if tiles:
        app._viajar_dentro_del_mapa(ses, 'arena spectator', {'llegada': tiles[0]})
    return True
