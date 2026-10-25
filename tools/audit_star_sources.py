"""Compile the native packed IDs, stats and all 27 Star Blessing recipes."""
import json
import pathlib
import xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parents[1]


def recover():
    source=ROOT/'extracted_paks/UPDATE19/setting/star_client.xml'
    root=ET.parse(source).getroot()
    defs={k:int(v) for n in root if n.tag=='DEFINE' for k,v in n.attrib.items()}
    ranks={'\u4e00\u822c':1,'\u7cbe\u7df4':3,'\u5b8c\u7f8e':5,'\u4e3b\u795e':7,'\u5176\u4ed6':9}
    stats={1:'hp_bonus',3:'mp_bonus',8:'atk',10:'def',11:'matk',12:'mdef',13:'hit',14:'eva',
           18:'lightning',19:'fire',20:'ice',21:'corrosion',22:'res_lightning',23:'res_fire',
           24:'res_ice',25:'res_corrosion',26:'res_body',27:'res_mind',40:'crit',63:'direct_damage',64:'block'}
    def packed(rank,name,level):return ranks[rank]*10000+defs[name]*100+int(level)
    cards={};recipes={}
    for e in root:
        r=e.attrib
        if e.tag=='\u661f\u724c\u8cc7\u8a0a':
            ident=packed(r['\u968e\u7d1a'],r['\u724c\u540d'],r['\u7b49\u7d1a'])
            bonuses={}
            for prop,value in (('\u4e3b\u80fd\u529b','\u4e3b\u6578\u503c'),('\u526f\u80fd\u529b','\u526f\u6578\u503c'),('\u7b2c\u4e09\u80fd\u529b','\u7b2c\u4e09\u6578\u503c')):
                key=stats.get(defs.get(r.get(prop)))
                if key:bonuses[key]=bonuses.get(key,0)+int(r.get(value) or 0)
            cards[str(ident)]=dict(rank=ranks[r['\u968e\u7d1a']],kind=defs[r['\u724c\u540d']],
                                  level=int(r['\u7b49\u7d1a']),bonuses=bonuses,
                                  convert=int(r['\u8f49\u5316\u7372\u5f97']),upgrade=int(r['\u5347\u7d1a\u6240\u9700']))
        if e.tag=='\u514c\u63db\u8cc7\u8a0a':
            recipes[r['\u7de8\u865f']]=dict(group=int(r['\u7fa4\u7d44']),
                reward=packed(r['\u54c1\u9805\u724c\u7a2e'],r['\u54c1\u9805\u724c\u540d'],1),
                materials=[[packed(r['\u6750\u6599\u724c\u7a2e%d'%n],r['\u6750\u6599\u724c\u540d%d'%n],r['\u6750\u6599\u7b49\u7d1a%d'%n]),int(r['\u6750\u6599\u6578\u91cf%d'%n])]
                           for n in range(1,5) if r.get('\u6750\u6599\u724c\u7a2e%d'%n)])
    return dict(source=str(source.relative_to(ROOT)),cards=cards,recipes=recipes,
                local_rules=dict(source='Native Coin prices and screenshot Bingo rewards; random weights and next-tier chance are local compatibility settings',
                    divination_costs_source='UPDATE19/setting/eng/wnd01.xml, native button tooltips50341..50345',
                    divination_costs=[1000000,2000000,4000000,8000000,16000000],
                    tier_weights=[[1000,0,0,0],[1000,0,0,0],[800,200,0,0],[600,400,0,0],[200,650,0,150]],
                    unlock_percent=25,star_key_weights=[75,25],
                    bingo_awards_source='Original IGG screenshot supplied by Karma, 2026-10-24; only visible thresholds transcribed',
                    bingo_awards=[[1,1,5],[2,1,10],[3,1,20],[4,1,40],[5,1,80],[6,4,3],[8,1,320]]))


if __name__=='__main__':
    import sys
    data=recover()
    if '--write' in sys.argv:
        (ROOT/'server/plantillas/star_blessing.json').write_text(json.dumps(data,ensure_ascii=True,indent=1)+'\n',encoding='utf8')
        print('Compiled',len(data['cards']),'cards and',len(data['recipes']),'recipes')
    else:print(json.dumps(data,ensure_ascii=True,indent=1))
