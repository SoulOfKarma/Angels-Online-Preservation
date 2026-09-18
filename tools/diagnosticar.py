"""
Diagnostica una sesion grabada con el cliente REAL.

Uso:
    python tools/diagnosticar.py                 <- la ultima sesion
    python tools/diagnosticar.py <base>          <- una en concreto

Reconstruye el dialogo completo en orden, marca cada mensaje del cliente que no
sabemos interpretar, y señala en que punto se corto. Eso convierte "no anduvo"
en "en el mensaje N el cliente esperaba otra cosa".
"""
import sys, pathlib, struct, collections
RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'proto'))
from framing import HDR, decode_header, submessages, checksum
from handshake import XorEvolving
from codec import Msg
import messages  # noqa

SES = RAIZ / 'logs' / 'sesiones'


def esquema(op, d):
    for rev in ('*', 'privado', 'igg'):
        m = Msg.registry.get((op, d, rev))
        if m:
            return m
    return None


def frames(data, cripto=None):
    off = 0
    while off + HDR <= len(data):
        h = decode_header(data, off)
        if h['length'] == 0 or h['length'] > 0x10000:
            yield None, f"longitud invalida ({h['length']}) en +{off}", off
            return
        if off + h['wire'] > len(data):
            yield None, (f"frame truncado en +{off}: necesita {h['wire']}, "
                         f"quedan {len(data)-off}"), off
            return
        cuerpo = data[off + HDR: off + h['wire']]
        if h['encrypted'] and cripto:
            cuerpo = cripto.decrypt(cuerpo)
        ok = checksum(cuerpo, h['length']) == h['checksum']
        yield h, (cuerpo, ok), off
        off += h['wire']


def main(base=None):
    if base is None:
        c = sorted(SES.glob('*_c2s.bin'), key=lambda p: p.stat().st_mtime)
        if not c:
            print("no hay sesiones grabadas en logs/sesiones/")
            return
        base = c[-1].name[:-8]
    print(f"=== sesion {base} ===\n")
    pc = SES / f"{base}_c2s.bin"
    ps = SES / f"{base}_s2c.bin"
    pk = SES / f"{base}_clave.txt"
    clave = bytes.fromhex(pk.read_text().strip()) if pk.exists() else bytes(16)
    dc = pc.read_bytes() if pc.exists() else b''
    ds = ps.read_bytes() if ps.exists() else b''
    print(f"cliente -> servidor : {len(dc)} bytes")
    print(f"servidor -> cliente : {len(ds)} bytes")
    print(f"clave de sesion     : {clave.hex(' ')}\n")

    if not dc:
        print("!! EL CLIENTE NO MANDO NADA.")
        print("   Recibio el Hello y corto. Revisar: formato del Hello, o el")
        print("   cliente esperaba conectarse a otro puerto primero.")
        return

    print("--- lo que mando el CLIENTE ---")
    cripto = XorEvolving(clave)
    vistos, sin_esquema = collections.Counter(), collections.Counter()
    i = 0
    for h, res, off in frames(dc, cripto):
        if h is None:
            print(f"\n!! CORTE: {res}")
            print(f"   bytes restantes: {dc[off:off+32].hex(' ')}")
            break
        cuerpo, ok = res
        subs, used = submessages(cuerpo[:h['length']])
        for op, b in subs:
            m = esquema(op, 'c2s')
            vistos[op] += 1
            marca = ''
            if m is None:
                sin_esquema[op] += 1
                marca = '  <-- SIN ESQUEMA'
            print(f"  #{i:<3} seq={h['seq']:<5} 0x{op:04X} {len(b):>5}B "
                  f"{'csum ok' if ok else 'CSUM MAL'} "
                  f"{m.name if m else '?':<16}{marca}")
            if m is None:
                print(f"        {b[:40].hex(' ')}")
            i += 1

    print(f"\n--- resumen ---")
    print(f"mensajes del cliente : {sum(vistos.values())}")
    print(f"opcodes distintos    : {len(vistos)}")
    if sin_esquema:
        print(f"SIN ESQUEMA          : "
              f"{ {f'0x{k:04X}': v for k, v in sin_esquema.items()} }")
        print("   ^ esto es lo que hay que implementar para avanzar")
    else:
        print("todos los mensajes del cliente se interpretaron")


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
