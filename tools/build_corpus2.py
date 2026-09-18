"""
Corpus v2: extrae la clave de sesion del Hello y aplica el cifrador correcto
por direccion.

Confirmado sobre trafico real de IGG (100% de checksums validos en ambas):
    S->C : CryptXOR    (clave fija de 16 bytes)
    C->S : CryptXORIV  (cada DWORD de la clave += padded_len tras cada paquete)

El Hello (seq=0xFFFF, plano) trae: [LE16 sub_len][LE32 key_len=16][clave]
El opcode 0x0002 LOGIN_REQ contiene credenciales: se guarda su tamano y
offset, nunca su contenido.
"""
import struct, sys, pathlib, sqlite3, collections

HDR, X, ENC, CMP = 6, 0x1357, 0x01, 0x80
SENSIBLES = {0x0002}


def csum(p, n):
    v = 0xD31F
    for i in range(0, min(n & ~1, len(p)), 2): v ^= struct.unpack_from('<H', p, i)[0]
    v &= 0xFFFF; s = v & 0xF
    if s: v = ((v << s) | (v >> (16 - s))) & 0xFFFF
    return (v & 0xFF) ^ ((v >> 8) & 0xFF)


def xor(d, k): return bytes(b ^ k[i % 16] for i, b in enumerate(d))


class Static:
    def __init__(s, k): s.k = bytearray(k)
    def dec(s, d): return xor(d, s.k)


class Evolving:
    def __init__(s, k): s.k = bytearray(k)
    def dec(s, d):
        o = xor(d, s.k)
        for i in range(0, 16, 4):
            struct.pack_into('<I', s.k, i,
                (struct.unpack_from('<I', s.k, i)[0] + len(d)) & 0xFFFFFFFF)
        return o


def raw_frames(d):
    off = 0
    while off + HDR <= len(d):
        if d[off:off+HDR] == b'\x00' * 6:
            off += HDR; continue
        l = struct.unpack_from('<H', d, off)[0] ^ X
        sq = struct.unpack_from('<H', d, off+2)[0] ^ l
        fl = (d[off+4] ^ (l & 0xFF)) & 0xFF
        if l == 0 or l > 0x4000 or fl not in (0,1,0x80,0x81) or not (1 <= sq <= 0x7FFE or sq == 0xFFFF):
            off += 1; continue
        pad = ((l+0xF)>>4)<<4 if fl & ENC else l
        if off + HDR + pad > len(d): break
        yield l, sq, fl, d[off+5], d[off+HDR:off+HDR+pad]
        off += HDR + pad


def find_key(path_s2c):
    """Primer frame seq=0xFFFF plano -> [LE16 sub_len][LE32 key_len][clave]."""
    for l, sq, fl, ck, body in raw_frames(path_s2c.read_bytes()):
        if sq == 0xFFFF and not (fl & ENC):
            if len(body) >= 22:
                klen = struct.unpack_from('<I', body, 2)[0]
                if klen == 16 and len(body) >= 22:
                    return bytes(body[6:22])
        break
    return b'\x00' * 16


def submsgs(p):
    out, i = [], 0
    while i + 4 <= len(p):
        sl = struct.unpack_from('<H', p, i)[0]
        if sl < 2 or i + 2 + sl > len(p): break
        out.append((struct.unpack_from('<H', p, i+2)[0], p[i+4:i+2+sl]))
        i += 2 + sl
    return out, i


def main(indir, dbpath):
    db = sqlite3.connect(dbpath)
    db.executescript("""
      DROP TABLE IF EXISTS packets;
      CREATE TABLE packets(stream TEXT, server TEXT, port INT, dir TEXT,
        seq INT, flags INT, csum_ok INT, chain_ok INT, opcode INT,
        body BLOB, size INT);
      CREATE INDEX idx_op ON packets(opcode);""")

    files = sorted(pathlib.Path(indir).glob('*.bin'))
    # clave por (servidor,puerto): sale del stream s2c que traiga el Hello
    keys = {}
    for p in files:
        if not p.stem.endswith('s2c'): continue
        parts = p.stem.split('_')
        ep = ('.'.join(parts[:4]), int(parts[4]))
        k = find_key(p)
        if any(k) or ep not in keys:
            keys[ep] = k
    for ep, k in keys.items():
        print(f"  clave {ep[0]}:{ep[1]} = {k.hex(' ')}{'   (nula)' if not any(k) else ''}")

    rows, st = [], collections.defaultdict(collections.Counter)
    for p in files:
        parts = p.stem.split('_')
        ep = ('.'.join(parts[:4]), int(parts[4]))
        d = p.stem.endswith('c2s') and 'c2s' or 's2c'
        key = keys.get(ep, b'\x00'*16)
        crypto = (Evolving if d == 'c2s' else Static)(key)
        for l, sq, fl, ck, body in raw_frames(p.read_bytes()):
            pt = crypto.dec(body) if (fl & ENC) else body
            if fl & CMP:
                st[d]['comprimidos'] += 1; continue
            ok = csum(pt, l) == ck
            msgs, used = submsgs(pt[:l])
            st[d]['frames'] += 1; st[d]['csum'] += ok; st[d]['chain'] += (used == l)
            for op, b in msgs:
                rows.append((p.name, ep[0], ep[1], d, sq, fl, int(ok), int(used == l),
                             op, b'' if op in SENSIBLES else b, len(b)))
    db.executemany("INSERT INTO packets VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    db.commit()
    print("\n=== VALIDACION ===")
    for d in ('c2s', 's2c'):
        s = st[d]; f = s['frames'] or 1
        print(f"  {d}: {s['frames']:>7} frames | checksum {100*s['csum']/f:5.1f}% | "
              f"cadena {100*s['chain']/f:5.1f}% | comprimidos {s['comprimidos']}")
    print(f"\n  sub-mensajes: {len(rows)} | opcodes: "
          f"{db.execute('SELECT COUNT(DISTINCT opcode) FROM packets WHERE chain_ok=1').fetchone()[0]}")
    db.close()


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
