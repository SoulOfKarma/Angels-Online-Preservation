"""Ver todos los 0x0013 enviados al jugador en ambas capturas."""
import json, struct

for path in ['logs/proxy/mundo_002738_130434_orden.jsonl', 'logs/proxy/mundo_003328_596403_orden.jsonl']:
    lines = open(path, 'r', encoding='utf-8').readlines()
    kinds = {}
    for l in lines:
        d = json.loads(l)
        if d['dir'] != 's2c' or d['opcode'] != 19:
            continue
        b = bytes.fromhex(d.get('hex', ''))
        # 0x0013 tiene: [LE32 ent][U8 cnt] y luego cnt * [U8 kind, LE32 val]
        if len(b) >= 6:
            ent, cnt = struct.unpack_from('<IB', b, 0)
            p = 5
            for _ in range(cnt):
                if p + 5 <= len(b):
                    k, v = struct.unpack_from('<BI', b, p)
                    kinds.setdefault(k, []).append((ent, v))
                    p += 5
    print(f"=== {path} ===")
    for k in sorted(kinds):
        samples = kinds[k][:3]
        print(f"  kind={k:2d}: count={len(kinds[k])} samples={samples}")

