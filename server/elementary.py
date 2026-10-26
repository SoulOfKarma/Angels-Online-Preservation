"""Angel Elementary: native quiz, daily registration and persistent results.

Rules are wnd05.xml24793:30 questions/10sec, remaining seconds for correct
answers,-3 for wrong answers,3 hearts and3 stars,one helper per question.
bufprize.xml type2 supplies the30 real ranked prizes.
The original server EXP formula is unavailable. Local compatibility uses
level²*score EXP,score Skill EXP and score//10 credit,with server EXP rates;
Smart Blessings Bell doubles all three. No invented reward items.
"""
import copy
import datetime as dt
import functools
import json
import math
from pathlib import Path
import random
import secrets
import struct
import time

import elementary_codec as wire

STAGE=502
TEACHER=56
_ROUND=None
_LOADED=False


@functools.lru_cache(maxsize=1)
def data():return json.loads((Path(__file__).parent/'plantillas/elementary.json').read_text('utf8'))
def _key(s):return '%s:%s'%(s.usuario.casefold(),s.personaje.char_id)
def _ready(s):return getattr(s,'personaje',None) is not None and not getattr(s,'desconectado',False)
def _notice(s,text):
    import clases
    s.enviar(clases.aviso(text,tipo=0))
def _sessions():
    import app
    return [s for s in app._tw_sesiones() if _ready(s)]


def _schema(con):
    con.execute('CREATE TABLE IF NOT EXISTS elementary_runs(id TEXT PRIMARY KEY,payload TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS elementary_results('
        'run TEXT,owner TEXT,character INTEGER,name TEXT,score INTEGER,place INTEGER,'
        'payload TEXT,awarded INTEGER DEFAULT 0,claimed INTEGER DEFAULT 0,'
        'PRIMARY KEY(run,owner,character))')


def current():
    global _ROUND,_LOADED
    if not _LOADED:
        import cuentas
        with cuentas._LOCK,cuentas._get_conn() as con:
            _schema(con)
            row=con.execute('SELECT payload FROM elementary_runs ORDER BY rowid DESC LIMIT 1').fetchone()
        _ROUND=json.loads(row[0]) if row else None
        _LOADED=True
    return _ROUND


def _save(r,con=None):
    global _ROUND
    if con is None:
        import cuentas
        with cuentas._LOCK,cuentas._get_conn() as own:
            _schema(own);own.execute('INSERT OR REPLACE INTO elementary_runs VALUES(?,?)',(r['id'],json.dumps(r)))
        _ROUND=r
    else:con.execute('INSERT OR REPLACE INTO elementary_runs VALUES(?,?)',(r['id'],json.dumps(r)))


def phase(r=None,now=None):
    r=current() if r is None else r
    now=time.time() if now is None else now
    if not r or r['state']=='done':return 'closed'
    return 'registration' if now<r['start'] else 'quiz'


def start(registration=900,now=None,identity=None):
    now=time.time() if now is None else now
    if phase(now=now)!='closed':raise ValueError('Angel Elementary is already open.')
    pool=data()['questions']
    selected=random.sample(pool,min(30,len(pool)))
    questions=[]
    for row in selected:
        order=random.sample(range(3),3)
        questions.append(dict(id=row['id'],order=order,correct=order.index(0),
            hint=random.choice([i for i,n in enumerate(order) if n!=0]),seed=secrets.randbelow(8)+1,
            cookie=secrets.randbits(32)))
    r=dict(id=identity or 'quiz:'+secrets.token_hex(8),state='open',start=now+max(0,registration),
           index=-1,key=secrets.token_hex(4),questions=questions,members={},end=now+max(0,registration)+len(questions)*10)
    _save(r)
    _announce('Angel Elementary registration is open! Enter with Ctrl+Q.')
    return r


def _announce(text):
    import totem_war
    packet=totem_war.cartel_deslizante(text)
    for s in _sessions():s.enviar(packet)


def portales():
    arrival=data()['return_tile']
    return [dict(tile=e['tile'],destino=41,llegada=list(arrival),radio=2,entity=75020000+i)
            for i,e in enumerate(data()['exits'])]


def poblar(stage):
    if stage!=STAGE:return []
    import login
    return [login._map_object_spawn(p['entity'],60001,tuple(p['tile'])) for p in portales()]


def enter(s):
    r=current()
    if phase(r)!='registration':
        _notice(s,'Angel Elementary registration is from 18:45 to 19:00 every night.');return False
    if getattr(s,'muerto',False) or getattr(s,'mapa_cargando',False):return False
    import app
    tile=data()['tags']['1'][0]
    if s.personaje.stage!=STAGE:app._sincronizar_cambio_mapa(s,STAGE,*tile)
    s._elementary_enter=r['id']
    _registration(s,r)
    return True


def _registration(s,r):
    #5f6eb0: minutesu32 at0,enabled byte7. Registration has a native minute timer.
    s.enviar(struct.pack('<HI3xB',0x162,max(1,math.ceil((r['start']-time.time())/60)),1))


def loaded(s):
    if s.personaje.stage!=STAGE:return
    r=current()
    if phase(r)=='registration':_registration(s,r)
    elif phase(r)=='quiz' and _key(s) in r['members']:
        _begin_packet(s,r);_question_packet(s,r)


def _join(s,body):
    r=current()
    if phase(r)!='registration' or s.personaje.stage!=STAGE or len(body)!=2:return
    if body[0] not in (0,1) or body[1] not in (0,1):return
    if _key(s) in r['members']:
        _notice(s,'You are already registered for Angel Elementary.');return
    for checked,item in zip(body,(26626,26627)):
        if checked and not any(it==item and 20<=slot<160 for slot,it in s.inventario.items()):
            _notice(s,'You do not have the selected Smart Blessings item.');return
    updated=copy.deepcopy(r)
    updated['members'][_key(s)]=dict(owner=s.usuario,char=s.personaje.char_id,name=s.personaje.nombre,
        level=s.personaje.nivel,rank=s.personaje.rango,score=0,correct=0,wrong=0,
        heart=3,star=3,helper=0,answered=-1,boost=bool(body[0]),bell=bool(body[1]))
    _save(updated)
    s.enviar(struct.pack('<HI3xB',0x162,0,0))
    _notice(s,'You have registered for Angel Elementary.')


@functools.lru_cache(maxsize=16)
def _cipher(key):return wire.Cipher(key)


def _begin_packet(s,r):
    m=r['members'][_key(s)]
    s.enviar(struct.pack('<HB4I',0x164,1,m['heart'],m['star'],len(r['members']),m['score'])+r['key'].encode()+b'\0')


def _question_packet(s,r):
    if r['index']<0 or r['index']>=len(r['questions']):return
    m=r['members'][_key(s)];q=r['questions'][r['index']]
    row=next(row for row in data()['questions'] if row['id']==q['id'])
    answers=[row['answers'][i] for i in q['order']]
    s.enviar(struct.pack('<H5I',0x163,q['cookie'],q['hint'],m['heart'],m['star'],r['index'])+
             wire.question(_cipher(r['key']),row,answers,q['seed']))
    #An already answered question remains server-locked after reconnect.
    if m['answered']==r['index']:s.enviar(struct.pack('<H3I',0x169,2,len(r['members']),m['score']))


def _active(s):
    r=current()
    if (phase(r)!='quiz' or s.personaje.stage!=STAGE or _key(s) not in r['members']
            or getattr(s,'muerto',False) or getattr(s,'mapa_cargando',False)
            or not 0<=r['index']<len(r['questions'])):return None
    deadline=r['start']+(r['index']+1)*10
    if time.time()>=deadline or r['members'][_key(s)]['answered']==r['index']:return None
    return r


def _answer(s,body):
    r=_active(s)
    if r is None or len(body)!=47:return
    q=r['questions'][r['index']]
    if struct.unpack_from('<I',body)[0]!=q['cookie']:return
    #The client sends a random decoy atbody4. Only the encrypted appdata is
    #the selected logical answer; neither client time nor flags award points.
    try:choice=wire.answer(_cipher(r['key']),body[14:46].split(b'\0',1)[0],q['seed'])
    except (ValueError,UnicodeError):return
    updated=copy.deepcopy(r);m=updated['members'][_key(s)]
    correct=choice==q['correct']
    if correct:
        gain=max(1,min(10,math.ceil(r['start']+(r['index']+1)*10-time.time())))
        m['score']+=gain*(2 if m['helper']==2 else 1);m['correct']+=1
    else:
        m['score']=max(0,m['score']-(0 if m.get('protected') else 3));m['wrong']+=1
    m['answered']=r['index'];_save(updated)
    s.enviar(struct.pack('<H3I',0x169,1 if correct else 0,len(r['members']),m['score']))


def _helper(s,kind):
    r=_active(s)
    if r is None:return
    original=r['members'][_key(s)];field='heart' if kind==1 else 'star'
    if original['helper'] or original[field]<=0:return
    updated=copy.deepcopy(r);m=updated['members'][_key(s)]
    m[field]-=1;m['helper']=kind;m['protected']=False
    slot=next((slot for slot,it in s.inventario.items() if it==26626 and 20<=slot<160),None)
    if m['boost'] and slot is not None:
        import recent_mall
        m['protected']=True
        try:
            recent_mall.cambiar(s,{slot:1},[],transaccion=lambda con,d:_save(updated,con))
        except recent_mall.Rechazo as exc:_notice(s,str(exc));return
        global _ROUND
        _ROUND=updated
    else:_save(updated)
    s.enviar(struct.pack('<HBI',0x165 if kind==1 else 0x166,0,m[field]))


def _finish(r):
    global _ROUND
    import cuentas
    updated=copy.deepcopy(r);updated['state']='done'
    #Native tie break: higher level,rank,older character. char_id is the
    #persistent creation order in this server; final ties have a stable key.
    ranked=sorted(updated['members'].items(),key=lambda v:(-v[1]['score'],-v[1]['level'],-v[1]['rank'],v[1]['char'],v[0]))
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE');_schema(con)
        for index,(key,m) in enumerate(ranked):
            con.execute('INSERT OR IGNORE INTO elementary_results(run,owner,character,name,score,place,payload) VALUES(?,?,?,?,?,?,?)',
                (r['id'],m['owner'].casefold(),m['char'],m['name'],m['score'],index+1,json.dumps(m)))
        _save(updated,con)
    _ROUND=updated
    cuentas._notificar_cambio(inmediato=True)
    _announce('Angel Elementary has ended! The top 30 can claim their prizes from the Elementary Teacher.')
    active=[s for s in _sessions() if s.personaje.stage==STAGE and _key(s) in r['members']]
    for s in active:
        for index,(_,m) in enumerate(ranked[:30]):
            s.enviar(struct.pack('<HII17sI',0x167,min(30,len(ranked)),index,m['name'].encode('latin-1','replace')[:16].ljust(17,b'\0'),m['score']))
        rank=next(i+1 for i,(key,_) in enumerate(ranked) if key==_key(s))
        m=r['members'][_key(s)]
        s.enviar(struct.pack('<H10I',0x168,m['score'],rank-1,len(ranked),m['correct'],m['heart'],m['star'],0,0,0,0))
        _notice(s,'Angel Elementary finished. Your rank: %d; points: %d.'%(rank,m['score']))


def _award(s):
    """Progress is saved once; item prizes stay pending for the teacher."""
    import cuentas,clases,combate,configuracion,app,recent_mall
    if getattr(s,'mapa_cargando',False) or getattr(s,'muerto',False):return
    with cuentas._LOCK,cuentas._get_conn() as con:
        _schema(con)
        rows=con.execute('SELECT run,payload FROM elementary_results WHERE owner=? AND character=? AND awarded=0',
                         (s.usuario.casefold(),s.personaje.char_id)).fetchall()
    for run,payload in rows:
        m=json.loads(payload);p=s.personaje;saved=[]
        bell=next((slot for slot,it in s.inventario.items() if it==26627 and 20<=slot<160),None) if m['bell'] else None
        mult=2 if bell is not None else 1
        points=max(1,m['score'])
        xp=int(p.nivel*p.nivel*points*mult*configuracion.multiplicador_exp(p.buffs))
        sk=int(points*mult*configuracion.multiplicador_skill_exp(p.buffs))
        credit=(m['score']//10)*mult
        def award(con,d):
            status=con.execute('SELECT awarded FROM elementary_results WHERE run=? AND owner=? AND character=?',
                               (run,s.usuario.casefold(),p.char_id)).fetchone()
            if not status or status[0]:raise recent_mall.Rechazo('This quiz reward was already delivered.')
            if (int(d.get('exp',p.exp))!=p.exp or int(d.get('nivel',p.nivel))!=p.nivel
                    or d.get('habilidades',[])!=[list(h) for h in p.habilidades]):
                raise recent_mall.Rechazo('Waiting for character progress to finish saving.')
            level=p.nivel;d['exp']=max(p.exp,combate.exp_para_nivel(level))+xp
            while level<combate.nivel_maximo() and d['exp']>=combate.exp_para_nivel(level+1):level+=1
            d.update(nivel=level,hp_max=p.hp_max+(level-p.nivel)*25,mp_max=p.mp_max+(level-p.nivel)*15)
            skills=[]
            for sid,lv,exp in p.habilidades:
                exp+=sk;cap=min(combate.nivel_maximo(),level+(11 if 20<=sid<32 else 0))
                while lv<cap and exp>=max(1,clases.exp_requerida_skill(lv,sid)):
                    exp-=max(1,clases.exp_requerida_skill(lv,sid));lv+=1
                if lv>=cap:exp=min(exp,max(1,clases.exp_requerida_skill(lv,sid)))
                skills.append([sid,lv,exp])
            d['habilidades']=skills;d['creditos']=int(d.get('creditos',p.creditos))+credit
            con.execute('UPDATE elementary_results SET awarded=1 WHERE run=? AND owner=? AND character=?',
                        (run,s.usuario.casefold(),p.char_id));saved.append(copy.deepcopy(d))
        try:recent_mall.cambiar(s,{bell:1} if bell is not None else {},[],transaccion=award)
        except recent_mall.Rechazo:continue
        d=saved[0]
        for attr in ('nivel','exp','hp_max','mp_max','creditos'):setattr(p,attr,d[attr])
        p.habilidades=[tuple(h) for h in d['habilidades']]
        actual,nxt=combate.exp_para_barra(p.nivel,p.exp)
        packets=[struct.pack('<HIB',0x1d,p.entity_id,4)+struct.pack('<BQ',29,p.nivel)+
                 struct.pack('<BQ',30,combate.exp_para_nivel(p.nivel))+struct.pack('<BQ',31,nxt)+struct.pack('<BQ',32,actual),
                 clases.aviso(str(xp),tipo=0,msg_id=clases.MSG_EXP),clases.arbol(p.habilidades),app._stats_ses(s)]
        for sid,_,_ in p.habilidades:packets.append(clases.aviso_doble(clases.MSG_SKILL_EXP,clases.nombre(sid),str(sk)))
        s.enviar(*packets)
        _notice(s,'Angel Elementary rewards delivered: %d Exp, %d Skill Exp and %d Credit.'%(xp,sk,credit))


def claim(s):
    import cuentas,recent_mall,dialogos
    if s.personaje.stage!=41 or max(abs(s.personaje.tile_x-132),abs(s.personaje.tile_y-80))>8:return
    with cuentas._LOCK,cuentas._get_conn() as con:
        _schema(con)
        row=con.execute('SELECT run,score,place,claimed FROM elementary_results WHERE owner=? AND character=? ORDER BY rowid DESC LIMIT 1',
                        (s.usuario.casefold(),s.personaje.char_id)).fetchone()
    if not row or row[1]<1 or row[2]>30:mid=8344
    elif row[3]:mid=8347
    else:
        prize=next((r for r in data()['prizes'] if r['place']==row[2]),None)
        if prize is None:return
        def mark(con,d):
            cur=con.execute('UPDATE elementary_results SET claimed=1 WHERE run=? AND owner=? AND character=? AND claimed=0',
                            (row[0],s.usuario.casefold(),s.personaje.char_id))
            if cur.rowcount!=1:raise recent_mall.Rechazo('This prize was already claimed.')
        try:recent_mall.cambiar(s,{},prize['items'],transaccion=mark)
        except recent_mall.Rechazo as exc:_notice(s,str(exc));return
        mid=8345
        _notice(s,'Angel Elementary Top %d prize delivered.'%row[2])
    s.enviar(dialogos.armar_linea(mid,4))


def pulsar(s,entity):
    s._elementary_teacher=False
    if s.personaje.stage!=41 or entity!=TEACHER:return False
    if max(abs(s.personaje.tile_x-132),abs(s.personaje.tile_y-80))>8 or getattr(s,'muerto',False):return True
    import dialogos
    s._elementary_teacher='menu';s.dlg_ent=TEACHER
    s.enviar(dialogos.armar_linea(8341,4,[8342,8343]))
    return True


def continuar(s,value):
    state=getattr(s,'_elementary_teacher',False)
    if not state:return False
    import dialogos
    if state=='menu' and dialogos.es_opcion(value) and dialogos.indice_opcion(value)==0:
        claim(s);s._elementary_teacher='done'
    else:
        s._elementary_teacher=False;s.dlg_ent=None
        s.enviar(struct.pack('<H',0x12)+dialogos.FIN)
    return True


def comando_gm(s,words):
    action=words[0].casefold() if words else 'status'
    try:
        if action=='start':start(max(0,min(900,int(words[1]) if len(words)>1 else 10)))
        elif action=='enter':enter(s)
        elif action=='finish':
            r=current()
            if r and phase(r)!='closed':_finish(r)
        elif action=='stop':
            r=current()
            if r:
                updated=copy.deepcopy(r);updated['state']='done';_save(updated)
        elif action!='status':raise ValueError('Use /quiz start [registration_seconds]|enter|finish|stop|status')
        r=current()
        _notice(s,'Angel Elementary:%s; participants:%d; question:%d.'%
                (phase(r),len((r or {}).get('members',{})),max(0,(r or {}).get('index',-1)+1)))
    except ValueError as exc:_notice(s,str(exc))


def procesar(s,opcode,body):
    if opcode not in (0x150,0x152,0x153,0x154,0x155):return False
    if not _ready(s) or s.rol!='mundo':return True
    if opcode==0x150 and not body:enter(s)
    elif opcode==0x152:_join(s,body)
    elif opcode==0x153:_answer(s,body)
    elif opcode in (0x154,0x155) and not body:_helper(s,1 if opcode==0x154 else 2)
    return True


def cron(now=None):
    now=time.time() if now is None else now
    r=current();local=dt.datetime.fromtimestamp(now).astimezone()
    opening=local.replace(hour=18,minute=45,second=0,microsecond=0)
    identity='scheduled:'+local.date().isoformat()
    if opening.timestamp()<=now<opening.timestamp()+900 and phase(r,now)=='closed' and (r or {}).get('id')!=identity:
        r=start(opening.timestamp()+900-now,now,identity)
    if r and phase(r,now)=='quiz':
        index=int((now-r['start'])//10)
        if index>=len(r['questions']):_finish(r)
        elif index!=r['index']:
            updated=copy.deepcopy(r);updated['index']=index
            for m in updated['members'].values():m['helper']=0;m['protected']=False
            _save(updated)
            if index==0:_announce('Angel Elementary has begun!')
            for s in _sessions():
                if s.personaje.stage==STAGE and _key(s) in updated['members']:
                    if r['index']<0:_begin_packet(s,updated)
                    _question_packet(s,updated)
    for s in _sessions():_award(s)
