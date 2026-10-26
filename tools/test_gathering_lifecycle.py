"""Real Samara drop pools and shared node disappearance/replenishment."""
import asyncio
import struct
from types import SimpleNamespace

import pytest
from test_competiciones import world, stored
import app, gathering_nodes as nodes, gathering_rewards as rewards, house_services as hs


@pytest.fixture
def timers(monkeypatch):
    pending = []
    monkeypatch.setattr(nodes, '_TIMERS', {})
    monkeypatch.setattr(app, '_VETAS_MUNDO', {})
    def later(delay, callback):
        handle = SimpleNamespace(cancel=lambda: None)
        pending.append((delay, callback))
        return handle
    monkeypatch.setattr(asyncio, 'get_event_loop', lambda: SimpleNamespace(call_later=later))
    return pending


def test_order_rate_is_exactly_ten_percent_for_every_original_order_pool():
    order_ids = rewards.order_items()
    covered = set()
    for mid, row in hs.xml_rows('material.xml').items():
        mat = app._material(mid)
        if not mat or not any(i in order_ids and w > 0 for i, w in mat['items']):
            continue
        items, empty = rewards.pool(mat)
        assert 10 * sum(w for i, w in items if i in order_ids) == sum(w for _, w in items) + empty
        # No new/unrelated orders and no changed relative normal/rare weights.
        assert {i for i, _ in items} == {i for i, _ in mat['items']}
        original = dict(mat['items'])
        for group in (order_ids, {i for i, _ in items} - order_ids):
            values = [(original[i], w) for i, w in items if i in group and original[i]]
            if values:
                a, b = values[0]
                assert all(x * b == y * a for x, y in values)
        covered.add(row.get('\u4f7f\u7528\u6280\u80fd'))
    assert set(app.SKILL_POR_MATERIAL) <= covered


@pytest.mark.parametrize('mid', [1, 381, 382, 383, 393])
def test_corresponding_orders_reach_inventory_and_database(world, monkeypatch, mid):
    s = world.player(); s.personaje.stage = 231
    monkeypatch.setattr(app, '_cuenta_de_veta', lambda *args: [0, 0])
    monkeypatch.setattr(__import__('lyceum_services'), 'straw_drop', lambda *args: [])
    items, empty = rewards.pool(app._material(mid)); boundary = 0
    for item, weight in items:
        if item in rewards.order_items():
            monkeypatch.setattr(rewards.random, 'randint', lambda a, b, t=boundary+1: t)
            assert app._sacar_de_veta(s, 'test', 231, 999, app._material(mid), mid)
            assert item in s.inventario.values() and item in stored(world, s)['inventario'].values()
        boundary += weight


def test_event_material_without_orders_keeps_original_pool():
    mat = app._material(639)
    assert rewards.pool(mat) == (tuple(map(tuple, mat['items'])), mat['no_produce'])


def resource():
    return next((r, mid) for r in app._recursos_de_plantilla(231)
                if (mid := app._veta_de(231, r['entity_id'])[0]) == 381)


def test_depletion_hides_shared_node_until_replenished_even_after_owner_leaves(world, monkeypatch, timers):
    a, b, outsider = world.player(), world.player(), world.player()
    a.personaje.stage = b.personaje.stage = 231
    row, mid = resource(); entity = row['entity_id']; mat = app._material(mid)
    counter = app._cuenta_de_veta(a, 231, entity, mat)
    counter[:] = [mat['limite']-1, 0]
    monkeypatch.setattr(rewards, 'roll', lambda mat: None)
    assert not app._sacar_de_veta(a, 'test', 231, entity, mat, mid)
    packet = struct.pack('<HI', 7, entity)
    assert a.packets.count(packet) == b.packets.count(packet) == 1
    assert packet not in outsider.packets
    nodes.depleted(a, 231, entity, mat, counter)
    assert len(timers) == 1 and timers[0][0] == mat['reponer']
    original = nodes._packets(231, entity)
    assert len(original) == 2 and not list(nodes.scene(b, original))
    a.personaje.stage = 41
    world.now[0] += mat['reponer']
    timers.pop()[1]()
    assert counter == [0, 0.0]
    assert all(b.packets.count(p) == 1 for p in original)
    assert not any(p in a.packets for p in original)
    assert list(nodes.scene(b, original)) == original


def test_late_scene_load_does_not_cancel_respawn_or_erase_fresh_progress(world, timers):
    s = world.player();s.personaje.stage = 231
    row, mid = resource();entity = row['entity_id'];mat = app._material(mid)
    counter = app._cuenta_de_veta(s, 231, entity, mat)
    counter[:] = [mat['limite'], world.now[0]]
    nodes.depleted(s, 231, entity, mat, counter)
    world.now[0] += mat['reponer']
    app._cuenta_de_veta(s, 231, entity, mat)[0] = 1
    timers.pop()[1]()
    assert counter == [1, 0.0]
    assert nodes._packets(231, entity)[0] in s.packets


def test_full_backpack_does_not_deplete_or_schedule_respawn(world, monkeypatch, timers):
    s = world.player();s.personaje.stage = 231
    row, mid = resource();entity = row['entity_id'];mat = app._material(mid)
    counter = app._cuenta_de_veta(s, 231, entity, mat);counter[0] = mat['limite']-1
    monkeypatch.setattr(rewards, 'roll', lambda mat: 15308)
    monkeypatch.setattr(app, '_meter', lambda *args: None)
    assert not app._sacar_de_veta(s, 'test', 231, entity, mat, mid)
    assert counter == [mat['limite']-1, 0.0] and not timers


def test_private_instance_respawn_never_leaks_to_another_run(world, monkeypatch, timers):
    a, same, other = world.player(), world.player(), world.player()
    for s in (a, same, other):s.personaje.stage = 73
    state_a, state_b = object(), object()
    monkeypatch.setattr(app, 'es_instancia', lambda st: st == 73)
    monkeypatch.setattr(__import__('eventos_mundo'), 'estado_de', lambda s: state_b if s is other else state_a)
    monkeypatch.setattr(nodes, '_packets', lambda *args: [b'node'])
    mat = dict(limite=1, reponer=90);counter = [1, world.now[0]]
    nodes.depleted(a, 73, 123, mat, counter)
    a.personaje.stage = 41
    timers.pop()[1]()
    assert b'node' in same.packets and b'node' not in other.packets


def test_healthy_scene_does_not_rescan_each_resources_template(world, monkeypatch, timers):
    s = world.player();s.personaje.stage = 231
    monkeypatch.setattr(app, '_veta_de', lambda *a: pytest.fail('No exhausted node needs resolving'))
    packets = [struct.pack('<HI', 14, entity) for entity in range(1000)]
    assert list(nodes.scene(s, packets)) == packets
