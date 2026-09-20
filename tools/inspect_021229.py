"""Analizar a fondo la nueva captura oficial mundo_021229_041795."""
import json, struct

path = 'logs/proxy/mundo_021229_041795_orden.jsonl'
lines = open(path, 'r', encoding='utf-8').readlines()
print(f"Total lineas: {len(lines)}")

# 1. Analizar el 0x0002 oficial
for l in lines:
    d = json.loads(l)
    if d['dir'] == 's2c' and d['opcode'] == 2 and len(d.get('hex', '')) > 2000:
        b = bytes.fromhex(d['hex'])
        print(f"\n--- PAQUETE 0x0002 OFICIAL (len {len(b)}) ---")
        nom = b[16:50].rstrip(b'\x00').decode('ascii', errors='ignore')
        print(f"Nombre: {nom}")
        u50 = b[50:102]
        print(f"u50 (52 bytes): {u50.hex()}")
        for i in range(len(u50)):
            if u50[i] != 0:
                print(f"  u50[{i:2d}] = {u50[i]:3d} (0x{u50[i]:02X})")
        break

# 2. Buscar tiendas abiertas (0x0034)
print("\n--- TIENDAS ABIERTAS (0x0034) ---")
for l in lines:
    d = json.loads(l)
    if d['dir'] == 's2c' and d['opcode'] == 0x0034:
        b = bytes.fromhex(d.get('hex', ''))
        shop_id = struct.unpack_from('<H', b, 0)[0] if len(b) >= 2 else -1
        print(f"t={d['t']:.2f}s Shop ID abierto: {shop_id} (hex={b.hex()})")

# 3. Buscar mensajes de Pet Revival o Pet Expert
print("\n--- DIALOGOS Y PET REVIVAL ---")
for l in lines:
    d = json.loads(l)
    if d['opcode'] in (0x0012, 0x0005, 0x000B) and d['dir'] == 's2c':
        b = bytes.fromhex(d.get('hex', ''))
        # buscar si es de pet expert
        if len(b) > 4:
            mid = struct.unpack_from('<I', b, 0)[0]
            if 6100 <= mid <= 6130:
                print(f"t={d['t']:.2f}s Dialogo Pet: mid={mid} hex={b.hex()[:40]}")
    elif d['opcode'] == 0x004F or 'revival' in str(d):
        print(f"t={d['t']:.2f}s {d['dir']} op=0x{d['opcode']:04X} hex={d.get('hex')}")

