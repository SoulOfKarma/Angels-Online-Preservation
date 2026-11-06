"""Sincronizar las 18 skills TW y sus sprites con la tabla portable del servidor.

La migracion de XML/PAK no actualizaba client_tables.json: el combate seguia
viendo la version anterior a TW y descartaba sus subhechizos y animaciones.
No modifica cuentas ni instalaciones externas.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tw_migracion as tw


def actualizar():
    path = tw.RAIZ / 'server' / 'plantillas' / 'client_tables.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = tw.filas(tw.leer(tw.IGG / 'update26' / 'setting' / 'eng' / 'magic.xml'))
    selected = {str(i): tw.atributos(rows[str(i)]) for i in range(16832, 17108)}
    assert len(selected) == 276
    effects = set(data.get('efectos_disponibles', []))
    for root in (tw.IGG, tw.TW):
        for folder in root.glob('*/shape/magic/*'):
            if folder.is_dir() and folder.name.isdigit():
                effects.add(int(folder.name))
    data.setdefault('magic_xml', {}).update(selected)
    data['efectos_disponibles'] = sorted(effects)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print('client_tables: 276 filas TW sincronizadas; %d efectos disponibles' % len(effects))


if __name__ == '__main__':
    actualizar()
