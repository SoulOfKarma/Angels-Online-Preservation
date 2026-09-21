import json
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

for e in entries:
    if e['dir'] == 's2c' and e['opcode'] == 0x1c:
        raw = bytes.fromhex(e['hex'])
        print(f"t={e['t']:.2f} S2C 0x001c len={len(raw)}")
        # Let's inspect the non-zero entries in the 1008 bytes
        # 1008 bytes / 36 skills = 28 bytes per skill?
        # or 1008 / 16?
        print("First 128 bytes hex:", raw[:128].hex())
        print("Last 128 bytes hex:", raw[-128:].hex())
        break

