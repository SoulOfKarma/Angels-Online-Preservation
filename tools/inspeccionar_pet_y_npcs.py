import xml.etree.ElementTree as ET
import sys
sys.stdout.reconfigure(encoding='utf-8')

p_xml = 'f:/Ao Proyect/AO/data/game_xml/setting_full/setting/eng/pet.xml'
tree = ET.parse(p_xml)
root = tree.getroot()

pet_map = {}
for elem in root:
    pid = elem.attrib.get('編號')
    if pid in ['3001', '3013', '3025', '3037', '3049', '3061', '3073', '3050']:
        print(f"Pet {pid}: name={elem.attrib.get('名稱')}, sprite={elem.attrib.get('圖號1')}, speed={elem.attrib.get('移動速度')}, type={elem.attrib.get('寵物類型')}")

