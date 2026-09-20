"""Analizar todos los tipos de 0x0013 (atributos) y 0x001D enviados al jugador."""
import json, struct

archivo = 'logs/proxy/mundo_002738_130434_orden.jsonl'
lines = open(archivo, 'r', encoding='utf-8').readlines()

kinds_13 = set()
kinds_1d = set()

for l in lines:
    d = json.loads(l)
    if d['dir'] != 's2c':
        continue
    op = d['opcode']
    b = bytes.fromhex(d.get('hex', ''))
    if op == 19 and len(b) >= 10: # 0x0013
        ent, cnt, kind, val = struct.unpack_from('<IBBI', b, 0)
        if ent == 336: # jugador
            kinds_13.add((kind, val))
    elif op == 29 and len(b) >= 14: # 0x001D
        ent, cnt, kind, sid, val = struct.unpack_from('<IBBII', b, 0)
        if ent == 336:
            kinds_1d.add((kind, sid, val))

print("--- Atributos 0x0013 del jugador ---")
for k, v in sorted(kinds_13):
    print(f"  kind={k:2d}: ejemplo_valor={v} (0x{v:X})")

print("\n--- Sub-mensajes 0x001D del jugador ---")
for k, s, v in sorted(kinds_1d)[:25]:
    print(f"  kind={k:2d} ({hex(k)}): skill_id={s:4d} val={v}")

