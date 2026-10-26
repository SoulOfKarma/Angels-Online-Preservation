"""Map transitions and native production, without touching live accounts."""
import copy
import json
import struct
from types import SimpleNamespace

import pytest
from test_competiciones import world,stored
import app,login,production_sites as sites,recent_mall


def router(world):
    result=app.Servidor.__new__(app.Servidor);result.mundos=world.players
    return result


@pytest.mark.parametrize('stage',[41,3,26,29,38,88])
@pytest.mark.parametrize('category',[1,2,3,5,6])
def test_original_station_click_opens_native_recipe_window(world,stage,category):
    s=world.player();p=s.personaje;p.stage=stage
    p.habilidades=[(sites.SKILLS[category],200,0)]
    station=next(r for r in sites.stations(stage) if r['category']==category)
    p.tile_x,p.tile_y=station['tile']
    assert app._recurso_con_entidad(stage,station['entity'])==station['tile']
    router(world).manejar(s,5,None,None,'test',struct.pack('<IB',station['entity'],0))
    assert struct.pack('<HB',0x4b,category) in s.packets
    assert sites.context(s)['category']==category


@pytest.mark.parametrize('stage',[41,3,26,29,38,88,500])
def test_native_recipe_atomic_material_consumption_and_product(world,monkeypatch,stage):
    s=world.player(items={20:35});p=s.personaje;p.stage=stage
    p.habilidades=[(26,200,0)];world.save(s)
    if stage==500:
        station=__import__('house_services').PRODUCTION[500022]
        p.tile_x,p.tile_y=station[1];s.house_make_station=500022
        monkeypatch.setattr(app,'_casa_actual',lambda _:SimpleNamespace(owner_id=p.char_id,level=2,cleanliness=100))
    else:
        station=next(r for r in sites.stations(stage) if r['category']==6)
        p.tile_x,p.tile_y=station['tile'];assert sites.open_station(s,6)
    callbacks=[]
    loop=SimpleNamespace(call_later=lambda delay,fn:callbacks.append(fn) or SimpleNamespace(cancelled=lambda:False))
    monkeypatch.setattr(__import__('asyncio'),'get_event_loop',lambda:loop)
    router(world).manejar(s,0x36,None,None,'test',struct.pack('<I',1))
    assert len(callbacks)==1 and s.inventario=={20:35}
    callbacks.pop()()
    assert 35 not in s.inventario.values() and 52 in s.inventario.values()
    assert stored(world,s)['custom_field']=='preserve me'
    assert struct.pack('<HBI',0x4c,1,1) in s.packets


def test_production_cannot_run_remotely_or_after_leaving_or_change_character(world,monkeypatch):
    s=world.player(items={20:35});p=s.personaje;p.stage=41;p.habilidades=[(26,200,0)]
    p.tile_x,p.tile_y=207,52;sites.open_station(s,6);world.save(s)
    pending=[]
    loop=SimpleNamespace(call_later=lambda delay,fn:pending.append(fn) or SimpleNamespace(cancelled=lambda:False))
    monkeypatch.setattr(__import__('asyncio'),'get_event_loop',lambda:loop)
    before=copy.deepcopy(stored(world,s));sites.craft(s,1)
    p.tile_x+=10;pending.pop()()
    assert s.inventario=={20:35} and stored(world,s)==before
    sites.craft(s,1);assert not pending
    p.tile_x-=10;sites.craft(s,1)
    s.personaje=world.player().personaje
    pending.pop()()
    assert s.inventario=={20:35} and stored(world,SimpleNamespace(personaje=p,usuario=s.usuario))==before


def test_scene_sequence_uses_live_inventory_and_no_captured_empty_social_lists(world):
    __import__('cuentas')._init_db()
    s=world.player(items={121:35,154:35,156:512,159:515})
    s.personaje.stage=41
    packets=login.secuencia(s.personaje)
    assert not any(p[:2] in (b'\x27\0',b'\x40\0') for p in packets)
    inventory=next(p for p in packets if p[:2]==b'\x1a\0')
    assert struct.unpack_from('<I',inventory,2)[0]>=4
    # The complete inventory includes backpack and reserved game-card cells.
    for slot in (121,154,156,159):
        entry=__import__('inventario')._entrada(s.personaje.char_id,slot,s.inventario[slot],1,None,s.personaje.entity_id)
        assert entry in inventory


def test_exchange_services_only_spawn_in_lyceum_and_sellers_are_accessible(world):
    import transitable
    assert recent_mall.poblar(41)
    for stage in [3,26,29,38,88]:assert not recent_mall.poblar(stage)
    for stage in [3,26,29,38]:
        data=json.loads((login.PLANTILLAS/app.mapas_poblados()[stage]).read_text(encoding='utf8'))
        for npc in data['spawns']:
            if npc['nombre'] not in ('W. Plan Seller','A. Recipe Seller'):continue
            assert transitable.se_pisa(stage,*npc['tile'])
            assert min(max(abs(npc['tile'][0]-r['tile'][0]),abs(npc['tile'][1]-r['tile'][1])) for r in sites.stations(stage))>=4


def test_blueprint_use_unlocks_only_that_recipe_persists_and_populates_native_bitmap(world):
    s=world.player(items={20:72});p=s.personaje;p.habilidades=[(26,200,0)];world.save(s)
    assert 1 in sites.known(p) and 19 not in sites.known(p)
    router(world).manejar(s,0x2e,None,None,'test',struct.pack('<BI',20,0))
    assert 20 not in s.inventario and 19 in p.recetas
    assert stored(world,s)['recetas']==[19] and stored(world,s)['custom_field']=='preserve me'
    assert sites.learned_packet(p,19) in s.packets
    saved=stored(world,s)
    saved.update(char_id=p.char_id,ranura=0,barra=[],quests=[])
    restored=__import__('cuentas').personaje_de({'personajes':[saved]})
    assert restored.recetas==[19] and 19 in sites.known(restored)
    # Restore after a map transition: recipe1 was automatic, recipe19 learned.
    __import__('cuentas')._init_db();p.stage=41
    packet=next(b for b in login.secuencia(p) if b[:2]==b'\x02\0')
    for ident in [1,19]:assert packet[1877+ident//8]&(1<<(ident%8))
    p.recetas=[];assert not sites.bits(p)[19//8]&(1<<(19%8))


def test_unlearned_recipe_and_failed_blueprint_transaction_consume_nothing(world):
    import sqlite3
    s=world.player(items={20:72});p=s.personaje;p.stage=41;p.tile_x,p.tile_y=207,52
    p.habilidades=[(26,200,0)];world.save(s);sites.open_station(s,6)
    before=copy.deepcopy(stored(world,s));sites.craft(s,19)
    assert any(b'Learn this production' in packet for packet in s.packets)
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_plan BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):sites.use_plan(s,20)
    assert stored(world,s)==before and not p.recetas and s.inventario=={20:72}


@pytest.mark.parametrize('stage,entity,expected_shop',[(3,121676,19),(26,121876,19),(29,121971,19),(38,122132,20),(163,122899,114),(170,123011,118)])
def test_exact_merchant_tree_opens_shop_once_without_generic_second_menu(world,stage,entity,expected_shop):
    s=world.player();s.personaje.stage=stage
    srv=router(world)
    srv.manejar(s,5,None,None,'test',struct.pack('<IH',entity,0))
    menu=[p for p in s.packets if p[:2]==b'\x12\0' and len(p)>11]
    assert len(menu)==1
    s.packets.clear()
    srv.manejar(s,0xb,None,{'valor':10},'test',bytes([10]))
    shops=[p for p in s.packets if p[:2]==b'\x34\0']
    assert shops==[struct.pack('<HH',0x34,expected_shop)]
    assert not any(p[:2]==b'\x12\0' and p[2:]!=bytes(9) for p in s.packets)


@pytest.mark.parametrize('box,contents',[(72059,[72043,72044,72045,72046]),(72060,[72047,72048,72049,72050,72051]),(72061,[72052,72053,72054,72055])])
def test_renewal_boxes_open_exact_contents(world,box,contents):
    s=world.player(items={20:box})
    router(world).manejar(s,0x2e,None,None,'test',struct.pack('<BI',20,0))
    assert sorted(s.inventario.values())==contents
    assert sorted(stored(world,s)['inventario'].values())==contents
