"""Ver exactamente la secuencia de combate y drop en t=290.0 a 292.0 de mundo_002738_130434."""
import json, struct

import glob

for p in glob.glob('logs/proxy/mundo_*_orden.jsonl'):
    print(f"=== {p} ===")
    lines = open(p, 'r', encoding='utf-8', errors='ignore').readlines()
    for idx, l in enumerate(lines):
        try:
            d = json.loads(l.strip())
        except Exception:
            continue
        if d.get('opcode') == 6 and d.get('dir') == 'c2s':

            t = d['t']
            print(f"C2S op=6 at t={t:.2f} hex={d.get('hex')}")
            # print next 8 packets
            for j in range(1, 10):
                if idx + j < len(lines):
                    d2 = json.loads(lines[idx + j])
                    print(f"   +{j} {d2.get('dir')} op=0x{d2.get('opcode'):04x} len={d2.get('len')} hex={d2.get('hex')[:60]}")
            break


