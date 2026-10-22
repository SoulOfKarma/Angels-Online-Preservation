"""TOTEM WAR: la guerra de facciones por los ocho campos de batalla.

QUE TRAE EL CLIENTE (update26/setting/eng/stage.xml y los .mpc):
  Los mapas de guerra van marcados con 戰地圖="是". En el cliente actual son
  ocho, del 200 al 207, copias "[TW]" de los campos de siempre:

      200 Crashing Hillock      (campo 8)     204 Mysterious Wetland (15)
      201 South of Mirror Lake  (9)           205 Thorn Wasteland    (16)
      202 Thunder Ruins         (11)          206 Quiet Vale         (17)
      203 North of Mirror Lake  (12)          207 Dragon Graveyard   (21)

  Megalith Plain (28) era de guerra en versiones viejas y ya no lo es.
  Cada arena trae los portales de las cuatro facciones y el de la milicia
  (TAG 1 Aurora, 2 Beast, 3 Steel, 4 Shadow, 5 Militia) y el centro del mapa
  en (165,95), donde el .mpc pone el objeto del evento 1001.

  Ningun evento de los mapas lleva a 200..207: la entrada la abre el servidor.

LA REGLA (la del usuario y la de la wiki, directory_totem-war): el totem del
centro lo gana la FACCION que lo rompe. Mientras dura la guerra se vuelve a
levantar con el nombre de su nueva duena, y los de esa faccion ya no le
pueden pegar; las otras si. Al acabar, se queda con el mapa la ultima que lo
rompio. Si quien lo rompe esta en una liga, la liga se queda tambien el
territorio (gremio_territorios), que es lo que miran el Terra Keeper y el
Heaven General.

HORARIO: miercoles 21:00 y sabado 14:00, hora de Chile, dos horas. Se usa la
hora LOCAL del servidor (Windows ya la lleva con el cambio de horario; el
Python de laragon no trae tzdata para pedir America/Santiago). Por GM:
/twstart [min] (30 por defecto; repetirlo vuelve a poner el reloj) y /twstop.
"""
import asyncio
import datetime
import logging
import struct
import time

import cuentas

log = logging.getLogger('totem_war')

CAMPO_A_TW = {8: 200, 9: 201, 11: 202, 12: 203, 15: 204, 16: 205, 17: 206, 21: 207}
TW_A_CAMPO = {v: k for k, v in CAMPO_A_TW.items()}
NOMBRE_TW = {200: 'Crashing Hillock', 201: 'South of Mirror Lake', 202: 'Thunder Ruins',
             203: 'North of Mirror Lake', 204: 'Mysterious Wetland', 205: 'Thorn Wasteland',
             206: 'Quiet Vale', 207: 'Dragon Graveyard'}

# Facciones: los codigos de login.CODIGO_FACCION.
NOMBRE_FACCION = {0: 'Neutral', 1: 'Aurora', 2: 'Beast', 3: 'Steel', 4: 'Shadow', 5: 'Militia'}
TAG_DE_FACCION = {1: 1, 2: 2, 3: 3, 4: 4}
TAG_MILICIA = 5

# El totem del centro. Tipo y sprite del Aur-Fort IV (D) de monster.xml (HP
# 50.000.000, sin ataque, inmune a todo).
TOTEM_NPC = 9847
TOTEM_SPRITE = 43406
TOTEM_TILE = (165, 97)
TOTEM_BASE_EID = 95_000_000
# Reaparece casi al instante (lo pidio el usuario: con 8 s se notaba).
SEGUNDOS_RELEVANTAR = 1

HORARIO = ((2, 21, 0), (5, 14, 0))       # (weekday, hora, minuto): mie 21:00, sab 14:00
DURACION_HORARIO = 120                    # minutos
MINUTOS_GM = 30

_ESTADO = {'fin': 0.0, 'por': None, 'arranque_horario': None}

# MODO DE GUERRA. 'antigua' (la que pidio la comunidad, 20/10/2026): el totem
# esta en el propio campo y se pelea ahi, como en Celestia. 'arena': las copias
# [TW] 200..207 del cliente nuevo. La propiedad se guarda con la clave de la
# arena en los dos modos (tw_faccion_duena, gremio_territorios).
MODO = 'antigua'

# Los campos de la guerra antigua. Sunflower Plain (7), Foggy Forest (20),
# Mysterious Garden (22) y Megalith Plain (28) tambien tenian totem en Celestia,
# pero el usuario los deja como zonas de entrenamiento.
# Casillas medidas en Celestia (0x012E, 20/10/2026), salvo campo 8:
# ajuste visual propuesto por el usuario el 21/10: (93,176) -> (92,174).
# Confirmado por el usuario en pantalla; no desplazar los otros campos.
TOTEM_CAMPO = {8: (92, 174), 9: (147, 100), 11: (196, 56), 12: (288, 11),
               15: (151, 156), 16: (162, 88), 17: (48, 95), 21: (153, 104)}
# El totem es el monstruo 21397 "Totem Lv 1" (el mismo en los doce campos de
# Celestia); el nivel lo sube la liga con ofrendas (ventana 0x012F).
TOTEM_TIPO_CAMPO = 21397
# Los cuatro campos de ENTRENAMIENTO (sin guerra) tambien tienen su totem en
# Celestia, junto al Terra Keeper; el minimapa lo marca. Casillas de los
# 0x012E capturados, emparejadas con el Terra Keeper de la misma captura:
# Sunflower Plain, Foggy Forest, Mysterious Garden y Megalith Plain. Son
# decorativos: siempre a la vista y nunca se les puede pegar.
TOTEM_ENTRENAMIENTO = {7: (216, 46), 20: (221, 56), 22: (206, 107), 28: (130, 92)}


def es_totem_decorativo(stage) -> bool:
    return int(stage or 0) in TOTEM_ENTRENAMIENTO


def _tw(stage) -> int:
    """La clave de propiedad (200..207) de un campo o de su arena."""
    st = int(stage or 0)
    return CAMPO_A_TW.get(st, st)


def es_arena(stage) -> bool:
    return int(stage or 0) in TW_A_CAMPO


# ------------------------------------------------------------------ estado

def activa() -> bool:
    return time.time() < _ESTADO['fin']


def restante() -> int:
    return max(0, int(_ESTADO['fin'] - time.time()))


def es_mapa_tw(stage) -> bool:
    """Si en ese mapa se pelea la guerra (y hay totem)."""
    st = int(stage or 0)
    if MODO == 'antigua':
        return st in TOTEM_CAMPO
    return st in TW_A_CAMPO


# Cada vez que el totem se vuelve a levantar lleva un id NUEVO. Con el mismo
# id, el cliente aun tenia la entidad muerta (le acababan de llegar dos
# 0x0013 a 0 y el 0x0007): tardaba en verse y salia sin barra de vida
# (sesion del 20/10/2026 15:42). Los ids siguen siendo distintos en sus 16
# bits bajos, que es como indexa el cliente su tabla de entidades.
_GENERACION = {}


def eid_totem(stage) -> int:
    return TOTEM_BASE_EID + 16 * _GENERACION.get(_tw(stage), 0) + _tw(stage)


def nueva_generacion(stage):
    k = _tw(stage)
    _GENERACION[k] = (_GENERACION.get(k, 0) + 1) % 8


def codigo_faccion(personaje) -> int:
    import login as _lg
    return int(_lg.CODIGO_FACCION.get(getattr(personaje, 'faction', '') or '', 5))


def _tabla():
    con = cuentas._get_conn()
    try:
        con.execute('CREATE TABLE IF NOT EXISTS tw_faccion_duena ('
                    'tw_stage INTEGER PRIMARY KEY, faccion INTEGER NOT NULL, '
                    'capturado_en TEXT DEFAULT CURRENT_TIMESTAMP)')
        con.commit()
    finally:
        con.close()


_DUENAS = {}
_DISPUTADAS = {}   # stage -> guild_id; se confirma al finalizar, no al primer golpe.
_RONDA = {}        # char_id -> bajas en esta guerra (el K.O. grande del marcador)


def liga_duena(stage):
    st = _tw(stage)
    return _DISPUTADAS.get(st, cuentas.db_obtener_dueno_de_territorio(st))


def puede_disputar(ses, stage):
    """Una liga sin territorio, o la defensora; nunca acaparar dos campos."""
    import gremios
    p = getattr(ses, 'personaje', None)
    g = gremios.obtener_gremio_de(p.char_id) if p else None
    if not g:
        return False
    gid = int(g['guild_id'])
    return not any(liga_duena(st) == gid and st != _tw(stage) for st in TW_A_CAMPO)


def faccion_duena(stage) -> int:
    """0 si el mapa es neutral. Va en memoria: la mira cada golpe al totem."""
    stage = _tw(stage)
    if stage in _DUENAS:
        return _DUENAS[stage]
    with cuentas._LOCK:
        _tabla()
        con = cuentas._get_conn()
        try:
            r = con.execute('SELECT faccion FROM tw_faccion_duena WHERE tw_stage=?',
                            (int(stage),)).fetchone()
        finally:
            con.close()
    _DUENAS[stage] = int(r[0]) if r else 0
    return _DUENAS[stage]


def poner_faccion_duena(stage, faccion):
    stage = _tw(stage)
    _DUENAS[int(stage)] = int(faccion)
    with cuentas._LOCK:
        _tabla()
        con = cuentas._get_conn()
        try:
            con.execute('INSERT OR REPLACE INTO tw_faccion_duena (tw_stage, faccion, capturado_en) '
                        'VALUES (?, ?, CURRENT_TIMESTAMP)', (int(stage), int(faccion)))
            con.commit()
        finally:
            con.close()


def dueno_del_campo(campo) -> str:
    """Quien tiene el territorio del campo normal `campo` (16 Thorn Wasteland...).
    Para el Terra Keeper, cuyos textos del cliente no nombran a la liga."""
    st = CAMPO_A_TW.get(int(campo or 0))
    if not st:
        return ''
    gid = cuentas.db_obtener_dueno_de_territorio(st)
    g = cuentas.db_obtener_gremio(gid) if gid else None
    f = NOMBRE_FACCION.get(faccion_duena(st), 'Neutral')
    if g:
        return '%s belongs to league %s (%s faction).' % (NOMBRE_TW[st], g['nombre'], f)
    if faccion_duena(st):
        return '%s belongs to the %s faction; no league holds it.' % (NOMBRE_TW[st], f)
    return '%s has no owner yet.' % NOMBRE_TW[st]


def _dueno_corto(st):
    """'Thorn Wasteland: Moonlights (Beast)' o 'Quiet Vale: Neutral'."""
    gid = cuentas.db_obtener_dueno_de_territorio(st)
    g = cuentas.db_obtener_gremio(gid) if gid else None
    f = NOMBRE_FACCION.get(faccion_duena(st), 'Neutral')
    if g:
        return '%s: %s (%s)' % (NOMBRE_TW[st], g['nombre'], f)
    return '%s: %s' % (NOMBRE_TW[st], f)


def kills_ko(entity_id, ronda, total) -> bytes:
    """s2c 0x001D codigo 25: el marcador K.O. (REA 00602470 -> 00602110):
    a = bajas de la ronda (el numero grande, 3 cifras), b = total (5 cifras).
    El cliente lo lee tambien de la ficha del 0x0002 (+0xf6f y +0xf6b)."""
    return struct.pack('<HIBBII', 0x001D, int(entity_id), 1, 25,
                       max(0, int(ronda)) % 1000, max(0, int(total)) % 100000)


# Creditos de rango por baja en la arena. El cliente los muestra con el 642
# ("Obtain %s Credit."); la cantidad oficial no esta en sus datos.
CREDITOS_POR_BAJA = 10


# LOS OBJETOS DE LA ARENA que el servidor tiene que mandar (server.obd):
#   60403 / 60404  光柵 rejas de luz naranja / azul (las barreras de faccion)
#   60373          puerta del campo de batalla, cerrada
#   60236          base de torre de defensa (SERV_CLASS_TOWERBASEOBJ)
# Lo demas del .mpc son marcadores ocultos (TAG, casillas de evento 60384,
# generadores) o decorado que dibuja el cliente. Las arenas no tienen
# plantilla, asi que nunca se mandaba ninguno.
OBJETOS_ARENA = (60403, 60404, 60373, 60236)
OBJETO_BASE_EID = 96_500_000
_CUERPO_TORNADO = bytes.fromhex('c0d3010000000000c2020000e714000000000000270000000000'
                                '00001a000000dc0661ea00004080030000')
_OBJ_ARENA = {}


def objetos_arena(stage):
    """Los 0x000E de los objetos visibles de la arena, desde su .mpc."""
    st = int(stage)
    if st in _OBJ_ARENA:
        return _OBJ_ARENA[st]
    salida = []
    try:
        import pathlib as _pl
        import sys as _sys
        tools = _pl.Path(__file__).resolve().parent.parent / 'tools'
        if str(tools) not in _sys.path:
            _sys.path.append(str(tools))
        import mapa_del_cliente
        import poblar_del_cliente
        m = mapa_del_cliente.mapa(st)
        cuerpos = poblar_del_cliente.objetos_que_se_mandan()
        for k, o in enumerate(x for x in (m.objetos if m else []) if x['id'] in OBJETOS_ARENA):
            b = bytearray(cuerpos.get(o['id']) or _CUERPO_TORNADO)
            struct.pack_into('<I', b, 0, OBJETO_BASE_EID + st * 1000 + k)
            struct.pack_into('<I', b, 4, int(o['capa']))
            struct.pack_into('<II', b, 8, int(o['px'][0]), m.alto * 32 - int(o['px'][1]))
            struct.pack_into('<H', b, 34, int(o['id']))
            if o['id'] not in cuerpos:
                b[38:41] = b'\x00\x00\x00'     # sin marca de evento: no se pulsa
            salida.append(struct.pack('<H', 0x000E) + bytes(b))
    except Exception:
        log.exception('objetos de la arena %s', st)
    _OBJ_ARENA[st] = salida
    return salida


# LOS PORTALES DE CRISTAL de cada faccion (Aurora/Beast/Steel/Shadow/Militia
# Portal, NPC 8978..8982). Los declara el .mpc de la arena (+22 el NPC, +30 la
# raiz de su dialogo 8274..8278: "By the power of the crystals, transport me
# to..."); sin plantilla no salian y el cuadro de arena quedaba vacio.
NPC_BASE_EID = 96_600_000
_NPC_ARENA = {}


def npcs_arena(stage):
    """[(eid, npc_type, nombre, tile, sprite)] de los NPC de la arena."""
    st = int(stage)
    if st not in _NPC_ARENA:
        salida = []
        try:
            import pathlib as _pl
            import sys as _sys
            tools = _pl.Path(__file__).resolve().parent.parent / 'tools'
            if str(tools) not in _sys.path:
                _sys.path.append(str(tools))
            import npcs_del_cliente
            for k, n in enumerate(npcs_del_cliente.declarados(st)):
                salida.append((NPC_BASE_EID + st * 100 + k, int(n['npc_type']),
                               n['nombre'], tuple(n['tile']), int(n['sprite'])))
        except Exception:
            log.exception('NPC de la arena %s', st)
        _NPC_ARENA[st] = salida
    return _NPC_ARENA[st]


# LAS FORTALEZAS DE LAS PUERTAS (monster.xml 9847..9854, 50.000.000 de vida).
# Los generadores de la arena (zonas 6..9 la "(D)", 18..21 la "(A)", 44..47 los
# 10 Totem Guard) apuntan a TAGs en la esquina (1,202): el sitio lo pone el
# servidor. En el video del oficial la "Aur-Fort (D)" esta en la puerta de
# Aurora; las 4 puertas (60373) se asignan a la faccion cuya llegada queda mas
# cerca, igual en las 8 arenas: (131,102) Aurora, (186,112) Beast,
# (202,82) Steel, (145,72) Shadow.
FUERTE_D = {1: 9847, 2: 9848, 3: 9849, 4: 9850}
FUERTE_A = {1: 9851, 2: 9852, 3: 9853, 4: 9854}
FACCION_DE_FUERTE = {t: f for d in (FUERTE_D, FUERTE_A) for f, t in d.items()}
ZONA_D = {1: 6, 2: 7, 3: 8, 4: 9}
ZONA_A = {1: 18, 2: 19, 3: 20, 4: 21}
ZONA_GUARDIAS = {1: 44, 2: 45, 3: 46, 4: 47}
FUERTE_BASE_EID = 96_700_000


def puertas_de(stage):
    """{faccion: casilla de su puerta} de la arena."""
    try:
        import pathlib as _pl
        import sys as _sys
        tools = _pl.Path(__file__).resolve().parent.parent / 'tools'
        if str(tools) not in _sys.path:
            _sys.path.append(str(tools))
        import mapa_del_cliente
        m = mapa_del_cliente.mapa(int(stage))
        puertas = [tuple(o['tile']) for o in m.objetos if o['id'] == 60373]
        salida = {}
        for f in (1, 2, 3, 4):
            t = (m.tags.get(f) or [(0, 0)])[0]
            libres = [q for q in puertas if q not in salida.values()]
            if libres:
                salida[f] = min(libres, key=lambda q: (q[0] - t[0]) ** 2 + (q[1] - t[1]) ** 2)
        return salida
    except Exception:
        log.exception('puertas de la arena %s', stage)
        return {}


def puntos_de_zona(stage):
    """{(stage, zona): [casillas]} para que las fortalezas (A) y los guardias
    que saca el evento de caida salgan en su puerta y no en la esquina."""
    salida = {}
    for f, (x, y) in puertas_de(stage).items():
        salida[(int(stage), ZONA_D[f])] = [[x, y]]
        salida[(int(stage), ZONA_A[f])] = [[x, y]]
        salida[(int(stage), ZONA_GUARDIAS[f])] = [[x + dx, y + dy] for dx, dy in
                                                  ((-3, -3), (0, -4), (3, -3), (-4, 0), (4, 0),
                                                   (-3, 3), (0, 4), (3, 3), (-2, 0), (2, 0))]
    return salida


def crear_fuertes(stage):
    """Las 4 fortalezas (D), una en cada puerta."""
    import combate as _cb
    import app as _a
    salida = []
    for f, (x, y) in sorted(puertas_de(stage).items()):
        tipo = FUERTE_D[f]
        nombre, sprite = _a._monstruo_bd(tipo)
        m = _cb.Monstruo(FUERTE_BASE_EID + int(stage) * 10 + f, tipo, nombre,
                         [x, y], sprite, stage=int(stage))
        m.es_fuerte_tw = True
        m.faccion_fuerte = f
        m.generado = True          # no reaparece solo: lo vuelve a sacar el evento
        m.zona_generador = ZONA_D[f]
        m.move_range = 0
        m.move_speed = 0
        m.es_estatico = True
        salida.append(m)
    return salida


def puede_pegar_fuerte(ses, m) -> bool:
    """Una fortaleza la atacan las OTRAS facciones, y solo en guerra."""
    p = getattr(ses, 'personaje', None)
    if p is None or not activa():
        return False
    f = codigo_faccion(p)
    return f in TAG_DE_FACCION and f != FACCION_DE_FUERTE.get(int(m.npc_type))


def junto_al_terra_keeper(campo):
    """La casilla al lado del Terra Keeper del campo (de su plantilla), o el
    punto de aparicion del mapa si no esta."""
    import json as _js
    import pathlib as _pl
    import login as _lg
    f = _lg.PLANTILLAS_POR_STAGE.get(int(campo))
    if f:
        try:
            d = _js.loads((_pl.Path(__file__).parent / 'plantillas' / f).read_text(encoding='utf-8'))
            for e in d.get('spawns', []):
                if e.get('nombre') == 'Terra Keeper':
                    return int(e['tile'][0]) + 1, int(e['tile'][1]) + 1
        except Exception:
            log.debug('Terra Keeper de %s', campo, exc_info=True)
    return _lg.spawn_de(int(campo))


def nombre_totem(stage) -> str:
    """Como en Celestia: el nombre de la liga duena, o '<faccion> Totem'."""
    gid = liga_duena(stage)
    g = cuentas.db_obtener_gremio(gid) if gid else None
    if g:
        return str(g['nombre'])[:16]
    f = faccion_duena(stage)
    return '%s Totem' % NOMBRE_FACCION.get(f, 'Neutral')


def paquete_territorios():
    """S2C 0x0131: u16 n; filas de 29 B (campo, faccion, ID DE LIGA, nombre17).

    REA 0060b690: el +8 de cada fila va al primer campo de la entrada, y la
    ficha de la liga (00662e00, "Terra:") lo compara con el id de la liga del
    jugador (+0x5e05). Aqui iba el LOGO, asi que el cliente nunca veia su
    territorio y ponia "No territory" aunque la base dijera lo contrario.
    """
    filas = []
    for st, campo in sorted(TW_A_CAMPO.items()):
        gid = liga_duena(st)        # incluye la que va ganando en esta guerra
        g = cuentas.db_obtener_gremio(gid) if gid else None
        nombre = str(g['nombre'] if g else '').encode('latin-1', 'replace')[:16]
        filas.append(struct.pack('<III17s', campo, faccion_duena(st),
                                 int(gid) if g else 0, nombre))
    # Y las arenas 200..207 con su faccion, como manda Celestia: el cliente mira
    # la fila del mapa donde esta para saber si el campo es suyo (0060b690).
    for st in sorted(TW_A_CAMPO):
        filas.append(struct.pack('<III17s', st, faccion_duena(st), 0, b''))
    # Megalith Plain ya no es TW en update26; limpiar tambien esa fila antigua.
    filas.append(struct.pack('<III17s', 28, 0, 0, b''))
    return struct.pack('<HH', 0x0131, len(filas)) + b''.join(filas)


# ------------------------------------------------------------------ totem

def _totem_clase():
    import combate as _cb

    class TotemTW(_cb.Monstruo):
        """El totem del centro. La vida es la de siempre, pero los golpes de
        la faccion duena no le bajan nada: se mira quien esta pegando ahora
        (combate.ATACANTE, el mismo que usa registrar_dano)."""
        es_totem_tw = True

        @property
        def hp(self):
            return self.__dict__.get('_hp', 0)

        @hp.setter
        def hp(self, valor):
            viejo = self.__dict__.get('_hp')
            if viejo is not None and valor < viejo and getattr(self, 'decorativo', False):
                return            # el de un campo de entrenamiento no se rompe
            if viejo is not None and valor < viejo and activa():
                # La guerra es de FACCIONES: cualquiera de otra faccion le pega,
                # tenga liga o no. La liga solo decide si ademas se queda el
                # territorio (capturado()).
                a = _cb.ATACANTE[0]
                if getattr(a, 'personaje', None) is not None and not puede_pegar(a, self):
                    return
            if viejo is not None and valor < viejo and not activa():
                return            # fuera de la guerra no se le puede pegar
            self.__dict__['_hp'] = max(0, int(valor))

    return TotemTW


def puede_pegar(ses, m) -> bool:
    """Si `ses` puede danar el totem: solo en guerra, y nunca la faccion que
    ya lo tiene. Neutro (nadie lo rompio): le pega cualquiera. La milicia y
    los de Heaven no son faccion de guerra y no le pegan."""
    p = getattr(ses, 'personaje', None)
    if p is None or not activa() or es_totem_decorativo(getattr(m, 'stage', 0)):
        return False
    f = codigo_faccion(p)
    if f not in TAG_DE_FACCION:
        return False
    return f != faccion_duena(int(m.stage))


def motivo_no_pegar(ses, m) -> str:
    p = getattr(ses, 'personaje', None)
    if not activa():
        return 'The totem battle has not begun.'
    if p is not None and codigo_faccion(p) not in TAG_DE_FACCION:
        return 'Only the four factions can fight for the totem.'
    return 'Your faction already holds this totem.'


def crear_totem(stage):
    """El Monstruo del totem para la sala compartida del mapa TW."""
    if es_totem_decorativo(stage):
        m = _totem_clase()(eid_totem(stage), TOTEM_TIPO_CAMPO, 'Totem',
                           list(TOTEM_ENTRENAMIENTO[int(stage)]), SPRITE_TOTEM_NEUTRO, stage=int(stage))
        m.decorativo = True
        m.atk = m.matk = 0
        m.agro = 0
        m.move_range = m.move_speed = 0
        m.es_estatico = True
        m.generado = True
        m.es_jefe = False
        return m
    if MODO == 'antigua' and int(stage) in TOTEM_CAMPO:
        # monster.xml: 21397 "Totem Lv 1" (300.000 HP) .. 21404 "Totem Lv 8"
        # (17.689.000 HP). El nivel lo suben las ofrendas.
        tipo = TOTEM_TIPO_CAMPO + max(1, min(NIVEL_MAX_TOTEM, nivel_totem(stage)[0])) - 1
        m = _totem_clase()(eid_totem(stage), tipo, nombre_totem(stage),
                           list(TOTEM_CAMPO[int(stage)]), sprite_totem(stage), stage=int(stage))
    else:
        m = _totem_clase()(eid_totem(stage), TOTEM_NPC, nombre_totem(stage),
                           TOTEM_TILE, TOTEM_SPRITE, stage=int(stage))
    m.atk = m.matk = 0
    m.agro = 0
    m.move_range = 0
    m.move_speed = 0
    m.es_estatico = True
    m.generado = True      # el respawn generico no lo toca: lo levanta relevantar()
    m.es_jefe = False
    return m


# EL TOTEM DEL CENTRO ES EL DE LA FACCION DUENA, no un cristal (lo vio el
# usuario en video del oficial). server.obd, SERV_CLASS_TOTEMOBJ:
#   60237 聖光圖騰 Aurora   60238 和風圖騰 Breeze/Beasts
#   60239 鐵輪圖騰 Steel    60240 永夜圖騰 Shadow (Dark City)
# Sin duena: 60151 "損壞的圖騰", el totem roto.
SPRITE_TOTEM_FACCION = {1: 60237, 2: 60238, 3: 60239, 4: 60240}
# Sin duena, uno de los cuatro (lo pidio el usuario: el 60151, el totem roto,
# no se ve como un totem).
SPRITE_TOTEM_NEUTRO = 60237
def sprite_totem(stage) -> int:
    return SPRITE_TOTEM_FACCION.get(faccion_duena(stage), SPRITE_TOTEM_NEUTRO)


# Cuerpo del 0x012E capturado en Celestia (mundo_130112_294532, el totem de
# Mysterious Garden). REA 0060b8b0: +0 id, +4 estado, +8/+12 CASILLA, +16
# nombre, +33 direccion, +34 sprite, +38 (8 sin liga duena, 0 con liga), +45
# tipo de monster.xml ("Totem Lv N"); el resto son vida/nivel que se copian.
_CUERPO_012E = bytes.fromhex(
    '4a420f0003000000ce0000006b0000004175726f726120546f74656d0000000000064deb'
    '000008000000000000955300000000000000000000000000000064000000640000000000'
    '000070170000')


def spawn_totem_campo(m) -> bytes:
    """s2c 0x012E: el totem de la guerra antigua, en su campo."""
    b = bytearray(_CUERPO_012E)
    struct.pack_into('<I', b, 0, int(m.entity_id))
    struct.pack_into('<II', b, 8, int(m.tile_x), int(m.tile_y))
    n = nombre_totem(m.stage).encode('latin-1', 'replace')[:16]
    b[16:33] = n.ljust(17, bytes(1))
    struct.pack_into('<H', b, 34, sprite_totem(m.stage))
    b[38] = 0 if liga_duena(m.stage) else 8
    struct.pack_into('<H', b, 45, int(getattr(m, 'npc_type', TOTEM_TIPO_CAMPO)))
    # El cartel es la ventana 0x2fda (REA 0064ab90):
    #   +40 nivel (+0x24c); el cartel pinta nivel + 1, por eso va nivel - 1.
    #   barra roja 0x2fdd: vida +63 de un maximo +67 (en %, como el 0x0013).
    #   barra azul 0x2fde: puntos +71 de los +75 que pide el siguiente nivel.
    # El cliente lee hasta el +79; a la plantilla capturada le faltaba un
    # byte, la vida quedaba con maximo 0 (sin barra roja) y la azul llena
    # (21/10/2026).
    if len(b) < 79:
        b.extend(bytes(79 - len(b)))
    nivel, puntos = nivel_totem(m.stage)
    struct.pack_into('<I', b, 40, max(0, int(nivel) - 1))
    vida = int(getattr(m, 'porcentaje', 100) or 0)
    struct.pack_into('<IIII', b, 63, max(0, min(100, vida)), 100,
                     int(puntos), puntos_para_subir(nivel))
    return struct.pack('<H', 0x012E) + bytes(b)


# La ventana del totem (s2c 0x012F, REA 0060c6c0). Solo la abre el cliente si
# la faccion del paquete (+4) es la suya. +8 liga[17], +25/+29 Fortification
# actual/maxima, +33 nivel-1 ("1/08"), +37 "Upgrade need", +41 0 = crearla.
NIVEL_MAX_TOTEM = 8
PUNTOS_POR_NIVEL = 100


def ventana_totem(m, crear=True) -> bytes:
    st = int(m.stage)
    b = bytearray(65)
    struct.pack_into('<II', b, 0, int(m.entity_id), faccion_duena(st))
    gid = liga_duena(st)
    g = cuentas.db_obtener_gremio(gid) if gid else None
    liga = str(g['nombre'] if g else '').encode('latin-1', 'replace')[:16]
    b[8:8 + len(liga)] = liga
    nivel, puntos = nivel_totem(st)
    # Fortification: aun sin datos de que la sube; se deja como en Celestia.
    struct.pack_into('<II', b, 25, 0, 100)
    struct.pack_into('<II', b, 33, nivel - 1,
                     puntos_para_subir(nivel) - puntos if nivel < NIVEL_MAX_TOTEM else 0)
    b[41] = 0 if crear else 1
    return struct.pack('<H', 0x012F) + bytes(b)


def _tabla_nivel():
    con = cuentas._get_conn()
    try:
        con.execute('CREATE TABLE IF NOT EXISTS tw_totem_nivel ('
                    'tw_stage INTEGER PRIMARY KEY, nivel INTEGER NOT NULL DEFAULT 1, '
                    'puntos INTEGER NOT NULL DEFAULT 0)')
        con.commit()
    finally:
        con.close()


def nivel_totem(stage):
    """(nivel 1..8, puntos hacia el siguiente)."""
    with cuentas._LOCK:
        _tabla_nivel()
        con = cuentas._get_conn()
        try:
            r = con.execute('SELECT nivel, puntos FROM tw_totem_nivel WHERE tw_stage=?',
                            (_tw(stage),)).fetchone()
        finally:
            con.close()
    return (int(r[0]), int(r[1])) if r else (1, 0)


def puntos_para_subir(nivel) -> int:
    """'Upgrade need'. En Celestia el nivel 1 pedia 100; de los demas no hay
    dato, asi que crece lineal: 100 x nivel."""
    return PUNTOS_POR_NIVEL * max(1, int(nivel))


_OFRENDAS = None


def puntos_de_ofrenda(item_id) -> int:
    """Puntos de totem por cada 200 unidades (plantillas/ofrendas_totem.json)."""
    global _OFRENDAS
    if _OFRENDAS is None:
        import json as _js
        import pathlib as _pl
        try:
            _OFRENDAS = {int(k): int(v) for k, v in _js.loads(
                (_pl.Path(__file__).parent / 'plantillas' / 'ofrendas_totem.json')
                .read_text(encoding='utf-8'))['puntos'].items()}
        except Exception:
            log.exception('ofrendas_totem.json')
            _OFRENDAS = {}
    return _OFRENDAS.get(int(item_id), 0)


UNIDAD_OFRENDA = 200


def reiniciar_nivel(stage):
    """El totem que cae vuelve a nivel 1 (y a la vida de un Totem Lv 1)."""
    with cuentas._LOCK:
        _tabla_nivel()
        con = cuentas._get_conn()
        try:
            con.execute('INSERT OR REPLACE INTO tw_totem_nivel (tw_stage, nivel, puntos) '
                        'VALUES (?,1,0)', (_tw(stage),))
            con.commit()
        finally:
            con.close()


def sumar_puntos_totem(stage, puntos):
    """Suma ofrendas y sube de nivel cuando toca. Devuelve (nivel, puntos)."""
    nivel, actual = nivel_totem(stage)
    actual += max(0, int(puntos))
    while actual >= puntos_para_subir(nivel) and nivel < NIVEL_MAX_TOTEM:
        actual -= puntos_para_subir(nivel)
        nivel += 1
    if nivel >= NIVEL_MAX_TOTEM:
        actual = 0
    with cuentas._LOCK:
        _tabla_nivel()
        con = cuentas._get_conn()
        try:
            con.execute('INSERT OR REPLACE INTO tw_totem_nivel (tw_stage, nivel, puntos) '
                        'VALUES (?,?,?)', (_tw(stage), nivel, actual))
            con.commit()
        finally:
            con.close()
    return nivel, actual


def spawn_totem(m, nivel=1) -> bytes:
    if (MODO == 'antigua' and int(m.stage) in TOTEM_CAMPO) or es_totem_decorativo(m.stage):
        return spawn_totem_campo(m)
    """s2c 0x0140: el totem de la arena (REA 005ef5f0).

    Como objeto 0x000E no salia: los totems de guerra son SERV_CLASS_TOTEMOBJ
    y el cliente solo los crea por su paquete propio, que comprueba la clase
    (0x80000804) y lee, ademas de la cabecera del 0x0008/0x000E:
      +16 nombre[16]   +34 sprite (u32)   +43 faccion
      +44 nombre de la LIGA duena[16] (lo compara con la del jugador)
      +62 nivel 1..6 del totem -> animacion Wait1..Wait6
    """
    st = int(m.stage)
    b = bytearray(64)
    struct.pack_into('<IIII', b, 0, int(m.entity_id), 0,
                     int(m.tile_x) * 32 + 16, int(m.tile_y) * 32 + 16)
    n = str(getattr(m, 'nombre', '') or nombre_totem(st)).encode('latin-1', 'replace')[:16]
    b[16:16 + len(n)] = n
    struct.pack_into('<I', b, 34, sprite_totem(st))
    b[43] = faccion_duena(st) & 0xFF
    gid = liga_duena(st)
    g = cuentas.db_obtener_gremio(gid) if gid else None
    liga = str(g['nombre'] if g else '').encode('latin-1', 'replace')[:16]
    b[44:44 + len(liga)] = liga
    b[62] = max(1, min(6, int(nivel or 1)))
    return struct.pack('<H', 0x0140) + bytes(b)


# ------------------------------------------------------------------ mapas

def tile_de_llegada(stage_tw, personaje):
    import eventos as _ev
    d = _ev.del_stage(int(stage_tw)) or {}
    tags = d.get('tags') or {}
    tag = TAG_DE_FACCION.get(codigo_faccion(personaje), TAG_MILICIA)
    pts = tags.get(str(tag)) or tags.get(str(TAG_MILICIA))
    return tuple(pts[0]) if pts else TOTEM_TILE


def redirigir(ses, stage, x, y):
    """(stage, x, y) a donde va de verdad quien pide ir a `stage`.

    Entrar en guerra requiere el Terra Keeper. Fuera de guerra se vuelve
    al campo; una liga con territorio no puede disputar otro campo."""
    p = ses.personaje
    stage = int(stage)
    if MODO == 'antigua':
        # Sin arenas: si algo pide ir a una, va a su campo.
        if stage in TW_A_CAMPO:
            import login as _lg
            campo = TW_A_CAMPO[stage]
            t = junto_al_terra_keeper(campo) or _lg.spawn_de(campo) or (x, y)
            return campo, t[0], t[1]
        return stage, x, y
    # Entrar en un campo normal nunca inscribe ni teletransporta a la guerra.
    # La entrada explicita se tramita mediante el dialogo del Terra Keeper.
    # Durante la guerra entra cualquiera: se pelea por la faccion. Antes una
    # liga que ya tenia otro campo era devuelta al campo normal al elegir la
    # arena en el Terra Keeper (log del 19/10: "stage 207 -> 21"). Que no
    # pueda quedarse DOS territorios lo controla capturado().
    if stage not in TW_A_CAMPO:
        return stage, x, y
    actual = int(getattr(p, 'stage', 0) or 0)
    duena = bool(faccion_duena(stage)) and codigo_faccion(p) == faccion_duena(stage)
    # Fuera de guerra entra la faccion duena (la defensa del totem: el Terra
    # Keeper la manda al TAG 5, el Militia Portal); en guerra, todos.
    if activa() or duena:
        if actual not in TW_A_CAMPO:
            ses.tw_origen = (actual, int(getattr(p, 'tile_x', 0)), int(getattr(p, 'tile_y', 0)))
        return stage, x, y
    # No puede entrar: vuelve a donde estaba (antes caia en el campo con las
    # coordenadas de la ARENA, "en cualquier lado").
    origen = getattr(ses, 'tw_origen', None)
    if origen and origen[0] == TW_A_CAMPO[stage]:
        return origen
    campo = TW_A_CAMPO[stage]
    if actual == campo:
        return campo, int(p.tile_x), int(p.tile_y)
    import login as _lg
    t = _lg.spawn_de(campo) or (x, y)
    return campo, t[0], t[1]


def stage_para_guardar(stage, x, y, ses):
    """Lo que se guarda en la base: nunca la arena (al reconectar sin guerra
    el mapa estaria vacio). Se guarda el campo de donde vino."""
    if int(stage) in TW_A_CAMPO:
        o = getattr(ses, 'tw_origen', None)
        if o and o[0] == TW_A_CAMPO[int(stage)]:
            return o
    return stage, x, y


# ------------------------------------------------------------------ avisos

def cartel_deslizante(texto, nombre='') -> bytes:
    """El aviso que cruza la parte de ARRIBA de la pantalla: 0x0128 canal 0.

    Leido en el cliente con REA (manejador 005f3b40 del 0x0128):

        +0 u32 entidad   +4 u8 canal   +5 nombre[17]   +22 texto ASCIIZ

    Los canales 0, 1 y 12 van a 006337c0, que crea el texto que se desplaza
    por arriba y lo copia al chat. Es el mismo diseno que chat_publico().
    Antes el texto iba en +46 (con un largo en +5): el cliente leia en +22
    una cadena vacia y no salia nada, ni al empezar la Totem War ni al acabar.
    """
    t = str(texto).encode('latin-1', 'replace')[:900]
    n = str(nombre or '').encode('latin-1', 'replace')[:16].ljust(17, b'\x00')
    return struct.pack('<HIB17s', 0x0128, 0, 0, n) + t + b'\x00'


# Los avisos del propio cliente (update26/setting/eng/string.xml). Llegan como
# 0x000D con el numero de cadena, igual que los de mejora (mejoras.py).
STR_EMPIEZA = 1783      # "The totem battle begins. All angels please be ready for the battle."
STR_TERMINA = 1784      # "The totem battle is over."
STR_ARENA = 1751        # "You are in the Totem Battlefield (PVP Area)..."
STR_ZONA_PVP = 2690     # "You have entered the PVP area. Take care!..."


def modo_pvp(entity_id, activo, mensaje=0) -> bytes:
    """s2c 0x001D codigo 22: el modo PvP del cliente (REA 005ff200).

    Pone la bandera de guerra (DAT_00a38118), enciende o apaga el modo PvP del
    personaje (0074a5b0 / 0074a5d0), escribe `mensaje` de string.xml en el chat
    y cambia a la musica de guerra (26.ogg en campo propio, 27.ogg en ajeno).
    El 0x001D es [u32 entidad][u8 n] y n x [u8 codigo][u32 a][u32 b]; el
    codigo 22 es (0x4568 - 0x4408) / 16 de la tabla de 005fbdd0.
    """
    return struct.pack('<HIBBII', 0x001D, int(entity_id), 1, 22,
                       1 if activo else 0, int(mensaje or 0))


def aviso_cliente(numero):
    import clases as _cl
    return _cl.aviso('', tipo=0, msg_id=int(numero))


def anuncio(texto, numero=None):
    pkts = (cartel_deslizante(texto),)
    return ((aviso_cliente(numero),) + pkts) if numero else pkts


# ------------------------------------------------------------------ control

_APP = [None]


def _app():
    if _APP[0] is None:
        import app as _a
        _APP[0] = _a
    return _APP[0]


def iniciar(minutos=MINUTOS_GM, por='gm'):
    """Empieza la guerra, o si ya esta, vuelve a poner el reloj en `minutos`."""
    ya = activa()
    _ESTADO['fin'] = time.time() + int(minutos) * 60
    _ESTADO['por'] = por
    a = _app()
    if ya:
        a._tw_difundir(*anuncio('Totem War timer reset: %d minutes left!' % int(minutos)))
    else:
        _DISPUTADAS.clear()
        _RONDA.clear()
        a._tw_difundir(*anuncio('Totem War has begun! Enter any battlefield to fight for '
                                'your faction (%d min).' % int(minutos), STR_EMPIEZA))
        a._tw_levantar_todos()
    log.info('Totem War %s por %s: %d min', 'reiniciada' if ya else 'iniciada', por, minutos)
    return ya


def terminar(por='gm'):
    if not activa() and _ESTADO['fin'] == 0:
        return False
    # Consolidar todos los cambios en una transaccion: una liga puede haber
    # perdido su campo y tomado uno nuevo dentro de esta misma guerra.
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            for st in _DISPUTADAS:
                con.execute('DELETE FROM gremio_territorios WHERE tw_stage=?', (st,))
            for st, gid in _DISPUTADAS.items():
                if gid:
                    con.execute('INSERT INTO gremio_territorios (tw_stage,guild_id) VALUES (?,?)', (st, gid))
            con.commit()
        finally:
            con.close()
    _DISPUTADAS.clear()
    _ESTADO['fin'] = 0.0
    partes = [_dueno_corto(st) for st in sorted(TW_A_CAMPO)]
    a = _app()
    a._tw_difundir(*anuncio('Totem War is over! ' + ' | '.join(partes), STR_TERMINA))
    a._tw_difundir(paquete_territorios())
    a._tw_sacar_de_las_arenas()
    log.info('Totem War terminada por %s', por)
    return True


def capturado(ses, m):
    """El totem de la arena cayo a manos de `ses`: su faccion (y su liga) se
    quedan el mapa. Devuelve el texto del anuncio."""
    p = ses.personaje
    st = _tw(m.stage)
    if not activa() or st not in TW_A_CAMPO:
        return None
    f = codigo_faccion(p)
    reiniciar_nivel(st)
    try:
        import gremios as _grm_n
        sin_liga = not _grm_n.obtener_gremio_de(p.char_id)
    except Exception:
        sin_liga = False
    if sin_liga:
        # Quien no tiene liga lo rompe pero no se lo queda nadie: vuelve a
        # neutro y cualquier faccion puede pegarle (lo pidio el usuario).
        poner_faccion_duena(st, 0)
        _DISPUTADAS[st] = None     # al terminar, el campo se queda sin liga
        return '%s destroyed the totem of %s! It is neutral again.' % (p.nombre, NOMBRE_TW[st])
    poner_faccion_duena(st, f)
    liga = ''
    try:
        import gremios as _grm
        g = _grm.obtener_gremio_de(p.char_id)
        if g and puede_disputar(ses, st):
            _DISPUTADAS[st] = int(g['guild_id'])
            liga = ' for the league %s' % g['nombre']
    except Exception:
        log.exception('territorio de la liga')
    # Los textos del cliente (string.xml): 1785 "%s has been occupied by
    # league %s and becomes %s's territory." y 1786 si no hay liga.
    if st in _DISPUTADAS and liga:
        nombre_liga = liga.replace(' for the league ', '')
        return "%s has been occupied by league %s and becomes %s's territory." % (
            NOMBRE_TW[st], nombre_liga, nombre_liga)
    return "%s has been occupied and becomes %s's territory." % (
        NOMBRE_TW[st], NOMBRE_FACCION.get(f, '?'))


def _toca_por_horario(ahora):
    for dia, h, mi in HORARIO:
        ini = ahora.replace(hour=h, minute=mi, second=0, microsecond=0)
        if ahora.weekday() == dia and ini <= ahora < ini + datetime.timedelta(minutes=DURACION_HORARIO):
            return ini
    return None


async def reloj():
    """Arranca y para la guerra segun el horario, y la cierra al vencer."""
    while True:
        try:
            ahora = datetime.datetime.now()
            ini = _toca_por_horario(ahora)
            if ini is not None and _ESTADO['arranque_horario'] != ini and not activa():
                _ESTADO['arranque_horario'] = ini
                fin = ini + datetime.timedelta(minutes=DURACION_HORARIO)
                iniciar(max(1, int((fin - ahora).total_seconds() // 60)), por='horario')
            if _ESTADO['fin'] and not activa():
                terminar(por='reloj')
        except Exception:
            log.exception('reloj de la Totem War')
        await asyncio.sleep(15)
