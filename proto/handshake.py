"""
Handshake (Hello) del protocolo Angels Online.

Derivado de sub_81EED0 / sub_81FAD0 / sub_81FC10 / sub_81FB70 en el binario
del cliente, y verificado contra capturas reales de ambos servidores.

El Hello viaja en un frame con seq=0xFFFF, SIN cifrar. Su cuerpo es un
sub-mensaje normal: [LE16 sub_len][ ... ].

Hay DOS variantes, y el cliente elige segun tenga o no un objeto cripto ya
instalado (sub_81EED0):

  MINIMA (la que usa IGG) -- 20 bytes de sub-mensaje:
      [LE32 key_len=16][16 bytes de clave]
    El cliente hace SetKey sobre sus cifradores internos.
    SetKey recibe la longitud en BITS: 8*16 = 128.

  CON CIFRADOR EMBEBIDO (la que usa el servidor privado) -- 132 bytes:
      [LE32 key_len=16][16 bytes de clave]
      [LE32 code_len=80][80 bytes de codigo maquina x86]
      [LE32 ctx_len=24][LE32 1][LE32 16][16 bytes]
    El cliente vuelve ejecutable ese codigo (sub_828170) y lo usa COMO
    funcion de descifrado. El servidor le manda el algoritmo, no solo la clave.

Para nuestro servidor conviene la MINIMA: esta atestiguada en produccion real
y no requiere generar codigo maquina.

Cifradores (confirmados al 100% sobre 150k frames reales):
    S -> C : XOR estatico de 16 bytes
    C -> S : XOR con clave evolutiva (cada DWORD += padded_len por paquete)
Ambos derivan de sub_81FC90/sub_81FD10: XOR por DWORD con mascara (n_dwords-1),
o sea la clave debe medir una potencia de 2 en dwords -- 16 bytes = 4 dwords.
"""
import struct

SEQ_HELLO = 0xFFFF
KEY_LEN = 16


def build_hello(key: bytes) -> bytes:
    """Hello minimo (estilo IGG). Devuelve el PAYLOAD del frame seq=0xFFFF."""
    if len(key) != KEY_LEN:
        raise ValueError(f"la clave debe medir {KEY_LEN} bytes, mide {len(key)}")
    sub = struct.pack('<I', KEY_LEN) + key
    return struct.pack('<H', len(sub)) + sub


def parse_hello(payload: bytes) -> dict:
    """Lee un Hello de cualquiera de las dos variantes."""
    sub_len = struct.unpack_from('<H', payload, 0)[0]
    a2 = payload[2:2 + sub_len]
    key_len = struct.unpack_from('<I', a2, 0)[0]
    out = {'sub_len': sub_len, 'key_len': key_len,
           'key': bytes(a2[4:4 + key_len]), 'key_bits': 8 * key_len,
           'variante': 'minima', 'code': None, 'ctx': None}
    off = 4 + key_len
    if len(a2) > off + 4:
        code_len = struct.unpack_from('<I', a2, off)[0]
        out['code'] = bytes(a2[off + 4: off + 4 + code_len])
        off += 4 + code_len
        if len(a2) >= off + 4:
            ctx_len = struct.unpack_from('<I', a2, off)[0]
            out['ctx'] = bytes(a2[off + 4: off + 4 + ctx_len])
        out['variante'] = 'cifrador embebido'
    return out


class XorStatic:
    """S->C. Equivale a sub_81FC90: XOR por DWORD, clave repetida."""
    def __init__(self, key): self.k = bytes(key)
    def apply(self, d): return bytes(b ^ self.k[i % KEY_LEN] for i, b in enumerate(d))
    encrypt = decrypt = apply


class XorEvolving:
    """C->S. Igual, pero tras cada paquete cada DWORD de la clave += padded_len."""
    def __init__(self, key): self.k = bytearray(key)
    def _step(self, n):
        for i in range(0, KEY_LEN, 4):
            struct.pack_into('<I', self.k, i,
                (struct.unpack_from('<I', self.k, i)[0] + n) & 0xFFFFFFFF)
    def apply(self, d):
        o = bytes(b ^ self.k[i % KEY_LEN] for i, b in enumerate(d))
        self._step(len(d))
        return o
    encrypt = decrypt = apply
