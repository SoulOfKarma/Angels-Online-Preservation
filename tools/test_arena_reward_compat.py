"""Authorized401+ -> original280 fallback, using temporary accounts only."""
import copy
import json
import sqlite3
import struct

import pytest
from test_competiciones import world,stored
import app
import arena_premios_compat as compat
import competiciones as c
import competicion_premios as prizes
import inventario as inv


@pytest.fixture
def result(world,monkeypatch):
    monkeypatch.setattr(app,'_stats_ses',lambda s:b'')
    c.iniciar(240,30,0,434)
    a,b=world.player(level=434),world.player(level=434)
    a.personaje.habilidades=[(17,434,0),(34,434,0)]
    b.personaje.habilidades=[(9,434,0),(33,434,0),(14,434,0)]
    for s in (a,b):world.save(s);c.entrada(s,240)
    c.baja(a,b)
    for s in (a,b):s._competicion_clerk=240
    return world,a,b


def claim_row(w,s):
    with sqlite3.connect(w.db) as con:
        state,raw=con.execute('SELECT estado,plan FROM competiciones_premios WHERE char_id=?',
                             (s.personaje.char_id,)).fetchone()
    return state,json.loads(raw)


def test_winner_and_runner_up_receive_skill_based_original280_sets_once(result):
    w,a,b=result
    state,plan=claim_row(w,a)
    assert state=='pendiente' and plan['compatibilidad']==compat.POLICY
    ids={it['id'] for it in plan['items']}
    assert ids=={66301,66313,66314,66315,66316,66317,66319,66320,66330}
    assert {it['caduca_en'] for it in plan['items']}=={w.now[0]+554400}
    assert plan['reclamar_hasta']==w.now[0]+14400
    assert prizes.entregar(a,automatico=True)==0
    assert c.opciones(a,7751)
    assert claim_row(w,a)[0]=='entregado'
    assert set(a.inventario.values())==ids
    assert all(a.personaje.mejoras[s]['arena_premio_item']==iid for s,iid in a.inventario.items())
    saved=stored(w,a)
    assert all(meta['arena_premio_fin']==w.now[0]+554400 for meta in saved['mejoras'].values())
    snapshot=copy.deepcopy(saved)
    assert c.opciones(a,7751) and stored(w,a)==snapshot
    assert prizes.entregar(b,stage=240)==1
    assert 66331 in b.inventario.values() and not any(i in b.inventario.values() for i in compat.WEAPONS.values())


def test_partial_allocation_with_full_bag_keeps_entire_claim_pending(result,monkeypatch):
    w,a,b=result
    a.inventario.update({s:8536 for s in range(20,25)})
    w.save(a)
    monkeypatch.setattr(app,'_tope_bolsa',lambda bag:25)
    before=copy.deepcopy(stored(w,a))
    assert prizes.entregar(a,stage=240)==0
    assert stored(w,a)==before and claim_row(w,a)[0]=='pendiente'
    a.inventario.clear();w.save(a)
    monkeypatch.setattr(app,'_tope_bolsa',lambda bag:40)
    assert prizes.entregar(a,stage=240)==1


def test_claim_window_expires_without_reward_or_retry_renewal(result):
    w,a,b=result
    deadline=claim_row(w,a)[1]['reclamar_hasta']
    w.now[0]=deadline
    assert prizes.entregar(a,stage=240)==0
    assert claim_row(w,a)[0]=='caducado' and not a.inventario
    assert prizes.entregar(a,stage=240)==0


def test_legacy_missing_table_is_repaired_only_at_correct_clerk_and_once(result):
    w,a,b=result
    with sqlite3.connect(w.db) as con:
        rid,raw=con.execute('SELECT ronda,datos FROM competiciones_resultados').fetchone()
        r=json.loads(raw);r.pop('arena_premio_compat',None)
        con.execute('UPDATE competiciones_resultados SET datos=?',(json.dumps(r),))
        con.execute("UPDATE competiciones_premios SET estado='sin_tabla',plan='null' WHERE char_id=?",(a.personaje.char_id,))
    assert prizes.entregar(a,automatico=True)==0
    assert prizes.entregar(a,stage=239)==0
    assert claim_row(w,a)[0]=='sin_tabla'
    assert prizes.entregar(a,stage=240)==1
    assert claim_row(w,a)[1]['usuario']==a.usuario
    assert prizes.entregar(a,stage=240)==0


def test_other_account_and_unsaved_combat_state_cannot_be_overwritten(result):
    w,a,b=result
    user=a.usuario;a.usuario='outsider'
    assert prizes.entregar(a,stage=240)==0
    a.usuario=user
    with sqlite3.connect(w.db) as con:
        data=json.loads(con.execute('SELECT datos FROM personajes WHERE char_id=?',(a.personaje.char_id,)).fetchone()[0])
        data['exp']=a.personaje.exp
        con.execute('UPDATE personajes SET datos=? WHERE char_id=?',(json.dumps(data),a.personaje.char_id))
    a.personaje.exp+=1
    assert prizes.entregar(a,stage=240)==0
    assert claim_row(w,a)[0]=='pendiente'


def test_deadline_survives_move_native_packets_and_equipped_expiry(result,monkeypatch):
    w,a,b=result
    assert prizes.entregar(a,stage=240)==1
    source=next(s for s,i in a.inventario.items() if i==66301)
    deadline=a.personaje.mejoras[source]['arena_premio_fin']
    a.inventario[3]=a.inventario.pop(source)
    app._mover_inst(a,source,3)
    assert a.personaje.mejoras[3]['arena_premio_fin']==deadline
    packet=inv.actualizar_ranuras(a.personaje.char_id,[(3,66301,1,None)],mejoras=a.personaje.mejoras)
    assert struct.unpack_from('<I',packet,6+47)[0]==int(deadline)
    p=copy.deepcopy(a.personaje.mejoras)
    # Reconnect does not renew absolute deadlines.
    a.personaje.mejoras=p
    a.personaje.hp=a.personaje.mp=2000
    w.now[0]=deadline
    compat.caducados(a)
    assert not a.inventario and not a.personaje.mejoras
    assert a.personaje.hp==a.personaje.mp==1000
    assert stored(w,a)['hp']==stored(w,a)['mp']==1000
    assert not stored(w,a)['inventario']
    assert claim_row(w,a)[0]=='entregado' and prizes.entregar(a,stage=240)==0


def test_personal_bank_move_keeps_absolute_deadline_and_expires(result):
    w,a,b=result
    assert prizes.entregar(a,stage=240)==1
    source=next(iter(a.inventario));iid=a.inventario.pop(source)
    a.personaje.banco={1:(iid,1)}
    c.mover_pase_banco(a.personaje,source,1,hacia_banco=True)
    deadline=a.personaje.mejoras[-10001]['arena_premio_fin']
    assert a.personaje.mejoras[-10001]['arena_premio_item']==iid
    compat.caducados(a,deadline)
    assert a.personaje.banco=={} and -10001 not in a.personaje.mejoras


def test_policy_is_frozen_and_never_used_for_lower_tier_or_cancelled(world,monkeypatch):
    monkeypatch.setattr(app,'_stats_ses',lambda s:b'')
    r=c.iniciar(240,30,0,434)
    assert r['arena_premio_compat']['habilitado']
    cfg=c.config_eventos()
    monkeypatch.setattr(c,'config_eventos',lambda:dict(cfg,arena_premio_compat=None))
    a,b=world.player(level=434),world.player(level=434)
    for s in (a,b):c.entrada(s,240)
    c.baja(a,b)
    assert claim_row(world,a)[0]=='pendiente'
    m=dict(nivel=400)
    assert compat.plan(dict(stage=239,clasificacion=['1']), '1',m,{}, {'habilitado':True}) is None


@pytest.mark.parametrize('place',[1,2,3,4,32,33])
def test_reward_components_follow_placement_without_fake_tickets(place):
    ranking=[str(i) for i in range(1,35)]
    plan=compat.plan(dict(stage=240,clasificacion=ranking,fin=1000,finalizada=1000),
        str(place),dict(nivel=434),dict(habilidades=[(9,434,0),(33,434,0),(14,434,0)]),
        {'habilitado':True})
    if place>32:
        assert plan is None
        return
    ids={i['id'] for i in plan['items']}
    assert (66298 in ids)==(place==1)
    assert (66304 in ids)==(place==1)
    assert (66317 in ids)==(place<=2)
    assert (bool(ids&{66330,66331,66332}))==(place<=3)
    assert {66309,66310,66311,66312,66319,66320}<=ids
    assert not ids&{17350,20191,77691}


def test_collection_and_npc_sale_cannot_launder_temporary_prize(result):
    w,a,b=result
    assert prizes.entregar(a,stage=240)==1
    slot=next(iter(a.inventario));iid=a.inventario[slot]
    assert compat.es_premio(a,slot)
    router=app.Servidor.__new__(app.Servidor)
    snapshot=copy.deepcopy(stored(w,a))
    router.manejar(a,0x16,None,None,'test',struct.pack('<BI',0x33,slot))
    assert a.inventario[slot]==iid
    router.manejar(a,0x28,None,None,'test',struct.pack('<I',1)+app._inst(a,slot)+struct.pack('<I',1))
    assert a.inventario[slot]==iid and stored(w,a)==snapshot


def test_bank_swap_keeps_each_prizes_deadline_with_its_own_item(result):
    w,a,b=result
    assert prizes.entregar(a,stage=240)==1
    slots=list(a.inventario)[:2]
    first,second=[copy.deepcopy(a.personaje.mejoras[s]) for s in slots]
    c.mover_pase_banco(a.personaje,slots[0],1,hacia_banco=True)
    c.mover_pase_banco(a.personaje,slots[1],2,hacia_banco=True)
    c.mover_pase_banco(a.personaje,1,2,desde_banco=True,hacia_banco=True,intercambio=True)
    assert a.personaje.mejoras[-10001]==second
    assert a.personaje.mejoras[-10002]==first


def test_database_failure_rolls_back_items_deadlines_and_claim(result):
    w,a,b=result
    with sqlite3.connect(w.db) as con:
        con.execute("CREATE TRIGGER fail_prize BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'failure'); END")
    before=copy.deepcopy(stored(w,a))
    with pytest.raises(sqlite3.IntegrityError):prizes.entregar(a,stage=240)
    assert stored(w,a)==before
    assert not a.inventario and not a.personaje.mejoras
    assert claim_row(w,a)[0]=='pendiente'


def test_magic_mount_follows_staff_not_armor():
    r=dict(stage=240,clasificacion=['1'],fin=1000)
    plan=compat.plan(r,'1',dict(nivel=434),dict(habilidades=[(8,434,0),(33,434,0)]),{'habilitado':True})
    ids={it['id'] for it in plan['items']}
    assert 66318 in ids and 66317 not in ids
