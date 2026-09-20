import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

con = sqlite3.connect('corpus/content.db')

cols = [c[1] for c in con.execute('pragma table_info(monster)').fetchall()]
print("monster cols:", cols)
for r in con.execute('select id, name, move_speed, move_range, atk_range, 攻擊法術1, 投射特效, 主動, AI from monster where id in (7, 19, 14, 21, 23, 110)').fetchall():
    print(r)




