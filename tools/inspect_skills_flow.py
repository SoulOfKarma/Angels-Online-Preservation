import json
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

# Find all C2S 0x0006
for idx, e in enumerate(entries):
    if e['dir'] == 'c2s' and e['opcode'] == 6:
        raw = bytes.fromhex(e['hex'])
        skill_id = struct.unpack_from('<H', raw, 0)[0]
        target_id = struct.unpack_from('<I', raw, 2)[0]
        print(f"\nt={e['t']:.2f} C2S 0x0006 skill_id={skill_id} target_id={target_id} hex={e['hex']}")
        # Print subsequent S2C packets within 1.5 seconds
        t_start = e['t']
        for j in range(idx + 1, min(idx + 35, len(entries))):
            ej = entries[j]
            if ej['t'] - t_start > 1.5:
                break
            if ej['dir'] == 's2c':
                print(f"   t={ej['t']:.2f} S2C op=0x{ej['opcode']:04x} len={ej['len']} hex={ej['hex']}")

