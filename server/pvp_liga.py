"""Combate dirigido entre jugadores durante Totem War, nunca en zonas seguras."""
import logging
import struct
import cuentas

log = logging.getLogger('pvp')


def objetivo(ses, eid):
    import presencia
    p = getattr(ses, 'personaje', None)
    if not p:
        return None
    for otro in presencia._vivas(presencia.clave_de_mapa(ses, p.stage)):
        if otro is not ses and presencia.entidad_de(otro) == int(eid):
            return otro
    return None


def permitido(ses, otro):
    motivo = _por_que_no(ses, otro)
    if motivo:
        log.info('PvP rechazado: %s -> %s: %s',
                 getattr(getattr(ses, 'personaje', None), 'nombre', '?'),
                 getattr(getattr(otro, 'personaje', None), 'nombre', '?'), motivo)
    return not motivo


def _por_que_no(ses, otro):
    """'' si `ses` puede pegarle a `otro`; si no, el motivo (para el log)."""
    import presencia, totem_war, gremios
    p, q = getattr(ses, 'personaje', None), getattr(otro, 'personaje', None)
    if not p or not q or ses is otro or p.stage != q.stage:
        return 'no estan en el mismo mapa'
    if not totem_war.activa() or not totem_war.es_mapa_tw(p.stage):
        return 'sin Totem War o fuera de la arena'
    if presencia.clave_de_mapa(ses, p.stage) != presencia.clave_de_mapa(otro, q.stage):
        return 'salas distintas'
    if getattr(ses, 'muerto', False) or getattr(otro, 'muerto', False) or p.hp <= 0 or q.hp <= 0:
        return 'alguno esta muerto'
    if totem_war.codigo_faccion(p) == totem_war.codigo_faccion(q):
        return 'misma faccion'
    a, b = gremios.obtener_gremio_de(p.char_id), gremios.obtener_gremio_de(q.char_id)
    if a and b and a['guild_id'] == b['guild_id']:
        return 'misma liga'
    return ''


def rivales_en_area(ses, cx, cy, radio):
    """Los jugadores a los que `ses` puede pegar dentro del area (cx, cy, radio)."""
    import presencia
    p = getattr(ses, 'personaje', None)
    if not p:
        return []
    salida = []
    for otro in presencia._vivas(presencia.clave_de_mapa(ses, p.stage)):
        q = getattr(otro, 'personaje', None)
        if (otro is not ses and q is not None
                and max(abs(q.tile_x - int(cx)), abs(q.tile_y - int(cy))) <= int(radio)
                and not _por_que_no(ses, otro)):
            salida.append(otro)
    return salida


def atacar(ses, otro, tipo, mag, arma, en_area=False):
    """Llamar despues de validar la cadencia/cooldown general en app.

    Con `en_area` es un golpe de habilidad de AREA: el alcance y el coste ya
    los cobro la habilidad (el rival esta dentro del radio), asi que no se
    miran ni se cobran otra vez. Antes las de area solo buscaban monstruos y
    a los jugadores no les llegaba nada (log del 20/10: Dimension Shift)."""
    import app, combate, presencia, skills, transitable
    if not permitido(ses, otro):
        return False
    p, q = ses.personaje, otro.personaje
    if tipo != combate.ATAQUE_NORMAL and not mag.get('es_ataque') and not en_area:
        return False
    if not en_area:
        alcance = combate.alcance_arma(arma) if tipo == combate.ATAQUE_NORMAL else max(1, mag.get('rango', 1))
        if max(abs(p.tile_x-q.tile_x), abs(p.tile_y-q.tile_y)) > alcance+1:
            return False
        if not transitable.linea_libre(p.stage, (p.tile_x,p.tile_y), (q.tile_x,q.tile_y)):
            return False
        mp, sp = int(mag.get('mp') or 0), int(mag.get('cost_sp') or 0)
        if p.mp < mp or int(getattr(ses, 'sp', 0) or 0) < sp:
            return False
        p.mp -= mp
        ses.sp = int(getattr(ses, 'sp', 0) or 0) - sp
        p.sp = ses.sp
    st, defensa = app._stats_ses(ses), app._stats_ses(otro)
    magia = tipo != combate.ATAQUE_NORMAL and skills.skill_de_magia(tipo) in (1,2,3,4)
    atk = struct.unpack_from('<I', st, 46 if magia else 26)[0]
    dfs = struct.unpack_from('<I', defensa, 50 if magia else 38)[0]
    if magia:
        atk = int(atk * (float(mag.get('dano_base') or 200) / float(mag.get('base_denom') or 200)))
    elif tipo != combate.ATAQUE_NORMAL:
        atk += int(round(combate.stance_de(tipo) * combate.PESO_STANCE))
    dano = combate.dano_recibido(atk, dfs)
    q.hp = max(0, q.hp-dano)
    apub, bpub = presencia.entidad_de(ses), presencia.entidad_de(otro)
    visibles = presencia._vivas(presencia.clave_de_mapa(ses, p.stage))
    for visor in visibles:
        a = p.entity_id if visor is ses else apub
        b = q.entity_id if visor is otro else bpub
        pkts = [combate.ataque(a, b), combate.numero_flotante(b, dano),
                combate.atributo(b, q.hp, combate.KIND_HP)]
        if not q.hp:
            if visor is otro:
                # La victima muere como cuando la mata un monstruo (app, IA de
                # monstruos): ataque con TIPO_MUERTE sobre si misma y HP 0.
                # Con el 0x0008 de muerte de monstruo su cliente no pasaba a
                # muerto ni ofrecia revivir.
                pkts += [combate.ataque(b, a, 0, combate.TIPO_MUERTE),
                         combate.atributo(b, 0, combate.KIND_HP)]
            else:
                pkts.append(combate.muerte_monstruo(b, a))
        mandar = getattr(visor, 'enviar_sin_espejo', visor.enviar)
        mandar(*pkts)
    ses.enviar(combate.atributo(p.entity_id, p.mp, combate.KIND_MP),
               combate.atributo(p.entity_id, ses.sp, combate.KIND_SP))
    if not q.hp:
        otro.muerto = True
        otro.objetivo_actual = None
        _contar_baja(ses, p)
        if getattr(otro, 'usuario', None):
            cuentas._actualizar_personaje(otro.usuario, q.char_id,
                lambda d: d.update(pvp_deaths=int(d.get('pvp_deaths', 0))+1))
    if getattr(otro, 'usuario', None):
        cuentas.guardar_progreso(otro.usuario, q.char_id, q.nivel, q.exp, q.hp, q.mp)
    if getattr(ses, 'usuario', None):
        cuentas.guardar_progreso(ses.usuario, p.char_id, p.nivel, p.exp, p.hp, p.mp, sp=ses.sp)
    return True


def _contar_baja(ses, p):
    """La baja: marcador K.O. (0x001D codigo 25) y creditos de rango."""
    import combate, clases, totem_war
    try:
        ronda = totem_war._RONDA.get(p.char_id, 0) + 1
        totem_war._RONDA[p.char_id] = ronda
        total = [int(getattr(p, 'pvp_kills', 0) or 0) + 1]
        if getattr(ses, 'usuario', None):
            def _sumar(d):
                d['pvp_kills'] = int(d.get('pvp_kills', 0) or 0) + 1
                d['tw_kills'] = int(d.get('tw_kills', 0) or 0) + 1
                total[0] = d['pvp_kills']
            cuentas._actualizar_personaje(ses.usuario, p.char_id, _sumar)
        total = total[0]
        p.pvp_kills = total
        p.creditos = int(getattr(p, 'creditos', 0) or 0) + totem_war.CREDITOS_POR_BAJA
        nuevo_rango = combate.rango_de_creditos(p.creditos)
        pkts = [totem_war.kills_ko(p.entity_id, ronda, total),
                combate.atributo(p.entity_id, p.creditos, combate.KIND_CREDITO),
                clases.aviso(str(totem_war.CREDITOS_POR_BAJA), tipo=0, msg_id=642)]
        if nuevo_rango > int(getattr(p, 'rango', 1) or 1):
            p.rango = nuevo_rango
            pkts += [combate.atributo(p.entity_id, p.rango, combate.KIND_RANGO),
                     combate.efecto_level_up(p.entity_id, es_rango=True)]
        ses.enviar(*pkts)
        if getattr(ses, 'usuario', None):
            cuentas.guardar_rango(ses.usuario, p.char_id, p.rango, p.creditos)
        log.info('PvP: %s lleva %d bajas en la ronda (%d en total), +%d creditos',
                 p.nombre, ronda, total, totem_war.CREDITOS_POR_BAJA)
    except Exception:
        log.exception('PvP: no se pudo contar la baja')
