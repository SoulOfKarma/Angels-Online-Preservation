"""
Extrae el contenido del juego desde los XML del cliente a una base SQLite.

Los parches se aplican en orden cronologico (data1 -> update26); un registro de
un parche posterior pisa al mismo id de uno anterior. Es la misma semantica que
usa el cliente al montar los .pak.

Los atributos vienen con nombres en chino tradicional; se traducen a columnas
legibles. Un atributo sin traduccion NO se descarta: se guarda con su nombre
original, para no perder datos por ignorancia.
"""
import re, sys, pathlib, sqlite3, collections, json
import xml.etree.ElementTree as ET

ORDEN = ['data1', 'update', 'update2', 'update3'] + \
        [f'UPDATE{i}' for i in range(4, 22)] + \
        [f'update{i}' for i in range(22, 27)]

TRAD = {
    '編號': 'id', '名稱': 'name', '圖號': 'sprite_id', '等級': 'level',
    '系別': 'element', '陣營': 'faction', 'HP': 'hp', 'MP': 'mp',
    '平均攻擊': 'atk_avg', '攻擊變數': 'atk_var', '防禦': 'def',
    '魔攻': 'matk', '魔防': 'mdef', '精準': 'accuracy', '靈敏': 'agility',
    '雷電防禦': 'res_lightning', '火焰防禦': 'res_fire', '寒冰防禦': 'res_ice',
    '腐蝕防禦': 'res_corrosion', '體質抵抗': 'res_body', '心靈抵抗': 'res_mind',
    '移動速度': 'move_speed', '移動範圍': 'move_range', '攻擊速度': 'atk_speed',
    '攻擊範圍': 'atk_range', '重擊機率': 'crit_rate', '耐久破壞': 'dura_dmg',
    '經驗價值': 'exp_value', '掉寶編號': 'drop_id',
    '平時音效': 'snd_idle', '攻擊音效': 'snd_atk', '陣亡音效': 'snd_die',
    '個數': 'count', '怪物名稱': 'monster_name',
    '判斷類型': 'cond_type', '判斷值1': 'cond_v1', '判斷值2': 'cond_v2',
    '觸發間隔': 'trigger_interval',
    '角色': 'exp_char', '生命': 'exp_life',
    '價格': 'price', '重量': 'weight', '說明': 'desc', '種類': 'kind',
    '需求等級': 'req_level', '攻擊': 'atk', '類型': 'type',
    '等級': 'level', '商店': 'shop',
}

# Claves primarias alternativas: no todos los XML usan 編號 (id).
CLAVES = ('id', 'level')

ARCHIVOS = ['level.xml', 'monster.xml', 'npc.xml', 'drop.xml', 'simpleai.xml', 'magic.xml', 'shop.xml', 'quest.xml', 'stage.xml', 'item.xml',
            'item2.xml', 'item3.xml', 'item4.xml', 'item5.xml', 'item6.xml',
            'item7.xml', 'item8.xml', 'item9.xml', 'petattrib.xml', 'doll.xml']

REC = re.compile(r'<(\w+)\s([^>]*?)/?>')
ATR = re.compile(r'([^\s=]+)="([^"]*)"')


def parse_xml(path):
    """Devuelve (tag_raiz, [registros]).

    Dos formatos conviven en estos XML:
      a) atributos:       <npc 編號="1" 名稱="..." />
      b) elementos hijos: <exp 等級="1"><角色>0</角色>...</exp>
    Se intenta ElementTree (maneja los dos); si el archivo tiene bytes sueltos
    que rompen el parser estricto, se cae al parser por regex, que solo lee
    atributos pero nunca falla.
    """
    txt = path.read_text(encoding='utf-8', errors='replace')
    try:
        root = ET.fromstring(txt)
        out, tag = [], None
        for el in root:
            tag = tag or el.tag
            d = {TRAD.get(k, k): v for k, v in el.attrib.items()}
            for hijo in el:
                if hijo.text is not None:
                    d[TRAD.get(hijo.tag, hijo.tag)] = hijo.text.strip()
            if d: out.append(d)
        if out: return tag, out
    except ET.ParseError:
        pass
    out, tag = [], None
    for m in REC.finditer(txt):
        t, body = m.group(1), m.group(2)
        if t in ('root', 'xml'): continue
        tag = tag or t
        d = {}
        for k, v in ATR.findall(body):
            d[TRAD.get(k, k)] = v
        if d: out.append(d)
    return tag, out


def main(raiz, dbpath):
    raiz = pathlib.Path(raiz)
    db = sqlite3.connect(dbpath)
    resumen = []
    for archivo in ARCHIVOS:
        # SEMANTICA DE PARCHES: merge por registro, el parche posterior pisa el
        # mismo id. Decidido por medicion, no por intuicion:
        #
        #   - monster.xml es acumulativo (1.682 registros en data1 -> 19.194 en
        #     update26), asi que merge y "gana el ultimo" dan casi lo mismo
        #     (19.206 vs 19.194).
        #   - drop.xml NO lo es: cae de 1.794 a 442 registros en update2 y los
        #     conjuntos de id son largamente disjuntos. update26 cubre apenas
        #     el 31,1% de los ids >=232 de data1.
        #
        # La prueba que decide: 1.316 drop_id referenciados por monstruos que
        # SIGUEN EXISTIENDO en update26 solo tienen tabla en parches viejos,
        # entre ellos los ids 1-10 (Wind Elf, el monstruo inicial). Con "gana
        # el ultimo" los primeros monstruos del juego no dropearian nada.
        # Por lo tanto el merge es lo correcto.
        fusion, procedencia, cols = {}, {}, []
        for pak in ORDEN:
            for sub in ('setting/eng', 'setting'):
                q = raiz / pak / sub / archivo
                if not q.exists(): continue
                tag, recs = parse_xml(q)
                for r in recs:
                    rid = next((r[k] for k in CLAVES if r.get(k) is not None), None)
                    if rid is None: continue
                    # fila de ENCABEZADO disfrazada de dato (id="編號")
                    if not str(rid).strip().lstrip('-').isdigit(): continue
                    fusion[rid] = r
                    procedencia[rid] = pak
                break
        if not fusion: continue
        # SQLite no distingue mayusculas en nombres de columna: 'AI' y 'ai'
        # colisionan. Se desambigua con sufijo en vez de descartar el atributo.
        vistos, mapa = {}, {}
        for r in fusion.values():
            for k in r:
                if k in mapa: continue
                base = k; low = base.lower(); n = vistos.get(low, 0)
                col = base if n == 0 else f"{base}_{n+1}"
                while col.lower() in vistos and n > 0:
                    n += 1; col = f"{base}_{n+1}"
                vistos[low] = vistos.get(low, 0) + 1
                vistos[col.lower()] = vistos.get(col.lower(), 0)
                mapa[k] = col; cols.append(col)
        tabla = archivo.replace('.xml', '')
        # 'drop' es palabra reservada en SQL: se renombra para no tener
        # que citarla en cada consulta.
        tabla = {'drop': 'drop_table'}.get(tabla, tabla)
        db.execute(f'DROP TABLE IF EXISTS "{tabla}"')
        defs = ', '.join(f'"{c}" TEXT' for c in cols)
        db.execute(f'CREATE TABLE "{tabla}" ({defs}, "_pak" TEXT)')
        db.executemany(
            f'INSERT INTO "{tabla}" VALUES ({",".join("?"*(len(cols)+1))})',
            [[r.get(o) for o in mapa] + [procedencia[k]] for k, r in fusion.items()])
        db.commit()
        sin_trad = sum(1 for c in cols if any(ord(ch) > 0x2E80 for ch in c))
        resumen.append((tabla, len(fusion), len(cols), sin_trad))
        print(f"  {tabla:<14} {len(fusion):>7} registros  {len(cols):>3} columnas"
              f"  ({sin_trad} sin traducir)")
    print(f"\n{len(resumen)} tablas en {dbpath}")
    db.close()


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
