"""Resuelve el catalogo del Item Mall de Taiwan (work/item_mall_tw.json) a IDs.

El catalogo se transcribio de capturas del cliente oficial TW: solo trae el
nombre chino tal como lo pinta la tienda (原型名稱 + 基本名稱) y el precio.
Aqui se busca cada nombre en las tablas item*.xml de Taiwan (las originales,
en chino), primero exacto y luego por parecido, y se informa de lo dudoso.

    python -I tools/mall_tw.py           informe -> work/item_mall_tw_ids.json
"""
import difflib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tw_migracion as tw  # noqa: E402

RAIZ = tw.RAIZ
ENTRADA = RAIZ / 'work' / 'item_mall_tw.json'
SALIDA = RAIZ / 'work' / 'item_mall_tw_ids.json'


def _norm(s):
    s = s.replace('（', '(').replace('）', ')').replace(' ', '').replace('　', '')
    return s.replace('Ⅴ', 'V')


def indice_tw():
    """{nombre_normalizado: [ids]} de las tablas TW vigentes en chino."""
    vista = tw.indice_tw(True)
    idx = {}
    for n in [''] + [str(i) for i in range(2, 10)]:
        r = 'setting\\eng\\item%s.xml' % n
        if r not in vista:
            continue
        for i, fila in tw.filas(tw.leer(vista[r][1])).items():
            a = tw.atributos(fila)
            for nom in (a.get('原型名稱', '') + a.get('基本名稱', ''), a.get('基本名稱', '')):
                if nom:
                    idx.setdefault(_norm(nom), []).append(int(i))
    return idx


def resolver():
    cat = json.loads(ENTRADA.read_text(encoding='utf-8'))
    idx = indice_tw()
    claves = list(idx)
    out, dudas = [], 0
    for f in cat['filas']:
        k = _norm(f['nombre'])
        ids = idx.get(k)
        modo = 'exacto'
        if not ids:
            cand = difflib.get_close_matches(k, claves, n=3, cutoff=0.8)
            ids = idx[cand[0]] if cand else []
            modo = 'parecido: %s' % cand if cand else 'NO ENCONTRADO'
            dudas += 1
        out.append(dict(f, ids=sorted(set(ids)), modo=modo))
    SALIDA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    ok = sum(1 for o in out if o['modo'] == 'exacto')
    print('%d filas: %d exactas, %d dudosas -> %s' % (len(out), ok, dudas, SALIDA))
    for o in out:
        if o['modo'] != 'exacto' or len(o['ids']) != 1:
            print('  %-28s %s ids=%s' % (o['nombre'], o['modo'], o['ids'][:6]))


MALL = RAIZ / 'server' / 'plantillas' / 'item_mall.json'
# Medido con los 21 objetos que estan en los dos catalogos: el precio IGG es
# unas 13 veces el de Taiwan (mediana 12,95; las monturas 20->259, 15->129,
# 10->59). Se redondea a la terminacion en 9 que usa IGG.
FACTOR = 13
# Ids de producto propios en un hueco libre de IGG (34022..39000). TIENE que
# ser < 40001: el 0x005F del cliente (REA FUN_00620e80) guarda cada producto en
# una tabla indexada por id y descarta id >= 0x9C41 -- y como solo avanza el
# puntero en los aceptados, todo lo que viene detras se pierde. Con 50000 no
# salia ni un producto de Taiwan.
ID_BASE = 36000
ID_MAX = 40000
NOMBRES_VARIOS = {'愛情廣播器'}  # la tienda TW vende todas sus variantes


def _precio(tw_precio):
    p = int(tw_precio) * FACTOR
    return max(9, p - p % 10 + 9) if p >= 10 else 9


def _mismo_objeto(i, igg_set, tw_set):
    """El ID es el mismo objeto en el cliente instalado y en Taiwan (sin
    choque como el 83266): misma categoria y mismo icono."""
    for n in [''] + [str(k) for k in range(2, 10)]:
        r = 'setting\\eng\\item%s.xml' % n
        fi = tw.filas(tw.leer(igg_set[r][1])) if r in igg_set else {}
        ft = tw.filas(tw.leer(tw_set[r][1])) if r in tw_set else {}
        if str(i) in ft:
            if str(i) not in fi:
                return False
            a, b = tw.atributos(fi[str(i)]), tw.atributos(ft[str(i)])
            return (a.get('物品類別') == b.get('物品類別')
                    and a.get('原型介面') == b.get('原型介面'))
    return False


def construir():
    """Anade a item_mall.json los objetos del catalogo TW que no vende ya."""
    import shutil
    import time
    if not SALIDA.exists():
        resolver()
    filas = json.loads(SALIDA.read_text(encoding='utf-8'))
    mall = json.loads(MALL.read_text(encoding='utf-8'))
    ya = {r['item'] for r in mall['rows']}
    igg_set, tw_set = tw.indice_igg(True), tw.indice_tw(True)
    nid = max([ID_BASE] + [r['id'] + 1 for r in mall['rows']
                          if str(r.get('price_source', '')).startswith('Taiwan mall capture')])
    orden = {}
    nuevas, saltadas = [], []
    for f in filas:
        ids = [i for i in f['ids'] if i not in ya]
        if not f['ids']:
            saltadas.append((f['nombre'], 'sin ID'))
            continue
        if len(ids) < len(f['ids']):
            saltadas.append((f['nombre'], 'ya en el mall IGG'))
            continue
        if f['nombre'] not in NOMBRES_VARIOS:
            ids = [max(ids)]
        for i in ids:
            if not _mismo_objeto(i, igg_set, tw_set):
                saltadas.append((f['nombre'], 'ID %d choca con otro objeto' % i))
                continue
            for q, p in f['precios']:
                orden[f['cat']] = orden.get(f['cat'], 0) + 1
                nuevas.append({'id': nid, 'item': i, 'flags': 1, 'sort': 5000 + orden[f['cat']],
                               'category': f['cat'], 'quantity': q, 'price': _precio(p),
                               'special_price': 0, 'duration': 0, 'start': '', 'end': '',
                               'limit': 0, 'gift': 0, 'gift_quantity': 0,
                               'price_source': 'Taiwan mall capture %s x%d' % (p, FACTOR)})
                nid += 1
    if nuevas:
        bk = RAIZ / 'work' / 'backup' / ('item_mall_%s.json' % time.strftime('%Y%m%d_%H%M%S'))
        shutil.copy2(MALL, bk)
        mall['rows'].extend(nuevas)
        mall['taiwan_source'] = ('work/item_mall_tw.json: capturas del Item Mall de ALO Taiwan '
                                 '(26/10/2026), autorizado por el usuario; ver tools/mall_tw.py')
        MALL.write_text(json.dumps(mall, ensure_ascii=False, indent=1), encoding='utf-8')
        print('respaldo', bk)
    print('filas anadidas: %d (%d objetos)' % (len(nuevas), len({r["item"] for r in nuevas})))
    for n, motivo in saltadas:
        print('  saltado %-26s %s' % (n, motivo))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'resolver': resolver, 'construir': construir}[sys.argv[1] if len(sys.argv) > 1 else 'resolver']()
