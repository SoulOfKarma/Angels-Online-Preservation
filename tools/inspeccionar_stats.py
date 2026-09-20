import json
import struct

p = json.load(open('server/plantillas/inventario.json'))
raw = bytes.fromhex(p['stats_sin_ropa'])
print("stats_sin_ropa len:", len(raw))
vals = struct.unpack('<26I', raw[:104])
for idx, v in enumerate(vals):
    print(f"[{idx*4:3d}] U32: {v} (0x{v:08X})")

