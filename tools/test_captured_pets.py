"""Regression checks for the captured-monster pet bridge."""
import pathlib
import struct
import sys


ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / 'server'))

import combate
import cuentas
import house_services as hs
import mascotas


def test_only_official_catch_xml_decides_the_archetype():
    caught = hs.capturable_monsters()
    # These crabs intentionally belong to different official skill archetypes.
    assert caught[32] == 16970
    assert caught[36] == 16972
    assert caught[49] == 16969
    assert caught[52] == 16976
    # House-hatching eggs must not silently make unrelated monsters catchable.
    assert 1217 not in caught


def test_luxurious_poke_egg_is_not_guaranteed():
    # NPC 7001 has base probability 500/10000. Even the 300% egg can fail.
    luxury = hs.capture_chance(300, 1, 100, npc_type=7001)
    assert 1.0 < luxury < 100.0
    assert luxury > hs.capture_chance(60, 1, 100, npc_type=7001)
    assert hs.capture_chance(300, 1, 100, npc_type=7001) > hs.capture_chance(
        300, 99, 100, npc_type=7001)


def test_capture_animation_keeps_effect_and_subtype_separate():
    packets = combate.efecto_captura(11, 22, 33, 44, 16982)
    assert len(packets) == 2
    assert int.from_bytes(packets[0][:2], 'little') == 0x0011  # red crystal effect 0x0011
    assert int.from_bytes(packets[1][:2], 'little') == 0x0011
    assert packets[0][2] == 19  # red crystal (Fire Trap) effect id
    assert packets[1][2] == 19
    assert packets[0][3] & 0x80 == 0x00  # phase 0x00
    assert packets[1][3] & 0x80 == 0x80  # phase 0x80
    assert struct.unpack_from('<II', packets[0], 12) == (33, 44)
    assert struct.unpack_from('<II', packets[1], 12) == (33, 44)
    assert packets[0][22] == 2  # es_magia=False (no orange runic ring on caster)
    assert struct.unpack_from('<H', packets[0], 23)[0] == 0  # no attack skill id


def test_quality_names_match_the_client_strings():
    assert mascotas.RANGO_NOMBRES == {
        1: 'Common', 2: 'Good', 3: 'Rare', 4: 'Awesome', 5: 'Super'}


def test_quality_does_not_rewrite_stars_or_stats():
    pet = {'sprite': 3403, 'estrellas': 3, 'atk': 100,
           'bonos': {'atk': 8}}
    mascotas.aplicar_rango(pet, rango=5, st=20, mult=1.5)
    assert pet['rango_nombre'] == 'Super'
    assert pet['estrellas'] == 3
    assert pet['atk'] == 100
    assert pet['bonos'] == {'atk': 8}


def test_captured_species_appears_at_advanced_evolution():
    pet = mascotas.recien_nacida('Sky Bird', 3403, npc_type=7014)
    pet['captured_name'] = 'Sky Bird'
    pet['captured_tipo'] = 43210
    old_stars = mascotas.calcular_estrellas_total(pet['bonos'])
    mascotas.evolucionar(pet, 'nice')
    assert pet['sprite'] == 3404       # official skill/stat archetype advanced
    assert pet['nombre'] == 'Blue Crab'  # junior Monster Egg form
    assert pet['tipo'] != 43210
    assert pet['skills'] == list(mascotas.skills_de(3404, pet['nivel']))
    mascotas.evolucionar(pet, 'nice')
    mascotas.evolucionar(pet, 'nice')
    assert pet['sprite'] == 3406
    assert pet['nombre'] == 'Sky Bird'
    assert pet['tipo'] == 43210          # advanced form is captured species
    assert pet['estrellas'] >= old_stars


def test_capture_visual_is_targeted_and_has_no_fake_attack_packet():
    pkts = combate.efecto_captura(1, 2, 61, 72)
    assert len(pkts) == 2
    assert struct.unpack_from('<H', pkts[0])[0] == 0x0011
    assert struct.unpack_from('<H', pkts[1])[0] == 0x0011
    assert struct.unpack_from('<II', pkts[0], 4) == (1, 2)
    assert struct.unpack_from('<II', pkts[0], 12) == (61, 72)
    assert not any(p[:2] == b'\x0A\x00' for p in pkts)


def test_old_captured_pet_is_repaired_when_loaded():
    legacy = {
        'nombre': 'Blue Crab', 'sprite': 3406, 'tipo': 42816,
        'nivel': 55, 'npc_type': 7014, 'rango': 4,
        'rango_nombre': 'Top', 'estrellas': 18,
        'bonos': {'hp': 43, 'mp': 29, 'dfs': 40, 'mdef': 25,
                  'rigor': 18, 'agilidad': 12},
    }
    repaired = cuentas._cargar_mascota(legacy)
    identity = hs.captured_monster_identity(7014)
    assert repaired['rango_nombre'] == 'Awesome'
    assert repaired['estrellas'] == mascotas.calcular_estrellas_total(legacy['bonos'])
    assert repaired['nombre'] == mascotas.abreviar_nombre_pet(identity['nombre'])
    assert repaired['tipo'] == identity['sprite']
