import xml.etree.ElementTree as ET
import sys
sys.stdout.reconfigure(encoding='utf-8')

p = 'f:/Ao Proyect/AO/data/game_xml/setting_full/setting/eng/msg.xml'
tree = ET.parse(p)
root = tree.getroot()

for elem in root:
    for k, v in elem.attrib.items():
        try:
            mid = int(v)
            if (5234 <= mid <= 5240) or (5627 <= mid <= 5635):
                text = [val for key, val in elem.attrib.items() if key != k]
                print(f"ID {mid}: {text[0] if text else ''}")
        except ValueError:
            pass

