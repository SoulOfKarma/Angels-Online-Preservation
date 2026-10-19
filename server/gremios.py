"""Sistema de Gremios / Ligas (Guilds).

Implementacion del protocolo de Angels Online para Ligas:
  - C2S 0x0041: Creacion de gremio (nombre, logo).
  - C2S 0x0042: Invitacion a gremio (nombre del jugador objetivo).
  - C2S 0x0043: Comandos de gremio (unirse, expulsar, salir, ascender, degradar,
                ceder mando, disolver, permisos, nombres de rangos, cartel, logo).
  - S2C 0x0054: Cartel / Boletin de gremio.
  - S2C 0x0055: Ficha principal de gremio (257 bytes).
  - S2C 0x0056: Lista de miembros (roster) con estado conectado/desconectado.
  - S2C 0x0057: Cuadro de invitacion a gremio ("%s invites you to join the league %s.").

Persistencia completa en SQLite a traves de server/cuentas.py.
"""
import logging
import functools
import struct
import time
import pathlib
import re
import xml.etree.ElementTree as ET
import clases
import cuentas

log = logging.getLogger('gremios')

# Opcodes
C2S_CREAR_GREMIO = 0x0041
C2S_INVITAR_GREMIO = 0x0042
C2S_COMANDO_GREMIO = 0x0043
C2S_CONTRIBUIR_GREMIO = 0x004B

S2C_CARTEL_GREMIO = 0x0054
S2C_DATOS_GREMIO = 0x0055
S2C_MIEMBROS_GREMIO = 0x0056
S2C_INVITACION_GREMIO = 0x0057

# Eventos de gremio (C2S 0x0043)
GLD_EVENT_OK = 0
GLD_EVENT_JOIN = 1
GLD_EVENT_KICK = 2
GLD_EVENT_LEAVE = 3
GLD_EVENT_PROMOTE = 4
GLD_EVENT_DEMOTE = 5
GLD_EVENT_ABDICATE = 6
GLD_EVENT_DISMISS = 7
GLD_EVENT_CHANGE_PERM = 8
GLD_EVENT_SET_RANK_NAME = 9
GLD_EVENT_UPDATE_BULLETIN = 10
GLD_EVENT_GET_BULLETIN = 11
GLD_EVENT_GET_GUILDDATA = 12
GLD_EVENT_GET_MEMBERS = 13
GLD_EVENT_UPDATE_LOGO = 17

# Rangos
GUILD_RANK_CHIEF = 0
GUILD_RANK_VICECHIEF = 1
GUILD_RANK_OFFICER = 2
GUILD_RANK_MEMBER = 3

# Permisos
GUILD_PERM_WITHDRAW_ITEM = 1          # 0x01
GUILD_PERM_WITHDRAW_MONEY = 2         # 0x02
GUILD_PERM_INVITE = 65536             # 0x10000
GUILD_PERM_KICK = 131072              # 0x20000
GUILD_PERM_PROMOTE = 262144           # 0x40000
GUILD_PERM_DEMOTE = 524288            # 0x80000
GUILD_PERM_ABDICATE = 1048576         # 0x100000
GUILD_PERM_DISMISS = 2097152          # 0x200000
GUILD_PERM_SET_RANK_NAME = 4194304    # 0x400000
GUILD_PERM_CHANGE_PERM = 8388608      # 0x800000
GUILD_PERM_UPDATE_BULLETIN = 16777216 # 0x1000000
GUILD_PERM_UPDATE_LOGO = 33554432     # 0x2000000

# Invitaciones pendientes: target_char_id -> dict(...)
_PENDIENTES_GUILD = {}


@functools.lru_cache(maxsize=1)
def umbrales_nivel():
    """Reputacion acumulada de 社團 en la ultima revision de level.xml."""
    root = pathlib.Path(__file__).resolve().parent.parent / 'extracted_paks'
    candidates = []
    for path in root.glob('*/setting/level.xml'):
        name = path.parents[1].name.lower()
        match = re.fullmatch(r'update(\d*)', name)
        if name == 'data1' or match:
            candidates.append((-1 if name == 'data1' else int(match.group(1) or 0), path))
    if not candidates:
        raise ValueError('Falta level.xml: no se pueden determinar los niveles de liga')
    rows = ET.parse(max(candidates, key=lambda p: p[0])[1]).getroot()
    thresholds = {int(e.get('\u7b49\u7d1a', 0)): int(e.findtext('\u793e\u5718') or 0)
                  for e in rows if 1 <= int(e.get('\u7b49\u7d1a', 0)) <= 10}
    values = tuple(thresholds[i] for i in range(1, 11))
    if values[0] != 0 or any(a >= b for a, b in zip(values, values[1:])):
        raise ValueError('Tabla de niveles de liga invalida')
    return values


def nivel_por_reputacion(reputacion):
    return max(i for i, threshold in enumerate(umbrales_nivel(), 1)
               if int(reputacion) >= threshold)


def _char_id(ses) -> int:
    p = getattr(ses, 'personaje', None)
    return int(getattr(p, 'char_id', 0) or 0) if p else 0


def _nombre(ses) -> str:
    p = getattr(ses, 'personaje', None)
    return (getattr(p, 'nombre', '') or '') if p else ''


def obtener_gremio_de(char_id: int):
    """Devuelve el dict del gremio al que pertenece el personaje, o None."""
    if not char_id:
        return None
    return cuentas.db_obtener_gremio_de_personaje(char_id)


def miembros_online_de(guild_id: int, mundos) -> list:
    """Devuelve las sesiones activas en el mundo de miembros de este gremio."""
    if not guild_id:
        return []
    res = []
    for s in list(mundos):
        cid = _char_id(s)
        if cid:
            g = obtener_gremio_de(cid)
            if g and g.get('guild_id') == guild_id:
                res.append(s)
    return res


def difundir_a_gremio(guild_id: int, mundos, *paquetes):
    """Envia uno o mas paquetes a todos los miembros conectados del gremio."""
    for s in miembros_online_de(guild_id, mundos):
        try:
            s.enviar(*paquetes)
            if hasattr(s, 'volcar'):
                s.volcar()
        except Exception:
            log.debug('error difundiendo a miembro de gremio', exc_info=True)


def mensaje_gremio(guild_id: int, mundos, texto: str):
    """Manda un mensaje al canal de liga de todos los miembros conectados."""
    pkt = clases.chat_league(0, "System", texto)
    difundir_a_gremio(guild_id, mundos, pkt)


# =========================================================================
# CONSTRUCCION DE PAQUETES S2C
# =========================================================================

def paquete_datos_gremio(gremio_dict, char_id: int, mi_rango: int = 3) -> bytes:
    """Genera el s2c 0x0055 (257 bytes exactos).

    Si gremio_dict es None, envia guild_id = 0, indicando al cliente que no esta en gremio.
    """
    # 257 bytes como en las capturas reales (Moonlights). El cliente (0x608fb0)
    # copia 142 a partir del +4 a su ficha de liga; el +0 es el personaje.
    b = bytearray(257)
    struct.pack_into('<I', b, 0, int(char_id))
    if gremio_dict:
        gid = int(gremio_dict.get('guild_id', 0))
        nivel = int(gremio_dict.get('nivel', 1))
        logo = int(gremio_dict.get('logo_id', 0))
        nombre = str(gremio_dict.get('nombre', '')).encode('latin-1', 'replace')[:16]
        rangos = gremio_dict.get('rangos') or ['Colonel', 'Vice-colonel', 'Cadre', 'Members']
        permisos = gremio_dict.get('permisos') or [-1, 16973824, 65536, 0]
        lider_cid = int(gremio_dict.get('lider_char_id', 0))
        miembros = cuentas.db_obtener_miembros_gremio(gid)
        cant_miembros = len(miembros)
        lider_nombre = next((m['nombre'] for m in miembros if m['char_id'] == lider_cid), '')
        lider_nombre = str(lider_nombre).encode('latin-1', 'replace')[:16]

        # En offset +4 de b (offset +6 del paquete completo):
        # +0   u32 guild_id
        # +4   u32 reputacion
        # +8   u32 numero de miembros
        # +12  17 B guild_name
        # +29  17 B nombre del lider
        # +46  68 B (4 titulos de rangos x 17 B)
        # +114 16 B (4 permisos x 4 B)
        # +130 u32 territorio (el cliente tambien lo calcula localmente)
        # +134 u32 logo_id
        # +138 u32 nivel
        base = 4
        struct.pack_into('<I', b, base + 0, gid)
        struct.pack_into('<I', b, base + 4, int(gremio_dict.get('reputacion', 0)))
        struct.pack_into('<I', b, base + 8, cant_miembros)
        b[base + 12:base + 12 + len(nombre)] = nombre
        b[base + 29:base + 29 + len(lider_nombre)] = lider_nombre

        # Titulos de los 4 rangos (17 bytes cada uno)
        for r_idx in range(4):
            t_nom = (rangos[r_idx] if r_idx < len(rangos) else '').encode('latin-1', 'replace')[:16]
            off_r = base + 46 + r_idx * 17
            b[off_r:off_r + len(t_nom)] = t_nom

        # Permisos de los 4 rangos (u32 cada uno)
        for p_idx in range(4):
            p_val = permisos[p_idx] if p_idx < len(permisos) else 0
            struct.pack_into('<I', b, base + 114 + p_idx * 4, p_val & 0xFFFFFFFF)

        struct.pack_into('<I', b, base + 134, logo)
        struct.pack_into('<I', b, base + 138, nivel)

    return struct.pack('<H', S2C_DATOS_GREMIO) + bytes(b)


def paquete_cartel_gremio(gremio_dict, char_id: int) -> bytes:
    """Genera el s2c 0x0054 con el cartel/boletin del gremio."""
    texto = (str(gremio_dict.get('cartel', '')) if gremio_dict else '').encode('latin-1', 'replace')
    # Longitud estandar del cartel es de hasta ~226 bytes
    texto = texto[:225]
    b = bytearray(4 + len(texto) + 1)
    struct.pack_into('<I', b, 0, int(char_id))
    b[4:4 + len(texto)] = texto
    b[-1] = 0
    return struct.pack('<H', S2C_CARTEL_GREMIO) + bytes(b)


def paquete_lista_miembros(guild_id: int, char_id: int, mundos) -> bytes:
    """Genera el s2c 0x0056 con la lista de miembros (32 bytes por miembro)."""
    miembros = cuentas.db_obtener_miembros_gremio(guild_id) if guild_id else []
    # Mapear char_id a sesion viva para nivel y online status
    online_map = {}
    for s in list(mundos):
        cid = _char_id(s)
        if cid:
            online_map[cid] = s

    b_miembros = []
    for m in miembros:
        m_cid = int(m['char_id'])
        s_activa = online_map.get(m_cid)
        online = 1 if s_activa is not None else 0
        nivel = m['nivel']
        clase_id = m['clase_id']
        if s_activa and getattr(s_activa, 'personaje', None):
            pj = s_activa.personaje
            nivel = getattr(pj, 'nivel', nivel) or nivel
            clase_id = getattr(pj, 'class_id', clase_id) or clase_id

        rec = bytearray(32)
        struct.pack_into('<I', rec, 0, m_cid)
        nom = str(m['nombre']).encode('latin-1', 'replace')[:16]
        rec[4:4 + len(nom)] = nom
        struct.pack_into('<I', rec, 21, int(nivel))
        rec[25] = int(clase_id) & 0xFF
        rec[26] = int(m['rango']) & 0xFF
        rec[27] = int(online) & 0xFF
        struct.pack_into('<I', rec, 28, int(m.get('contribucion', 0) or 0))
        b_miembros.append(rec)

    cab = bytearray(5)
    struct.pack_into('<I', cab, 0, int(char_id))
    cab[4] = min(255, len(b_miembros))
    return struct.pack('<H', S2C_MIEMBROS_GREMIO) + bytes(cab) + b''.join(b_miembros)


def paquete_invitacion_gremio(target_char_id: int, nombre_invitador: str, nombre_gremio: str) -> bytes:
    """Genera el s2c 0x0057 (40 bytes con opcode): cuadro de invitacion a la liga."""
    b = bytearray(38)
    struct.pack_into('<I', b, 0, int(target_char_id))
    n_inv = nombre_invitador.encode('latin-1', 'replace')[:16]
    b[4:4 + len(n_inv)] = n_inv
    n_gld = nombre_gremio.encode('latin-1', 'replace')[:16]
    b[21:21 + len(n_gld)] = n_gld
    return struct.pack('<H', S2C_INVITACION_GREMIO) + bytes(b)


# =========================================================================
# LOGICA DE COMANDOS DE GREMIO
# =========================================================================

def _rango_de(gremio_dict, char_id: int) -> int:
    """Obtiene el rango del jugador en su gremio (0..3), o 3 por defecto."""
    if not gremio_dict:
        return 3
    if int(gremio_dict.get('lider_char_id', 0)) == char_id:
        return 0
    miembros = cuentas.db_obtener_miembros_gremio(gremio_dict['guild_id'])
    for m in miembros:
        if m['char_id'] == char_id:
            return int(m['rango'])
    return 3


def limite_miembros(nivel: int) -> int:
    """Tabla usada por el cliente en 0x8C2588, indices 1..10."""
    return (30, 40, 50, 60, 70, 70, 70, 70, 70, 70)[max(1, min(10, int(nivel or 1))) - 1]


@functools.lru_cache(maxsize=1)
def materiales_contribucion():
    """ID de fila -> (item, unidades por lote, reputacion por lote)."""
    import house_services
    filas = house_services.xml_rows('guild_contrib.xml')
    return {ident: (int(r['\u6536\u53d6\u7269\u8cc7']), int(r['\u6578\u91cf']),
                    int(r['\u7372\u5f97\u540d\u8072']))
            for ident, r in filas.items()}


def interpretar_contribucion(cuerpo: bytes):
    """0x004B: cuenta u8 y hasta 100 pares (ID de fila u16, lotes u32).

    sub_6225F0 envia el ID de gcontrib, no el ID del objeto. La interfaz
    limita los lotes a existencias / cantidad de la fila (sub_6640xx).
    """
    if not cuerpo or not 1 <= cuerpo[0] <= 100 or len(cuerpo) != 1 + 6 * cuerpo[0]:
        raise ValueError('paquete de contribucion invalido')
    filas = materiales_contribucion()
    requeridos = {}
    puntos = 0
    vistos = set()
    for i in range(cuerpo[0]):
        ident, lotes = struct.unpack_from('<HI', cuerpo, 1 + 6 * i)
        if ident in vistos or ident not in filas or not lotes:
            raise ValueError('fila o cantidad invalida')
        vistos.add(ident)
        item, cantidad, fama = filas[ident]
        if item <= 0 or cantidad <= 0 or fama <= 0:
            raise ValueError('datos de contribucion invalidos')
        requeridos[item] = requeridos.get(item, 0) + cantidad * lotes
        puntos += fama * lotes
        if requeridos[item] > 0xffffffff or puntos > 0xffffffff:
            raise ValueError('contribucion demasiado grande')
    return requeridos, puntos


def _tiene_permiso(gremio_dict, char_id: int, permiso_flag: int) -> bool:
    """Verifica si el jugador tiene el permiso solicitado segun su rango."""
    if not gremio_dict:
        return False
    rango = _rango_de(gremio_dict, char_id)
    if rango == GUILD_RANK_CHIEF:
        return True
    permisos = gremio_dict.get('permisos') or [0, 0, 0, 0]
    p_val = permisos[rango] if rango < len(permisos) else 0
    return bool(p_val & permiso_flag)


def al_entrar_jugador(ses, mundos):
    """Envia ficha y cartel de gremio al conectar o cambiar de mapa si pertenece a uno."""
    cid = _char_id(ses)
    if not cid:
        return
    g = obtener_gremio_de(cid)
    if g:
        rango = _rango_de(g, cid)
        ses.enviar(paquete_datos_gremio(g, cid, mi_rango=rango))
        ses.enviar(paquete_cartel_gremio(g, cid))
        if hasattr(ses, 'volcar'):
            ses.volcar()
        # Notificar a los companeros de gremio conectados que se conecto
        actualizar_lista_para_gremio(g['guild_id'], mundos)


def al_desconectar_jugador(ses, mundos):
    """Limpia pendientes y actualiza el estado offline en el gremio."""
    cid = _char_id(ses)
    _PENDIENTES_GUILD.pop(cid, None)
    if cid:
        g = obtener_gremio_de(cid)
        if g:
            # Notificar que paso a offline
            actualizar_lista_para_gremio(g['guild_id'], mundos)


def actualizar_lista_para_gremio(guild_id: int, mundos):
    """Envia 0x0056 actualizado a todos los miembros online del gremio."""
    for s in miembros_online_de(guild_id, mundos):
        cid = _char_id(s)
        try:
            s.enviar(paquete_lista_miembros(guild_id, cid, mundos))
            if hasattr(s, 'volcar'):
                s.volcar()
        except Exception:
            pass


def procesar_crear_gremio(ses, cuerpo: bytes, mundos):
    """C2S 0x0041: [guild_name (17B)][u32 logo_id]."""
    cid = _char_id(ses)
    p = getattr(ses, 'personaje', None)
    if not cid or not p:
        return

    # Comprobar si ya esta en un gremio
    if obtener_gremio_de(cid):
        ses.enviar(clases.aviso("You are already in a league.", tipo=0))
        return

    nombre = cuerpo[:17].split(b'\x00', 1)[0].decode('latin-1', 'replace').strip()
    logo_id = struct.unpack_from('<I', cuerpo, 17)[0] if len(cuerpo) >= 21 else 0

    if len(nombre) < 2 or len(nombre) > 16:
        ses.enviar(clases.aviso("League name must be between 2 and 16 characters.", tipo=0))
        return

    # Verificar que el nombre no este ocupado
    if cuentas.db_obtener_gremio_por_nombre(nombre):
        ses.enviar(clases.aviso("That league name is unavailable.", tipo=0))
        return

    # Requisitos del dialogo 5778.
    nivel = int(getattr(p, 'nivel', 1) or 1)
    # Requisitos del League Clerk (dialogo 5778 del cliente): nivel 25,
    # rango 3 y 60.000 de oro. El dialogo ya los mira antes de abrir la ventana.
    if nivel < 25:
        ses.enviar(clases.aviso("You must be at least Level 25 to create a league.", tipo=0))
        return
    if int(getattr(p, 'rango', 1) or 1) < 3:
        ses.enviar(clases.aviso("You must reach Rank 3 to create a league.", tipo=0))
        return

    costo_oro = 60000
    oro_actual = int(getattr(ses, 'oro', 0) or 0)
    if oro_actual < costo_oro:
        ses.enviar(clases.aviso(f"Creating a league requires {costo_oro} gold coins.", tipo=0))
        return

    # La creacion y el cobro se confirman juntos: un nombre duplicado o un
    # fallo de base no deben hacer perder oro al jugador.
    if not getattr(ses, 'usuario', None):
        ses.enviar(clases.aviso('Could not create the league.', tipo=0))
        return
    clase_id = int(getattr(p, 'class_id', 1) or 1)
    try:
        gid = cuentas.db_crear_gremio(nombre, cid, p.nombre, nivel, clase_id,
                                      logo_id=logo_id, usuario=ses.usuario,
                                      oro_final=oro_actual - costo_oro)
    except Exception:
        log.exception('No se pudo crear la liga %s', nombre)
        ses.enviar(clases.aviso('Could not create the league; no gold was charged.', tipo=0))
        return
    ses.oro = oro_actual - costo_oro
    p.oro = ses.oro
    try:
        import inventario as _inv
        inst = getattr(ses, 'instancias', {}).get(_inv.RANURA_ORO, 0)
        ses.enviar(_inv.actualizar_ranura(cid, _inv.RANURA_ORO, _inv.ITEM_ORO, ses.oro, inst, getattr(p, 'entity_id', 0) or 0))
    except Exception:
        pass

    log.info("%s creo la liga '%s' (id=%d, logo=%d)", p.nombre, nombre, gid, logo_id)

    g = cuentas.db_obtener_gremio(gid)
    ses.enviar(paquete_datos_gremio(g, cid, mi_rango=0))
    ses.enviar(paquete_cartel_gremio(g, cid))
    ses.enviar(paquete_lista_miembros(gid, cid, mundos))
    ses.enviar(clases.aviso(f"Congratulations! League '{nombre}' has been founded!", tipo=0))
    if hasattr(ses, 'volcar'):
        ses.volcar()


def procesar_invitar_gremio(ses, cuerpo: bytes, mundos):
    """C2S 0x0042: [target_name (17B)]."""
    cid = _char_id(ses)
    p = getattr(ses, 'personaje', None)
    if not cid or not p:
        return

    g = obtener_gremio_de(cid)
    if not g:
        ses.enviar(clases.aviso("You are not in any league now.", tipo=0))
        return

    if not _tiene_permiso(g, cid, GUILD_PERM_INVITE):
        ses.enviar(clases.aviso("Your are unqualified to make that decision.", tipo=0))
        return

    target_name = cuerpo[:17].split(b'\x00', 1)[0].decode('latin-1', 'replace').strip()
    if not target_name or target_name.lower() == p.nombre.lower():
        return

    # Buscar sesion del objetivo
    target_ses = None
    for s in list(mundos):
        p_otro = getattr(s, 'personaje', None)
        if p_otro and p_otro.nombre.lower() == target_name.lower():
            target_ses = s
            break

    if not target_ses:
        ses.enviar(clases.aviso("The character is not in the world.", tipo=0))
        return

    target_cid = _char_id(target_ses)
    if obtener_gremio_de(target_cid):
        ses.enviar(clases.aviso("The target is already in a league.", tipo=0))
        return

    # El limite depende del nivel, como en la ficha del cliente.
    miembros = cuentas.db_obtener_miembros_gremio(g['guild_id'])
    if len(miembros) >= limite_miembros(g.get('nivel', 1)):
        ses.enviar(clases.aviso("The league is full.", tipo=0))
        return

    _PENDIENTES_GUILD[target_cid] = {
        'guild_id': g['guild_id'],
        'inviter_cid': cid,
        'inviter_name': p.nombre,
        'guild_name': g['nombre'],
        'ts': time.time()
    }

    target_ses.enviar(paquete_invitacion_gremio(target_cid, p.nombre, g['nombre']))
    if hasattr(target_ses, 'volcar'):
        target_ses.volcar()
    ses.enviar(clases.aviso(f"Sent league invitation to {target_name}.", tipo=0))
    log.info("%s invita a %s a la liga %s", p.nombre, target_name, g['nombre'])


def procesar_comando_gremio(ses, cuerpo: bytes, mundos):
    """C2S 0x0043: Dispatch de acciones de gremio segun cmd_id."""
    if len(cuerpo) < 5:
        return
    cmd_id = cuerpo[4]
    param1 = struct.unpack_from('<I', cuerpo, 9)[0] if len(cuerpo) >= 13 else 0
    param2 = struct.unpack_from('<I', cuerpo, 13)[0] if len(cuerpo) >= 17 else 0
    str_param = ''
    if len(cuerpo) > 21:
        str_param = cuerpo[21:].split(b'\x00', 1)[0].decode('latin-1', 'replace').strip()

    cid = _char_id(ses)
    p = getattr(ses, 'personaje', None)
    if not cid or not p:
        return

    # 1. Unirse a gremio (GLD_EVENT_JOIN)
    if cmd_id == GLD_EVENT_JOIN:
        inv = _PENDIENTES_GUILD.pop(cid, None)
        if not inv:
            return
        if param2 == 1: # Aceptar
            gid = inv['guild_id']
            g = cuentas.db_obtener_gremio(gid)
            if not g:
                return
            if obtener_gremio_de(cid):
                return
            if len(cuentas.db_obtener_miembros_gremio(gid)) >= limite_miembros(g.get('nivel', 1)):
                ses.enviar(clases.aviso("The league is full.", tipo=0))
                return
            nivel = int(getattr(p, 'nivel', 1) or 1)
            clase_id = int(getattr(p, 'class_id', 1) or 1)
            cuentas.db_agregar_miembro_gremio(gid, cid, p.nombre, nivel, clase_id, rango=3)

            ses.enviar(paquete_datos_gremio(g, cid, mi_rango=3))
            ses.enviar(paquete_cartel_gremio(g, cid))
            ses.enviar(paquete_lista_miembros(gid, cid, mundos))
            if hasattr(ses, 'volcar'):
                ses.volcar()

            mensaje_gremio(gid, mundos, f"{p.nombre} joins the league.")
            actualizar_lista_para_gremio(gid, mundos)
            log.info("%s se unio a la liga %s", p.nombre, g['nombre'])
        else: # Rechazar
            log.info("%s rechazo la invitacion a la liga %s", p.nombre, inv['guild_name'])
        return

    # Los siguientes comandos requieren estar en un gremio
    g = obtener_gremio_de(cid)
    if not g:
        ses.enviar(clases.aviso("You are not in any league now.", tipo=0))
        return
    gid = g['guild_id']
    mi_rango = _rango_de(g, cid)

    # Nunca aplicar acciones sobre un personaje de otra liga. _rango_de tiene
    # un valor por defecto y por si solo no acredita la pertenencia.
    if cmd_id in (GLD_EVENT_KICK, GLD_EVENT_PROMOTE, GLD_EVENT_DEMOTE, GLD_EVENT_ABDICATE):
        if not any(m['char_id'] == param1 for m in cuentas.db_obtener_miembros_gremio(gid)):
            return

    # 2. Expulsar miembro (GLD_EVENT_KICK, param1 = target_char_id)
    if cmd_id == GLD_EVENT_KICK:
        target_cid = param1
        if not _tiene_permiso(g, cid, GUILD_PERM_KICK):
            ses.enviar(clases.aviso("Your are unqualified to make that decision.", tipo=0))
            return
        target_rango = _rango_de(g, target_cid)
        if target_cid == cid or target_rango <= mi_rango:
            ses.enviar(clases.aviso("You cannot kick a member of equal or higher rank.", tipo=0))
            return
        target_nom = ''
        miembros = cuentas.db_obtener_miembros_gremio(gid)
        for m in miembros:
            if m['char_id'] == target_cid:
                target_nom = m['nombre']
                break
        cuentas.db_remover_miembro_gremio(target_cid)
        # Si el objetivo esta conectado, resetearle el gremio
        for s in list(mundos):
            if _char_id(s) == target_cid:
                s.enviar(paquete_datos_gremio(None, target_cid))
                s.enviar(clases.aviso("You have been kicked out of the league.", tipo=0))
                if hasattr(s, 'volcar'):
                    s.volcar()
                break
        mensaje_gremio(gid, mundos, f"{target_nom} is kicked out of the league.")
        actualizar_lista_para_gremio(gid, mundos)
        log.info("%s expulso a %s de la liga %s", p.nombre, target_nom, g['nombre'])
        return

    # 3. Dejar gremio (GLD_EVENT_LEAVE)
    if cmd_id == GLD_EVENT_LEAVE:
        if mi_rango == GUILD_RANK_CHIEF:
            ses.enviar(clases.aviso("The colonel is unable to leave the league.", tipo=0))
            return
        cuentas.db_remover_miembro_gremio(cid)
        ses.enviar(paquete_datos_gremio(None, cid))
        if hasattr(ses, 'volcar'):
            ses.volcar()
        mensaje_gremio(gid, mundos, f"{p.nombre} leaves the league.")
        actualizar_lista_para_gremio(gid, mundos)
        log.info("%s dejo la liga %s", p.nombre, g['nombre'])
        return

    # 4. Ascender miembro (GLD_EVENT_PROMOTE, param1 = target_char_id)
    if cmd_id == GLD_EVENT_PROMOTE:
        target_cid = param1
        if not _tiene_permiso(g, cid, GUILD_PERM_PROMOTE):
            ses.enviar(clases.aviso("Your are unqualified to make that decision.", tipo=0))
            return
        target_rango = _rango_de(g, target_cid)
        if target_rango <= mi_rango:
            ses.enviar(clases.aviso("You cannot promote this member.", tipo=0))
            return
        if target_rango <= GUILD_RANK_VICECHIEF: # No se puede ascender a Coronel por esta via
            ses.enviar(clases.aviso("Unable to upgrade to colonel.", tipo=0))
            return
        nuevo_rango = target_rango - 1
        if nuevo_rango <= mi_rango and mi_rango != GUILD_RANK_CHIEF:
            ses.enviar(clases.aviso("Cannot promote to a rank equal or higher than your own.", tipo=0))
            return
        cuentas.db_actualizar_rango_miembro(target_cid, nuevo_rango)
        target_nom = ''
        for m in cuentas.db_obtener_miembros_gremio(gid):
            if m['char_id'] == target_cid:
                target_nom = m['nombre']
                break
        mensaje_gremio(gid, mundos, f"{target_nom}'s rank is upgraded.")
        actualizar_lista_para_gremio(gid, mundos)
        # Actualizar datos del objetivo si esta conectado
        for s in list(mundos):
            if _char_id(s) == target_cid:
                s.enviar(paquete_datos_gremio(g, target_cid, mi_rango=nuevo_rango))
                break
        log.info("%s ascendio a %s a rango %d en liga %s", p.nombre, target_nom, nuevo_rango, g['nombre'])
        return

    # 5. Degradar miembro (GLD_EVENT_DEMOTE, param1 = target_char_id)
    if cmd_id == GLD_EVENT_DEMOTE:
        target_cid = param1
        if not _tiene_permiso(g, cid, GUILD_PERM_DEMOTE):
            ses.enviar(clases.aviso("Your are unqualified to make that decision.", tipo=0))
            return
        target_rango = _rango_de(g, target_cid)
        if target_rango <= mi_rango:
            ses.enviar(clases.aviso("You cannot demote this member.", tipo=0))
            return
        if target_rango >= GUILD_RANK_MEMBER:
            ses.enviar(clases.aviso("The members of the league are unable to be demoted.", tipo=0))
            return
        nuevo_rango = target_rango + 1
        cuentas.db_actualizar_rango_miembro(target_cid, nuevo_rango)
        target_nom = ''
        for m in cuentas.db_obtener_miembros_gremio(gid):
            if m['char_id'] == target_cid:
                target_nom = m['nombre']
                break
        mensaje_gremio(gid, mundos, f"{target_nom}'s rank is degraded.")
        actualizar_lista_para_gremio(gid, mundos)
        for s in list(mundos):
            if _char_id(s) == target_cid:
                s.enviar(paquete_datos_gremio(g, target_cid, mi_rango=nuevo_rango))
                break
        log.info("%s degrado a %s a rango %d en liga %s", p.nombre, target_nom, nuevo_rango, g['nombre'])
        return

    # 6. Ceder liderazgo (GLD_EVENT_ABDICATE, param1 = target_char_id)
    if cmd_id == GLD_EVENT_ABDICATE:
        if mi_rango != GUILD_RANK_CHIEF:
            ses.enviar(clases.aviso("Your are unqualified to make that decision.", tipo=0))
            return
        target_cid = param1
        if target_cid == cid:
            return
        # Viejo lider pasa a Vice-colonel (1), nuevo lider pasa a Colonel (0)
        cuentas.db_transferir_liderazgo_gremio(gid, target_cid)
        g_act = cuentas.db_obtener_gremio(gid)
        target_nom = ''
        for m in cuentas.db_obtener_miembros_gremio(gid):
            if m['char_id'] == target_cid:
                target_nom = m['nombre']
                break
        mensaje_gremio(gid, mundos, f"{target_nom} becomes the Colonel.")
        actualizar_lista_para_gremio(gid, mundos)
        for s in miembros_online_de(gid, mundos):
            c_s = _char_id(s)
            s.enviar(paquete_datos_gremio(g_act, c_s, mi_rango=_rango_de(g_act, c_s)))
        log.info("%s cedio el liderazgo de la liga %s a %s", p.nombre, g['nombre'], target_nom)
        return

    # 7. Disolver gremio (GLD_EVENT_DISMISS)
    if cmd_id == GLD_EVENT_DISMISS:
        if mi_rango != GUILD_RANK_CHIEF:
            ses.enviar(clases.aviso("Your are unqualified to make that decision.", tipo=0))
            return
        nom_gremio = g['nombre']
        if int(g.get('fondos', 0) or 0) or cuentas.db_banco_gremio(gid):
            ses.enviar(clases.aviso('Empty the league warehouse before disbanding.', tipo=0))
            return
        miembros_afectados = miembros_online_de(gid, mundos)
        cuentas.db_disolver_gremio(gid)
        for s in miembros_afectados:
            c_s = _char_id(s)
            s.enviar(paquete_datos_gremio(None, c_s))
            s.enviar(clases.aviso("The league is disbanded.", tipo=0))
            if hasattr(s, 'volcar'):
                s.volcar()
        log.info("%s disolvio la liga '%s'", p.nombre, nom_gremio)
        return

    # 8. Cambiar permisos (GLD_EVENT_CHANGE_PERM, param1 = rango_idx, param2 = perm_flags)
    if cmd_id == GLD_EVENT_CHANGE_PERM:
        if not _tiene_permiso(g, cid, GUILD_PERM_CHANGE_PERM):
            ses.enviar(clases.aviso("Your are unqualified to make that decision.", tipo=0))
            return
        rango_idx = param1
        perm_flags = param2
        if rango_idx == GUILD_RANK_CHIEF:
            return # Permisos del lider son siempre todos
        cuentas.db_actualizar_permisos_gremio(gid, rango_idx, perm_flags)
        g_act = cuentas.db_obtener_gremio(gid)
        for s in miembros_online_de(gid, mundos):
            c_s = _char_id(s)
            s.enviar(paquete_datos_gremio(g_act, c_s, mi_rango=_rango_de(g_act, c_s)))
        log.info("%s actualizo permisos para rango %d en liga %s: 0x%X", p.nombre, rango_idx, g['nombre'], perm_flags)
        return

    # 9. Cambiar nombre de rango (GLD_EVENT_SET_RANK_NAME, param2 = rango_idx, str_param = nuevo_nombre)
    if cmd_id == GLD_EVENT_SET_RANK_NAME:
        if not _tiene_permiso(g, cid, GUILD_PERM_SET_RANK_NAME):
            ses.enviar(clases.aviso("Your are unqualified to make that decision.", tipo=0))
            return
        rango_idx = param2
        nuevo_nom = str_param[:16]
        if not nuevo_nom or not 0 <= rango_idx <= 3:
            return
        cuentas.db_actualizar_nombre_rango_gremio(gid, rango_idx, nuevo_nom)
        g_act = cuentas.db_obtener_gremio(gid)
        mensaje_gremio(gid, mundos, f"{g['rangos'][rango_idx]}'s position name is changed to {nuevo_nom}.")
        for s in miembros_online_de(gid, mundos):
            c_s = _char_id(s)
            s.enviar(paquete_datos_gremio(g_act, c_s, mi_rango=_rango_de(g_act, c_s)))
        log.info("%s renombro rango %d a '%s' en liga %s", p.nombre, rango_idx, nuevo_nom, g['nombre'])
        return

    # 10. Actualizar boletin/cartel (GLD_EVENT_UPDATE_BULLETIN, str_param = nuevo_cartel)
    if cmd_id == GLD_EVENT_UPDATE_BULLETIN:
        if not _tiene_permiso(g, cid, GUILD_PERM_UPDATE_BULLETIN):
            ses.enviar(clases.aviso("Your are unqualified to make that decision.", tipo=0))
            return
        cuentas.db_actualizar_cartel_gremio(gid, str_param)
        g_act = cuentas.db_obtener_gremio(gid)
        for s in miembros_online_de(gid, mundos):
            c_s = _char_id(s)
            s.enviar(paquete_cartel_gremio(g_act, c_s))
        log.info("%s actualizo el cartel de la liga %s", p.nombre, g['nombre'])
        return

    # 11. Pedir cartel (GLD_EVENT_GET_BULLETIN)
    if cmd_id == GLD_EVENT_GET_BULLETIN:
        ses.enviar(paquete_cartel_gremio(g, cid))
        if hasattr(ses, 'volcar'):
            ses.volcar()
        return

    # 12. Pedir datos de gremio (GLD_EVENT_GET_GUILDDATA)
    if cmd_id == GLD_EVENT_GET_GUILDDATA:
        ses.enviar(paquete_datos_gremio(g, cid, mi_rango=mi_rango))
        if hasattr(ses, 'volcar'):
            ses.volcar()
        return

    # 13. Pedir miembros (GLD_EVENT_GET_MEMBERS)
    if cmd_id == GLD_EVENT_GET_MEMBERS:
        ses.enviar(paquete_lista_miembros(gid, cid, mundos))
        if hasattr(ses, 'volcar'):
            ses.volcar()
        return

    # 17. Actualizar logo (GLD_EVENT_UPDATE_LOGO, param2 = logo_id)
    if cmd_id == GLD_EVENT_UPDATE_LOGO:
        if not _tiene_permiso(g, cid, GUILD_PERM_UPDATE_LOGO):
            ses.enviar(clases.aviso("Your are unqualified to make that decision.", tipo=0))
            return
        nuevo_logo = param2
        cuentas.db_actualizar_logo_gremio(gid, nuevo_logo)
        g_act = cuentas.db_obtener_gremio(gid)
        for s in miembros_online_de(gid, mundos):
            c_s = _char_id(s)
            s.enviar(paquete_datos_gremio(g_act, c_s, mi_rango=_rango_de(g_act, c_s)))
        log.info("%s actualizo el logo de la liga %s a %d", p.nombre, g['nombre'], nuevo_logo)
        return


# =========================================================================
# BANCO DE LIGA
# =========================================================================
# El s2c 0x0059 (manejador 0x607670 del cliente) es el banco de la liga y
# tiene EXACTAMENTE el formato del almacen personal 0x004E: un LE32 con
# tipo*1000 + cuenta y detras las entradas (recorridas con el mismo paso:
# +1 y luego 0x55 + el u16 de +0x32). Con tipo 2 abre la ventana -- a
# CreateBankWnd le pasa 1, que es CUR_BANK_TYPE = BANK_TYPE_GUILD -- y con
# tipo 1 solo vacia y rellena la lista. La ventana pasa antes por la
# contrasena de comercio (0x5c05e0), que con el byte 0x278 a 0 deja pasar.
# Depositar y sacar van por los mismos 0x0038 / 0x0039 que el banco propio:
# el servidor decide segun el banco que este abierto.
S2C_BANCO_GREMIO = 0x0059
CASILLAS_BANCO_GREMIO = 48


def paquete_banco_gremio(gremio_dict, char_id: int, entidad: int, tipo: int = 2) -> bytes:
    import inventario as _inv
    gid = int(gremio_dict['guild_id'])
    items = [(0, _inv.ITEM_ORO, int(gremio_dict.get('fondos', 0) or 0), {})]
    items.extend((r, it, cn, meta) for r, (it, cn, meta) in
                 sorted(cuentas.db_banco_gremio_detallado(gid).items()))
    entradas = []
    for r, it, cn, meta in items:
        try:
            inst = bytes.fromhex(meta.get('instancia', ''))
            if len(inst) != 8:
                inst = None
        except (TypeError, ValueError):
            inst = None
        pet = meta.get('mascota')
        if pet:
            pet = dict(pet, ranura=r, fuera=False)
        e = bytearray(_inv._entrada(char_id, r, it, cn, inst, entidad, mascota=pet))
        struct.pack_into('<BI', e, 33, _inv.CONT_BANCO, _inv.ID_BANCO)
        struct.pack_into('<I', e, 40, cn)
        struct.pack_into('<H', e, 84, struct.unpack_from('<H', e, 1)[0])
        e = bytes(e)
        mejora = meta.get('mejora') or {}
        e = _inv.marcar_caducidad_mercenario(e, mejora)
        e = _inv.marcar_vinculacion(e, mejora)
        if mejora.get('veces'):
            e = _inv.marcar_mejora(e, mejora['veces'])
        if mejora.get('extra'):
            e = _inv.marcar_extras(e, mejora['extra'])
        if mejora.get('huecos') or mejora.get('gemas'):
            e = _inv.marcar_huecos(e, mejora.get('huecos') or 0, mejora.get('gemas'))
        entradas.append(e)
    return struct.pack('<HI', S2C_BANCO_GREMIO, tipo * 1000 + len(entradas)) + b''.join(entradas)


def puede_sacar(gremio_dict, char_id: int, oro: bool = False) -> bool:
    return _tiene_permiso(gremio_dict, char_id,
                          GUILD_PERM_WITHDRAW_MONEY if oro else GUILD_PERM_WITHDRAW_ITEM)
