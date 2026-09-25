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


def recorrido(sesiones, lado):
    """Celdas por las que paso el jugador, segun sus MOVE_REQ.

    Es mejor referencia que las celdas con bichos. Una celda sin nada puede
    ser agua o pared, y entonces esta bien que este vacia; pero si el jugador
    PASO por ahi y aun asi no llego ningun spawn, esa zona esta de verdad
    vacia. Y si no paso, no se sabe nada de ella: hay que ir.

    Se intento sacar el dato de transitable del propio archivo de mapa. El
    .mpc se lee sin problema -- cabecera 'MAP', ancho y alto en los offsets 4
    y 8, y una tabla de 7 bytes por casilla que arranca en el 96, confirmada
    porque 96 + ancho*alto*7 da exactamente el offset que guarda la cabecera
    en el 52. Pero de esos 7 bytes cinco son siempre cero, y los dos que
    varian no son transitable: el jugador de prueba camino por los dos
    valores del byte 2 casi por igual (468 y 462 casillas), y de los 18
    valores del byte 0 piso todos los que tienen casillas suficientes. La
    capa estara en alguno de los bloques posteriores del archivo.
    """
    paso = set()
    for f in sesiones:
        for linea in open(f, encoding='utf-8'):
            try:
                r = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if r.get('dir') != 'c2s' or r.get('opcode') != 4:
                continue
            b = bytes.fromhex(r.get('hex') or '')
            if len(b) < 7:
                continue
            cx, cy = struct.unpack_from('<HH', b, 0)
            paso.add((cx // 32 // lado, cy // 32 // lado))
            for k in range(b[4]):
                if 7 + k * 4 + 4 <= len(b):
                    x, y = struct.unpack_from('<HH', b, 7 + k * 4)
                    paso.add((x // 32 // lado, y // 32 // lado))
    return paso


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


def dibujar(cuenta, ancho, alto, lado, paso=None):
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
            if n:
                k = 1 + int((len(escala) - 2) * (n / techo))
                linea += escala[min(k, len(escala) - 1)]
            elif paso and (fx, fy) in paso:
                linea += '~'          # se paso por ahi y no habia nada
            else:
                linea += ' '
        print(f'{fy:>3} |{linea}|')
    print(f'    @ = lo mas denso ({techo} entidades)')
    if paso:
        print('    ~ = se paso por ahi y no habia nada: esta bien vacio')
        print('    vacio = NO se paso: no se sabe que hay')
    else:
        print('    vacio = nada capturado (puede ser agua o zona sin recorrer)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('plantilla', help='nombre sin .json, o una ruta')
    ap.add_argument('--celda', type=int, default=15,
                    help='lado de la celda en casillas (por defecto 15)')
    ap.add_argument('--contra', default=None,
                    help='otra plantilla con la que comparar, para ver que '
                         'aporto el ultimo recorrido')
    ap.add_argument('--sesiones', nargs='*', default=None,
                    help='capturas del mismo mapa; marca por donde se paso, '
                         'para separar "vacio de verdad" de "no se fue"')
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
    paso = recorrido(a.sesiones, a.celda) if a.sesiones else None
    dibujar(cuenta, ancho, alto, a.celda, paso)

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
                pisada = bool(paso) and (fx, fy) in paso
                huecos.append((fx * a.celda + a.celda // 2,
                               fy * a.celda + a.celda // 2, vec, pisada))
    if huecos:
        faltan = [h for h in huecos if not h[3]]
        vacios = [h for h in huecos if h[3]]
        if faltan:
            print('\n    HUECOS POR VISITAR (casilla aproximada):')
            for x, y, v, _ in sorted(faltan, key=lambda h: -h[2])[:10]:
                print(f'      ({x},{y})  {v} de 8 celdas vecinas tienen algo'
                      + ('  y no se paso por ahi' if paso else ''))
            print('      Pasar por ahi y volver a generar la plantilla.')
        if vacios:
            print(f'\n    {len(vacios)} huecos por los que SI se paso: estan'
                  ' vacios de verdad (agua, pared o claro).')
        if not paso:
            print('      Con --sesiones se separa "vacio de verdad" de'
                  ' "no se fue".')
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
