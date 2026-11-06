"""Quita de exchange.xml las filas de Taiwan metidas en grupos de IGG.

POR QUE. exchange.xml de IGG (original: 22.684 filas, work/backup/
20261026_160246) y el de Taiwan usan los mismos numeros de grupo para tiendas
DISTINTAS: el 607 es en IGG el PD del Noryo (2 filas) y en Taiwan la tienda
del aniversario del mall (199). La fusion de tablas anadio las filas de TW
con numero nuevo y cayeron dentro de los menus de los NPC de IGG: Fashionable
sacaba Safe Keys, monedas del aniversario y cajas de set de nivel 410 en
chino en el canje del Noryo. Tambien estaban mal las 410 de
anadir_canjes_tw.py: el "contenido comun" que mido alli eran estas mismas
filas de TW ya mezcladas.

REGLA: si el grupo existe en el exchange.xml original de IGG, se queda solo
con sus filas de IGG. Las filas de TW solo se quedan en grupos que IGG no
usa (los de la region nueva, 697-717...).

    python -I work/limpiar_canjes_tw.py            # solo cuenta
    python -I work/limpiar_canjes_tw.py instalar   # escribe (con respaldo)
"""
import collections
import datetime
import json
import shutil
import sys

sys.path.insert(0, r'G:\Ao Proyect Improved\AO 2\tools')
sys.stdout.reconfigure(encoding='utf-8')
import tw_migracion as tw
import pak_tool

R = tw.RAIZ
ORIGINAL = R / 'work' / 'backup' / '20261026_160246' / 'extracted_paks_update26' / 'setting' / 'eng' / 'exchange.xml'
ACTUAL = R / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'exchange.xml'

orig = {k: tw.atributos(v) for k, v in tw.filas(tw.leer(ORIGINAL)).items()}
grupos_igg = {a.get('群組') for a in orig.values()}
txt = tw.leer(ACTUAL)
filas = tw.filas(txt)
quitar = {}
for k, fila in filas.items():
    if k in orig:
        continue
    g = tw.atributos(fila).get('群組')
    if g in grupos_igg:
        quitar[k] = (g, fila)

rm = json.loads((R / 'server' / 'plantillas' / 'recent_mall.json').read_text(encoding='utf-8'))
dueno = rm['exchange_owners']
por_npc = collections.Counter(dueno.get(g, 'sin NPC del Lyceum') for g, _ in quitar.values())
print('filas actuales %d, de IGG %d, de TW en grupos de IGG (a quitar) %d, de TW que se quedan %d'
      % (len(filas), len(orig), len(quitar), len(filas) - len(orig) - len(quitar)))
print('a quitar por NPC:', dict(por_npc))

if len(sys.argv) > 1 and sys.argv[1] == 'instalar' and quitar:
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bk = tw.BACKUPS / ('limpiar_canjes_' + ts)
    bk.mkdir(parents=True)
    shutil.copy2(ACTUAL, bk / 'exchange.xml')
    for p in ('update26.pak', 'update26.pak.bak'):
        shutil.copy2(tw.CLIENTE / p, bk / p)
    nuevo = txt
    for k, (g, fila) in quitar.items():
        i = nuevo.index(fila)
        ini = nuevo.rfind('\n', 0, i) + 1          # la linea entera, con su tabulador
        fin = nuevo.index('\n', i) + 1
        nuevo = nuevo[:ini] + nuevo[fin:]
    datos = (b'\xef\xbb\xbf' if tw.leer_bom(ACTUAL) else b'') + nuevo.encode('utf-8')
    ACTUAL.write_bytes(datos)
    for p in ('update26.pak', 'update26.pak.bak'):
        rep, add = pak_tool.actualizar(tw.CLIENTE / p, {'SETTING\\ENG\\EXCHANGE.XML': datos})
        print('%s: %d reemplazados, %d anadidos' % (p, rep, add))
    print('instalado; respaldo en', bk)
