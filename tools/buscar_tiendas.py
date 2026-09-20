import xml.etree.ElementTree as ET
import sys
sys.stdout.reconfigure(encoding='utf-8')

# Build item id -> name map from item.xml
raw_item = open('f:/Ao Proyect/AO/data/game_xml/setting_full/setting/eng/item.xml', 'rb').read()
root_item = ET.fromstring(raw_item)
item_names = {}
for elem in root_item:
    vals = list(elem.attrib.values())
    if len(vals) >= 3:
        item_names[vals[0]] = vals[2]

# Now check shops
raw_shop = open('f:/Ao Proyect/AO/data/game_xml/setting_full/setting/shop.xml', 'rb').read()
root_shop = ET.fromstring(raw_shop)

for elem in root_shop:
    sid = list(elem.attrib.values())[0]
    items = []
    for c in elem:
        if c.text and c.text.strip():
            items.append(c.text.strip())
    names = [item_names.get(it, f"item_{it}") for it in items[:6]]
    # Check if any item contains 'Scroll', 'Stance', 'Spell', 'Magic', 'Recipe', 'Plan'
    all_names = " ".join([item_names.get(it, "") for it in items])
    if any(k in all_names for k in ['Sword', 'Spear', 'Axe', 'Bow', 'Fire', 'Earth', 'Wind', 'Water', 'Heal', 'Scroll', 'Stance', 'Hammer']):
        print(f"Shop {sid} (total {len(items)} items): {names[:5]}")

