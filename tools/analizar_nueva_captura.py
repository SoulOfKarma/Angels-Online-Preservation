"""Analizar los paquetes del servidor oficial en la nueva captura mundo_003328_596403."""
import json, struct

archivo = 'logs/proxy/mundo_003328_596403_orden.jsonl'
lines = open(archivo, 'r', encoding='utf-8').readlines()

print(f"Total lineas: {len(lines)}")

# 1. Buscar mensajes de texto / chat (opcode 0x000D o similar)
# En AO el aviso de texto en pantalla/chat suele ser 0x000D o 0x0003/0x0008
print("\n--- TEXTOS Y AVISOS S->C ---")
for l in lines:
    d = json.loads(l)
    if d['dir'] != 's2c':
        continue
    h = d.get('hex', '')
    b = bytes.fromhex(h)
    # Buscar strings legibles como Exp, Gold, obtained, etc.
    for term in [b'Exp', b'Gold', b'obtained', b'Level Up', b'Sword', b'Finesse', b'Grapple']:
        if term in b:
            # Encontrar el string completo
            pos = b.find(term)
            start = max(0, pos - 10)
            end = min(len(b), pos + 40)
            print(f"t={d['t']:.2f}s op={d['opcode']} len={len(b)} texto={b[start:end]}")
            print(f"   hex={b[:60].hex()}")
            break

# 2. Buscar paquetes tras una muerte o ataque (0x000B, 0x000A, 0x0007, 0x0013)
print("\n--- PAQUETES DE COMBATE Y EXPERIENCIA ---")
for l in lines:
    d = json.loads(l)
    if d['dir'] != 's2c':
        continue
    # Submensajes de opcode 26 o paquetes propios
    op = d['opcode']
    if op in (7, 10, 11, 17, 19, 29): # 0x0007, 0x000A, 0x000B, 0x0011, 0x0013, 0x001D
        b = bytes.fromhex(d.get('hex', ''))
        print(f"t={d['t']:.2f}s op=0x{op:04X} len={len(b)} hex={b.hex()[:50]}")

