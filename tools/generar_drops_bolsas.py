import json
import pathlib
import sqlite3
import time
import xml.etree.ElementTree as ET

RAIZ = pathlib.Path(__file__).resolve().parent.parent

def build_drops_cache():
    t0 = time.time()
    tablas = {}

    # 1. First load from content.db drop_table
    db = RAIZ / 'corpus' / 'content.db'
    if db.exists():
        con = sqlite3.connect(db)
        cols = [c[1] for c in con.execute('pragma table_info(drop_table)')]
        for row in con.execute('select * from drop_table'):
            d = dict(zip(cols, row))
            did = str(d.get('id') or '').strip()
            if not did or not did.isdigit():
                continue
            factor = int(d.get('factor') or 100)
            items = []
            for i in range(1, 41):
                it = d.get(f'item{i}')
                cnt = d.get(f'count{i}')
                prob = d.get(f'prob{i}')
                if it and str(it).isdigit() and int(it) > 0:
                    items.append([
                        int(it),
                        int(cnt) if cnt and str(cnt).isdigit() else 1,
                        int(prob) if prob and str(prob).isdigit() else 1
                    ])
            if items:
                tablas[int(did)] = items

    # 2. Merge from all serv_drop.xml and drop.xml
    all_xmls = list(RAIZ.glob('extracted_paks/**/serv_drop.xml')) + list(RAIZ.glob('extracted_paks/**/drop.xml'))
    for p in all_xmls:
        raw = p.read_bytes()
        for enc in ['utf-8', 'cp950', 'gbk', 'big5', 'latin1']:
            try:
                text = raw.decode(enc)
                root = ET.fromstring(text.encode('utf-8'))
                for e in root:
                    did = e.attrib.get('編號') or e.attrib.get('id')
                    if did and did.isdigit():
                        did_int = int(did)
                        if did_int in tablas:
                            continue  # keep existing or prioritize
                        items = []
                        for i in range(1, 41):
                            it = e.attrib.get(f'item{i}')
                            cnt = e.attrib.get(f'count{i}')
                            prob = e.attrib.get(f'prob{i}')
                            if it and it.isdigit() and int(it) > 0:
                                items.append([
                                    int(it),
                                    int(cnt) if cnt and cnt.isdigit() else 1,
                                    int(prob) if prob and prob.isdigit() else 1
                                ])
                        if items:
                            tablas[did_int] = items
                break
            except Exception:
                pass

    out_file = RAIZ / 'server' / 'plantillas' / 'drops_bolsas.json'
    out_file.write_text(json.dumps(tablas, separators=(',', ':')), encoding='utf-8')
    t1 = time.time()
    size_mb = out_file.stat().st_size / (1024 * 1024)
    print(f"Generated {out_file.name} with {len(tablas)} drop tables ({size_mb:.2f} MB) in {t1 - t0:.2f}s")

if __name__ == '__main__':
    build_drops_cache()

