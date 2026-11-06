"""Recetas de canje que Taiwan anadio a grupos que IGG ya tiene.

POR QUE. exchange.xml de IGG y el de TW comparten numeros de grupo, pero solo
en algunos el contenido es el mismo (Fashionable 439, Gear Clerk 181/182,
Astral Angel 393: cientos de recetas en comun). En esos, TW siguio metiendo
recetas nuevas (trajes, etc.) que aqui no estaban porque la fusion de tablas
solo anade filas con numero NUEVO y estas reusaban numeros de IGG. Se anaden
al final con numeros nuevos y el mismo grupo; el texto 獎賞說明 sale del
nombre ingles del premio.

En los grupos sin recetas en comun (los viejos de Fortunia, 4..294) TW
cambio el contenido entero: eso no es "nuevo" y no se toca.

    python -I work/anadir_canjes_tw.py            # solo lista
    python -I work/anadir_canjes_tw.py instalar   # escribe (con respaldo)
"""
import datetime, json, re, shutil, sys
sys.path.insert(0, r'G:\Ao Proyect Improved\AO 2\tools')
sys.stdout.reconfigure(encoding='utf-8')
import tw_migracion as tw, pak_tool

R = 'setting\eng\exchange.xml'
tws, iggs = tw.indice_tw(True), tw.indice_igg(True)
ruta_igg = iggs[R][1]
txt = tw.leer(ruta_igg)
ex, extw = tw.filas(txt), tw.filas(tw.leer(tws[R][1]))
rm = json.load(open(tw.RAIZ / 'server' / 'plantillas' / 'recent_mall.json', encoding='utf-8'))

nombres = {}
for i in range(1, 12):
    r = 'setting\eng\item%d.xml' % i
    if r in iggs:
        for k, f in tw.filas(tw.leer(iggs[r][1])).items():
            nombres[k] = tw.atributos(f).get('基本名稱') or tw.atributos(f).get('名稱') or ''


def receta(a):
    pr = tuple(sorted((a[k], a.get(k + '數量', '1')) for k in a if re.fullmatch(r'獎賞\d+', k)))
    ma = tuple(sorted((a[k], a.get(k + '數量', '1')) for k in a if re.fullmatch(r'材料\d+', k)))
    return pr, ma


def por_grupo(t):
    d = {}
    for i, f in t.items():
        a = tw.atributos(f)
        d.setdefault(a.get('群組'), {})[receta(a)] = i
    return d


gi, gt = por_grupo(ex), por_grupo(extw)
nuevas = []
for g, owner in sorted(rm['exchange_owners'].items(), key=lambda x: int(x[0])):
    t, i = gt.get(g, {}), gi.get(g, {})
    if not (set(t) & set(i)):
        continue
    for r, id_tw in sorted(t.items(), key=lambda x: int(x[1])):
        if r in i or not all(x in nombres for x, _ in r[0] + r[1]):
            continue
        nuevas.append((owner, g, id_tw))

sig = max(map(int, ex)) + 1
filas = []
for owner, g, id_tw in nuevas:
    fila = extw[id_tw]
    a = tw.atributos(fila)
    premio = nombres.get(a.get('獎賞1', ''), '')
    fila = re.sub(r'編號="\d+"', '編號="%d"' % sig, fila, count=1)
    fila = re.sub(r'獎賞說明="[^"]*"', '獎賞說明="%s"' % premio.replace('"', '&quot;'), fila, count=1)
    filas.append(fila)
    sig += 1

from collections import Counter
print('recetas nuevas por NPC:', dict(Counter(o for o, _, _ in nuevas)))
for (owner, g, id_tw), fila in [x for x in zip(nuevas, filas) if x[0][0] == 'Fashionable'][:14]:
    a = tw.atributos(fila)
    mats = [(nombres.get(a[k], a[k]), a.get(k + '數量')) for k in a if re.fullmatch(r'材料\d+', k)]
    print(' ', owner, g, a.get('獎賞說明'), 'x' + a.get('獎賞1數量', '1'), '<-', mats)

if len(sys.argv) > 1 and sys.argv[1] == 'instalar' and filas:
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bk = tw.BACKUPS / ('canjes_tw_' + ts)
    bk.mkdir(parents=True)
    shutil.copy2(ruta_igg, bk / 'exchange.xml')
    for p in ('update26.pak', 'update26.pak.bak'):
        shutil.copy2(tw.CLIENTE / p, bk / p)
    salto = '\r\n' if '\r\n' in txt else '\n'
    pos = tw.punto_insercion(txt)
    # Las filas van con un tabulador delante, como las demas.
    if txt[pos - 1] == '\t':
        bloque = ''.join(f + salto + '\t' for f in filas)
    else:
        bloque = ''.join('\t' + f + salto for f in filas)
    nuevo = txt[:pos] + bloque + txt[pos:]
    datos = (b'\xef\xbb\xbf' if tw.leer_bom(ruta_igg) else b'') + nuevo.encode('utf-8')
    ruta_igg.write_bytes(datos)
    for p in ('update26.pak', 'update26.pak.bak'):
        rep, add = pak_tool.actualizar(tw.CLIENTE / p, {'SETTING\\ENG\\EXCHANGE.XML': datos})
        print('%s: %d reemplazados, %d anadidos' % (p, rep, add))
    print('instalado; respaldo en', bk)
