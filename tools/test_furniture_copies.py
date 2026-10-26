"""Exercise duplicate decorations through native inventory, layout and SQL saves."""
import copy
import sqlite3
import struct

import pytest
from test_competiciones import world, stored
import app
import casas
import inventario
import login

REAL_REFRESH = app._refrescar


@pytest.fixture(autouse=True)
def inventory_sequence(monkeypatch):
    # Exercise the real scene inventory branch without unrelated guild tables.
    rows = [m for m in login._cargar_secuencia() if m['opcode'] == 0x001A]
    assert rows
    monkeypatch.setattr(login, '_SEC', rows)


def inventory_packet(p):
    packet = next(pkt for pkt in login.secuencia(p) if pkt[:2] == b'\x1a\0')
    count = struct.unpack_from('<I', packet, 2)[0]
    pos, rows = 6, {}
    for _ in range(count):
        item = struct.unpack_from('<I', packet, pos + 9)[0]
        slot = struct.unpack_from('<H', packet, pos + 38)[0]
        rows[slot] = (item, packet[pos + 1:pos + 9])
        pos += 86 + struct.unpack_from('<H', packet, pos + 51)[0]
    assert pos == len(packet)
    return rows


def entry(uid, item=73230, x=100):
    return dict(item_id=item, item_uid=int.from_bytes(uid, 'little'),
                dir=0, x=x, y=100, state=0, extra=0, expire=0)


def editor(world):
    s = world.player(items={slot:73230 for slot in range(377, 384)})
    c = casas.CasaData(s.personaje.char_id, s.personaje.nombre, deed_id=17935)
    s.personaje.stage = casas.STAGE_HOUSE
    s.casa_visitando = c
    s.house_furnishing = True
    c.is_open = False
    s.personaje.casa = c.serializar()
    return s, c


def save_layout(s, entries, name=b'Test House'):
    keys = ('item_id', 'item_uid', 'dir', 'x', 'y', 'state', 'extra', 'expire')
    body = struct.pack('<I17s', len(entries), name)
    body += b''.join(casas._FURNITURE_RECORD.pack(*(e[k] for k in keys)) for e in entries)
    app.Servidor.__new__(app.Servidor).manejar(s, 0x13b, None, None, 'test', body)


def stock(s):
    return {slot:item for slot, item in s.inventario.items() if 377 <= slot <= 476}


def assert_visible_copies(s, c, expected):
    rows = inventory_packet(s.personaje)
    copies = [uid for slot, (item, uid) in rows.items() if 377 <= slot <= 476]
    placed_ids = {e['item_uid'] for e in c.placed_furniture}
    assert len(copies) == len(set(copies)) == expected
    assert all(any(uid) and int.from_bytes(uid, 'little') not in placed_ids for uid in copies)
    assert all(app._inst(s, slot) == uid for slot, (_, uid) in rows.items())


def test_scene_loading_gives_same_type_copies_stable_individual_ids(world):
    s, c = editor(world)
    rows = inventory_packet(s.personaje)
    assert_visible_copies(s, c, 7)
    assert inventory_packet(s.personaje) == rows
    assert app._instancias(s) is s.personaje._instancias


def test_select_last_copy_save_twice_add_another_and_retrieve_first(world):
    s, c = editor(world)
    rows = inventory_packet(s.personaje)
    first = entry(rows[383][1])
    second = entry(rows[381][1], x=140)
    save_layout(s, [first])
    assert set(stock(s)) == set(range(377, 383))
    assert c.placed_furniture == [first]
    assert_visible_copies(s, c, 6)
    save_layout(s, [first])
    assert len(stock(s)) == 6
    save_layout(s, [first, second])
    assert set(stock(s)) == {377, 378, 379, 380, 382}
    assert_visible_copies(s, c, 5)
    save_layout(s, [second])
    assert len(stock(s)) == 6 and c.placed_furniture == [second]
    assert app._inst(s, 381) == rows[383][1]
    assert_visible_copies(s, c, 6)
    persisted = stored(world, s)
    assert casas.CasaData.deserializar(persisted['casa']).placed_furniture == [second]
    assert sum(377 <= int(slot) <= 476 for slot in persisted['inventario']) == 6
    assert persisted['custom_field'] == 'preserve me'


def test_replace_placed_copy_with_same_type_consumes_and_returns_exact_ids(world):
    s, c = editor(world)
    rows = inventory_packet(s.personaje)
    first, replacement = entry(rows[383][1]), entry(rows[380][1])
    save_layout(s, [first])
    save_layout(s, [replacement])
    assert len(stock(s)) == 6 and c.placed_furniture == [replacement]
    assert app._inst(s, 380) == rows[383][1]
    assert_visible_copies(s, c, 6)


def test_save_sends_native_delta_only_for_selected_copy_and_returns_its_id(world, monkeypatch):
    monkeypatch.setattr(app, '_refrescar', REAL_REFRESH)
    s, _ = editor(world)
    rows = inventory_packet(s.personaje)
    selected = entry(rows[383][1])
    save_layout(s, [selected])
    updates = [pkt for pkt in s.packets if pkt[:2] == b'\x1b\0']
    assert updates == [inventario.vaciar_ranura(s.personaje.entity_id, 383)]
    s.packets.clear()
    save_layout(s, [])
    updates = [pkt for pkt in s.packets if pkt[:2] == b'\x1b\0']
    assert len(updates) == 1
    assert updates[0][7:15] == rows[383][1]
    assert struct.unpack_from('<I', updates[0], 15)[0] == 73230
    assert struct.unpack_from('<H', updates[0], 44)[0] == 383


def test_reconnect_rebuilds_independent_stock_ids_around_saved_placements(world):
    s, c = editor(world)
    rows = inventory_packet(s.personaje)
    save_layout(s, [entry(rows[383][1])])
    saved = stored(world, s)
    p = login.Personaje(char_id=s.personaje.char_id, nombre=s.personaje.nombre,
                        stage=casas.STAGE_HOUSE, casa=saved['casa'],
                        inventario={int(slot):item for slot, item in saved['inventario'].items()})
    rows = inventory_packet(p)
    ids = [uid for slot, (_, uid) in rows.items() if 377 <= slot <= 476]
    assert len(ids) == len(set(ids)) == 6
    assert all(int.from_bytes(uid, 'little') != c.placed_furniture[0]['item_uid'] for uid in ids)


def test_legacy_duplicate_ids_are_repaired_without_consuming_hidden_stock(world):
    s, c = editor(world)
    legacy = inventario.instancia_de(s.personaje.char_id, 73230)
    c.placed_furniture = [entry(legacy)]
    s.personaje.casa = c.serializar()
    app._instancias(s).update({slot:legacy for slot in stock(s)})
    before = stored(world, s)
    assert_visible_copies(s, c, 7)
    assert len(stock(s)) == 7 and stored(world, s) == before


@pytest.mark.parametrize('uid', [b'unknown!', b'\xff' * 8])
def test_unknown_copy_id_cannot_consume_another_copy_of_same_type(world, uid):
    s, c = editor(world)
    inventory_packet(s.personaje)
    before = copy.deepcopy(stored(world, s))
    save_layout(s, [entry(uid)])
    assert not c.placed_furniture and len(stock(s)) == 7
    assert stored(world, s) == before
    assert any(b'missing furniture copy' in pkt for pkt in s.packets)


def test_save_failure_restores_copy_binding_layout_name_and_character_data(world):
    s, c = editor(world)
    rows = inventory_packet(s.personaje)
    first = entry(rows[383][1])
    s.personaje.mejoras[383] = {'vinculacion':{'dueno':s.personaje.char_id}, 'custom':42}
    world.save(s)
    before_sql = stored(world, s)
    before = copy.deepcopy((s.inventario, s.cantidades, app._instancias(s),
                            s.personaje.mejoras, s.personaje.casa, c.serializar()))
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER furniture_fail BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    save_layout(s, [first], name=b'Changed name')
    after = (s.inventario, s.cantidades, app._instancias(s),
             s.personaje.mejoras, s.personaje.casa, c.serializar())
    assert after == before and stored(world, s) == before_sql
    assert any(b'could not be saved' in pkt for pkt in s.packets)


def test_session_instance_map_changes_with_character(world):
    s, c = editor(world)
    original = inventory_packet(s.personaje)
    app._instancias(s)
    other = world.player(items={377:73230})
    s.personaje = other.personaje
    rows = inventory_packet(s.personaje)
    assert app._inst(s, 377) == rows[377][1] != original[377][1]
    assert app._instancias(s) is app._instancias(other)


def test_registered_copy_keeps_its_id_through_scene_reload(world):
    import furniture_items
    s = world.player(items={20:73230, 21:73230})
    inventory_packet(s.personaje)
    assert furniture_items.usar(s, 20) and furniture_items.usar(s, 21)
    ids = {slot:app._inst(s, slot) for slot in (377, 378)}
    rows = inventory_packet(s.personaje)
    assert ids[377] != ids[378]
    assert {slot:rows[slot][1] for slot in ids} == ids


def test_cardbook_commit_keeps_scene_and_inventory_instance_maps_shared(world):
    import cartas
    s, _ = editor(world)
    inventory_packet(s.personaje)
    plan = cartas._copia(s)
    new_id = inventario.instancia_nueva()
    app._instancias(plan)[383] = new_id
    cartas._confirmar(s, plan)
    assert inventory_packet(s.personaje)[383][1] == app._inst(s, 383) == new_id
