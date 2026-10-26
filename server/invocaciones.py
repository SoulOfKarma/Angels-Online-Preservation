"""Summon cast, arrival effect and publication are separate timed phases."""
import asyncio
import struct
import time


def lanzar(ses,tipo,mag,tx,ty,addr='summon'):
    import app,combate,login,presencia,cuentas
    from house_services import xml_rows
    p=ses.personaje
    if not p or getattr(ses,'_summon_cast',None):return False
    mp,sp=int(mag.get('mp',0)),int(mag.get('cost_sp',0))
    if p.mp<mp or getattr(ses,'sp',0)<sp:return False
    npc=int(mag['invoca_npc']);info=combate.datos_invocacion(npc)
    cast=combate.calcular_cast_time(mag.get('cast_time',2000),buffs=p.buffs,
                                   habilidades=p.habilidades,es_magia=True)
    # Native magic.xml: Putridox's arrival animation has800ms hit time.
    arrival=max(0,int(xml_rows('magic.xml').get(tipo,{}).get('\u547d\u4e2d\u6642\u9593') or 0))/1000
    ef=combate.efecto_de_ataque(tipo) or mag.get('efecto',9)
    totem='totem' in info['nombre'].lower() or (info.get('move_speed',70) or 0)<=0
    radius=max(1,int(mag.get('rango',12)))
    if totem:tx,ty=p.tile_x,p.tile_y
    elif not (tx>0 and ty>0 and max(abs(tx-p.tile_x),abs(ty-p.tile_y))<=radius):tx,ty=p.tile_x+1,p.tile_y
    stage=p.stage;room=presencia.clave_de_mapa(ses,stage);life=getattr(ses,'competicion_vida',0)
    token=object();ses._summon_cast=token
    p.mp-=mp;ses.sp=getattr(ses,'sp',0)-sp;p.sp=ses.sp
    if getattr(ses,'sentado',False):
        ses.sentado=False;ses.enviar(struct.pack('<HIII',0x000a,p.entity_id,0,0))
    app._dar_sp(ses,p.entity_id,mag,addr)
    ses.enviar(combate.atributo(p.entity_id,p.mp,combate.KIND_MP),
               combate.atributo(p.entity_id,ses.sp,combate.KIND_SP),
               combate.confirmar_cast(0,tx,ty),
               combate.numero_de_dano(p.entity_id,0,ataque=tipo,efecto=ef,cast_time=cast,
                                       es_magia=True,tile_x=tx,tile_y=ty),combate.gcd_paquete())
    public=presencia.entidad_de(ses)
    presencia.notificar_companero_accion(ses,combate.numero_de_dano(public,0,ataque=tipo,
        efecto=ef,cast_time=cast,es_magia=True,tile_x=tx,tile_y=ty))
    def valid():
        ok=(getattr(ses,'_summon_cast',None) is token and ses.personaje is p
            and not getattr(ses,'muerto',False) and not getattr(ses,'desconectado',False)
            and not getattr(ses,'mapa_cargando',False) and p.stage==stage
            and presencia.clave_de_mapa(ses,p.stage)==room and getattr(ses,'competicion_vida',0)==life)
        if not ok and getattr(ses,'_summon_cast',None) is token:ses._summon_cast=None
        return ok
    def spawn():
        if not valid():return
        ses._summon_cast=None
        duo=any(5136<=int(k)<=5140 and (not isinstance(v,dict) or v.get('fin',time.time()+1)>time.time())
                for k,v in (p.buffs or {}).items() if str(k).isdigit())
        old1=getattr(ses,'invocacion',None);old2=getattr(ses,'invocacion2',None)
        removed=[]
        if duo and old1 and not old2:slot='invocacion2';kept=old1
        elif duo and not old1:slot='invocacion';kept=old2
        elif duo:
            removed=[old1];ses.invocacion=old2;slot='invocacion2';kept=old2
        else:
            removed=[v for v in (old1,old2) if v];ses.invocacion2=None;slot='invocacion';kept=None
        for old in removed:
            ses.enviar(combate.atributo(old['entity_id'],0,combate.KIND_HP),combate.despawn_monstruo(old['entity_id']))
            presencia.notificar_invocacion_despawn(ses,old['entity_id'])
        eid=p.entity_id+8000
        if kept and kept['entity_id']==eid:eid+=1
        inv=dict(entity_id=eid,npc_type=npc,nombre=info['nombre'],sprite=info['sprite'],
                 hp=info['hp'],hp_max=info['hp'],atk=info['atk'],defensa=info['def'],
                 matk=info.get('matk',0),mdef=info.get('mdef',0),level=info.get('level',1),
                 accuracy=info.get('accuracy',50),agility=info.get('agility',50),crit_rate=info.get('crit_rate',5),
                 atk_range=8 if totem else info.get('atk_range',1),move_speed=0 if totem else info.get('move_speed',70),
                 atk_speed=info.get('atk_speed',70),skills=info.get('skills',[]),tile_x=tx,tile_y=ty,
                 expira=time.time()+mag.get('dur_invoca',3600),objetivo=None,ultimo_ataque=0.,proximo_paso=0.)
        setattr(ses,slot,inv)
        packet=login.spawn_invocacion(eid,npc,info['nombre'],(tx,ty),sprite=info['sprite'])
        health=combate.atributo(eid,100,combate.KIND_HP)
        packets=[struct.pack('<HIBBI',0x0013,p.entity_id,1,0x3d,eid),
                 struct.pack('<HIBBII',0x001d,p.entity_id,1,0x2a,eid,0),packet,health,
                 struct.pack('<HIBBI',0x0013,eid,1,0x3c,p.entity_id)]
        cd=int(mag.get('cd_ms',2000));group=tuple(combate.grupo_de(tipo))
        if cd>0:
            packets.extend(struct.pack('<HIBBII',0x001d,p.entity_id,1,3,k,cd) for k in group)
            def reset():
                if ses.personaje is p and not getattr(ses,'desconectado',False):
                    ses.enviar_inmediato(*(struct.pack('<HIBBII',0x001d,p.entity_id,1,3,k,0) for k in group))
            asyncio.get_event_loop().call_later(cd/1000,reset)
        packets.extend(app._otorgar_skill_exp(ses,p,p.entity_id,magic_id=tipo))
        ses.enviar_inmediato(*packets)
        presencia.notificar_invocacion_spawn(ses,inv,packet,health)
    def impact():
        if not valid():return
        ses.enviar_inmediato(combate.cierre_de_dano(p.entity_id,0,ataque=tipo,efecto=ef,
                                                   es_magia=True,tile_x=tx,tile_y=ty))
        presencia.notificar_companero_accion(ses,combate.cierre_de_dano(public,0,ataque=tipo,
            efecto=ef,es_magia=True,tile_x=tx,tile_y=ty))
        if arrival:asyncio.get_event_loop().call_later(arrival,spawn)
        else:spawn()
    asyncio.get_event_loop().call_later(cast/1000,impact)
    if getattr(ses,'usuario',None):
        cuentas.guardar_progreso(ses.usuario,p.char_id,p.nivel,p.exp,p.hp,p.mp,p.habilidades,
                                 hp_max=p.hp_max,mp_max=p.mp_max,sp=ses.sp,buffs=p.buffs)
    return True
