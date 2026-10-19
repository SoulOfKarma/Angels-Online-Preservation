"""Inspeccion reproducible de los datos originales de ligas, sin modificar el cliente."""
import json
import pathlib
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / 'server'), str(ROOT / 'tools')]
import house_services as hs
import mapa_del_cliente as mapas
import eventos_del_cliente as eventos


def main():
    out = {'stages': {}, 'maps': {}, 'messages': {}}
    for sid, row in hs.xml_rows('stage.xml').items():
        name = row.get('\u540d\u7a31', '')
        if sid == 501 or any(word in name.lower() for word in ('terra', 'territor', '[tw]')):
            out['stages'][sid] = row
    acc, cond = eventos.diccionario()
    for sid in (3, 26, 29, 38, 41, 200, 201, 202, 203, 204, 205, 501):
        if sid == 501:
            paths = list((ROOT / 'extracted_paks').glob('*/map/farm.mpc'))
            m = mapas.Mapa(sid, max(paths, key=lambda p: mapas._orden(p.parents[1])))
        else:
            m = mapas.mapa(sid)
        if not m:
            continue
        root = ET.fromstring(m.dialogos_xml) if m.dialogos_xml else []
        nodes = []
        chosen = {int(n.get('\u7de8\u865f', 0)) for n in root
                  if any(5920 <= int(v) <= 5985 for v in n.attrib.values() if v.isdigit())}
        chosen.update((1000403,))
        for _ in range(4):
            for n in root:
                if int(n.get('\u7de8\u865f', 0)) in chosen:
                    chosen.update(int(c.get('\u4e0b\u4e00\u53e5', 0)) for c in n.iter())
        for n in root:
            if not n.get('\u7de8\u865f') or int(n.get('\u7de8\u865f', 0)) not in chosen:
                continue
            nodes.append({'id': int(n.get('\u7de8\u865f')), 'text': n.get('\u8a0a\u606f'),
                          'next': n.get('\u4e0b\u4e00\u53e5'),
                          'branches': [dict(c.attrib) for c in n if c.tag != '\u89f8\u767c\u5668'],
                          'triggers': [{'conditions': [(cond.get(x[0], x[0]), x[1]) for x in
                                        [eventos._cod(c) for c in t.findall('\u689d\u4ef6')]],
                                        'actions': [(acc.get(x[0], x[0]), x[1]) for x in
                                        [eventos._cod(a) for a in t.findall('\u52d5\u4f5c')]]}
                                       for t in n.findall('\u89f8\u767c\u5668')]})
        relevant = []
        for tr in eventos.disparadores_del_mapa(m.ruta):
            if sid == 501 or any(5920 <= int(v) <= 5985 for n, pp in tr['acciones'] for v in pp):
                relevant.append(tr)
        out['maps'][sid] = {'path': str(m.ruta), 'size': [m.ancho, m.alto],
                           'tags': m.tags if sid == 501 else {}, 'nodes': nodes,
                           'events': relevant}
    for ident, row in hs.xml_rows('msg.xml').items():
        if 5920 <= ident <= 5985:
            out['messages'][ident] = row
    if '--farm' in sys.argv:
        print(json.dumps(out['maps'][501], ensure_ascii=True, indent=2))
    elif '--heaven' in sys.argv:
        print(json.dumps(out['maps'][3]['nodes'], ensure_ascii=True, indent=2))
    else:
        print(json.dumps(out, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
