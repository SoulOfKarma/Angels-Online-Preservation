"""Competition integration in a temporary database, never real accounts."""
import copy
import datetime as dt
import json
import pathlib
import sqlite3
import struct
import sys
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
import app
import combate
import competiciones as c
import configuracion
import cuentas
import login
import presencia
import pvp_liga


@pytest.fixture
def world(tmp_path, monkeypatch):
    db = tmp_path / 'events.db'
    monkeypatch.setattr(cuentas, 'DB_PATH', db)
    monkeypatch.setattr(cuentas, '_notificar_cambio', lambda **kw: None)
    monkeypatch.setattr(c, '_BASE', None)
    monkeypatch.setattr(c, '_RONDAS', {})
    # Stable default for tests asserting team-specific mechanics; production
    # randomizes tied teams. Explicit randomness tests override this.
    monkeypatch.setattr(c.random, 'choice', lambda xs: xs[0])
    # Exercise paid admission/official scheduling in isolation; production
    # remains fail-closed until its missing official reward tables are supplied.
    monkeypatch.setattr(c, '_modo_pruebas', lambda: False)
    original_config = c.config_eventos
    monkeypatch.setattr(c, 'config_eventos', lambda: dict(original_config(), formato_arena='supervivencia',arena_preparacion_segundos=0))
    clock = [2_000_000_000.0]
    monkeypatch.setattr(c.time, 'time', lambda: clock[0])
    players, broadcasts, trips = [], [], []
    monkeypatch.setattr(app, '_tw_sesiones', lambda: list(players))
    monkeypatch.setattr(app, '_tw_difundir', lambda *pk: broadcasts.extend(pk))
    monkeypatch.setattr(app, '_refrescar', lambda *a, **kw: [])
    monkeypatch.setattr(app, '_vida_max', lambda p, *a: p.hp_max)
    monkeypatch.setattr(app, '_mana_max', lambda p, *a: p.mp_max)
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE personajes (char_id INTEGER PRIMARY KEY, usuario TEXT, nombre TEXT, datos TEXT, ranura INTEGER DEFAULT 0, actualizado_en TEXT)')

    def save(s):
        data = {'nombre': s.personaje.nombre, 'oro': s.oro, 'inventario': s.inventario,
                'cantidades': s.cantidades, 'mejoras': s.personaje.mejoras,
                'nivel': s.personaje.nivel, 'custom_field': 'preserve me'}
        data['habilidades'] = s.personaje.habilidades
        with sqlite3.connect(db) as con:
            con.execute('INSERT OR REPLACE INTO personajes (char_id,usuario,nombre,datos) VALUES (?,?,?,?)',
                        (s.personaje.char_id, s.usuario, s.personaje.nombre, json.dumps(data)))

    def player(level=410, items=None, gold=2_000_000_000):
        cid = len(players) + 1
        p = login.Personaje(char_id=cid, entity_id=1000+cid, nombre='P%d' % cid,
                            nivel=level, stage=114, faction='Beasts',
                            hp=1000, hp_max=1000, mp=1000, mp_max=1000, oro=gold, exp=12345)
        p.logros_cont = {'supremo': 1}
        p.inventario = dict(items or {})
        packets = []
        s = SimpleNamespace(personaje=p, usuario='u%d' % cid, rol='mundo',
                            entity_id=p.entity_id, oro=gold, inventario=p.inventario,
                            cantidades={}, instancias={}, monstruos={}, muerto=False,
                            sp=1000, packets=packets,
                            enviar=lambda *pk: packets.extend(pk),
                            enviar_inmediato=lambda *pk: packets.extend(pk))
        players.append(s)
        save(s)
        return s

    def travel(s, stage, x, y):
        trips.append((s.personaje.char_id, stage, x, y))
        s.personaje.stage, s.personaje.tile_x, s.personaje.tile_y = stage, x, y

    monkeypatch.setattr(app, '_sincronizar_cambio_mapa', travel)
    monkeypatch.setattr(app, '_guardar_bolsa', lambda s, cid: save(s))
    return SimpleNamespace(db=db, now=clock, players=players, broadcasts=broadcasts,
                           trips=trips, player=player, save=save)


def test_pass_bank_moves_preserve_deadline_and_unrelated_metadata(world):
    s = world.player(items={20: 28866})
    p = s.personaje
    deadline = world.now[0] + 10
    p.mejoras = {20: {'holy_pass_fin': deadline, 'custom': 4},
                 -10002: {'holy_pass_fin': deadline + 20}}
    c.mover_pase_banco(p, 20, 1, hacia_banco=True)
    assert p.mejoras[20] == {'custom': 4}
    c.mover_pase_banco(p, 1, 2, desde_banco=True, hacia_banco=True, intercambio=True)
    assert p.mejoras[-10001]['holy_pass_fin'] == deadline + 20
    c.mover_pase_banco(p, 2, 30, desde_banco=True)
    assert p.mejoras[30]['holy_pass_fin'] == deadline
    assert -10002 not in p.mejoras
    world.now[0] = deadline + 1
    s.inventario = p.inventario = {30: 28866}
    c.depurar_pases(s)
    assert not s.inventario


def test_new_pass_starts_expiry_at_acquisition(world):
    s = world.player()
    slot = app._meter(s, 28866)
    assert slot is not None
    assert s.personaje.mejoras[slot]['holy_pass_fin'] == world.now[0] + 7*24*3600


def test_explicit_free_gm_tests_never_charge_or_schedule(world,monkeypatch):
    monkeypatch.setattr(c,'_modo_pruebas',lambda: True)
    cfg = c.config_eventos()
    monkeypatch.setattr(c,'config_eventos',lambda:dict(cfg,cobrar_entrada_en_pruebas=False))
    s = world.player(items={20:8537})
    r = c.iniciar(112,60,0)
    assert r['prueba']
    c.entrada(s,112)
    assert s.inventario[20]==8537
    c.terminar(112)
    r = c.iniciar(240,30,0,410)
    before = s.oro
    c.entrada(s,240)
    assert s.oro==before
    c.terminar(240)
    world.now[0]=dt.datetime(2026,10,25,19,25).astimezone().timestamp()
    c.cron(dt.datetime.fromtimestamp(world.now[0]).astimezone())
    assert all(c.fase(c.ronda(stage))=='cerrada' for stage in c.MAPAS)


def test_gm_arena_defaults_to_normal_gold_charge_once(world,monkeypatch):
    monkeypatch.setattr(c,'_modo_pruebas',lambda:True)
    s = world.player()
    r = c.iniciar(240,30,0,410)
    assert r['prueba'] and r['cobrar_entrada_en_pruebas']
    original = s.oro
    c.entrada(s,240)
    assert s.oro == original-c.tramo(410)[6]
    s.personaje.stage = 114
    c.entrada(s,240)
    assert s.oro == original-c.tramo(410)[6]


@pytest.mark.parametrize('items,expired,consumed',[
    ({20:8537},False,True),
    ({20:8537,21:28866},False,False),
    ({20:8537,21:28866},True,True),
])
def test_gm_holy_uses_normal_stone_and_prioritizes_live_pass(world,monkeypatch,items,expired,consumed):
    monkeypatch.setattr(c,'_modo_pruebas',lambda:True)
    s = world.player(items=items)
    s.cantidades[20] = 2
    if 21 in items:
        s.personaje.mejoras[21] = {'holy_pass_fin':world.now[0]+(-1 if expired else 600)}
    world.save(s)
    original_gold = s.oro
    c.iniciar(112,60,0)
    c.entrada(s,112)
    assert s.oro == original_gold
    assert s.cantidades[20] == (1 if consumed else 2)
    s.personaje.stage = 114
    c.entrada(s,112)
    assert s.cantidades[20] == (1 if consumed else 2)


def test_gm_holy_requires_a_stone_and_arena_requires_gold(world,monkeypatch):
    monkeypatch.setattr(c,'_modo_pruebas',lambda:True)
    s = world.player(gold=0)
    c.iniciar(112,60,0)
    with pytest.raises(c.Rechazo,match='Battlefield Cursed Stone'):
        c.entrada(s,112)
    c.iniciar(240,30,0,410)
    with pytest.raises(c.Rechazo,match='gold'):
        c.entrada(s,240)
    assert not c.ronda(112)['miembros'] and not c.ronda(240)['miembros']


def stored(world, s):
    with sqlite3.connect(world.db) as con:
        return json.loads(con.execute('SELECT datos FROM personajes WHERE char_id=?',
                                     (s.personaje.char_id,)).fetchone()[0])


@pytest.mark.parametrize('cmd,args,stage', [('aastart', ['30','410','0'], 240),
                                         ('hbstart', ['60','0'], 112)])
def test_real_gm_start_is_separate_and_never_teleports(world, cmd, args, stage):
    s = world.player()
    before = (s.personaje.stage, s.personaje.tile_x, s.personaje.tile_y)
    assert app._probar_gm(s, ('/'+cmd+' '+' '.join(args)).encode(), 'test')
    assert c.fase(c.ronda(stage)) == 'combate'
    assert (s.personaje.stage, s.personaje.tile_x, s.personaje.tile_y) == before
    assert not world.trips and world.broadcasts


@pytest.mark.parametrize('level,stage,fee', [(60,159,75000),(259,159,200000000),
                                          (260,239,4000000),(400,239,8000000),(410,240,8000000)])
def test_arena_fee_bracket_and_reentry_are_idempotent(world, level, stage, fee):
    s = world.player(level)
    c.iniciar(stage, 30, 0, level)
    c.entrada(s, stage)
    assert s.oro == 2_000_000_000-fee
    assert stored(world, s)['oro'] == s.oro
    assert stored(world, s)['custom_field'] == 'preserve me'
    s.personaje.stage = 114
    c.entrada(s, stage)
    assert s.oro == 2_000_000_000-fee


def test_wrong_level_and_insufficient_gold_do_not_charge(world):
    c.iniciar(240, 30, 0, 410)
    for s in (world.player(100), world.player(410, gold=5)):
        before = stored(world, s)
        with pytest.raises(c.Rechazo):
            c.entrada(s, 240)
        assert stored(world, s) == before and not c.ronda(240)['miembros']


def test_stale_account_balance_is_not_overwritten(world):
    s = world.player()
    c.iniciar(240, 30, 0, 410)
    with sqlite3.connect(world.db) as con:
        con.execute('UPDATE personajes SET datos=json_set(datos,\'$.oro\',10) WHERE char_id=1')
    with pytest.raises(c.Rechazo):
        c.entrada(s, 240)
    assert stored(world, s)['oro'] == 10 and not c.ronda(240)['miembros']


def test_database_failure_rolls_back_fee_and_registration(world):
    s = world.player()
    c.iniciar(240, 30, 0, 410)
    before = stored(world, s)
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_round BEFORE UPDATE ON competiciones BEGIN SELECT RAISE(ABORT,'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        c.entrada(s, 240)
    assert stored(world, s) == before
    assert not c.ronda(240)['miembros'] and s.oro == before['oro']


def test_holy_has_no_level_restriction_and_consumes_one_stone(world):
    s = world.player(1, {20: 8537})
    s.cantidades[20] = 3
    world.save(s)
    c.iniciar(112, 60, 0)
    c.entrada(s, 112)
    assert s.cantidades[20] == 2 and s.oro == 2_000_000_000
    s.personaje.stage = 114
    c.entrada(s, 112)
    assert s.cantidades[20] == 2


def test_timed_pass_has_priority_and_never_refreshes(world):
    s = world.player(items={20:28866,21:8537})
    c.iniciar(112, 60, 0)
    c.entrada(s, 112)
    deadline = s.personaje.mejoras[20]['holy_pass_fin']
    assert deadline == world.now[0]+7*86400
    assert s.inventario == {20:28866,21:8537}
    c.terminar(112)
    world.now[0] += 100
    s.personaje.stage = 114
    c.iniciar(112, 60, 0)
    c.entrada(s,112)
    assert s.personaje.mejoras[20]['holy_pass_fin'] == deadline
    assert s.inventario == {20:28866,21:8537}


def test_expired_pass_does_not_admit_and_disappears(world):
    s = world.player(items={20:28866})
    s.personaje.mejoras[20] = {'holy_pass_fin': world.now[0]-1}
    world.save(s)
    c.iniciar(112, 60, 0)
    with pytest.raises(c.Rechazo):
        c.entrada(s,112)
    c.depurar_pases(s)
    assert not s.inventario and not stored(world,s)['inventario']


@pytest.mark.parametrize('box', [16762,16763])
def test_sealed_boxes_are_not_entry_passes(world,box):
    s = world.player(items={20:box})
    c.iniciar(112,60,0)
    with pytest.raises(c.Rechazo):
        c.entrada(s,112)
    assert s.inventario == {20:box}


def test_holy_balances_teams_and_rejects_friendly_fire_and_outsiders(world):
    c.iniciar(112,60,0)
    players = [world.player(items={20:8537}) for _ in range(3)]
    for s in players:
        c.entrada(s,112)
    a,b,same = players
    assert c.motivo_pvp(a,b) == ''
    assert c.motivo_pvp(a,same) == 'same Holy Battlefield team'
    spectator = world.player()
    c.entrada(spectator,112,True)
    assert c.motivo_pvp(a,spectator)
    outsider = world.player()
    outsider.personaje.stage = 112
    assert c.motivo_pvp(a,outsider)
    assert pvp_liga.permitido(a,b)
    assert not pvp_liga.permitido(a,same)


def test_arena_allows_same_faction_but_spectators_are_immune(world):
    c.iniciar(240,30,0,410)
    a,b = world.player(),world.player()
    for s in (a,b):
        c.entrada(s,240)
    assert c.motivo_pvp(a,b) == '' and pvp_liga.permitido(a,b)
    c.ronda(240)['miembros']['2']['espectador'] = True
    assert not pvp_liga.permitido(a,b)


def test_registration_phase_is_not_combat_and_late_admission_is_closed(world):
    c.iniciar(112,60,15)
    a,b = world.player(items={20:8537}),world.player(items={20:8537})
    for s in (a,b):
        c.entrada(s,112)
    assert c.motivo_pvp(a,b)
    world.now[0] += 15*60
    assert c.motivo_pvp(a,b) == ''
    late = world.player(items={20:8537})
    with pytest.raises(c.Rechazo):
        c.entrada(late,112)


def test_holy_capture_delivery_needs_distance_team_and_real_carrier(world):
    c.iniciar(112,60,0)
    s = world.player(items={20:8537})
    c.entrada(s,112)
    assert c.pulsar(s,71112002)
    assert not c.ronda(112)['portadores']  # out of range
    s.personaje.tile_x,s.personaje.tile_y = (100,88)
    c.pulsar(s,71112002)
    assert c.ronda(112)['portadores'] == {'2':s.personaje.char_id}
    s.personaje.tile_x,s.personaje.tile_y = (235,208)
    c.pulsar(s,112001)
    assert c.ronda(112)['puntos']['1'] == 1
    assert not c.ronda(112)['portadores']
    c.pulsar(s,112001)
    assert c.ronda(112)['puntos']['1'] == 1  # no duplicate hand-in


def test_twenty_crystals_end_only_holy_round(world):
    c.iniciar(112,60,0)
    c.iniciar(240,30,0,410)
    s = world.player(items={20:8537})
    c.entrada(s,112)
    r = c.ronda(112)
    r['puntos']['1'] = 19
    r['portadores']['2'] = s.personaje.char_id
    c._guardar(r)
    s.personaje.tile_x,s.personaje.tile_y = (235,208)
    c.pulsar(s,112001)
    assert c.ronda(112)['cerrada'] and c.ronda(112)['ganador'] == 1
    assert s.personaje.stage == 112 and s._holy_retorno
    world.now[0] += 10
    c.tick_retornos()
    assert s.personaje.stage == 114 and c.fase(c.ronda(240)) == 'combate'


def test_carrier_disconnect_restores_crystal(world):
    c.iniciar(112,60,0)
    s = world.player(items={20:8537})
    c.entrada(s,112)
    s.personaje.tile_x,s.personaje.tile_y = (100,88)
    c.pulsar(s,71112002)
    c.abandonar(s,112)
    assert not c.ronda(112)['portadores']


def test_arena_death_becomes_spectator_no_exp_loss_or_tw_rewards(world, monkeypatch):
    c.iniciar(240,30,0,410)
    a,b = world.player(),world.player()
    for s in (a,b):
        c.entrada(s,240)
    monkeypatch.setattr(presencia, '_vivas', lambda *a: list(world.players))
    def forbidden(*args):
        pytest.fail('A competition death must not use TW rewards')
    monkeypatch.setattr(pvp_liga, '_contar_baja', forbidden)
    pvp_liga._aplicar(a,b,2000,False,False,combate.ATAQUE_NORMAL,0,False)
    assert b.personaje.exp == 12345
    assert not b.muerto and b.personaje.hp == 1000
    assert c.ronda(240)['miembros']['2']['espectador']
    assert c.ronda(240)['clasificacion'] == ['1','2']
    assert all(s.personaje.stage == 114 for s in (a,b))
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT COUNT(*) FROM competiciones_resultados').fetchone()[0] == 1


def test_pending_combo_cannot_hit_new_holy_life(world, monkeypatch):
    c.iniciar(112,60,0)
    a,b = world.player(items={20:8537}),world.player(items={20:8537})
    for s in (a,b):
        c.entrada(s,112)
    a.personaje.tile_x,a.personaje.tile_y = 50,50
    b.personaje.tile_x,b.personaje.tile_y = 51,50
    data = bytearray(100)
    struct.pack_into('<I',data,26,2000)
    monkeypatch.setattr(app, '_stats_ses', lambda *a: bytes(data))
    monkeypatch.setattr(app, '_otorgar_skill_exp', lambda *a,**kw: [])
    monkeypatch.setattr(pvp_liga, '_multiplicador', lambda *a:(1,0))
    monkeypatch.setattr(pvp_liga, '_prob_critico', lambda *a:0)
    monkeypatch.setattr(presencia, '_vivas', lambda *a: list(world.players))
    callbacks = []
    monkeypatch.setattr(app.asyncio,'get_event_loop',lambda:SimpleNamespace(
        call_later=lambda delay,cb:callbacks.append(cb)))
    assert pvp_liga.atacar(a,b,combate.ATAQUE_NORMAL,{},0,golpes=3)
    assert b.competicion_vida == 1 and b.personaje.hp == 1000
    for cb in callbacks:
        cb()
    assert b.personaje.hp == 1000
    assert c.ronda(112)['miembros']['1']['bajas'] == 1


def test_official_holy_window_and_no_restart_of_finished_round(world):
    instant = dt.datetime(2026,10,23,11,45)  # Friday, 15 min before noon
    world.now[0] = instant.timestamp()
    c.cron(instant)
    r = c.ronda(112)
    assert c.fase(r) == 'registro'
    assert r['inicio'] == instant.replace(hour=12,minute=0).timestamp()
    assert r['fin'] - r['inicio'] == 3600
    c.terminar(112)
    original_id = r['id']
    c.cron(instant)
    assert c.ronda(112)['cerrada'] and c.ronda(112)['id'] == original_id


def test_sunday_official_401_plus_window_is_1932(world):
    instant = dt.datetime(2026,10,25,19,17)
    world.now[0] = instant.timestamp()
    c.cron(instant)
    r = c.ronda(240)
    assert r['min'] == 401 and dt.datetime.fromtimestamp(r['inicio']).strftime('%H:%M') == '19:32'
    assert r['fin'] - r['inicio'] == configuracion.DURACION_ANGEL_ARENA_MIN*60


def test_round_and_membership_survive_cache_reload(world):
    s = world.player()
    c.iniciar(240,30,0,410)
    c.entrada(s,240)
    original = copy.deepcopy(c.ronda(240))
    c._RONDAS.clear()
    c._BASE = None
    assert c.ronda(240) == original
    s.personaje.stage = 114
    c.entrada(s,240)
    assert s.oro == 1_992_000_000


def test_real_clerk_packet_join_uses_new_engine(world):
    import dialogos
    s = world.player()
    c.iniciar(240,30,0,410)
    server = app.Servidor.__new__(app.Servidor)
    server.manejar(s,0x0005,None,None,'test',struct.pack('<IH',114004,0))
    # Third menu entry is sign up to join (not the info entry or watch).
    server.manejar(s,0x000B,None,{'valor':dialogos.PRIMERA_OPCION+1},'test')
    assert s.personaje.stage == 114 and s.oro == 2_000_000_000
    server.manejar(s,0x000B,None,{'valor':dialogos.PRIMERA_OPCION},'test')
    assert s.personaje.stage == 114 and s.oro == 2_000_000_000
    server.manejar(s,0x000B,None,{'valor':1},'test')
    assert s.personaje.stage == 240 and s.oro == 1_992_000_000
    assert c.ronda(240)['miembros']['1']['espectador'] is False


@pytest.mark.parametrize('stage', c.MAPAS)
def test_competition_maps_have_visible_return_portals(world, stage):
    packets = login.poblar(stage)
    assert any(p[:2] == b'\x0e\x00' for p in packets)
    portal = c.portales(stage)[0]
    assert app._portal_en(stage,*portal['tile'])['destino'] == 114


@pytest.mark.parametrize('bad', [['0','410','0'],['30','20','0'],['30','410','-1'],['130','410','0']])
def test_invalid_gm_start_does_not_open_or_move(world,bad):
    s = world.player()
    c.comando_gm(s,'aastart',bad)
    assert not c.ronda(240) and not world.trips
