"""Periodic EXP and Skill EXP distribution for active Daily Event battle stages.

While inside any active Daily Event map during the battle phase, participating
players receive periodic character experience and skill experience bonuses.
Amounts scale with character level and active buff multipliers.
The reward and its per-character pulse receipt commit in one transaction.
"""
import json
import struct

INTERVAL=10
EXP_PER_LEVEL=4800
EXP_CAP=2_000_000
EXP_MINIMUM=50_000
SKILL_EXP_AMOUNT=100


def _award(ses,r,stamp,interval):
    import app,clases,combate,configuracion,cuentas,daily_events
    p=ses.personaje
    if (daily_events.fase(r,stamp)!='combate' or p.stage!=r['stage']
            or getattr(ses,'_daily_round',None)!=r['id']
            or daily_events._key(ses) not in r['members']
            or getattr(ses,'muerto',False) or getattr(ses,'desconectado',False)
            or getattr(ses,'mapa_cargando',False)):return False
    pulse=max(0,int((stamp-r['start'])//interval))
    exp_gain=min(EXP_CAP,max(EXP_MINIMUM,int(p.nivel*EXP_PER_LEVEL*
        configuracion.multiplicador_exp(p.buffs))))
    skill_gain=max(10,int(round(SKILL_EXP_AMOUNT*configuracion.multiplicador_skill_exp(p.buffs))))
    before=[list(h) for h in (p.habilidades or [])]
    with cuentas._LOCK,cuentas._get_conn() as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute('CREATE TABLE IF NOT EXISTS daily_presence_awards('
                    'round_id TEXT,usuario TEXT,char_id INTEGER,pulse INTEGER,exp INTEGER,skill_exp INTEGER,'
                    'PRIMARY KEY(round_id,usuario,char_id,pulse))')
        key=(r['id'],ses.usuario.casefold(),p.char_id,pulse)
        if con.execute('SELECT 1 FROM daily_presence_awards WHERE round_id=? AND usuario=? AND char_id=? AND pulse=?',key).fetchone():return False
        row=con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',(ses.usuario,p.char_id)).fetchone()
        if not row:return False
        data=json.loads(row[0])
        if (int(data.get('nivel',p.nivel))!=p.nivel or int(data.get('exp',p.exp))!=p.exp
                or data.get('habilidades',[])!=before):
            return False  # A pending combat save must not overwrite newer progress.
        old_level=p.nivel;new_level=old_level
        data['exp']=max(int(p.exp or 0),combate.exp_para_nivel(old_level))+exp_gain
        while new_level<combate.nivel_maximo() and data['exp']>=combate.exp_para_nivel(new_level+1):new_level+=1
        data['nivel']=new_level
        data['hp_max']=p.hp_max+(new_level-old_level)*25
        data['mp_max']=p.mp_max+(new_level-old_level)*15
        skills=[]
        for sid,level,points in before:
            points+=skill_gain
            cap=min(combate.nivel_maximo(),new_level+(11 if sid in range(20,32) else 0))
            while level<cap and points>=max(1,clases.exp_requerida_skill(level,sid)):
                points-=max(1,clases.exp_requerida_skill(level,sid));level+=1
            if level>=cap:points=min(points,max(1,clases.exp_requerida_skill(level,sid)))
            skills.append([sid,level,points])
        data['habilidades']=skills
        con.execute('INSERT INTO daily_presence_awards VALUES(?,?,?,?,?,?)',(*key,exp_gain,skill_gain))
        con.execute('UPDATE personajes SET datos=? WHERE usuario=? AND char_id=?',(json.dumps(data),ses.usuario,p.char_id))
    p.exp=data['exp'];p.nivel=new_level;p.hp_max=data['hp_max'];p.mp_max=data['mp_max'];p.habilidades=[tuple(h) for h in skills]
    cuentas._notificar_cambio(inmediato=True)
    actual,next_exp=combate.exp_para_barra(p.nivel,p.exp)
    packets=[struct.pack('<HIB',0x1d,p.entity_id,4)+struct.pack('<BQ',29,p.nivel)
             +struct.pack('<BQ',30,combate.exp_para_nivel(p.nivel))+struct.pack('<BQ',31,next_exp)
             +struct.pack('<BQ',32,actual),clases.aviso(str(exp_gain),tipo=0,msg_id=clases.MSG_EXP)]
    if new_level>old_level:packets.extend([combate.efecto_level_up(p.entity_id),app._stats_ses(ses)])
    for (sid,level,points),(_,old_skill,_) in zip(skills,before):
        packets.append(struct.pack('<HIBBII',0x1d,p.entity_id,1,0,sid,points&0xffffffff))
        packets.append(clases.aviso_doble(clases.MSG_SKILL_EXP,clases.nombre(sid),str(skill_gain)))
        if level>old_skill:packets.append(clases.aviso_doble(clases.MSG_SKILL_SUBE,clases.nombre(sid)))
    if any(a[1]!=b[1] for a,b in zip(skills,before)):packets.extend([clases.arbol(p.habilidades),app._stats_ses(ses)])
    ses.enviar(*packets)
    return True


def tick(r,stamp,interval=INTERVAL):
    import daily_events
    if daily_events.fase(r,stamp)!='combate' or stamp<r.get('_exp_tick',0)+interval:return
    for ses in daily_events._sessions(r):_award(ses,r,stamp,interval)
    r['_exp_tick']=stamp
