"""Reported live failures: real routers, interleaved callbacks, temporary DB."""
import asyncio
import copy
import struct
from types import SimpleNamespace
import pytest
from test_competiciones import world,stored
from test_holy_battlefield import battle,building
import app
import bolsas
import combate
import competiciones as c
import holy_battlefield as hb
import inventario as inv
import presencia
import transitable


@pytest.fixture
def timers(monkeypatch):
    pending=[]
    monkeypatch.setattr(asyncio,'get_event_loop',lambda:SimpleNamespace(
        call_later=lambda delay,callback,*args:pending.append((delay,lambda:callback(*args)))))
    return pending


@pytest.mark.parametrize('iid',list(range(74136,74144))+[74145]+list(range(74146,74154))+[74155])
@pytest.mark.parametrize('full',[False,True])
def test_red_blue_potions_restore_and_show_amount_even_when_full(world,monkeypatch,timers,iid,full):
    s=world.player(items={20:iid});s.cantidades[20]=2
    s.personaje.hp_max=s.personaje.mp_max=200000
    s.personaje.hp=s.personaje.mp=200000 if full else 100
    world.save(s)
    monkeypatch.setattr(app,'_stats_ses',lambda s:b'')
    monkeypatch.setattr(app,'_vida_max',lambda p,**kw:p.hp_max)
    monkeypatch.setattr(app,'_mana_max',lambda p,**kw:p.mp_max)
    assert bolsas.buff_de(iid,world.now[0]) is None
    amount=inv.efecto_consumible(iid)
    s.packets.clear()
    app.Servidor.__new__(app.Servidor).manejar(s,0x2e,None,None,'test',struct.pack('<I',20))
    assert s.cantidades[20]==1
    for key,value in amount.items():
        assert getattr(s.personaje,key)==(200000 if full else min(200000,100+value))
        kind=combate.TIPO_CURA_HP if key=='hp' else combate.TIPO_CURA_MP
        assert combate.numero_flotante(s.personaje.entity_id,value,kind) in s.packets
        assert stored(world,s)[key]==getattr(s.personaje,key)
    assert not s.personaje.buffs


def test_combo_hits_keep_the_caster_when_other_team_runs_between_hits(battle,monkeypatch,timers):
    w,a,b=battle
    c.al_entrar(a)
    target=building(c.ronda(112),2,'guard',7)
    a.sp=a.personaje.sp=10000
    a.personaje.tile_x,a.personaje.tile_y=target.tile_x,target.tile_y
    monkeypatch.setattr(app,'_otorgar_skill_exp',lambda *args,**kw:[])
    monkeypatch.setattr(combate,'ATACANTE',[a])
    hits=[]
    receive=target.recibir
    def hit(*args,**kwargs):
        damage=receive(*args,**kwargs)
        hits.append(damage)
        return damage
    monkeypatch.setattr(target,'recibir',hit)
    before=target.hp
    app.Servidor.__new__(app.Servidor).manejar(a,6,None,None,'test',struct.pack('<HI',5850,target.entity_id))
    first=target.hp
    assert first<before
    # b owns this golem: the unbound callback previously saw b and dealt0.
    for _,callback in sorted(timers,key=lambda v:v[0]):
        combate.ATACANTE[0]=b
        callback()
        assert combate.ATACANTE[0] is b
    assert target.hp<first
    assert len(hits)==9 and all(damage>0 for damage in hits)
    assert c.ronda(112)['dano_edificios'][str(target.entity_id)][str(a.personaje.char_id)]==before-target.hp


def test_crystal_requires_adjacent_physical_arrival_not_projected_endpoint(battle):
    w,a,b=battle
    x,y=c.CRISTALES[2][1]
    a.personaje.tile_x,a.personaje.tile_y=x+2,y
    c.pulsar(a,c.CRISTALES[2][0])
    assert not c.ronda(112)['portadores']
    a.personaje.tile_x,a.personaje.tile_y=x,y
    a._holy_camino=(w.now[0]+1,(x+8,y))
    c.pulsar(a,c.CRISTALES[2][0])
    assert not c.ronda(112)['portadores']
    w.now[0]+=1
    hb.contacto_cristal(a)
    assert c.ronda(112)['portadores']['2']==a.personaje.char_id


@pytest.mark.parametrize('mid,dx,expected,mp,sp',[(276,4,4,46,0),(755,9,5,0,1000)])
def test_ground_blink_moves_with_crystal_and_correct_cost(battle,monkeypatch,mid,dx,expected,mp,sp):
    w,a,b=battle
    monkeypatch.setattr(transitable,'se_pisa',lambda *args:True)
    a.personaje.tile_x,a.personaje.tile_y=(160,160)
    a.personaje.mp=10000;a.sp=10000
    c.ronda(112)['portadores']['2']=a.personaje.char_id
    before=(a.personaje.mp,a.sp)
    a.packets.clear()
    app.Servidor.__new__(app.Servidor).manejar(a,6,None,None,'test',struct.pack('<HIIIH',mid,0,160+dx,160,0))
    assert (a.personaje.tile_x,a.personaje.tile_y)==(160+expected,160)
    assert (a.personaje.mp,a.sp)==(before[0]-mp,before[1]-sp)
    assert c.ronda(112)['portadores']['2']==a.personaje.char_id
    assert any(p[:2]==b'\x03\0' for p in a.packets)
    assert not any(p[:2]==b'\x0c\0' for p in a.packets)


def test_repeated_rear_walk_does_not_starve_guardian_jump(battle,timers):
    w,a,b=battle
    a.personaje.tile_x,a.personaje.tile_y=(239,225)
    assert hb.paso_guardian(a,(241,227),(239,225),demora=0.4)
    assert hb.paso_guardian(a,(240,226),(239,225),demora=0.4)
    assert len(timers)==1
    timers[0][1]()
    assert (a.personaje.tile_x,a.personaje.tile_y)==tuple(hb.datos()['tags']['61'][0])


def test_end_clears_holy_mode_before_zero_team(battle,monkeypatch):
    w,a,b=battle
    monkeypatch.setattr(app,'_stats_ses',lambda s:b'')
    a.packets.clear()
    c.terminar(112,'time limit')
    mode=struct.pack('<HIBBII',0x1d,a.personaje.entity_id,1,62,0,0)
    team=hb.equipo(a.personaje.entity_id,0)
    assert mode in a.packets and team in a.packets
    assert a.packets.index(mode)<a.packets.index(team)


def test_shark_stats_rehydrate_without_recasting_and_keep_deadline(world):
    s=world.player();p=s.personaje
    deadline=world.now[0]+120
    p.buffs={415:{'fin':deadline,'es_transform':True,'mag':{'trans_sprite':42455}}}
    buff=p.buffs[415]
    combate.rehidratar_transformaciones(p.buffs)
    assert buff['es_melee_trans'] and buff['matk_pct']==150 and buff['mdef_pct']==200
    assert buff['mp_to_hp_pct']==130 and buff['atk_speed']==20
    assert buff['fin']==deadline
    snapshot=copy.deepcopy(buff)
    combate.rehidratar_transformaciones(p.buffs)
    assert buff==snapshot


def test_arena_both_clients_get_each_others_hostile_marks_after_registration(world,monkeypatch):
    monkeypatch.setattr(app,'_stats_ses',lambda s:b'')
    r=c.iniciar(240,30,1,434)
    a,b=world.player(level=434),world.player(level=434)
    for s in (a,b):c.entrada(s,240)
    world.now[0]=r['inicio']+1
    for s in (a,b):s.packets.clear()
    for s in (a,b):c.al_entrar(s)
    for viewer,other in ((a,b),(b,a)):
        eid=presencia.entidad_de(other)
        assert struct.pack('<HIBBII',0x1d,viewer.personaje.entity_id,1,42,eid,1) in viewer.packets
        assert c.modo_arena(viewer.personaje.entity_id,True) in viewer.packets
        assert c.motivo_pvp(viewer,other)==''


def test_gate_seven_reflected_pair_orientation_and_all_gates_present(battle):
    for team in (1,2):
        guards=sorted([d for d in hb.datos()['structures'] if d['kind']=='guard'
                       and d['team']==team and d['number']==7],key=lambda d:d['tile'])
        assert [hb.spawn_edificio(hb.monstruos()[d['entity']])[35] for d in guards]==[3,7]
        assert all(hb.gate_alive(c.ronda(112),team,n) for n in range(1,11))
        assert hb.spawn_tag(c.ronda(112),team)==(3 if team==1 else 4)


def test_holy_damage_updates_do_not_respawn_every_living_guardian(battle,monkeypatch):
    w,a,b=battle
    r=c.ronda(112)
    hb.publicar(r)
    for s in (a,b):s.packets.clear()
    monkeypatch.setattr(combate,'ATACANTE',[a])
    target=building(r,2,'guard',7)
    assert target.recibir(1000)>0
    for s in (a,b):
        assert not any(p[:2]==b'\x08\0' for p in s.packets)
        assert combate.atributo(target.entity_id,target.porcentaje) in s.packets


def test_temporary_stat_item_uses_buff_route_and_persists(world,monkeypatch,timers):
    s=world.player(items={20:63816})
    monkeypatch.setattr(app,'_stats_ses',lambda s:b'')
    monkeypatch.setattr(app,'_vida_max',lambda p,*a,**kw:p.hp_max+12000)
    monkeypatch.setattr(app,'_mana_max',lambda p,*a,**kw:p.mp_max+9600)
    app.Servidor.__new__(app.Servidor).manejar(s,0x2e,None,None,'test',struct.pack('<I',20))
    buff=s.personaje.buffs[20834]
    assert buff['def']==4000 and buff['matk']==2800
    assert buff['fin']==world.now[0]+3600
    assert '20834' in stored(world,s)['buffs']
    assert s.inventario[20]==63816  # Permanent-use stone, not an instant potion.
