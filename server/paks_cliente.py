"""Las tablas del cliente (setting/*.xml) sacadas de sus propios .pak.

`extracted_paks/` no va en el repo (3,6 GB y es material de IGG), pero cada
vez mas modulos leen sus xml de ahi (house_services, fusion, logros, bonos,
pase...). En una instalacion limpia eso reventaba: un jugador del repo
publico no podia usar una escritura de casa porque house_services.xml_rows
recorria una carpeta que no existe (21/10/2026).

Al arrancar, si falta, se crea `extracted_paks/update26/setting/` con la
version VIGENTE de cada archivo de setting/ (el del pak de numero mas alto
que lo trae, igual que el cliente), leida del cliente instalado. Se queda solo
en esa maquina: la carpeta esta en .gitignore.
"""
import logging
import pathlib
import re
import struct
import zlib

log = logging.getLogger('paks_cliente')

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DESTINO = RAIZ / 'extracted_paks' / 'update26'
MARCA = RAIZ / 'extracted_paks' / '.desde_cliente'


def numero(nombre: str) -> int:
    """data1 < update < update2 < ... < update26 (ver tools/paks.py)."""
    n = pathlib.Path(nombre).stem.lower()
    if n == 'data1':
        return -1
    if n == 'update':
        return 0
    m = re.fullmatch(r'update(\d+)', n)
    return int(m.group(1)) if m else -2


def _directorio(data: bytes):
    """[(nombre, crc, csize, usize, offset)] del pak (formato OD\\x05\\x06)."""
    eocd = bytearray(data[-22:])
    if eocd[:4] != b'OD\x05\x06':
        return []
    for i in range(4, 22):
        eocd[i] ^= (3 * i - 91) & 0xFF
    _, _, _, _, _, cd_off, _ = struct.unpack('<HHHHIIH', eocd[4:22])
    # El tamano comprimido es un u16 y en los paks grandes se desborda: se
    # descomprime hasta el final y zlib para solo donde acaba el bloque.
    raw = bytearray(data[cd_off + 4: len(data) - 22])
    raw[0] ^= 0x7A
    cd = zlib.decompressobj().decompress(bytes(raw))
    out, off = [], 0
    while off + 46 <= len(cd):
        (_, _, _, _, _, _, _, crc, csize, usize, fn_len, ex_len, cm_len,
         _, _, _, lhoff) = struct.unpack_from('<IHHHHHHIIIHHHHHII', cd, off)
        nombre = cd[off + 46: off + 46 + fn_len].decode('ascii', errors='ignore')
        out.append((nombre.replace('/', '\\'), crc, csize, usize, lhoff))
        off += 46 + fn_len + ex_len + cm_len
    return out


def asegurar_extraidos(ruta_cliente=None) -> int:
    """Crea extracted_paks/update26/setting desde el cliente si no existe.
    Devuelve cuantos archivos escribio."""
    if (RAIZ / 'extracted_paks').is_dir() and not MARCA.exists():
        return 0                        # la carpeta de verdad (la del desarrollador)
    if ruta_cliente is None:
        try:
            import cliente_local
            ruta_cliente = cliente_local.ruta_cliente()
        except Exception:
            log.exception('no se encontro el cliente')
            return 0
    ruta_cliente = pathlib.Path(ruta_cliente)
    paks = sorted((p for p in ruta_cliente.glob('*') if p.suffix.lower() == '.pak'
                   and numero(p.name) >= -1), key=lambda p: numero(p.name))
    if not paks:
        log.warning('sin extracted_paks y sin .pak del cliente en %s: '
                    'las tablas del cliente no estaran disponibles', ruta_cliente)
        return 0
    vigente = {}
    for pak in paks:
        fuente = pak.with_name(pak.name + '.bak')      # el original, sin parches nuestros
        fuente = fuente if fuente.exists() else pak
        try:
            for nombre, crc, csize, usize, lhoff in _directorio(fuente.read_bytes()):
                if nombre.upper().startswith('SETTING\\'):
                    vigente[nombre.lower()] = (fuente, crc, csize, usize, lhoff)
        except Exception:
            log.exception('no se pudo leer %s', pak)
    escritos = 0
    cache = {}
    for nombre, (fuente, crc, csize, usize, lhoff) in vigente.items():
        destino = DESTINO / pathlib.PureWindowsPath(nombre)
        if destino.exists() and destino.stat().st_size == usize:
            continue
        data = cache.get(fuente) or cache.setdefault(fuente, fuente.read_bytes())
        try:
            contenido = zlib.decompress(data[lhoff: lhoff + csize], -15)
        except Exception:
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(contenido)
        escritos += 1
    MARCA.parent.mkdir(parents=True, exist_ok=True)
    MARCA.write_text(str(ruta_cliente), encoding='utf-8')
    log.info('tablas del cliente: %d archivos de setting/ sacados de %s', escritos, ruta_cliente)
    return escritos
