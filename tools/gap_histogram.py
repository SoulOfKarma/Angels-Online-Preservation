"""Mide los 'huecos' entre frames: son perdida de captura o un elemento sistematico?"""
import struct, sys, pathlib, collections

HDR, HDR_XOR, FLAG_ENC = 6, 0x1357, 0x01
MAX_PAYLOAD = 0x4000

def hdr(d, o):
    l = struct.unpack_from('<H', d, o)[0] ^ HDR_XOR
    seq = struct.unpack_from('<H', d, o+2)[0] ^ l
    fl = d[o+4] ^ (l & 0xFF)
    pad = ((l + 0xF) >> 4) << 4 if (fl & FLAG_ENC) else l
    return l, seq, fl, pad

def valid(d, o):
    if o + HDR > len(d): return None
    l, seq, fl, pad = hdr(d, o)
    if l == 0 or l > MAX_PAYLOAD: return None
    if not (1 <= seq <= 0x7FFE or seq == 0xFFFF): return None
    if fl not in (0x00, 0x01, 0x80, 0x81): return None
    if o + HDR + pad > len(d): return None
    return l, seq, fl, pad

def chain(d, o, n):
    c = 0
    while c < n:
        v = valid(d, o)
        if not v: break
        o += HDR + v[3]; c += 1
    return c

path = pathlib.Path(sys.argv[1])
d = path.read_bytes()
gaps = collections.Counter()
samples = collections.defaultdict(list)
off, frames = 0, 0
while off + HDR <= len(d):
    v = valid(d, off)
    if v:
        off += HDR + v[3]; frames += 1; continue
    found = -1
    for c in range(off+1, min(off+4096, len(d)-HDR)):
        if chain(d, c, 5) >= 5:
            found = c; break
    if found < 0: break
    g = found - off
    gaps[g] += 1
    if len(samples[g]) < 3:
        samples[g].append(d[off:found].hex(' '))
    off = found

print(f"{path.name}: {frames} frames, {sum(gaps.values())} huecos\n")
print("tamano_hueco  veces   contenido de muestra")
print("-" * 78)
for g, n in gaps.most_common(10):
    ex = samples[g][0] if samples[g] else ''
    print(f"{g:>10}  {n:>7}   {ex[:56]}")
