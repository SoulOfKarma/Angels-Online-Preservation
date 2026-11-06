"""Registra en las plantillas del servidor los destinos nuevos de jumpmap.xml
(Superwing y punto de aparicion). Solo anade ids/stages que no estan."""
import json, pathlib, re, sys
R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'tools'))
import tw_migracion as tw

filas = tw.filas(tw.leer(R / 'extracted_paks/update26/setting/eng/jumpmap.xml'))
P = R / 'server/plantillas'
ag = json.loads((P / 'angels_go.json').read_text(encoding='utf-8'))
jm = json.loads((P / 'jumpmap.json').read_text(encoding='utf-8'))
ya_st = {d['stage'] for d in jm['destinos']}
n_ag = n_jm = 0
for i, f in sorted(filas.items(), key=lambda x: int(x[0])):
    a = tw.atributos(f)
    st, tile = int(a['場景編號']), [int(a['傳送座標X']), int(a['傳送座標Y'])]
    if i not in ag['destinos']:
        cats = [int(a[k]) for k in ('類別1', '類別2', '類別3') if a.get(k)]
        ag['destinos'][i] = {'stage': st, 'tile': tile, 'punto': a.get('傳點名稱'), 'categorias': cats}
        n_ag += 1
    if st not in ya_st and a.get('傳點名稱') in (None, 'Entrance'):
        jm['destinos'].append({'stage': st, 'nombre': a.get('場景名稱', ''),
                               'punto': a.get('傳點名稱') or '', 'tile': tile})
        ya_st.add(st)
        n_jm += 1
(P / 'angels_go.json').write_text(json.dumps(ag, ensure_ascii=False, indent=1), encoding='utf-8')
(P / 'jumpmap.json').write_text(json.dumps(jm, ensure_ascii=False, indent=2), encoding='utf-8')
print('angels_go +%d, jumpmap +%d' % (n_ag, n_jm))
