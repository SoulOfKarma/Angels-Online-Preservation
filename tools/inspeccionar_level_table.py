import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

con = sqlite3.connect('corpus/content.db')
cur = con.cursor()
cols = [c[1] for c in cur.execute('pragma table_info(level)').fetchall()]
print("Level columns count:", len(cols))
print("First 15 cols:", cols[:15])

rows = cur.execute('select * from level limit 5').fetchall()
for r in rows:
    print(r[:10])

