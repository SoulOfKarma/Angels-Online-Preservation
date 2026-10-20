"""Que casillas se pueden pisar, para que los monstruos no atraviesen paredes.

Los datos salen de la capa de casillas del .mpc del cliente; los prepara
tools/transitable.py en plantillas/transitable.bin (ahi esta explicado de
donde sale y como se comprobo). Un mapa que no este en el fichero se trata
como todo transitable, que es como iba antes.
"""
import pathlib
import struct

_MAPAS = None
FICHERO = pathlib.Path(__file__).parent / 'plantillas' / 'transitable.bin'


def _cargar():
    global _MAPAS
    if _MAPAS is None:
        _MAPAS = {}
        try:
            b = FICHERO.read_bytes()
            n, p = struct.unpack_from('<I', b, 0)[0], 4
            for _ in range(n):
                st, w, h = struct.unpack_from('<HHH', b, p)
                p += 6
                largo = (w * h + 7) // 8
                _MAPAS[st] = (w, h, b[p:p + largo])
                p += largo
        except Exception:
            _MAPAS = {}
    return _MAPAS


def se_pisa(stage, x, y):
    m = _cargar().get(int(stage or 0))
    if m is None:
        return True
    w, h, bits = m
    if not (0 <= x < w and 0 <= y < h):
        return False
    i = y * w + x
    return bool(bits[i >> 3] & (1 << (i & 7)))


def conocido(stage):
    return int(stage or 0) in _cargar()


def _linea(desde, hasta):
    (x0, y0), (x1, y1) = desde, hasta
    n = max(abs(x1 - x0), abs(y1 - y0))
    for k in range(1, n + 1):
        yield (x0 + round((x1 - x0) * k / n), y0 + round((y1 - y0) * k / n))


def linea_libre(stage, desde, hasta):
    """Si se puede ir en linea recta de una casilla a otra sin pisar pared."""
    if not conocido(stage):
        return True
    anterior = desde
    for x, y in _linea(desde, hasta):
        if not se_pisa(stage, x, y):
            return False
        if x != anterior[0] and y != anterior[1]:
            if not (se_pisa(stage, x, anterior[1]) and se_pisa(stage, anterior[0], y)):
                return False
        anterior = x, y
    return True


def paso_hacia(stage, desde, hasta, limite=4096):
    """Un unico segmento seguro de regreso; BFS acotada para rodear paredes."""
    from collections import deque
    desde, hasta = tuple(desde), tuple(hasta)
    if desde == hasta:
        return desde
    cola, anterior = deque([desde]), {desde: None}
    while cola and len(anterior) < limite:
        x, y = cola.popleft()
        for dx, dy in ((0,1),(1,0),(0,-1),(-1,0), (1,1),(1,-1),(-1,1),(-1,-1)):
            t = x+dx, y+dy
            if t in anterior or not linea_libre(stage, (x,y), t):
                continue
            anterior[t] = (x,y)
            if t == hasta:
                while anterior[t] != desde:
                    t = anterior[t]
                return t
            cola.append(t)
    return desde


def avanzar(stage, desde, objetivo, pasos, parar_a=0):
    """Hasta `pasos` casillas desde `desde` hacia `objetivo`, bordeando paredes.

    Cada paso va a la vecina transitable que mas acerca (las ocho), y solo si
    acerca de verdad: contra una pared que no se puede rodear se queda quieto
    en vez de atravesarla o ponerse a oscilar. Para a `parar_a` casillas del
    objetivo (el alcance del ataque). Devuelve la casilla final.
    """
    x, y = int(desde[0]), int(desde[1])
    tx, ty = int(objetivo[0]), int(objetivo[1])
    if not conocido(stage):
        for _ in range(pasos):
            if max(abs(tx - x), abs(ty - y)) <= parar_a:
                break
            x += (tx > x) - (tx < x)
            y += (ty > y) - (ty < y)
        return x, y
    for _ in range(pasos):
        if max(abs(tx - x), abs(ty - y)) <= parar_a:
            break
        actual = (tx - x) ** 2 + (ty - y) ** 2
        mejor = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not dx and not dy:
                    continue
                nx, ny = x + dx, y + dy
                if not se_pisa(stage, nx, ny):
                    continue
                # En diagonal, que no corte una esquina de pared.
                if dx and dy and not (se_pisa(stage, x + dx, y) and se_pisa(stage, x, y + dy)):
                    continue
                d = (tx - nx) ** 2 + (ty - ny) ** 2
                if d < actual and (mejor is None or d < mejor[0]):
                    mejor = (d, nx, ny)
        if mejor is None:
            break
        if not linea_libre(stage, desde, (mejor[1], mejor[2])):
            break  # Un MOVE solo dibuja un segmento, no una ruta doblada.
        _, x, y = mejor
    return x, y
