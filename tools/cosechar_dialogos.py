"""Recorre TODAS las capturas y saca los dialogos y tiendas de cada NPC.

No hace falta decirle de que mapa es cada sesion: los entity_id de los NPC no
se repiten entre mapas, asi que con un indice global entidad -> (mapa, NPC)
se identifica solo.

    python tools/cosechar_dialogos.py --salida server/plantillas/npcs.json
"""
import argparse
import glob
import json
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
from leer_dialogos import parsear_dialogo, textos, tiendas


def indice():
    """entidad -> (stage, mapa, nombre, npc_type) de todos los NPC poblados."""
    sys.path.insert(0, str(RAIZ / 'server'))
    import app
    out = {}
    # app.mapas_poblados() y no login.PLANTILLAS_POR_STAGE: el Angel Lyceum y
    # el Fighting Palace viven en la tabla aparte, y el Lyceum es justo donde
    # mas NPC se han clicado.
    for st, fn in app.mapas_poblados().items():
        p = RAIZ / 'server' / 'plantillas' / fn
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding='utf-8'))
        for e in d.get('spawns', []):
            # Alguna plantilla vieja no trae entity_id ni npc_type; se salta
            # en vez de reventar.
            if e.get('monstruo') or 'entity_id' not in e or 'npc_type' not in e:
                continue
            out[e['entity_id']] = (st, fn[:-5], e.get('nombre', '?'), e['npc_type'])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--salida', default='server/plantillas/npcs.json')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')

    idx = indice()
    print('%d NPC en el indice' % len(idx))
    msg, sh = textos(), tiendas()
    npcs = {}
    vistos = set()
    for f in sorted(glob.glob(str(RAIZ / 'logs' / 'proxy' / 'mundo_*orden.jsonl'))):
        try:
            regs = [json.loads(l) for l in open(f, encoding='utf-8', errors='replace')
                    if l.strip()]
        except Exception:
            continue
        ult = None
        for r in regs:
            if r['dir'] == 'c2s' and r['opcode'] in (0x05, 0x0B) and r.get('hex'):
                b = bytes.fromhex(r['hex'])
                if len(b) >= 4:
                    e = struct.unpack_from('<I', b, 0)[0]
                    if e in idx:
                        ult = e
            if ult is None or r['dir'] != 's2c':
                continue
            st, mapa, nom, tipo = idx[ult]
            k = str(tipo)
            if r['opcode'] == 0x12 and r['len'] >= 12:
                d = parsear_dialogo(bytes.fromhex(r['hex']))
                if d:
                    npcs.setdefault(k, {'nombre': nom, 'stage': st, 'mapa': mapa})
                    npcs[k]['dialogo'] = d
                    vistos.add(mapa)
            elif r['opcode'] == 0x34 and r['len'] >= 2:
                npcs.setdefault(k, {'nombre': nom, 'stage': st, 'mapa': mapa})
                npcs[k]['tienda'] = struct.unpack_from(
                    '<H', bytes.fromhex(r['hex']), 0)[0]
                vistos.add(mapa)

    for v in npcs.values():
        d = v.get('dialogo')
        if d:
            v['texto'] = msg.get(d['mid'])
            v['textos_opciones'] = [msg.get(o) for o in d['opciones']]
        if 'tienda' in v:
            v['articulos'] = sh.get(v['tienda'], [])

    con_t = sum(1 for v in npcs.values() if 'tienda' in v)
    con_d = sum(1 for v in npcs.values() if 'dialogo' in v)
    print('%d NPC distintos: %d con dialogo, %d con tienda, en %d mapas'
          % (len(npcs), con_d, con_t, len(vistos)))
    por_mapa = {}
    for v in npcs.values():
        por_mapa.setdefault(v['mapa'], []).append(v['nombre'])
    for m, l in sorted(por_mapa.items(), key=lambda x: -len(x[1])):
        print('   %-26s %d' % (m, len(l)))
    (RAIZ / a.salida).write_text(json.dumps(npcs, ensure_ascii=False, indent=1),
                                 encoding='utf-8')
    print('guardado en %s' % a.salida)


if __name__ == '__main__':
    main()
