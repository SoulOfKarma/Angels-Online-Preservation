"""
Cuentas y personajes.

LIMITACION HONESTA: el bloque de 16 bytes que el cliente manda en 0x0002 AUTH
no esta descifrado -- no sabemos como codifica usuario y contrasena. Por lo
tanto el servidor **no valida credenciales**: acepta cualquier autenticacion y
la asocia a la cuenta configurada.

Para un servidor local propio eso no cambia nada. Cuando se entienda el formato
del bloque, la validacion entra en `validar()` sin tocar el resto.

Cada AUTH recibido se guarda en logs/auth_muestras/ -- justamente para poder
descifrar el formato comparando varios intentos con credenciales conocidas.
"""
import json
import pathlib
import datetime
import hashlib
import os
import tempfile
import threading

BASE = pathlib.Path(__file__).parent.parent / 'data'
ARCHIVO = BASE / 'cuentas.json'
MUESTRAS = pathlib.Path(__file__).parent.parent / 'logs' / 'auth_muestras'
_LOCK = threading.RLock()
GUARDAR_AUTH_CRUDO = os.environ.get('AO_GUARDAR_AUTH_CRUDO', '0') == '1'
REGISTRAR_HASH_PRIMER_LOGIN = os.environ.get('AO_REGISTRAR_PRIMER_HASH', '0') == '1'

POR_DEFECTO = {
    "cuentas": {
        "karma": {
            "password": "123456",
            # Sin personajes: las 3 ranuras arrancan vacias y se crean desde
            # el cliente. No se inventan valores de nivel, mapa ni stats.
            "personajes": []
        }
    }
}


def cargar():
    """Carga las cuentas y recupera automáticamente un backup válido."""
    with _LOCK:
        BASE.mkdir(parents=True, exist_ok=True)
        if not ARCHIVO.exists():
            guardar_documento(POR_DEFECTO)
        try:
            return json.loads(ARCHIVO.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            backup = ARCHIVO.with_suffix('.json.bak')
            if backup.exists():
                datos = json.loads(backup.read_text(encoding='utf-8'))
                guardar_documento(datos)
                return datos
            raise


def guardar_documento(datos: dict):
    """Escribe cuentas.json sin dejarlo truncado si el proceso falla.

    Todas las escrituras del módulo deben pasar por aquí. Primero se genera
    un archivo temporal, se fuerza a disco y finalmente se reemplaza el
    archivo original de forma atómica.
    """
    BASE.mkdir(parents=True, exist_ok=True)
    temporal = None
    try:
        fd, temporal = tempfile.mkstemp(
            prefix='cuentas_', suffix='.tmp', dir=str(BASE)
        )
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as archivo:
            json.dump(datos, archivo, indent=2, ensure_ascii=False)
            archivo.flush()
            os.fsync(archivo.fileno())

        if ARCHIVO.exists():
            backup = ARCHIVO.with_suffix('.json.bak')
            try:
                os.replace(str(ARCHIVO), str(backup))
            except OSError:
                pass
        os.replace(str(temporal), str(ARCHIVO))
        temporal = None
    finally:
        if temporal:
            try:
                os.remove(temporal)
            except OSError:
                pass


def _guardar(datos: dict):
    with _LOCK:
        guardar_documento(datos)


# VALIDACION DE CONTRASENA: DESACTIVADA, y la razon importa.
#
# Primero probe OFF_HASH=21 (copiando el criterio del proyecto anterior:
# usuario 8 B + 13 B de sesion). Rechazaba ingresos validos.
# Despues medi 20 muestras y elegi OFF_HASH=54, porque +54..+69 salia
# IDENTICO en las 13 con contrasena. Pero eso era justamente la trampa:
# sale identico **porque es una constante del cliente**, no porque sea el
# hash. Por eso acepta cualquier clave.
#
# La region +21..+29 si toma dos valores distintos, pero varia entre intentos
# de la MISMA sesion, asi que tampoco es concluyente.
#
# Para resolverlo hace falta un experimento controlado: varios ingresos con
# una clave A y varios con una clave B, y comparar. Ver tools/analizar_auth.py.
# Hasta entonces NO se valida: es preferible aceptar todo a rechazar ingresos
# legitimos con una regla inventada.
VALIDAR_PASSWORD = os.environ.get('AO_VALIDAR_PASSWORD', '0') == '1'
# El experimento controlado confirmó que este bloque de 32 bytes es estable
# para la misma cuenta/clave y cambia al cambiar la clave.
OFF_HASH = 21
LARGO_HASH = 32


def hash_de_auth(cuerpo: bytes) -> str:
    """Extrae el hash de contrasena del AUTH de 73 B.

    El bloque NO se descifra: se compara tal cual. No hace falta conocer el
    algoritmo, solo que sea determinista -- y lo es: +54..+69 salio identico
    en las 13 muestras reales con contrasena.
    """
    return (cuerpo[OFF_HASH:OFF_HASH + LARGO_HASH].hex()
            if len(cuerpo) >= OFF_HASH + LARGO_HASH else '')


def validar(usuario: str, cuerpo_auth: bytes = b'') -> tuple:
    """Devuelve (cuenta, motivo). cuenta=None si el ingreso se rechaza.

    La contrasena se REGISTRA en el primer ingreso de cada cuenta y se compara
    en los siguientes. No se puede validar contra el texto que escribiste
    porque el algoritmo del bloque no esta descifrado -- lo que se compara es
    el hash que manda el cliente.
    """
    d = cargar()
    cta = d['cuentas'].get(usuario)
    if cta is None:
        # Servidor local: la cuenta se crea sola en el primer ingreso.
        # Rechazar por inexistente solo estorba cuando se prueba con
        # clientes distintos, cada uno con su propio usuario guardado.
        cta = {'password': '', 'personajes': []}
        d['cuentas'][usuario] = cta
        _guardar(d)
        if VALIDAR_PASSWORD and not REGISTRAR_HASH_PRIMER_LOGIN:
            return None, "cuenta nueva: requiere registro inicial controlado"
        return cta, f"cuenta '{usuario}' creada en el primer ingreso"

    h = hash_de_auth(cuerpo_auth)
    if VALIDAR_PASSWORD and (not h or set(h) == {'0'}):
        return None, "contrasena vacia"

    if not VALIDAR_PASSWORD:
        return cta, "sin validar (ver cuentas.py: el campo del hash no esta identificado)"

    guardado = cta.get('hash')
    if not guardado:
        if not REGISTRAR_HASH_PRIMER_LOGIN:
            return None, "cuenta sin credencial registrada"
        cta['hash'] = h
        _guardar(d)
        return cta, "contrasena registrada en el primer ingreso"
    if guardado != h:
        return None, "contrasena incorrecta"
    return cta, "ok"


def guardar_muestra_auth(bloque: bytes, nota: str = ""):
    """Guarda un AUTH crudo para poder descifrar el formato mas adelante.

    Comparando varios intentos con credenciales CONOCIDAS (usuario y clave
    distintos) se puede deducir como se codifican. Por eso se guardan.
    """
    MUESTRAS.mkdir(parents=True, exist_ok=True)
    marca = datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    digest = hashlib.sha256(bloque).hexdigest()
    (MUESTRAS / f"auth_{marca}.sha256").write_text(digest, encoding='ascii')
    # Solo se habilita durante el experimento controlado de analizar_auth.py.
    # Después debe volver a quedar desactivado porque el paquete puede
    # contener datos de sesión.
    if GUARDAR_AUTH_CRUDO:
        (MUESTRAS / f"auth_{marca}.bin").write_bytes(bloque)
    if nota:
        (MUESTRAS / f"auth_{marca}.txt").write_text(nota, encoding='utf-8')


def _ahora():
    import time
    return time.time()


def personaje_de(cuenta, indice=0):
    from login import Personaje
    if indice >= len(cuenta.get('personajes', [])):
        return None            # ranura vacia
    p = cuenta['personajes'][indice]
    return Personaje(
        entity_id=1000 + p['char_id'] % 1000,
        char_id=p['char_id'],
        nombre=p['nombre'],
        tile_x=p['tile_x'], tile_y=p['tile_y'],
        habilidades=[tuple(x) for x in p['habilidades']],
        barra=list(p['barra']),
        quests=[tuple(x) for x in p['quests']],
        hp=p.get('hp', 205), hp_max=p.get('hp_max', 205),
        mp=p.get('mp', 154), mp_max=p.get('mp_max', 154),
        # Las claves de JSON siempre son texto; las ranuras son numeros.
        inventario={int(k): v for k, v in p.get('inventario', {}).items()},
        # Recortado a diez lamparas: hubo un fallo que llenaba la barra
        # sola y dejo guardados valores imposibles como 14000.
        sp=max(0, min(int(p.get('sp') or 0), 10 * 1000)),
        # Las mejoras van por CASILLA: el +N, las gemas y los stats verdes
        # de la pieza que hay en esa ranura. Se guardaban solo en memoria,
        # asi que al reconectar se perdia todo lo mejorado.
        mejoras={int(k): v for k, v in (p.get('mejoras') or {}).items()},
        checkpoint_stage=int((p.get('checkpoint') or {}).get('stage', 0)),
        checkpoint_x=int(((p.get('checkpoint') or {}).get('tile') or [0, 0])[0]),
        checkpoint_y=int(((p.get('checkpoint') or {}).get('tile') or [0, 0])[1]),
        cantidades={int(k): int(v) for k, v in p.get('cantidades', {}).items()},
        tutorial=p.get('tutorial', 0),
        oro=p.get('oro', 0),
        stage=p.get('stage_id', 51),
        faction=p.get('faction', 'Heaven'),
        nivel=p.get('nivel', 1),
        exp=p.get('exp', 0),
        banco={int(k): v for k, v in p.get('banco', {}).items()},
        # Los seis sistemas del README de RE:Angels Online.
        album={str(k): int(v) for k, v in (p.get('album') or {}).items()},
        logros=[int(x) for x in (p.get('logros') or [])],
        cartas=[int(x) for x in (p.get('cartas') or [])],
        estrellas=[tuple(x) for x in (p.get('estrellas') or [])
                   if isinstance(x, (list, tuple)) and len(x) >= 2],
        casa={'muebles': [int(x) for x in
                          ((p.get('casa') or {}).get('muebles') or [])]},
        # Con su hora de caducidad. Los ya vencidos se tiran al cargar: no
        # tiene sentido devolver un buff de hace tres dias, y las claves
        # vuelven como numeros porque en JSON son texto.
        buffs={int(k): v for k, v in (p.get('buffs') or {}).items()
               if isinstance(v, dict) and v.get('fin', 0) > _ahora()},
        class_id=p.get('class_id', 0),
        creditos=int(p.get('creditos', 0) or 0),
        rango=max(1, min(20, int(p.get('rango', 1) or 1))),
        banco_habilidades={int(k): list(v) for k, v in p.get('banco_habilidades', {}).items()},
        hechizos_aprendidos=set(p.get('hechizos_aprendidos', [])),
        mascota=_cargar_mascota(p.get('mascota')),
        mascotas=_cargar_mascotas(p),
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
    for k, v in st.items():
        if k in ('hp', 'mp') and f.get(k, 0) > 0:
            continue
        f[k] = v
    f.setdefault('saciedad', 100)
    f.setdefault('intimidad', 60)
    f.setdefault('estrellas', 1)
    return f


def borrar_personaje(usuario: str, ranura: int):
    """Borra el personaje de esa ranura. Devuelve su char_id, o None.

    En el juego real el borrado tiene un contador de ocho horas (en la
    captura llega como 28799 segundos en la lista de personajes). Aqui se
    borra en el acto, que es lo util para probar.
    """
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return None
    for i, p in enumerate(c.get('personajes', [])):
        if p.get('ranura') == ranura:
            char_id = p.get('char_id')
            del c['personajes'][i]
            _guardar(d)
            return char_id
    return None


def guardar_inventario(usuario: str, char_id: int, bolsa: dict,
                       cantidades=None, mejoras=None):
    """Deja el inventario en disco tras mover un item.

    Las cantidades van aparte para no cambiar el formato de 'inventario',
    que es {ranura: item_id}. Una casilla que no aparece lleva una unidad.
    """
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['inventario'] = {str(k): v for k, v in sorted(bolsa.items())}
            if mejoras is not None:
                p['mejoras'] = {str(k): v
                                for k, v in sorted(mejoras.items())
                                if v and (v.get('veces') or v.get('gemas')
                                          or v.get('extra') or v.get('vinculacion'))}
            if cantidades is not None:
                p['cantidades'] = {str(k): int(v)
                                   for k, v in sorted(cantidades.items())
                                   if int(v) > 1 and int(k) in bolsa}
            _guardar(d)
            return


def guardar_mejoras(usuario: str, char_id: int, mejoras: dict):
    """Deja en disco el +N, las gemas y los stats verdes de cada casilla.

    Iban solo en memoria, asi que al reconectar se perdia todo lo mejorado.
    Se guarda aparte del inventario porque hay veinte sitios que guardan la
    bolsa y solo uno que toca las mejoras.
    """
    if not usuario:
        return
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['mejoras'] = {str(k): v for k, v in sorted((mejoras or {}).items())
                            if v and (v.get('veces') or v.get('gemas')
                                      or v.get('extra') or v.get('vinculacion'))}
            _guardar(d)
            return


def guardar_checkpoint(usuario: str, char_id: int, stage: int, tx: int, ty: int):
    """Donde revive el personaje, fijado hablando con Cupid."""
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['checkpoint'] = {'stage': int(stage), 'tile': [int(tx), int(ty)]}
            _guardar(d)
            return


def guardar_habilidades(usuario: str, char_id: int, habilidades):
    """Deja en disco las habilidades que dio la eleccion de clase."""
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['habilidades'] = [list(h) for h in habilidades]
            # Sincronizar tambien con el banco de habilidades para no perder los niveles entrenados
            banco = p.setdefault('banco_habilidades', {})
            for h in habilidades:
                if isinstance(h, (list, tuple)) and len(h) >= 2:
                    banco[str(h[0])] = [int(h[1]), int(h[2]) if len(h) > 2 else 0]
            _guardar(d)
            return


def guardar_hechizos(usuario: str, char_id: int, hechizos):
    """Guarda la lista de hechizos aprendidos por el personaje."""
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['hechizos_aprendidos'] = list(hechizos)
            _guardar(d)
            return


def guardar_banco_habilidades(usuario: str, char_id: int, banco: dict):
    """Guarda el banco de habilidades completo (niveles y exp de todas las ramas)."""
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['banco_habilidades'] = {str(k): list(v) for k, v in banco.items()}
            _guardar(d)
            return


def guardar_clase(usuario: str, char_id: int, class_id: int):
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['class_id'] = class_id
            _guardar(d)
            return


def guardar_posicion(usuario: str, char_id: int, tile_x: int, tile_y: int):
    """Deja en disco donde quedo el personaje al desconectar."""
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['tile_x'], p['tile_y'] = int(tile_x), int(tile_y)
            _guardar(d)
            return


def guardar_tutorial(usuario: str, char_id: int, etapa: int):
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['tutorial'] = int(etapa)
            _guardar(d)
            return


def guardar_oro(usuario: str, char_id: int, oro: int):
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['oro'] = int(oro)
            _guardar(d)
            return


def guardar_barra(usuario: str, char_id: int, barra: list):
    """Deja en disco los accesos rapidos de la barra (F1..F8, 1..8, etc.)."""
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['barra'] = list(barra)
            _guardar(d)
            return


def guardar_mapa(usuario: str, char_id: int, stage: int, tile_x: int, tile_y: int):
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['stage_id'] = int(stage)
            p['tile_x'], p['tile_y'] = int(tile_x), int(tile_y)
            _guardar(d)
            return


def guardar_faccion(usuario: str, char_id: int, faccion: str):
    """Guarda la faccion elegida (Aurora, Dark City, Iron Castle, Breeze Woods)."""
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['faction'] = faccion
            _guardar(d)
            return


def guardar_progreso(usuario: str, char_id: int, nivel: int, exp: int,
                     hp: int = None, mp: int = None, habilidades: list = None,
                     hp_max: int = None, mp_max: int = None, sp: int = None,
                     buffs: dict = None):
    """Guarda nivel, exp, hp, mp, hp_max, mp_max, habilidades y SP.

    El SP no se guardaba: al salir y entrar se perdian las lamparas que
    costaba un rato llenar. Se conserva, igual que la experiencia.
    """
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['nivel'] = int(nivel)
            p['exp'] = int(exp)
            if sp is not None:
                p['sp'] = max(0, int(sp))
            if buffs is not None:
                # Se guarda la hora ABSOLUTA de caducidad, asi un buff de 30
                # minutos sigue corriendo aunque salgas: la carta de doble
                # experiencia dura lo que dura, no lo que estes conectado.
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
            _guardar(d)
            return


def guardar_sistemas(usuario: str, char_id: int, p):
    """Guarda el estado de los seis sistemas: album, logros, cartas,
    estrellas y casa. Van juntos porque se tocan en los mismos momentos y
    asi es una sola escritura del archivo."""
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for fila in c.get('personajes', []):
        if fila.get('char_id') != char_id:
            continue
        fila['album'] = {str(k): int(v)
                         for k, v in (getattr(p, 'album', None) or {}).items()}
        fila['logros'] = sorted({int(x) for x in (getattr(p, 'logros', None) or [])})
        fila['cartas'] = sorted({int(x) for x in (getattr(p, 'cartas', None) or [])})
        fila['estrellas'] = [list(x) for x in (getattr(p, 'estrellas', None) or [])]
        fila['casa'] = {'muebles': [int(x) for x in
                                    ((getattr(p, 'casa', None) or {}).get('muebles') or [])]}
        _guardar(d)
        return


def guardar_banco(usuario: str, char_id: int, banco: dict):
    """Guarda los items del almacen/banco del personaje."""
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['banco'] = {str(k): v for k, v in sorted(banco.items())}
            _guardar(d)
            return


def guardar_buffs(usuario: str, char_id: int, buffs: dict):
    """Guarda los buffs activos del personaje."""
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['buffs'] = buffs
            _guardar(d)
            return


def guardar_mascota(usuario: str, char_id: int, mascota: dict, mascotas: dict = None):
    """Guarda la ficha de la mascota del personaje y el catalogo de mascotas."""
    if not usuario:
        return
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            m_dict = p.setdefault('mascotas', {})
            if mascotas and isinstance(mascotas, dict):
                for k, v in mascotas.items():
                    if isinstance(v, dict) and v.get('sprite'):
                        clean_v = {ck: cv for ck, cv in v.items() if ck not in ('entidad',)}
                        clean_v['fuera'] = False
                        m_dict[str(k)] = clean_v
            if mascota and isinstance(mascota, dict) and mascota.get('sprite'):
                limpia = {k: v for k, v in mascota.items()
                          if k not in ('entidad',)}
                limpia['fuera'] = False
                p['mascota'] = limpia
                r_key = str(limpia.get('ranura') if limpia.get('ranura') is not None else limpia.get('item', '0'))
                m_dict[r_key] = limpia
            else:
                p.pop('mascota', None)
            _guardar(d)
            return


def guardar_rango(usuario: str, char_id: int, rango: int, creditos: int = None):
    """Guarda el rango (1..20) y opcionalmente los creditos de rango del personaje."""
    if not usuario:
        return
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['rango'] = max(1, min(20, int(rango or 1)))
            if creditos is not None:
                p['creditos'] = int(creditos or 0)
            _guardar(d)
            return
