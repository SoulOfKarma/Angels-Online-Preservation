import json, struct

lines = open('logs/proxy/mundo_222257_472928_orden.jsonl','r',encoding='utf-8').readlines()
# Buscar sub-mensajes 001b dentro de frames grandes
for l in lines:
    d = json.loads(l)
    h = d.get('hex','')
    b = bytes.fromhex(h)
    for i in range(0, len(b)-1):
        if b[i]==0x1b and b[i+1]==0x00:
            ctx = b[max(0,i-4):i+20].hex()
            print(f"t={d['t']:.3f} op={d['opcode']} off={i} context={ctx}")
            break

