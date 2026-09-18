"""
Servidor de LOGIN (el puerto al que apunta server.xml).

Flujo real, reconstruido de una captura del servidor de login de IGG
(209.151.154.242:24100):

    cliente -> AUTH de 73 B   usuario en TEXTO PLANO, terminado en nulo y
                              rellenado a multiplo de 4; la contrasena va
                              cifrada en un bloque opaco
    servidor -> 0x000C        MOTD: [LE32 largo][texto]
    servidor -> 0x0000        lista de personajes
    servidor -> 0x0004        REDIRECT: ip en texto + puerto del mundo

Nota sobre compresion: el servidor real manda esa respuesta comprimida con
LZO1X (flags=0x81). **Nosotros la mandamos sin comprimir** (flags=0x00): el bit
7 de flags le dice al cliente si tiene que descomprimir, asi que no hace falta
implementar el compresor, solo el descompresor para leer capturas.
"""
import struct
import pathlib

PLANTILLAS = pathlib.Path(__file__).parent / 'plantillas'

# offsets dentro de la plantilla descomprimida, medidos sobre la captura
OFF_MOTD_LARGO = 8
OFF_MOTD_TEXTO = 12
OFF_NOMBRE_1 = 76
OFF_NOMBRE_2 = 101
LARGO_NOMBRE = 12          # campo de nombre: "Karma" + nulos


def respuesta_login(personajes=None, texto_motd=None, cuenta='',
                    ranuras=3, subcanal=2) -> bytes:
    """Payload de la respuesta de login: MOTD + datos de cuenta.

    Se CONSTRUYE desde cero (ver lista_personajes.py), no se parchea una
    plantilla capturada. Parchear a ciegas costo tres crashes distintos.

    El servidor real manda esto comprimido con LZO1X (flags=0x81); nosotros
    lo mandamos sin comprimir, que el cliente acepta igual porque el bit 7
    de flags le indica si debe descomprimir.
    """
    from lista_personajes import bloque_cuenta
    # SIN MOTD: el servidor real no manda 0x000C en el login. Se comprobo
    # sobre una captura en vivo: solo tres frames -- HELLO, 0x0000 y 0x0004,
    # cada uno en su propio frame y todos con seq=1.
    c = bloque_cuenta(personajes or [], cuenta=cuenta,
                      ranuras=ranuras, subcanal=subcanal)
    return struct.pack('<HH', len(c) + 2, 0x0000) + c


def redirect(ip: str, puerto: int) -> bytes:
    """Sub-mensaje 0x0004: ip en texto + puerto. Cuerpo de 30 B.

       +0  [7 B opacos]
       +7  ip terminada en nulo (16 B)
       +23 LE16 puerto
       +25 [5 B cero]
    """
    cuerpo = bytearray(30)
    cuerpo[2:6] = b'\xaa\x75\xb1\x3f'          # tal como en la captura
    b = ip.encode('ascii')[:15]
    cuerpo[7:7 + len(b)] = b
    struct.pack_into('<H', cuerpo, 23, puerto)
    return struct.pack('<H', 0x0004) + bytes(cuerpo)


def usuario_de_auth(cuerpo: bytes) -> str:
    """Extrae el usuario del AUTH de 73 B: cadena en claro terminada en nulo."""
    fin = cuerpo.find(b'\x00')
    return cuerpo[:fin if fin >= 0 else 0].decode('ascii', 'replace')


def respuesta_error(codigo: int = 1) -> bytes:
    """Respuesta de login rechazado: 0x0000 con codigo de error no-cero.

    El campo [2-3] del bloque de cuenta es el codigo de error; un valor
    distinto de cero hace que el cliente muestre el cartel correspondiente.
    """
    from lista_personajes import TAM_CUENTA
    a = bytearray(TAM_CUENTA)
    struct.pack_into('<H', a, 2, codigo)
    cuerpo = bytes(a[2:])
    return struct.pack('<HH', len(cuerpo) + 2, 0x0000) + cuerpo
