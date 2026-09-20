import xml.etree.ElementTree as ET
import sys
sys.stdout.reconfigure(encoding='utf-8')

tree = ET.parse('f:/Ao Proyect/AO/data/game_xml/setting_full/setting/eng/msg.xml')
root = tree.getroot()

def show_range(start, end):
    for elem in root:
        for k, v in elem.attrib.items():
            try:
                mid = int(v)
                if start <= mid <= end:
                    txt = [val for key, val in elem.attrib.items() if key != k]
                    print(f"{mid}: {txt[0] if txt else ''}")
            except ValueError:
                pass

print("--- Angels Tutor (10100-10135) ---")
show_range(10100, 10135)

print("\n--- Magic Seller (5230-5240) ---")
show_range(5230, 5240)

print("\n--- Scroll Seller (5625-5635) ---")
show_range(5625, 5635)

