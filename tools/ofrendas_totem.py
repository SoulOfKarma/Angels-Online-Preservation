"""La tabla de ofrendas al totem: id de objeto -> puntos por cada 200 unidades.

Sale de los textos del Terra Keeper (arbol del mapa 16, nodos 1000058..1000091,
msg.xml): "When you use [Obsidian Brick], [Coral Strip]... you can upgrade your
totem experience by about 12 points", y asi hasta 1180 puntos. Y del 1000057:
"Every contribution is donated as a basic unit of 200". Los nombres se buscan
tal cual en las nueve tablas de objetos.

    python tools/ofrendas_totem.py      escribe server/plantillas/ofrendas_totem.json
"""
import json
import pathlib
import re
import sqlite3
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
import dialogos            # noqa: E402
import inventario          # noqa: E402

NODOS = ['1000058', '1000059', '1000060', '1000061', '1000062', '1000066', '1000067',
         '1000068', '1000069', '1000070', '1000071', '1000072', '1000073', '1000074',
         '1000091']


def main():
    msg = dialogos._cargar_msg_dict()
    arbol = json.loads((RAIZ / 'server' / 'plantillas' / 'dialogos_mapa.json')
                       .read_text(encoding='utf-8'))['16']
    con = sqlite3.connect(RAIZ / 'corpus' / 'content.db')
    por_nombre = {}
    for t in inventario.TABLAS_ITEM:
        try:
            for i, n in con.execute('SELECT id, "基本名稱" FROM %s' % t):
                if n and str(i).isdigit():
                    por_nombre.setdefault(str(n).strip().lower(), int(i))
        except sqlite3.Error:
            continue
    tabla, faltan = {}, []
    for k in NODOS:
        texto = msg.get(arbol[k]['m']) or ''
        pts = re.search(r'by (?:about )?(\d+)', texto)
        if not pts:
            continue
        for nombre in re.findall(r'\[([^\]]+)\]', texto):
            iid = por_nombre.get(nombre.strip().lower())
            if not iid:
                # Los textos no siempre escriben el nombre igual que el objeto
                # ("Leather lace" / "Leatherlace", "slice" / "slices"): se
                # compara sin espacios ni guiones y, si no, el mas parecido.
                import difflib
                clave = re.sub(r'[\s\-]', '', nombre.lower())
                juntos = {re.sub(r'[\s\-]', '', k): v for k, v in por_nombre.items()}
                iid = juntos.get(clave)
                if not iid:
                    cerca = difflib.get_close_matches(clave, list(juntos), n=1, cutoff=0.88)
                    iid = juntos[cerca[0]] if cerca else None
            if iid:
                tabla[str(iid)] = int(pts.group(1))
            else:
                faltan.append(nombre)
    salida = RAIZ / 'server' / 'plantillas' / 'ofrendas_totem.json'
    salida.write_text(json.dumps({'_nota': __doc__.strip().splitlines()[0],
                                  'unidad': 200, 'puntos': tabla},
                                 ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('%d materiales; sin id: %s' % (len(tabla), faltan))


if __name__ == '__main__':
    main()
