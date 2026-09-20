"""Analizar todos los paquetes 0x000B (opcode 11) en mundo_002738_130434."""
import json, struct

archivo = 'logs/proxy/mundo_002738_130434_orden.jsonl'
lines = open(archivo, 'r', encoding='utf-8').readlines()

for l in lines:
    d = json.loads(l)
    if d['dir'] != 's2c' or d['opcode'] != 11:
        continue
    b = bytes.fromhex(d.get('hex', ''))
    if len(b) >= 11:
        ent, kind, val, pad = struct.unpack_from('<IBIH', b, 0)
        print(f"t={d['t']:.2f}s 0x000B: ent={ent} kind={kind} val={val} (0x{val:X}) pad={pad} raw={b.hex()}")

