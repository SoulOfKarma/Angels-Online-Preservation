import json
from collections import Counter

op_counts = Counter()
c2s_records = []

with open('logs/proxy/mundo_181238_268869_orden.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get('dir') == 'c2s':
            op = d.get('opcode')
            op_counts[op] += 1
            c2s_records.append((i, op, d.get('len'), d.get('hex')))

print("Client opcodes in mundo_181238_268869_orden.jsonl:")
for op, count in op_counts.most_common():
    print(f"  Opcode {hex(op)} ({op}): {count} times")

print("\nAll c2s packets that are NOT movement (0x4) or ping/heartbeat (0xf):")
for i, op, ln, h in c2s_records:
    if op not in (4, 15):
        print(f"  Line {i}: op={hex(op)} len={ln} hex={h}")

