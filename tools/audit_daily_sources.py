"""Compile all21 Daily maps from native MPC generators and resources."""
import json
import pathlib
import struct
import sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'server'),str(ROOT/'tools')]
import daily_events
from house_services import xml_rows
from mapa_del_cliente import mapa
import poblar_del_cliente as builder


def portals(stage):
    import eventos,transitable
    m=mapa(stage);native=m.portales();out=[]
    for portal in native:
        if portal['destino'] is None:continue
        tiles=eventos.casillas_de_tag(portal['destino'],portal['tag'])
        if not tiles:continue
        out.append(dict(tile=list(portal['tile']),destino=portal['destino'],llegada=list(tiles[0]),
                        evento_cliente=True,dibujar=True,radio=1,source='native MPC conditional entry'))
    kind=daily_events.info(stage)['kind'];teams=range(1,5) if kind==1 else range(1,3) if kind==0 else (1,)
    bases=[(eventos.casillas_de_tag(stage,t) or eventos.casillas_de_tag(stage,1))[0] for t in teams]
    occupied={tuple(p['tile']) for p in out};exits=[]
    KNOWN_EXITS = {
        0: [(20, 99), (370, 102)],                          # Bleach of Red
        1: [(31, 168), (182, 27), (460, 103), (308, 244)],  # Faction Showdown
        2: [(28, 25)],                                       # Angelic Guard (Training City clover arch)
        3: [(88, 45), (88, 158), (312, 44), (310, 159)],    # Swindle World (4 faction platforms)
        4: [(301, 173)],                                     # Quick Reflexes
        5: [(5, 4)],                                         # Joy Angel Village
        6: [(350, 31)],                                      # Happiness Guard
    }
    if kind in KNOWN_EXITS:
        for t in KNOWN_EXITS[kind]:
            if transitable.se_pisa(stage, *t):
                occupied.add(t);exits.append(t)
    else:
        for base in bases:
            candidates=[tuple(p['tile']) for p in native if p['destino'] is None]
            candidates.sort(key=lambda t:max(abs(t[0]-base[0]),abs(t[1]-base[1])))
            candidates += [(base[0]+dx,base[1]+dy) for r in range(6,25)
                           for dx,dy in ((r,0),(-r,0),(0,r),(0,-r))]
            tile=next(t for t in candidates if t not in occupied
                      and all(max(abs(t[0]-b[0]),abs(t[1]-b[1]))>3 for b in bases)
                      and transitable.se_pisa(stage,*t))
            occupied.add(tile);exits.append(tile)
    for tile in exits:
        out.append(dict(tile=list(tile),destino=41,llegada=list(eventos.casillas_de_tag(41,1)[0]),
                        daily_exit=True,dibujar=True,radio=2,source='local exit near native entrance'))
    for i,portal in enumerate(out):portal['entity']=70000000+stage*1000+i
    return out


def recover(stage):
    m=mapa(stage);monsters=xml_rows('monster.xml');npcs=xml_rows('npc.xml')
    entries=[];used=set();event_zones=builder.zonas_de_evento(stage)
    builder._PISABLE=builder._suelo_de(stage)
    for g in m.generadores():
        if not g['cantidad']:continue
        row=monsters.get(g['tipo']) or npcs.get(g['tipo'])
        if not row:raise ValueError('Unresolved Daily generator '+str((stage,g['tipo'])))
        # Finite large chest groups are released by native completion events.
        # Keep their full census in the template, inactive until GENERATE.
        count=g['cantidad'] if g['tipo'] in (9223,9224) else min(g['cantidad'],40)
        for tile in builder._repartir(g['puntos'] or [g['tile']],count,m.ancho,m.alto,used):
            entries.append(dict(entity_id=85000000+stage*10000+len(entries),npc_type=g['tipo'],
                nombre=row['\u540d\u7a31'],sprite=int(row.get('\u5716\u865f') or 0),
                tile=list(tile),zona=g['zona'],monstruo=g['tipo'] in monsters,klass=1 if g['tipo'] in monsters else 199,
                direccion=2,visible=0,apagado=bool(g['zona'] in event_zones or daily_events.info(stage)['kind']==6),respawn=g['tiempo']))
    # MPC-placed guides, not just monster generators.
    raw=pathlib.Path(m.ruta).read_bytes()
    for o in m.objetos:
        if not 40000<=o['id']<42000:continue
        typ=struct.unpack_from('<H',raw,m.off_objetos+o['i']*74+22)[0]
        row=npcs.get(typ)
        if row:entries.append(dict(entity_id=85000000+stage*10000+len(entries),npc_type=typ,
            nombre=row['\u540d\u7a31'],sprite=o['id'],tile=list(o['tile']),monstruo=False,klass=199,direccion=6))
    resources,missing=builder.recursos_de(stage)
    bosses=[e['entity_id'] for e in entries if e['monstruo'] and 'Chest' not in e['nombre'] and
            ('Lord ' in e['nombre'] or e['nombre'].startswith('Swindle '))]
    return dict(source=str(pathlib.Path(m.ruta).relative_to(ROOT)),stage=stage,portals=portals(stage),
                spawns=entries,recursos=resources,bosses=bosses,
                missing_resource_shapes=dict(missing),
                tags={str(k):v for k,v in __import__('eventos').del_stage(stage)['tags'].items()})


if __name__=='__main__':
    for stage in sorted(daily_events.STAGES):
        path=ROOT/('server/plantillas/daily_%d.json'%stage)
        r=json.loads(path.read_text('utf8')) if '--portals-only' in sys.argv else recover(stage)
        if '--portals-only' in sys.argv:r['portals']=portals(stage)
        path.write_text(json.dumps(r,ensure_ascii=True,indent=1)+'\n',encoding='utf8')
        print(stage,len(r['spawns']),len(r['recursos']),len(r['bosses']),flush=True)
