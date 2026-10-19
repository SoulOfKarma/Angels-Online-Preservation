"""Apunta en cada monstruo de una plantilla de instancia la ZONA de su generador.

POR QUE. Los portales de varias instancias (Cloud-top Land, Leviathan's
Bedroom, Botti Palace, Dinosaur Arena...) solo dejan pasar cuando la zona de
la sala esta limpia: GENERATOR_ALIVE(zona) = 0. El servidor sacaba la zona de
cada monstruo por cercania a los puntos de la zona (RADIO_ZONA), y como los
de plantilla estan repartidos por la sala, casi no los contaba: de los 15 Sky
Soldier de la zona 76 de Cloud-top Land veia 3. Matando esos 3 se abria.

COMO. Cada monstruo se asigna a la zona del generador de SU TIPO cuyo punto le
queda mas cerca. Los de generadores sin zona (zona 0) no llevan zona.

    python tools/zonas_de_plantilla.py --stage 111 [--poner]
"""
import argparse
import collections
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import mapa_del_cliente as cli          # noqa: E402
sys.path.insert(1, str(RAIZ / 'server'))
import login as lg                      # noqa: E402


def asignar(stage, d):
    por_tipo = collections.defaultdict(list)       # tipo -> [(zona, punto)]
    for g in cli.mapa(stage).generadores():
        if not g.get('zona'):
            continue
        for p in (g['puntos'] or [g['tile']]):
            por_tipo[g['tipo']].append((g['zona'], tuple(p)))
    cuenta = collections.Counter()
    for e in d['spawns']:
        cand = por_tipo.get(e.get('npc_type'))
        if not e.get('monstruo'):
            e.pop('zona', None)
            continue
        if not cand:
            # Su tipo no sale de ninguna zona: 0 = sin zona, explicito, para
            # que el servidor no se la adjudique por cercania a otra.
            e['zona'] = 0
            continue
        x, y = e['tile']
        zona = min(cand, key=lambda zp: max(abs(zp[1][0] - x), abs(zp[1][1] - y)))[0]
        e['zona'] = int(zona)
        cuenta[int(zona)] += 1
    return cuenta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', type=int, required=True)
    ap.add_argument('--poner', action='store_true')
    a = ap.parse_args()
    f = RAIZ / 'server' / 'plantillas' / lg.PLANTILLAS_POR_STAGE[a.stage]
    d = json.loads(f.read_text(encoding='utf-8'))
    cuenta = asignar(a.stage, d)
    print('%s: %s' % (f.name, dict(sorted(cuenta.items()))))
    if a.poner:
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
        print('escrito')


if __name__ == '__main__':
    main()
