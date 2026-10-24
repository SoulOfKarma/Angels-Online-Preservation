"""New matches, GM controls and original achievements in temporary accounts."""
import copy
import json
import sqlite3

import pytest

from test_competiciones import world, stored
import angel_arena
import app
import competicion_logros as al
import competiciones as c
import holy_battlefield as hb
import logros
import presencia


def counters(world, ses):
    return stored(world, ses).get('logros_cont', {})


def test_holy_score_crystal_achievements_persist_once_and_survive_reload(world):
    c.iniciar(112, 60, 0)
    a, b = world.player(items={20:8537}), world.player(items={20:8537})
    for s in (a,b):
        c.entrada(s,112)
    r = c.ronda(112)
    r['miembros']['1'].update(score=500, cristales=1)
    c._guardar(r)
    data = stored(world,a)
    assert {137,138,139,140,141,142,148,149,160} <= set(data['logros'])
    assert counters(world,a)['hb:score'] == 500
    c._guardar(r)
    c._BASE = None
    c._guardar(c.ronda(112))
    assert counters(world,a)['hb:cristales'] == 1
    assert counters(world,a)['hb:score'] == 500
    assert set(a.personaje.logros) == set(data['logros'])


def test_holy_single_round_resets_on_exit_but_cumulative_does_not(world):
    c.iniciar(112, 60, 0)
    a = world.player(items={20:8537})
    c.entrada(a,112)
    r = c.ronda(112)
    r['miembros']['1']['cristales'] = 3
    c._guardar(r)
    c.abandonar(a,112)
    r['miembros']['1']['cristales'] = 5
    c._guardar(r)
    assert counters(world,a)['hb:cristales'] == 5
    assert counters(world,a)['hb:cristales:best'] == 3
    assert 161 not in stored(world,a).get('logros', [])  # not four in one continuous session
    assert 164 in stored(world,a)['logros']


def test_offline_win_count_and_cancel_are_idempotent(world):
    for motive, expected in [('20 crystals',1), ('gm stop',1)]:
        c.iniciar(112,60,0)
        a, b = world.player(items={20:8537}), world.player(items={20:8537})
        for s in (a,b):
            c.entrada(s,112)
        r = c.ronda(112)
        r['puntos']['1'] = 20
        c._guardar(r)
        world.players.clear()  # Both offline; no session needed for persistence.
        c.terminar(112,motive)
        assert counters(world,a).get('hb:win',0) == (1 if motive=='20 crystals' else 0)
        assert not c.terminar(112,motive)


def test_all_original_competition_rules_are_measured():
    for f in logros.tabla():
        if f['regla'] in ('聖域戰場規則','戰天使擂台'):
            assert al.medir(f,{}) is not None, f


def elimination(world, monkeypatch, n):
    cfg = c.config_eventos()
    monkeypatch.setattr(c,'config_eventos',lambda:dict(cfg,formato_arena='eliminatorias'))
    c.iniciar(240,30,0,410)
    players = [world.player() for _ in range(n)]
    for s in players:
        c.entrada(s,240)
    angel_arena.tick(c.ronda(240))
    return players


def test_modern_arena_duels_countdown_wrong_opponent_and_advancement(world, monkeypatch):
    players = elimination(world,monkeypatch,4)
    r = c.ronda(240)
    assert r['arena']['tag'] == 104 and len(r['arena']['duelos']) == 2
    a,b = [world.players[int(cid)-1] for cid in r['arena']['duelos'][0]['jugadores']]
    other = next(s for s in players if s not in (a,b))
    assert c.motivo_pvp(a,b) == 'Arena countdown'
    world.now[0] += 6
    assert c.motivo_pvp(a,b) == ''
    assert c.motivo_pvp(a,other) == 'Players belong to different Arena matches'
    first_duels = copy.deepcopy(r['arena']['duelos'])
    for duel in first_duels:
        winner,loser = [players[int(cid)-1] for cid in duel['jugadores']]
        c.baja(winner,loser)
    r = c.ronda(240)
    assert r['arena']['tag'] == 105
    world.now[0] += 6
    winner, loser = [players[int(cid)-1] for cid in r['arena']['duelos'][0]['jugadores']]
    c.baja(winner,loser)
    assert c.ronda(240)['cerrada']
    assert 254 in stored(world,winner)['logros']
    assert counters(world,winner)['aa:win'] == 1
    assert counters(world,loser).get('aa:win',0) == 0
    assert counters(world,winner)['aa:qualified'] == 1


def test_match_timeout_never_invents_a_champion(world, monkeypatch):
    players = elimination(world,monkeypatch,2)
    world.now[0] = c.ronda(240)['arena']['fin']+1
    angel_arena.tick(c.ronda(240))
    assert c.ronda(240)['cerrada']
    for s in players:
        assert counters(world,s).get('aa:win',0) == 0


def test_registration_disconnect_allows_return_before_start(world):
    c.iniciar(240,30,15,410)
    a = world.player()
    c.entrada(a,240)
    c.abandonar(a,240)
    assert not c.ronda(240)['miembros']['1']['espectador']
    a.personaje.stage = 114
    c.entrada(a,240)
    assert not c.ronda(240)['miembros']['1']['espectador']


def test_gm_begin_and_enter_preserve_registration_and_map_loading(world):
    a = world.player(items={20:8537})
    c.comando_gm(a,'hbstart',['60','15'])
    assert c.fase(c.ronda(112)) == 'registro'
    c.comando_gm(a,'hb',['enter'])
    assert a.personaje.stage == 112
    c.comando_gm(a,'hb',['begin'])
    assert c.fase(c.ronda(112)) == 'combate'


def test_spectator_visibility_is_asymmetric_and_notifications_hidden(world, monkeypatch):
    c.iniciar(112,60,0)
    a,b = world.player(items={20:8537}),world.player()
    c.entrada(a,112)
    c.entrada(b,112,True)
    sent = []
    monkeypatch.setattr(presencia,'_mandar',lambda ses,*pk: sent.append(ses))
    monkeypatch.setattr(presencia,'_spawn',lambda ses:b'player')
    monkeypatch.setattr(presencia,'_vestir',lambda ses:[])
    monkeypatch.setattr(presencia,'paquetes_mascota',lambda ses:[])
    presencia._presentar(a,b)
    assert sent and all(s is b for s in sent)
    sent.clear()
    presencia._presentar(b,a)
    presencia.notificar_equipo(b)
    presencia.mover(b,0,0,32,32)
    assert not sent


def test_spectator_arena_portal_shows_original_menu(world, monkeypatch):
    c.iniciar(240,30,0,410)
    s = world.player()
    c.entrada(s,240,True)
    angel_arena.abrir_menu(s,'test')
    assert [x[0] for x in s.dlg_mapa['opciones']] == [8068,8069,8070,8071,8072,8073]
    trips = []
    monkeypatch.setattr(app,'_viajar_dentro_del_mapa',lambda *a:trips.append(a))
    assert angel_arena.opcion(s,8068)
    assert trips[0][2]['llegada'] == (179,156)


def test_reward_ledger_is_atomic_retry_safe_and_frozen(world, monkeypatch):
    import competicion_premios as premios
    monkeypatch.setattr(app,'_stats_ses',lambda ses:b'')
    c.iniciar(112,60,0)
    a,b = world.player(items={20:8537}),world.player(items={20:8537})
    for s in (a,b):
        c.entrada(s,112)
    r = c.ronda(112)
    r['premios_config'] = [{'nivel_min':1,'nivel_max':10000,'resultado':'ganador',
                            'oro':123,'items':[{'id':8536,'cantidad':2}]}]
    r['puntos']['1']=20
    c._guardar(r)
    original = a.oro
    c.terminar(112,'20 crystals')
    assert a.oro == original+123
    assert sum(a.cantidades[s] for s,it in a.inventario.items() if it==8536) == 2
    assert premios.entregar(a) == 0
    assert a.oro == original+123
    with sqlite3.connect(world.db) as con:
        assert con.execute("SELECT estado FROM competiciones_premios WHERE char_id=1").fetchone()[0] == 'entregado'


def test_unknown_official_reward_is_never_substituted_when_compat_disabled(world,monkeypatch):
    import competicion_premios as premios
    cfg = c.config_eventos()
    monkeypatch.setattr(c,'config_eventos',lambda:dict(cfg,holy_exp=None))
    c.iniciar(112,60,0)
    a,b = world.player(items={20:8537}),world.player(items={20:8537})
    for s in (a,b):
        c.entrada(s,112)
    c.terminar(112,'time limit')
    assert premios.entregar(a) == 0
    with sqlite3.connect(world.db) as con:
        assert con.execute("SELECT estado FROM competiciones_premios WHERE char_id=1").fetchone()[0] == 'sin_tabla'


def test_holy_native_team_chat_does_not_leak_to_enemies_or_spectators(world):
    c.iniciar(112,60,15)
    a,b,ally,watch = [world.player(items={20:8537}) for _ in range(4)]
    for s in (a,b,ally):
        c.entrada(s,112)
    c.entrada(watch,112,True)
    world.now[0]=c.ronda(112)['inicio']+1
    for s in world.players:
        s.packets.clear()
    hb.chat_equipo(a,'Strategy')
    assert a.packets and ally.packets
    assert not b.packets and not watch.packets


def test_all_arena_match_arrivals_use_walkable_tiles():
    import eventos
    import transitable
    for stage in c.ARENAS:
        for tag in range(100,106):
            for x,y in eventos.casillas_de_tag(stage,tag):
                assert transitable.se_pisa(stage,x-1,y)
                assert transitable.se_pisa(stage,x+1,y)


def test_holy_team_property_sent_for_existing_players_on_join(world):
    import struct
    c.iniciar(112,60,0)
    a = world.player(items={20:8537})
    c.entrada(a,112)
    pkt = presencia._vestir(a)[0]
    assert struct.unpack('<HIBBII',pkt) == (0x001D,presencia.entidad_de(a),1,38,1,1)


def test_reward_full_bag_keeps_gold_and_claim_pending_until_retry(world, monkeypatch):
    import competicion_premios as premios
    monkeypatch.setattr(app,'_stats_ses',lambda ses:b'')
    c.iniciar(112,60,0)
    a,b = world.player(items={20:8537}),world.player(items={20:8537})
    for s in (a,b):
        c.entrada(s,112)
    a.inventario.update({slot:8536 for slot in range(20,app._tope_bolsa(a.inventario)+1)})
    world.save(a)
    r = c.ronda(112)
    r['premios_config'] = [{'nivel_min':1,'nivel_max':10000,'resultado':'ganador',
                           'oro':123,'items':[{'id':8536,'cantidad':2}]}]
    r['puntos']['1']=20
    c._guardar(r)
    c.terminar(112,'20 crystals')
    original = a.oro
    assert premios.entregar(a) == 0
    assert a.oro == original
    with sqlite3.connect(world.db) as con:
        assert con.execute("SELECT estado FROM competiciones_premios WHERE char_id=1").fetchone()[0] == 'pendiente'
    a.inventario.pop(20)
    world.save(a)
    assert premios.entregar(a) == 1
    assert a.oro == original+123


def test_arena_start_does_not_send_respawn_before_map_ready(world, monkeypatch):
    cfg = c.config_eventos()
    monkeypatch.setattr(c,'config_eventos',lambda:dict(cfg,formato_arena='eliminatorias'))
    c.iniciar(240,30,0,410)
    a,b = world.player(),world.player()
    for s in (a,b):
        c.entrada(s,240)
        s.mapa_cargando = True
        s.packets.clear()
    angel_arena.tick(c.ronda(240))
    assert not any(pkt[:2] in (b'\x03\x00',b'\x0a\x00') for pkt in a.packets)
    assert a._competicion_reubicar
    a.mapa_cargando = False
    c.al_entrar(a)
    assert not getattr(a,'_competicion_reubicar',None)
    assert (a.personaje.tile_x,a.personaje.tile_y) == angel_arena.casilla(c.ronda(240),'1')
