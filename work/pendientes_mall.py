"""Textos en chino/japones que se ven desde el Item Mall.

Recorre: productos de server/plantillas/item_mall.json -> objeto -> su
動態資料1 (fila de drop.xml con item1..N) -> objetos de dentro, varios niveles.
De cada objeto alcanzado mira 原型名稱 + 基本名稱 (el nombre que pinta el
cliente) y 說明定義 (el tooltip). Lo que el Traductor aun no sabe sale en
work/traduccion/lotes/mall_NNN.json para traducir a mano.

    python -I work/pendientes_mall.py
"""
import json
import re
import sys

sys.path.insert(0, r'G:\Ao Proyect Improved\AO 2\tools')
sys.stdout.reconfigure(encoding='utf-8')
import tw_migracion as tw
import traducir as tr

iggs = tw.indice_igg(True)
items = {}
for r, (pak, f) in iggs.items():
    nombre = r.lower().split('\\')[-1]
    if r.lower().startswith('setting\\eng\\') and re.fullmatch(r'item\d*\.xml', nombre):
        for k, fila in tw.filas(tw.leer(f)).items():
            items[k] = tw.atributos(fila)
drops = {}
for tabla in ('drop.xml', 'serv_drop.xml'):
    for k, v in tw.filas(tw.leer(iggs['setting\\eng\\' + tabla][1])).items():
        drops.setdefault(k, tw.atributos(v))
mall = json.loads((tw.RAIZ / 'server' / 'plantillas' / 'item_mall.json').read_text(encoding='utf-8'))

pend = [str(r['item']) for r in mall['rows']]
visto = set()
while pend:
    i = pend.pop()
    if i in visto or i not in items:
        continue
    visto.add(i)
    d = drops.get(items[i].get('動態資料1', '').strip())
    if d:
        pend += [v for k, v in d.items() if re.fullmatch(r'item\d+', k) and v and v != '0']

t = tr.Traductor()
segs = {}
for i in sorted(visto, key=int):
    a = items[i]
    for campo in ('原型名稱', '基本名稱', '說明定義'):
        for s in t.segmentos_pendientes(a.get(campo, '')):
            segs.setdefault(s, i)
nombres = [s for s in segs if len(s) < 40]
largos = [s for s in segs if len(s) >= 40]
print('objetos alcanzados desde el mall:', len(visto))
print('segmentos sin traducir: %d nombres cortos, %d descripciones (%d caracteres)'
      % (len(nombres), len(largos), sum(map(len, segs))))
for f in tr.LOTES.glob('mall_*.json'):
    f.unlink()
orden = nombres + largos
for n in range(0, len(orden), 200):
    (tr.LOTES / ('mall_%03d.json' % (n // 200))).write_text(
        json.dumps({s: '' for s in orden[n:n + 200]}, ensure_ascii=False, indent=0), encoding='utf-8')
print('lotes:', (len(orden) + 199) // 200)
