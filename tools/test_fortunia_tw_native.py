"""Catalogo TW real, todas sus ramas y el catalogo antes mezclado con Noryo."""
import collections
import copy
import json
import struct

import pytest
from test_competiciones import world, stored
from test_competition_proxy_admission import click, answer
import app
import dialogos
import house_services as hs
import login
import recent_mall as rm
import restaurar_canjes_tw as build
import tw_migracion as tw

CONFIG=json.loads(build.CONFIG.read_text(encoding='utf-8'))
NATIVE=CONFIG['native_fortunia']
NPC=next(n for n in CONFIG['npcs'] if n['nombre']=='TW Fortunia')


def path_to(group):
    queue=collections.deque([(str(NPC['root']),[])])
    seen=set()
    while queue:
        key,path=queue.popleft()
        if key=='0' or key in seen:continue
        seen.add(key);node=CONFIG['nodes'][key]
        if [98,[group]] in node.get('a',[]):return path
        queue.extend((str(dest),path+[i]) for i,(_,dest) in enumerate(node.get('o',[])))
    raise AssertionError(group)


def open_native(s,group):
    s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=NPC['tile']
    click(s,NPC['entity_id'])
    for index in path_to(group):answer(s,index)
    assert s._recent_mall_npc=='TW Fortunia' and s._lyceum_exchange==group
    assert struct.pack('<HI',0x151,group) in s.packets


def total(s,item):
    return sum(s.cantidades.get(slot,1) for slot,value in s.inventario.items() if value==item)


def test_entire_native_catalog_keeps_every_original_cost_reward_and_flag():
    source=build.rows(tw.indice_tw()['setting\\eng\\exchange.xml'][1])
    current=hs.xml_rows('exchange.xml')
    groups={4,5,6,7,9,10,11,25,38,125,495,496,514,515,549,630,631}
    expected={key for key,row in source.items() if int(row['群組']) in groups}
    assert set(NATIVE['recipes'])==expected and len(expected)==838
    assert set(map(int,NATIVE['groups']))==groups
    for old,new in NATIVE['recipes'].items():
        before,after=source[old],current[new]
        assert 35389<=new<50000
        assert after['群組']==str(NATIVE['groups'][before['群組']])
        assert {k:v for k,v in before.items() if k not in ('編號','群組','獎賞說明')}=={
            k:v for k,v in after.items() if k not in ('編號','群組','獎賞說明')}
        assert after['獎賞說明'].isascii()


@pytest.mark.parametrize('group',list(NATIVE['groups'].values()))
def test_every_native_category_opens_by_actual_npc_click(world,group):
    s=world.player();open_native(s,group)
    assert any(r.get('群組')==str(group) for r in hs.xml_rows('exchange.xml').values())


def test_new_npc_is_spawned_once_and_original_services_are_preserved(world):
    spawns=login.poblar(41)
    for entity in (NPC['entity_id'],401,404):
        assert sum(pk[:2]==b'\x08\0' and struct.unpack_from('<I',pk,2)[0]==entity for pk in spawns)==1
    texts=dialogos._cargar_msg_dict()
    for key,value in CONFIG['messages'].items():assert texts[int(key)]==value and value.isascii()


def test_tw_fortunia_has_same_facing_height_and_y_as_original(world):
    spawns=login.poblar(41)
    def body(entity):
        return next(pk[2:] for pk in spawns if pk[:2]==b'\x08\0' and struct.unpack_from('<I',pk,2)[0]==entity)
    normal,clone=body(401),body(NPC['entity_id'])
    assert normal[12:16]==clone[12:16]
    assert normal[32:]==clone[32:]
    assert clone[33]==5 and clone[48:50]==bytes.fromhex('800c')


@pytest.mark.parametrize('source_id,reward,material',[(34639,68614,20228),(34640,68654,20229),
                                             (34641,68634,20230),(34642,68354,20231),
                                             (34643,83205,22658),(34648,83210,22658)])
def test_level_450_upgrades_and_perfect_gems_consume_native_cost_once(world,source_id,reward,material):
    rid=NATIVE['recipes'][str(source_id)]
    recipe=app._obtener_receta_exchange(rid)
    qty=81 if material==22658 else 103
    assert recipe['materiales']==[(material,qty)] and recipe['premios']==[(reward,1)]
    s=world.player(items={20:material});s.cantidades[20]=qty*2;world.save(s)
    open_native(s,int(hs.xml_rows('exchange.xml')[rid]['群組']))
    app.Servidor.__new__(app.Servidor).manejar(s,0x160,None,None,'test',struct.pack('<II',rid,1))
    assert total(s,material)==qty and total(s,reward)==1
    assert stored(world,s)['inventario']=={str(k):v for k,v in s.inventario.items()}


def test_native_exchange_requires_current_npc_and_range(world):
    s=world.player(items={20:20228});s.cantidades[20]=103;world.save(s)
    open_native(s,NATIVE['groups']['630']);before=copy.deepcopy(stored(world,s))
    s._recent_mall_npc='Fortunia'
    assert rm.canjear(s,NATIVE['recipes']['34639'],1) and stored(world,s)==before
    open_native(s,NATIVE['groups']['630']);s.personaje.tile_x=200
    assert rm.canjear(s,NATIVE['recipes']['34639'],1) and stored(world,s)==before


def test_all_199_former_noryo_extras_are_translated_and_directly_reachable(world):
    catalog=CONFIG['anniversary_catalog'];current=hs.xml_rows('exchange.xml')
    original=build.rows(build.SOURCE)
    expected={int(k) for k,r in original.items() if r['群組']=='607' and int(k)>22684}
    assert set(catalog['recipe_ids'])==expected and len(expected)==199
    for rid in expected:
        before,after=original[str(rid)],current[rid]
        assert after['群組']==str(catalog['group'])
        assert not tw.RE_CJK.search(after['獎賞說明'])
        assert {k:v for k,v in before.items() if k not in ('群組','獎賞說明')}=={
            k:v for k,v in after.items() if k not in ('群組','獎賞說明')}
    s=world.player();s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=174,82
    click(s,401)
    index=next(i for i,(mid,_) in enumerate(s.dlg_mapa['opciones']) if mid==catalog['message'])
    answer(s,index)
    assert struct.pack('<HI',0x151,catalog['group']) in s.packets
    assert s._recent_mall_npc=='Fortunia' and s._lyceum_exchange==catalog['group']


@pytest.mark.parametrize('rid,materials,reward',[(29625,[(70008,55)],35776),
        (29627,[(70010,1),(70009,1),(70008,50)],70161)])
def test_former_noryo_keys_and_410_sets_can_be_exchanged_and_saved(world,rid,materials,reward):
    items={20+i:item for i,(item,_) in enumerate(materials)}
    s=world.player(items=items)
    s.cantidades.update({20+i:qty for i,(_,qty) in enumerate(materials)});world.save(s)
    s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=174,82;click(s,401)
    answer(s,next(i for i,(mid,_) in enumerate(s.dlg_mapa['opciones']) if mid==994100))
    recipe=app._obtener_receta_exchange(rid)
    assert recipe['materiales']==materials and recipe['premios']==[(reward,1)]
    app.Servidor.__new__(app.Servidor).manejar(s,0x160,None,None,'test',struct.pack('<II',rid,1))
    assert total(s,reward)==1 and all(total(s,item)==0 for item,_ in materials)
    assert stored(world,s)['inventario']=={str(k):v for k,v in s.inventario.items()}
