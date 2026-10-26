"""Native collection cells, level/color scoring and permanent stat thresholds."""
import copy
import sqlite3
import struct
import pytest
from test_competiciones import world,stored
import album,app,logros


def deposit(s,slot):
    app.Servidor.__new__(app.Servidor).manejar(s,0x16,None,None,'test',struct.pack('<BI',0x33,slot))


def test_collection_uses_native_level_squared_formula_and_color(world):
    assert album.descripcion(355)==(0,1,0,30)
    assert album.descripcion(69578)==(0,2,4,4495)
    assert album.valor_de(69578,{'extra':{'atk':1000}})>4495


def test_album_native_packet_and_consumption_are_persisted_without_losing_stack(world):
    s=world.player(items={20:355});s.cantidades[20]=2;world.save(s)
    deposit(s,20)
    assert s.inventario=={20:355} and s.cantidades[20]==1
    assert stored(world,s)['album']['arma']==30
    assert stored(world,s)['custom_field']=='preserve me'
    packet=next(p for p in s.packets if p[:2]==b'\x56\x01')
    assert len(packet)==26 and struct.unpack_from('<8H',packet,6)==(1,0,0,0,0,0,0,0)
    word=struct.unpack_from('<I',packet,22)[0]
    assert word>>30==1 and word&0x1ffff==30
    s.packets.clear()
    app.Servidor.__new__(app.Servidor).manejar(s,0x16,None,None,'test',b'\x32'+bytes(4))
    assert s.packets==[packet]


def test_four_native_grids_fill_then_weaker_equipment_is_not_consumed(world):
    s=world.player(items={20:20});s.cantidades[20]=5;world.save(s)
    for _ in range(4):deposit(s,20)
    assert s.cantidades[20]==1 and len(s.personaje.album['_entries'])==4
    before=copy.deepcopy(stored(world,s));deposit(s,20)
    assert stored(world,s)==before and s.cantidades[20]==1
    assert any(b'stronger equipment' in p for p in s.packets)


def test_album_threshold_stats_apply_immediately_and_from_saved_totals(world):
    s=world.player(items={20:69578})
    before=app._stats_ses(s)
    deposit(s,20)
    assert not s.inventario
    raw=album.bonos(s.personaje.album);buff=logros.con_reputacion({},s.personaje)['album']
    assert buff['atk']==raw['atk']>0 and buff['matk']==raw['matk']>0
    after=app._stats_ses(s)
    assert struct.unpack_from('<I',after,26)[0]-struct.unpack_from('<I',before,26)[0]==raw['atk']
    assert stored(world,s)['album']['arma']==4495


def test_album_sql_failure_cannot_destroy_equipment_or_add_collection_points(world):
    s=world.player(items={20:69578});before=copy.deepcopy(stored(world,s))
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_album BEFORE UPDATE ON personajes BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):deposit(s,20)
    assert stored(world,s)==before and s.inventario=={20:69578}
    assert not s.personaje.album


def test_appearance_uses_xml_theme_and_five_copies_without_consuming_sixth(world):
    assert album.descripcion(3400)==(7,0,3,7)
    assert album.descripcion(3596) is None  #7-day version
    s=world.player(items={20:3400});s.cantidades[20]=6;world.save(s)
    for _ in range(5):deposit(s,20)
    assert s.personaje.album['_entries']==[[7,0,3,0,35]]
    assert s.personaje.album['apariencia']==35 and s.cantidades[20]==1
    before=copy.deepcopy(stored(world,s));deposit(s,20)
    assert stored(world,s)==before and s.cantidades[20]==1
    packet=album.paquete(s.personaje)
    assert struct.unpack_from('<8H',packet,6)[-1]==1
    assert struct.unpack_from('<I',packet,22)[0]==(3<<20)|35


def test_album_does_not_consume_equipped_items(world):
    s=world.player(items={3:69578});deposit(s,3)
    assert s.inventario=={3:69578} and not s.personaje.album
