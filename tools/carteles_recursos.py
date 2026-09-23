"""Rellena el NOMBRE de los recursos de las plantillas, desde el 0x000F.

El 0x000E coloca el recurso; el 0x000F es el mismo mensaje con el nombre en
ascii en los offsets 16..31 y un byte mas de cola. Mandando solo el 0x000E el
recurso se dibuja pero no tiene cartel, que es justo lo que se veia: en
Celestia salia "Bone Den(L)" y en el nuestro el hueco vacio.

No hace falta recorrer ningun mapa otra vez: los 0x000F ya estan en las
capturas viejas. Este script las recorre todas, junta los carteles por
entity_id y los mete en la plantilla que corresponda.
"""
import glob
import json
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).parent.parent


def carteles():
    """entity_id -> campos del 0x000F, de TODAS las capturas."""
    out = {}
    for f in sorted(glob.glob(str(RAIZ / 'logs' / 'proxy' / '*_orden.jsonl'))):
        for l in open(f, encoding='utf-8'):
            try:
                x = json.loads(l)
            except Exception:
                continue
            if x.get('dir') != 's2c' or x.get('opcode') != 0x000F:
                continue
            h = x.get('hex')
            if not h:
                continue
            b = bytes.fromhex(h)
            if len(b) < 40:
                continue
            nombre = b[16:32].split(b'\x00')[0].decode('ascii', 'replace')
            if not nombre.strip():
                continue
            # La clave NO puede ser solo el entity_id: los ids bajos se
            # repiten entre mapas distintos y el Lyceum acababa con carteles
            # de otro mapa, en otra posicion y con otro sprite. Se ata
            # tambien a la POSICION y al SPRITE, que es lo que identifica de
            # verdad a un objeto concreto.
            clave = (struct.unpack_from('<I', b, 0)[0],
                     struct.unpack_from('<II', b, 8),
                     struct.unpack_from('<H', b, 34)[0])
            out.setdefault(clave, {
                'nombre_visible': nombre,
                'estado': struct.unpack_from('<I', b, 4)[0],
                'marca_nombre': b[32],
                'cola_nombre': b[36:].hex(),
            })
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    c = carteles()
    print('carteles 0x000F distintos en las capturas: %d\n' % len(c))
    total = puestos = 0
    for f in sorted((RAIZ / 'server' / 'plantillas').glob('*.json')):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        if not isinstance(d, dict) or not d.get('recursos'):
            continue
        n = 0
        for r in d['recursos']:
            total += 1
            for k in ('nombre_visible', 'estado', 'marca_nombre', 'cola_nombre'):
                r.pop(k, None)
            px, spr = r.get('px'), r.get('sprite')
            if (px is None or spr is None) and r.get('hex'):
                crudo = bytes.fromhex(r['hex'])
                if px is None:
                    px = list(struct.unpack_from('<II', crudo, 8))
                if spr is None:
                    spr = struct.unpack_from('<H', crudo, 34)[0]
            if px is None or spr is None:
                continue
            clave = (r.get('entity_id'), (int(px[0]), int(px[1])), int(spr))
            if clave in c:
                r.update(c[clave])
                n += 1
        puestos += n
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
        print('%-26s %3d recursos, %3d con cartel' % (f.name, len(d['recursos']), n))
    print('\n%d de %d recursos con nombre' % (puestos, total))


if __name__ == '__main__':
    main()
