"""Reported Holy failures, using temporary accounts and the real packet router."""
import struct

import pytest
from test_competiciones import world
from test_holy_battlefield import battle,building
import app
import combate
import competiciones as c
import competicion_dialogos as dialogs
import holy_battlefield as hb


def test_all_sixty_resources_have_original_names_and_named_packets(battle):
    packets=hb.paquetes()
    names={struct.unpack_from('<I',p,2)[0]:p[18:34].rstrip(b'\0') for p in packets if p[:2]==b'\x0f\0'}
    assert len(names)==60
    for d in hb.recursos():
        assert names[d['entity_id']]==app._material(d['material'])['nombre'].encode('ascii')
        assert app._veta_de(112,d['entity_id'])[0]==d['material']


@pytest.mark.parametrize('event',[51,61,71,81])
def test_walking_behind_friendly_guard_warps_but_destroyed_gate_does_not(battle,event):
    w,a,b=battle
    owner=a if event<71 else b
    rival=b if event<71 else a
    d=next(d for d in hb.datos()['barriers'] if d['event']==event)
    x,y=d['tile'];start,end=(x-1,y),(x,y)
    assert not hb.paso_guardian(rival,start,end)
    assert hb.bloquear_paso(rival,start,end)
    assert hb.paso_guardian(owner,start,end)
    assert (owner.personaje.tile_x,owner.personaje.tile_y)==tuple(hb.datos()['tags'][str(event)][0])
    r=c.ronda(112)
    for guard in hb.datos()['structures']:
        if guard['kind']=='guard' and guard['team']==(1 if event<71 else 2) and guard['number']==1:
            r['edificios'][str(guard['entity'])]=0
    c._guardar(r)
    assert not hb.paso_guardian(owner,start,end)
    assert not hb.bloquear_paso(rival,start,end)
    hb.construir(owner,'guard',1)
    assert hb.paso_guardian(owner,start,end)
    assert hb.bloquear_paso(rival,start,end)


def test_blue_pillar_neighborhood_is_not_an_automatic_exit(battle):
    w,a,b=battle
    for p in c.portales(112):
        if not p.get('solo_clic'):continue
        assert c.portal_en(112,*p['tile']) is None
        b.personaje.tile_x,b.personaje.tile_y=p['tile']
        assert c.pulsar(b,p['entity'])
        assert b.personaje.stage==112
    assert c.portal_en(112,311,8)['destino']==114
    assert c.portal_en(112,23,284)['destino']==114


@pytest.mark.parametrize('kind',['guard','idol'])
@pytest.mark.parametrize('magic',[601,combate.ATAQUE_NORMAL])
def test_allied_building_rejected_before_mp_sp_cooldown_or_combat_packets(battle,kind,magic):
    w,a,b=battle
    target=building(c.ronda(112),1,kind,1)
    a.monstruos=hb.monstruos()
    a.objetivo_actual=target.entity_id
    a.packets.clear()
    before=(a.personaje.mp,a.sp,target.hp)
    server=app.Servidor.__new__(app.Servidor)
    server.manejar(a,6,None,None,'test',struct.pack('<HI',magic,target.entity_id))
    assert (a.personaje.mp,a.sp,target.hp)==before
    assert not a.packets and not getattr(a,'ultimo_uso',{})
    assert a.objetivo_actual is None
    assert not hb.puede_atacar(a,target) and hb.puede_atacar(b,target)


def test_clicking_friendly_guard_neither_warps_nor_attacks(battle):
    w,a,b=battle
    target=building(c.ronda(112),1,'guard',1)
    a.monstruos=hb.monstruos()
    a.personaje.tile_x,a.personaje.tile_y=target.tile_x,target.tile_y
    a.packets.clear()
    server=app.Servidor.__new__(app.Servidor)
    server.manejar(a,5,None,None,'test',struct.pack('<IH',target.entity_id,0))
    assert (a.personaje.tile_x,a.personaje.tile_y)==(target.tile_x,target.tile_y)
    assert target.hp==target.hp_max
    assert not any(p[:2] in (b'\x0a\0',b'\x0b\0') for p in a.packets)


def test_one_stone_admits_repeatedly_through_registration_combat_and_reload(world,monkeypatch):
    c.iniciar(112,60,5)
    s=world.player(items={20:8537});s.cantidades[20]=200;world.save(s)
    c.entrada(s,112)
    r=c.ronda(112);rid=r['id'];team=c._miembro(r,s)['equipo']
    assert s.cantidades[20]==199
    for offset in (-120,10,900,3000):
        world.now[0]=r['inicio']+offset
        c.abandonar(s,112)
        s.personaje.stage=114
        monkeypatch.setattr(c,'_BASE',None)  # Reconnect/server round reload.
        s._competicion_clerk=112
        assert dialogs.opcion(s,7583)  # Even Join recognizes an existing admission.
        assert s._competicion_dialogo['fase']=='viajar'
        assert dialogs.continuar(s,1)
        assert s.personaje.stage==112 and s.cantidades[20]==199
        current=c.ronda(112)
        assert current['id']==rid and c._miembro(current,s)['equipo']==team
    world.now[0]=r['fin']+1;s.personaje.stage=114
    with pytest.raises(c.Rechazo):c.entrada(s,112)
    assert s.cantidades[20]==199
