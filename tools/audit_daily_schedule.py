"""Read-only targeted evidence: calendar definitions and Party Angel actions."""
import pathlib
import sys
import json
import xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'server'),str(ROOT/'tools')]
from house_services import xml_rows
import recent_mall
sys.stdout.reconfigure(encoding='utf-8')

for name in ('event.xml','spevent.xml'):
    for path in (ROOT/'extracted_paks').glob('*/setting/**/'+name):
        tree=ET.parse(path).getroot()
        print(str(path.relative_to(ROOT)),tree.tag,len(tree),[dict(x.attrib) for x in list(tree)[:2]])

for key,row in recent_mall.datos()['nodes'].items():
    if recent_mall.datos()['node_owners'].get(key)=='Party Angel':print('PARTY',key,row)
print('PARTY_MAGIC',xml_rows('magic.xml').get(14955))
strings=xml_rows('string.xml')
for i in (3040,3042,3044,3046,3048,3050,3052,3703):print('HELP',i,strings.get(i))
for i,r in strings.items():
    text=r.get('\u6587\u5b57','')
    if ('Star Key' in text or 'Star Blessing' in text) and len(text)<1200:print('STAR_HELP',i,text)
for n in range(1,10):
    row=xml_rows('item%s.xml'%(n if n>1 else '')).get(58283)
    if row:print('STAR_KEY',row)
