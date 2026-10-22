"""Regression checks against real XML and the server's cast handler."""
import heapq
import itertools
import pathlib
import struct
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
import app
import combate as cb
import login
import transitable


class Clock:
    def __init__(self):
        self.now = 1000000.0
        self.pending = []
        self.ids = itertools.count()

    def call_later(self, delay, callback):
        heapq.heappush(self.pending, (self.now + delay, next(self.ids), callback))

    def advance(self, seconds):
        end = self.now + seconds
        while self.pending and self.pending[0][0] <= end:
            self.now, _, callback = heapq.heappop(self.pending)
            callback()
        self.now = end


@pytest.fixture
def battle(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(app.asyncio, 'get_event_loop', lambda: clock)
    monkeypatch.setattr(app.time, 'time', lambda: clock.now)
    monkeypatch.setattr(app, '_otorgar_skill_exp', lambda *a, **kw: [])
    monkeypatch.setattr(app, '_dar_sp', lambda *a, **kw: None)
    monkeypatch.setattr(app, '_stats_ses', lambda *a: b'')
    monkeypatch.setattr(app, '_receptores_de_buff', lambda *a: ([], True))
    p = login.Personaje(hp=20000, hp_max=100000, mp=50000, mp_max=150000)
    packets = []
    s = SimpleNamespace(personaje=p, rol='mundo', entity_id=p.entity_id,
                        inventario={}, monstruos={}, usuario=None, muerto=False,
                        enviar=lambda *pk: packets.extend(pk),
                        enviar_inmediato=lambda *pk: packets.extend(pk))
    server = app.Servidor.__new__(app.Servidor)

    def cast(skill):
        server.manejar(s, 0x0006, None, None, 'test',
                       struct.pack('<HI', skill, p.entity_id))
        clock.advance(1.1)

    return SimpleNamespace(p=p, s=s, packets=packets, clock=clock, cast=cast)


@pytest.mark.parametrize('skill,bonus', [(15105, 10000), (13369, 8000), (270, 326)])
def test_max_mana_buff_never_refills_current_resources(battle, skill, bonus):
    before_max = app._mana_max(battle.p, {})
    cost = cb.datos_magia(skill)['mp']
    battle.cast(skill)
    assert skill in battle.p.buffs
    assert battle.p.mp == 50000 - cost
    assert battle.p.hp == 20000
    assert app._mana_max(battle.p, {}) == before_max + bonus


def test_buff_on_other_player_does_not_refill_either(battle):
    mag = cb.datos_magia(15105)
    entry = dict(mag)
    entry.pop('mp', None)
    entry.pop('hp', None)
    app._buff_a_otro(battle.s, 15105, entry, mag['dur_ms'], mag)
    assert (battle.p.hp, battle.p.mp) == (20000, 50000)
    assert app._mana_max(battle.p, {}) == 160000


def test_explicit_instant_mana_recovery_is_preserved(battle):
    mag = cb.datos_magia(12960)  # Soul Discharge V
    battle.s.sp = 2000
    battle.cast(12960)
    assert mag['mp_cura'] == 12000
    assert battle.p.mp == 50000 - mag.get('mp', 0) + 12000


def test_max_buff_expiry_only_clamps_to_restored_limit(battle):
    battle.cast(13369)
    battle.p.mp = 155000
    battle.clock.advance(16)
    assert 13369 not in battle.p.buffs
    assert battle.p.mp == 150000


def test_mental_stimulation_first_use_and_reuse(battle):
    battle.cast(15602)
    assert 15657 in battle.p.buffs and 15662 not in battle.p.buffs
    assert battle.p.mp == 50000 - 8742
    assert app._mana_max(battle.p, {}) == 158590
    battle.clock.advance(30)
    before = battle.p.mp
    battle.cast(15602)
    assert {15657, 15662} <= battle.p.buffs.keys()
    assert battle.p.mp == before - 8742 + 859
    battle.clock.advance(2)
    assert battle.p.mp == before - 8742 + 2 * 859
    cooldown_ids = [struct.unpack_from('<I', packet, 8)[0]
                    for packet in battle.packets
                    if len(packet) == 16 and packet[:2] == b'\x1d\x00'
                    and packet[7] == 3]
    assert cooldown_ids and set(cooldown_ids) == {15602}


def test_thoughtless_recovers_hp_only_on_successful_reuse(battle, monkeypatch):
    monkeypatch.setattr(cb.random, 'randint', lambda a, b: 1)
    battle.cast(16376)
    assert 16538 in battle.p.buffs and 16543 not in battle.p.buffs
    assert (battle.p.hp, battle.p.mp) == (20000, 50000 - 9487)
    battle.clock.advance(30)
    battle.cast(16376)
    assert {16538, 16543} <= battle.p.buffs.keys()
    assert (battle.p.hp, battle.p.mp) == (21524, 50000 - 2 * 9487)


def test_reuse_failure_and_expired_base_do_not_trigger_regen():
    for buffs, roll in [({16538: {'fin': 200}}, 100),
                        ({16538: {'fin': 99}}, 1), ({}, 1)]:
        resolved = cb.buff_al_reutilizar(16376, buffs, ahora=100,
                                        azar=lambda a, b: roll)
        assert resolved['id'] == 16538
        assert resolved['mp'] == 9487


def test_refresh_replaces_regen_callbacks(battle):
    battle.cast(15602)
    battle.clock.advance(30)
    battle.cast(15602)
    battle.clock.advance(30)
    before = battle.p.mp
    battle.cast(15602)
    # New immediate tick, then exactly one active timer at the next interval.
    assert battle.p.mp == before - 8742 + 859
    before = battle.p.mp
    battle.clock.advance(2)
    assert battle.p.mp == before + 859


def test_pending_regen_does_not_follow_a_replaced_character(battle):
    battle.cast(15602)
    battle.clock.advance(30)
    battle.cast(15602)
    replacement = login.Personaje(mp=100, mp_max=150000)
    battle.s.personaje = replacement
    battle.clock.advance(3)
    assert replacement.mp == 100


@pytest.mark.parametrize('skill', [13841, 15241])
def test_offensive_brands_are_not_conditional_self_buffs(skill):
    mag = cb.datos_magia(skill)
    assert mag['es_ataque'] and not mag.get('reuso_base_id')


def test_peril_chasm_blocked_spawn_cannot_disable_walls():
    mob = SimpleNamespace(tile_x=93, tile_y=22, _anda_por_tierra=False)
    assert not transitable.se_pisa(339, 93, 22)
    assert app._mapa_de_paso(mob, 339) == 339


def test_blocked_spawn_keeps_wall_checks_in_other_maps(monkeypatch):
    width = height = 7
    bits = bytearray((width * height + 7) // 8)
    for y in range(height):
        for x in range(width):
            if x == 3:
                continue
            index = y * width + x
            bits[index >> 3] |= 1 << (index & 7)
    monkeypatch.setattr(transitable, '_MAPAS', {999: (width, height, bytes(bits))})
    mob = SimpleNamespace(tile_x=3, tile_y=1, _anda_por_tierra=False)
    stage = app._mapa_de_paso(mob, 999)
    assert stage == 999
    assert not transitable.linea_libre(stage, (1, 1), (5, 1))
    assert not transitable.camino(stage, (1, 1), (5, 1))
