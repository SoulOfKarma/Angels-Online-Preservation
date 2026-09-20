import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

con = sqlite3.connect('corpus/content.db')
cols = ('右手裝備', '左手裝備', '頭部裝備', '飾品裝備', '身體裝備', '手部裝備', '腳部裝備', '背部裝備', '寵物座騎裝備')
campos = ','.join(f'"{c}"' for c in cols)
for iid in ['10', '3605', '3396']:
    row = con.execute(f'select "物品類別", {campos} from item where id="{iid}"').fetchone()
    print(f"Item {iid}: 物品類別={repr(row[0])}")
    for c, v in zip(cols, row[1:]):
        print(f"   {c}: {repr(v)}")

