import json
import struct

d = json.load(open('server/plantillas/dialogos_npc.json', encoding='utf-8'))['npcs']
for name, data in d.items():
    raw = bytes.fromhex(data['hex'])
    mid, val, n_str, n_opt, zero = struct.unpack_from('<IHBBB', raw, 0)
    print(f"NPC '{name}': mid={mid}, val={val}")

