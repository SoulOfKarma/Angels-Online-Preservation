import json
import glob

print("Searching for sitting packets...")
# Check all client packets in recent sessions
for path in sorted(glob.glob('logs/proxy/mundo_*_orden.jsonl'))[-5:]:
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('dir') == 'c2s':
                op = d.get('opcode')
                # Check for uncommon opcodes or sitting opcodes (0x0007, 0x000A, 0x0016, 0x002B, 0x0032, etc.)
                if op in (7, 10, 11, 14, 22, 43, 50):
                    print(f"{path} line {i}: op={hex(op)} len={d.get('len')} hex={d.get('hex')}")

