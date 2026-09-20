import json

with open('logs/proxy/mundo_222257_472928_orden.jsonl', 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        d = json.loads(line)
        if d.get('opcode') == 11 and d.get('dir') == 's2c':
            print(f"{d.get('t'):.2f} S->C 0x000B len={d.get('len')} hex={d.get('hex')}")

