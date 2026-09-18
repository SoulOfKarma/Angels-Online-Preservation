"""
Identifica cuales streams son protocolo Angels Online, sin inspeccionar contenido.

Criterio puramente estructural: se aplica el framing de AO y se mide que
fraccion de bytes queda explicada por frames con checksum valido. El trafico
que no es AO (HTTPS, etc.) no supera el umbral y se descarta sin ser leido.
"""
import struct, sys, pathlib, collections

HDR, HDR_XOR, FLAG_ENC = 6, 0x1357, 0x01


def checksum(p, n):
    v = 0xD31F
    for i in range(0, min(n & ~1, len(p)), 2):
        v ^= struct.unpack_from('<H', p, i)[0]
    v &= 0xFFFF
    s = v & 0xF
    if s: v = ((v << s) | (v >> (16 - s))) & 0xFFFF
    return (v & 0xFF) ^ ((v >> 8) & 0xFF)


def score(data, limit=200000):
    """Devuelve (frames_ok, bytes_explicados, bytes_probados)."""
    off = ok = expl = 0
    d = data[:limit]
    while off + HDR <= len(d):
        if d[off:off+HDR] == b'\x00'*6:
            off += HDR; continue
        l = struct.unpack_from('<H', d, off)[0] ^ HDR_XOR
        seq = struct.unpack_from('<H', d, off+2)[0] ^ l
        fl = (d[off+4] ^ (l & 0xFF)) & 0xFF
        if l == 0 or l > 0x4000 or fl not in (0, 1, 0x80, 0x81) \
           or not (1 <= seq <= 0x7FFE or seq == 0xFFFF):
            off += 1; continue
        pad = ((l + 0xF) >> 4) << 4 if (fl & FLAG_ENC) else l
        if off + HDR + pad > len(d): break
        body = d[off+HDR: off+HDR+pad]
        if fl == 0 and checksum(body, l) == d[off+5]:
            ok += 1; expl += HDR + pad
        elif fl & FLAG_ENC:
            ok += 1; expl += HDR + pad          # cifrado: no verificable sin clave
        off += HDR + pad
    return ok, expl, len(d)


agg = collections.defaultdict(lambda: [0, 0, 0, 0])   # endpoint -> [frames, expl, probados, streams]
for p in pathlib.Path(sys.argv[1]).glob('*.bin'):
    if p.stat().st_size < 4000: continue
    parts = p.stem.split('_')
    ep = '.'.join(parts[:4]) + ':' + parts[4]
    ok, expl, tot = score(p.read_bytes())
    a = agg[ep]
    a[0] += ok; a[1] += expl; a[2] += tot; a[3] += 1

print(f"{'endpoint':<26} {'streams':>8} {'frames':>9} {'% explicado':>12}  veredicto")
print("-" * 76)
for ep, (ok, expl, tot, n) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
    pct = 100 * expl / tot if tot else 0
    if pct < 5: continue
    v = "PROTOCOLO AO" if pct > 85 and ok > 50 else ("parcial" if pct > 40 else "no es AO")
    print(f"{ep:<26} {n:>8} {ok:>9} {pct:>11.1f}%  {v}")
