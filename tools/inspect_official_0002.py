"""Inspeccionar el paquete 0x0002 de la captura oficial mundo_003328_596403."""
import json, struct

lines = open('logs/proxy/mundo_003328_596403_orden.jsonl', 'r', encoding='utf-8').readlines()

for l in lines:
    d = json.loads(l)
    if d['dir'] == 's2c' and d['opcode'] == 2 and len(d.get('hex', '')) > 2000:
        b = bytes.fromhex(d['hex'])
        print(f"Encontrado 0x0002 de len {len(b)}")
        # Nombre (+16..+50)
        name = b[16:50].rstrip(b'\x00').decode('ascii', errors='ignore')
        print(f"Nombre: {name}")
        # unk_50 (+50..+102)
        u50 = b[50:102]
        print(f"unk_50 (52 bytes): {u50.hex()}")
        # Imprimir como DWORDs
        dwords = struct.unpack('<13I', u50)
        for idx, dw in enumerate(dwords):
            print(f"  DW[{idx:2d}] (offset +{idx*4:2d} dentro de u50, abs +{50+idx*4:3d}): {dw:10d} (0x{dw:08X})")
        # stats (+102..+207)
        stats = b[102:207]
        hp, hp_max, mp, mp_max = struct.unpack_from('<IIII', stats, 0)
        print(f"Stats iniciales: HP={hp}/{hp_max} MP={mp}/{mp_max}")
        break

