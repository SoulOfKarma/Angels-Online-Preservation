"""
Cuentas y personajes con base de datos SQLite local (cuentas.db).

Proteccion contra cortes de luz:
  - SQLite con modo WAL (Write-Ahead Logging) y PRAGMA synchronous = FULL.
  - Las transacciones son ACID y atomicas; un corte de suministro electrico o
    cierre inesperado del proceso NUNCA deja archivos truncados ni corrompidos.
  - Copias de seguridad automaticas y rotativas en data/backups/ mediante la
    API nativa de SQLite (con.backup).
  - Mantiene un espejo en data/cuentas.json para compatibilidad e inspeccion manual.
"""
import sqlite3
import json
import pathlib
import datetime
import hashlib
import hmac
import os
import tempfile
import threading
import time
import logging
import asyncio

log = logging.getLogger('cuentas')

BASE = pathlib.Path(__file__).parent.parent / 'data'
DB_PATH = BASE / 'cuentas.db'
BACKUPS_DIR = BASE / 'backups'
ARCHIVO = BASE / 'cuentas.json'
MUESTRAS = pathlib.Path(__file__).parent.parent / 'logs' / 'auth_muestras'

_LOCK = threading.RLock()

# LOS INTERRUPTORES DEL LOGIN viven en la tabla `configuracion` de cuentas.db.
# Antes eran variables de entorno (AO_VALIDAR_PASSWORD, AO_REGISTRAR_PRIMER_HASH,
# AO_GUARDAR_AUTH_CRUDO); el commit 5efe06d las quito del codigo y dejo la
# validacion siempre puesta. Ahora se cambian en la base:
#     UPDATE configuracion SET valor='0' WHERE clave='validar_password';
# y valen en el siguiente login, sin reiniciar el servidor.
CONFIGURACION_POR_DEFECTO = {
    'validar_password': ('1', 'Comprobar la contrasena al entrar (0 = entra cualquiera).'),
    'registrar_primer_hash': ('1', 'Una cuenta sin contrasena guardada se queda con la del '
                                   'primer ingreso (0 = se rechaza).'),
    'guardar_auth_crudo': ('0', 'Guardar el AUTH entero en logs/auth_muestras (para analizarlo).'),
    'reemplazar_contrasena': ('0', 'Si la contrasena no coincide, se queda la nueva en vez de '
                                   'rechazar. Para cambiarlas: encender, entrar con la nueva en '
                                   'cada cuenta, apagar.'),
}


def flag(clave: str) -> bool:
    """Lee un interruptor de la tabla configuracion ('1' = encendido)."""
    try:
        con = _get_conn()
        try:
            row = con.execute('SELECT valor FROM configuracion WHERE clave = ?', (clave,)).fetchone()
        finally:
            con.close()
        if row is not None:
            return str(row[0]).strip() == '1'
    except Exception:
        log.debug('configuracion %s', clave, exc_info=True)
    return CONFIGURACION_POR_DEFECTO.get(clave, ('0', ''))[0] == '1'


# Estructura del paquete AUTH (73 B):
#   [0:21]  char usuario[21] (texto plano terminado en nulo, con basura de pila al final)
#   [21:53] hash de 32 B (256 bits) de la contrasena (determinista)
#   [53:70] GUID / token de hardware del cliente (17 B)
#   [70:73] 3 B de residuo no inicializado de la pila (00 00 00, bb 00 00, 60 00 00, etc.)
OFF_HASH = 21
LARGO_HASH = 32

_CAMBIOS_DESDE_BACKUP = 0
_ULTIMO_BACKUP = time.time()
MAX_BACKUPS_CONSERVADOS = 10


def _get_conn():
    """Abre conexion a SQLite con protecciones contra cortes de luz."""
    BASE.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), timeout=15.0)
    con.execute('PRAGMA journal_mode = WAL;')
    con.execute('PRAGMA synchronous = FULL;')
    con.execute('PRAGMA foreign_keys = ON;')
    con.execute('PRAGMA busy_timeout = 10000;')
    return con


def _init_db():
    with _LOCK:
        BASE.mkdir(parents=True, exist_ok=True)
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        con = _get_conn()
        try:
            con.execute('''
            CREATE TABLE IF NOT EXISTS cuentas (
                usuario TEXT PRIMARY KEY COLLATE NOCASE,
                password TEXT NOT NULL DEFAULT '',
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ''')
            con.execute('''
            CREATE TABLE IF NOT EXISTS personajes (
                usuario TEXT NOT NULL COLLATE NOCASE,
                char_id INTEGER NOT NULL,
                ranura INTEGER NOT NULL,
                nombre TEXT NOT NULL,
                datos TEXT NOT NULL,
                actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (usuario, ranura),
                FOREIGN KEY (usuario) REFERENCES cuentas(usuario) ON DELETE CASCADE
            );
            ''')
            con.execute('CREATE INDEX IF NOT EXISTS idx_pj_char_id ON personajes(usuario, char_id);')
            # Los interruptores del login, en la base y no en variables de
            # entorno (ver CONFIGURACION_POR_DEFECTO).
            con.execute('''
            CREATE TABLE IF NOT EXISTS configuracion (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL,
                nota TEXT NOT NULL DEFAULT ''
            );
            ''')
            con.execute('''
            CREATE TABLE IF NOT EXISTS gremios (
                guild_id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
                lider_char_id INTEGER NOT NULL,
                nivel INTEGER NOT NULL DEFAULT 1,
                logo_id INTEGER NOT NULL DEFAULT 0,
                fondos INTEGER NOT NULL DEFAULT 0,
                reputacion INTEGER NOT NULL DEFAULT 0,
                cartel TEXT NOT NULL DEFAULT '',
                rango_0 TEXT NOT NULL DEFAULT 'Colonel',
                rango_1 TEXT NOT NULL DEFAULT 'Vice-colonel',
                rango_2 TEXT NOT NULL DEFAULT 'Cadre',
                rango_3 TEXT NOT NULL DEFAULT 'Members',
                perm_0 INTEGER NOT NULL DEFAULT -1,
                perm_1 INTEGER NOT NULL DEFAULT 16973824,
                perm_2 INTEGER NOT NULL DEFAULT 65536,
                perm_3 INTEGER NOT NULL DEFAULT 0,
                creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ''')
            # Las bases anteriores a la contribucion de liga ya tienen la tabla.
            if 'reputacion' not in {r[1] for r in con.execute('PRAGMA table_info(gremios)')}:
                con.execute('ALTER TABLE gremios ADD COLUMN reputacion INTEGER NOT NULL DEFAULT 0')
            con.execute('''
            CREATE TABLE IF NOT EXISTS gremio_miembros (
                guild_id INTEGER NOT NULL,
                char_id INTEGER PRIMARY KEY,
                nombre TEXT NOT NULL,
                nivel INTEGER NOT NULL DEFAULT 1,
                clase_id INTEGER NOT NULL DEFAULT 1,
                rango INTEGER NOT NULL DEFAULT 3,
                contribucion INTEGER NOT NULL DEFAULT 0,
                ingreso_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES gremios(guild_id) ON DELETE CASCADE
            );
            ''')
            con.execute('CREATE INDEX IF NOT EXISTS idx_gremio_miembros_guild ON gremio_miembros(guild_id);')
            con.execute('CREATE TABLE IF NOT EXISTS liga_farm_retorno ('
                        'char_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, '
                        'stage INTEGER NOT NULL, x INTEGER NOT NULL, y INTEGER NOT NULL)')
            con.execute('''
            CREATE TABLE IF NOT EXISTS gremio_territorios (
                tw_stage INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                capturado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (guild_id) REFERENCES gremios(guild_id) ON DELETE CASCADE
            );
            ''')
            con.execute('CREATE INDEX IF NOT EXISTS idx_gremio_territorios_guild ON gremio_territorios(guild_id);')
            con.execute('''
            CREATE TABLE IF NOT EXISTS liga_granja_cultivos (
                guild_id INTEGER NOT NULL,
                plot_id INTEGER NOT NULL,
                char_id INTEGER NOT NULL,
                char_name TEXT NOT NULL,
                crop_id INTEGER NOT NULL,
                sembrado_en INTEGER NOT NULL,
                madura_en INTEGER NOT NULL,
                marchita_en INTEGER NOT NULL,
                riego_count INTEGER NOT NULL DEFAULT 0,
                abono_count INTEGER NOT NULL DEFAULT 0,
                cosechado_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (guild_id, plot_id)
            );
            ''')
            # BANCO DE LIGA: los objetos por casilla. El oro va en gremios.fondos.
            con.execute('''
            CREATE TABLE IF NOT EXISTS gremio_banco (
                guild_id INTEGER NOT NULL,
                ranura INTEGER NOT NULL,
                item_id INTEGER NOT NULL,
                cantidad INTEGER NOT NULL DEFAULT 1,
                datos TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY (guild_id, ranura)
            );
            ''')
            if 'datos' not in {r[1] for r in con.execute('PRAGMA table_info(gremio_banco)')}:
                con.execute("ALTER TABLE gremio_banco ADD COLUMN datos TEXT NOT NULL DEFAULT '{}'")
            for clave, (valor, nota) in CONFIGURACION_POR_DEFECTO.items():
                con.execute('INSERT OR IGNORE INTO configuracion (clave, valor, nota) VALUES (?, ?, ?)',
                            (clave, valor, nota))
            con.commit()

            cur = con.cursor()
            cur.execute('SELECT COUNT(*) FROM cuentas')
            cant_cuentas = cur.fetchone()[0]
            if cant_cuentas == 0:
                _migrar_desde_json(con)
        finally:
            con.close()


def _migrar_desde_json(con):
    """Importa cuentas existentes de archivos JSON a SQLite."""
    candidatos = [
        ARCHIVO,
        BASE / 'cuentas_backup_karmav3_lv408.json',
        BASE / 'cuentas.json base',
        ARCHIVO.with_suffix('.json.bak'),
        BASE / 'cuentas.json2',
    ]
    datos_cargados = None
    for cand in candidatos:
        if cand.exists():
            try:
                txt = cand.read_text(encoding='utf-8')
                d = json.loads(txt)
                if d and isinstance(d.get('cuentas'), dict) and len(d['cuentas']) > 0:
                    datos_cargados = d
                    log.info(f"Migrando cuentas a SQLite desde {cand.name}")
                    break
            except Exception:
                continue

    if not datos_cargados:
        datos_cargados = {
            "cuentas": {
                "karma": {"password": "123456", "personajes": []}
            }
        }

    proximo_char_id = 1001
    cur = con.cursor()
    cur.execute("SELECT MAX(char_id) FROM personajes")
    row_m = cur.fetchone()
    if row_m and row_m[0]:
        proximo_char_id = row_m[0] + 1

    for u, c in datos_cargados.get('cuentas', {}).items():
        con.execute("INSERT OR REPLACE INTO cuentas (usuario, password) VALUES (?, ?)", (u, c.get('password', '')))
        for idx, p in enumerate(c.get('personajes', [])):
            r = int(p.get('ranura') if p.get('ranura') is not None else idx)
            cid = int(p.get('char_id') or 0)
            if not cid:
                cid = proximo_char_id
                proximo_char_id += 1
            p['char_id'] = cid
            con.execute(
                "INSERT OR REPLACE INTO personajes (usuario, char_id, ranura, nombre, datos) VALUES (?, ?, ?, ?, ?)",
                (u, cid, r, p.get('nombre', ''), json.dumps(p, ensure_ascii=False))
            )
    con.commit()
    log.info("Migracion automatica a SQLite completada exitosamente.")
    hacer_backup(motivo="migracion_inicial")




def hacer_backup(motivo="auto") -> pathlib.Path:
    """Copia de seguridad en caliente garantizada por la API nativa de SQLite."""
    global _CAMBIOS_DESDE_BACKUP, _ULTIMO_BACKUP
    with _LOCK:
        try:
            BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = BACKUPS_DIR / f"cuentas_auto_{ts}.db"
            src = sqlite3.connect(str(DB_PATH))
            dst = sqlite3.connect(str(backup_file))
            with dst:
                src.backup(dst)
            dst.close()
            src.close()
            _CAMBIOS_DESDE_BACKUP = 0
            _ULTIMO_BACKUP = time.time()
            log.info(f"Backup automatico creado en {backup_file.name} (motivo: {motivo})")
            _limpiar_backups_antiguos()
            _exportar_json_disco()
            return backup_file
        except Exception:
            log.exception("Error al crear backup automatico de SQLite")
            return None


def _limpiar_backups_antiguos():
    """Mantiene los ultimos N backups y purga los mas viejos para no llenar disco."""
    try:
        backups = sorted(BACKUPS_DIR.glob("cuentas_auto_*.db"), key=os.path.getmtime)
        if len(backups) > MAX_BACKUPS_CONSERVADOS:
            sobrantes = backups[:-MAX_BACKUPS_CONSERVADOS]
            for b in sobrantes:
                try:
                    b.unlink()
                except OSError:
                    pass
    except Exception:
        pass


def _exportar_json_disco():
    """Escribe data/cuentas.json de forma atomica para inspeccion externa."""
    temporal = None
    try:
        datos = cargar()
        fd, temporal = tempfile.mkstemp(prefix='cuentas_mirror_', suffix='.tmp', dir=str(BASE))
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(temporal), str(ARCHIVO))
        temporal = None
    except PermissionError:
        # El caso de siempre: cuentas.json esta ABIERTO en un editor y
        # Windows no deja reemplazarlo. No es un error de verdad -- el espejo
        # es solo para mirar, los datos viven en cuentas.db -- asi que basta
        # un aviso, sin la traza entera en cada guardado.
        log.warning("cuentas.json esta abierto en otro programa; el espejo "
                    "se actualizara cuando se cierre")
    except Exception:
        log.exception("Error al sincronizar cuentas.json espejo")
    finally:
        # Si el reemplazo fallo, el temporal se quedaba tirado en data/: se
        # habian juntado 71 (21 MB) con cuentas.json abierto en el editor.
        if temporal:
            try:
                os.remove(temporal)
            except OSError:
                pass


# El respaldo y el espejo cuentas.json van en un HILO APARTE. Se hacian en el
# mismo hilo que atiende el juego, en CADA cambio (cuentas.json entero con
# fsync, y cada 25 la copia de la base): al plantar en la granja el servidor
# se quedaba medio segundo parado con el "Backup automatico" en medio
# (hestia.log, 20/10/2026 16:19:38). Los cambios seguidos se juntan en uno.
_PENDIENTE_RESPALDO = threading.Event()
_RESPALDO_INMEDIATO = [False]
_HILO_RESPALDO = [None]
ESPERA_RESPALDO = 1.5


def _trabajador_respaldo():
    while True:
        _PENDIENTE_RESPALDO.wait()
        time.sleep(ESPERA_RESPALDO)       # junta los cambios que lleguen seguidos
        _PENDIENTE_RESPALDO.clear()
        inmediato, _RESPALDO_INMEDIATO[0] = _RESPALDO_INMEDIATO[0], False
        try:
            if inmediato or _CAMBIOS_DESDE_BACKUP >= 25 or (time.time() - _ULTIMO_BACKUP > 300):
                hacer_backup(motivo="cambios_frecuentes")
            else:
                _exportar_json_disco()
        except Exception:
            log.exception("Error en el respaldo en segundo plano")


def _notificar_cambio(inmediato=False):
    global _CAMBIOS_DESDE_BACKUP
    _CAMBIOS_DESDE_BACKUP += 1
    if inmediato:
        _RESPALDO_INMEDIATO[0] = True
    if _HILO_RESPALDO[0] is None or not _HILO_RESPALDO[0].is_alive():
        _HILO_RESPALDO[0] = threading.Thread(target=_trabajador_respaldo, name='respaldo-cuentas',
                                             daemon=True)
        _HILO_RESPALDO[0].start()
    _PENDIENTE_RESPALDO.set()


async def tarea_backup_periodico(intervalo_segundos=300):
    """Tarea asincrona de fondo que respalda la base de datos periodicamente."""
    while True:
        try:
            await asyncio.sleep(intervalo_segundos)
            if _CAMBIOS_DESDE_BACKUP > 0:
                hacer_backup(motivo="intervalo_periodico")
        except asyncio.CancelledError:
            hacer_backup(motivo="cierre_servidor")
            break
        except Exception:
            log.exception("Error en tarea_backup_periodico")


def cargar() -> dict:
    """Devuelve el arbol completo de cuentas y personajes desde SQLite."""
    with _LOCK:
        con = _get_conn()
        try:
            cur = con.cursor()
            cur.execute("SELECT usuario, password FROM cuentas ORDER BY usuario ASC")
            cuentas_dict = {}
            for u, pw in cur.fetchall():
                cuentas_dict[u] = {'password': pw, 'personajes': []}

            cur.execute("SELECT usuario, ranura, datos FROM personajes ORDER BY ranura ASC")
            for u, ranura, datos_json in cur.fetchall():
                # Encontrar cuenta coincidente (case-insensitive)
                cta = cuentas_dict.get(u)
                if cta is None:
                    for k in cuentas_dict:
                        if k.lower() == u.lower():
                            cta = cuentas_dict[k]
                            break
                if cta is not None:
                    try:
                        p_dict = json.loads(datos_json)
                        p_dict['ranura'] = ranura       # la de la base manda
                        cta['personajes'].append(p_dict)
                    except Exception:
                        pass
            return {'cuentas': cuentas_dict}
        finally:
            con.close()


def guardar_documento(datos: dict):
    """Guarda un documento completo en SQLite y sincroniza el espejo."""
    with _LOCK:
        con = _get_conn()
        try:
            for u, c in datos.get('cuentas', {}).items():
                con.execute("INSERT OR REPLACE INTO cuentas (usuario, password) VALUES (?, ?)", (u, c.get('password', '')))
                p_list = c.get('personajes', [])
                ranuras_activas = set()
                for idx, p in enumerate(p_list):
                    r = int(p.get('ranura') if p.get('ranura') is not None else idx)
                    ranuras_activas.add(r)
                    cid = int(p.get('char_id') or (1001 + r))
                    con.execute(
                        "INSERT OR REPLACE INTO personajes (usuario, char_id, ranura, nombre, datos) VALUES (?, ?, ?, ?, ?)",
                        (u, cid, r, p.get('nombre', ''), json.dumps(p, ensure_ascii=False))
                    )
                # Borrar personajes eliminados en esta cuenta
                cur = con.cursor()
                cur.execute("SELECT ranura FROM personajes WHERE usuario = ?", (u,))
                for (r_db,) in cur.fetchall():
                    if r_db not in ranuras_activas:
                        con.execute("DELETE FROM personajes WHERE usuario = ? AND ranura = ?", (u, r_db))
            con.commit()
            _notificar_cambio(inmediato=True)
        finally:
            con.close()


def _guardar(datos: dict):
    guardar_documento(datos)


def guardar_personaje_nuevo(usuario: str, p: dict):
    """Create only: never replace an occupied slot or reuse another name."""
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            r = int(p.get('ranura', 0))
            name = str(p.get('nombre', '')).strip()
            if not name or not 0 <= r < 3:
                raise ValueError('Invalid character name or slot')
            if any(str(n).casefold() == name.casefold() for (n,) in con.execute('SELECT nombre FROM personajes')):
                raise ValueError('Character name already exists')
            if con.execute('SELECT 1 FROM personajes WHERE usuario=? AND ranura=?', (usuario,r)).fetchone():
                raise ValueError('Character slot already occupied')
            cid = max(1001, int(con.execute('SELECT COALESCE(MAX(char_id),1000)+1 FROM personajes').fetchone()[0]))
            p.update(nombre=name, char_id=cid)
            con.execute("INSERT OR IGNORE INTO cuentas (usuario, password) VALUES (?, '')", (usuario,))
            con.execute(
                "INSERT INTO personajes (usuario, char_id, ranura, nombre, datos) VALUES (?, ?, ?, ?, ?)",
                (usuario, cid, r, p.get('nombre', ''), json.dumps(p, ensure_ascii=False))
            )
            con.commit()
            _notificar_cambio(inmediato=True)
        finally:
            con.close()


def _actualizar_personaje(usuario: str, char_id: int, mutador_fn):
    """Modifica un personaje en SQLite bajo una transaccion atomica protegida."""
    with _LOCK:
        con = _get_conn()
        try:
            cur = con.cursor()
            cur.execute("SELECT ranura, datos FROM personajes WHERE usuario = ? AND char_id = ?", (usuario, char_id))
            row = cur.fetchone()
            if not row:
                # Fallback: si char_id no coincide o hay 1 solo personaje para ese usuario
                cur.execute("SELECT ranura, datos FROM personajes WHERE usuario = ?", (usuario,))
                row = cur.fetchone()
                if not row:
                    return
            ranura, datos_json = row
            p = json.loads(datos_json)
            mutador_fn(p)
            con.execute(
                "UPDATE personajes SET nombre = ?, datos = ?, actualizado_en = CURRENT_TIMESTAMP WHERE usuario = ? AND ranura = ?",
                (p.get('nombre', ''), json.dumps(p, ensure_ascii=False), usuario, ranura)
            )
            con.commit()
            _notificar_cambio()
        finally:
            con.close()


def hash_de_auth(cuerpo: bytes) -> str:
    """Extrae el hash de contrasena del AUTH (32 bytes = 256 bits desde offset 21)."""
    if len(cuerpo) >= OFF_HASH + LARGO_HASH:
        return cuerpo[OFF_HASH:OFF_HASH + LARGO_HASH].hex()
    elif len(cuerpo) >= LARGO_HASH:
        return cuerpo[-LARGO_HASH:].hex()
    return cuerpo.hex() if cuerpo else ''


def _firmar(h: str, sal: str) -> str:
    return hashlib.sha256((sal + h).encode('ascii')).hexdigest()


def _personajes(con, usuario: str) -> list:
    """Personajes de la cuenta, cada uno con la ranura que tiene en la base."""
    pjs = []
    for r, d in con.execute("SELECT ranura, datos FROM personajes WHERE usuario = ? "
                            "ORDER BY ranura ASC", (usuario,)):
        p = json.loads(d)
        p['ranura'] = r
        pjs.append(p)
    return pjs


def lista_de_personajes(usuario: str) -> list:
    with _LOCK:
        con = _get_conn()
        try:
            return _personajes(con, usuario)
        finally:
            con.close()


def validar(usuario: str, cuerpo_auth: bytes = b'') -> tuple:
    """Valida la contrasena. Una cuenta sin contrasena guardada (nueva, o
    creada antes de esta validacion) se queda con la de este ingreso."""
    h = hash_de_auth(cuerpo_auth)
    validar_pw = flag('validar_password')
    if not h and validar_pw:
        return None, "contrasena vacia"
    with _LOCK:
        con = _get_conn()
        try:
            cur = con.cursor()
            cur.execute("SELECT password FROM cuentas WHERE usuario = ?", (usuario,))
            row = cur.fetchone()
            guardado = row[0] if row else ''
            if not validar_pw:
                # Sin validar: entra cualquiera, y la cuenta se crea si no esta.
                if row is None:
                    con.execute("INSERT INTO cuentas (usuario, password) VALUES (?, '')", (usuario,))
                    con.commit()
                    _notificar_cambio(inmediato=True)
                return {'personajes': _personajes(con, usuario)}, "ok (sin validar contrasena)"
            coincide = True
            if '$' in guardado:
                sal, firma = guardado.split('$', 1)
                coincide = hmac.compare_digest(_firmar(h, sal), firma)
                if not coincide:
                    # Compatibilidad con cuentas registradas con el hash legacy de 52 B:
                    # En 52 B se incluian 3 B de residuo de pila (cuerpo[70:73]) que
                    # variaban en cambio de personaje (ej. 60 00 00 o bb 00 00 en vez de 00 00 00).
                    # Se prueba con el padding de ceros o el slice directo de 52 B.
                    h52_cero = (cuerpo_auth[21:70] + b'\x00\x00\x00').hex() if len(cuerpo_auth) >= 70 else ''
                    h52_crudo = cuerpo_auth[-52:].hex() if len(cuerpo_auth) >= 52 else ''
                    if (h52_cero and hmac.compare_digest(_firmar(h52_cero, sal), firma)) or \
                       (h52_crudo and hmac.compare_digest(_firmar(h52_crudo, sal), firma)):
                        coincide = True
                        # Migrar transparentemente la cuenta al hash limpio de 32 B
                        sal_nueva = os.urandom(16).hex()
                        reg_nuevo = f"{sal_nueva}${_firmar(h, sal_nueva)}"
                        con.execute("UPDATE cuentas SET password = ? WHERE usuario = ?",
                                    (reg_nuevo, usuario))
                        con.commit()
                        _notificar_cambio(inmediato=True)
            if not coincide:
                if not flag('reemplazar_contrasena'):
                    return None, "contrasena incorrecta"
                sal = os.urandom(16).hex()
                con.execute("UPDATE cuentas SET password = ? WHERE usuario = ?",
                            (f"{sal}${_firmar(h, sal)}", usuario))
                con.commit()
                _notificar_cambio(inmediato=True)
                return {'personajes': _personajes(con, usuario)}, "contrasena reemplazada"
            if '$' in guardado:
                motivo = "ok"
            elif not flag('registrar_primer_hash'):
                return None, "la cuenta no tiene contrasena registrada"
            else:
                sal = os.urandom(16).hex()
                registro = f"{sal}${_firmar(h, sal)}"
                if row is None:
                    con.execute("INSERT INTO cuentas (usuario, password) VALUES (?, ?)",
                                (usuario, registro))
                    motivo = f"cuenta '{usuario}' creada en el primer ingreso"
                else:
                    con.execute("UPDATE cuentas SET password = ? WHERE usuario = ?",
                                (registro, usuario))
                    motivo = "contrasena registrada"
                con.commit()
                _notificar_cambio(inmediato=True)
            return {'personajes': _personajes(con, usuario)}, motivo
        finally:
            con.close()


def guardar_muestra_auth(bloque: bytes, nota: str = ""):
    MUESTRAS.mkdir(parents=True, exist_ok=True)
    marca = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    digest = hashlib.sha256(bloque).hexdigest()
    (MUESTRAS / f"auth_{marca}.sha256").write_text(digest, encoding='ascii')
    if flag('guardar_auth_crudo'):
        (MUESTRAS / f"auth_{marca}.bin").write_bytes(bloque)
    if nota:
        (MUESTRAS / f"auth_{marca}.txt").write_text(nota, encoding='utf-8')


def _ahora():
    return time.time()


def personaje_de(cuenta, ranura=0):
    """El personaje que esta en esa ranura (no en esa posicion de la lista)."""
    from login import Personaje
    p = next((x for x in (cuenta or {}).get('personajes', [])
              if x.get('ranura') == ranura), None)
    if p is None:
        return None
    # REPARACION AL CARGAR. El banco guarda cada casilla como (objeto,
    # cantidad); en memoria es tupla pero de la base vuelve como LISTA, y el
    # codigo del banco solo miraba la tupla. Al sacar algo, la lista entera
    # [objeto, cantidad] acababa DENTRO de la mochila como si fuera un id, y
    # desde ese momento todo lo que calcula peso o stats reventaba con
    # "int() ... not 'list'": no se podia mover nada. Aqui se deshace: la
    # casilla se queda con el objeto y la cantidad pasa a donde va.
    _cant_limpia = {int(k): int(v) for k, v in p.get('cantidades', {}).items()}
    _inv_limpio = {}
    for _k, _v in p.get('inventario', {}).items():
        if isinstance(_v, (list, tuple)):
            if not _v or not _v[0] or int(_v[0]) <= 0:
                continue
            _inv_limpio[int(_k)] = int(_v[0])
            if len(_v) > 1 and int(_v[1]) > 1:
                _cant_limpia[int(_k)] = int(_v[1])
        else:
            if _v and int(_v) > 0:
                _inv_limpio[int(_k)] = int(_v)
    _casa_limpia = dict(p.get('casa') or {})
    if _casa_limpia:
        _casa_limpia['is_open'] = False
        _casa_limpia['outdoor_obj_id'] = 0
        if _casa_limpia.get('deed_id'):
            _inv_limpio[376] = int(_casa_limpia['deed_id'])
    if 376 not in _inv_limpio:
        _inv_limpio[376] = 10115
    _exp_puesto = float(p.get('expiracion_puesto', 0) or 0.0)
    if _exp_puesto > 0 and _ahora() >= _exp_puesto:
        _inv_limpio.pop(166, None)
        _cant_limpia.pop(166, None)
        _exp_puesto = 0.0
    _st = p.get('stage_id', 51)
    _tx = p.get('tile_x', 150)
    _ty = p.get('tile_y', 100)
    if _st == 500:
        _cp_st = int((p.get('checkpoint') or {}).get('stage', 0) or 0)
        _cp_t = (p.get('checkpoint') or {}).get('tile') or [0, 0]
        if _cp_st and _cp_st != 500:
            _st = _cp_st
            _tx, _ty = int(_cp_t[0] or 150), int(_cp_t[1] or 100)
        else:
            _fac = p.get('faction') or ''
            _ciudades = {'Aurora': (3, 150, 105), 'Beasts': (26, 140, 150), 'Steel': (29, 150, 120), 'Shadow': (38, 150, 120)}
            _st, _tx, _ty = _ciudades.get(_fac, (41, 244, 30))
    return Personaje(
        entity_id=1000 + p['char_id'] % 1000,
        char_id=p['char_id'],
        nombre=p['nombre'],
        tile_x=_tx, tile_y=_ty,
        habilidades=[tuple(x) for x in p['habilidades']],
        barra=list(p['barra']),
        quests=[tuple(x) for x in p['quests']],
        hp=p.get('hp', 205), hp_max=p.get('hp_max', 205),
        mp=p.get('mp', 154), mp_max=p.get('mp_max', 154),
        inventario=_inv_limpio,
        sp=max(0, min(int(p.get('sp') or 0), 10 * 1000)),
        mejoras={int(k): v for k, v in (p.get('mejoras') or {}).items()},
        checkpoint_stage=int((p.get('checkpoint') or {}).get('stage', 0)),
        checkpoint_x=int(((p.get('checkpoint') or {}).get('tile') or [0, 0])[0]),
        checkpoint_y=int(((p.get('checkpoint') or {}).get('tile') or [0, 0])[1]),
        cantidades=_cant_limpia,
        tutorial=p.get('tutorial', 0),
        oro=p.get('oro', 0),
        stage=_st,
        faction=p.get('faction', 'Heaven'),
        nivel=p.get('nivel', 1),
        exp=p.get('exp', 0),
        banco={int(k): (tuple(v) if isinstance(v, list) else v)
               for k, v in p.get('banco', {}).items()},
        banco_oro=int(p.get('banco_oro', 0)),
        album={str(k): ([list(x) if isinstance(x, (list, tuple)) else x for x in v] if isinstance(v, (list, tuple)) else int(v)) for k, v in (p.get('album') or {}).items()},
        logros=[int(x) for x in (p.get('logros') or [])],
        recetas=[int(x) for x in (p.get('recetas') or [])],
        cartas=[int(x) for x in (p.get('cartas') or [])],
        cartas_canjes=[int(x) for x in (p.get('cartas_canjes') or [])],
        permisos=[str(x) for x in (p.get('permisos') or [])],
        estrellas=[tuple(x) for x in (p.get('estrellas') or [])
                   if isinstance(x, (list, tuple)) and len(x) >= 2],
        star_blessing=p.get('star_blessing') or {},
        travel_mark=p.get('travel_mark') or {},
        casa=_casa_limpia,
        buffs={int(k): v for k, v in (p.get('buffs') or {}).items()
               if str(k).isdigit() and isinstance(v, dict) and v.get('fin', 0) > _ahora()},
        class_id=p.get('class_id', 0),
        creditos=int(p.get('creditos', 0) or 0),
        rango=max(1, min(20, int(p.get('rango', 1) or 1))),
        banco_habilidades={int(k): list(v) for k, v in p.get('banco_habilidades', {}).items()},
        hechizos_aprendidos=set(p.get('hechizos_aprendidos', [])),
        mascota=_cargar_mascota(p.get('mascota')),
        mascotas=_cargar_mascotas(p),
        apariencia=list(p.get('apariencia') or [0, 0, 0, 8, 8]),
        quest_kills={str(k): int(v) for k, v in (p.get('quest_kills') or {}).items()},
        expiracion_puesto=_exp_puesto,
        emotes={int(x) for x in (p.get('emotes') or [])},
        quick_emotes={int(k): int(v) for k, v in (p.get('quick_emotes') or {0: -1, 1: -1, 2: -1, 3: -1}).items()},
        chat_filtros={int(k):int(v) for k,v in (p.get('chat_filtros') or {}).items()},
    )


def _cargar_mascotas(p: dict) -> dict:
    res = {}
    for k, v in (p.get('mascotas') or {}).items():
        if isinstance(v, dict) and v.get('sprite'):
            res[str(k)] = _cargar_mascota(v)
    if p.get('mascota') and isinstance(p.get('mascota'), dict) and p['mascota'].get('sprite'):
        m_act = _cargar_mascota(p['mascota'])
        r_k = str(m_act.get('ranura') if m_act.get('ranura') is not None else m_act.get('item', '0'))
        if r_k not in res:
            res[r_k] = m_act
    return res


def _cargar_mascota(m) -> dict:
    if not isinstance(m, dict) or not m.get('sprite'):
        return {}
    import mascotas as _ms
    f = dict(m)
    f['fuera'] = False
    f['entidad'] = None
    sp = int(f.get('sprite') or 0)
    nv = max(1, int(f.get('nivel') or 1))
    d = _ms.ficha_de_sprite(sp)
    if d.get('tipo'):
        f['tipo'] = d['tipo']
    st = _ms.stats_de(sp, nv)
    rango = int(f.get('rango') or 1)
    mult = getattr(_ms, 'RANGO_MULTIPLICADORES', {}).get(rango, 1.0)
    for k, v in st.items():
        if k in ('hp', 'mp') and f.get(k, 0) > 0:
            continue
        f[k] = max(1, int(round(v * mult))) if mult > 1.0 else v
    f.setdefault('saciedad', 100)
    f.setdefault('intimidad', 60)
    f.setdefault('estrellas', 1)
    f.setdefault('rango', 1)
    f.setdefault('npc_type', 0)
    f['rango_nombre'] = getattr(_ms, 'RANGO_NOMBRES', {}).get(rango, 'Common')
    if int(f.get('npc_type') or 0) > 0:
        # Repara fichas creadas por la implementación antigua: el rango no
        # fabrica estrellas ni multiplica stats, y la forma avanzada debe ser
        # la del monstruo capturado incluso después de reconectar.
        f['estrellas'] = _ms.calcular_estrellas_total(f.get('bonos') or {})
        import house_services as _hs_cap
        ident = _hs_cap.captured_monster_identity(f['npc_type'])
        captured_name = f.get('captured_name') or _ms.abreviar_nombre_pet(ident['nombre'])
        captured_tipo = int(f.get('captured_tipo') or ident['sprite'] or 0)
        f['captured_name'] = captured_name
        if captured_tipo:
            f['captured_tipo'] = captured_tipo

        # Preservar el nombre:
        # 1. Si fue renombrada por el jugador, mantenerla intacta.
        # 2. Si no fue renombrada, asegurarse de que no quede con arquetipos genéricos
        #    ('Clown', 'Blue Crab', 'Monster Egg', 'Pet') o nombres truncados ('Mutated Chin').
        es_renombrada = bool(f.get('renombrada'))
        cur_nom = f.get('nombre')
        if not es_renombrada:
            if not cur_nom or cur_nom in ('Clown', 'Blue Crab', 'Monster Egg', 'Pet', 'Mutated Chin', 'Mutated Chim'):
                f['nombre'] = captured_name

        if not any(_ms.ramas_de(sp)):
            if captured_tipo:
                f['tipo'] = captured_tipo
    return f


def borrar_personaje(usuario: str, ranura: int):
    """Borra el personaje de esa ranura en SQLite. Devuelve su char_id o None."""
    with _LOCK:
        con = _get_conn()
        try:
            cur = con.cursor()
            cur.execute("SELECT char_id FROM personajes WHERE usuario = ? AND ranura = ?", (usuario, ranura))
            row = cur.fetchone()
            if not row:
                return None
            char_id = row[0]
            con.execute("DELETE FROM personajes WHERE usuario = ? AND ranura = ?", (usuario, ranura))
            con.commit()
            _notificar_cambio(inmediato=True)
            return char_id
        finally:
            con.close()


def _slot_sort_key(item):
    k = item[0] if isinstance(item, (tuple, list)) else item
    try:
        return (0, int(k))
    except (ValueError, TypeError):
        return (1, str(k))


def inventario_equivalente(datos, bolsa, cantidades):
    """Compare item quantities, not sparse JSON representations.

    Saving omits singleton counts; login also synthesizes the active house
    deed in376. Neither is an inventory transaction. Real stack/item changes
    still fail the optimistic check; orphan count keys carry no item.
    """
    def foto(items, counts):
        counts = {int(k):int(v) for k,v in (counts or {}).items()}
        out = {}
        for slot,value in (items or {}).items():
            slot = int(slot)
            embedded = 1
            if isinstance(value,(list,tuple)):
                if not value:
                    continue
                embedded = int(value[1]) if len(value)>1 else 1
                value = value[0]
            if not value or int(value)<=0:
                continue
            qty = counts.get(slot,embedded)
            out[slot] = (int(value),max(0 if 497<=slot<=556 else 1,qty))
        return out
    saved = foto(datos.get('inventario'),datos.get('cantidades'))
    current = foto(bolsa,cantidades)
    deed = int((datos.get('casa') or {}).get('deed_id') or 10115)
    if 376 not in saved and current.get(376)==(deed,1):
        saved[376] = current[376]
    return saved==current


def guardar_inventario(usuario: str, char_id: int, bolsa: dict,
                       cantidades=None, mejoras=None, expiracion_puesto=None):
    def _mut(p):
        p['inventario'] = {str(k): int(v) for k, v in sorted(bolsa.items(), key=_slot_sort_key) if v and int(v) > 0}
        if mejoras is not None:
            p['mejoras'] = {str(k): v
                            for k, v in sorted(mejoras.items(), key=_slot_sort_key)
                            if v and (v.get('veces') or v.get('gemas')
                                      or v.get('extra') or v.get('vinculacion')
                                      or v.get('house_egg_deadline') or v.get('mercenary_token_deadline') or v.get('holy_pass_fin')
                                      or v.get('arena_premio_fin') or v.get('mall_fin'))}
        if cantidades is not None:
            p['cantidades'] = {str(k): int(v)
                               for k, v in sorted(cantidades.items(), key=_slot_sort_key)
                               if (int(v) > 1 or 497 <= int(k) <= 556) and (int(k) in bolsa or str(k) in bolsa)}
        if expiracion_puesto is not None:
            p['expiracion_puesto'] = float(expiracion_puesto)
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_mejoras(usuario: str, char_id: int, mejoras: dict):
    if not usuario:
        return
    def _mut(p):
        p['mejoras'] = {str(k): v for k, v in sorted((mejoras or {}).items(), key=_slot_sort_key)
                        if v and (v.get('veces') or v.get('gemas')
                                  or v.get('extra') or v.get('vinculacion')
                                  or v.get('house_egg_deadline') or v.get('mercenary_token_deadline') or v.get('holy_pass_fin')
                                  or v.get('arena_premio_fin') or v.get('mall_fin'))}
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_checkpoint(usuario: str, char_id: int, stage: int, tx: int, ty: int):
    def _mut(p):
        p['checkpoint'] = {'stage': int(stage), 'tile': [int(tx), int(ty)]}
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_habilidades(usuario: str, char_id: int, habilidades):
    def _mut(p):
        p['habilidades'] = [list(h) for h in habilidades]
        banco = p.setdefault('banco_habilidades', {})
        for h in habilidades:
            if isinstance(h, (list, tuple)) and len(h) >= 2:
                banco[str(h[0])] = [int(h[1]), int(h[2]) if len(h) > 2 else 0]
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_hechizos(usuario: str, char_id: int, hechizos):
    def _mut(p):
        p['hechizos_aprendidos'] = list(hechizos)
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_banco_habilidades(usuario: str, char_id: int, banco: dict):
    def _mut(p):
        p['banco_habilidades'] = {str(k): list(v) for k, v in banco.items()}
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_clase(usuario: str, char_id: int, class_id: int):
    def _mut(p):
        p['class_id'] = class_id
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_posicion(usuario: str, char_id: int, tile_x: int, tile_y: int):
    def _mut(p):
        p['tile_x'], p['tile_y'] = int(tile_x), int(tile_y)
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_tutorial(usuario: str, char_id: int, etapa: int):
    def _mut(p):
        p['tutorial'] = int(etapa)
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_quests(usuario: str, char_id: int, quests: list):
    if not usuario:
        return
    def _mut(p):
        p['quests'] = [list(q) for q in (quests or [])]
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_quest_kills(usuario: str, char_id: int, quest_kills: dict):
    if not usuario:
        return
    def _mut(p):
        p['quest_kills'] = {str(k): int(v) for k, v in (quest_kills or {}).items()}
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_oro(usuario: str, char_id: int, oro: int):
    def _mut(p):
        p['oro'] = int(oro)
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_barra(usuario: str, char_id: int, barra: list):
    def _mut(p):
        p['barra'] = list(barra)
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_mapa(usuario: str, char_id: int, stage: int, tile_x: int, tile_y: int):
    def _mut(p):
        p['stage_id'] = int(stage)
        p['tile_x'], p['tile_y'] = int(tile_x), int(tile_y)
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_faccion(usuario: str, char_id: int, faccion: str):
    def _mut(p):
        p['faction'] = faccion
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_progreso(usuario: str, char_id: int, nivel: int, exp: int,
                     hp: int = None, mp: int = None, habilidades: list = None,
                     hp_max: int = None, mp_max: int = None, sp: int = None,
                     buffs: dict = None):
    def _mut(p):
        p['nivel'] = int(nivel)
        p['exp'] = int(exp)
        if sp is not None:
            p['sp'] = max(0, int(sp))
        if buffs is not None:
            p['buffs'] = {str(k): v for k, v in (buffs or {}).items()
                          if isinstance(v, dict) and v.get('fin', 0) > 0}
        if hp is not None:
            p['hp'] = int(hp)
        if hp_max is not None:
            p['hp_max'] = int(hp_max)
        if mp is not None:
            p['mp'] = int(mp)
        if mp_max is not None:
            p['mp_max'] = int(mp_max)
        if habilidades is not None:
            p['habilidades'] = [list(h) for h in habilidades]
            banco = p.setdefault('banco_habilidades', {})
            for h in habilidades:
                if isinstance(h, (list, tuple)) and len(h) >= 2:
                    banco[str(h[0])] = [int(h[1]), int(h[2]) if len(h) > 2 else 0]
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_sistemas(usuario: str, char_id: int, p):
    def _mut(fila):
        fila['album'] = {str(k): ([list(x) if isinstance(x, (list, tuple)) else x for x in v] if isinstance(v, (list, tuple)) else int(v))
                         for k, v in (getattr(p, 'album', None) or {}).items()}
        fila['logros'] = sorted({int(x) for x in (getattr(p, 'logros', None) or [])})
        fila['cartas'] = sorted({int(x) for x in (getattr(p, 'cartas', None) or [])})
        fila['permisos'] = sorted({str(x) for x in (getattr(p, 'permisos', None) or [])})
        fila['estrellas'] = [list(x) for x in (getattr(p, 'estrellas', None) or [])]
        c_val = getattr(p, 'casa', None)
        if hasattr(c_val, 'serializar'):
            fila['casa'] = c_val.serializar()
        elif isinstance(c_val, dict):
            fila['casa'] = dict(c_val)
        else:
            fila['casa'] = {}
        fila['emotes'] = sorted({int(x) for x in (getattr(p, 'emotes', None) or [])})
        fila['quick_emotes'] = {str(k): int(v) for k, v in (getattr(p, 'quick_emotes', None) or {}).items()}
        fila['chat_filtros'] = {str(k):int(v) for k,v in (getattr(p,'chat_filtros',None) or {}).items()}
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_casa(usuario: str, char_id: int, casa):
    def _mut(fila):
        if hasattr(casa, 'serializar'):
            fila['casa'] = casa.serializar()
        elif isinstance(casa, dict):
            fila['casa'] = dict(casa)
        else:
            fila['casa'] = {}
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_casa_e_inventario(usuario: str, char_id: int, casa, bolsa: dict,
                               cantidades=None, mejoras=None):
    """Commit a decoration save atomically.

    Placing and taking back furniture changes both the house and the
    Furniture bag.  Persisting those in separate transactions can duplicate
    or lose an item if the process stops between writes.
    """
    casa_data = casa.serializar() if hasattr(casa, 'serializar') else dict(casa or {})
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute(
                'SELECT datos FROM personajes WHERE usuario=? AND char_id=?',
                (usuario, int(char_id))).fetchone()
            if row is None:
                raise ValueError('Character no longer exists.')
            datos = json.loads(row[0])
            datos['casa'] = casa_data
            datos['inventario'] = {
                str(k): int(v) for k, v in sorted(bolsa.items(), key=_slot_sort_key) if v and int(v) > 0
            }
            if cantidades is not None:
                datos['cantidades'] = {
                    str(k): int(v)
                    for k, v in sorted(cantidades.items(), key=_slot_sort_key)
                    if (int(v) > 1 or 497 <= int(k) <= 556)
                    and (int(k) in bolsa or str(k) in bolsa)
                }
            if mejoras is not None:
                datos['mejoras'] = {
                    str(k): v
                    for k, v in sorted(mejoras.items(), key=_slot_sort_key)
                    if v and (v.get('veces') or v.get('gemas')
                              or v.get('extra') or v.get('vinculacion')
                              or v.get('house_egg_deadline') or v.get('mercenary_token_deadline') or v.get('holy_pass_fin')
                              or v.get('arena_premio_fin') or v.get('mall_fin'))
                }
            con.execute(
                'UPDATE personajes SET datos=?, actualizado_en=CURRENT_TIMESTAMP '
                'WHERE usuario=? AND char_id=?',
                (json.dumps(datos, ensure_ascii=False), usuario, int(char_id)))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
    _notificar_cambio(inmediato=True)


def todas_las_casas_abiertas() -> list:
    """Return all open outdoor house data saved across all characters."""
    out = []
    with _LOCK:
        con = _get_conn()
        try:
            cur = con.execute('SELECT char_id, nombre, datos FROM personajes')
            for row in cur:
                if not row[2]:
                    continue
                try:
                    cid = int(row[0])
                    nom = row[1] or ''
                    d = json.loads(row[2])
                    c = d.get('casa')
                    if isinstance(c, dict) and c.get('is_open') and c.get('outdoor_stage'):
                        out.append((cid, nom, c))
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            con.close()
    return out


def guardar_emotes(usuario: str, char_id: int, emotes):
    def _mut(fila):
        fila['emotes'] = sorted({int(x) for x in (emotes or [])})
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_quick_emotes(usuario: str, char_id: int, quick_emotes):
    def _mut(fila):
        fila['quick_emotes'] = {str(k): int(v) for k, v in (quick_emotes or {}).items()}
    _actualizar_personaje(usuario, char_id, _mut)

def guardar_chat_filtros(usuario: str, char_id: int, filtros):
    """Strict owner/character update: never fall back to another character."""
    with _LOCK:
        with _get_conn() as con:
            rows=con.execute('SELECT rowid,datos FROM personajes WHERE usuario=? AND char_id=?',
                             (usuario,char_id)).fetchall()
            if len(rows)!=1:return False
            rowid,raw=rows[0]
            data=json.loads(raw)
            data['chat_filtros']={str(k):int(v) for k,v in filtros.items()}
            con.execute('UPDATE personajes SET datos=? WHERE rowid=? AND usuario=? AND char_id=?',
                        (json.dumps(data,ensure_ascii=False),rowid,usuario,char_id))
    _notificar_cambio()
    return True


def guardar_cardbook(usuario: str, char_id: int, plan):
    """Commit card ownership/redemptions and inventory in ONE transaction.

    Require the exact authenticated character; do not fall back to a different
    slot. Never write whole account JSON or change unrelated systems.
    """
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute(
                'SELECT ranura, datos FROM personajes WHERE usuario=? AND char_id=?',
                (usuario, char_id)).fetchone()
            if row is None:
                raise ValueError('Character no longer exists.')
            datos = json.loads(row[1])
            datos['cartas'] = sorted(set(int(x) for x in plan.personaje.cartas))
            datos['cartas_canjes'] = sorted(set(int(x) for x in
                                                 plan.personaje.cartas_canjes))
            datos['inventario'] = {str(k): int(v) for k, v in plan.inventario.items() if v and int(v) > 0}
            datos['cantidades'] = {str(k): int(v) for k, v in plan.cantidades.items()
                                    if int(k) in plan.inventario}
            datos['mejoras'] = {str(k): v for k, v in
                                (getattr(plan.personaje, 'mejoras', {}) or {}).items()}
            # Reward items may themselves be pets; _meter prepares their data.
            datos['mascota'] = getattr(plan.personaje, 'mascota', {}) or {}
            datos['mascotas'] = getattr(plan.personaje, 'mascotas', {}) or {}
            con.execute('UPDATE personajes SET datos=?, actualizado_en=CURRENT_TIMESTAMP '
                        'WHERE usuario=? AND char_id=?',
                        (json.dumps(datos, ensure_ascii=False), usuario, char_id))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        _notificar_cambio(inmediato=True)


def guardar_banco(usuario: str, char_id: int, banco: dict):
    def _mut(p):
        p['banco'] = {str(k): v for k, v in sorted(banco.items(), key=_slot_sort_key)}
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_banco_oro(usuario: str, char_id: int, oro: int):
    def _mut(p):
        p['banco_oro'] = int(oro)
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_buffs(usuario: str, char_id: int, buffs: dict):
    def _mut(p):
        p['buffs'] = buffs
    _actualizar_personaje(usuario, char_id, _mut)


def guardar_mascota(usuario: str, char_id: int, mascota: dict, mascotas: dict = None):
    if not usuario:
        return
    def _mut(p):
        m_dict = p.setdefault('mascotas', {})
        if mascotas and isinstance(mascotas, dict):
            for k, v in mascotas.items():
                if isinstance(v, dict) and v.get('sprite'):
                    clean_v = {ck: cv for ck, cv in v.items() if ck not in ('entidad',)}
                    clean_v['fuera'] = False
                    m_dict[str(k)] = clean_v
        if mascota and isinstance(mascota, dict) and mascota.get('sprite'):
            limpia = {k: v for k, v in mascota.items() if k not in ('entidad',)}
            limpia['fuera'] = False
            p['mascota'] = limpia
            r_key = str(limpia.get('ranura') if limpia.get('ranura') is not None else limpia.get('item', '0'))
            m_dict[r_key] = limpia
        else:
            p.pop('mascota', None)
    _actualizar_personaje(usuario, char_id, _mut)


def confirmar_entrega_productor(usuario, char_id, consumption, rewards, bonus=None):
    """Atomically apply only the validated order slots and its reward deltas.

    Never replaces inventory from a session snapshot or falls back to another
    character. apply_delivery validates all affected slots before any write.
    """
    from producer_orders import apply_delivery
    import combate
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT datos FROM personajes WHERE usuario=? AND char_id=?',
                              (usuario, char_id)).fetchone()
            if not row:
                raise ValueError('Producer delivery character not found')
            before = json.loads(row[0])
            after, touched = apply_delivery(before, consumption, rewards, bonus,
                                             combate.exp_para_nivel, combate.nivel_maximo(),
                                             combate.rango_de_creditos)
            con.execute('UPDATE personajes SET datos=?, actualizado_en=CURRENT_TIMESTAMP '
                        'WHERE usuario=? AND char_id=?',
                        (json.dumps(after, ensure_ascii=False), usuario, char_id))
            con.commit()
            _notificar_cambio()
            return after, touched
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def guardar_rango(usuario: str, char_id: int, rango: int, creditos: int = None):
    if not usuario:
        return
    def _mut(p):
        p['rango'] = max(1, min(20, int(rango or 1)))
        if creditos is not None:
            p['creditos'] = int(creditos or 0)
    _actualizar_personaje(usuario, char_id, _mut)


# =========================================================================
# OPERACIONES DE BASE DE DATOS PARA GREMIOS (GUILDS / LIGAS)
# =========================================================================

def _fila_a_gremio(row) -> dict:
    if not row:
        return None
    return {
        'guild_id': int(row[0]),
        'nombre': str(row[1]),
        'lider_char_id': int(row[2]),
        'nivel': int(row[3]),
        'logo_id': int(row[4]),
        'fondos': int(row[5]),
        'cartel': str(row[6] or ''),
        'rangos': [str(row[7]), str(row[8]), str(row[9]), str(row[10])],
        'permisos': [int(row[11]), int(row[12]), int(row[13]), int(row[14])],
        'creado_en': str(row[15]),
        'reputacion': int(row[16]),
    }


def db_crear_gremio(nombre: str, lider_char_id: int, lider_nombre: str,
                    lider_nivel: int = 1, lider_clase: int = 1,
                    logo_id: int = 0, cartel: str = '', usuario=None, oro_final=None) -> int:
    with _LOCK:
        con = _get_conn()
        try:
            cur = con.cursor()
            cur.execute('BEGIN IMMEDIATE')
            if usuario is not None:
                row = cur.execute('SELECT ranura, datos FROM personajes WHERE usuario=? AND char_id=?',
                                  (usuario, lider_char_id)).fetchone()
                if not row or oro_final is None or int(oro_final) < 0:
                    raise ValueError('No se puede cobrar la creacion de la liga')
                pj = json.loads(row[1])
                pj['oro'] = int(oro_final)
                cur.execute('UPDATE personajes SET datos=?, actualizado_en=CURRENT_TIMESTAMP '
                            'WHERE usuario=? AND ranura=?',
                            (json.dumps(pj, ensure_ascii=False), usuario, row[0]))
            cur.execute('''
            INSERT INTO gremios (nombre, lider_char_id, logo_id, cartel)
            VALUES (?, ?, ?, ?)
            ''', (nombre, lider_char_id, logo_id, cartel))
            gid = cur.lastrowid
            cur.execute('''
            INSERT INTO gremio_miembros (guild_id, char_id, nombre, nivel, clase_id, rango, contribucion)
            VALUES (?, ?, ?, ?, ?, 0, 0)
            ''', (gid, lider_char_id, lider_nombre, lider_nivel, lider_clase))
            con.commit()
            _notificar_cambio()
            return gid
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_obtener_gremio(guild_id: int):
    if not guild_id:
        return None
    with _LOCK:
        con = _get_conn()
        try:
            row = con.execute('''
            SELECT guild_id, nombre, lider_char_id, nivel, logo_id, fondos, cartel,
                   rango_0, rango_1, rango_2, rango_3,
                   perm_0, perm_1, perm_2, perm_3, creado_en, reputacion
            FROM gremios WHERE guild_id = ?
            ''', (guild_id,)).fetchone()
            return _fila_a_gremio(row)
        finally:
            con.close()


def db_obtener_gremio_por_nombre(nombre: str):
    if not nombre:
        return None
    with _LOCK:
        con = _get_conn()
        try:
            row = con.execute('''
            SELECT guild_id, nombre, lider_char_id, nivel, logo_id, fondos, cartel,
                   rango_0, rango_1, rango_2, rango_3,
                   perm_0, perm_1, perm_2, perm_3, creado_en, reputacion
            FROM gremios WHERE nombre = ? COLLATE NOCASE
            ''', (nombre.strip(),)).fetchone()
            return _fila_a_gremio(row)
        finally:
            con.close()


def db_obtener_gremio_de_personaje(char_id: int):
    if not char_id:
        return None
    with _LOCK:
        con = _get_conn()
        try:
            row = con.execute('''
            SELECT g.guild_id, g.nombre, g.lider_char_id, g.nivel, g.logo_id, g.fondos, g.cartel,
                   g.rango_0, g.rango_1, g.rango_2, g.rango_3,
                   g.perm_0, g.perm_1, g.perm_2, g.perm_3, g.creado_en, g.reputacion
            FROM gremios g
            JOIN gremio_miembros m ON g.guild_id = m.guild_id
            WHERE m.char_id = ?
            ''', (char_id,)).fetchone()
            return _fila_a_gremio(row)
        finally:
            con.close()


def db_obtener_miembros_gremio(guild_id: int) -> list:
    if not guild_id:
        return []
    with _LOCK:
        con = _get_conn()
        try:
            cur = con.cursor()
            cur.execute('''
            SELECT char_id, nombre, nivel, clase_id, rango, contribucion, ingreso_en
            FROM gremio_miembros
            WHERE guild_id = ?
            ORDER BY rango ASC, nivel DESC
            ''', (guild_id,))
            res = []
            for r in cur.fetchall():
                res.append({
                    'char_id': int(r[0]),
                    'nombre': str(r[1]),
                    'nivel': int(r[2]),
                    'clase_id': int(r[3]),
                    'rango': int(r[4]),
                    'contribucion': int(r[5]),
                    'ingreso_en': str(r[6]),
                })
            return res
        finally:
            con.close()


def db_contribuir_gremio(usuario: str, char_id: int, guild_id: int,
                         puntos: int, bolsa: dict, cantidades: dict):
    """Guarda materiales consumidos y reputacion en la misma transaccion."""
    puntos = int(puntos)
    if not usuario or puntos <= 0:
        raise ValueError('contribucion invalida')
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT ranura, datos FROM personajes WHERE usuario = ? AND char_id = ?',
                              (usuario, char_id)).fetchone()
            miembro = con.execute('SELECT contribucion FROM gremio_miembros WHERE guild_id = ? AND char_id = ?',
                                  (guild_id, char_id)).fetchone()
            guild = con.execute('SELECT reputacion FROM gremios WHERE guild_id = ?', (guild_id,)).fetchone()
            if not row or not miembro or not guild:
                raise ValueError('personaje o liga inexistente')
            if int(miembro[0]) + puntos > 0xffffffff or int(guild[0]) + puntos > 0xffffffff:
                raise ValueError('limite de reputacion alcanzado')
            import gremios
            nuevo_nivel = gremios.nivel_por_reputacion(int(guild[0]) + puntos)
            con.execute('UPDATE gremios SET nivel=MAX(nivel, ?) WHERE guild_id=?',
                        (nuevo_nivel, guild_id))
            ranura, datos = row
            pj = json.loads(datos)
            pj['inventario'] = {str(k): int(v) for k, v in sorted(bolsa.items(), key=_slot_sort_key)
                                if v and int(v) > 0}
            pj['cantidades'] = {str(k): int(v) for k, v in sorted(cantidades.items(), key=_slot_sort_key)
                                if (int(v) > 1 or 497 <= int(k) <= 556)
                                and (int(k) in bolsa or str(k) in bolsa)}
            con.execute('UPDATE personajes SET datos = ?, actualizado_en = CURRENT_TIMESTAMP '
                        'WHERE usuario = ? AND ranura = ?',
                        (json.dumps(pj, ensure_ascii=False), usuario, ranura))
            con.execute('UPDATE gremios SET reputacion = reputacion + ? WHERE guild_id = ?',
                        (puntos, guild_id))
            con.execute('UPDATE gremio_miembros SET contribucion = contribucion + ? '
                        'WHERE guild_id = ? AND char_id = ?', (puntos, guild_id, char_id))
            con.commit()
            _notificar_cambio()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_agregar_miembro_gremio(guild_id: int, char_id: int, nombre: str,
                              nivel: int = 1, clase_id: int = 1,
                              rango: int = 3, contribucion: int = 0):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('''
            INSERT INTO gremio_miembros
            (guild_id, char_id, nombre, nivel, clase_id, rango, contribucion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (guild_id, char_id, nombre, nivel, clase_id, rango, contribucion))
            con.commit()
            _notificar_cambio()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_remover_miembro_gremio(char_id: int):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('DELETE FROM gremio_miembros WHERE char_id = ?', (char_id,))
            con.commit()
            _notificar_cambio()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_actualizar_rango_miembro(char_id: int, nuevo_rango: int):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('UPDATE gremio_miembros SET rango = ? WHERE char_id = ?',
                        (nuevo_rango, char_id))
            con.commit()
            _notificar_cambio()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_actualizar_cartel_gremio(guild_id: int, nuevo_cartel: str):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('UPDATE gremios SET cartel = ? WHERE guild_id = ?',
                        (nuevo_cartel, guild_id))
            con.commit()
            _notificar_cambio()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_actualizar_logo_gremio(guild_id: int, nuevo_logo: int):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('UPDATE gremios SET logo_id = ? WHERE guild_id = ?',
                        (nuevo_logo, guild_id))
            con.commit()
            _notificar_cambio()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_actualizar_permisos_gremio(guild_id: int, rango_idx: int, nuevo_perm: int):
    if not (0 <= rango_idx <= 3):
        return
    col = f'perm_{rango_idx}'
    with _LOCK:
        con = _get_conn()
        try:
            con.execute(f'UPDATE gremios SET {col} = ? WHERE guild_id = ?',
                        (nuevo_perm, guild_id))
            con.commit()
            _notificar_cambio()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_actualizar_nombre_rango_gremio(guild_id: int, rango_idx: int, nuevo_nombre: str):
    if not (0 <= rango_idx <= 3):
        return
    col = f'rango_{rango_idx}'
    with _LOCK:
        con = _get_conn()
        try:
            con.execute(f'UPDATE gremios SET {col} = ? WHERE guild_id = ?',
                        (nuevo_nombre, guild_id))
            con.commit()
            _notificar_cambio()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_transferir_liderazgo_gremio(guild_id: int, nuevo_lider_char_id: int):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            anterior = con.execute('SELECT lider_char_id FROM gremios WHERE guild_id=?',
                                   (guild_id,)).fetchone()
            nuevo = con.execute('SELECT 1 FROM gremio_miembros WHERE guild_id=? AND char_id=?',
                                (guild_id, nuevo_lider_char_id)).fetchone()
            if not anterior or not nuevo or anterior[0] == nuevo_lider_char_id:
                raise ValueError('Transferencia de liga invalida')
            con.execute('UPDATE gremio_miembros SET rango=1 WHERE guild_id=? AND char_id=?',
                        (guild_id, anterior[0]))
            con.execute('UPDATE gremio_miembros SET rango=0 WHERE guild_id=? AND char_id=?',
                        (guild_id, nuevo_lider_char_id))
            con.execute('UPDATE gremios SET lider_char_id = ? WHERE guild_id = ?',
                        (nuevo_lider_char_id, guild_id))
            con.commit()
            _notificar_cambio()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_disolver_gremio(guild_id: int):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('DELETE FROM gremio_miembros WHERE guild_id = ?', (guild_id,))
            con.execute('DELETE FROM gremios WHERE guild_id = ?', (guild_id,))
            con.commit()
            _notificar_cambio()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


# Inicializar base de datos y migrar si es necesario al importar el modulo
_init_db()


# =========================================================================
# BANCO DE LIGA
# =========================================================================

def db_banco_gremio(guild_id: int) -> dict:
    """{ranura: (item_id, cantidad)} del banco de la liga."""
    with _LOCK:
        con = _get_conn()
        try:
            return {int(r): (int(i), int(c)) for r, i, c in con.execute(
                'SELECT ranura, item_id, cantidad FROM gremio_banco WHERE guild_id = ?',
                (int(guild_id),))}
        finally:
            con.close()


def db_banco_gremio_detallado(guild_id: int) -> dict:
    """Como db_banco_gremio, incluyendo los datos de cada objeto."""
    with _LOCK:
        con = _get_conn()
        try:
            return {int(r): (int(i), int(c), json.loads(d or '{}')) for r, i, c, d in con.execute(
                'SELECT ranura, item_id, cantidad, datos FROM gremio_banco WHERE guild_id = ?',
                (int(guild_id),))}
        finally:
            con.close()


def db_mover_banco_gremio(usuario, char_id, guild_id, ranura, depositar,
                           registro, bolsa, cantidades, mejoras, mascotas, mascota):
    """Mueve el objeto y guarda la mochila en una sola transaccion SQLite."""
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT ranura, datos FROM personajes WHERE usuario=? AND char_id=?',
                              (usuario, char_id)).fetchone()
            miembro = con.execute('SELECT 1 FROM gremio_miembros WHERE guild_id=? AND char_id=?',
                                  (guild_id, char_id)).fetchone()
            actual = con.execute('SELECT item_id, cantidad, datos FROM gremio_banco '
                                 'WHERE guild_id=? AND ranura=?', (guild_id, ranura)).fetchone()
            if not row or not miembro or (depositar and actual) or (not depositar and not actual):
                raise ValueError('movimiento de banco invalido')
            if not depositar and (int(actual[0]), int(actual[1]), json.loads(actual[2] or '{}')) != registro:
                raise ValueError('el objeto del banco cambio')
            pj = json.loads(row[1])
            pj['inventario'] = {str(k): int(v) for k, v in bolsa.items() if v and int(v) > 0}
            pj['cantidades'] = {str(k): int(v) for k, v in cantidades.items()
                                if (int(v) > 1 or 497 <= int(k) <= 556)
                                and (int(k) in bolsa or str(k) in bolsa)}
            pj['mejoras'] = {str(k): v for k, v in mejoras.items() if v}
            pj['mascotas'] = {str(k): {ck: cv for ck, cv in v.items() if ck != 'entidad'}
                              for k, v in mascotas.items() if isinstance(v, dict)}
            if mascota:
                pj['mascota'] = {k: v for k, v in mascota.items() if k != 'entidad'}
            else:
                pj.pop('mascota', None)
            con.execute('UPDATE personajes SET datos=?, actualizado_en=CURRENT_TIMESTAMP '
                        'WHERE usuario=? AND ranura=?',
                        (json.dumps(pj, ensure_ascii=False), usuario, row[0]))
            if depositar:
                item, cantidad, datos = registro
                con.execute('INSERT INTO gremio_banco (guild_id, ranura, item_id, cantidad, datos) '
                            'VALUES (?, ?, ?, ?, ?)',
                            (guild_id, ranura, item, cantidad, json.dumps(datos, ensure_ascii=False)))
            else:
                con.execute('DELETE FROM gremio_banco WHERE guild_id=? AND ranura=?', (guild_id, ranura))
            con.commit()
            _notificar_cambio()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_mover_oro_banco_gremio(usuario, char_id, guild_id, cambio_banco, oro):
    """Actualiza oro del personaje y de la liga sin dejar una mitad guardada."""
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT ranura, datos FROM personajes WHERE usuario=? AND char_id=?',
                              (usuario, char_id)).fetchone()
            miembro = con.execute('SELECT 1 FROM gremio_miembros WHERE guild_id=? AND char_id=?',
                                  (guild_id, char_id)).fetchone()
            fondos = con.execute('SELECT fondos FROM gremios WHERE guild_id=?', (guild_id,)).fetchone()
            if not row or not miembro or not fondos or not 0 <= int(fondos[0]) + cambio_banco <= 0xffffffff:
                raise ValueError('movimiento de oro invalido')
            pj = json.loads(row[1])
            pj['oro'] = int(oro)
            con.execute('UPDATE personajes SET datos=?, actualizado_en=CURRENT_TIMESTAMP '
                        'WHERE usuario=? AND ranura=?',
                        (json.dumps(pj, ensure_ascii=False), usuario, row[0]))
            con.execute('UPDATE gremios SET fondos=fondos+? WHERE guild_id=?', (cambio_banco, guild_id))
            con.commit()
            _notificar_cambio()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_intercambiar_banco_gremio(guild_id: int, origen: int, destino: int) -> bool:
    """Mueve (o intercambia, si el destino esta ocupado) dos casillas del banco
    de la liga en una transaccion. False si en el origen no hay nada."""
    guild_id, origen, destino = int(guild_id), int(origen), int(destino)
    if origen == destino:
        return False
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            if not con.execute('SELECT 1 FROM gremio_banco WHERE guild_id=? AND ranura=?',
                               (guild_id, origen)).fetchone():
                con.rollback()
                return False
            # -1 de casilla puente para no chocar con la clave (guild_id, ranura)
            con.execute('UPDATE gremio_banco SET ranura=-1 WHERE guild_id=? AND ranura=?', (guild_id, origen))
            con.execute('UPDATE gremio_banco SET ranura=? WHERE guild_id=? AND ranura=?', (origen, guild_id, destino))
            con.execute('UPDATE gremio_banco SET ranura=? WHERE guild_id=? AND ranura=-1', (destino, guild_id))
            con.commit()
            _notificar_cambio()
            return True
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()


def db_poner_banco_gremio(guild_id: int, ranura: int, item_id: int, cantidad: int):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('INSERT OR REPLACE INTO gremio_banco (guild_id, ranura, item_id, cantidad) '
                        'VALUES (?, ?, ?, ?)', (int(guild_id), int(ranura), int(item_id), int(cantidad)))
            con.commit()
        finally:
            con.close()


def db_quitar_banco_gremio(guild_id: int, ranura: int):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('DELETE FROM gremio_banco WHERE guild_id = ? AND ranura = ?',
                        (int(guild_id), int(ranura)))
            con.commit()
        finally:
            con.close()


def db_poner_fondos_gremio(guild_id: int, fondos: int):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('UPDATE gremios SET fondos = ? WHERE guild_id = ?',
                        (max(0, int(fondos)), int(guild_id)))
            con.commit()
        finally:
            con.close()


# OPERACIONES DE TERRITORIO Y TOTEM WAR
def db_asignar_territorio_gremio(tw_stage: int, guild_id: int):
    """Asigna la propiedad de un campo de batalla (tw_stage 200..207) a una liga."""
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            if int(tw_stage) not in range(200, 208):
                raise ValueError('Invalid Totem War territory.')
            if not con.execute('SELECT 1 FROM gremios WHERE guild_id=?', (int(guild_id),)).fetchone():
                raise ValueError('The league does not exist.')
            otro = con.execute('SELECT tw_stage FROM gremio_territorios WHERE guild_id=? AND tw_stage<>?',
                               (int(guild_id), int(tw_stage))).fetchone()
            if otro:
                raise ValueError('Your league already owns another territory.')
            con.execute('INSERT OR REPLACE INTO gremio_territorios (tw_stage, guild_id, capturado_en) '
                        'VALUES (?, ?, CURRENT_TIMESTAMP)', (int(tw_stage), int(guild_id)))
            con.commit()
            _notificar_cambio()
        finally:
            con.close()


def db_obtener_dueno_de_territorio(tw_stage: int):
    """Devuelve el guild_id que posee el territorio tw_stage, o None."""
    with _LOCK:
        con = _get_conn()
        try:
            row = con.execute('SELECT guild_id FROM gremio_territorios WHERE tw_stage = ?',
                              (int(tw_stage),)).fetchone()
            return int(row[0]) if row else None
        finally:
            con.close()


def db_gremio_tiene_territorio(guild_id: int) -> bool:
    """Si la liga posee algun territorio (condicion 28: HAVE_GUILD_REGION)."""
    if not guild_id:
        return False
    with _LOCK:
        con = _get_conn()
        try:
            row = con.execute('SELECT 1 FROM gremio_territorios WHERE guild_id = ? LIMIT 1',
                              (int(guild_id),)).fetchone()
            return bool(row)
        finally:
            con.close()


def db_obtener_territorios_de_gremio(guild_id: int) -> list:
    """Lista de tw_stage que posee una liga."""
    if not guild_id:
        return []
    with _LOCK:
        con = _get_conn()
        try:
            rows = con.execute('SELECT tw_stage FROM gremio_territorios WHERE guild_id = ?',
                               (int(guild_id),)).fetchall()
            return [int(r[0]) for r in rows]
        finally:
            con.close()


def db_antiguedad_miembro_gremio(char_id: int) -> int:
    """Segundos transcurridos desde que el personaje ingreso a su gremio (condicion 82)."""
    if not char_id:
        return 0
    with _LOCK:
        con = _get_conn()
        try:
            row = con.execute("SELECT strftime('%s', 'now') - strftime('%s', ingreso_en) "
                              "FROM gremio_miembros WHERE char_id = ?", (int(char_id),)).fetchone()
            if row and row[0] is not None:
                return max(0, int(row[0]))
        finally:
            con.close()
    return 0


# OPERACIONES DE CULTIVOS DE GRANJA DE LIGA
def db_guardar_cultivo(guild_id: int, plot_id: int, char_id: int, char_name: str,
                       crop_id: int, sembrado_en: int, madura_en: int, marchita_en: int):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('''
            INSERT OR REPLACE INTO liga_granja_cultivos
            (guild_id, plot_id, char_id, char_name, crop_id, sembrado_en, madura_en, marchita_en, riego_count, abono_count, cosechado_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
            ''', (int(guild_id), int(plot_id), int(char_id), str(char_name), int(crop_id),
                  int(sembrado_en), int(madura_en), int(marchita_en)))
            con.commit()
        finally:
            con.close()


def db_obtener_cultivos_gremio(guild_id: int) -> list:
    with _LOCK:
        con = _get_conn()
        try:
            rows = con.execute('''
            SELECT plot_id, char_id, char_name, crop_id, sembrado_en, madura_en, marchita_en, riego_count, abono_count, cosechado_count
            FROM liga_granja_cultivos WHERE guild_id = ?
            ''', (int(guild_id),)).fetchall()
            res = []
            for r in rows:
                res.append({
                    'plot_id': int(r[0]), 'char_id': int(r[1]), 'char_name': r[2],
                    'crop_id': int(r[3]), 'sembrado_en': int(r[4]), 'madura_en': int(r[5]),
                    'marchita_en': int(r[6]), 'riego_count': int(r[7]), 'abono_count': int(r[8]),
                    'cosechado_count': int(r[9])
                })
            return res
        finally:
            con.close()


def db_obtener_cultivo(guild_id: int, plot_id: int):
    with _LOCK:
        con = _get_conn()
        try:
            r = con.execute('''
            SELECT plot_id, char_id, char_name, crop_id, sembrado_en, madura_en, marchita_en, riego_count, abono_count, cosechado_count
            FROM liga_granja_cultivos WHERE guild_id = ? AND plot_id = ?
            ''', (int(guild_id), int(plot_id))).fetchone()
            if not r:
                return None
            return {
                'plot_id': int(r[0]), 'char_id': int(r[1]), 'char_name': r[2],
                'crop_id': int(r[3]), 'sembrado_en': int(r[4]), 'madura_en': int(r[5]),
                'marchita_en': int(r[6]), 'riego_count': int(r[7]), 'abono_count': int(r[8]),
                'cosechado_count': int(r[9])
            }
        finally:
            con.close()


def db_actualizar_riego_cultivo(guild_id: int, plot_id: int):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('UPDATE liga_granja_cultivos SET riego_count = riego_count + 1 WHERE guild_id = ? AND plot_id = ?',
                        (int(guild_id), int(plot_id)))
            con.commit()
        finally:
            con.close()


def db_actualizar_abono_cultivo(guild_id: int, plot_id: int):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('UPDATE liga_granja_cultivos SET abono_count = abono_count + 1 WHERE guild_id = ? AND plot_id = ?',
                        (int(guild_id), int(plot_id)))
            con.commit()
        finally:
            con.close()


def db_eliminar_cultivo(guild_id: int, plot_id: int):
    with _LOCK:
        con = _get_conn()
        try:
            con.execute('DELETE FROM liga_granja_cultivos WHERE guild_id = ? AND plot_id = ?',
                        (int(guild_id), int(plot_id)))
            con.commit()
        finally:
            con.close()

