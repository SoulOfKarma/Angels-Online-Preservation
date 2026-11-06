"""La integracion que faltaba: script del cliente, menus reales y entregas de red."""
import json
import pathlib
import struct
from types import SimpleNamespace

import pytest
from test_competiciones import world
from test_taiwan_skills import combat
import app
import dialogos
import dialogos_mapa
import login
import misiones
import taiwan_skills as tw
from session import Session
from smart_script import simbolos
from auditar_flores_fragrant import auditar

ROOT = pathlib.Path(__file__).resolve().parents[1]
FLOWERS = auditar()


def test_installed_visual_script_has_every_new_cast_and_impact_function():
    data = (ROOT / 'extracted_paks/update26/script/magic.so').read_bytes()
    functions = simbolos(data)
    for effect in range(715, 734):
        assert functions['cast%03d' % effect][1] == 5
        assert functions['magic%03d' % effect][1] == 4
    for effect in (17, 19, 133, 136, 519, 546, 714):
        assert 'magic%03d' % effect in functions


def test_client_flower_and_merchant_texts_are_english_without_replacing_other_dialogue():
    import tw_migracion as migration
    rows = migration.filas(migration.leer(ROOT / 'extracted_paks/update26/setting/eng/msg.xml'))
    for mid in [*range(517382, 517406), *range(516871, 516876)]:
        text = migration.atributos(rows[str(mid)])['文字']
        assert text and not migration.RE_CJK.search(text), (mid, text)
        assert text.isascii(), (mid, text)
    assert 'greenhouse' in migration.atributos(rows['517404'])['文字']
    assert 'bright-yellow' in migration.atributos(rows['517396'])['文字']
    assert {flower['mensaje'] for flower in FLOWERS['flores']} == set(range(517396, 517400))


@pytest.mark.parametrize('eid,mid,shop', [(90425000, 516871, 228), (90425001, 516872, 227)])
def test_spell_and_stance_merchants_use_mpc_before_unrelated_quest(world, monkeypatch, eid, mid, shop):
    s = world.player()
    s.personaje.stage = 425
    s.personaje.tile_x, s.personaje.tile_y = 186, 97
    # It must never reach the portrait/name-based quest625 fallback.
    monkeypatch.setattr(misiones, 'interactuar_npc', lambda *a, **kw: pytest.fail('entered unrelated quest matcher'))
    server = app.Servidor('127.0.0.1', 0)
    server.manejar(s, 5, None, {}, 'test', struct.pack('<IH', eid, 0))
    assert any(pk[:2] == b'\x12\0' and struct.unpack_from('<I', pk, 2)[0] == mid for pk in s.packets)
    assert s.personaje.stage == 425
    option_node = s.dlg_mapa['opciones'][0][1]
    native = dialogos_mapa._arbol(425)[str(option_node)]
    assert [14, [shop]] in native['a']
    server.manejar(s, 0xb, None, {'valor': 10}, 'test', b'\x0a')
    assert any(pk[:2] == b'\x34\0' and struct.unpack_from('<H', pk, 2)[0] == shop for pk in s.packets)


@pytest.mark.parametrize('eid,shop', [(90425000, 228), (90425001, 227)])
def test_sand_skill_shops_open_even_if_the_mpc_shop_action_is_missing(
        world, monkeypatch, eid, shop):
    s = world.player()
    s.personaje.stage = 425
    s.personaje.tile_x, s.personaje.tile_y = (186, 97) if shop == 228 else (222, 113)
    server = app.Servidor('127.0.0.1', 0)
    server.manejar(s, 5, None, {}, 'test', struct.pack('<IH', eid, 0))

    choice_node = s.dlg_mapa['opciones'][0][1]
    tree = json.loads(json.dumps(dialogos_mapa._TODO))
    tree['425'][str(choice_node)] = {}
    monkeypatch.setattr(dialogos_mapa, '_TODO', tree)
    monkeypatch.setattr(
        dialogos_mapa, '_CON_SP',
        {stage: nodes for stage, nodes in dialogos_mapa._CON_SP.items() if stage != 425})
    s.packets.clear()

    server.manejar(s, 0xb, None, {'valor': 10}, 'test', b'\x0a')

    assert s.packets == [
        struct.pack('<HH', 0x0034, shop),
        struct.pack('<H', 0x0012) + dialogos.FIN,
    ]


@pytest.mark.parametrize('flower,route', [(flower, route) for flower in FLOWERS['flores']
                                        for route in flower['rutas']],
                         ids=['%s-tag%s' % (flower['entidad'], route['tag'])
                              for flower in FLOWERS['flores'] for route in flower['rutas']])
def test_every_flower_click_and_care_sequence_reaches_its_native_destination(world, flower, route):
    s = world.player()
    s.usuario = None
    s.personaje.stage = 428
    s.personaje.tile_x, s.personaje.tile_y = flower['tile']
    assert app._recurso_con_entidad(428, flower['entidad']) == tuple(flower['tile'])
    server = app.Servidor('127.0.0.1', 0)
    server.manejar(s, 5, None, {}, 'test', struct.pack('<IH', flower['entidad'], 0))
    assert any(pk[:2] == b'\x12\0' and struct.unpack_from('<I', pk, 2)[0] == flower['mensaje'] for pk in s.packets)
    assert [mid for mid, _ in s.dlg_mapa['opciones']] == [517400, 517401, 517402, 517403]
    for care in route['cuidados']:
        choice = [mid for mid, _ in s.dlg_mapa['opciones']].index(care)
        server.manejar(s, 0xb, None, {'valor': 10 + choice}, 'test', bytes([10 + choice]))
    x, y = route['destinos'][0]
    assert s.personaje.stage == 428
    assert (s.personaje.tile_x, s.personaje.tile_y) == (x, y)
    assert struct.pack('<HIII', 3, s.personaje.entity_id, x, y) in s.packets
    assert any(pk[:2] == b'\x12\0' and struct.unpack_from('<I', pk, 2)[0] == route['mensaje'] for pk in s.packets)
    # El aviso debe seguir abierto al llegar, como en el cliente TW.
    move_index = s.packets.index(struct.pack('<HIII', 3, s.personaje.entity_id, x, y))
    result_index = next(i for i, pk in enumerate(s.packets)
                        if pk[:2] == b'\x12\0' and struct.unpack_from('<I', pk, 2)[0] == route['mensaje'])
    assert result_index > move_index
    assert not any(pk[:2] == b'\x12\0' and not any(pk[2:]) for pk in s.packets[result_index + 1:])
    s.packets.clear()
    server.manejar(s, 0xb, None, {'valor': 1}, 'test', b'\x01')
    assert any(pk[:2] == b'\x12\0' and not any(pk[2:]) for pk in s.packets)
    assert not any(pk[:2] == b'\x03\0' for pk in s.packets)


def test_new_region_totems_match_captured_lyceum_name_visibility():
    original = json.loads((ROOT / 'server/plantillas/lyceum.json').read_text(encoding='utf-8'))
    expected = {e['nombre']: struct.unpack_from('<I', bytes.fromhex(e['hex']), 4)[0]
                for e in original['spawns'] if 'Totem' in e['nombre']}
    packets = login.poblar(425)
    totems = [pk for pk in packets if pk[:2] == b'\x08\0'
              and struct.unpack_from('<I', pk, 2)[0] in (90425006, 90425007, 90425008, 90425009)]
    assert len(totems) == 4
    for pk in totems:
        name = pk[18:34].split(b'\0')[0].decode('ascii')
        assert struct.unpack_from('<I', pk, 6)[0] == expected[name] == 0


def test_cast_effect_timers_flush_a_real_session_without_waiting_for_player_input(combat):
    c = combat
    sent = []
    session = Session(('test', 0))
    session.personaje = c.p
    session.entity_id = c.p.entity_id
    session.monstruos = c.s.monstruos
    session.inventario = c.s.inventario
    session.writer = SimpleNamespace(write=sent.append)
    cast = tw.Lanzamiento(session, 16896, 'test')
    cast.visual(16896, session, cast=2000)
    assert sent and not session.salida
    cast.visual(16896, session, close=True)
    assert len(sent) == 2 and not session.salida
