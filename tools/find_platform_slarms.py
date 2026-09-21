import json
import struct

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

slarms_platform = []
for e in entries:
    if e['dir'] == 's2c' and e['opcode'] == 8:
        raw = bytes.fromhex(e['hex'])
        name = raw[16:32].split(b'\x00')[0].decode('latin1', 'replace')
        if name == 'Little Slarm':
            eid, unk, x, y = struct.unpack_from('<IIII', raw, 0)
            if 190 <= x <= 240 and 15 <= y <= 60:
                slarms_platform.append((eid, x, y, raw.hex()))

print(f"Total Little Slarms on player's platform (190<=x<=240, 15<=y<=60): {len(slarms_platform)}")
for s in slarms_platform:
    print(f"eid={s[0]} pos=({s[1]},{s[2]})")

