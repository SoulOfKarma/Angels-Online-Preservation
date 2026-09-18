"""Que opcode precede y sigue a cada separador de 6 ceros?"""
import struct, sys, pathlib, collections

HDR, HDR_XOR, FLAG_ENC = 6, 0x1357, 0x01
SEP = b'\x00' * 6

def hdr(d, o):
    l = struct.unpack_from('<H', d, o)[0] ^ HDR_XOR
    seq = struct.unpack_from('<H', d, o+2)[0] ^ l
    fl = d[o+4] ^ (l & 0xFF)
    pad = ((l + 0xF) >> 4) << 4 if (fl & FLAG_ENC) else l
    return l, seq, fl, pad

def valid(d, o):
    if o + HDR > len(d): return None
    l, seq, fl, pad = hdr(d, o)
    if l == 0 or l > 0x4000: return None
    if not (1 <= seq <= 0x7FFE or seq == 0xFFFF): return None
    if fl not in (0x00, 0x01, 0x80, 0x81): return None
    if o + HDR + pad > len(d): return None
    return l, seq, fl, pad

def opcodes(payload):
    """Extrae opcodes de los sub-mensajes [LE16 len][LE16 opcode][...]"""
    out, p = [], 0
    while p + 4 <= len(payload):
        sl = struct.unpack_from('<H', payload, p)[0]
        if sl < 2 or p + 2 + sl > len(payload): break
        out.append(struct.unpack_from('<H', payload, p + 2)[0])
        p += 2 + sl
    return out

d = pathlib.Path(sys.argv[1]).read_bytes()
before, after, seqs = collections.Counter(), collections.Counter(), collections.Counter()
nsep = 0
off = 0
prev_ops, prev_seq = None, None
while off + HDR <= len(d):
    if d[off:off+HDR] == SEP and valid(d, off + HDR):
        nsep += 1
        if prev_ops:
            before[f"0x{prev_ops[-1]:04X}"] += 1
            seqs[prev_seq] += 1
        l, sq, fl, pad = valid(d, off + HDR)
        ops = opcodes(d[off+HDR+HDR: off+HDR+HDR+l]) if fl == 0 else []
        if ops: after[f"0x{ops[0]:04X}"] += 1
        off += HDR
        continue
    v = valid(d, off)
    if not v:
        off += 1; continue
    l, sq, fl, pad = v
    if fl == 0:
        prev_ops = opcodes(d[off+HDR: off+HDR+l]) or prev_ops
    prev_seq = sq
    off += HDR + pad

print(f"separadores de 6 ceros encontrados: {nsep}\n")
print("ULTIMO opcode ANTES del separador:")
for k, n in before.most_common(8): print(f"   {k}  x{n}")
print("\nPRIMER opcode DESPUES del separador:")
for k, n in after.most_common(8): print(f"   {k}  x{n}")
print("\nSEQ del frame anterior al separador:")
for k, n in seqs.most_common(8): print(f"   seq=0x{k:04X}  x{n}")
