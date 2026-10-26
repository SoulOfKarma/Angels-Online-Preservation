"""Compile scoped recent IGG bags, their real probabilities and NPC trees."""
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from house_services import xml_rows
from mapa_del_cliente import _orden
from propagar_dialogos_mapa import _nodo
from bolsas import PIEDRAS_SELLADAS

from mall_selection import selection,drop_rows
PRODUCTS=tuple(selection()[0])
# Previously offered stock remains openable after catalog removal. This is
# compatibility for existing inventory, not permission to sell these items.
RETIRED_OPENABLES=(82599,82598,82597,82594,82303,82300,82063,82052,82051,81448,
    81426,81425,81365,81343,81298,81027,80895,80892,80771,80770,80769,80768,
    80767,80766,80517,80514,79660,79542,79195,79059,79056,79055,79054,78508,
    76574,76562,76560,75514,74366,74365,74364,74363,74362,74361,74360,74199)


def recover():
    items={i:r for n in range(1,10) for i,r in xml_rows('item%s.xml'%(n if n>1 else '')).items()}
    drops=drop_rows()
    source=max((ROOT/'extracted_paks').glob('*/setting/eng/spmsg.xml'),key=lambda p:_orden(p.parents[2]))
    native={n.get('\u7de8\u865f'):_nodo(n) for n in ET.parse(source).getroot() if n.tag=='\u5c0d\u8a71'}
    nodes={};owners={};npcs=[]
    for name,eid,typ,sprite,tile,root,face,dirn in (
            ('Gear Clerk',406,14319,40046,[170,93],505823,46,7),
            ('Fashionable',71410003,8994,40207,[158,91],504816,1006,7),
            ('Daily Events Clerk',71410004,8912,40209,[161,93],504318,1009,7),
            ('Astral Angel',71410005,24516,40051,[177,100],514507,51,5),
            ('Party Angel',71410006,14419,40195,[174,91],509872,195,5),
            ('Chat Bubble Exchange',71410007,24740,40035,[151,87],516361,35,7),
            ('Reissue Angel',71410008,24801,40002,[194,91],516960,2,2)):
        # NPC coordinates and directions come from UPDATE19/update24 sp_*.xml.
        # Dialogue roots link to official spmsg.xml trees and exchange groups.
        npcs.append(dict(nombre=name,entity_id=eid,npc_type=typ,sprite=sprite,
                         tile=tile,root=root,face=face,direccion=dirn))
        pending=[root]
        while pending:
            key=str(pending.pop())
            if key=='0' or key in nodes:continue
            r=nodes[key]=native.get(key,{});owners[key]=name
            pending.extend([r['s']] if r.get('s') else [])
            pending.extend(v[1] for v in r.get('o',[]))
            pending.extend(v['ir'] for v in r.get('r',[]))
    # GvG redemption boxes remain service items, never extra Item Mall stock.
    gvg=json.loads((ROOT/'server/plantillas/league_war.json').read_text('utf8'))
    pending=list(PRODUCTS)+list(RETIRED_OPENABLES)+[64716,42591,42592,42593,63519]+[o['item'] for o in gvg['shop']];seen=set();boxes={};metadata={}
    groups={a[1][0] for n in nodes.values() for a in n.get('a',[]) if a[0]==98 and a[1]}
    recipes={i:r for i,r in xml_rows('exchange.xml').items()
             if int(r.get('\u7fa4\u7d44') or 0) in groups}
    for r in recipes.values():
        pending.extend(int(r['\u734e\u8cde%d'%n]) for n in range(1,6) if r.get('\u734e\u8cde%d'%n))
    while pending:
        ident=pending.pop(0)
        if ident in seen:continue
        seen.add(ident);r=items[ident]
        metadata[str(ident)]=dict(name=r.get('\u539f\u578b\u540d\u7a31','')+r['\u57fa\u672c\u540d\u7a31'],
                                 level=int(r.get('\u7b49\u7d1a\u9650\u5236') or 0),
                                 duration=int(r.get('\u6301\u7e8c\u6642\u9593') or 0))
        if __import__('inventario').resolver_tarjeta_puesto(ident) is not None:continue
        if r.get('\u7269\u54c1\u985e\u5225') not in ('\u79ae\u7269','\u7d05\u5305'):continue
        table=int(r.get('\u52d5\u614b\u8cc7\u65991') or 0)
        d=drops.get(table)
        # Original tooltips explicitly specify these fixed 20-potion bundles.
        # Their server-only drop records are absent from the extracted XML.
        if not d and ident in (48072,48073):
            reward=48053 if ident==48072 else 48054
            boxes[str(ident)]=dict(table=table,mode='all',rewards=[[reward,20,0]],source='original item tooltip')
            pending.append(reward);continue
        if not d:
            if ident in PIEDRAS_SELLADAS:
                pending.append(PIEDRAS_SELLADAS[ident]);continue
            # Some old Daily gear boxes reference server-only reward tables.
            # Keep their identities for the native menu, never invent loot.
            metadata[str(ident)]['unsupported_box']=table
            continue
        rewards=[[int(d['item%d'%i]),int(d.get('count%d'%i) or 1),int(d.get('prob%d'%i) or 0)]
                 for i in range(1,41) if d.get('item%d'%i)]
        weighted=any('prob%d'%i in d for i in range(1,41))
        if not rewards or weighted and any(p<=0 for _,_,p in rewards):raise ValueError('Incomplete drop weights')
        boxes[str(ident)]=dict(table=table,mode='random' if weighted else 'all',rewards=rewards)
        pending.extend(i for i,_,_ in rewards)
    return dict(source=str(source.relative_to(ROOT)),products=list(PRODUCTS),items=metadata,
                boxes=boxes,npcs=npcs,nodes=nodes,node_owners=owners,
                exchange_owners={str(a[1][0]):owners[str(k)] for k,n in nodes.items() for a in n.get('a',[]) if a[0]==98 and a[1]})


if __name__=='__main__':
    data=recover()
    if '--write' in sys.argv:
        (ROOT/'server/plantillas/recent_mall.json').write_text(json.dumps(data,ensure_ascii=True)+'\n',encoding='utf8')
        print('Compiled',len(data['npcs']),'NPCs,',len(data['items']),'item definitions,',len(data['boxes']),'boxes')
    else:print(json.dumps(data,ensure_ascii=True))
