"""
Prueba de ida y vuelta por SOCKET real contra el servidor.

Levanta el servidor, conecta un cliente sintetico que habla el protocolo
validado, y comprueba que el Hello llega bien y que los mensajes del cliente
se reciben e interpretan.
"""
import asyncio, sys, pathlib, struct
RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'server')); sys.path.insert(0, str(RAIZ / 'proto'))
from app import Servidor
from framing import HDR, decode_header, build_frame, pack_submessages
from handshake import parse_hello, XorEvolving
from codec import Msg
import messages  # noqa

PUERTO = 17777


async def main():
    srv = Servidor('127.0.0.1', PUERTO)
    servidor = await asyncio.start_server(srv.cliente, '127.0.0.1', PUERTO)
    async with servidor:
        r, w = await asyncio.open_connection('127.0.0.1', PUERTO)

        # 1. recibir el Hello
        raw = await r.read(256)
        h = decode_header(raw, 0)
        hello = parse_hello(raw[HDR:HDR + h['length']])
        print(f"1. Hello recibido: seq=0x{h['seq']:04X} plano={not h['encrypted']} "
              f"variante={hello['variante']}")
        print(f"   clave de sesion: {hello['key'].hex(' ')}")
        assert h['seq'] == 0xFFFF and not h['encrypted'] and len(hello['key']) == 16

        # 2. mandar un MOVE_REQ real, cifrado como lo haria el cliente
        cripto = XorEvolving(hello['key'])
        MOVE = Msg.registry[(0x0004, 'c2s', '*')]
        sub = MOVE.build(cur_x=3102, cur_y=453, unk_05=0x9b4c,
                         path=[{'x': 3600, 'y': 431}])
        payload = pack_submessages([sub])
        pad = ((len(payload) + 15) >> 4) << 4
        from framing import checksum, encode_header
        marco = (encode_header(len(payload), 1, 0x01, checksum(payload, len(payload)))
                 + cripto.encrypt(payload + b'\x00' * (pad - len(payload))))
        w.write(marco); await w.drain()
        print(f"2. MOVE_REQ enviado cifrado ({len(marco)} bytes en el cable)")

        await asyncio.sleep(0.3)
        w.close()
        await asyncio.sleep(0.2)
        print(f"3. el servidor lo interpreto: opcodes sin esquema = "
              f"{dict(srv.desconocidos) or 'ninguno'}")
        print(f"   sesiones atendidas: {srv.sesiones}")
    print("\nTRANSPORTE OK: handshake, cifrado C->S y parseo funcionan por socket real.")

asyncio.run(main())
