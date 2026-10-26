"""Holy Battlefield buildings: original map112 objects, no Totem War state.

    All gameplay state belongs to its persisted competition round. Construction
    is a joint transaction with the contributor's inventory, never free on
    replay. Monsters share that state and cannot damage friendly buildings.
"""
import copy
import functools
import json
import pathlib
import random
import struct
import time

import combate
import cuentas

GATE_COST = (40, 20, 20, 15, 15, 30, 30, 5, 5, 40)
IDOL_COST = 2  # msg7658; msg7654 contradicts this with 1.
MATERIAL = 8536
_POOLS = {}


def equipo(entity,team,companero=False):
    # REA005f0ef0: long table starts4408, entry38 ->005ffe10/1.
    # NPC/pet scalar table entry63 ->0060d540. Long120 was out of table!
    return (struct.pack('<HIBBI',0x0013,entity,1,63,int(team)) if companero else
            struct.pack('<HIBBII',0x001D,entity,1,38,1,int(team)))


@functools.lru_cache(maxsize=1)
def datos():
    return json.loads((pathlib.Path(__file__).parent / 'plantillas' / 'holy_battlefield.json').read_text(encoding='utf-8'))


def recursos():
    import app
    return [dict(d,nombre_visible=(app._material(d['material']) or {}).get('nombre','Battle Mine'))
            for d in datos().get('resources',[])]


def puede_atacar(ses,target):
    if not __import__('daily_events').can_target(ses,target):return False
    if not __import__('league_war').can_target(ses,target):return False
    if not getattr(target,'es_estructura_hb',False):return True
    import competiciones as c
    r=c.ronda(112)
    try:m=miembro(ses,r)
    except c.Rechazo:return False
    return bool(target.vivo and target.hb_round==r['id'] and target.hb_data['team']!=m['equipo'])


@functools.lru_cache(maxsize=1)
def objetos_originales():
    import sys
    tools_path=str(pathlib.Path(__file__).resolve().parents[1]/'tools')
    if tools_path not in sys.path:sys.path.append(tools_path)
    import mapa_del_cliente
    m=mapa_del_cliente.mapa(112)
    return {(o['tile'][0],o['tile'][1],o['id']):dict(px=(o['px'][0],m.alto*32-o['px'][1]),capa=o['capa'])
            for o in m.objetos if o['id'] in (60374,60383,60375,60376,60367,60368)}


def objeto(entity,sprite,tile):
    import login
    packet=bytearray(login._map_object_spawn(entity,sprite,tuple(tile)))
    source=objetos_originales().get((tile[0],tile[1],sprite))
    if source is None:
        source=next((v for (x,y,s),v in objetos_originales().items()
                     if (x,y)==tuple(tile) and s in (60374,60383,60375,60376)),None)
    if source:
        struct.pack_into('<III',packet,6,source['capa'],*source['px'])
    return bytes(packet)


def puertas_base(r=None):
    import competiciones as c
    active=c.fase(r or c.ronda(112))=='combate'
    return [objeto(eid,(60403 if team==1 else 60404) if active else sprite,tile)
            for eid,tile,sprite,team in bases()]


def bases():
    return [(716112000+i,(x,y),sprite,1 if x>200 else 2)
            for i,(x,y,sprite) in enumerate(objetos_originales()) if sprite in (60375,60376)]


@functools.lru_cache(maxsize=1)
def pasajes():
    """Original paired mini-warps: event3 ->tag4;event4 ->tag3."""
    objetos_originales()
    import mapa_del_cliente
    objects=mapa_del_cliente.mapa(112).objetos
    return [(716113000+event,tuple(next(o['tile'] for o in objects if o['evento']==event)),7-event)
            for event in (3,4)]


@functools.lru_cache(maxsize=1)
def limites_base():
    # Original event7 protects orange,8 blue, including crystal carriers.
    objetos_originales()  # Makes the existing client-map reader available.
    import mapa_del_cliente
    return [(tuple(o['tile']),o['evento']-6) for o in mapa_del_cliente.mapa(112).objetos
            if o['evento'] in (7,8)]


def puerta(d,r):
    # server.obd:60373/60382 closed;60374/60383 open, retaining the arch.
    sprite=d['sprite']-1 if gate_alive(r,d['team'],d['number']) else d['sprite']
    return objeto(d['entity'],sprite,tuple(d['tile']))


def spawn_edificio(m):
    import login
    d=m.hb_data
    packet=bytearray(login._npc_spawn(m.entity_id,m.npc_type,m.nombre,
                                    (m.tile_x,m.tile_y),m.sprite,klass=1))
    if d['kind']=='guard':
        pair=sorted((v for v in datos()['structures'] if v['kind']=='guard'
                     and v['team']==d['team'] and v['number']==d['number']),key=lambda v:v['tile'])
        # Opposite outward diagonals for normal and mirrored arches.
        normal=pair[1]['tile'][1]>pair[0]['tile'][1]
        facing=(5 if normal else 3) if d['entity']==pair[0]['entity'] else (1 if normal else 7)
        packet[35]=facing  # _npc_spawn ignores direccion for klass1.
    return bytes(packet)


def salto(ses,tile):
    """Holy Swiftness1640/45: local0003 only; never reload/presence re-entry."""
    import app,presencia
    p=ses.personaje
    ses._holy_camino=None
    # Discard queued movement/collision callbacks from the departed side.
    ses._holy_salto_pendiente=None
    ses._token_choque=None
    app._cancelar_portal_armado(ses)
    def effect(eid):return combate.efecto_magia_self_inicio(eid,45,1640,cast_time=0)
    ses.enviar(effect(p.entity_id))
    presencia.notificar_companero_accion(ses,effect(presencia.entidad_de(ses)))
    __import__('desplazamientos').reubicar(ses,tile,'holy')
    ses.enviar(combate.efecto_magia_self_fin(p.entity_id,45,1640))
    presencia.notificar_companero_accion(ses,
        combate.efecto_magia_self_fin(presencia.entidad_de(ses),45,1640))


def cartel(ses,texto):
    import app
    author=ses.personaje.nombre.encode('latin1','replace')[:16].ljust(17,b'\0')
    message=('0'+texto).encode('latin1','replace')+b'\0'
    app._tw_difundir(struct.pack('<HIB17s',0x128,0,13,author)+message)


def sincronizar_puertas(ses,r):
    """A repeated000E does NOT replace a sprite (005b85d0); recreate changes."""
    packets=puertas_base(r)+[puerta(d,r) for d in datos()['walls']]
    if __import__('competiciones').fase(r)=='combate':
        packets.extend(objeto(eid,60402,tile) for eid,tile,tag in pasajes())
    previous=getattr(ses,'_holy_puertas',{})
    current={}
    changed=[]
    for packet in packets:
        eid=struct.unpack_from('<I',packet,2)[0]
        current[eid]=packet
        if previous.get(eid)!=packet:
            changed.extend((combate.despawn_monstruo(eid),packet))
    changed.extend(combate.despawn_monstruo(eid) for eid in previous.keys()-current.keys())
    ses._holy_puertas=current
    if changed:ses.enviar(*changed)


def inicial():
    # Karma's requested layout: every gate starts guarded; idols start at10.
    return {str(d['entity']): d['hp'] if (d['number']<=10 if d['kind']=='idol'
            else True) else 0 for d in datos()['structures']}


def miembro(ses, r=None):
    import competiciones as c
    p = getattr(ses, 'personaje', None)
    r = r or c.ronda(112)
    m = c._miembro(r, ses) if p else None
    if not p or p.stage != 112 or c.fase(r) != 'combate' or not m or m['espectador'] or p.hp <= 0 or getattr(ses, 'muerto', False):
        raise c.Rechazo('Only active Holy Battlefield participants can use this service.')
    return m


def idols(r, team):
    return sum(1 for d in datos()['structures'] if d['kind']=='idol' and d['team']==team
               and r.get('edificios', {}).get(str(d['entity']), 0)>0)


def gate_alive(r, team, number):
    guards = [d for d in datos()['structures'] if d['kind']=='guard' and d['team']==team and d['number']==number]
    return bool(r and guards and all(r.get('edificios', {}).get(str(d['entity']), 0)>0 for d in guards))


def spawn_tag(r, team):
    # 101..110 are MINE gathering regions, not resurrection points!
    # Use original base / central statue tags as the compatibility frontier.
    step = min(5, idols(r, team)//5)
    return ((3,3,3,125,130,135) if team==1 else (4,4,4,150,155,160))[step]


def contacto_cristal(ses):
    """Original floor crystals are collected by proximity, not only NPC clicks."""
    import competiciones as c
    r=c.ronda(112)
    m=c._miembro(r,ses)
    if (c.fase(r)!='combate' or not m or m['espectador']
            or ses.personaje.hp<=0 or getattr(ses,'muerto',False)):
        return
    p=ses.personaje
    for team,(eid,_,_) in c.CRISTALES.items():
        tile=posicion_cristal(r,team)
        if max(abs(p.tile_x-tile[0]),abs(p.tile_y-tile[1]))<=1:
            c.pulsar(ses,eid)


def posicion_real(ses):
    """Movement packets predict their endpoint; pickup uses physical arrival."""
    pending=getattr(ses,'_holy_camino',None)
    if pending and pending[0]>time.time():return pending[1]
    return ses.personaje.tile_x,ses.personaje.tile_y


class Edificio(combate.Monstruo):
    def __init__(self, d, r):
        super().__init__(d['entity'], d['npc_type'], d['nombre'], d['tile'], d['sprite'], stage=112)
        self.hb_data = d
        self.hb_round = r['id']
        self.es_estructura_hb = True
        self.es_estatico = True
        self.move_speed = self.move_range = self.agro = 0
        self.hp_max = d['hp']
        self.hp = int(r.get('edificios', {}).get(str(self.entity_id), 0))

    def toca_reaparecer(self):
        return False  # Only construction can restore a destroyed building.

    def aplicar_efecto(self, ef):
        return None  # No charm, sacrifice, healing or periodic poison on buildings.

    def recibir(self, ataque, es_magico=False, mult=1.0, var_pct=0.05, es_pet=False):
        import competiciones as c
        ses = combate.ATACANTE[0]
        r = c.ronda(112)
        try:
            m = miembro(ses, r)
        except c.Rechazo:
            return 0
        if not r or r['id'] != self.hb_round or m['equipo']==self.hb_data['team'] or not self.vivo:
            return 0
        before = self.hp
        damage = super().recibir(ataque, es_magico, mult, var_pct, es_pet)
        new = copy.deepcopy(r)
        new['edificios'][str(self.entity_id)] = self.hp
        if not es_pet:
            hits = new.setdefault('dano_edificios',{}).setdefault(str(self.entity_id),{})
            cid = str(ses.personaje.char_id)
            hits[cid] = hits.get(cid,0)+min(before,damage)
        if not self.hp:
            mnew = new['miembros'][str(ses.personaje.char_id)]
            mnew['edificios_destruidos'] = mnew.get('edificios_destruidos', 0)+1
            kind = self.hb_data['kind']
            mnew[kind] = mnew.get(kind, 0)+1
            involved = new.setdefault('dano_edificios',{}).pop(str(self.entity_id),{})
            if self.hb_data['kind']=='guard':
                # Either guard's death removes its entire gate.
                for d in datos()['structures']:
                    if (d['kind']=='guard' and d['team']==self.hb_data['team']
                            and d['number']==self.hb_data['number']):
                        new['edificios'][str(d['entity'])] = 0
                        other = new['dano_edificios'].pop(str(d['entity']),{})
                        for cid, amount in other.items():
                            involved[cid] = involved.get(cid,0)+amount
                total = sum(involved.values())
                for cid, amount in involved.items():
                    if cid in new['miembros'] and total:
                        score(new,cid,max(1,GATE_COST[self.hb_data['number']-1]*amount//total))
            elif involved:
                score(new,max(involved,key=lambda cid:(involved[cid],-int(cid))),2)
        try:
            # HP-only hits change no achievement metric. Keep HP durable,
            # without reading every participant's character on each combo hit.
            c._guardar(new,actualizar_logros=not self.hp)
        except Exception:
            self.hp = before
            raise
        if self.hp:
            for viewer in c._sesiones():
                if viewer.personaje.stage==112:
                    viewer.enviar(combate.atributo(self.entity_id,self.porcentaje))
        else:
            publicar(new)
        if not self.hp and self.hb_data['kind']=='idol':
            team=self.hb_data['team']
            cartel(ses,'%s remain %d statues. Rebirth area back.' %
                   ('Gabriel' if team==1 else 'Raphael',idols(new,team)))
        return damage


def monstruos(r=None):
    import competiciones as c
    r = r or c.ronda(112)
    if not r or c.fase(r)=='cerrada':
        return {}
    if r['id'] not in _POOLS:
        _POOLS.clear()
        _POOLS[r['id']] = {d['entity']: Edificio(d, r) for d in datos()['structures']}
    pool = _POOLS[r['id']]
    for eid, m in pool.items():
        m.hp = int(r.get('edificios', {}).get(str(eid), 0))
    return pool


def sincronizar_monstruos(ses,r=None,sala=None):
    """Visible round buildings and combat targets must be the SAME objects.

    A world room can predate the round (or retain the previous round's pool).
    Never let that room replace fresh targets with its stale dictionary.
    """
    sala=sala or getattr(ses,'_sala',None)
    room=sala if getattr(sala,'stage',None)==112 else None
    targets=getattr(room,'monstruos',None) if room else getattr(ses,'monstruos',None)
    if targets is None:targets={}
    ids={d['entity'] for d in datos()['structures']}
    for eid in list(targets):
        if eid in ids or getattr(targets[eid],'es_estructura_hb',False):
            del targets[eid]
    targets.update(monstruos(r))
    ses.monstruos=targets
    if room:
        room.monstruos=targets
        for other in getattr(room,'sesiones',[]):
            if getattr(getattr(other,'personaje',None),'stage',None)==112:
                other.monstruos=targets
    return targets


def paquetes(r=None):
    import competiciones as c, login
    r = r or c.ronda(112)
    packets = puertas_base(r)
    if c.fase(r)=='combate':
        packets.extend(objeto(eid,60402,tile) for eid,tile,tag in pasajes())
    for d in recursos():
        packets.extend((login.objeto_de_mapa(d),login.objeto_nombrado(d)))
    for d in datos()['npcs']:
        packets.append(login._npc_spawn(d['entity'], d['npc_type'], d['nombre'], d['tile'], d['sprite'], klass=199, direccion=6))
    for d in datos()['walls']:
        packets.append(puerta(d,r))
    for m in monstruos(r).values():
        if m.vivo:
            packets.append(spawn_edificio(m))
            packets.append(equipo(m.entity_id,m.hb_data['team'],True))
            packets.append(combate.atributo(m.entity_id, m.porcentaje))
    return packets


def publicar(r):
    import competiciones as c, login
    pool = monstruos(r)
    for s in c._sesiones():
        if s.personaje.stage==112:
            old_round,previous=getattr(s,'_holy_edificios',(None,{}))
            if old_round!=r['id']:previous={}
            packets=[]
            for m in pool.values():
                if m.vivo:
                    if not previous.get(m.entity_id,False):
                        packets.extend((spawn_edificio(m),equipo(m.entity_id,m.hb_data['team'],True)))
                    packets.append(combate.atributo(m.entity_id,m.porcentaje))
                elif previous.get(m.entity_id,True):
                    packets.append(combate.despawn_monstruo(m.entity_id))
            s._holy_edificios=(r['id'],{m.entity_id:m.vivo for m in pool.values()})
            sincronizar_puertas(s,r)
            sincronizar_monstruos(s,r)
            s.enviar(*packets)
            marcador(s,r)


def score(r,cid,amount):
    m = r['miembros'].get(str(cid))
    if m and not m['espectador']:
        m['score'] = m.get('score',0)+max(0,int(amount))


def chat_equipo(ses, texto):
    import clases
    import competiciones as c
    p=getattr(ses,'personaje',None)
    if not p or p.stage!=112 or not texto.strip():return
    r = c.ronda(112)
    m = c._miembro(r, ses)
    if not m or m['espectador'] or c.fase(r) != 'combate':
        return
    for otro in c._sesiones():
        om = c._miembro(r, otro)
        if otro.personaje.stage == 112 and om and not om['espectador'] and om['equipo'] == m['equipo']:
            otro.enviar(clases.chat_battle(ses.personaje.nombre, texto[:500]))


def marcador(ses,r=None,ocultar=False):
    """REA 5F3D70/6692A0: S2C013B, 14 bytes; TEAMID long38/1."""
    import competiciones as c
    r = r or c.ronda(112)
    ocultar = ocultar or ses.personaje.stage != 112 or c.fase(r)=='cerrada'
    ses._holy_marcador = not ocultar
    m = c._miembro(r,ses)
    team = m['equipo'] if m and not m['espectador'] and not ocultar and c.fase(r)!='cerrada' else 0
    ses.enviar(equipo(ses.personaje.entity_id,team))
    import presencia
    presencia.notificar_companero_accion(ses,
        equipo(presencia.entidad_de(ses),team))
    gates = sum(gate_alive(r,team,n) for n in range(1,11)) if team else 0
    ses.enviar(struct.pack('<H8BI',0x013B,int(not ocultar),
        min(255,(r or {}).get('puntos',{}).get('1',0)),
        min(255,(r or {}).get('puntos',{}).get('2',0)),int(bool(team)),
        gates,idols(r,team) if team else 0,10,25,
        min(99999,(m or {}).get('score',0))))


def equipo_publico(ses):
    import competiciones as c
    import presencia
    m = c._miembro(c.ronda(112),ses)
    team = m['equipo'] if m and not m['espectador'] else 0
    return equipo(presencia.entidad_de(ses),team)


def soltar(r,ses):
    """Death/disconnect drops the crystal for 30s; ownership stays authoritative."""
    for owner,cid in list(r['portadores'].items()):
        if int(cid)==ses.personaje.char_id:
            r['portadores'].pop(owner)
            if ses.personaje.stage != 112:
                r.setdefault('cristales_estado',{}).pop(owner,None)
                continue  # A map-change hook already has destination coordinates.
            state = r.setdefault('cristales_estado',{}).setdefault(owner,{})
            state.update(tile=[ses.personaje.tile_x,ses.personaje.tile_y],
                         retorno=time.time()+30)
            state.pop('limite',None)


def posicion_cristal(r,owner):
    import competiciones as c
    return tuple((r or {}).get('cristales_estado',{}).get(str(owner),{}).get('tile') or c.CRISTALES[owner][1])


def sincronizar_portador(ses,r=None,quitar=False):
    """Native magic3141: 5min carrier vulnerability, no casting MP cost."""
    import competiciones as c, presencia
    p = ses.personaje
    r = r or c.ronda(112)
    owner = next((key for key,cid in (r or {}).get('portadores',{}).items()
                  if cid==p.char_id),None) if p.stage==112 and not quitar else None
    state = (r or {}).get('cristales_estado',{}).get(owner,{})
    deadline = state.get('limite',0) if owner else 0
    if deadline<=time.time():
        deadline = 0
    old = (p.buffs or {}).get(3141)
    if deadline:
        p.buffs[3141] = {'fin':deadline,'mit':-30,'mag_mit':-30,'hb_crystal':r['id']}
    elif old:
        p.buffs.pop(3141,None)
    elif not (getattr(ses,'flags_magicos',(0,0))[0] & 0x04000000):
        return
    ms = max(0,int((deadline-time.time())*1000)) if deadline else 0
    ses.enviar(struct.pack('<HIBBII',0x001D,p.entity_id,1,4,3141,ms))
    presencia.notificar_companero_accion(ses,
        struct.pack('<HIBBII',0x001D,presencia.entidad_de(ses),1,4,3141,ms))
    ses.enviar(estado_portador(ses,p.entity_id,quitar=not bool(deadline)))
    presencia.notificar_companero_accion(ses,
        estado_portador(ses,presencia.entidad_de(ses),quitar=not bool(deadline)))


def estado_portador(ses,entity,quitar=False):
    # REA60fc60 ->4b6790 ->600fb0:0185 bit26 triggers BearCrystal Lua.
    lo,hi=getattr(ses,'flags_magicos',(0,0))
    lo=(lo & ~0x04000000) | (0 if quitar else 0x04000000)
    return struct.pack('<HIII',0x0185,entity,lo,hi)


def tick_cristales():
    import competiciones as c
    r = c.ronda(112)
    if c.fase(r)!='combate':
        return
    new = copy.deepcopy(r)
    now = time.time()
    changed = False
    for owner,state in list(new.get('cristales_estado',{}).items()):
        if min(state.get('limite',float('inf')),state.get('retorno',float('inf')))<=now:
            new['portadores'].pop(owner,None)
            new['cristales_estado'].pop(owner)
            changed = True
    if changed:
        c._guardar(new)
        c._publicar_cristales(new)


def transferir_cristal(ses,eid):
    import competiciones as c, presencia
    r = c.ronda(112)
    if not r or ses.personaje.stage!=112:
        return False
    other = next((s for s in c._sesiones() if s is not ses and s.personaje.stage==112
                  and eid in (s.personaje.entity_id,presencia.entidad_de(s))),None)
    if other is None:
        return False
    owner = next((owner for owner,cid in r['portadores'].items() if cid==ses.personaje.char_id),None)
    if not owner:
        return False
    try:
        a,b = miembro(ses,r),miembro(other,r)
        if a['equipo']!=b['equipo'] or max(abs(ses.personaje.tile_x-other.personaje.tile_x),abs(ses.personaje.tile_y-other.personaje.tile_y))>3:
            raise c.Rechazo('Pass the crystal to a nearby living teammate.')
        new = copy.deepcopy(r)
        state = new.setdefault('cristales_estado',{}).setdefault(owner,{})
        history = state.setdefault('participantes',[])
        for cid in (ses.personaje.char_id,other.personaje.char_id):
            if cid not in history:
                history.append(cid)
        state.update(limite=time.time()+300)
        new['portadores'][owner]=other.personaje.char_id
        c._guardar(new)
        c._publicar_cristales(new)
        c.aviso(other,'Your teammate passed you the battle crystal. Deliver within 5 minutes.')
    except c.Rechazo as exc:
        c.aviso(ses,exc)
    return True


def bloquear_paso(ses, desde, hasta):
    """Original two-sided gate trigger lines; own side may pass."""
    import competiciones as c, app
    if not ses.personaje or ses.personaje.stage!=112:
        return False
    r = c.ronda(112)
    m = c._miembro(r,ses)
    if not r or not m or m['espectador']:
        return False
    if c.fase(r)!='combate':return False
    crossed = set(app._casillas_del_tramo(desde,hasta))
    carrying=ses.personaje.char_id in r.get('portadores',{}).values()
    if any(tile in crossed and (team!=m['equipo'] or carrying) for tile,team in limites_base()):
        return True
    for d in datos()['barriers']:
        ev = d['event']
        team = 1 if ev<71 else 2
        number = (ev-51)%10+1
        if tuple(d['tile']) in crossed and team!=m['equipo'] and gate_alive(r,team,number):
            return True
    return False


def paso_guardian(ses,desde,hasta,demora=0):
    """Walk-triggered ally crossing. Destroyed gate: ordinary walk, no warp."""
    import app,competiciones as c
    try:m=miembro(ses)
    except c.Rechazo:return False
    r=c.ronda(112)
    if tuple(desde)==tuple(hasta):return False
    route=list(app._casillas_del_tramo(desde,hasta))
    arrival=getattr(ses,'_holy_salto_llegada',None)
    if arrival:
        route=[t for t in route if max(abs(t[0]-arrival[0]),abs(t[1]-arrival[1]))>2]
        if max(abs(hasta[0]-arrival[0]),abs(hasta[1]-arrival[1]))>2:
            ses._holy_salto_llegada=None
    for guard in datos()['structures']:
        if guard['kind']!='guard' or guard['team']!=m['equipo'] or not gate_alive(r,guard['team'],guard['number']):continue
        n=guard['number'];tags=(50+n,60+n) if guard['team']==1 else (70+n,80+n)
        origin=min(tags,key=lambda t:max(abs(guard['tile'][0]-datos()['tags'][str(t)][0][0]),
                                        abs(guard['tile'][1]-datos()['tags'][str(t)][0][1])))
        rear=datos()['tags'][str(origin)][0]
        other=next(g for g in datos()['structures'] if g['kind']=='guard' and g['team']==guard['team']
                   and g['number']==n and g['entity']!=guard['entity'])
        dx=1 if guard['tile'][0]>other['tile'][0] else -1
        dy=1 if guard['tile'][1]>other['tile'][1] else -1
        back=(guard['tile'][0]+2*dx,guard['tile'][1]+2*dy)
        contact=next((t for t in route if max(abs(t[0]-rear[0]),abs(t[1]-rear[1]))<=1 or
               (max(abs(t[0]-guard['tile'][0]),abs(t[1]-guard['tile'][1]))<=3
                and (t[0]-guard['tile'][0])*dx+(t[1]-guard['tile'][1])*dy>=0)
               ),None)
        if contact is not None:
            tile=datos()['tags'][str(next(t for t in tags if t!=origin))][0]
            # Trigger on reaching the rear area, not at the far end of a
            # possibly long client waypoint beyond the guardian.
            fraction=max(abs(contact[0]-desde[0]),abs(contact[1]-desde[1]))/max(1,
                max(abs(hasta[0]-desde[0]),abs(hasta[1]-desde[1])))
            return _cruzar_guardian(ses,tile,hasta,r,guard['team'],n,demora*fraction)
    for tile in route:
        for barrier in datos()['barriers']:
            if tuple(barrier['tile'])!=tuple(tile) or tuple(tile)==tuple(desde):continue
            event=barrier['event']
            team=1 if event<71 else 2
            number=(event-51)%10+1
            if team==m['equipo'] and gate_alive(r,team,number):
                tag=event  # Original GOTO_TAG(event) is already the opposite side.
                destination=datos()['tags'][str(tag)][0]
                return _cruzar_guardian(ses,destination,hasta,r,team,number,demora)
    return False


def _cruzar_guardian(ses,destination,hasta,r,team,number,demora):
    import asyncio,competiciones as c
    def jump():
        ses.objetivo_actual=None
        salto(ses,destination)
        ses._holy_salto_llegada=tuple(destination)
    if demora<=0:
        jump()
        return True
    signature=(r['id'],tuple(destination),team,number)
    pending=getattr(ses,'_holy_salto_pendiente',None)
    if pending and pending[0]==signature:return True
    token=(signature,object())
    ses._holy_salto_pendiente=token
    def arrived():
        if getattr(ses,'_holy_salto_pendiente',None) is not token:return
        ses._holy_salto_pendiente=None
        current=c.ronda(112)
        p=getattr(ses,'personaje',None)
        if (not p or p.stage!=112
                or not current or current['id']!=r['id'] or not gate_alive(current,team,number)):
            return
        try:miembro(ses,current)
        except c.Rechazo:return
        if max(abs(p.tile_x-hasta[0]),abs(p.tile_y-hasta[1]))<=2:jump()
    try:asyncio.get_event_loop().call_later(demora,arrived)
    except RuntimeError:
        ses._holy_salto_pendiente=None
        return False
    return True


def _commit(ses, before, after, bag, counts):
    """Materials and construction persist atomically; stale inventories fail."""
    import app, competiciones as c
    p = ses.personaje
    improvements = copy.deepcopy(p.mejoras or {})
    touched = set(ses.inventario) | set(bag)
    for slot in set(ses.inventario)-set(bag):
        improvements.pop(slot,None)
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT datos FROM personajes WHERE char_id=? AND usuario=?',(p.char_id,ses.usuario)).fetchone()
            current = con.execute('SELECT datos FROM competiciones WHERE stage=112').fetchone()
            if not row or not current or json.loads(current[0])!=before:
                raise c.Rechazo('Battle state changed; retry. No material consumed.')
            data = json.loads(row[0])
            if not cuentas.inventario_equivalente(data,ses.inventario,app._cantidades(ses)):
                raise c.Rechazo('Inventory changed; save/reconnect and retry. No material consumed.')
            data.update(inventario={str(k):v for k,v in bag.items()},
                        cantidades={str(k):v for k,v in counts.items()},
                        mejoras={str(k):v for k,v in improvements.items()})
            con.execute('UPDATE personajes SET datos=? WHERE char_id=? AND usuario=?',(json.dumps(data),p.char_id,ses.usuario))
            con.execute('UPDATE competiciones SET datos=? WHERE stage=112',(json.dumps(after),))
            import competicion_logros
            logros_nuevos = competicion_logros.aplicar(con, after)
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    c._RONDAS[112] = after
    try:
        competicion_logros.publicar(logros_nuevos)
    except Exception:
        __import__('logging').getLogger(__name__).exception('Committed building achievement notification')
    ses.inventario.clear()
    ses.inventario.update(bag)
    p.inventario = ses.inventario
    app._cantidades(ses).clear()
    app._cantidades(ses).update(counts)
    p.mejoras = improvements
    for slot in touched:
        if slot not in bag:
            app._instancias(ses).pop(slot,None)
    cuentas._notificar_cambio()
    ses.enviar(*app._refrescar(ses,touched))


def _take(bag,counts,item,amount):
    import app
    for slot in sorted(list(bag)):
        if bag[slot]!=item or not 20<=slot<=app._tope_bolsa(bag):
            continue
        qty = counts.get(slot,1)
        take = min(qty,amount)
        amount -= take
        if take==qty:
            bag.pop(slot)
            counts.pop(slot,None)
        else:
            counts[slot]=qty-take
        if not amount:
            return
    raise ValueError('Insufficient material')


def construir(ses,kind,number=0):
    import app, competiciones as c
    r = c.ronda(112)
    m = miembro(ses,r)
    team = m['equipo']
    available = [d for d in datos()['structures'] if d['team']==team and d['kind']==kind
                 and (not number or d['number']==number)]
    if kind=='idol':
        available = sorted((d for d in available if not r['edificios'].get(str(d['entity']),0)),key=lambda d:d['number'])[:1]
        cost = IDOL_COST
    elif kind=='guard' and 1<=number<=10:
        if gate_alive(r,team,number):
            raise c.Rechazo('This gate already stands. No materials consumed.')
        cost = GATE_COST[number-1]
    else:
        raise c.Rechazo('Invalid building.')
    if not available:
        raise c.Rechazo('All statues already stand. No materials consumed.')
    bag,counts = dict(ses.inventario),dict(app._cantidades(ses))
    qty = sum(counts.get(s,1) for s,it in bag.items() if it==MATERIAL and 20<=s<=app._tope_bolsa(bag))
    if not qty:
        raise c.Rechazo('You need Building Material (8536).')
    new = copy.deepcopy(r)
    key = '%d:%s:%d' % (team,kind,available[0]['number'])
    progress = new.setdefault('construccion',{})
    used = min(qty,cost-progress.get(key,0))
    _take(bag,counts,MATERIAL,used)
    score(new,ses.personaje.char_id,used)
    progress[key] = progress.get(key,0)+used
    if progress[key]>=cost:
        for d in available:
            new['edificios'][str(d['entity'])] = d['hp']
        progress.pop(key)
        mn = new['miembros'][str(ses.personaje.char_id)]
        mn['construcciones'] = mn.get('construcciones',0)+1
        mn['build_'+kind] = mn.get('build_'+kind, 0)+1
    _commit(ses,r,new,bag,counts)
    publicar(new)
    c.aviso(ses,'Building restored.' if key not in progress else 'Contribution saved: %d/%d materials.' % (progress[key],cost))
    return used


def convertir(ses):
    import app, competiciones as c
    r = c.ronda(112)
    miembro(ses,r)
    bag,counts = dict(ses.inventario),dict(app._cantidades(ses))
    recipes = sorted(datos()['recipes'], key=lambda d:(d['item'] not in (8534,8535),d['amount'],d['item']))
    recipe = next((d for d in recipes if sum(counts.get(s,1) for s,it in bag.items() if it==d['item'] and 20<=s<=app._tope_bolsa(bag))>=d['amount']),None)
    if not recipe:
        raise c.Rechazo('Not enough raw materials. Raw Building Stone: 50; Quality Building Stone: 1.')
    _take(bag,counts,recipe['item'],recipe['amount'])
    slot = next((s for s,it in bag.items() if it==MATERIAL and 20<=s<=app._tope_bolsa(bag)),None)
    if slot is None:
        slot = app._ranura_libre(bag)
        if slot is None:
            raise c.Rechazo('Clear an inventory slot first; no materials consumed.')
        bag[slot]=MATERIAL
        counts[slot]=recipe['output']
    else:
        counts[slot]=counts.get(slot,1)+recipe['output']
    _commit(ses,r,copy.deepcopy(r),bag,counts)
    c.aviso(ses,'Created %d Building Material.' % recipe['output'])


def mostrar(ses,message,options,portrait,stage=112):
    import dialogos
    messages = message if isinstance(message,(list,tuple)) else [message]
    ses.dlg_guion = [dialogos.armar_linea(mid,portrait,options if i==len(messages)-1 else [])[2:]
                     for i,mid in enumerate(messages)]
    ses.dlg_ent = getattr(ses,'_holy_servicio',None) or getattr(ses,'dlg_ent',None) or 112
    ses.dlg_val = portrait
    ses.dlg_paso = 1
    ses.dlg_mapa = {'stage':stage,'opciones':[(x,1000021 if stage==114 and x==7582 else 0) for x in options],
                    'guion':ses.dlg_guion}
    ses.enviar(dialogos.linea_de(ses.dlg_guion,0,ses.personaje.nombre))


def pulsar(ses,eid):
    import competiciones as c
    if not ses.personaje or ses.personaje.stage!=112:
        return False
    passage=next((d for d in pasajes() if d[0]==eid),None)
    if passage:
        try:
            miembro(ses)
            tile=passage[1]
            if max(abs(ses.personaje.tile_x-tile[0]),abs(ses.personaje.tile_y-tile[1]))>3:
                raise c.Rechazo('Move closer to the light passage.')
            salto(ses,datos()['tags'][str(passage[2])][0])
        except c.Rechazo as exc:c.aviso(ses,exc)
        return True
    gate=next((d for d in datos()['structures'] if d['entity']==eid and d['kind']=='guard'),None)
    base=next((d for d in bases() if d[0]==eid),None)
    if gate or base:
        try:
            m=miembro(ses)
            team=gate['team'] if gate else base[3]
            tile=gate['tile'] if gate else base[1]
            if max(abs(ses.personaje.tile_x-tile[0]),abs(ses.personaje.tile_y-tile[1]))>3:
                raise c.Rechazo('Move closer to the passage.')
            if m['equipo']!=team:
                raise c.Rechazo('Enemy passage: destroy its guardian to advance.')
            if gate:
                return True  # Walking behind the guardian activates it, never clicking.
            else:
                if ses.personaje.char_id in c.ronda(112)['portadores'].values():
                    raise c.Rechazo('Deliver the crystal before using this passage.')
                return True  # Own side walks through; event7/8 only repels rivals/carriers.
        except c.Rechazo as exc:c.aviso(ses,exc)
        return True
    npc = next((d for d in datos()['npcs'] if d['entity']==eid),None)
    if not npc:
        return False
    ses._holy_servicio = None
    try:
        _validar_npc(ses,npc)
        ses._holy_servicio = eid
        kind = npc['npc_type']
        if kind in (2471,2478):
            mostrar(ses,7635,[7636,7637,7638,7639],38)
        elif kind in (2434,2475):
            mostrar(ses,7649,[7650,7651,7652,7653],180)
        elif kind in (2435,2476):
            mostrar(ses,7667,[7668,7669,7670,7671],7)
        elif kind in (2436,2477):
            mostrar(ses,7687,[7688,7669,7689,7671],55)
        elif kind in (2486,2487):
            mostrar(ses,7741,[7742,7743],181)
        else:
            c.aviso(ses,'Return to Sign-up Office using the tornado.')
    except c.Rechazo as exc:
        c.aviso(ses,exc)
    return True


def _validar_npc(ses,npc):
    import competiciones as c
    m = miembro(ses)
    if m['equipo']!=npc['team']:
        raise c.Rechazo('Ask the specialist on your own team.')
    p = ses.personaje
    if max(abs(p.tile_x-npc['tile'][0]),abs(p.tile_y-npc['tile'][1]))>4:
        raise c.Rechazo('Move closer to your specialist.')


def opcion(ses,opt):
    import competiciones as c
    if not ses.personaje or ses.personaje.stage!=112:
        return False
    npc = next((d for d in datos()['npcs'] if d['entity']==getattr(ses,'_holy_servicio',None)),None)
    if not npc:
        return False
    refresh = False
    try:
        _validar_npc(ses,npc)
        typ = npc['npc_type']
        if opt in (7639,7653,7671,7743):
            ses._holy_servicio = None
            c.cerrar_dialogo(ses)
        elif typ in (2471,2478):
            if opt==7638:
                refresh = True
                convertir(ses)
            elif opt in (7636,7637):
                mostrar(ses,[7640,7641,7642,7643] if opt==7636 else [7644,7645],[7638,7639],38)
        elif typ in (2434,2475):
            if opt==7652:
                refresh = True
                construir(ses,'idol')
            elif opt in (7650,7651):
                mostrar(ses,[7654,7655,7656,7657] if opt==7650 else 7658,[7652,7653],180)
        elif typ in (2435,2476):
            if opt==7670:
                mostrar(ses,7678,list(range(7679,7684))+[7671],7)
            elif 7679<=opt<=7683:
                refresh = True
                construir(ses,'guard',opt-7679+6)
            elif opt in (7668,7669):
                mostrar(ses,[7672,7673,7674,7675,7676] if opt==7668 else 7677,[7670,7671],7)
        elif typ in (2436,2477):
            if opt==7689:
                mostrar(ses,7678,list(range(7692,7697))+[7671],55)
            elif 7692<=opt<=7696:
                refresh = True
                construir(ses,'guard',opt-7692+1)
            elif opt in (7688,7669):
                mostrar(ses,[7672,7673,7674,7690] if opt==7688 else 7691,[7689,7671],55)
        elif typ in (2486,2487) and opt==7742:
            import app
            tag = random.choice((52,63,64,65,61) if npc['team']==1 else (82,73,74,75,71))
            x,y = datos()['tags'][str(tag)][0]
            salto(ses,(x,y))
    except c.Rechazo as exc:
        c.aviso(ses,exc)
    if refresh:
        # The generic router consumes dlg_mapa before dispatch. Without a new
        # page the next click closes the stale page instead of choosing again.
        if typ in (2435,2476):
            mostrar(ses,7678,list(range(7679,7684))+[7671],7)
        elif typ in (2436,2477):
            mostrar(ses,7678,list(range(7692,7697))+[7671],55)
        elif typ in (2434,2475):
            mostrar(ses,7658,[7652,7653],180)
        else:
            mostrar(ses,7635,[7636,7637,7638,7639],38)
    return True
