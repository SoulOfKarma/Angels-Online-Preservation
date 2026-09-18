"""
Lee logs/proxy/<sesion>_orden.jsonl y muestra, para cada mensaje del CLIENTE,
que mando el servidor justo despues.

Para que sirve: con los .bin separados por sentido no hay forma de saber que
respuesta corresponde a que pedido. Ese fue el limite concreto que impidio
identificar el dialogo de los NPC -- se veia un 0x0012 del cliente y una
rafaga de 0x0012 del servidor, pero nada permitia afirmar que una fuera la
respuesta de la otra. Con marcas de tiempo si.

Uso:
    python tools/correlacionar.py                      # la sesion mas reciente
    python tools/correlacionar.py --opcode 0x12        # solo ese pedido
    python tools/correlacionar.py --ventana 1.5        # segundos a mirar
"""
import argparse
import json
import pathlib

RAIZ = pathlib.Path(__file__).parent.parent
PROXY = RAIZ / 'logs' / 'proxy'


def cargar(ruta):
    """Lee el registro aunque los objetos no esten separados por salto de
    linea: las primeras capturas salieron todas en un solo renglon."""
    txt = ruta.read_text(encoding='utf-8')
    # Las primeras capturas separaban los objetos con los dos caracteres
    # literales barra-n en vez de un salto de linea. Se normaliza aca para
    # no perder esas capturas, que costaron una sesion de juego.
    txt = txt.replace(chr(92) + 'n{', chr(10) + '{')
    dec = json.JSONDecoder()
    ev, i, n = [], 0, len(txt)
    while i < n:
        while i < n and txt[i].isspace():
            i += 1
        if i >= n:
            break
        try:
            obj, i = dec.raw_decode(txt, i)
        except ValueError:
            break          # cola incompleta: la captura se corto al salir
        ev.append(obj)
    return ev


def novedades(ruta, desde):
    """Compara contra las capturas anteriores y marca lo que nunca se vio.

    Responde una pregunta concreta: cuando el cliente hace algo nuevo, ¿el
    servidor le manda algo que no habiamos visto? Si no llega nada nuevo,
    entonces eso que hizo el cliente lo resolvio por su cuenta y no hay nada
    que implementar del lado del servidor.
    """
    previas = [x for x in sorted(PROXY.glob('*_orden.jsonl'),
                                 key=lambda q: q.stat().st_mtime)
               if x != ruta]
    conocidos = set()
    for q in previas:
        for e in cargar(q):
            conocidos.add((e['dir'], e['opcode']))
    print(f'referencia: {len(previas)} capturas anteriores, '
          f'{len(conocidos)} pares de sentido y opcode ya vistos')
    print()

    ev = [e for e in cargar(ruta) if e['t'] >= desde]
    RUIDO = {0x0004, 0x000F, 0x0005, 0x006D, 0x0016, 0x0167, 0x0195}
    hubo = False
    for e in ev:
        if (e['dir'], e['opcode']) in conocidos:
            continue
        hubo = True
        d = 'CLIENTE ' if e['dir'] == 'c2s' else 'SERVIDOR'
        print(f"  NUEVO  [{e['t']:8.3f}] {d} 0x{e['opcode']:04X} "
              f"({e['len']} B)  {e['hex'][:80]}")
    if not hubo:
        print('  No aparecio ningun opcode nuevo.')
        print('  Si el cliente hizo algo que antes no hacia y aun asi no llego')
        print('  nada nuevo, ese algo lo resuelve el cliente por su cuenta.')

    print()
    print('linea de tiempo, sin movimiento ni latidos:')
    for e in ev:
        if e['opcode'] in RUIDO:
            continue
        marca = ' <-- NUEVO' if (e['dir'], e['opcode']) not in conocidos else ''
        d = 'CLI ->' if e['dir'] == 'c2s' else '   <- SRV'
        print(f"  [{e['t']:8.3f}] {d} 0x{e['opcode']:04X} {e['len']:5}B  "
              f"{e['hex'][:56]}{marca}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--archivo')
    ap.add_argument('--opcode', help='p.ej. 0x12; por defecto, todos')
    ap.add_argument('--ventana', type=float, default=1.0,
                    help='segundos tras el pedido que se consideran respuesta')
    ap.add_argument('--saltar-entrada', type=int, default=0,
                    help='ignora los primeros N mensajes del servidor')
    ap.add_argument('--novedades', action='store_true',
                    help='marca lo que no aparece en ninguna captura anterior')
    ap.add_argument('--desde', type=float, default=0.0,
                    help='ignora lo que pase antes de ese segundo')
    a = ap.parse_args()

    if a.archivo:
        ruta = pathlib.Path(a.archivo)
    else:
        cand = sorted(PROXY.glob('*_orden.jsonl'),
                      key=lambda p: p.stat().st_mtime)
        if not cand:
            print('No hay capturas. Corre tools/proxy.py y jugá un rato.')
            return
        ruta = cand[-1]
    print(f'captura: {ruta.name}\n')

    if a.novedades:
        novedades(ruta, a.desde)
        return

    ev = cargar(ruta)
    c2s = [e for e in ev if e['dir'] == 'c2s']
    s2c = [e for e in ev if e['dir'] == 's2c']
    print(f'{len(c2s)} del cliente, {len(s2c)} del servidor\n')

    filtro = int(a.opcode, 0) if a.opcode else None
    for i, p in enumerate(c2s):
        if filtro is not None and p['opcode'] != filtro:
            continue
        resp = [e for e in s2c
                if p['t'] < e['t'] <= p['t'] + a.ventana][a.saltar_entrada:]
        print(f"[{p['t']:8.3f}] CLIENTE 0x{p['opcode']:04X} ({p['len']} B) "
              f"{p['hex'][:48]}")
        if not resp:
            print('             (el servidor no contesto nada)')
        for r in resp[:12]:
            print(f"    +{r['t'] - p['t']:6.3f}s  SERVIDOR 0x{r['opcode']:04X} "
                  f"({r['len']} B) {r['hex'][:64]}")
        if len(resp) > 12:
            print(f'             ... y {len(resp) - 12} mas')
        print()


if __name__ == '__main__':
    main()
