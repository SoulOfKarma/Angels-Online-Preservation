"""
Validacion por replay: se alimenta la sesion del servidor con el stream C2S
REAL capturado y se mide cuanto entiende.

No es un test que uno pueda hacerse trampa a si mismo: los bytes los produjo
un cliente real hablando con un servidor real. Si nuestra sesion los parsea,
es porque el protocolo esta bien implementado.

Mide dos cosas distintas:
  ENTRADA  que fraccion de lo que el cliente dice sabemos interpretar
  SALIDA   que fraccion de lo que el servidor real respondio sabriamos construir
"""
import sys, pathlib, collections, struct
RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'proto'))

from session import Session
from framing import HDR, decode_header, submessages, checksum
from codec import Msg
import messages  # noqa

SEP = b'\x00' * 6


def frames_en_claro(d):
    off = 0
    while off + HDR <= len(d):
        if d[off:off + HDR] == SEP:
            off += HDR; continue
        h = decode_header(d, off)
        if h['length'] == 0 or h['length'] > 0x4000 or h['flags'] not in (0, 1, 0x80, 0x81):
            off += 1; continue
        if off + h['wire'] > len(d): break
        yield h, d[off + HDR: off + h['wire']]
        off += h['wire']


def esquema(op, direccion):
    for rev in ('*', 'privado', 'igg'):
        m = Msg.registry.get((op, direccion, rev))
        if m: return m
    return None


def main(par_c2s, par_s2c):
    # ---- ENTRADA: replay del stream real del cliente
    ses = Session(('replay', 0), key=b'\x00' * 16)   # el privado usa clave nula
    ses.enviar_hello()
    msgs = ses.alimentar(pathlib.Path(par_c2s).read_bytes())

    ent = collections.Counter()
    ent_ok = collections.Counter()
    for op, cuerpo in msgs:
        ent[op] += 1
        m, d = ses.parsear(op, cuerpo)
        if m is not None and d is not None:
            ent_ok[op] += 1

    tot_e, ok_e = sum(ent.values()), sum(ent_ok.values())
    print("=" * 74)
    print("REPLAY -- stream C2S real contra nuestra sesion de servidor")
    print("=" * 74)
    print(f"\nENTRADA: {tot_e} mensajes del cliente, {len(ent)} opcodes distintos")
    print(f"  interpretados correctamente: {ok_e}/{tot_e} = {100*ok_e/max(tot_e,1):.1f}%\n")
    print(f"  {'opcode':<9} {'cant':>7} {'ok':>7}  estado")
    for op, n in ent.most_common(14):
        k = ent_ok[op]
        est = "OK" if k == n else ("SIN ESQUEMA" if k == 0 else "parcial")
        print(f"  0x{op:04X}   {n:>7} {k:>7}  {est}")

    # ---- SALIDA: que sabriamos construir de lo que el servidor real dijo
    sal = collections.Counter()
    sal_ok = collections.Counter()
    for h, cuerpo in frames_en_claro(pathlib.Path(par_s2c).read_bytes()):
        if h['encrypted'] or h['compressed']: continue
        if checksum(cuerpo, h['length']) != h['checksum']: continue
        subs, used = submessages(cuerpo[:h['length']])
        if used != h['length']: continue
        for op, b in subs:
            sal[op] += 1
            m = esquema(op, 's2c')
            if m is None: continue
            try:
                if m.roundtrip(b): sal_ok[op] += 1
            except Exception: pass

    tot_s, ok_s = sum(sal.values()), sum(sal_ok.values())
    print(f"\nSALIDA: {tot_s} mensajes del servidor real, {len(sal)} opcodes distintos")
    print(f"  que sabriamos construir: {ok_s}/{tot_s} = {100*ok_s/max(tot_s,1):.1f}%\n")
    print(f"  {'opcode':<9} {'cant':>8} {'ok':>8}  estado")
    for op, n in sal.most_common(14):
        k = sal_ok[op]
        est = "OK" if k == n else ("SIN ESQUEMA" if k == 0 else "parcial")
        print(f"  0x{op:04X}   {n:>8} {k:>8}  {est}")

    faltan = [(op, n) for op, n in sal.most_common() if sal_ok[op] == 0]
    if faltan:
        print(f"\n  opcodes S2C sin esquema, por volumen:")
        for op, n in faltan[:10]:
            print(f"    0x{op:04X}  {n:>7} mensajes  ({100*n/tot_s:.2f}% del trafico)")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
