import xml.etree.ElementTree as ET
import json
import sys

raw_msg = open('f:/Ao Proyect/AO/data/game_xml/setting_full/setting/eng/msg.xml', 'rb').read()
root_msg = ET.fromstring(raw_msg)
msgs = {}
for elem in root_msg:
    vals = list(elem.attrib.values())
    if len(vals) >= 2:
        try:
            msgs[int(vals[0])] = vals[1]
        except ValueError:
            pass

# Check Pet Expert (6100 to 6125)
print("=== PET EXPERT (6100-6125) ===")
for mid in range(6100, 6126):
    if mid in msgs:
        print(f"{mid}: {msgs[mid]}")

# Check Skill Angel (5020 to 5030)
print("\n=== SKILL ANGEL (5020-5030) ===")
for mid in range(5020, 5031):
    if mid in msgs:
        print(f"{mid}: {msgs[mid]}")

# Check Chief Director & Bank (5028 to 5040)
print("\n=== CHIEF DIRECTOR & BANK (5028-5040) ===")
for mid in range(5028, 5041):
    if mid in msgs:
        print(f"{mid}: {msgs[mid]}")

