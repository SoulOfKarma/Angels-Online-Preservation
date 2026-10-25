"""Read the historical IGG mall catalog, not the unrelated NPC shop table."""
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from house_services import xml_rows
from mapa_del_cliente import _orden
from audit_recent_mall_sources import PRODUCTS
from mall_selection import items,name,selection,RECENT_SALES


def recover():
    source=max((ROOT/'extracted_paks').glob('*/setting/eng/mall.xml'),key=lambda p:_orden(p.parents[2]))
    definitions={k:int(v) for n in ET.parse(source).getroot() if n.tag=='DEFINE'
                 for k,v in n.attrib.items() if v.isdigit()}
    flags={n.get('__name__'):int(n.get('__value__'),0) for n in ET.parse(source).getroot()
           if n.get('__name__') and n.get('__value__')}
    rows=[]
    for ident,row in xml_rows('mall.xml').items():
        if not 1<=ident<=40000:raise ValueError('Mall ID outside native bound')
        rows.append(dict(id=ident,item=int(row['\u9053\u5177\u7de8\u865f']),
                         flags=sum(value for label,value in flags.items() if row.get(label)=='\u662f'),
                         sort=int(row.get('\u6392\u5e8f') or 0),
                         category=definitions[row['\u5206\u985e\u985e\u5225']],
                         quantity=int(row['\u6578\u91cf']),price=int(row['\u552e\u50f9']),
                         special_price=int(row.get('\u7279\u50f9') or 0),
                         duration=int(row.get('\u6709\u6548\u671f\u9650') or 0),
                         start=row.get('\u4e0a\u67b6\u6642\u9593',''),
                         end=row.get('\u4e0b\u67b6\u6642\u9593',''),limit=0,gift=0,gift_quantity=0))
    original_count=len(rows)
    table=items();selected,excluded=selection()
    # Dated promotions are superseded, while permanent utility products keep
    # their native prices. Cabinet deliveries store item IDs at purchase time.
    historical=list(rows)
    rows=[r for r in rows if not __import__('re').search(r'\b20(?:0\d|1\d|2[012])\b',name(table.get(r['item'],{})))]
    # Explicitly approved local fallback when the last server-side catalog
    # price is unavailable. Never replace a verified original product price.
    reserved={81972:39000,82270:39001,82408:39002,82660:39003}
    for item in sorted(PRODUCTS):
        if any(r['item']==item and r['category']==selected[item] for r in rows):continue
        ident=reserved.get(item,10000+item-70000)
        if any(r['id']==ident for r in rows):raise ValueError('Local catalog ID collision')
        exact=[r for r in historical if r['item']==item and r['quantity']==1]
        family=name(table[item]).lower()
        def similarity(r):
            import re
            words=lambda s:set(re.findall('[a-z]+',s.lower()))-{'lucky','bag','egg','star'}
            return len(words(family)&words(name(table.get(r['item'],{}))))
        candidates=[r for r in historical if r['quantity']==1 and r['category']==selected[item]]
        reference=max(candidates,key=similarity) if candidates else None
        price=exact[0]['price'] if exact else reference['price'] if reference and similarity(reference)>=2 else 399
        price_source='original mall.xml' if exact else ('local closest original product %d'%reference['id'] if reference and similarity(reference)>=2 else 'local fallback approved by Karma')
        if item==81972 and not exact:
            price=399;price_source='local price explicitly approved by Karma for item81972'
        quantity=1
        if selected[item]==16 and 74136<=item<=74155:
            # User-provided original IGG Mall screenshot: Red/Blue Potion II,
            # 200 for 79 AG. Other grades use that nearest series reference.
            quantity,price=200,79
            price_source='original user screenshot: 200 Red/Blue Potion II for 79 AG' if item in (74137,74147) else 'local closest original potion series: 200 for 79 AG'
        rows.append(dict(id=ident,item=item,flags=3,sort=100000-item,category=selected[item],
                         quantity=quantity,price=price,special_price=0,duration=0,start='',end='',
                         limit=0,gift=0,gift_quantity=0,price_source=price_source))
    for item,evidence in RECENT_SALES.items():
        base=next(r for r in rows if r['item']==item)
        base.update(original_sale=evidence,publication='local restoration of verified IGG Mall product')
        for cat in evidence['categories']:
            if any(r['item']==item and r['category']==cat for r in rows):continue
            rows.append(dict(base,id=34000+list(RECENT_SALES).index(item)*10+cat-23,
                             category=cat,sort=82660-item))
    # Local purchase totals decide Top Sale at runtime. With no purchases,
    # the verified recent products form an explicitly local featured list.
    for item in (82660,82408,82270,80489,80490,80491,80492,80493,80494,80495):
        if item not in selected:continue
        r=next(r for r in rows if r['item']==item)
        rows.append(dict(r,id=30000+item-80000,category=22,sort=82660-item))
    # The same actual Mall class-bag edition supplies the weapon/armor
    # subtabs. This lists the bag, not its individual reward equipment.
    for item in range(80489,80496):
        if item not in selected:continue
        r=next(r for r in rows if r['item']==item)
        for cat in (29,30):rows.insert(0,dict(r,id=32000+(item-80489)*2+(cat-29),category=cat,sort=item-80489))
    def row_allowed(item_id):
        row = table.get(item_id)
        if not row: return False
        text = name(row).lower()
        if any(k in text for k in ('5x', 'x5', '5 x', 'x 5')) and 'stone' in text: return False
        if str(row.get('\u539f\u578b\u4ecb\u9762', '')) in ('5290', '5480', 'None', ''): return False
        if row.get('\u4e0d\u53ef\u4ea4\u6613') == '\u662f': return False
        if row.get('\u4e0d\u53ef\u5b58\u5009\u5eab') == '\u662f' or row.get('\u4e0d\u53ef\u5b58\u5009') == '\u662f': return False
        if row.get('\u7269\u54c1\u985e\u5225') in ('\u7d05\u5305', '\u79ae\u7269'):
            if row.get('\u4e0d\u53ef\u4e1f\u68c4') == '\u662f': return False
        return True
    rows = [r for r in rows if row_allowed(r['item'])]
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('Duplicate catalog listing ID')
    if 6+57*len(rows)>65500:raise ValueError('Catalog exceeds native packet size')
    return dict(source=str(source.relative_to(ROOT)),historical=True,historical_rows=original_count,
                recent_source='plantillas/recent_mall.json',
                purchases_enabled=True,initial_angel_gold=1000000,excluded=excluded,rows=rows,
                top_sale=dict(source='local completed purchases over 30 days; recent featured fallback',days=30,limit=10))


if __name__=='__main__':
    data=recover()
    if '--write' in sys.argv:
        (ROOT/'server/plantillas/item_mall.json').write_text(json.dumps(data,ensure_ascii=True)+'\n',encoding='utf8')
        print('Compiled',len(data['rows']),'offers')
    else:print(json.dumps(data,ensure_ascii=True))
