import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('logs/proxy/mundo_102010_448895_orden.jsonl', 'r', encoding='utf-8') as f:
    entries = [json.loads(line) for line in f if line.strip()]

print(f"Total entries: {len(entries)}")
if entries:
    print(f"Time range: t={entries[0].get('t', 0):.2f} to t={entries[-1].get('t', 0):.2f}")

# Find unique opcodes sent by client (c2s) and server (s2c)
c2s_ops = sorted(set(e['opcode'] for e in entries if e['dir'] == 'c2s'))
s2c_ops = sorted(set(e['opcode'] for e in entries if e['dir'] == 's2c'))

print(f"C2S opcodes: {[f'0x{op:04x}' for op in c2s_ops]}")
print(f"S2C opcodes: {[f'0x{op:04x}' for op in s2c_ops]}")

