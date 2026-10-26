"""Legacy-house identity migration and real Decorate requests, with temp DBs."""
import copy
import json
import sqlite3
import struct

import pytest
from test_competiciones import world, stored
import app, casas


@pytest.fixture(autouse=True)
def houses(monkeypatch):
    monkeypatch.setattr(casas, '_CASAS_ACTIVAS', {})
    monkeypatch.setattr(casas, '_OBJ_A_CASA', {})


@pytest.mark.parametrize('data', [
    {'deed_id':17935},
    {'deed_id':17935, 'muebles':[]},
    {'deed_id':17935, 'owner_id':0, 'owner_name':'', 'house_name':"'s House"},
    {'deed_id':17935, 'owner_id':999, 'owner_name':'Previous', 'house_name':"Previous's House"},
])
def test_loaded_house_belongs_to_its_character_even_with_legacy_identity(data):
    before = copy.deepcopy(data)
    c = casas.obtener_o_crear_casa(1001, 'Karma', raw_data=data)
    assert (c.owner_id, c.owner_name, c.house_name, c.deed_id) == (1001,'Karma',"Karma's House",17935)
    assert data == before
    assert casas.pkt_house_name(c.house_name)[2:].rstrip(b'\0') == b"Karma's House"


def test_cached_invalid_owner_is_repaired_without_replacing_the_house():
    c = casas.CasaData(0, '', 17935)
    c.cleanliness = 870
    c.placed_furniture = [{'item_id':10476, 'item_uid':1234}]
    casas._CASAS_ACTIVAS[1001] = c
    assert casas.obtener_o_crear_casa(1001, 'Karma') is c
    assert (c.owner_id, c.owner_name, c.house_name) == (1001,'Karma',"Karma's House")
    assert c.cleanliness == 870 and c.placed_furniture[0]['item_uid'] == 1234


def test_custom_name_layout_pets_and_house_progress_survive_migration():
    c = casas.CasaData(0, '', 17935)
    c.house_name = 'My Villa';c.cleanliness = 870;c.votes_total = 13;c.visitors_total = 8
    c.placed_furniture = [{'item_id':10476,'item_uid':1234,'x':113,'y':227,'dir':1}]
    c.care_pets = {'477': {'item_id':3393,'exp':90,'name':'Pet'}}
    raw = c.serializar()
    restored = casas.obtener_o_crear_casa(1001, 'Karma', raw_data=raw).serializar()
    expected = casas.CasaData.deserializar(raw).serializar()
    expected.update(owner_id=1001, owner_name='Karma')
    assert restored == expected
    assert restored['house_name'] == 'My Villa'


def test_placeholder_lookup_never_overwrites_the_real_owner_name():
    c = casas.obtener_o_crear_casa(1001, 'Karma')
    assert casas.obtener_o_crear_casa(1001, 'Owner_1001') is c
    assert (c.owner_name, c.house_name) == ('Karma',"Karma's House")


def test_real_owner_resolves_an_earlier_placeholder_cache_entry():
    c = casas.obtener_o_crear_casa(1001, 'Owner_1001')
    assert casas.obtener_o_crear_casa(1001, 'Karma') is c
    assert (c.owner_name, c.house_name) == ('Karma',"Karma's House")


def attach(s, data, world):
    s.personaje.casa = copy.deepcopy(data)
    with sqlite3.connect(world.db) as con:
        row = json.loads(con.execute('SELECT datos FROM personajes WHERE char_id=?',
                                     (s.personaje.char_id,)).fetchone()[0])
        row['casa'] = copy.deepcopy(data)
        row['unrelated_character_field'] = 'keep'
        con.execute('UPDATE personajes SET datos=? WHERE char_id=?',
                    (json.dumps(row),s.personaje.char_id))


@pytest.mark.parametrize('has_deed', [True,False])
def test_login_repairs_and_persists_existing_zero_owner_preserving_other_fields(world,has_deed):
    s = world.player(items={376:17935} if has_deed else {})
    raw = {'deed_id':17935,'owner_id':0,'owner_name':'','house_name':"'s House",'custom_house_field':42}
    attach(s,raw,world)
    before = stored(world,s)
    app._sanear_escrituras(s.personaje,s.usuario,'test')
    after = stored(world,s)
    assert after['casa']['owner_id'] == s.personaje.char_id
    assert after['casa']['owner_name'] == s.personaje.nombre
    assert after['casa']['house_name'] == s.personaje.nombre+"'s House"
    assert after['casa']['deed_id'] == 17935 and after['casa']['custom_house_field'] == 42
    assert {k:v for k,v in after.items() if k!='casa'} == {k:v for k,v in before.items() if k!='casa'}
    assert s.personaje.casa == after['casa']
    casas._CASAS_ACTIVAS.clear()
    reloaded = casas.obtener_o_crear_casa(s.personaje.char_id,s.personaje.nombre,raw_data=after['casa'])
    assert reloaded.owner_id == s.personaje.char_id and reloaded.house_name == s.personaje.nombre+"'s House"


def test_first_equipped_deed_never_creates_an_owner_zero_record(world):
    s = world.player(items={376:10115});s.personaje.casa = {}
    app._sanear_escrituras(s.personaje,s.usuario,'test')
    assert stored(world,s)['casa']['owner_id'] == s.personaje.char_id
    assert stored(world,s)['casa']['owner_name'] == s.personaje.nombre


def test_actual_decorate_request_enters_legacy_owners_house(world,monkeypatch):
    s = world.player(items={376:17935});s.personaje.stage = 370
    s.personaje.casa = {'deed_id':17935,'owner_id':0,'owner_name':'','house_name':"'s House"}
    monkeypatch.setattr(__import__('presencia'),'salir',lambda *a,**kw:None)
    server = app.Servidor.__new__(app.Servidor);server.mundos = world.players
    server.manejar(s,0x136,None,None,'test',struct.pack('<I',17935))
    assert s.personaje.stage == 500 and s.house_furnish_pending
    assert s.casa_visitando.owner_id == s.personaje.char_id
    assert s.casa_visitando.house_name == s.personaje.nombre+"'s House"
    packet = next(p for p in s.packets if p[:2] == b'\x0c\0')
    assert struct.unpack_from('<I',packet,2)[0] == 500 and packet[28] == 4
    assert not any(b'Only the owner' in p for p in s.packets)


def test_actual_decorate_request_cannot_claim_another_owners_visited_house(world):
    owner,visitor = world.player(),world.player()
    c = casas.obtener_o_crear_casa(owner.personaje.char_id,owner.personaje.nombre)
    visitor.personaje.stage = 500;visitor.casa_visitando = c
    before = c.serializar()
    server = app.Servidor.__new__(app.Servidor);server.mundos = world.players
    server.manejar(visitor,0x136,None,None,'test',struct.pack('<I',c.deed_id))
    assert any(b'Only the owner' in p for p in visitor.packets)
    assert c.serializar() == before and not getattr(visitor,'house_furnishing',False)
