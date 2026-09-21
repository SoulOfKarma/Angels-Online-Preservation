import json
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

for e in entries:
    if e['dir'] == 's2c' and e['opcode'] == 0x20:
        raw = bytes.fromhex(e['hex'])
        target_eid = struct.unpack_from('<I', raw, 0)[0]
        effect_id = struct.unpack_from('<H', raw, 4)[0]
        source_eid = struct.unpack_from('<I', raw, 6)[0]
        print(f"t={e['t']:7.2f} S2C 0x0020 effect_id={effect_id:3d} target={target_eid} source={source_eid} hex={e['hex']}")

