"""
Valida la HIPOTESIS de framing del protocolo Angels Online contra capturas reales.

No confia en el codigo previo: lo somete a prueba. Si el framing es correcto,
recorrer cada stream TCP real (header -> longitud -> siguiente header) debe
consumir el archivo entero sin bytes sobrantes y sin longitudes absurdas.

Hipotesis bajo prueba (header de 6 bytes ofuscado):
    b0-1: payload_length XOR 0x1357   (LE16)
    b2-3: sequence       XOR payload_length (LE16)
    b4  : flags          XOR (payload_length & 0xFF)
    b5  : checksum del payload en claro
  wire = 6 + (payload redondeado a 16 si flags bit0 [encrypted])
"""
import struct, sys, pathlib, collections

HDR = 6
HDR_XOR = 0x1357
FLAG_ENC = 0x01
FLAG_CMP = 0x80
MAX_PAYLOAD = 0x4000   # cota de cordura


def decode_header(raw, off):
    l = struct.unpack_from('<H', raw, off)[0] ^ HDR_XOR
    seq = struct.unpack_from('<H', raw, off + 2)[0] ^ l
    flags = raw[off + 4] ^ (l & 0xFF)
    csum = raw[off + 5]
    padded = ((l + 0xF) >> 4) << 4 if (flags & FLAG_ENC) else l
    return l, seq, flags, csum, padded


def walk(data):
    """Recorre frames. Devuelve (frames, offset_final, motivo_corte)."""
    off, frames = 0, []
    while off + HDR <= len(data):
        l, seq, flags, csum, padded = decode_header(data, off)
        if l > MAX_PAYLOAD:
            return frames, off, f"payload_length absurdo ({l})"
        if off + HDR + padded > len(data):
            return frames, off, f"frame truncado (necesita {HDR+padded}, quedan {len(data)-off})"
        frames.append({
            'off': off, 'len': l, 'seq': seq, 'flags': flags,
            'enc': bool(flags & FLAG_ENC), 'cmp': bool(flags & FLAG_CMP),
            'csum': csum, 'wire': HDR + padded,
            'payload': data[off + HDR: off + HDR + padded],
        })
        off += HDR + padded
    return frames, off, "fin limpio" if off == len(data) else f"sobran {len(data)-off} bytes"


def main(root):
    files = sorted(pathlib.Path(root).glob('*.bin'))
    tot_f = tot_clean = tot_bytes = tot_consumed = 0
    flagstat = collections.Counter()
    seqbad = 0
    print(f"{'archivo':<44} {'bytes':>9} {'frames':>7} {'consumido':>10}  estado")
    print("-" * 100)
    for p in files:
        data = p.read_bytes()
        if not data:
            continue
        frames, off, reason = walk(data)
        ok = (off == len(data))
        tot_f += len(frames); tot_bytes += len(data); tot_consumed += off
        if ok:
            tot_clean += 1
        for f in frames:
            flagstat[f['flags']] += 1
            # secuencia valida: 1..0x7FFE o 0xFFFF (hello)
            if not (1 <= f['seq'] <= 0x7FFE or f['seq'] == 0xFFFF):
                seqbad += 1
        mark = "OK " if ok else "!! "
        print(f"{p.name:<44} {len(data):>9} {len(frames):>7} {off:>10}  {mark}{reason}")

    print("-" * 100)
    print(f"archivos             : {len(files)}")
    print(f"streams 100% limpios : {tot_clean}/{len([p for p in files if p.stat().st_size>0])}")
    print(f"frames totales       : {tot_f}")
    print(f"bytes consumidos     : {tot_consumed}/{tot_bytes}  ({100*tot_consumed/max(tot_bytes,1):.2f}%)")
    print(f"secuencias fuera de rango: {seqbad}")
    print("\nflags observados (flag: frames):")
    for fl, n in flagstat.most_common(12):
        tags = []
        if fl & FLAG_ENC: tags.append("ENC")
        if fl & FLAG_CMP: tags.append("CMP")
        if not tags: tags.append("plano")
        print(f"  0x{fl:02x}  {n:>7}  {'+'.join(tags)}")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '.')
