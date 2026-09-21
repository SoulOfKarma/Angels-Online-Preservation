import json
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

pkts_1c = [e for e in entries if e['dir'] == 's2c' and e['opcode'] == 0x1c]
print(f"Total 0x001c packets: {len(pkts_1c)}")

for idx, p in enumerate(pkts_1c):
    raw = bytes.fromhex(p['hex'])
    t = p['t']
    print(f"\n--- Packet {idx} at t={t:.2f} ---")
    for i in range(72):
        chunk = raw[i*14 : (i+1)*14]
        if chunk[0] in (9, 12, 13, 15, 16, 33):
            print(f"  i={i:2d}: hex={chunk.hex()} -> id={chunk[0]} b1={chunk[1]} b2={chunk[2]} b3={chunk[3]} b8..11={chunk[8:12].hex()} b12={chunk[12]} b13={chunk[13]}")

