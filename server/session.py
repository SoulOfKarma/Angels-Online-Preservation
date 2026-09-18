"""
Estado y maquinaria de una conexion.

Toda la capa de protocolo esta validada contra capturas reales:
  - framing       : 168.570/168.570 frames re-codificados identicos
  - handshake     : build_hello() reproduce el Hello de IGG byte a byte
  - sub-mensajes  : 24/24 esquemas, 97,6% del corpus

Configuracion elegida (las tres atestiguadas en produccion real):
  - Hello en variante minima con clave de 16 bytes
  - S->C en texto plano (el servidor privado lo hace y el cliente lo acepta)
  - C->S descifrado con XOR evolutivo a partir de esa clave
"""
import os
import sys
import pathlib
import logging
import collections

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'proto'))
from framing import HDR, decode_header, build_frame, submessages, pack_submessages, SEQ_HELLO
from handshake import build_hello, XorEvolving
from codec import Msg
import messages  # noqa: registra los esquemas

log = logging.getLogger('session')

PLANTILLA_HELLO = pathlib.Path(__file__).parent / 'plantillas' / 'hello_embebido.bin'


class Session:
    def __init__(self, addr, key=None):
        self.addr = addr
        self.key = key if key is not None else os.urandom(16)
        self.recv_crypto = XorEvolving(self.key)
        self.seq = 1
        self.buf = bytearray()
        self.salida = []                       # frames listos para enviar
        self.desconocidos = collections.Counter()
        self.vistos = collections.Counter()
        self.entity_id = None
        self.personaje = None
        self.rol = 'mundo'
        self.usuario = None
        self.puerto = None
        self.cerrar_tras_redirect = False

    # ---------------------------------------------------------------- salida

    def _next_seq(self):
        # El SERVIDOR no incrementa: manda siempre seq=1. Medido en 2.730 de
        # 2.731 frames reales, y confirmado en la captura del proxy (los dos
        # frames del login usan seq=1). Solo el CLIENTE incrementa.
        return 1

    def enviar_hello(self):
        # Se manda la variante CON CIFRADOR EMBEBIDO, no la minima.
        # Comparando frame por frame contra una captura de un servidor vivo,
        # los tres frames del login coincidian salvo este: el real manda 134 B
        # (cifrador embebido, clave en cero) y yo mandaba 22 B (minima, clave
        # aleatoria). La variante minima la usaba IGG; este cliente espera la
        # otra, que le hace instalar el cifrador que el servidor le envia.
        # Con clave en cero, el XOR es identidad y el trafico queda en claro.
        pl = PLANTILLA_HELLO.read_bytes()
        self.key = bytes(16)
        self.recv_crypto = XorEvolving(self.key)
        self.salida.append(build_frame(pl, SEQ_HELLO))

    def enviar(self, *submsgs):
        """submsgs: bytes ya serializados por Msg.build (opcode incluido)."""
        if not submsgs:
            return
        self.salida.append(build_frame(pack_submessages(submsgs), self._next_seq()))

    def enviar_crudo(self, payload):
        """Envia un payload ya armado como cadena de sub-mensajes.

        El servidor de login manda su respuesta asi (y el real la comprime con
        LZO1X; nosotros la mandamos sin comprimir, que el cliente acepta igual)."""
        self.salida.append(build_frame(payload, self._next_seq()))

    def drenar(self):
        out = b''.join(self.salida)
        self.salida.clear()
        return out

    # ---------------------------------------------------------------- entrada

    def alimentar(self, data: bytes):
        """Acumula bytes del cliente y devuelve [(opcode, cuerpo)] completos."""
        self.buf.extend(data)
        recibidos = []
        while len(self.buf) >= HDR:
            h = decode_header(self.buf, 0)
            if h['length'] == 0 or h['length'] > 0x10000:
                log.warning(f"[{self.addr}] longitud invalida {h['length']}, se descarta 1 byte")
                del self.buf[0]
                continue
            if len(self.buf) < h['wire']:
                break                          # frame incompleto, esperar mas
            cuerpo = bytes(self.buf[HDR:h['wire']])
            del self.buf[:h['wire']]
            if h['encrypted']:
                cuerpo = self.recv_crypto.decrypt(cuerpo)
            if h['compressed']:
                log.warning(f"[{self.addr}] frame comprimido: sin soporte todavia")
                continue
            msgs, _ = submessages(cuerpo[:h['length']])
            recibidos.extend(msgs)
        return recibidos

    # ---------------------------------------------------------------- dispatch

    def parsear(self, opcode, cuerpo):
        """Devuelve el dict del mensaje, o None si no hay esquema."""
        for rev in ('*', 'privado', 'igg'):
            m = Msg.registry.get((opcode, 'c2s', rev))
            # Alcance POR SERVICIO: un esquema declarado para ciertos puertos
            # no se aplica en otros. El mismo opcode significa cosas distintas
            # en login, mundo y archivos -- 0x0004 es movimiento en el mundo
            # y estado de interfaz en el login.
            if m is not None and m.puertos and self.puerto not in m.puertos:
                continue
            if m:
                try:
                    return m, m.parse(cuerpo)
                except Exception as e:
                    log.debug(f"[{self.addr}] 0x{opcode:04X} no parsea: {e}")
                    return m, None
        return None, None
