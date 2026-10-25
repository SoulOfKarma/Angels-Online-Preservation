"""Native Star Blessing state, atomic card movement and local draw rules.

REA Angel.exe: 6248A0/6E7A70 receives 017F; 59CBE0/59C700 sends
015F(cmd,source,destination); 59BF10 sends 0160(group,recipe index).
Original card stats, conversion/upgrade costs and recipes are preserved.
Coin prices are native UI data; draw probabilities are local settings.
"""
import copy
import functools
import json
import pathlib
import random
import struct
import asyncio

LEVELS=(100,160,200,240,280,320,360,400)
LINES=((0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6))
STAR_KEYS=(58283,67178,69997,79859)
AUTO_INTERVAL=0.3


@functools.lru_cache(maxsize=1)
def datos():
    return json.loads((pathlib.Path(__file__).parent/'plantillas/star_blessing.json').read_text('utf8'))


def estado(raw=None):
    raw=raw if isinstance(raw,dict) else {}
    out={k:[int(v) if str(v) in datos()['cards'] else 0 for v in (list(raw.get(k,[]))+[0]*n)[:n]]
         for k,n in (('temp',20),('saved',10),('equipped',8))}
    out.update(working=int(raw.get('working',0)),power=max(0,int(raw.get('power',0))),
               dust=max(0,int(raw.get('dust',0))),rank=max(1,min(5,int(raw.get('rank',1)))),
               bingo=(list(raw.get('bingo',[]))+[0]*9)[:9],marked=(list(raw.get('marked',[]))+[0]*9)[:9],
               bingo_claimed=bool(raw.get('bingo_claimed',False)))
    # Old server snapshots sent packed card IDs to Bingo. Native6E80E0
    # expects only sign types1..15; migrate without losing obtained cards.
    out['bingo']=[int(c)//100%100 if int(c)>15 else int(c) for c in out['bingo']]
    if any(not 0<=c<=15 for c in out['bingo']):out['bingo']=[0]*9;out['marked']=[0]*9
    out['free_v']=max(0,int(raw.get('free_v',0)))
    out['free_iv']=max(0,int(raw.get('free_iv',0)))
    if str(out['working']) not in datos()['cards']:out['working']=0
    return out


def _pack(values):return struct.pack('<%dI'%len(values),*values) if values else b''


def lineas(s):return sum(all(s['marked'][i] for i in line) for line in LINES)


def coste(s,rank):
    if rank==5 and s['free_v'] or rank==4 and s['free_iv']:return 0
    return datos()['local_rules']['divination_costs'][rank-1]


def _reset_bingo(s):
    s['bingo']=random.sample(range(1,16),9);s['marked']=[0]*9;s['bingo_claimed']=False


def paquete(p,state=None,preview=None):
    s=estado(getattr(p,'star_blessing',None)) if state is None else state
    fields=[]
    def add(key,data):fields.append(struct.pack('<IB',key,1)+data)
    for key,name in ((1,'equipped'),(2,'temp'),(3,'saved')):
        add(key,_pack([len(s[name])]+s[name]))
    add(4,_pack([s['working']]))
    # 6E83C0/getStarPower returns module+8, the SECOND DWORD of field5.
    # Native6EA13B writes module+F8 to50052: the Stardust counter at top
    # right (wnd01 tooltip). Bottom-left Coins is the normal actor property.
    add(5,_pack([min(s['dust'],0xffffffff),min(s['power'],0xffffffff)]))
    rules=datos()['local_rules']
    # Native6E9D17 prints the signed count even for an unavailable tier:
    # -1 becomes a visible "-1" badge. Availability uses current rank or
    # a positive free count, so zero is correct for an empty IV/V counter.
    credits=[0,0,0,s['free_iv'],s['free_v']]
    add(7,struct.pack('<5i',*credits)+b''.join(struct.pack('<IB',int(c),bool(m)) for c,m in zip(s['bingo'],s['marked']))+_pack([lineas(s)]))
    # Field8 is Bingo reward thresholds (1=Starforce,4=free Divination IV).
    rewards=rules['bingo_awards']
    add(8,_pack([len(rewards)])+b''.join(struct.pack('<BBI',*r) for r in rewards))
    add(9,bytes([bool(getattr(p,'_star_auto',False))]))
    if preview is not None:
        materials,reward=preview
        add(10,_pack([len(materials)])+b''.join(_pack([slot,qty,card]) for slot,qty,card in materials)+_pack([reward]))
    payload=_pack([s['rank'],sum(p.nivel>=lv for lv in LEVELS),len(fields)])+b''.join(fields)
    return struct.pack('<HI',0x017f,len(payload)+4)+payload


def bonos(p):
    if not getattr(p,'star_blessing',None):return {}
    s=estado(getattr(p,'star_blessing',None));out={}
    for ident in s['equipped'][:sum(p.nivel>=lv for lv in LEVELS)]:
        for key,value in datos()['cards'].get(str(ident),{}).get('bonuses',{}).items():
            out[key]=out.get(key,0)+value
    return out


class Rechazo(ValueError):pass


def aviso(s,text):
    import clases
    s.enviar(clases.aviso(text,tipo=0))


def _commit(ses,operation,consume=None):
    import app,cuentas
    p=ses.personaje
    if getattr(ses,'muerto',False) or getattr(ses,'mapa_cargando',False):raise Rechazo('Wait until your character is ready.')
    if p.nivel<100:raise Rechazo('Star Blessing requires level 100.')
    old=estado(getattr(p,'star_blessing',None));s=copy.deepcopy(old)
    gold=ses.oro
    def update(con,data):
        nonlocal gold
        if estado(data.get('star_blessing'))!=old or int(data.get('oro',0))!=ses.oro:
            raise Rechazo('Character data changed. Reconnect before trying again.')
        gold=operation(s,ses.oro)
        if not 0<=gold<=ses.oro:raise Rechazo('Not enough Coins.')
        data.update(star_blessing=s,oro=gold)
    if consume is not None:
        import recent_mall
        try:recent_mall.cambiar(ses,consume,[],transaccion=update)
        except recent_mall.Rechazo as exc:raise Rechazo(str(exc)) from exc
    else:
        with cuentas._LOCK,cuentas._get_conn() as con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',(ses.usuario,p.char_id)).fetchone()
            if not row:raise Rechazo('Character not found.')
            data=json.loads(row[0]);update(con,data)
            con.execute('UPDATE personajes SET datos=? WHERE usuario=? AND char_id=?',(json.dumps(data),ses.usuario,p.char_id))
    p.star_blessing=s;p.oro=ses.oro=gold
    cuentas._notificar_cambio(inmediato=True)
    ses.enviar(paquete(p),app._stats_ses(ses))


def _move(s,source,index,target,dest):
    if not 1<=index<=len(s[source]) or not s[source][index-1]:raise Rechazo('Select a Star Sign first.')
    if s[source][index-1]==99901:raise Rechazo('Stardust cannot be moved. Use Auto Convert.')
    if dest in (-1,0xffffffff):
        dest=next((i+1 for i,v in enumerate(s[target]) if not v),0)
    if not 1<=dest<=len(s[target]):raise Rechazo('There are no free Star Sign slots.')
    s[source][index-1],s[target][dest-1]=s[target][dest-1],s[source][index-1]


def slots(ses,body):
    if len(body)!=12:return
    if getattr(ses.personaje,'_star_auto',False):aviso(ses,'Wait until Auto Divine has finished.');return
    cmd,index,dest=struct.unpack('<III',body)
    def operation(s,gold):
        if cmd in (1,2,9,10,11):
            a,b={1:('temp','saved'),2:('saved','temp'),9:('temp','temp'),10:('saved','saved'),11:('equipped','equipped')}[cmd]
            if cmd==11 and (index>sum(ses.personaje.nivel>=lv for lv in LEVELS) or dest>sum(ses.personaje.nivel>=lv for lv in LEVELS)):
                raise Rechazo('This Star Matrix slot is locked.')
            _move(s,a,index,b,dest)
        elif cmd in (3,6):
            unlocked=sum(ses.personaje.nivel>=lv for lv in LEVELS)
            if cmd==3:
                if dest==0xffffffff:dest_slot=next((i+1 for i,v in enumerate(s['equipped'][:unlocked]) if not v),0)
                else:dest_slot=dest
                if not 1<=dest_slot<=unlocked:raise Rechazo('This Star Matrix slot is locked.')
                _move(s,'saved',index,'equipped',dest_slot)
            else:
                if index>unlocked:raise Rechazo('This Star Matrix slot is locked.')
                _move(s,'equipped',index,'saved',dest)
            kinds=[datos()['cards'][str(c)]['kind'] for c in s['equipped'] if c]
            if len(kinds)!=len(set(kinds)) or any(k>=98 for k in kinds):
                raise Rechazo('Only one Star Sign of each type can be equipped.')
        elif cmd in (4,5):
            source='saved' if cmd==4 else 'equipped'
            if cmd==5 and index>sum(ses.personaje.nivel>=lv for lv in LEVELS):raise Rechazo('This Star Matrix slot is locked.')
            if not 1<=index<=len(s[source]) or not s[source][index-1]:raise Rechazo('Select a Star Sign first.')
            s['working'],s[source][index-1]=s[source][index-1],s['working']
        elif cmd in (7,8):
            target='equipped' if cmd==7 else 'saved'
            s['work']=[s['working']]
            _move(s,'work',1,target,dest)
            s['working']=s.pop('work')[0]
            if cmd==7:
                unlocked=sum(ses.personaje.nivel>=lv for lv in LEVELS)
                if any(s['equipped'][unlocked:]):raise Rechazo('This Star Matrix slot is locked.')
                kinds=[datos()['cards'][str(c)]['kind'] for c in s['equipped'] if c]
                if len(kinds)!=len(set(kinds)) or any(k>=98 for k in kinds):raise Rechazo('Only one Star Sign of each type can be equipped.')
        else:raise Rechazo('Unknown Star Blessing operation.')
        return gold
    try:_commit(ses,operation)
    except Rechazo as e:aviso(ses,str(e));ses.enviar(paquete(ses.personaje))


def _draw(s,rank,gold,free=False):
    rules=datos()['local_rules']
    if not 1<=rank<=5 or not free and rank not in (1,s['rank']) and not(rank==5 and s['free_v'] or rank==4 and s['free_iv']):raise Rechazo('This Divination level is locked.')
    price=0 if free else coste(s,rank)
    if gold<price:raise Rechazo('Not enough Coins.')
    slot=next((i for i,c in enumerate(s['temp']) if not c),None)
    if slot is None:raise Rechazo('Not enough Divination Outcome slots.')
    tier=random.choices((1,3,5,9),weights=rules['tier_weights'][rank-1],k=1)[0]
    card=99901 if tier==9 else tier*10000+random.randint(1,15)*100+1
    s['temp'][slot]=card
    if rank==5 and s['free_v']:s['free_v']-=1
    elif rank==4 and s['free_iv']:s['free_iv']-=1
    s['rank']=rank+1 if rank<5 and random.randrange(100)<rules['unlock_percent'] else 1
    if s['free_v']:s['rank']=5
    elif s['free_iv']:s['rank']=4
    if not any(s['bingo']):_reset_bingo(s)
    for i,c in enumerate(s['bingo']):
        if c==card//100%100:s['marked'][i]=1
    return gold-price


def _auto_divine(ses):
    p=ses.personaje
    if getattr(p,'_star_auto',False):return
    s=estado(getattr(p,'star_blessing',None))
    if all(s['temp']):aviso(ses,'Not enough Divination Outcome slots.');return
    try:loop=asyncio.get_running_loop()
    except RuntimeError:raise Rechazo('Auto Divine requires an active world session.')
    async def run():
        try:
            while not getattr(ses,'cerrada',False) and ses.personaje is p:
                try:_commit(ses,lambda state,gold:_draw(state,state['rank'],gold))
                except Rechazo as exc:aviso(ses,str(exc));break
                if all(estado(p.star_blessing)['temp']):break
                await asyncio.sleep(AUTO_INTERVAL)
        finally:
            p._star_auto=False;ses._star_auto_task=None
            if not getattr(ses,'cerrada',False) and ses.personaje is p:ses.enviar(paquete(p))
    p._star_auto=True;ses.enviar(paquete(p));ses._star_auto_task=loop.create_task(run())


def _plan(s,recipe):
    consumed=[]
    for card,qty in recipe['materials']:
        if card==99901:
            if s['dust']<qty:raise Rechazo('Not enough Stardust for this exchange.')
            consumed.append((0,qty,card));continue
        slots=[i+1 for i,c in enumerate(s['saved']) if c==card]
        if len(slots)<qty:raise Rechazo('Required Star Signs must be in Star Sign Storage.')
        consumed.extend((i,1,card) for i in slots[:qty])
    return consumed


def exchange(ses,group,index):
    recipes=[r for r in datos()['recipes'].values() if r['group']==group]
    if group not in (1,2) or not 1<=index<=len(recipes):return
    recipe=recipes[index-1]
    try:
        plan=_plan(estado(getattr(ses.personaje,'star_blessing',None)),recipe)
        ses._star_exchange=copy.deepcopy(recipe)
        ses.enviar(paquete(ses.personaje,preview=(plan,recipe['reward'])))
    except Rechazo as e:aviso(ses,str(e));ses._star_exchange=None


def accion(ses,cmd):
    if cmd==21:ses._star_exchange=None;return
    if cmd==13:
        try:_auto_divine(ses)
        except Rechazo as exc:aviso(ses,str(exc))
        return
    # Collect commits between successive draws. The draw loop reads the
    # updated state next time, including any newly awarded free IV credits.
    if cmd!=16 and getattr(ses.personaje,'_star_auto',False):aviso(ses,'Wait until Auto Divine has finished.');return
    def operation(s,gold):
        if cmd==101:
            # Item58283's original description specifies Stardust/Perfect
            # plus a free Divination V. The server odds are local settings.
            if not any(not c for c in s['temp']):raise Rechazo('Not enough Divination Outcome slots.')
            perfect=random.choices((False,True),weights=datos()['local_rules']['star_key_weights'],k=1)[0]
            if perfect:s['temp'][s['temp'].index(0)]=50000+random.randint(1,15)*100+1
            else:s['temp'][s['temp'].index(0)]=99901
            s['free_v']+=1;s['rank']=5
            return gold
        if 1<=cmd<=5:return _draw(s,cmd,gold)
        if cmd==15:
            for c in s['temp']:
                if c==99901:s['dust']+=1
                else:s['power']+=datos()['cards'].get(str(c),{}).get('convert',0)
            s['temp']=[0]*20
        elif cmd==12:
            card=datos()['cards'].get(str(s['working']))
            if not card or not card['upgrade'] or str(s['working']+1) not in datos()['cards']:
                raise Rechazo('This Star Sign cannot be leveled up further.')
            if s['power']<card['upgrade']:raise Rechazo('Not enough Starforce.')
            s['power']-=card['upgrade'];s['working']+=1
        elif cmd==20:
            recipe=getattr(ses,'_star_exchange',None)
            if not recipe:raise Rechazo('Select an exchange first.')
            plan=_plan(s,recipe)
            for slot,qty,card in plan:
                if slot:s['saved'][slot-1]=0
                else:s['dust']-=qty
            dest=next((i for i,c in enumerate(s['saved']) if not c),None)
            if dest is None:raise Rechazo('Star Sign Storage is full.')
            s['saved'][dest]=recipe['reward']
        elif cmd==16:
            total=lineas(s)
            if not total or s['bingo_claimed']:raise Rechazo('There is no unclaimed Star Bingo reward.')
            # Highest matching threshold; amounts/types from the user's IGG
            # screenshot. Six lines grant three free IV draws, not Starforce.
            _,kind,qty=max((r for r in datos()['local_rules']['bingo_awards'] if r[0]<=total),key=lambda r:r[0])
            if kind==1:s['power']+=qty
            elif kind==4:s['free_iv']+=qty;s['rank']=4
            _reset_bingo(s)
        elif cmd==17:
            if not any(s['bingo']):_reset_bingo(s)
            slots=[i for i,m in enumerate(s['marked']) if not m]
            if not slots:raise Rechazo('The Bingo card is complete. Collect its rewards first.')
            s['marked'][random.choice(slots)]=1
        elif cmd==18:_reset_bingo(s)
        else:raise Rechazo('This Star Blessing option is not configured; no currency was spent.')
        return gold
    try:
        consume=None
        if cmd in (101,17):
            import app
            accepted=STAR_KEYS if cmd==101 else (58284,)
            slot=next((slot for slot,item in ses.inventario.items() if item in accepted and 20<=slot<=app._tope_bolsa(ses.inventario)),None)
            if slot is None:raise Rechazo('You need a Star Key.' if cmd==101 else 'You need a Bingo Lucky Draw item.')
            consume={slot:1}
        _commit(ses,operation,consume)
        if cmd==20:ses._star_exchange=None;aviso(ses,'Star Sign exchange completed.')
    except Rechazo as e:aviso(ses,str(e));ses.enviar(paquete(ses.personaje))
