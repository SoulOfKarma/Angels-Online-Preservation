"""Native OPEN_MAKE stations and atomic, location-bound recipe requests."""
from collections import Counter
import functools
import random
import struct

SKILLS={1:27,2:28,3:29,5:31,6:26}
NOTES={1:693,2:694,3:695,5:696,6:691}
# S2C001D has its own handler table at this+17416 (5F0EF0).
# Recipe handler601B50 is registered at17592, so its extended kind is11.
# 93 is the index relative to the separate S2C0013 table at16104.
RECIPE_ATTRIBUTE=11


@functools.lru_cache(maxsize=1)
def plans():
    from house_services import xml_rows
    result={}
    for n in range(1,10):
        for ident,row in xml_rows('item%s.xml'%('' if n==1 else n)).items():
            if row.get('\u7269\u54c1\u985e\u5225')=='\u914d\u65b9':
                result[ident]=int(row.get('\u52d5\u614b\u8cc7\u65991') or 0)
    return result


def known(p):
    from house_services import xml_rows
    levels={int(h[0]):int(h[1]) for h in p.habilidades}
    books=set(plans().values())
    # Basic material-processing recipes have no blueprint item; equipment
    # recipes referenced by a blueprint must be learned with that item.
    automatic={i for i,row in xml_rows('make.xml').items() if i not in books
               and levels.get(int(row.get('\u6280\u80fd1') or 0),0)>=int(row.get('\u7b49\u7d1a1') or 1)}
    return {i for i in automatic|set(getattr(p,'recetas',[]) or []) if 0<i<=4096}


def bits(p):
    result=bytearray(2048)
    for ident in known(p):result[ident//8]|=1<<(ident%8)
    return bytes(result)


def learned_packet(p,ident):
    return struct.pack('<HIBBII',0x1d,p.entity_id,1,RECIPE_ATTRIBUTE,ident,1)


def recipe_packets(p,ids):
    ids=sorted(set(ids))
    packets=[]
    for start in range(0,len(ids),200):
        chunk=ids[start:start+200]
        packets.append(struct.pack('<HIB',0x1d,p.entity_id,len(chunk))+
                       b''.join(struct.pack('<BII',RECIPE_ATTRIBUTE,ident,1) for ident in chunk))
    return packets


def window(s,category):
    s.enviar(*recipe_packets(s.personaje,known(s.personaje)),struct.pack('<HB',0x4b,category))


def gm(s,args):
    """Learn recipes for testing; regular crafting skill/material checks remain."""
    import clases,house_services,recent_mall
    branches={'all':set(SKILLS.values()),'weapon':{26},'armor':{27},'sewing':{28},'craft':{29},'cooking':{31}}
    try:
        if len(args)>2:raise ValueError()
        name=args[0].casefold() if args else 'all'
        if name not in branches:raise ValueError()
        limit=int(args[1]) if len(args)>1 else 1000
        if not 1<=limit<=1000:raise ValueError()
        ids={i for i,r in house_services.xml_rows('make.xml').items()
             if 0<i<=4096 and int(r.get('\u6280\u80fd1') or 0) in branches[name]
             and int(r.get('\u7b49\u7d1a1') or 1)<=limit}
        learned=[];added=[]
        def store(con,data):
            previous=set(map(int,data.get('recetas') or []))
            added.extend(sorted(ids-previous))
            learned.extend(sorted(previous|ids));data['recetas']=learned
        recent_mall.cambiar(s,{},[],transaccion=store)
        s.personaje.recetas=learned
        s.enviar(*recipe_packets(s.personaje,ids),clases.aviso(
            'Learned %d production recipes (%s, skill level <= %d). Crafting requirements still apply.'%(len(added),name,limit),tipo=0))
    except ValueError:
        s.enviar(clases.aviso('Usage: /recipes [all|weapon|armor|sewing|craft|cooking] [max_skill_level]',tipo=0))
    except recent_mall.Rechazo as exc:
        s.enviar(clases.aviso(str(exc),tipo=0))


def use_plan(s,slot):
    import recent_mall,clases,house_services
    ident=plans().get(s.inventario.get(slot))
    if not ident:return False
    if ident in known(s.personaje):
        s.enviar(clases.aviso('You already know this production recipe.',tipo=0));return True
    row=house_services.recipe(ident)
    if not row:return True
    skill=int(row.get('\u6280\u80fd1') or 0);level=int(row.get('\u7b49\u7d1a1') or 1)
    if not any(int(h[0])==skill and int(h[1])>=level for h in s.personaje.habilidades):
        s.enviar(clases.aviso('Your production skill level is insufficient.',tipo=0));return True
    learned=[]
    def store(con,data):
        values=set(map(int,data.get('recetas',[])))
        if ident in values:raise recent_mall.Rechazo('You already know this production recipe.')
        values.add(ident);learned.extend(sorted(values));data['recetas']=learned
    try:recent_mall.cambiar(s,{slot:1},[],transaccion=store)
    except recent_mall.Rechazo as exc:
        s.enviar(clases.aviso(str(exc),tipo=0));return True
    s.personaje.recetas=learned
    s.enviar(learned_packet(s.personaje,ident),clases.aviso('Production recipe learned.',tipo=0))
    return True


@functools.lru_cache(maxsize=None)
def stations(stage):
    import eventos,app
    native=eventos.del_stage(stage) or {}
    categories={}
    for event in native.get('disparadores',[]):
        for action,args in event.get('haz',[]):
            if action==18 and args and args[0] in SKILLS:categories[event['ev']]=args[0]
    points={tuple(map(int,xy.split(','))):categories[row[0]] for xy,row in native.get('objetos',{}).items() if row[0] in categories}
    result=[]
    for resource in app._recursos_de_plantilla(stage):
        tile=resource.get('tile')
        if not tile and resource.get('px'):tile=[int(n)//32 for n in resource['px']]
        if not tile and resource.get('hex'):
            tile=[n//32 for n in struct.unpack_from('<II',bytes.fromhex(resource['hex']),8)]
        if tile and tuple(tile) in points:
            result.append(dict(entity=resource['entity_id'],tile=tuple(tile),category=points[tuple(tile)]))
    return result


def _near(s,tile):return max(abs(s.personaje.tile_x-tile[0]),abs(s.personaje.tile_y-tile[1]))<=4


def open_station(s,category):
    import clases
    p=s.personaje
    candidates=[row for row in stations(p.stage) if row['category']==category and _near(s,row['tile'])]
    if not candidates:return False
    skill=SKILLS[category]
    if not any(int(h[0])==skill and int(h[1])>0 for h in p.habilidades):
        s.enviar(clases.aviso('',tipo=7,msg_id=NOTES[category]));return True
    row=min(candidates,key=lambda row:max(abs(p.tile_x-row['tile'][0]),abs(p.tile_y-row['tile'][1])))
    s.craft_station=dict(row,stage=p.stage,character=p.char_id)
    window(s,category);return True


def context(s):
    p=s.personaje
    if p.stage==500:
        import house_services,app
        station=house_services.PRODUCTION.get(getattr(s,'house_make_station',None))
        if not station:return None
        house=app._casa_actual(s)
        if house.owner_id!=p.char_id or house.level<2 or not house.cleanliness or getattr(s,'house_furnishing',False):return None
        return dict(stage=500,character=p.char_id,tile=station[1],category=station[3]) if _near(s,station[1]) else None
    row=getattr(s,'craft_station',None)
    if row and row['stage']==p.stage and row['character']==p.char_id and _near(s,row['tile']):return row
    return None


@functools.lru_cache(maxsize=None)
def products(ident):
    """Exact product/quality weights, not the drop-table ID as an item ID."""
    from house_services import recipe,xml_rows
    row=recipe(ident)
    if not row:return None
    result=int(row.get('\u7269\u54c1\u7de8\u865f') or 0)
    quantity=int(row.get('\u88fd\u4f5c\u6578\u91cf') or 1)
    if not result:return None
    if row.get('\u53c3\u8003\u6389\u5bf6')!='\u662f':return 1,((result,quantity,1),)
    drop=xml_rows('serv_drop.xml').get(result)
    if not drop:return None
    factor=int(drop.get('factor') or 0)
    if factor<=0 or int(drop.get('\u500b\u6578') or 1)!=1:return None
    choices=[]
    for key,value in drop.items():
        if not key.startswith('item') or not key[4:].isdigit():continue
        n=key[4:];weight=int(drop.get('prob'+n) or 0)
        amount=int(drop.get('count'+n) or 1)*quantity
        if int(value)>0 and weight>0 and amount>0:choices.append((int(value),amount,weight))
    if not choices or sum(w for _,_,w in choices)>factor:return None
    return factor,tuple(choices)


def _product_roll(table):
    factor,choices=table;ticket=random.randrange(factor)
    for item,amount,weight in choices:
        if ticket<weight:return [(item,amount)]
        ticket-=weight
    return []


def craft(s,ident):
    import app,clases,house_services,recent_mall
    def reject(text):s.enviar(struct.pack('<H',0x4d),clases.aviso(text,tipo=0))
    place=context(s);p=s.personaje;row=house_services.recipe(ident)
    if not place:return reject('Use the appropriate production station nearby.')
    if not row:return reject('Unknown production recipe.')
    if ident not in known(p):return reject('Learn this production recipe first.')
    if int(row.get('\u6280\u80fd1') or 0)!=SKILLS[place['category']]:return reject('This recipe requires a different production station.')
    for n in (1,2,3):
        skill=int(row.get('\u6280\u80fd%d'%n) or 0);level=int(row.get('\u7b49\u7d1a%d'%n) or 0)
        if skill and not any(int(h[0])==skill and int(h[1])>=level for h in p.habilidades):return reject('Your production skill level is insufficient.')
    output=products(ident)
    if output is None:return reject('The original recipe product table is unavailable; no materials consumed.')
    need=Counter()
    for n in range(1,7):
        item=int(row.get('\u539f\u6599%d'%n) or 0);amount=int(row.get('\u6578\u91cf%d'%n) or 0)
        if item and amount:need[item]+=amount
    if not need:return reject('This recipe has no material requirements.')
    def plan():
        slots={}
        for item,amount in need.items():
            for slot,value in sorted(s.inventario.items()):
                if not 20<=slot<=app._tope_bolsa(s.inventario) or value!=item:continue
                take=min(amount,app._cantidades(s).get(slot,1));slots[slot]=take;amount-=take
                if not amount:break
            if amount:raise recent_mall.Rechazo('Not enough production materials; nothing consumed.')
        return slots
    try:plan()
    except recent_mall.Rechazo as exc:return reject(str(exc))
    old=getattr(s,'craft_task',None)
    if old and not old.cancelled():return
    owner=p;station=dict(place)
    def finish():
        s.craft_task=None
        if s.personaje is not owner or not getattr(s,'conectado',True) or context(s)!=station:
            return reject('Production stopped because you left the station.')
        try:
            consume=plan();success=random.randrange(100)<int(row.get('\u6210\u529f\u6a5f\u7387') or 100)
            rewards=_product_roll(output) if success else []
            recent_mall.cambiar(s,consume,rewards)
        except recent_mall.Rechazo as exc:return reject(str(exc))
        if success:
            s.enviar(*app._otorgar_skill_exp(s,p,p.entity_id,skills_forzadas={SKILLS[station['category']]},prob_override=1.0))
        s.enviar(struct.pack('<HBI',0x4c,int(success),ident))
    delay=max(.1,float(row.get('\u88fd\u4f5c\u6642\u9593') or 1))
    import lyceum_services,asyncio
    delay*=max(.1,1-lyceum_services.bono(p.buffs,'fabricacion_pct')/100)
    s.craft_task=asyncio.get_event_loop().call_later(delay,finish)
