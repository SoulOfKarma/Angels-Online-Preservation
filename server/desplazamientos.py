"""Ground-targeted formula7 movement, distinct from offensive Dimension Shift."""
import asyncio
import re
import struct
import time


def reubicar(ses,tile,origen='spell'):
    """Local blink: stop the old path and reject only its in-flight replies."""
    import app,presencia
    p=ses.personaje
    old=(p.tile_x,p.tile_y)
    ses._salto_local=(time.time()+0.75,p.stage,old,tuple(tile))
    ses.objetivo_actual=None
    ses._holy_salto_pendiente=None
    ses._token_choque=None
    ses._holy_camino=None
    app._cancelar_portal_armado(ses)
    app._viajar_dentro_del_mapa(ses,origen,{'llegada':tuple(tile),'solo_0003':True})
    move=app.Msg.registry[(0x0005,'s2c','*')]
    def stopped(eid):
        return move.build(entity_id=eid,cur_x=tile[0]*32,cur_y=tile[1]*32,
                          dst_x=tile[0]*32,dst_y=tile[1]*32,speed=1000)
    ses.enviar(stopped(p.entity_id))
    eid=presencia.entidad_de(ses)
    presencia.notificar_companero_accion(ses,struct.pack('<HIII',3,eid,*tile),stopped(eid))


def movimiento_obsoleto(ses,cur_x,cur_y):
    """A new click from the landing point is accepted immediately (no lock)."""
    pending=getattr(ses,'_salto_local',None)
    if not pending:return False
    deadline,stage,old,new=pending
    p=ses.personaje
    if time.time()>=deadline or not p or p.stage!=stage:
        ses._salto_local=None
        return False
    current=(cur_x//32,cur_y//32)
    distance=lambda a,b:max(abs(a[0]-b[0]),abs(a[1]-b[1]))
    if distance(current,new)<=1:
        ses._salto_local=None
        return False
    return distance(current,old)<distance(current,new)


def lanzar(ses,mid,mag,x,y):
    import app,combate,presencia,transitable
    p=ses.personaje
    if not p or getattr(ses,'muerto',False) or getattr(ses,'mapa_cargando',False):return False
    origin=(p.tile_x,p.tile_y)
    limit=max(1,int(mag.get('rango',12)))
    if mag.get('nombre','').lower().startswith('rushing'):
        raw=combate._magic_xml().get(mid,{})
        match=re.search(r'charge range\s*(\d+)',raw.get('\u8aaa\u660e',''),re.I)
        if match:limit=int(match.group(1))
    dx,dy=x-origin[0],y-origin[1]
    distance=max(abs(dx),abs(dy))
    if not distance:return False
    if distance>limit:
        x,y=origin[0]+round(dx*limit/distance),origin[1]+round(dy*limit/distance)
    if not transitable.se_pisa(p.stage,x,y):return False
    if p.stage==112 and __import__('holy_battlefield').bloquear_paso(ses,origin,(x,y)):return False
    now=time.time();uses=getattr(ses,'ultimo_uso',None) or {}
    cd=int(mag.get('cd_ms',0))
    if now-uses.get(mid,0)<cd/1000:return False
    mp=int(mag.get('mp',0));sp=int(mag.get('cost_sp',0))
    if p.mp<mp or getattr(ses,'sp',0)<sp:return False
    p.mp-=mp;ses.sp=getattr(ses,'sp',0)-sp;p.sp=ses.sp
    uses[mid]=now;ses.ultimo_uso=uses
    ses.objetivo_actual=None;ses._holy_salto_pendiente=None;ses._token_choque=None;ses._holy_camino=None
    app._cancelar_portal_armado(ses)
    effect=int(mag.get('efecto',45))
    ses.enviar(combate.efecto_magia_self_inicio(p.entity_id,effect,mid,cast_time=0))
    eid=presencia.entidad_de(ses)
    presencia.notificar_companero_accion(ses,combate.efecto_magia_self_inicio(eid,effect,mid,cast_time=0))
    reubicar(ses,(x,y))
    ses.enviar(combate.efecto_magia_self_fin(p.entity_id,effect,mid),
               combate.atributo(p.entity_id,p.mp,combate.KIND_MP),
               combate.atributo(p.entity_id,ses.sp,combate.KIND_SP))
    if cd:
        ses.enviar(struct.pack('<HIBBII',0x1d,p.entity_id,1,3,mid,cd))
        def ready():
            # A recast/reconnect must not clear the newer cast's cooldown.
            if (getattr(ses,'personaje',None) is p
                    and getattr(ses,'ultimo_uso',{}).get(mid)==now):
                ses.enviar(struct.pack('<HIBBII',0x1d,p.entity_id,1,3,mid,0))
        asyncio.get_event_loop().call_later(cd/1000,ready)
    presencia.notificar_companero_accion(ses,combate.efecto_magia_self_fin(eid,effect,mid))
    ses.enviar(*app._otorgar_skill_exp(ses,p,p.entity_id,magic_id=mid))
    if getattr(ses,'usuario',None):
        import cuentas
        cuentas.guardar_progreso(ses.usuario,p.char_id,p.nivel,p.exp,p.hp,p.mp,p.habilidades,
                                 sp=ses.sp,buffs=p.buffs)
    return True
