"""Canjes TW separados de IGG, acceso real por Fortunia y persistencia atomica."""
import collections
import copy
import json
import pathlib
import sqlite3
import struct

import pytest
from test_competiciones import world, stored
from test_competition_proxy_admission import click, answer
import app
import dialogos
import house_services as hs
import recent_mall as rm
import restaurar_canjes_tw as build

CONFIG = json.loads(build.CONFIG.read_text(encoding='utf-8'))


def path_to_group(group):
    pending = collections.deque([('990200', [])])
    seen = set()
    while pending:
        key, path = pending.popleft()
        if key in seen or key == '0': continue
        seen.add(key)
        node = CONFIG['nodes'][key]
        if [98,[group]] in node.get('a',[]): return path
        pending.extend((str(dest), path+[index]) for index,(_,dest) in enumerate(node.get('o',[])))
    raise AssertionError(group)


def open_group(s, group):
    s.personaje.stage = 41
    s.personaje.tile_x, s.personaje.tile_y = 174,82
    click(s,401)
    assert [mid for mid,_ in s.dlg_mapa['opciones']] == [504132,504825,505907,510922,511419,994100,5020]
    answer(s,0)
    assert s.dlg_mapa['opciones'][6] == (990200,990200)
    answer(s,6)
    for index in path_to_group(group): answer(s,index)
    assert s._lyceum_exchange == group and s._recent_mall_npc == 'Fortunia'
    assert struct.pack('<HI',0x151,group) in s.packets


def simple_recipe():
    return next(rid for rid in CONFIG['recipe_ids']
                if hs.xml_rows('exchange.xml')[rid]['群組'] == str(CONFIG['group_map']['443'])
                and '材料2' not in hs.xml_rows('exchange.xml')[rid])


def total(s,item):
    return sum(s.cantidades.get(slot,1) for slot,i in s.inventario.items() if i == item)


def test_all_removed_recipes_keep_native_costs_rewards_and_separate_groups():
    source = build.rows(build.SOURCE)
    original = build.rows(build.ORIGINAL)
    current = hs.xml_rows('exchange.xml')
    assert len(CONFIG['recipe_ids']) == 8470 and len(CONFIG['group_map']) == 191
    for key in CONFIG['recipe_ids']:
        old, now = source[str(key)], current[key]
        assert int(now['群組']) == CONFIG['group_map'][old['群組']] >= 2000
        assert {k:v for k,v in now.items() if k not in ('群組','獎賞說明')} == {
            k:v for k,v in old.items() if k not in ('群組','獎賞說明')}
    for key,row in original.items():
        assert {k:v for k,v in current[int(key)].items() if k != '獎賞說明'} == {
            k:v for k,v in row.items() if k != '獎賞說明'}
    assert sum(r.get('群組') == '607' for r in current.values()) == 2


def test_2026_anniversary_recipes_use_a_separate_group_without_replacing_igg():
    import tw_migracion as migration
    source_path = migration.indice_tw(True)['setting\\eng\\exchange.xml'][1]
    source = migration.filas(migration.leer(source_path))
    sample = migration.atributos(next(iter(source.values())))
    group_key = list(sample)[1]
    source_rows = [(key, migration.atributos(row)) for key, row in source.items()
                   if migration.atributos(row).get(group_key) == '683']
    current = hs.xml_rows('exchange.xml')
    source_to_target = CONFIG['isolated_group_map']
    target_group = source_to_target['683']
    target_ids = CONFIG['new_group_recipe_ids']

    assert len(source_rows) == len(target_ids) == 65
    assert CONFIG['exchange_owners'][str(target_group)] == 'Anniversary Angel'
    assert rm.datos()['nodes']['2019294']['a'] == [[98, [target_group]]]
    assert rm.datos()['node_owners']['2019294'] == 'Anniversary Angel'
    assert current[33477]['群組'] == '683'
    assert current[33477]['獎賞1'] == '83008'
    for (source_id, source_row), target_id in zip(source_rows, target_ids):
        target_row = current[target_id]
        assert target_row['群組'] == str(target_group)
        assert target_row['獎賞說明'].isascii()
        assert {k: v for k, v in target_row.items()
                if k not in ('編號', '群組', '獎賞說明')} == {
                    k: v for k, v in source_row.items()
                    if k not in ('編號', '群組', '獎賞說明')}


def test_menu_labels_are_installed_english_and_every_group_is_reachable():
    texts = dialogos._cargar_msg_dict()
    for key,value in CONFIG['messages'].items():
        assert texts[int(key)] == value and value.isascii()
    for group in CONFIG['group_map'].values():
        assert path_to_group(group)
        assert rm.datos()['exchange_owners'][str(group)] == 'Fortunia'
    fashion = rm.datos()['nodes']['504816']['o']
    assert [517276,2022800] in fashion and [517355,2022800] not in fashion
    assert rm.datos()['nodes']['2022800']['a'] == [[98,[622]]]
    assert texts[514661].startswith("It's time for the 2026 Mall Anniversary!")
    assert texts[513667] == 'Anniversary Wave 1 (Badges)'


def test_fortunia_is_not_spawned_twice_and_original_shops_still_open(world):
    import login
    packets = login.poblar(41)
    assert sum(pk[:2] == b'\x08\0' and struct.unpack_from('<I',pk,2)[0] == 401 for pk in packets) == 1
    assert sum(pk[:2] == b'\x08\0' and struct.unpack_from('<I',pk,2)[0] == 404 for pk in packets) == 1
    s = world.player();s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=174,82
    click(s,401);answer(s,1)
    assert struct.pack('<HI',0x151,45) in s.packets


@pytest.mark.parametrize('index,group',list(enumerate((596,294,594,595,57,56))))
def test_original_fortunia_categories_open_populated_exchanges(world,index,group):
    s=world.player();s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=174,82
    click(s,401);answer(s,0);answer(s,index)
    assert struct.pack('<HI',0x151,group) in s.packets
    assert not any(pk[:2]==b'\x34\0' for pk in s.packets)
    assert any(row.get('群組')==str(group) for row in hs.xml_rows('exchange.xml').values())
    assert s._lyceum_exchange==group


@pytest.mark.parametrize('branch,index,group',[(1,i,374+i) for i in range(4)] +
                          [(2,i,g) for i,g in enumerate((378,379,380,381,382,477))])
def test_scrollmaker_full_native_menu_opens_each_exchange(world,branch,index,group):
    s=world.player();s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=169,71
    click(s,404)
    assert [mid for mid,_ in s.dlg_mapa['opciones']]==[513262,513265,513266,513263]
    answer(s,branch);answer(s,index)
    assert struct.pack('<HI',0x151,group) in s.packets
    assert s._lyceum_exchange==group and s._recent_mall_npc=='Scrollmaker'
    assert any(row.get('群組')==str(group) for row in hs.xml_rows('exchange.xml').values())


def test_real_fortunia_voucher_exchange_persists_exact_cost_and_reward(world):
    rid = simple_recipe();recipe=app._obtener_receta_exchange(rid)
    item,qty = recipe['materiales'][0]
    s=world.player(items={20:item});s.cantidades[20]=qty*2;world.save(s)
    before=stored(world,s)
    group=int(hs.xml_rows('exchange.xml')[rid]['群組'])
    open_group(s,group)
    app.Servidor.__new__(app.Servidor).manejar(s,0x160,None,None,'test',struct.pack('<II',rid,1))
    assert total(s,item)==qty
    for item,qty in recipe['premios']: assert total(s,item)==qty
    assert stored(world,s)['custom_field']==before['custom_field']
    assert stored(world,s)['inventario']=={str(k):v for k,v in s.inventario.items()}


def test_new_exchange_requires_its_npc_open_group_and_distance(world):
    rid=simple_recipe();recipe=app._obtener_receta_exchange(rid);item,qty=recipe['materiales'][0]
    s=world.player(items={20:item});s.cantidades[20]=qty;world.save(s)
    before=copy.deepcopy(stored(world,s))
    assert rm.canjear(s,rid,1)
    assert stored(world,s)==before
    group=int(hs.xml_rows('exchange.xml')[rid]['群組']);open_group(s,group)
    s.personaje.tile_x=200
    assert rm.canjear(s,rid,1)
    assert stored(world,s)==before and total(s,item)==qty


def test_failed_exchange_transaction_never_consumes_vouchers(world):
    rid=simple_recipe();recipe=app._obtener_receta_exchange(rid);item,qty=recipe['materiales'][0]
    s=world.player(items={20:item});s.cantidades[20]=qty;world.save(s)
    open_group(s,int(hs.xml_rows('exchange.xml')[rid]['群組']))
    before=copy.deepcopy(stored(world,s))
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_tw BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):rm.canjear(s,rid,1)
    assert stored(world,s)==before and total(s,item)==qty


def test_original_daily_limit_is_atomic_and_survives_reconnect(world):
    rid=32643;recipe=app._obtener_receta_exchange(rid);item,qty=recipe['materiales'][0]
    s=world.player(items={20:item});s.cantidades[20]=qty*12;world.save(s)
    group=int(hs.xml_rows('exchange.xml')[rid]['群組']);open_group(s,group)
    assert rm.canjear(s,rid,10)
    assert stored(world,s)['exchange_daily'][str(rid)]['used']==10
    before=copy.deepcopy(stored(world,s))
    assert rm.canjear(s,rid,1)
    assert stored(world,s)==before and total(s,item)==qty*2
    # El contador procede de SQLite, no de un atributo de la sesion.
    s._lyceum_exchange=None;open_group(s,group)
    assert rm.canjear(s,rid,1) and stored(world,s)==before
