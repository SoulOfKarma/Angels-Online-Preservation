import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
con = sqlite3.connect('corpus/content.db')
cols = [c[1] for c in con.execute('pragma table_info(magic)').fetchall()]
# Spear is 槍. Let's find magics with Spear in name or desc
for r in con.execute("select id, name, 特效編號, 消耗MP from magic where name like '%Spear%' or desc like '%Spear%' or desc like '%spear%' limit 20").fetchall():
    print(r)

