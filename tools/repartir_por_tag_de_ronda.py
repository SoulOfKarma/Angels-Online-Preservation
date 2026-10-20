"""Reparte los monstruos de una instancia por los puntos de RONDA de su zona.

EL PATRON DEL .mpc. En Unknown Chambers (stage 176) cada generador con zona
impar apunta a un TAG de UN solo punto, pegado a la entrada, y el TAG
siguiente trae los puntos por donde de verdad se reparten:

    zona 81 (1 punto, (36,20))  -> TAG 82 con 10 puntos por todo el pasillo
    zona 91 (2 puntos)          -> TAG 92 con  7 puntos por la sala
    zona 103 (4 puntos)         -> TAG 104 y 105 con 31 y 23 puntos

y los conteos cuadran: 7 bichos para 7 puntos, 120 para 54. Repartiendo solo
alrededor del punto del +21, con 25 por generador y separacion 5,
poblar_del_cliente abria el anillo hasta 34 casillas y llenaba la sala del
Archeology Profe con lo que tenia que estar por todo el mapa.

COMO SE REPARTE AQUI:
  * los puntos de ronda son los del TAG zona+1 (y zona+2 si el siguiente
    tambien es de ronda y no pertenece a otro generador), solo los que
    caen en la MISMA isla de suelo que el generador;
  * cada bicho va a un punto por turnos y a una casilla libre a radio <= 3
    de el, que se vea en linea recta desde el punto (no a traves de pared);
  * la separacion empieza en 3 y baja si no cabe, en vez de abrir el radio;
  * los de zona 0 se quedan cerca de su generador, radio <= 6, misma isla;
  * cada monstruo lleva 'zona' = la del +21, que es la que mira
    GENERATOR_ALIVE para abrir las puertas.

Conserva entity_id y orden de la plantilla.

    python tools/repartir_por_tag_de_ronda.py --stage 176 --ronda-sin-zona 101,102,104,105 [--poner]
"""
import argparse
import collections
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import mapa_del_cliente as cli           # noqa: E402
import poblar_del_cliente as pob         # noqa: E402
sys.path.insert(0, str(RAIZ / 'server'))
import importlib.util as _iu             # noqa: E402
_sp = _iu.spec_from_file_location('transitable_srv', RAIZ / 'server' / 'transitable.py')
tr = _iu.module_from_spec(_sp)
_sp.loader.exec_module(tr)
import login as lg                       # noqa: E402

RADIO_PUNTO = 3
RADIO_SIN_ZONA = 6


def islas(stage, ancho, alto):
    comp, n = {}, 0
    for y in range(alto):
        for x in range(ancho):
            if (x, y) in comp or not tr.se_pisa(stage, x, y):
                continue
            n += 1
            pila = [(x, y)]
            comp[(x, y)] = n
            while pila:
                a, b = pila.pop()
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    t = (a + dx, b + dy)
                    if t not in comp and tr.se_pisa(stage, *t):
                        comp[t] = n
                        pila.append(t)
    return comp


def puntos_de_ronda(m, g, zonas_generador, comp, sin_zona=()):
    z = g['zona']
    base = list(g['puntos'] or [g['tile']])
    isla = {comp.get(tuple(p)) for p in base} - {None}
    if not z and sin_zona and g['cantidad'] > 1:
        # TAGs de ronda que el mapa no ata a ningun generador (en el 176, el
        # 101 y el 102 caen en la sala de los generadores sin zona). Solo los
        # puntos de la misma isla y a <= 25 casillas.
        gx, gy = g['tile']
        pts = [tuple(p) for t in sin_zona for p in (m.tags.get(t) or [])
               if comp.get(tuple(p)) in isla
               and max(abs(p[0] - gx), abs(p[1] - gy)) <= 25]
        return (pts or base), isla
    if not z or g['cantidad'] <= 1:
        return base, isla       # jefes y guardianes sueltos: en su punto
    ronda = []
    for siguiente in (z + 1, z + 2):
        pts = m.tags.get(siguiente) or []
        if siguiente in zonas_generador or len(pts) < 2:
            break
        ronda += [tuple(p) for p in pts if comp.get(tuple(p)) in isla]
    return (ronda or base), isla


def _libre(centro, radio, usadas, sep, isla, comp, stage):
    mejores = []
    for r in range(0, radio + 1):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if r and max(abs(dx), abs(dy)) != r:
                    continue
                t = (centro[0] + dx, centro[1] + dy)
                if comp.get(t) not in isla or t in usadas:
                    continue
                if not all(tr.se_pisa(stage, t[0] + ex, t[1] + ey)
                           for ex in (-1, 0, 1) for ey in (-1, 0, 1)):
                    continue
                if not tr.linea_libre(stage, centro, t):
                    continue
                if sep > 1 and any((t[0] + ex, t[1] + ey) in usadas
                                   for ex in range(-sep + 1, sep)
                                   for ey in range(-sep + 1, sep)):
                    continue
                mejores.append(t)
        if mejores:
            return mejores[0]
    return None


def repartir(stage, d, sin_zona=()):
    m = cli.mapa(stage)
    comp = islas(stage, m.ancho, m.alto)
    fuera = pob.zonas_de_evento(stage)
    gens = [g for g in m.generadores() if not (g['zona'] and g['zona'] in fuera)]
    zonas_generador = {g['zona'] for g in m.generadores() if g['zona']}
    # Los spawns salen en el orden de los generadores (poblar_del_cliente).
    mobs = [e for e in d['spawns'] if e.get('npc_type') is not None
            and (e.get('monstruo') or e.get('apagado'))]
    usadas = set()
    i = 0
    informe = []
    for g in gens:
        n = max(1, min(pob.TOPE_POR_GENERADOR, g['cantidad']))
        grupo = mobs[i:i + n]
        i += n
        if any(e['npc_type'] != g['tipo'] for e in grupo):
            raise SystemExit('la plantilla no sigue el orden de los generadores '
                             '(tipo %s en %r)' % (g['tipo'], [e['nombre'] for e in grupo][:3]))
        pts, isla = puntos_de_ronda(m, g, zonas_generador, comp, sin_zona)
        radio = RADIO_PUNTO if (g['zona'] or len(pts) > 1) else RADIO_SIN_ZONA
        for k, e in enumerate(grupo):
            p = pts[k % len(pts)]
            t = None
            for sep in (3, 2, 1):
                t = _libre(p, radio, usadas, sep, isla, comp, stage)
                if t:
                    break
            t = t or tuple(p)
            usadas.add(t)
            e['tile'] = [t[0], t[1]]
            e['zona'] = int(g['zona'] or 0)
        informe.append((g['tipo'], grupo[0]['nombre'] if grupo else '?', n,
                        g['zona'], len(pts)))
    # Lo que sobra solo puede ser de una zona que el mapa saca POR EVENTO
    # (GENERATE / ENABLE_GENERATOR): no nace de inicio, lo crea _generar_zona.
    tipos_evento = {g['tipo']: g['zona'] for g in m.generadores()
                    if g['zona'] and g['zona'] in fuera}
    for e in mobs[i:]:
        if e['npc_type'] not in tipos_evento:
            raise SystemExit('sobra %s en la plantilla' % e['nombre'])
        e['apagado'] = True
        e['zona'] = int(tipos_evento[e['npc_type']])
        pts = m.tags.get(e['zona']) or []
        if pts:
            e['tile'] = list(pts[0])        # donde lo saca _generar_zona
        informe.append((e['npc_type'], e['nombre'] + ' (por evento)', 1, e['zona'], 0))
    return informe


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', type=int, required=True)
    ap.add_argument('--poner', action='store_true')
    ap.add_argument('--ronda-sin-zona', default='',
                    help='TAGs de ronda para los generadores sin zona, p.ej. 101,102')
    a = ap.parse_args()
    f = RAIZ / 'server' / 'plantillas' / lg.PLANTILLAS_POR_STAGE[a.stage]
    d = json.loads(f.read_text(encoding='utf-8'))
    sz = tuple(int(x) for x in a.ronda_sin_zona.split(',') if x)
    for fila in repartir(a.stage, d, sz):
        print('  %5d %-28s x%-3d zona %-4s puntos %d' % fila)
    if a.poner:
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f.name, 'escrito')


if __name__ == '__main__':
    main()
