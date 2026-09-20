import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

con = sqlite3.connect('corpus/content.db')

con = sqlite3.connect('corpus/content.db')

import glob, json, struct

for r in con.execute('select level, exp_char, exp_life from level limit 15').fetchall():
    print(r)








print("--- Distinct 施展動作 ---")
for r in con.execute('select distinct "施展動作" from magic').fetchall():
    print(r)

print("--- Priest spells ---")
for r in con.execute('select id, name, "施展動作", "特效編號", "攻擊型", "物理型", "HP定義", hp, "對象" from magic where id in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20)').fetchall():
    print(r)



