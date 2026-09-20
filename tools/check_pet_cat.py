import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
con = sqlite3.connect('corpus/content.db')
cols = [c[1] for c in con.execute('pragma table_info(item)').fetchall()]
idx_cat = cols.index('物品類別')
row = con.execute('select * from item where id="3605"').fetchone()
val = row[idx_cat]
print('Category:', repr(val), 'type:', type(val))
print('Equals 寵物:', val == '寵物', 'in:', '寵物' in str(val))

