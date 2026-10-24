"""Avatar formula29: separate companion slot, lifetime, combat/substitute roles."""
import asyncio
import struct
import time


def spawn(ses,inv):
    """005EBBF0 -> 005EC200: NPC6269/6270 requires a47-byte doll tail."""
    import login
    p=ses.personaje
    a=list(getattr(p,'apariencia',None) or [0,0,0,8,8])
    tail=bytearray(47)
    tail[:5]=bytes([a[0],a[4],a[3],a[2],a[1]])
    bag=getattr(ses,'inventario',{})
    for i,(fashion,gear) in enumerate(((167,1),(168,2),(169,3),(170,4),(171,5),(172,6),(173,7),(174,10))):
        struct.pack_into('<I',tail,5+i*4,int(bag.get(fashion) or bag.get(gear) or 0))
    struct.pack_into('<IIH',tail,37,int(bag.get(3,0)),int(bag.get(175,0)),int(p.class_id))
    base=login.spawn_invocacion(inv['entity_id'],inv['npc_type'],inv['nombre'],(inv['tile_x'],inv['tile_y']),sprite=inv['sprite'])
    return base[:65]+bytes(tail)


def lanzar(ses, tipo, mag):
    import app, combate, login, presencia
    p=ses.personaje
    mp,sp=int(mag.get('mp',0)),int(mag.get('cost_sp',0))
    if p.mp<mp or int(getattr(ses,'sp',0))<sp:
        return False
    p.mp-=mp
    ses.sp=int(getattr(ses,'sp',0))-sp
    p.sp=ses.sp
    cast=combate.calcular_cast_time(mag.get('cast_time',1000),buffs=p.buffs,habilidades=p.habilidades,es_magia=False)
    ses.enviar(combate.atributo(p.entity_id,p.mp,combate.KIND_MP),
               combate.atributo(p.entity_id,ses.sp,combate.KIND_SP),
               combate.numero_de_dano(p.entity_id,p.entity_id,0,ataque=tipo,efecto=mag.get('efecto',0),cast_time=cast),
               combate.gcd_paquete())
    stage=p.stage
    vida=getattr(ses,'competicion_vida',0)
    def finish():
        if (getattr(ses,'desconectado',False) or getattr(ses,'muerto',False) or p.stage!=stage
                or getattr(ses,'competicion_vida',0)!=vida):
            return
        old=getattr(ses,'avatar_clon',None)
        if old:
            ses.enviar(combate.despawn_monstruo(old['entity_id']))
            presencia.notificar_invocacion_despawn(ses,old['entity_id'])
        npc=int(mag['invoca_npc'])
        info=combate.datos_invocacion(npc)
        pct=max(1,int(mag['clon_poder']))
        stats=app._stats_ses(ses)
        hp=max(1,app._vida_max(p)*pct//100)
        # Parameter2 is interpreted as a percentage of the owner's base stats.
        # This server-side scaling is explicit; no unrelated static NPC damage.
        eid=90_000_000+presencia.entidad_de(ses)*4+3
        inv=dict(entity_id=eid,npc_type=npc,nombre=p.nombre,sprite=info['sprite'],
                 hp=hp,hp_max=hp,atk=struct.unpack_from('<I',stats,26)[0]*pct//100,
                 matk=struct.unpack_from('<I',stats,46)[0]*pct//100,
                 defensa=struct.unpack_from('<I',stats,38)[0]*pct//100,
                 mdef=struct.unpack_from('<I',stats,54)[0]*pct//100,
                 move_speed=info.get('move_speed',70),atk_speed=info.get('atk_speed',70),
                 atk_range=info.get('atk_range',1),skills=[],tile_x=p.tile_x+1,tile_y=p.tile_y,
                 expira=time.time()+mag['dur_invoca'],objetivo=None,ultimo_ataque=0,
                 es_clon=True,
                 clon_sustituto=bool(mag['clon_sustituto']))
        ses.avatar_clon=inv
        spawn_packet=spawn(ses,inv)
        health=combate.atributo(eid,100,combate.KIND_HP)
        ses.enviar(combate.cierre_de_dano(p.entity_id,p.entity_id,ataque=tipo,efecto=mag.get('efecto',0)),
                   spawn_packet,health,struct.pack('<HIBBI',0x0013,eid,1,0x3c,p.entity_id))
        presencia.notificar_invocacion_spawn(ses,inv,spawn_packet,health)
        ses.enviar(*app._otorgar_skill_exp(ses,p,p.entity_id,magic_id=tipo))
    asyncio.get_event_loop().call_later(max(0.01,cast/1000),finish)
    if getattr(ses,'usuario',None):
        app.cuentas.guardar_progreso(ses.usuario,p.char_id,p.nivel,p.exp,p.hp,p.mp,sp=ses.sp)
    return True


def absorber(ses, dano):
    import combate,presencia
    inv=getattr(ses,'avatar_clon',None)
    if not inv or not inv.get('clon_sustituto') or inv.get('expira',0)<=time.time() or inv.get('hp',0)<=0:
        return dano
    amount=min(max(0,int(dano)),int(inv['hp']))
    inv['hp']-=amount
    packets=[combate.numero_flotante(inv['entity_id'],amount),
             combate.atributo(inv['entity_id'],int(100*inv['hp']/max(1,inv['hp_max'])),combate.KIND_HP)]
    if not inv['hp']:
        packets.append(combate.despawn_monstruo(inv['entity_id']))
        ses.avatar_clon=None
    ses.enviar(*packets)
    presencia.notificar_companero_accion(ses,*packets)
    return int(dano)-amount
