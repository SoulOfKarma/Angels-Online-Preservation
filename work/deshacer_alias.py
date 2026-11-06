"""Deshace la primera reparacion de ALIAS (26/10 ~17:15): restaura
update26.pak / .bak de los respaldos previos y, desde ellos, los 51 archivos
de extracted_paks/update26 que se tocaron."""
import pathlib, shutil, sys
R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'tools'))
import pak_tool
C = pathlib.Path(r'C:\AO\Angels Online')
B = R / 'work' / 'backup'
shutil.copy2(B / 'update26_antes_alias.pak', C / 'update26.pak')
shutil.copy2(B / 'update26bak_antes_alias.pak', C / 'update26.pak.bak')
data = (C / 'update26.pak').read_bytes()
es = {e['nombre'].upper(): e for e in pak_tool.leer_indice(data)[0]}
n = 0
for f in (R / 'extracted_paks' / 'update26' / 'setting').rglob('*.xml'):
    k = str(f.relative_to(R / 'extracted_paks' / 'update26')).replace('/', '\\').upper()
    if k in es:
        raw = pak_tool.leer_entrada(data, es[k])
        if raw != f.read_bytes():
            f.write_bytes(raw)
            n += 1
print('restaurados en extracted_paks:', n)
