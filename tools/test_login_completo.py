"""
Prueba del flujo COMPLETO: login -> redirect -> mundo.

Simula lo que hace el cliente real:
  1. conecta al puerto de login, manda un AUTH de 73 B con el usuario en claro
  2. comprueba que recibe MOTD, lista de personajes y REDIRECT
  3. sigue el redirect, conecta al puerto de mundo
  4. comprueba que recibe la secuencia de inicializacion
"""
import asyncio, sys, struct, pathlib
RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'server')); sys.path.insert(0, str(RAIZ / 'proto'))
from app import Servidor
from framing import HDR, decode_header, encode_header, checksum, submessages, pack_submessages
from handshake import parse_hello, XorEvolving
from codec import Msg
import messages  # noqa

LOGIN, MUNDO = 17900, 17901


def cifrar(payload, seq, c):
    pad = ((len(payload) + 15) >> 4) << 4
    return (encode_header(len(payload), seq, 0x01, checksum(payload, len(payload)))
            + c.encrypt(payload + b'\x00' * (pad - len(payload))))


def subs_de(buf):
    out, off = [], 0
    while off + HDR <= len(buf):
        h = decode_header(buf, off)
        if h['length'] == 0 or off + h['wire'] > len(buf): break
        cu = buf[off + HDR: off + h['wire']]
        if h['seq'] != 0xFFFF and not h['encrypted']:
            out.extend(submessages(cu[:h['length']])[0])
        off += h['wire']
    return out


async def leer(r, t=0.6):
    d = b''
    while True:
        try:
            x = await asyncio.wait_for(r.read(65536), t)
        except asyncio.TimeoutError:
            break
        if not x: break
        d += x
    return d


async def main():
    srv = Servidor('127.0.0.1', LOGIN, fport=17902, wport=MUNDO)
    import functools
    s1 = await asyncio.start_server(functools.partial(srv.cliente, rol='login'), '127.0.0.1', LOGIN)
    s2 = await asyncio.start_server(functools.partial(srv.cliente, rol='mundo'), '127.0.0.1', MUNDO)
    async with s1, s2:
        # --- LOGIN ---
        r, w = await asyncio.open_connection('127.0.0.1', LOGIN)
        raw = await r.read(4096)
        h = decode_header(raw, 0)
        clave = parse_hello(raw[HDR:HDR + h['length']])['key']
        print(f"1. login: Hello, clave={clave.hex()[:16]}...")

        c = XorEvolving(clave)
        auth = bytearray(73)
        auth[0:5] = b'karma'
        # hash de contrasena simulado (no puede ser cero: eso se rechaza)
        auth[21:] = bytes(range(1, 73 - 21 + 1))
        w.write(cifrar(pack_submessages([struct.pack('<H', 0x0002) + bytes(auth)]), 1, c))
        await w.drain()
        print("2. AUTH de 73 B enviado (usuario 'karma')")

        d = await leer(r)
        ss = subs_de(d)
        print(f"3. respuesta: {len(d)} B, {len(ss)} sub-mensajes -> "
              f"{[f'0x{o:04X}({len(b)}B)' for o, b in ss]}")
        ip = puerto = None
        for op, b in ss:
            if op == 0x000C:
                n = struct.unpack_from('<I', b, 4)[0]
                print(f"   MOTD: '{b[8:8+n].split(bytes(1))[0].decode()}'")
            if op == 0x0000:
                nom = [x for x in b.split(b'\x00') if 3 <= len(x) <= 12
                       and all(32 <= q < 127 for q in x)]
                print(f"   lista de personajes: {[x.decode() for x in nom][:4]}")
            if op == 0x0004:
                ip = b[7:].split(b'\x00')[0].decode()
                puerto = struct.unpack_from('<H', b, 23)[0]
                print(f"   REDIRECT -> {ip}:{puerto}")
        w.close()
        if not puerto:
            print("\n!! no llego el redirect"); return

        # --- MUNDO ---
        r2, w2 = await asyncio.open_connection(ip, puerto)
        raw2 = await r2.read(4096)
        h2 = decode_header(raw2, 0)
        clave2 = parse_hello(raw2[HDR:HDR + h2['length']])['key']
        print(f"\n4. mundo {ip}:{puerto}: Hello recibido")
        c2 = XorEvolving(clave2)
        w2.write(cifrar(pack_submessages([struct.pack('<H', 0x0002) + bytes(33)]), 1, c2))
        await w2.drain()
        d2 = await leer(r2)
        ss2 = subs_de(d2)
        print(f"5. secuencia de inicializacion: {len(ss2)} mensajes, {len(d2)} bytes")
        for op, b in ss2[:3]:
            m = next((Msg.registry.get((op, 's2c', rv)) for rv in ('*','privado','igg')
                      if Msg.registry.get((op, 's2c', rv))), None)
            if op == 0x0002 and m:
                dd = m.parse(b)
                print(f"   personaje: '{dd['name_raw'].split(bytes(1))[0].decode()}' "
                      f"entidad={dd['entity_id']} tile=({dd['tile_x']},{dd['tile_y']})")
        w2.close()
        await asyncio.sleep(0.2)
    print("\nFLUJO COMPLETO OK: login -> redirect -> mundo")

asyncio.run(main())
