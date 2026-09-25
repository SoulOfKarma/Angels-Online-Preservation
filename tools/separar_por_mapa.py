"""Parte una sesion del proxy en un archivo por mapa.

poblar_mapa.py le asigna TODOS los 0x0008 y 0x000E de las sesiones que se le
pasen al stage que se le diga. Eso vale cuando la sesion es de un solo mapa,
que era el caso mientras se capturaba en Celestia: alli cada cambio de mapa
abria conexion nueva y el proxy lo dejaba en su propio archivo.

En el cliente de Taiwan (8.7.5.7) no es asi: el 0x000C llega DENTRO de la
misma sesion y se siguen recibiendo spawns del mapa nuevo por la misma
conexion. Una sola sesion puede traer cinco mapas. Pasarsela entera a
poblar_mapa.py mete los bichos de un mapa en la plantilla de otro, que es un
error silencioso y dificil de ver despues.

Aqui se corta por 0x000C y se escribe un archivo por tramo. El stage inicial
no sale de la sesion -- el primer 0x000C ya es el del PRIMER cambio, no el de
la entrada -- asi que hay que decirlo con --stage-inicial; si no se dice, los
registros previos al primer cambio se descartan, que es lo seguro.

    python tools/separar_por_mapa.py logs/proxy/mundo_023131_269495_orden.jsonl \
        --stage-inicial 416 --salida logs/proxy/partido
"""
import argparse
import collections
import json
import pathlib
import struct

# Lo unico que consume poblar_mapa.py: spawns y objetos de mapa.
INTERESAN = (0x0008, 0x000E)


def tramos(registros, stage_inicial=None):
    """Devuelve {stage: [registros]} cortando por cada 0x000C."""
    actual = stage_inicial
    salida = collections.defaultdict(list)
    for r in registros:
        h = r.get('hex') or ''
        if r.get('dir') == 's2c' and r.get('opcode') == 0x000C and len(h) >= 8:
            actual = struct.unpack_from('<I', bytes.fromhex(h), 0)[0]
            continue
        if actual is None:
            # Antes del primer cambio y sin --stage-inicial: no se sabe de que
            # mapa son. Se tiran en vez de adivinar.
            continue
        if r.get('opcode') in INTERESAN:
            salida[actual].append(r)
    return salida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sesion')
    ap.add_argument('--stage-inicial', type=int, default=None,
                    help='mapa en el que empieza la sesion; sin esto se '
                         'descarta todo lo anterior al primer 0x000C')
    ap.add_argument('--salida', default=None,
                    help='carpeta donde dejar los trozos (por defecto, al lado)')
    a = ap.parse_args()

    origen = pathlib.Path(a.sesion)
    destino = pathlib.Path(a.salida) if a.salida else origen.parent / 'partido'
    destino.mkdir(parents=True, exist_ok=True)

    regs = []
    for linea in origen.open(encoding='utf-8'):
        try:
            regs.append(json.loads(linea))
        except json.JSONDecodeError:
            continue

    partes = tramos(regs, a.stage_inicial)
    base = origen.name.replace('_orden.jsonl', '')
    for stage, rr in sorted(partes.items()):
        q = destino / f'{base}_stage{stage}_orden.jsonl'
        with q.open('w', encoding='utf-8', newline='') as fh:
            for r in rr:
                fh.write(json.dumps(r, ensure_ascii=False) + '\n')
        sp = sum(1 for r in rr if r['opcode'] == 0x0008)
        ob = sum(1 for r in rr if r['opcode'] == 0x000E)
        print(f'  stage {stage:>4}: {sp:>5} spawns, {ob:>5} objetos -> {q.name}')
    if not partes:
        print('  nada que separar')


if __name__ == '__main__':
    main()
