"""Recover Olympus data from the latest local IGG XML/MPC; never touch accounts."""
import json
import pathlib
import sys
import struct
import xml.etree.ElementTree as ET
from collections import deque

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from house_services import xml_rows
import transitable
from mapa_del_cliente import mapa, _orden
from propagar_dialogos_mapa import _nodo


def posiciones(stage,generators,width,height):
    """Spread finite waves over their own disconnected native floor platform.

    Joint allocation prevents four neighboring generators from packing sixty
    mobs into the same corner. Cardinal flood fill cannot cross a wall or jump
    to another floor. Singleton guardians retain their original position.
    """
    components={}; result={}; occupied=set()
    for index,g in enumerate(generators):
        tile=tuple(g['tile'])
        if not transitable.se_pisa(stage,*tile):
            raise ValueError('Blocked Olympus generator: '+str((stage,tile)))
        if tile not in components:
            queue=deque([tile]); cells={tile}
            while queue:
                x,y=queue.popleft()
                for t in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if (t in cells or not(0<=t[0]<width and 0<=t[1]<height)
                            or not transitable.se_pisa(stage,*t)):continue
                    cells.add(t);queue.append(t)
            for t in cells:components[t]=cells
        if g['cantidad']==1:
            if tile in occupied:raise ValueError('Duplicate singleton Olympus generator')
            result[index]=[tile];occupied.add(tile)
    floors={}
    for index,g in enumerate(generators):
        if index in result:continue
        cells=components[tuple(g['tile'])]
        floors.setdefault(min(cells),dict(cells=cells,indices=[]))['indices'].append(index)
        result[index]=[]
    distance=lambda a,b:max(abs(a[0]-b[0]),abs(a[1]-b[1]))
    for floor in floors.values():
        cells=floor['cells']; indices=floor['indices']
        # A one-tile margin keeps large sprites away from walls. Reserve space
        # around fixed guardians. Each room has >1000 safe floor tiles.
        candidates=sorted(t for t in cells if t not in occupied
                          and all((t[0]+dx,t[1]+dy) in cells
                                  for dx in (-1,0,1) for dy in (-1,0,1))
                          and all(distance(t,o)>=3 for o in occupied if o in cells))
        count=sum(generators[i]['cantidad'] for i in indices)
        if len(candidates)<count:raise ValueError('Insufficient Olympus floor space')
        fixed=[o for o in occupied if o in cells]
        distances={t:min((distance(t,o) for o in fixed),default=1000) for t in candidates}
        # Allocate types in rounds, spreading every zone throughout its floor.
        for k in range(max(generators[i]['cantidad'] for i in indices)):
            for i in indices:
                if k>=generators[i]['cantidad']:continue
                anchor=tuple(generators[i]['tile'])
                t=max(distances,key=lambda p:(distances[p],-distance(p,anchor),-p[1],-p[0]))
                result[i].append(t);occupied.add(t);del distances[t]
                for p in distances:distances[p]=min(distances[p],distance(p,t))
    return result


def recover():
    sources=list((ROOT/'extracted_paks').glob('*/setting/eng/spmsg.xml'))
    source=max(sources,key=lambda p:_orden(p.parents[2]))
    all_nodes={n.get('\u7de8\u865f'):_nodo(n) for n in ET.parse(source).getroot()
               if n.tag=='\u5c0d\u8a71'}
    nodes={}; pending=['511651','511648']
    while pending:
        key=str(pending.pop())
        if key in nodes or key=='0':continue
        n=nodes[key]=all_nodes[key]
        pending.extend([n['s']] if n.get('s') else [])
        pending.extend(v[1] for v in n.get('o',[]))
        pending.extend(v['ir'] for v in n.get('r',[]))
    cfg={'source':str(source.relative_to(ROOT)), 'nodes':nodes,
         'npcs':[dict(entity_id=71410001,npc_type=11085,nombre='Olly',sprite=40293,
                      tile=[39,16],direccion=5,root=511651),
                 dict(entity_id=71410002,npc_type=14750,nombre='Ozzy',sprite=40003,
                      tile=[44,14],direccion=7,root=511648)],'maps':{}}
    entrance=next(o for o in mapa(41).objetos if o['id']==60001 and o['evento']==8)
    cfg['entrance']=dict(entity=73411853,sprite=entrance['id'],tile=entrance['tile'],
                         event=entrance['evento'],root=512557)
    monsters,npcs=xml_rows('monster.xml'),xml_rows('npc.xml')
    for stage in (217,332):
        m=mapa(stage); spawns=[]; zones={}
        generators=m.generadores()
        positions=posiciones(stage,generators,m.ancho,m.alto)
        for index,g in enumerate(generators):
            row=monsters.get(g['tipo']) or npcs.get(g['tipo'])
            if not row:raise ValueError('Unresolved generator: '+str(g['tipo']))
            mob=g['tipo'] in monsters
            count=g['cantidad']
            if count>100:raise ValueError('Unexpected generator count')
            tiles=positions[index]
            for tile in tiles:
                e=dict(entity_id=72000000+stage*10000+len(spawns),npc_type=g['tipo'],
                       nombre=row['\u540d\u7a31'],sprite=int(row['\u5716\u865f']),
                       tile=list(tile),zona=g['zona'],monstruo=mob,klass=1 if mob else 199,
                       direccion=2,visible=0,apagado=mob)
                spawns.append(e)
                if mob:zones.setdefault(str(g['zona']),[]).append(e)
        raw=pathlib.Path(m.ruta).read_bytes()
        for o in m.objetos:
            if not 40000<=o['id']<50000:continue
            typ=struct.unpack_from('<H',raw,m.off_objetos+o['i']*74+22)[0]
            if typ not in npcs:continue
            row=npcs[typ]
            spawns.append(dict(entity_id=72000000+stage*10000+len(spawns),npc_type=typ,
                              nombre=row['\u540d\u7a31'],sprite=o['id'],tile=o['tile'],
                              monstruo=False,klass=199,direccion=6))
        objects=[dict(entity=73000000+stage*10000+o['i'],sprite=o['id'],
                      tile=o['tile'],event=o['evento']) for o in m.objetos
                 if o['evento'] and (o['id']==60001 or o['zona']==101)]
        cfg['maps'][str(stage)]=dict(source=str(pathlib.Path(m.ruta).relative_to(ROOT)),
                                    spawns=spawns,zones=zones,objects=objects)
    return cfg


if __name__=='__main__':
    print(json.dumps(recover(),ensure_ascii=True))
