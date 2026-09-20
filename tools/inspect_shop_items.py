import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

con = sqlite3.connect('corpus/content.db')

for shop_id in range(1, 100):
    row = con.execute('select * from shop where id=?', (str(shop_id),)).fetchone()
    if not row:
        continue
    items = [int(x) for x in row[1:10] if x and str(x).isdigit() and int(x) > 0]
    if items:
        # Consultar nombres de los primeros items
        nombres = []
        for it in items[:3]:
            r_it = con.execute('select "基本名稱", "物品類別" from item where id=?', (str(it),)).fetchone()
            if r_it:
                nombres.append(f"{r_it[0]} ({r_it[1]})")
        print(f"Shop {shop_id:2d}: {', '.join(nombres)}")

