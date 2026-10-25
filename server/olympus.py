"""Olympus: original IGG NPC trees, per-floor generators and private trials.

Weekly prize quantities are server-only and deliberately not invented.
"""
import datetime as dt
import functools
import json
import pathlib
import struct
import time
import uuid

STAGES=frozenset((217,332))
MARK=8561


@functools.lru_cache(maxsize=1)
def datos():
    return json.loads((pathlib.Path(__file__).parent/'plantillas/olympus_tower.json').read_text('utf8'))


def _npc(ses):
    if not getattr(ses,'personaje',None):return None
    stage=ses.personaje.stage
    if stage==41:return datos()['npcs']
    return [n for n in datos()['maps'].get(str(stage),{}).get('spawns',[]) if not n['monstruo']]


def cerca(ses,name):
    p=ses.personaje
    return any(n['nombre']==name and max(abs(p.tile_x-n['tile'][0]),abs(p.tile_y-n['tile'][1]))<=4
               for n in (_npc(ses) or []))


def poblar(stage):
    import login
    ns=datos()['npcs'] if stage==41 else datos()['maps'].get(str(stage),{}).get('spawns',[])
    packets=[login._npc_spawn(n['entity_id'],n['npc_type'],n['nombre'],tuple(n['tile']),
                             sprite=n['sprite'],klass=199,direccion=n.get('direccion',6))
             for n in ns if not n.get('monstruo')]
    packets.extend(login._map_object_spawn(o['entity'],o['sprite'],tuple(o['tile']))
                   for o in datos()['maps'].get(str(stage),{}).get('objects',[]))
    if stage==41:
        o=datos()['entrance']
        packets.append(login._map_object_spawn(o['entity'],o['sprite'],tuple(o['tile'])))
    return packets


def pulsar(ses,ent,addr='olympus'):
    import app
    if ses.personaje.stage==41 and ent==datos()['entrance']['entity']:
        o=datos()['entrance'];p=ses.personaje
        if max(abs(p.tile_x-o['tile'][0]),abs(p.tile_y-o['tile'][1]))<=4:
            app._recorrer_dialogo_mapa(ses,addr,41,o['root'])
        return True
    for n in _npc(ses) or []:
        if n['entity_id']!=ent:continue
        if not cerca(ses,n['nombre']):return True
        ses._olympus_npc=n['nombre']
        ses._lyceum_exchange=None
        app._recorrer_dialogo_mapa(ses,addr,ses.personaje.stage,n.get('root',10000))
        return True
    for o in datos()['maps'].get(str(ses.personaje.stage),{}).get('objects',[]):
        if o['entity']!=ent:continue
        p=ses.personaje
        if max(abs(p.tile_x-o['tile'][0]),abs(p.tile_y-o['tile'][1]))<=4:
            import eventos_mundo
            effects=eventos_mundo.al_pulsar(ses,tuple(o['tile']))
            app._aplicar_efectos(ses,addr,effects)
        return True
    return False


def mostrar(ses,mid,face=1093):
    import dialogos
    pkt=dialogos.armar_linea(mid,face)
    ses.dlg_ent,ses.dlg_val=ses.personaje.entity_id,face
    ses.dlg_guion,ses.dlg_paso,ses.dlg_mapa=[pkt[2:]],1,None
    ses.enviar(pkt)


def _schema(con):
    con.execute('CREATE TABLE IF NOT EXISTS olympus_runs '
                '(id TEXT PRIMARY KEY,usuario TEXT NOT NULL,char_id INTEGER NOT NULL,'
                'inicio REAL NOT NULL,fin REAL NOT NULL,restante INTEGER,registrado INTEGER DEFAULT 0,'
                'semana TEXT,nombre TEXT,nivel INTEGER,rango INTEGER,faccion TEXT,abandonado INTEGER DEFAULT 0)')
    con.execute('CREATE TABLE IF NOT EXISTS olympus_daily '
                '(usuario TEXT,char_id INTEGER,dia TEXT,fin REAL,PRIMARY KEY(usuario,char_id,dia))')


def _mark(ses):
    return (getattr(ses.personaje,'buffs',{}) or {}).get(MARK,{}).get('fin',0)>time.time()


def antes_dialogo(ses,stage,node):
    """Handle transactional leaf nodes before the generic action interpreter."""
    import app,cuentas,equipos,eventos
    if stage==41 and str(node) in datos()['nodes']:
        name=getattr(ses,'_olympus_npc',None)
        if name not in ('Olly','Ozzy') or not cerca(ses,name):return True
        if node==2016722:
            if _mark(ses):mostrar(ses,8340)
            elif equipos.cuantos(ses)>1:mostrar(ses,8297)
            else:
                import eventos_mundo
                with cuentas._LOCK,cuentas._get_conn() as con:
                    _schema(con)
                    con.execute('UPDATE olympus_runs SET abandonado=1 WHERE usuario=? AND char_id=? AND registrado=0',
                                (ses.usuario,ses.personaje.char_id))
                eventos_mundo._CORRIDAS.pop(('solo',(ses.usuario.casefold(),ses.personaje.char_id)),None)
                ses._olympus_run=None
                ses._olympus_admitido=True
                tile=eventos.casillas_de_tag(217,1)[0]
                app._viajar_por_portal(ses,'olympus',{'destino':217,'llegada':tile})
            return True
        if node==2015500:
            _ozzy(ses)
            return True
        if node==2016737:
            ses._lyceum_exchange=280
            ses.enviar(struct.pack('<HI',0x0151,280))
            return True
        if node==2016726:
            # Native rejection when no eligible previous-week result exists.
            # A genuine top30 result stays unclaimed until its prize table is known.
            rows=clasificacion(39)
            own=next((i for i,r in enumerate(rows,1) if r['usuario'].casefold()==ses.usuario.casefold()
                      and r['a']==ses.personaje.char_id),None)
            if own and own<=30:
                import clases
                ses.enviar(clases.aviso('Olympus weekly reward data is not configured. Your reward has not been marked as claimed.',tipo=0))
            else:mostrar(ses,8318)
            return True
    if stage in STAGES and node==1000001:
        if not cerca(ses,'Omos'):return True
        registrar(ses)
        return True
    return False


def _ozzy(ses):
    """Original1 Coin ->1 Box, once per local day, atomic and owner-scoped."""
    import app,cuentas
    now=time.time();day=dt.datetime.fromtimestamp(now).date().isoformat();p=ses.personaje
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE');_schema(con)
        if con.execute('SELECT 1 FROM olympus_daily WHERE usuario=? AND char_id=? AND fin>?',
                       (ses.usuario,p.char_id,now)).fetchone():
            mostrar(ses,511658,3);return
        bag,counts=dict(ses.inventario),dict(app._cantidades(ses))
        coin=next((s for s,it in bag.items() if it==54260 and 20<=s<=app._tope_bolsa(bag)),None)
        if coin is None:mostrar(ses,511659,3);return
        # Original NPC demands an empty slot even if spending its last coin frees one.
        dest=app._ranura_libre(bag)
        if dest is None:mostrar(ses,511660,3);return
        row=con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',
                        (ses.usuario,p.char_id)).fetchone()
        if not row or not cuentas.inventario_equivalente(json.loads(row[0]),bag,counts):
            import clases
            ses.enviar(clases.aviso('Inventory changed; please reconnect before exchanging. No coin was consumed.',tipo=0))
            return
        n=counts.get(coin,1)
        if n>1:counts[coin]=n-1
        else:bag.pop(coin);counts.pop(coin,None)
        bag[dest]=54262;counts[dest]=1
        data=json.loads(row[0]);data.update(inventario={str(k):v for k,v in bag.items()},
                                         cantidades={str(k):v for k,v in counts.items()})
        for s in (coin,dest):
            if s==dest or s not in bag:data.setdefault('mejoras',{}).pop(str(s),None)
        con.execute('UPDATE personajes SET datos=? WHERE usuario=? AND char_id=?',
                    (json.dumps(data),ses.usuario,p.char_id))
        con.execute('INSERT OR REPLACE INTO olympus_daily VALUES(?,?,?,?)',(ses.usuario,p.char_id,day,now+86400))
    ses.inventario.clear();ses.inventario.update(bag)
    app._cantidades(ses).clear();app._cantidades(ses).update(counts)
    p.inventario,p.cantidades=ses.inventario,app._cantidades(ses)
    for s in (coin,dest):
        if s==dest or s not in bag:
            (p.mejoras or {}).pop(s,None);app._instancias(ses).pop(s,None)
    ses.enviar(*app._refrescar(ses,{coin,dest}))
    cuentas._notificar_cambio();mostrar(ses,511657,3)


def usar(ses,slot):
    """Native54262 box ->5x54904; formula33 heart removes8561 outside tower."""
    import app,cuentas,clases
    item=ses.inventario.get(slot)
    if item not in (54262,54904):return False
    p=ses.personaje
    def reject(text):ses.enviar(clases.aviso(text,tipo=0));return True
    if not 20<=slot<=app._tope_bolsa(ses.inventario) or getattr(ses,'muerto',False):
        return reject('You cannot use this item now.')
    if item==54904 and p.stage in STAGES:return reject('Olympic Hearts cannot be used inside Olympus Tower.')
    if item==54904 and not _mark(ses):return reject('There is no active Olympus Mark to remove.')
    dest=app._ranura_libre(ses.inventario) if item==54262 else None
    if item==54262 and dest is None:return reject('Clear one bag slot before opening the Olympic Heart Box.')
    bag,counts=dict(ses.inventario),dict(app._cantidades(ses))
    if counts.get(slot,1)>1:counts[slot]-=1
    else:bag.pop(slot);counts.pop(slot,None)
    if dest is not None:bag[dest]=54904;counts[dest]=5
    buffs=dict(getattr(p,'buffs',{}) or {})
    if item==54904:buffs.pop(MARK,None)
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',(ses.usuario,p.char_id)).fetchone()
        if not row or not cuentas.inventario_equivalente(json.loads(row[0]),ses.inventario,app._cantidades(ses)):
            return reject('Inventory changed. No item was consumed; reconnect before trying again.')
        data=json.loads(row[0])
        data.update(inventario={str(k):v for k,v in bag.items()},cantidades={str(k):v for k,v in counts.items()})
        if item==54904:data['buffs']=buffs
        for s in (slot,dest):
            if s is not None and (s==dest or s not in bag):data.setdefault('mejoras',{}).pop(str(s),None)
        con.execute('UPDATE personajes SET datos=? WHERE usuario=? AND char_id=?',(json.dumps(data),ses.usuario,p.char_id))
    ses.inventario.clear();ses.inventario.update(bag)
    app._cantidades(ses).clear();app._cantidades(ses).update(counts)
    p.inventario,p.cantidades,p.buffs=ses.inventario,app._cantidades(ses),buffs
    changed={slot}
    if dest is not None:changed.add(dest)
    for s in changed:
        if s==dest or s not in bag:
            (p.mejoras or {}).pop(s,None);app._instancias(ses).pop(s,None)
    ses.enviar(*app._refrescar(ses,changed))
    if item==54904:ses.enviar(struct.pack('<HIBBII',0x001D,p.entity_id,1,4,MARK,0))
    ses.enviar(clases.aviso('Received5 Olympic Hearts.' if item==54262 else 'The Olympus Mark has been removed.',tipo=0))
    cuentas._notificar_cambio()
    return True


def generar(ses,stage,zona):
    """Finite native waves, with original counts and non-overlapping positions."""
    if stage not in STAGES:return False
    import app,combate,login
    for row in datos()['maps'][str(stage)]['zones'].get(str(zona),[]):
        eid=row['entity_id']
        if eid in (ses.monstruos or {}):continue  # killed mobs never respawn
        m=combate.Monstruo(eid,row['npc_type'],row['nombre'],row['tile'],row['sprite'],stage=stage)
        m.generado=True;m.zona_generador=m.zona_plantilla=int(zona)
        if ses.monstruos is None:ses.monstruos={}
        ses.monstruos[eid]=m
        ses.enviar(login._npc_spawn(eid,m.npc_type,m.nombre,tuple(m.tile),sprite=m.sprite,klass=1))
    return True


def efecto(ses,action,param=0):
    import app,cuentas
    p=ses.personaje
    if not p or p.stage not in STAGES:return False
    if action==111:
        if getattr(ses,'_olympus_run',None):return True  # crossing217/332 keeps one clock
        if _mark(ses):mostrar(ses,8298,0);return False
        now=time.time();rid=uuid.uuid4().hex
        with cuentas._LOCK,cuentas._get_conn() as con:
            _schema(con)
            con.execute('INSERT INTO olympus_runs(id,usuario,char_id,inicio,fin) VALUES(?,?,?,?,?)',
                        (rid,ses.usuario,p.char_id,now,now+param/1000))
        ses._olympus_run=rid
        import eventos_mundo
        eventos_mundo.corrida_de(ses,eventos_mundo.grupo_de_instancia(p.stage))['olympus_run']=rid
        import combate
        from house_services import xml_rows
        mag=combate.datos_magia(MARK)
        duration=int(xml_rows('magic.xml')[MARK]['\u6301\u7e8c\u6642\u9593'])
        entry=app._entrada_de_buff(mag,duration)
        entry['persist_death']=True
        if getattr(p,'buffs',None) is None:p.buffs={}
        app._buff_a_otro(ses,MARK,entry,duration*1000,mag)
        cuentas.guardar_buffs(ses.usuario,p.char_id,p.buffs)
        ses.enviar(struct.pack('<HI',0x016A,int(param//1000)))
    elif action==112:
        rid=getattr(ses,'_olympus_run',None)
        if not rid:return False
        with cuentas._LOCK,cuentas._get_conn() as con:
            _schema(con)
            con.execute('UPDATE olympus_runs SET restante=MAX(0,CAST(fin-? AS INTEGER)) '
                        'WHERE id=? AND usuario=? AND char_id=? AND restante IS NULL AND fin>?',
                        (time.time(),rid,ses.usuario,p.char_id,time.time()))
        ses.enviar(struct.pack('<H',0x016B))
    return True


def _week(now=None):
    day=dt.datetime.fromtimestamp(time.time() if now is None else now).date()
    return (day-dt.timedelta(days=day.weekday())).isoformat()


def registrar(ses):
    import cuentas,app,eventos
    p=ses.personaje;rid=getattr(ses,'_olympus_run',None)
    if p.faction not in ('Aurora','Beasts','Steel','Shadow'):
        import clases
        ses.enviar(clases.aviso('Only graduated faction members can register an Olympus result.',tipo=0))
        return
    with cuentas._LOCK,cuentas._get_conn() as con:
        _schema(con)
        row=con.execute('SELECT restante,registrado FROM olympus_runs WHERE id=? AND usuario=? AND char_id=?',
                        (rid,ses.usuario,p.char_id)).fetchone()
        if not row or row[0] is None:mostrar(ses,8306,1112);return
        if row[1]:mostrar(ses,8348,1112);return
        con.execute('UPDATE olympus_runs SET registrado=1,semana=?,nombre=?,nivel=?,rango=?,faccion=? WHERE id=?',
                    (_week(),p.nombre,p.nivel,p.rango,p.faction,rid))
    mostrar(ses,8310,1112)


def clasificacion(tipo):
    """Current/previous week; only recorded Omos results, best run per owner."""
    import cuentas
    week=_week()
    if tipo==39:week=(dt.date.fromisoformat(week)-dt.timedelta(days=7)).isoformat()
    with cuentas._get_conn() as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name='olympus_runs'").fetchone():return []
        rows=con.execute('SELECT usuario,char_id,nombre,nivel,rango,faccion,restante FROM olympus_runs '
                         'WHERE registrado=1 AND semana=? ORDER BY restante DESC,nivel DESC,rango DESC,char_id ASC',
                         (week,)).fetchall()
    seen=set();result=[]
    for u,cid,n,lv,rank,f,remaining in rows:
        key=u.casefold(),cid
        if key in seen:continue
        seen.add(key)
        result.append(dict(usuario=u,a=cid,nombre=n,nivel=lv,segundo=rank,
                           faccion={'Aurora':0,'Beasts':1,'Steel':2,'Shadow':3}.get(f,0),puntos=remaining))
    return result


def tick(ses):
    import cuentas,app,eventos
    p=getattr(ses,'personaje',None)
    if not p:return
    rid=getattr(ses,'_olympus_run',None)
    if p.stage not in STAGES:
        ses._olympus_run=None;return
    if not rid:return
    with cuentas._get_conn() as con:
        row=con.execute('SELECT fin,restante FROM olympus_runs WHERE id=? AND usuario=? AND char_id=?',
                        (rid,ses.usuario,p.char_id)).fetchone()
    if row and row[1] is None and time.time()>=row[0]:
        ses.enviar(struct.pack('<H',0x016B))
        app._viajar_por_portal(ses,'olympus',{'destino':41,'llegada':eventos.casillas_de_tag(41,1)[0]})


def cambio_mapa(ses,destination):
    import cuentas
    p=ses.personaje
    if p.stage in STAGES and destination not in STAGES:
        rid=getattr(ses,'_olympus_run',None)
        if rid:
            with cuentas._LOCK,cuentas._get_conn() as con:
                _schema(con)
                con.execute('UPDATE olympus_runs SET abandonado=1 WHERE id=? AND usuario=? AND char_id=? AND registrado=0',
                            (rid,ses.usuario,p.char_id))
        ses._olympus_run=None
        ses.enviar(struct.pack('<H',0x016B))


def al_entrar(ses):
    """Recover the same server-owned clock on reconnect, without renewing it."""
    import cuentas
    p=ses.personaje
    if p.stage not in STAGES:return
    with cuentas._get_conn() as con:
        if not con.execute("SELECT 1 FROM sqlite_master WHERE name='olympus_runs'").fetchone():return
        row=con.execute('SELECT id,fin,restante FROM olympus_runs WHERE usuario=? AND char_id=? '
                        'AND registrado=0 AND abandonado=0 AND fin>? ORDER BY inicio DESC LIMIT 1',
                        (ses.usuario,p.char_id,time.time())).fetchone()
    if row:
        import eventos_mundo,app,eventos,clases
        corrida=eventos_mundo._CORRIDAS.get(eventos_mundo._clave_corrida(ses))
        if row[2] is None and (not corrida or corrida.get('olympus_run')!=row[0]):
            # Restart must not produce an empty, already-cleared tower.
            ses._olympus_run=row[0]
            ses.enviar(clases.aviso('The previous Olympus instance is no longer available. The Olympus Mark remains active.',tipo=0))
            app._viajar_por_portal(ses,'olympus',{'destino':41,'llegada':eventos.casillas_de_tag(41,1)[0]})
            return
        ses._olympus_run=row[0]
        if row[2] is None:ses.enviar(struct.pack('<HI',0x016A,max(0,int(row[1]-time.time()))))
