"""Pet-only combo regression: one skill effect, N damage ticks."""
import ast
from functools import lru_cache
import pathlib
import struct
import sys
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
import combate
import pet_combos
import presencia


class FakeLoop:
    def __init__(self):
        self.pending = []

    def call_later(self, delay, callback):
        self.pending.append((delay, callback))

    def run(self):
        for _, callback in sorted(self.pending, key=lambda entry: entry[0]):
            callback()


@lru_cache(maxsize=1)
def app_tree():
    return ast.parse((ROOT / 'server' / 'app.py').read_text(encoding='utf-8'))


def original_first_hit_packets(pet, target, damage):
    # Exercise the actual tuple used by the IA, without starting a server.
    node = next(n for n in ast.walk(app_tree()) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == '_pkgs_pet_hit'
                        for t in n.targets))
    scope = {'_cb': combate, 'pet_eid': 777, 'pet_targ': target,
             'dano_pet': damage, 'f_pet': pet, 'sk_usada': 6588,
             'ef_pet': 288, '_pet_skill_magic': False}
    exec(compile(ast.Module(body=[node], type_ignores=[]), '<pet first hit>', 'exec'), scope)
    return scope['_pkgs_pet_hit']


@pytest.fixture
def battle(monkeypatch):
    target = object.__new__(combate.Monstruo)
    target.entity_id, target.hp, target.hp_max = 42, 5000, 5000
    target.encantado = False
    pet = {'nombre': 'Battlemaid', 'fuera': True, 'hp': 100}
    owner = SimpleNamespace(stage=1, char_id=123, mascota=pet, mascota_orden=1)
    packets, broadcasts, deaths = [], [], []
    ses = SimpleNamespace(personaje=owner, muerto=False, pet_entity_id=777,
                          monstruos={42: target}, zona=1,
                          enviar_inmediato=lambda *pk: packets.extend(pk))
    monkeypatch.setattr(presencia, 'clave_de_mapa', lambda s, stage: (stage, s.zona))
    monkeypatch.setattr(presencia, 'notificar_companero_accion',
                        lambda s, *pk: broadcasts.extend(pk))
    monkeypatch.setattr(combate, 'ATACANTE', [None])
    return SimpleNamespace(ses=ses, pet=pet, target=target, owner=owner,
                           packets=packets, broadcasts=broadcasts,
                           deaths=deaths, loop=FakeLoop())


def schedule(battle, *, damage=100, combo=None, area=True):
    if combo is None:
        combo = combate.combo_de(6588)  # Full Buster VIII, actual XML: 6 hits
    return pet_combos.programar_subgolpes(
        battle.ses, battle.pet, 777, battle.target, damage, combo,
        es_aoe=area, al_morir=battle.deaths.append, loop=battle.loop)


def test_full_buster_is_one_effect_and_six_hits(battle):
    assert combate.datos_magia(6588)['es_aoe'] is True
    assert combate.combo_de(6588)['golpes'] == 6
    # The IA has applied the first hit before scheduling the other five.
    combate.ATACANTE[0] = battle.ses
    battle.target.registrar_dano(100, es_pet=True)
    battle.target.hp -= 100
    first = original_first_hit_packets(battle.pet, battle.target, 100)
    battle.packets.extend(first)
    battle.broadcasts.extend(first)
    duration = schedule(battle)
    battle.loop.run()
    opcodes = [struct.unpack_from('<H', p)[0] for p in battle.packets]
    # One skill-start/skill-end pair only, never reissued per combo hit.
    assert opcodes.count(0x0011) == 2
    assert opcodes.count(0x000B) == 6
    assert battle.target.hp == 4400
    assert battle.target.dano_pet == 600
    assert battle.target.dano_por == {123: 600}
    assert battle.broadcasts == battle.packets
    assert len(battle.loop.pending) == 5
    assert duration == pytest.approx(1.2)
    assert not battle.deaths


def test_nonarea_combo_preserves_its_original_interval(battle):
    duration = schedule(battle, combo={'golpes': 4, 'intervalo_ms': 300}, area=False)
    assert [delay for delay, _ in battle.loop.pending] == pytest.approx([.3, .6, .9])
    assert duration == pytest.approx(.9)


def test_changing_selected_target_does_not_redirect_pending_hits(battle):
    other = SimpleNamespace(hp=9000)
    schedule(battle)
    battle.ses.pet_objetivo = other
    battle.loop.run()
    assert other.hp == 9000
    assert battle.target.hp == 4500


@pytest.mark.parametrize('change', [
    'dismiss', 'dead_pet', 'safe', 'new_pet', 'new_entity', 'dead_owner',
    'logout', 'new_owner', 'new_stage', 'new_instance', 'removed_target',
    'dead_target', 'charmed_target',
])
def test_pending_hits_cancel_when_context_is_invalid(battle, change):
    schedule(battle)
    if change == 'dismiss':
        battle.pet['fuera'] = False
    elif change == 'dead_pet':
        battle.pet['hp'] = 0
    elif change == 'safe':
        battle.owner.mascota_orden = 2
    elif change == 'new_pet':
        battle.owner.mascota = dict(battle.pet)
    elif change == 'new_entity':
        battle.ses.pet_entity_id = 888
    elif change == 'dead_owner':
        battle.ses.muerto = True
    elif change == 'logout':
        battle.ses.personaje = None
    elif change == 'new_owner':
        battle.ses.personaje = SimpleNamespace(stage=1)
    elif change == 'new_stage':
        battle.owner.stage = 2
    elif change == 'new_instance':
        battle.ses.zona = 2
    elif change == 'removed_target':
        battle.ses.monstruos = {}
    elif change == 'dead_target':
        battle.target.hp = 0
    elif change == 'charmed_target':
        battle.target.encantado = True
    before = battle.target.hp
    battle.loop.run()
    assert battle.target.hp == before
    assert not battle.packets and not battle.broadcasts and not battle.deaths


def test_combo_kills_once_and_counts_only_actual_damage(battle):
    battle.target.hp = 150
    schedule(battle)
    battle.loop.run()
    assert battle.target.hp == 0
    assert battle.deaths == [battle.target]
    assert battle.target.dano_pet == 150
    assert len(battle.packets) == 4  # two effective subhits, not five


def test_damage_credit_is_scoped_to_owner_and_restores_other_context(battle):
    other = SimpleNamespace(personaje=SimpleNamespace(char_id=999))
    schedule(battle)
    combate.ATACANTE[0] = other
    battle.loop.run()
    assert battle.target.dano_por == {123: 500}
    assert combate.ATACANTE[0] is other


@pytest.mark.parametrize('combo', [None, {'golpes': 1}])
def test_single_hits_do_not_schedule_extra_attacks(battle, combo):
    duration = pet_combos.programar_subgolpes(
        battle.ses, battle.pet, 777, battle.target, 100, combo,
        es_aoe=False, al_morir=battle.deaths.append, loop=battle.loop)
    assert duration == 0
    assert not battle.loop.pending


def test_ia_waits_for_combo_to_finish_before_another_attack():
    node = next(n for n in ast.walk(app_tree()) if isinstance(n, ast.If)
                and "f_pet.get('combo_hasta'" in ast.unparse(n.test))
    condition = compile(ast.Expression(body=node.test), '<pet attack gate>', 'eval')
    scope = {'ahora': 100, 'cadencia_pet': .95,
             'f_pet': {'ultimo_ataque': 98, 'combo_hasta': 100.2}}
    assert not eval(condition, scope)
    scope['ahora'] = 100.3
    assert eval(condition, scope)
