"""Native encrypted answers, timing, helpers, original Top30 claims and SQL."""
import copy
import json
import sqlite3
import struct
import pytest
from test_competiciones import world,stored
import app
import elementary as q
import elementary_codec as wire


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(q,'_ROUND',None);monkeypatch.setattr(q,'_LOADED',False)


def request(srv,s,op,body=b''):
    decoded={'valor':body[0]} if op==0xb and body else None
    srv.manejar(s,op,None,decoded,'test',body)
def setup(world,items=None):
    s=world.player(level=10,items=items)
    srv=app.Servidor.__new__(app.Servidor);srv.mundos=world.players
    return srv,s
def enrol(world,srv,s,flags=b'\0\0'):
    q.start(10);request(srv,s,0x150)
    assert world.trips[-1][1:]==(502,97,63)
    request(srv,s,0x152,flags)
    world.now[0]+=10;q.cron()
    return q.current()
def answer_body(r,choice,decoy=2,remaining=999):
    item=r['questions'][r['index']]
    encoded=q._cipher(r['key']).encode(str((item['seed']+choice)<<item['seed']))
    return struct.pack('<II2BI',item['cookie'],decoy,0,0,remaining)+encoded.ljust(33,b'\0')


def test_original_cipher_standard_zero_key_vector_and_native_little_endian():
    cipher=wire.Cipher(bytes(4))
    assert cipher.block(0,0)==(0x4ef99745,0x6198dd78)
    assert cipher.block(0x4ef99745,0x6198dd78,decrypt=True)==(0,0)
    cipher=wire.Cipher('abcd')
    for seed in range(1,9):
        for choice in range(3):
            encoded=cipher.encode(str((seed+choice)<<seed))
            assert wire.answer(cipher,encoded,seed)==choice
    with pytest.raises(ValueError):wire.answer(cipher,b'not base64!',1)


def test_native_registration_question_and_server_time_score_not_client_decoy(world):
    srv,s=setup(world);r=enrol(world,srv,s)
    packet=next(p for p in s.packets if p[:2]==b'\x63\x01')
    fields=packet[22:-1].split(wire.SEPARATOR)
    cipher=q._cipher(r['key']);text=[cipher.decode(x) for x in fields]
    assert len(text)==6 and text[-1]==str(r['questions'][0]['seed'])
    world.now[0]+=5
    request(srv,s,0x153,answer_body(r,r['questions'][0]['correct'],decoy=99,remaining=99999))
    assert q.current()['members'][q._key(s)]['score']==5
    before=copy.deepcopy(q.current())
    request(srv,s,0x153,answer_body(r,r['questions'][0]['correct']))
    assert q.current()==before
    world.now[0]+=5;q.cron()
    assert q.current()['index']==1
    #A previous question cookie cannot answer the next question.
    request(srv,s,0x153,answer_body(r,r['questions'][0]['correct']))
    assert q.current()['members'][q._key(s)]['answered']==0


def test_helper_exclusion_boost_consumed_once_protects_wrong_answer(world):
    srv,s=setup(world,{20:26626});s.cantidades[20]=2;world.save(s)
    r=enrol(world,srv,s,b'\1\0')
    request(srv,s,0x155)
    assert s.cantidades[20]==1
    m=q.current()['members'][q._key(s)]
    assert m['star']==2 and m['heart']==3 and m['protected']
    request(srv,s,0x154)
    assert s.cantidades[20]==1 and q.current()['members'][q._key(s)]['heart']==3
    wrong=next(i for i in range(3) if i!=r['questions'][0]['correct'])
    request(srv,s,0x153,answer_body(q.current(),wrong))
    assert q.current()['members'][q._key(s)]['wrong']==1 and q.current()['members'][q._key(s)]['score']==0


def test_finish_persists_progress_and_teacher_gives_original_top_prize_once(world):
    srv,s=setup(world,{20:26627})
    s.personaje.habilidades=[(1,1,0)];world.save(s)
    r=enrol(world,srv,s,b'\0\1')
    request(srv,s,0x153,answer_body(r,r['questions'][0]['correct']))
    q._finish(q.current());q.cron()
    saved=stored(world,s)
    assert saved['exp']==s.personaje.exp and saved['exp']>12345
    assert saved['habilidades']==[list(h) for h in s.personaje.habilidades]
    assert not s.inventario  #Bell consumed with progress receipt
    before=copy.deepcopy(saved);q.cron();assert stored(world,s)==before
    s.personaje.stage=41;s.personaje.tile_x=132;s.personaje.tile_y=80
    request(srv,s,0x5,struct.pack('<I',56))
    assert any(struct.unpack_from('<I',p,2)[0]==8341 for p in s.packets if p[:2]==b'\x12\0' and len(p)>6)
    request(srv,s,0xb,b'\x0a')
    assert sum(s.cantidades.get(k,1) for k,v in s.inventario.items() if v==25832)==200
    before=copy.deepcopy(stored(world,s));q.claim(s)
    assert stored(world,s)==before and any(b'prize delivered' in p for p in s.packets)
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT awarded,claimed FROM elementary_results').fetchone()==(1,1)


def test_helper_database_failure_keeps_item_counter_and_round_unchanged(world):
    srv,s=setup(world,{20:26626});r=enrol(world,srv,s,b'\1\0')
    before=copy.deepcopy(q.current())
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_quiz BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):request(srv,s,0x154)
    assert q.current()==before and s.inventario=={20:26626}


def test_quiz_persists_questions_answers_and_score_across_reload(world,monkeypatch):
    srv,s=setup(world);r=enrol(world,srv,s)
    request(srv,s,0x153,answer_body(r,r['questions'][0]['correct']))
    before=copy.deepcopy(q.current())
    monkeypatch.setattr(q,'_LOADED',False);monkeypatch.setattr(q,'_ROUND',None)
    assert q.current()==before
    request(srv,s,0x153,answer_body(r,r['questions'][0]['correct']))
    assert q.current()==before


def test_full_thirty_question_round_closes_and_persists_one_result(world):
    srv,s=setup(world);r=enrol(world,srv,s)
    for index in range(30):
        r=q.current();assert r['index']==index
        request(srv,s,0x153,answer_body(r,r['questions'][index]['correct']))
        world.now[0]+=10;q.cron()
    assert q.phase()=='closed'
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT score,place,awarded FROM elementary_results').fetchone()==(300,1,1)
        saved=json.loads(con.execute('SELECT payload FROM elementary_runs').fetchone()[0])
        assert saved['state']=='done'
    q.cron()
    with sqlite3.connect(world.db) as con:assert con.execute('SELECT COUNT(*) FROM elementary_results').fetchone()[0]==1


def test_late_answer_and_client_flags_cannot_award_or_reuse_helper(world):
    srv,s=setup(world);r=enrol(world,srv,s)
    for index in range(4):
        request(srv,s,0x154)
        m=q.current()['members'][q._key(s)]
        assert m['heart']==max(0,2-index)
        request(srv,s,0x155);assert q.current()['members'][q._key(s)]['star']==(2 if index==3 else 3)
        old=copy.deepcopy(q.current())
        world.now[0]+=10
        request(srv,s,0x153,answer_body(old,old['questions'][index]['correct']))
        assert q.current()==old
        q.cron()
    assert q.current()['members'][q._key(s)]['score']==0


def test_scheduled_registration_opens_once_per_date_without_early_battle_notice(world):
    import datetime as dt
    srv,s=setup(world)
    world.now[0]=dt.datetime(2026,10,25,18,45).astimezone().timestamp()
    q.cron();r=q.current();q.cron()
    banners=[p for p in s.packets if b'Angel Elementary registration is open' in p]
    assert len(banners)==1 and r['start']==world.now[0]+900
    assert not any(b'has begun' in p for p in s.packets)
    world.now[0]+=900;q.cron();q.cron()
    assert sum(b'has begun' in p for p in s.packets)==1


def test_teacher_refuses_zero_score_and_full_bag_keeps_reward_pending(world):
    srv,s=setup(world);r=enrol(world,srv,s)
    request(srv,s,0x153,answer_body(r,r['questions'][0]['correct']))
    q._finish(q.current())
    s.personaje.stage=41;s.personaje.tile_x=132;s.personaje.tile_y=80
    s.inventario.update({slot:20 for slot in range(20,80)});world.save(s)
    q.claim(s)
    with sqlite3.connect(world.db) as con:assert con.execute('SELECT claimed FROM elementary_results').fetchone()[0]==0
    s.inventario.pop(20);world.save(s);q.claim(s)
    assert sum(s.cantidades.get(k,1) for k,v in s.inventario.items() if v==25832)==200


def test_quiz_exit_portals_and_collision_are_native():
    import transitable
    assert {tuple(p['tile']) for p in q.portales()}=={(78,46),(115,47)}
    assert transitable.conocido(502) and transitable.se_pisa(502,97,63)
    assert not transitable.se_pisa(502,0,0)
