"""Native room UI lifecycle and sender authority, using real router."""
import struct
import pytest
from test_competiciones import world
import app
import chatrooms as rooms


@pytest.fixture(autouse=True)
def clean_rooms(monkeypatch):
    monkeypatch.setattr(rooms, '_ROOMS', {})


def request(srv, s, op, body): srv.manejar(s, op, None, None, 'test', body)
def setup(world):
    a, b, c = world.player(), world.player(), world.player()
    srv = app.Servidor.__new__(app.Servidor); srv.mundos = world.players
    return srv, a, b, c
def create(srv, s, kind=6, target=0):
    request(srv, s, 0x120, struct.pack('<IBI33sI', 0, kind, 0, b'Test room', target))
    return next(reversed(rooms._ROOMS.values()))
def join(srv, s, room, target=None):
    request(srv, s, 0x124, struct.pack('<II', (target or s).personaje.char_id, room.ident))
def say(srv, s, room, text=b'Hello'):
    request(srv, s, 0x126, struct.pack('<IBI', 0, room.kind, room.ident) + text + b'\0')


@pytest.mark.parametrize('kind',[6,8])
def test_map_change_restores_room_only_for_moving_member(world,kind):
    srv,a,b,c=setup(world)
    room=create(srv,a,kind,b.personaje.char_id if kind==8 else 0)
    if kind==6:join(srv,b,room)
    say(srv,b,room,b'Before travel')
    a.packets.clear();b.packets.clear()
    a.mapa_cargando=True
    request(srv,a,0x125,struct.pack('<II',a.personaje.char_id,room.ident))
    assert rooms._key(a) in room.members
    a.personaje.stage=41;a.mapa_cargando=False;rooms.loaded(a)
    assert any(p[:2]==b'\x23\x01' and struct.unpack_from('<H',p,11)[0]==1 for p in a.packets)
    assert any(p.endswith(b'Before travel\0') for p in a.packets)
    assert not b.packets and rooms._key(a) in room.members
    say(srv,a,room,b'After travel')
    assert b.packets[-1].endswith(b'After travel\0')


def test_room_native_create_list_join_and_chat_never_goes_public(world):
    srv, a, b, c = setup(world)
    room = create(srv, a)
    assert a.packets[0][:2] == b'\x24\x01'
    assert a.packets[0][13] == 16  # shard, not channel2
    assert len(a.packets[0]) == 38
    request(srv, b, 0x122, bytes(4) + b'\6')
    packet = b.packets[-1]
    assert packet[:2] == b'\x22\x01' and len(packet) == 66
    assert struct.unpack_from('<HHI', packet, 9) == (1, 50, room.ident)
    join(srv, b, room)
    roster = next(p for p in b.packets if p[:2] == b'\x23\x01')
    assert struct.unpack_from('<H', roster, 11)[0] == 1 and len(roster) == 38
    a.packets.clear(); b.packets.clear(); c.packets.clear()
    say(srv, b, room)
    assert a.packets == b.packets and len(a.packets) == 1 and not c.packets
    assert a.packets[0][:2] == b'\x26\x01' and a.packets[0][6] == 6
    assert a.packets[0][28:] == b'Hello\0'
    say(srv, c, room)
    assert not c.packets and len(a.packets) == 1


def test_room_only_master_can_kick_or_transfer_and_departure_elects_next(world):
    srv, a, b, c = setup(world)
    room = create(srv, a); join(srv, b, room); join(srv, c, room)
    request(srv, b, 0x125, struct.pack('<II', a.personaje.char_id, room.ident))
    assert room.master == rooms._key(a) and len(room.members) == 3
    body = bytes(5) + struct.pack('<II', room.ident, c.personaje.char_id)
    request(srv, b, 0x129, body); assert room.master == rooms._key(a)
    request(srv, a, 0x129, body); assert room.master == rooms._key(c)
    request(srv, c, 0x125, struct.pack('<II', a.personaje.char_id, room.ident))
    assert rooms._key(a) not in room.members
    rooms.desconectar(c); assert room.master == rooms._key(b)
    rooms.desconectar(b); assert room.ident not in rooms._ROOMS


def test_private_conversations_limit_invites_and_respect_blocks(world):
    srv, a, b, c = setup(world)
    room = create(srv, a, 8, b.personaje.char_id)
    assert set(room.members) == {rooms._key(a), rooms._key(b)}
    join(srv, c, room); assert rooms._key(c) not in room.members
    join(srv, b, room, c); assert rooms._key(c) not in room.members
    request(srv, c, 0x106, bytes(21) + a.personaje.nombre.encode().ljust(17, b'\0'))
    join(srv, a, room, c); assert rooms._key(c) not in room.members
    a.packets.clear(); b.packets.clear(); c.packets.clear()
    say(srv, a, room)
    assert a.packets == b.packets and not c.packets and a.packets[0][6] == 8


def test_session_character_change_cannot_keep_old_membership(world):
    srv, a, b, c = setup(world)
    room = create(srv, a); join(srv, b, room)
    a.personaje = c.personaje
    b.packets.clear(); say(srv, a, room, b'Forged')
    assert rooms._key(a) not in room.members
    assert not any(b'Forged' in p for p in b.packets)
