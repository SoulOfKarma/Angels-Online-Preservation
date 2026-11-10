"""Traduccion zh/ja -> en de los textos del cliente, por memoria y por lotes.

Orden de busqueda de un texto (o de cada linea de un texto):
  1. work/traduccion/manual/*.json   lo traducido a mano / por Claude
  2. work/traduccion/memoria.json    pares reales TW(chino) <-> IGG(ingles)
                                     por ID y campo (tw_migracion.py memoria)
  3. plantillas numericas: '41星祝福打孔錘' se resuelve con el patron
     aprendido de '40星祝福打孔錘' cambiando solo los numeros.

Las claves de los manuales son segmentos con los numeros cambiados por '#'
(asi un mismo texto sirve para todos los niveles). En el valor, cada '#' se
rellena en orden con los numeros del original; si hay que reordenarlos se
escribe {0}, {1}...

Los valores se guardan como texto llano y se escapan al aplicarlos: el XML
del cliente lleva los saltos como '&#xA;' o como '\\n' literal y eso NO se
toca -- se traduce linea a linea.

    python -I tools/traducir.py estado
    python -I tools/traducir.py exportar [n_por_lote] [max_lotes]
"""
import collections
import json
import pathlib
import re
import sys
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tw_migracion as tw  # noqa: E402
from colores_texto import normalizar_colores  # noqa: E402

DIR = tw.RAIZ / 'work' / 'traduccion'
MANUAL = DIR / 'manual'
LOTES = DIR / 'lotes'

RN = re.compile(r'\d+')
SEP = re.compile(r'(&#xA;|\\n|\n)')
# prefijo de vineta / sufijo de cantidad (*10, ×2) que no se traducen
PARTES = re.compile(r'^([\s・·]*)(.*?)(\s*[\*×]\s*\d+\s*)?$', re.S)
PERGAMINO = re.compile(
    r'(.+?)第([一二三四五六七八九十])階，「(.+)」的(?:招式|法術)，對卷軸按下右鍵即可學會。',
    re.S)
RANGOS = dict(zip('一二三四五六七八九十',
                  ('Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ', 'Ⅵ', 'Ⅶ', 'Ⅷ', 'Ⅸ', 'Ⅹ')))


def escapar(s: str) -> str:
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace('"', '&quot;').replace('\n', '&#xA;'))


def _rellenar(plantilla: str, nums) -> str:
    if '{0}' in plantilla:
        return plantilla.format(*nums)
    it = iter(nums)
    return re.sub('#', lambda m: next(it, '#'), plantilla)


class Traductor:
    def __init__(self):
        self.tm = json.loads(tw.MEMORIA.read_text(encoding='utf-8')) if tw.MEMORIA.exists() else {}
        # plantillas numericas de la memoria: '#星祝福打孔錘' -> '{0}-star ...'
        self.tm_pat = {}
        for zh, en in self.tm.items():
            nz, ne = RN.findall(zh), RN.findall(en)
            if nz and sorted(nz) == sorted(ne) and len(set(nz)) == len(nz):
                tpl = RN.sub(lambda m: '{%d}' % nz.index(m.group(0)), en)
                self.tm_pat.setdefault(RN.sub('#', zh), tpl)
        self.manual = {}
        if MANUAL.is_dir():
            for f in sorted(MANUAL.glob('*.json')):
                for k, v in json.loads(f.read_text(encoding='utf-8')).items():
                    if v and v.strip():
                        self.manual[k] = escapar(v)

    def buscar(self, s: str):
        """Traduccion de un segmento exacto, o None."""
        nums = RN.findall(s)
        k = RN.sub('#', s)
        if k in self.manual:
            return _rellenar(self.manual[k], nums)
        if s in self.manual:
            return self.manual[s]
        if s in self.tm:
            return self.tm[s]
        if nums and k in self.tm_pat:
            try:
                return self.tm_pat[k].format(*nums)
            except (IndexError, KeyError):
                return None
        m = PERGAMINO.fullmatch(s)
        if m:
            nombre, rango, descripcion = m.groups()
            romano = RANGOS[rango]
            titulo = self.buscar(nombre + romano)
            # Los nombres IGG usan romanos ASCII; las claves TW usan Unicode.
            sufijo = ' ' + unicodedata.normalize('NFKC', romano)
            texto, completo = self.traducir(descripcion)
            if titulo and titulo.endswith(sufijo) and completo:
                nombre_igg = titulo[:-len(sufijo)]
                nivel = '一二三四五六七八九十'.index(rango) + 1
                return '%s rank %d, [%s], right click the scroll to learn.' % (
                    nombre_igg, nivel, texto)
        return None

    def traducir(self, v: str):
        """(texto, completo). Lo no resuelto se deja como estaba."""
        if not tw.RE_CJK.search(v):
            return normalizar_colores(v), True
        r = self.buscar(v)
        if r is not None:
            return normalizar_colores(r), True
        trozos, completo = [], True
        for s in SEP.split(v):
            if not s or SEP.fullmatch(s) or not tw.RE_CJK.search(s):
                trozos.append(s)
                continue
            pre, core, suf = PARTES.match(s).groups()
            r = self.buscar(core)
            if r is None:
                completo = False
                trozos.append(s)
            else:
                trozos.append(pre + r + (suf or ''))
        return normalizar_colores(''.join(trozos)), completo

    def segmentos_pendientes(self, v: str):
        """Claves normalizadas (con '#') que faltan para traducir v."""
        if not tw.RE_CJK.search(v) or self.buscar(v) is not None:
            return []
        out = []
        for s in SEP.split(v):
            if s and not SEP.fullmatch(s) and tw.RE_CJK.search(s):
                core = PARTES.match(s).group(2)
                if self.buscar(core) is None:
                    out.append(RN.sub('#', core))
        return out


# Prioridad de un campo: los nombres se ven en todas partes.
PESO_CAMPO = {'基本名稱': 0, '名稱': 0, '原型名稱': 0, '封號': 1, '場景名稱': 1,
              '任務名稱': 1, '文字': 2, '說明定義': 3, '說明': 3, '獎賞說明': 4,
              '怪物名稱': 9, 'Npc名稱': 9}


def recolectar(trad: Traductor):
    """{segmento: info} de todo lo pendiente, con contexto para traducir."""
    info = {}
    for r, fi, ft in tw.tablas_vigentes():
        tabla = r.split('\\')[-1]
        nuevas = [(k, v) for k, v in ft.items() if k not in fi]
        for es_nueva, (i, fila) in [(False, x) for x in fi.items()] + [(True, x) for x in nuevas]:
            for a, v in tw.atributos(fila).items():
                if not tw.es_texto(a):
                    continue
                for seg in trad.segmentos_pendientes(v):
                    d = info.get(seg)
                    if d is None:
                        d = info[seg] = dict(n=0, nueva=False, peso=9, ctx='%s#%s %s' % (tabla, i, a))
                    d['n'] += 1
                    d['nueva'] |= es_nueva
                    d['peso'] = min(d['peso'], PESO_CAMPO.get(a, 5))
    return info


def estado():
    trad = Traductor()
    tot = hechos = 0
    for r, fi, ft in tw.tablas_vigentes():
        filas = list(fi.values()) + [v for k, v in ft.items() if k not in fi]
        for fila in filas:
            for a, v in tw.atributos(fila).items():
                if tw.es_texto(a) and tw.RE_CJK.search(v):
                    tot += 1
                    hechos += trad.traducir(v)[1]
    print('campos de texto con chino/japones: %d, traducidos completos: %d (%.1f%%)'
          % (tot, hechos, 100.0 * hechos / max(tot, 1)))
    print('entradas manuales: %d, memoria: %d' % (len(trad.manual), len(trad.tm)))


def exportar(por_lote: int = 300, max_lotes: int = 10):
    """Escribe lotes {segmento: ''} por prioridad, para rellenar y mover a manual/."""
    trad = Traductor()
    info = recolectar(trad)
    orden = sorted(info, key=lambda s: (info[s]['peso'], not info[s]['nueva'],
                                        len(s) > 40, -info[s]['n'], s))
    LOTES.mkdir(parents=True, exist_ok=True)
    for f in LOTES.glob('lote_*.json'):
        f.unlink()
    for n in range(min(max_lotes, (len(orden) + por_lote - 1) // por_lote)):
        trozo = orden[n * por_lote:(n + 1) * por_lote]
        lote = {s: '' for s in trozo}
        ctx = {s: info[s]['ctx'] for s in trozo}
        (LOTES / ('lote_%03d.json' % n)).write_text(
            json.dumps(lote, ensure_ascii=False, indent=0), encoding='utf-8')
        (LOTES / ('lote_%03d.ctx.json' % n)).write_text(
            json.dumps(ctx, ensure_ascii=False, indent=0), encoding='utf-8')
    print('pendientes: %d segmentos (%d chars); %d nuevos de TW 27-32'
          % (len(info), sum(map(len, info)), sum(1 for d in info.values() if d['nueva'])))


if __name__ == '__main__':
    orden = sys.argv[1] if len(sys.argv) > 1 else 'estado'
    if orden == 'exportar':
        exportar(*[int(x) for x in sys.argv[2:4]])
    else:
        estado()
