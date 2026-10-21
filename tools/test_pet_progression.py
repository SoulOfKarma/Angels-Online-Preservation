"""Regression tests: pet progression must change bonuses, not just labels.

Run: python -m pytest tools/test_pet_progression.py -q
No saved characters or databases are modified.
"""
import copy
import pathlib
import random
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import fusion
import mascotas


BATTLEMAID = {
    'sprite': 3200, 'nombre': 'Battlemaid', 'nivel': 86, 'rango': 4,
    'hp': 5443, 'mejoras': 15, 'estrellas': 16,
    'bonos': {'hp': 764, 'mp': 449, 'atk': 328, 'dfs': 365,
              'rigor': 397, 'agilidad': 360},
}


@pytest.fixture(autouse=True)
def preserve_random_state():
    state = random.getstate()
    yield
    random.setstate(state)


def test_capture_star_examples_match_xml_thresholds():
    assert mascotas.calcular_estrellas_total(BATTLEMAID['bonos']) == 16
    devil = dict(zip(mascotas.STATS_BONO,
                     (1230, 533, 558, 723, 310, 321, 250, 276)))
    assert mascotas.calcular_estrellas_total(devil) == 16


def test_star_up_uses_inherited_attributes_not_another_species(monkeypatch):
    pet = copy.deepcopy(BATTLEMAID)
    pet['bonos'].update(matk=310, mdef=321)
    before = pet['bonos'].copy()

    def forbidden(*args):
        raise AssertionError('Inherited bonuses must not use Hydra ranges')

    monkeypatch.setattr(mascotas, 'rangos_bonos_de', forbidden)
    random.seed(5)
    mascotas.subir_estrella(pet, 10)
    assert all(pet['bonos'][k] > before[k] for k in mascotas.STATS_BONO)
    assert pet['estrellas'] == mascotas.calcular_estrellas_total(pet['bonos'])


def test_star_up_does_not_manufacture_absent_bonuses():
    pet = copy.deepcopy(BATTLEMAID)
    mascotas.subir_estrella(pet, 10)
    assert pet['bonos'].get('matk', 0) == 0
    assert pet['bonos'].get('mdef', 0) == 0
    assert pet['estrellas'] == mascotas.calcular_estrellas_total(pet['bonos'])


def test_star_up_repeatedly_keeps_general_star_consistent():
    pet = {'sprite': 3200, 'estrellas': 2,
           'bonos': {'hp': 92, 'mp': 55, 'atk': 41, 'dfs': 51,
                     'rigor': 42, 'agilidad': 46}}
    random.seed(5)
    for _ in range(12):
        before = pet['bonos'].copy()
        result = mascotas.subir_estrella(pet, 10)
        assert result == mascotas.calcular_estrellas_total(pet['bonos'])
        assert all(pet['bonos'][k] >= v for k, v in before.items())


def test_star_up_at_eight_stars_does_not_reduce_or_inflate_stats():
    bonuses = {k: v + 123 for k, v in mascotas.cargar_pet_star()[80].items()}
    pet = {'sprite': 3200, 'estrellas': 80, 'bonos': bonuses.copy()}
    assert mascotas.subir_estrella(pet, 10) == 80
    assert pet['bonos'] == bonuses


@pytest.mark.parametrize('amount', [0, -1])
def test_nonpositive_star_up_is_noop(amount):
    pet = copy.deepcopy(BATTLEMAID)
    before = copy.deepcopy(pet)
    mascotas.subir_estrella(pet, amount)
    assert pet == before


def test_first_feed_generates_bonuses_and_applies_its_increment(monkeypatch):
    pet = {'sprite': 3200, 'mejoras': 0, 'bonos': {}, 'estrellas': 1}
    monkeypatch.setattr(mascotas, 'sortear_bonos', lambda sprite: {'atk': 40})
    monkeypatch.setattr(mascotas, 'rangos_bonos_de', lambda sprite: {'atk': (40, 40)})
    assert mascotas.mejorar_mascota(pet) == (True, 1)
    assert pet['bonos']['atk'] == 60
    assert pet['estrellas'] == mascotas.calcular_estrellas_total(pet['bonos'])


def test_feed_recalculates_label_and_keeps_existing_bonuses():
    pet = copy.deepcopy(BATTLEMAID)
    pet['mejoras'] = 14
    pet['estrellas'] = 79  # stale label from old code
    before = pet['bonos'].copy()
    assert mascotas.mejorar_mascota(pet) == (True, 15)
    assert all(pet['bonos'][k] > v for k, v in before.items())
    assert pet['estrellas'] == mascotas.calcular_estrellas_total(pet['bonos'])


def test_feed_at_plus_fifteen_is_noop():
    pet = copy.deepcopy(BATTLEMAID)
    before = copy.deepcopy(pet)
    assert mascotas.mejorar_mascota(pet) == (False, 15)
    assert pet == before


def run_fusion(monkeypatch, main, *, roll=1, potion=0, assistant_bonuses=None):
    assistant = {'sprite': 15561, 'nombre': 'Assistant', 'nivel': 72,
                 'hp': 100, 'bonos': {'hp': 1230, 'mp': 533, 'atk': 558,
                                      'dfs': 723, 'matk': 310, 'mdef': 321}}
    if assistant_bonuses is not None:
        assistant['bonos'] = assistant_bonuses
    p = SimpleNamespace(nombre='Test', mascotas={1: main, 2: assistant})
    ses = SimpleNamespace(personaje=p, inventario={1: 20012, 2: 999, 3: 123})
    messages, spent, closed = [], [], []

    def consume(session, slots):
        spent.extend(slots)
        for slot in slots:
            session.inventario.pop(slot, None)
        return set(slots)

    monkeypatch.setattr(fusion, '_gastar', consume)
    monkeypatch.setattr(fusion, '_cerrar', lambda *args: closed.append(args))
    monkeypatch.setattr(fusion, '_logro', lambda *args, **kwargs: None)
    monkeypatch.setattr(fusion, 'dato1_pocion', lambda item: potion)
    monkeypatch.setattr(fusion, 'bono_pocion', lambda item: 0)
    monkeypatch.setattr(random, 'randint', lambda low, high: roll)
    fusion._fusion_mascota(ses, None, messages.append, 1, 2, 3, 0)
    return p, messages, spent, closed


def test_successful_fusion_grows_battlemaid_above_initial_ranges(monkeypatch):
    main = copy.deepcopy(BATTLEMAID)
    before = main['bonos'].copy()
    p, messages, spent, closed = run_fusion(monkeypatch, main)
    # Highest eligible assistant attributes: defense, attack, magic defense.
    assert main['bonos']['dfs'] == before['dfs'] + 723 * 30 // 100
    assert main['bonos']['atk'] == before['atk'] + 558 * 30 // 100
    assert main['bonos']['mdef'] == 321 * 30 // 100
    assert main['bonos']['hp'] == before['hp']
    assert main['bonos']['mp'] == before['mp']
    assert main['estrellas'] == mascotas.calcular_estrellas_total(main['bonos'])
    assert main['mejoras'] == 15
    assert 1 in p.mascotas and 2 not in p.mascotas
    assert set(spent) == {0, 2, 3}
    assert messages[-1] == 'Pet fusion successful.'
    assert not any('upper limit' in m for m in messages)
    assert closed


def test_fusion_hp_growth_is_not_capped_by_hydra_initial_range(monkeypatch):
    main = copy.deepcopy(BATTLEMAID)
    run_fusion(monkeypatch, main, assistant_bonuses={'hp': 1230})
    assert main['bonos']['hp'] == 764 + 369


def test_failed_blessed_fusion_does_not_grant_bonuses(monkeypatch):
    main = copy.deepcopy(BATTLEMAID)
    before = copy.deepcopy(main)
    p, messages, spent, closed = run_fusion(monkeypatch, main, roll=100, potion=10020)
    assert main == before
    assert 1 in p.mascotas and 2 not in p.mascotas
    assert 1 not in spent
    assert messages[-1] == 'Pet Fusion failed.'
    assert closed


def test_failed_unprotected_fusion_keeps_existing_destruction_rule(monkeypatch):
    main = copy.deepcopy(BATTLEMAID)
    p, messages, spent, closed = run_fusion(monkeypatch, main, roll=100)
    assert not p.mascotas
    assert 1 in spent and 2 in spent
    assert messages[-1] == 'Pet fusion failed. The Main pet died.'
    assert closed


def test_ineligible_fusion_spends_nothing(monkeypatch):
    main = copy.deepcopy(BATTLEMAID)
    main['estrellas'] = 1
    main['bonos'] = mascotas.cargar_pet_star()[80].copy()
    before = copy.deepcopy(main)
    p, messages, spent, closed = run_fusion(monkeypatch, main)
    assert main == before
    assert set(p.mascotas) == {1, 2}
    assert not spent and not closed
    assert 'upper limits' in messages[-1]
