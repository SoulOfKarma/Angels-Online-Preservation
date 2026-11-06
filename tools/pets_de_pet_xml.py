"""Vuelca pet.xml de los paks a un JSON que el servidor pueda leer.

pet.xml es la tabla que faltaba para las mascotas. Trae, por cada una:

    編號        el sprite, que es el numero que viaja en la entrada del
                inventario (+131) y en el 0x0065 (+16)
    圖號1       el TIPO, que va en el +4 del 0x0065. Dejandolo en cero el
                cliente no sabe que mascota es: la ventana salia sin nivel
                y sin dibujo
    名稱        el nombre por defecto, el de su clase
    寵物類型     con que fila de petattrib se sacan sus stats
    階段        原型 / 初階 / 中階 / 高階 / 頂階, la etapa de evolucion
    升階變化1/2  las DOS ramas a las que puede evolucionar. La 1 es la
                "mean" y la 2 la "nice" del arbol de la wiki: el Elf Egg
                (3181) va a Naughty Elf (3183) o a Flying Guy (3182)
    條件成長值   el valor de crianza que hace falta para pasar de etapa

Hay 25 versiones del fichero en los paks y ganan las nuevas, asi que se
leen en orden: data1, update, update3, UPDATE4..UPDATE21, update22 y las
siguientes. Con ese orden los trece pares sprite/tipo medidos en el proxy
cuadran los trece.

    python tools/pets_de_pet_xml.py
"""
import collections
import json
import os
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).parent.parent
SALIDA = RAIZ / 'server' / 'plantillas' / 'mascotas.json'

CAMPOS = {'編號': 'sprite', '圖號1': 'tipo', '名稱': 'nombre',
          '寵物類型': 'clase', '階段': 'etapa',
          '經驗等級表': 'exp_tipo',
          '升階變化1': 'rama1', '升階變化2': 'rama2',
          '條件成長值': 'crianza', '移動速度': 'velocidad',
          '攻擊速度': 'vel_ataque', '攻擊範圍': 'rango_ataque',
          '頭像編號': 'retrato',
          '技能1階級表': 'sk1', '技能2階級表': 'sk2', '技能3階級表': 'sk3',
          'HP': 'hp_min', 'HP上限': 'hp_max',
          'MP': 'mp_min', 'MP上限': 'mp_max',
          '平均攻擊': 'atk_min', '平均攻擊上限': 'atk_max',
          '防禦': 'dfs_min', '防禦上限': 'dfs_max',
          '魔攻': 'matk_min', '魔攻上限': 'matk_max',
          '魔防': 'mdef_min', '魔防上限': 'mdef_max',
          '精準': 'rigor_min', '精準上限': 'rigor_max',
          '靈敏': 'agilidad_min', '靈敏上限': 'agilidad_max'}



def _orden(p):
    """data1 primero y los update numerados despues, de menor a mayor."""
    n = str(p).split(os.sep)[-4]
    if n == 'data1':
        return (0, 0)
    if n == 'update':
        return (1, 0)
    m = re.search(r'(\d+)', n)
    return (2, int(m.group(1)) if m else 0)


def cargar(raiz=None):
    """{sprite: {...}} con todas las mascotas, la version nueva mandando."""
    raiz = pathlib.Path(raiz or RAIZ)
    # petex.xml trae doce mas con el mismo esquema (los lobos 3001+). Va
    # PRIMERO para que pet.xml pueda pisarlas si las repite.
    # TODAS las carpetas, no solo eng/: hay paks que dejan el fichero en
    # setting/ a secas o en big5/, y ganan siempre los updates mas nuevos.
    fs = []
    for pat in ('extracted_paks/*/setting/*/petex.xml',
                'extracted_paks/*/setting/petex.xml',
                'extracted_paks/*/setting/*/pet.xml',
                'extracted_paks/*/setting/pet.xml'):
        fs += sorted(raiz.glob(pat), key=_orden)
    idx = {}
    for f in fs:
        txt = f.read_text(encoding='utf-8', errors='replace')
        for trozo in re.findall(r'<pet\s([^>]*?)/>', txt):
            a = dict(re.findall(r'(\S+?)="([^"]*)"', trozo))
            if not a.get('編號', '').isdigit():
                continue
            d = {}
            for k, v in CAMPOS.items():
                # Taiwan trae clases con espacios (' 輔助攻擊型', '魔攻型 ') y
                # el servidor las busca tal cual en petattrib: sin recortar,
                # esas mascotas caian en la clase por defecto.
                val = (a.get(k) or '').strip()
                if val == '':
                    continue
                d[v] = int(val) if val.lstrip('-').isdigit() else val
            idx[int(a['編號'])] = d
    return idx


ASPECTOS = RAIZ / 'server' / 'plantillas' / 'crianza.json'
HABILIDADES = RAIZ / 'server' / 'plantillas' / 'petskills.json'


def _mezclar(raiz, patron, etiqueta):
    """Todos los <etiqueta> de ese patron, con la version nueva mandando."""
    fs = sorted(pathlib.Path(raiz).glob(patron), key=_orden)
    idx = {}
    for f in fs:
        txt = f.read_text(encoding='utf-8', errors='replace')
        for trozo in re.findall(r'<%s\s([^>]*?)/>' % etiqueta, txt):
            a = dict(re.findall(r'(\S+?)="([^"]*)"', trozo))
            if a.get('編號', '').isdigit():
                idx[int(a['編號'])] = a
    return idx


def habilidades(raiz=None):
    """Las tablas de habilidades de mascota de petskill.xml (niveles 1 a 26)."""
    raiz = pathlib.Path(raiz or RAIZ)
    idx = {}
    for pat in ('extracted_paks/*/setting/*/petskill.xml',
                'extracted_paks/*/setting/petskill.xml'):
        idx.update(_mezclar(raiz, pat, 'petskill'))
    out = {}
    for n, a in sorted(idx.items()):
        out[str(n)] = [int(a.get('技能%d級' % k) or 0) for k in range(1, 27)]
    return out


def crianza(raiz=None):
    """Las situaciones de petaspect.xml: el sistema de crianza.

    Cada una trae una escena y TRES opciones, y cada opcion suma un
    "valor de reaccion" que va de -3 a +3. El propio texto lo dice: "las
    acciones del dueño afectaran la direccion de crecimiento del pet". Ese
    acumulado es lo que decide a cual de las dos ramas evoluciona, y el
    umbral es el 條件成長值 de cada mascota, que vale 10.

    Positivo tira de una rama y negativo de la otra; cual es cual todavia
    hay que medirlo criando una y viendo a donde sale.
    """
    raiz = pathlib.Path(raiz or RAIZ)
    idx = {}
    for pat in ('extracted_paks/*/setting/*/petaspect.xml',
                'extracted_paks/*/setting/petaspect.xml'):
        idx.update(_mezclar(raiz, pat, 'petaspect'))
    out = {}
    for n, a in sorted(idx.items()):
        out[str(n)] = {
            'tipo': int(a.get('類型') or 0),
            'texto': a.get('敘述句', ''),
            'opciones': [
                {'texto': a.get('選項%d' % k, ''),
                 'valor': int(a.get('反應值%d' % k) or 0)}
                for k in (1, 2, 3)
                if a.get('選項%d' % k)],
        }
    return out


ATRIBUTOS = RAIZ / 'server' / 'plantillas' / 'petattrib.json'


def petattrib(raiz=None):
    """La tabla petattrib.xml volcada a JSON compacto {clase: {nivel: [hp,mp,atk,dfs,matk,mdef,rigor,agilidad]}}."""
    raiz = pathlib.Path(raiz or RAIZ)
    fs = []
    for pat in ('extracted_paks/*/setting/*/petattrib.xml',
                'extracted_paks/*/setting/petattrib.xml'):
        fs += sorted(raiz.glob(pat), key=_orden)
    out = {}
    for f in fs:
        txt = f.read_text(encoding='utf-8', errors='replace')
        for trozo in re.findall(r'<petattrib\s([^>]*?)/>', txt):
            a = dict(re.findall(r'(\S+?)="([^"]*)"', trozo))
            clase = a.get('寵物類型')
            lv = a.get('等級')
            if not clase or not lv or not lv.isdigit():
                continue
            out.setdefault(clase, {})[str(int(lv))] = [
                int(float(a.get('HP') or 0)),
                int(float(a.get('MP') or 0)),
                int(float(a.get('平均攻擊') or 0)),
                int(float(a.get('防禦') or 0)),
                int(float(a.get('魔攻') or 0)),
                int(float(a.get('魔防') or 0)),
                int(float(a.get('精準') or 0)),
                int(float(a.get('靈敏') or 0)),
            ]
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    idx = cargar()
    if not idx:
        print('no encontre ningun pet.xml en extracted_paks/')
        return 1
    SALIDA.write_text(json.dumps({str(k): v for k, v in sorted(idx.items())},
                                 ensure_ascii=False, indent=1),
                      encoding='utf-8')
    asp = crianza()
    ASPECTOS.write_text(json.dumps(asp, ensure_ascii=False, indent=1),
                        encoding='utf-8')
    sks = habilidades()
    HABILIDADES.write_text(json.dumps(sks, ensure_ascii=False, indent=1),
                           encoding='utf-8')
    attr = petattrib()
    ATRIBUTOS.write_text(json.dumps(attr, ensure_ascii=False, separators=(',', ':')),
                         encoding='utf-8')
    print('%d situaciones de crianza -> %s'
          % (len(asp), ASPECTOS.relative_to(RAIZ)))
    print('%d tablas de habilidades -> %s'
          % (len(sks), HABILIDADES.relative_to(RAIZ)))
    print('%d clases de petattrib -> %s'
          % (len(attr), ATRIBUTOS.relative_to(RAIZ)))
    etapas = collections.Counter(d.get('etapa') for d in idx.values())
    print('%d mascotas -> %s' % (len(idx), SALIDA.relative_to(RAIZ)))
    print('etapas:', dict(etapas))
    print('clases distintas:', len({d.get('clase') for d in idx.values()}))
    return 0


if __name__ == '__main__':
    sys.exit(main())

