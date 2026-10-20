"""Reparacion reproducible de posiciones, sin importar tipos Chaos a normal.

Dino usa coordenadas de su homologo Chaos por sprite/zona. Unknown conserva
su zona y mueve solamente puntos invalidos al suelo mas cercano al generador.
"""
import collections
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'server'))
import transitable


def reparar(dino, chaos, unknown):
    grupos = collections.defaultdict(list)
    for e in chaos['spawns']:
        if e.get('monstruo'):
            grupos[e['sprite'], e.get('zona')].append(e['tile'])
    indices = collections.Counter()
    for e in dino['spawns']:
        if not e.get('monstruo'):
            continue
        key = e['sprite'], e.get('zona')
        puntos = grupos[key]
        if not puntos:
            raise ValueError('Sin homologo Chaos: %r' % (key,))
        e['tile'] = list(puntos[indices[key] % len(puntos)])
        indices[key] += 1
    for e in unknown['spawns']:
        if not e.get('monstruo') or transitable.se_pisa(176, *e['tile']):
            continue
        x, y = e['tile']
        candidatos = []
        for r in range(1, 31):
            candidatos = [(x+dx, y+dy) for dx in range(-r, r+1) for dy in range(-r, r+1)
                          if max(abs(dx), abs(dy)) == r and transitable.se_pisa(176, x+dx, y+dy)]
            if candidatos:
                break
        if not candidatos:
            raise ValueError('Zona sin suelo: %r' % e)
        e['tile'] = list(min(candidatos, key=lambda p: ((p[0]-x)**2+(p[1]-y)**2, p)))
    return dino, unknown


if __name__ == '__main__':
    base = ROOT / 'server' / 'plantillas'
    names = ['dinosaur_arena.json', 'c_dinosaur_arena.json', 'unknown_chambers.json']
    docs = [json.loads((base / n).read_text(encoding='utf-8')) for n in names]
    # Unknown Chambers ya no sale de aqui: lo reparte
    # tools/repartir_por_tag_de_ronda.py por sus TAG de ronda.
    for name, data in zip((names[0],), reparar(*docs)[:1]):
        (base / name).write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(name, 'corregido')
