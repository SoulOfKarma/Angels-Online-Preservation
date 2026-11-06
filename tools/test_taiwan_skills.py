"""Ejecutar las skills TW con reloj virtual y cuentas temporales."""
import heapq
import struct
from types import SimpleNamespace

import pytest
from test_competiciones import world
import app
import combate as cb
import desplazamientos
import equipos
import presencia
import pvp_liga
import taiwan_skills as tw
import transitable


@pytest.fixture
def combat(world, monkeypatch):
    s = world.player()
    p = s.personaje
    p.stage = 41
    p.tile_x = p.tile_y = 50
    p.hp = p.hp_max = 200000
    p.mp = p.mp_max = 200000
    p.buffs = {}
    s.sp = p.sp = 10000
    s.usuario = None
    callbacks, moves, kills, public = [], [], [], []
    serial = [0]
    def schedule(delay, callback):
        serial[0] += 1
        heapq.heappush(callbacks, (world.now[0] + delay, serial[0], callback))
    def advance(seconds):
        until = world.now[0] + seconds
        while callbacks and callbacks[0][0] <= until:
            now, _, callback = heapq.heappop(callbacks)
            world.now[0] = now
            callback()
        world.now[0] = until
    def move(ses, tile, *a):
        moves.append((ses, tile))
        ses.personaje.tile_x, ses.personaje.tile_y = tile
    def monster(eid=900, tile=(53, 50)):
        m = cb.Monstruo(eid, 19, 'Target', tile, stage=41)
        m.hp = m.hp_max = 50_000_000
        m.res_body = m.res_mind = 0
        s.monstruos[eid] = m
        return m
    def stats(ses):
        packet = bytearray(100)
        for offset, value in ((26, 1000), (30, 400), (38, 100), (46, 1000), (54, 100)):
            struct.pack_into('<I', packet, offset, value)
        return bytes(packet)
    monkeypatch.setattr(cb, '_MAGIC_CACHE', {})
    monkeypatch.setattr(cb, '_MAGIC_XML', None)
    monkeypatch.setattr(cb, '_EFECTOS_DISPONIBLES', None)
    monkeypatch.setattr(tw.asyncio, 'get_event_loop', lambda: SimpleNamespace(call_later=schedule))
    monkeypatch.setattr(app, '_stats_ses', stats)
    monkeypatch.setattr(app, '_otorgar_skill_exp', lambda *a, **kw: [])
    monkeypatch.setattr(app, '_procesar_muerte_monstruo', lambda s, m, *a, **kw: kills.append(m))
    monkeypatch.setattr(cb, 'es_jefe', lambda _: False)
    monkeypatch.setattr(pvp_liga, '_prob_critico', lambda _: 0)
    monkeypatch.setattr(pvp_liga, 'rivales_en_area', lambda *a: [])
    monkeypatch.setattr(presencia, 'notificar_companero_accion', lambda s, *pk: public.extend(pk))
    monkeypatch.setattr(presencia, 'sesion_por_entidad', lambda s, eid: next(
        (other for other in world.players if presencia.entidad_de(other) == eid), None))
    monkeypatch.setattr(desplazamientos, 'reubicar', move)
    monkeypatch.setattr(transitable, 'se_pisa', lambda *a: True)
    monkeypatch.setattr(transitable, 'linea_libre', lambda *a: True)
    return SimpleNamespace(s=s, p=p, advance=advance, monster=monster, moves=moves,
                           kills=kills, public=public, world=world, monkeypatch=monkeypatch)


def cast(c, mid, target=None, tile=None):
    return tw.lanzar(c.s, mid, target.entity_id if target is not None else 0,
                     *(tile or (0, 0)))


def effect_ids(packets):
    return {p[2] | ((p[3] & 15) << 8) for p in packets if p[:2] == b'\x11\0'}


def test_all_90_scroll_skills_and_their_native_effects_are_in_server_table(combat):
    for start in tw.LINEAS:
        for mid in range(start, start + 5):
            c = tw.Lanzamiento(combat.s, mid, 'test')
            row = tw.raw(mid)
            assert row
            assert cb.datos_magia(mid)['nombre']
            effect = c.effect(mid)
            if effect:
                assert cb.efecto_existe(effect), (mid, effect)
            for key in ('轉嫁法術',):
                if row.get(key):
                    assert tw.raw(int(row[key])), (mid, key)


def test_time_rift_blinks_hits_roots_and_publishes_native_731(combat):
    c = combat
    m = c.monster(tile=(57, 50))
    outside = c.monster(901, (70, 50))
    hp, mp = m.hp, c.p.mp
    assert cast(c, 16911, tile=(56, 50))
    # magic.xml omits 前置時間: this is an instant teleport.
    assert c.moves and m.hp == hp
    c.advance(.51)
    assert (c.p.tile_x, c.p.tile_y) == (56, 50)
    assert m.hp < hp and outside.hp == outside.hp_max
    assert 17081 in m.debuffs and m.aturdido
    assert c.p.mp == mp - 9869
    assert 731 in effect_ids(c.s.packets) & effect_ids(c.public)
    phases = [pk[3] & 128 for pk in c.s.packets if pk[:2] == b'\x11\0']
    assert phases[:2] == [0, 128]


def test_ultimate_healing_is_heal_and_checks_hp_after_first_recovery(combat):
    c = combat
    assert cb.datos_magia(16896)['es_cura']
    c.p.hp = 1000
    assert cast(c, 16896)
    assert c.p.hp == 1000
    c.advance(2.01)
    assert c.p.hp == 63000
    c.advance(1)
    c.p.hp = 100000
    assert cast(c, 16896)
    c.advance(2.01)
    assert c.p.hp == 131000  # Above 60% after first heal: no second 31000.


def test_emergency_care_swaps_party_positions_heals_ally_and_buffs_caster(combat):
    c = combat
    ally = c.world.player()
    ally.usuario = None
    ally.personaje.stage = 41
    ally.personaje.tile_x, ally.personaje.tile_y = 55, 52
    ally.personaje.hp_max, ally.personaje.hp = 100000, 1000
    c.monkeypatch.setattr(equipos, 'grupo_de', lambda s: [c.s, ally])
    assert tw.lanzar(c.s, 16891, presencia.entidad_de(ally))
    c.advance(2.01)
    assert tw.pos(c.s) == (55, 52) and tw.pos(ally) == (50, 50)
    assert ally.personaje.hp == 24700
    assert c.p.buffs[17051]['def'] == 5250
    assert c.p.buffs[17051]['mdef'] == 5250
    assert 17051 not in ally.personaje.buffs


def test_rescue_rejects_unrelated_player_without_spending_mp(combat):
    c = combat
    c.monkeypatch.setattr(equipos, 'grupo_de', lambda _: [c.s])
    other = c.world.player()
    other.personaje.stage = 41
    other.personaje.tile_x, other.personaje.tile_y = 51, 50
    mp = c.p.mp
    assert not tw.lanzar(c.s, 16891, presencia.entidad_de(other))
    assert c.p.mp == mp and not getattr(c.s, 'ultimo_uso', {})


def test_rescue_can_heal_self_without_custom_chat_prompts(combat):
    c = combat
    c.p.hp = 1000
    assert cast(c, 16891)
    c.advance(2.01)
    assert c.p.hp == 24700 and c.p.buffs[17051]['def'] == 5250
    assert not c.moves
    assert not any(pk[:2] == b'\x0d\0' for pk in c.s.packets)


def test_heal_at_full_hp_still_shows_native_green_recovery_number(combat):
    c = combat
    assert cast(c, 16896)
    c.advance(2.01)
    heals = [pk for pk in c.s.packets if pk[:2] == b'\x0b\0' and pk[6] == cb.TIPO_CURA_HP]
    assert c.p.hp == c.p.hp_max and len(heals) == 1
    assert struct.unpack_from('<I', heals[0], 7)[0] == 31000


def test_whirlwind_sword_dance_damages_area_and_wind_armor_expires(combat):
    c = combat
    m = c.monster()
    hp = m.hp
    assert cast(c, 16836)
    c.advance(.51)
    assert c.p.buffs[16941]['def'] == 5250
    assert c.p.buffs[16941]['move_speed_bonus'] == 50
    assert m.hp == hp
    c.advance(1.31)
    assert m.hp < hp and c.s.sp == 8000
    c.advance(5)
    assert 16941 not in c.p.buffs


@pytest.mark.parametrize('mid,count', [(16841, 8), (16871, 8), (16876, 10)])
def test_melee_combos_execute_every_native_hit(combat, mid, count):
    c = combat
    m = c.monster(tile=(51, 50))
    assert cast(c, mid, None if mid == 16841 else m)
    c.advance(2)
    hits = [pk for pk in c.s.packets if pk[:2] == b'\x0b\0' and struct.unpack_from('<I', pk, 2)[0] == m.entity_id]
    assert len(hits) == count
    assert m.hp < m.hp_max


def test_barrage_has_small_area_around_target(combat):
    c = combat
    main = c.monster(tile=(53, 50))
    nearby = c.monster(901, (54, 50))
    far = c.monster(902, (56, 50))
    assert cast(c, 16871, main)
    c.advance(2)
    assert main.hp < main.hp_max and nearby.hp < nearby.hp_max
    assert far.hp == far.hp_max


def test_earthsplitter_hits_three_times_in_front_and_reduces_defense(combat):
    c = combat
    front = c.monster(tile=(55, 50))
    behind = c.monster(901, (48, 50))
    off_line = c.monster(902, (54, 54))
    c.monkeypatch.setattr(tw.random, 'randint', lambda *a: 1)
    assert cast(c, 16846, tile=(56, 50))
    c.advance(2)
    hits = [pk for pk in c.s.packets if pk[:2] == b'\x0b\0' and struct.unpack_from('<I', pk, 2)[0] == front.entity_id]
    assert len(hits) == 3
    assert front.debuffs[16956]['def_mod'] == -7870
    assert behind.hp == behind.hp_max and off_line.hp == off_line.hp_max


def test_skullcrusher_checks_remaining_hp_before_knockdown(combat):
    c = combat
    m = c.monster(tile=(51, 50))
    assert cast(c, 16851, m)
    c.advance(.51)
    assert m.aturdido and 16966 in m.debuffs
    c.advance(3)
    m.aturdido_hasta = 0
    m.debuffs.clear()
    m.hp = m.hp_max // 3
    assert cast(c, 16851, m)
    c.advance(.51)
    assert not m.aturdido and 16966 not in m.debuffs


def test_spear_armor_break_spreads_to_nearby_enemies(combat):
    c = combat
    m = c.monster()
    nearby = c.monster(901, (54, 50))
    assert cast(c, 16856, m)
    c.advance(.11)
    assert m.debuffs[16971]['def_mod'] == -23610
    c.advance(1.01)
    assert m.debuffs[16976]['def_mod'] == -15740
    assert nearby.debuffs[16976]['def_mod'] == -15740


def test_spiral_thrust_charges_and_hits_eight_times(combat):
    c = combat
    m = c.monster(tile=(58, 50))
    assert cast(c, 16861, m)
    c.advance(2)
    assert tw.distance(tw.pos(c.s), tw.pos(m)) == 1
    hits = [pk for pk in c.s.packets if pk[:2] == b'\x0b\0' and struct.unpack_from('<I', pk, 2)[0] == m.entity_id]
    assert len(hits) == 8


def test_retreat_shot_damages_target_and_moves_caster(combat):
    c = combat
    m = c.monster()
    assert cast(c, 16866, m)
    c.advance(.41)
    assert m.hp < m.hp_max and tw.pos(c.s) == (55, 50)


def test_knife_auto_detonates_and_recast_consumes_mark_without_double_explosion(combat):
    c = combat
    m = c.monster()
    assert cast(c, 16881, m)
    c.advance(.41)
    assert 17026 in m.debuffs
    hp = m.hp
    c.advance(10)
    assert m.hp < hp and 17026 not in m.debuffs
    assert cast(c, 16881, m)
    c.advance(1.1)
    assert cast(c, 16881, m)
    c.advance(.41)
    # The second-stage explosion has its own 300 ms impact time.
    assert 17026 not in m.debuffs
    hp = m.hp
    c.advance(10)
    assert m.hp == hp


def test_flame_brand_spreads_ticks_and_detonates_on_second_cast(combat):
    c = combat
    m = c.monster()
    neighbor = c.monster(901, (54, 50))
    assert cast(c, 16916, m)
    c.advance(1.71)
    assert 17086 in m.debuffs and 17086 in neighbor.debuffs
    hp = m.hp
    c.advance(2)
    assert m.hp == hp - 7320
    assert cast(c, 16916, m)
    c.advance(2.51)
    assert 17086 not in m.debuffs and m.hp < hp - 7320
    assert 546 in effect_ids(c.s.packets)


def test_rockskin_changes_defenses_and_physical_resistance(combat):
    c = combat
    assert cast(c, 16926)
    c.advance(.11)
    buff = c.p.buffs[16926]
    assert (buff['def'], buff['mdef'], buff['mit']) == (5250, 5250, 50)
    assert 732 in effect_ids(c.s.packets)
    c.advance(30)
    assert 16926 not in c.p.buffs


def test_steel_beak_roots_weakens_and_recovers_hp_mp_on_kill(combat):
    c = combat
    m = c.monster()
    c.monkeypatch.setattr(tw.random, 'randint', lambda *a: 1)
    assert cast(c, 16931, m)
    c.advance(2.31)
    assert 17102 in m.debuffs and m.aturdido
    c.advance(1.01)
    assert m.debuffs[17107]['mdef_mod'] == -5390
    c.p.hp, c.p.mp = 10000, 10000
    m.hp = 1
    assert cast(c, 16931, m)
    c.advance(2.31)
    assert not m.vivo and c.kills == [m]
    assert c.p.hp == 40000
    assert c.p.mp == 10000 - 8737 + 30000


def summon(eid, x=53, y=50):
    return dict(entity_id=eid, hp=10000, hp_max=10000, tile_x=x, tile_y=y)


def test_terrifying_command_pulses_from_summon_and_reduces_enemy_damage(combat):
    c = combat
    m = c.monster()
    c.s.invocacion = summon(3000)
    assert cast(c, 16901)
    c.advance(1.51)
    assert m.debuffs[17066]['phys_dmg_pct'] == -30
    assert m.debuffs[17066]['mag_dmg_pct'] == -30
    hp = m.hp
    c.advance(1)
    assert m.hp == hp - 10000
    assert 729 in effect_ids(c.s.packets)
    terror = next(pk for pk in c.s.packets if pk[:2] == b'\x11\0'
                  and (pk[2] | ((pk[3] & 15) << 8)) == 729)
    assert struct.unpack_from('<I', terror, 4)[0] == 3000
    c.advance(20)
    assert 16901 not in c.p.buffs


def test_soul_burst_consumes_both_summons_and_hits_both_areas(combat):
    c = combat
    c.s.invocacion = summon(3000)
    c.s.invocacion2 = summon(3001, 65, 50)
    a, b = c.monster(), c.monster(901, (65, 50))
    assert cast(c, 16906)
    c.advance(2.11)
    assert c.s.invocacion is None and c.s.invocacion2 is None
    assert a.hp < a.hp_max and b.hp < b.hp_max
    assert 730 in effect_ids(c.s.packets)


@pytest.mark.parametrize('reason', ['mp', 'sp', 'range', 'wall', 'cooldown'])
def test_invalid_casts_never_spend_resources_or_damage(combat, reason):
    c = combat
    m = c.monster(tile=(51, 50))
    if reason == 'mp':
        c.p.mp = 1
        mid = 16931
    else:
        mid = 16851
    if reason == 'sp': c.s.sp = 1
    if reason == 'range': m.tile_x = 70
    if reason == 'wall': c.monkeypatch.setattr(transitable, 'linea_libre', lambda *a: False)
    if reason == 'cooldown': c.s.ultimo_uso = {mid: c.world.now[0]}
    before = c.p.mp, c.s.sp, m.hp
    assert not cast(c, mid, m)
    c.advance(10)
    assert (c.p.mp, c.s.sp, m.hp) == before


@pytest.mark.parametrize('cancel', ['death', 'map', 'disconnect', 'character', 'room', 'respawn'])
def test_callbacks_never_hit_after_context_changes(combat, cancel):
    c = combat
    m = c.monster(tile=(51, 50))
    assert cast(c, 16876, m)
    c.advance(.51)
    hp = m.hp
    if cancel == 'death': c.s.muerto = True
    elif cancel == 'map': c.p.stage = 42
    elif cancel == 'disconnect': c.s.desconectado = True
    elif cancel == 'character': c.s.personaje = None
    elif cancel == 'room': c.s._mapa_presencia = ('different',)
    else: m.vida_combate += 1
    c.advance(2)
    assert m.hp == hp


def test_dispatch_routes_real_cast_packet_to_new_implementation(combat):
    c = combat
    m = c.monster(tile=(56, 50))
    server = app.Servidor('127.0.0.1', 0)
    server.manejar(c.s, 6, None, {}, 'test', struct.pack('<HIIIH', 16911, 0, 56, 50, 0))
    c.advance(.51)
    assert c.moves and m.hp < m.hp_max


@pytest.mark.parametrize('start', list(tw.LINEAS))
@pytest.mark.parametrize('rank', range(5))
def test_every_rank_performs_its_combat_action(combat, start, rank):
    c = combat
    kind = tw.LINEAS[start]
    m = c.monster(tile=(51, 50))
    c.monkeypatch.setattr(tw.random, 'randint', lambda *a: 1)
    target = m
    tile = None
    if kind in ('command', 'burst'):
        c.s.invocacion = summon(3000)
        target = None
    elif kind in ('sword', 'slashes', 'rockskin', 'heal'):
        target = None
    elif kind in ('rift', 'earthsplit'):
        target, tile = None, (52, 50)
    elif kind == 'rescue':
        ally = c.world.player()
        ally.usuario = None
        ally.personaje.stage = 41
        ally.personaje.tile_x, ally.personaje.tile_y = 52, 50
        ally.personaje.hp_max, ally.personaje.hp = 100000, 1
        c.monkeypatch.setattr(equipos, 'grupo_de', lambda _: [c.s, ally])
        assert tw.lanzar(c.s, start + rank, presencia.entidad_de(ally))
        c.advance(5)
        assert ally.personaje.hp > 1 and tw.pos(c.s) == (52, 50)
        return
    c.p.hp = 1000
    assert cast(c, start + rank, target, tile)
    c.advance(5)
    if kind == 'heal':
        assert c.p.hp > 1000
    elif kind == 'rockskin':
        assert c.p.buffs[start + rank]['def'] > 0
    else:
        assert m.hp < m.hp_max, (kind, rank)


def enemy_player(c):
    other = c.world.player()
    other.usuario = None
    q = other.personaje
    q.stage, q.tile_x, q.tile_y = 41, 53, 50
    q.hp = q.hp_max = 50_000_000
    q.mp = q.mp_max = 200000
    other.sp = q.sp = 10000
    c.monkeypatch.setattr(pvp_liga, 'permitido', lambda *a: True)
    c.monkeypatch.setattr(presencia, '_vivas', lambda _: [c.s, other])
    c.monkeypatch.setattr(pvp_liga, 'rivales_en_area', lambda s, x, y, r:
                          [other] if tw.distance((x, y), tw.pos(other)) <= r else [])
    return other


def test_rift_root_really_blocks_player_movement_then_expires(combat):
    c = combat
    other = enemy_player(c)
    assert cast(c, 16911, tile=(53, 50))
    c.advance(.51)
    assert other.personaje.hp < other.personaje.hp_max
    assert tw.inmovilizado(other) and tw.bloquear_movimiento(other)
    before = tw.pos(other)
    assert not tw.lanzar(other, 16911, 0, 54, 50)
    assert tw.pos(other) == before
    c.advance(3)
    assert not tw.inmovilizado(other)


def test_mana_bomb_drains_mp_and_auto_explodes_on_players_after_buff_expiry(combat):
    c = combat
    other = enemy_player(c)
    assert tw.lanzar(c.s, 16881, presencia.entidad_de(other))
    c.advance(2.41)
    assert other.personaje.mp == 194000
    hp = other.personaje.hp
    c.advance(8.01)
    assert other.personaje.hp < hp
    assert 17026 not in other.personaje.buffs


def test_anti_chain_tactics_reduces_later_combo_hits(combat):
    c = combat
    other = enemy_player(c)
    other.personaje.tile_x = 51
    other.personaje.buffs[600] = {'fin': c.world.now[0] + 300}
    c.monkeypatch.setattr(tw.random, 'randint', lambda *a: 100)
    assert tw.lanzar(c.s, 16876, presencia.entidad_de(other))
    c.advance(.21)
    hp = other.personaje.hp
    c.advance(2)
    assert hp < other.personaje.hp_max and other.personaje.hp == hp


def test_summon_replaced_during_cast_is_not_detonated(combat):
    c = combat
    c.s.invocacion = summon(3000)
    assert cast(c, 16906)
    replacement = summon(3001)
    c.s.invocacion = replacement
    c.advance(3)
    assert c.s.invocacion is replacement


def test_physical_skill_sends_weapon_animation_and_native_effect(combat):
    c = combat
    m = c.monster(tile=(51, 50))
    assert cast(c, 16851, m)
    attacks = [pk for pk in c.s.packets if pk[:2] == b'\x0a\0']
    assert attacks and struct.unpack_from('<HH', attacks[0], 10) == cb.golpe_de_arma(0)
    assert 718 in effect_ids(c.s.packets) & effect_ids(c.public)


def test_ally_receives_cast_animation_with_own_local_target_entity(combat):
    c = combat
    ally = c.world.player()
    ally.usuario = None
    ally.personaje.stage = 41
    ally.personaje.tile_x, ally.personaje.tile_y = 51, 50
    ally.personaje.hp = 1
    assert tw.lanzar(c.s, 16896, presencia.entidad_de(ally))
    packet = next(pk for pk in ally.packets if pk[:2] == b'\x11\0')
    assert struct.unpack_from('<II', packet, 4) == (presencia.entidad_de(c.s), ally.personaje.entity_id)
    c.advance(2.01)
    assert ally.personaje.hp > 1 and c.p.hp == c.p.hp_max


def test_lower_rank_cannot_bypass_group_cooldown(combat):
    c = combat
    m = c.monster(tile=(51, 50))
    assert cast(c, 16851, m)
    c.advance(.51)
    before = c.s.sp
    assert not cast(c, 16847, m)
    assert c.s.sp == before
