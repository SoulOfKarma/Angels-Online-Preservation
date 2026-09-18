"""
Construye el corpus de paquetes reales a partir de los streams TCP capturados.

Framing y cifrado confirmados contra el binario del cliente (sub_81E900 lector,
sub_81EF80 emisor, sub_81DBF0 checksum). Los separadores de 6 bytes en cero son
artefactos del sniffer -- el cliente real los trataria como error fatal -- y se
descartan.

Criterio de validacion: tras descifrar, la cadena de sub-mensajes
[LE16 len][LE16 opcode][...] debe consumir EXACTAMENTE payload_length.
Si eso se cumple en masa, framing + clave estan probados.
"""
import struct, sys, pathlib, sqlite3, collections

HDR, HDR_XOR, FLAG_ENC, FLAG_CMP = 6, 0x1357, 0x01, 0x80
SEP = b'\x00' * 6


class CryptXORIV:
    """XOR de 16 bytes con clave evolutiva: tras cada paquete, cada DWORD += padded_len."""
    def __init__(self, key=b'\x00' * 16):
        self.key = bytearray(key)

    def decrypt(self, data):
        k = self.key
        out = bytes(b ^ k[i % 16] for i, b in enumerate(data))
        for i in range(0, 16, 4):
            v = (struct.unpack_from('<I', k, i)[0] + len(data)) & 0xFFFFFFFF
            struct.pack_into('<I', k, i, v)
        return out


def checksum(payload, length):
    val = 0xD31F
    for i in range(0, min(length & ~1, len(payload)), 2):
        val ^= struct.unpack_from('<H', payload, i)[0]
    val &= 0xFFFF
    s = val & 0xF
    if s:
        val = ((val << s) | (val >> (16 - s))) & 0xFFFF
    return (val & 0xFF) ^ ((val >> 8) & 0xFF)


def submsgs(payload):
    """Devuelve (lista_de_(opcode,body), bytes_consumidos)."""
    out, p = [], 0
    while p + 4 <= len(payload):
        sl = struct.unpack_from('<H', payload, p)[0]
        if sl < 2 or p + 2 + sl > len(payload):
            break
        op = struct.unpack_from('<H', payload, p + 2)[0]
        out.append((op, payload[p + 4: p + 2 + sl]))
        p += 2 + sl
    return out, p


def parse_stream(data, encrypted_dir):
    crypto = CryptXORIV()
    off = 0
    stats = collections.Counter()
    while off + HDR <= len(data):
        if data[off:off + HDR] == SEP:
            stats['separadores'] += 1
            off += HDR
            continue
        l = struct.unpack_from('<H', data, off)[0] ^ HDR_XOR
        seq = struct.unpack_from('<H', data, off + 2)[0] ^ l
        flags = (data[off + 4] ^ (l & 0xFF)) & 0xFF
        csum = data[off + 5]
        if l == 0 or l > 0x10000:
            off += 1; stats['desync'] += 1; continue
        padded = ((l + 0xF) >> 4) << 4 if (flags & FLAG_ENC) else l
        if off + HDR + padded > len(data):
            stats['cola_incompleta'] += 1
            break
        raw = data[off + HDR: off + HDR + padded]
        off += HDR + padded

        body = crypto.decrypt(raw) if (flags & FLAG_ENC) else raw
        if flags & FLAG_CMP:
            stats['comprimidos_omitidos'] += 1
            continue
        ok_csum = checksum(body, l) == csum
        msgs, consumed = submsgs(body[:l])
        exact = (consumed == l)
        stats['frames'] += 1
        stats['csum_ok'] += ok_csum
        stats['cadena_exacta'] += exact
        yield seq, flags, ok_csum, exact, msgs, stats


def main(indir, dbpath):
    db = sqlite3.connect(dbpath)
    db.executescript("""
      DROP TABLE IF EXISTS packets;
      CREATE TABLE packets(
        stream TEXT, server TEXT, port INT, dir TEXT,
        seq INT, flags INT, csum_ok INT, chain_ok INT,
        opcode INT, body BLOB, size INT);
      CREATE INDEX idx_op ON packets(opcode);
      CREATE INDEX idx_dir ON packets(dir);
    """)
    total = collections.Counter()
    per_dir = collections.defaultdict(collections.Counter)
    rows = []
    for p in sorted(pathlib.Path(indir).glob('*.bin')):
        if p.stat().st_size < 20:
            continue
        parts = p.stem.split('_')
        server, port, direction = '.'.join(parts[:4]), int(parts[4]), parts[-1]
        st = None
        for seq, flags, ok, exact, msgs, st in parse_stream(p.read_bytes(), direction == 'c2s'):
            for op, body in msgs:
                rows.append((p.name, server, port, direction, seq, flags,
                             int(ok), int(exact), op, body, len(body)))
        if st:
            for k, v in st.items():
                total[k] += v; per_dir[direction][k] += v
    db.executemany("INSERT INTO packets VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    db.commit()

    print("=== VALIDACION ===")
    for d in ('c2s', 's2c'):
        s = per_dir[d]
        f = s['frames'] or 1
        print(f"  {d}: {s['frames']:>7} frames | checksum OK {100*s['csum_ok']/f:5.1f}% | "
              f"cadena exacta {100*s['cadena_exacta']/f:5.1f}% | desync {s['desync']} | sep {s['separadores']}")
    print(f"\n  sub-mensajes guardados: {len(rows)}")
    n = db.execute("SELECT COUNT(DISTINCT opcode) FROM packets").fetchone()[0]
    print(f"  opcodes distintos     : {n}")
    db.close()


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
