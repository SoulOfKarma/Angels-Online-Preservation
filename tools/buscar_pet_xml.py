import xml.etree.ElementTree as ET

tree = ET.parse('extracted_paks/update26/setting/eng/pet.xml')
for el in tree.iter():
    nom = el.attrib.get('名稱', '')
    if any(w in nom.lower() for w in ['shark', 'crimson', 'ritualist', 'demoness']):
        print(el.attrib.get('編號'), el.attrib.get('圖號1'), nom)
