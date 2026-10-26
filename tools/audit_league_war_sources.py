"""Export eight original GvG maps, tags, objectives and mine positions."""
import importlib.util
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'server'),str(ROOT/'tools')]
from mapa_del_cliente import mapa
from house_services import xml_rows


def recover():
    maps={}
    for stage in range(265,273):
        m=mapa(stage)
        maps[str(stage)]=dict(source=str(Path(m.ruta).relative_to(ROOT)) if hasattr(m,'ruta') else '',
            tags=m.tags,exits=[o['tile'] for o in m.objetos if o['id']==60001],
            mines=[dict(entity_id=91000000+stage*1000+o['i'],sprite=o['id'],tile=o['tile'],
                        px=[o['px'][0],m.alto*32-o['px'][1]],material=639)
                   for o in m.objetos if o['id']==60387],
            objectives=[dict(tile=o['tile'],npc_type=o['tipo']) for o in m.objetos if o['tipo']==3976])
    offers=[(i,300) for i in range(48007,48015)]+[(48015,600),(48016,300),(48017,150),(48018,200),
        (48049,100),(48050,100),(43301,20),(43302,20),(43303,20),(43304,20),
        (48051,10),(48052,10),(48072,5),(48073,5)]
    mercenaries=[dict(npc_type=k,level=int(v['\u7b49\u7d1a']),name=v['\u540d\u7a31'],sprite=int(v['\u5716\u865f']))
        for k,v in xml_rows('monster.xml').items() if v.get('HP') and 'mercenary' in v.get('\u540d\u7a31','').lower()]
    return dict(maps=maps,source_note='Native map265..272.mpc; material639/item37362. Redemption items and prices verified against screenshots supplied by Karma (League War 2018).',
        mechanics_reference='https://aog.userjoy.com/en/news_con.php?c=09&news=11150',mercenaries=mercenaries,robot=37388,
        local_balance=True,registration_seconds=900,duration_seconds=1800,
        schedules=[dict(weekday=2,start='21:00'),dict(weekday=6,start='17:00'),dict(weekday=6,start='22:30')],
        points=dict(kill=80,statue=20,stone=10),stone_batch=100,statue_respawn=20,repute=dict(win=30,draw=15,loss=5),
        rewards=dict(win=120,draw=80,loss=40),weekly=[1000,750,500],season=[4000,3000,2000],
        shop=[dict(id=n,item=item,price=price,source='user screenshots / original item XML')
              for n,(item,price) in enumerate(offers,1)])


def floors():
    spec=importlib.util.spec_from_file_location('floor_exporter',ROOT/'tools/transitable.py')
    exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter)
    target=ROOT/'server/plantillas/transitable.bin';raw=target.read_bytes()
    count=struct.unpack_from('<I',raw)[0];pos=4;records=[]
    for _ in range(count):
        stage,w,h=struct.unpack_from('<HHH',raw,pos);end=pos+6+(w*h+7)//8
        if stage not in range(265,273):records.append(raw[pos:end])
        pos=end
    if pos!=len(raw):raise ValueError('Invalid floor database')
    for stage in range(265,273):
        m=mapa(stage)
        # mapa_del_cliente keeps the official source at .ruta/.path by revision.
        sources=list((ROOT/'extracted_paks').glob('*/map/map%d.mpc'%stage))
        from mapa_del_cliente import _orden
        source=max(sources,key=lambda p:_orden(p.parents[1]))
        w,h,bits=exporter.capa(source)
        records.append(struct.pack('<HHH',stage,w,h)+bits)
    target.write_bytes(struct.pack('<I',len(records))+b''.join(records))


if __name__=='__main__':
    data=recover()
    if '--write' in sys.argv:
        (ROOT/'server/plantillas/league_war.json').write_text(json.dumps(data,ensure_ascii=True)+'\n',encoding='utf8')
        floors();print('Recovered eight GvG maps and local test balance.')
    else:print(json.dumps(data,ensure_ascii=True))
