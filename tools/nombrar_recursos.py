"""Le pone nombre a los objetos de mapa de las plantillas ya hechas.

No hace falta volver a recorrer ningun mapa: los 0x000E ya estaban guardados
en cada plantilla, lo unico que faltaba era cruzar su sprite con el 圖號 de
material.xml para saber QUE recurso es cada uno.

Solo se escribe lo que se puede sostener: si el sprite sale con un unico
nombre queda como `material`; si sale con varios, queda la lista entera en
`material_posibles`; si no sale, no se inventa nada.
"""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
from poblar_mapa import materiales, SPRITE_FIJO


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    mats = materiales()
    sin_nombre = {}
    for f in sorted((RAIZ / 'server' / 'plantillas').glob('*.json')):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(d, dict) or not d.get('recursos'):
            continue
        n_ok = n_amb = n_no = 0
        for r in d['recursos']:
            spr = r.get('sprite')
            if spr is None and r.get('hex'):
                spr = int.from_bytes(bytes.fromhex(r['hex'])[34:36], 'little')
                r['sprite'] = spr
            if spr is None:
                continue
            r.pop('material', None)
            r.pop('material_posibles', None)
            r.pop('que_es', None)
            if spr in SPRITE_FIJO:
                r['que_es'] = SPRITE_FIJO[spr]
                n_ok += 1
                continue
            n = mats.get(spr)
            if isinstance(n, str):
                r['material'] = n
                n_ok += 1
            elif n:
                r['material_posibles'] = n
                n_amb += 1
            else:
                n_no += 1
                sin_nombre[spr] = sin_nombre.get(spr, 0) + 1
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                     encoding='utf-8')
        print('%-26s %3d objetos: %3d con nombre, %d ambiguos, %d sin datos'
              % (f.name, len(d['recursos']), n_ok, n_amb, n_no))
    if sin_nombre:
        print('\nsprites que material.xml no cubre (no trae 圖號 para ellos):')
        for s, c in sorted(sin_nombre.items()):
            print('   %d x%d' % (s, c))


if __name__ == '__main__':
    main()
