"""
Servidor de avatares (fport en server.xml, 21238).

Habla el MISMO protocolo que el resto: header ofuscado de 6 B + sub-mensajes.
Reconstruido de una captura real (puerto 30007 del servidor privado):

    cliente  -> 0x0000 : [LE32 ?][timestamp "0000-00-00 00:00:00"\0][nombre.png\0]
    servidor -> 0x0002 : [LE32 ?][nombre.png\0][relleno][datos PNG]

Los avatares son los retratos que los jugadores suben. Si el archivo no
existe, se responde igual pero sin datos: el cliente usa el retrato por
defecto en vez de quedarse esperando.
"""
import re
import pathlib
import struct

DIR_AVATARES = pathlib.Path(__file__).parent.parent / 'data' / 'avatares'
RE_PNG = re.compile(rb'[\w\.\-]+\.png')


def nombre_pedido(cuerpo: bytes) -> str:
    m = RE_PNG.search(cuerpo)
    return m.group().decode('ascii', 'replace') if m else ''


def respuesta_avatar(cuerpo_pedido: bytes) -> bytes:
    """Sub-mensaje 0x0002 con el avatar, o sin datos si no existe."""
    nombre = nombre_pedido(cuerpo_pedido)
    cab = cuerpo_pedido[:4] if len(cuerpo_pedido) >= 4 else bytes(4)
    datos = b''
    if nombre:
        f = DIR_AVATARES / nombre
        if f.exists():
            datos = f.read_bytes()
        else:
            # Si el avatar no existe se manda uno por defecto en vez de una
            # respuesta vacia. El cliente se CONGELA al entrar al mundo sin
            # tocar la red, y una de las pocas cosas que espera en ese momento
            # es su propio retrato; una respuesta sin datos podria dejarlo
            # esperando para siempre.
            d = pathlib.Path(__file__).parent / 'plantillas' / 'avatar_por_defecto.png'
            if d.exists():
                datos = d.read_bytes()
    nb = nombre.encode('ascii', 'replace') + b'\x00'
    # El cuerpo mide 69 bytes, medido contra una captura real (yo generaba 67
    # y quedaba 2 bytes corto).
    relleno = bytes(max(0, 69 - 4 - len(nb)))
    return struct.pack('<H', 0x0002) + cab + nb + relleno + datos


def guardar_avatar(cuerpo: bytes) -> str:
    """El cliente tambien SUBE su retrato (opcode 0x000B en el mundo)."""
    nombre = nombre_pedido(cuerpo)
    if not nombre:
        return ''
    i = cuerpo.find(b'\x89PNG')
    if i < 0:
        return ''
    DIR_AVATARES.mkdir(parents=True, exist_ok=True)
    (DIR_AVATARES / nombre).write_bytes(cuerpo[i:])
    return nombre
