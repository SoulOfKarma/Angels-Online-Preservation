import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

con = sqlite3.connect('corpus/content.db')

for r in con.execute('select id, name, "圖號1", "類別" from npc where name like "%Portal%" or name like "%Warp%" or name like "%Teleport%" limit 20').fetchall():
    print(f"ID={r[0]:4s} Name={r[1]:25s} Sprite={r[2]} Type={r[3]}")

