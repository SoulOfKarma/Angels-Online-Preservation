"""Registration reminders share /notice delivery, for Arena and Holy alike."""
import datetime as dt

import pytest

from test_competiciones import world
import competiciones as c
import totem_war


def tick(world, timestamp):
    world.now[0] = timestamp
    c.cron(dt.datetime.fromtimestamp(timestamp).astimezone())


@pytest.mark.parametrize('stage',[112,159,239,240])
def test_default_signup_notices_10_5_1_start_once_and_cache_reload(world,monkeypatch,stage):
    messages = []
    monkeypatch.setattr(c,'anunciar',messages.append)
    level = {112:410,159:60,239:260,240:410}[stage]
    r = c.iniciar(stage,60,nivel=level)
    start = r['inicio']
    assert start-world.now[0] == 15*60
    assert 'for 15 minutes' in messages[0]
    tick(world,start-14*60)
    assert len(messages) == 1
    for minutes in (10,5,1):
        tick(world,start-minutes*60)
        assert 'registration closes in %d minute' % minutes in messages[-1]
        count = len(messages)
        tick(world,start-minutes*60+5)
        assert len(messages) == count
        c._BASE = None
        c._RONDAS.clear()
        tick(world,start-minutes*60+10)
        assert len(messages) == count
    tick(world,start)
    assert messages[-1].endswith('registration closed. Battle begins!')
    count = len(messages)
    tick(world,start+5)
    assert len(messages) == count
    assert c.ronda(stage)['avisos_registro'] == [15,10,5,1]


@pytest.mark.parametrize('stage',[112,240])
def test_short_test_signup_only_reminds_one_minute(world,monkeypatch,stage):
    messages = []
    monkeypatch.setattr(c,'anunciar',messages.append)
    r = c.iniciar(stage,60,2,410)
    tick(world,r['inicio']-60)
    assert len(messages) == 2
    assert 'closes in 1 minute.' in messages[-1]
    tick(world,r['inicio'])
    assert messages[-1].endswith('Battle begins!')


def test_delayed_clock_does_not_replay_obsolete_notices(world,monkeypatch):
    messages = []
    monkeypatch.setattr(c,'anunciar',messages.append)
    r = c.iniciar(112,60)
    tick(world,r['inicio']-4*60)
    assert len(messages) == 1  # No obsolete 10/5 announcements on recovery.
    tick(world,r['inicio']-60)
    assert '1 minute.' in messages[-1]


def test_cancelled_round_never_announces_countdown_or_start(world,monkeypatch):
    messages = []
    monkeypatch.setattr(c,'anunciar',messages.append)
    r = c.iniciar(112,60)
    c.terminar(112,'gm stop')
    count = len(messages)
    for seconds in (600,300,60,0,-5):
        tick(world,r['inicio']-seconds)
    assert len(messages) == count


@pytest.mark.parametrize('scores,winner',[( (2,1),'Jabaly'),((1,2),'Raphael'),((0,0),None),((3,3),None)])
def test_holy_final_notice_names_only_the_winner(world,monkeypatch,scores,winner):
    messages = []
    monkeypatch.setattr(c,'anunciar',messages.append)
    r = c.iniciar(112,60,0)
    r['puntos'].update(zip(('1','2'),scores))
    assert c.terminar(112,'time limit')
    expected = 'The Holy Battlefield event ends now.'
    if winner:
        expected += ' Congratulations! %s won the event.' % winner
    assert messages[-1] == expected
    count = len(messages)
    assert not c.terminar(112,'time limit')
    assert len(messages) == count


def test_holy_cancel_never_declares_a_winner(world,monkeypatch):
    messages = []
    monkeypatch.setattr(c,'anunciar',messages.append)
    r = c.iniciar(112,60,0)
    r['puntos']['1'] = 5
    c.terminar(112,'gm stop')
    assert messages[-1] == 'The Holy Battlefield event ends now.'


def test_holy_countdown_keeps_original_deadline_on_reentry(world):
    c.iniciar(112,60,0)
    s = world.player(items={20:8537})
    c.entrada(s,112)
    c.terminar(112,'time limit')
    deadline = s._holy_retorno[1]
    world.now[0] += 4
    s._holy_retorno = None
    c.al_entrar(s)
    assert s._holy_retorno[1] == deadline
    c.tick_retornos()
    expected = b'The event has now ended. You will be teleported out of the arena in 6 seconds.'
    assert any(expected in p for p in s.packets if p[:2] == b'\x0d\0')
    world.now[0] = deadline
    c.tick_retornos()
    assert s.personaje.stage == 114


@pytest.mark.parametrize('command',['hbstart','aastart'])
def test_gm_defaults_to_fifteen_minutes(world,command):
    ses = world.player()
    c.comando_gm(ses,command,[])
    stage = 112 if command == 'hbstart' else 240
    assert c.ronda(stage)['inicio']-world.now[0] == 900


def test_gm_begin_skips_remaining_reminders_and_announces_start_once(world,monkeypatch):
    messages = []
    monkeypatch.setattr(c,'anunciar',messages.append)
    ses = world.player()
    c.comando_gm(ses,'hbstart',[])
    c.comando_gm(ses,'hb',['begin'])
    assert len([m for m in messages if 'Battle begins!' in m]) == 1
    tick(world,world.now[0]+5)
    assert not any('registration closes in' in m for m in messages)
    assert len([m for m in messages if 'Battle begins!' in m]) == 1


def test_reminder_uses_identical_notice_packet(world):
    r = c.iniciar(112,60)
    world.broadcasts.clear()
    tick(world,r['inicio']-600)
    assert world.broadcasts == [totem_war.cartel_deslizante(
        'Holy Battlefield: registration closes in 10 minutes. Enter via Sign-up Office.')]
