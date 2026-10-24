"""Fresh Holy scenes must also supply fresh combat targets to shared rooms."""
import datetime as dt
import struct
from types import SimpleNamespace
import pytest
from test_competiciones import world
from test_holy_battlefield import battle,building
import app
import combate
import competiciones as c
import holy_battlefield as hb


@pytest.mark.parametrize('kind',['guard','idol'])
@pytest.mark.parametrize('team',[1,2])
def test_enemy_building_click_routes_to_basic_attack_after_old_room(battle,monkeypatch,kind,team):
    w,a,b=battle
    attacker=a if team==2 else b
    target=building(c.ronda(112),team,kind,1)
    # Room was created before Holy opened: client has spawns, room has none.
    room=SimpleNamespace(stage=112,monstruos={},sesiones=[a,b])
    for s in (a,b):s._sala=room;s.monstruos=room.monstruos
    c.al_entrar(attacker)
    assert a.monstruos is b.monstruos is room.monstruos
    assert attacker.monstruos[target.entity_id] is target
    calls=[]
    server=app.Servidor.__new__(app.Servidor)
    route=server.manejar
    def intercept(s,opcode,*args):
        if opcode==6:calls.append(args[-1]);return
        return route(s,opcode,*args)
    monkeypatch.setattr(server,'manejar',intercept)
    attacker.personaje.tile_x,attacker.personaje.tile_y=target.tile_x,target.tile_y
    attacker.packets.clear()
    server.manejar(attacker,5,None,None,'test',struct.pack('<IH',target.entity_id,0))
    assert calls==[struct.pack('<HI',combate.ATAQUE_NORMAL,target.entity_id)]
    assert not any(b'Enemy passage' in p for p in attacker.packets)
    monkeypatch.setattr(combate,'ATACANTE',[attacker])
    assert target.recibir(10**9,var_pct=0)>0
    assert not target.vivo
    if kind=='idol':assert hb.idols(c.ronda(112),team)==9
    else:assert not hb.gate_alive(c.ronda(112),team,1)


def test_new_round_replaces_previous_building_objects_in_shared_room(battle):
    w,a,b=battle
    old=hb.monstruos()
    room=SimpleNamespace(stage=112,monstruos=dict(old),sesiones=[a,b])
    for s in (a,b):s._sala=room;s.monstruos=room.monstruos
    c.terminar(112,'gm stop')
    new=c.iniciar(112,60,0)
    a.personaje.stage=b.personaje.stage=112
    hb.sincronizar_monstruos(a,new)
    assert len(room.monstruos)==90
    assert all(m.hb_round==new['id'] for m in room.monstruos.values())
    assert all(room.monstruos[eid] is not m for eid,m in old.items())
    assert a.monstruos is b.monstruos is room.monstruos


@pytest.mark.parametrize('weapon',[0,6])
@pytest.mark.parametrize('kind',['guard','idol'])
def test_real_basic_attack_damages_enemy_not_allied_building(battle,monkeypatch,weapon,kind):
    import asyncio
    w,a,b=battle
    target=building(c.ronda(112),2,kind,1)
    c.al_entrar(a)
    a.inventario[3]=weapon
    a.personaje.tile_x,a.personaje.tile_y=target.tile_x+1,target.tile_y
    monkeypatch.setattr(app,'_otorgar_skill_exp',lambda *args,**kwargs:[])
    monkeypatch.setattr(combate,'ATACANTE',[a])  # Set by the real socket reader before dispatch.
    monkeypatch.setattr(asyncio,'get_event_loop',lambda:SimpleNamespace(call_later=lambda *args:None))
    server=app.Servidor.__new__(app.Servidor)
    hp=target.hp
    server.manejar(a,6,None,None,'test',struct.pack('<HI',combate.ATAQUE_NORMAL,target.entity_id))
    assert target.hp<hp


@pytest.mark.parametrize('scores,winner',[((3,1),1),((1,3),2),((2,2),0)])
def test_time_limit_compares_captures_not_personal_score(battle,scores,winner):
    w,a,b=battle
    r=c.ronda(112)
    r['puntos'].update(zip(('1','2'),scores))
    r['miembros']['1']['score']=99999
    r['miembros']['2']['score']=0
    c._guardar(r)
    w.now[0]=r['fin']+1
    c.cron(dt.datetime.fromtimestamp(w.now[0],dt.timezone.utc))
    assert r['cerrada'] and r['ganador']==winner


def test_warp_callback_cancelled_if_round_ends_or_gate_destroyed(battle,monkeypatch):
    import asyncio
    w,a,b=battle
    pending=[]
    monkeypatch.setattr(asyncio,'get_event_loop',lambda:SimpleNamespace(
        call_later=lambda delay,callback:pending.append(callback)))
    a.personaje.tile_x,a.personaje.tile_y=(239,225)
    assert hb.paso_guardian(a,(241,227),(239,225),demora=0.5)
    a.packets.clear()
    c.ronda(112)['edificios'][str(building(c.ronda(112),1,'guard',1).entity_id)]=0
    pending.pop()()
    assert not any(p[:2]==b'\x03\0' for p in a.packets)
