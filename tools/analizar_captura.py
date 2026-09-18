"""
Analiza una captura de un servidor REAL y extrae el flujo completo de login.

    python tools/analizar_captura.py captura.pcapng

Hace todo el recorrido: extrae los streams TCP, identifica cuales son
protocolo AO, saca la clave del Hello, descifra, descomprime LZO si hace
falta, y lista el dialogo completo en orden con los opcodes decodificados.

Lo que buscamos es el mensaje que manda el cliente al apretar "Enter game",
que es el unico que nos falta para entrar al mundo.
"""
import sys, pathlib, struct, subprocess, collections
RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'proto'))
from framing import HDR, decode_header, submessages, checksum
from handshake import parse_hello, XorStatic, XorEvolving
from lzo import descomprimir
from codec import Msg
import messages  # noqa

SEP = b'\x00' * 6


def nombre(op, d):
    for rev in ('*', 'privado', 'igg'):
        m = Msg.registry.get((op, d, rev))
        if m:
            return m.name
    return '?'


def recorrer(datos, clave, es_s2c):
    cripto = (XorStatic if es_s2c else XorEvolving)(clave)
    off = 0
    while off + HDR <= len(datos):
        if datos[off:off + HDR] == SEP:
            off += HDR; continue
        h = decode_header(datos, off)
        if h['length'] == 0 or h['length'] > 0x4000 or h['flags'] not in (0, 1, 0x80, 0x81):
            off += 1; continue
        if off + h['wire'] > len(datos):
            break
        cuerpo = datos[off + HDR: off + h['wire']]
        if h['encrypted']:
            cuerpo = cripto.decrypt(cuerpo)
        cuerpo = cuerpo[:h['length']]
        if h['compressed']:
            try: cuerpo = descomprimir(cuerpo)
            except Exception: pass
        yield h, cuerpo
        off += h['wire']


def main(pcap):
    f = pathlib.Path(pcap)
    if not f.exists():
        print(f"No existe el archivo: {pcap}")
        print()
        print("Uso:  python tools/analizar_captura.py <tu_captura.pcapng>")
        print()
        print("Primero hay que hacer la captura con Wireshark:")
        print("  1. Abrir Wireshark y empezar a capturar")
        print("  2. Arrancar el cliente DESDE CERO (si ya esta abierto no")
        print("     se captura el Hello y sin la clave no se descifra nada)")
        print("  3. Loguearse, crear personaje, apretar Enter game, entrar")
        print("  4. Parar la captura y guardarla como .pcapng")
        print()
        print("Despues pasar la ruta REAL de ese archivo a este comando.")
        cand = sorted(RAIZ.glob('*.pcapng')) + sorted(RAIZ.glob('*.pcap'))
        if cand:
            print()
            print("Capturas que ya hay en el proyecto:")
            for c in cand:
                print(f"  {c.name}  ({c.stat().st_size/1048576:.0f} MB)")
        return
    tmp = RAIZ / 'corpus' / 'captura_nueva'
    print(f"1. extrayendo streams de {pcap} ...")
    subprocess.run([sys.executable, str(RAIZ / 'tools' / 'pcap_streams.py'),
                    pcap, str(tmp)], check=True,
                   stdout=subprocess.DEVNULL)
    print(f"2. clasificando ...")
    subprocess.run([sys.executable, str(RAIZ / 'tools' / 'classify_streams.py'),
                    str(tmp)])
    print("\n3. dialogo por endpoint (solo los que son protocolo AO):\n")
    for p in sorted(tmp.glob('*_s2c.bin'), key=lambda x: -x.stat().st_size)[:6]:
        d = p.read_bytes()
        if len(d) < 30: continue
        h0 = decode_header(d, 0)
        if h0['seq'] != 0xFFFF or h0['encrypted']:
            continue                      # sin Hello no hay clave
        clave = parse_hello(d[HDR:HDR + h0['length']])['key']
        pc = pathlib.Path(str(p).replace('_s2c.bin', '_c2s.bin'))
        print(f"=== {p.name[:34]}  clave={clave.hex()[:16]}...")
        if pc.exists():
            print("  --- CLIENTE ---")
            for h, c in recorrer(pc.read_bytes(), clave, False):
                for op, b in submessages(c)[0]:
                    print(f"    0x{op:04X} {len(b):>5}B  {nombre(op,'c2s')}")
        print("  --- SERVIDOR ---")
        for h, c in recorrer(d[h0['wire']:], clave, True):
            for op, b in submessages(c)[0]:
                print(f"    0x{op:04X} {len(b):>5}B  {nombre(op,'s2c')}")
        print()


if __name__ == '__main__':
    main(sys.argv[1])
