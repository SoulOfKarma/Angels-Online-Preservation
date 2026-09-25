"""Dice que partes de un mapa quedaron sin recorrer.

El problema que resuelve: una captura solo trae lo que se tuvo A LA VISTA, y
ningun servidor manda el mapa entero de golpe. Medido en los dos: en Celestia
solo el 4% de los spawns llega en los 2 segundos siguientes al cambio de mapa,
y en Floating Station (Taiwan) llego 1 spawn en los primeros 2 segundos y 219
repartidos a lo largo de 213. En los dos casos el bicho aparece cuando entra
en el radio de vision del jugador.

La consecuencia es que una plantilla puede estar a medias sin que se note.
Commercial Street dio 71 monstruos en el primer recorrido, 109 en el segundo y
125 en el tercero, y solo se descubrio porque el usuario desconfio del numero.

Aqui se parte el mapa en celdas y se marca cuales tienen algo. Una celda vacia
rodeada de celdas llenas es una zona por la que no se paso; una vacia en el
borde puede ser simplemente agua o pared, asi que esto ORIENTA, no decide.

    python tools/cobertura_mapa.py floating_station
    python tools/cobertura_mapa.py floating_station --celda 10
    python tools/cobertura_mapa.py commercial_street --contra copia_vieja.json
"""
import argparse
import json
import ntpath
import pathlib
import sqlite3
import struct

RAIZ = pathlib.Path(__file__).parent.parent
PAKS = pathlib.Path('G:/extracted_paks')


def medidas_del_mapa(stage):
    """Ancho y alto en casillas, leidos del .mpc del cliente.

    El .mpc no esta cifrado: empieza por 'MAP\\0' y trae ancho y alto como dos
    enteros de 32 bits en los offsets 4 y 8. Si no se encuentra el archivo se
    devuelve None y se usa la extension de lo capturado.
    """
    db = RAIZ / 'corpus' / 'content.db'
    if not db.exists():
        return None
    con = sqlite3.connect(db)
    fila = con.execute('select 地圖檔 from stage where id=?', (str(stage),)).fetchone()
    con.close()
    if not fila or not fila[0]:
        return None
    nombre = ntpath.basename(fila[0]).lower()
    for p in PAKS.glob('*/map/*'):
        if p.name.lower() == nombre:
            cab = p.read_bytes()[:12]
            if cab[:3] == b'MAP':
                return struct.unpack_from('<II', cab, 4)
    return None


def celdas(plantilla, lado):
    """{(cx,cy): cuantas entidades} a partir de spawns y objetos."""
    cuenta = {}
    for e in plantilla.get('spawns', []):
        x, y = e['tile']
        cuenta[(x // lado, y // lado)] = cuenta.get((x // lado, y // lado), 0) + 1
    for r in plantilla.get('recursos', []):
        x, y = r['px'][0] // 32, r['px'][1] // 32
        cuenta[(x // lado, y // lado)] = cuenta.get((x // lado, y // lado), 0) + 1
    return cuenta


def dibujar(cuenta, ancho, alto, lado):
    cols = (ancho + lado - 1) // lado
    filas = (alto + lado - 1) // lado
    escala = ' .:-=+*#%@'
    techo = max(cuenta.values()) if cuenta else 1
    print(f'    cada celda = {lado}x{lado} casillas; el mapa mide {ancho}x{alto}')
    print('    ' + ''.join(str(c % 10) for c in range(cols)))
    for fy in range(filas):
        linea = ''
        for fx in range(cols):
            n = cuenta.get((fx, fy), 0)
            if n == 0:
                linea += ' '
            else:
                k = 1 + int((len(escala) - 2) * (n / techo))
                linea += escala[min(k, len(escala) - 1)]
        print(f'{fy:>3} |{linea}|')
    print(f'    vacio = nada capturado;  @ = lo mas denso ({techo} entidades)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('plantilla', help='nombre sin .json, o una ruta')
    ap.add_argument('--celda', type=int, default=15,
                    help='lado de la celda en casillas (por defecto 15)')
    ap.add_argument('--contra', default=None,
                    help='otra plantilla con la que comparar, para ver que '
                         'aporto el ultimo recorrido')
    a = ap.parse_args()

    q = pathlib.Path(a.plantilla)
    if not q.exists():
        q = RAIZ / 'server' / 'plantillas' / (a.plantilla + '.json')
    d = json.loads(q.read_text(encoding='utf-8'))
    stage = d.get('stage')

    med = medidas_del_mapa(stage)
    xs = [e['tile'][0] for e in d.get('spawns', [])] + \
         [r['px'][0] // 32 for r in d.get('recursos', [])]
    ys = [e['tile'][1] for e in d.get('spawns', [])] + \
         [r['px'][1] // 32 for r in d.get('recursos', [])]
    if med:
        ancho, alto = med
    else:
        ancho, alto = (max(xs) + 1, max(ys) + 1) if xs else (1, 1)
        print('    (sin .mpc: se usa la extension de lo capturado)')

    mobs = sum(1 for e in d.get('spawns', []) if e.get('monstruo'))
    print(f'{q.name}: stage {stage}, {mobs} monstruos, '
          f'{len(d.get("spawns", [])) - mobs} NPC, '
          f'{len(d.get("recursos", []))} objetos')
    if xs:
        print(f'    lo capturado va de x {min(xs)}..{max(xs)} e y {min(ys)}..{max(ys)}')
    print()

    cuenta = celdas(d, a.celda)
    dibujar(cuenta, ancho, alto, a.celda)

    cols = (ancho + a.celda - 1) // a.celda
    filas = (alto + a.celda - 1) // a.celda
    llenas = len(cuenta)
    print(f'\n    celdas con algo: {llenas} de {cols * filas} '
          f'({100 * llenas / (cols * filas):.0f}%)')

    # Huecos sospechosos: celda vacia con al menos cinco vecinas llenas. En
    # medio de una zona recorrida, un hueco asi casi siempre es por donde no
    # se paso; pegado al borde puede ser agua o pared.
    huecos = []
    for fy in range(filas):
        for fx in range(cols):
            if (fx, fy) in cuenta:
                continue
            vec = sum(1 for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                      if (dx or dy) and (fx + dx, fy + dy) in cuenta)
            if vec >= 5:
                huecos.append((fx * a.celda + a.celda // 2,
                               fy * a.celda + a.celda // 2, vec))
    if huecos:
        print('\n    HUECOS con vecindario recorrido (casilla aproximada):')
        for x, y, v in sorted(huecos, key=lambda h: -h[2])[:10]:
            print(f'      ({x},{y})  {v} de 8 celdas vecinas tienen algo')
        print('      Pasar por ahi y volver a generar. Si sigue vacio, es'
              ' agua o pared.')
    else:
        print('\n    sin huecos rodeados: lo recorrido no deja islas vacias')

    if a.contra:
        p2 = pathlib.Path(a.contra)
        if not p2.exists():
            p2 = RAIZ / 'server' / 'plantillas' / (a.contra + '.json')
        viejo = json.loads(p2.read_text(encoding='utf-8'))
        a1 = {e['entity_id'] for e in d.get('spawns', [])}
        a0 = {e['entity_id'] for e in viejo.get('spawns', [])}
        print(f'\n    contra {p2.name}: {len(a1 - a0)} entidades nuevas, '
              f'{len(a0 - a1)} que ya no estan, {len(a1 & a0)} iguales')
        if not (a1 - a0):
            print('      el ultimo recorrido no aporto nada: el mapa esta'
                  ' saturado')


if __name__ == '__main__':
    main()
