"""League War: original UI/maps/schedule and screenshot-verified redemption.

Battle scoring, registration length and settlement amounts are explicitly local
compatibility settings in league_war.json, authorized by Karma. They are not
claimed as recovered IGG server formulas. C2S158/159/15A/15B, S2C173..177.
"""
import copy
import datetime as dt
import functools
import json
from pathlib import Path
import secrets
import struct
import time
import random

STAGES=frozenset(range(265,273))
_DB=None
_ROUND=None
_ROOMS={}


@functools.lru_cache(maxsize=1)
def config():return json.loads((Path(__file__).parent/'plantillas/league_war.json').read_text('utf8'))
def _key(s):return '%s:%d'%(s.usuario.casefold(),s.personaje.char_id)
def _notice(s,text):s.enviar(__import__('clases').aviso(text,tipo=0))
def _guild(s):return __import__('gremios').obtener_gremio_de(s.personaje.char_id)
def _sessions():return [s for s in __import__('app')._tw_sesiones() if getattr(s,'personaje',None) and not getattr(s,'desconectado',False)]


def _schema(con):
    con.execute('CREATE TABLE IF NOT EXISTS gvg_rounds(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
    con.execute('CREATE TABLE IF NOT EXISTS gvg_results(run TEXT,stage INTEGER,guild INTEGER,season INTEGER,week INTEGER,'
                'name TEXT,outcome TEXT,repute INTEGER,PRIMARY KEY(run,stage,guild))')
    con.execute('CREATE TABLE IF NOT EXISTS gvg_participants(run TEXT,owner TEXT,character INTEGER,guild INTEGER,'
                'season INTEGER,week INTEGER,points INTEGER,PRIMARY KEY(run,owner,character))')
    con.execute('CREATE TABLE IF NOT EXISTS gvg_wallet(owner TEXT,character INTEGER,points INTEGER DEFAULT 0,'
                'PRIMARY KEY(owner,character))')
    con.execute('CREATE TABLE IF NOT EXISTS gvg_claims(period INTEGER,kind TEXT,owner TEXT,character INTEGER,'
                'PRIMARY KEY(period,kind,owner,character))')


def current():
    global _DB,_ROUND
    import cuentas
    if _DB!=str(cuentas.DB_PATH):
        with cuentas._LOCK,cuentas._get_conn() as con:
            _schema(con);row=con.execute('SELECT payload FROM gvg_rounds ORDER BY rowid DESC LIMIT 1').fetchone()
        _ROUND=json.loads(row[0]) if row else None;_DB=str(cuentas.DB_PATH);_ROOMS.clear()
    return _ROUND


def _save(r,con=None):
    global _ROUND
    if con is None:
        import cuentas
        with cuentas._LOCK,cuentas._get_conn() as own:
            _schema(own);own.execute('INSERT OR REPLACE INTO gvg_rounds VALUES(?,?)',(r['id'],json.dumps(r)))
        cuentas._notificar_cambio(inmediato=True)
        _ROUND=r
    else:con.execute('INSERT OR REPLACE INTO gvg_rounds VALUES(?,?)',(r['id'],json.dumps(r)))


def phase(r=None,now=None):
    r=current() if r is None else r;now=time.time() if now is None else now
    if not r or r['state']=='done':return 'closed'
    return 'registration' if now<r['start'] else ('battle' if now<r['end'] else 'ending')


def periods(stamp=None):
    # Stable four-week seasons anchored to Monday 1970-01-05, in server time.
    day=dt.datetime.fromtimestamp(time.time() if stamp is None else stamp).date()
    week=(day-dt.date(1970,1,5)).days//7
    return week,week//4


def start(registration=None,duration=None,identity=None,now=None):
    current()
    if phase()!='closed':raise ValueError('League War is already open.')
    now=time.time() if now is None else now;cfg=config()
    registration=cfg['registration_seconds'] if registration is None else max(0,int(registration))
    duration=cfg['duration_seconds'] if duration is None else max(10,int(duration))
    week,season=periods(now+registration)
    r=dict(id=identity or 'gvg:'+secrets.token_hex(8),nonce=secrets.randbelow(2**31-1)+1,
        state='registration',start=now+registration,end=now+registration+duration,week=week,season=season,
        registered=[],matches={str(st):dict(guilds=[],scores={'1':0,'2':0},dead=[],respawns={},summons=[],kills={},members={}) for st in sorted(STAGES)})
    _save(r);_announce('League War Registration has begun');return r


def _announce(text):
    packet=__import__('totem_war').cartel_deslizante(text)
    for s in _sessions():s.enviar(packet)


def _match(s):
    r=current()
    return (r or {}).get('matches',{}).get(str(s.personaje.stage))


def member(s):
    m=_match(s);entry=(m or {}).get('members',{}).get(_key(s))
    if not entry:return None
    g=_guild(s)
    return entry if g and g['guild_id']==entry['guild'] else None


def register(s,stage,cancel=False):
    r=current();g=_guild(s)
    if phase(r)!='registration':raise ValueError('League War registration is closed.')
    if not g or g['lider_char_id']!=s.personaje.char_id:raise ValueError('Only the League Leader may register.')
    if int(g.get('nivel',1))<6:raise ValueError('Your League must be Level 6 or above.')
    if stage not in STAGES:raise ValueError('Unknown League War battlefield.')
    found=any(x['id']==g['guild_id'] for x in r['registered'])
    if cancel:
        if not found:raise ValueError('Your League is not registered.')
        r=copy.deepcopy(r);r['registered']=[x for x in r['registered'] if x['id']!=g['guild_id']]
        _save(r)
        return
    if found:raise ValueError('Your League is already registered.')
    if len(r['registered'])>=16:raise ValueError('All eight League War battlefields are full.')
    r=copy.deepcopy(r);r['registered'].append(dict(id=g['guild_id'],name=g['nombre']))
    _save(r);_notice(s,'Your League has registered. The battlefield is assigned when battle begins.')


def _begin():
    r=current()
    if phase(r)!='battle' or r['state']=='battle':return
    r=copy.deepcopy(r);r['state']='battle'
    pool=list(r['registered']);rank={row[0]:i for i,row in enumerate(ranking(r['season']))}
    random.shuffle(pool);pool.sort(key=lambda g:rank.get(g['id'],len(rank)))
    stages=random.sample(sorted(STAGES),len(STAGES))
    for stage in stages:
        if not pool:break
        first=pool.pop(0);pair=[first]
        if pool:
            nearby=[g for g in pool if abs(rank.get(g['id'],len(rank))-rank.get(first['id'],len(rank)))<=3] or pool
            other=random.choice(nearby);pool.remove(other);pair.append(other)
        r['matches'][str(stage)]['guilds']=pair
    _save(r);_announce('League War has begun!')
    for s in _sessions():
        if getattr(s,'_gvg_ui',False):ui(s)


def enter(s,stage=None):
    _begin();r=current();g=_guild(s)
    if not g or phase(r)!='battle':raise ValueError('League War entry opens when battle begins.')
    found=next(((int(st),m) for st,m in r['matches'].items() if any(x['id']==g['guild_id'] for x in m['guilds'])),None)
    if not found:raise ValueError('Your League is not registered here.')
    if getattr(s,'muerto',False) or getattr(s,'mapa_cargando',False):raise ValueError('Wait until your character is ready.')
    import app,competiciones,daily_events
    if s.personaje.stage in competiciones.MAPAS or s.personaje.stage in daily_events.STAGES or s.personaje.stage==502:
        raise ValueError('Leave your current event first.')
    if app.es_instancia(s.personaje.stage) and s.personaje.stage not in STAGES:raise ValueError('Leave your current instance first.')
    stage,m=found;team=next(i for i,x in enumerate(m['guilds'],1) if x['id']==g['guild_id'])
    r=copy.deepcopy(r);m=r['matches'][str(stage)]
    m['members'].setdefault(_key(s),dict(owner=s.usuario.casefold(),character=s.personaje.char_id,
        guild=g['guild_id'],team=team,played=False))
    _save(r);tile=config()['maps'][str(stage)]['tags'][str(3 if team==1 else 6)][0]
    if s.personaje.stage==stage:competiciones._reubicar(s,stage,tile)
    else:app._sincronizar_cambio_mapa(s,stage,*tile)


def room(stage):
    r=current();m=(r or {}).get('matches',{}).get(str(stage))
    if not m:return __import__('eventos_mundo').EstadoDeMapa(stage)
    key=(r['id'],stage)
    if key in _ROOMS:return _ROOMS[key]
    import combate,eventos_mundo
    e=eventos_mundo.EstadoDeMapa(stage);e.monstruos={}
    for team,row in enumerate(config()['maps'][str(stage)]['objectives'],1):
        eid=93000000+stage*10+team
        monster=combate.Monstruo(eid,3976,'League War Statue',row['tile'],42571,stage=stage)
        monster.gvg_team=team;monster.gvg_round=r['id'];monster.generado=True;monster.agro=0;monster.move_speed=0
        if eid in m['dead']:monster.vivo=False;monster.hp=0
        e.monstruos[eid]=monster
    for row in m.get('summons',[]):
        if row['entity'] in m['dead']:continue
        monster=combate.Monstruo(row['entity'],row['npc_type'],row['name'],row['tile'],row['sprite'],stage=stage)
        monster.gvg_team=row['team'];monster.gvg_round=r['id'];monster.gvg_owner=row['owner'];monster.generado=True
        monster.hp=row.get('hp',monster.hp);monster.agro=0;e.monstruos[monster.entity_id]=monster
    _ROOMS[key]=e;return e


def participating(s):return bool(member(s) and phase()=='battle' and not getattr(s,'muerto',False) and s.personaje.hp>0)


def can_target(s,target):
    if s.personaje.stage not in STAGES:return True
    m=member(s)
    return bool(participating(s) and getattr(target,'gvg_round',None)==current()['id']
                and getattr(target,'gvg_team',m['team'])!=m['team'] and target.vivo)


def motivo_pvp(s,other):
    if s.personaje.stage not in STAGES:return None
    a,b=member(s),member(other)
    if phase()!='battle' or not a or not b:return 'League War is not active for these players'
    if getattr(s,'muerto',False) or getattr(other,'muerto',False) or s.personaje.hp<=0 or other.personaje.hp<=0:return 'Dead player'
    return '' if a['guild']!=b['guild'] else 'Same League'


def _attribute(eid,kind,value):return struct.pack('<HIBBII',0x1d,eid,1,63,kind,value)


def marks(s,public=False,active=None):
    if s.personaje.stage not in STAGES:return ()
    m=member(s);active=participating(s) if active is None else active
    eid=__import__('presencia').entidad_de(s) if public else s.personaje.entity_id
    return (_attribute(eid,1,m['team'] if m and active else 0),
        __import__('competiciones').modo_arena(eid,bool(active)),
        __import__('holy_battlefield').equipo(eid,m['team'] if m and active else 0))


def update(s):
    r=current();m=_match(s);entry=member(s)
    if not m or not entry:return
    eid=s.personaje.entity_id
    packets=list(marks(s))+[_attribute(eid,6,r['nonce'])]
    for i,g in enumerate(m['guilds'],1):
        packets.extend((struct.pack('<HH17s',0x177,i,g['name'].encode('latin1','replace')[:16].ljust(17,b'\0')),
            _attribute(eid,i+1,m['scores'][str(i)]),
            _attribute(eid,i+3,sum(1 for p in _sessions() if p.personaje.stage==s.personaje.stage and (member(p) or {}).get('guild')==g['id']))))
    # Re-sending subtype6 every second recreates native battlefield windows;
    # repeated PvP/team initialization also interrupts attack presentation.
    scene=(r['id'],s.personaje.stage,id(s.personaje))
    previous=getattr(s,'_gvg_scene_packets',(None,()))
    old=set(previous[1]) if previous[0]==scene else set()
    delta=[packet for packet in packets if packet not in old]
    if delta:s.enviar(*delta)
    s._gvg_scene_packets=(scene,tuple(packets))


def loaded(s):
    if s.personaje.stage not in STAGES:
        s.personaje.buffs.pop('gvg_field',None);return
    if not member(s) or phase()=='closed':leave(s);return
    s.monstruos=room(s.personaje.stage).monstruos
    s._gvg_scene_packets=None,None
    import login
    for m in s.monstruos.values():
        if m.vivo:s.enviar(login._npc_spawn(m.entity_id,m.npc_type,m.nombre,(m.tile_x,m.tile_y),sprite=m.sprite,klass=1),
                           __import__('holy_battlefield').equipo(m.entity_id,m.gvg_team,True))
    s.personaje.buffs['gvg_field']={'fin':current()['end'],'hp_pct':100}
    s.enviar(__import__('app')._stats_ses(s));update(s)
    __import__('presencia').notificar_companero_accion(s,*marks(s,True))


def before_travel(s,destination):
    if s.personaje.stage in STAGES and destination!=s.personaje.stage:
        s.enviar(*marks(s,active=False),_attribute(s.personaje.entity_id,6,0))
        __import__('presencia').notificar_companero_accion(s,*marks(s,True,False))
        s.personaje.buffs.pop('gvg_field',None)
        robot=config()['robot']
        if robot in s.inventario.values():
            def remove(con,data):
                slots=[k for k,v in data['inventario'].items() if v==robot]
                for k in slots:
                    data['inventario'].pop(k,None);data['cantidades'].pop(k,None);data['mejoras'].pop(k,None)
            __import__('recent_mall').cambiar(s,{},[],transaccion=remove)
            if s.inventario.get(10)!=robot:s.montado=False
        s.personaje.hp=min(s.personaje.hp,__import__('app')._vida_max(s.personaje))


def portals(stage):
    if stage not in STAGES:return []
    return [dict(entity=94000000+stage*10+i,tile=tile,dibujar=True,gvg_portal=i,radio=2)
            for i,tile in enumerate(config()['maps'][str(stage)]['exits'],1)]


def portal(s,por):
    entry=member(s)
    if not entry:return True
    if por['gvg_portal']!=entry['team']:
        _notice(s,'Use the portal belonging to your League.');return True
    __import__('app')._recorrer_dialogo_mapa(s,'gvg',s.personaje.stage,8371 if entry['team']==1 else 8376)
    return True


def resources(stage):
    if stage not in STAGES:return []
    return [dict(row,nombre_visible='League War Stones') for row in config()['maps'][str(stage)]['mines']]


def populate(stage):
    if stage not in STAGES:return []
    import login
    return [packet for row in resources(stage) for packet in (login.objeto_de_mapa(row),login.objeto_nombrado(row)) if packet]


def use(s,slot):
    if s.inventario.get(slot)==config()['robot'] and s.personaje.stage not in STAGES:
        _notice(s,'This robot can only be used on the League War battlefield.');return True
    if s.inventario.get(slot)!=63519:return False
    import recent_mall
    def credit(con,data):
        _schema(con);con.execute('INSERT INTO gvg_wallet VALUES(?,?,120) ON CONFLICT(owner,character) DO UPDATE SET points=points+120',
                                (s.usuario.casefold(),s.personaje.char_id))
    recent_mall.cambiar(s,{slot:1},[],transaccion=credit)
    _notice(s,'You received 120 League War Reward Points.');ui(s);return True


def leave(s):
    if s.personaje.stage not in STAGES:return
    if getattr(s,'muerto',False):__import__('competiciones')._revivir(s)
    __import__('app')._sincronizar_cambio_mapa(s,41,175,89)


def kill(s,other):
    if not getattr(other,'muerto',False) or other.personaje.hp>0:return
    if motivo_pvp(s,other) not in ('','Dead player'):return
    a,b=member(s),member(other)
    if not a or not b or a['guild']==b['guild'] or phase()!='battle':return
    life=(current()['id'],int(getattr(other,'competicion_vida',0)))
    if getattr(other,'_gvg_counted_death',None)==life:return
    r=copy.deepcopy(current());m=r['matches'][str(s.personaje.stage)]
    now=time.time();history=m.setdefault('kills',{}).setdefault(_key(other),[])
    history[:]=[stamp for stamp in history if now-stamp<120]
    gap=max(0,int(getattr(s,'_gvg_source_level',s.personaje.nivel))-other.personaje.nivel)
    points=(80,40,20,10) if gap<=5 else ((60,30,15,7) if gap<=10 else ((40,20,10,5) if gap<=20 else (20,10,5,1)))
    m['scores'][str(a['team'])]+=points[min(3,len(history))];history.append(now);_save(r)
    other._gvg_counted_death=life
    other._gvg_revive_at=now+5
    for p in _sessions():
        if p.personaje.stage==s.personaje.stage:update(p)


def respawn(s):
    m=member(s)
    if not m:return
    __import__('competiciones')._revivir(s)
    tile=config()['maps'][str(s.personaje.stage)]['tags'][str(3 if m['team']==1 else 6)][0]
    __import__('competiciones')._reubicar(s,s.personaje.stage,tile)


def monster_dead(s,monster):
    if not hasattr(monster,'gvg_team'):return False
    if not participating(s) or monster.gvg_round!=current()['id']:return True
    entry=member(s)
    if entry['team']==monster.gvg_team:return True
    r=copy.deepcopy(current());m=r['matches'][str(s.personaje.stage)]
    if monster.entity_id in m['dead']:return True
    m['dead'].append(monster.entity_id)
    if not hasattr(monster,'gvg_owner'):
        m['scores'][str(entry['team'])]+=config()['points']['statue']
        m.setdefault('respawns',{})[str(monster.entity_id)]=time.time()+config()['statue_respawn']
    _save(r)
    for p in _sessions():
        if p.personaje.stage==s.personaje.stage:update(p)
    return True


def finish(cancel=False):
    global _ROUND
    r=current()
    if not r or r['state']=='done':return False
    r=copy.deepcopy(r);r['state']='done';r['finished']=time.time();r['cancelled']=cancel
    import cuentas
    with cuentas._LOCK,cuentas._get_conn() as con:
        _schema(con);con.execute('BEGIN IMMEDIATE')
        for stage,m in r['matches'].items():
            played={v['guild'] for v in m['members'].values() if v['played']}
            if cancel or len(m['guilds'])!=2 or len(played)!=2:continue
            scores=m['scores'];winner=0 if scores['1']==scores['2'] else (1 if scores['1']>scores['2'] else 2)
            for team,g in enumerate(m['guilds'],1):
                outcome='draw' if not winner else ('win' if winner==team else 'loss')
                inserted=con.execute('INSERT OR IGNORE INTO gvg_results VALUES(?,?,?,?,?,?,?,?)',
                    (r['id'],int(stage),g['id'],r['season'],r['week'],g['name'],outcome,config()['repute'][outcome])).rowcount
                if not inserted:continue
                for v in m['members'].values():
                    if not v['played'] or v['guild']!=g['id']:continue
                    points=config()['rewards'][outcome]
                    con.execute('INSERT INTO gvg_participants VALUES(?,?,?,?,?,?,?)',
                        (r['id'],v['owner'],v['character'],g['id'],r['season'],r['week'],points))
                    con.execute('INSERT INTO gvg_wallet VALUES(?,?,?) ON CONFLICT(owner,character) DO UPDATE SET points=points+excluded.points',
                        (v['owner'],v['character'],points))
        _save(r,con)
    _ROUND=r;cuentas._notificar_cambio(inmediato=True)
    _announce('League War has ended!'+(' (cancelled)' if cancel else ' Results saved.'))
    for s in _sessions():
        if s.personaje.stage in STAGES:
            s.enviar(*marks(s,active=False),_attribute(s.personaje.entity_id,6,0));_notice(s,'League War has ended. Returning to Angel Lyceum in 10 seconds.')
        if getattr(s,'_gvg_ui',False):ui(s)
    return True


def wallet(s,con=None):
    if con is None:
        import cuentas
        with cuentas._get_conn() as con:
            _schema(con);return wallet(s,con)
    row=con.execute('SELECT points FROM gvg_wallet WHERE owner=? AND character=?',(s.usuario.casefold(),s.personaje.char_id)).fetchone()
    return int(row[0]) if row else 0


def ranking(period,kind='season',con=None):
    if con is None:
        import cuentas
        with cuentas._get_conn() as con:
            _schema(con);return ranking(period,kind,con)
    if kind not in ('season','week'):raise ValueError('Unknown period')
    return con.execute('SELECT guild,MAX(name),SUM(repute),SUM(outcome="win"),SUM(outcome="loss"),SUM(outcome="draw") '
                       'FROM gvg_results WHERE '+kind+'=? GROUP BY guild ORDER BY SUM(repute) DESC,guild LIMIT 100',(period,)).fetchall()


def _entitlement(s,kind,con):
    week,season=periods();period=(week if kind=='week' else season)-1
    rows=ranking(period,kind,con)
    for place,row in enumerate(rows[:3]):
        played=con.execute('SELECT 1 FROM gvg_participants WHERE owner=? AND character=? AND guild=? AND '+kind+'=? LIMIT 1',
                           (s.usuario.casefold(),s.personaje.char_id,row[0],period)).fetchone()
        claimed=con.execute('SELECT 1 FROM gvg_claims WHERE period=? AND kind=? AND owner=? AND character=?',
                            (period,kind,s.usuario.casefold(),s.personaje.char_id)).fetchone()
        if played and not claimed:return period,config()['weekly' if kind=='week' else 'season'][place]
    return period,0


def claim(s,kind):
    import cuentas
    with cuentas._LOCK,cuentas._get_conn() as con:
        _schema(con);con.execute('BEGIN IMMEDIATE');period,amount=_entitlement(s,kind,con)
        if not amount:raise ValueError('No unclaimed League War reward for the previous '+kind+'.')
        con.execute('INSERT INTO gvg_claims VALUES(?,?,?,?)',(period,kind,s.usuario.casefold(),s.personaje.char_id))
        con.execute('INSERT INTO gvg_wallet VALUES(?,?,?) ON CONFLICT(owner,character) DO UPDATE SET points=points+excluded.points',
                    (s.usuario.casefold(),s.personaje.char_id,amount))
    cuentas._notificar_cambio(inmediato=True);_notice(s,'League War reward delivered: %d Reward Points.'%amount);ui(s)


def redeem(s,orders):
    import recent_mall,cuentas
    offers={o['id']:o for o in config()['shop']};seen=set();rewards=[];total=0
    if not orders or len(orders)>100:raise ValueError('Invalid redemption batch.')
    for offer,qty in orders:
        if offer in seen or offer not in offers or not 1<=qty<=999:raise ValueError('Invalid redemption offer or quantity.')
        seen.add(offer);row=offers[offer];total+=row['price']*qty;rewards.append((row['item'],qty))
    if total>2_000_000_000:raise ValueError('Redemption total is too large.')
    def pay(con,data):
        _schema(con)
        if wallet(s,con)<total:raise recent_mall.Rechazo('Not enough League War Reward Points.')
        con.execute('UPDATE gvg_wallet SET points=points-? WHERE owner=? AND character=?',(total,s.usuario.casefold(),s.personaje.char_id))
    recent_mall.cambiar(s,{},rewards,transaccion=pay)
    _notice(s,'League War rewards delivered. Used %d Reward Points.'%total);ui(s)


def infuse(s,action):
    if not participating(s):raise ValueError('Enter an active League War first.')
    if action==4:return robot(s)
    if action in (2,3):return summon(s,action)
    if action!=1:raise ValueError('Unknown League War resource action.')
    consume={slot:__import__('app')._cantidades(s).get(slot,1) for slot,item in s.inventario.items() if item==37362 and 20<=slot<=__import__('app')._tope_bolsa(s.inventario)}
    amount=sum(consume.values())//config()['stone_batch']*config()['stone_batch']
    if not amount:raise ValueError('You need at least 100 League War Stones.')
    remaining=amount
    for slot in list(consume):
        take=min(consume[slot],remaining);remaining-=take
        if take:consume[slot]=take
        else:consume.pop(slot)
    r=copy.deepcopy(current());m=r['matches'][str(s.personaje.stage)];m['scores'][str(member(s)['team'])]+=amount//config()['stone_batch']*config()['points']['stone']
    __import__('recent_mall').cambiar(s,consume,[],transaccion=lambda con,data:_save(r,con))
    global _ROUND
    _ROUND=r;_notice(s,'Donated %d League War Stones.'%amount)
    for other in _sessions():
        if other.personaje.stage==s.personaje.stage:update(other)


def production_level(s):
    return max((int(h[1]) for h in s.personaje.habilidades if 20<=int(h[0])<=23 or 26<=int(h[0])<=29 or int(h[0])==31),default=0)


def robot(s):
    ids={int(h[0]) for h in s.personaje.habilidades}
    if not production_level(s) or ids-set(range(20,30))-{31,32}:raise ValueError('Only production characters without combat skills can collect this robot.')
    if config()['robot'] in s.inventario.values():raise ValueError('You already have the League War robot.')
    __import__('recent_mall').cambiar(s,{},[(config()['robot'],1)])


def summon(s,action):
    level=production_level(s)
    if not level:raise ValueError('A production skill is required to summon a mercenary.')
    choices=[row for row in config()['mercenaries'] if row['level']<=level]
    if not choices:raise ValueError('Your production skill is too low.')
    selected=max(choices,key=lambda row:(row['level'],row['npc_type']))
    r=copy.deepcopy(current());m=r['matches'][str(s.personaje.stage)];team=member(s)['team']
    if sum(1 for row in m['summons'] if row['entity'] not in m['dead'] and row['owner']==_key(s))>=3:
        raise ValueError('You already have three active League War mercenaries.')
    consume={};remaining=100
    for slot,item in sorted(s.inventario.items()):
        if item!=37362 or not 20<=slot<=__import__('app')._tope_bolsa(s.inventario):continue
        consume[slot]=min(remaining,__import__('app')._cantidades(s).get(slot,1));remaining-=consume[slot]
        if not remaining:break
    if remaining:raise ValueError('You need 100 League War Stones to summon a mercenary.')
    base=team if action==2 else 3-team
    tag=5 if base==1 else 8;tiles=config()['maps'][str(s.personaje.stage)]['tags'][str(tag)]
    row=dict(selected,entity=95000000+s.personaje.stage*1000+len(m['summons']),team=team,owner=_key(s),tile=tiles[len(m['summons'])%len(tiles)])
    m['summons'].append(row)
    __import__('recent_mall').cambiar(s,consume,[],transaccion=lambda con,data:_save(r,con))
    global _ROUND
    _ROUND=r
    shared=room(s.personaje.stage)
    if row['entity'] not in shared.monstruos:
        monster=__import__('combate').Monstruo(row['entity'],row['npc_type'],row['name'],row['tile'],row['sprite'],stage=s.personaje.stage)
        monster.gvg_team=team;monster.gvg_round=r['id'];monster.gvg_owner=_key(s);monster.generado=True;monster.agro=0
        shared.monstruos[monster.entity_id]=monster
    for player in _sessions():
        if player.personaje.stage==s.personaje.stage:
            player.monstruos=shared.monstruos
            monster=player.monstruos[row['entity']]
            player.enviar(__import__('login')._npc_spawn(monster.entity_id,monster.npc_type,monster.nombre,row['tile'],sprite=monster.sprite,klass=1),
                           __import__('holy_battlefield').equipo(monster.entity_id,team,True))
            if getattr(player,'_sala',None):player._sala=shared


def ui(s):
    r=current();g=_guild(s);gid=g['guild_id'] if g else 0;week,season=periods()
    import cuentas,gremios
    with cuentas._get_conn() as con:
        _schema(con);rows=ranking(season,con=con);balance=wallet(s,con)
        entry=next(((i,row) for i,row in enumerate(rows,1) if row[0]==gid),(0,(0,'',0,0,0,0)))
        week_reward=_entitlement(s,'week',con)[1];season_reward=_entitlement(s,'season',con)[1]
    # 5F9040 passes body offsets0/142/159/193 into5075C0.
    body=bytearray(205)
    if g:body[:142]=gremios.paquete_datos_gremio(g,s.personaje.char_id)[6:148]
    place,row=entry;struct.pack_into('<H',body,146,min(65535,row[2]));body[148:151]=bytes(min(255,n) for n in row[3:6]);struct.pack_into('<H',body,153,place)
    struct.pack_into('<I',body,197,min(2_000_000_000,balance));body[201]=0;body[203]=bool(week_reward);body[204]=bool(season_reward)
    s.enviar(struct.pack('<H',0x174)+body)
    war=[]
    day=dt.datetime.fromtimestamp((r or {}).get('start',time.time()))
    date=day.year*10000+day.month*100+day.day
    start_minutes=day.hour*60+day.minute
    signup=dt.datetime.fromtimestamp((r or {}).get('start',time.time())-config()['registration_seconds'])
    end=dt.datetime.fromtimestamp((r or {}).get('end',time.time()))
    # Native War Plan rows are dates/time slots, not the eight battle maps.
    for stage in (265,):
        registered=any(x['id']==gid for x in (r or {}).get('registered',[]));state=phase(r)
        status=1 if state=='closed' else (4 if registered and state=='registration' else (2 if registered else 0))
        flags=1 if state=='registration' else (2 if state=='battle' and registered else 0)
        # REA6CCCB0 renders YYYYMMDD at+12, signup minutes at+16/+20,
        # battle minutes at+24/+28. They are not timestamps or guild IDs.
        war.append(struct.pack('<10I',stage,1,(r or {}).get('nonce',0),date,
            signup.hour*60+signup.minute,start_minutes,start_minutes,end.hour*60+end.minute,flags,status))
    s.enviar(struct.pack('<HI',0x173,len(war))+b''.join(war))
    s.enviar(struct.pack('<HI',0x175,len(rows))+b''.join(struct.pack('<I17sII',row[0],row[1].encode('latin1','replace')[:16].ljust(17,b'\0'),row[2],i) for i,row in enumerate(rows,1)))
    offers=config()['shop'];s.enviar(struct.pack('<HI',0x176,len(offers))+b''.join(struct.pack('<III',o['id'],o['item'],o['price']) for o in offers))


def process(s,opcode,body):
    special=opcode in (0x158,0x159,0x15a,0x15b) or opcode==0x16 and len(body)==5 and body[0] in (64,65,66,67)
    if not special:return False
    if getattr(s,'rol',None)!='mundo' or not getattr(s,'personaje',None):return True
    try:
        if opcode==0x16:
            if body[0]==64:s._gvg_ui=True;ui(s)
            elif body[0]==65:s._gvg_ui=False
            else:claim(s,'week' if body[0]==66 else 'season')
        elif opcode in (0x158,0x159) and len(body)==9:
            channel,stage,nonce=struct.unpack('<BII',body);r=current()
            if channel or not r or nonce!=r['nonce']:raise ValueError('This League War listing has expired. Reopen it.')
            if opcode==0x158:
                g=_guild(s);m=r['matches'].get(str(stage),{})
                cancel=bool(g and any(x['id']==g['guild_id'] for x in r['registered']))
                register(s,stage,cancel);ui(s)
            else:enter(s,stage)
        elif opcode==0x15a and len(body)==7:
            kind,action,count=struct.unpack('<IBH',body)
            if kind==10:infuse(s,action)
        elif opcode==0x15b and len(body)>=4:
            count=struct.unpack_from('<I',body)[0]
            if count>100 or len(body)!=4+count*8:raise ValueError('Invalid redemption packet.')
            redeem(s,[struct.unpack_from('<II',body,4+i*8) for i in range(count)])
    except (ValueError,__import__('recent_mall').Rechazo) as exc:_notice(s,str(exc))
    return True


def cron(now=None):
    now=dt.datetime.fromtimestamp(time.time()) if now is None else now;stamp=now.timestamp();r=current()
    for slot in config()['schedules']:
        if now.weekday()!=slot['weekday']:continue
        h,m=map(int,slot['start'].split(':'));start_at=now.replace(hour=h,minute=m,second=0,microsecond=0).timestamp()
        identity='gvg:'+str(int(start_at))
        if start_at-config()['registration_seconds']<=stamp<start_at and phase(r)=='closed' and (r or {}).get('id')!=identity:
            r=start(int(start_at-stamp),identity=identity,now=stamp)
    if not r:return
    if phase(r)=='battle':
        _begin()
        changed=False;r=copy.deepcopy(current())
        for s in _sessions():
            if s.personaje.stage in STAGES and member(s):
                entry=r['matches'][str(s.personaje.stage)]['members'][_key(s)]
                if not entry['played']:entry['played']=True;changed=True
                if getattr(s,'muerto',False) and stamp>=getattr(s,'_gvg_revive_at',stamp):respawn(s)
                update(s)
        if changed:_save(r)
        tick()
    elif phase(r)=='ending':finish()
    elif phase(r)=='closed' and stamp>=r.get('finished',stamp)+10:
        for s in _sessions():
            if s.personaje.stage in STAGES:leave(s)


def tick():
    """One shared AI tick per field; statues and mercenaries never use mob loot."""
    r=copy.deepcopy(current());changed=False
    import combate,login,transitable
    for stage,match in r['matches'].items():
        stage=int(stage);players=[s for s in _sessions() if s.personaje.stage==stage and member(s)]
        if not players:continue
        shared=room(stage)
        for eid,deadline in list(match.get('respawns',{}).items()):
            if time.time()<deadline:continue
            monster=shared.monstruos.get(int(eid))
            if monster:
                monster.vivo=True;monster.hp=monster.hp_max
                for s in players:s.enviar(login._npc_spawn(monster.entity_id,monster.npc_type,monster.nombre,(monster.tile_x,monster.tile_y),sprite=monster.sprite,klass=1),
                                          __import__('holy_battlefield').equipo(monster.entity_id,monster.gvg_team,True))
            if int(eid) in match['dead']:match['dead'].remove(int(eid))
            del match['respawns'][eid];changed=True
        for row in match.get('summons',[]):
            monster=shared.monstruos.get(row['entity'])
            if not monster or not monster.vivo:continue
            targets=[(s.personaje,s) for s in players if participating(s) and member(s)['team']!=row['team']]
            targets.extend((other,None) for other in shared.monstruos.values() if other.vivo and other.gvg_team!=row['team'])
            if not targets:continue
            target,session=min(targets,key=lambda pair:max(abs(pair[0].tile_x-monster.tile_x),abs(pair[0].tile_y-monster.tile_y)))
            distance=max(abs(target.tile_x-monster.tile_x),abs(target.tile_y-monster.tile_y))
            if distance>2:
                before=(monster.tile_x,monster.tile_y)
                tile=transitable.avanzar(stage,before,(target.tile_x,target.tile_y),3,parar_a=2)
                monster.tile_x,monster.tile_y=tile;monster.tile=list(tile)
                from codec import Msg
                packet=Msg.registry[(5,'s2c','*')].build(entity_id=monster.entity_id,cur_x=before[0]*32,cur_y=before[1]*32,dst_x=tile[0]*32,dst_y=tile[1]*32,speed=max(50,monster.move_speed))
                for s in players:s.enviar(packet)
            else:
                owner=next((s for s in players if _key(s)==row['owner']),None)
                if owner is None:continue
                if session:
                    import pvp_liga
                    damage=pvp_liga.dano_pvp(monster.pegar(),__import__('app').defensa_jugador(session),1,.03)
                    owner._gvg_source_level=row['level']
                    try:pvp_liga._aplicar(owner,session,damage,False,True,1,0,False,origen_eid=monster.entity_id)
                    finally:owner.__dict__.pop('_gvg_source_level',None)
                    # _aplicar can save the live round through kill(); do not overwrite it below.
                    latest=current()['matches'][str(stage)]
                    match['scores']=copy.deepcopy(latest['scores']);match['kills']=copy.deepcopy(latest.get('kills',{}))
                else:
                    target.hp=max(0,target.hp-max(1,monster.pegar()-target.defensa//2));target.vivo=target.hp>0
                    for s in players:s.enviar(combate.atributo(target.entity_id,target.porcentaje))
                    if not target.vivo:
                        match['dead'].append(target.entity_id)
                        if not hasattr(target,'gvg_owner'):
                            match['scores'][str(row['team'])]+=config()['points']['statue']
                            match['respawns'][str(target.entity_id)]=time.time()+config()['statue_respawn']
                        for s in players:s.enviar(combate.despawn_monstruo(target.entity_id))
            row['tile']=[monster.tile_x,monster.tile_y];row['hp']=monster.hp;changed=True
    if changed:_save(r)


def gm(s,args):
    try:
        action=args[0].lower() if args else 'status'
        if action=='start':start(int(args[1]) if len(args)>1 else 60,int(args[2]) if len(args)>2 else None)
        elif action=='register':register(s,264+int(args[1]) if len(args)>1 else 265)
        elif action=='enter':enter(s)
        elif action=='finish':finish()
        elif action=='stop':finish(cancel=True)
        elif action=='status':_notice(s,'League War: '+phase());ui(s)
        else:raise ValueError('Use /gvg start [registration seconds] [battle seconds], register [1..8], enter, finish, stop or status.')
    except (ValueError,IndexError) as exc:_notice(s,str(exc))
