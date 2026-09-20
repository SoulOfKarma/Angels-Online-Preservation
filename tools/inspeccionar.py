import struct
import json

d = json.load(open('server/plantillas/dialogos_npc.json'))['npcs']
for name in ['Shopkeeper', 'Cupid', 'Director Wolay']:
    raw = bytes.fromhex(d[name]['hex'])
    mid, val, n_str, n_opt, zero = struct.unpack_from('<IHBBB', raw, 0)
    opts = [struct.unpack_from('<I', raw, 9 + 4 * k)[0] for k in range(n_opt)]
    print(name, f"mid={mid}, val={val}, n_str={n_str}, n_opt={n_opt}, opts={opts}")

def armar_hex(mid, val, opts=[]):
    hdr = struct.pack('<IHBBB', mid, val, 0, len(opts), 0)
    body = b''.join(struct.pack('<I', o) for o in opts)
    return (hdr + body).hex()

print("Aurora Totem hex:", armar_hex(10201, 4, [10205, 10207, 10208, 10206]))

