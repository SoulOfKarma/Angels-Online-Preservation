"""Native Item Mall, with local account-wide Angel Gold and atomic deliveries.

REA: c2s012D requests mall data, NOT radar. s2c005F is catalog(count+57-byte
rows),0061 is the gift list and0062 the Angel Gold balance. No paid balance,
gift stock or current promotions can be inferred from a YouTube screenshot.
Karma authorized the original catalog and a ONE-TIME1,000,000 AG per account.
"""
import datetime as dt
import functools
import json
import pathlib
import struct
import time
import uuid
import sqlite3


@functools.lru_cache(maxsize=1)
def datos():
    return json.loads((pathlib.Path(__file__).parent/'plantillas/item_mall.json').read_text('utf8'))


def _timestamp(value):
    if not value:return None
    try:return dt.datetime.strptime(value,'%y%m%d%H%M').timestamp()
    except (ValueError,OverflowError):return None


def _top_sales(rows,now):
    config=datos().get('top_sale')
    if not config:return rows
    import cuentas
    by_id={r['id']:r['item'] for r in datos()['rows']}
    totals={}
    # Ranking must never initialize wallets, create a database, or write a
    # schema merely because the client requests its catalog.
    try:
        con=sqlite3.connect(cuentas.DB_PATH.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)
        try:
            purchases=con.execute("SELECT referencia,COUNT(*) FROM item_mall_movimientos "
                                  "WHERE motivo='purchase' AND fecha>=? GROUP BY referencia",
                                  (now-int(config['days'])*86400,)).fetchall()
        finally:con.close()
        for product,count in purchases:
            item=by_id.get(product)
            if item:totals[item]=totals.get(item,0)+count
    except sqlite3.OperationalError:
        pass  # No local history yet: use the recent featured ordering.
    top=sorted((r for r in rows if r['category']==22),
               key=lambda r:(-totals.get(r['item'],0),r['sort'],r['id']))[:int(config['limit'])]
    top=[dict(r,sort=i) for i,r in enumerate(top)]
    return [r for r in rows if r['category']!=22]+top


def disponibles(now=None):
    now=time.time() if now is None else now
    rows=[r for r in datos()['rows']
            if (not r['start'] or (_timestamp(r['start']) is not None and _timestamp(r['start'])<=now))
            and (not r['end'] or (_timestamp(r['end']) is not None and now<_timestamp(r['end'])))]
    return _top_sales(rows,now)


def catalogo(now=None):
    rows=disponibles(now)
    records=[]
    for r in rows:
        records.append(struct.pack('<9I11siIH',r['id'],r['item'],r['flags'],r['sort'],r['category'],
                                   r['quantity'],r['price'],r['special_price'],r['duration'],
                                   r['end'].encode('ascii').ljust(11,b'\0'),r['limit'],r['gift'],r['gift_quantity']))
    return struct.pack('<HI',0x005F,len(rows))+b''.join(records)


def _schema(con):
    con.execute('CREATE TABLE IF NOT EXISTS item_mall_wallet '
                '(usuario TEXT PRIMARY KEY COLLATE NOCASE,ag INTEGER NOT NULL CHECK(ag>=0))')
    con.execute('CREATE TABLE IF NOT EXISTS item_mall_movimientos '
                '(id TEXT PRIMARY KEY,usuario TEXT,delta INTEGER,motivo TEXT,referencia INTEGER,fecha REAL)')
    con.execute('CREATE TABLE IF NOT EXISTS item_mall_cabinet '
                '(id INTEGER PRIMARY KEY AUTOINCREMENT,usuario TEXT COLLATE NOCASE,producto INTEGER,item INTEGER,'
                'cantidad INTEGER,precio INTEGER,remitente TEXT,duracion INTEGER,fin REAL,creado REAL)')
    con.execute("CREATE TRIGGER IF NOT EXISTS item_mall_initial_audit AFTER INSERT ON item_mall_wallet BEGIN "
                "INSERT OR IGNORE INTO item_mall_movimientos VALUES('initial:'||lower(NEW.usuario),NEW.usuario,NEW.ag,'initial',NULL,strftime('%s','now')); END")
    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cuentas'").fetchone():
        grant=int(datos()['initial_angel_gold'])
        con.execute('CREATE TRIGGER IF NOT EXISTS item_mall_new_account AFTER INSERT ON cuentas BEGIN '
                    'INSERT OR IGNORE INTO item_mall_wallet VALUES(NEW.usuario,%d); END' % grant)


def inicializar_cuentas(con):
    """Idempotent backfill; INSERT OR IGNORE never resets an existing balance."""
    _schema(con)
    before=con.execute('SELECT COUNT(*) FROM item_mall_wallet').fetchone()[0]
    con.execute('INSERT OR IGNORE INTO item_mall_wallet '
                'SELECT usuario,? FROM cuentas',(int(datos()['initial_angel_gold']),))
    return con.execute('SELECT COUNT(*) FROM item_mall_wallet').fetchone()[0]-before


def caducados(ses,now=None):
    import arena_premios_compat
    arena_premios_compat.caducados(ses,now,campo_fin='mall_fin',campo_item='mall_item')


def _wallet(con,user):
    con.execute('INSERT OR IGNORE INTO item_mall_wallet VALUES(?,?)',
                (user,int(datos()['initial_angel_gold'])))
    return int(con.execute('SELECT ag FROM item_mall_wallet WHERE usuario=?',(user,)).fetchone()[0])


def saldo(user):
    import cuentas
    with cuentas._LOCK,cuentas._get_conn() as con:
        _schema(con)
        return _wallet(con,user)


def almacen(user):
    import cuentas
    with cuentas._get_conn() as con:
        _schema(con)
        con.execute('DELETE FROM item_mall_cabinet WHERE usuario=? AND fin IS NOT NULL AND fin<=?',(user,time.time()))
        rows=con.execute('SELECT id,item,cantidad,precio,remitente FROM item_mall_cabinet '
                         'WHERE usuario=? ORDER BY id LIMIT 10',(user,)).fetchall()
    #0061: U8 count, records[id,item,U16 quantity,price,sender17,msglen,msg,NUL].
    records=[struct.pack('<IIHI17sBB',ident,item,qty,price,
                         (sender or '').encode('latin1','replace')[:16].ljust(17,b'\0'),0,0)
             for ident,item,qty,price,sender in rows]
    return struct.pack('<HB',0x0061,len(records))+b''.join(records)


class Rechazo(ValueError):pass


def es_temporal(ses,slot):
    meta=(getattr(ses.personaje,'mejoras',{}) or {}).get(slot,{})
    return bool(meta.get('mall_fin') and meta.get('mall_item')==ses.inventario.get(slot))


@functools.lru_cache(maxsize=None)
def _duracion_item(item):
    from house_services import xml_rows
    for table in ['item.xml']+['item%d.xml'%i for i in range(2,10)]:
        row=xml_rows(table).get(item)
        if row:return int(row.get('\u6301\u7e8c\u6642\u9593') or 0)
    return 0


def comprar(ses,product,receiver=None):
    import cuentas
    row=next((r for r in disponibles() if r['id']==product),None)
    if not datos()['purchases_enabled']:raise Rechazo('Item Mall purchases are disabled.')
    if not row:raise Rechazo('This Item Mall product is unavailable.')
    if row['flags']&0x20:raise Rechazo('The bonus-item data for this product is not configured. No AG was charged.')
    if receiver and row['flags']&0x200:raise Rechazo('This product cannot be gifted.')
    price=int(row['special_price'] or row['price'])
    if price<=0 or not 1<=row['quantity']<=65535:raise Rechazo('Invalid Item Mall price or quantity.')
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE');_schema(con)
        target=ses.usuario
        if receiver:
            owners=con.execute('SELECT usuario FROM personajes WHERE nombre=? COLLATE NOCASE',(receiver,)).fetchall()
            if len(owners)!=1:raise Rechazo('Gift recipient not found or ambiguous.')
            target=owners[0][0]
        if con.execute('SELECT COUNT(*) FROM item_mall_cabinet WHERE usuario=?',(target,)).fetchone()[0]>=10:
            raise Rechazo('The recipient Store Cabinet is full. No AG was charged.')
        if row['flags']&0x100 and con.execute('SELECT 1 FROM item_mall_movimientos WHERE usuario=? COLLATE NOCASE '
                                            "AND motivo='purchase' AND referencia=?",(ses.usuario,product)).fetchone():
            raise Rechazo('This product is limited to one purchase per account.')
        balance=_wallet(con,ses.usuario)
        if balance<price:raise Rechazo('Not enough Angel Gold.')
        duration=int(row['duration'] or _duracion_item(row['item']))
        deadline=time.time()+duration*60 if duration and row['flags']&8 else None
        con.execute('UPDATE item_mall_wallet SET ag=ag-? WHERE usuario=?',(price,ses.usuario))
        con.execute('INSERT INTO item_mall_cabinet(usuario,producto,item,cantidad,precio,remitente,duracion,fin,creado) '
                    'VALUES(?,?,?,?,?,?,?,?,?)',(target,product,row['item'],row['quantity'],price,
                                               ses.personaje.nombre if receiver else '',duration,deadline,time.time()))
        ident=con.execute('SELECT last_insert_rowid()').fetchone()[0]
        con.execute('INSERT INTO item_mall_movimientos VALUES(?,?,?,?,?,?)',
                    (uuid.uuid4().hex,ses.usuario,-price,'purchase',product,time.time()))
    cuentas._notificar_cambio(inmediato=True)
    return ident,target


def retirar(ses,ident,destination=0xffffffff):
    import app,cuentas,inventario
    p=ses.personaje
    if getattr(ses,'mapa_cargando',False) or getattr(ses,'muerto',False):
        raise Rechazo('Wait until your character is ready to claim the delivery.')
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE');_schema(con)
        delivery=con.execute('SELECT item,cantidad,duracion,fin FROM item_mall_cabinet WHERE id=? AND usuario=?',
                             (ident,ses.usuario)).fetchone()
        if not delivery:raise Rechazo('That Store Cabinet delivery is unavailable or already claimed.')
        record=con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',
                           (ses.usuario,p.char_id)).fetchone()
        if not record:raise Rechazo('Character not found.')
        data=json.loads(record[0])
        if not cuentas.inventario_equivalente(data,ses.inventario,app._cantidades(ses)):
            raise Rechazo('Inventory changed. Reconnect before claiming the delivery.')
        item,remaining,duration,deadline=delivery
        if deadline and deadline<=time.time():raise Rechazo('This timed delivery has expired.')
        deadline=deadline or (time.time()+duration*60 if duration else None)
        bag,counts=dict(ses.inventario),dict(app._cantidades(ses))
        upgrades={int(k):dict(v) for k,v in data.get('mejoras',{}).items()}
        changed=set();fresh=set()
        preferred=int(destination)
        if preferred!=0xffffffff and not 20<=preferred<=app._tope_bolsa(bag):
            raise Rechazo('Invalid bag destination.')
        stackable=inventario.es_apilable(item)
        while remaining:
            slot=next((s for s,it in sorted(bag.items()) if stackable and not deadline and it==item
                       and 20<=s<=app._tope_bolsa(bag) and not upgrades.get(s) and counts.get(s,1)<999),None)
            if slot is None:
                slot=preferred if preferred!=0xffffffff and preferred not in bag else app._ranura_libre(bag)
                if slot is None:raise Rechazo('Your backpack is full. The delivery remains in Store Cabinet.')
                bag[slot]=item;counts[slot]=0;fresh.add(slot);upgrades.pop(slot,None)
                if deadline:upgrades[slot]={'mall_fin':deadline,'mall_item':item}
            amount=min(remaining,999-counts.get(slot,1)) if stackable else 1
            counts[slot]=counts.get(slot,1)+amount;remaining-=amount;changed.add(slot)
        data.update(inventario={str(k):v for k,v in bag.items()},cantidades={str(k):v for k,v in counts.items()},
                    mejoras={str(k):v for k,v in upgrades.items()})
        con.execute('UPDATE personajes SET datos=? WHERE usuario=? AND char_id=?',
                    (json.dumps(data),ses.usuario,p.char_id))
        con.execute('DELETE FROM item_mall_cabinet WHERE id=? AND usuario=?',(ident,ses.usuario))
        con.execute('INSERT INTO item_mall_movimientos VALUES(?,?,?,?,?,?)',
                    (uuid.uuid4().hex,ses.usuario,0,'claim',ident,time.time()))
    ses.inventario.clear();ses.inventario.update(bag)
    app._cantidades(ses).clear();app._cantidades(ses).update(counts)
    p.inventario,p.cantidades,p.mejoras=ses.inventario,app._cantidades(ses),upgrades
    for slot in fresh:app._instancias(ses)[slot]=inventario.instancia_nueva()
    ses.enviar(*app._refrescar(ses,changed),almacen(ses.usuario))
    cuentas._notificar_cambio(inmediato=True)


def _aviso(ses,text):
    import clases
    ses.enviar(clases.aviso(text,tipo=0))


def procesar(ses,opcode,body):
    import clases
    if not getattr(ses,'personaje',None) or getattr(ses,'rol',None)!='mundo':return False
    if opcode==0x012D:
        if body:return True  # exact native request is empty
        ses.enviar(catalogo(),almacen(ses.usuario),struct.pack('<HI',0x0062,saldo(ses.usuario)))
        return True
    if opcode in (0x012B,0x012C):
        if len(body)!=(5 if opcode==0x012B else 21):return True
        product=struct.unpack_from('<I',body)[0]
        if opcode==0x012B and body[4]!=0:return True
        receiver=body[4:].split(b'\0',1)[0].decode('latin1').strip() if opcode==0x012C else None
        if opcode==0x012C and not receiver:return True
        try:
            _,target=comprar(ses,product,receiver)
            _aviso(ses,'Item Mall purchase successful. Claim your items from Store Cabinet.' if not receiver else 'Your Item Mall gift has been sent.')
            import app
            recipients=[s for s in app._tw_sesiones() if getattr(s,'usuario','').casefold()==target.casefold()]
            for s in recipients:
                if s is not ses:s.enviar(almacen(target))
        except Rechazo as exc:_aviso(ses,str(exc))
        ses.enviar(almacen(ses.usuario),struct.pack('<HI',0x0062,saldo(ses.usuario)))
        return True
    if opcode==0x012E:
        # Native client also uses this as a catalog product availability check.
        ses.enviar(catalogo(),struct.pack('<HI',0x0062,saldo(ses.usuario)))
        return True
    if opcode==0x002F and body and body[0] in (20,21,22):
        if body[0] in (20,21):ses.enviar(almacen(ses.usuario))
        elif len(body)==9:
            try:
                retirar(ses,*struct.unpack_from('<II',body,1))
                _aviso(ses,'Item Mall delivery claimed successfully.')
            except Rechazo as exc:_aviso(ses,str(exc))
        return True
    return False
