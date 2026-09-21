import json
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

for e in entries:
    op = e['opcode']
    if op in (0x0007, 0x000b, 0x0012) and (e['dir'] == 'c2s' or e['len'] < 100):
        d = e['dir']
        t = e['t']
        l = e['len']
        h = e['hex']
        # If 0x0012 or 0x000B: decode dialogue id
        extra = ""
        if op == 0x0012 and d == 's2c' and l >= 4:
            diag_id = struct.unpack_from('<I', bytes.fromhex(h), 0)[0]
            extra = f"diag_id={diag_id}"
        elif op == 0x000B and d == 'c2s' and l >= 1:
            choice = bytes.fromhex(h)[0]
            extra = f"choice={choice}"
        print(f"t={t:7.2f} | {d:3s} | op=0x{op:04x} | len={l:3d} | {extra:16s} | hex={h}")

