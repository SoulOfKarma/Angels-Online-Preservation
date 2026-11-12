"""EL PARCHE DEL CLIENTE POR EL LAUNCHER.

Lo que el servidor cambia en el cliente (item9.xml, skill.xml sin
exclusiones, el strfilter.xml de UPDATE21, el logo...) se escribia a mano en
la carpeta del cliente de ESTA maquina. Aqui se junta en un registro y se
sirve como un parche normal del launcher, para que cualquier cliente que abra
START.EXE se lo baje solo. Formato medido en el launcher de Global y en el de
Taiwan (docs/ACTUALIZADOR_LAUNCHER_IGG.md):

  1. El indice (update3.ini por FTP en IGG, version.ini por HTTP en Global)
     trae `[VERSION] GameVer = <version>` y `GameURL = update.ini`.
  2. El launcher baja `GameURL + ".pak"`: el descriptor en deflate crudo,
     con `[info] compress = 1` y `[version] ver/path/file`.
  3. Cada `file = <prefijo><nombre>, <pak>, <carpeta>, <bytes>` se baja de
     `path + carpeta + "/" + prefijo + nombre + ".pak"` (deflate crudo) y el
     launcher lo mete en `<pak>.pak`.

La version del parche es la del cliente con el ultimo numero subido: sube
cada vez que cambia lo registrado (huella sha1), y se apunta en
data/parche_cliente.json para no repetirla al reiniciar.
"""
import hashlib
import json
import logging
import pathlib
import struct
import zlib

log = logging.getLogger('parche_cliente')

RAIZ = pathlib.Path(__file__).resolve().parent.parent
ESTADO = RAIZ / 'data' / 'parche_cliente.json'
RUTA = 'update/'
DESCRIPTOR = 'update.ini'

# (pak, carpeta, nombre) -> bytes, en minusculas y con '/'.
_REGISTRO = {}
_CACHE = {}


def _norm(s: str) -> str:
    return (s or '').replace('\\', '/').strip('/').lower()


def registrar(pak: str, carpeta: str, nombre: str, datos: bytes):
    """Apunta un archivo del parche. `pak` sin extension ('update26'), o ''
    para dejarlo suelto en la carpeta del juego."""
    pak = _norm(pak)
    if pak.endswith('.pak'):
        pak = pak[:-4]
    _REGISTRO[(pak, _norm(carpeta), _norm(nombre))] = bytes(datos)
    _CACHE.clear()


def registrar_pak(pak_path, reemplazos: dict):
    """Lo que `cliente_local.actualizar_pak_cliente` mete en un pak."""
    pak = pathlib.Path(pak_path).stem
    for clave, datos in reemplazos.items():
        partes = _norm(clave).rsplit('/', 1)
        carpeta, nombre = (partes[0], partes[1]) if len(partes) == 2 else ('', partes[0])
        registrar(pak, carpeta, nombre, datos)


def _deflate(datos: bytes) -> bytes:
    """Deflate crudo, una sola vez por contenido (el mismo archivo va bajo
    varios nombres: sin esto, servir el indice tardaba tanto que el launcher
    se rendia)."""
    memo = _CACHE.setdefault('deflate', {})
    clave = hashlib.md5(datos).digest() + len(datos).to_bytes(8, 'little')
    if clave not in memo:
        c = zlib.compressobj(6, zlib.DEFLATED, -15)
        memo[clave] = c.compress(datos) + c.flush()
    return memo[clave]


def _huella() -> str:
    if 'huella_calc' in _CACHE:
        return _CACHE['huella_calc']
    h = hashlib.sha1()
    for k in sorted(_REGISTRO):
        h.update('|'.join(k).encode('utf-8'))
        h.update(hashlib.sha1(_REGISTRO[k]).digest())
    _CACHE['huella_calc'] = h.hexdigest()
    return _CACHE['huella_calc']


def version(base: str) -> str:
    """La version del parche: `base` con el ultimo numero + n, donde n sube
    cada vez que cambia lo registrado. Sin nada registrado, `base`."""
    if not _REGISTRO:
        return base
    huella = _huella()
    if _CACHE.get('version') and _CACHE.get('huella') == huella:
        return _CACHE['version']
    try:
        est = json.loads(ESTADO.read_text(encoding='utf-8'))
    except Exception:
        est = {}
    if est.get('huella') != huella or est.get('base') != base:
        est = {'base': base, 'huella': huella, 'n': int(est.get('n', 0)) + 1}
        try:
            ESTADO.parent.mkdir(parents=True, exist_ok=True)
            ESTADO.write_text(json.dumps(est), encoding='utf-8')
        except OSError as e:
            log.warning('no se pudo guardar %s: %s', ESTADO, e)
    # El launcher compara las versiones COMO TEXTO: con tres cifras fijas
    # (101, 102...) todas quedan por encima de la base (8.7.6.1 < 8.7.6.101)
    # y ordenadas entre si hasta la 999.
    partes = base.split('.')
    partes[-1] = str(100 + int(est['n']))
    v = '.'.join(partes)
    _CACHE.update(version=v, huella=huella)
    return v


def _prefijo(v: str) -> str:
    return v.replace('.', '-')


def crear_pak(entradas: dict) -> bytes:
    """Un .pak como los del juego (el formato que lee
    cliente_local._extraer_archivo_pak): los datos en deflate crudo seguidos,
    la firma OD 05 06, el directorio central en zlib con el primer byte XOR
    0x7A y el fin de directorio con su XOR. El START.EXE de IGG abre asi lo
    que baja y busca dentro la entrada por nombre (FUN_0040a140 ->
    FUN_00414ca0 / FUN_00417f10)."""
    firma = bytes((0x4F, 0x44, 5, 6))
    cuerpo = bytearray()
    cd = bytearray()
    for nombre, datos in entradas.items():
        # (datos, False): la entrada va GUARDADA tal cual (metodo 0).
        guardar = isinstance(datos, tuple)
        if guardar:
            datos = datos[0]
        comp = bytes(datos) if guardar else _deflate(datos)
        fn = nombre.encode('ascii', 'replace')
        cd += struct.pack('<IHHHHHHIIIHHHHHII', 0x02014B50, 20, 20, 0, 0 if guardar else 8, 0, 0,
                          zlib.crc32(datos) & 0xFFFFFFFF, len(comp), len(datos),
                          len(fn), 0, 0, 0, 0, 32, len(cuerpo)) + fn
        cuerpo += comp
    cd_comp = bytearray(zlib.compress(bytes(cd)))
    cd_comp[0] ^= 0x7A
    eocd = bytearray(firma + struct.pack('<HHHHIIH', len(cd_comp) & 0xFFFF, len(cd_comp) >> 16,
                                         len(entradas), len(entradas), len(cd), len(cuerpo), 0))
    for i in range(4, 22):
        eocd[i] ^= (3 * i - 91) & 0xFF
    return bytes(cuerpo) + firma + bytes(cd_comp) + bytes(eocd)


def _nombres_en_pak(carpeta: str, nombre: str) -> list:
    """Con que nombre busca el launcher la entrada dentro de lo que baja:
    carpeta + barra invertida + nombre (FUN_0040a140). Como no se sabe si lo
    pasa a mayusculas o cambia '/' por la barra invertida, van las variantes
    (los mismos bytes con varios nombres)."""
    b = chr(92)
    crudo = (carpeta + b + nombre) if carpeta else nombre
    norm = crudo.replace('/', b)
    out = []
    for n in (crudo, norm, norm.upper(), norm.lower()):
        if n not in out:
            out.append(n)
    return out


def _empaquetar(contenido: bytes, carpeta: str, nombre: str, formato: str,
                ruta_final: str = None) -> bytes:
    """'pak' para el START.EXE de IGG (FTP); 'deflate' (crudo) para el de
    Global (HTTP), que es lo que se le vio bajar.

    El de IGG copia la entrada que encuentra TAL CUAL, sin descomprimir, a
    update/<pak>/<carpeta>/ (se vio: 8-7-6-102stage.xml quedo en deflate) y
    al instalar la trata como un MINI-PAK de una entrada con la ruta final
    (los ~90 bytes de mas de cada archivo de Taiwan son justo su directorio y
    su fin). Asi que la entrada que busca lleva GUARDADO ese mini-pak.
    `ruta_final` None = el descriptor, que se lee como texto."""
    if formato == 'deflate':
        return _deflate(contenido)
    # Tercera prueba: con el mini-pak anidado tambien fallo al instalar. Ahora
    # la entrada va GUARDADA (metodo 0) con el archivo tal cual y el
    # descriptor dice compress = 0: lea como lea el launcher la entrada, en
    # update/ queda el archivo sin comprimir y al instalar lo mete el en su
    # pak. `ruta_final` se deja por si hace falta volver al anidado.
    return crear_pak({n: (contenido,) for n in _nombres_en_pak(carpeta, nombre)})


def _archivos(base: str, formato: str = 'pak') -> dict:
    """url relativa -> (linea del descriptor, bytes a servir)."""
    clave = 'archivos_' + formato
    if clave in _CACHE and _CACHE.get('huella') == _huella():
        return _CACHE[clave]
    v = version(base)
    pre = _prefijo(v)
    out = {}
    for (pak, carpeta, nombre), datos in sorted(_REGISTRO.items()):
        # La ruta dentro del pak del juego, como las que ya tiene
        # (SETTING\ENG\ACTIVITYURL.XML).
        final = ((carpeta + '/' if carpeta else '') + nombre).replace('/', chr(92)).upper()
        if formato == 'pak':
            # START.EXE de IGG (FUN_0040c950 -> FUN_0040a140), compress = 1.
            # PROBADO contra una copia del cliente (12/11/2026): baja
            # path + carpeta/ + prefijo+nombre + '.pak' a update/<pak>/<carpeta>/
            # TAL CUAL, y al instalar lo abre como pak (el pak del juego queda
            # copiado en .bck mientras) y busca la entrada carpeta\nombre SIN
            # el prefijo, que es tambien la que escribe. Va en deflate bajo
            # las grafias de ese nombre (tal cual, con barras invertidas y en
            # mayusculas). Con compress = 0 lee la copia como archivo normal y
            # escribe entradas de 0 bytes.
            comp = crear_pak({n: bytes(datos) for n in _nombres_en_pak(carpeta, nombre)})
            url = RUTA + (carpeta + '/' if carpeta else '') + pre + nombre + '.pak'
        else:
            comp = _empaquetar(datos, carpeta, pre + nombre, formato, final)
            url = RUTA + (carpeta + '/' if carpeta else '') + pre + nombre + '.pak'
        linea = 'file = %s%s, %s, %s, %d' % (pre, nombre, pak, carpeta, len(comp))
        out[url] = (linea, comp)
    _CACHE[clave] = out
    return out


def lineas_indice(base: str) -> str:
    """La seccion [VERSION] para el indice (update3.ini / version.ini)."""
    if not _REGISTRO:
        return ''
    return '[VERSION]\r\nGameVer = %s\r\nGameURL = %s\r\n' % (version(base), DESCRIPTOR)


def descriptor(base: str, formato: str = 'pak') -> bytes:
    """`update.ini.pak`: el descriptor (`update.ini`) empaquetado."""
    arch = _archivos(base, formato)
    # compress = 1 en los dos (el de IGG instala abriendo la copia como pak).
    comprimido = 1
    txt = ('[info]\r\nserver = \r\nexecute = \r\npackage = \r\nsource = \r\n'
           'iniurl = \r\nloaderver = \r\nloaderurl = \r\ncompress = %d\r\ntime_mark = 1\r\n\r\n' % comprimido)
    txt += ('[rebuildpak]\r\n\r\n[version]\r\nver = %s\r\npath = %s\r\n' % (version(base), RUTA))
    txt += ''.join(linea + '\r\n' for linea, _ in arch.values())
    return _empaquetar(txt.encode('cp950', 'replace'), '', DESCRIPTOR, formato)


def resolver(ruta: str, base: str, formato: str = 'pak'):
    """Los bytes de una ruta pedida por FTP/HTTP, o None. Acepta prefijos
    (`alog-patch/`, la carpeta del FTP...) quitando segmentos por delante."""
    if not _REGISTRO:
        return None
    r = _norm(ruta)
    arch = _archivos(base, formato)
    claves = {k.lower(): v for k, v in arch.items()}
    partes = r.split('/')
    for i in range(len(partes)):
        sub = '/'.join(partes[i:])
        if sub == _norm(DESCRIPTOR + '.pak'):
            return descriptor(base, formato)
        if sub in claves:
            return claves[sub][1]
    # Por si el launcher pide solo el nombre.
    nombre = partes[-1]
    for k, v in claves.items():
        if k.rsplit('/', 1)[-1] == nombre:
            return v[1]
    return None


def resumen(base: str) -> str:
    return '%d archivos, version %s' % (len(_REGISTRO), version(base))
