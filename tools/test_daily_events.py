"""Native Daily menu/calendar and safe exchange behavior."""
import copy
import datetime as dt
import sqlite3
import struct
from types import SimpleNamespace

import pytest

from test_competiciones import world,stored
from test_competition_proxy_admission import click,answer,mid
import app
import daily_events as daily
import recent_mall as rm


def test_clerk_has_native_dialogue_and_all_six_original_exchange_menus(world):
    s=world.player();s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=161,93
    click(s,71410004);assert mid(s)==504314
    answer(s,1);assert mid(s)==506591
    groups=[]
    for i in range(6):
        click(s,71410004);answer(s,1);answer(s,i);groups.append(s._lyceum_exchange)
    assert groups==[296,297,345,299,346,347]


def test_coin_exchange_is_atomic_and_cannot_be_claimed_remotely(world):
    s=world.player(items={20:22251});s.cantidades[20]=100;world.save(s)
    s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=161,93
    click(s,71410004);answer(s,1);answer(s,0)
    recipe=app._obtener_receta_exchange(12322)
    quantity=recipe['materiales'][0][1]
    assert rm.canjear(s,12322,1)
    assert 22252 in s.inventario.values()
    assert sum(s.cantidades.get(k,1) for k,v in s.inventario.items() if v==22251)==100-quantity
    before=copy.deepcopy(stored(world,s));s.personaje.tile_x=250
    rm.canjear(s,12322,1);assert stored(world,s)==before


def test_missing_original_box_contents_never_spend_daily_coins(world):
    s=world.player(items={20:22251});s.cantidades[20]=999;world.save(s)
    s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=161,93
    click(s,71410004);answer(s,1);answer(s,1)
    before=copy.deepcopy(stored(world,s));rm.canjear(s,12326,1)
    assert stored(world,s)==before


def test_daily_calendar_has_two_distinct_events_per_day_and_native_display_order(world):
    rows=daily.calendario();packets=daily.paquetes()
    assert len(rows)==42 and {r['day'] for r in rows}==set(range(7))
    assert len({r['stage'] for r in rows})==21
    for day in range(7):assert len({r['name'] for r in rows if r['day']==day})==2
    assert {r['name'] for r in rows if r['day']==0}!={r['name'] for r in rows if r['day']==1}
    for r,p in zip(rows,packets):
        assert len(p)==74 and struct.unpack_from('<I',p,58)[0]==r['id']
        assert struct.unpack_from('<I',p,66)[0]==r['entry']
        assert struct.unpack_from('<I',p,54)[0]==r['help']
        assert struct.unpack_from('<I',p,62)[0]==len(rows)  # 5F5E2F only renders at total.
        # 6CC45C formats row+28 before row+24: receiver copies +2A/+26.
        assert struct.unpack_from('<I',p,42)[0]==r['minimum']
        assert struct.unpack_from('<I',p,38)[0]==r['maximum']
        assert r['registration']<r['start']<r['end']


def test_closed_daily_packets_do_not_consume_items_or_enter(world):
    s=world.player(items={20:8537});before=copy.deepcopy(stored(world,s))
    router=app.Servidor.__new__(app.Servidor)
    router.manejar(s,0x14b,None,None,'test',b'')
    assert len(s.packets)==42 and all(p[:2]==b'\x57\x01' for p in s.packets)
    router.manejar(s,0x14a,None,None,'test',struct.pack('<I',1))
    assert stored(world,s)==before and not world.trips
    s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=161,93;daily.claim(s)
    assert b'winning certificate' in s.packets[-1] and stored(world,s)==before


def start_player(world,stage,level=410):
    s=world.player(level=level)
    daily.iniciar(stage,registration=0)
    daily.entrar(s,stage)
    daily.al_entrar(s)
    return s,daily.actual(stage)


def test_ordinary_mob_ai_does_not_depend_on_daily_state(world):
    s=world.player();m=SimpleNamespace()
    assert daily.controls_ai(s,m) is False
    assert daily.can_target(s,m) is True


@pytest.mark.parametrize('stage',[373,178,374,375,371,372,376])
def test_all_seven_events_enter_the_correct_map_and_share_round_state(world,stage):
    s,r=start_player(world,stage)
    assert s.personaje.stage==stage and world.trips[-1][1]==stage
    assert app._sala_para(s) is daily.room(r)
    assert s.monstruos is daily.room(r).monstruos
    assert any(p[:2]==b'\x6a\x01' for p in s.packets)
    assert not daily.can_target(s,next((m for m in s.monstruos.values() if getattr(m,'daily_objective',False)),SimpleNamespace(npc_type=9238,daily_objective=True)))


def test_registration_blocks_combat_and_reconnect_does_not_reset_killed_guard(world):
    s=world.player();daily.iniciar(374,registration=1);daily.entrar(s,374);daily.al_entrar(s)
    m=next(iter(s.monstruos.values()))
    assert daily.controls_ai(s,m) and not daily.can_target(s,m)
    world.now[0]+=61;daily.cron()
    assert not daily.controls_ai(s,m) and daily.can_target(s,m)
    m.hp=0;daily.muerte_monstruo(s,m);daily.al_entrar(s)
    assert s.monstruos[m.entity_id].hp==0
    assert len(daily.datos(374)['bosses'])==5
    assert len(daily.datos(375)['bosses'])==5


def test_joy_cannot_collect_before_start_or_after_end(world,monkeypatch):
    s=world.player();daily.iniciar(372,registration=1);daily.entrar(s,372);daily.al_entrar(s)
    monkeypatch.setattr(app,'_veta_de',lambda *a:(1,(0,0)))
    assert app._recolectar(s,'test',372,999)
    assert b'Wait until the Daily Event begins' in s.packets[-1]
    assert not app._sacar_de_veta(s,'test',372,999,{},1)
    world.now[0]+=61
    assert daily.participando(s)
    daily._finish(daily.actual(372))
    assert not daily.participando(s) and 'daily_joy' not in s.personaje.buffs


def test_bleach_enemy_only_death_score_settlement_claim_once_and_replay(world,monkeypatch):
    a,r=start_player(world,373);b=world.player();daily.entrar(b,373);daily.al_entrar(b)
    ally=world.player();daily.entrar(ally,373);daily.al_entrar(ally)
    assert __import__('pvp_liga').permitido(a,b)
    assert not __import__('pvp_liga').permitido(a,ally)
    # Exercise scoring independently of the visual teleport implementation.
    monkeypatch.setattr(app,'_viajar_dentro_del_mapa',lambda *a,**kw:None)
    b.muerto=True;b.personaje.hp=0;daily.baja(a,b)
    assert b.personaje.hp>0 and not b.muerto
    daily._finish(daily.actual(373));daily._finish(daily.actual(373))
    a.personaje.stage=41;a.personaje.tile_x,a.personaje.tile_y=161,93
    daily.claim(a);before=copy.deepcopy(stored(world,a));daily.claim(a)
    assert list(a.inventario.values()).count(42593)==1 and stored(world,a)==before
    assert any(b'Daily Event rewards delivered' in p for p in a.packets)
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT COUNT(*) FROM daily_rewards WHERE usuario=?',(b.usuario,)).fetchone()[0]==0


def test_full_backpack_keeps_reward_pending_and_sql_error_rolls_back_claim(world,monkeypatch):
    s,r=start_player(world,376)
    daily._finish(r)
    s.personaje.stage=41;s.personaje.tile_x,s.personaje.tile_y=161,93
    monkeypatch.setattr(app,'_ranura_libre',lambda bag:None)
    daily.claim(s)
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT claimed FROM daily_rewards').fetchone()==(0,)
    monkeypatch.setattr(app,'_ranura_libre',lambda bag:20)
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_claim BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):daily.claim(s)
    assert not s.inventario
    with sqlite3.connect(world.db) as con:assert con.execute('SELECT claimed FROM daily_rewards').fetchone()==(0,)


def test_daily_scheduler_opens_only_today_slots_once_and_closes_at_deadline(world):
    world.now[0]=dt.datetime(2026,10,25,17,45).timestamp()  # Sunday Swindle.
    daily.cron();daily.cron()
    opened=[r for r in daily._ROUNDS.values() if daily.fase(r)=='registro']
    assert {r['stage'] for r in opened}=={180,190,191,375}
    assert len(opened)==4
    world.now[0]+=15*60;daily.cron()
    assert all(daily.fase(r)=='combate' for r in opened)
    world.now[0]+=30*60;daily.cron()
    assert all(r['phase']=='ended' for r in daily._ROUNDS.values())


def test_daily_survival_objective_is_protected_and_waves_start_after_registration(world):
    s=world.player();daily.iniciar(376,registration=1);daily.entrar(s,376);daily.al_entrar(s)
    assert len(s.monstruos)==1
    tower=next(iter(s.monstruos.values()));assert tower.daily_objective
    world.now[0]+=61;daily.cron()
    waves=[m for m in s.monstruos.values() if getattr(m,'daily_wave',False)]
    assert waves and not daily.can_target(s,tower)
    assert daily.controls_ai(s,waves[0])
    waves[0].en_combate_con=s.personaje.entity_id
    assert not daily.controls_ai(s,waves[0])


def test_gm_commands_use_common_dispatcher(world):
    s=world.player()
    assert app._gm_parsear('/daily start guard 5 410 0')==('daily','daily',['start','guard','5','410','0'])
    assert app._probar_gm(s,b'/dailystart guard 5 410 0','test')
    assert daily.actual(374)
    assert app._probar_gm(s,b'/daily enter guard','test')
    assert s.personaje.stage==374


def test_native_swindle_battle_gate_and_pk_action_work_only_after_start(world):
    import eventos,eventos_mundo as em
    s=world.player();daily.iniciar(375,registration=1);daily.entrar(s,375);daily.al_entrar(s)
    effects=eventos.ejecutar(375,1,eventos.DISPAROS_AL_PASAR,em.ContextoSesion(s))
    assert not any(e[0] in ('ir_a_tag','daily_pk') for e in effects)
    world.now[0]+=61
    effects=eventos.ejecutar(375,1,eventos.DISPAROS_AL_PASAR,em.ContextoSesion(s))
    assert ('ir_a_tag',11) in effects and ('daily_pk',) in effects
    daily.pk(s);assert s._daily_unsafe and s._daily_aura


def test_native_guard_death_opens_gate_and_swindle_death_releases_chests(world):
    import eventos_mundo as em
    a,r=start_player(world,374)
    first=next(m for m in a.monstruos.values() if m.npc_type==23211);first.hp=0
    effects=em.al_morir_monstruo(a,first)
    assert any(e[0]=='objeto_estatico' for e in effects)
    b,r=start_player(world,375)
    king=next(m for m in b.monstruos.values() if m.npc_type==23216);king.hp=0
    effects=em.al_morir_monstruo(b,king)
    assert any(e[0]=='generar' for e in effects)
    before=set(b.monstruos)
    app._aplicar_efectos(b,'test',effects)
    created=[m for eid,m in b.monstruos.items() if eid not in before]
    assert created and all(m.npc_type==9224 and m.vivo for m in created)


@pytest.mark.parametrize('stage,level',[(189,100),(188,200),(179,300),(374,410)])
def test_guard_chest_batches_use_full_census_unique_walkable_tiles_and_do_not_repeat(world,stage,level):
    import eventos_mundo as em,transitable
    s,r=start_player(world,stage,level)
    bosses=[s.monstruos[eid] for eid in daily.datos(stage)['bosses']]
    for boss in bosses:
        boss.hp=0
        app._aplicar_efectos(s,'test',em.al_morir_monstruo(s,boss))
    chests=[m for m in s.monstruos.values() if m.npc_type==9223]
    assert len(chests)==370
    assert len({(m.tile_x,m.tile_y) for m in chests})==370
    assert all(transitable.se_pisa(stage,m.tile_x,m.tile_y) for m in chests)
    assert sum(m.zona_generador==220 for m in chests)==10
    assert sum(m.zona_generador==218 for m in chests)==150
    app._aplicar_efectos(s,'test',em.al_morir_monstruo(s,bosses[0]))
    assert len([m for m in s.monstruos.values() if m.npc_type==9223])==370
    chest=chests[0];chest.hp=0
    effects=em.al_morir_monstruo(s,chest)
    assert ('ir_a_tag',1) in effects  # Original chest opening returns to entry.
    daily._ROOMS.pop(r['id']);daily.al_entrar(s)
    assert len([m for m in s.monstruos.values() if m.npc_type==9223])==370
    assert s.monstruos[chest.entity_id].hp==0


def test_swindle_releases_forty_distributed_chests_and_opening_returns_to_faction_entry(world):
    import eventos_mundo as em
    s,r=start_player(world,375)
    king=next(m for m in s.monstruos.values() if m.npc_type==23216);king.hp=0
    effects=em.al_morir_monstruo(s,king);app._aplicar_efectos(s,'test',effects)
    chests=[m for m in s.monstruos.values() if m.npc_type==9224]
    assert len(chests)==40 and len({(m.tile_x,m.tile_y) for m in chests})==40
    chests[0].hp=0
    assert any(e[0]=='ir_a_tag' for e in em.al_morir_monstruo(s,chests[0]))


def test_daily_experience_tick_awards_periodic_exp_and_skill_exp(world):
    import daily_experience
    s, r = start_player(world, 374, level=410)
    s.personaje.habilidades = [(1, 10, 0)]  # Sword skill
    world.save(s)
    init_exp = s.personaje.exp
    stamp = r['start'] + 10
    daily_experience.tick(r, stamp)
    assert s.personaje.exp > init_exp
    assert s.personaje.habilidades[0][2] > 0
    # Chat notices (0x000D) and status updates (0x001D) sent, NO fake damage/heal floats (0x000B)
    assert any(p[:2] == b'\x0d\x00' for p in s.packets)
    assert any(p[:2] == b'\x1d\x00' for p in s.packets)
    assert not any(p[:2] == b'\x0b\x00' for p in s.packets)
    # Consecutive tick before interval does nothing
    exp_after = s.personaje.exp
    daily_experience.tick(r, stamp + 2)
    assert s.personaje.exp == exp_after


def test_periodic_daily_reward_commits_progress_and_replay_receipt_together(world):
    import daily_experience
    s,r=start_player(world,374,level=410)
    s.personaje.habilidades=[(1,10,0)];world.save(s)
    stamp=r['start']+10
    daily_experience.tick(r,stamp)
    data=stored(world,s)
    assert data['exp']==s.personaje.exp and data['habilidades']==[list(h) for h in s.personaje.habilidades]
    before=s.personaje.exp
    r.pop('_exp_tick',None)
    daily_experience.tick(r,stamp)
    assert s.personaje.exp==before
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT COUNT(*) FROM daily_presence_awards').fetchone()[0]==1
    daily_experience.tick(r,stamp+10)
    assert s.personaje.exp>before


def test_daily_reward_sql_failure_can_retry_without_partial_skill_or_exp(world):
    import daily_experience
    s,r=start_player(world,374,level=410)
    s.personaje.habilidades=[(1,10,0)];world.save(s)
    initial=s.personaje.exp;stamp=r['start']+10
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_daily BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):daily_experience.tick(r,stamp)
    assert s.personaje.exp==initial and s.personaje.habilidades==[(1,10,0)]
    with sqlite3.connect(world.db) as con:con.execute('DROP TRIGGER fail_daily')
    daily_experience.tick(r,stamp)
    assert stored(world,s)['exp']==s.personaje.exp>initial


def test_immediate_gm_daily_has_one_battle_banner_and_no_signup_banner(world,monkeypatch):
    packets=[];monkeypatch.setattr(app,'_tw_difundir',lambda *pk:packets.extend(pk))
    daily.iniciar_evento('guard',minutes=30,registration=0)
    assert len(packets)==1 and b'battle has begun' in packets[0]
    daily.cron()
    assert len(packets)==1


def test_swindle_world_spawns_players_on_their_respective_faction_platforms(world):
    daily.iniciar_evento('swindle', minutes=30, registration=0)
    for faction, expected_tile in [
        ('Aurora', (97, 158)),
        ('Beasts', (95, 51)),
        ('Steel', (305, 52)),
        ('Shadow', (303, 155)),
    ]:
        p_ses = world.player(level=410)
        p_ses.personaje.faction = faction
        daily.entrar(p_ses, 375)
        assert (p_ses.personaje.tile_x, p_ses.personaje.tile_y) == expected_tile


def test_daily_banner_announcements_broadcast_top_notices(world, monkeypatch):
    import totem_war
    broadcasted = []
    monkeypatch.setattr('app._tw_difundir', lambda *pkts: broadcasted.extend(pkts))
    daily.iniciar_evento('guard', minutes=30, registration=5)
    assert any(p[:2] == b'\x28\x01' for p in broadcasted)  # 0x0128 cartel_deslizante banner



def test_daily_exit_portals_present_and_visible_in_all_daily_stages(world):
    import login
    for stage in sorted(daily.STAGES):
        d = daily.datos(stage)
        exits = [p for p in d.get('portals', []) if p.get('daily_exit')]
        assert len(exits) >= 1, f'Stage {stage} missing exit portal'
        for exit_p in exits:
            assert exit_p['destino'] == 41
            assert exit_p['llegada'] == [175, 89]
            assert exit_p['radio'] == 2
            assert exit_p['dibujar'] is True
        # Visual spawn objects generated for exit
        pkts = login.portales_de(stage)
        assert len(pkts) >= len(exits)
    # Stage 374 specifically at archway [28, 25]
    exit_374 = next(p for p in daily.datos(374)['portals'] if p.get('daily_exit'))
    assert exit_374['tile'] == [28, 25]


def test_simultaneous_daily_event_family_start_and_level_bracket_routing(world):
    s_low = world.player(level=50)
    s_high = world.player(level=410)
    daily.comando_gm(s_high, 'dailystart', ['guard', '30', '0'])
    # All 4 brackets are started
    for stg in (189, 188, 179, 374):
        assert daily.fase(daily.actual(stg)) in ('registro', 'combate')
    # Low level enters tier I (stage 189)
    daily.entrar(s_low, 374)  # Even if requested 374, routed to 189 for level 50
    assert s_low.personaje.stage == 189
    # High level enters tier IV (stage 374)
    daily.entrar(s_high, 189)  # Even if requested 189, routed to 374 for level 410
    assert s_high.personaje.stage == 374

