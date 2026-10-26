"""Native text mail100..103/3B..3F; mailbox ownership never comes from C2S.

Layouts:5a6f10 sender,5a7200/7290/7310 queries,5a24c0/25a0 receivers.
This client's mail has text and CC fields; inventory is not part of it.
"""
import hashlib
import struct
import time


def _key(s):return s.usuario.casefold(),int(s.personaje.char_id)
def _str(text,size=17):return str(text).encode('latin-1','replace')[:size-1].ljust(size,b'\0')


def _schema(con):
    con.execute('CREATE TABLE IF NOT EXISTS social_mail('
        'id INTEGER PRIMARY KEY AUTOINCREMENT,owner TEXT,character INTEGER,sender TEXT,'
        'sender_character INTEGER,sender_name TEXT,subject TEXT,body TEXT,created INTEGER,read INTEGER DEFAULT 0)')
    con.execute('CREATE TABLE IF NOT EXISTS social_mail_batches('
        'owner TEXT,character INTEGER,digest TEXT,created REAL,PRIMARY KEY(owner,character,digest))')
    con.execute('CREATE TABLE IF NOT EXISTS social_filters('
        'owner TEXT,character INTEGER,name TEXT,blocked INTEGER,PRIMARY KEY(owner,character,name))')


def bloqueado(con,sender_name,recipient):
    _schema(con)
    return bool(con.execute('SELECT 1 FROM social_filters WHERE owner=? AND character=? AND name=? AND blocked=1',
                           (*recipient,sender_name.casefold())).fetchone())


def _ack(s,status=0,name=''):
    return struct.pack('<HIHH',0x3b,s.personaje.char_id,status,0)+_str(name)


def _inbox(s,con):
    rows=con.execute('SELECT id,sender_name,subject,created,read FROM social_mail '
                    'WHERE owner=? AND character=? ORDER BY id DESC LIMIT 90',_key(s)).fetchall()
    data=[]
    for ident,sender,subject,created,read in rows:
        record=bytearray(64)
        struct.pack_into('<I',record,0,ident);record[4:21]=_str(sender);record[21:54]=_str(subject,33)
        struct.pack_into('<II',record,54,int(created),int(read));data.append(bytes(record))
    return struct.pack('<HII',0x3c,s.personaje.char_id,len(data))+b''.join(data)


def notificar(s):
    import cuentas
    with cuentas._LOCK,cuentas._get_conn() as con:
        _schema(con)
        unread=con.execute('SELECT COUNT(*) FROM social_mail WHERE owner=? AND character=? AND read=0',_key(s)).fetchone()[0]
        trusted=[r[0] for r in con.execute('SELECT name FROM social_filters WHERE owner=? AND character=? AND blocked=0 ORDER BY name',_key(s)).fetchall()]
    s.enviar(struct.pack('<HII',0x3f,s.personaje.char_id,unread))
    #5a3250 reads a count followed by NUL-terminated trusted names.
    s.enviar(struct.pack('<HII',0x40,s.personaje.char_id,len(trusted))+
             b''.join(name.encode('latin-1','replace')+b'\0' for name in trusted))


def loaded(s):
    notificar(s)
    if getattr(s,'_mail_open',False):
        import cuentas
        with cuentas._LOCK,cuentas._get_conn() as con:
            _schema(con);s.enviar(_inbox(s,con))


def procesar(s,opcode,body,sessions):
    if opcode not in (0x100,0x101,0x102,0x103,0x106,0x107):return False
    import cuentas,clases
    if getattr(s,'desconectado',False):return True
    if opcode==0x100:
        if not 90<=len(body)<=3000:return True
        recipient=body[4:21].split(b'\0',1)[0].decode('latin-1')
        cc_count=struct.unpack_from('<I',body,21)[0]
        if not recipient or cc_count>50:return True
        end=body.find(b'\0',89)
        if end<0 or end-89>2047:return True
        text=body[89:end].decode('latin-1');subject=body[46:79].split(b'\0',1)[0].decode('latin-1')
        cc=body[end+1:].split(b'\0')
        if cc and cc[-1]==b'':cc.pop()
        if len(cc)!=cc_count or any(not n or len(n)>16 for n in cc):return True
        names=list(dict.fromkeys([recipient]+[n.decode('latin-1') for n in cc]))
        now=time.time();digest=hashlib.sha256(body[4:]).hexdigest()
        deliveries=[];duplicate=False
        with cuentas._LOCK,cuentas._get_conn() as con:
            con.execute('BEGIN IMMEDIATE');_schema(con)
            previous=con.execute('SELECT created FROM social_mail_batches WHERE owner=? AND character=? AND digest=?',(*_key(s),digest)).fetchone()
            duplicate=bool(previous and previous[0]>now-2)
            if not duplicate:
                for name in names:
                    rows=con.execute('SELECT usuario,char_id FROM personajes WHERE nombre=? COLLATE NOCASE',(name,)).fetchall()
                    if len(rows)!=1:s.enviar(_ack(s,1,name));return True
                    target=(rows[0][0].casefold(),int(rows[0][1]))
                    if bloqueado(con,s.personaje.nombre,target):s.enviar(_ack(s,2,name));return True
                    count=con.execute('SELECT COUNT(*) FROM social_mail WHERE owner=? AND character=?',target).fetchone()[0]
                    if count>=90:s.enviar(_ack(s,3,name));return True
                    if target not in deliveries:deliveries.append(target)
                for target in deliveries:
                    con.execute('INSERT INTO social_mail(owner,character,sender,sender_character,sender_name,subject,body,created) '
                        'VALUES(?,?,?,?,?,?,?,?)',(*target,*_key(s),s.personaje.nombre,subject,text,int(now)))
                con.execute('INSERT OR REPLACE INTO social_mail_batches VALUES(?,?,?,?)',(*_key(s),digest,now))
        if not duplicate:cuentas._notificar_cambio(inmediato=True)
        s.enviar(_ack(s))
        for recipient_session in sessions:
            if (getattr(recipient_session,'personaje',None) and not getattr(recipient_session,'desconectado',False)
                    and _key(recipient_session) in deliveries):notificar(recipient_session)
        return True
    changed=False;packets=[]
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE');_schema(con)
        if opcode==0x101:
            if len(body)!=21:return True
            s._mail_open=True
            packets.append(_inbox(s,con))
        elif opcode in (0x102,0x103):
            if len(body)!=25:return True
            ident=struct.unpack_from('<I',body,21)[0]
            row=con.execute('SELECT body FROM social_mail WHERE owner=? AND character=? AND id=?',(*_key(s),ident)).fetchone()
            if opcode==0x102:
                header=bytearray(70)
                struct.pack_into('<IHI',header,0,s.personaje.char_id,0 if row else 1,ident)
                packets.append(struct.pack('<H',0x3d)+header+((row[0].encode('latin-1','replace')+b'\0') if row else b'\0'))
                if row:
                    changed=bool(con.execute('UPDATE social_mail SET read=1 WHERE owner=? AND character=? AND id=? AND read=0',(*_key(s),ident)).rowcount)
            else:
                changed=bool(con.execute('DELETE FROM social_mail WHERE owner=? AND character=? AND id=?',(*_key(s),ident)).rowcount)
                packets.append(struct.pack('<HIIH',0x3e,s.personaje.char_id,ident,0 if changed else 1))
        else:
            if len(body)!=38:return True
            name=body[21:38].split(b'\0',1)[0].decode('latin-1').strip()
            if not name:return True
            con.execute('INSERT OR REPLACE INTO social_filters VALUES(?,?,?,?)',(*_key(s),name.casefold(),int(opcode==0x106)))
            changed=True
    if changed:cuentas._notificar_cambio(inmediato=True)
    s.enviar(*packets)
    return True
