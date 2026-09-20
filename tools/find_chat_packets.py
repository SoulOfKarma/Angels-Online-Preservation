"""Buscar los avisos de chat en ambas capturas mundo."""
import json, struct

for path in ['logs/proxy/mundo_003328_596403_orden.jsonl', 'logs/proxy/mundo_002738_130434_orden.jsonl']:
    lines = open(path, 'r', encoding='utf-8').readlines()
    print(f"=== {path} ({len(lines)} lineas) ===")
    for l in lines:
        d = json.loads(l)
        if d['dir'] != 's2c':
            continue
        b = bytes.fromhex(d.get('hex', ''))
        # Revisar si hay strings imprimibles de mas de 4 caracteres
        for s in [b'Exp', b'Gold', b'obtained', b'Level Up', b'has obtained']:
            if s in b:
                print(f"t={d['t']:.2f} op=0x{d['opcode']:04X} ({d['opcode']}) len={len(b)}")
                # Imprimir el paquete completo en hex y ascii
                print(f"   ASCII: {bytes([c if 32 <= c <= 126 else 46 for c in b]).decode('ascii', errors='ignore')}")
                print(f"   HEX:   {b[:80].hex()}")
                break

