"""Aliua's reward must leave the existing level-based skill slots alone."""
import copy
import pathlib
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import skills
import supremo


def character(count):
    return SimpleNamespace(
        char_id=123, nombre='Test', nivel=410,
        habilidades=[(sid, 410 - sid, 10000 + sid) for sid in range(1, count + 1)],
        banco_habilidades={20: (300, 123456)}, logros_cont={'other': 7})


@pytest.mark.parametrize('count', [6, 7, 8, 9])
def test_reward_is_idempotent_and_never_changes_skills_or_bank(count):
    p = character(count)
    equipped, bank = p.habilidades, p.banco_habilidades
    before = copy.deepcopy((equipped, bank))
    for _ in range(3):
        supremo.conceder_poder(p)
        assert p.habilidades is equipped
        assert p.banco_habilidades is bank
        assert (equipped, bank) == before
        assert p.logros_cont == {'other': 7, 'supremo': 1}


@pytest.mark.parametrize('level,count', [(300, 6), (301, 7), (350, 7),
                                       (351, 8), (400, 8), (401, 9), (410, 9), (999, 9)])
def test_level_based_slot_limits_stay_unchanged(level, count):
    assert skills.ranuras_de_habilidad(level) == count


@pytest.mark.parametrize('already_completed', [False, True])
def test_real_dialogue_reward_preserves_nine_skills(monkeypatch, already_completed):
    import app
    import misiones
    p = character(9)
    before = copy.deepcopy((p.habilidades, p.banco_habilidades))
    packets, completed, achievements, consumption, saved = [], [], [], [], []
    state = {'completed': already_completed}
    ses = SimpleNamespace(personaje=p, enviar=lambda *pk: packets.extend(pk))
    monkeypatch.setattr(app, '_logros_datos', lambda *args: None)
    monkeypatch.setattr(app, '_logros_guardar', lambda *args: saved.append(True))
    monkeypatch.setattr(app, '_logros_dar', lambda s, a, lid: achievements.append(lid))
    monkeypatch.setattr(app, '_aliua_mostrar', lambda *args: None)
    monkeypatch.setattr(app, '_guardar_bolsa', lambda *args: None)
    monkeypatch.setattr(app, '_refrescar', lambda *args: [])
    monkeypatch.setattr(app, '_cant_total_item', lambda *args: 200)

    def consume(s, item, count):
        consumption.append((item, count))
        return []

    def finish(s, qid):
        completed.append(qid)
        state['completed'] = True

    monkeypatch.setattr(app, '_consumir_item_total', consume)
    monkeypatch.setattr(misiones, 'tiene_mision', lambda *args: True)
    monkeypatch.setattr(misiones, 'obtener_paso_actual',
                        lambda *args: 999 if state['completed'] else 3)
    monkeypatch.setattr(misiones, 'mision_completada', lambda *args: state['completed'])
    monkeypatch.setattr(misiones, 'completar_mision', finish)

    def forbidden(*args, **kwargs):
        raise AssertionError('Aliua must not request another skill slot')

    monkeypatch.setattr(skills, 'completar_ranuras_extra', forbidden)
    monkeypatch.setattr(skills, 'rama_de_relleno', forbidden)
    for _ in range(2):
        app._aliua_opcion(ses, 'test', 1234, supremo.OP_SI_PODER)
        assert (p.habilidades, p.banco_habilidades) == before
        assert len(p.habilidades) == 9
    assert p.logros_cont['supremo'] == 1
    assert achievements == [supremo.LOGRO, supremo.LOGRO]
    assert saved
    assert completed == ([] if already_completed else [supremo.MISION])
    assert len(consumption) == (0 if already_completed else 1)
    if consumption:
        assert consumption[0] == (supremo.MATERIALES[0], 200)
