import json
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

print(f"Total entries: {len(entries)}")

# Find all 0x0006 (skill request) or 0x0011 (spell effect) or 0x000a (entity state/anim) or 0x001d (attributes/exp)
interesting_ops = {0x0006, 0x0007, 0x000a, 0x000b, 0x000d, 0x0011, 0x001d, 0x0042, 0x005f, 0x0149}

combat_events = []
for e in entries:
    if e['opcode'] in interesting_ops:
        combat_events.append(e)

print(f"Total combat/skill events: {len(combat_events)}")
# Group by time clusters or print first 40
for e in combat_events[:80]:
    t = e['t']
    d = e['dir']
    op = e['opcode']
    l = e['len']
    h = e['hex']
    print(f"t={t:7.2f} | {d:3s} | op=0x{op:04x} ({op:3d}) | len={l:3d} | hex={h}")

