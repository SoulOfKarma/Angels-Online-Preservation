"""Sistema de fusion (Fusion, WND_FUSE).

Sacado con REA del cliente (play_angel_unpacked.exe) el 20/10/2026 y de la
captura de Celestia mundo_202739_136382 (alli la ventana existe pero el
servidor no contesta):

- La ventana la abre el propio cliente desde su menu. Las casillas son
  controles de wnd05.xml: 15004 Principal (centro), 15007 Asistente (arriba),
  15005 Pocion de fusion (izquierda), 15006 Aleatorio (derecha) y 15008
  Producto.
- Al pulsar el boton OK, fuse.l llama a game.fuseok(0) (FUN_0061dec0). La
  vista previa de mascota llama a fuseok(1), despues de fuseconfirm. Las dos
  mandan el c2s 0x0147
      [u8 modo][u16 principal][u16 asistente][u16 pocion][u16 aleatorio]
  con las casillas de la mochila (0 si esa casilla esta vacia). En Celestia
  se vio: 00 1800 3700 3400 0000.
- El producto sale en la ventana con el s2c 0x001D codigo 50 (FUN_005ff390,
  hueco 0x4728 de la tabla de 005fbdd0): con (casilla, 0) muestra el objeto
  de esa casilla de la mochila, con (x, -1) la mascota principal, y con
  (objeto, cantidad) un objeto suelto. El codigo 51 abre la vista previa de
  la mascota (CreatePetPreRes).

Las reglas son las de la ayuda del juego (string.xml 2783-2785). Para los
CONSUMIBLES: 10 del principal + 10 del asistente + una pocion dan un objeto
nuevo, con un 100% de exito, y "the result depends on the Main and Assistant
items". serv_fuse.xml da a cada consumible un 權值 que es su NIVEL de valor
(1 las pociones basicas ... 111 las insignias). Nadie ha medido como lo
elegia el oficial, asi que el resultado sale de un consumible del nivel del
mayor de los dos (60%), del siguiente (30%, mas el bono de la pocion) o del
anterior (10%).

EQUIPO y MASCOTAS: las comprobaciones y la probabilidad de exito son las del
cliente (FUN_005d25b0, FUN_005d3020, FUN_005d3b40 y la vista previa
FUN_005d3d30). Cuanto atributo pasa lo decide el servidor y no se sabe:
ver PORCENTAJE_BASE. La de transformacion (Shape Fusion Potion), abajo.
"""
import functools
import logging
import pathlib
import random
import re
import sqlite3
import struct

log = logging.getLogger('fusion')

C2S_FUSION = 0x0147
CODIGO_PRODUCTO = 50
CANTIDAD_CONSUMIBLE = 10
CAT_POCION = '融合劑'
CAT_CONSUMIBLE, CAT_MASCOTA = '消耗品', '寵物'
PROB_MISMO, PROB_SUBE = 0.60, 0.30          # el resto, baja un nivel

_RAIZ = pathlib.Path(__file__).resolve().parent.parent


def _ultimo(nombre):
    """El archivo de setting/ del update mas reciente que lo trae."""
    mejor = None
    for carpeta in (_RAIZ / 'extracted_paks').iterdir():
        m = re.fullmatch(r'update(\d*)', carpeta.name.lower())
        if not m:
            continue
        p = carpeta / 'setting' / nombre
        if p.is_file():
            n = int(m.group(1) or 0)
            if mejor is None or n > mejor[0]:
                mejor = (n, p)
    return mejor[1] if mejor else None


@functools.lru_cache(maxsize=1)
def tabla():
    """{item_id: (categoria, nivel)} de los objetos que se pueden fusionar."""
    res = {}
    f = _ultimo('fuse.xml')
    if f:
        for item, cat in re.findall(r'道具編號="(\d+)" 融合編號="\d+" 融合類別="([^"]+)"',
                                    f.read_text(encoding='utf-8')):
            res[int(item)] = (cat, 0)
    s = _ultimo('serv_fuse.xml')
    if s:
        for item, peso, cat in re.findall(
                r'道具編號="(\d+)" 融合編號="\d+" 權值="(\d+)" 融合類別="([^"]+)"',
                s.read_text(encoding='utf-8')):
            res[int(item)] = (cat, int(peso))
    return res


@functools.lru_cache(maxsize=1)
def _niveles():
    """[(nivel, [items])] de los consumibles, de menor a mayor."""
    por_nivel = {}
    for item, (cat, nivel) in tabla().items():
        if cat == CAT_CONSUMIBLE and nivel > 0:
            por_nivel.setdefault(nivel, []).append(item)
    return sorted(por_nivel.items())


@functools.lru_cache(maxsize=4096)
def _fila(item_id):
    import inventario
    con = sqlite3.connect(_RAIZ / 'corpus' / 'content.db')
    try:
        return inventario.fila_item(con, '"基本名稱", "物品類別", "動態資料2", "動態資料1"', int(item_id))
    finally:
        con.close()


def nombre(item_id):
    f = _fila(item_id)
    return str(f[0]) if f and f[0] else str(item_id)


def es_pocion(item_id):
    f = _fila(item_id)
    return bool(f) and str(f[1] or '') == CAT_POCION


def bono_pocion(item_id):
    """El bono de exito de la pocion (動態資料2: Good 5, Lucky/Blessed 20)."""
    f = _fila(item_id)
    try:
        return max(0, int(f[2] or 0)) if f else 0
    except (TypeError, ValueError):
        return 0


def dato1_pocion(item_id):
    """動態資料1 de la pocion: Fusion 0, Good/Lucky 10, Blessed y Shape 10020."""
    f = _fila(item_id)
    try:
        return max(0, int(f[3] or 0)) if f else 0
    except (TypeError, ValueError):
        return 0


# ---- Formulas del cliente (REA, FUN_005d3b40 = la "Success Rate: %d%%") ----

def exito_equipo(pocion_d2):
    """FUN_00716c90: 80 + bono de la pocion."""
    return min(100, int(pocion_d2) % 10000 + 80)


def exito_mascota_cliente(estrellas, nivel, pocion_d2):
    """FUN_00716cb0 tal cual: 60 - estrellas*90/10 + nivel*100/40, entre 0
    y 80, mas el bono de la pocion, con tope 100. `estrellas` en decimas
    (1..80), el +0x130 de la mascota en el cliente. Es lo que ensena el
    cliente en "Success Rate", pero es durisima: 0% para una 4,5 estrellas
    de nivel 90. No se usa; queda de referencia."""
    r = 60 - (int(estrellas) * 90) // 10 + (int(nivel) * 100) // 40
    r = max(0, min(80, r))
    return min(100, r + int(pocion_d2) % 10000)


# La que usa el servidor, mas suave (lo pidio el usuario el 20/10/2026):
# 70% de base, -5% por cada estrella por encima de 3, +1% por cada 10
# niveles por encima de 80, entre 30% y 90%, mas el bono de la pocion.
EXITO_MASCOTA_BASE, EXITO_MASCOTA_MIN, EXITO_MASCOTA_MAX = 70, 30, 90


def exito_mascota(estrellas, nivel, pocion_d2):
    r = (EXITO_MASCOTA_BASE
         - (max(0, int(estrellas) - 30) * 5) // 10
         + max(0, int(nivel) - 80) // 10)
    r = max(EXITO_MASCOTA_MIN, min(EXITO_MASCOTA_MAX, r))
    return min(100, r + int(pocion_d2) % 10000)


# Lo que pasa del asistente al principal, en %. NO sale en el cliente (lo
# decide el servidor): 30% mas el 動態資料1 de la pocion (Good/Lucky +10,
# Blessed +20). Las pociones con 動態資料1 >= 10000 (Blessed) no destruyen
# el principal si falla. Las dos cosas son una interpretacion.
PORCENTAJE_BASE = 30
NIVEL_MIN_PRINCIPAL, NIVEL_MIN_ASISTENTE = 80, 60      # string.xml 2708/2709
RANGO_MIN_PRINCIPAL = 3                                # 2710 "high level pet"
DIFERENCIA_NIVEL_EQUIPO = 10                           # 2712
ID_POCION_FORMA = (16074, 74158)                       # 0x3eca, Shape Fusion Potion


def porcentaje_traspaso(pocion_d1):
    return PORCENTAJE_BASE + int(pocion_d1) % 10000


def protege(pocion_d1):
    return int(pocion_d1) >= 10000


def resultado_consumible(principal, asistente, bono=0, azar=random.random):
    """El consumible que sale de fusionar principal y asistente."""
    niveles = _niveles()
    if not niveles:
        return None
    base = max(tabla()[principal][1], tabla()[asistente][1])
    i = min(range(len(niveles)), key=lambda k: abs(niveles[k][0] - base))
    r = azar()
    sube = PROB_SUBE + bono / 100.0
    if r < sube:
        i = min(len(niveles) - 1, i + 1)
    elif r >= sube + PROB_MISMO:
        i = max(0, i - 1)
    return random.choice(niveles[i][1])


def paquete_producto(entidad, a, b):
    """s2c 0x001D codigo 50: lo que sale en la casilla Producto."""
    return struct.pack('<HIBBIi', 0x001D, int(entidad), 1, CODIGO_PRODUCTO, int(a), int(b))


@functools.lru_cache(maxsize=4096)
def con_tiempo(item_id):
    """Si la pieza caduca (持續時間 / 刪除時間 en item.xml)."""
    import inventario
    con = sqlite3.connect(_RAIZ / 'corpus' / 'content.db')
    try:
        f = inventario.fila_item(con, '"持續時間", "刪除時間"', int(item_id))
    finally:
        con.close()
    return bool(f) and any(str(x or '').strip() not in ('', '0') for x in f)


def _mejora(p, ranura):
    m = getattr(p, 'mejoras', None) or {}
    return m.get(ranura) or m.get(str(ranura))


def _mascota(p, ranura):
    m = getattr(p, 'mascotas', None) or {}
    return m.get(str(ranura)) or m.get(ranura)


def _quitar_mascota(p, ranura):
    m = getattr(p, 'mascotas', None)
    if m:
        m.pop(str(ranura), None)
        m.pop(ranura, None)
    mf = getattr(p, 'mascota', None)
    if isinstance(mf, dict) and mf.get('ranura') == ranura:
        p.mascota = None


def procesar(ses, addr, cuerpo):
    """c2s 0x0147 de la ventana de fusion."""
    import clases
    p = getattr(ses, 'personaje', None)
    bolsa = getattr(ses, 'inventario', None)
    if not p or bolsa is None or len(cuerpo) < 9:
        return
    modo, principal, asistente, pocion, aleatorio = struct.unpack_from('<BHHHH', cuerpo, 0)

    def aviso(texto):
        ses.enviar(clases.aviso(texto, tipo=0))

    if principal not in bolsa:
        aviso('The Main Item slot is empty.')                 # 2700
        return
    if not pocion or pocion not in bolsa:
        aviso('Fusion potion required.')                      # 2702
        return
    if not es_pocion(bolsa[pocion]):
        aviso('Input the fusion potion.')                     # 2703
        return
    if not asistente or asistente not in bolsa:
        aviso('The Assistant Item slot is empty.')            # 2701
        return
    if _mascota(p, principal) is not None:
        if int(bolsa[pocion]) in ID_POCION_FORMA:
            _forma(ses, addr, aviso, modo, principal, asistente, pocion, aleatorio)
            return
        if modo == 1:
            aviso('The fusion potion must be a shapeshift potion.')   # 2724
            return
        _fusion_mascota(ses, addr, aviso, principal, asistente, pocion, aleatorio)
        return
    if modo == 1:
        return
    if int(bolsa[pocion]) in ID_POCION_FORMA:
        aviso('Pet fusion potions can only be used for pet fusion.')   # 2716
        return
    import inventario
    if inventario.ranura_equipo_de(int(bolsa[principal])):
        _fusion_equipo(ses, addr, aviso, principal, asistente, pocion, aleatorio)
        return
    _fusion_consumible(ses, addr, aviso, principal, asistente, pocion, aleatorio)


def _gastar(ses, ranuras):
    """Quita una unidad de cada casilla (con su mejora) y devuelve las tocadas."""
    import app
    p = ses.personaje
    for r in ranuras:
        if r and r in ses.inventario:
            app._sacar(ses, r, 1)
            if r not in ses.inventario:
                m = getattr(p, 'mejoras', None) or {}
                m.pop(r, None)
                m.pop(str(r), None)
    return {r for r in ranuras if r}


def _cerrar(ses, addr, tocadas, producto=None):
    import app
    p = ses.personaje
    pk = list(app._refrescar(ses, sorted(tocadas)))
    if producto is not None:
        pk.append(paquete_producto(p.entity_id, producto, 0))
    ses.enviar(*pk)
    app._guardar_bolsa(ses, p.char_id)


def _fusion_consumible(ses, addr, aviso, principal, asistente, pocion, aleatorio):
    import app
    p, bolsa = ses.personaje, ses.inventario
    it_p, it_a = int(bolsa[principal]), int(bolsa[asistente])
    if tabla().get(it_p, (None, 0))[0] != CAT_CONSUMIBLE:
        aviso('The Main Item cannot be fused')                # 2717
        return
    if tabla().get(it_a, (None, 0))[0] != CAT_CONSUMIBLE:
        aviso('The Assistant Item cannot be fused')           # 2718
        return
    if aleatorio:
        aviso('The random slot does not require an item when fusing a consumable item.')  # 2731
        return
    if principal == asistente:
        falta = app._cant_de(ses, principal) < 2 * CANTIDAD_CONSUMIBLE
    else:
        falta = (app._cant_de(ses, principal) < CANTIDAD_CONSUMIBLE
                 or app._cant_de(ses, asistente) < CANTIDAD_CONSUMIBLE)
    if falta:
        aviso('Requires %d for each dish.' % CANTIDAD_CONSUMIBLE)     # 2714
        return
    it_pocion = int(bolsa[pocion])
    nuevo = resultado_consumible(it_p, it_a, bono_pocion(it_pocion))
    if not nuevo:
        aviso('Item error. Unable to fuse.')
        return
    tocadas = {principal, asistente, pocion}
    app._sacar(ses, principal, CANTIDAD_CONSUMIBLE)
    app._sacar(ses, asistente, CANTIDAD_CONSUMIBLE)
    app._sacar(ses, pocion, 1)
    ranura = app._meter(ses, nuevo, 1)
    if ranura is None:
        app._meter(ses, it_p, CANTIDAD_CONSUMIBLE)
        app._meter(ses, it_a, CANTIDAD_CONSUMIBLE)
        app._meter(ses, it_pocion, 1)
        _cerrar(ses, addr, tocadas)
        aviso('Your backpack is full.')
        return
    tocadas.add(ranura)
    _cerrar(ses, addr, tocadas, ranura)
    aviso('Fusion successful: %s' % nombre(nuevo))
    _logro(ses, 'fusion_cons:%d' % int(nuevo))
    log.info('[%s] %s fusiona %s + %s (pocion %s) -> %s', addr, p.nombre,
             nombre(it_p), nombre(it_a), nombre(it_pocion), nombre(nuevo))


def _fusion_equipo(ses, addr, aviso, principal, asistente, pocion, aleatorio):
    """string.xml 2783/2785: el asistente tiene que ser del mismo tipo y a no
    mas de 10 niveles; pasa UN atributo extra suyo al principal en
    proporcion. Exito 80% + pocion (cliente). Si falla, el principal se
    pierde (2739) salvo con pocion bendita (2740). El asistente, la pocion y
    el aleatorio se gastan siempre: solo queda el principal."""
    import random as _r
    import inventario
    import mejoras as _mj
    p, bolsa = ses.personaje, ses.inventario
    it_p, it_a = int(bolsa[principal]), int(bolsa[asistente])
    if inventario.categoria_item(it_p) != inventario.categoria_item(it_a):
        aviso('Please provide equipment of the same type.')   # 2719
        return
    if abs(inventario.nivel_de_item(it_p) - inventario.nivel_de_item(it_a)) > DIFERENCIA_NIVEL_EQUIPO:
        aviso('The level gap between the Main and Assistant Items cannot be more than %d.'
              % DIFERENCIA_NIVEL_EQUIPO)                       # 2712
        return
    mej_p, mej_a = _mejora(p, principal) or {}, _mejora(p, asistente) or {}
    if con_tiempo(it_p) or con_tiempo(it_a):
        aviso('Time limited equipment cannot be used for fusion.')    # 2746
        return
    extras_a = {k: v for k, v in (mej_a.get('extra') or {}).items() if v}
    rangos = _mj.rangos_verde(it_p) or {}
    candidatos = [k for k in extras_a if k in rangos]
    if not candidatos:
        aviso('The attribute of the Assistant item cannot be fused.')   # 2743
        return
    it_pocion = int(bolsa[pocion])
    d1, d2 = dato1_pocion(it_pocion), bono_pocion(it_pocion)
    exito = exito_equipo(d2)
    tocadas = _gastar(ses, [asistente, pocion, aleatorio])
    if _r.randint(1, 100) > exito:
        if protege(d1):
            aviso('Equipment fusion failed.')                  # 2740
        else:
            tocadas |= _gastar(ses, [principal])
            aviso('Equipment fusion failed, destroying all the equipment.')   # 2739
        _cerrar(ses, addr, tocadas)
        log.info('[%s] %s: fusion de equipo fallida (%d%%)', addr, p.nombre, exito)
        return
    stat = _r.choice(candidatos)
    suma = max(1, int(extras_a[stat]) * porcentaje_traspaso(d1) // 100)
    extras_p = dict(mej_p.get('extra') or {})
    tope = int(rangos[stat][1])
    if stat not in extras_p and len([v for v in extras_p.values() if v]) >= _mj.MAX_EXTRAS_ENTRADA:
        aviso('During the fusion process, all attributes of the Main Item reached their upper limits.')
    else:
        antes = int(extras_p.get(stat) or 0)
        extras_p[stat] = max(antes, min(tope, antes + suma))     # nunca baja
        if extras_p[stat] >= tope:
            aviso('During the fusion process, the attribute of the Main Item reached its upper limit.')  # 2747
        mej_p = dict(mej_p, extra=extras_p)
        p.mejoras = dict(getattr(p, 'mejoras', None) or {})
        p.mejoras.pop(str(principal), None)
        p.mejoras[principal] = mej_p
    tocadas.add(principal)
    _cerrar(ses, addr, tocadas, principal)
    aviso('Equipment fusion successful.')                      # 2741
    log.info('[%s] %s: fusion de equipo %s +%d %s (%d%%)', addr, p.nombre,
             nombre(it_p), suma, stat, exito)


def _fusion_mascota(ses, addr, aviso, principal, asistente, pocion, aleatorio):
    """string.xml 2783-2785 y la vista previa del cliente (FUN_005d3d30).

    Principal nivel 80+ y de rango alto, asistente nivel 60+, los dos vivos y
    ninguno sacado. Exito: politica configurada en exito_mascota. Pasan hasta 3
    atributos del asistente, solo los que en el principal no superan sus
    estrellas + 10 (igual que la vista previa), en proporcion. Los rangos
    iniciales de pet.xml NO son topes de crecimiento. Si falla, la mascota
    principal muere (2727), salvo con
    pocion bendita. El asistente, la pocion y el aleatorio se gastan."""
    import random as _r
    import mascotas as _ms
    p, bolsa = ses.personaje, ses.inventario
    m_p, m_a = _mascota(p, principal), _mascota(p, asistente)
    if m_a is None:
        aviso('The Assistant Item must be a pet egg.')         # 2705
        return
    if int(bolsa[pocion]) in ID_POCION_FORMA:
        aviso('Shapeshift fusion is not available yet.')
        return
    for m in (m_p, m_a):
        if m.get('fuera'):
            aviso("You're now using this pet.")                # 2707
            return
        if int(m.get('hp') or 0) <= 0:
            aviso('The pet is dead.')                          # 604
            return
    if int(m_a.get('nivel') or 0) < NIVEL_MIN_ASISTENTE:
        aviso('The level of the Assistant Item must be at least %d.' % NIVEL_MIN_ASISTENTE)
        return
    if int(m_p.get('nivel') or 0) < NIVEL_MIN_PRINCIPAL:
        aviso('The level of the Main Item must be at least %d.' % NIVEL_MIN_PRINCIPAL)
        return
    if int(m_p.get('rango') or 1) < RANGO_MIN_PRINCIPAL:
        aviso('The pet for the Main Item must be high level pet.')   # 2710
        return
    estrellas = max(1, int(m_p.get('estrellas') or 1))
    bon_p, bon_a = dict(m_p.get('bonos') or {}), dict(m_a.get('bonos') or {})
    orden = sorted((k for k in _ms.STATS_BONO if int(bon_a.get(k) or 0) > 0),
                   key=lambda k: -_ms.estrella_de_bono(bon_a[k], k))
    elegibles = [k for k in orden
                 if _ms.estrella_de_bono(bon_p.get(k, 0), k) <= estrellas + 10][:3]
    if not elegibles:
        aviso('During the fusion process, all attributes of the Main Item reached their upper limits.')
        return
    it_pocion = int(bolsa[pocion])
    d1, d2 = dato1_pocion(it_pocion), bono_pocion(it_pocion)
    exito = exito_mascota(estrellas, m_p.get('nivel') or 1, d2)
    tocadas = _gastar(ses, [pocion, aleatorio])
    _quitar_mascota(p, asistente)
    tocadas |= _gastar(ses, [asistente])
    if _r.randint(1, 100) > exito:
        if not protege(d1):
            _quitar_mascota(p, principal)
            tocadas |= _gastar(ses, [principal])
            aviso('Pet fusion failed. The Main pet died.')     # 2727
        else:
            aviso('Pet Fusion failed.')                        # 2786
        _cerrar(ses, addr, tocadas)
        log.info('[%s] %s: fusion de mascota fallida (%d%%)', addr, p.nombre, exito)
        return
    pct = porcentaje_traspaso(d1)
    for k in elegibles:
        suma = max(1, int(bon_a[k]) * pct // 100)
        antes = int(bon_p.get(k) or 0)
        bon_p[k] = antes + suma
    m_p['bonos'] = bon_p
    m_p['estrellas'] = _ms.calcular_estrellas_total(bon_p)
    tocadas.add(principal)
    _cerrar(ses, addr, tocadas, principal)
    aviso('Pet fusion successful.')                            # 2728
    _logro(ses, 'fusion_pets')
    _logro(ses, 'fusion_estrellas', int(m_p.get('estrellas') or 1) // 10, maximo=True)
    log.info('[%s] %s: fusion de mascota %s %s (%d%%)', addr, p.nombre,
             m_p.get('nombre'), elegibles, exito)


# ---- Fusion de TRANSFORMACION (Shape Fusion Potion) ----
#
# REA: game.fuseispettrans (FUN_0059a4b0) solo deja seguir si la pocion es la
# 0x3eca (16074). fuseconfirm (FUN_005d3020) pide ademas que la principal
# tenga 3 estrellas o mas (+0x130 >= 30, string 2720) y que NI la principal
# NI la asistente esten ya en la lista 寵物 de fuse.xml (2717/2718): una
# mascota de fusion no se vuelve a transformar.
#
# El flujo, de script/fuse.l: Preview -> fuseok(1) = c2s 0x0147 modo 1 -> el
# servidor contesta 0x001D codigo 51 con el fuse_id del resultado (el
# cliente lo busca en fuse.xml, tabla 0xae1b70, y escribe "Result Preview:
# <nombre>") -> OK manda game.netcommand(47, 1) (c2s 0x0016 accion 47) y
# Cancelar netcommand(47, 0).
#
# El resultado es un huevo de la lista 寵物 de serv_fuse.xml, cuyo 權值 es su
# nivel de valor (1 los elfos ... 43 los dragones). Como se elige no esta en
# el cliente: el nivel sale de las estrellas de la principal (3 estrellas los
# niveles bajos, 8 los altos) con el mismo 60/30/10 de los consumibles, y un
# consumible de fusion en el hueco Aleatorio ayuda a subir ("for better or
# worse"). La nueva hereda nivel, bonos y estrellas de la principal; de la
# asistente no queda nada (string.xml 2785).
CODIGO_VISTA_PREVIA = 51
ACCION_ACEPTAR_FORMA = 47
ESTRELLAS_MIN_FORMA = 30


@functools.lru_cache(maxsize=1)
def _niveles_mascota():
    """[(nivel, [(fuse_id, item)])] de la lista 寵物, de menor a mayor."""
    s = _ultimo('serv_fuse.xml')
    por_nivel = {}
    if s:
        for item, fid, peso in re.findall(
                r'道具編號="(\d+)" 融合編號="(\d+)" 權值="(\d+)" 融合類別="寵物"',
                s.read_text(encoding='utf-8')):
            por_nivel.setdefault(int(peso), []).append((int(fid), int(item)))
    return sorted(por_nivel.items())


def resultado_forma(estrellas, item_aleatorio=0, azar=random.random):
    """(fuse_id, item) del huevo que sale de la transformacion."""
    niveles = _niveles_mascota()
    if not niveles:
        return None
    frac = (max(ESTRELLAS_MIN_FORMA, min(80, int(estrellas))) - ESTRELLAS_MIN_FORMA) / float(80 - ESTRELLAS_MIN_FORMA)
    i = int(round(frac * (len(niveles) - 1)))
    extra = 0.0
    cat, nv = tabla().get(int(item_aleatorio or 0), (None, 0))
    if cat == CAT_CONSUMIBLE and nv:
        extra = 0.20 * nv / 111.0
    r = azar()
    sube = PROB_SUBE + extra
    if r < sube:
        i = min(len(niveles) - 1, i + 1)
    elif r >= sube + PROB_MISMO:
        i = max(0, i - 1)
    return random.choice(niveles[i][1])


def paquete_vista_previa(entidad, fuse_id):
    """s2c 0x001D codigo 51: CreatePetPreRes con el fuse_id del resultado."""
    return struct.pack('<HIBBII', 0x001D, int(entidad), 1, CODIGO_VISTA_PREVIA, 0, int(fuse_id))


def _validar_forma(ses, aviso, principal, asistente):
    p = ses.personaje
    m_p, m_a = _mascota(p, principal), _mascota(p, asistente)
    if m_a is None:
        aviso('The Assistant Item must be a pet egg.')         # 2705
        return None
    for m in (m_p, m_a):
        if m.get('fuera'):
            aviso("You're now using this pet.")                # 2707
            return None
        if int(m.get('hp') or 0) <= 0:
            aviso('The pet is dead.')                          # 604
            return None
    lista = tabla()
    if lista.get(int(ses.inventario[principal]), (None,))[0] == CAT_MASCOTA:
        aviso('The Main Item cannot be fused')                 # 2717
        return None
    if lista.get(int(ses.inventario[asistente]), (None,))[0] == CAT_MASCOTA:
        aviso('The Assistant Item cannot be fused')            # 2718
        return None
    if int(m_p.get('estrellas') or 1) < ESTRELLAS_MIN_FORMA:
        aviso('Only pets that are 3 stars or higher can be used.')    # 2720
        return None
    if int(m_a.get('nivel') or 0) < NIVEL_MIN_ASISTENTE:
        aviso('The level of the Assistant Item must be at least %d.' % NIVEL_MIN_ASISTENTE)
        return None
    if int(m_p.get('nivel') or 0) < NIVEL_MIN_PRINCIPAL:
        aviso('The level of the Main Item must be at least %d.' % NIVEL_MIN_PRINCIPAL)
        return None
    return m_p, m_a


def _forma(ses, addr, aviso, modo, principal, asistente, pocion, aleatorio):
    """Modo 1: calcula y ensena el resultado. Modo 0: lo hace del tiron."""
    v = _validar_forma(ses, aviso, principal, asistente)
    if not v:
        return
    m_p, _m_a = v
    bolsa = ses.inventario
    alea = int(bolsa.get(aleatorio) or 0) if aleatorio else 0
    clave = (principal, asistente, pocion, aleatorio, int(bolsa[principal]), int(bolsa[asistente]))
    pend = getattr(ses, 'fusion_pendiente', None)
    if not pend or pend.get('clave') != clave:
        # El resultado se fija la primera vez: repetir la vista previa no
        # vuelve a tirar los dados.
        res = resultado_forma(m_p.get('estrellas') or 1, alea)
        if not res:
            aviso('Item error. Unable to fuse.')
            return
        pend = {'clave': clave, 'fuse_id': res[0], 'item': res[1]}
        ses.fusion_pendiente = pend
    if modo == 1:
        ses.enviar(paquete_vista_previa(ses.personaje.entity_id, pend['fuse_id']))
        return
    aplicar_forma(ses, addr, aviso)


def aceptar_forma(ses, addr, si):
    """c2s 0x0016 accion 47 (netcommand(47, 1|0)) tras la vista previa."""
    import clases
    if not si:
        return
    aplicar_forma(ses, addr, lambda t: ses.enviar(clases.aviso(t, tipo=0)))


def aplicar_forma(ses, addr, aviso):
    import random as _r
    import app
    pend = getattr(ses, 'fusion_pendiente', None)
    p, bolsa = ses.personaje, ses.inventario
    if not pend or not p:
        return
    principal, asistente, pocion, aleatorio = pend['clave'][:4]
    if (principal not in bolsa or asistente not in bolsa or pocion not in bolsa
            or int(bolsa[principal]) != pend['clave'][4] or int(bolsa[asistente]) != pend['clave'][5]
            or int(bolsa[pocion]) not in ID_POCION_FORMA):
        ses.fusion_pendiente = None
        aviso('Item error. Unable to fuse.')
        return
    v = _validar_forma(ses, aviso, principal, asistente)
    if not v:
        return
    ses.fusion_pendiente = None
    m_p = v[0]
    it_pocion = int(bolsa[pocion])
    d1, d2 = dato1_pocion(it_pocion), bono_pocion(it_pocion)
    exito = exito_mascota(m_p.get('estrellas') or 1, m_p.get('nivel') or 1, d2)
    tocadas = _gastar(ses, [pocion, aleatorio])
    _quitar_mascota(p, asistente)
    tocadas |= _gastar(ses, [asistente])
    if _r.randint(1, 100) > exito:
        if not protege(d1):
            _quitar_mascota(p, principal)
            tocadas |= _gastar(ses, [principal])
            aviso('Pet fusion failed. The Main pet died.')     # 2727
        else:
            aviso('Pet Fusion failed.')                        # 2786
        _cerrar(ses, addr, tocadas)
        log.info('[%s] %s: transformacion fallida (%d%%)', addr, p.nombre, exito)
        return
    hereda = {'bonos': dict(m_p.get('bonos') or {}),
              'estrellas': int(m_p.get('estrellas') or 1),
              'rango': int(m_p.get('rango') or 1)}
    nivel = int(m_p.get('nivel') or 1)
    _quitar_mascota(p, principal)
    tocadas |= _gastar(ses, [principal])
    ranura = app._meter(ses, pend['item'], 1, pet_metadata=hereda)
    if ranura is None:
        aviso('Your backpack is full.')
        _cerrar(ses, addr, tocadas)
        return
    nueva = _mascota(p, ranura)
    if nueva is not None:
        nueva.pop('nombre', None)
        import mascotas as _ms
        nueva['nombre'] = _ms.ficha_de_sprite(int(nueva.get('sprite') or 0)).get('nombre') or nombre(pend['item'])
        try:
            app._pet_subir(nueva, nivel)
        except Exception:
            nueva['nivel'] = nivel
    tocadas.add(ranura)
    _cerrar(ses, addr, tocadas, ranura)
    aviso('Pet fusion result: %s' % nombre(pend['item']))      # 2723
    aviso('Pet fusion successful.')                            # 2728
    _logro(ses, 'fusion_pet:%d' % int(pend['item']))
    _logro(ses, 'fusion_pets')
    log.info('[%s] %s: transformacion -> %s (fuse_id %d, %d%%)', addr, p.nombre,
             nombre(pend['item']), pend['fuse_id'], exito)


def _logro(ses, clave, n=1, maximo=False):
    """Contador de logros de fusion (融合相關), ver app._logros_contar."""
    try:
        import app
        app._logros_contar(ses, clave, n, maximo=maximo)
    except Exception:
        log.exception('logros de fusion')
