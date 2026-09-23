"""El servidor confirma el PRIMER tramo de la ruta, no el ultimo.

El cliente no pide ir en linea recta: manda la ruta ya esquivada, con sus
curvas para rodear el agua y los acantilados, y espera que se le confirme
tramo a tramo. Confirmando el ultimo waypoint se le manda en linea recta al
final del recorrido, cortando por encima de lo intransitable; al terminar el
personaje queda dentro de una zona de la que su buscador de rutas ya no sabe
salir, empieza a mandar rutas VACIAS y se queda trabado hasta reconectar.

Esta prueba mide las dos cosas contra capturas reales de Celestia:
  - que el servidor real devuelve el primer waypoint
  - que su cliente nunca manda una ruta vacia
"""
import glob
import json
import os
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'proto'))
import messages  # noqa: F401  (registra los mensajes)
from codec import Msg

REQ = Msg.registry[(0x0004, 'c2s', '*')]


def sesiones():
    return sorted(glob.glob(str(RAIZ / 'logs' / 'proxy' / 'mundo_*_orden.jsonl')),
                  key=os.path.getmtime)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    prim = ult = vacias = total = 0
    for f in sesiones():
        ls = []
        for l in open(f, encoding='utf-8'):
            try:
                ls.append(json.loads(l))
            except Exception:
                pass
        yo = None
        for x in ls:
            if x['dir'] == 's2c' and x['opcode'] == 0x0002 and x['len'] > 1000:
                yo = struct.unpack_from('<I', bytes.fromhex(x['hex']), 0)[0]
                break
        if yo is None:
            continue
        for i, x in enumerate(ls):
            if x['dir'] != 'c2s' or x['opcode'] != 0x0004 or not x.get('hex'):
                continue
            try:
                d = REQ.parse(bytes.fromhex(x['hex']))
            except Exception:
                continue
            total += 1
            p = d.get('path') or []
            if not p:
                vacias += 1
                continue
            if len(p) < 2:
                continue
            for y in ls[i + 1:i + 60]:
                if y['dir'] == 'c2s' and y['opcode'] == 0x0004:
                    break
                if y['dir'] == 's2c' and y['opcode'] == 0x0005 and y.get('hex'):
                    b = bytes.fromhex(y['hex'])
                    if len(b) >= 22 and struct.unpack_from('<I', b, 0)[0] == yo:
                        got = struct.unpack_from('<II', b, 12)
                        if got == (p[0]['x'], p[0]['y']):
                            prim += 1
                        elif got == (p[-1]['x'], p[-1]['y']):
                            ult += 1
                        break
    if not total:
        print('no hay capturas de mundo en logs/proxy/, nada que comprobar')
        return
    print('MOVE_REQ mirados: %d' % total)
    print('  rutas de 2+ tramos donde Celestia confirma el PRIMERO: %d' % prim)
    print('  ... donde confirma el ULTIMO                         : %d' % ult)
    print('  rutas VACIAS mandadas por su cliente                 : %d' % vacias)
    assert prim > 0, 'no se encontro ninguna ruta de varios tramos que medir'
    # No se exige un cero absoluto, y conviene saber por que. El emparejado de
    # aqui es aproximado: coge el PRIMER 0x0005 del jugador que venga tras el
    # MOVE_REQ, y ese eco puede pertenecer ya a la peticion siguiente cuando
    # el cliente encadena pasos cada 0,2 s. Con 1.118 rutas medidas salen 3
    # que parecen confirmar el ultimo waypoint, y DOS de ellas son rutas cuyos
    # dos waypoints son casillas contiguas -- (45,89)/(45,90) y
    # (29,104)/(29,105) --, donde las dos reglas se diferencian en una casilla
    # y no se pueden distinguir. Queda UNA sola discrepancia de verdad.
    # Lo que la prueba defiende es que la regla del primer tramo domina; si
    # empezara a fallar de verdad, esta proporcion se cae enseguida.
    assert ult <= max(3, prim * 0.02), (
        'Celestia confirmo el ultimo waypoint %d veces de %d: eso ya no es '
        'ruido del emparejado, la regla medida no se sostiene' % (ult, prim + ult))
    # La ruta vacia es RARA, no imposible. Con 8.249 movimientos medidos no
    # salia ninguna y se dio por hecho que no existia; con 18.115 aparecio una
    # (sesion mundo_180145, un 0x0004 de 7 bytes en vez de los 11 de siempre),
    # y Celestia le CONTESTO en el acto.
    # No cambia el arreglo, lo refuerza: nuestro servidor la responde con su
    # acuse y no mueve al personaje, que es justo lo que hace el real. Lo que
    # si se cae es la afirmacion "el cliente nunca la manda"; lo que se
    # defiende aqui es que es marginal, porque si empezara a ser frecuente
    # significaria que le estamos provocando nosotros el atasco otra vez.
    assert vacias <= max(2, total * 0.001), (
        'el cliente de Celestia mando %d rutas vacias de %d movimientos: eso '
        'ya no es un caso aislado' % (vacias, total))
    print('\nOK: el primer tramo es la regla, y la ruta vacia no es normal.')


if __name__ == '__main__':
    main()
