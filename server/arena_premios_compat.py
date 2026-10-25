"""Karma-authorized Lv280 equipment fallback for401+ (NOT official401+ table)."""
import time

POLICY='arena_lv280_para401_v1'
DURATION=9240*60
WEAPONS={9:66298,10:66299,11:66300,17:66301,8:66302,32:66303}
ARMOR={32:(66305,66306,66307,66308),33:(66309,66310,66311,66312),
       34:(66313,66314,66315,66316)}


def es_premio(ses,slot):
    p=getattr(ses,'personaje',None)
    meta=(getattr(p,'mejoras',None) or {}).get(slot,{})
    return bool(meta.get('arena_premio_fin') and
                meta.get('arena_premio_item')==getattr(ses,'inventario',{}).get(slot))


def plan(r,cid,member,data,config):
    import clases
    if (not config or not config.get('habilitado') or r['stage']!=240
            or not 401<=int(member['nivel']) or cid not in r.get('clasificacion',[])):
        return None
    place=r['clasificacion'].index(cid)+1
    if place>32:return None
    skills={int(sid):int(level) for sid,level,_ in data.get('habilidades',[])}
    bag={int(k):int(v) for k,v in data.get('inventario',{}).items()}
    weapon=clases.skill_de_item(bag.get(3,0))
    if weapon not in WEAPONS:
        candidates=[sid for sid in WEAPONS if sid in skills]
        weapon=max(candidates,key=lambda sid:(skills[sid],-sid)) if candidates else 8
    # Prefer the learned armor branch, independent of the weapon class.
    candidates=[sid for sid in ARMOR if sid in skills]
    armor=max(candidates,key=lambda sid:(skills[sid],-sid)) if candidates else (
        32 if weapon in (17,32) else 34 if weapon==8 else 33)
    items=list(ARMOR[armor])+[66319,66320]
    if place<=2:items.append(66318 if weapon==8 else 66317)
    if place<=3:items.append(66329+place)
    if place==1:
        items.insert(0,WEAPONS[weapon])
        if 14 in skills and weapon in (9,10):items.append(66304)
    finished=float(r.get('finalizada',r['fin']))
    return dict(exp=0,oro=0,creditos=0,skill_exp=0,skill_exp_ppm=0,
        items=[dict(id=i,cantidad=1,caduca_en=finished+DURATION) for i in items],
        compatibilidad=POLICY,fuente='Lv280 original; sustitucion401+ autorizada por Karma',
        reclamar_hasta=finished+4*3600,puesto=place,armor_skill=armor,weapon_skill=weapon)


def caducados(ses,now=None,*,campo_fin='arena_premio_fin',campo_item='arena_premio_item'):
    """Deadline metadata travels with normal equipment and personal-bank moves."""
    import app,cuentas,inventario,presencia
    p=getattr(ses,'personaje',None)
    if not p:return
    now=time.time() if now is None else now
    changed=[];bank=[]
    for slot,meta in list((p.mejoras or {}).items()):
        if meta.get(campo_fin,float('inf'))>now:continue
        iid=meta.get(campo_item)
        if slot>=0 and ses.inventario.get(slot)==iid:
            app._sacar(ses,slot,app._cant_de(ses,slot));changed.append(slot)
        elif slot<-10000:
            key=-10000-slot
            stored=(getattr(p,'banco',None) or {}).get(key)
            if stored and int(stored[0])==iid:
                p.banco.pop(key);bank.append(key)
        p.mejoras.pop(slot,None)
    if not changed and not bank:return
    equipped=any(inventario.es_equipo(s) for s in changed)
    if equipped:
        p.hp=min(p.hp,app._vida_max(p,ses.inventario))
        p.mp=min(p.mp,app._mana_max(p,ses.inventario))
    if getattr(ses,'usuario',None):
        if bank:cuentas.guardar_banco(ses.usuario,p.char_id,p.banco)
        app._guardar_bolsa(ses,p.char_id)
        if equipped:
            cuentas.guardar_progreso(ses.usuario,p.char_id,p.nivel,p.exp,p.hp,p.mp,p.habilidades,
                                     sp=getattr(ses,'sp',0),buffs=getattr(p,'buffs',None))
    packets=app._refrescar(ses,changed)
    packets.extend(inventario.banco_vaciar_ranura(s) for s in bank)
    if equipped:
        packets.append(app._stats_ses(ses));presencia.notificar_equipo(ses)
    ses.enviar(*packets)
