"""
Prueba de ida y vuelta del framing contra frames REALES.

Si nuestro emisor produce bytes identicos a los que emitio el servidor real,
el framing de salida es correcto. Es la contraparte del harness de opcodes:
aquel valida el CONTENIDO del payload, este valida el SOBRE.
"""
import sys, struct, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'proto'))
from framing import (HDR, decode_header, build_frame, checksum,
                     submessages, pack_submessages)

SEP = b'\x00' * 6


def walk(d):
    """Recorre frames saltando los separadores espurios del sniffer SOLO en
    los limites de frame -- nunca dentro de un payload."""
    off = 0
    while off + HDR <= len(d):
        if d[off:off + HDR] == SEP:
            off += HDR
            continue
        h = decode_header(d, off)
        if h['length'] == 0 or h['length'] > 0x4000:
            off += 1
            continue
        if h['flags'] not in (0x00, 0x01, 0x80, 0x81):
            off += 1
            continue
        if off + h['wire'] > len(d):
            break
        yield h, d[off + HDR: off + h['wire']], d[off:off + h['wire']]
        off += h['wire']


tot = ok = stot = sok = 0
enc = cmp_ = 0
for p in sorted(pathlib.Path('logs/raw_streams').glob('*s2c.bin')):
    if p.stat().st_size < 1000:
        continue
    for h, body, original in walk(p.read_bytes()):
        if h['encrypted']:
            enc += 1; continue
        if h['compressed']:
            cmp_ += 1; continue
        if checksum(body, h['length']) != h['checksum']:
            continue
        tot += 1
        if build_frame(body[:h['length']], h['seq']) == original:
            ok += 1
        msgs, used = submessages(body[:h['length']])
        if used == h['length'] and msgs:
            stot += 1
            if pack_submessages([struct.pack('<H', o) + b for o, b in msgs]) == body[:h['length']]:
                sok += 1

print(f"frames en claro verificados : {tot}")
print(f"  re-codificados identicos  : {ok}  ({100*ok/max(tot,1):.1f}%)")
print(f"payloads con cadena completa: {stot}")
print(f"  re-empaquetados identicos : {sok}  ({100*sok/max(stot,1):.1f}%)")
print(f"(omitidos: {enc} cifrados, {cmp_} comprimidos)")
