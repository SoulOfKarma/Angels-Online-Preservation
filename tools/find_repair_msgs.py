import sys, pathlib, re
sys.stdout.reconfigure(encoding='utf-8')
t = pathlib.Path(r'f:\Ao Proyect\AO\data\game_xml\msg.xml').read_text(encoding='latin-1')
for m in re.finditer(r'<[^\n]*Repair[^\n]*>', t):
    print(m.group(0))

