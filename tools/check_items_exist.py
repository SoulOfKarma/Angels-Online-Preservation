import sqlite3

con = sqlite3.connect('corpus/content.db')
items_to_check = [1, 26, 19838, 28, 30, 1577, 1949, 1951, 19966, 5933, 2, 1228, 1581, 1587, 1590, 20044, 20055, 3399, 20075, 20104, 19826]

for it in items_to_check:
    r = con.execute('select id, "基本名稱", "物品類別" from item where id=?', (str(it),)).fetchone()
    if r:
        print(f"Item {it:5d}: {r[1]} (cat: {r[2]})")
    else:
        print(f"Item {it:5d}: NO EXISTE EN ITEM.XML!")
