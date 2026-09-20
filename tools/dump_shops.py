import xml.etree.ElementTree as ET
import json

raw_item = open('f:/Ao Proyect/AO/data/game_xml/setting_full/setting/eng/item.xml', 'rb').read()
root_item = ET.fromstring(raw_item)
item_names = {}
for elem in root_item:
    vals = list(elem.attrib.values())
    if len(vals) >= 3:
        item_names[vals[0]] = vals[2]

raw_shop = open('f:/Ao Proyect/AO/data/game_xml/setting_full/setting/shop.xml', 'rb').read()
root_shop = ET.fromstring(raw_shop)

res = {}
for elem in root_shop:
    sid = list(elem.attrib.values())[0]
    if sid in ['8', '9', '10', '11', '17', '18', '36', '39', '47', '62']:
        items = [c.text.strip() for c in elem if c.text and c.text.strip()]
        res[sid] = [f"{it}: {item_names.get(it, '?')}" for it in items]

with open('server/plantillas/shops_test.json', 'w', encoding='utf-8') as f:
    json.dump(res, f, indent=2, ensure_ascii=False)

