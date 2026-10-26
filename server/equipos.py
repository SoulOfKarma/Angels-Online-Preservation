"""Equipos (party): invitar, aceptar, salir.

TODO ESTO SALE DE UNA CAPTURA DEL GLOBAL con tres cuentas montando un equipo
de verdad -- Yuki, KarmaSilk y KarmaWeapon -- grabada con el proxy delante.
Son los tres ficheros mundo_141825, mundo_141841 y mundo_144108. Sin esa
captura no habria habido forma: de las 1.230 sesiones anteriores del
proyecto, ninguna tiene un solo paquete de grupo, porque quien capturaba iba
siempre solo.

EL FLUJO, leido de la captura paquete a paquete:

    1. el lider manda   c2s 0x0017  con el NOMBRE del invitado
    2. al invitado le llega  s2c 0x0023  con el id y el nombre del lider
       -> ese es el cartel de "X te invita"
    3. el invitado contesta  c2s 0x0018  con [01][u32 0]
    4. a TODOS los del grupo les llega  s2c 0x0024  con la lista entera

C2S 0x0017, 34 bytes: el nombre del invitado en ASCIIZ al principio. Lo que
viene detras es BASURA DE PILA del cliente -- en las tres invitaciones
capturadas sale distinto y hasta con restos legibles como "t\\0 3\\0 2\\0
_\\0 1\\0 . \\0 D L L" -- asi que no se lee nada mas que el nombre.

C2S 0x0018, 5 bytes: [u8 accion][u32]. Medido el 1 = aceptar, que es lo que
mandaron los dos invitados. El lider mando un 4 en mitad de la sesion. Las
nativas del cliente dicen que por este mismo opcode van groupdeny,
groupdisband, groupjoin, groupkick, groupleave y grouppromote, o sea seis
acciones; solo el 1 esta confirmado y el resto se tratan como "salir", que
es lo seguro: deshacer el grupo nunca deja a nadie colgado.

S2C 0x0024, la lista: cabecera de 10 bytes y 98 por miembro.

    cabecera  +0  u32 ???          (0x400011ac en una sesion, 0x400011d3 en otra)
              +4  u8  0
              +5  u32 char_id del lider
              +9  u8  cuantos miembros
    miembro   +0  u32 char_id
              +4  u16 ???
              +6  u16 ???
              +8  nombre ASCIIZ
              +41 u16 nivel
              +51 u8  100   (un porcentaje, siempre 100 en la captura)

Las cuentas cuadran: 10 + 98 = 108, 10 + 2*98 = 206 y 10 + 3*98 = 304, que
son exactamente los tres tamanos que se vieron segun el grupo tenia uno, dos
o tres miembros.

S2C 0x0023, 38 bytes: u32 char_id del lider, nombre ASCIIZ y relleno.

NO CONFUNDIR CON LA GUILD. En la misma captura salen dos paquetes mas con
nombres dentro y no son del grupo: el 0x0055 (257 B) lleva "Moonlights",
que es el nombre de la GUILD, y el 0x0054 (232 B) su cartel -- "Se Acepta
de Todo / Mancos, Los del Genshin, Pinwinos..." --. Los tres personajes del
equipo son Yuki, KarmaSilk y KarmaWeapon, y son exactamente los tres que
aparecen en el 0x0024 de 304 bytes.
"""
import logging
import struct

log = logging.getLogger('equipos')

INVITAR = 0x0017          # c2s, lo manda el lider con el nombre
ACCION = 0x0018           # c2s, [u8 accion][u32]
CARTEL = 0x0023           # s2c, "X te invita"
LISTA = 0x0024            # s2c, la lista del grupo

ACEPTAR = 1               # medido
TAM_MIEMBRO = 78
CABECERA = 10

# char_id del lider -> [sesiones], en orden de entrada (el lider primero).
_GRUPOS = {}
# char_id -> char_id del lider de su grupo
_DE_QUIEN = {}
# char_id del invitado -> char_id del que le invito, mientras no conteste
_PENDIENTES = {}
_MODOS = {}  # leader -> 0 Share, 1 Alone (native C2S 0x0017 last byte)


def modo_de(ses):
    return _MODOS.get(lider_de(ses),0)


def _char_id(ses) -> int:
    p = getattr(ses, 'personaje', None)
    return int(getattr(p, 'char_id', 0) or 0) if p else 0


def _nombre(ses) -> str:
    p = getattr(ses, 'personaje', None)
    return (getattr(p, 'nombre', '') or '') if p else ''


def grupo_de(ses):
    """Las sesiones del grupo de ese jugador, o [] si va solo."""
    lider = _DE_QUIEN.get(_char_id(ses))
    return list(_GRUPOS.get(lider) or []) if lider else []


def cuantos(ses) -> int:
    """Numero de miembros en el grupo de ses, o 1 si va solo."""
    g = grupo_de(ses)
    return len(g) if g else 1


def lider_de(ses) -> int:
    """char_id del lider del grupo de ses, o 0 si no esta en un grupo."""
    return _DE_QUIEN.get(_char_id(ses), 0)


def cartel_de_invitacion(ses_lider) -> bytes:
    """El s2c 0x0023 que le saca el cuadro al invitado (38 bytes cuerpo, 40 bytes con opcode)."""
    b = bytearray(38)
    struct.pack_into('<I', b, 0, _char_id(ses_lider))
    n = _nombre(ses_lider).encode('ascii', 'replace')[:16]
    b[4:4 + len(n)] = n
    # REA602D80 reads packet+23 (body+21) for the invitation's mode.
    b[21] = modo_de(ses_lider)
    return struct.pack('<H', CARTEL) + bytes(b)


def _entidad_vista(s, para):
    """Con que entidad ve `para` al miembro `s` en su mapa, o 0 si no lo ve.

    Es el u32 del +4 de cada miembro. Leido con REA en el cliente (la lista
    la guarda 00506fc0, en bloques de 78 bytes) y visto en la captura del
    Global (detras del id de cada miembro va su entidad, aa00e507): con ella
    el cliente une el retrato con el personaje del mapa. Iba siempre a 0, y
    por eso el retrato del companero salia apagado -- como si estuviera en
    otro mapa -- y sin buffs ni vida al pasar el raton.
    """
    if s is para:
        p = getattr(s, 'personaje', None)
        return int(getattr(p, 'entity_id', 0) or 0) if p else 0
    try:
        import presencia as _pr
        if (para is not None and getattr(s, '_mapa_presencia', None) is not None
                and getattr(s, '_mapa_presencia', None) == getattr(para, '_mapa_presencia', None)):
            return _pr.entidad_de(s)
    except Exception:
        pass
    return 0


def _vida_pct(s):
    p = getattr(s, 'personaje', None)
    if p is None:
        return 0
    try:
        import app as _app
        tope = _app._vida_max(p)
    except Exception:
        tope = getattr(p, 'hp_max', 100)
    tope = max(1, int(tope or 1), int(getattr(p, 'hp', 0) or 0))
    return max(0, min(100, int(round((getattr(p, 'hp', 0) or 0) * 100.0 / tope))))


def _mp_pct(s):
    p = getattr(s, 'personaje', None)
    if p is None:
        return 0
    try:
        import app as _app
        tope = _app._mana_max(p, getattr(s, 'inventario', None))
    except Exception:
        tope = getattr(p, 'mp_max', 100)
    tope = max(1, int(tope or 1), int(getattr(p, 'mp', 0) or 0))
    return max(0, min(100, int(round((getattr(p, 'mp', 0) or 0) * 100.0 / tope))))


def serializar_miembro(s, para=None) -> bytes:
    """Bloque de 78 bytes con los datos de un miembro para 0x0024 y 0x0026.

    Estructura exacta verificada en Angel.exe (0x506fc0, 0x603ba0, 0x58bc00):
      +0   u32 char_id
      +4   u32 entity_id (vista por 'para', 0 si esta en otro mapa)
      +8   16 B nombre (ASCIIZ nulo-rellenado)
      +24  u8 nivel
      +25  u32 stage (el id de mapa donde esta el miembro)
      +29  u16 tile_x
      +31  u16 tile_y
      +33  u16 hp_pct (0..100)
      +35  u16 mp_pct (0..100)
      +37  10 * u16 buffs (20 bytes)
      +57  10 * u16 debuffs (20 bytes)
      +77  u8 genero (0=masculino, 1=femenino)
    """
    p = getattr(s, 'personaje', None)
    b = bytearray(TAM_MIEMBRO)
    struct.pack_into('<I', b, 0, _char_id(s))
    struct.pack_into('<I', b, 4, _entidad_vista(s, para))
    n = _nombre(s).encode('ascii', 'replace')[:16]
    b[8:8 + len(n)] = n
    if p is not None:
        b[24] = max(1, min(255, int(getattr(p, 'nivel', 1) or 1)))
        struct.pack_into('<I', b, 25, int(getattr(p, 'stage', 0) or 0))
        struct.pack_into('<H', b, 29, max(0, int(getattr(p, 'tile_x', 0) or 0)))
        struct.pack_into('<H', b, 31, max(0, int(getattr(p, 'tile_y', 0) or 0)))
        struct.pack_into('<H', b, 33, _vida_pct(s))
        struct.pack_into('<H', b, 35, _mp_pct(s))
        buffs = getattr(p, 'buffs', {}) or {}
        if isinstance(buffs, dict):
            b_ids = [int(bid) for bid in buffs.keys() if str(bid).isdigit()][:10]
            for idx, bid in enumerate(b_ids):
                struct.pack_into('<H', b, 37 + idx * 2, bid & 0xFFFF)
        b[77] = int(getattr(p, 'genero', 0) or 0) & 1
    return bytes(b)


ACTUALIZACION = 0x0026  # s2c 0x0026 (80 bytes con opcode)


def paquete_actualizacion_miembro(s, para=None) -> bytes:
    """El s2c 0x0026 (80 B con opcode) que actualiza vida, mana y posicion de un miembro."""
    return struct.pack('<H', ACTUALIZACION) + serializar_miembro(s, para)


def notificar_stats(ses):
    """Envia 0x0026 a todos los companeros del grupo cuando cambian HP, MP o posicion."""
    lider = _DE_QUIEN.get(_char_id(ses))
    if not lider:
        return
    miembros = _GRUPOS.get(lider) or []
    if len(miembros) <= 1:
        return
    for otro in miembros:
        if otro is not ses:
            try:
                otro.enviar(paquete_actualizacion_miembro(ses, para=otro))
                if hasattr(otro, 'volcar'):
                    otro.volcar()
            except Exception:
                pass


def lista_del_grupo(lider_id, para=None) -> bytes:
    """El s2c 0x0024 con los miembros, tal como lo arma el servidor real."""
    miembros = _GRUPOS.get(lider_id) or []
    cab = bytearray(CABECERA)
    struct.pack_into('<I', cab, 0, 0x0000006A)
    # REA506FC0 copies body+4 into GROUP_DROPITEM_TYPE.
    cab[4] = _MODOS.get(lider_id,0)
    struct.pack_into('<I', cab, 5, int(lider_id))
    cab[9] = len(miembros) & 0xFF
    partes = [cab]
    for s in miembros:
        partes.append(serializar_miembro(s, para))
    return struct.pack('<H', LISTA) + b''.join(partes)


def _avisar(lider_id):
    """Le manda la lista nueva a todos los del grupo, a cada uno la suya."""
    for s in list(_GRUPOS.get(lider_id) or []):
        try:
            s.enviar(lista_del_grupo(lider_id, para=s))
            if hasattr(s, 'volcar'):
                s.volcar()
        except Exception:
            log.debug('no se pudo mandar la lista', exc_info=True)


def al_cambiar_de_mapa(ses):
    """Al entrar en un mapa, la lista otra vez: cambia quien ve a quien
    (los del mismo mapa se encienden, los demas se apagan)."""
    lider = _DE_QUIEN.get(_char_id(ses))
    if lider and lider in _GRUPOS:
        _avisar(lider)


def invitar(ses, nombre_invitado, buscar_sesion, modo=0):
    """El lider invita por nombre. `buscar_sesion` resuelve nombre -> sesion."""
    nombre_invitado = (nombre_invitado or '').strip()
    if not nombre_invitado or nombre_invitado == _nombre(ses):
        return False, 'no hay a quien invitar'
    otro = buscar_sesion(nombre_invitado)
    if otro is None:
        return False, 'no esta conectado'
    if _DE_QUIEN.get(_char_id(otro)):
        return False, 'ya esta en un grupo'
    # El que invita arma el grupo si todavia no lo tiene.
    mio = _DE_QUIEN.get(_char_id(ses))
    if mio and mio!=_char_id(ses):
        return False, 'solo el lider puede invitar'
    if not mio:
        mio = _char_id(ses)
        _GRUPOS[mio] = [ses]
        _DE_QUIEN[mio] = mio
        _MODOS[mio] = 1 if modo==1 else 0
    if len(_GRUPOS.get(mio, [])) >= 5:
        return False, 'el grupo ya esta lleno (maximo 5)'
    # A rejected invitation leaves a one-person group. Retrying with Alone
    # must use the new selection instead of retaining that group's Share.
    if len(_GRUPOS.get(mio, [])) == 1:
        _MODOS[mio] = 1 if modo == 1 else 0
    _PENDIENTES[_char_id(otro)] = mio
    try:
        otro.enviar(cartel_de_invitacion(ses))
    except Exception:
        _PENDIENTES.pop(_char_id(otro),None)
        log.debug('no se pudo mandar el cartel', exc_info=True)
        return False, 'no se pudo avisar'
    log.info('%s invita a %s', _nombre(ses), nombre_invitado)
    return True, ''


def aceptar(ses):
    """El invitado dice que si."""
    yo = _char_id(ses)
    lider = _PENDIENTES.pop(yo, None)
    if not lider or lider not in _GRUPOS:
        return False
    if _DE_QUIEN.get(yo) or len(_GRUPOS[lider])>=5:
        return False
    _GRUPOS[lider].append(ses)
    _DE_QUIEN[yo] = lider
    _avisar(lider)
    log.info('%s entra al grupo de %s', _nombre(ses), lider)
    return True


EVENTO = 0x0025           # s2c, un miembro entra o se va
SE_VA = 4
ID_GRUPO = 0x6A           # el mismo que va en la cabecera de lista_del_grupo


def aviso_de_salida(s) -> bytes:
    """s2c 0x0025 tipo 4: "este miembro deja el grupo".

    Medido en las capturas del IGG (mundo_172633 y mundo_172821): tras el
    c2s 0x0018 04 (Leave Team) el servidor real manda 26 bytes,
        04 | u32 id del grupo | u32 id del miembro | nombre (17)
    p. ej. 04 70000000 1e010000 "KarmaV1". Antes se mandaba la lista vacia
    (0x0024 sin miembros) y el cliente no lo tomaba como una salida: seguia
    viendose en el grupo y no podia volver a dejarlo.
    """
    n = _nombre(s).encode('ascii', 'replace')[:16]
    return (struct.pack('<HBII', EVENTO, SE_VA, ID_GRUPO, _char_id(s))
            + n + bytes(17 - len(n)))


def _mandar_a(sesiones, *paquetes):
    for s in sesiones:
        try:
            s.enviar(*paquetes)
            if hasattr(s, 'volcar'):
                s.volcar()
        except Exception:
            log.debug('no se pudo avisar al grupo', exc_info=True)


def salir(ses):
    """El jugador deja el grupo, o se desconecta.

    Si se va el lider, o queda uno solo, el grupo se deshace: a cada uno le
    llega la salida de todos los demas y la suya.
    """
    yo = _char_id(ses)
    _PENDIENTES.pop(yo, None)
    lider = _DE_QUIEN.pop(yo, None)
    if not lider:
        return False
    miembros = _GRUPOS.get(lider) or []
    if ses in miembros:
        miembros.remove(ses)
    salida_mia = aviso_de_salida(ses)
    if yo == lider or len(miembros) <= 1:
        for s in list(miembros):
            _DE_QUIEN.pop(_char_id(s), None)
        _GRUPOS.pop(lider, None)
        _MODOS.pop(lider,None)
        for invited,owner in list(_PENDIENTES.items()):
            if owner==lider:_PENDIENTES.pop(invited,None)
        todos = miembros + [ses]
        avisos = [aviso_de_salida(s) for s in todos]
        _mandar_a(todos, *avisos)
        log.info('el grupo de %s se deshace', lider)
    else:
        _GRUPOS[lider] = miembros
        _mandar_a(miembros + [ses], salida_mia)
        _avisar(lider)
        log.info('%s deja el grupo de %s', _nombre(ses), lider)
    return True


def _miembro(lider, objetivo):
    """La sesion del grupo con ese id: el char_id (el de la lista) o el id
    publico con el que se le ve (presencia.entidad_de)."""
    try:
        import presencia as _pr
    except Exception:
        _pr = None
    for s in _GRUPOS.get(lider) or []:
        if _char_id(s) == objetivo or (_pr and _pr.entidad_de(s) == objetivo):
            return s
    return None


def expulsar(ses, objetivo):
    """El lider echa a un miembro (0x0018 02 + id)."""
    lider = _DE_QUIEN.get(_char_id(ses))
    if lider != _char_id(ses):
        return False
    otro = _miembro(lider, objetivo)
    if otro is None or otro is ses:
        return False
    return salir(otro)


def ascender(ses, objetivo):
    """El lider le pasa el mando a otro miembro (0x0018 03 + id)."""
    lider = _DE_QUIEN.get(_char_id(ses))
    if lider != _char_id(ses):
        return False
    otro = _miembro(lider, objetivo)
    if otro is None or otro is ses:
        return False
    miembros = _GRUPOS.pop(lider, [])
    nuevo = _char_id(otro)
    miembros = [otro] + [s for s in miembros if s is not otro]
    _GRUPOS[nuevo] = miembros
    _MODOS[nuevo] = _MODOS.pop(lider,0)
    for invited,owner in list(_PENDIENTES.items()):
        if owner==lider:_PENDIENTES[invited]=nuevo
    for s in miembros:
        _DE_QUIEN[_char_id(s)] = nuevo
    _avisar(nuevo)
    log.info('%s pasa el mando del grupo a %s', _nombre(ses), _nombre(otro))
    return True


EXPULSAR = 2
ASCENDER = 3
DEJAR = 4
DESHACER = 5
RECHAZAR = 7


def rechazar(ses):
    """El invitado rechaza la invitacion (c2s 0x0018 07, groupdeny)."""
    yo = _char_id(ses)
    lider = _PENDIENTES.pop(yo, None)
    if lider:
        log.info('%s rechaza la invitacion al grupo de %s', _nombre(ses), lider)
        return True
    return False


def deshacer(ses):
    """El lider deshace el grupo entero (c2s 0x0018 05, groupdisband)."""
    yo = _char_id(ses)
    lider = _DE_QUIEN.get(yo)
    if lider == yo:
        return salir(ses)
    return False


def accion(ses, codigo, cuerpo=b''):
    """El c2s 0x0018: [u8 accion][u32 id del miembro, si va a alguien].

    Mapeo de acciones segun nativas de Angel.exe (0x6152b0):
      01: groupjoin / aceptar
      02: groupkick / expulsar (con target_id)
      03: grouppromote / ascender lider (con target_id)
      04: groupleave / salir
      05: groupdisband / deshacer grupo
      07: groupdeny / rechazar invitacion
    """
    objetivo = struct.unpack_from('<I', cuerpo, 1)[0] if len(cuerpo) >= 5 else 0
    if codigo == ACEPTAR:
        return 'aceptar' if aceptar(ses) else 'nada'
    if codigo == EXPULSAR:
        return 'expulsar' if expulsar(ses, objetivo) else 'nada'
    if codigo == ASCENDER:
        return 'ascender' if ascender(ses, objetivo) else 'nada'
    if codigo == DESHACER:
        return 'deshacer' if deshacer(ses) else 'nada'
    if codigo == RECHAZAR:
        return 'rechazar' if rechazar(ses) else 'nada'
    if codigo == DEJAR:
        return 'salir' if salir(ses) else 'nada'
    return 'nada'


def olvidar_todo():
    _GRUPOS.clear()
    _DE_QUIEN.clear()
    _PENDIENTES.clear()
    _MODOS.clear()
