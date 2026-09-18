"""
Creacion de personaje y actualizacion de ranura.

El cliente manda 0x0003 (57 B) al confirmar el dialogo "Character Info", y
espera 0x0001 con la ficha de la ranura creada.

Paquete 0x0003 CREAR, medido de una sesion real del cliente:

    +0   LE32   indice de ranura (0..2)
    +4   LE16   ?
    +6   char   nombre, terminado en nulo
    +20  LE32   ?
    +32..47     basura de pila cuando los campos opcionales quedan en
                "Choose." (Place/Job/Face/Pty). No se interpretan.

Valores del personaje nuevo: nivel 1 y mapa 41 "Angel Lyceum", que es el
nombre que usan las propias tarjetas del cliente ("Angel Lyceum ID Card") y
figura asi en stage.xml. NO se inventan stats.
"""
import json
import struct
import pathlib

MAPA_INICIAL = 51                 # Guide Palace (stage.name en content.db)
# MEDIDO, no deducido. La ficha 0x0002 que el servidor privado le mando a un
# personaje recien creado trae tile=(82,83) en +8/+12, y los tres NPC_SPAWN
# del tutorial caen alrededor: Interface Tutor (80,85) a 2 tiles, Angel
# Raphael (88,87) a 6, Angel Aide (96,85) a 14. Antes usaba el centro
# geometrico del mapa (185,78), que queda a 97 tiles del NPC mas cercano:
# por eso el jugador aparecia solo, fuera del rango de vista de todos.
TILE_INICIAL = tuple(int(x) for x in
                     __import__('os').environ.get('AO_TILE', '82,83').split(','))          # "Guide Palace" segun stage.xml
NIVEL_INICIAL = 1
CLASE_INICIAL = 0          # "Novice" segun class.xml

# Stats iniciales REALES, tomados de capturas de pantalla de un personaje
# nivel 1 recien creado en el servidor Global y en uno privado: la tarjeta de
# seleccion muestra HP 205/205 y MP 154/154, y el mapa inicial es
# "Guide Palace" (id 51), no "Angel Lyceum" (41) como puse antes.
HP_INICIAL = 296
MP_INICIAL = 218


def parsear_creacion(cuerpo: bytes) -> dict:
    ranura = struct.unpack_from('<I', cuerpo, 0)[0] if len(cuerpo) >= 4 else 0
    fin = cuerpo.find(b'\x00', 6)
    nombre = cuerpo[6:fin if fin > 6 else 6].decode('ascii', 'replace').strip()
    return {'ranura': ranura & 0xFF, 'nombre': nombre}


# Kit con el que arranca un personaje. Los id salen de item.xml y estan
# cruzados campo a campo contra las capturas de pantalla del cliente: peso 10,
# no comerciable, no almacenable, nivel minimo 1 y 5, "7 free slots" y la lista
# de contenido del Growth Box coinciden las seis veces.
#
# La ropa del cuerpo esta CONFIRMADA en el trafico real: el 0x001B que el
# servidor privado manda al equipar lleva el item 26 con su id de instancia.
#
# La Newborn Gift Box depende de la clase, por eso va aparte:
#     1944  Archer y Productor
#     1948  Guerrero
#     1952  Mago
# Se entrega al elegir clase, no al crear el personaje (el tooltip pide nivel 5).
CAJA_POR_CLASE = {'arquero': 1944, 'productor': 1944,
                  'guerrero': 1948, 'mago': 1952}

ROPA_INICIAL = {
    'cuerpo':  26,      # Students' Uniform  -- va equipada, da +10 de defensa
    'guantes': 28,      # Students' Gloves
    'zapatos': 30,      # Students' shoes
}
INVENTARIO_INICIAL = [
    20103,              # Level 1-10 Growth Box
]

# OJO: todavia no se entregan. Falta poder CONSTRUIR el 0x001B (el contenido
# del contenedor); hoy server/equipo.py solo sabe reproducir los dos estados
# que se capturaron. Ver docs/01_HECHOS_VERIFICADOS.md.


def personaje_nuevo(nombre: str, ranura: int, char_id: int) -> dict:
    return {
        'nombre': nombre,
        'char_id': char_id,
        'ranura': ranura,
        'nivel': NIVEL_INICIAL,
        'class_id': CLASE_INICIAL,
        'stage_id': MAPA_INICIAL,
        'hp': HP_INICIAL,
        'hp_max': HP_INICIAL,
        'mp': MP_INICIAL,
        'mp_max': MP_INICIAL,
        # Apariencia copiada de una ficha REAL capturada de un servidor
        # vivo. Con todo en cero el cliente no puede armar la ruta del
        # sprite del personaje y manda basura de pila en su 0x0006.
        'apariencia': [0, 0, 0, 8, 8],
        # PROVISIONAL, y conviene decirlo: no es el punto de aparicion real.
        # La cabecera de map/map051.mpc dice que Guide Palace mide 371x156
        # tiles, asi que (0,0) es la esquina y con toda probabilidad no se
        # puede caminar ahi. Esto es el centro geometrico -- deducido del
        # tamano del mapa, no medido de un servidor. Se ajusta con AO_TILE.
        'tile_x': TILE_INICIAL[0],
        'tile_y': TILE_INICIAL[1],
        'habilidades': [],
        'barra': [],
        'quests': [],
        # Arranca con la ropa puesta en la ranura del cuerpo. Es lo que se ve
        # en el trafico real: el 0x001B del privado mueve el item 26 desde la
        # ranura 2, o sea que ahi estaba.
        # Ranura 0 = el oro, 2 = el cuerpo, de la 20 en adelante la mochila.
        # SOLO estos dos. Se probo entregar tambien 28, 30 y 20103 y el cliente
        # no los mostro: dejo las ranuras 20, 21 y 22 vacias en pantalla
        # mientras el servidor las creia ocupadas, o sea que del 0x001A de 467
        # bytes no leyo las cinco entradas. La suposicion de que el tamano
        # fuera 4 + 86*N + 33 para cualquier N era falsa, o falta algun campo
        # que diga cuantas entradas vienen. Hasta saberlo, solo lo comprobado.
        'inventario': {
            '0': 1,                           # Gold
            '2': ROPA_INICIAL['cuerpo'],      # 26 Students' Uniform, puesta
        },
    }


def respuesta_creacion(ranura: int, p: dict) -> bytes:
    """Sub-mensaje 0x0001: el cliente copia 144 B desde el offset 4 a la
    ficha de la ranura y vuelve a dibujar la pantalla de seleccion."""
    from lista_personajes import _ficha
    cuerpo = bytearray(152)              # [LE16 error][ficha de 147 B + extra]
    # cuerpo[0:2] = 0  -> exito
    _ficha(cuerpo, 2, ranura, p)
    return struct.pack('<H', 0x0001) + bytes(cuerpo)


def guardar(usuario: str, p: dict, archivo: pathlib.Path):
    d = json.loads(archivo.read_text(encoding='utf-8'))
    c = d['cuentas'].setdefault(usuario, {'password': '', 'personajes': []})
    c['personajes'] = [x for x in c['personajes'] if x.get('ranura') != p['ranura']]
    c['personajes'].append(p)
    c['personajes'].sort(key=lambda x: x.get('ranura', 0))
    archivo.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding='utf-8')
