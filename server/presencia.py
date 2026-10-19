"""Que los jugadores se vean entre ellos.

HASTA AHORA EL SERVIDOR NO TENIA NADA DE ONLINE. No es que las instancias
estuvieran separadas: lo estaban TODOS los mapas. Se comprobo buscando
cualquier envio de una sesion a otra y no habia ni uno; la lista de sesiones
de mundo (`self.mundos`) solo se usaba para que la consola de GM supiera a
quien darle un item. Cada jugador tenia su copia del mundo, con sus propios
monstruos armados por `_monstruos_de()` al cambiar de mapa.

Esto es la primera capa de las tres que hacen falta:

    1. PRESENCIA  <- esto
       verse, verse moverse y verse desaparecer.
    2. MUNDO COMPARTIDO
       que los monstruos cuelguen del mapa y no de la sesion, con la exp y
       el botin repartidos. Es el paso que toca el combate entero.
    3. EQUIPOS
       los opcodes 0x0017 (groupinvite) y 0x0018 (el resto: join, leave,
       kick, promote, disband, deny) y, encima, las copias de instancia por
       equipo.

EL PAQUETE ES EL 0x0001, Y SE SUPO POR UNA CAPTURA. El primer intento uso
el 0x0008, que es el que dibuja NPC y monstruos, y NO FUNCIONO: dos clientes
en Bling Plaza, en casillas pegadas, no se veian. Lo que faltaba era una
captura con jugadores de verdad dentro, y la trajo la sesion del Global con
tres cuentas montando un equipo (Yuki, KarmaSilk y KarmaWeapon).

Buscando que paquetes S2C llevan el nombre de un jugador salio en seguida:

    0x0026  98 B   x14845   la ficha de un jugador, el mismo bloque de 98
                            bytes que usa cada miembro en la lista del grupo
    0x0001  184 B  x73      APARECE UN JUGADOR

Y el 0x0001 se confirmo cruzandolo con el movimiento: las cinco entidades
que salen en sus 0x0001 son las mismas que luego andan en los 0x0005 -- la
de KarmaSilk dio 59 pasos -- asi que el id esta donde se creia y el
movimiento va por el mismo 0x0005 de siempre, que es lo unico que ya estaba
bien del primer intento.

    +0   u32 entity_id
    +8   u32 casilla x
    +12  u32 casilla y
    +16  nombre ASCIIZ (16 bytes)
    +150 nombre de la GUILD ASCIIZ
    el resto: apariencia y equipo

EL CUERPO SE COPIA. De los 184 bytes solo se entienden esos cuatro campos;
el resto es la apariencia y no se sabe armar. Se coge uno capturado de un
jugador de verdad y se le cambian la entidad, la casilla y el nombre, que es
el mismo truco que ya se usa para dibujar los tornados y los objetos de
mapa. Consecuencia: todos los jugadores se veran con la pinta del que se
capturo hasta que se sepa leer la apariencia. Se les ve, se les ve andar y
se les lee el nombre, que es lo que hacia falta.

EL SPRITE sale de la clase del personaje. El cliente arma la ruta del dibujo
como \\chr\\iNNNg\\2NNNN_Wait.spr a partir de la apariencia, y en la lista de
personajes esa apariencia son el class_id y cinco bytes. Aqui se usa el
mismo numero que el jugador ve en su propia ficha.
"""
import collections
import logging
import struct
import inventario as _inv

log = logging.getLogger('presencia')

# Las entidades de los jugadores no pueden chocar con nada de lo que ya hay
# en un mapa: los monstruos del cliente van en 50.000.000, los objetos de
# mapa en 60.000.000 y los tornados dibujados en 70.000.000.
BASE_ENTIDAD = 80_000_000

# Quien esta en cada mapa. stage -> lista de sesiones.
_POR_MAPA = collections.defaultdict(list)


_ENTIDADES_ASIGNADAS = set()


def entidad_de(ses) -> int:
    """El id con el que los DEMAS ven a este jugador en el cliente de Celestia."""
    e = getattr(ses, '_entidad_publica', None)
    if e is None:
        cand = 2001
        while cand in _ENTIDADES_ASIGNADAS:
            cand += 1
        _ENTIDADES_ASIGNADAS.add(cand)
        e = cand
        ses._entidad_publica = e
    return e


def liberar_entidad(ses):
    e = getattr(ses, '_entidad_publica', None)
    if e and e in _ENTIDADES_ASIGNADAS:
        _ENTIDADES_ASIGNADAS.remove(e)
    ses._entidad_publica = None


def _datos(ses):
    p = getattr(ses, 'personaje', None)
    if p is None:
        return None
    return (entidad_de(ses), getattr(p, 'nombre', '') or '?',
            int(getattr(p, 'tile_x', 0)), int(getattr(p, 'tile_y', 0)),
            int(getattr(p, 'sprite', 0) or 0))


# Un 0x0001 oficial de Celestia (128 bytes, medido en Hidden Grove).
# No confundir con los 184 B del servidor IGG Global que rompen el stream de Celestia.
PLANTILLA = bytes.fromhex(
    '5600000000000000b50000005f00000043686f636f000000000000000000000000000000'
    '00000000000000000000000000000100000000010100000004000000a9300000aa300000'
    'e703000000000000ab300000ac3000000000000096070000751d00000000000000000000'
    '0000000000000000000000000000000000000000'
)
OFF_ENTIDAD, OFF_X, OFF_Y, OFF_NOMBRE, TAM_NOMBRE = 0, 8, 12, 16, 16
# El byte +50 de la ficha 0x0002 que se manda a cada jugador (ver _spawn).
CUERPO_FICHA = 5
APARECE = 0x0001


def transform_sprite_de(ses) -> int:
    """Devuelve el sprite de transformacion activo si el jugador esta transformado, o 0 si no."""
    import time
    p = getattr(ses, 'personaje', None)
    if not p:
        return 0
    buffs = getattr(p, 'buffs', None) or {}
    ahora = time.time()
    for b_id, b_data in buffs.items():
        if not isinstance(b_data, dict):
            continue
        if b_data.get('fin', 0) > ahora and b_data.get('es_transform'):
            ts = b_data.get('trans_sprite') or (b_data.get('mag') or {}).get('trans_sprite')
            if ts:
                return int(ts)
    return 0


def _spawn(ses):
    """El 0x0001 oficial de 128 bytes que presenta a ese jugador ante los demas."""
    d = _datos(ses)
    if d is None:
        return None
    eid, nombre, tx, ty, _sprite = d
    p = getattr(ses, 'personaje', None)
    b = bytearray(PLANTILLA)
    struct.pack_into('<I', b, OFF_ENTIDAD, eid)
    struct.pack_into('<I', b, 4, 0)
    struct.pack_into('<I', b, OFF_X, tx)
    struct.pack_into('<I', b, OFF_Y, ty)
    n = nombre.encode('ascii', 'replace')[:TAM_NOMBRE - 1]
    b[OFF_NOMBRE:OFF_NOMBRE + TAM_NOMBRE] = n + bytes(TAM_NOMBRE - len(n))

    # Apariencia base (5 bytes en offsets 55..59 segun sub_5E97F0 en Angel.exe)
    apariencia = getattr(p, 'apariencia', None) or [0, 0, 0, 8, 8]
    if isinstance(apariencia, (list, tuple)) and len(apariencia) >= 5:
        b[55] = int(apariencia[0])
        b[56] = int(apariencia[1])
        b[57] = int(apariencia[2])
        b[58] = int(apariencia[3])
        b[59] = int(apariencia[4])

    import login as _lg
    b[60] = _lg.CODIGO_FACCION.get(getattr(p, 'faction', ''), 5)

    # Byte +50: una marca que 005e97f0 pasa a FUN_004b1ff0 (byte << 21, se
    # guarda en +0xe8 del personaje). NO es el cuerpo: en los jugadores
    # capturados vale 0, 1, 4, 5 o 7 y cambia en el mismo jugador. Va el 5 de
    # nuestra ficha 0x0002.
    b[50] = int(getattr(p, 'cuerpo', 0) or CUERPO_FICHA)

    # EL ASPECTO, tal como lo arma el servidor real. Medido en los 0x0001 de
    # jugadores capturados en el IGG (logs/proxy, 128 B), por ejemplo uno
    # vestido de enfermera:
    #   +64..+92  las 8 ranuras de la tabla 0x8c0904 con el FASHION delante
    #             y, si no hay, el equipo: Kind Nurse Hat, Kind Nurse Uniform
    #             (en la del CUERPO), las jeringas, guantes, zapatos, la
    #             mochila y la MONTURA DE FASHION (Koga Nincat)
    #   +96       el ARMA de verdad (Pan's Rescue, un arco)
    #   +100      la INSIGNIA (Seashell Badge)
    #   +106      0
    # Es la misma regla que la ID Card (lista_personajes.RANURAS_CARD), que si
    # se veia bien. Antes aqui el cuerpo llevaba la armadura y no el fashion,
    # en +96 iba el vestido, en +100 la segunda arma de fashion y en +106 la
    # insignia, y los demas jugadores salian con el cuerpo por defecto.
    bolsa = getattr(ses, 'inventario', None) or {}

    for idx, (r_fash, r_eq) in enumerate(((167, 1), (168, 2), (169, 3), (170, 4),
                                          (171, 5), (172, 6), (173, 7), (174, 10))):
        it = int(bolsa.get(r_fash) or bolsa.get(r_eq) or 0)
        struct.pack_into('<I', b, 64 + idx * 4, it)
    struct.pack_into('<I', b, 96, int(bolsa.get(3) or 0))
    struct.pack_into('<I', b, 100, int(bolsa.get(175) or 0))
    # Burbuja de chat para otros jugadores: Angel.exe 0x5e997b lee dword ptr [packet + 0x6C]
    # (offset 106 en 'b') y lo almacena en la ranura 15 (0xF) del equipo del personaje.
    # Al hablar, Angel.exe (0x4b977a) consulta la ranura 15 para dibujar la burbuja.
    # (El offset 62 NO es la burbuja: es el indicador de circulo de seleccion/aura en el suelo).
    it_burbuja = int(bolsa.get(_inv.RANURA_BURBUJA) or 0)
    struct.pack_into('<I', b, 106, it_burbuja)

    # Estado del personaje (+61): 7 sentado, 0 de pie. El 8 NO es "montado":
    # en 316 jugadores capturados el servidor real no lo usa nunca (0 con o
    # sin montura, 7 sentados), y 005e97f0 lo pasa a FUN_004b4c10(1), que
    # pone una pose de descanso y le borra la forma al personaje.
    b[61] = 7 if getattr(ses, 'sentado', False) else 0

    # Gremio / Liga sobre la cabeza (Angel.exe 0x5e98b0 offset +0x74 en paquete, +0x73 logo):
    try:
        import gremios as _grm_p
        cid_p = getattr(p, 'char_id', 0)
        if cid_p:
            g_p = _grm_p.obtener_gremio_de(cid_p)
            if g_p:
                b[113] = int(g_p.get('logo_id', 0) or 0) & 0xFF
                g_nom = str(g_p.get('nombre', '')).encode('latin-1', 'replace')[:15] + b'\x00'
                b[114:114 + len(g_nom)] = g_nom
    except Exception:
        pass

    return struct.pack('<H', APARECE) + bytes(b)


def _vestir(ses):
    """Lo que se manda DETRAS del 0x0001 para vestir a otro jugador: nada.

    Se probo a mandar los dieciseis 0x001D code=1 (equipar_visual) de cada
    pieza, como al jugador propio, y no servia. En los jugadores capturados
    del IGG el servidor real manda el 0x0001 SOLO -- con el fashion en sus
    ocho ranuras (ver _spawn) -- y el 0x001D de una pieza unicamente cuando
    la cambia; y detras del 0x0001 esos 0x001D podian volver a meter la
    armadura en la ranura del cuerpo encima del vestido de fashion. Cada
    cambio de equipo ya reenvia el 0x0001 entero (notificar_equipo).
    """
    return []


def _despawn(eid):
    import combate as _cb
    return _cb.despawn_monstruo(eid)


def _vivas(stage):
    """Las sesiones de ese mapa que siguen conectadas y con personaje."""
    vivas = []
    for s in _POR_MAPA.get(stage, []):
        if getattr(s, 'personaje', None) is None:
            continue
        if getattr(s, 'cerrada', False):
            continue
        if isinstance(stage, tuple) and stage[0] == 501 and clave_de_mapa(s, 501) != stage:
            continue
        vivas.append(s)
    _POR_MAPA[stage] = vivas
    return vivas


def _mandar(ses, *paquetes):
    paquetes = [p for p in paquetes if p]
    if not paquetes:
        return
    try:
        if hasattr(ses, 'enviar_inmediato'):
            ses.enviar_inmediato(*paquetes)
        else:
            ses.enviar(*paquetes)
    except Exception:
        log.debug('no se pudo mandar a una sesion', exc_info=True)


def clave_de_mapa(ses, stage):
    """Con quien se comparte pantalla en ese mapa.

    Fuera de las instancias, todo el mapa. Dentro, solo los de la misma
    corrida (eventos_mundo._CORRIDAS): el grupo, o uno mismo si va solo. Es
    lo que hacen las copias de instancia del juego (平行空間=15, repartidas
    por grupo): dos grupos en la Magic Kichen Path no se cruzan.
    """
    # Stage 500 is a parallel house space.  Players only share visibility
    # when they are visiting the same owner's house; otherwise every house
    # would leak into the same room.
    if int(stage) == 501:
        import granja_liga
        return granja_liga.clave(ses)
    if int(stage) == 500:
        casa = getattr(ses, 'casa_visitando', None)
        owner_id = getattr(casa, 'owner_id', None)
        if owner_id is None and getattr(ses, 'personaje', None):
            owner_id = getattr(ses.personaje, 'char_id', 0)
        return (500, 'house', int(owner_id or 0))
    try:
        import eventos_mundo as _evm
        if _evm.grupo_de_instancia(stage):
            return (int(stage), _evm._clave_corrida(ses))
    except Exception:
        log.debug('clave de mapa', exc_info=True)
    return stage


_PL_MUNDO = [None]


def _plantilla_mascota_mundo():
    if _PL_MUNDO[0] is None:
        import json as _json
        _PL_MUNDO[0] = bytes.fromhex(_json.loads(
            _inv.PLANTILLA_INI.read_text(encoding='utf-8'))['mascota_mundo'])
    return _PL_MUNDO[0]


def paquetes_mascota(ses_owner) -> list:
    """Paquetes para presentar la mascota activa de ses_owner a otros jugadores.

    En Angel.exe las mascotas NUNCA se spawnean con 0x0008 (_npc_spawn).
    Se spawnean con s2c 0x0050 (entidad_mundo) llevando su sprite real, nombre,
    y el id público del dueño (entidad_de(ses_owner)) junto al enlace 0x001D/0x0013.
    """
    p = getattr(ses_owner, 'personaje', None)
    if not p:
        return []
    f_pet = getattr(p, 'mascota', None)
    pet_eid = getattr(ses_owner, 'pet_entity_id', None)
    if not isinstance(f_pet, dict) or not f_pet.get('fuera') or not pet_eid:
        return []

    import mascotas as _ms
    import combate as _cb

    owner_eid = entidad_de(ses_owner)
    px = f_pet.get('x', getattr(p, 'tile_x', 0) + 1)
    py = f_pet.get('y', getattr(p, 'tile_y', 0))

    est = dict(f_pet)
    est.update({
        'entidad': pet_eid,
        'x': px,
        'y': py,
        'dueno': owner_eid,
        'dueno_nombre': p.nombre,
        'tipo': f_pet.get('tipo', 0),
        'sprite': f_pet.get('sprite', 0),
        'nombre': f_pet.get('nombre', 'Pet'),
    })

    pkts = [
        _ms.entidad_mundo(_plantilla_mascota_mundo(), est),
        _ms.enlazar(owner_eid, pet_eid),
        _cb.atributo(pet_eid, _ms.hp_eff(f_pet), _cb.KIND_HP),
    ]
    if int(f_pet.get('saciedad', 0)) > 100:
        pkts.append(struct.pack('<HIBBII', 0x001D, pet_eid, 1, 4, 3796, max(60000, (int(f_pet['saciedad']) - 100) * 60000)))
    return pkts


def paquetes_invocaciones(ses_owner) -> list:
    """Paquetes de invocaciones y mercenarios activos de ses_owner para otros jugadores."""
    p = getattr(ses_owner, 'personaje', None)
    if not p:
        return []
    import login as _lg
    import combate as _cb
    owner_pub_eid = entidad_de(ses_owner)
    pkts = []
    for inv_key in ('invocacion', 'invocacion2'):
        inv = getattr(ses_owner, inv_key, None)
        if inv and isinstance(inv, dict) and (inv.get('hp', 0) > 0 or inv.get('hp_max', 0) > 0):
            eid = inv.get('entity_id')
            if not eid:
                continue
            npc_t = inv.get('npc_type') or inv.get('npc_tipo', 9999)
            tx = inv.get('tile_x', p.tile_x)
            ty = inv.get('tile_y', p.tile_y)
            sp_pkg = _lg.spawn_invocacion(eid, npc_t, inv.get('nombre', 'Summon'),
                                          (tx, ty), sprite=inv.get('sprite', 0))
            cur_hp = inv.get('hp', inv.get('hp_max', 1))
            max_hp = max(1, inv.get('hp_max', 1))
            hp_pct = max(1, min(100, int(100 * cur_hp / max_hp)))
            hp_pkg = _cb.atributo(eid, hp_pct, _cb.KIND_HP)
            link_owner = struct.pack('<HIBBI', 0x0013, owner_pub_eid, 1, 0x3d, eid)
            link_inv = struct.pack('<HIBBI', 0x0013, eid, 1, 0x3c, owner_pub_eid)
            pkts.extend([sp_pkg, hp_pkg, link_owner, link_inv])
    return pkts


def entrar(ses, stage):
    """El jugador llega a un mapa: se le presenta a los que ya estaban y al
    reves, incluyendo mascotas e invocaciones activas."""
    import combate as _cb
    import login as _lg
    salir(ses, avisar=True)
    stage = clave_de_mapa(ses, stage)
    yo_spawn = _spawn(ses)
    otros = _vivas(stage)
    ts_yo = transform_sprite_de(ses)
    # Con que forma le ven los demas (ver notificar_transformacion).
    ses._forma_publica = int(ts_yo or 0)

    for s in otros:
        if s is ses:
            continue
        # Presentar a 'ses' ante 's'
        _mandar(s, yo_spawn, *_vestir(ses), *paquetes_puesto(ses))
        if ts_yo:
            _mandar(s, _cb.atributo(entidad_de(ses), ts_yo, _cb.KIND_TRANSFORM))

        # Summons / Mercenarios de 'ses' hacia 's'
        _mandar(s, *paquetes_invocaciones(ses))

        # Pet de 'ses' hacia 's' (con 0x0050, nombre y sprite real)
        _mandar(s, *paquetes_mascota(ses))

        # Monstruo encantado de 'ses' hacia 's'
        m_enc_yo = getattr(ses, 'monstruo_encantado', None)
        if m_enc_yo and getattr(m_enc_yo, 'vivo', False) and m_enc_yo.hp > 0:
            m_pkg = _lg._npc_spawn(m_enc_yo.entity_id, m_enc_yo.tipo, m_enc_yo.nombre,
                                   (m_enc_yo.tile_x, m_enc_yo.tile_y), sprite=m_enc_yo.sprite)
            m_hp = _cb.atributo(m_enc_yo.entity_id, m_enc_yo.porcentaje, _cb.KIND_HP)
            _mandar(s, m_pkg, m_hp)

        # Presentar a 's' ante 'ses'
        s_spawn = _spawn(s)
        _mandar(ses, s_spawn, *_vestir(s), *paquetes_puesto(s))
        ts_s = transform_sprite_de(s)
        if ts_s:
            _mandar(ses, _cb.atributo(entidad_de(s), ts_s, _cb.KIND_TRANSFORM))

        # Summons / Mercenarios de 's' hacia 'ses'
        _mandar(ses, *paquetes_invocaciones(s))

        # Pet de 's' hacia 'ses' (con 0x0050, nombre y sprite real)
        _mandar(ses, *paquetes_mascota(s))

        # Monstruo encantado de 's' hacia 'ses'
        m_enc = getattr(s, 'monstruo_encantado', None)
        if m_enc and getattr(m_enc, 'vivo', False) and m_enc.hp > 0:
            m_pkg = _lg._npc_spawn(m_enc.entity_id, m_enc.tipo, m_enc.nombre,
                                   (m_enc.tile_x, m_enc.tile_y), sprite=m_enc.sprite)
            m_hp = _cb.atributo(m_enc.entity_id, m_enc.porcentaje, _cb.KIND_HP)
            _mandar(ses, m_pkg, m_hp)

    if ses not in _POR_MAPA[stage]:
        _POR_MAPA[stage].append(ses)
    ses._mapa_presencia = stage
    # La lista del grupo lleva con que entidad se ve a cada miembro: al
    # cambiar de mapa hay que mandarla de nuevo (equipos._entidad_vista).
    try:
        import equipos as _eq
        _eq.al_cambiar_de_mapa(ses)
    except Exception:
        log.debug('lista del grupo al entrar', exc_info=True)
    if otros:
        log.info('%s entra al mapa %s, donde ya hay %d',
                 getattr(ses.personaje, 'nombre', '?'), stage, len(otros))


def notificar_transformacion(ses, trans_sprite: int):
    """Avisa a todos los demas jugadores del mapa que este jugador cambio de forma."""
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None:
        return
    import combate as _cb
    eid = entidad_de(ses)
    pkt = _cb.atributo(eid, int(trans_sprite or 0), _cb.KIND_TRANSFORM)
    # AL DESTRANSFORMARSE, la ropa otra vez. Medido en las sesiones grabadas
    # del 14/10 (logs/sesiones/*_174146 y *_174156): cada cliente recibia al
    # otro vestido y transformado, y a los pocos segundos el "fin de
    # transformacion" (kind 33 = 0). Con eso el cliente le quita la forma al
    # OTRO jugador pero no le vuelve a poner el equipo, y lo deja con el
    # cuerpo por defecto (el vestido rosa). Solo se arreglaba cuando ese
    # jugador cambiaba algo de equipo y le llegaba otra vez su 0x0001.
    # Y no basta con mandarle otra vez su 0x0001: en la sesion grabada a las
    # 17:46 le llegaron a Karma los 0x0001 de KarmaV3 enteros tras cada fin
    # de transformacion y lo seguia dibujando desnudo. El cliente se queda la
    # "forma" vieja (+0x246/+0x248 del personaje, que solo limpia
    # FUN_004b4c10). Asi que se le borra (0x0007 sin animacion) y se crea de
    # nuevo: una entidad recien creada empieza sin forma.
    #
    # Tampoco basta con borrarla y crearla con el MISMO id: en la sesion de
    # las 18:11 Karma recibio "transformarse -> 42455", "fin" y su 0x0001
    # tras un 0x0007, y siguio en rosa, mientras que a KarmaV3, que nunca se
    # transformo, se le veia vestido con el mismo aspecto. El cliente deja al
    # personaje marcado como transformado (FUN_005fa4e0 le pone entonces el
    # cuerpo por defecto: 0x4e9f/0x4f27/0x4e5a) y, llegando el 0x0007 y el
    # 0x0001 juntos, vuelve a usar el mismo objeto marcado. Asi que al
    # destransformarse se le da a los demas un id publico NUEVO: el viejo se
    # borra y aparece otro personaje, limpio, con su ropa.
    antes = getattr(ses, '_forma_publica', 0)
    ses._forma_publica = int(trans_sprite or 0)
    if not trans_sprite:
        if not antes:
            return        # ya se le veia sin transformar: nada que deshacer
        otros = [s for s in _vivas(stage) if s is not ses]
        if otros:
            for s in otros:
                _mandar(s, _despawn(eid))
            # El nuevo ANTES de soltar el viejo: entidad_de da el primero
            # libre, y soltando antes devolveria el mismo.
            ses._entidad_publica = None
            entidad_de(ses)
            _ENTIDADES_ASIGNADAS.discard(eid)
            sp = _spawn(ses)
            for s in otros:
                if sp:
                    _mandar(s, sp, *_vestir(ses), *paquetes_puesto(ses))
            log.info('%s deja de estar transformado: id publico %s -> %s',
                     getattr(ses.personaje, 'nombre', '?'), eid, entidad_de(ses))
            try:
                import equipos as _eq
                _eq.al_cambiar_de_mapa(ses)     # el retrato, con el id nuevo
            except Exception:
                pass
        return
    for s in _vivas(stage):
        if s is not ses:
            _mandar(s, pkt)


def notificar_equipo(ses):
    """Avisa a todos los demas jugadores del mapa que este jugador cambio de equipo o apariencia."""
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None:
        return
    yo_spawn = _spawn(ses)
    if not yo_spawn:
        return
    ts = transform_sprite_de(ses)
    import combate as _cb
    pkt_trans = _cb.atributo(entidad_de(ses), ts, _cb.KIND_TRANSFORM) if ts else None
    vestir = _vestir(ses)
    puesto = paquetes_puesto(ses)
    for s in _vivas(stage):
        if s is not ses:
            _mandar(s, yo_spawn, *vestir, *puesto)
            if pkt_trans:
                _mandar(s, pkt_trans)


def salir(ses, avisar=True):
    """El jugador deja el mapa (o se desconecta): se le borra de las demas
    pantallas."""
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None:
        liberar_entidad(ses)
        return
    ses._mapa_presencia = None
    lista = _POR_MAPA.get(stage) or []
    if ses in lista:
        lista.remove(ses)
    if avisar:
        fuera = _despawn(entidad_de(ses))
        for s in _vivas(stage):
            if s is not ses:
                _mandar(s, fuera)
    liberar_entidad(ses)


def mover(ses, cur_x, cur_y, dst_x, dst_y, velocidad=50):
    """Reenvia el paso de un jugador a los demas del mapa.

    Las coordenadas van en PIXELES, igual que las manda el cliente en su
    0x0004 y que las espera el 0x0005.
    """
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None:
        return
    otros = [s for s in _vivas(stage) if s is not ses]
    if not otros:
        return
    try:
        import app as _app
        MOVE = _app.Msg.registry[(0x0005, 's2c', '*')]
        paso = MOVE.build(entity_id=entidad_de(ses), cur_x=int(cur_x),
                          cur_y=int(cur_y), dst_x=int(dst_x), dst_y=int(dst_y),
                          speed=int(velocidad) or 50)
    except Exception:
        log.debug('no se pudo armar el paso', exc_info=True)
        return
    for s in otros:
        _mandar(s, paso)


def cuantos(stage) -> int:
    return len(_vivas(stage))


def mapas_con_gente() -> dict:
    return {st: len(_vivas(st)) for st in list(_POR_MAPA) if _vivas(st)}


def paquetes_puesto(ses) -> tuple:
    """Paquetes S2C (0x000A accion 10 + 0x0043 kind 0) que dibujan el cartel del
    puesto de venta (Stall) y su mensaje Hawk sobre un jugador para los demas.

    Segun Angel.exe:
      - FUN_005ecbd0 (0x000A): accion 10 (pkt+0x0A) y estilo 0..6 (pkt+0x0B)
        llama a 0x650870(entity_ptr, estilo, "") que crea el boton flotante
        encima del jugador con su entity_id en appdata.
      - FUN_005f1110 (0x0043): kind 0 (pkt+6) y texto ASCIIZ (pkt+7)
        llama a 0x650af0(entity_ptr, texto) para escribir el Hawk en el cartel.
    """
    pv = getattr(ses, 'puesto', None) or getattr(ses, 'puesto_venta', None)
    if not pv:
        return ()
    eid = entidad_de(ses)
    estilo = pv.get('estilo')
    if estilo is None:
        import inventario as _iv_est
        estilo = _iv_est.estilo_puesto_de(getattr(ses, 'inventario', None))
    estilo = max(0, min(6, int(estilo or 0)))
    hawk = (pv.get('hawk') or '').encode('latin-1', 'replace')[:48]
    pkt_accion = struct.pack('<HIIBBH', 0x000A, eid, 0, 10, estilo, 0)
    pkt_hawk = struct.pack('<HIB', 0x0043, eid, 0) + hawk + b'\x00'
    return (pkt_accion, pkt_hawk)


def notificar_puesto(ses):
    """Avisa a los demas jugadores del mapa que este jugador abrio o actualizo su puesto."""
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None and getattr(ses, 'personaje', None):
        stage = clave_de_mapa(ses, getattr(ses.personaje, 'stage', None))
    if stage is None:
        return
    pkts = paquetes_puesto(ses)
    if not pkts:
        return
    for s in _vivas(stage):
        if s is not ses:
            _mandar(s, *pkts)


def notificar_cierre_puesto(ses):
    """Avisa a los demas jugadores del mapa que este jugador cerro su puesto."""
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None and getattr(ses, 'personaje', None):
        stage = clave_de_mapa(ses, getattr(ses.personaje, 'stage', None))
    if stage is None:
        return
    eid = entidad_de(ses)
    # Accion 0 en 0x000A llama a 0x650a30 -> 0x5bbc90(4, eid), quitando el cartel
    # flotante y cerrando WND_SALE_TRADE si alguien lo estaba mirando.
    pkt_fin = struct.pack('<HIIBBH', 0x000A, eid, 0, 0, 0, 0)
    for s in _vivas(stage):
        if s is not ses:
            _mandar(s, pkt_fin)


def sesion_por_entidad(ses_consulta, eid: int):
    """Busca la sesion de un jugador en el mapa actual por su entidad publica (o propia)."""
    eid = int(eid or 0)
    if not eid:
        return None
    stage = getattr(ses_consulta, '_mapa_presencia', None)
    if stage is None and getattr(ses_consulta, 'personaje', None):
        stage = clave_de_mapa(ses_consulta, getattr(ses_consulta.personaje, 'stage', None))
    candidatos = list(_vivas(stage)) if stage is not None else []
    for st_k in list(_POR_MAPA):
        for s_extra in _vivas(st_k):
            if s_extra not in candidatos:
                candidatos.append(s_extra)
    for s in candidatos:
        if entidad_de(s) == eid:
            return s
        p = getattr(s, 'personaje', None)
        if p and int(getattr(p, 'entity_id', 0) or 0) == eid and (getattr(s, 'puesto', None) or getattr(s, 'puesto_venta', None)):
            return s
    return None


def notificar_invocacion_spawn(ses, inv, spawn_pkg, hp_pkg):
    """Avisa a todos los demas jugadores del mapa que aparecio una invocacion o mercenario."""
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None and getattr(ses, 'personaje', None):
        stage = getattr(ses.personaje, 'stage', None)
    if stage is None or not inv:
        return
    owner_pub_eid = entidad_de(ses)
    eid = inv.get('entity_id') if isinstance(inv, dict) else 0
    link_owner = struct.pack('<HIBBI', 0x0013, owner_pub_eid, 1, 0x3d, eid) if eid else b''
    link_inv = struct.pack('<HIBBI', 0x0013, eid, 1, 0x3c, owner_pub_eid) if eid else b''
    for s in _vivas(stage):
        if s is not ses:
            _mandar(s, spawn_pkg, hp_pkg, link_owner, link_inv)


def notificar_invocacion_movimiento(ses, entity_id, move_pkt):
    """Avisa a todos los demas jugadores del mapa que una invocacion se movio."""
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None and getattr(ses, 'personaje', None):
        stage = getattr(ses.personaje, 'stage', None)
    if stage is None:
        return
    for s in _vivas(stage):
        if s is not ses:
            _mandar(s, move_pkt)


def notificar_invocacion_despawn(ses, entity_id):
    """Avisa a todos los demas jugadores del mapa que una invocacion murio o expiro."""
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None and getattr(ses, 'personaje', None):
        stage = getattr(ses.personaje, 'stage', None)
    if stage is None:
        return
    import combate as _cb
    pkt_despawn = _cb.despawn_monstruo(entity_id)
    pkt_hp = _cb.atributo(entity_id, 0, _cb.KIND_HP)
    for s in _vivas(stage):
        if s is not ses:
            _mandar(s, pkt_hp, pkt_despawn)


def notificar_mascota_spawn(ses, pet_eid=None, sprite=None, tx=None, ty=None):
    """Avisa a todos los demas jugadores del mapa que salio o cambio una mascota."""
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None and getattr(ses, 'personaje', None):
        stage = getattr(ses.personaje, 'stage', None)
    if stage is None:
        return
    pkts = paquetes_mascota(ses)
    if not pkts:
        return
    for s in _vivas(stage):
        if s is not ses:
            _mandar(s, *pkts)


def notificar_mascota_movimiento(ses, pet_eid, move_pkt):
    """Avisa a todos los demas jugadores del mapa que una mascota se movio."""
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None and getattr(ses, 'personaje', None):
        stage = getattr(ses.personaje, 'stage', None)
    if stage is None:
        return
    for s in _vivas(stage):
        if s is not ses:
            _mandar(s, move_pkt)


def notificar_companero_accion(ses, *paquetes):
    """Replica ataques/skills de pets, mercenarios e invocaciones en el mapa.

    Spawn y movimiento ya se compartian, pero sus 0x000A/0x0011 solo se
    enviaban al dueno; para los demas la criatura se acercaba al monstruo y
    quedaba inmovil, sin ataque, efecto ni cambio de HP visible.
    """
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None and getattr(ses, 'personaje', None):
        stage = clave_de_mapa(ses, getattr(ses.personaje, 'stage', None))
    if stage is None:
        return
    limpios = tuple(p for p in paquetes if p)
    if not limpios:
        return
    for s in _vivas(stage):
        if s is not ses:
            _mandar(s, *limpios)


def notificar_mascota_despawn(ses, pet_eid):
    """Avisa a todos los demas jugadores del mapa que se guardo la mascota."""
    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None and getattr(ses, 'personaje', None):
        stage = getattr(ses.personaje, 'stage', None)
    if stage is None:
        return
    import mascotas as _ms
    import combate as _cb
    owner_eid = entidad_de(ses)
    pkt_despawn = _ms.quitar(pet_eid)
    pkt_unlink = _ms.enlazar(owner_eid, 0)
    pkt_hp = _cb.atributo(pet_eid, 0, _cb.VIDA)
    for s in _vivas(stage):
        if s is not ses:
            _mandar(s, pkt_hp, pkt_unlink, pkt_despawn)


def notificar_emocion(ses, emote_id: int):
    """Envia S2C 0x0019 con el emote al jugador y a los demas en el mapa."""
    p = getattr(ses, 'personaje', None)
    if not p:
        return
    emo = int(emote_id) & 0xFF
    # Paquete para el propio jugador (usa su entity_id de ficha 0x0002)
    eid_propio = getattr(p, 'entity_id', None)
    if eid_propio is not None:
        pkt_propio = struct.pack('<HIB', 0x0019, int(eid_propio), emo)
        ses.enviar(pkt_propio)

    stage = getattr(ses, '_mapa_presencia', None)
    if stage is None and p:
        stage = clave_de_mapa(ses, getattr(p, 'stage', None))
    if stage is not None:
        eid_pub = entidad_de(ses)
        pkt_pub = struct.pack('<HIB', 0x0019, int(eid_pub), emo)
        for s in _vivas(stage):
            if s is not ses:
                _mandar(s, pkt_pub)


def notificar_emocion_entidad(stage, entity_id: int, emote_id: int):
    """Envia S2C 0x0019 con el emote para cualquier entidad (NPC, monstruo) a todos en el mapa."""
    if stage is None:
        return
    pkt = struct.pack('<HIB', 0x0019, int(entity_id), int(emote_id) & 0xFF)
    for s in _vivas(stage):
        _mandar(s, pkt)


def paquete_emotes_desbloqueados(emotes) -> bytes:
    """Construye S2C 0x005C con el array de 37 bytes de emotes comprados/desbloqueados (12..48).

    En Angel.exe FUN_006094a0 lee [opcode 0x005C][37 bytes] y almacena cada byte
    en m_bEmotBuy[i] (offset 0x240 + i, que en game.getemotbuy(i - 1) se consulta
    sumando el indice a 0x234). Luego invoca Lua CreateEmotionWndUpdate() para
    refrescar la lista de la ventana si esta abierta.
    """
    emotes_set = set(emotes or [])
    flags = bytearray(37)
    for i in range(37):
        if (12 + i) in emotes_set:
            flags[i] = 1
    return struct.pack('<H', 0x005C) + bytes(flags)


def paquete_quick_emotes(entity_id: int, quick_emotes: dict) -> bytes:
    """Construye S2C 0x001D con las 4 ranuras de emotes rapidos (Alt+1..Alt+4).

    En Angel.exe FUN_005f0ef0 maneja 0x001D. Para kind=6 llama a FUN_005ffc70,
    que guarda [this + slot*4 + 0x5dd8] = emote_id (o -1 / 0xFFFFFFFF si esta vacio).
    """
    items = []
    for slot in range(4):
        emo = quick_emotes.get(slot, -1)
        if emo is None or emo < 0:
            emo_val = 0xFFFFFFFF
        else:
            emo_val = int(emo) & 0xFFFF
        items.append(struct.pack('<BII', 6, slot, emo_val))
    return struct.pack('<HIB', 0x001D, int(entity_id), 4) + b''.join(items)



