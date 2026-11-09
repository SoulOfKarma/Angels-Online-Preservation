"""Diagnostico de solo lectura para recuperar los textos entre G y F."""
import collections
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import tw_migracion as tw
import pak_tool

OTHER = pathlib.Path(r'F:\Ao Proyect\AO 2')
CLIENT = pathlib.Path(r'C:\AO\Angels Online')


def extracted(root):
    return tw.indice(root / 'extracted_paks', [p.name for p in
        (root / 'extracted_paks').iterdir() if p.is_dir()], True)


def main():
    g, f = extracted(ROOT), extracted(OTHER)
    report = {'tables': {}, 'manual_missing': [], 'client': {}}
    for key in sorted(g.keys() & f.keys()):
        if not key.startswith('setting\\eng\\') or not key.endswith('.xml'):
            continue
        gr, fr = tw.filas(tw.leer(g[key][1])), tw.filas(tw.leer(f[key][1]))
        changes = []
        for ident in gr.keys() & fr.keys():
            ga, fa = tw.atributos(gr[ident]), tw.atributos(fr[ident])
            for field, value in ga.items():
                old = fa.get(field, '')
                if tw.es_texto(field) and value != old and not tw.RE_CJK.search(value):
                    changes.append({'id': ident, 'field': field, 'g': value,
                                    'f': old, 'cjk_f': bool(tw.RE_CJK.search(old))})
        if changes:
            report['tables'][key] = changes
            print(key, 'textos distintos', len(changes), 'CJK en F',
                  sum(c['cjk_f'] for c in changes))
    for p in (ROOT / 'work/traduccion/manual').glob('*.json'):
        q = OTHER / 'work/traduccion/manual' / p.name
        if not q.exists() or p.read_bytes() != q.read_bytes():
            report['manual_missing'].append(p.name)
    print('Manuales faltantes/distintos:', report['manual_missing'])
    for root, label in [(ROOT, 'g'), (OTHER, 'f')]:
        view = g if label == 'g' else f
        for name in ('item.xml', 'item1.xml', 'item2.xml', 'item3.xml', 'item4.xml',
                     'item5.xml', 'item6.xml', 'item7.xml', 'item8.xml', 'item9.xml'):
            entry = view.get('setting\\eng\\' + name)
            if entry:
                for ident, row in tw.filas(tw.leer(entry[1])).items():
                    a = tw.atributos(row)
                    if re.search(r'60[%％]', a.get('基本名稱', '') + a.get('說明定義', '')):
                        print(label, name, ident, json.dumps(a, ensure_ascii=False)[:650])
    for name in ('angel.dat', 'update26.pak', 'update26.pak.bak', 'update32.pak'):
        p = CLIENT / name
        if p.exists():
            data = p.read_bytes()
            info = {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            if name != 'angel.dat':
                entries, _ = pak_tool.leer_indice(data)
                selected = {}
                for e in entries:
                    key = tw.normal(e['nombre'])
                    if key in ('setting\\eng\\wnd01.xml', 'script\\main.l') or key.endswith('world1024x768_30.mpc'):
                        raw = pak_tool.leer_entrada(data, e)
                        selected[key] = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
                        if key.endswith('wnd01.xml'):
                            selected[key]['tabs'] = re.findall(r'<window[^>]*id="2551[3-6]"[^>]*>', raw.decode('utf-8-sig'))
                info['selected'] = selected
            report['client'][name] = info
            print(name, json.dumps(info, ensure_ascii=False))
    out = ROOT / 'work/tw_update32_nov2026/auditoria_g_f.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Informe:', out)


if __name__ == '__main__':
    main()
