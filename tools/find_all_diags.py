import json
import struct

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

for e in entries:
    if e['dir'] == 's2c' and e['opcode'] == 0x0012:
        raw = bytes.fromhex(e['hex'])
        diag_id = struct.unpack_from('<I', raw, 0)[0] if len(raw) >= 4 else 0
        print(f"t={e['t']:.2f} S2C 0x0012 diag_id={diag_id} hex={e['hex']}")

