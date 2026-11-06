"""Leer, extraer y construir .pak del cliente (formato OD\\x05\\x06).

El lector viejo de server/cliente_local.py solo usaba el u16 bajo del tamano
del indice comprimido. Con los paks modernos de Taiwan (y Eternal 28) el
indice pasa de 64 KB y hay que combinar los dos u16: lo | (hi << 16).

    python -I tools/pak_tool.py list     <pak>
    python -I tools/pak_tool.py verify   <pak>
    python -I tools/pak_tool.py extract  <pak> <destino>
    python -I tools/pak_tool.py manifest <pak> <salida.json>
    python -I tools/pak_tool.py build    <carpeta> <salida.pak>

Estructura (medida, ver docs/MIGRACION_TAIWAN_UPDATE32.md):
  datos DEFLATE crudo de cada archivo, en lhoff
  'OD\\x05\\x06' + indice zlib (primer byte ^ 0x7A)    en cd_offset
  pie de 22 bytes: 'OD\\x05\\x06' + 18 bytes ^ (3*i - 91)
"""
import hashlib
import json
import pathlib
import struct
import sys
import zlib

FIRMA = b'OD\x05\x06'
CD_FMT = '<IHHHHHHIIIHHHHHII'      # 46 bytes, como el central directory de ZIP


def _xor_pie(pie: bytearray) -> bytearray:
    for i in range(4, 22):
        pie[i] ^= (3 * i - 91) & 0xFF
    return pie


def leer_indice(data: bytes):
    """Devuelve (entradas, cd_offset). Cada entrada es un dict."""
    pie = bytearray(data[-22:])
    if pie[:4] != FIRMA:
        raise ValueError('sin firma OD\\x05\\x06 al final')
    _xor_pie(pie)
    lo, hi, n_a, n_b, cd_usize, cd_offset, _ = struct.unpack('<HHHHIIH', pie[4:22])
    cd_csize = lo | (hi << 16)
    if cd_offset + 4 + cd_csize > len(data):
        raise ValueError('indice fuera del archivo')
    raw = bytearray(data[cd_offset + 4: cd_offset + 4 + cd_csize])
    raw[0] ^= 0x7A
    cd = zlib.decompress(bytes(raw))
    if len(cd) != cd_usize:
        raise ValueError('indice: tamano %d != %d' % (len(cd), cd_usize))
    entradas = []
    off = 0
    while off < len(cd):
        (sig, made, need, flags, method, mtime, mdate, crc, csize, usize,
         fn_len, ex_len, cm_len, disk, iattr, eattr, lhoff) = struct.unpack_from(CD_FMT, cd, off)
        nombre_b = cd[off + 46: off + 46 + fn_len]
        try:
            nombre = nombre_b.decode('ascii')
        except UnicodeDecodeError:
            nombre = nombre_b.decode('big5', errors='replace')
        if lhoff + csize > cd_offset:
            raise ValueError('%s: datos fuera de la zona de datos' % nombre)
        entradas.append(dict(nombre=nombre, crc=crc, csize=csize, usize=usize,
                             lhoff=lhoff, method=method, flags=flags,
                             mtime=mtime, mdate=mdate, made=made, need=need,
                             eattr=eattr))
        off += 46 + fn_len + ex_len + cm_len
    if len(entradas) not in (n_a, n_b):
        raise ValueError('contadores %d/%d, leidas %d' % (n_a, n_b, len(entradas)))
    return entradas, cd_offset


def leer_entrada(data: bytes, e: dict, verificar: bool = True) -> bytes:
    bloque = data[e['lhoff']: e['lhoff'] + e['csize']]
    raw = zlib.decompress(bloque, -15) if e['method'] == 8 else bytes(bloque)
    if verificar:
        if len(raw) != e['usize']:
            raise ValueError('%s: usize %d != %d' % (e['nombre'], len(raw), e['usize']))
        if zlib.crc32(raw) & 0xFFFFFFFF != e['crc']:
            raise ValueError('%s: CRC invalido' % e['nombre'])
    return raw


def ruta_segura(destino: pathlib.Path, nombre: str) -> pathlib.Path:
    partes = [p for p in nombre.replace('\\', '/').split('/') if p not in ('', '.')]
    if not partes or '..' in partes or ':' in partes[0]:
        raise ValueError('ruta insegura: %r' % nombre)
    final = destino.joinpath(*partes).resolve()
    if destino.resolve() not in final.parents:
        raise ValueError('ruta fuera del destino: %r' % nombre)
    return final


def extraer(pak: pathlib.Path, destino: pathlib.Path) -> int:
    data = pak.read_bytes()
    entradas, _ = leer_indice(data)
    vistos = {}
    for e in entradas:
        f = ruta_segura(destino, e['nombre'])
        k = str(f).lower()
        if k in vistos:
            print('AVISO colision por mayusculas: %s / %s' % (vistos[k], e['nombre']))
        vistos[k] = e['nombre']
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(leer_entrada(data, e))
    return len(entradas)


def manifiesto(pak: pathlib.Path) -> dict:
    data = pak.read_bytes()
    entradas, _ = leer_indice(data)
    filas = []
    for e in entradas:
        raw = leer_entrada(data, e)
        filas.append(dict(ruta=e['nombre'].replace('/', '\\').lower(),
                          nombre=e['nombre'], csize=e['csize'], usize=e['usize'],
                          crc='%08X' % e['crc'], lhoff=e['lhoff'],
                          sha256=hashlib.sha256(raw).hexdigest()))
    return dict(pak=pak.name, tamano=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
                entradas=len(filas), archivos=filas)


def construir(archivos, salida: pathlib.Path) -> int:
    """archivos: lista de (nombre_interno, bytes). Escribe un pak nuevo."""
    datos = bytearray()
    cd = bytearray()
    for nombre, raw in archivos:
        co = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15)
        comp = co.compress(raw) + co.flush()
        nb = nombre.replace('/', '\\').encode('ascii')
        cd += struct.pack(CD_FMT, 0x02014B50, 20, 20, 0, 8, 0, 0,
                          zlib.crc32(raw) & 0xFFFFFFFF, len(comp), len(raw),
                          len(nb), 0, 0, 0, 0, 0x20, len(datos)) + nb
        datos += comp
    cd_comp = bytearray(zlib.compress(bytes(cd)))
    cd_comp[0] ^= 0x7A
    n = len(archivos)
    if n > 0xFFFF:
        raise ValueError('demasiadas entradas para un pak: %d' % n)
    pie = bytearray(FIRMA + struct.pack('<HHHHIIH', len(cd_comp) & 0xFFFF,
                                        len(cd_comp) >> 16, n, n, len(cd),
                                        len(datos), 0))
    salida.write_bytes(bytes(datos) + FIRMA + bytes(cd_comp) + bytes(_xor_pie(pie)))
    return n


def actualizar(pak: pathlib.Path, nuevos: dict) -> tuple:
    """Reescribe pak reemplazando y anadiendo {nombre_interno: bytes}.

    Las entradas que no se tocan conservan su bloque comprimido tal cual.
    Los nombres se comparan sin mayusculas y con '\\'. Devuelve
    (reemplazados, anadidos)."""
    data = pak.read_bytes()
    entradas, _ = leer_indice(data)
    pend = {k.replace('/', '\\').lower(): (k.replace('/', '\\'), v) for k, v in nuevos.items()}
    datos, cd = bytearray(), bytearray()
    n_rep = 0

    def _entrada(nombre, crc, comp, usize):
        nb = nombre.encode('ascii')
        return struct.pack(CD_FMT, 0x02014B50, 20, 20, 0, 8, 0, 0, crc, len(comp),
                           usize, len(nb), 0, 0, 0, 0, 0x20, len(datos)) + nb

    def _comprimir(raw):
        co = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15)
        return co.compress(raw) + co.flush()

    for e in entradas:
        k = e['nombre'].replace('/', '\\').lower()
        if k in pend:
            raw = pend.pop(k)[1]
            comp = _comprimir(raw)
            cd += _entrada(e['nombre'], zlib.crc32(raw) & 0xFFFFFFFF, comp, len(raw))
            n_rep += 1
        else:
            comp = data[e['lhoff']: e['lhoff'] + e['csize']]
            if e['method'] != 8:
                comp = _comprimir(comp)
            cd += _entrada(e['nombre'], e['crc'], comp, e['usize'])
        datos += comp
    for nombre, raw in pend.values():
        comp = _comprimir(raw)
        cd += _entrada(nombre, zlib.crc32(raw) & 0xFFFFFFFF, comp, len(raw))
        datos += comp
    cd_comp = bytearray(zlib.compress(bytes(cd)))
    cd_comp[0] ^= 0x7A
    n = len(entradas) + len(pend)
    pie = bytearray(FIRMA + struct.pack('<HHHHIIH', len(cd_comp) & 0xFFFF,
                                        len(cd_comp) >> 16, n, n, len(cd), len(datos), 0))
    tmp = pak.with_name(pak.name + '.tmp')
    tmp.write_bytes(bytes(datos) + FIRMA + bytes(cd_comp) + bytes(_xor_pie(pie)))
    leer_indice(tmp.read_bytes())          # que se pueda releer antes de sustituir
    tmp.replace(pak)
    return n_rep, len(pend)


def construir_de_carpeta(carpeta: pathlib.Path, salida: pathlib.Path) -> int:
    archivos = []
    for f in sorted(carpeta.rglob('*')):
        if f.is_file():
            archivos.append((str(f.relative_to(carpeta)).replace('/', '\\'), f.read_bytes()))
    return construir(archivos, salida)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    orden, pak = argv[0], pathlib.Path(argv[1])
    if orden == 'list':
        for e in leer_indice(pak.read_bytes())[0]:
            print('%10d %10d %08X %s' % (e['csize'], e['usize'], e['crc'], e['nombre']))
    elif orden == 'verify':
        data = pak.read_bytes()
        es, _ = leer_indice(data)
        for e in es:
            leer_entrada(data, e)
        print('%s: %d entradas OK' % (pak.name, len(es)))
    elif orden == 'extract':
        print('%d archivos' % extraer(pak, pathlib.Path(argv[2])))
    elif orden == 'manifest':
        pathlib.Path(argv[2]).write_text(json.dumps(manifiesto(pak), indent=1), encoding='utf-8')
    elif orden == 'build':
        print('%d archivos' % construir_de_carpeta(pak, pathlib.Path(argv[2])))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
