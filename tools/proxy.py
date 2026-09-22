"""
Proxy de captura: se pone en el medio entre el cliente y un servidor REAL.

Por que un proxy y no Wireshark:
  - entrega los streams ya separados por conexion y por sentido
  - saca la clave del Hello al vuelo y la guarda junto a la captura
  - y sobre todo: REESCRIBE EL REDIRECT, para que la conexion al servidor de
    mundo tambien pase por aca. Sin eso solo se captura el login.

Uso:
    python tools/proxy.py --server-xml "G:/Play Angels Online/server.xml"

Deja una copia .bak del server.xml y lo apunta a 127.0.0.1. Todo queda en
logs/proxy/ con el mismo formato que el resto del proyecto, asi que
tools/diagnosticar.py lo entiende sin cambios.
"""
import asyncio
import argparse
import os
import re
import datetime
import pathlib
import struct
import sys
import time
import json
import logging

RAIZ = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ / 'proto'))
from framing import HDR, decode_header, encode_header, checksum, submessages
from handshake import parse_hello, XorStatic, XorEvolving

log = logging.getLogger('proxy')
SALIDA = RAIZ / 'logs' / 'proxy'


class Grab:
    """Graba una conexion en los dos sentidos, mas la clave de sesion."""

    def __init__(self, etiqueta):
        SALIDA.mkdir(parents=True, exist_ok=True)
        marca = datetime.datetime.now().strftime('%H%M%S_%f')
        self.base = etiqueta + '_' + marca
        self.c2s = open(SALIDA / (self.base + '_c2s.bin'), 'wb')
        self.s2c = open(SALIDA / (self.base + '_s2c.bin'), 'wb')
        # Los dos sentidos MEZCLADOS y con marca de tiempo. Con los .bin por
        # separado no se puede saber que respuesta corresponde a que pedido:
        # es justo lo que falto para identificar el dialogo de los NPC.
        self.orden = open(SALIDA / (self.base + '_orden.jsonl'), 'w',
                          encoding='utf-8')
        self.t0 = time.time()
        self.clave = None
        self.cripto = {}                  # sentido -> cifrador
        # Lo que entrega recv() son trozos de TCP, no frames: un frame puede
        # venir partido entre dos lecturas, o varios pueden llegar juntos. Sin
        # acumular, los frames partidos se pierden -- en la primera captura se
        # perdieron cuatro bloques de 4 a 5 KB, justo los mas grandes.
        self.pendiente = {'c2s': b'', 's2c': b''}

    def guardar_clave(self, k):
        self.clave = k
        (SALIDA / (self.base + '_clave.txt')).write_text(k.hex(), encoding='utf-8')

    def anotar(self, sentido, datos):
        """Descifra, parte en sub-mensajes y los deja en orden cronologico.

        El cliente cifra con clave evolutiva (cambia en cada paquete), asi que
        hay que descifrar en secuencia y con un cifrador propio por sentido."""
        if self.clave is None:
            return
        cr = self.cripto.get(sentido)
        if cr is None:
            cr = self.cripto[sentido] = (XorEvolving(self.clave) if sentido == 'c2s'
                                         else XorStatic(self.clave))
        datos = self.pendiente[sentido] + datos
        off = 0
        while off + HDR <= len(datos):
            try:
                h = decode_header(datos, off)
            except Exception:
                break
            if h['length'] == 0:
                break
            if off + h['wire'] > len(datos):
                break              # frame incompleto: esperar mas bytes
            crudo = datos[off + HDR: off + h['wire']]
            cuerpo = cr.decrypt(crudo) if h['encrypted'] else crudo
            if h['seq'] != 0xFFFF and not h['compressed']:
                try:
                    subs, usado = submessages(cuerpo[:h['length']])
                    if usado != h['length']:
                        subs = [(-1, cuerpo[:h['length']])]
                except Exception:
                    subs = [(-1, cuerpo[:h['length']])]
                for op, b in subs:
                    self.orden.write(json.dumps({
                        't': round(time.time() - self.t0, 4),
                        'dir': sentido, 'opcode': op, 'len': len(b),
                        'hex': b[:4096].hex()}))   # 256 escondia el formato del 0x001A
                    self.orden.write(chr(10))
                self.orden.flush()
            off += h['wire']
        self.pendiente[sentido] = datos[off:]

    def cerrar(self):
        for f in (self.c2s, self.s2c, self.orden):
            try:
                f.close()
            except Exception:
                pass


def reescribir_redirect(datos, clave, host_nuevo, puerto_nuevo, aviso):
    """Cambia ip y puerto de los mensajes que mandan al cliente a otro sitio.

    Son dos:

    - **0x0004 REDIRECT**, en la sesion de login: manda al cliente del login
      al mundo.
    - **0x000C CAMBIO DE MAPA**, en la sesion de mundo:
      `[u32 stage][u16 puerto][ip asciiz]`. Celestia lo usa para mudar al
      cliente a OTRO servidor al cambiar de mapa: en la captura del West
      Playground llega con el puerto 30001 y la ip 35.236.242.228. Como no se
      reescribia, el cliente se reconectaba directo al servidor real y la
      grabacion se cortaba en seco justo al cambiar de mapa.

    Hay que rehacer el frame entero: el checksum se calcula sobre el texto en
    claro y viaja en el header, asi que no alcanza con parchear los bytes.
    """
    salida = bytearray()
    off = 0
    while off + HDR <= len(datos):
        h = decode_header(datos, off)
        if h['length'] == 0 or off + h['wire'] > len(datos):
            salida.extend(datos[off:])
            break
        crudo = datos[off + HDR: off + h['wire']]
        cuerpo = XorStatic(clave).decrypt(crudo) if h['encrypted'] else crudo
        plano = cuerpo[:h['length']]
        cambiado = False

        if not h['compressed']:
            subs, usado = submessages(plano)
            if usado == h['length']:
                nuevo = bytearray()
                for op, b in subs:
                    b = bytearray(b)
                    if op == 0x0004 and len(b) >= 25:
                        ip_vieja = bytes(b[7:23]).split(b'\x00')[0].decode('ascii', 'replace')
                        pt_viejo = struct.unpack_from('<H', b, 23)[0]
                        aviso(ip_vieja, pt_viejo)
                        b[7:23] = host_nuevo.encode('ascii')[:15].ljust(16, b'\x00')
                        struct.pack_into('<H', b, 23, puerto_nuevo)
                        cambiado = True
                    elif op == 0x000C and len(b) >= 8:
                        # Solo si trae ip de verdad: el cambio de mapa dentro
                        # del mismo servidor manda un 0x000C corto, y ese no
                        # se toca.
                        cruda = bytes(b[6:]).split(b'\x00')[0]
                        try:
                            ip_vieja = cruda.decode('ascii')
                        except UnicodeDecodeError:
                            ip_vieja = ''
                        if ip_vieja.count('.') == 3:
                            pt_viejo = struct.unpack_from('<H', b, 4)[0]
                            stage = struct.unpack_from('<I', b, 0)[0]
                            aviso(ip_vieja, pt_viejo, stage)
                            hueco = len(b) - 6
                            b[6:] = (host_nuevo.encode('ascii')[:hueco - 1]
                                     .ljust(hueco, b'\x00'))
                            struct.pack_into('<H', b, 4, puerto_nuevo)
                            cambiado = True
                    nuevo += struct.pack('<HH', len(b) + 2, op) + bytes(b)
                if cambiado:
                    plano = bytes(nuevo)

        if cambiado:
            n = len(plano)
            ck = checksum(plano, n)
            if h['encrypted']:
                pad = ((n + 0xF) >> 4) << 4
                salida += encode_header(n, h['seq'], 0x01, ck)
                salida += XorStatic(clave).encrypt(plano + b'\x00' * (pad - n))
            else:
                salida += encode_header(n, h['seq'], 0x00, ck) + plano
        else:
            salida += datos[off: off + h['wire']]
        off += h['wire']
    return bytes(salida)


class Proxy:
    def __init__(self, destino, puerto, wpuerto_local, fport):
        self.destino = destino
        self.puerto = puerto
        self.wpuerto_local = wpuerto_local
        self.fport = fport
        self.mundo_real = None      # (ip, puerto) que dijo el servidor real

    async def tuberia(self, lector, escritor, grab, sentido, transformar=None):
        f = grab.c2s if sentido == 'c2s' else grab.s2c
        try:
            while True:
                d = await lector.read(65536)
                if not d:
                    break
                f.write(d)
                f.flush()
                grab.anotar(sentido, d)
                if sentido == 's2c' and grab.clave is None:
                    try:
                        h = decode_header(d, 0)
                        if h['seq'] == 0xFFFF and not h['encrypted']:
                            k = parse_hello(d[HDR:HDR + h['length']])['key']
                            grab.guardar_clave(k)
                            log.info('  clave de sesion: ' + k.hex(' '))
                    except Exception:
                        pass
                if transformar and grab.clave is not None:
                    d = transformar(d, grab.clave)
                escritor.write(d)
                await escritor.drain()
        except (ConnectionResetError, asyncio.IncompleteReadError, BrokenPipeError):
            pass
        finally:
            try:
                escritor.close()
            except Exception:
                pass

    async def maneja(self, lector, escritor, puerto_destino, etiqueta,
                     reescribe, host_destino=None):
        # El cambio de mapa puede mandar a OTRA maquina, no solo a otro
        # puerto, asi que el host se pasa aparte en vez de usar siempre el
        # del login.
        host_destino = host_destino or self.destino
        addr = escritor.get_extra_info('peername')
        grab = Grab(etiqueta)
        log.info('[%s] cliente %s -> %s:%s  (grabando %s)',
                 etiqueta, addr, host_destino, puerto_destino, grab.base)
        try:
            rl, wl = await asyncio.open_connection(host_destino, puerto_destino)
        except Exception as e:
            log.error('[%s] no se pudo conectar al servidor real: %s', etiqueta, e)
            escritor.close()
            return

        def aviso(ip, pt, stage=None):
            self.mundo_real = (ip, pt)
            if stage is None:
                log.info('  REDIRECT del servidor: %s:%s', ip, pt)
            else:
                log.info('  CAMBIO DE MAPA al stage %s: %s:%s', stage, ip, pt)
            log.info('  reescrito a 127.0.0.1:%s (asi la sesion de mundo '
                     'tambien se graba)', self.wpuerto_local)

        t = None
        if reescribe:
            def t(d, k):
                return reescribir_redirect(d, k, '127.0.0.1',
                                           self.wpuerto_local, aviso)

        await asyncio.gather(
            self.tuberia(lector, wl, grab, 'c2s'),
            self.tuberia(rl, escritor, grab, 's2c', t),
        )
        grab.cerrar()
        log.info('[%s] cerrada -> logs/proxy/%s_*.bin', etiqueta, grab.base)

    async def correr(self):
        import functools

        s1 = await asyncio.start_server(
            functools.partial(self.maneja, puerto_destino=self.puerto,
                              etiqueta='login', reescribe=True),
            '127.0.0.1', self.puerto)
        log.info('LOGIN    127.0.0.1:%s -> %s:%s', self.puerto, self.destino, self.puerto)

        async def mundo(l, e):
            if not self.mundo_real:
                log.warning('llego una conexion de mundo sin redirect previo')
                e.close()
                return
            ip, pt = self.mundo_real
            self.destino_mundo = ip
            # reescribe=True tambien aqui: la sesion de mundo es la que
            # trae el 0x000C del cambio de mapa. Sin esto el cliente se iba
            # al servidor real en cuanto cambiabas de mapa.
            await self.maneja(l, e, puerto_destino=pt, etiqueta='mundo',
                              reescribe=True, host_destino=ip)

        s2 = await asyncio.start_server(mundo, '127.0.0.1', self.wpuerto_local)
        log.info('MUNDO    127.0.0.1:%s -> (el que diga el redirect)', self.wpuerto_local)

        # Hay servidores que usan el mismo puerto para login y para archivos
        # (Celestia: port 30000 y fport 30000). Ahi no se puede levantar un
        # segundo listener: las dos cosas entran por el de login.
        s3 = None
        if self.fport != self.puerto:
            s3 = await asyncio.start_server(
                functools.partial(self.maneja, puerto_destino=self.fport,
                                  etiqueta='archivos', reescribe=False),
                '127.0.0.1', self.fport)
            log.info('ARCHIVOS 127.0.0.1:%s -> %s:%s',
                     self.fport, self.destino, self.fport)
        else:
            log.info('ARCHIVOS comparten el puerto de login (fport = port = %s)',
                     self.fport)
        log.info('')
        log.info('Arranca el cliente. Todo queda en logs/proxy/')
        servidores = [s1, s2] + ([s3] if s3 else [])
        await asyncio.gather(*(s.serve_forever() for s in servidores))


def main():
    ap = argparse.ArgumentParser()
    # La IP del servidor no va en el repo. Se pasa con --destino o con
    # la variable de entorno AO_DESTINO.
    ap.add_argument('--destino', default=os.environ.get('AO_DESTINO'),
                    help='IP del servidor; si no se pasa se lee del server.xml')
    ap.add_argument('--puerto', type=int,
                    help='puerto de login; por defecto el del server.xml')
    ap.add_argument('--fport', type=int,
                    help='puerto de archivos; por defecto el del server.xml')
    ap.add_argument('--wpuerto', type=int, default=0,
                    help='puerto local donde se recibe la sesion de mundo; '
                         '0 = el de login mas uno')
    ap.add_argument('--server-xml',
                    help='ruta al server.xml del cliente; se edita dejando copia .bak')
    ap.add_argument('--restaurar', action='store_true',
                    help='devuelve el server.xml a su version original y sale')
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

    if a.server_xml:
        p = pathlib.Path(a.server_xml)
        bak = p.with_suffix(p.suffix + '.bak')
        # Cada servidor privado usa sus propios puertos: AngelWar escucha en
        # 24100/12007, no en 30000/30007. Salen del server.xml, asi que no
        # hace falta que los averigue nadie.
        fuente = bak if (bak.exists() and not a.restaurar) else p
        datos = re.search(
            r'ip="([^"]+)"\s+port="(\d+)"[^>]*?fip="([^"]+)"\s+fport="(\d+)"',
            fuente.read_text(encoding='utf-8-sig'))
        if datos:
            a.destino = a.destino or datos.group(1)
            a.puerto = a.puerto or int(datos.group(2))
            a.fport = a.fport or int(datos.group(4))
            if datos.group(3) != datos.group(1):
                log.warning('fip (%s) no es la misma ip que port (%s)',
                            datos.group(3), datos.group(1))
        elif not a.restaurar:
            log.error('no pude leer ip/port de %s', p.name)
            return
        if a.restaurar:
            if bak.exists():
                p.write_bytes(bak.read_bytes())
                log.info('server.xml restaurado desde %s', bak.name)
            else:
                log.error('no hay copia de seguridad %s', bak.name)
            return
        if not bak.exists():
            bak.write_bytes(p.read_bytes())
            log.info('copia de seguridad: %s', bak)
        t = p.read_text(encoding='utf-8-sig')
        t = t.replace('ip="' + a.destino + '"', 'ip="127.0.0.1"')
        t = t.replace('fip="' + a.destino + '"', 'fip="127.0.0.1"')
        p.write_text(t, encoding='utf-8-sig')
        log.info('server.xml apuntado a 127.0.0.1 (original en %s)', bak.name)

    if not a.destino or not a.puerto or not a.fport:
        log.error('falta la IP o los puertos: pasalos con --destino/--puerto/'
                  '--fport o usa --server-xml')
        return
    if not a.wpuerto:
        a.wpuerto = a.puerto + 1
    try:
        asyncio.run(Proxy(a.destino, a.puerto, a.wpuerto, a.fport).correr())
    except KeyboardInterrupt:
        log.info('proxy detenido')


if __name__ == '__main__':
    main()
