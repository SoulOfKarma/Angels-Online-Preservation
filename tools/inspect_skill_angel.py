import json

with open('logs/proxy/mundo_222257_472928_orden.jsonl', 'r', encoding='utf-8', errors='ignore') as f:
    record = 0
    for line in f:
        d = json.loads(line)
        h = d.get('hex', '')
        if '9f13000004' in h:
            print("Found Skill Angel dialogue at t=", d.get('t'))
            record = 15
        if record > 0:
            print(f"{d.get('t'):.2f} {d.get('dir')} op=0x{d.get('opcode'):04x} len={d.get('len')} hex={h}")
            record -= 1

