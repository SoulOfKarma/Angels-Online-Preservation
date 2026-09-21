import json
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

spawns = []
for e in entries:
    if e['dir'] == 's2c' and e['opcode'] == 8: # 0x0008 NPC_SPAWN
        raw = bytes.fromhex(e['hex'])
        eid, unk, x, y = struct.unpack_from('<IIII', raw, 0)
        name = raw[16:32].split(b'\x00')[0].decode('latin1', 'replace')
        klass = struct.unpack_from('<I', raw, 40)[0]
        ntype = struct.unpack_from('<H', raw, 45)[0] if len(raw) >= 47 else 0
        sprite = struct.unpack_from('<H', raw, 34)[0] if len(raw) >= 36 else 0
        spawns.append((eid, name, x, y, ntype, sprite, klass, raw.hex()))

print(f"Total 0x0008 spawns: {len(spawns)}")
for s in spawns:
    print(f"eid={s[0]:5d} | ntype={s[4]:4d} | sprite={s[5]:5d} | klass={s[6]:3d} | pos=({s[2]:3d},{s[3]:3d}) | name='{s[1]}'")

