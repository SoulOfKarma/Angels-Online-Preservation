"""Migrar el contenido de ALO Taiwan (update27..32) al cliente IGG.

Medido (docs/MIGRACION_TAIWAN_UPDATE32.md, REA sobre angel.dat IGG):
  * el angel.dat IGG ya monta update27.pak .. update31.pak (WinMain, 0x5341f7),
    pero NO update32.pak: lo de 32 se funde en nuestro update31;
  * IGG lee las tablas de setting\\eng\\, Taiwan de setting\\BIG5\\; el
    formato es el mismo (XML UTF-8 con etiquetas en chino).

Politica: IGG manda. Una fila (o un archivo) que ya existe en el cliente IGG
se queda como esta -- es lo que el servidor ya conoce y lo que se tradujo.
De Taiwan solo se anade lo que IGG no tiene: filas con ID nuevo y archivos
con ruta nueva.

    python -I tools/tw_migracion.py analizar
"""
import collections
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import paks  # noqa: E402
from colores_texto import normalizar_colores  # noqa: E402

RAIZ = pathlib.Path(__file__).parent.parent
TW = RAIZ / 'extracted_paks_tw'
IGG = RAIZ / 'extracted_paks'
PAKS_TW = ['update27', 'update28', 'update29', 'update30', 'update31', 'update32']

RE_FILA = re.compile(r'<(\S+)\s+編號="(\d+)"[^>]*?/>', re.S)
RE_CJK = re.compile(r'[぀-ヿ㐀-鿿豈-﫿ｦ-ﾟ]')
RE_ATTR = re.compile(r'\s([^\s=<>"]+)="([^"]*)"')
MEMORIA = RAIZ / 'work' / 'traduccion' / 'memoria.json'

# Campos de texto libre que ve el jugador. El resto de valores en chino
# (是/否, 物品類別, 顏色, 系別, HP定義...) son enums que el exe compara tal
# cual: IGG tambien los deja en chino y NO se traducen.
CAMPOS_TEXTO = {
    '基本名稱', '原型名稱', '說明定義', '文字', '名稱', '說明', '獎賞說明',
    '怪物名稱', 'Npc名稱', '任務名稱', '任務前言', '任務類型', '地點',
    '承接', '承接人員', '封號', '場景名稱', '傳點名稱', '卡片說明',
    '卡片提示', '卡片名稱', '套卡說明', '套卡名稱', '類別名稱',
}
RE_CAMPO_NUM = re.compile(r'^(步驟|地點|承接|答案|題目)\d*$')


def es_texto(campo: str) -> bool:
    return campo in CAMPOS_TEXTO or bool(RE_CAMPO_NUM.match(campo))


def atributos(fila: str) -> dict:
    return dict(RE_ATTR.findall(fila))


def normal(rel: str) -> str:
    """Ruta interna comparable entre ramas: minusculas, BIG5 -> eng."""
    r = rel.replace('/', '\\').lower()
    if r.startswith('setting\\big5\\'):
        r = 'setting\\eng\\' + r[len('setting\\big5\\'):]
    return r


def indice(raiz: pathlib.Path, nombres, solo_setting: bool = False) -> dict:
    """{ruta normal: (pak, archivo)} con 'el pak mas alto gana'."""
    vista = {}
    for n in sorted(nombres, key=lambda x: paks.numero(raiz / x)):
        base = raiz / n
        dirs = [d for d in base.iterdir() if d.is_dir()
                and (not solo_setting or d.name.lower() == 'setting')]
        for d in dirs:
            for f in d.rglob('*'):
                if f.is_file():
                    vista[normal(str(f.relative_to(base)))] = (n, f)
    return vista


def indice_igg(solo_setting: bool = False) -> dict:
    # extracted_paks/update27.. no son de IGG (que acaba en update26): ahi
    # se dejan los .mpc de Taiwan para que los lean las herramientas del
    # servidor. Contarlos como IGG los sacaba de los paks al reconstruir.
    return indice(IGG, [d.name for d in IGG.iterdir() if d.is_dir()
                        and paks.numero(IGG / d.name) <= 26], solo_setting)


def indice_tw(solo_setting: bool = False) -> dict:
    return indice(TW, PAKS_TW, solo_setting)


def filas(texto: str) -> dict:
    return {m.group(2): m.group(0) for m in RE_FILA.finditer(texto)}


def leer(f: pathlib.Path) -> str:
    return f.read_bytes().decode('utf-8-sig', errors='replace')


def analizar():
    igg, tw = indice_igg(), indice_tw()
    por_tipo = collections.Counter()
    nuevos = [r for r in tw if r not in igg]
    for r in nuevos:
        por_tipo[r.split('\\')[0] + ' ' + pathlib.Path(r).suffix] += 1
    print('archivos TW 27-32 (vigentes): %d, nuevos para IGG: %d' % (len(tw), len(nuevos)))
    for k, v in por_tipo.most_common():
        print('   %-22s %d' % (k, v))
    print()
    print('%-26s %8s %8s %8s %8s' % ('tabla', 'IGG', 'TW', 'nuevos', 'nuevosCJK'))
    informe = {}
    for r in sorted(x for x in tw if x.startswith('setting\\eng\\') and x.endswith('.xml')):
        ft = filas(leer(tw[r][1]))
        fi = filas(leer(igg[r][1])) if r in igg else {}
        nuevos_id = [i for i in ft if i not in fi]
        cjk = sum(1 for i in nuevos_id if RE_CJK.search(ft[i]))
        informe[r] = dict(igg=len(fi), tw=len(ft), nuevos=len(nuevos_id),
                          pak_tw=tw[r][0], pak_igg=igg[r][0] if r in igg else None)
        print('%-26s %8d %8d %8d %8d' % (r[12:], len(fi), len(ft), len(nuevos_id), cjk))
    (TW / '_manifests' / 'analisis.json').write_text(
        json.dumps(dict(nuevos=nuevos, tablas=informe), ensure_ascii=False, indent=1),
        encoding='utf-8')


def tablas_vigentes():
    """[(ruta, filas_igg, filas_tw)] de las tablas con ID de setting\\eng."""
    igg, tw = indice_igg(True), indice_tw(True)
    out = []
    for r in sorted(set(igg) | set(tw)):
        if r.startswith('setting\\eng\\') and r.endswith('.xml'):
            fi = filas(leer(igg[r][1])) if r in igg else {}
            ft = filas(leer(tw[r][1])) if r in tw else {}
            if fi or ft:
                out.append((r, fi, ft))
    return out


def pendientes(tablas):
    """{texto_cjk: n} de los campos de texto que veria el jugador tras fusionar."""
    cnt = collections.Counter()
    for r, fi, ft in tablas:
        for i, fila in list(fi.items()) + [(k, v) for k, v in ft.items() if k not in fi]:
            for a, v in atributos(fila).items():
                if es_texto(a) and RE_CJK.search(v):
                    cnt[v] += 1
    return cnt


# IDs que este servidor uso para objetos PROPIOS y que en Taiwan son otra
# cosa: el 83266 es la Rank Promotion Medal aqui y un huevo de mascota en TW.
# Sus pares por ID no son traducciones: '機兵蛋' salia "Rank Promotion Medal".
IDS_PROPIOS = {'83266'}


def numeros_casan(zh: str, en: str) -> bool:
    """IGG reutilizo IDs: '2011商城紀念金幣' quedo como '2012 Olympics Coin'.
    Si los dos lados traen numeros y no son los mismos, el par no vale."""
    nz = set(re.findall(r'\d+', zh))
    ne = set(re.findall(r'\d+', en.replace(',', '')))
    return not (nz and ne) or nz == ne


def memoria():
    """Pares zh->en por ID y campo: TW (chino) contra IGG (ya en ingles)."""
    igg, tw_ = indice_igg(True), indice_tw(True)
    u26_puro = RAIZ / 'work' / 'backup' / '20261026_160246' / 'extracted_paks_update26'
    if (u26_puro / 'setting').is_dir():
        igg = indice(IGG, [d.name for d in IGG.iterdir() if d.is_dir()
                           and paks.numero(IGG / d.name) < 26], True)
        for f in (u26_puro / 'setting').rglob('*'):
            if f.is_file():
                igg[normal(str(f.relative_to(u26_puro)))] = ('update26', f)
    tablas = []
    for r in sorted(set(igg) | set(tw_)):
        if r.startswith('setting\\eng\\') and r.endswith('.xml'):
            fi = filas(leer(igg[r][1])) if r in igg else {}
            ft = filas(leer(tw_[r][1])) if r in tw_ else {}
            if fi or ft:
                tablas.append((r, fi, ft))
    votos = collections.defaultdict(collections.Counter)
    for r, fi, ft in tablas:
        for i, fila_t in ft.items():
            if i not in fi or i in IDS_PROPIOS:
                continue
            ai, at = atributos(fi[i]), atributos(fila_t)
            if r.endswith('\\exchange.xml') and ai.get('獎賞1') != at.get('獎賞1'):
                continue
            for a, zh in at.items():
                en = ai.get(a)
                if (es_texto(a) and en and RE_CJK.search(zh)
                        and not RE_CJK.search(en) and numeros_casan(zh, en)):
                    votos[zh][en] += 1
    tm = {zh: c.most_common(1)[0][0] for zh, c in votos.items()}
    MEMORIA.parent.mkdir(parents=True, exist_ok=True)
    MEMORIA.write_text(json.dumps(tm, ensure_ascii=False, indent=0), encoding='utf-8')
    pend = pendientes(tablas_vigentes())
    cubiertas = [v for v in pend if v in tm]
    print('pares zh->en: %d' % len(tm))
    print('textos CJK a traducir: %d unicos (%d chars); cubiertos por memoria: %d'
          % (len(pend), sum(map(len, pend)), len(cubiertas)))
    resto = [v for v in pend if v not in tm]
    print('resto: %d unicos, %d chars (nombres <=20 chars: %d)'
          % (len(resto), sum(map(len, resto)), sum(1 for v in resto if len(v) <= 20)))


SALIDA = RAIZ / 'work' / 'salida'
# El pak IGG en el que cae cada pak TW. El angel.dat IGG original solo monta
# hasta update31; tools/parchear_angel_update32.py le anade update32.pak.
DESTINO_PAK = {'update27': 'update27', 'update28': 'update28', 'update29': 'update29',
               'update30': 'update30', 'update31': 'update31', 'update32': 'update32'}
RE_VALOR = re.compile(r'(\s)([^\s=<>"]+)="([^"]*)"')
# Assets que IGG ya tiene pero que Taiwan cambio y hacen falta: map169.mpc
# (Karang Desert) de TW 32 trae el tornado (7,172) que lleva a Sand Castle
# Tales; el de IGG (UPDATE14) no lo tiene.
REEMPLAZOS_TW = {'map\\map169.mpc', 'script\\magic.so'}


def traducir_xml(texto: str, trad) -> str:
    def _attr(m):
        sp, a, v = m.groups()
        if es_texto(a):
            if RE_CJK.search(v):
                v = trad.traducir(v)[0]
            v = normalizar_colores(v)
        return '%s%s="%s"' % (sp, a, v)
    return RE_VALOR.sub(_attr, texto)


def fusionar_tabla(texto_igg: str, filas_tw: dict) -> str:
    """Anade al final (antes de </root>) las filas TW con ID que IGG no tiene."""
    ya = filas(texto_igg)
    nuevas = [v for k, v in sorted(filas_tw.items(), key=lambda x: int(x[0])) if k not in ya]
    if not nuevas:
        return texto_igg
    bloque = ''.join('    %s\r\n' % v.strip() for v in nuevas)
    return texto_igg[:punto_insercion(texto_igg)] + bloque + texto_igg[punto_insercion(texto_igg):]


def punto_insercion(texto: str) -> int:
    """Donde van las filas nuevas: ANTES del <ALIAS .../> si lo hay.

    Las tablas IGG acaban en <ALIAS id="編號" classname="類別名稱" .../>, que
    le dice al exe como se llaman los atributos. Lo que va detras del ALIAS
    el cliente no lo carga: con las filas de TW ahi, la categoria 40 no salia
    en el Superwing y stage.xml no tenia el 423 -> crash al entrar (terreno
    nulo en sub_56F160, 0x56F1B3)."""
    m = RE_META.search(texto)
    pos = m.start() if m else texto.rfind('</root>')
    if pos < 0:
        raise ValueError('tabla sin </root>')
    return texto.rfind('\n', 0, pos) + 1


# Los bloques de metadatos del final de las tablas IGG: puede haber varios
# <ALIAS> y <DEFINE> seguidos (actboard trae 2, battlepass 6, chardef 7).
RE_META = re.compile(r'<(ALIAS|DEFINE)\b')


# Archivos de setting\ (fuera de eng\) en los que solo se anaden elementos
# con clave nueva. El resto de los que IGG ya tiene se queda como IGG.
RAIZ_XML_ADD = {'itemicon2.xml', 'itemicon3.xml', 'itemicon4.xml', 'skillicon.xml',
                'peticon.xml', 'faceicon.xml', 'shop.xml', 'level.xml',
                'pet_inlay.xml', 'chardef.xml'}
RAIZ_OBD_ADD = {'char3.obd', 'char4.obd', 'npc.obd', 'common.obd', 'mapobj.obd',
                'server.obd', 'm02.obd'}
CLAVES = ('id', '編號', '等級', '號碼', 'Sequence')


def _clave(el):
    for k in CLAVES:
        if k in el.attrib:
            return el.tag, k, el.attrib[k]
    return None


def fusionar_xml_add(texto_igg: str, texto_tw: str) -> str:
    """Anade los hijos (nivel 1 y 2) de TW cuya clave no esta en IGG.
    Los de nivel 2 se meten antes del cierre de su seccion en IGG."""
    import xml.etree.ElementTree as ET
    ri, rt = ET.fromstring(texto_igg), ET.fromstring(texto_tw)
    ya = set()
    for padre in [ri] + list(ri):
        for el in padre:
            c = _clave(el)
            if c:
                ya.add((padre.tag if padre is not ri else '', c))
    por_padre = collections.defaultdict(list)
    for padre in [rt] + list(rt):
        ptag = padre.tag if padre is not rt else ''
        for el in padre:
            c = _clave(el)
            if c and (ptag, c) not in ya:
                el.tail = None
                por_padre[ptag].append(ET.tostring(el, encoding='unicode').strip())
                ya.add((ptag, c))
    out = texto_igg
    for ptag, els in por_padre.items():
        cierre = '</%s>' % (ptag or 'root')
        pos = out.find(cierre) if ptag else punto_insercion(out)
        if pos < 0:
            continue                        # seccion que IGG no tiene: no se inventa
        out = out[:pos] + ''.join('\t%s\r\n' % e for e in els) + out[pos:]
    return out


RE_OBJ = re.compile(rb'\[OBJECT\][^\[]*?(?=\r?\n\[|\Z)', re.S)
RE_SEQ = re.compile(rb'^\s*Sequence\s*=\s*(\d+)', re.M)


def fusionar_obd_add(igg: bytes, tw_: bytes) -> bytes:
    """Anade al final los bloques [OBJECT] cuya Sequence no tiene IGG."""
    ya = {m.group(1) for b in RE_OBJ.finditer(igg) for m in [RE_SEQ.search(b.group(0))] if m}
    nuevos = []
    for b in RE_OBJ.finditer(tw_):
        m = RE_SEQ.search(b.group(0))
        if m and m.group(1) not in ya:
            nuevos.append(b.group(0).rstrip(b'\r\n'))
            ya.add(m.group(1))
    if not nuevos:
        return igg
    return igg.rstrip(b'\r\n') + b'\r\n\r\n' + b'\r\n\r\n\r\n'.join(nuevos) + b'\r\n'


def construir(con_paks: bool = True):
    """work/salida/setting (tablas fusionadas y traducidas) y work/salida/paks."""
    import shutil
    import traducir
    trad = traducir.Traductor()
    igg_set, tw_set = indice_igg(True), indice_tw(True)
    dst = SALIDA / 'setting_update26'
    if dst.exists():
        shutil.rmtree(dst)
    escritos = 0
    for r, (pak, f) in sorted(tw_set.items()):
        nombre = r.split('\\')[-1]
        if r in igg_set and r.count('\\') == 1 and (nombre in RAIZ_XML_ADD or nombre in RAIZ_OBD_ADD):
            if nombre in RAIZ_OBD_ADD:
                viejo = igg_set[r][1].read_bytes()
                nuevo = fusionar_obd_add(viejo, f.read_bytes())
            else:
                viejo = igg_set[r][1].read_bytes()
                nuevo_txt = fusionar_xml_add(leer(igg_set[r][1]), leer(f))
                nuevo = b'\xef\xbb\xbf' * leer_bom(igg_set[r][1]) + nuevo_txt.encode('utf-8')
            if nuevo != viejo:
                destino = dst.joinpath(*r.split('\\'))
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(nuevo)
                escritos += 1
            continue
        if not r.endswith('.xml'):
            if r not in igg_set and r.count('\\') == 1 and not r.endswith('.tic'):
                destino = dst.joinpath(*r.split('\\'))      # .obd/.ini nuevos de TW
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(f.read_bytes())
                escritos += 1
            continue
        if r in igg_set:
            if not r.startswith('setting\\eng\\'):
                continue                    # battlepass.xml y cia: los parchea el servidor
            texto_igg = leer(igg_set[r][1])
            ft = filas(leer(f))
            if not ft:
                continue                    # sin IDs (wnd, sp...): manda IGG
            texto = fusionar_tabla(texto_igg, ft)
        else:
            texto = leer(f)                 # archivo nuevo de Taiwan
        texto = traducir_xml(texto, trad)
        if r in igg_set and texto == leer(igg_set[r][1]):
            continue
        destino = dst.joinpath(*r.split('\\'))
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b'\xef\xbb\xbf' * leer_bom(f) + texto.encode('utf-8'))
        escritos += 1
    # Las tablas IGG que Taiwan no toca tambien se traducen (el chino viejo).
    for r, (pak, f) in sorted(igg_set.items()):
        if r in tw_set or not r.endswith('.xml') or not r.startswith('setting\\eng\\'):
            continue
        texto = leer(f)
        nuevo = traducir_xml(texto, trad)
        if nuevo != texto:
            destino = dst.joinpath(*r.split('\\'))
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(b'\xef\xbb\xbf' * leer_bom(f) + nuevo.encode('utf-8'))
            escritos += 1
    print('tablas escritas en %s: %d' % (dst, escritos))
    if not con_paks:
        return

    # Assets nuevos (ruta que IGG no tiene) -> update27..31.pak
    igg_todo, tw_todo = indice_igg(), indice_tw()
    por_pak = collections.defaultdict(list)
    for r, (pak, f) in tw_todo.items():
        if (r in igg_todo and r not in REEMPLAZOS_TW) or r.startswith('setting\\'):
            continue
        por_pak[DESTINO_PAK[pak]].append((str(f.relative_to(TW / pak)), f))
    main_l = RAIZ / 'extracted_paks' / 'update32_main_l_pestana_sand_castle.l'
    if not main_l.is_file():
        raise FileNotFoundError('falta el MAIN.L de Sand Castle Tales: %s' % main_l)
    por_pak['update32'] = [
        (rel, f) for rel, f in por_pak['update32']
        if rel.replace('/', '\\').lower() != 'script\\main.l'
    ]
    por_pak['update32'].append(('SCRIPT\\MAIN.L', main_l))
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import pak_tool
    (SALIDA / 'paks').mkdir(parents=True, exist_ok=True)
    for nombre, lista in sorted(por_pak.items()):
        salida = SALIDA / 'paks' / (nombre + '.pak')
        n = pak_tool.construir([(rel, f.read_bytes()) for rel, f in sorted(lista)], salida)
        print('%s: %d archivos, %.1f MB' % (salida.name, n, salida.stat().st_size / 1e6))


def leer_bom(f: pathlib.Path) -> bool:
    with open(f, 'rb') as h:
        return h.read(3) == b'\xef\xbb\xbf'


CLIENTE = pathlib.Path(r'C:\AO\Angels Online')
BACKUPS = RAIZ / 'work' / 'backup'


def instalar(con_paks: bool = True, cliente: bool = True):
    """Lleva work/salida al cliente y a extracted_paks/update26, con respaldo.

    Las tablas van DENTRO de update26.pak (y de su .bak, del que el servidor
    saca stage.xml/battlepass/activityurl): asi los parches que aplica
    cliente_local.aplicar_modo_estacion al arrancar siguen mandando.
    Los assets nuevos van en update27..32.pak; update32 requiere el
    angel.dat IGG parcheado. El MAIN.L guardado de Sand Castle Tales se
    vuelve a incluir al reconstruir ese pak. Con cliente=False solo se
    instala la vista extraida que usa el servidor; no se escribe en C:\\AO."""
    import datetime
    import shutil
    import pak_tool
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    bk = BACKUPS / ts
    if cliente:
        (bk / 'cliente').mkdir(parents=True)
    (bk / 'extracted_paks_update26').mkdir(parents=True)
    tablas = SALIDA / 'setting_update26'
    archivos = [f for f in tablas.rglob('*') if f.is_file()]
    nuevos_paks = sorted((SALIDA / 'paks').glob('*.pak')) if con_paks else []
    registro = dict(ts=ts, cliente=str(CLIENTE), tablas=[], extraidos_nuevos=[],
                    paks_nuevos=[p.name for p in nuevos_paks])

    # 1. respaldos
    if cliente:
        for n in ['update26.pak', 'update26.pak.bak'] + [p.name for p in nuevos_paks]:
            if (CLIENTE / n).exists():
                shutil.copy2(CLIENTE / n, bk / 'cliente' / n)
    dst_ext = IGG / 'update26'
    for f in archivos:
        rel = f.relative_to(tablas)
        actual = dst_ext / rel
        if actual.exists():
            (bk / 'extracted_paks_update26' / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(actual, bk / 'extracted_paks_update26' / rel)
        else:
            registro['extraidos_nuevos'].append(str(rel))
    print('respaldo en', bk)

    # 2. extracted_paks/update26 (lo que lee el servidor)
    for f in archivos:
        rel = f.relative_to(tablas)
        (dst_ext / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst_ext / rel)
        registro['tablas'].append(str(rel))

    # 3. update26.pak y su .bak
    mapa = {str(f.relative_to(tablas)).replace('/', '\\').upper(): f.read_bytes() for f in archivos}
    if cliente:
        for n in ('update26.pak', 'update26.pak.bak'):
            if (CLIENTE / n).exists():
                rep, add = pak_tool.actualizar(CLIENTE / n, mapa)
                print('%s: %d reemplazados, %d anadidos' % (n, rep, add))

    # 4. paks de assets
    if cliente:
        for p in nuevos_paks:
            shutil.copy2(p, CLIENTE / p.name)
            print('copiado', p.name)
    (bk / 'instalacion.json').write_text(json.dumps(registro, indent=1), encoding='utf-8')
    print('listo. Para deshacer: python -I tools/tw_migracion.py desinstalar', ts)


def contenido():
    """corpus/content.db: anade las filas nuevas y las traducciones.

    Se genera una base temporal con tools/extract_content.py (lee
    extracted_paks, ya fusionado) y de ella se copian a la de produccion
    solo (a) filas con id que no estaba y (b) textos que estaban en chino y
    ahora tienen traduccion. Nada mas cambia."""
    import datetime
    import shutil
    import sqlite3
    import extract_content
    prod = RAIZ / 'corpus' / 'content.db'
    tmp = RAIZ / 'work' / 'content_tw_tmp.db'
    if tmp.exists():
        tmp.unlink()
    extract_content.main(str(IGG), str(tmp))
    bk = BACKUPS / ('content_%s.db' % datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    BACKUPS.mkdir(parents=True, exist_ok=True)
    shutil.copy2(prod, bk)
    textos = {extract_content.TRAD.get(a, a) for a in CAMPOS_TEXTO} | {'name', 'desc'}
    src, dst = sqlite3.connect(tmp), sqlite3.connect(prod)
    for (tabla,) in src.execute("select name from sqlite_master where type='table'"):
        cols_src = [r[1] for r in src.execute('pragma table_info("%s")' % tabla)]
        cols_dst = [r[1] for r in dst.execute('pragma table_info("%s")' % tabla)]
        if not cols_dst or 'id' not in cols_src and 'level' not in cols_src:
            continue
        clave = 'id' if 'id' in cols_src else 'level'
        for c in cols_src:
            if c.lower() not in {x.lower() for x in cols_dst}:
                dst.execute('ALTER TABLE "%s" ADD COLUMN "%s" TEXT' % (tabla, c))
                cols_dst.append(c)
        ctxt = [c for c in cols_src if c in textos and c in cols_dst]
        sel = ','.join(['rowid', '"%s"' % clave] + ['"%s"' % c for c in ctxt])
        actual = {}
        for r in dst.execute('select %s from "%s"' % (sel, tabla)):
            actual[r[1]] = (r[0], dict(zip(ctxt, r[2:])))
        nuevas = trad = 0
        q = ','.join('"%s"' % c for c in cols_src)
        for fila in src.execute('select %s from "%s"' % (q, tabla)).fetchall():
            d = dict(zip(cols_src, fila))
            if d[clave] not in actual:
                dst.execute('INSERT INTO "%s" (%s) VALUES (%s)' % (tabla, q, ','.join('?' * len(cols_src))), fila)
                nuevas += 1
                continue
            rowid, viejos = actual[d[clave]]
            for c in ctxt:
                v, antes = d[c], viejos.get(c)
                if v and antes and RE_CJK.search(antes) and not RE_CJK.search(v):
                    dst.execute('UPDATE "%s" SET "%s"=? WHERE rowid=?' % (tabla, c), (v, rowid))
                    trad += 1
        dst.commit()
        if nuevas or trad:
            print('  %-14s +%d filas nuevas, %d textos traducidos' % (tabla, nuevas, trad))
    src.close()
    dst.close()
    tmp.unlink()
    print('content.db actualizado; respaldo en', bk)


def reparar_alias():
    """Las filas que quedaron DETRAS del <ALIAS> (instalaciones del 26/10
    antes de punto_insercion) se mueven delante, en extracted_paks/update26
    y en update26.pak y su .bak."""
    import pak_tool
    base = IGG / 'update26'
    cambios = {}
    for f in (base / 'setting').rglob('*.xml'):
        raw = f.read_bytes()
        bom = raw.startswith(b'\xef\xbb\xbf')
        txt = raw.decode('utf-8-sig', errors='replace')
        metas = list(RE_META.finditer(txt))
        if not metas:
            continue
        fin_ultima = txt.find('>', metas[-1].start()) + 1
        cierre = txt.rfind('</root>')
        cola = txt[fin_ultima:cierre]
        if not cola.strip():
            continue                        # nada detras de los metadatos
        ini = txt.rfind('\n', 0, metas[0].start()) + 1
        nuevo = (txt[:ini] + cola.strip('\r\n') + '\r\n'
                 + txt[ini:fin_ultima] + '\r\n' + txt[cierre:])
        f.write_bytes(b'\xef\xbb\xbf' * bom + nuevo.encode('utf-8'))
        cambios[str(f.relative_to(base)).replace('/', '\\').upper()] = f.read_bytes()
    print('tablas reparadas: %d' % len(cambios))
    for n in ('update26.pak', 'update26.pak.bak'):
        if cambios and (CLIENTE / n).exists():
            print(n, pak_tool.actualizar(CLIENTE / n, cambios))
    return sorted(cambios)


def ajustes_wnd():
    """Los dos cambios de interfaz que Taiwan hizo para la region 30.

    * wnd05.xml, ventana Angels GO!: la lista de "Map Types" (id 28383)
      tenia rows="39"; con la categoria 40 (Sand Castle Tales) TW la sube a
      rows="40" y alto 460. Con 39 la categoria 40 no salia en la lista.
    * wnd01.xml, mapa del mundo: TW anade la pestana 25516 "砂城秘譚". Los
      cuatro mapas nuevos usan appdata=5 en el archivo TW; las pestañas en
      inglés se separan y Switch Maps se desplaza para dejarles sitio.
    Las versiones vigentes (update26 y update25) se copian a update26 y se
    meten en update26.pak y su .bak."""
    import paks
    import pak_tool
    cambios = {}
    w5 = pathlib.Path(paks.vigente('wnd05.xml'))
    t = w5.read_bytes().decode('utf-8-sig')
    t2 = re.sub(r'(<window class="WND_CLASS_LIST" id="28383" range="63,91,164,)380(" '
                r'workrange="4,0,156,)380(" cols="1" rows=")39"',
                r'\g<1>460\g<2>460\g<3>40"', t)
    if t2 != t:
        cambios['setting\\eng\\wnd05.xml'] = t2
    w1 = pathlib.Path(paks.vigente('wnd01.xml'))
    t = w1.read_bytes().decode('utf-8-sig')
    if 'id="25516"' not in t:
        inicio = t.find('id="25515"')
        fin = t.find('</window>', inicio)
        if inicio < 0 or fin < 0:
            raise SystemExit('wnd01.xml: no se encontro la pestana Night City Code')
        boton_night = t[inicio:fin]
        t = t[:inicio] + boton_night.replace(' bsRadioEnd=""', '') + t[fin:]
        boton = ('\t<window class="WND_CLASS_BUTTON" id="25516" range="494,561,105,17" fcolor="101" '
                 'font="1" icon="27108" check="27112" title="Sand Castle Tales" appdata="5">\r\n'
                 '\t\t<style wsVisible="" bsVCenter="" bsHCenter="" bsRadio=""  wsTab="" bsRadioEnd=""/>\r\n'
                 '\t\t<OnCommand>OnStageMapPage</OnCommand>\r\n\t</window>\r\n\r\n')
        ancla = t.find('<!--切換地圖-->')
        if ancla < 0 or 'bsRadioEnd=""/>' in t[t.find('id="25515"'):ancla] :
            raise SystemExit('wnd01.xml: no se encontro el sitio esperado para la pestana 25516')
        ini = t.rfind('\n', 0, ancla) + 1
        t = t[:ini] + boton + t[ini:]
        cambios['setting\\eng\\wnd01.xml'] = t
    posiciones = {'25513': '134', '25514': '254', '25515': '374', '25516': '494'}
    t2 = t
    for bid, x in posiciones.items():
        t2 = re.sub(r'(id="%s" range=")\d+,561,\d+,17(")' % bid,
                    r'\g<1>%s,561,105,17\g<2>' % x, t2)
        t2 = re.sub(r'(<window class="WND_CLASS_BUTTON" id="%s"[^>]*\bappdata=")\d+(")' % bid,
                    r'\g<1>5\2', t2)
    switch, n = re.subn(r'(id="24750" range=")\d+,561,70,18(")',
                        r'\g<1>617,561,70,18\2', t2, count=1)
    if n != 1:
        raise SystemExit('wnd01.xml: no se encontro el boton Switch Maps esperado')
    t2 = switch
    if t2 != t:
        t = t2
        cambios['setting\\eng\\wnd01.xml'] = t
    # Sin <child>25516</child> en la ventana del mapa el boton no se crea
    # (TW lo pone detras del 25515). Faltaba: la pestana no salia.
    if '<child>25516</child>' not in t:
        t2 = re.sub(r'(<child>25515</child>[ \t]*\r?\n)', r'\g<1>\t\t<child>25516</child>\r\n', t, count=1)
        if t2 == t:
            raise SystemExit('wnd01.xml: no se encontro <child>25515</child>')
        cambios['setting\\eng\\wnd01.xml'] = t2
    for rel, txt in cambios.items():
        f = IGG / 'update26' / pathlib.PureWindowsPath(rel)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b'\xef\xbb\xbf' + txt.encode('utf-8'))
    mapa = {k.upper(): (IGG / 'update26' / pathlib.PureWindowsPath(k)).read_bytes() for k in cambios}
    for n in ('update26.pak', 'update26.pak.bak'):
        if mapa and (CLIENTE / n).exists():
            print(n, pak_tool.actualizar(CLIENTE / n, mapa))
    print('ajustes de interfaz:', sorted(cambios) or 'ya estaban')


def msg_propios():
    """Anade a msg.xml las lineas de work/msg_propios.json que falten.

    Son textos del servidor sin equivalente en IGG ni en Taiwan (p. ej. los
    NPC de servicio de Bluesand Realm, cuyas lineas de Floral Alley dicen
    'Floral Alley'). Se escriben en extracted_paks/update26 y en
    update26.pak y su .bak."""
    import pak_tool
    datos = json.loads((RAIZ / 'work' / 'msg_propios.json').read_text(encoding='utf-8'))
    f = IGG / 'update26' / 'setting' / 'eng' / 'msg.xml'
    raw = f.read_bytes()
    bom = raw.startswith(b'\xef\xbb\xbf')
    txt = raw.decode('utf-8-sig')
    ya = filas(txt)
    import traducir
    nuevas = ['    <字串 編號="%s" 文字="%s"/>\r\n' % (k, traducir.escapar(v))
              for k, v in sorted(datos.items()) if k.isdigit() and k not in ya]
    if not nuevas:
        print('msg.xml ya tiene las lineas propias')
        return
    p = punto_insercion(txt)
    txt = txt[:p] + ''.join(nuevas) + txt[p:]
    f.write_bytes(b'\xef\xbb\xbf' * bom + txt.encode('utf-8'))
    for n in ('update26.pak', 'update26.pak.bak'):
        if (CLIENTE / n).exists():
            pak_tool.actualizar(CLIENTE / n, {'SETTING\\ENG\\MSG.XML': f.read_bytes()})
    print('msg.xml: +%d lineas propias' % len(nuevas))


def desinstalar(ts: str):
    import shutil
    bk = BACKUPS / ts
    reg = json.loads((bk / 'instalacion.json').read_text(encoding='utf-8'))
    for n in reg['paks_nuevos']:
        if (bk / 'cliente' / n).exists():
            shutil.copy2(bk / 'cliente' / n, CLIENTE / n)
        elif (CLIENTE / n).exists():
            (CLIENTE / n).unlink()
    for n in ('update26.pak', 'update26.pak.bak'):
        if (bk / 'cliente' / n).exists():
            shutil.copy2(bk / 'cliente' / n, CLIENTE / n)
    for f in (bk / 'extracted_paks_update26').rglob('*'):
        if f.is_file():
            shutil.copy2(f, IGG / 'update26' / f.relative_to(bk / 'extracted_paks_update26'))
    for rel in reg['extraidos_nuevos']:
        p = IGG / 'update26' / rel
        if p.exists():
            p.unlink()
    print('restaurado el estado de', ts)


if __name__ == '__main__':
    orden = sys.argv[1] if len(sys.argv) > 1 else 'analizar'
    if orden == 'tablas':
        construir(con_paks=False)
    elif orden == 'instalar':
        instalar()
    elif orden == 'instalar_tablas':
        instalar(con_paks=False)
    elif orden == 'instalar_servidor':
        instalar(con_paks=False, cliente=False)
    elif orden == 'contenido':
        contenido()
    elif orden == 'msg_propios':
        msg_propios()
    elif orden == 'ajustes_wnd':
        ajustes_wnd()
    elif orden == 'reparar_alias':
        print('\n'.join(reparar_alias()))
    elif orden == 'desinstalar':
        desinstalar(sys.argv[2])
    else:
        {'analizar': analizar, 'memoria': memoria, 'construir': construir}[orden]()
