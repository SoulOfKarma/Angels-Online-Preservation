"""Native friends protocol0027..002A, consent and persistent mutual contacts.

REA:570890 invite popup,570f20 accepted friend,56fc40 list42-byte rows.
0122 belongs to the Game tab; it is not the friends list.
"""
import json
import struct
import time

_PENDIENTES={}
LIMIT=100


def _key(s):return s.usuario.casefold(),int(s.personaje.char_id)
def _str(s):return str(s or '').encode('ascii','replace')[:16].ljust(17,b'\0')
def _read(raw):return raw.split(b'\0',1)[0].decode('ascii','strict').strip()
def _online(s):
    return (getattr(s,'personaje',None) is not None
            and not getattr(s,'desconectado',False) and getattr(s,'conectado',True)
            and getattr(s,'rol','mundo')=='mundo')


def _schema(con):
    con.execute('CREATE TABLE IF NOT EXISTS social_friends('
                'owner TEXT,character INTEGER,target_owner TEXT,target INTEGER,grupo TEXT NOT NULL DEFAULT "",'
                'PRIMARY KEY(owner,character,target_owner,target))')


def _rows(con,s):
    _schema(con)
    return con.execute('SELECT f.target_owner,f.target,p.nombre,f.grupo FROM social_friends f '
        'JOIN personajes p ON lower(p.usuario)=f.target_owner AND p.char_id=f.target '
        'WHERE f.owner=? AND f.character=? ORDER BY p.nombre COLLATE NOCASE',_key(s)).fetchall()


def _list(s,rows):
    records=b''.join(struct.pack('<I',cid)+_str(name)+_str(group)+struct.pack('<I',0)
                     for _,cid,name,group in rows)
    return struct.pack('<HII',0x27,s.personaje.char_id,len(rows))+records


def _added(s,other):
    """84-byte body: self/status/id/server17/name17/status/profile25."""
    p=other.personaje
    body=bytearray(84)
    struct.pack_into('<IHI',body,0,s.personaje.char_id,0,p.char_id)
    body[10:27]=_str('Hestia');body[27:44]=_str(p.nombre)
    struct.pack_into('<I',body,44,0 if _online(other) else 10)
    return struct.pack('<H',0x2a)+body


def _status(s,cid,name,other=None):
    # 570000/0028 ALWAYS moves the contact to the online vector, regardless
    # of its displayed status.571AD0/002E moves it offline and fixes counters.
    if other is None or not _online(other):
        return struct.pack('<HII',0x2e,s.personaje.char_id,cid)
    #0028 updates an existing record. Flag1 suppresses the client's automatic
    #001A query, so a status reply cannot create a request/reply loop.
    body=bytearray(83)
    struct.pack_into('<IB',body,0,s.personaje.char_id,1)
    body[5:22]=_str('Hestia')
    struct.pack_into('<II',body,22,0,cid)
    if other is not None and _online(other):
        p=other.personaje
        struct.pack_into('<IIHB',body,30,int(p.stage),int(p.tile_x),int(p.tile_y),int(getattr(p,'genero',0))&1)
    body[66:83]=_str(name)
    return struct.pack('<H',0x28)+body


def sincronizar(s,sessions,notify=False,offline=False):
    import cuentas
    with cuentas._LOCK,cuentas._get_conn() as con:rows=_rows(con,s)
    live={_key(x):x for x in sessions if _online(x) and (x is not s or not offline)}
    if not offline:
        s.enviar(_list(s,rows))
        for owner,cid,name,_ in rows:s.enviar(_status(s,cid,name,live.get((owner,cid))))
    if notify:
        for owner,cid,_,_ in rows:
            other=live.get((owner,cid))
            if other:
                other.enviar(_status(other,s.personaje.char_id,s.personaje.nombre,None if offline else s))
    if offline:
        for key,(source,_,_,_) in list(_PENDIENTES.items()):
            if key==_key(s) or source is s:_PENDIENTES.pop(key,None)


def procesar(s,opcode,body,sessions):
    if opcode not in (0x19,0x1a,0x1b,0x1c,0x1e,0x1f,0x20,0x21):return False
    import clases,cuentas
    def notice(text):s.enviar(clases.aviso(text,tipo=0))
    if opcode==0x19:
        if len(body)!=21:return True
        try:name=_read(body[:17])
        except UnicodeDecodeError:return True
        target=next((x for x in sessions if _online(x) and x.personaje.nombre.casefold()==name.casefold()),None)
        if target is None or target is s:
            notice('That character is not online.');return True
        key=_key(target);old=_PENDIENTES.get(key)
        if old and old[1]>time.time():
            notice('That character already has a pending friend invitation.');return True
        with cuentas._LOCK,cuentas._get_conn() as con:
            own=_rows(con,s);theirs=_rows(con,target)
            if __import__('correo').bloqueado(con,s.personaje.nombre,_key(target)):
                notice('That character is not accepting your invitations.');return True
            if any((owner,cid)==key for owner,cid,_,_ in own):
                notice('That character is already your friend.');return True
            if len(own)>=LIMIT or len(theirs)>=LIMIT:
                notice('The friend list is full.');return True
        _PENDIENTES[key]=(s,time.time()+60,_key(s),target)
        target.enviar(struct.pack('<HIH',0x29,target.personaje.char_id,0)+_str(s.personaje.nombre))
        notice('Friend invitation sent to %s.'%target.personaje.nombre)
        return True
    if opcode==0x1c:
        pending=_PENDIENTES.pop(_key(s),None)
        if pending and _online(pending[0]):
            pending[0].enviar(clases.aviso('%s declined your friend invitation.'%s.personaje.nombre,tipo=0))
        return True
    if opcode==0x1b:
        if len(body)!=4:return True
        pending=_PENDIENTES.get(_key(s))
        if not pending:return True
        other,deadline,source_key,recipient=pending
        # The native reply carries a selected-contact ID which can be0;
        # authorization is the pending invitation addressed to this session.
        if recipient is not s or deadline<=time.time() or not _online(other) or _key(other)!=source_key:
            _PENDIENTES.pop(_key(s),None);return True
        with cuentas._LOCK,cuentas._get_conn() as con:
            con.execute('BEGIN IMMEDIATE');own=_rows(con,s);theirs=_rows(con,other)
            if __import__('correo').bloqueado(con,other.personaje.nombre,_key(s)):
                _PENDIENTES.pop(_key(s),None);return True
            if len(own)>=LIMIT or len(theirs)>=LIMIT:
                notice('The friend list is full.');return True
            for a,b in ((s,other),(other,s)):
                con.execute('INSERT OR IGNORE INTO social_friends(owner,character,target_owner,target) VALUES(?,?,?,?)',
                            (*_key(a),*_key(b)))
        _PENDIENTES.pop(_key(s),None);cuentas._notificar_cambio(inmediato=True)
        s.enviar(_added(s,other));other.enviar(_added(other,s))
        return True
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE');rows=_rows(con,s)
        if opcode==0x1a:
            if len(body)==8:
                cid=struct.unpack_from('<I',body)[0]
                row=next((r for r in rows if r[1]==cid),None)
                if row:
                    live=next((x for x in sessions if _online(x) and _key(x)==tuple(row[:2])),None)
                    s.enviar(_status(s,cid,row[2],live))
            return True
        if opcode==0x1e:
            if len(body)!=4:return True
            cid=struct.unpack('<I',body)[0]
            con.execute('DELETE FROM social_friends WHERE owner=? AND character=? AND target=?',(*_key(s),cid))
        elif opcode==0x20 and len(body)==21:
            try:group=_read(body[4:])
            except UnicodeDecodeError:return True
            con.execute('UPDATE social_friends SET grupo=? WHERE owner=? AND character=? AND target=?',
                        (group,*_key(s),struct.unpack_from('<I',body)[0]))
        elif opcode==0x1f and len(body)==34:
            try:old,new=_read(body[:17]),_read(body[17:])
            except UnicodeDecodeError:return True
            con.execute('UPDATE social_friends SET grupo=? WHERE owner=? AND character=? AND grupo=?',(new,*_key(s),old))
        elif opcode==0x21 and len(body)==17:
            try:group=_read(body)
            except UnicodeDecodeError:return True
            con.execute('UPDATE social_friends SET grupo="" WHERE owner=? AND character=? AND grupo=?',(*_key(s),group))
        else:return True
    cuentas._notificar_cambio(inmediato=True);sincronizar(s,sessions)
    return True
