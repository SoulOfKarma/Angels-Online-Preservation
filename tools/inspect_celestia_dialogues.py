import json
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

# Find all 0x0007 (dialogue request), 0x000b (dialogue reply / choices), 0x0012 (open dialogue)
for e in entries:
    op = e['opcode']
    if op in (0x0005, 0x0007, 0x000b, 0x0012):
        d = e['dir']
        t = e['t']
        l = e['len']
        h = e['hex']
        print(f"t={t:7.2f} | {d:3s} | op=0x{op:04x} | len={l:3d} | hex={h}")

