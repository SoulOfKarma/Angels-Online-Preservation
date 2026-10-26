"""Native public chatrooms and private group conversations.

REA: create6184e0/619200 sends120, join618ab0 sends124,
leave619650 sends125, list618dc0 sends122, master619790 sends129.
Receivers5f24e0..5f2c30 and5729e0 use variable member records.
Rooms last for the connected conversation, never across server restarts.
"""
import itertools
import struct
import time
from dataclasses import dataclass, field

_ROOMS = {}
_IDS = itertools.count(1)
# server.xml: Hestia id16. The client compares this byte to958e98 before
# opening its own room; channel/subset2 is a different field.
SERVER_ID = 16


def _key(s): return s.usuario.casefold(), int(s.personaje.char_id)
def _live(s): return getattr(s, 'personaje', None) is not None and not getattr(s, 'desconectado', False)
def _text(s, n=17): return str(s).encode('latin-1', 'replace')[:n-1].ljust(n, b'\0')
def _notice(s, text):
    import clases
    s.enviar(clases.aviso(text, tipo=0))


@dataclass
class Room:
    ident: int
    kind: int
    title: str
    master: tuple
    members: dict = field(default_factory=dict)
    identities: dict = field(default_factory=dict)
    last_message: dict = field(default_factory=dict)
    history: list = field(default_factory=list)

    @property
    def capacity(self): return 50 if self.kind == 6 else 12


def _member(s, person=None):
    p = s.personaje if person is None else person
    return struct.pack('<B17sIHB', SERVER_ID, _text(p.nombre), p.char_id, 1,
                       int(getattr(p, 'genero', 0)) & 1)


def _join_packet(room, s):
    return struct.pack('<HIHBI', 0x124, s.personaje.char_id, 0, room.kind, room.ident) + _member(s)


def _roster(room, s, members):
    return struct.pack('<HIBIH', 0x123, s.personaje.char_id, room.kind,
                       room.ident, len(members)) + b''.join(_member(m) for m in members)


def _master(room):
    master = room.members[room.master]
    packet = struct.pack('<HIBI17s', 0x129, master.personaje.char_id,
                         room.kind, room.ident, _text(master.personaje.nombre))
    for s in list(room.members.values()): s.enviar(packet)


def _blocked(source, target):
    import correo, cuentas
    with cuentas._LOCK, cuentas._get_conn() as con:
        return correo.bloqueado(con, source.personaje.nombre, _key(target))


def _list(s):
    records = []
    for room in _ROOMS.values():
        if room.kind != 6: continue
        master = room.members.get(room.master)
        if master is None: continue
        records.append(struct.pack('<HHI32s17s', len(room.members), room.capacity,
                       room.ident, _text(room.title, 32), _text(master.personaje.nombre)))
    s.enviar(struct.pack('<HIBH', 0x122, s.personaje.char_id, 6, len(records)) + b''.join(records))


def _add(room, target):
    key = _key(target)
    if key in room.members: return
    previous = list(room.members.values())
    room.members[key] = target
    room.identities[key] = target.personaje
    packet = _join_packet(room, target)
    target.enviar(packet)
    if room.kind == 6:
        target.enviar(struct.pack('<HIHBI33s', 0x120, target.personaje.char_id,
                      0, room.kind, room.ident, _text(room.title, 33)))
    target.enviar(_roster(room, target, previous))
    for other in previous: other.enviar(packet)
    if room.kind == 6: _master(room)


def _remove(room, key):
    s = room.members.pop(key, None)
    if s is None: return
    original = room.identities.pop(key, s.personaje)
    room.last_message.pop(key, None)
    packet = struct.pack('<HIHBI', 0x125, original.char_id, 0,
                         room.kind, room.ident) + _member(s, original)
    if _live(s) and s.personaje is original: s.enviar(packet)
    for other in list(room.members.values()): other.enviar(packet)
    if not room.members:
        _ROOMS.pop(room.ident, None)
    elif room.master == key:
        room.master = next(iter(room.members))
        if room.kind == 6: _master(room)


def desconectar(s):
    for room in list(_ROOMS.values()):
        for key, member in list(room.members.items()):
            if member is s: _remove(room, key)


def _prune():
    for room in list(_ROOMS.values()):
        for key, s in list(room.members.items()):
            if not _live(s) or room.identities[key] is not s.personaje or _key(s) != key:
                _remove(room, key)


def loaded(s):
    _prune()
    key=_key(s)
    for room in _ROOMS.values():
        if room.members.get(key) is not s:continue
        s.enviar(_join_packet(room,s))
        if room.kind==6:
            s.enviar(struct.pack('<HIHBI33s',0x120,s.personaje.char_id,0,room.kind,room.ident,_text(room.title,33)))
        s.enviar(_roster(room,s,[member for member in room.members.values() if member is not s]))
        master=room.members[room.master]
        if room.kind==6:s.enviar(struct.pack('<HIBI17s',0x129,master.personaje.char_id,room.kind,room.ident,_text(master.personaje.nombre)))
        for recipients,packet in room.history:
            if key in recipients:s.enviar(packet)


def procesar(s, opcode, body, sessions):
    is_chat = opcode == 0x126 and len(body) >= 10 and body[4] in (6, 8)
    if opcode not in (0x120, 0x122, 0x124, 0x125, 0x129) and not is_chat: return False
    if not _live(s): return True
    if opcode==0x125 and getattr(s,'mapa_cargando',False):return True
    _prune()
    key = _key(s)
    if opcode == 0x122:
        if len(body) == 5 and body[4] == 6: _list(s)
        return True
    if opcode == 0x120:
        if len(body) != 46 or body[4] not in (6, 8): return True
        kind = body[4]
        title = body[9:42].split(b'\0', 1)[0].decode('latin-1').strip()
        target_id = struct.unpack_from('<I', body, 42)[0]
        if len([r for r in _ROOMS.values() if key in r.members]) >= 10:
            _notice(s, 'You already have too many conversations open.'); return True
        if kind == 6:
            if not title or any(ord(c) < 32 for c in title): return True
            if any(r.kind == 6 and key in r.members for r in _ROOMS.values()):
                _notice(s, 'Leave your current chatroom first.'); return True
            targets = []
        else:
            target = next((p for p in sessions if _live(p) and p is not s
                           and p.personaje.char_id == target_id), None)
            if target is None or _blocked(s, target):
                _notice(s, 'That character cannot join this conversation.'); return True
            if any(r.kind == 8 and set(r.members) == {key, _key(target)} for r in _ROOMS.values()): return True
            targets = [target]
        room = Room(next(_IDS), kind, title, key)
        _ROOMS[room.ident] = room
        _add(room, s)
        for target in targets: _add(room, target)
        return True
    if opcode in (0x124, 0x125):
        if len(body) != 8: return True
        target_id, ident = struct.unpack('<II', body)
        room = _ROOMS.get(ident)
        if room is None: return True
        target = next((p for p in sessions if _live(p) and p.personaje.char_id == target_id), None)
        if target is None: return True
        tkey = _key(target)
        if opcode == 0x125:
            if target is not s and (room.master != key or key not in room.members): return True
            if key not in room.members: return True
            _remove(room, tkey)
        else:
            if tkey in room.members: return True
            if target is not s and (room.kind != 8 or room.master != key): return True
            if room.kind == 8 and key not in room.members: return True
            if room.kind == 6 and any(r.kind == 6 and tkey in r.members for r in _ROOMS.values()): return True
            if len(room.members) >= room.capacity or sum(tkey in r.members for r in _ROOMS.values()) >= 10: return True
            if any(_blocked(member, target) or _blocked(target, member) for member in room.members.values()):
                _notice(s, 'That character cannot join this conversation.'); return True
            _add(room, target)
        return True
    if opcode == 0x129:
        if len(body) != 13: return True
        ident, target_id = struct.unpack_from('<II', body, 5)
        room = _ROOMS.get(ident)
        if room is None or room.kind != 6 or room.master != key: return True
        target_key = next((k for k, p in room.members.items() if p.personaje.char_id == target_id), None)
        if target_key is not None:
            room.master = target_key
            _master(room)
        return True
    ident = struct.unpack_from('<I', body, 5)[0]
    room = _ROOMS.get(ident)
    if room is None or room.kind != body[4] or room.members.get(key) is not s: return True
    raw = body[9:]
    if not 1 <= len(raw) <= 301 or raw[-1] != 0 or b'\0' in raw[:-1]: return True
    text = raw[:-1].decode('latin-1').strip()
    if not text: return True
    now = time.monotonic()
    if now - room.last_message.get(key, -1e10) < .2: return True
    room.last_message[key] = now
    packet = struct.pack('<HIBI17s', 0x126, s.personaje.char_id, room.kind,
                         room.ident, _text(s.personaje.nombre)) + text.encode('latin-1') + b'\0'
    recipients=set()
    for target in list(room.members.values()):
        if target is s or not _blocked(s, target):
            target.enviar(packet);recipients.add(_key(target))
    room.history.append((recipients,packet))
    del room.history[:-200]
    return True
