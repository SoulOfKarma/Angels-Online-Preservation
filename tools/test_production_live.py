"""Live recipe updates, producer orders, graduated exit and friend counters."""
import copy
import sqlite3
import struct
from types import SimpleNamespace

import pytest
from test_competiciones import world,stored
import app,amigos,house_services as hs,misiones,production_sites as sites


def router(world):
    server=app.Servidor.__new__(app.Servidor);server.mundos=world.players
    return server


def recipe_updates(s):
    result=set()
    for packet in s.packets:
        if packet[:2]!=b'\x1d\0':continue
        count=packet[6]
        assert len(packet)==7+9*count
        for index in range(count):
            kind,ident,enabled=struct.unpack_from('<BII',packet,7+9*index)
            # Native5F0EF0 uses base17416, not the simple-attribute base16104.
            assert kind==11 and enabled==1
            result.add(ident)
    return result


def test_blueprint_updates_client_immediately_without_map_or_window_reload(world):
    s=world.player(items={20:72});s.personaje.habilidades=[(26,200,0)];world.save(s)
    before_scene=s.personaje.stage
    router(world).manejar(s,0x2e,None,None,'test',struct.pack('<BI',20,0))
    assert recipe_updates(s)=={19}
    assert stored(world,s)['recetas']==[19]
    assert s.personaje.stage==before_scene and not world.trips
    assert not any(p[:2] in (b'\x02\0',b'\x4b\0') for p in s.packets)
    s.packets.clear();sites.window(s,6)
    assert 19 in recipe_updates(s) and s.packets[-1]==struct.pack('<HB',0x4b,6)


@pytest.mark.parametrize('branch,skill',[('weapon',26),('armor',27),('sewing',28),('craft',29),('cooking',31),('all',None)])
def test_gm_learns_exact_branch_and_level_persists_and_updates_now(world,branch,skill):
    s=world.player(items={20:35});before=copy.deepcopy(s.inventario)
    expected={i for i,r in hs.xml_rows('make.xml').items() if 0<i<=4096
              and int(r['\u6280\u80fd1']) in ({skill} if skill else set(sites.SKILLS.values()))
              and int(r['\u7b49\u7d1a1'])<=200}
    assert app._probar_gm(s,('/recipes %s 200'%branch).encode(),'test')
    assert set(s.personaje.recetas)==expected==recipe_updates(s)
    assert set(stored(world,s)['recetas'])==expected
    assert stored(world,s)['custom_field']=='preserve me' and s.inventario==before
    s.packets.clear();app._probar_gm(s,('/recetas %s 200'%branch).encode(),'test')
    assert set(s.personaje.recetas)==expected
    assert any(b'Learned 0 production recipes' in p for p in s.packets)


def test_gm_recipe_database_failure_does_not_publish_uncommitted_learning(world):
    s=world.player(items={20:35});before=copy.deepcopy(stored(world,s))
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_recipe BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):app._probar_gm(s,b'/recipes weapon 200','test')
    assert not s.personaje.recetas and not recipe_updates(s) and stored(world,s)==before


@pytest.mark.parametrize('roll,expected',[(0,602),(9159210,158),(9979490,162)])
def test_bought_blueprint_can_manufacture_original_quality_variants(world,monkeypatch,roll,expected):
    s=world.player(items={20:72,21:52,22:114});p=s.personaje;p.stage=41
    p.habilidades=[(26,200,0)];s.cantidades.update({21:15,22:15});world.save(s)
    router(world).manejar(s,0x2e,None,None,'test',struct.pack('<BI',20,0))
    p.tile_x,p.tile_y=207,52;sites.open_station(s,6)
    pending=[]
    loop=SimpleNamespace(call_later=lambda delay,fn:pending.append(fn) or SimpleNamespace(cancelled=lambda:False))
    monkeypatch.setattr(__import__('asyncio'),'get_event_loop',lambda:loop)
    monkeypatch.setattr(sites.random,'randrange',lambda stop:0 if stop==100 else roll)
    router(world).manejar(s,0x36,None,None,'test',struct.pack('<I',19))
    assert len(pending)==1
    pending.pop()()
    assert list(s.inventario.values())==[expected]
    assert list(stored(world,s)['inventario'].values())==[expected]
    assert struct.pack('<HBI',0x4c,1,19) in s.packets


@pytest.mark.parametrize('ticket,item',[(1,35),(1648,886),(1697,887),(1746,897),(1795,898),(1844,None)])
def test_copper_gathering_uses_local_order_rate_and_original_corresponding_items(world,monkeypatch,ticket,item):
    s=world.player();s.personaje.stage=41
    monkeypatch.setattr(app,'_cuenta_de_veta',lambda *args:[0,0])
    monkeypatch.setattr(__import__('lyceum_services'),'straw_drop',lambda *args:[])
    monkeypatch.setattr(misiones,'verificar_progreso_recoleccion',lambda *args:[])
    def draw(start,end):
        assert (start,end)==(1,1960)
        return ticket
    monkeypatch.setattr(app.random,'randint',draw)
    assert app._sacar_de_veta(s,'test',41,999,app._material(1),1)
    assert list(s.inventario.values())==([] if item is None else [item])
    assert list(stored(world,s)['inventario'].values())==([] if item is None else [item])


def test_order_tables_cover_every_gathering_profession_with_matching_items():
    orders=hs.xml_rows('order.xml');order_items={int(r.get('\u8a02\u55ae\u539f\u578b') or 0) for r in orders.values()}
    seen=set()
    for ident,row in hs.xml_rows('material.xml').items():
        skill=row.get('\u4f7f\u7528\u6280\u80fd')
        if skill not in app.SKILL_POR_MATERIAL:continue
        mat=app._material(ident)
        if mat and any(item in order_items and weight>0 for item,weight in mat['items']):seen.add(skill)
    assert seen==set(app.SKILL_POR_MATERIAL)
    assert [(int(r['\u6210\u54c1\u7de8\u865f']),int(r['\u6210\u54c1\u6578\u91cf'])) for r in orders.values() if r.get('\u8a02\u55ae\u539f\u578b')=='886']==[(52,30)]


@pytest.mark.parametrize('faction,city',[('Aurora',3),('Beasts',29),('Steel',38),('Shadow',26)])
def test_graduated_wolay_keeps_return_menu_despite_missing_tutorial_history(world,faction,city):
    s=world.player(level=200);p=s.personaje;p.stage=41;p.faction=faction;p.quests=[]
    p.tile_x,p.tile_y=131,65
    assert 100 not in misiones.misiones_disponibles_npc(p,'Director Wolay',stage=41,entidad=3)
    srv=router(world);srv.manejar(s,5,None,None,'test',struct.pack('<IH',3,0))
    dialog=next(packet for packet in s.packets if packet[:2]==b'\x12\0')
    assert struct.unpack_from('<I',dialog,2)[0]==5079
    assert not any(q==100 for q,_ in p.quests)
    srv.manejar(s,0xb,None,{'valor':10},'test',bytes([10]))
    for _ in range(5):
        if world.trips:break
        srv.manejar(s,0xb,None,{'valor':1},'test',b'\1')
    assert world.trips and world.trips[-1][1]==city


def test_ungraduated_wolay_still_offers_original_registration():
    p=__import__('login').Personaje(stage=41,faction='Heaven',nivel=1,quests=[])
    assert 100 in misiones.misiones_disponibles_npc(p,'Director Wolay',stage=41,entidad=3)


def test_online_offline_friend_counters_follow_native_vector_transitions(world):
    a,b,c=world.player(),world.player(),world.player();srv=router(world)
    amigos._PENDIENTES.clear()
    for friend in (b,c):
        srv.manejar(a,0x19,None,None,'test',friend.personaje.nombre.encode().ljust(17,b'\0')+bytes(4))
        srv.manejar(friend,0x1b,None,None,'test',bytes(4))
    online=set();offline=set()
    def apply():
        for packet in a.packets:
            op=struct.unpack_from('<H',packet)[0]
            if op==0x27:
                online.clear();offline.clear()
                offline.update(struct.unpack_from('<I',packet,10+42*i)[0] for i in range(struct.unpack_from('<I',packet,6)[0]))
            elif op==0x28:  # native570000 moves online even when status says10
                cid=struct.unpack_from('<I',packet,28)[0];online.add(cid);offline.discard(cid)
                assert struct.unpack_from('<I',packet,24)[0]==0
            elif op==0x2e:  # native571AD0 performs the actual offline move
                assert len(packet)==10
                cid=struct.unpack_from('<I',packet,6)[0];offline.add(cid);online.discard(cid)
        a.packets.clear()
    b.conectado=False;a.packets.clear();amigos.sincronizar(a,world.players);apply()
    assert (len(online),len(offline))==(1,1)
    c.desconectado=True
    for _ in range(2):amigos.sincronizar(c,world.players,notify=True,offline=True);apply()
    assert (len(online),len(offline))==(0,2)
    b.conectado=True;amigos.sincronizar(b,world.players,notify=True);apply()
    assert (len(online),len(offline))==(1,1)
    amigos._PENDIENTES.clear()
