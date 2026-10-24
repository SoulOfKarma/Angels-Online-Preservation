"""Original reward responses through the real Clerk choice/ack router."""
import copy
import struct
import sqlite3

import pytest

from test_arena_reward_compat import result, claim_row
from test_competiciones import world, stored
from test_competition_proxy_admission import click, answer, mid
import app
import house_services


def claim(s):
    click(s,114004)
    answer(s,3)  # original root option7751


def test_delivery_shows_original_dialogue_and_ack_does_not_deliver_again(result):
    w,a,b=result
    claim(a)
    assert claim_row(w,a)[0]=='entregado'
    assert mid(a)==7761
    assert a.packets[-1]==struct.pack('<HIHBBB',18,7761,71,0,0,0)
    assert a.dlg_mapa is None and a._competicion_dialogo is None
    saved=copy.deepcopy(stored(w,a))
    answer(a)
    assert a.packets[-1]==struct.pack('<H',18)+bytes(9)
    assert stored(w,a)==saved
    claim(a)
    assert stored(w,a)==saved
    assert mid(a)==7781  # already claimed is never reported as a new delivery


@pytest.mark.parametrize('state',['sin_puesto','cancelado','observador','sin_competencia'])
def test_ineligible_result_shows_original_no_reward_dialogue(result,state):
    w,a,b=result
    with sqlite3.connect(w.db) as con:
        con.execute('UPDATE competiciones_premios SET estado=?,plan=? WHERE char_id=?',
                    (state,'null',a.personaje.char_id))
    saved=copy.deepcopy(stored(w,a))
    claim(a)
    assert mid(a)==7781 and stored(w,a)==saved
    assert claim_row(w,a)[0]==state
    answer(a)
    assert a.packets[-1]==struct.pack('<H',18)+bytes(9)


def test_no_result_shows_original_no_reward_dialogue(world):
    s=world.player(level=434)
    claim(s)
    assert mid(s)==7781 and not s.inventario


def test_full_bag_shows_original_rejection_then_retry_shows_delivery(result,monkeypatch):
    w,a,b=result
    a.inventario.update({s:8536 for s in range(20,25)})
    w.save(a)
    monkeypatch.setattr(app,'_tope_bolsa',lambda bag:25)
    saved=copy.deepcopy(stored(w,a))
    claim(a)
    assert mid(a)==7762 and claim_row(w,a)[0]=='pendiente'
    assert stored(w,a)==saved
    answer(a)
    a.inventario.clear();w.save(a)
    monkeypatch.setattr(app,'_tope_bolsa',lambda bag:40)
    claim(a)
    assert mid(a)==7761 and claim_row(w,a)[0]=='entregado'


def test_expired_claim_shows_original_deadline_dialogue(result):
    w,a,b=result
    w.now[0]=claim_row(w,a)[1]['reclamar_hasta']
    claim(a)
    assert mid(a)==7775 and claim_row(w,a)[0]=='caducado'
    assert not a.inventario


def test_dialogue_ids_exist_in_original_english_data():
    rows=house_services.xml_rows('msg.xml')
    assert 'take this gear' in rows[7761]['\u6587\u5b57']
    assert 'bag is full' in rows[7762]['\u6587\u5b57']
    assert 'time for collecting' in rows[7775]['\u6587\u5b57']
    assert 'disqualified from claiming' in rows[7781]['\u6587\u5b57']
