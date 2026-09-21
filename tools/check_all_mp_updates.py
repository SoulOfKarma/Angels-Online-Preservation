import json

with open('logs/proxy/mundo_181238_268869_orden.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        try:
            d = json.loads(line)
        except Exception:
            continue
        if d.get('dir') == 's2c' and d.get('opcode') == 19:
            raw = bytes.fromhex(d.get('hex'))
            if len(raw) >= 10:
                ent = int.from_bytes(raw[:4], 'little')
                k = raw[5]
                v = int.from_bytes(raw[6:10], 'little')
                if k == 2:
                    print(f"Line {i} (t={d.get('t'):.2f}): MP update: {v}")

