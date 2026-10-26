"""Wraith arrival animation timing, cancellation and Duo Summon publication."""
import struct
from types import SimpleNamespace
import pytest
from test_competiciones import world
import app,combate,invocaciones,presencia


def setup(world,monkeypatch):
    s=world.player();p=s.personaje;p.mp=p.mp_max=30000;p.tile_x=p.tile_y=50
    queue=[];effects=[];published=[];removed=[]
    monkeypatch.setattr(invocaciones.asyncio,'get_event_loop',lambda:SimpleNamespace(
        call_later=lambda delay,fn:queue.append((delay,fn))))
    monkeypatch.setattr(app,'_otorgar_skill_exp',lambda *a,**kw:[])
    monkeypatch.setattr(presencia,'notificar_companero_accion',lambda s,*pk:effects.extend(pk))
    monkeypatch.setattr(presencia,'notificar_invocacion_spawn',lambda s,inv,*pk:published.append(inv))
    monkeypatch.setattr(presencia,'notificar_invocacion_despawn',lambda s,eid:removed.append(eid))
    return s,queue,effects,published,removed


def test_putridox_native_cast_and_coffin_complete_before_entity_is_published(world,monkeypatch):
    s,q,effects,published,_=setup(world,monkeypatch)
    mag=combate.datos_magia(13840)
    assert invocaciones.lanzar(s,13840,mag,52,51)
    assert not getattr(s,'invocacion',None) and not published
    initial=[pk for pk in s.packets if pk[:2]==b'\x11\0']
    assert len(initial)==1 and initial[0][3]&0x80==0
    assert struct.unpack_from('<H',initial[0],23)[0]==13840
    assert struct.unpack_from('<II',initial[0],12)==(52,51)
    assert initial[0][2]|((initial[0][3]&15)<<8)==458
    delay,impact=q.pop(0);assert delay==2
    impact();assert not published and not getattr(s,'invocacion',None)
    assert s.packets[-1][3]&0x80
    delay,spawn=q.pop(0);assert delay==.8
    spawn();assert len(published)==1 and s.invocacion is published[0]
    assert s.invocacion['npc_type']==20355
    assert len(effects)==2 and effects[1][3]&0x80
    assert not s._summon_cast
    assert s.personaje.mp==27000


@pytest.mark.parametrize('cancel',['death','disconnect','map','loading','character'])
def test_summon_cancelled_context_never_spawns_or_replaces_existing_companion(world,monkeypatch,cancel):
    s,q,_,published,removed=setup(world,monkeypatch)
    old={'entity_id':3333,'hp':100};s.invocacion=old
    assert invocaciones.lanzar(s,13840,combate.datos_magia(13840),52,51)
    q.pop(0)[1]()  # cast finished, arrival animation is now playing
    if cancel=='death':s.muerto=True
    elif cancel=='disconnect':s.desconectado=True
    elif cancel=='map':s.personaje.stage=41
    elif cancel=='loading':s.mapa_cargando=True
    else:s.personaje=None
    q.pop(0)[1]()
    assert not published and not removed and s.invocacion is old
    assert not s._summon_cast


def test_summon_resource_validation_does_not_charge_mp_for_insufficient_sp(world,monkeypatch):
    s,q,_,published,_=setup(world,monkeypatch)
    mag=dict(combate.datos_magia(13840),cost_sp=2000)
    assert not invocaciones.lanzar(s,13840,mag,52,51)
    assert s.personaje.mp==30000 and s.sp==1000 and not q and not published


def test_duo_second_slot_notifies_observers_with_the_second_summon(world,monkeypatch):
    s,q,_,published,removed=setup(world,monkeypatch)
    first={'entity_id':s.personaje.entity_id+8000,'hp':100};s.invocacion=first
    s.personaje.buffs={5140:{'fin':world.now[0]+300}}
    assert invocaciones.lanzar(s,13840,combate.datos_magia(13840),52,51)
    assert not invocaciones.lanzar(s,13840,combate.datos_magia(13840),52,51)
    q.pop(0)[1]();q.pop(0)[1]()
    assert s.invocacion is first and published==[s.invocacion2] and not removed
    assert s.invocacion2['entity_id']!=first['entity_id']
