"""Equip Pet 558: admission, real stats, movement and XML level growth."""
import copy
import json
import pathlib
import struct
import sys
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ITEM_PET = 20012  # Battlemaid item; 44181 is its graphics type, NOT its item ID.
sys.path.insert(0, str(ROOT / 'server'))
import inventario as inv
import mascotas
import pet_equipment as pe


def pet(slot=20):
    return {'item': ITEM_PET, 'sprite': 3200, 'tipo': 44181, 'ranura': slot,
            'nombre': 'Battlemaid', 'nivel': 120, 'hp': 1000, 'hp_max': 1000,
            'mp': 500, 'mp_max': 500, 'estrellas': 50, 'mejoras': 15,
            'fuera': False, 'saciedad': 100, 'intimidad': 80,
            'bonos': mascotas.cargar_pet_star()[50].copy()}


def test_real_slot_is_not_accessory_or_amplify():
    assert pe.RANURA == 558
    assert inv.es_equipo(558)
    assert inv.es_ranura_valida(ITEM_PET, 558)
    assert not inv.es_ranura_valida(1201, 558)
    assert not inv.es_ranura_valida(ITEM_PET, 9)
    assert not inv.es_equipo(559)
    assert inv.vaciar_ranura(100, 558) == struct.pack('<HIBBIH', 0x001B, 1, 2, 1, 100, 558)


@pytest.mark.parametrize('stars, accepted', [(49, False), (50, True), (51, True), (80, True)])
def test_star_requirement_uses_tenths(stars, accepted):
    ficha = pet()
    ficha['estrellas'] = stars
    assert (pe.error_equipar(ficha) is None) is accepted


@pytest.mark.parametrize('field,value', [('fuera', True), ('hp', 0), ('estrellas', 49)])
def test_unavailable_pets_neither_equip_nor_grant_bonuses(field, value):
    ficha = pet(558)
    ficha[field] = value
    assert pe.error_equipar(ficha)
    assert pe.bonos({558: ITEM_PET}, {'558': ficha}) == {}


def test_only_green_bonuses_are_transferred():
    ficha = pet(558)
    ficha['hp_max'] = 999999
    ficha['atk'] = 999999
    ficha['saciedad'] = 600
    expected = {'hp': 1812, 'mp': 1297, 'atk': 507, 'def': 666,
                'matk': 225, 'mdef': 219, 'accuracy': 98, 'agility': 60}
    assert pe.bonos({558: ITEM_PET}, {'558': ficha}) == expected
    result = inv.bonos_de_equipo({558: ITEM_PET}, mascotas={'558': ficha})
    for key, value in expected.items():
        if key == 'atk':
            assert result['atk_r'] == result['atk_l'] == value
        else:
            assert result[key] == value


def test_bag_and_amplify_do_not_grant_equip_pet_bonuses():
    for slot in (20, 9, 559):
        assert pe.bonos({slot: ITEM_PET}, {str(slot): pet(slot)}) == {}


def test_real_stats_packet_and_hp_mp_limits_include_equipped_pet():
    bolsa = {558: ITEM_PET}
    fichas = {'558': pet(558)}
    before = inv.stats({}, [], hp=1000, hp_max=1000, mp=500, mp_max=500)[2:]
    after = inv.stats(bolsa, [], hp=1000, hp_max=1000, mp=500, mp_max=500,
                      mascotas=fichas)[2:]
    # Effective R/L attack, defense, magic attack/defense; bases unchanged.
    for offset, gain in ((24, 507), (28, 507), (36, 666), (44, 225), (52, 219),
                         (4, 1812), (12, 1297)):
        assert struct.unpack_from('<I', after, offset)[0] - struct.unpack_from('<I', before, offset)[0] == gain
    for offset in (20, 32, 40, 48):
        assert after[offset:offset+4] == before[offset:offset+4]
    for offset, gain in ((58, 98), (62, 60)):
        assert struct.unpack_from('<H', after, offset)[0] - struct.unpack_from('<H', before, offset)[0] == gain
    assert inv.vida_maxima(1000, [], bolsa, mascotas=fichas) == 2812
    assert inv.mana_maximo(500, [], bolsa, mascotas=fichas) == 1797


@pytest.fixture
def session(monkeypatch):
    import app
    import login
    import presencia
    p = login.Personaje(nombre='Test', char_id=123, nivel=120,
                        hp=1000, hp_max=1000, mp=500, mp_max=500)
    p.mascotas, p.mascota = {'20': pet()}, None
    packets = []
    ses = SimpleNamespace(rol='mundo', usuario=None, personaje=p,
                          inventario={20: ITEM_PET}, cantidades={20: 1},
                          instancias={20: b'12345678'}, oro=0,
                          enviar=lambda *pk: packets.extend(pk))
    p.inventario = ses.inventario
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *args: None)
    monkeypatch.setattr(app, '_apariencia', lambda *args: [])
    monkeypatch.setattr(presencia, 'notificar_equipo', lambda *args: None)
    srv = app.Servidor.__new__(app.Servidor)
    monkeypatch.setattr(srv, '_sincronizar_ranura_pet_room', lambda *args: None)
    return ses, srv, packets


def move(session, origin, destination):
    ses, srv, _ = session
    srv.manejar(ses, 0x0012, None, None, 'test', struct.pack('<HH', origin, destination))


def test_equip_unequip_keeps_state_and_removes_real_bonus(session):
    import app
    ses, _, packets = session
    original = ses.personaje.mascotas['20']
    before = app._stats_ses(ses)
    move(session, 20, 558)
    assert ses.inventario == {558: ITEM_PET}
    assert ses.personaje.mascotas['558'] is original
    assert original['ranura'] == 558
    assert ses.instancias[558] == b'12345678'
    assert original['mejoras'] == 15
    assert app._vida_max(ses.personaje) == 2812
    assert app._stats_ses(ses) != before
    move(session, 558, 21)
    assert ses.inventario == {21: ITEM_PET}
    assert ses.personaje.mascotas['21'] is original
    assert ses.instancias[21] == b'12345678'
    assert app._stats_ses(ses) == before
    assert any(p == inv.vaciar_ranura(ses.personaje.entity_id, 558) for p in packets)


def test_equip_swap_and_reverse_validation(session):
    ses, _, _ = session
    old = pet(558)
    old['mejoras'] = 7
    ses.personaje.mascotas['558'] = old
    ses.inventario[558] = ITEM_PET
    ses.instancias[558] = b'87654321'
    move(session, 20, 558)
    assert ses.personaje.mascotas['20'] is old
    assert ses.personaje.mascotas['558']['mejoras'] == 15
    assert ses.instancias[558] == b'12345678'
    # Reverse drag must not sneak a lower-star pet into 558 via a swap.
    old['estrellas'] = 49
    before = copy.deepcopy(ses.inventario)
    move(session, 558, 20)
    assert ses.inventario == before
    assert ses.personaje.mascotas['20'] is old


@pytest.mark.parametrize('field,value', [('estrellas', 49), ('hp', 0), ('fuera', True)])
def test_rejected_drag_keeps_bag_and_metadata(session, field, value):
    ses, _, _ = session
    ses.personaje.mascotas['20'][field] = value
    move(session, 20, 558)
    assert ses.inventario == {20: ITEM_PET}
    assert '558' not in ses.personaje.mascotas
    assert ses.instancias[20] == b'12345678'


def test_equipped_pet_cannot_be_summoned(session):
    import app
    ses, _, _ = session
    move(session, 20, 558)
    app._pet_alternar(ses, 'test', 558)
    assert not ses.personaje.mascotas['558']['fuera']


def test_rejected_active_pet_keeps_its_window_identity(session):
    ses, _, _ = session
    ficha = ses.personaje.mascotas['20']
    ficha.update(fuera=True, instancia=7777, entidad=6001)
    ses.personaje.mascota = ficha
    before = copy.deepcopy(ficha)
    move(session, 20, 558)
    assert ficha == before
    assert ses.inventario == {20: ITEM_PET}


def test_equipping_does_not_replace_another_active_pet(session):
    ses, _, _ = session
    active = pet(22)
    active.update(fuera=True, instancia=8888, entidad=6001)
    ses.personaje.mascota = active
    ses.personaje.mascotas['22'] = active
    ses.inventario[22] = ITEM_PET
    move(session, 20, 558)
    assert ses.personaje.mascota is active
    assert active['fuera'] is True


def test_json_roundtrip_preserves_equipment_bonuses(session):
    ses, _, _ = session
    move(session, 20, 558)
    restored = json.loads(json.dumps(ses.personaje.mascotas))
    assert pe.bonos(ses.inventario, restored) == pe.bonos(
        ses.inventario, ses.personaje.mascotas)
    assert restored['558']['mejoras'] == 15


def test_pet_binding_is_applied_once_and_travels_with_the_pet(session):
    ses, _, _ = session
    move(session, 20, 558)
    binding = copy.deepcopy(ses.personaje.mejoras[558]['vinculacion'])
    assert binding == {'item_id': ITEM_PET, 'dueno': 123, 'restantes': 2}
    move(session, 558, 21)
    assert ses.personaje.mejoras[21]['vinculacion'] == binding
    move(session, 21, 558)
    assert ses.personaje.mejoras[558]['vinculacion'] == binding


def test_battlemaid_level_121_jump_is_in_original_xml_and_applied():
    rows = ET.parse(ROOT / 'extracted_paks/update26/setting/eng/petattrib.xml').getroot()
    cls = mascotas.tipo_de(3200)
    source = {int(row.get('\u7b49\u7d1a')): row.attrib for row in rows
              if row.get('\u5bf5\u7269\u985e\u578b') == cls}
    assert int(source[120]['\u5e73\u5747\u653b\u64ca']) == 2234
    assert int(source[121]['\u5e73\u5747\u653b\u64ca']) == 2386
    ficha = pet()
    ficha.update(mascotas.stats_de(3200, 120))
    ficha['exp'] = 0
    bonuses = ficha['bonos'].copy()
    assert mascotas.dar_exp(ficha, mascotas.exp_para_subir(120, 3200)) == 1
    assert ficha['nivel'] == 121
    assert ficha['atk'] == 2386
    assert ficha['hp_max'] == int(source[121]['HP']) == 7744
    assert ficha['bonos'] == bonuses
    assert ficha['mejoras'] == 15 and ficha['estrellas'] == 50
