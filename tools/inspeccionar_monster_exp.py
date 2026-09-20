import sqlite3
con = sqlite3.connect('corpus/content.db')
rows = con.execute('select id, name, level, exp_value from monster where id in ("7", "19", "20")').fetchall()
for r in rows:
    print("Monster:", r)

