"""Buscar paquetes 0x000A (evento) en sub-mensajes del opcode 26."""
import json, struct

lines = open('logs/proxy/mundo_222257_472928_orden.jsonl','r',encoding='utf-8').readlines()

count = 0
for idx, l in enumerate(lines):
    d = json.loads(l)
    if d['dir'] != 's2c' or d['opcode'] != 26:
        continue
    h = d.get('hex','')
    b = bytes.fromhex(h)
    # Sub-mensajes dentro del frame de opcode 26
    # Buscar patron 0a00 seguido de datos
    for p in range(0, len(b)-14):
        if b[p] == 0x0a and b[p+1] == 0x00:
            atacante = struct.unpack_from('<I', b, p+2)[0]
            objetivo = struct.unpack_from('<I', b, p+6)[0]
            valor = struct.unpack_from('<I', b, p+10)[0]
            if atacante < 50000 and objetivo < 50000:
                ctx = b[p:p+14].hex()
                print(f"0x000A t={d['t']:.3f} atk={atacante} obj={objetivo} val={valor} ({hex(valor)}) hex={ctx}")
                count += 1
                if count > 30:
                    break
    if count > 30:
        break

# Tambien buscar fuera del opcode 26 - en frame propio
print("\n--- 0x000A como opcode propio ---")
count2 = 0
for l in lines:
    d = json.loads(l)
    if d['dir'] != 's2c' or d['opcode'] != 10:
        continue
    h = d.get('hex','')
    b = bytes.fromhex(h)
    if len(b) >= 12:
        atacante = struct.unpack_from('<I', b, 0)[0]
        objetivo = struct.unpack_from('<I', b, 4)[0]
        valor = struct.unpack_from('<I', b, 8)[0]
        print(f"0x000A t={d['t']:.3f} atk={atacante} obj={objetivo} val={valor} ({hex(valor)})")
        count2 += 1
        if count2 > 20:
            break

