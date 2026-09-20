import json

d = json.load(open('server/plantillas/lyceum.json', encoding='utf-8'))
print("Spawns count:", len(d.get('spawns', [])))
print("Recursos count:", len(d.get('recursos', [])))

npcs = [s['nombre'] for s in d.get('spawns', []) if not s.get('monstruo')]
print("NPCs in lyceum.json:", set(npcs))

monsters = [s['nombre'] for s in d.get('spawns', []) if s.get('monstruo')]
print("Monsters in lyceum.json:", set(monsters))

for s in d.get('spawns', []):
    name = s.get('nombre')
    if any(k in name for k in ['Tutor', 'Scroll', 'Magic', 'Pet', 'Smith', 'Plan', 'Art', 'Sewing', 'Badge', 'Professor']):
        print(f"Spawn: eid={s['entity_id']}, name={name}, npc_type={s.get('npc_type')}, tile={s.get('tile')}")

