import xml.etree.ElementTree as ET
import sys
sys.stdout.reconfigure(encoding='utf-8')

raw_item = open('f:/Ao Proyect/AO/data/game_xml/setting_full/setting/eng/item.xml', 'rb').read()
root_item = ET.fromstring(raw_item)
item_names = {}
for elem in root_item:
    vals = list(elem.attrib.values())
    if len(vals) >= 3:
        item_names[vals[0]] = vals[2]

raw_shop = open('f:/Ao Proyect/AO/data/game_xml/setting_full/setting/shop.xml', 'rb').read()
root_shop = ET.fromstring(raw_shop)

shops_to_check = ['1', '2', '3', '4', '5', '6', '18', '47', '62', '64', '69']
for elem in root_shop:
    sid = list(elem.attrib.values())[0]
    if sid in shops_to_check:
        items = [c.text.strip() for c in elem if c.text and c.text.strip()]
        names = [f"{it}:{item_names.get(it, '?')}" for it in items[:6]]
        print(f"Shop {sid} (total {len(items)}): {names}")

