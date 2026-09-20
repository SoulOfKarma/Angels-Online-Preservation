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

BASE = pathlib.Path(__file__).parent.parent / 'data'
ARCHIVO = BASE / 'cuentas.json'
MUESTRAS = pathlib.Path(__file__).parent.parent / 'logs' / 'auth_muestras'

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
    BASE.mkdir(parents=True, exist_ok=True)
    if not ARCHIVO.exists():
        ARCHIVO.write_text(json.dumps(POR_DEFECTO, indent=2, ensure_ascii=False),
                           encoding='utf-8')
    return json.loads(ARCHIVO.read_text(encoding='utf-8'))


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
VALIDAR_PASSWORD = False
OFF_HASH = 54
LARGO_HASH = 16


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
        ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                           encoding='utf-8')
        return cta, f"cuenta '{usuario}' creada en el primer ingreso"

    h = hash_de_auth(cuerpo_auth)
    if VALIDAR_PASSWORD and (not h or set(h) == {'0'}):
        return None, "contrasena vacia"

    if not VALIDAR_PASSWORD:
        return cta, "sin validar (ver cuentas.py: el campo del hash no esta identificado)"

    guardado = cta.get('hash')
    if not guardado:
        cta['hash'] = h
        ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding='utf-8')
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
    (MUESTRAS / f"auth_{marca}.bin").write_bytes(bloque)
    if nota:
        (MUESTRAS / f"auth_{marca}.txt").write_text(nota, encoding='utf-8')


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
        tutorial=p.get('tutorial', 0),
        oro=p.get('oro', 0),
        stage=p.get('stage_id', 51),
        faction=p.get('faction', 'Heaven'),
        nivel=p.get('nivel', 1),
        exp=p.get('exp', 0),
        banco={int(k): v for k, v in p.get('banco', {}).items()},
        buffs=p.get('buffs', {}),
    )


def guardar_inventario(usuario: str, char_id: int, bolsa: dict):
    """Deja el inventario en disco tras mover un item."""
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['inventario'] = {str(k): v for k, v in sorted(bolsa.items())}
            ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                               encoding='utf-8')
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
            ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                               encoding='utf-8')
            return


def guardar_clase(usuario: str, char_id: int, class_id: int):
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['class_id'] = class_id
            ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                               encoding='utf-8')
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
            ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                               encoding='utf-8')
            return


def guardar_tutorial(usuario: str, char_id: int, etapa: int):
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['tutorial'] = int(etapa)
            ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                               encoding='utf-8')
            return


def guardar_oro(usuario: str, char_id: int, oro: int):
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['oro'] = int(oro)
            ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                               encoding='utf-8')
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
            ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                               encoding='utf-8')
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
            ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                               encoding='utf-8')
            return


def guardar_progreso(usuario: str, char_id: int, nivel: int, exp: int,
                     hp: int = None, mp: int = None, habilidades: list = None):
    """Guarda nivel, exp, hp, mp y habilidades del personaje."""
    d = json.loads(ARCHIVO.read_text(encoding='utf-8'))
    c = d['cuentas'].get(usuario)
    if not c:
        return
    for p in c.get('personajes', []):
        if p.get('char_id') == char_id:
            p['nivel'] = int(nivel)
            p['exp'] = int(exp)
            if hp is not None:
                p['hp'] = int(hp)
            if mp is not None:
                p['mp'] = int(mp)
            if habilidades is not None:
                p['habilidades'] = [list(h) for h in habilidades]
            ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                               encoding='utf-8')
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
            ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                               encoding='utf-8')
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
            ARCHIVO.write_text(json.dumps(d, indent=2, ensure_ascii=False),
                               encoding='utf-8')
            return

