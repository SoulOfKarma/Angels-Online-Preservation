"""
Prueba end-to-end del flujo de entrada al mundo, por socket real.

Un cliente sintetico que habla el protocolo validado:
  1. recibe el Hello y saca la clave
  2. manda 0x0002 (autenticacion) cifrado
  3. recibe la secuencia de inicializacion y la DECODIFICA con los esquemas
  4. manda un MOVE_REQ y comprueba la respuesta
"""
import asyncio, sys, struct, pathlib, collections
RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'server')); sys.path.insert(0, str(RAIZ / 'proto'))
from app import Servidor
from framing import HDR, decode_header, encode_header, checksum, submessages, pack_submessages
from handshake import parse_hello, XorEvolving
from codec import Msg
import messages  # noqa

PUERTO = 17801


def cifrar(payload, seq, cripto):
    pad = ((len(payload) + 15) >> 4) << 4
    return (encode_header(len(payload), seq, 0x01, checksum(payload, len(payload)))
            + cripto.encrypt(payload + b'\x00' * (pad - len(payload))))


def leer_subs(buf):
    subs, off = [], 0
    while off + HDR <= len(buf):
        h = decode_header(buf, off)
        if h['length'] == 0 or off + h['wire'] > len(buf): break
        cuerpo = buf[off + HDR: off + h['wire']]
        if h['seq'] != 0xFFFF and not h['encrypted']:
            s, _ = submessages(cuerpo[:h['length']])
            subs.extend(s)
        off += h['wire']
    return subs


async def main():
    srv = Servidor('127.0.0.1', PUERTO)
    servidor = await asyncio.start_server(srv.cliente, '127.0.0.1', PUERTO)
    async with servidor:
        r, w = await asyncio.open_connection('127.0.0.1', PUERTO)

        raw = await r.read(4096)
        h = decode_header(raw, 0)
        hello = parse_hello(raw[HDR:HDR + h['length']])
        print(f"1. Hello  clave={hello['key'].hex()[:16]}...  variante={hello['variante']}")

        cripto = XorEvolving(hello['key'])
        auth = struct.pack('<H', 0x0002) + b'\x00' * 33
        w.write(cifrar(pack_submessages([auth]), 1, cripto)); await w.drain()
        print("2. autenticacion enviada (0x0002, 33 B)")

        await asyncio.sleep(0.4)
        datos = b''
        while True:
            try:
                trozo = await asyncio.wait_for(r.read(65536), 0.4)
            except asyncio.TimeoutError:
                break
            if not trozo: break
            datos += trozo
        subs = leer_subs(datos)
        print(f"3. recibidos {len(subs)} sub-mensajes ({len(datos)} bytes)\n")

        print(f"   {'#':>3} {'opcode':<8} {'bytes':>6}  decodificado")
        okc = 0
        for i, (op, b) in enumerate(subs):
            m = next((Msg.registry.get((op, 's2c', rv)) for rv in ('*', 'privado', 'igg')
                      if Msg.registry.get((op, 's2c', rv))), None)
            nota = ''
            if m:
                try:
                    d = m.parse(b)
                    okc += 1
                    if op == 0x0002:
                        nota = (f"{m.name}: entidad={d['entity_id']} "
                                f"tile=({d['tile_x']},{d['tile_y']}) "
                                f"nombre='{d['name_raw'].split(bytes(1))[0].decode()}'")
                    elif op == 0x005D:
                        nota = f"{m.name}: ts={d['timestamp']}"
                    elif op == 0x0021:
                        nota = f"{m.name}: {d['n']} quests"
                    elif op == 0x005B:
                        nota = f"{m.name}: {sum(1 for x in d['ranuras'] if x['usada'])} ranuras usadas"
                    else:
                        nota = m.name
                except Exception as e:
                    nota = f"{m.name} (no parsea: {e})"
            else:
                nota = 'sin esquema'
            print(f"   {i:>3} 0x{op:04X}   {len(b):>6}  {nota}")
        print(f"\n   decodificados con esquema: {okc}/{len(subs)}")

        # movimiento
        MOVE = Msg.registry[(0x0004, 'c2s', '*')]
        sub = MOVE.build(cur_x=3102, cur_y=453, unk_05=0, path=[{'x': 3600, 'y': 431}])
        w.write(cifrar(pack_submessages([sub]), 2, cripto)); await w.drain()
        await asyncio.sleep(0.4)
        try:
            resp = await asyncio.wait_for(r.read(65536), 0.5)
        except asyncio.TimeoutError:
            resp = b''
        rs = leer_subs(resp)
        print(f"\n4. MOVE_REQ enviado -> respuesta: {[f'0x{o:04X}' for o,_ in rs]}")
        for op, b in rs:
            if op == 0x0005:
                d = Msg.registry[(0x0005, 's2c', '*')].parse(b)
                print(f"   ENTITY_MOVE: entidad={d['entity_id']} "
                      f"({d['cur_x']},{d['cur_y']}) -> ({d['dst_x']},{d['dst_y']}) vel={d['speed']}")
        w.close()
        await asyncio.sleep(0.2)

asyncio.run(main())
