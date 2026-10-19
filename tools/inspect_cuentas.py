import sqlite3
import json

con = sqlite3.connect('data/cuentas.db')
r = con.execute("select datos from personajes where nombre='Karma'").fetchone()
if r:
    d = json.loads(r[0])
    inv = d.get('inventario', {})
    print("Karma's inventory count:", len(inv))
    for k, v in sorted(inv.items(), key=lambda x: int(x[0])):
        if v == 0 or v == '0' or not v or int(k) in (43, 50):
            print(f"  Slot {k}: {v}")
    print("\nAll slots around 40-55:")
    for k in range(40, 55):
        if str(k) in inv:
            print(f"  Slot {k}: {inv[str(k)]}")
        elif k in inv:
            print(f"  Slot {k}: {inv[k]}")
        else:
            print(f"  Slot {k}: <NOT IN INV>")

