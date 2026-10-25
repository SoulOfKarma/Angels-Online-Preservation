"""Power Clone effective-owner scaling, combat orders and native Star ranks."""
import struct
from types import SimpleNamespace
import pytest
from test_competiciones import world
import app,avatar_clones as clones,combate,presencia


def summon(world,monkeypatch,rank=5):
    s=world.player(items={3:69578});p=s.personaje;p.mp=p.mp_max=30000
    p.tile_x,p.tile_y=50,50
    p.habilidades=[(16,410,0)]
    p.buffs={987654:dict(fin=world.now[0]+600,atk=2500,matk=3600,mdef=2100,
                       crit=27,hit=500,eva=300,es_melee_trans=True,matk_pct=150,mdef_pct=200)}
    callbacks=[]
    monkeypatch.setattr(clones.asyncio,'get_event_loop',lambda:SimpleNamespace(call_later=lambda delay,fn:callbacks.append(fn)))
    monkeypatch.setattr(app,'_otorgar_skill_exp',lambda *a,**kw:[])
    mag=combate.datos_magia(15280+rank)
    assert clones.lanzar(s,15280+rank,mag)
    callbacks.pop()()
    return s,s.avatar_clon


@pytest.mark.parametrize('rank,pct',[(1,75),(2,80),(3,85),(4,90),(5,100)])
def test_clone_copies_effective_equipment_transformation_crit_range_and_cadence(world,monkeypatch,rank,pct):
    s,inv=summon(world,monkeypatch,rank);stats=app._stats_ses(s)
    assert inv['npc_type']==6270 and not inv['clon_sustituto']
    for key,offset in (('atk',26),('atk_l',30),('defensa',38),('matk',46),('mdef',54)):
        assert inv[key]==struct.unpack_from('<I',stats,offset)[0]*pct//100
    for key,offset in (('accuracy',60),('agility',64),('crit_rate',68)):
        assert inv[key]==struct.unpack_from('<H',stats,offset)[0]*pct//100
    assert inv['hp_max']==s.personaje.hp_max*pct//100
    assert inv['mp_max']==s.personaje.mp_max*pct//100
    assert inv['atk_range']==combate.alcance_arma(69578)>1
    assert inv['cadencia']==combate.cadencia_ataque(s.personaje.buffs,s.personaje.habilidades,item_id=69578)
    assert inv['move_speed']==app._velocidad_de(s)
    assert inv['level']==s.personaje.nivel
    for key,offset in (('res_body',72),('res_mind',76),('res_lightning',78),
                       ('res_fire',82),('res_ice',86),('res_corrosion',90)):
        assert inv[key]==struct.unpack_from('<H',stats,offset)[0]*pct//100


def monster(s,ident=501,**changes):
    m=combate.Monstruo(ident,23211,'Target',[51,50],110976,stage=s.personaje.stage)
    m.hp=m.hp_max=1000000;m.agro=0
    for key,value in changes.items():setattr(m,key,value)
    s.monstruos[ident]=m
    return m


def test_clone_takes_existing_target_then_retargets_and_rejects_friends_dead_or_stale(world,monkeypatch):
    s,inv=summon(world,monkeypatch);a=monster(s);b=monster(s,502)
    s.objetivo_actual=a.entity_id;clones.objetivo(s,inv);assert inv['objetivo'] is a
    clones.ordenar(s,b);assert inv['objetivo'] is b
    clones.objetivo(s,inv);assert inv['objetivo'] is b
    b.hp=0;a.encantado=True;clones.objetivo(s,inv);assert inv['objetivo'] is None
    a.encantado=False;a.en_combate_con=s.personaje.entity_id;s.objetivo_actual=None
    clones.objetivo(s,inv);assert inv['objetivo'] is a
    s.monstruos.clear();clones.objetivo(s,inv);assert inv['objetivo'] is None
    s.monstruos[a.entity_id]=a;inv['clon_sustituto']=True
    clones.ordenar(s,a);assert inv['objetivo'] is None


def test_power_clone_deals_real_damage_obeys_cadence_and_routes_kill_once(world,monkeypatch):
    s,inv=summon(world,monkeypatch);m=monster(s);s.objetivo_actual=m.entity_id
    monkeypatch.setattr(__import__('transitable'),'linea_libre',lambda *a:True)
    monkeypatch.setattr(clones.random,'random',lambda:0.99)
    monkeypatch.setattr(presencia,'notificar_companero_accion',lambda *a:None)
    deaths=[];monkeypatch.setattr(app,'_procesar_muerte_monstruo',lambda *a,**kw:deaths.append(a[1].entity_id))
    before=m.hp;now=world.now[0]
    clones.atacar(s,inv,m,now)
    assert m.hp<before and m.en_combate_con==s.personaje.entity_id
    hp=m.hp;clones.atacar(s,inv,m,now+0.1);assert m.hp==hp
    assert any(p[:2]==b'\x0a\0' and struct.unpack_from('<I',p,2)[0]==inv['entity_id'] for p in s.packets)
    m.hp=1;clones.atacar(s,inv,m,now+inv['cadencia']+0.01)
    clones.atacar(s,inv,m,now+2*inv['cadencia']+0.02)
    assert m.hp==0 and deaths==[m.entity_id] and inv['objetivo'] is None


@pytest.mark.parametrize('magic',range(15378,15423))
def test_each_star_rank_keeps_native_npc_stats_skill_and_roman_name(magic):
    mag=combate.datos_magia(magic);npc=22541+magic-15378
    data=combate.datos_invocacion(npc);rank=(magic-15378)%5
    assert mag['es_invocacion'] and mag['invoca_npc']==npc
    assert data['nombre'].split()[-1]==('I','II','III','IV','V')[rank]
    assert data['level']==280+rank*10 and data['skills']==[20450+magic-15378]
    if rank==4:
        previous=combate.datos_invocacion(npc-2)
        assert data['atk']>previous['atk'] and data['matk']>previous['matk']
