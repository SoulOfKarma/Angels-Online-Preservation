"""Original Blessing/Battlefield dialogue roots and safe registration lobby."""
import pathlib
import struct
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import app
import combate
import dialogos_mapa
import login
import lyceum_services


@pytest.fixture
def world(monkeypatch):
    p = login.Personaje(nivel=410, hp=100, hp_max=1000, mp=100, mp_max=1000,
                        stage=41, faction='Beasts')
    packets, timers, journeys = [], [], []
    s = SimpleNamespace(personaje=p, inventario=p.inventario, rol='mundo',
                        entity_id=p.entity_id, monstruos={}, usuario=None, muerto=False,
                        enviar=lambda *pk: packets.extend(pk),
                        enviar_inmediato=lambda *pk: packets.extend(pk))
    monkeypatch.setattr(app, '_stats_ses', lambda *a: b'')
    monkeypatch.setattr(app.asyncio, 'get_event_loop', lambda: SimpleNamespace(
        call_later=lambda delay, cb: timers.append((delay, cb))))
    monkeypatch.setattr(app, '_viajar_por_portal',
                        lambda ses, addr, portal, **kw: journeys.append(portal))
    return SimpleNamespace(p=p, s=s, packets=packets, timers=timers,
                           journeys=journeys, server=app.Servidor.__new__(app.Servidor))


def click(world, entity):
    world.server.manejar(world.s, 0x0005, None, None, 'test', struct.pack('<IH', entity, 0))


@pytest.mark.parametrize('level,mid,atk,matk', [(1, 6755, 100, 60), (50, 6755, 100, 60),
                                            (51, 6756, 200, 120), (410, 6756, 200, 120)])
def test_actual_blessing_menu_executes_xml_buff(world, level, mid, atk, matk):
    world.p.nivel = level
    click(world, 410)
    assert world.s.dlg_mapa['opciones'][1][0] == 5385
    node = dict(world.s.dlg_mapa['opciones'])[5385]
    assert app._recorrer_dialogo_mapa(world.s, 'test', 41, node)
    buff = world.p.buffs[mid]
    assert buff['atk'] == atk and buff['matk'] == matk
    assert world.timers[-1][0] == 7200
    assert (world.p.hp, world.p.mp) == (100, 100)


def test_blessing_upgrade_replaces_rank_without_stacking(world):
    world.p.nivel = 50
    lyceum_services.bendecir(world.s)
    world.p.nivel = 51
    lyceum_services.bendecir(world.s)
    assert set(world.p.buffs) == {6756}
    assert world.p.buffs[6756]['persist_death']


@pytest.mark.parametrize('faction,can_enter', [('Beasts', True), ('Heaven', False)])
def test_battlefield_angel_uses_its_own_menu_and_lobby_destination(world, faction, can_enter):
    world.p.faction = faction
    click(world, 408)
    node = dict(world.s.dlg_mapa['opciones'])[7547]
    app._recorrer_dialogo_mapa(world.s, 'test', 41, node)
    assert bool(world.journeys) is can_enter
    if can_enter:
        assert world.journeys[0]['destino'] == 114


def test_lobby_has_all_four_original_clerks(world):
    world.p.stage = 114
    packets = login.poblar(114)
    spawned = {struct.unpack_from('<I', p, 2)[0] for p in packets if p[:2] == b'\x08\x00'}
    assert spawned == {114001, 114002, 114003, 114004}
    for packet in packets:
        if packet[:2] == b'\x08\x00':
            assert packet[35] == 6
    assert sum(p[:2] == b'\x16\x00' for p in packets) == 4
    assert app._nombre_entidad(world.s, 114004) == 'High-Tier Clerk'
    click(world, 114004)
    assert struct.unpack_from('<I', world.packets[-1], 2)[0] == 8366


def test_unimplemented_battle_admission_cannot_consume_stone(world, monkeypatch):
    world.p.stage = 114
    world.p.inventario[20] = 8537
    tree = dialogos_mapa._arbol(114)
    node = next(k for k, n in tree.items()
                if any(a[0] == 9 for a in n.get('a', []))
                and any(a[0] in (71, 86) for a in n.get('a', [])))
    monkeypatch.setattr(dialogos_mapa, '_cumple', lambda *a: False)
    calls = []
    monkeypatch.setattr(app, '_aplicar_efectos', lambda *a: calls.append(a))
    assert app._recorrer_dialogo_mapa(world.s, 'test', 114, node)
    assert not calls and world.p.inventario[20] == 8537


def test_lobby_return_tornado_is_at_user_position(world):
    portal = app._portal_en(114, 23, 29)
    assert portal and portal['destino'] == 41
    assert portal['dibujar'] and not portal['preguntar']
    assert login.portales_de(114)[0][:2] == b'\x0e\x00'
    assert app._nombre_entidad(world.s, 114005) != 'Exit Guide'


def test_census_uses_its_faction_menu_and_portrait(world):
    world.p.nombre = 'KarmaV3'
    click(world, 49)
    packet = world.packets[-1]
    assert packet[:2] == b'\x12\x00'
    assert struct.unpack_from('<IH', packet, 2) == (5829, 46)
    assert packet[8] == 2  # "1", player name; never empty %1.
    assert b'KarmaV3\x00' in packet
    assert [o[0] for o in world.s.dlg_mapa['opciones']] == [5830, 5831, 5832]


def test_wolay_return_waits_for_second_dialogue_close(world, monkeypatch):
    import dialogos
    import misiones
    travels = []
    monkeypatch.setattr(misiones, 'interactuar_npc', lambda *a, **kw: (False, None, {}))
    monkeypatch.setattr(misiones, 'misiones_disponibles_npc', lambda *a, **kw: [])
    monkeypatch.setattr(app, '_cerrar_viaje', lambda *a: travels.append(a))
    click(world, 3)
    assert struct.unpack_from('<IH', world.packets[-1], 2) == (5079, 49)
    world.server.manejar(world.s, 0x000B, None, {'valor': dialogos.PRIMERA_OPCION}, 'test')
    assert struct.unpack_from('<I', world.packets[-1], 2)[0] == 5082
    assert not travels
    world.server.manejar(world.s, 0x000B, None, {'valor': 1}, 'test')
    assert len(travels) == 1


def test_census_information_option_uses_original_xml(world):
    import dialogos
    click(world, 49)
    world.server.manejar(world.s, 0x000B, None, {'valor': dialogos.PRIMERA_OPCION}, 'test')
    assert struct.unpack_from('<I', world.packets[-1], 2)[0] == 6211
    assert [o[0] for o in world.s.dlg_mapa['opciones']] == [6212, 6213]


@pytest.mark.parametrize('action', [29, 61])
def test_census_unsupported_transfer_cannot_charge_or_give_items(world, monkeypatch, action):
    tree = dialogos_mapa._arbol(41)
    node = next(k for k, n in tree.items()
                if any(a[0] == 20 for a in n.get('a', []))
                and any(a[0] == action for a in n.get('a', [])))
    calls = []
    monkeypatch.setattr(dialogos_mapa, '_cumple', lambda *a: False)
    monkeypatch.setattr(app, '_aplicar_efectos', lambda *a: calls.append(a))
    world.p.oro = 2_000_000_000
    world.p.inventario[20] = 8537
    assert app._recorrer_dialogo_mapa(world.s, 'test', 41, node)
    assert not calls
    assert world.p.oro == 2_000_000_000
    assert world.p.faction == 'Beasts' and world.p.inventario == {20: 8537}
    assert world.s.dlg_mapa is None
