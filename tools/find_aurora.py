import json
import struct

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

for e in entries:
    if e['dir'] == 's2c' and e['opcode'] == 8:
        raw = bytes.fromhex(e['hex'])
        name = raw[16:32].split(b'\x00')[0].decode('latin1', 'replace')
        if 'Aurora' in name:
            eid, unk, x, y = struct.unpack_from('<IIII', raw, 0)
            ntype = struct.unpack_from('<H', raw, 45)[0] if len(raw) >= 47 else 0
            sprite = struct.unpack_from('<H', raw, 34)[0] if len(raw) >= 36 else 0
            print(f"Aurora: eid={eid} ntype={ntype} sprite={sprite} pos=({x},{y}) hex={raw.hex()}")

