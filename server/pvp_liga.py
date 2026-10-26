"""Player combat: timed wars, competitions and permanent Outpost faction PvP."""
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
    if presencia.clave_de_mapa(ses, p.stage) != presencia.clave_de_mapa(otro, q.stage):
        return 'salas distintas'
    import competiciones
    competition_reason = competiciones.motivo_pvp(ses, otro)
    if competition_reason is not None:
        return competition_reason
    daily_reason=__import__('daily_events').motivo_pvp(ses,otro)
    if daily_reason is not None:return daily_reason
    gvg_reason=__import__('league_war').motivo_pvp(ses,otro)
    if gvg_reason is not None:return gvg_reason
    import outpost_pvp
    if not outpost_pvp.es_mapa(p.stage) and (not totem_war.activa() or not totem_war.es_mapa_tw(p.stage)):
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


def _multiplicador(ses, tipo, mag, magia):
    """(mult, var_pct) del golpe, con las MISMAS reglas que el ataque a
    monstruos de app: poder del hechizo, 1.2/1.35 de las fisicas, 傷害係數,
    % del equipo y % de los buffs. Sin el critico."""
    import combate, inventario
    p = ses.personaje
    mult, var_pct = 1.0, 0.03
    if magia:
        base = float(mag.get('dano_base') or 0)
        denom = float(mag.get('base_denom') or 200) or 200.0
        mult = base / denom if base > 0 else 1.0
        var_pct = 0.05
        if mag.get('dano_var'):
            var_pct = min(0.15, max(0.02, float(mag['dano_var']) / denom))
        if mag.get('dano_coef'):
            mult *= float(mag['dano_coef']) / 100.0
    elif tipo != combate.ATAQUE_NORMAL:
        combo = combate.combo_de(tipo)
        mult = 1.2 if (combo and combo.get('golpes', 1) > 1) else 1.35
        if mag.get('dano_coef'):
            mult *= float(mag['dano_coef']) / 100.0
    mods = inventario.modificadores_porcentuales_equipo(getattr(ses, 'inventario', None) or {})
    pct = mods.get('mag_dmg_pct' if magia else 'phys_dmg_pct', 0)
    if pct > 0:
        mult *= 1.0 + pct / 100.0
    pct_b = combate.pct_dano_buffs(getattr(p, 'buffs', None), magia)
    if pct_b:
        mult *= 1.0 + pct_b / 100.0
    return mult, var_pct


def _prob_critico(ses):
    import time, app
    extra = 0
    for b in (getattr(ses.personaje, 'buffs', None) or {}).values():
        if isinstance(b, dict) and b.get('fin', 0) > time.time() and 'crit' in b:
            extra += b['crit']
    return min(0.90, (app.critico_jugador(ses) + extra) / 100.0)


# Ajuste global del dano entre jugadores (1.0 = como contra un monstruo de esa
# defensa). Sin datos del oficial; si en PvP se muere demasiado rapido, bajarlo.
FACTOR_PVP = 1.0


def dano_pvp(atk, defensa, mult, var_pct):
    """Formula de AO entre jugadores: (ATAQUE - DEFENSA) x multiplicador.

    La defensa se resta ANTES de multiplicar por la habilidad. Con la de los
    monstruos (multiplicar y luego restar) una magia de x8 con Spl Atk
    101.435 contra 102.735 de Spl Dfs seguia haciendo ~700.000: se cargaba a
    un Archer de 233.000 de vida de un golpe (20/10/2026). Si la defensa
    supera al ataque queda la mitigacion suave 420/(DEF+420), que es un
    rasguno, como debe ser entre stats parecidas."""
    import random
    defensa = max(0, int(defensa))
    atk = max(0, int(atk))
    mult = float(mult) * FACTOR_PVP
    resta = (atk - defensa) * mult
    suave = atk * mult * (420.0 / (defensa + 420.0) if defensa > 0 else 1.0)
    base = max(1.0, resta, suave)
    return max(1, int(round(base * (1.0 + random.uniform(-var_pct, var_pct)))))


def mitigacion(otro, magia):
    """Lo que deja pasar la victima (0..1): la mitigacion del equipo
    (phys/mag_mit_mult) y la de sus buffs activos ('mit' / 'mag_mit', el
    物理/魔法傷害抵銷 de magic.xml), igual que cuando le pega un monstruo
    (app, IA de monstruos). En PvP no se miraba ninguna de las dos."""
    import time, inventario
    factor = 1.0
    mods = inventario.modificadores_porcentuales_equipo(getattr(otro, 'inventario', None) or {})
    mult = mods.get('mag_mit_mult' if magia else 'phys_mit_mult', 1.0)
    if 0 < mult < 1.0:
        factor *= mult
    ahora = time.time()
    clave = 'mag_mit' if magia else 'mit'
    for b in (getattr(getattr(otro, 'personaje', None), 'buffs', None) or {}).values():
        if isinstance(b, dict) and b.get('fin', 0) > ahora and b.get(clave):
            factor *= max(0.0, 1.0 - float(b[clave]) / 100.0)
    return factor


def atacar(ses, otro, tipo, mag, arma, en_area=False, golpes=None, separacion=None):
    """Llamar despues de validar la cadencia/cooldown general en app.

    Con `en_area` es un golpe de habilidad de AREA: el alcance y el coste ya
    los cobro la habilidad (el rival esta dentro del radio), asi que no se
    miran ni se cobran otra vez, y la animacion ya la puso la habilidad.

    LOS COMBOS PEGAN TODOS SUS GOLPES (combate.combo_de), cada uno con su
    critico, como contra monstruos; antes en PvP solo salia el primero.
    `golpes` y `separacion` los fija quien llama (las AoE de combo)."""
    import asyncio, random
    import app, combate, skills, transitable
    if not permitido(ses, otro):
        return False
    p, q = ses.personaje, otro.personaje
    if tipo != combate.ATAQUE_NORMAL and not mag.get('es_ataque') and not en_area:
        return False
    if tipo != combate.ATAQUE_NORMAL and mag.get('no_jugadores'):
        return False          # 不能對玩家施放 de magic.xml
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
    magia = tipo != combate.ATAQUE_NORMAL and skills.skill_de_magia(tipo) in (1,2,3,4)
    atk = struct.unpack_from('<I', app._stats_ses(ses), 46 if magia else 26)[0]
    dfs = struct.unpack_from('<I', app._stats_ses(otro), 54 if magia else 38)[0]
    if not magia and tipo != combate.ATAQUE_NORMAL:
        atk += int(round(combate.stance_de(tipo) * combate.PESO_STANCE))
    mult, var_pct = _multiplicador(ses, tipo, mag, magia)
    crit = _prob_critico(ses)
    combo = combate.combo_de(tipo) if tipo != combate.ATAQUE_NORMAL else None
    n = max(1, int(golpes)) if golpes is not None else (combo['golpes'] if combo else 1)
    sep = separacion if separacion is not None else max(0.05, (combo or {}).get('intervalo_ms', 200) / 1000.0)
    efecto = combate.efecto_de_ataque(tipo) if tipo != combate.ATAQUE_NORMAL else 0

    vida_objetivo = getattr(otro, 'competicion_vida', 0)
    def _golpe(primero=False):
        if getattr(otro, 'competicion_vida', 0) != vida_objetivo:
            return  # No transferir el resto del combo a su nueva vida/respawn.
        if not permitido(ses, otro):
            return
        es_crit = random.random() < crit
        dano = dano_pvp(atk, dfs, mult * (1.5 if es_crit else 1.0), var_pct)
        dano = max(1, int(round(dano * mitigacion(otro, magia))))
        _aplicar(ses, otro, dano, es_crit, primero and not en_area, tipo, efecto, magia)

    _golpe(primero=True)
    if n > 1:
        try:
            bucle = asyncio.get_event_loop()
            for k in range(1, n):
                bucle.call_later(sep * k, _golpe)
        except RuntimeError:
            pass
    if not en_area:
        ses.enviar(combate.atributo(p.entity_id, p.mp, combate.KIND_MP),
                   combate.atributo(p.entity_id, ses.sp, combate.KIND_SP))
        if getattr(ses, 'usuario', None):
            cuentas.guardar_progreso(ses.usuario, p.char_id, p.nivel, p.exp, p.hp, p.mp, sp=ses.sp)
    return True


def _aplicar(ses, otro, dano, es_crit, con_efecto, tipo, efecto, magia, *, origen_eid=None):
    """Un golpe ya calculado: vida, paquetes a todos los que lo ven y muerte."""
    import combate, presencia
    p, q = ses.personaje, otro.personaje
    dano = __import__('avatar_clones').absorber(otro,dano)
    q.hp = max(0, q.hp - dano)
    apub, bpub = presencia.entidad_de(ses), presencia.entidad_de(otro)
    visibles = presencia._vivas(presencia.clave_de_mapa(ses, p.stage))
    tipo_num = combate.TIPO_DANO_CRITICO if es_crit else combate.TIPO_DANO
    for visor in visibles:
        a = origen_eid if origen_eid is not None else (p.entity_id if visor is ses else apub)
        b = q.entity_id if visor is otro else bpub
        pkts = []
        if con_efecto and efecto:
            # El efecto de la habilidad sobre el rival, UNA vez por uso.
            pkts += [combate.numero_de_dano(a, b, dano, tipo, efecto=efecto, cast_time=0, es_magia=magia),
                     combate.cierre_de_dano(a, b, tipo, efecto=efecto, es_magia=magia)]
        elif con_efecto:
            pkts.append(combate.ataque(a, b))
        pkts += [combate.numero_flotante(b, dano, tipo_num),
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
        mandar = getattr(visor, 'enviar_sin_espejo', None) or visor.enviar
        try:
            mandar(*pkts)
            if hasattr(visor, 'volcar'):
                visor.volcar()
        except Exception:
            pass
    if not q.hp:
        otro.muerto = True
        otro.objetivo_actual = None
        import competiciones
        if p.stage in competiciones.MAPAS:
            competiciones.baja(ses, otro)
            return  # no recompensas de Totem War ni penalizacion de EXP
        if p.stage in __import__('daily_events').STAGES:
            __import__('daily_events').baja(ses,otro)
            return
        if p.stage in __import__('league_war').STAGES:
            __import__('league_war').kill(ses,otro)
            return
        import outpost_pvp
        if not outpost_pvp.es_mapa(p.stage):
            _contar_baja(ses, p)  # Outpost is not a source of TW credits/round kills.
        try:
            import app as _app_l
            _app_l._logros_contar(otro, 'muertes')
        except Exception:
            log.exception('logros: muerte PvP')
        if getattr(otro, 'usuario', None):
            cuentas._actualizar_personaje(otro.usuario, q.char_id,
                lambda d: d.update(pvp_deaths=int(d.get('pvp_deaths', 0))+1))
    if getattr(otro, 'usuario', None):
        cuentas.guardar_progreso(otro.usuario, q.char_id, q.nivel, q.exp, q.hp, q.mp)


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
