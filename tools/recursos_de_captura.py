"""Copia a una plantilla los RECURSOS (vetas, arboles...) de una captura del proxy.

POR QUE. Las Territory Areas se poblaron desde el .mpc del cliente y sus
recursos salian sin nombre: el nombre solo viaja en el 0x000F del servidor
("Copper(M)", "Bone Den(L)"...), que el .mpc no trae. Celestia manda por cada
recurso el 0x000E (el objeto) y el 0x000F (el cartel con el nombre).

Se guardan como las plantillas capturadas: 'crudo' (el 0x000E tal cual) y
'nombre_visible', 'marca_nombre' (byte 32 del 0x000F) y 'cola_nombre' (36..43),
que es lo que lee login.objeto_nombrado(). Los monstruos no se tocan.

    python tools/recursos_de_captura.py --stage 50 --captura logs/proxy/mundo_130341_992186_orden.jsonl [--poner]
"""
import argparse
import json
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import login as lg       # noqa: E402


def recursos(captura):
    objetos, carteles = {}, {}
    for linea in open(captura, encoding='utf-8'):
        e = json.loads(linea)
        if e.get('dir') != 's2c' or not e.get('hex'):
            continue
        b = bytes.fromhex(e['hex'])
        if e['opcode'] == 0x000E and len(b) >= 43:
            objetos[struct.unpack_from('<I', b, 0)[0]] = b[:43]
        elif e['opcode'] == 0x000F and len(b) >= 44:
            carteles[struct.unpack_from('<I', b, 0)[0]] = b[:44]
    salida = []
    for eid, b in objetos.items():
        if struct.unpack_from('<H', b, 34)[0] == 60001:
            continue      # los tornados los dibuja portales.json: no duplicarlos
        px = list(struct.unpack_from('<II', b, 8))
        r = {'entity_id': eid, 'sprite': struct.unpack_from('<H', b, 34)[0],
             'capa': struct.unpack_from('<I', b, 4)[0], 'px': px,
             'tile': [px[0] // 32, px[1] // 32], 'crudo': b.hex(),
             'copiado_de': pathlib.Path(captura).name}
        c = carteles.get(eid)
        if c:
            r['nombre_visible'] = c[16:32].split(b'\0')[0].decode('ascii', 'replace')
            r['marca_nombre'] = c[32]
            r['cola_nombre'] = c[36:44].hex()
        salida.append(r)
    return salida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', type=int, required=True)
    ap.add_argument('--captura', required=True)
    ap.add_argument('--poner', action='store_true')
    a = ap.parse_args()
    rec = recursos(a.captura)
    con_nombre = sum(1 for r in rec if r.get('nombre_visible'))
    print('%d recursos, %d con nombre' % (len(rec), con_nombre))
    for r in rec[:8]:
        print('  ', r['sprite'], r['tile'], r.get('nombre_visible'))
    if a.poner:
        f = RAIZ / 'server' / 'plantillas' / lg.PLANTILLAS_POR_STAGE[a.stage]
        d = json.loads(f.read_text(encoding='utf-8'))
        # La captura solo trae lo que estuvo a la vista: se conservan los de la
        # plantilla que no esten en ella (mismo sprite a <= 2 casillas).
        def _cerca(x, y):
            return (x['sprite'] == y['sprite'] and
                    max(abs(x['tile'][0] - y['tile'][0]), abs(x['tile'][1] - y['tile'][1])) <= 2)
        viejos = [r for r in d.get('recursos', []) if not any(_cerca(r, n) for n in rec)]
        d['recursos'] = rec + viejos
        print('  + %d de la plantilla que la captura no vio' % len(viejos))
        d['_nota_recursos'] = ('Recursos copiados de la captura de Celestia %s '
                               '(tools/recursos_de_captura.py), con su nombre.'
                               % pathlib.Path(a.captura).name)
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f.name, 'escrito')


if __name__ == '__main__':
    main()
