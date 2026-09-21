import glob
import json
import sqlite3

con = sqlite3.connect('corpus/content.db')

for path in sorted(glob.glob('logs/proxy/mundo_*_orden.jsonl')):
    found = []
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            d = json.loads(line)
            if d.get('dir') == 'c2s' and d.get('opcode') == 6:
                raw = bytes.fromhex(d.get('hex'))
                skill_id = int.from_bytes(raw[0:2], 'little')
                target = int.from_bytes(raw[2:6], 'little')
                row = con.execute('select id, name from magic where id=?', (str(skill_id),)).fetchone()
                name = row[1] if row else '?'
                found.append((i, skill_id, name, hex(target)))
    if found:
        print(f"=== {path} ===")
        for i, skill_id, name, target in found:
            print(f"  Line {i}: skill={skill_id} ({name}) target={target}")

