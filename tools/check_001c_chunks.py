import json
import struct

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

for e in entries:
    if e['dir'] == 's2c' and e['opcode'] == 0x1c:
        raw = bytes.fromhex(e['hex'])
        # Check chunk sizes dividing 1008:
        # 1008 = 72 * 14 = 63 * 16 = 56 * 18 = 42 * 24 = 36 * 28 = 24 * 42
        for chunk_sz in [16, 20, 24, 28, 32]:
            if len(raw) % chunk_sz == 0:
                n = len(raw) // chunk_sz
                print(f"Testing chunk_sz={chunk_sz}, count={n}")
                for i in range(n):
                    chunk = raw[i*chunk_sz : (i+1)*chunk_sz]
                    if any(b != 0 for b in chunk):
                        print(f"  [{i}]: {chunk.hex()}")
        break

