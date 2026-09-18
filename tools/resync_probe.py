"""
Distingue 'framing equivocado' de 'captura con huecos'.

Si al romperse un stream podemos avanzar N bytes y reencontrar una cadena larga
de frames validos, entonces el framing es correcto y lo que falta son segmentos
TCP que el sniffer no capturo. Si nunca resincroniza, el framing esta mal.
"""
import struct, sys, pathlib

HDR, HDR_XOR, FLAG_ENC = 6, 0x1357, 0x01
MAX_PAYLOAD = 0x4000
CONFIRM = 6          # frames validos seguidos para aceptar un resync


def hdr(data, off):
    l = struct.unpack_from('<H', data, off)[0] ^ HDR_XOR
    seq = struct.unpack_from('<H', data, off + 2)[0] ^ l
    flags = data[off + 4] ^ (l & 0xFF)
    padded = ((l + 0xF) >> 4) << 4 if (flags & FLAG_ENC) else l
    return l, seq, flags, padded


def chain_ok(data, off, n):
    """Cuantos frames validos seguidos hay desde off (hasta n)."""
    c = 0
    while c < n and off + HDR <= len(data):
        l, seq, flags, padded = hdr(data, off)
        if l == 0 or l > MAX_PAYLOAD: break
        if not (1 <= seq <= 0x7FFE or seq == 0xFFFF): break
        if flags not in (0x00, 0x01, 0x80, 0x81): break
        if off + HDR + padded > len(data): break
        off += HDR + padded
        c += 1
    return c


def analyze(path):
    data = path.read_bytes()
    off, frames, gaps, gapbytes = 0, 0, 0, 0
    while off + HDR <= len(data):
        n = chain_ok(data, off, 1)
        if n == 1:
            l, seq, flags, padded = hdr(data, off)
            off += HDR + padded
            frames += 1
            continue
        # roto: buscar resync
        found = -1
        for cand in range(off + 1, min(off + 200000, len(data) - HDR)):
            if chain_ok(data, cand, CONFIRM) >= CONFIRM:
                found = cand
                break
        if found < 0:
            return frames, gaps, gapbytes, len(data) - off, len(data)
        gaps += 1
        gapbytes += found - off
        off = found
    return frames, gaps, gapbytes, 0, len(data)


targets = sorted(pathlib.Path(sys.argv[1]).glob('*s2c.bin'), key=lambda p: -p.stat().st_size)[:8]
print(f"{'archivo':<40} {'bytes':>9} {'frames':>7} {'huecos':>7} {'bytes perdidos':>15} {'cola':>8}")
print("-" * 95)
for p in targets:
    if p.stat().st_size < 100: continue
    fr, g, gb, tail, total = analyze(p)
    pct = 100 * (total - gb - tail) / total
    print(f"{p.name:<40} {total:>9} {fr:>7} {g:>7} {gb:>15} {tail:>8}   -> {pct:.1f}% explicado")
