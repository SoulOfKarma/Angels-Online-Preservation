"""Unused furniture stays tradable; registration and layouts are persistent."""
import copy
import sqlite3
import struct

import pytest
from test_competiciones import world,stored
from test_recent_mall import use,total
import app
import casas
import cuentas
import furniture_items as furniture


def test_playful_lizard_egg_gives_one_original_random_unused_furniture(world,monkeypatch):
    import recent_mall
    s=world.player(items={20:82599})
    monkeypatch.setattr(recent_mall.random,'choices',lambda rows,**kw:[rows[1]])
    use(s,20)
    assert s.inventario=={20:73227} and not furniture.protegido(s,20)


def test_two_registered_furniture_items_have_independent_uids_and_binding(world,monkeypatch):
    monkeypatch.setattr(cuentas,'_notificar_cambio',lambda **kw:None)
    s=world.player(items={20:73226,21:73227})
    use(s,20);use(s,21)
    assert s.inventario=={377:73226,378:73227}
    assert s.instancias[377]!=s.instancias[378]
    assert furniture.protegido(s,377) and furniture.protegido(s,378)
    assert stored(world,s)['mejoras']['377']['vinculacion']['dueno']==s.personaje.char_id
    assert stored(world,s)['custom_field']=='preserve me'


def test_furniture_registration_failure_does_not_consume_stock(world,monkeypatch):
    s=world.player(items={20:73226})
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER furniture_fail BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    before=copy.deepcopy(stored(world,s))
    with pytest.raises(sqlite3.IntegrityError):furniture.usar(s,20)
    assert s.inventario=={20:73226} and stored(world,s)==before


def test_multiple_placed_items_survive_save_reload_and_removing_one(world,monkeypatch):
    monkeypatch.setattr(cuentas,'_notificar_cambio',lambda **kw:None)
    s=world.player(items={20:73226,21:73227});use(s,20);use(s,21)
    c=casas.CasaData(s.personaje.char_id,s.personaje.nombre,deed_id=10115)
    s.personaje.stage=500;s.casa_visitando=c;s.house_furnishing=True;c.is_open=False
    entries=[dict(item_id=item,item_uid=struct.unpack('<Q',s.instancias[slot])[0],dir=0,x=x,y=100,state=0,extra=0,expire=0)
             for slot,item,x in ((377,73226,100),(378,73227,140))]
    def save(items):
        body=struct.pack('<I17s',len(items),b'Test House')+b''.join(casas._FURNITURE_RECORD.pack(*[e[k] for k in ('item_id','item_uid','dir','x','y','state','extra','expire')]) for e in items)
        app.Servidor.__new__(app.Servidor).manejar(s,0x13b,None,None,'test',body)
    save(entries)
    assert len(c.placed_furniture)==2 and not s.inventario
    assert len(stored(world,s)['casa']['placed_furniture'])==2
    loaded=casas.CasaData.deserializar(stored(world,s)['casa'])
    assert loaded.placed_furniture==c.placed_furniture
    save(entries[1:])
    assert c.placed_furniture==entries[1:] and total(s,73226)==1
    assert len(stored(world,s)['casa']['placed_furniture'])==1


def test_mall_latest_category_and_no_taurus_2013():
    import item_mall
    rows=item_mall.disponibles()
    assert next(r for r in rows if r['item']==81972)['category']==23
    assert not any(r['item'] in range(31441,31448) for r in rows)
    assert set(range(80489,80496))<={r['item'] for r in rows if r['category']==28}
    assert {11,13,19,22,23,28,29,30,31,32,33,34,35}<={r['category'] for r in rows}
