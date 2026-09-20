import xml.etree.ElementTree as ET
import sys
sys.stdout.reconfigure(encoding='utf-8')

tree = ET.parse('f:/Ao Proyect/AO/data/game_xml/setting_full/setting/eng/msg.xml')
root = tree.getroot()

for elem in root:
    for k, v in elem.attrib.items():
        try:
            mid = int(v)
            if 5233 <= mid <= 5242 or 5626 <= mid <= 5636:
                txt = [val for key, val in elem.attrib.items() if key != k]
                print(f"{mid}: {txt[0] if txt else ''}")
        except ValueError:
            pass

