"""Native wire, original stat values and transactional card operations."""
import copy
import json
import sqlite3
import struct
import asyncio

import pytest
from test_competiciones import world,stored
import app
import star_blessing as star


def save_state(w,s,state):
    s.personaje.star_blessing=star.estado(state)
    with sqlite3.connect(w.db) as con:
        data=stored(w,s);data['star_blessing']=s.personaje.star_blessing
        con.execute('UPDATE personajes SET datos=? WHERE char_id=?',(json.dumps(data),s.personaje.char_id))


def move(s,cmd,src,dest=0xffffffff):
    app.Servidor.__new__(app.Servidor).manejar(s,0x15f,None,None,'test',struct.pack('<III',cmd,src,dest))


def act(s,cmd):
    app.Servidor.__new__(app.Servidor).manejar(s,0x16,None,None,'test',struct.pack('<BI',70,cmd))


def test_native_state_unlocks_all_eight_slots_and_has_exact_field_boundaries(world):
    s=world.player(level=434);pkt=star.paquete(s.personaje)
    assert struct.unpack_from('<H4I',pkt)==(0x17f,len(pkt)-2,1,8,8)
    # Parse using the native reader sizes, not a mirror of the serializer.
    off=18
    sizes={1:36,2:84,3:44,4:4,5:8,7:69,8:46,9:1}
    for key in (1,2,3,4,5,7,8,9):
        assert struct.unpack_from('<IB',pkt,off)==(key,1)
        off+=5+sizes[key]
    assert off==len(pkt)


def test_card_equip_upgrade_unequip_persist_and_change_real_stats(world):
    s=world.player();save_state(world,s,dict(saved=[10801],power=100))
    move(s,3,1)
    assert star.bonos(s.personaje)=={'atk':40}
    assert stored(world,s)['star_blessing']['equipped'][0]==10801
    move(s,5,1);act(s,12);move(s,7,1,1)
    assert star.bonos(s.personaje)=={'atk':80}
    assert s.personaje.star_blessing['power']==0
    move(s,6,1)
    assert not star.bonos(s.personaje) and s.personaje.star_blessing['saved'][0]==10802
    assert stored(world,s)['custom_field']=='preserve me'


def test_duplicates_locked_slots_and_insufficient_starforce_roll_back(world):
    s=world.player(level=100);save_state(world,s,dict(saved=[10801,30801],working=10801))
    move(s,3,1,2)
    assert not any(s.personaje.star_blessing['equipped'])
    move(s,3,1,1);before=copy.deepcopy(stored(world,s))
    move(s,3,2,1)  # Replacing the same type is valid and preserves the old card.
    assert s.personaje.star_blessing['saved'][1]==10801
    move(s,3,2,2)
    assert s.personaje.star_blessing['equipped'][1]==0
    before=copy.deepcopy(stored(world,s));act(s,12)
    assert stored(world,s)==before


def test_convert_is_once_only_and_exchange_revalidates_materials(world):
    s=world.player();save_state(world,s,dict(temp=[10801,30801],dust=20))
    act(s,15);act(s,15)
    assert s.personaje.star_blessing['power']==300
    star.exchange(s,1,1);act(s,20);act(s,20)
    assert s.personaje.star_blessing['saved'].count(50801)==1
    assert s.personaje.star_blessing['dust']==0


def test_failed_database_commit_never_spends_currency_or_moves_cards(world):
    s=world.player();before=copy.deepcopy(stored(world,s))
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER star_fail BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):star.accion(s,1)
    assert stored(world,s)==before and s.oro==before['oro'] and not s.personaje.star_blessing


def test_no_gold_no_card_and_premium_unknown_never_charges(world):
    s=world.player(gold=0);act(s,1)
    assert not any(star.estado(s.personaje.star_blessing)['temp'])
    assert s.oro==0
    s=world.player();before=copy.deepcopy(stored(world,s));act(s,101)
    assert stored(world,s)==before


def wire_fields(p):
    packet=star.paquete(p);size,rank,unlocked,count=struct.unpack_from('<4I',packet,2)
    assert size==len(packet)-2 and size-4==len(packet)-6
    off=18;fields={}
    for _ in range(count):
        key,enabled=struct.unpack_from('<IB',packet,off);off+=5
        if key in (1,2,3):
            n=struct.unpack_from('<I',packet,off)[0];length=4+n*4
        else:length={4:4,5:8,7:69,8:46,9:1}[key]
        fields[key]=packet[off:off+length];off+=length
    assert off==len(packet)
    return fields


def test_received_cards_go_to_divination_not_matrix_and_native_stardust_counter(world):
    s=world.player(items={20:58283});s.cantidades[20]=3;s.personaje.cantidades=s.cantidades
    save_state(world,s,dict(temp=[30801],saved=[50801],equipped=[10801],power=145,dust=28))
    fields=wire_fields(s.personaje)
    # Native receiver destinations: key1 -> +60 (matrix), key2 -> +40
    # (showTempSlot), key3 -> +20 (storage). Distinct sentinels catch swaps.
    assert struct.unpack_from('<II',fields[1])==(8,10801)
    assert struct.unpack_from('<II',fields[2])==(20,30801)
    assert struct.unpack_from('<II',fields[3])==(10,50801)
    assert struct.unpack('<II',fields[5])==(28,145)


def test_star_key_consumes_one_and_grants_free_v_credit_without_gold(world,monkeypatch):
    s=world.player(items={20:58283},gold=0);s.cantidades[20]=2;world.save(s)
    # Perfect bonus + non-dust free Divination V, independent of unlocked rank.
    monkeypatch.setattr(star.random,'choices',lambda values,**kw:[True] if values==(False,True) else [3])
    act(s,101)
    assert s.cantidades[20]==1 and s.oro==0
    state=stored(world,s)['star_blessing']
    assert sum(bool(c) for c in state['temp'])==1 and state['free_v']==1
    assert not any(state['equipped']) and not any(state['saved'])
    assert any(c//10000==5 for c in state['temp'])
    fields=wire_fields(s.personaje)
    assert struct.unpack_from('<5i',fields[7])==(0,0,0,0,1)
    act(s,5)
    assert s.oro==0 and s.personaje.star_blessing['free_v']==0
    assert sum(bool(c) for c in s.personaje.star_blessing['temp'])==2


def test_full_outcomes_or_database_failure_never_spends_star_key(world):
    s=world.player(items={20:58283});save_state(world,s,dict(temp=[10801]*20))
    before=copy.deepcopy(stored(world,s));act(s,101)
    assert stored(world,s)==before and s.inventario=={20:58283}
    save_state(world,s,{})
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_key BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):star.accion(s,101)
    assert s.inventario=={20:58283} and not any(star.estado(s.personaje.star_blessing)['temp'])


def test_native_bingo_uses_sign_types_line_count_and_typed_original_rewards(world):
    s=world.player();save_state(world,s,dict(bingo=[10801,11501,10101,10201,10601,10901,11001,11101,10701],
                                           marked=[1,1,1,0,0,0,0,0,0],free_iv=8,free_v=0))
    fields=wire_fields(s.personaje)
    assert struct.unpack_from('<5i',fields[7])==(0,0,0,8,0)
    assert [struct.unpack_from('<IB',fields[7],20+5*i)[0] for i in range(9)]==[8,15,1,2,6,9,10,11,7]
    assert struct.unpack_from('<I',fields[7],65)==(1,)
    count=struct.unpack_from('<I',fields[8])[0]
    rewards=[struct.unpack_from('<BBI',fields[8],4+6*i) for i in range(count)]
    assert rewards==[(1,1,5),(2,1,10),(3,1,20),(4,1,40),(5,1,80),(6,4,3),(8,1,320)]


def test_bingo_claim_is_once_only_and_completed_bingo_does_not_block_divination(world):
    s=world.player();save_state(world,s,dict(bingo=list(range(1,10)),marked=[1]*9))
    gold=s.oro;act(s,1)
    assert s.oro==gold-1000000 and sum(bool(c) for c in s.personaje.star_blessing['temp'])==1
    act(s,16);act(s,16)
    assert s.personaje.star_blessing['power']==320 and not any(s.personaje.star_blessing['marked'])
    assert stored(world,s)['star_blessing']['power']==320


def test_six_bingo_lines_grant_three_real_free_iv_draws(world,monkeypatch):
    s=world.player(gold=0)
    save_state(world,s,dict(bingo=list(range(1,10)),marked=[1,0,1,1,1,1,1,1,1]))
    assert star.lineas(s.personaje.star_blessing)==6
    act(s,16)
    assert s.personaje.star_blessing['free_iv']==3 and s.personaje.star_blessing['power']==0
    monkeypatch.setattr(star.random,'randrange',lambda *a:99)
    for _ in range(3):act(s,4)
    assert s.personaje.star_blessing['free_iv']==0 and s.oro==0
    assert sum(bool(c) for c in s.personaje.star_blessing['temp'])==3
    before=copy.deepcopy(stored(world,s));act(s,4);assert stored(world,s)==before


def test_bingo_lucky_draw_consumes_its_item_once_and_never_coins(world):
    s=world.player(items={20:58284});save_state(world,s,dict(bingo=list(range(1,10))))
    gold=s.oro;act(s,17)
    assert not s.inventario and sum(s.personaje.star_blessing['marked'])==1 and s.oro==gold
    before=copy.deepcopy(stored(world,s));act(s,17);assert stored(world,s)==before


@pytest.mark.parametrize('recipe_id',list(star.datos()['recipes']))
def test_all_native_perfect_and_olympian_recipes_consume_exact_materials(world,recipe_id):
    recipe=star.datos()['recipes'][recipe_id]
    saved=[card for card,qty in recipe['materials'] if card!=99901 for _ in range(qty)]
    dust=sum(qty for card,qty in recipe['materials'] if card==99901)
    s=world.player();save_state(world,s,dict(saved=saved,dust=dust))
    group=recipe['group']
    recipes=[r for r in star.datos()['recipes'].values() if r['group']==group]
    star.exchange(s,group,recipes.index(recipe)+1);act(s,20)
    state=stored(world,s)['star_blessing']
    assert [c for c in state['saved'] if c]==[recipe['reward']] and state['dust']==0
    before=copy.deepcopy(state);act(s,20);assert stored(world,s)['star_blessing']==before


def test_dust_stays_out_of_storage_and_converts_to_dust_not_starforce(world):
    s=world.player();save_state(world,s,dict(temp=[99901,10801]))
    before=copy.deepcopy(stored(world,s));move(s,1,1);assert stored(world,s)==before
    act(s,15)
    assert s.personaje.star_blessing['dust']==1 and s.personaje.star_blessing['power']==50
    assert struct.unpack('<II',wire_fields(s.personaje)[5])==(1,50)


def test_native_coin_prices_and_left_rank_transition_are_enforced(world,monkeypatch):
    s=world.player();monkeypatch.setattr(star.random,'randrange',lambda *a:0)
    assert star.datos()['local_rules']['divination_costs']==[1000000,2000000,4000000,8000000,16000000]
    before=s.oro;act(s,1)
    assert s.oro==before-1000000 and s.personaje.star_blessing['rank']==2
    act(s,2);assert s.oro==before-3000000 and s.personaje.star_blessing['rank']==3
    before=copy.deepcopy(stored(world,s));act(s,5);assert stored(world,s)==before


def test_auto_divine_sends_one_outcome_at_a_time_and_stops_full(world,monkeypatch):
    s=world.player();save_state(world,s,dict(bingo=list(range(2,11)),marked=[1]*9))
    monkeypatch.setattr(star,'AUTO_INTERVAL',0.001)
    monkeypatch.setattr(star.random,'choices',lambda *a,**kw:[1])
    monkeypatch.setattr(star.random,'randint',lambda *a:1)
    monkeypatch.setattr(star.random,'randrange',lambda *a:99)
    initial=s.oro
    async def run():
        act(s,13);task=s._star_auto_task;act(s,13)
        assert s._star_auto_task is task
        await task
    asyncio.run(run())
    assert all(s.personaje.star_blessing['temp']) and s.oro==initial-20000000
    packets=[p for p in s.packets if p[:2]==b'\x7f\x01']
    assert len(packets)==22 and not s.personaje._star_auto
    before=copy.deepcopy(stored(world,s));act(s,13);assert stored(world,s)==before


def test_auto_divine_stops_at_insufficient_gold_without_losing_cards(world,monkeypatch):
    s=world.player(gold=1500000)
    monkeypatch.setattr(star,'AUTO_INTERVAL',0.001)
    monkeypatch.setattr(star.random,'randrange',lambda *a:99)
    async def run():
        act(s,13);await s._star_auto_task
    asyncio.run(run())
    assert s.oro==500000 and sum(bool(c) for c in s.personaje.star_blessing['temp'])==1


def test_empty_free_draw_counters_never_send_negative_badges(world):
    s=world.player()
    for rank in range(1,6):
        save_state(world,s,dict(rank=rank))
        assert struct.unpack_from('<5i',wire_fields(s.personaje)[7])==(0,0,0,0,0)


@pytest.mark.parametrize('marks,power,free_iv,total_cost',[
    ([1,1,1,0,0,0,0,0,0],5,0,20000000),
    ([1,0,1,1,1,1,1,1,1],0,3,17000000),
])
def test_collect_between_auto_draws_keeps_task_cards_and_payment_consistent(
        world,monkeypatch,marks,power,free_iv,total_cost):
    s=world.player();save_state(world,s,dict(bingo=list(range(1,10)),marked=marks))
    monkeypatch.setattr(star,'AUTO_INTERVAL',0.001)
    monkeypatch.setattr(star.random,'choices',lambda *a,**kw:[1])
    monkeypatch.setattr(star.random,'randint',lambda *a:1)
    monkeypatch.setattr(star.random,'randrange',lambda *a:99)
    gold=s.oro
    async def run():
        act(s,13);task=s._star_auto_task
        await asyncio.sleep(0)  # First draw commits, then yields to Collect.
        assert s.personaje._star_auto and not task.done()
        assert sum(bool(c) for c in s.personaje.star_blessing['temp'])==1
        coins=s.oro;act(s,16)
        state=s.personaje.star_blessing
        assert state['power']==power and state['free_iv']==free_iv
        assert not any(state['marked']) and s.oro==coins
        assert s._star_auto_task is task and s.personaje._star_auto
        act(s,16)  # No new lines: neither duplicate reward nor cancellation.
        assert s.personaje.star_blessing==state and s._star_auto_task is task
        await task
    asyncio.run(run())
    state=stored(world,s)['star_blessing']
    assert state['power']==power and state['free_iv']==0
    assert sum(bool(c) for c in state['temp'])==20 and s.oro==gold-total_cost
    assert not s.personaje._star_auto and s._star_auto_task is None
