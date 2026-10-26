"""Native Daily Events calendar, shared rooms and recurring rounds.

REA 59AB30 -> C2S014B; 6734F0 -> C2S014A(U32 entry ID).
S2C0157 has 18 DWORDs; 6CBCB0 reorders entry/help identifiers. The
Native maps supply generators, gates and treasures. The controller owns
registration, team rules, objectives and settlement.
"""
import datetime as dt
import struct
import copy
import functools
import json
import pathlib
import time
import uuid

_DB=None
_ROUNDS={}
_ROOMS={}
_ANUNCIOS_BATALLA=set()
_ANUNCIOS_FIN=set()
ALIASES={'bleach':0,'faction':1,'guard':2,'swindle':3,'quick':4,'joy':5,'happiness':6}


def anuncio_banner(texto):
    try:
        import app, totem_war
        app._tw_difundir(totem_war.cartel_deslizante(texto))
    except Exception:
        pass

# Original string.xml titles/help and stage.xml maps. The weekly schedule
# is configured separately; the original server's timetable is not in MPCs.
GAMES=(
    ('Bleach of Red',((177,3039,3040,1,119),(184,3053,3054,120,259),(185,3055,3056,260,400),(373,3702,3703,401,9999))),
    ('Faction Showdown',((178,3041,3042,1,9999),)),
    ('Angelic Guard',((189,3074,3075,1,119),(188,3070,3071,120,259),(179,3043,3044,260,400),(374,3704,3705,401,9999))),
    ('Swindle World',((191,3076,3077,1,119),(190,3072,3073,120,259),(180,3045,3046,260,400),(375,3706,3707,401,9999))),
    ('Quick Reflexes',((181,3047,3048,1,169),(371,3699,3710,170,9999))),
    ('Joy Angel Village',((182,3049,3050,1,219),(372,3700,3701,170,9999))),
    ('Happiness Guard',((183,3051,3052,1,119),(186,3063,3064,120,259),(187,3065,3066,260,400),(376,3708,3709,401,9999))),
)
STAGES=frozenset(r[0] for _,rows in GAMES for r in rows)


@functools.lru_cache(maxsize=1)
def programacion():
    return json.loads((pathlib.Path(__file__).parent/'plantillas/daily_schedule.json').read_text('utf8'))


def calendario():
    rows=[]
    cfg=programacion()
    for slot in cfg['slots']:
        name,brackets=GAMES[ALIASES[slot['alias']]]
        hour,minute=map(int,slot['start'].split(':'));start=hour*60+minute
        for stage,title,help_id,minimum,maximum in brackets:
            index=len(rows)+1
            rows.append(dict(id=index,entry=index,day=slot['day'],name=name,stage=stage,title=title,
                             help=help_id,minimum=minimum,maximum=maximum,
                             registration=start-cfg['registration_minutes'],start=start,end=start+cfg['duration_minutes']))
    return rows


def paquetes():
    out=[]
    rows=calendario()
    for r in rows:
        h=lambda minutes:(minutes//60,minutes%60)
        # packet+62 -> row+64, packet+66 -> row+60 (entry command).
        values=(r['day'],*h(r['registration']),*h(r['start']),*h(r['start']),*h(r['end']),
                r['maximum'],r['minimum'],r['stage'],r['title'],r['help'],r['id'],len(rows),r['entry'],
                1 if fase(actual(r['stage'])) in ('registro','combate') and r['day']==(dt.datetime.now().weekday()+1)%7 else 0)
        out.append(struct.pack('<H18I',0x157,*values))
    return out


def procesar(ses,opcode,body):
    if opcode not in (0x14a,0x14b):return False
    if getattr(ses,'rol',None)!='mundo' or not getattr(ses,'personaje',None):return True
    if opcode==0x14b:
        if not body:
            cron();ses._daily_calendar=True;ses.enviar(*paquetes())
    elif len(body)==4:
        key=struct.unpack('<I',body)[0]
        r=next((r for r in calendario() if r['entry']==key),None)
        if r:
            try:entrar(ses,r['stage'])
            except Rechazo as exc:aviso(ses,str(exc))
    return True


def claim(ses):
    import cuentas,recent_mall
    if not recent_mall.cerca(ses,'Daily Events Clerk'):
        aviso(ses,'Talk to Daily Events Clerk to collect your rewards.');return
    _ensure()
    with cuentas._get_conn() as con:
        rows=con.execute('SELECT round_id,item FROM daily_rewards WHERE usuario=? AND char_id=? AND claimed=0',
                         (ses.usuario,ses.personaje.char_id)).fetchall()
    if not rows:
        aviso(ses,'You do not have a winning certificate! You can acquire it by participating in our Daily Events!');return
    def once(con,data):
        for rid,item in rows:
            cur=con.execute('UPDATE daily_rewards SET claimed=1 WHERE round_id=? AND usuario=? AND char_id=? AND claimed=0',
                            (rid,ses.usuario,ses.personaje.char_id))
            if cur.rowcount!=1:raise recent_mall.Rechazo('This reward has already been claimed.')
    try:
        recent_mall.cambiar(ses,{},[(item,1) for _,item in rows],transaccion=once)
        aviso(ses,'Daily Event rewards delivered. Congratulations!')
    except recent_mall.Rechazo as exc:aviso(ses,str(exc))


class Rechazo(ValueError):pass


def aviso(ses,text):
    import clases
    ses.enviar(clases.aviso(text,tipo=0))


def _schema(con):
    con.execute('CREATE TABLE IF NOT EXISTS daily_rounds(id TEXT PRIMARY KEY,stage INTEGER,data TEXT)')
    con.execute('CREATE TABLE IF NOT EXISTS daily_rewards(round_id TEXT,usuario TEXT,char_id INTEGER,item INTEGER,'
                'claimed INTEGER DEFAULT 0,PRIMARY KEY(round_id,usuario,char_id))')


def _ensure():
    global _DB,_ROUNDS,_ROOMS
    import cuentas
    key=str(cuentas.DB_PATH)
    if _DB==key:return
    with cuentas._LOCK,cuentas._get_conn() as con:
        _schema(con)
        records=[json.loads(row[0]) for row in con.execute('SELECT data FROM daily_rounds')]
        # Rooms are authoritative in memory. An interrupted round cannot
        # award a defense victory after restarting with a pristine tower.
        for r in records:
            if r['phase'] not in ('ended','cancelled'):
                r['phase']='cancelled';r['reason']='server restart'
                con.execute('UPDATE daily_rounds SET data=? WHERE id=?',(json.dumps(r),r['id']))
    _DB=key;_ROUNDS={r['id']:r for r in records};_ROOMS={}


def _save(r):
    import cuentas
    with cuentas._LOCK,cuentas._get_conn() as con:
        _schema(con)
        con.execute('INSERT OR REPLACE INTO daily_rounds VALUES(?,?,?)',(r['id'],r['stage'],json.dumps(r)))
    _ROUNDS[r['id']]=r


def actual(stage):
    _ensure()
    return max((r for r in _ROUNDS.values() if r['stage']==stage),key=lambda r:r['start'],default=None)


def fase(r,now=None):
    if not r or r['phase'] in ('ended','cancelled'):return 'cerrada'
    now=time.time() if now is None else now
    return 'registro' if now<r['start'] else 'combate' if now<r['end'] else 'final'


def info(stage):
    for kind,(name,brackets) in enumerate(GAMES):
        for tier,row in enumerate(brackets):
            if row[0]==stage:return dict(kind=kind,name=name,tier=tier,stage=stage,minimum=row[3],maximum=row[4])
    return None


def iniciar(stage,minutes=30,registration=5,start=None,identity=None):
    _ensure();meta=info(stage)
    if not meta:raise Rechazo('Unknown Daily Event.')
    if fase(actual(stage))!='cerrada':raise Rechazo('This Daily Event is already open.')
    begin=time.time()+registration*60 if start is None else start
    r=dict(meta,id=identity or uuid.uuid4().hex,start=begin,end=begin+max(1,minutes)*60,
           phase='registration',members={},scores={},dead=[],completed=False,wave=0,next_wave=begin,
           winners=[],reason='',return_at=0)
    _save(r)
    return r


def iniciar_evento(alias,minutes=30,registration=5,start=None,identity=None):
    """Open every native level bracket at the same instant, atomically."""
    _ensure()
    import cuentas
    if alias not in ALIASES:raise Rechazo('Unknown Daily Event.')
    stages=[row[0] for row in GAMES[ALIASES[alias]][1]]
    if any(fase(actual(stage))!='cerrada' for stage in stages):raise Rechazo('This Daily Event is already open.')
    begin=time.time()+registration*60 if start is None else start
    family=identity or uuid.uuid4().hex
    rounds=[dict(info(stage),id=family+'-%d'%stage,family=family,start=begin,
                 end=begin+max(1,minutes)*60,phase='registration' if begin>time.time() else 'battle',members={},scores={},dead=[],
                 completed=False,wave=0,next_wave=begin,winners=[],reason='',return_at=0)
            for stage in stages]
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE');_schema(con)
        for r in rounds:con.execute('INSERT INTO daily_rounds VALUES(?,?,?)',(r['id'],r['stage'],json.dumps(r)))
    _ROUNDS.update({r['id']:r for r in rounds})
    name=GAMES[ALIASES[alias]][0]
    if begin>time.time():
        anuncio_banner('[Daily Event] %s registration is open! Sign up on the Daily Events board!'%name)
    else:
        anuncio_banner('[Daily Event] %s battle has begun! Enter now!'%name)
    return rounds


def _key(ses):return '%s:%d'%(ses.usuario.casefold(),ses.personaje.char_id)


def _sessions(r):
    import app
    return [s for s in app._tw_sesiones() if getattr(s,'personaje',None) and s.personaje.stage==r['stage']
            and getattr(s,'_daily_round',None)==r['id'] and _key(s) in r['members']]


def _spawn_tile(r,team=1):
    import eventos
    if r['kind']==3:
        tag={1:2,2:4,3:9,4:3}.get(team,2)
    elif r['kind'] in (0,1):
        tag=team
    else:
        tag=1
    tiles=eventos.casillas_de_tag(r['stage'],tag) or eventos.casillas_de_tag(r['stage'],1)
    if not tiles:raise Rechazo('The Daily Event entrance is unavailable.')
    return tuple(tiles[0])


def entrar(ses,stage):
    import app,competiciones
    p=ses.personaje;r=actual(stage);meta=info(stage)
    if not meta or not r:raise Rechazo('This Daily Event is not accepting registrations.')
    if getattr(ses,'muerto',False) or getattr(ses,'mapa_cargando',False):raise Rechazo('Wait until your character is ready.')
    if p.stage in competiciones.MAPAS:raise Rechazo('Leave your current battlefield first.')
    if p.stage in STAGES and p.stage!=stage:raise Rechazo('Leave your current Daily Event first.')
    if not meta['minimum']<=p.nivel<=meta['maximum']:
        alias_rows=GAMES[meta['kind']][1]
        matching_stage=next((row[0] for row in alias_rows if row[3]<=p.nivel<=row[4]),None)
        if matching_stage and matching_stage!=stage:
            r_match=actual(matching_stage)
            if r_match and fase(r_match) in ('registro','combate'):
                stage=matching_stage;r=r_match;meta=info(stage)
    if not meta['minimum']<=p.nivel<=meta['maximum']:raise Rechazo('Your level does not match this Daily Event.')
    key=_key(ses);member=r['members'].get(key)
    if fase(r) not in ('registro', 'combate'):
        raise Rechazo('Registration for this Daily Event is closed.')
    if member is None:
        team=1
        if r['kind']==0:
            team=min((1,2),key=lambda t:sum(m['team']==t for m in r['members'].values()))
        if r['kind'] in (1,3):
            team={'Aurora':1,'Beasts':2,'Steel':3,'Shadow':4}.get(p.faction,0)
            if not team:
                team=1 if r['kind']==3 else 0
            if not team:raise Rechazo('Join a faction before entering %s.'%r['name'])
        tile=_spawn_tile(r,team)
        new=copy.deepcopy(r)
        new['members'][key]=dict(usuario=ses.usuario,char_id=p.char_id,name=p.nombre,level=p.nivel,
                                 team=team,kills=0,deaths=0,score=0,joined=time.time())
        _save(new);r=new
    else:tile=_spawn_tile(r,member['team'])
    ses._daily_round=r['id'];ses._daily_unsafe=False
    app._viajar_por_portal(ses,'daily',dict(destino=stage,llegada=tile))


@functools.lru_cache(maxsize=None)
def datos(stage):
    return json.loads((pathlib.Path(__file__).parent/('plantillas/daily_%d.json'%stage)).read_text('utf8'))


def portales(stage):
    return datos(stage).get('portals',[]) if stage in STAGES else []


def sala(ses):
    r=actual(ses.personaje.stage)
    return room(r) if r else __import__('eventos_mundo').EstadoDeMapa(ses.personaje.stage)


def room(r):
    if r['id'] in _ROOMS:return _ROOMS[r['id']]
    import eventos_mundo,combate
    e=eventos_mundo.EstadoDeMapa(r['stage']);e.monstruos={}
    for row in datos(r['stage'])['spawns']:
        if not row.get('monstruo') or (row.get('apagado') and row.get('zona') not in r.get('released',[])):continue
        m=combate.Monstruo(row['entity_id'],row['npc_type'],row['nombre'],row['tile'],row['sprite'],stage=r['stage'])
        m.zona_plantilla=row.get('zona',0);m.daily_round=r['id'];m.daily_respawn=row.get('respawn',30)
        if row.get('apagado'):m.generado=True;m.zona_generador=row.get('zona',0)
        if m.entity_id in r['dead']:m.vivo=False;m.hp=0
        e.monstruos[m.entity_id]=m
    # Native tower/slarm types and native map tags, not decorative stand-ins.
    if r['kind'] in (1,6):
        objectives=range(1,5) if r['kind']==1 else (1,)
        import eventos
        for team in objectives:
            typ=9238 if r['kind']==1 else (9264,9359,9360,23221)[r['tier']]
            tag=10+team if r['kind']==1 else 9
            tile=(eventos.casillas_de_tag(r['stage'],tag) or [_spawn_tile(r,team)])[0]
            row=__import__('house_services').xml_rows('monster.xml')[typ]
            eid=89000000+r['stage']*10+team
            m=combate.Monstruo(eid,typ,row['\u540d\u7a31'],tile,int(row['\u5716\u865f']),stage=r['stage'])
            m.daily_objective=True;m.daily_team=team;m.daily_round=r['id'];m.agro=0;m.move_speed=0;m.generado=True
            e.monstruos[eid]=m
    _ROOMS[r['id']]=e
    return e


def generar(ses,stage,tag):
    """Guard/Swindle death events release a finite native chest group once."""
    if stage not in STAGES:return False
    r=actual(stage)
    if not r or r['kind'] not in (2,3):return False
    rows=[row for row in datos(stage)['spawns'] if row.get('apagado')
          and row.get('zona')==tag and row.get('npc_type') in (9223,9224)]
    if not rows:return False
    if fase(r)!='combate' or _key(ses) not in r['members']:return True
    if tag in r.get('released',[]):return True
    import combate,login
    e=room(r)
    # Persist activation before publishing. Re-entry can reconstruct the
    # same IDs; repeated death/GENERATE packets cannot refill claimed chests.
    r.setdefault('released',[]).append(tag)
    try:_save(r)
    except Exception:
        r['released'].remove(tag);raise
    packets=[]
    for row in rows:
        m=combate.Monstruo(row['entity_id'],row['npc_type'],row['nombre'],row['tile'],row['sprite'],stage=stage)
        m.generado=True;m.zona_generador=tag;m.zona_plantilla=tag;m.daily_round=r['id']
        if m.entity_id in r['dead']:m.vivo=False;m.hp=0
        e.monstruos[m.entity_id]=m
        if m.vivo:packets.append(login._npc_spawn(m.entity_id,m.npc_type,m.nombre,row['tile'],sprite=m.sprite,klass=1))
    for player in _sessions(r):player.enviar(*packets)
    return True


def monstruos(stage):
    r=actual(stage)
    return room(r).monstruos if r else {}


def al_entrar(ses):
    p=ses.personaje
    if p.stage not in STAGES:
        p.buffs.pop('daily_joy',None);ses._daily_round=None;ses._daily_aura=False;return
    r=actual(p.stage)
    if not r or _key(ses) not in r['members'] or fase(r)=='cerrada':
        _return(ses);return
    ses._daily_round=r['id']
    ses._daily_presence=(r['id'],max(time.time(),r['start']))
    ses.monstruos=room(r).monstruos
    ses.enviar(struct.pack('<HI',0x16a,max(0,int(r['end']-time.time()))))
    if r['kind']==5:p.buffs['daily_joy']={'fin':r['end'],'recoleccion_pct':90}
    from login import _npc_spawn
    for m in ses.monstruos.values():
        if getattr(m,'daily_objective',False):ses.enviar(_npc_spawn(m.entity_id,m.npc_type,m.nombre,(m.tile_x,m.tile_y),sprite=m.sprite,klass=1))
    aura(ses,fase(r)=='combate' and r['kind']==0)


def marcas(ses,public=False,active=None):
    p=getattr(ses,'personaje',None)
    if not p or p.stage not in STAGES:return ()
    r=actual(p.stage);member=(r or {}).get('members',{}).get(_key(ses))
    if active is None:active=bool(member and fase(r)=='combate' and (r['kind']==0 or r['kind']==3 and getattr(ses,'_daily_unsafe',False)))
    eid=__import__('presencia').entidad_de(ses) if public else p.entity_id
    packets=[__import__('competiciones').modo_arena(eid,active),struct.pack('<HIBBII',0x1d,eid,1,42,eid,int(active))]
    if r and r['kind']==0:
        packets.append(__import__('holy_battlefield').equipo(eid,member['team'] if member and active else 0))
    return tuple(packets)


def aura(ses,active):
    import presencia,competiciones
    p=ses.personaje
    ses.enviar(*marcas(ses,active=active));ses._daily_aura=active
    for other in presencia._vivas(presencia.clave_de_mapa(ses,p.stage)):
        if other is not ses:other.enviar(*marcas(ses,True,active))


def antes_viajar(ses,destination):
    if ses.personaje.stage in STAGES and destination!=ses.personaje.stage:
        ses._daily_round=None
        ses._daily_presence=None
        if getattr(ses,'_daily_aura',False):aura(ses,False)
        ses.personaje.buffs.pop('daily_joy',None)
        ses.enviar(struct.pack('<H',0x16b));ses._daily_unsafe=False


def _return(ses):
    import app,eventos,competiciones
    if getattr(ses,'muerto',False):competiciones._revivir(ses)
    app._viajar_por_portal(ses,'daily',dict(destino=41,llegada=(eventos.casillas_de_tag(41,1) or [(161,93)])[0]))


def motivo_pvp(ses,other):
    if ses.personaje.stage not in STAGES:return None
    r=actual(ses.personaje.stage)
    if fase(r)!='combate':return 'Daily Event is not fighting'
    a=r['members'].get(_key(ses));b=r['members'].get(_key(other))
    if not a or not b:return 'Unregistered Daily Event player'
    if getattr(ses,'muerto',False) or getattr(other,'muerto',False):return 'Dead player'
    if r['kind']==0:return '' if a['team']!=b['team'] else 'Same Daily Event team'
    if r['kind']==3:
        if a['team']==b['team']:return 'Same faction'
        return '' if getattr(ses,'_daily_unsafe',False) and getattr(other,'_daily_unsafe',False) else 'Daily Event safe zone'
    return 'This Daily Event does not permit player combat'


def can_target(ses,target):
    if getattr(ses.personaje,'stage',0) not in STAGES:return True
    r=actual(ses.personaje.stage)
    if fase(r)!='combate' or _key(ses) not in r['members']:return False
    if getattr(target,'daily_objective',False):return False
    if r['kind']==1:
        team=r['members'][_key(ses)]['team'];typ=target.npc_type
        bomb={9096:1,9097:2,9098:3,9099:4}.get(typ)
        switch={9227:1,9228:2,9229:3,9095:4}.get(typ)
        if bomb:return bomb!=team
        if switch:return switch==team
    return True


def basic_only(stage):return stage in (181,371)


def participando(ses):
    stage=getattr(getattr(ses,'personaje',None),'stage',0)
    if stage not in STAGES:return False
    r=actual(stage)
    return bool(fase(r)=='combate' and _key(ses) in r['members'])


def controls_ai(ses,m):
    """Keep objectives/waiting rounds out of ordinary wandering/aggro AI."""
    stage=getattr(getattr(ses,'personaje',None),'stage',0)
    if stage not in STAGES:return False
    r=actual(stage)
    if fase(r)!='combate' or getattr(m,'daily_objective',False):return True
    if r['kind']==1:return True  # Switches are passive; bomb movement is server-owned.
    return r['kind']==6 and not getattr(m,'en_combate_con',None)


def pk(ses):
    r=actual(ses.personaje.stage)
    if r and r['kind']==3 and fase(r)=='combate' and _key(ses) in r['members']:
        ses._daily_unsafe=True;aura(ses,True)


def baja(ses,other):
    r=actual(ses.personaje.stage)
    if not r:return
    a=r['members'].get(_key(ses));b=r['members'].get(_key(other))
    if not a or not b:return
    a['kills']+=1;b['deaths']+=1
    if r['kind']==0:r['scores'][str(a['team'])]=r['scores'].get(str(a['team']),0)+1
    _save(r)
    import competiciones,app
    competiciones._revivir(other)
    if r['kind']==3:other._daily_unsafe=False;aura(other,False)
    app._viajar_dentro_del_mapa(other,'daily',dict(llegada=_spawn_tile(r,b['team'])))


def muerte_monstruo(ses,m):
    if getattr(getattr(ses,'personaje',None),'stage',0) not in STAGES:return
    r=actual(ses.personaje.stage)
    if fase(r)!='combate':return
    if r['kind'] not in (4,5):
        if m.entity_id in r['dead']:return
        r['dead'].append(m.entity_id)
    member=r['members'].get(_key(ses))
    if member:member['score']+=1
    bosses=set(datos(r['stage'])['bosses'])
    if bosses and bosses.issubset(r['dead']) and not r['completed']:
        r['completed']=True
        for player in _sessions(r):aviso(player,'All Daily Event guardians have been defeated. Collect the treasures before time runs out!')
    _save(r)


def _finish(r,cancel=False):
    import cuentas
    if r['phase'] in ('ended','cancelled'):return
    teams=[]
    if not cancel and r['kind']==0:
        scores={t:r['scores'].get(str(t),0) for t in (1,2)}
        if scores[1]!=scores[2]:teams=[max(scores,key=scores.get)]
    if not cancel and r['kind']==1:
        objs=[m for m in room(r).monstruos.values() if getattr(m,'daily_objective',False)]
        if objs:
            best=max(m.hp for m in objs);teams=[m.daily_team for m in objs if m.hp==best]
            if len(teams)!=1:teams=[]
    if not cancel and r['kind']==6 and any(m.vivo and m.hp>0 for m in room(r).monstruos.values() if getattr(m,'daily_objective',False)):teams=[1]
    new=copy.deepcopy(r);new['phase']='cancelled' if cancel else 'ended';new['winners']=teams;new['return_at']=time.time()+10
    eligible={_key(s) for s in _sessions(r)}
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE');_schema(con)
        con.execute('INSERT OR REPLACE INTO daily_rounds VALUES(?,?,?)',(new['id'],new['stage'],json.dumps(new)))
        for key,m in new['members'].items():
            if m['team'] not in teams or key not in eligible:continue
            # Native Dailies Coin Bag tiers. One bag is a documented local
            # compatibility quantity while IGG's server reward counts are absent.
            item=64716 if m['level']<120 else 42591 if m['level']<260 else 42592 if m['level']<=400 else 42593
            con.execute('INSERT OR IGNORE INTO daily_rewards VALUES(?,?,?,?,0)',(new['id'],m['usuario'],m['char_id'],item))
    _ROUNDS[new['id']]=new
    cuentas._notificar_cambio(inmediato=True)
    for player in _sessions(new):
        aura(player,False)
        player.personaje.buffs.pop('daily_joy',None)
        if getattr(player,'recoleccion',None):__import__('app')._parar_recoleccion(player)
        aviso(player,new['name']+' has ended.'+(' Claim your winning reward at Daily Events Clerk.' if new['members'][_key(player)]['team'] in teams else ''))
    family=r.get('family',r['id'])
    if not cancel and family not in _ANUNCIOS_FIN:
        _ANUNCIOS_FIN.add(family)
        anuncio_banner('[Daily Event] %s has ended! Claim your rewards at the Daily Events Clerk!'%new['name'])


def _mechanics(r,now):
    e=room(r);players=_sessions(r)
    if not players:return
    if now<r.get('_tick',0)+1:return
    r['_tick']=now
    if r['kind']==3:
        for player in players:
            m_team=r['members'].get(_key(player),{}).get('team',1)
            base=_spawn_tile(r,m_team)
            if getattr(player,'_daily_unsafe',False) and max(abs(player.personaje.tile_x-base[0]),abs(player.personaje.tile_y-base[1]))<=8:
                player._daily_unsafe=False;aura(player,False)
    import combate,transitable,login
    objectives=[m for m in e.monstruos.values() if getattr(m,'daily_objective',False)]
    # Goddess waves use the native generator roster and positions. Release
    # successive groups instead of dumping every wave onto the first entrant.
    if r['kind']==6 and now>=r['next_wave']:
        rows=[d for d in datos(r['stage'])['spawns'] if d.get('monstruo') and d.get('apagado')]
        if rows:
            # Goddess's original generators all have tag0; retain their
            # native roster order instead of discarding untagged generators.
            zones=list(dict.fromkeys(d.get('zona') or d['npc_type'] for d in rows));zone=zones[r['wave']%len(zones)]
            for row in [d for d in rows if (d.get('zona') or d['npc_type'])==zone][:8]:
                eid=90000000+r['stage']*10000+r['wave']*100+len(e.monstruos)
                m=combate.Monstruo(eid,row['npc_type'],row['nombre'],row['tile'],row['sprite'],stage=r['stage'])
                m.daily_wave=True;m.generado=True;e.monstruos[eid]=m
                for p in players:p.enviar(login._npc_spawn(eid,m.npc_type,m.nombre,(m.tile_x,m.tile_y),sprite=m.sprite,klass=1))
        r['wave']+=1;r['next_wave']=now+60;_save(r)
    for m in list(e.monstruos.values()):
        if not m.vivo or getattr(m,'daily_objective',False):continue
        if r['kind']==6 and getattr(m,'en_combate_con',None):continue
        if r['kind']==1:
            team={9096:1,9097:2,9098:3,9099:4}.get(m.npc_type)
            targets=[o for o in objectives if o.vivo and o.daily_team!=team] if team else []
        elif r['kind']==6:targets=[o for o in objectives if o.vivo]
        else:continue
        if not targets:continue
        target=min(targets,key=lambda o:max(abs(o.tile_x-m.tile_x),abs(o.tile_y-m.tile_y)))
        before=m.tile_x,m.tile_y
        if max(abs(target.tile_x-m.tile_x),abs(target.tile_y-m.tile_y))>2:
            tile=transitable.avanzar(r['stage'],before,(target.tile_x,target.tile_y),3,parar_a=2)
            m.tile_x,m.tile_y=tile;m.tile=list(tile)
            from codec import Msg
            packet=Msg.registry[(5,'s2c','*')].build(entity_id=m.entity_id,cur_x=before[0]*32,cur_y=before[1]*32,dst_x=m.tile_x*32,dst_y=m.tile_y*32,speed=max(50,m.move_speed))
            for p in players:p.enviar(packet)
        else:
            damage=max(1,m.pegar()-target.defensa//2);target.hp=max(0,target.hp-damage);target.vivo=target.hp>0
            for p in players:p.enviar(combate.numero_flotante(target.entity_id,damage,1),combate.atributo(target.entity_id,target.porcentaje))
            if r['kind']==1:
                m.hp=0;m.vivo=False;m.muerto_en=now
                for p in players:p.enviar(combate.despawn_monstruo(m.entity_id))
            if not target.vivo and r['kind']==6:_finish(r);return


def cron(now=None):
    _ensure();current=dt.datetime.fromtimestamp(time.time()) if now is None else now
    stamp=current.timestamp()
    changed=False
    cfg=programacion()
    for slot in cfg['slots']:
        if slot['day']!=(current.weekday()+1)%7:continue
        hour,minute=map(int,slot['start'].split(':'))
        start=current.replace(hour=hour,minute=minute,second=0,microsecond=0).timestamp()
        registration=cfg['registration_minutes']*60
        if not start-registration<=stamp<start:continue
        identity='daily-%s-%s-%s'%(current.date().isoformat(),slot['alias'],slot['start'])
        if not any(r.get('family')==identity for r in _ROUNDS.values()):
            stages=[row[0] for row in GAMES[ALIASES[slot['alias']]][1]]
            if all(fase(actual(stage),stamp)=='cerrada' for stage in stages):
                iniciar_evento(slot['alias'],minutes=cfg['duration_minutes'],start=start,identity=identity);changed=True
    for r in list(_ROUNDS.values()):
        state=fase(r,stamp)
        if state=='combate':
            if r['phase']=='registration':
                r['phase']='battle';_save(r)
                changed=True
                family=r.get('family',r['id'])
                if family not in _ANUNCIOS_BATALLA:
                    _ANUNCIOS_BATALLA.add(family)
                    anuncio_banner('[Daily Event] %s battle has begun!'%r['name'])
                for p in _sessions(r):
                    aura(p,r['kind']==0);aviso(p,r['name']+' has begun!')
            __import__('daily_experience').tick(r,stamp)
            _mechanics(r,stamp)
        elif state=='final':_finish(r);changed=True
        elif r.get('return_at') and stamp>=r['return_at']:
            for p in _sessions(r):_return(p)
            r['return_at']=0;_save(r)
    if changed:
        import app
        for ses in app._tw_sesiones():
            if getattr(ses,'_daily_calendar',False):ses.enviar(*paquetes())


def comando_gm(ses,cmd,args):
    args=list(args)
    try:
        action='start' if cmd=='dailystart' else 'stop' if cmd=='dailystop' else args.pop(0).lower() if args else 'status'
        alias=args.pop(0).lower() if args else 'guard'
        if alias not in ALIASES:raise Rechazo('Use bleach, faction, guard, swindle, quick, joy or happiness.')
        rows=GAMES[ALIASES[alias]][1]
        stage=next((r[0] for r in reversed(rows) if r[3]<=ses.personaje.nivel<=r[4]),rows[-1][0])
        if action=='start':
            minutes=int(args[0]) if args else 30
            registration=int(args[2]) if len(args)>2 else (int(args[1]) if len(args)>1 and int(args[1])<=30 else 0)
            if not 1<=minutes<=180 or not 0<=registration<=30:raise Rechazo('Invalid Daily Event duration.')
            opened=iniciar_evento(alias,minutes,registration)
            aviso(ses,'%s opened in all %d level brackets. Use /daily enter %s.'%(GAMES[ALIASES[alias]][0],len(opened),alias))
        elif action in ('enter','join'):entrar(ses,stage)
        elif action in ('stop','finish'):
            for bracket in rows:
                r=actual(bracket[0])
                if r:_finish(r,cancel=action=='stop')
        else:aviso(ses,'%s: %s'%(GAMES[ALIASES[alias]][0],fase(actual(stage))))
    except (ValueError,IndexError) as exc:aviso(ses,str(exc))
