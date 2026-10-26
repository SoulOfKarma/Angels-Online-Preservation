"""Native text/CC mail, owner scoped reads and deletes, block/trust changes."""
import sqlite3
import struct
import pytest
from test_competiciones import world
import app,correo


def request(srv,s,op,body):srv.manejar(s,op,None,None,'test',body)


def send(srv,s,name,subject='Hello',text='A message',cc=()):
    body=bytearray(89)
    body[4:21]=name.encode().ljust(17,b'\0')
    struct.pack_into('<I',body,21,len(cc));body[46:79]=subject.encode().ljust(33,b'\0')
    request(srv,s,0x100,bytes(body)+text.encode()+b'\0'+b''.join(n.encode()+b'\0' for n in cc))


def control(ident):return bytes(21)+struct.pack('<I',ident)


def setup(world):
    a,b,c=world.player(),world.player(),world.player()
    srv=app.Servidor.__new__(app.Servidor);srv.mundos=world.players
    return srv,a,b,c


def test_open_mailbox_restored_after_map_change_without_resetting_mail(world):
    srv,a,b,c=setup(world);send(srv,a,b.personaje.nombre)
    request(srv,b,0x101,bytes(21));before=b.packets[-1]
    b.packets.clear();b.personaje.stage=41
    __import__('social_state').loaded(b,world.players)
    assert before in b.packets
    request(srv,b,0x101,bytes(21));assert b.packets[-1]==before


def test_native_mail_send_offline_inbox_read_and_owner_delete(world):
    srv,a,b,c=setup(world);b.desconectado=True
    send(srv,a,b.personaje.nombre)
    assert any(p[:2]==b'\x3b\0' and p[6:8]==bytes(2) for p in a.packets)
    request(srv,b,0x101,bytes(21));assert not b.packets
    b.desconectado=False;request(srv,b,0x101,bytes(21))
    packet=b.packets[-1];assert packet[:2]==b'\x3c\0' and len(packet)==74
    ident=struct.unpack_from('<I',packet,10)[0]
    assert packet[14:31].rstrip(b'\0')==a.personaje.nombre.encode()
    request(srv,c,0x102,control(ident))
    assert c.packets[-1][6:8]==b'\x01\0' and b'A message' not in c.packets[-1]
    request(srv,c,0x103,control(ident))
    assert c.packets[-1][-2:]==b'\x01\0'
    request(srv,b,0x102,control(ident));detail=b.packets[-1]
    assert detail[:2]==b'\x3d\0' and detail[72:]==b'A message\0'
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT read FROM social_mail WHERE id=?',(ident,)).fetchone()[0]==1
    request(srv,b,0x103,control(ident))
    assert b.packets[-1][-2:]==bytes(2)
    with sqlite3.connect(world.db) as con:assert con.execute('SELECT COUNT(*) FROM social_mail').fetchone()[0]==0


def test_mail_cc_is_atomic_deduplicated_and_notifies_each_online_recipient(world):
    srv,a,b,c=setup(world)
    send(srv,a,b.personaje.nombre,cc=(c.personaje.nombre,))
    send(srv,a,b.personaje.nombre,cc=(c.personaje.nombre,))
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT COUNT(*) FROM social_mail').fetchone()[0]==2
    assert any(p[:2]==b'\x3f\0' for p in b.packets)
    assert any(p[:2]==b'\x3f\0' for p in c.packets)
    send(srv,a,b.personaje.nombre,subject='Unknown CC',cc=('Nobody',))
    with sqlite3.connect(world.db) as con:assert con.execute('SELECT COUNT(*) FROM social_mail').fetchone()[0]==2


def test_native_block_and_unblock_persist_and_filter_mail(world):
    srv,a,b,c=setup(world)
    body=bytes(21)+a.personaje.nombre.encode().ljust(17,b'\0')
    request(srv,b,0x106,body);send(srv,a,b.personaje.nombre)
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT COUNT(*) FROM social_mail').fetchone()[0]==0
        assert correo.bloqueado(con,a.personaje.nombre,correo._key(b))
    request(srv,b,0x107,body);send(srv,a,b.personaje.nombre)
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT COUNT(*) FROM social_mail').fetchone()[0]==1


def test_mail_database_failure_rolls_back_all_cc_deliveries_and_no_success(world):
    srv,a,b,c=setup(world)
    correo.notificar(a);a.packets.clear()
    with sqlite3.connect(world.db) as con:
        con.execute("CREATE TRIGGER fail_mail BEFORE INSERT ON social_mail WHEN NEW.owner='u3' BEGIN SELECT RAISE(ABORT,'test'); END")
    with pytest.raises(sqlite3.IntegrityError):send(srv,a,b.personaje.nombre,cc=(c.personaje.nombre,))
    with sqlite3.connect(world.db) as con:
        assert con.execute('SELECT COUNT(*) FROM social_mail').fetchone()[0]==0
    assert not a.packets and not b.packets and not c.packets
