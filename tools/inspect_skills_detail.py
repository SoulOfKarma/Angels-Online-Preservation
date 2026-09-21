import json
import sqlite3

con = sqlite3.connect('corpus/content.db')

def inspect_lines(path, start, end):
    print(f"\n=================== {path} [{start}..{end}] ===================")
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i < start: continue
            if i > end: break
            try:
                d = json.loads(line)
            except Exception:
                continue
            dir_ = d.get('dir')
            op = hex(d.get('opcode', 0))
            ln = d.get('len')
            h = d.get('hex', '')
            extra = ""
            if op == '0x6' and dir_ == 'c2s':
                raw = bytes.fromhex(h)
                sk = int.from_bytes(raw[:2], 'little')
                tgt = int.from_bytes(raw[2:6], 'little')
                row = con.execute('select name from magic where id=?', (str(sk),)).fetchone()
                extra = f"SKILL CAST: {sk} ({row[0] if row else '?'}) target={hex(tgt)}"
            elif op == '0x11':
                raw = bytes.fromhex(h)
                ef = raw[0]
                phase = raw[1]
                atk = int.from_bytes(raw[2:6], 'little')
                tgt = int.from_bytes(raw[6:10], 'little')
                val = int.from_bytes(raw[18:20], 'little')
                tp = raw[20]
                sk = int.from_bytes(raw[21:23], 'little')
                extra = f"EFFECT 0x11: ef={ef} phase=0x{phase:02x} atk={hex(atk)} tgt={hex(tgt)} val={val} type={tp} skill={sk}"
            elif op == '0x13':
                raw = bytes.fromhex(h)
                ent = int.from_bytes(raw[:4], 'little')
                k = raw[5] if len(raw) > 5 else None
                v = int.from_bytes(raw[6:10], 'little') if len(raw) >= 10 else None
                extra = f"ATTR 0x13: ent={hex(ent)} kind={k} val={v}"
            elif op == '0x1d':
                raw = bytes.fromhex(h)
                ent = int.from_bytes(raw[:4], 'little')
                k = raw[5] if len(raw) > 5 else None
                sk = int.from_bytes(raw[6:10], 'little') if len(raw) >= 10 else None
                dur = int.from_bytes(raw[10:14], 'little') if len(raw) >= 14 else None
                extra = f"BUFF/SKILL 0x1D: ent={hex(ent)} kind={k} id={sk} dur/val={dur}"
            elif op == '0xa':
                raw = bytes.fromhex(h)
                a = int.from_bytes(raw[:4], 'little')
                t = int.from_bytes(raw[4:8], 'little')
                v = int.from_bytes(raw[8:12], 'little')
                extra = f"ACTION 0x0A: a={hex(a)} t={hex(t)} v={v}"
            elif op == '0x149':
                extra = f"COOLDOWN 0x149: {h}"
            print(f"[{i}] {dir_} {op} len={ln} | {extra or h[:40]}")

inspect_lines('logs/proxy/mundo_002738_130434_orden.jsonl', 748, 775)
inspect_lines('logs/proxy/mundo_003328_596403_orden.jsonl', 162, 180)

