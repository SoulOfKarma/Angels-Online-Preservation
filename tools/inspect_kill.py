import json

with open('logs/proxy/mundo_222257_472928_orden.jsonl', 'r', encoding='utf-8', errors='ignore') as f:
    record = 0
    for line in f:
        d = json.loads(line)
        h = d.get('hex', '')
        op = d.get('opcode')
        # look for monster death (0x0013 with 010000000000: count 1, kind 0, hp 0)
        if op == 19 and h.endswith('010000000000'):
            print(f"=== KILL AT {d.get('t'):.2f} entity={h[:8]} ===")
            record = 20
        if record > 0:
            print(f"  {d.get('t'):.2f} {d.get('dir')} op=0x{op:04x} len={d.get('len')} hex={h}")
            record -= 1

