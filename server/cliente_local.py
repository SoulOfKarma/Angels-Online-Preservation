"""
Sincronizador del cliente local (C:\\AO\\Angels Online), parcheo de update26.pak,
modos estacionales (Normal, Navidad, Halloween, Sakura, Verano), consumible
custom de Rango (ID 83266, basado en sprite 8921 de 5873) y servidor local
de actualizacion para START.EXE (FTP + HTTP).

REGLA DE SEGURIDAD:
Antes de modificar cualquier archivo del cliente (update26.pak, START.EXE, reg.ini),
se crea siempre una copia de respaldo (.bak) intacta si no existe todavia.
"""
import asyncio
import json
import logging
import os
import pathlib
import shutil
import sqlite3
import struct
import re
import subprocess
import time
import zlib

import configuracion as _cf

log = logging.getLogger('cliente_local')

RAIZ_PROYECTO = pathlib.Path(__file__).parent.parent

# LA ESTACION NO ESTA EN map041.mpc. Esta en stage.xml, en la escena 41:
#
#   normal     <場景 編號="41" ... 地圖檔="map\map041.mpc" ... 天氣="無" />
#   navidad    <場景 編號="41" ... 地圖檔="map\map041.mpc"
#                               裝飾地圖檔="map!xmas.mpc" ... 天氣="小雪" />
#
# O sea: un mapa de DECORACION aparte (裝飾地圖檔) que se pinta encima del
# mapa base, mas el clima. Comprobado en los veintitantos stage.xml de los
# paks: los que van sin nieve no traen 裝飾地圖檔 y llevan 天氣="0" o "無",
# y los dos de navidad (UPDATE17 y update26) traen 041xmas.mpc con
# 天氣="自動下雪" y "小雪".
#
# Antes esto cambiaba map041.mpc, que es el mapa BASE y no lleva estacion
# ninguna: por eso poner "normal" no quitaba la nieve. Y peor, para
# halloween/sakura/verano metia el mapa de decoracion en el sitio del base,
# que son archivos de la mitad de tamano.
#
# El pak que manda es update26.pak, el de numero mas alto que trae
# SETTING\ENG\STAGE.XML.
ESTACIONES = {
    'normal':    (None,                       '無'),
    'navidad':   (r'map\041xmas.mpc',      '小雪'),
    'halloween': (r'map\041halloween.mpc', '無'),
    'sakura':    (r'map\041sakura.mpc',    '無'),
    'verano':    (r'map\041matsuri.mpc',   '無'),
}

# De donde sale cada mapa de decoracion si no esta la plantilla.
DECORADOS_ESTACION = {
    'navidad':   RAIZ_PROYECTO / 'extracted_paks' / 'UPDATE10' / 'map' / '041xmas.mpc',
    'halloween': RAIZ_PROYECTO / 'extracted_paks' / 'UPDATE6' / 'map' / '041halloween.mpc',
    'sakura':    RAIZ_PROYECTO / 'extracted_paks' / 'UPDATE6' / 'map' / '041sakura.mpc',
    'verano':    RAIZ_PROYECTO / 'extracted_paks' / 'UPDATE19' / 'map' / '041matsuri.mpc',
}

# Tope de copias a la vez y respiro entre una y otra.
MAX_CLIENTES = 10
RESPIRO_ENTRE_CLIENTES = 1.5

MAPAS_ESTACION = ESTACIONES      # nombre viejo, por si algo lo importa


LINEA_XML_MEDALLA = (
    '    <\u9053\u5177 \u7de8\u865f="83266" \u539f\u578b\u4ecb\u9762="8921" '
    '\u57fa\u672c\u540d\u7a31="Rank Promotion Medal" \u7269\u54c1\u985e\u5225="\u7d93\u9a57\u5377" '
    '\u91cd\u91cf="1" \u50f9\u683c="100" \u6536\u8cfc\u50f9\u683c="10" '
    '\u52d5\u614b\u8cc7\u65991="3" \u52d5\u614b\u8cc7\u65992="1" log\u7b49\u7d1a="30" '
    '\u8aaa\u660e\u5b9a\u7fa9="Right click to use and automatically promote your character\'s Rank by +1 level." '
    '\u53ef\u5806\u758a="\u662f" \u53ef\u4f7f\u7528="\u662f" />'
)


# DONDE ESTA EL CLIENTE.
#
# Estaba escrito a mano en cinco sitios como C:\AO\Angels Online, asi que
# a quien lo tuviera en otro lado no le funcionaba nada de la parte del
# cliente y encima sin decir por que. Ahora se busca.
#
# Un directorio es el cliente si tiene Angel.exe y al menos un .pak. Se
# mira, en este orden: lo que diga la variable de entorno AO_CLIENTE, lo
# que diga RUTA_CLIENTE en configuracion.py, los sitios de siempre, y los
# vecinos del propio repo (que es lo habitual: el cliente al lado del
# servidor). Si no aparece ninguno se devuelve igual la ruta configurada,
# y quien la use ya comprueba que exista.
_CLIENTE_CACHE = None


def _unidades() -> list:
    """Las letras de unidad montadas, de la C en adelante.

    Se saltan las que no responden: una unidad de red caida o un lector
    vacio cuelgan el arranque si se les pregunta sin mas.
    """
    if os.name != 'nt':
        return []
    salida = []
    for letra in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
        try:
            if pathlib.Path('%s:' % letra + os.sep).is_dir():
                salida.append(letra)
        except OSError:
            continue
    return salida


def _parece_cliente(d: pathlib.Path) -> bool:
    try:
        if not (d / 'Angel.exe').exists():
            return False
        return any(d.glob('*.pak')) or any(d.glob('*.PAK'))
    except OSError:
        return False


def _candidatos_cliente():
    """Rutas donde puede estar el cliente, de la mas probable a la menos.

    Es un GENERADOR a proposito: lo caro es recorrer las unidades, y con
    la ruta configurada bien puesta no hace falta llegar ahi. Devolviendo
    una lista entera, el arranque se iba a dos segudos y medio aunque el
    cliente estuviera en el primer sitio que se mira.
    """
    env = os.environ.get('AO_CLIENTE')
    if env:
        yield pathlib.Path(env)
    configurada = str(getattr(_cf, 'RUTA_CLIENTE', '') or '')
    if configurada:
        yield pathlib.Path(configurada)

    # Vecinos del repo: lo normal es el cliente al lado del servidor.
    base = RAIZ_PROYECTO
    for arriba in (base, base.parent, base.parent.parent):
        try:
            if not arriba.is_dir():
                continue
            for hijo in sorted(arriba.iterdir()):
                if hijo.is_dir() and 'angel' in hijo.name.lower():
                    yield hijo
                    for nieto in ('Angels Online', 'client', 'cliente'):
                        yield hijo / nieto
        except OSError:
            continue

    # Y por ultimo las unidades, a lo ancho. El cliente puede estar en
    # C:\AO\Angels Online, en C:\Angels Online a secas, en D:, E:, F:, G:
    # o colgado de cualquier carpeta intermedia (D:\Juegos\MMO\Angels
    # Online). Por eso se recorre por PROFUNDIDAD en vez de adivinar
    # nombres: tres niveles desde la raiz de cada unidad.
    #
    # Lo que lo mantiene rapido es la lista de carpetas que NO se pisan:
    # Windows y compania tienen decenas de miles de subdirectorios y ahi
    # no va a estar el juego.
    limite = time.monotonic() + SEGUNDOS_BUSQUEDA
    raices = [pathlib.Path('%s:' % l + os.sep) for l in _unidades()]
    for d in _por_niveles(raices, PROF_BUSQUEDA, limite):
        yield d
    if time.monotonic() > limite:
        log.info('busqueda del cliente cortada a los %.0f s'
                 % SEGUNDOS_BUSQUEDA)


# Carpetas que no se recorren buscando el cliente: son enormes y el juego
# no va a estar ahi.
SALTAR = {
    'windows', '$recycle.bin', 'system volume information', 'programdata',
    'appdata', 'perflogs', 'recovery', 'msocache', 'node_modules',
    '.git', 'onedrive', 'temp', 'tmp', 'cache', '$winreagent',
}

# Cuantos niveles por debajo de la raiz de cada unidad, y cuantos segundos
# como mucho. Sin el tope de tiempo, con el cliente en ningun lado, tres
# niveles de cinco unidades tardaban 42 segundos y el servidor se quedaba
# parado al arrancar. Los casos normales ni se enteran: con la ruta
# configurada se resuelve en 0,00 s y no se llega nunca a esta parte.
PROF_BUSQUEDA = 3
SEGUNDOS_BUSQUEDA = 3.0
# Los dos primeros niveles van SIN tope de tiempo. Son unos 900 directorios
# en total y cubren lo que de verdad pasa -- C:\Angels Online, C:\AO\Angels
# Online, D:\Games\Angels Online -- asi que vale la pena asegurarlos aunque
# el disco este frio. El tercero es un extra y se corta si tarda.
PROF_SIN_TOPE = 2


def _por_niveles(raices, prof: int, limite: float = None):
    """Los directorios colgados de esas raices, nivel a nivel.

    Va a lo ANCHO y mezclando TODAS las unidades: primero el nivel 1 de
    C:, D:, E:..., luego el nivel 2 de todas, y asi. Es lo que hace que
    valga la pena: recorriendo una unidad entera antes de pasar a la
    siguiente, el tiempo se acababa dentro de C: y un cliente en F: no
    aparecia nunca, aunque estuviera a dos carpetas de la raiz.
    """
    nivel = list(raices)
    for hondura in range(prof):
        siguiente = []
        # Los primeros niveles no se cortan: ver PROF_SIN_TOPE.
        tope = None if hondura < PROF_SIN_TOPE else limite
        for d in nivel:
            if tope is not None and time.monotonic() > tope:
                return
            try:
                hijos = sorted(d.iterdir())
            except OSError:
                continue
            for h in hijos:
                try:
                    if not h.is_dir() or h.name.lower() in SALTAR:
                        continue
                except OSError:
                    continue
                yield h
                siguiente.append(h)
        nivel = siguiente


def ruta_cliente(refrescar: bool = False) -> pathlib.Path:
    """El directorio del cliente, buscandolo si hace falta."""
    global _CLIENTE_CACHE
    if _CLIENTE_CACHE is not None and not refrescar:
        return _CLIENTE_CACHE

    configurada = str(getattr(_cf, 'RUTA_CLIENTE', '') or '')
    vistos = set()
    for c in _candidatos_cliente():
        k = str(c).lower()
        if k in vistos:
            continue
        vistos.add(k)
        if _parece_cliente(c):
            if configurada and k != configurada.lower():
                log.info('cliente encontrado en %s (RUTA_CLIENTE decia %s)'
                         % (c, configurada))
            _CLIENTE_CACHE = c
            return c

    log.info('no se encontro el cliente; la parte del cliente se queda sin hacer')
    _CLIENTE_CACHE = pathlib.Path(configurada) if configurada else pathlib.Path('.')
    return _CLIENTE_CACHE


def _asegurar_bak(ruta: pathlib.Path) -> pathlib.Path:
    """Crea una copia .bak del archivo original si aun no existe."""
    bak = ruta.with_name(ruta.name + '.bak')
    if ruta.exists() and not bak.exists():
        shutil.copy2(ruta, bak)
        log.info(f"Backup creado: {bak}")
    return bak


def _parchear_item9_xml_bytes(xml_bytes: bytes) -> bytes:
    """Inserta el item 83266 (Rank Promotion Medal) en item9.xml si no esta."""
    txt = xml_bytes.decode('utf-8', errors='ignore')
    if '\u7de8\u865f="83266"' in txt:
        return xml_bytes
    objetivo = '    <\u9053\u5177 />'
    if objetivo in txt:
        txt = txt.replace(objetivo, LINEA_XML_MEDALLA, 1)
    else:
        cierre = '</root>'
        txt = txt.replace(cierre, LINEA_XML_MEDALLA + '\r\n' + cierre, 1)
    return txt.encode('utf-8')


def registrar_medalla_en_servidor():
    """Asegura que el item 83266 exista en content.db, extracted_paks y client_tables.json."""
    # 1. extracted_paks/update26/setting/eng/item9.xml
    f_xml = RAIZ_PROYECTO / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'item9.xml'
    if f_xml.exists():
        try:
            orig = f_xml.read_bytes()
            nuevo = _parchear_item9_xml_bytes(orig)
            if nuevo != orig:
                f_xml.write_bytes(nuevo)
        except Exception as e:
            log.warning(f"No se pudo actualizar {f_xml}: {e}")

    # 2. corpus/content.db (tabla item9)
    db_path = RAIZ_PROYECTO / 'corpus' / 'content.db'
    if db_path.exists():
        try:
            con = sqlite3.connect(db_path)
            cur = con.execute('SELECT id FROM item9 WHERE id = ?', ('83266',)).fetchone()
            if not cur:
                con.execute(
                    'INSERT INTO item9 (id, "\u539f\u578b\u4ecb\u9762", "\u57fa\u672c\u540d\u7a31", '
                    '"\u7269\u54c1\u985e\u5225", weight, price, "\u6536\u8cfc\u50f9\u683c", '
                    '"\u52d5\u614b\u8cc7\u65991", "\u52d5\u614b\u8cc7\u65992", "log\u7b49\u7d1a", '
                    '"\u8aaa\u660e\u5b9a\u7fa9", "\u53ef\u5806\u758a", "\u53ef\u4f7f\u7528", _pak) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (
                        '83266', '8921', 'Rank Promotion Medal', '\u7d93\u9a57\u5377',
                        '1', '100', '10', '3', '1', '30',
                        "Right click to use and automatically promote your character's Rank by +1 level.",
                        '\u662f', '\u662f', 'update26'
                    )
                )
                con.commit()
                log.info("Item 83266 (Rank Promotion Medal) registrado en corpus/content.db")
            con.close()
        except Exception as e:
            log.warning(f"No se pudo registrar 83266 en content.db: {e}")

    # 3. server/plantillas/client_tables.json
    f_json = pathlib.Path(__file__).parent / 'plantillas' / 'client_tables.json'
    if f_json.exists():
        try:
            raw = json.loads(f_json.read_text(encoding='utf-8'))
            nombres = raw.get('item_names')
            if isinstance(nombres, dict) and '83266' not in nombres:
                nombres['83266'] = 'Rank Promotion Medal'
                f_json.write_text(json.dumps(raw, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        except Exception:
            pass


def actualizar_pak_cliente(pak_path: pathlib.Path, reemplazos: dict) -> bool:
    """Reemplaza archivos dentro de un archivo .pak (formato OD\\x05\\x06 de Angel.exe).
    reemplazos: {'MAP\\\\MAP041.MPC': bytes_nuevos, 'SETTING\\\\ENG\\\\ITEM9.XML': bytes_nuevos}
    """
    if not pak_path.exists():
        return False
    _asegurar_bak(pak_path)
    data = pak_path.read_bytes()
    eocd = bytearray(data[-22:])
    if eocd[:4] != b'OD\x05\x06':
        log.warning(f"{pak_path} no tiene firma OD\\x05\\x06")
        return False
    for i in range(4, 22):
        eocd[i] ^= (3 * i - 91) & 0xFF
    comp_cd_size, cd_disk, disk_entries, total_entries, cd_size, cd_offset, comment_len = struct.unpack('<HHHHIIH', eocd[4:22])
    cd_raw = bytearray(data[cd_offset + 4 : cd_offset + 4 + comp_cd_size])
    cd_raw[0] ^= 0x7A
    cd = bytearray(zlib.decompress(bytes(cd_raw)))

    # Verificar si los reemplazos ya estan aplicados (comparando CRC32 y usize)
    mapa_norm = {k.upper().replace('/', '\\'): v for k, v in reemplazos.items()}
    pendientes = {}
    off = 0
    entradas = []
    while off < len(cd):
        sig, ver_made, ver_need, flags, method, mtime, mdate, crc, csize, usize, fn_len, ex_len, cm_len, disk, iattr, eattr, lhoff = struct.unpack_from('<IHHHHHHIIIHHHHHII', cd, off)
        fname = cd[off + 46 : off + 46 + fn_len].decode('ascii', errors='ignore')
        key = fname.upper().replace('/', '\\')
        if key in mapa_norm:
            nuevo_raw = mapa_norm[key]
            nuevo_crc = zlib.crc32(nuevo_raw) & 0xFFFFFFFF
            if crc != nuevo_crc or usize != len(nuevo_raw):
                pendientes[key] = (nuevo_raw, nuevo_crc)
        entradas.append((off, fn_len, ex_len, cm_len, key))
        off += 46 + fn_len + ex_len + cm_len

    if not pendientes:
        return True

    # Escribir los nuevos bloques comprimidos al final de la zona de datos (en cd_offset)
    cuerpo_datos = bytearray(data[:cd_offset])
    for off, fn_len, ex_len, cm_len, key in entradas:
        if key in pendientes:
            nuevo_raw, nuevo_crc = pendientes[key]
            c_obj = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15)
            comp_bytes = c_obj.compress(nuevo_raw) + c_obj.flush()
            nuevo_lhoff = len(cuerpo_datos)
            cuerpo_datos.extend(comp_bytes)
            # Actualizar crc (+16), csize (+20), usize (+24) y lhoff (+42) en la entrada del Central Directory
            struct.pack_into('<III', cd, off + 16, nuevo_crc, len(comp_bytes), len(nuevo_raw))
            struct.pack_into('<I', cd, off + 42, nuevo_lhoff)

    # Comprimir el nuevo Central Directory con zlib estandar y XOR 0x7A en el primer byte
    cd_comp = bytearray(zlib.compress(bytes(cd)))
    cd_comp[0] ^= 0x7A
    nuevo_cd_offset = len(cuerpo_datos)

    nuevo_eocd = bytearray(b'OD\x05\x06' + struct.pack(
        '<HHHHIIH',
        len(cd_comp),
        0,
        total_entries,
        total_entries,
        len(cd),
        nuevo_cd_offset,
        0
    ))
    for i in range(4, 22):
        nuevo_eocd[i] ^= (3 * i - 91) & 0xFF

    salida = bytes(cuerpo_datos) + b'OD\x05\x06' + bytes(cd_comp) + bytes(nuevo_eocd)
    pak_path.write_bytes(salida)
    log.info(f"Actualizado {pak_path.name}: {list(pendientes.keys())}")
    return True


def _extraer_archivo_pak(pak_path: pathlib.Path, nombre_buscado: str) -> bytes:
    """Extrae un archivo descomprimido desde un .pak (formato OD\\x05\\x06)."""
    if not pak_path.exists():
        return b''
    data = pak_path.read_bytes()
    eocd = bytearray(data[-22:])
    if eocd[:4] != b'OD\x05\x06':
        return b''
    for i in range(4, 22):
        eocd[i] ^= (3 * i - 91) & 0xFF
    comp_cd_size, _, _, _, _, cd_offset, _ = struct.unpack('<HHHHIIH', eocd[4:22])
    cd_raw = bytearray(data[cd_offset + 4 : cd_offset + 4 + comp_cd_size])
    cd_raw[0] ^= 0x7A
    cd = zlib.decompress(bytes(cd_raw))
    objetivo = nombre_buscado.upper().replace('/', '\\')
    off = 0
    while off < len(cd):
        sig, ver_made, ver_need, flags, method, mtime, mdate, crc, csize, usize, fn_len, ex_len, cm_len, disk, iattr, eattr, lhoff = struct.unpack_from('<IHHHHHHIIIHHHHHII', cd, off)
        fname = cd[off + 46 : off + 46 + fn_len].decode('ascii', errors='ignore').upper().replace('/', '\\')
        if fname == objetivo:
            return zlib.decompress(data[lhoff : lhoff + csize], -15)
        off += 46 + fn_len + ex_len + cm_len
    return b''


def _obtener_decorado(modo_Norm: str) -> bytes:
    """Los bytes del mapa de DECORACION de esa estacion, o vacio si no lleva."""
    f_zlib = (pathlib.Path(__file__).parent / 'plantillas' / 'mapas_estacion'
              / f'{modo_Norm}.zlib')
    if f_zlib.exists():
        try:
            return zlib.decompress(f_zlib.read_bytes())
        except Exception:
            pass
    f = DECORADOS_ESTACION.get(modo_Norm)
    return f.read_bytes() if (f and f.exists()) else b''


# La escena 41 del stage.xml, para cambiarle el decorado y el clima.
_RE_ESCENA_41 = re.compile(
    '<場景 編號="41"[^>]*/>'.encode('utf-8'))


def _parchear_stage_xml(raw: bytes, modo_Norm: str) -> bytes:
    """Deja la escena 41 con el decorado y el clima de esa estacion."""
    m = _RE_ESCENA_41.search(raw)
    if not m:
        return raw
    tag = m.group(0).decode('utf-8')
    decorado, clima = ESTACIONES.get(modo_Norm, (None, '無'))

    # fuera el decorado y el clima que hubiera
    tag = re.sub(r'\s*裝飾地圖檔="[^"]*"', '', tag)
    tag = re.sub('天氣="[^"]*"', '天氣="%s"' % clima, tag)
    if '天氣=' not in tag:
        tag = tag.replace('/>', '天氣="%s" />' % clima)
    if decorado:
        # va justo detras del mapa base, que es donde lo pone el
        # original. La sustitucion va con lambda a proposito: la
        # ruta lleva \041 y re.sub se lo comia como escape.
        tag = re.sub('(地圖檔="[^"]*")',
                     lambda mm: mm.group(1) + ' 裝飾地圖檔="' + decorado + '"',
                     tag, count=1)
    return raw[:m.start()] + tag.encode('utf-8') + raw[m.end():]


def aplicar_modo_estacion(modo: str = None) -> str:
    """Aplica la estacion y el item custom 83266 en el cliente local.

    La estacion se cambia en stage.xml, NO en map041.mpc: ver el comentario
    de ESTACIONES arriba.
    """
    registrar_medalla_en_servidor()
    modo_Norm = (modo or getattr(_cf, 'MODO_ESTACION', 'normal') or 'normal').strip().lower()
    if modo_Norm not in ESTACIONES:
        modo_Norm = 'normal'
    _cf.MODO_ESTACION = modo_Norm

    ruta_cli = ruta_cliente()
    if not ruta_cli.exists():
        return modo_Norm
    pak26 = ruta_cli / 'update26.pak'
    if not pak26.exists():
        return modo_Norm
    bak26 = _asegurar_bak(pak26)
    reemplazos = {}

    # El item custom
    f_item9 = RAIZ_PROYECTO / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'item9.xml'
    raw_item9 = (f_item9.read_bytes() if f_item9.exists()
                 else _extraer_archivo_pak(bak26 if bak26.exists() else pak26,
                                           r'SETTING\ENG\ITEM9.XML'))
    if raw_item9:
        reemplazos[r'SETTING\ENG\ITEM9.XML'] = _parchear_item9_xml_bytes(raw_item9)

    # La estacion: se parte SIEMPRE del stage.xml original del .bak, que si
    # no, cada cambio se aplicaria encima del anterior.
    raw_stage = _extraer_archivo_pak(bak26 if bak26.exists() else pak26,
                                     r'SETTING\ENG\STAGE.XML')
    if raw_stage:
        reemplazos[r'SETTING\ENG\STAGE.XML'] = _parchear_stage_xml(raw_stage, modo_Norm)

    # El mapa de decoracion va suelto en map\, que el cliente lo lee antes
    # que el del pak y ademas el pak no admite archivos nuevos.
    dir_map = ruta_cli / 'map'
    try:
        dir_map.mkdir(parents=True, exist_ok=True)
        deco = _obtener_decorado(modo_Norm)
        nombre = (ESTACIONES[modo_Norm][0] or '').split('\\')[-1]
        if deco and nombre:
            (dir_map / nombre).write_bytes(deco)
        # Un map041.mpc suelto de antes tapaba el del pak. Aqui se cambiaba
        # el mapa BASE creyendo que era la estacion, asi que si quedo uno
        # escrito hay que quitarlo o el Lyceum se queda como lo dejaron.
        suelto = dir_map / 'map041.mpc'
        if suelto.exists():
            suelto.unlink()
            log.info('quitado el map041.mpc suelto: la estacion no va ahi')
    except Exception:
        pass

    if reemplazos:
        try:
            actualizar_pak_cliente(pak26, reemplazos)
        except Exception as e:
            log.warning(f"No se pudo actualizar {pak26} (quiza el juego esta abierto): {e}")
    return modo_Norm


def parchear_launcher():
    """Parchea C:\\AO\\Angels Online\\START.EXE y reg.ini (creando .bak antes)
    para que el launcher apunte a 127.0.0.1 y muestre el panel local."""
    ruta_cli = ruta_cliente()
    if not ruta_cli.exists():
        return

    puerto_ftp = int(getattr(_cf, 'PUERTO_UPDATE_FTP', 2121))
    puerto_http = int(getattr(_cf, 'PUERTO_UPDATE_HTTP', 8080))

    # 1. reg.ini
    reg_ini = ruta_cli / 'reg.ini'
    if reg_ini.exists():
        _asegurar_bak(reg_ini)
        txt_reg = (
            "[PROFILE]\r\n"
            "GameName = Angels Online\r\n"
            "Version = 8.5.1.0\r\n"
            "GameDir = ./\r\n"
            "LoaderVer = 1.7\r\n"
            "PassiveMode = 1\r\n"
            "UpdateIP = 127.0.0.1\r\n"
            f"UpdatePort = {puerto_ftp}\r\n"
        )
        if reg_ini.read_text(encoding='utf-8', errors='ignore') != txt_reg:
            reg_ini.write_text(txt_reg, encoding='utf-8')
            log.info(f"Actualizado {reg_ini} -> 127.0.0.1:{puerto_ftp}")

    # 2. START.EXE
    start_exe = ruta_cli / 'START.EXE'
    if start_exe.exists():
        _asegurar_bak(start_exe)
        raw = bytearray(start_exe.read_bytes())
        cambiado = False

        # Puerto por defecto en .data (0x07E004)
        if len(raw) >= 0x07E030:
            p_act = struct.unpack_from('<I', raw, 0x07E004)[0]
            if p_act != puerto_ftp:
                struct.pack_into('<I', raw, 0x07E004, puerto_ftp)
                cambiado = True

            # IP por defecto en .data (0x07E008, 20 bytes)
            ip_bytes = b'127.0.0.1\x00'.ljust(20, b'\x00')
            if raw[0x07E008:0x07E008 + 20] != ip_bytes:
                raw[0x07E008:0x07E008 + 20] = ip_bytes
                cambiado = True

            # IP fallback en .rdata (0x0686E4, 20 bytes)
            if raw[0x0686E4:0x0686E4 + 20] != ip_bytes:
                raw[0x0686E4:0x0686E4 + 20] = ip_bytes
                cambiado = True

            # URL del navegador embebido en .rdata (0x0688C8, 28 bytes: "http://ao.igg.com/patch.php\x00")
            url_local = f"http://127.0.0.1:{puerto_http}/p.htm".encode('ascii')
            if len(url_local) < 28:
                url_padded = url_local + b'\x00' * (28 - len(url_local))
                if raw[0x0688C8:0x0688C8 + 28] != url_padded:
                    raw[0x0688C8:0x0688C8 + 28] = url_padded
                    cambiado = True

            # Timer 1 (0x005638) y Timer 2 (0x0063F5) a 50ms para respuesta instantanea
            if raw[0x005638:0x00563C] != b'\x32\x00\x00\x00':
                raw[0x005638:0x00563C] = b'\x32\x00\x00\x00'
                cambiado = True
            if raw[0x0063F5:0x0063F9] != b'\x32\x00\x00\x00':
                raw[0x0063F5:0x0063F9] = b'\x32\x00\x00\x00'
                cambiado = True

            # En CUpdater::ThreadProc (VA 0x0040EFD5 / raw 0x00E3D5):
            # Marcar estado 4 ("You have the latest version.") y completado ([esi+4]=1, [esi+5]=0)
            # al instante sin bloquearse esperando en WinInet FTP
            parche_ready = bytes.fromhex('6a048bcee8d2a2ffffc6460401c6460500eb2390')
            if raw[0x00E3D5:0x00E3D5 + 20] != parche_ready:
                raw[0x00E3D5:0x00E3D5 + 20] = parche_ready
                cambiado = True

            # Cambiar recurso de cadena 24 ("angel.dat" en UTF-16LE en 0x168258) por "Angel.exe"
            # para que al pulsar ENTER / START lance nuestro cliente Angel.exe desempaquetado
            str_angel_exe = 'Angel.exe'.encode('utf-16le')
            if len(raw) >= 0x168258 + len(str_angel_exe):
                if raw[0x168258:0x168258 + len(str_angel_exe)] != str_angel_exe:
                    raw[0x168258:0x168258 + len(str_angel_exe)] = str_angel_exe
                    cambiado = True

        if cambiado:
            try:
                start_exe.write_bytes(bytes(raw))
                log.info(f"Parcheado {start_exe} -> listo al instante, HTTP 127.0.0.1:{puerto_http} -> Angel.exe")
            except Exception as e:
                log.warning(f"No se pudo parchear {start_exe} (quiza esta en ejecucion): {e}")


async def _manejar_ftp(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Mini servidor FTP local para que START.EXE valide update3.ini al instante."""
    pasv_srv = None
    pasv_queue = asyncio.Queue()

    async def _on_data_conn(r_d, w_d):
        await pasv_queue.put((r_d, w_d))

    try:
        writer.write(b"220 Angels Online Local Update Server Ready\r\n")
        await writer.drain()
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=15.0)
            if not line:
                break
            cmd_line = line.decode('ascii', errors='ignore').strip()
            if not cmd_line:
                continue
            parts = cmd_line.split(' ', 1)
            cmd = parts[0].upper()
            arg = parts[1].strip() if len(parts) > 1 else ''

            if cmd == 'USER':
                writer.write(b"331 User name okay, need password.\r\n")
            elif cmd == 'PASS':
                writer.write(b"230 User logged in, proceed.\r\n")
            elif cmd == 'SYST':
                writer.write(b"215 UNIX Type: L8\r\n")
            elif cmd in ('PWD', 'XPWD'):
                writer.write(b'257 "/" is current directory.\r\n')
            elif cmd == 'TYPE':
                writer.write(b"200 Type set to I.\r\n")
            elif cmd == 'CWD':
                writer.write(b"250 Directory changed.\r\n")
            elif cmd == 'PASV':
                if pasv_srv:
                    pasv_srv.close()
                pasv_srv = await asyncio.start_server(_on_data_conn, '127.0.0.1', 0)
                port = pasv_srv.sockets[0].getsockname()[1]
                p1, p2 = port >> 8, port & 0xFF
                writer.write(f"227 Entering Passive Mode (127,0,0,1,{p1},{p2}).\r\n".encode('ascii'))
            elif cmd in ('LIST', 'NLST'):
                ini_bytes = _contenido_update3_ini()
                writer.write(b"150 Opening ASCII mode data connection for directory list.\r\n")
                await writer.drain()
                r_d, w_d = await asyncio.wait_for(pasv_queue.get(), timeout=5.0)
                list_line = f"-rw-r--r-- 1 owner group {len(ini_bytes)} Jan 01 00:00 update3.ini\r\n".encode('ascii')
                w_d.write(list_line)
                await w_d.drain()
                w_d.close()
                writer.write(b"226 Transfer complete.\r\n")
            elif cmd == 'SIZE':
                ini_bytes = _contenido_update3_ini()
                writer.write(f"213 {len(ini_bytes)}\r\n".encode('ascii'))
            elif cmd == 'RETR':
                ini_bytes = _contenido_update3_ini()
                writer.write(b"150 Opening BINARY mode data connection.\r\n")
                await writer.drain()
                r_d, w_d = await asyncio.wait_for(pasv_queue.get(), timeout=5.0)
                w_d.write(ini_bytes)
                await w_d.drain()
                w_d.close()
                writer.write(b"226 Transfer complete.\r\n")
            elif cmd == 'QUIT':
                writer.write(b"221 Goodbye.\r\n")
                await writer.drain()
                break
            else:
                writer.write(b"200 OK\r\n")
            await writer.drain()
    except Exception:
        pass
    finally:
        if pasv_srv:
            pasv_srv.close()
        try:
            writer.close()
        except Exception:
            pass


def _contenido_update3_ini() -> bytes:
    """Genera el update3.ini que hace que START.EXE marque el cliente como actualizado."""
    return (
        "[INFO]\r\n"
        "LoaderVer = 1.7\r\n"
        "GameVerFrom = 8.5.1.0\r\n"
        "GameVerTrans = 8.5.1.0\r\n"
        "[VERSION]\r\n"
        "[COMPLEXFILE]\r\n"
    ).encode('ascii')


# El panel del launcher en dos idiomas. El elegido se recuerda mientras
# el servidor este levantado; no se guarda en configuracion.py porque es
# cosa de quien mira el panel, no del servidor.
IDIOMA_PANEL = 'es'

TEXTOS = {
    'es': {
        'titulo': 'Angels Online - Servidor Local Custom',
        'estado': 'Estado:', 'online': 'ONLINE (127.0.0.1)',
        'estacion': 'Estacion activa en Angel Lyceum:',
        'cambiar': 'Cambiar estacion del cliente antes de entrar:',
        'copias': 'Abrir varias copias del cliente a la vez:',
        'abiertas': 'abiertas',
        'pie1': 'Flechas y bolitas infinitas activas',
        'pie2': 'Rank Promotion Medal (ID 83266) disponible (+1 Rango por uso)',
        'temporadas': ['Normal (Clasico)', 'Navidad (Nieve)', 'Halloween',
                       'Sakura (Primavera)', 'Verano (Matsuri)'],
    },
    'en': {
        'titulo': 'Angels Online - Custom Local Server',
        'estado': 'Status:', 'online': 'ONLINE (127.0.0.1)',
        'estacion': 'Active season in Angel Lyceum:',
        'cambiar': 'Change the client season before you log in:',
        'copias': 'Open several copies of the client at once:',
        'abiertas': 'opened',
        'pie1': 'Infinite arrows and pellets enabled',
        'pie2': 'Rank Promotion Medal (ID 83266) available (+1 Rank per use)',
        'temporadas': ['Normal (Classic)', 'Christmas (Snow)', 'Halloween',
                       'Sakura (Spring)', 'Summer (Matsuri)'],
    },
}


# Las tres pantallas del logo de arranque, una por resolucion. Viven en
# UPDATE21.PAK, que es el pak de numero mas alto que las trae.
LOGOS_ARRANQUE = ('LOGO02A', 'LOGO02B', 'LOGO02C')
PAK_LOGOS = 'UPDATE21.PAK'


def _vaciar_shp(raw: bytes) -> bytes:
    """Deja un .SHP del logo con todos sus pixeles a cero.

    El formato es 'TLHS' y la imagen va CRUDA en RGB565: en las tres
    comprueba que total - offset_de_datos == ancho * alto * 2, asi que no
    hay compresion que respetar. Se toca solo el area de pixeles y la
    cabecera se deja intacta, que es lo que hace esto seguro: el archivo
    conserva su tamano y sus medidas, y el cliente no tiene de que
    quejarse.
    """
    if raw[:4] != b'TLHS' or len(raw) < 48:
        return raw
    ancho, alto = struct.unpack_from('<II', raw, 20)
    datos = struct.unpack_from('<I', raw, 44)[0]
    if datos <= 0 or datos >= len(raw):
        return raw
    if len(raw) - datos != ancho * alto * 2:
        return raw                      # no es crudo: no se toca
    return raw[:datos] + b'\x00' * (len(raw) - datos)


def quitar_logo_arranque() -> bool:
    """Deja en blanco la pantalla del logo que sale al abrir el cliente."""
    ruta_cli = ruta_cliente()
    pak = ruta_cli / PAK_LOGOS
    if not pak.exists():
        return False
    bak = _asegurar_bak(pak)
    reemplazos = {}
    for nombre in LOGOS_ARRANQUE:
        clave = 'SHAPE' + chr(92) + 'LOGO' + chr(92) + nombre + '.SHP'
        raw = _extraer_archivo_pak(bak if bak.exists() else pak, clave)
        if raw:
            vacio = _vaciar_shp(raw)
            if vacio != raw:
                reemplazos[clave] = vacio
    if not reemplazos:
        return False
    try:
        actualizar_pak_cliente(pak, reemplazos)
        log.info('logo de arranque vaciado: %s' % ', '.join(LOGOS_ARRANQUE))
        return True
    except Exception as e:
        log.warning('no se pudo vaciar el logo: %s' % e)
        return False


# LA EXCLUSION ENTRE RAMAS DE HABILIDAD.
#
# Esta en setting/eng/skill.xml, en el atributo 互斥N ("mutuamente
# excluyente") de cada rama. Son once reglas:
#
#   Life <-> Wraith        Chaos <-> Earth
#   Meditate <-> Enhance   Grapple <-> Snipe
#   Mantle / Garment / Vestment  (las tres entre si)
#
# El servidor nunca comprobo nada: al recibir el 0x002F contenedor 10
# acepta la pareja que le manden. Quien se niega es el selector del
# cliente, y lo hace leyendo estos atributos. Quitandolos, el Skill Angel
# deja elegir cualquier rama y no hace falta el comando /rama.
#
# skill.xml vive en UPDATE8.PAK, data1.pak y update.pak, y ninguno de los
# tres lo sabe abrir nuestro lector (son del formato viejo). Por eso el
# arreglado se deja SUELTO en setting/eng/, que el cliente lee antes que
# el del pak -- lo mismo que se hace con el mapa de decoracion de la
# estacion. Para deshacerlo basta borrar ese archivo.
RUTA_SKILL_XML = 'setting/eng/skill.xml'
_RE_EXCLUSION = re.compile(r'\s*互斥\d+="[^"]*"')


def quitar_exclusion_ramas() -> int:
    """Deja skill.xml sin reglas de exclusion. Devuelve cuantas quito."""
    # La plantilla ya viene sin exclusiones y es lo unico que viaja en el
    # repo: extracted_paks no esta publicado.
    plantilla = pathlib.Path(__file__).parent / 'plantillas' / 'skill_sin_exclusion.xml.zlib'
    nuevo, cuantas = None, 0
    if plantilla.exists():
        try:
            nuevo = zlib.decompress(plantilla.read_bytes()).decode('utf-8')
            cuantas = 14
        except Exception:
            nuevo = None
    if nuevo is None:
        origen = None
        for sub in ('UPDATE8', 'update', 'data1'):
            f = RAIZ_PROYECTO / 'extracted_paks' / sub / 'setting' / 'eng' / 'skill.xml'
            if f.exists():
                origen = f
                break
        if origen is None:
            return 0
        txt = origen.read_text(encoding='utf-8-sig', errors='ignore')
        nuevo, cuantas = _RE_EXCLUSION.subn('', txt)
    if not cuantas:
        return 0
    ruta_cli = ruta_cliente()
    destino = ruta_cli / RUTA_SKILL_XML
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists() and destino.read_text(encoding='utf-8', errors='ignore') == nuevo:
            return cuantas
        destino.write_text(nuevo, encoding='utf-8')
        log.info('skill.xml suelto sin exclusiones: %d reglas quitadas' % cuantas)
    except OSError as e:
        log.warning('no se pudo escribir %s: %s' % (destino, e))
        return 0
    return cuantas


def abrir_clientes(cuantos: int = 1) -> int:
    """Lanza N copias de Angel.exe y devuelve cuantas arrancaron.

    El cliente se lanza con el directorio del juego como cwd, que es de
    donde lee reg.ini para saber a que servidor conectarse. Van con un
    respiro entre una y otra: arrancandolas de golpe se pisan leyendo los
    .pak y alguna se queda a medias.
    """
    ruta_cli = ruta_cliente()
    exe = ruta_cli / 'Angel.exe'
    if not exe.exists():
        log.warning('no esta %s, no se abre nada' % exe)
        return 0
    cuantos = max(1, min(int(cuantos or 1), MAX_CLIENTES))
    abiertos = 0
    for i in range(cuantos):
        try:
            subprocess.Popen([str(exe)], cwd=str(ruta_cli), close_fds=True)
            abiertos += 1
            if i + 1 < cuantos:
                time.sleep(RESPIRO_ENTRE_CLIENTES)
        except Exception as e:
            log.warning('no se pudo abrir la copia %d: %s' % (i + 1, e))
    log.info('abiertas %d copia(s) del cliente' % abiertos)
    return abiertos


async def _manejar_http(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Mini servidor HTTP para el panel embebido de START.EXE (permite cambiar modo estacional)."""
    try:
        req = await asyncio.wait_for(reader.read(2048), timeout=5.0)
        primera = req.decode('ascii', errors='ignore').splitlines()[0] if req else ''
        path = primera.split(' ')[1] if len(primera.split(' ')) > 1 else '/p.htm'

        if 'modo=' in path:
            nuevo_m = path.split('modo=', 1)[1].split('&')[0].strip().lower()
            if nuevo_m in MAPAS_ESTACION:
                aplicar_modo_estacion(nuevo_m)

        abiertos = 0
        if 'abrir=' in path:
            try:
                abiertos = abrir_clientes(int(path.split('abrir=', 1)[1]
                                              .split('&')[0].strip() or 1))
            except ValueError:
                abiertos = 0

        global IDIOMA_PANEL
        if 'lang=' in path:
            _l = path.split('lang=', 1)[1].split('&')[0].strip().lower()
            if _l in TEXTOS:
                IDIOMA_PANEL = _l
        T = TEXTOS.get(IDIOMA_PANEL, TEXTOS['es'])

        modo_act = getattr(_cf, 'MODO_ESTACION', 'normal')
        botones = []
        etiquetas = list(zip(('normal', 'navidad', 'halloween',
                              'sakura', 'verano'), T['temporadas']))
        for k, label in etiquetas:
            activo = (k == modo_act)
            bg = '#d4af37' if activo else '#2b3448'
            fg = '#111' if activo else '#e6edf3'
            botones.append(
                f'<a href="/p.htm?modo={k}" style="display:inline-block;margin:3px 4px;padding:4px 9px;'
                f'background:{bg};color:{fg};text-decoration:none;font-weight:bold;border:1px solid #637394;'
                f'font-size:11px;">{label}</a>'
            )

        sel = []
        for cod, nom in (('es', 'ES'), ('en', 'EN')):
            act = (cod == IDIOMA_PANEL)
            sel.append(
                f'<a href="/p.htm?lang={cod}" style="display:inline-block;'
                f'margin-left:4px;padding:2px 7px;'
                f'background:{"#d4af37" if act else "#2b3448"};'
                f'color:{"#111" if act else "#e6edf3"};text-decoration:none;'
                f'font-weight:bold;border:1px solid #637394;font-size:10px;">{nom}</a>')

        html = (
            "<html><head><meta charset='utf-8'>"
            "<style>body{margin:0;padding:10px 14px;background:#111622;color:#e6edf3;"
            "font-family:Tahoma,Arial,sans-serif;font-size:12px;overflow:hidden;}"
            "h3{margin:0 0 6px 0;color:#f5d76e;font-size:14px;display:inline-block;}"
            ".box{background:#1a2234;border:1px solid #354463;padding:8px 10px;margin-top:6px;}"
            ".ok{color:#56d364;font-weight:bold;}"
            ".lang{float:right;margin-top:2px;}"
            "</style></head><body>"
            f"<span class='lang'>{''.join(sel)}</span>"
            f"<h3>{T['titulo']}</h3>"
            f"<div>{T['estado']} <span class='ok'>{T['online']}</span> &nbsp;|&nbsp; "
            f"{T['estacion']} <b style='color:#f5d76e'>{modo_act.upper()}</b></div>"
            "<div class='box'><div style='margin-bottom:4px;color:#9fb1d1;'>"
            f"{T['cambiar']}</div>"
            + "".join(botones) +
            "</div>"
            "<div class='box'><div style='margin-bottom:4px;color:#9fb1d1;'>"
            f"{T['copias']}</div>"
            + "".join(
                f'<a href="/p.htm?abrir={n}" style="display:inline-block;'
                f'margin:3px 4px;padding:4px 11px;background:#2b3448;color:#e6edf3;'
                f'text-decoration:none;font-weight:bold;border:1px solid #637394;'
                f'font-size:11px;">x{n}</a>' for n in (1, 2, 3, 4, 5, 8))
            + (f"<span style='color:#56d364;margin-left:8px;'>{T['abiertas']} {abiertos}</span>"
               if abiertos else "")
            + "</div>"
            "<div style='margin-top:6px;color:#8b949e;font-size:11px;'>"
            f"&bull; {T['pie1']} &nbsp;|&nbsp; &bull; {T['pie2']}"
            "</div></body></html>"
        ).encode('utf-8')

        resp = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/html; charset=utf-8\r\n"
            b"Cache-Control: no-cache\r\n"
            + f"Content-Length: {len(html)}\r\n\r\n".encode('ascii')
            + html
        )
        writer.write(resp)
        await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def iniciar_servidores_launcher():
    """Inicia los servidores FTP (2121) y HTTP (8080) locales para START.EXE."""
    p_ftp = int(getattr(_cf, 'PUERTO_UPDATE_FTP', 2121))
    p_http = int(getattr(_cf, 'PUERTO_UPDATE_HTTP', 8080))
    srvs = []
    try:
        s_ftp = await asyncio.start_server(_manejar_ftp, '127.0.0.1', p_ftp)
        srvs.append(s_ftp)
        log.info(f"Servidor FTP de actualizacion (START.EXE) en 127.0.0.1:{p_ftp}")
    except Exception as e:
        log.warning(f"No se pudo abrir puerto FTP {p_ftp}: {e}")
    try:
        s_http = await asyncio.start_server(_manejar_http, '127.0.0.1', p_http)
        srvs.append(s_http)
        log.info(f"Servidor HTTP de noticias/estacion (START.EXE) en 127.0.0.1:{p_http}")
    except Exception as e:
        log.warning(f"No se pudo abrir puerto HTTP {p_http}: {e}")
    return srvs
