"""Valida la implementacion de LZO1X contra TODOS los frames comprimidos reales."""
import sys, pathlib, collections
RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'proto'))
from framing import HDR, decode_header, submessages, checksum
from handshake import parse_hello, XorStatic, XorEvolving
from lzo import descomprimir

SEP = b'\x00' * 6
ok = err = 0
cadena_ok = 0
fallos = collections.Counter()
total_in = total_out = 0

for p in sorted((RAIZ / 'logs' / 'raw_streams').glob('*.bin')):
    d = p.read_bytes()
    if len(d) < 30: continue
    es_s2c = p.stem.endswith('s2c')
    clave = bytes(16)
    off = 0
    h0 = decode_header(d, 0)
    if h0['seq'] == 0xFFFF and not h0['encrypted']:
        try: clave = parse_hello(d[HDR:HDR + h0['length']])['key']
        except Exception: pass
    cripto = (XorStatic if es_s2c else XorEvolving)(clave)
    while off + HDR <= len(d):
        if d[off:off + HDR] == SEP: off += HDR; continue
        h = decode_header(d, off)
        if h['length'] == 0 or h['length'] > 0x4000 or h['flags'] not in (0,1,0x80,0x81):
            off += 1; continue
        if off + h['wire'] > len(d): break
        cuerpo = d[off + HDR: off + h['wire']]
        if h['encrypted']: cuerpo = cripto.decrypt(cuerpo)
        if h['compressed']:
            total_in += h['length']
            try:
                r = descomprimir(cuerpo[:h['length']])
                ok += 1; total_out += len(r)
                s, used = submessages(r)
                if used == len(r) and s: cadena_ok += 1
            except Exception as e:
                err += 1; fallos[type(e).__name__] += 1
        off += h['wire']

print(f"frames comprimidos procesados : {ok + err}")
print(f"  descomprimidos sin error    : {ok}  ({100*ok/max(ok+err,1):.1f}%)")
print(f"  con cadena de sub-mensajes exacta: {cadena_ok}/{ok}"
      f"  ({100*cadena_ok/max(ok,1):.1f}%)")
if fallos: print(f"  fallos: {dict(fallos)}")
if total_out: print(f"  razon de compresion: {total_in} -> {total_out} "
                   f"({total_out/max(total_in,1):.2f}x)")
