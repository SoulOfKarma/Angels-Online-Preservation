import xml.etree.ElementTree as ET
import sys
sys.stdout.reconfigure(encoding='utf-8')

tree = ET.parse('f:/Ao Proyect/AO/data/game_xml/setting_full/setting/eng/msg.xml')
root = tree.getroot()

for elem in root:
    for k, v in elem.attrib.items():
        try:
            mid = int(v)
            if 330 <= mid <= 340 or 420 <= mid <= 430 or 490 <= mid <= 510:
                txt = [val for key, val in elem.attrib.items() if key != k]
                print(f"{mid}: {txt[0] if txt else ''}")
        except ValueError:
            pass

