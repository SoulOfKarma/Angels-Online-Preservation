"""Recetas de canje que Taiwan anadio a grupos que IGG ya tiene.

POR QUE. exchange.xml de IGG y el de TW comparten numeros de grupo, pero solo
en algunos el contenido es el mismo (Fashionable 439, Gear Clerk 181/182,
Astral Angel 393: cientos de recetas en comun). En esos, TW siguio metiendo
recetas nuevas (trajes, etc.) que aqui no estaban porque la fusion de tablas
solo anade filas con numero NUEVO y estas reusaban numeros de IGG. Se anaden
al final con numeros nuevos y el mismo grupo; el texto 獎賞說明 sale del
nombre ingles del premio.

`isolated_group_map` maneja grupos TW que colisionan con un catalogo IGG
distinto: copia las filas con IDs nuevos y un grupo alternativo. Para instalar
solo los datos del servidor, sin tocar los PAK del cliente, usar
`instalar_servidor`.

En los grupos sin recetas en comun (los viejos de Fortunia, 4..294) TW
cambio el contenido entero: eso no es "nuevo" y no se toca.

    python -I work/anadir_canjes_tw.py            # solo lista
    python -I work/anadir_canjes_tw.py instalar_servidor  # solo extraccion del servidor
    python -I work/anadir_canjes_tw.py instalar   # tambien actualiza los PAK del cliente
"""
import datetime, json, pathlib, re, shutil, sys
sys.path.insert(0, r'G:\Ao Proyect Improved\AO 2\tools')
sys.stdout.reconfigure(encoding='utf-8')
import tw_migracion as tw, pak_tool

R = r'setting\eng\exchange.xml'
tws, iggs = tw.indice_tw(True), tw.indice_igg(True)
ruta_igg = iggs[R][1]
txt = tw.leer(ruta_igg)
ex, extw = tw.filas(txt), tw.filas(tw.leer(tws[R][1]))
rm = json.loads((tw.RAIZ / 'server' / 'plantillas' / 'tw_exchanges.json').read_text(encoding='utf-8'))

items, nombres = {}, {}
for i in range(12):
    r = 'setting\\eng\\item%d.xml' % i if i else 'setting\\eng\\item.xml'
    if r in iggs:
        for k, f in tw.filas(tw.leer(iggs[r][1])).items():
            a = tw.atributos(f)
            items[k] = a
            nombres[k] = a.get('基本名稱') or a.get('名稱') or ''
    for base in (tw.SALIDA / 'setting_update26',
                 tw.RAIZ / 'extracted_paks' / 'update26'):
        path = base / 'setting' / 'eng' / pathlib.Path(r).name
        if not path.exists():
            continue
        for k, f in tw.filas(tw.leer(path)).items():
            a = tw.atributos(f)
            items[k] = a
            nombres[k] = a.get('基本名稱') or a.get('名稱') or ''


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
pendientes = []
grupos_aislados = {int(group) for group in rm.get('isolated_group_map', {}).values()}
for g, owner in sorted(rm['exchange_owners'].items(), key=lambda x: int(x[0])):
    t, i = gt.get(g, {}), gi.get(g, {})
    if not (set(t) & set(i)):
        continue
    for r, id_tw in sorted(t.items(), key=lambda x: int(x[1])):
        if r in i or not all(x in nombres for x, _ in r[0] + r[1]):
            continue
        pendientes.append((owner, g, id_tw, int(g)))

for source_group, target_group in sorted(
        rm.get('isolated_group_map', {}).items(), key=lambda x: int(x[0])):
    owner = rm['exchange_owners'].get(str(target_group))
    if not owner:
        raise ValueError('isolated Taiwan exchange group %s has no owner' % target_group)
    target_recipes = set(gi.get(str(target_group), {}))
    for recipe, id_tw in sorted(gt.get(source_group, {}).items(),
                                key=lambda x: int(x[1])):
        if recipe in target_recipes:
            continue
        missing = [item for item, _ in recipe[0] + recipe[1] if item not in nombres]
        if missing:
            raise ValueError('missing translated item names for Taiwan group %s: %s'
                             % (source_group, ', '.join(sorted(set(missing), key=int))))
        pendientes.append((owner, source_group, id_tw, int(target_group)))

sig = max(map(int, ex)) + 1
filas = []
for owner, g, id_tw, target_group in pendientes:
    fila = extw[id_tw]
    a = tw.atributos(fila)
    premio = nombres.get(a.get('獎賞1', ''), '')
    if target_group in grupos_aislados:
        item = a.get('獎賞1', '')
        detalle = items.get(item, {})
        prototipo = detalle.get('原型名稱', '').strip()
        if prototipo.isdigit() and prototipo != '2026':
            prototipo += ' pcs'
        if prototipo and not premio.lower().startswith(prototipo.lower()):
            premio = (prototipo + ' ' + premio).strip()
        premio = {
            '85008': '2026 Mall Anniversary Gold Coin',
            '85012': '2026 Mall Anniversary Gold Coin Lottery Ticket',
        }.get(item, premio)
    fila = re.sub(r'編號="\d+"', '編號="%d"' % sig, fila, count=1)
    fila = re.sub(r'群組="\d+"', '群組="%d"' % target_group, fila, count=1)
    fila = re.sub(r'獎賞說明="[^"]*"', '獎賞說明="%s"' % premio.replace('"', '&quot;'), fila, count=1)
    filas.append(fila)
    sig += 1

from collections import Counter
print('recetas nuevas por NPC:', dict(Counter(o for o, _, _, _ in pendientes)))
for (owner, g, id_tw, _), fila in [x for x in zip(pendientes, filas) if x[0][0] == 'Fashionable'][:14]:
    a = tw.atributos(fila)
    mats = [(nombres.get(a[k], a[k]), a.get(k + '數量')) for k in a if re.fullmatch(r'材料\d+', k)]
    print(' ', owner, g, a.get('獎賞說明'), 'x' + a.get('獎賞1數量', '1'), '<-', mats)

modo = sys.argv[1] if len(sys.argv) > 1 else ''
if modo in ('instalar', 'instalar_servidor') and filas:
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bk = tw.BACKUPS / ('canjes_tw_' + ts)
    bk.mkdir(parents=True)
    shutil.copy2(ruta_igg, bk / 'exchange.xml')
    if modo == 'instalar':
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
    if modo == 'instalar':
        for p in ('update26.pak', 'update26.pak.bak'):
            rep, add = pak_tool.actualizar(tw.CLIENTE / p, {'SETTING\\ENG\\EXCHANGE.XML': datos})
            print('%s: %d reemplazados, %d anadidos' % (p, rep, add))
        print('instalado en los paks del cliente; respaldo en', bk)
    else:
        print('instalado solo en la extraccion del servidor; respaldo en', bk)
