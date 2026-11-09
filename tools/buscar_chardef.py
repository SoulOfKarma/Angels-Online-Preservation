import pathlib, sys
sys.path.insert(0, '.')
from tools import pak_tool

c_ao = pathlib.Path('C:/AO/Angels Online')
for p in sorted(c_ao.glob('*.pak')):
    try:
        b = p.read_bytes()
        entradas, _ = pak_tool.leer_indice(b)
        for meta in entradas:
            nom = meta.get('nombre', meta.get('path', ''))
            if '42390' in nom:
                print(p.name, nom)
    except Exception: pass
