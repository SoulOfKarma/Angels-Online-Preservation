"""Holy crossings are local Swiftness, not a stage load or click warp."""
import struct
import pytest
from test_competiciones import world
from test_holy_battlefield import battle,building
import app
import combate
import competiciones as c
import holy_battlefield as hb
import presencia


@pytest.mark.parametrize('team',[1,2])
@pytest.mark.parametrize('side',[0,1])
def test_behind_guard_walk_blinks_without_map_load_or_click(battle,monkeypatch,team,side):
    w,a,b=battle
    owner=a if team==1 else b
    guards=sorted([d for d in hb.datos()['structures'] if d['kind']=='guard'
                   and d['team']==team and d['number']==1],key=lambda d:d['tile'])
    guard,other=guards[side],guards[1-side]
    dx=1 if guard['tile'][0]>other['tile'][0] else -1
    dy=1 if guard['tile'][1]>other['tile'][1] else -1
    back=(guard['tile'][0]+2*dx,guard['tile'][1]+2*dy)
    start=(back[0]+3*dx,back[1]+3*dy)
    owner.personaje.tile_x,owner.personaje.tile_y=start
    owner.packets.clear()
    before=(owner.personaje.hp,owner.personaje.mp,owner.sp)
    def forbidden(*a,**kw):pytest.fail('Same-map crossing must not load/re-enter the map')
    monkeypatch.setattr(app,'_sincronizar_cambio_mapa',forbidden)
    monkeypatch.setattr(presencia,'entrar',forbidden)
    public=[]
    monkeypatch.setattr(presencia,'notificar_companero_accion',lambda s,*pk:public.extend(pk))
    assert hb.paso_guardian(owner,start,back)
    assert owner.personaje.stage==112 and not getattr(owner,'mapa_cargando',False)
    assert (owner.personaje.hp,owner.personaje.mp,owner.sp)==before
    assert any(p[:2]==b'\x03\0' for p in owner.packets)
    assert not any(p[:2] in (b'\x0c\0',b'\x1b\0',b'\x02\0') for p in owner.packets)
    assert any(p[:2]==b'\x11\0' and struct.unpack_from('<H',p,23)[0]==1640 for p in owner.packets)
    assert any(p[:2]==b'\x03\0' and struct.unpack_from('<I',p,2)[0]==presencia.entidad_de(owner) for p in public)
    arrival=(owner.personaje.tile_x,owner.personaje.tile_y)
    assert not hb.paso_guardian(owner,arrival,(arrival[0]+1,arrival[1]))  # No bounce loop.


def test_every_guard_pair_faces_opposite_outward_directions(battle):
    w,a,b=battle
    r=c.ronda(112)
    for team in (1,2):
        for number in range(1,11):
            pair=sorted([d for d in hb.datos()['structures'] if d['kind']=='guard'
                         and d['team']==team and d['number']==number],key=lambda d:d['tile'])
            packets=[hb.spawn_edificio(hb.monstruos(r)[d['entity']]) for d in pair]
            dirs=[p[35] for p in packets]
            assert (dirs[0]-dirs[1])%8==4
            assert set(dirs)==({1,5} if pair[1]['tile'][1]>pair[0]['tile'][1] else {3,7})


def test_real_walk_packet_behind_guard_uses_local_blink(battle,monkeypatch):
    import asyncio
    from types import SimpleNamespace
    w,a,b=battle
    scheduled=[]
    monkeypatch.setattr(asyncio,'get_event_loop',lambda:SimpleNamespace(
        call_later=lambda delay,callback:scheduled.append((delay,callback))))
    a.personaje.tile_x,a.personaje.tile_y=(241,227)
    a.packets.clear()
    def forbidden(*args,**kw):pytest.fail('Movement must not call map change')
    monkeypatch.setattr(app,'_sincronizar_cambio_mapa',forbidden)
    data=dict(cur_x=241*32,cur_y=227*32,path=[dict(x=239*32,y=225*32)])
    app.Servidor.__new__(app.Servidor).manejar(a,4,None,data,'test',b'')
    assert not any(p[:2]==b'\x03\0' for p in a.packets)
    assert len(scheduled)==1 and scheduled[0][0]>0
    scheduled[0][1]()  # Blink only AFTER walking to the rear trigger.
    assert any(p[:2]==b'\x03\0' for p in a.packets)
    assert (a.personaje.tile_x,a.personaje.tile_y)==tuple(hb.datos()['tags']['61'][0])


def test_crystal_capture_has_red_banner_once_delivery_only_changes_counter(battle):
    w,a,b=battle
    a.personaje.tile_x,a.personaje.tile_y=c.CRISTALES[2][1]
    w.broadcasts.clear()
    c.pulsar(a,c.CRISTALES[2][0]);c.pulsar(a,c.CRISTALES[2][0])
    banners=[p for p in w.broadcasts if p[:2]==b'\x28\x01']
    assert len(banners)==1 and banners[0][6]==13
    assert b"I have obtained Raphael's Crystal!" in banners[0]
    w.broadcasts.clear()
    eid=next(eid for eid,(team,tile) in c.ENTREGAS.items() if team==1)
    a.personaje.tile_x,a.personaje.tile_y=c.ENTREGAS[eid][1]
    c.pulsar(a,eid)
    assert c.ronda(112)['puntos']['1']==1 and not w.broadcasts


def test_statue_banner_uses_remaining_count_not_delivery(battle,monkeypatch):
    w,a,b=battle
    monkeypatch.setattr(combate,'ATACANTE',[a])
    statue=building(c.ronda(112),2,'idol',1)
    w.broadcasts.clear()
    statue.recibir(10**9,var_pct=0)
    banners=[p for p in w.broadcasts if p[:2]==b'\x28\x01']
    assert len(banners)==1 and b'Raphael remain 9 statues. Rebirth area back.' in banners[0]
