import sqlite3
import sys

con = sqlite3.connect('corpus/content.db')
cols = [c[1] for c in con.execute('pragma table_info(magic)').fetchall()]
for mid in (601, 602, 603, 701, 702, 703, 713, 714, 656):
    row = con.execute('select * from magic where id=?', (str(mid),)).fetchone()
    if not row: continue
    d = dict(zip(cols, row))
    sys.stdout.buffer.write(f"\n=== {mid}: {d.get('name')} ===\n".encode('utf-8'))
    for k, v in d.items():
        if v and v != '0' and v != 'None':
            sys.stdout.buffer.write(f"  {k}: {v}\n".encode('utf-8'))

