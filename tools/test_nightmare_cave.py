"""Native cave entry, dialogue reward icons and atomic original exchanges."""
import copy
import sqlite3
import struct

import pytest
from test_competiciones import world, stored
import app, dialogos_mapa as dm, eventos, eventos_mundo as em, login
import nightmare_cave as cave


def router(world):
    srv = app.Servidor.__new__(app.Servidor);srv.mundos = world.players
    return srv


def click(world, s, npc_type):
    entity, row = next((i, r) for i, r in cave.npcs(s.personaje.stage).items()
                       if r['npc_type'] == npc_type)
    s.personaje.tile_x, s.personaje.tile_y = row['tile']
    router(world).manejar(s, 5, None, None, 'test', struct.pack('<IH', entity, 0))
    return row


def action(world, s, value):
    router(world).manejar(s, 0xb, None, {'valor': value}, 'test', bytes([value]))


def selected_node(stage, action_number):
    return next(int(k) for k, node in dm._arbol(stage).items()
                if any(a == action_number for a, args in node.get('a', []))
                and (action_number != 20 or any(a == 10 and args[0] == 2852 for a, args in node.get('a', []))))


@pytest.mark.parametrize('stage', sorted(cave.HEAD_STAGES))
def test_heads_open_the_original_passport_menu_and_charge_once(world, stage):
    s = world.player(level=40, gold=50000);s.personaje.stage = stage
    click(world, s, 1920)
    packet = next(p for p in s.packets if p[:2] == b'\x12\0')
    assert struct.unpack_from('<I', packet, 2)[0] == 6000
    action(world, s, 12)  # Passport option; next text6013 offers OK/Quit.
    action(world, s, 1)
    action(world, s, 10)
    assert 2852 in s.inventario.values()
    assert stored(world, s)['oro'] == s.personaje.oro == s.oro == 0
    assert stored(world, s)['custom_field'] == 'preserve me'
    snapshot = copy.deepcopy(stored(world, s))
    # A replay of the confirmation cannot add a second permit or charge again.
    app._recorrer_dialogo_mapa(s, 'test', stage, selected_node(stage, 20))
    assert stored(world, s) == snapshot


@pytest.mark.parametrize('level,gold', [(39, 50000), (40, 49999)])
def test_passport_rejection_keeps_gold_and_inventory(world, level, gold):
    s = world.player(level=level, gold=gold);s.personaje.stage = 29
    click(world, s, 1920)
    before = stored(world, s)
    app._recorrer_dialogo_mapa(s, 'test', 29, selected_node(29, 20))
    assert stored(world, s) == before and not s.inventario


def test_failed_permit_transaction_never_delivers_or_charges(world):
    s = world.player(gold=50000);s.personaje.stage = 29
    click(world, s, 1920)
    before = stored(world, s)
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_pass BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):
        app._recorrer_dialogo_mapa(s, 'test', 29, selected_node(29, 20))
    assert stored(world, s) == before and not s.inventario and s.oro == 50000


@pytest.mark.parametrize('stage', sorted(cave.ENTRANCE_STAGES))
@pytest.mark.parametrize('has_pass', [False, True])
def test_four_field_entries_require_but_preserve_passport(world, stage, has_pass):
    s = world.player(items={20:2852} if has_pass else {});s.personaje.stage = stage
    click(world, s, 1923)
    if has_pass:
        entry_index = next(i for i, (message, _) in enumerate(s.dlg_mapa['opciones']) if message == 6020)
        action(world, s, 10 + entry_index)
        assert not world.trips and s.personaje.stage == stage
        assert struct.unpack_from('<I', s.packets[-1], 2)[0] == 6022
        action(world, s, 1)  # Finish the warning before the map transition.
        assert world.trips and world.trips[-1][1] == 61
        assert s.inventario[20] == 2852
    else:
        action(world, s, 10)
        assert not world.trips


def entry_warning(world, s):
    s.personaje.stage = 28
    click(world, s, 1923)
    action(world, s, 10)
    assert not world.trips and struct.unpack_from('<I', s.packets[-1], 2)[0] == 6022


def test_entry_closes_warning_before_sending_map_change_and_ignores_repeat(world, monkeypatch):
    s = world.player(items={20:2852})
    entry_warning(world, s)
    original = app._sincronizar_cambio_mapa
    close = b'\x12\0' + __import__('dialogos').FIN
    def travel(ses, stage, x, y):
        assert ses.packets[-1] == close
        ses.enviar(__import__('clases').cambiar_mapa(stage))
        original(ses, stage, x, y)
    monkeypatch.setattr(app, '_sincronizar_cambio_mapa', travel)
    action(world, s, 1)
    assert s.packets[-2] == close and s.packets[-1][:2] == b'\x0c\0'
    assert len(world.trips) == 1 and s.inventario[20] == 2852
    action(world, s, 1)
    assert len(world.trips) == 1


@pytest.mark.parametrize('reason', ['cancel', 'move', 'map', 'dead', 'pass', 'dialogue', 'npc'])
def test_pending_entry_is_cancelled_when_warning_or_admission_is_no_longer_valid(world, reason):
    s = world.player(items={20:2852})
    entry_warning(world, s)
    if reason == 'move':s.personaje.tile_x = 100
    elif reason == 'map':s.personaje.stage = 29
    elif reason == 'dead':s.muerto = True
    elif reason == 'pass':s.inventario.clear()
    elif reason == 'dialogue':
        s.dlg_guion = [__import__('dialogos').armar_linea(6019, 7, [])[2:]]
    elif reason == 'npc':click(world, s, 1923)
    action(world, s, 0 if reason == 'cancel' else 1)
    assert not world.trips and getattr(s, '_nightmare_entry', None) is None


def test_native_population_has_slarm_spirits_inspectors_and_no_unsummoned_bosses():
    rows = cave.npcs(61)
    assert {r['npc_type'] for r in rows.values()} == set(range(1921, 1928)) - {1923}
    mobs = app._monstruos_de(61)
    assert len(mobs) == 40 and all(m.npc_type == 436 for m in mobs.values())
    assert not any(m.agro for m in mobs.values())
    spawns = login.poblar(61)
    assert struct.pack('<I', 66100900) in b''.join(spawns)


@pytest.mark.parametrize('npc,stone,tag,attendants', [(1924,2848,71,4), (1925,2849,72,2),
                                                    (1926,2850,74,7), (1927,2851,73,2)])
def test_spirit_summons_boss_and_native_attendants_only_with_its_stone(world, monkeypatch, npc, stone, tag, attendants):
    s = world.player(items={20:stone});s.personaje.stage = 61
    s.cantidades[20] = 2;world.save(s)
    monkeypatch.setattr(em, 'estado_de', lambda ses: state)
    state = em.EstadoDeMapa(61)
    s.monstruos = {}
    click(world, s, npc)
    action(world, s, 10)
    assert s.inventario[20] == stone and s.cantidades[20] == 1
    assert stored(world, s)['cantidades']['20'] == 1
    assert len(s.monstruos) == 1 + attendants
    bosses = [m for m in s.monstruos.values() if m.zona_generador == tag]
    assert len(bosses) == 1 and bosses[0].vivo
    assert bosses[0].hp_max >= 200000
    before = len(s.monstruos)
    click(world, s, npc);action(world, s, 10)
    assert len(s.monstruos) == before and s.cantidades[20] == 1


@pytest.mark.parametrize('faction,destination', [('Aurora',8), ('Beasts',9), ('Steel',28), ('Shadow',25)])
def test_exit_portal_uses_original_faction_conditions(world, faction, destination):
    s = world.player();s.personaje.stage = 61;s.personaje.faction = faction
    portal = app._portal_en(61, 6, 5)
    assert portal and portal['evento_cliente']
    app._portal_por_evento(s, 'test', portal)
    assert world.trips[-1][1] == destination


def test_inspector_reward_icons_and_selection_spend_dream_pieces_atomically(world):
    s = world.player(items={20:3040});s.cantidades[20] = 10;world.save(s)
    s.personaje.stage = 61
    click(world, s, 1921)
    action(world, s, 11)  # Trade Dream Pieces.
    action(world, s, 10)  # Light armor group.
    preview = s.packets[-1]
    assert preview[:2] == b'\x12\0' and preview[10] == 5
    assert struct.unpack_from('<II', preview, len(preview)-40) == (2881,1)
    action(world, s, 10)  # Exchange confirmation -> choose one original item.
    selection = s.packets[-1]
    assert selection[10] == 0x85
    action(world, s, 22)  # Third reward, original item2883.
    assert 3040 not in s.inventario.values() and 2883 in s.inventario.values()
    assert list(stored(world, s)['inventario'].values()) == [2883]
    before = stored(world, s)
    action(world, s, 22)
    assert stored(world, s) == before


def test_inspector_cannot_exchange_after_leaving_or_without_pieces(world):
    s = world.player();s.personaje.stage = 61
    click(world, s, 1921)
    action(world, s, 11);action(world, s, 10);action(world, s, 10)
    action(world, s, 20)
    assert not s.inventario


def test_failed_stone_commit_cannot_create_a_boss(world):
    s = world.player(items={20:2848});s.personaje.stage = 61
    click(world, s, 1924)
    before = stored(world, s)
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_stone BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):
        action(world, s, 10)
    assert stored(world, s) == before and not s.monstruos and s.inventario[20] == 2848


def test_inspector_rechecks_position_before_consuming_pieces(world):
    s = world.player(items={20:3040});s.cantidades[20] = 10;world.save(s)
    s.personaje.stage = 61
    click(world, s, 1921)
    action(world, s, 11);action(world, s, 10);action(world, s, 10)
    before = stored(world, s)
    s.personaje.tile_x = 180
    action(world, s, 20)
    assert stored(world, s) == before and s.cantidades[20] == 10
