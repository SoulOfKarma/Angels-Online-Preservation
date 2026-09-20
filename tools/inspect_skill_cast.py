import json

with open('logs/proxy/mundo_222257_472928_orden.jsonl', 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        d = json.loads(line)
        t = d.get('t', 0)
        if 556.30 <= t <= 558.10:
            print(f"{t:.3f} {d.get('dir')} op=0x{d.get('opcode'):04x} len={d.get('len')} hex={d.get('hex')}")

