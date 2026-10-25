"""Read Star UI strings and native consumable rows, without account state."""
import pathlib,sys,json,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'server'),str(ROOT/'tools')]
sys.stdout.reconfigure(encoding='utf-8')
from house_services import xml_rows
from mall_selection import items,name
import star_blessing
for rank in (1,3,5,7,9):print('CARD_KINDS',rank,[r['kind'] for r in star_blessing.datos()['cards'].values() if r['rank']==rank and r['level']==1])
for i,r in xml_rows('string.xml').items():
    text=r.get('\u6587\u5b57','')
    if 3590<=i<=3645:print('STRING',i,text)
for i,r in items().items():
    text=name(r)
    if '\u661f\u76e4' in r.get('\u7269\u54c1\u985e\u5225',''):print('STAR_TYPE',i,text,r.get('\u7269\u54c1\u985e\u5225'),r.get('\u8aaa\u660e\u5b9a\u7fa9'))
    if re.search(r'Bingo|Star Key',text):print('STAR_ITEM',json.dumps(r,ensure_ascii=True))
    if re.search(r'^(Maple Mark|Maple Teleportation|Mark Stone|Mark Portal|Angelic Cave Scroll|Building Blocks City Scroll|Pharaoh Village Scroll|Witch Fly Book|Witch Summon Book)',text):
        print('SCROLL',i,text,r.get('\u5e38\u99d0\u6cd5\u8853'),r.get('\u4f7f\u7528\u516c\u5f0f'))
        mid=int(r.get('\u5e38\u99d0\u6cd5\u8853') or 0)
        if mid:print('SCROLL_MAGIC',mid,json.dumps(xml_rows('magic.xml').get(mid),ensure_ascii=True))
