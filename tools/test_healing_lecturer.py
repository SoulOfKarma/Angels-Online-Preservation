"""El retrato compartido no debe bloquear el arbol nativo de Healing Lecturer."""
import importlib
import os
import pathlib
import sys

import pytest


@pytest.fixture(scope='module')
def dm(tmp_path_factory):
    before = os.environ.get('AO_DATOS')
    os.environ['AO_DATOS'] = str(tmp_path_factory.mktemp('healing_datos'))
    root = pathlib.Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root / 'server'), str(root / 'proto')]
    module = importlib.import_module('dialogos_mapa')
    yield module
    if before is None:
        os.environ.pop('AO_DATOS', None)
    else:
        os.environ['AO_DATOS'] = before


class QuestContext:
    sabe = {2, 6, 7, 10, 11}

    def __init__(self, step=2):
        self.step = step

    def paso_de_mision(self, quest):
        return self.step - 1 if quest == 605 else -1

    def mision_terminada(self, quest):
        return quest in (601, 602, 603, 604)


def test_real_portrait_collision_and_explicit_root(dm):
    ctx = QuestContext()
    assert dm.raiz_de_mision(41, 48) is None  # 60401 y 80015 comparten cara.
    assert dm.arbol_de_mision_para(41, 48, ctx, raiz=60401) == 60401
    assert dm._elegir(dm._arbol(41), 60401, ctx) == '1000573'
    assert dm._arbol(41)['1000573']['m'] == 60509
    assert dm._arbol(41)['1000573']['o'][0] == [60510, 1000574]


def test_collection_step_keeps_its_reminder(dm):
    ctx = QuestContext(step=1)
    assert dm.arbol_de_mision_para(41, 48, ctx, raiz=60401) == 60401
    assert dm._elegir(dm._arbol(41), 60401, ctx) == '1000544'


def test_unknown_explicit_root_never_uses_a_different_npc(dm):
    assert dm.arbol_de_mision_para(41, 48, QuestContext(), raiz=999999999) is None


def test_tutorial_exclusion_is_preserved(dm):
    assert dm.arbol_de_mision_para(51, 48, QuestContext(), raiz=60401) is None


def test_native_rewards_match_the_quest(dm):
    actions = dm._arbol(28)['1000078']['a']
    assert actions == [[7, [32, 18000]], [7, [49, 225]], [19, [8000]], [4, [605, 3]]]


def test_lyceum_entity_uses_its_exact_npc_type(dm):
    app = importlib.import_module('app')
    assert app._npc_type_de(41, 52) == 1919
    assert app.DIALOGO_DE_NPC[(41, 1919)] == 60401
