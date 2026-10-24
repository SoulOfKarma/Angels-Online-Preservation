"""User-reported runtime regressions; only temporary accounts/SQLite."""
import copy
import json
import sqlite3
import struct

import pytest

from test_competiciones import world, stored
import app
import clases
import competiciones as c
import competicion_premios as rewards
import dialogos
import holy_battlefield as hb
import inventario as inv
import login


@pytest.mark.parametrize('level,stage,eid',[(70,159,114001),(303,239,114003),(434,240,114004)])
def test_each_actual_arena_menu_admits_matching_paid_player(world,level,stage,eid):
    s = world.player(level=level)
    c.iniciar(stage,30,15,level)
    server = app.Servidor.__new__(app.Servidor)
    server.manejar(s,5,None,None,'test',struct.pack('<IH',eid,0))
    assert s._competicion_clerk==stage
    server.manejar(s,11,None,{'valor':dialogos.PRIMERA_OPCION+1},'test')
    server.manejar(s,11,None,{'valor':dialogos.PRIMERA_OPCION},'test')
    server.manejar(s,11,None,{'valor':1},'test')
    assert s.personaje.stage==stage
    assert s.oro==2_000_000_000-c.tramo(level)[6]
    assert not c._miembro(c.ronda(stage),s)['espectador']


def test_closed_holy_clerk_has_original_single_page_rejection(world):
    s = world.player()
    server = app.Servidor.__new__(app.Servidor)
    server.manejar(s,5,None,None,'test',struct.pack('<IH',114002,0))
    server.manejar(s,11,None,{'valor':dialogos.PRIMERA_OPCION+1},'test')
    assert [struct.unpack_from('<I',line)[0] for line in s.dlg_guion]==[7607]
    assert all(struct.unpack_from('<H',line,4)[0]==69 for line in s.dlg_guion)
    assert s.personaje.stage==114 and not world.trips


def test_all_holy_spawn_ids_unique_and_all_native_exit_tiles_connected(world):
    c.iniciar(112,60,0)
    packets = c.poblar(112)
    entities = [struct.unpack_from('<I',p,2)[0] for p in packets if p[:2] in (b'\x08\0',b'\x0e\0')]
    assert len(entities)==len(set(entities))
    assert len(c.portales(112))==14
    assert {v[0] for v in c.CRISTALES.values()}.isdisjoint(p['entity'] for p in c.portales(112))
    for portal in c.portales(112):
        if portal.get('solo_clic'):
            assert app._portal_en(112,*portal['tile']) is None
        else:
            assert app._portal_en(112,*portal['tile'])['destino']==114
    assert len(hb.datos()['resources'])==60
    for resource in hb.datos()['resources']:
        mid,px = app._veta_de(112,resource['entity_id'])
        assert 248<=mid<=257 and px==resource['px']
        assert {x[0] for x in app._material(mid)['items']}=={8534,8535}


def test_tied_teams_randomized_balanced_and_reentry_preserves_assignment(world,monkeypatch):
    monkeypatch.setattr(c.random,'choice',lambda xs:xs[-1])
    c.iniciar(112,60,15)
    a,b = [world.player(items={20:8537}) for _ in range(2)]
    assert c.entrada(a,112)['equipo']==2
    assert c.entrada(b,112)['equipo']==1
    a.personaje.stage=114
    assert c.entrada(a,112)['equipo']==2
    assert len(c.ronda(112)['miembros'])==2


def test_scene_transition_clears_old_dialogue_and_holy_overlay(world):
    s = world.player()
    s.personaje.stage=112
    hb.mostrar(s,7581,[7583],69)
    c.antes_de_viajar(s,114)
    assert s.dlg_ent is None and s.dlg_mapa is None and s.dlg_guion is None
    assert struct.pack('<H',18)+dialogos.FIN in s.packets
    board = next(p for p in reversed(s.packets) if p[:2]==b'\x3b\x01')
    assert board[2]==0 and board[5]==0
    assert not s._holy_marcador


@pytest.mark.parametrize('sealed,opened,days',[(16762,16764,30),(16763,16765,60)])
def test_unseal_deadline_is_atomic_and_visible_on_all_item_packets(world,monkeypatch,sealed,opened,days):
    s = world.player(items={20:sealed})
    app.Servidor.__new__(app.Servidor).manejar(s,0x2e,None,None,'test',struct.pack('<I',20))
    assert s.inventario=={20:opened}
    deadline = int(world.now[0]+days*86400)
    assert stored(world,s)['mejoras']['20']['holy_pass_fin']==deadline
    state = s.personaje.mejoras[20]
    entry = inv._entrada(s.personaje.char_id,20,opened,1,dueno=s.personaje.entity_id)
    marked = inv.marcar_caducidad_holy(entry,state)
    assert len(marked)==len(entry) and marked[51:53]==entry[51:53]
    assert struct.unpack_from('<I',marked,47)[0]==deadline
    assert not marked[58]&2
    for packet in (inv.completo(s.personaje.char_id,[(20,opened)],s.personaje.entity_id,mejoras=s.personaje.mejoras),
                   inv.actualizar_ranuras(s.personaje.char_id,[(20,opened,1,None)],mejoras=s.personaje.mejoras)):
        assert struct.unpack_from('<I',packet,6+47)[0]==deadline
    c.mover_pase_banco(s.personaje,20,1,hacia_banco=True)
    bank = inv.almacen(s.personaje.char_id,[(1,opened,1)],mejoras=s.personaje.mejoras)
    assert struct.unpack_from('<I',bank,6+47)[0]==deadline
    bank = inv.banco_poner(s.personaje.char_id,1,opened,mejoras=s.personaje.mejoras)
    assert struct.unpack_from('<I',bank,6+47)[0]==deadline
    c.mover_pase_banco(s.personaje,1,21,desde_banco=True)
    packet = inv.banco_sacar(s.personaje.char_id,21,opened,mejoras=s.personaje.mejoras)
    assert struct.unpack_from('<I',packet,6+47)[0]==deadline


def test_unseal_transaction_failure_preserves_seal_and_no_timer(world):
    s = world.player(items={20:16762})
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_seal BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'no'); END")
    with pytest.raises(sqlite3.IntegrityError):
        c.desellar_pase(s,20)
    assert s.inventario=={20:16762} and not s.personaje.mejoras


def test_holy_own_formula_delivers_exp_skills_once_then_counts_10_to_zero(world,monkeypatch):
    monkeypatch.setattr(app,'_stats_ses',lambda s:b'')
    c.iniciar(112,60,0)
    a,b = [world.player(level=70,items={20:8537}) for _ in range(2)]
    for s in (a,b):
        s.personaje.habilidades=[[1,20,0],[2,20,0]]
        world.save(s)
        c.entrada(s,112)
    r = c.ronda(112)
    r['puntos']['1']=1
    r['miembros']['1']['score']=500
    c._guardar(r)
    before = a.personaje.exp
    c.terminar(112,'time limit')
    assert a.personaje.exp>before
    assert all(row[1]>20 for row in a.personaje.habilidades)
    awarded = copy.deepcopy((a.personaje.exp,a.personaje.habilidades))
    assert rewards.entregar(a)==0
    assert (a.personaje.exp,a.personaje.habilidades)==awarded
    assert a.personaje.stage==112
    for _ in range(10):
        world.now[0] += 1
        c.tick_retornos()
    assert a.personaje.stage==114 and b.personaje.stage==114
    messages = [p for p in a.packets if p[:2]==b'\x0d\0']
    assert all(any(c._texto_retorno_holy(i).encode() in p for p in messages) for i in range(11))


@pytest.mark.parametrize('level',[70,410])
@pytest.mark.parametrize('team_points,personal_points,exp_ppm,skill_ppm',[
    ((1,0),(500,500),(150000,100000),(1000000,750000)),
    ((0,1),(500,500),(100000,150000),(750000,1000000)),
    ((0,0),(500,500),(100000,100000),(750000,750000)),
    ((0,0),(0,500),(50000,100000),(250000,750000)),
    ((1,0),(0,0),(50000,50000),(250000,250000)),
])
def test_current_holy_compatibility_pays_both_sides_by_level_once(
        world,monkeypatch,level,team_points,personal_points,exp_ppm,skill_ppm):
    """Audit existing policy, not a claim these percentages are official."""
    import combate
    import clases
    monkeypatch.setattr(app,'_stats_ses',lambda s:b'')
    c.iniciar(112,60,0)
    players = [world.player(level=level,items={20:8537}) for _ in range(2)]
    for s in players:
        s.personaje.exp = combate.exp_para_nivel(level)
        s.personaje.habilidades = [[1,20,0]]
        world.save(s)
        c.entrada(s,112)
    r = c.ronda(112)
    r['puntos'].update(zip(('1','2'),team_points))
    for cid,points in zip(('1','2'),personal_points):
        r['miembros'][cid]['score'] = points
    before = [s.personaje.exp for s in players]
    gap = combate.exp_para_nivel(level+1)-combate.exp_para_nivel(level)
    c.terminar(112,'time limit')
    for i,s in enumerate(players):
        assert s.personaje.exp-before[i] == gap*exp_ppm[i]//1000000
        skill_level = s.personaje.habilidades[0][1]
        received = (sum(clases.exp_requerida_skill(lv,1) for lv in range(20,skill_level))
                    +s.personaje.habilidades[0][2])
        assert received == clases.exp_requerida_skill(20,1)*skill_ppm[i]//1000000
        awarded = copy.deepcopy((s.personaje.exp,s.personaje.habilidades))
        assert rewards.entregar(s)==0
        assert (s.personaje.exp,s.personaje.habilidades)==awarded


def test_own_dropped_crystal_returns_home_without_duplicate_points(world):
    c.iniciar(112,60,0)
    a,b = [world.player(items={20:8537}) for _ in range(2)]
    for s in (a,b): c.entrada(s,112)
    b.personaje.tile_x,b.personaje.tile_y=(218,207)
    c.pulsar(b,c.CRISTALES[1][0])
    b.personaje.tile_x,b.personaje.tile_y=(200,200)
    c.abandonar(b,112)
    a.personaje.tile_x,a.personaje.tile_y=(200,200)
    c.pulsar(a,c.CRISTALES[1][0])
    assert hb.posicion_cristal(c.ronda(112),1)==(218,207)
    assert c._miembro(c.ronda(112),a)['score']==20
    c.pulsar(a,c.CRISTALES[1][0])
    assert c._miembro(c.ronda(112),a)['score']==20


def test_native_exits_can_be_clicked_nearby_but_not_remotely(world):
    c.iniciar(112,60,0)
    s = world.player(items={20:8537})
    c.entrada(s,112)
    portal = c.portales(112)[0]
    server = app.Servidor.__new__(app.Servidor)
    server.manejar(s,5,None,None,'test',struct.pack('<IH',portal['entity'],0))
    assert s.personaje.stage==112
    s.personaje.tile_x,s.personaje.tile_y=portal['tile']
    server.manejar(s,5,None,None,'test',struct.pack('<IH',portal['entity'],0))
    assert s.personaje.stage==114


def test_crystal_carrier_effect_is_native_passive_and_removed_on_drop(world):
    import pvp_liga
    c.iniciar(112,60,0)
    s = world.player(items={20:8537})
    c.entrada(s,112)
    s.personaje.tile_x,s.personaje.tile_y=(100,88)
    before_mp = s.personaje.mp
    c.pulsar(s,c.CRISTALES[2][0])
    assert s.personaje.mp==before_mp
    assert s.personaje.buffs[3141]['mit']==-30
    assert pvp_liga.mitigacion(s,False)==pytest.approx(1.3)
    c.abandonar(s,112)
    assert 3141 not in s.personaje.buffs


def test_frontier_tags_are_walkable_not_mining_zones():
    import transitable
    for team in (1,2):
        for count in (0,5,10,15,20,25):
            r = {'edificios':hb.inicial()}
            for d in hb.datos()['structures']:
                if d['kind']=='idol' and d['team']==team:
                    r['edificios'][str(d['entity'])] = d['hp'] if d['number']<=count else 0
            tag = hb.spawn_tag(r,team)
            assert tag not in range(101,111)
            assert transitable.se_pisa(112,*hb.datos()['tags'][str(tag)][0])
