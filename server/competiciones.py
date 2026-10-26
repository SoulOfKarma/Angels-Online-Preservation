"""Angel Arena / Holy Battlefield: rounds, admission and isolated PvP.

Schedules: IGG msg.xml 7565/7567/7596/8267/8268/8362..8369.
Fees260+: 4M/8M confirmed explicitly by Karma; conflicting English XML is
not used to silently multiply that cost. See the proxy admission notes.
Arena duration is a compatibility setting, not verified official data.
No invented automatic item/EXP rewards: results are persisted separately.
"""
import asyncio
import copy
import datetime as dt
import json
import logging
import math
import pathlib
import random
import time
import uuid

import cuentas

log = logging.getLogger('competiciones')
ARENAS = (159, 239, 240)
MAPAS = (112,) + ARENAS
TRAMOS = (
    (60, 89, 159, 0, 19, 30, 75000),
    (90, 119, 159, 1, 19, 30, 350000),
    (120, 149, 159, 2, 19, 30, 1200000),
    (150, 179, 159, 3, 19, 30, 6000000),
    (180, 209, 159, 4, 19, 30, 30000000),
    (210, 239, 159, 5, 19, 30, 75000000),
    (240, 259, 159, 6, 19, 30, 200000000),
    (260, 279, 239, 0, 19, 31, 4000000),
    (280, 299, 239, 1, 19, 31, 8000000),
    (300, 319, 239, 2, 19, 31, 8000000),
    (320, 339, 239, 3, 19, 31, 8000000),
    (340, 359, 239, 4, 19, 31, 8000000),
    (360, 379, 239, 5, 19, 31, 8000000),
    (380, 400, 239, 6, 19, 31, 8000000),
    (401, 10000, 240, 6, 19, 32, 8000000),
)
# Timed boxes 16762/16763 are deliberately NOT admitted as active passes.
PASES = {16764: 43200*60, 16765: 86400*60, 28866: 10080*60, 40921: 43200*60}
PIEDRAS = (8770, 24882, 8537)
CLERKS = {'Low-Tier Clerk': (159, 7550), 'Mid-Tier Clerk': (239, 7551),
          'High-Tier Clerk': (240, 7552), 'BattlefieldClerk': (112, 7581)}
CRISTALES = {1: (71112001, (218, 207), 60368), 2: (71112002, (100, 88), 60367)}
ENTREGAS = {112001: (1, (235, 208)), 112002: (2, (110, 81))}
# Original MPC tornado positions; direct lobby return is compatibility behavior.
SALIDAS_ARENA = ((62,35),(173,155),(74,155),(273,156),(149,193),(199,218),
    (150,144),(274,182),(199,118),(249,143),(200,269),(250,242),(300,218),
    (299,168),(300,117),(250,92),(199,68),(150,92),(99,117),(99,217),
    (149,242),(49,242),(101,269),(151,294),(251,294),(350,242),(350,192),
    (349,142),(349,92),(300,67),(251,42),(150,42),(50,92),(51,142),(50,192))
_RONDAS = {}
_BASE = None


class Rechazo(ValueError):
    def __init__(self,texto,dialogo=None):
        super().__init__(texto)
        self.dialogo = dialogo


def config_eventos():
    return json.loads((pathlib.Path(__file__).parent / 'plantillas' / 'competiciones_config.json').read_text(encoding='utf-8'))


def _modo_pruebas():
    """Fail closed: configuring unknown rewards cannot silently enable paid PvP."""
    cfg = config_eventos()
    if cfg.get('modo_pruebas') is not True:
        raise Rechazo('Official reward tables are not verified. Production competitions remain disabled.')
    return True


def _esquema(con):
    con.execute('CREATE TABLE IF NOT EXISTS competiciones (stage INTEGER PRIMARY KEY, datos TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS competiciones_resultados (ronda TEXT PRIMARY KEY, datos TEXT NOT NULL)')


def _cargar():
    global _BASE
    if _BASE == str(cuentas.DB_PATH):
        return
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            _esquema(con)
            rows = con.execute('SELECT stage, datos FROM competiciones').fetchall()
            con.commit()
        finally:
            con.close()
    _RONDAS.clear()
    _RONDAS.update({int(st): json.loads(data) for st, data in rows})
    _BASE = str(cuentas.DB_PATH)


def _guardar(r, resultado=False, actualizar_logros=True):
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            _esquema(con)
            data = json.dumps(r)
            con.execute('INSERT OR REPLACE INTO competiciones VALUES (?,?)', (r['stage'], data))
            if resultado:
                con.execute('INSERT OR REPLACE INTO competiciones_resultados VALUES (?,?)', (r['id'], data))
                __import__('competicion_premios').preparar(con,r)
            import competicion_logros
            logros_nuevos = competicion_logros.aplicar(con, r) if actualizar_logros else []
            con.commit()
        finally:
            con.close()
    _RONDAS[r['stage']] = r
    try:
        competicion_logros.publicar(logros_nuevos)
    except Exception:
        log.exception('Competition achievement notification (transaction already committed)')


def ronda(stage):
    _cargar()
    return _RONDAS.get(int(stage))


def fase(r, ahora=None):
    if not r or r.get('cerrada'):
        return 'cerrada'
    now = time.time() if ahora is None else ahora
    if now >= r['fin']:
        return 'cerrada'
    if now < r.get('registro_fin',r['inicio']):
        return 'registro'
    return 'preparacion' if now < r['inicio'] else 'combate'


def tramo(nivel):
    cap = __import__('combate').nivel_maximo()
    return next((t[:1]+(min(t[1],cap),)+t[2:] for t in TRAMOS if t[0] <= int(nivel) <= min(t[1],cap)), None)


def aviso(ses, texto):
    import clases
    ses.enviar(clases.aviso(str(texto), tipo=0))


def modo_arena(entity_id, activo):
    """Native Arena mode: property36 -> 005ffa00, not Totem War property22."""
    import struct
    return struct.pack('<HIBBII',0x001D,int(entity_id),1,36,int(bool(activo)),0)


def marcas_actor(ses,publico=False,quitar=False):
    """Native long38/1 supplies Holy team;42 sets the hostile faction bit."""
    import struct,presencia
    import holy_battlefield as hb
    p=ses.personaje
    r=ronda(p.stage)
    m=_miembro(r,ses)
    active=bool(not quitar and fase(r)=='combate' and m and not m['espectador'])
    if p.stage in ARENAS and __import__('angel_arena').esperando(r):active=False
    eid=presencia.entidad_de(ses) if publico else p.entity_id
    actors=[eid]+[inv['entity_id'] for key in ('invocacion','invocacion2','avatar_clon')
                  if (inv:=getattr(ses,key,None)) and inv.get('hp',0)>0]
    pet=getattr(p,'mascota',None)
    if pet and pet.get('fuera') and getattr(ses,'pet_entity_id',None):actors.append(ses.pet_entity_id)
    team=m['equipo'] if (not quitar and m and not m['espectador']
                         and p.stage==112 and fase(r)!='cerrada') else 0
    return [packet for actor in actors for packet in (
        hb.equipo(actor,team,actor!=eid),
        struct.pack('<HIBBII',0x001D,eid,1,42,actor,int(active)))]


def _sesiones():
    import app
    return list(app._tw_sesiones())


def anunciar(texto):
    import app, totem_war
    app._tw_difundir(totem_war.cartel_deslizante(texto))


def anunciar_resultados(r):
    """Native result notices, based only on the committed final placements."""
    import app, struct
    if r['stage'] not in ARENAS or not r.get('clasificacion') or r.get('motivo') in ('gm','gm stop','cancelled'):
        return
    ranking = [(i+1,r['miembros'][cid]['nombre']) for i,cid in enumerate(r['clasificacion'][:10])]
    anunciar('The Angel Arena event results are coming in.')
    anunciar('The results of the Angel Arena are coming... '+', '.join('%d place %s' % x for x in ranking))
    for place,name in ranking:
        # S2C0128 channel13 selects native banner variant1 (005f3b40).
        # This is separate from ordinary Super BC channel11 / variant0.
        author = name.encode('latin-1','replace')[:16].ljust(17,b'\0')
        message = ('0%d place : player %s.' % (place,name)).encode('latin-1','replace')+b'\0'
        app._tw_difundir(struct.pack('<HIB17s',0x0128,0,13,author)+message)


def _nombre_evento(r):
    return ('Holy Battlefield' if r['stage'] == 112 else
            'Angel Arena %d..%s' % (r['min'],r['max']))


def _avisar_registro(r, ahora):
    """One notice per five-minute milestone and at one minute; persisted.

    Use the current minute's window so a delayed tick/restart never emits
    a backlog of obsolete 10/5/1 notices. Opening already announced its minute.
    """
    minuto = math.ceil((r.get('registro_fin',r['inicio'])-ahora)/60)
    if minuto <= 0:
        return
    if 'avisos_registro' not in r:
        # Old rounds have no delivery history: don't replay their current notice.
        r['avisos_registro'] = [minuto]
        _guardar(r)
        return
    if (minuto != 1 and minuto % 5 != 0) or minuto in r['avisos_registro']:
        return
    r['avisos_registro'].append(minuto)
    _guardar(r)
    anunciar('%s: registration closes in %d minute%s. Enter via Sign-up Office.' %
             (_nombre_evento(r),minuto,'' if minuto == 1 else 's'))


def iniciar(stage, minutos, registro=15, nivel=401, por='gm', inicio=None, identidad=None):
    testing = _modo_pruebas()
    stage, minutos, registro = int(stage), int(minutos), int(registro)
    if stage not in MAPAS or not 1 <= minutos <= 120 or not 0 <= registro <= 60:
        raise Rechazo('Invalid map/time: duration 1..120 min, registration 0..60 min.')
    previous = ronda(stage)
    if fase(previous) != 'cerrada':
        raise Rechazo('A round is already open here. Stop it before opening another.')
    t = tramo(nivel) if stage in ARENAS else None
    if stage in ARENAS and (not t or t[2] != stage):
        raise Rechazo('This level belongs to a different Angel Arena tier.')
    cfg = config_eventos()
    preparation = max(0,min(60,int(cfg.get('arena_preparacion_segundos',60)))) if stage in ARENAS and registro else 0
    signup_end = time.time()+registro*60 if inicio is None else inicio-preparation
    start = signup_end+preparation
    restante_registro = max(0,math.ceil((signup_end-time.time())/60))
    r = {'id': identidad or uuid.uuid4().hex, 'stage': stage, 'inicio': start,
         'fin': start + minutos*60, 'registro_fin':signup_end, 'cerrada': False, 'por': por,
         'ingreso_tardio': por == 'gm' and registro == 0,
         'min': t[0] if t else 1, 'max': t[1] if t else 10000,
         'miembros': {}, 'puntos': {'1': 0, '2': 0}, 'portadores': {}, 'eliminados': []}
    r['avisos_registro'] = [restante_registro] if restante_registro else []
    r['prueba'] = testing
    r['cobrar_entrada_en_pruebas'] = bool(cfg.get('cobrar_entrada_en_pruebas',True))
    r['logros_habilitados'] = not testing or cfg.get('logros_en_pruebas', True)
    r['premios_config'] = copy.deepcopy(cfg.get('premios_holy' if stage == 112 else 'premios_arena'))
    r['holy_exp_config'] = copy.deepcopy(cfg.get('holy_exp')) if stage==112 else None
    r['arena_premio_compat'] = copy.deepcopy(cfg.get('arena_premio_compat')) if stage in ARENAS else None
    __import__('competicion_premios').validar_holy_exp(r['holy_exp_config'])
    __import__('competicion_premios').validar(r['premios_config'], holy=stage == 112)
    r['premios_en_pruebas'] = bool(cfg.get('premios_en_pruebas', False))
    if stage in ARENAS:
        r['formato_arena'] = cfg.get('formato_arena', 'supervivencia')
        r['arena_config'] = {'ronda_segundos': max(10, int(cfg.get('arena_ronda_segundos', 600))),
                             'cuenta_segundos': max(0, int(cfg.get('arena_cuenta_segundos', 5)))}
    if stage == 112:
        import holy_battlefield as hb
        r['edificios'] = hb.inicial()
    _guardar(r)
    anunciar('%s: registration open%s. Enter via Sign-up Office.' % (
        _nombre_evento(r),
        ' (GM test: battle already running)' if restante_registro == 0 else ' for %d minutes' % restante_registro))
    if testing:
        log.info('TEST ROUND: %s; achievements %s; no unverified item prizes.' % (
            'normal gold/stone admission' if r['cobrar_entrada_en_pruebas'] else 'free admission',
            'enabled' if r['logros_habilitados'] else 'disabled'))
    return r


def _miembro(r, ses):
    member = (r or {}).get('miembros', {}).get(str(ses.personaje.char_id))
    return member if member and __import__('competicion_identidad').coincide(member,ses) else None


def entrada(ses, stage, espectador=False):
    """Commit the fee/pass and round membership together; re-entry is free."""
    import app
    p = ses.personaje
    if p.stage != 114 or getattr(ses, 'muerto', False):
        raise Rechazo('Talk to the clerk at the Sign-up Office while alive.')
    r = ronda(stage)
    if fase(r) == 'cerrada':
        if stage in ARENAS:
            abiertas = [ronda(s) for s in ARENAS if fase(ronda(s)) != 'cerrada']
            detalle = '; '.join('%d..%d' % (x['min'],x['max']) for x in abiertas) or 'none'
            raise Rechazo('No Arena round for this clerk. Your real level: %d. Open brackets: %s.' % (p.nivel,detalle),7577)
        raise Rechazo('Holy Battlefield registration is closed.',7607)
    old = _miembro(r, ses)
    if str(p.char_id) in r['miembros'] and not old:
        raise Rechazo('Legacy character ID collision: another account owns this round entry.')
    if old:
        if stage in ARENAS and old.get('salio_en') and fase(r) == 'combate':
            old['espectador'] = True
            old['sin_puesto'] = True
        if not old['espectador'] and not r['min'] <= p.nivel <= r['max']:
            raise Rechazo('Your real level no longer fits this round.',7575)
        old.pop('salio_en', None)
        _guardar(r)
        _viajar(ses, r, old)
        return old
    if len(r['miembros']) >= 500:
        raise Rechazo('This round is full.',7613)
    if (stage in ARENAS and r.get('formato_arena') == 'eliminatorias' and not espectador
            and sum(m.get('competidor', not m['espectador']) for m in r['miembros'].values()) >= 64):
        raise Rechazo('The 64-player Arena bracket is full. You can watch.')
    if stage in ARENAS and r.get('arena') and not espectador:
        raise Rechazo('Arena matches have already been assigned. You can watch.')
    if not espectador and not r['min'] <= p.nivel <= r['max']:
        raise Rechazo('Your real level is outside this round\'s bracket.',7575)
    # Late admission is only allowed for explicit GM immediate-test rounds.
    if not espectador and fase(r) != 'registro' and not r.get('ingreso_tardio'):
        raise Rechazo('Registration has ended. You can watch the battle.',7607 if stage==112 else 7577)
    if not getattr(ses, 'usuario', None):
        raise Rechazo('Save/login this character before registration.')
    bag = dict(ses.inventario)
    counts = dict(app._cantidades(ses))
    improvements = copy.deepcopy(getattr(p, 'mejoras', None) or {})
    gold = old_gold = int(getattr(ses, 'oro', p.oro))
    original_bag = dict(bag)
    original_counts = dict(counts)
    consumed = []
    if r.get('prueba') and not r.get('cobrar_entrada_en_pruebas',False):
        pass  # Explicit free-test setting; old rounds retain their original terms.
    elif not espectador and stage == 112:
        now = time.time()
        live = []
        for slot, item in sorted(bag.items()):
            if 20 <= slot <= app._tope_bolsa(bag) and item in PASES:
                meta = improvements.setdefault(slot, {})
                deadline = meta.get('holy_pass_fin')
                if deadline is None:
                    # Compatibility for old items that never had a running timer:
                    # first admission activates the duration; it is never refreshed.
                    deadline = meta['holy_pass_fin'] = now + PASES[item]
                if deadline > now:
                    live.append(slot)
        if not live:
            slot = next((s for item in PIEDRAS for s, it in sorted(bag.items())
                         if 20 <= s <= app._tope_bolsa(bag) and it == item and counts.get(s, 1) > 0), None)
            if slot is None:
                raise Rechazo('You need an unexpired Battlefield Cursed Stone or a single-use stone.',7605)
            consumed.append(slot)
            qty = counts.get(slot, 1)
            if qty > 1:
                counts[slot] = qty-1
            else:
                bag.pop(slot)
                counts.pop(slot, None)
                improvements.pop(slot, None)
    elif not espectador:
        fee = tramo(p.nivel)[6]
        if gold < fee:
            raise Rechazo('Registration costs %d gold for your level.' % fee,7576)
        gold -= fee
    member = {'usuario':ses.usuario, 'nombre': p.nombre, 'nivel': p.nivel, 'equipo': 0, 'competidor': not espectador,
              'espectador': bool(espectador), 'bajas': 0, 'muertes': 0, 'cristales': 0}
    if stage == 112 and not espectador:
        def weight(team):
            members = [m for m in r['miembros'].values() if m['equipo'] == team and not m['espectador']]
            return len(members), sum(m['nivel'] for m in members)
        best = min(weight(1),weight(2))
        member['equipo'] = random.choice([team for team in (1,2) if weight(team)==best])
    new = copy.deepcopy(r)
    new['miembros'][str(p.char_id)] = member
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT datos FROM personajes WHERE char_id=? AND usuario=?',
                              (p.char_id, ses.usuario)).fetchone()
            if not row:
                raise Rechazo('Character not found; nothing has been charged.')
            current = json.loads(con.execute('SELECT datos FROM competiciones WHERE stage=?', (stage,)).fetchone()[0])
            if current != r:
                raise Rechazo('Registration changed; please retry. Nothing has been charged.')
            data = json.loads(row[0])
            if (int(data.get('oro', 0)) != old_gold
                    or not cuentas.inventario_equivalente(data,original_bag,original_counts)):
                raise Rechazo('Character inventory/gold changed. Save or reconnect and retry; nothing charged.')
            data.update(oro=gold, inventario={str(k): v for k, v in bag.items()},
                        cantidades={str(k): v for k, v in counts.items()},
                        mejoras={str(k): v for k, v in improvements.items()})
            con.execute('UPDATE personajes SET datos=? WHERE char_id=? AND usuario=?',
                        (json.dumps(data), p.char_id, ses.usuario))
            con.execute('UPDATE competiciones SET datos=? WHERE stage=?', (json.dumps(new), stage))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    _RONDAS[stage] = new
    ses.inventario.clear()
    ses.inventario.update(bag)
    p.inventario = ses.inventario
    app._cantidades(ses).clear()
    app._cantidades(ses).update(counts)
    p.mejoras = improvements
    ses.oro = p.oro = gold
    for slot in consumed:
        if slot not in bag:
            app._instancias(ses).pop(slot, None)
    cuentas._notificar_cambio()
    ses.enviar(*app._refrescar(ses, consumed, con_oro=True))
    _viajar(ses, new, member)
    return member


def _viajar(ses, r, member):
    import app, eventos
    if member['espectador'] or (r['stage'] in ARENAS and fase(r) in ('registro','preparacion')):
        tag = 1
    elif r['stage'] in ARENAS:
        import angel_arena
        tile = angel_arena.casilla(r, str(ses.personaje.char_id)) if angel_arena.habilitada(r) else None
        if tile:
            _reubicar(ses, r['stage'], tile)
            return
        if angel_arena.habilitada(r):
            tag = 1  # Original Waterfall waiting area, not a fighting cell.
        else:
            # Free-for-all shares one fighting platform, not the disconnected
            # spectator platforms2..13 used by the elimination format.
            tiles = eventos.casillas_de_tag(r['stage'],2)
            if not tiles:
                raise Rechazo('Missing Arena fighting platform.')
            _reubicar(ses,r['stage'],tiles[(int(ses.personaje.char_id)-1)%len(tiles)])
            return
    else:
        import holy_battlefield as hb
        tag = hb.spawn_tag(r, member['equipo']) if member.get('_reviviendo') else member['equipo']
    tiles = eventos.casillas_de_tag(r['stage'], tag)
    if not tiles:
        raise Rechazo('Missing map arrival; registration is saved, re-entry will not charge again.')
    _reubicar(ses, r['stage'], tiles[0])


def _reubicar(ses, stage, tile):
    """Same-map respawns/round changes never queue two client map loads."""
    import app
    if getattr(ses,'mapa_cargando',False):
        ses._competicion_reubicar = (stage,tuple(tile),(ronda(stage) or {}).get('id'))
        return
    if ses.personaje.stage != stage:
        app._sincronizar_cambio_mapa(ses,stage,*tile)
        return
    cerrar_dialogo(ses)
    app._viajar_dentro_del_mapa(ses,'competition',{'llegada':tile,'solo_0003':True})
    if getattr(ses,'_mapa_presencia',None) is not None:
        __import__('presencia').entrar(ses,stage)


def cerrar_dialogo(ses):
    import struct, dialogos
    if getattr(ses,'dlg_guion',None) or getattr(ses,'dlg_mapa',None):
        ses.enviar(struct.pack('<H',0x0012)+dialogos.FIN)
    for key in ('dlg_ent','dlg_mapa','dlg_guion','_holy_servicio','_competicion_clerk','_competicion_dialogo'):
        setattr(ses,key,None)
    ses.dlg_paso = 0


def antes_de_viajar(ses, stage):
    """Clear scene-specific UI BEFORE CHANGE_MAP, not behind its load barrier."""
    old = ses.personaje.stage
    if old in MAPAS+(114,) or stage in MAPAS+(114,):
        cerrar_dialogo(ses)
    if old == 112 and stage != 112:
        __import__('holy_battlefield').sincronizar_portador(ses,quitar=True)
        __import__('holy_battlefield').marcador(ses,ocultar=True)
    if old in MAPAS:
        ses.enviar(*marcas_actor(ses,quitar=True))
        __import__('presencia').notificar_companero_accion(ses,*marcas_actor(ses,True,True))
        if old in ARENAS:
            ses.enviar(modo_arena(ses.personaje.entity_id,False))
        elif old==112:
            import struct
            ses.enviar(struct.pack('<HIBBII',0x001D,ses.personaje.entity_id,1,62,0,0))
        ses.enviar(__import__('totem_war').modo_pvp(ses.personaje.entity_id,False))


def al_entrar(ses):
    import totem_war
    p = ses.personaje
    if not p:
        return
    if getattr(ses,'mapa_cargando',False):
        return
    ses.enviar(__import__('star_blessing').paquete(p))
    __import__('olympus').al_entrar(ses)
    __import__('arena_premios_compat').caducados(ses)
    old_stage = getattr(ses, '_competicion_stage', None)
    if old_stage in MAPAS and old_stage != p.stage:
        abandonar(ses, old_stage)
    ses._competicion_stage = p.stage if p.stage in MAPAS else None
    if p.stage not in MAPAS:
        if old_stage == 112 or getattr(ses,'_holy_marcador',False):
            __import__('holy_battlefield').marcador(ses, ocultar=True)
        if getattr(ses, 'competicion_pvp', False):
            ses.enviar(totem_war.modo_pvp(p.entity_id, False))
            ses.competicion_pvp = False
        __import__('daily_events').al_entrar(ses)
        return
    r = ronda(p.stage)
    m = _miembro(r, ses)
    if (p.stage==112 and m and r.get('cerrada')
            and not getattr(ses,'_holy_retorno',None)):
        ses._holy_retorno = (r['id'],r.get('finalizada',time.time()-10)+10,11)
    if not getattr(ses,'mapa_cargando',False):
        pendiente = ses.__dict__.pop('_competicion_reubicar',None)
        revivir = ses.__dict__.pop('_competicion_revivir',False)
        if pendiente and pendiente[0] == p.stage and pendiente[2] == (r or {}).get('id'):
            if revivir:
                _revivir(ses)
            _reubicar(ses,p.stage,pendiente[1])
    if p.stage == 112:
        import holy_battlefield as hb
        hb.sincronizar_monstruos(ses,r)
        hb.sincronizar_puertas(ses,r)
        hb.sincronizar_portador(ses,r)
        hb.marcador(ses, r)
    elif getattr(ses,'_holy_marcador',False):
        __import__('holy_battlefield').marcador(ses, ocultar=True)
    enabled = bool(fase(r) == 'combate' and m and not m['espectador'])
    if p.stage in ARENAS and __import__('angel_arena').esperando(r):
        enabled = False
    # Property22 is Totem War, NOT competition PvP. The server enforces
    # competition attacks; TEAMID supplies Holy's native orange/blue teams.
    ses.enviar(totem_war.modo_pvp(p.entity_id, False))
    ses.competicion_pvp = enabled
    if p.stage in ARENAS:
        ses.enviar(modo_arena(p.entity_id,enabled))
    elif p.stage==112:
        import struct
        ses.enviar(struct.pack('<HIBBII',0x001D,p.entity_id,1,62,int(enabled),0))
    ses.enviar(*marcas_actor(ses))
    __import__('presencia').notificar_companero_accion(ses,*marcas_actor(ses,True))
    # Reassert BOTH directions after each phase/spawn refresh. A joiner may
    # have seen the other actors during registration with hostility disabled.
    for other in _sesiones():
        if other is not ses and other.personaje.stage==p.stage:
            ses.enviar(*(__import__('presencia').para_receptor(ses,packet)
                         for packet in marcas_actor(other,True)))
    if not m:
        aviso(ses, 'You are not registered here. Return to Sign-up Office to join or watch.')
    else:
        aviso(ses, '%s; %s; team %d; %.0f min remaining.' % (
            'Holy Battlefield' if p.stage == 112 else 'Angel Arena', fase(r), m['equipo'],
            max(0, r['fin']-time.time())/60))


def abandonar(ses, stage=None):
    """Leaving/disconnecting cannot hide a carrier or keep an Arena contender alive."""
    p = getattr(ses, 'personaje', None)
    stage = stage or getattr(ses, '_competicion_stage', None)
    if not p or stage not in MAPAS:
        return
    r = ronda(stage)
    m = _miembro(r, ses)
    if fase(r) == 'cerrada' or not m:
        return
    m['salio_en'] = time.time()
    if stage in ARENAS and fase(r) == 'combate' and not m['espectador']:
        m['espectador'] = True
        m['sin_puesto'] = True
        if str(p.char_id) not in r['eliminados']:
            r['eliminados'].append(str(p.char_id))
    if stage == 112:
        import holy_battlefield as hb
        hb.soltar(r, ses)
        m['segmento_base'] = {k: int(m.get(k, 0)) for k in __import__('competicion_logros').METRICAS}
    else:
        r['portadores'] = {team: cid for team, cid in r['portadores'].items() if int(cid) != p.char_id}
    _guardar(r)
    if stage == 112:
        _publicar_cristales(r)


def portales(stage):
    if stage not in MAPAS:
        return []
    # MPC112 event92 -> CHANGE_MAP(114,3), in addition to tornado events1/2.
    tiles = (((311,8),(23,284),(39,55),(41,53),(44,52),(46,51),(48,50),
              (262,250),(264,248),(267,247),(269,246),(272,245),(274,244),(277,243))
             if stage == 112 else SALIDAS_ARENA)
    return [{'entity': 71500000 + stage*1000 + i, 'tile': tile,
             'destino': 114, 'llegada': (22, 36), 'preguntar': False, 'dibujar': True,
             'sprite': 60384 if stage==112 and i>=2 else 60001,
             'solo_clic': stage==112 and i>=2, 'solo_espectador': stage==112 and i>=2,
             'arena_menu': stage in ARENAS}
            for i, tile in enumerate(tiles)]


def portal_en(stage, x, y):
    return next((p for p in portales(stage) if not p.get('solo_clic')
                 and max(abs(x-p['tile'][0]), abs(y-p['tile'][1])) <= 1), None)


def poblar(stage):
    import login
    packets = [login._map_object_spawn(p['entity'], p['sprite'], p['tile']) for p in portales(stage)]
    if stage != 112:
        return packets
    r = ronda(112)
    import holy_battlefield as hb
    packets += [hb.objeto(eid, 60301 if str(team) in (r or {}).get('portadores', {}) else sprite, hb.posicion_cristal(r,team))
                for team, (eid, tile, sprite) in CRISTALES.items()]
    packets += [login._npc_spawn(112001, 2433, 'Angel Gabriel', (235,208), sprite=40042, klass=199, direccion=6),
                login._npc_spawn(112002, 1892, 'Angel Raphael', (110,81), sprite=40003, klass=199, direccion=6)]
    import holy_battlefield as hb
    return packets + hb.paquetes(r)


def activar_pase_nuevo(ses, slot, item):
    """New stacks start now; adding to an existing stack never extends it."""
    p = getattr(ses, 'personaje', None)
    if p and item in PASES:
        if p.mejoras is None:
            p.mejoras = {}
        p.mejoras.setdefault(slot, {}).setdefault('holy_pass_fin', time.time() + PASES[item])


def desellar_pase(ses, slot):
    """Unseal atomically: inventory and absolute deadline must survive together."""
    import app, inventario
    p = ses.personaje
    item = ses.inventario.get(slot)
    result = {16762:16764,16763:16765}.get(item)
    if not result or not 20<=slot<=app._tope_bolsa(ses.inventario):
        return False
    bag, counts = dict(ses.inventario),dict(app._cantidades(ses))
    qty = counts.get(slot,1)
    dest = slot if qty==1 else app._ranura_libre(bag)
    if dest is None:
        aviso(ses,'Clear one inventory slot before removing the seal. Nothing consumed.')
        return True
    improvements = copy.deepcopy(p.mejoras or {})
    if qty==1:
        bag.pop(slot)
        counts.pop(slot,None)
        improvements.pop(slot,None)
    else:
        counts[slot] = qty-1
    bag[dest],counts[dest] = result,1
    improvements[dest] = {'holy_pass_fin':time.time()+PASES[result]}
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT datos FROM personajes WHERE char_id=? AND usuario=?',(p.char_id,ses.usuario)).fetchone()
            if not row:
                con.rollback()
                return True
            data = json.loads(row[0])
            if not cuentas.inventario_equivalente(data,ses.inventario,app._cantidades(ses)):
                con.rollback()
                aviso(ses,'Inventory changed. Reconnect and retry; seal not consumed.')
                return True
            data.update(inventario={str(k):v for k,v in bag.items()},
                        cantidades={str(k):v for k,v in counts.items()},
                        mejoras={str(k):v for k,v in improvements.items()})
            con.execute('UPDATE personajes SET datos=? WHERE char_id=? AND usuario=?',(json.dumps(data),p.char_id,ses.usuario))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    ses.inventario.clear()
    ses.inventario.update(bag)
    p.inventario = ses.inventario
    app._cantidades(ses).clear()
    app._cantidades(ses).update(counts)
    p.mejoras = improvements
    app._instancias(ses)[dest] = inventario.instancia_nueva()
    ses.enviar(*app._refrescar(ses,{slot,dest}))
    cuentas._notificar_cambio()
    return True


def mover_pase_banco(p, origen, destino, *, desde_banco=False, hacia_banco=False,
                     intercambio=False):
    """Keep pass deadlines across bank moves without changing bank item tuples.

    Negative metadata slots -10001..-10048 are reserved for personal bank
    passes. They are never equipment/inventory slots or sent to the client.
    """
    mejoras = p.mejoras if p.mejoras is not None else {}
    p.mejoras = mejoras
    src = -10000-int(origen) if desde_banco else int(origen)
    dst = -10000-int(destino) if hacia_banco else int(destino)
    a = (mejoras.get(src) or {}).pop('holy_pass_fin', None)
    b = (mejoras.get(dst) or {}).pop('holy_pass_fin', None)
    for key in (src, dst):
        if key in mejoras and not mejoras[key]:
            mejoras.pop(key)
    if a is not None:
        mejoras.setdefault(dst, {})['holy_pass_fin'] = a
    if intercambio and b is not None:
        mejoras.setdefault(src, {})['holy_pass_fin'] = b
    keys=('arena_premio_fin','arena_premio_item','arena_premio_ronda','mall_fin','mall_item')
    a={k:mejoras.get(src,{}).pop(k) for k in keys if k in mejoras.get(src,{})}
    b={k:mejoras.get(dst,{}).pop(k) for k in keys if k in mejoras.get(dst,{})}
    if a:mejoras.setdefault(dst,{}).update(a)
    if intercambio and b:mejoras.setdefault(src,{}).update(b)


def depurar_pases(ses, ahora=None):
    """Expired activated passes vanish; their deadline travels with item metadata."""
    import app
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    now = time.time() if ahora is None else ahora
    slots = [s for s, item in list(ses.inventario.items()) if item in PASES
             and (p.mejoras.get(s) or {}).get('holy_pass_fin', float('inf')) <= now]
    if not slots:
        return
    for slot in slots:
        app._sacar(ses, slot, app._cant_de(ses, slot))
        p.mejoras.pop(slot, None)
    ses.enviar(*app._refrescar(ses, slots))
    if getattr(ses, 'usuario', None):
        app._guardar_bolsa(ses, p.char_id)


def motivo_pvp(ses, otro):
    """None outside these maps; otherwise '' means allowed, text means deny."""
    p, q = ses.personaje, otro.personaje
    if p.stage not in MAPAS:
        return None
    r = ronda(p.stage)
    a, b = _miembro(r, ses), _miembro(r, otro)
    if fase(r) != 'combate':
        return 'competition is not fighting'
    if not a or not b or a['espectador'] or b['espectador']:
        return 'unregistered player or spectator'
    if getattr(ses, 'muerto', False) or getattr(otro, 'muerto', False) or min(p.hp, q.hp) <= 0:
        return 'dead player'
    if p.stage == 112 and a['equipo'] == b['equipo']:
        return 'same Holy Battlefield team'
    if p.stage in ARENAS and __import__('angel_arena').habilitada(r):
        return __import__('angel_arena').motivo(r, str(p.char_id), str(q.char_id))
    return ''


def _revivir(ses):
    import app, combate, supremo
    p = ses.personaje
    ses.muerto = ses.fantasma = False
    ses._holy_camino=None
    ses._holy_salto_pendiente=None
    ses._token_choque=None
    ses.competicion_vida = int(getattr(ses, 'competicion_vida', 0)) + 1
    combate.rehidratar_transformaciones(p.buffs)
    p.hp, p.mp = app._vida_max(p), app._mana_max(p)
    ses.enviar(supremo.paquete_estado(p), combate.atributo(p.entity_id, p.hp, combate.KIND_HP),
               combate.atributo(p.entity_id, p.mp, combate.KIND_MP),
               __import__('struct').pack('<HIII', 0x000A, p.entity_id, 0, 0))
    ses.enviar(app._stats_ses(ses))


def baja(ses, otro):
    """Called instead of TW rewards after a PvP death in a competition."""
    r = ronda(ses.personaje.stage)
    a, b = _miembro(r, ses), _miembro(r, otro)
    if not a or not b:
        return
    a['bajas'] += 1
    if r['stage'] == 112 and otro.personaje.nivel > ses.personaje.nivel-10:
        import holy_battlefield as hb
        hb.score(r,ses.personaje.char_id,2)
    b['muertes'] += 1
    if r['stage'] == 112:
        import holy_battlefield as hb
        hb.soltar(r, otro)
    else:
        r['portadores'] = {team: cid for team, cid in r['portadores'].items()
                           if int(cid) != otro.personaje.char_id}
    if r['stage'] in ARENAS:
        b['espectador'] = True
        r['eliminados'].append(str(otro.personaje.char_id))
    _guardar(r)
    if r['stage'] in ARENAS and not __import__('angel_arena').habilitada(r):
        remaining = [m for m in r['miembros'].values() if not m['espectador']]
        if len(remaining) <= 1 and len(r['eliminados']) + len(remaining) >= 2:
            # Finish directly: do not teleport the victim to a waiting platform
            # immediately before CHANGE_MAP to the lobby.
            terminar(r['stage'],motivo='last survivor')
            return
    _revivir(otro)
    b['_reviviendo']=True
    _viajar(otro, r, b)
    b.pop('_reviviendo',None)
    al_entrar(otro)
    if r['stage'] == 112:
        _publicar_cristales(r)
    else:
        import angel_arena
        if angel_arena.habilitada(r):
            angel_arena.tick(r)
            return
        remaining = [m for m in r['miembros'].values() if not m['espectador']]
        if len(remaining) <= 1 and len(r['eliminados']) + len(remaining) >= 2:
            terminar(r['stage'], motivo='last survivor')


def terminar(stage, motivo='gm'):
    import app, totem_war
    r = ronda(stage)
    if not r or r.get('cerrada'):
        return False
    r['cerrada'] = True
    r['finalizada'] = time.time()
    r['motivo'] = motivo
    r['portadores'] = {}
    r['cristales_estado'] = {}
    if stage == 112:
        x, y = r['puntos']['1'], r['puntos']['2']
        r['ganador'] = 1 if x > y else 2 if y > x else 0
        presentes = {str(s.personaje.char_id) for s in _sesiones()
                     if s.personaje.stage==112 and not getattr(s,'mapa_cargando',False)}
        for cid,m in r['miembros'].items():
            m['presente_al_cierre'] = cid in presentes
    else:
        alive = [cid for cid, m in r['miembros'].items() if not m['espectador']]
        unresolved = ((__import__('angel_arena').habilitada(r) and motivo != 'last survivor')
                      or len(alive)>1)
        if unresolved:
            for cid in alive:
                r['miembros'][cid]['sin_puesto'] = True
            alive = []
        alive.sort(key=lambda cid: (-r['miembros'][cid]['bajas'], -r['miembros'][cid]['nivel'], int(cid)))
        r['clasificacion'] = [] if unresolved else [
            cid for cid in dict.fromkeys(alive + list(reversed(r['eliminados'])))
            if not r['miembros'][cid].get('sin_puesto')]
    _guardar(r, resultado=True)
    anunciar_resultados(r)
    if stage == 112:
        # Client string.xml 2147: a draw has no winning-side suffix.
        mensaje = 'The Holy Battlefield event ends now.'
        if r['ganador'] and motivo not in ('gm','gm stop','cancelled'):
            mensaje += ' Congratulations! %s won the event.' % {1:'Jabaly',2:'Raphael'}[r['ganador']]
        anunciar(mensaje)
    else:
        anunciar('Angel Arena ended (%s). Results saved.' % motivo)
    for ses in _sesiones():
        if getattr(ses.personaje, 'stage', None) == stage:
            if stage==112:
                import struct
                # Disable Holy's mode BEFORE TEAMID0; otherwise native UI
                # renders team0 as a green ring during the exit countdown.
                ses.enviar(struct.pack('<HIBBII',0x001D,ses.personaje.entity_id,1,62,0,0))
                __import__('holy_battlefield').sincronizar_portador(ses,r)
            ses.enviar(*marcas_actor(ses,quitar=True))
            __import__('presencia').notificar_companero_accion(ses,*marcas_actor(ses,True,True))
            ses.competicion_pvp = False
            ses.enviar(totem_war.modo_pvp(ses.personaje.entity_id, False))
            if getattr(ses, 'muerto', False):
                _revivir(ses)
            if stage in ARENAS:
                # Native mode refreshes music: do it AFTER removing death state.
                ses.enviar(modo_arena(ses.personaje.entity_id,False))
            if stage==112 and motivo not in ('gm','gm stop','cancelled'):
                # Claims are committed before the countdown; delivery is
                # idempotent and retries if the player disconnects/full bag.
                __import__('competicion_premios').entregar(ses, automatico=True)
                ses._holy_retorno = (r['id'],time.time()+10,10)
                aviso(ses,_texto_retorno_holy(10))
                __import__('holy_battlefield').marcador(ses,ocultar=True)
            else:
                app._sincronizar_cambio_mapa(ses, 114, 22, 36)
    return True


def _texto_retorno_holy(segundos):
    # Original client string.xml 2180 (also used after reconnect).
    return ('The event has now ended. You will be teleported out of the arena in %s seconds.'
            % segundos)


def tick_retornos():
    import app
    for ses in _sesiones():
        pending = getattr(ses,'_holy_retorno',None)
        if not pending:
            continue
        rid, deadline, last = pending
        r = ronda(112)
        if ses.personaje.stage!=112 or not r or r['id']!=rid or not r.get('cerrada'):
            ses._holy_retorno = None
            continue
        left = max(0,math.ceil(deadline-time.time()))
        if left < last:
            aviso(ses,_texto_retorno_holy(left))
            ses._holy_retorno = (rid,deadline,left)
        if not left and not getattr(ses,'mapa_cargando',False):
            ses._holy_retorno = None
            app._sincronizar_cambio_mapa(ses,114,22,36)


def _publicar_cristales(r):
    import combate, holy_battlefield as hb
    packets = [packet for team,(eid,tile,sprite) in CRISTALES.items()
               for packet in (combate.despawn_monstruo(eid),
                   hb.objeto(eid,60301 if str(team) in r['portadores'] else sprite,hb.posicion_cristal(r,team)))]
    for s in _sesiones():
        if s.personaje.stage == 112:
            hb.sincronizar_portador(s,r)
            s.enviar(*packets)
            hb.marcador(s,r)


def pulsar(ses, eid):
    portal = next((x for x in portales(ses.personaje.stage) if x['entity']==eid),None) if ses.personaje else None
    if portal and not portal['arena_menu']:
        p = ses.personaje
        member=_miembro(ronda(p.stage),ses)
        if portal.get('solo_espectador') and member and not member['espectador']:
            return True  # MPC112/event92 is click-only and requires TEAMID0.
        if max(abs(p.tile_x-portal['tile'][0]),abs(p.tile_y-portal['tile'][1]))<=3:
            __import__('app')._sincronizar_cambio_mapa(ses,114,*portal['llegada'])
        else:
            aviso(ses,'Move closer to the exit.')
        return True
    import holy_battlefield as hb
    if hb.pulsar(ses, eid):
        return True
    if hb.transferir_cristal(ses, eid):
        return True
    p = ses.personaje
    if not p or p.stage != 112 or eid not in ({x[0] for x in CRISTALES.values()} | set(ENTREGAS)):
        return False
    r = ronda(112)
    member = _miembro(r, ses)
    if fase(r) != 'combate' or not member or member['espectador'] or getattr(ses, 'muerto', False) or p.hp <= 0:
        aviso(ses, 'Only active Holy Battlefield competitors can capture crystals.')
        return True
    team = member['equipo']
    target = next(((t, hb.posicion_cristal(r,t)) for t, (entity, tile, _) in CRISTALES.items() if entity == eid), None)
    own, tile = target if target else ENTREGAS[eid]
    actual=hb.posicion_real(ses) if target else (p.tile_x,p.tile_y)
    if max(abs(actual[0]-tile[0]), abs(actual[1]-tile[1])) > (1 if target else 3):
        aviso(ses, 'Move closer to the crystal or your team\'s angel.')
        return True
    if target:
        if own == team:
            if r.get('cristales_estado',{}).get(str(own),{}).get('tile'):
                r['cristales_estado'].pop(str(own))
                hb.score(r,p.char_id,20)
                _guardar(r)
                _publicar_cristales(r)
            return True
        if str(own) in r['portadores'] or p.char_id in r['portadores'].values():
            return True
        r['portadores'][str(own)] = p.char_id
        state = r.setdefault('cristales_estado',{}).setdefault(str(own),{})
        state.pop('tile',None)
        state.pop('retorno',None)
        state['limite']=time.time()+300
        if p.char_id not in state.setdefault('participantes',[]):
            state['participantes'].append(p.char_id)
    else:
        enemy = str(3-team)
        if (own != team or r['portadores'].get(enemy) != p.char_id or str(team) in r['portadores']
                or r.get('cristales_estado',{}).get(str(team),{}).get('tile')):
            hb.mostrar(ses,7630 if own!=team else [7631,7632,7633],[],42 if own==1 else 3)
            return True
        r['portadores'].pop(enemy)
        r['puntos'][str(team)] += 1
        member['cristales'] += 1
        import holy_battlefield as hb
        hb.score(r,p.char_id,500)
        state = r.get('cristales_estado',{}).pop(enemy,{})
        for cid in state.get('participantes',[]):
            if cid!=p.char_id:
                hb.score(r,cid,20)
    _guardar(r)
    _publicar_cristales(r)
    if target and own!=team:
        hb.cartel(ses,"I have obtained %s's Crystal!" % ('Gabriel' if own==1 else 'Raphael'))
    if max(r['puntos'].values()) >= 20:
        terminar(112, motivo='20 crystals')
    return True


def opciones(ses, opcion):
    """Only intercept the root clerk's explicit join/watch/re-entry options."""
    import holy_battlefield as hb
    import angel_arena
    if angel_arena.opcion(ses, opcion):
        return True
    if hb.opcion(ses, opcion):
        return True
    if __import__('competicion_dialogos').opcion(ses,opcion):
        return True
    stage = getattr(ses, '_competicion_clerk', None)
    if ses.personaje.stage != 114 or stage not in MAPAS:
        return False
    joins = (7583, 7585) if stage == 112 else (7552,)
    watches = (7584,) if stage == 112 else (7553,)
    if opcion not in joins + watches + (7751,):
        return False
    if opcion == 7751:
        cantidad = __import__('competicion_premios').entregar(ses,stage=stage)
        if cantidad:
            # Original msg.xml delivery response. Install a fresh dialogue
            # script: the router has already consumed the root menu choice.
            __import__('competicion_dialogos').mostrar(ses,stage,7761)
        else:
            __import__('competicion_premios').informar_reclamacion(ses,stage)
        return True
    return False


def cron(ahora=None):
    """Original wall-clock hours, interpreted in the server's local timezone."""
    import configuracion
    _cargar()
    now = ahora or dt.datetime.now().astimezone()
    for stage, r in list(_RONDAS.items()):
        phase = fase(r, now.timestamp())
        if phase == 'registro':
            _avisar_registro(r,now.timestamp())
        if phase == 'preparacion' and not r.get('preparacion_anunciada'):
            r['preparacion_anunciada'] = True
            _guardar(r)
            anunciar('The sign-up for the Angel Arena event has now ended. The event will begin in 1 minutes time.')
        if not r['cerrada'] and phase == 'cerrada':
            terminar(stage, motivo='time limit')
        elif phase == 'combate' and not r.get('anunciado'):
            r['anunciado'] = True
            _guardar(r)
            anunciar('%s: registration closed. Battle begins!' % _nombre_evento(r))
            for ses in _sesiones():
                if ses.personaje.stage == stage:
                    member = _miembro(r,ses)
                    if (stage in ARENAS and member and not member['espectador']
                            and not __import__('angel_arena').habilitada(r)):
                        _viajar(ses,r,member)
                    al_entrar(ses)
        if phase == 'combate' and stage in ARENAS:
            import angel_arena
            angel_arena.tick(r)
            if r.get('arena') and not angel_arena.esperando(r) and not r['arena'].get('activada'):
                r['arena']['activada'] = True
                _guardar(r)
                for ses in _sesiones():
                    if ses.personaje.stage == stage:
                        al_entrar(ses)
    if _modo_pruebas():
        return  # GM tests only until official reward delivery is complete.
    windows = [(t[2], t[0], t[3], t[4], t[5], configuracion.DURACION_ANGEL_ARENA_MIN) for t in TRAMOS]
    windows += [(112, 1, day, hour, 0, 60) for day in (4, 6) for hour in (12, 21)]
    for stage, level, weekday, hour, minute, duration in windows:
        start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        identity = 'official-%d-%s' % (stage, start.isoformat())
        if (now.weekday() == weekday and start-dt.timedelta(minutes=15) <= now < start
                and fase(_RONDAS.get(stage), now.timestamp()) == 'cerrada'
                and (_RONDAS.get(stage) or {}).get('id') != identity):
            iniciar(stage, duration, 15, level, por='horario', inicio=start.timestamp(), identidad=identity)


async def reloj():
    while True:
        try:
            cron()
            try:
                __import__('daily_events').cron()
            except Exception:
                log.exception('Daily Events clock')
            try:
                __import__('elementary').cron()
            except Exception:
                log.exception('Angel Elementary clock')
            try:
                __import__('league_war').cron()
            except Exception:
                log.exception('League War clock')
            import holy_battlefield as hb
            hb.tick_cristales()
            tick_retornos()
            for ses in _sesiones():
                depurar_pases(ses)
                __import__('olympus').tick(ses)
                __import__('arena_premios_compat').caducados(ses)
                __import__('item_mall').caducados(ses)
                __import__('competicion_premios').entregar(ses, automatico=True)
        except Exception:
            log.exception('competition clock')
        await asyncio.sleep(1)


def comando_gm(ses, cmd, argumentos):
    """Start opens registration; it never teleports the GM."""
    import configuracion
    args = list(argumentos)
    holy = cmd.startswith('hb') or cmd in ('holybf', 'holybattlefield')
    action = 'start' if cmd.endswith('start') else 'stop' if cmd.endswith('stop') else (args.pop(0).lower() if args else 'status')
    try:
        if action == 'start':
            duration = int(args.pop(0)) if args else (60 if holy else configuracion.DURACION_ANGEL_ARENA_MIN)
            level = int(args.pop(0)) if args and not holy else ses.personaje.nivel
            signup = int(args.pop(0)) if args else 15
            if args:
                raise ValueError('too many arguments')
            bracket = tramo(level)
            stage = 112 if holy else bracket[2] if bracket else 0
            r = iniciar(stage, duration, signup, level)
            aviso(ses, 'Round opened in map %d; registration %d min, battle %d min. GM position unchanged.' % (
                r['stage'], signup, duration))
        elif action == 'stop':
            level = int(args.pop(0)) if args and not holy else ses.personaje.nivel
            if args:
                raise ValueError('too many arguments')
            bracket = tramo(level)
            stage = 112 if holy else bracket[2] if bracket else 0
            aviso(ses, 'Round stopped.' if terminar(stage, 'gm stop') else 'No open round.')
        elif action == 'status' and not args:
            for stage in ((112,) if holy else ARENAS):
                r = ronda(stage)
                aviso(ses, 'Map %d: %s; levels %s..%s; %d registered.' % (
                    stage,fase(r),(r or {}).get('min','-'),(r or {}).get('max','-'),len((r or {}).get('miembros', {}))))
        elif action in ('lobby', 'enter', 'join', 'watch', 'begin', 'finish'):
            import app
            if getattr(ses,'mapa_cargando',False) and action in ('lobby','enter','join','watch'):
                raise Rechazo('Wait until the current map has finished loading.')
            level = int(args.pop(0)) if args and not holy else ses.personaje.nivel
            if args:
                raise ValueError('too many arguments')
            bracket = tramo(level)
            stage = 112 if holy else bracket[2] if bracket else 0
            r = ronda(stage)
            if action == 'lobby' or (action in ('enter', 'join', 'watch') and ses.personaje.stage != 114):
                aviso(ses, 'Going to Sign-up Office. After loading, use /%s %s again to enter.' %
                      ('hb' if holy else 'aa', 'watch' if action == 'watch' else 'enter'))
                app._sincronizar_cambio_mapa(ses, 114, 22, 36)
            elif action in ('enter', 'join', 'watch'):
                entrada(ses, stage, espectador=action == 'watch')
            elif action == 'begin':
                if fase(r) != 'registro':
                    raise Rechazo('No registration period is open.')
                duration = r['fin']-r['inicio']
                r['inicio'] = time.time()
                r['registro_fin'] = r['inicio']
                r['fin'] = r['inicio']+duration
                _guardar(r)
                cron(dt.datetime.fromtimestamp(time.time()).astimezone())
            elif action == 'finish':
                if fase(r) != 'combate':
                    raise Rechazo('No battle is running.')
                terminar(stage, motivo='gm test finish')
        else:
            raise ValueError('unknown action')
    except ValueError as exc:
        aviso(ses, '%s. Usage: /aastart [battle_min] [level] [registration_min] | /hbstart [battle_min] [registration_min]; /aastop [level], /hbstop.' % exc)
