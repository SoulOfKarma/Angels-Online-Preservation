"""
Lector pcapng en streaming + reensamblado TCP por flujo.

Formato pcapng: cada bloque es
    u32 tipo | u32 longitud_total | cuerpo (longitud_total-12) | u32 longitud_total
La longitud se REPITE al final. Omitir esos 4 bytes desincroniza todo.
"""
import struct, sys, pathlib, collections

SHB, IDB, EPB, SPB = 0x0A0D0D0A, 0x00000001, 0x00000006, 0x00000003


def blocks(f):
    en = '<'
    while True:
        hdr = f.read(8)
        if len(hdr) < 8:
            return
        btype = struct.unpack(en + 'I', hdr[0:4])[0]
        blen = struct.unpack(en + 'I', hdr[4:8])[0]
        if btype == SHB:
            # el orden de bytes se decide aqui
            magic = f.read(4)
            en = '<' if magic == b'\x4d\x3c\x2b\x1a' else '>'
            blen = struct.unpack(en + 'I', hdr[4:8])[0]
            f.read(blen - 12)          # resto del cuerpo (ya incluye la long. final)
            continue
        if blen < 12 or blen > 50_000_000:
            return
        body = f.read(blen - 12)
        if len(body) < blen - 12:
            return
        f.read(4)                      # longitud repetida  <-- el bug estaba aca
        yield btype, body, en


def eth_ip_tcp(data):
    if len(data) < 34:
        return None
    et = struct.unpack_from('>H', data, 12)[0]
    off = 14
    if et == 0x8100:
        et = struct.unpack_from('>H', data, 16)[0]
        off = 18
    if et != 0x0800:
        return None
    ihl = (data[off] & 0xF) * 4
    if data[off + 9] != 6:             # no TCP
        return None
    tot = struct.unpack_from('>H', data, off + 2)[0]
    src = '.'.join(str(b) for b in data[off + 12:off + 16])
    dst = '.'.join(str(b) for b in data[off + 16:off + 20])
    t = off + ihl
    if len(data) < t + 20:
        return None
    sp, dp = struct.unpack_from('>HH', data, t)
    seq = struct.unpack_from('>I', data, t + 4)[0]
    doff = (data[t + 12] >> 4) * 4
    end = off + tot
    payload = data[t + doff: end if end <= len(data) else len(data)]
    return src, sp, dst, dp, seq, payload


def main(pcap, outdir, min_bytes=2000):
    outdir = pathlib.Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    flows = collections.defaultdict(dict)
    npkt = ntcp = 0
    linktypes = collections.Counter()
    with open(pcap, 'rb') as f:
        for btype, body, en in blocks(f):
            if btype == IDB:
                linktypes[struct.unpack_from(en + 'H', body, 0)[0]] += 1
                continue
            if btype != EPB or len(body) < 20:
                continue
            npkt += 1
            caplen = struct.unpack_from(en + 'I', body, 12)[0]
            r = eth_ip_tcp(body[20:20 + caplen])
            if not r:
                continue
            src, sp, dst, dp, seq, pl = r
            if not pl:
                continue
            ntcp += 1
            flows[(src, sp, dst, dp)][seq] = pl
            if ntcp % 300000 == 0:
                print(f"  ...{ntcp} segmentos, {len(flows)} flujos", flush=True)

    print(f"linktypes: {dict(linktypes)}")
    print(f"paquetes: {npkt} | segmentos TCP con datos: {ntcp} | flujos: {len(flows)}\n")

    written = 0
    for (src, sp, dst, dp), segs in sorted(
            flows.items(), key=lambda kv: -sum(len(v) for v in kv[1].values())):
        total = sum(len(v) for v in segs.values())
        if total < min_bytes:
            continue
        server, port, direction = (dst, dp, 'c2s') if dp < sp else (src, sp, 's2c')
        buf = b''.join(segs[k] for k in sorted(segs))
        tag = abs(hash((src, sp, dst, dp))) % 100000
        name = f"{server.replace('.', '_')}_{port}_{tag}_{direction}.bin"
        (outdir / name).write_bytes(buf)
        written += 1
        if written <= 30:
            print(f"  {name:<48} {len(buf):>10}")
    print(f"\nescritos {written} streams")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
