"""
Framing a nivel de paquete.

Derivado de sub_81E900 (lector) y sub_81EF80 (emisor) del cliente, y validado
contra 163.314 frames reales con 100% de checksums correctos.

    b0-1 : payload_length XOR 0x1357            (LE16)
    b2-3 : sequence       XOR payload_length    (LE16)
    b4   : flags          XOR (payload_length & 0xFF)
             bit 0 = cifrado   bit 7 = comprimido
    b5   : checksum del payload EN CLARO
    wire = 6 + (cifrado ? redondeo_a_16(payload_length) : payload_length)

El payload es una concatenacion de sub-mensajes: [LE16 sub_len][LE16 opcode][...]
donde sub_len incluye el opcode.
"""
import struct

HDR = 6
HDR_XOR = 0x1357
FLAG_ENC = 0x01
FLAG_CMP = 0x80
SEQ_HELLO = 0xFFFF
SEQ_MAX = 0x7FFE


def checksum(payload: bytes, length: int) -> int:
    """sub_81DBF0. Se calcula SIEMPRE sobre el payload en claro."""
    v = 0xD31F
    for i in range(0, min(length & ~1, len(payload)), 2):
        v ^= struct.unpack_from('<H', payload, i)[0]
    v &= 0xFFFF
    s = v & 0xF
    if s:
        v = ((v << s) | (v >> (16 - s))) & 0xFFFF
    return (v & 0xFF) ^ ((v >> 8) & 0xFF)


def decode_header(raw: bytes, off: int = 0) -> dict:
    l = struct.unpack_from('<H', raw, off)[0] ^ HDR_XOR
    seq = struct.unpack_from('<H', raw, off + 2)[0] ^ l
    flags = (raw[off + 4] ^ (l & 0xFF)) & 0xFF
    padded = ((l + 0xF) >> 4) << 4 if (flags & FLAG_ENC) else l
    return {'length': l, 'seq': seq, 'flags': flags, 'checksum': raw[off + 5],
            'padded': padded, 'wire': HDR + padded,
            'encrypted': bool(flags & FLAG_ENC), 'compressed': bool(flags & FLAG_CMP)}


def encode_header(length: int, seq: int, flags: int, csum: int) -> bytes:
    h = bytearray(HDR)
    struct.pack_into('<H', h, 0, (length ^ HDR_XOR) & 0xFFFF)
    struct.pack_into('<H', h, 2, (seq ^ length) & 0xFFFF)
    h[4] = (flags ^ (length & 0xFF)) & 0xFF
    h[5] = csum & 0xFF
    return bytes(h)


def build_frame(payload: bytes, seq: int, crypto=None) -> bytes:
    """Arma un frame completo. Si crypto es None, va en claro (flags=0).

    El checksum se calcula ANTES de cifrar, sobre el texto en claro -- el
    cliente lo verifica despues de descifrar (sub_81E900).
    """
    n = len(payload)
    ck = checksum(payload, n)
    if crypto is None:
        return encode_header(n, seq, 0x00, ck) + payload
    padded = ((n + 0xF) >> 4) << 4
    body = crypto.encrypt(payload + b'\x00' * (padded - n))
    return encode_header(n, seq, FLAG_ENC, ck) + body


def iter_frames(buf: bytes):
    """Recorre frames. Devuelve (info, cuerpo_crudo, offset). No descifra."""
    off = 0
    while off + HDR <= len(buf):
        h = decode_header(buf, off)
        if h['length'] == 0 or h['length'] > 0x10000:
            break
        if off + h['wire'] > len(buf):
            break
        yield h, buf[off + HDR: off + h['wire']], off
        off += h['wire']


def submessages(payload: bytes):
    """[(opcode, cuerpo)] y bytes consumidos."""
    out, i = [], 0
    while i + 4 <= len(payload):
        sl = struct.unpack_from('<H', payload, i)[0]
        if sl < 2 or i + 2 + sl > len(payload):
            break
        out.append((struct.unpack_from('<H', payload, i + 2)[0], payload[i + 4: i + 2 + sl]))
        i += 2 + sl
    return out, i


def pack_submessages(msgs) -> bytes:
    """msgs: iterable de bytes ya serializados (opcode incluido, como devuelve
    Msg.build). Antepone el LE16 de largo a cada uno."""
    return b''.join(struct.pack('<H', len(m)) + m for m in msgs)
