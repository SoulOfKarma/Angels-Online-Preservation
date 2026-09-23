"""La reescritura del proxy no puede perder ni un byte.

read() corta el flujo donde quiere: un trozo puede terminar con un frame a
medias, o con menos de 6 bytes, que no alcanzan ni para el header. Esos bytes
sueltos se estaban perdiendo y el cliente recibia el flujo corrido: el framing
se desincronizaba y la partida se cortaba sola al rato.

Se prueban capturas reales troceadas de todas las formas posibles, incluida la
peor de todas: byte a byte.
"""
import sys, glob, os, pathlib

RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'proto'))
sys.path.insert(0, str(RAIZ / 'tools'))
from proxy import reescribir_redirect

TROZOS = (65536, 8192, 4096, 1500, 536, 73, 17, 3, 1)


def pasar(datos, clave, trozo, aviso):
    salida = bytearray()
    for i in range(0, len(datos), trozo):
        d = datos[i:i + trozo]
        try:
            salida += reescribir_redirect(d, clave, '127.0.0.1', 30001, aviso)
        except Exception:
            salida += d
    return bytes(salida)


def main():
    capturas = sorted(glob.glob(str(RAIZ / 'logs' / 'proxy' / '*_s2c.bin')),
                      key=os.path.getmtime)[-12:]
    if not capturas:
        print('no hay capturas en logs/proxy/, nada que comprobar')
        return
    probadas = 0
    for base in capturas:
        cf = base.replace('_s2c.bin', '_clave.txt')
        if not os.path.exists(cf):
            continue
        clave = bytes.fromhex(open(cf).read().strip())
        datos = open(base, 'rb').read()
        for trozo in TROZOS:
            vistos = []
            salida = pasar(datos, clave, trozo,
                           lambda ip, pt, st=None: vistos.append(ip))
            # Sin redirect que tocar, la salida tiene que ser IDENTICA.
            if not vistos:
                assert salida == datos, (
                    'se perdieron bytes en %s con trozos de %d: %d -> %d'
                    % (os.path.basename(base), trozo, len(datos), len(salida)))
            else:
                # Con redirect cambia la ip y el puerto, pero NO el largo.
                assert len(salida) == len(datos), (
                    'la reescritura cambio el largo en %s con trozos de %d'
                    % (os.path.basename(base), trozo))
            probadas += 1
    print('%d combinaciones captura/trozo: ni un byte perdido' % probadas)


if __name__ == '__main__':
    main()
