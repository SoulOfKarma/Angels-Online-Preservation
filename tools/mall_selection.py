"""Local catalog policy built from the final available IGG item revision.

Original prices win; new listings explicitly reference the closest old product.
No Taiwan/Global item IDs are mixed into the IGG catalog.
"""
import re
import pathlib
import functools
import xml.etree.ElementTree as ET
from house_services import xml_rows
from bolsas import PIEDRAS_SELLADAS

# These are sale roots, not the vouchers/equipment awarded inside them.
# Republishing is local; original promotion dates are retained as evidence.
RECENT_SALES={
    82270:dict(period='2025 Halloween; exact sale dates not recovered',source='https://ao.igg.com/news/news.php?aid=5528',
               categories=(23,24,25,40)),
    82408:dict(date='2025-11-06',source='https://ao.igg.com/news/news.php?aid=5532',
               categories=(23,24,25)),
    82660:dict(date='2025-12-04',end='2026-01-01',source='https://ao.igg.com/news/news.php?aid=5540',
               categories=(23,24,25)),
}


def items():
    return {i:r for n in range(1,10) for i,r in xml_rows('item%s.xml'%(n if n>1 else '')).items()}


def name(row):return row.get('\u539f\u578b\u540d\u7a31','')+row.get('\u57fa\u672c\u540d\u7a31','')


@functools.lru_cache(maxsize=1)
def drop_rows():
    # drop.xml is an incremental patch table, unlike cumulative item.xml.
    # Measured and documented in extract_content.py: reading only the final
    # file silently loses most of the original equipment reward boxes.
    from mapa_del_cliente import _orden
    root=pathlib.Path(__file__).resolve().parents[1]/'extracted_paks'
    paths=list(root.glob('*/setting/drop.xml'))+list(root.glob('*/setting/eng/drop.xml'))
    paths.sort(key=lambda p:(_orden(p.relative_to(root).parts[0]),p.parent.name=='eng'))
    rows={}
    for path in paths:
        for e in ET.parse(path).getroot():
            if str(e.get('\u7de8\u865f','')).isdigit():rows[int(e.get('\u7de8\u865f'))]=dict(e.attrib)
    return rows


def category(row):
    text=name(row).lower();typ=row.get('\u7269\u54c1\u985e\u5225','')
    if re.search('furniture|baby egg|potted|wallpaper|carpet|landscape|statue egg',text):
        return 33 if re.search('wall|frame',text) else 34 if re.search('floor|carpet',text) else 35 if re.search('landscape|outside',text) else 32
    if typ=='\u5bf5\u7269' or 'pet' in text or 'fusion' in text:return 19
    if re.search('hammer|pestle|drill|attribute set',text):return 11
    if typ=='\u50a2\u4ff1':
        import casas
        native=casas.mueble(casas.item_a_mueble(int(row['\u7de8\u865f']))) or {}
        return {'\u5730\u4e0a\u64fa\u8a2d':32,'\u7246\u4e0a\u88dd\u6f62':33,'\u5730\u677f\u5730\u6bef':34,'\u5c4b\u5916\u666f\u89c0':35}.get(native.get('categoria'),32)
    if typ=='\u6a5f\u7532':return 17
    if 'potion' in text:return 16
    if re.search('scroll|mark',text) and re.search('teleport|summon|maple',text):return 27
    if re.search('20\d\d.*(taurus|aries|gemini|cancer|leo|virgo|libra|scorpio|sagittarius|capricorn|aquarius|pisces)',text):return 28
    if re.search('weapon|sword|axe|spear|longbow|staff|blade',text):return 29
    if re.search('armor|gown|garment',text):return 30
    if re.search('mount|steed|ride|skytrooper',text):return 31
    if typ in ('\u7d05\u5305','\u79ae\u7269'):return 28
    return 13


def selection():
    table=items();drops=drop_rows();memo={}
    def supported(i,path=frozenset()):
        if i in memo:return memo[i]
        if i in path or i not in table:return False
        row=table[i]
        if row.get('\u7269\u54c1\u985e\u5225') not in ('\u7d05\u5305','\u79ae\u7269'):return True
        if i in PIEDRAS_SELLADAS:return supported(PIEDRAS_SELLADAS[i],path|{i})
        drop=drops.get(int(row.get('\u52d5\u614b\u8cc7\u65991') or 0))
        children=[int(drop['item%d'%n]) for n in range(1,41) if drop.get('item%d'%n)] if drop else []
        ok=bool(children) and all(supported(c,path|{i}) for c in children)
        memo[i]=ok;return ok
    # Explicit sales evidence only. Appearing in item.xml/drop.xml does NOT
    # make an event reward, nested prize or bound variant a Mall product.
    # The Newbie box is the user's explicit On Sale addition.
    selected={81972:23,82270:28,82408:28,82660:28}
    excluded=[]
    def allowed(row):
        if not row:return False
        text=name(row).lower()
        if any(k in text for k in ('5x','x5','5 x','x 5')) and 'stone' in text:return False
        if str(row.get('\u539f\u578b\u4ecb\u9762','')) in ('5290','5480','None',''):return False
        if row.get('\u4e0d\u53ef\u4ea4\u6613')=='\u662f':return False
        if row.get('\u4e0d\u53ef\u5b58\u5009\u5eab')=='\u662f' or row.get('\u4e0d\u53ef\u5b58\u5009')=='\u662f':return False
        if row.get('\u7269\u54c1\u985e\u5225') in ('\u7d05\u5305','\u79ae\u7269'):
            if row.get('\u4e0d\u53ef\u4e1f\u68c4')=='\u662f':return False
        return True
    # Dated class-bag families already sold by the native catalog. Replace
    # each with the newest available edition; do not classify arbitrary bags
    # by name, item ID, or by having a complete loot table.
    catalog_ids={int(r.get('\u9053\u5177\u7de8\u865f') or 0) for r in xml_rows('mall.xml').values()}
    normalize=lambda text:re.sub(r'\s+',' ',re.sub(r'\b20\d\d\b','',text.lower()).replace('artisan','craftsman')).strip()
    families={normalize(name(table[i])) for i in catalog_ids if i in table
              and re.search(r'\b20\d\d\b',name(table[i]))}
    for i,row in sorted(table.items(),reverse=True):
        text=name(row)
        if not re.search(r'\b202[345]\b',text) or normalize(text) not in families:continue
        if any(normalize(name(table[j]))==normalize(text) for j in selected):continue
        if not allowed(row):continue
        if not supported(i):excluded.append(dict(item=i,name=text,reason='Missing nested server drop table'));continue
        selected.setdefault(i,category(row))
    # Original IGG Mall screenshot supplied by the user, 200 for79 AG.
    selected.update({74137:16,74147:16})
    for i in list(selected):
        if not allowed(table[i]):
            excluded.append(dict(item=i,name=name(table[i]),reason='Bound/event bag excluded by user'));selected.pop(i)
    return selected,excluded
