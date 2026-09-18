"""Muestra los primeros frames de un stream en crudo, para ubicar el handshake."""
import struct, sys, pathlib
HDR, HDR_XOR, FLAG_ENC = 6, 0x1357, 0x01

def frames(data, n):
    off, out = 0, []
    while off + HDR <= len(data) and len(out) < n:
        l = struct.unpack_from('<H', data, off)[0] ^ HDR_XOR
        seq = struct.unpack_from('<H', data, off+2)[0] ^ l
        flags = data[off+4] ^ (l & 0xFF)
        csum = data[off+5]
        padded = ((l + 0xF) >> 4) << 4 if (flags & FLAG_ENC) else l
        if l > 0x4000 or off + HDR + padded > len(data): break
        out.append((off, l, seq, flags, csum, data[off+HDR:off+HDR+padded]))
        off += HDR + padded
    return out

for name in sys.argv[1:]:
    p = pathlib.Path(name)
    print(f"\n===== {p.name} ({p.stat().st_size} bytes) =====")
    for off, l, seq, flags, csum, pl in frames(p.read_bytes(), 4):
        tag = "ENC" if flags & 1 else "PLANO"
        print(f"  off={off:<6} len={l:<5} seq=0x{seq:04X} flags=0x{flags:02x}({tag}) csum=0x{csum:02x}")
        print(f"    {pl[:48].hex(' ')}{' ...' if len(pl)>48 else ''}")
