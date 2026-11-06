"""Healing Cross: seleccion real, potencia, limite y efecto nativo 499."""
import struct

import pytest
from test_competiciones import world
from test_taiwan_skills import combat
import app
import combate as cb
import presencia


def dispatch(c, mid, target):
    app.Servidor('127.0.0.1', 0).manejar(
        c.s, 6, None, {}, 'test', struct.pack('<HIIIH', mid, target, 0, 0, 0))


def recovery(packets):
    return [struct.unpack_from('<I', pk, 7)[0] for pk in packets
            if pk[:2] == b'\x0b\0' and pk[6] == cb.TIPO_CURA_HP]


@pytest.mark.parametrize('mid,amount', [(13310, 5500), (13311, 7000), (13312, 9000),
                                       (13313, 12000), (13314, 17000)])
@pytest.mark.parametrize('select_self', [True, False])
def test_all_ranks_heal_low_hp_with_matk_and_native_animation(combat, mid, amount, select_self):
    c = combat
    c.p.hp = 1000
    monster = c.monster(tile=(51, 50))
    mag = cb.datos_magia(mid)
    assert mag['es_cura'] and mag['es_auto'] and not mag['es_ataque']
    before_mp = c.p.mp
    dispatch(c, mid, c.p.entity_id if select_self else 0)
    c.advance(1.1)
    assert c.p.hp == 1000 + amount
    assert c.p.mp == before_mp - mag['mp']
    assert monster.hp == monster.hp_max
    assert recovery(c.s.packets) == [amount]
    visuals = [pk for pk in c.s.packets if pk[:2] == b'\x11\0']
    assert len(visuals) == 2
    assert all((pk[2] | ((pk[3] & 15) << 8)) == 499 for pk in visuals)
    assert [pk[3] & 128 for pk in visuals] == [0, 128]
    assert struct.unpack_from('<H', visuals[0], 20)[0] == 1000
    assert all(struct.unpack_from('<H', pk, 23)[0] == mid for pk in visuals)


def test_healing_cross_uses_target_hp_cap_without_healing_caster(combat):
    c = combat
    c.p.hp = 1000
    ally = c.world.player()
    ally.usuario = None
    ally.personaje.stage = c.p.stage
    ally.personaje.tile_x, ally.personaje.tile_y = 51, 50
    ally.personaje.hp, ally.personaje.hp_max = 1000, 10000
    c.s._mapa_presencia = 'test'
    c.monkeypatch.setattr(presencia, '_vivas', lambda _: [c.s, ally])
    dispatch(c, 13314, presencia.entidad_de(ally))
    c.advance(1.1)
    assert ally.personaje.hp == 9000  # Potencia limitada a 80% de SU maximo.
    assert c.p.hp == 1000
    assert recovery(ally.packets) == [8000]
    assert recovery(c.s.packets) == []


def test_healing_cross_never_exceeds_full_hp_and_still_shows_recovery(combat):
    c = combat
    dispatch(c, 13314, c.p.entity_id)
    c.advance(1.1)
    assert c.p.hp == c.p.hp_max
    assert recovery(c.s.packets) == [17000]


def test_healing_cross_rejects_monster_target_before_costs_or_damage(combat):
    c = combat
    monster = c.monster()
    before_mp = c.p.mp
    dispatch(c, 13314, monster.entity_id)
    c.advance(1.1)
    assert c.p.mp == before_mp and monster.hp == monster.hp_max
    assert not c.s.packets


def test_healing_cross_respects_cooldown_and_insufficient_mp(combat):
    c = combat
    c.p.hp = 1000
    dispatch(c, 13314, c.p.entity_id)
    c.advance(1.1)
    before_hp, before_mp = c.p.hp, c.p.mp
    dispatch(c, 13314, c.p.entity_id)
    c.advance(.5)
    assert (c.p.hp, c.p.mp) == (before_hp, before_mp)
    c.advance(1)
    c.p.mp = 100
    dispatch(c, 13314, c.p.entity_id)
    c.advance(1.1)
    assert c.p.hp == before_hp and c.p.mp == 100
