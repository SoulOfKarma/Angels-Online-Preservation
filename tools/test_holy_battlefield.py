"""Construction, PvP objectives and original map data, temporary accounts only."""
import copy
import json
import sqlite3

import pytest

from test_competiciones import world, stored
import app
import combate
import competiciones as c
import holy_battlefield as hb


@pytest.fixture
def battle(world, monkeypatch):
    monkeypatch.setattr(hb,'_POOLS',{})
    c.iniciar(112,60,0)
    a,b = world.player(items={20:8537,21:8536}),world.player(items={20:8537,21:8536})
    for s in (a,b):
        s.cantidades[21]=100
        world.save(s)
        c.entrada(s,112)
    return world,a,b


def building(r,team,kind,number):
    d = next(x for x in hb.datos()['structures'] if x['team']==team and x['kind']==kind and x['number']==number)
    return hb.monstruos(r)[d['entity']]


def test_original_layout_and_opening_buildings(battle):
    w,a,b = battle
    r = c.ronda(112)
    assert len(hb.datos()['structures'])==90
    for team in (1,2):
        assert hb.idols(r,team)==10
        assert [n for n in range(1,11) if hb.gate_alive(r,team,n)]==list(range(1,11))
    assert hb.spawn_tag(r,1)==3 and hb.spawn_tag(r,2)==4
    assert len(hb.paquetes(r))>40


def test_build_statue_consumes_only_required_material_and_advances_spawn(battle):
    w,a,b = battle
    for _ in range(5):
        assert hb.construir(a,'idol')==2
    r = c.ronda(112)
    assert hb.idols(r,1)==15 and hb.spawn_tag(r,1)==125
    assert a.cantidades[21]==90
    assert r['miembros']['1']['score']==10
    assert stored(w,a)['cantidades']['21']==90


def test_statue_cap_does_not_consume_extra_material(battle):
    w,a,b = battle
    for _ in range(15):
        hb.construir(a,'idol')
    before = a.cantidades[21]
    with pytest.raises(c.Rechazo,match='already stand'):
        hb.construir(a,'idol')
    assert a.cantidades[21]==before and hb.idols(c.ronda(112),1)==25


def test_gate_partial_contribution_saved_and_no_repeat_charge(battle):
    w,a,b = battle
    r=c.ronda(112)
    for d in hb.datos()['structures']:
        if d['team']==1 and d['kind']=='guard' and d['number']==2:
            r['edificios'][str(d['entity'])]=0
    c._guardar(r)
    a.cantidades[21]=7
    w.save(a)
    assert hb.construir(a,'guard',2)==7
    assert not hb.gate_alive(c.ronda(112),1,2)
    assert c.ronda(112)['construccion']['1:guard:2']==7
    a.inventario[21]=8536
    a.cantidades[21]=100
    w.save(a)
    assert hb.construir(a,'guard',2)==13
    assert hb.gate_alive(c.ronda(112),1,2) and a.cantidades[21]==87
    with pytest.raises(c.Rechazo,match='already stands'):
        hb.construir(a,'guard',2)
    assert a.cantidades[21]==87 and c.ronda(112)['miembros']['1']['score']==20


def test_build_transaction_failure_does_not_consume_or_create(battle):
    w,a,b = battle
    before = copy.deepcopy(c.ronda(112))
    with sqlite3.connect(w.db) as con:
        con.execute("CREATE TRIGGER fail_build BEFORE UPDATE ON competiciones BEGIN SELECT RAISE(ABORT,'no'); END")
    with pytest.raises(sqlite3.IntegrityError):
        hb.construir(a,'idol')
    assert c.ronda(112)==before and a.cantidades[21]==100
    assert stored(w,a)['cantidades']['21']==100


def test_guard_death_removes_pair_and_rebuild_restores_both(battle,monkeypatch):
    w,a,b = battle
    r = c.ronda(112)
    guard = building(r,2,'guard',1)
    monkeypatch.setattr(combate,'ATACANTE',[a])
    guard.recibir(10**9,var_pct=0)
    r = c.ronda(112)
    assert not hb.gate_alive(r,2,1)
    assert all(not m.vivo for m in hb.monstruos(r).values() if m.hb_data['team']==2 and m.hb_data['kind']=='guard' and m.hb_data['number']==1)
    assert r['miembros']['1']['score']==40
    hb.construir(b,'guard',1)
    assert hb.gate_alive(c.ronda(112),2,1)
    assert not guard.toca_reaparecer()


def test_friendly_spectator_and_stale_round_cannot_damage_building(battle,monkeypatch):
    w,a,b = battle
    guard = building(c.ronda(112),1,'guard',1)
    monkeypatch.setattr(combate,'ATACANTE',[a])
    assert guard.recibir(10**9)==0 and guard.hp==guard.hp_max
    c.ronda(112)['miembros']['2']['espectador']=True
    monkeypatch.setattr(combate,'ATACANTE',[b])
    assert guard.recibir(10**9)==0


def test_statue_kill_points_exclude_pet_damage(battle,monkeypatch):
    w,a,b = battle
    statue = building(c.ronda(112),2,'idol',1)
    monkeypatch.setattr(combate,'ATACANTE',[a])
    statue.recibir(10**9,var_pct=0,es_pet=True)
    assert c.ronda(112)['miembros']['1'].get('score',0)==0
    statue = building(c.ronda(112),2,'idol',2)
    statue.recibir(10**9,var_pct=0)
    assert c.ronda(112)['miembros']['1']['score']==2
    assert hb.idols(c.ronda(112),2)==8


def test_reconnect_restores_building_hp_not_full_health(battle,monkeypatch):
    w,a,b = battle
    statue = building(c.ronda(112),2,'idol',1)
    monkeypatch.setattr(combate,'ATACANTE',[a])
    statue.recibir(10000,var_pct=0)
    expected = statue.hp
    monkeypatch.setattr(hb,'_POOLS',{})
    monkeypatch.setattr(c,'_BASE',None)
    assert building(c.ronda(112),2,'idol',1).hp==expected<statue.hp_max


def test_raw_stone_conversion_uses_original_order(battle):
    w,a,b = battle
    a.inventario[22]=8534
    a.cantidades[22]=50
    w.save(a)
    hb.convertir(a)
    assert 22 not in a.inventario and a.cantidades[21]==101


def test_enemy_gate_blocks_crossing_but_not_own_team(battle):
    w,a,b = battle
    line = next(d for d in hb.datos()['barriers'] if d['event']==51)['tile']
    assert hb.bloquear_paso(b,(line[0]-1,line[1]),(line[0]+1,line[1]))
    assert not hb.bloquear_paso(a,(line[0]-1,line[1]),(line[0]+1,line[1]))


def test_npc_requires_team_and_distance(battle):
    w,a,b = battle
    npc = next(d for d in hb.datos()['npcs'] if d['npc_type']==2434)
    a.personaje.tile_x,a.personaje.tile_y = npc['tile']
    assert hb.pulsar(a,npc['entity']) and a._holy_servicio==npc['entity']
    assert a.dlg_mapa['opciones'][2][0]==7652
    b.personaje.tile_x,b.personaje.tile_y = npc['tile']
    assert hb.pulsar(b,npc['entity']) and b._holy_servicio is None


def test_alex_uses_original_random_front_teleport_without_refill(battle,monkeypatch):
    w,a,b = battle
    npc = next(d for d in hb.datos()['npcs'] if d['npc_type']==2486)
    a.personaje.tile_x,a.personaje.tile_y=npc['tile']
    a.personaje.hp,a.personaje.mp=400,300
    monkeypatch.setattr(hb.random,'choice',lambda xs:xs[0])
    assert hb.pulsar(a,npc['entity'])
    assert a.dlg_mapa['opciones']==[(7742,0),(7743,0)]
    assert hb.opcion(a,7742)
    assert (a.personaje.tile_x,a.personaje.tile_y)==tuple(hb.datos()['tags']['52'][0])
    assert (a.personaje.hp,a.personaje.mp)==(400,300)


def test_native_board_packet_and_own_team_property(battle):
    import struct
    w,a,b = battle
    hb.marcador(a)
    board = a.packets[-1]
    assert len(board)==14
    assert struct.unpack('<H8BI',board)==(0x013B,1,0,0,1,10,10,10,25,0)
    assert struct.unpack('<HIBBII',a.packets[-2])==(0x001D,a.personaje.entity_id,1,38,1,1)


def test_carried_and_dropped_crystals_have_real_time_limits(battle):
    w,a,b = battle
    a.personaje.tile_x,a.personaje.tile_y=(100,88)
    c.pulsar(a,71112002)
    w.now[0]+=301
    hb.tick_cristales()
    assert not c.ronda(112)['portadores']
    c.pulsar(a,71112002)
    a.personaje.tile_x,a.personaje.tile_y=(120,90)
    c.abandonar(a,112)
    assert hb.posicion_cristal(c.ronda(112),2)==(120,90)
    w.now[0]+=31
    hb.tick_cristales()
    assert hb.posicion_cristal(c.ronda(112),2)==(100,88)


def test_leaving_map_does_not_drop_crystal_at_lobby_coordinates(battle):
    w,a,b = battle
    a.personaje.tile_x,a.personaje.tile_y=(100,88)
    c.pulsar(a,71112002)
    a.personaje.stage,a.personaje.tile_x,a.personaje.tile_y=114,22,36
    c.abandonar(a,112)
    assert hb.posicion_cristal(c.ronda(112),2)==(100,88)
