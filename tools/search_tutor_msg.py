import sqlite3, pathlib

db = pathlib.Path('corpus/content.db')
con = sqlite3.connect(db)
print("--- Buscar en msg ---")
for r in con.execute('select id, val from msg where val like ? or val like ? limit 20', ('%tutor%lyceum%', '%tutor in%')).fetchall():
    print(r[0], r[1][:100])

print("\n--- Buscar en dialogos_npc.json ---")
import json
f = pathlib.Path('server/plantillas/dialogos_npc.json')
d = json.loads(f.read_text(encoding='utf-8'))
for k, v in d.items():
    if 'tutor' in k.lower():
        print(f"Key={k}")
        for step in v.get('pasos', []):
            print("  ", step)

