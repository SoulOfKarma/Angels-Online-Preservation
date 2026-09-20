import sqlite3

con = sqlite3.connect('corpus/content.db')
cols = [c[1] for c in con.execute('pragma table_info(magic)').fetchall()]
row = con.execute('select * from magic where id="601"').fetchone()
d = dict(zip(cols, row))
for k, v in d.items():
    if v:
        print(f"{k}: {v}")

