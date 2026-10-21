"""Acciones de Farm: reglas de string.xml 3164..3167 y crops.xml.

Los importes de EXP heredados NO estan confirmados como tabla oficial.
Las cuotas y el historial se persisten; reiniciar/reconectar no los restablece.
"""
import asyncio
import datetime
import time
import struct
import functools
import cuentas
_PROGRAMADOS = set()


def refrescar_cultivo(ses, cultivo, actualizar_tierra=False):
    """Reconstruye la representacion sin borrar ni resembrar el cultivo.

    La tierra y la planta son entidades distintas en el mismo punto. Si cambia
    la tierra, se inserta PRIMERO y la planta DESPUES, como al entrar a Farm.
    005b85d0 reutiliza entidades existentes sin cambiar su secuencia: para
    actualizar el sprite hay que retirar la entidad antes de recrearla.

    No usar S2C0010 con efectos SP_CLASS_MAGIC (50076/50077): la prueba real
    produjo artefactos. Queda pendiente validar su transporte, no sus nombres.
    """
    import combate, granja_liga as farm
    plot = int(cultivo['plot_id'])
    eid = farm.CROP_BASE_EID + plot
    ahora = time.time()
    pkts = [combate.despawn_monstruo(eid)]
    if actualizar_tierra:
        pkts.extend((combate.despawn_monstruo(farm.PARCELA_BASE_EID + plot),
                     farm.paquete_tierra(plot, mojada=cultivo['riego_count'] > 0)))
    pkts.extend((farm.paquete_cultivo(
        eid, cultivo['crop_id'], cultivo['char_name'], farm.coordenadas_de_parcela(plot),
        farm.sprite_de_etapa(cultivo['crop_id'], cultivo['sembrado_en'], cultivo['madura_en'], ahora),
        maduro=ahora >= cultivo['madura_en']), paquete_estado_cultivo(cultivo)))
    difundir(ses, *pkts)


@functools.lru_cache(maxsize=None)
def semilla_de_cultivo(crop_id):
    import inventario, pathlib, sqlite3
    con = sqlite3.connect(pathlib.Path(__file__).resolve().parent.parent / 'corpus/content.db')
    try:
        for tabla in inventario.TABLAS_ITEM:
            row = con.execute('SELECT id FROM %s WHERE "物品類別"=? AND "動態資料1"=? LIMIT 1' % tabla,
                              ('農場種子', str(int(crop_id)))).fetchone()
            if row:
                return int(row[0])
    finally:
        con.close()
    return 0


def paquete_estado_cultivo(c):
    """S2C015F, REA005f6a20/005d47e0. Identificador de parcela1..70."""
    con = cuentas._get_conn()
    try:
        _tabla(con)
        secure = bool(con.execute('SELECT 1 FROM liga_farm_acciones WHERE plot_id=? AND sembrado_en=? '
                                  'AND char_id=? AND accion=\'secure\' LIMIT 1',
                                  (c['plot_id'], c['sembrado_en'], c['char_id'])).fetchone())
    finally:
        con.close()
    return struct.pack('<H8IBBB', 0x015F, c['plot_id'], c['char_id'], semilla_de_cultivo(c['crop_id']),
                       max(0, c['madura_en']-int(time.time())), max(0, c['marchita_en']-int(time.time())),
                       c['abono_count'], c['riego_count'], c['cosechado_count'], int(secure), 0, 0)


def paquete_cuotas(ses):
    dia = datetime.date.today().isoformat()
    con = cuentas._get_conn()
    try:
        _tabla(con)
        rows = dict(con.execute('SELECT accion,COUNT(*) FROM liga_farm_acciones '
                                'WHERE char_id=? AND dia=? GROUP BY accion', (ses.personaje.char_id, dia)))
    finally:
        con.close()
    return struct.pack('<HB6I', 0x0160, 0, rows.get('fertilize', 0), rows.get('water', 0),
                       rows.get('harvest', 0)+rows.get('secure', 0), 5, 5, 5)


def _tabla(con):
    con.execute('CREATE TABLE IF NOT EXISTS liga_farm_acciones ('
                'guild_id INTEGER, plot_id INTEGER, sembrado_en INTEGER, '
                'char_id INTEGER, dia TEXT, accion TEXT, cantidad INTEGER DEFAULT 1)')


def difundir(ses, *pkts):
    import granja_liga as farm
    if getattr(getattr(ses, 'personaje', None), 'stage', None) != farm.STAGE:
        return
    if not farm.liga_autorizada(ses):
        return
    ses.enviar(*pkts)
    sala = getattr(ses, '_sala', None)
    for otro in list(getattr(sala, 'sesiones', ())):
        if (otro is not ses and not getattr(otro, 'cerrada', False)
                and farm.clave(otro) == farm.clave(ses)
                and getattr(getattr(otro, 'personaje', None), 'stage', None) == farm.STAGE):
            getattr(otro, 'enviar_sin_espejo', otro.enviar)(*pkts)


def _seleccion(ses, entity_id):
    import granja_liga as farm
    p = getattr(ses, 'personaje', None)
    g = farm.liga_autorizada(ses) if p else None
    if not g or int(p.stage) != farm.STAGE or getattr(ses, 'muerto', False):
        return None
    plot = int(entity_id)
    if plot >= farm.CROP_BASE_EID:
        plot = farm.parcela_de_entidad(plot) or 0
    if plot not in farm.PARCELAS_CULTIVO:
        return None
    xy = farm.coordenadas_de_parcela(plot)
    if not xy:
        return None
    if max(abs(p.tile_x-xy[0]), abs(p.tile_y-xy[1])) > farm.RADIO_INTERACCION:
        _avisar(ses, 'Move closer to the crop to water, fertilize or harvest it.')
        return None
    c = cuentas.db_obtener_cultivo(g['guild_id'], plot)
    return (g, c) if c and farm.info_cultivo(c['crop_id']) else None


def _avisar(ses, texto):
    import clases
    ses.enviar(clases.aviso(texto, tipo=0))


def _experiencia(ses, exp=0, skill=0):
    """exp / skill son FRACCIONES de lo que pide el nivel (ver recompensa)."""
    import clases, combate, app, struct
    p = ses.personaje
    if exp:
        exp = max(1, int((combate.exp_para_nivel(p.nivel + 1) - combate.exp_para_nivel(p.nivel)) * exp))
        p.exp = max(int(p.exp or 0), combate.exp_para_nivel(p.nivel)) + int(exp)
        while p.nivel < combate.nivel_maximo() and p.exp >= combate.exp_para_nivel(p.nivel+1):
            p.nivel += 1
            p.hp_max += 25
            p.mp_max += 15
            ses.enviar(combate.atributo(p.entity_id, p.nivel, 29),
                       combate.efecto_level_up(p.entity_id))
        # A nivel alto el porcentaje pasa de 4.294 millones y el 0x000B (u32)
        # reventaba con struct.error: el riego no daba nada (20/10/2026).
        # La barra va por el 0x001D de 64 bits (29 nivel, 30 base, 31
        # siguiente, 32 actual), como en las recompensas de mision.
        actual, siguiente = combate.exp_para_barra(p.nivel, p.exp)
        ses.enviar(struct.pack('<HIB', 0x001D, p.entity_id, 4)
                   + struct.pack('<BQ', 29, p.nivel)
                   + struct.pack('<BQ', 30, combate.exp_para_nivel(p.nivel))
                   + struct.pack('<BQ', 31, siguiente) + struct.pack('<BQ', 32, actual))
        if int(exp) <= 0xFFFFFFFF:
            ses.enviar(combate.exp_paquete(p.entity_id, int(exp)))
        else:
            ses.enviar(clases.aviso(str(int(exp)), tipo=0, msg_id=clases.MSG_EXP))
    if skill:
        nuevas = []
        for sid, nivel, puntos in p.habilidades or []:
            ganado = max(1, int(clases.exp_requerida_skill(nivel, sid) * skill))
            puntos += ganado
            tope = p.nivel + 11 if sid in range(20, 32) else p.nivel
            while nivel < tope and puntos >= max(1, clases.exp_requerida_skill(nivel, sid)):
                puntos -= max(1, clases.exp_requerida_skill(nivel, sid))
                nivel += 1
            puntos = min(puntos, max(1, clases.exp_requerida_skill(nivel, sid)))
            nuevas.append((sid, nivel, puntos))
            ses.enviar(clases.aviso_doble(clases.MSG_SKILL_EXP, clases.nombre(sid), str(ganado)))
        p.habilidades = nuevas
        ses.enviar(clases.arbol(nuevas))
    if getattr(ses, 'usuario', None):
        cuentas.guardar_progreso(ses.usuario, p.char_id, p.nivel, p.exp, p.hp, p.mp, p.habilidades)


def accion(ses, entity_id, nombre):
    import granja_liga as farm
    seleccion = _seleccion(ses, entity_id)
    if not seleccion:
        return False
    g, c = seleccion
    now = int(time.time())
    if now >= c['marchita_en']:
        _avisar(ses, 'The produce has withered.')
        return False
    if nombre != 'harvest' and now >= c['madura_en']:
        _avisar(ses, 'This produce has already ripened.')
        return False
    if nombre == 'harvest' and now < c['madura_en']:
        _avisar(ses, 'The produce is still growing.')
        return False
    info = farm.info_cultivo(c['crop_id'])
    gid, cid, plot = int(g['guild_id']), int(ses.personaje.char_id), c['plot_id']
    dia = datetime.date.today().isoformat()
    premio = None
    # Serializar cuota, reserva del propietario y contadores del cultivo.
    with cuentas._LOCK:
        con = cuentas._get_conn()
        try:
            con.execute('BEGIN IMMEDIATE')
            _tabla(con)
            n = con.execute('SELECT COUNT(*) FROM liga_farm_acciones WHERE char_id=? AND dia=? '
                            'AND (accion=? OR (?=\'harvest\' AND accion=\'secure\'))',
                            (cid, dia, nombre, nombre)).fetchone()[0]
            if n >= 5:
                _avisar(ses, 'You have reached your daily farm action limit (5).')
                return False
            columna, limite = {'water': ('riego_count', int(info.get('澆水次數') or 0)),
                               'fertilize': ('abono_count', int(info.get('施肥次數') or 0)),
                               'harvest': ('cosechado_count', max(0, int(info.get('總採收量') or 0)
                                                              - int(info.get('保障採收量') or 0)))}[nombre]
            cont = con.execute('SELECT %s FROM liga_granja_cultivos WHERE guild_id=? AND plot_id=?' % columna,
                               (gid, plot)).fetchone()
            if not cont:
                return False
            especial = 'secure' if nombre == 'harvest' and cid == c['char_id'] else nombre
            previo = con.execute('SELECT COUNT(*) FROM liga_farm_acciones WHERE guild_id=? AND plot_id=? '
                                 'AND sembrado_en=? AND char_id=? AND accion=?',
                                 (gid, plot, c['sembrado_en'], cid, especial)).fetchone()[0]
            if nombre == 'harvest' and previo:
                if especial == 'secure':
                    especial = 'harvest'
                    previo = con.execute('SELECT COUNT(*) FROM liga_farm_acciones WHERE guild_id=? AND plot_id=? '
                                         'AND sembrado_en=? AND char_id=? AND accion=?',
                                         (gid, plot, c['sembrado_en'], cid, especial)).fetchone()[0]
                if previo:
                    _avisar(ses, 'You have already harvested this produce.')
                    return False
            if cont[0] >= limite and especial != 'secure':
                _avisar(ses, 'This produce has reached its action limit.')
                return False
            if nombre == 'harvest':
                import bolsas, app
                dinamico = int(info.get('收成動態資料') or 0)
                premio = bolsas._sorteo(dinamico) if info.get('收成類別') == '紅包' else (dinamico, 1)
                if not premio or not premio[0]:
                    _avisar(ses, 'The harvest reward table is unavailable; your crop has been preserved.')
                    return False
                cantidad = int(info.get('保障採收量') or 1) if especial == 'secure' else 1
                ranura = app._meter(ses, premio[0], premio[1] * cantidad)
                if ranura is None:
                    _avisar(ses, 'Inventory is full; your crop has been preserved.')
                    return False
            if especial != 'secure':
                con.execute('UPDATE liga_granja_cultivos SET %s=%s+1 WHERE guild_id=? AND plot_id=?' %
                            (columna, columna), (gid, plot))
            con.execute('INSERT INTO liga_farm_acciones (guild_id,plot_id,sembrado_en,char_id,dia,accion) '
                        'VALUES (?,?,?,?,?,?)', (gid, plot, c['sembrado_en'], cid, dia, especial))
            con.commit()
        finally:
            con.close()
    if premio:
        ses.enviar(*app._refrescar(ses, [ranura]))
        app._guardar_bolsa(ses, cid)
    actualizado = cuentas.db_obtener_cultivo(gid, plot)
    if actualizado:
        refrescar_cultivo(ses, actualizado, actualizar_tierra=nombre == 'water')
    ses.enviar(paquete_cuotas(ses))
    # string.xml 3165/3166 (la ayuda de la granja): Regar da [EXP], Abonar da
    # [Skill EXP] y Cosechar da [EXP and Skill EXP] mas el producto, "segun el
    # agua y el abono que lleve". Los importes no salen en ningun xml: base
    # heredada + un plus por cada riego / abono que tenga el cultivo.
    _experiencia(ses, *recompensa(nombre, ses.personaje.nivel, actualizado or c))
    _avisar(ses, {'water': 'Watered successfully.', 'fertilize': 'Fertilized successfully.',
                 'harvest': 'Harvest successful!'}[nombre])
    import app as _app_fm
    _app_fm._pase_evento(ses, {'water': '澆水農作物類', 'fertilize': '施肥農作物類',
                               'harvest': '採收農作物類'}[nombre])
    return True


# La curva de EXP es exponencial (nivel 10 pide 2.375; nivel 100, 360
# millones), asi que una cifra fija no sirve: se da un PORCENTAJE de lo que pide
# el nivel actual. La Skill EXP igual, de lo que pide cada habilidad en el suyo.
EXP_REGAR = 0.02             # 2% del nivel por riego
SKILL_ABONAR = 0.10          # 10% de cada habilidad por abono
EXP_COSECHA, EXP_POR_RIEGO = 0.05, 0.01
SKILL_COSECHA, SKILL_POR_ABONO = 0.15, 0.02


def recompensa(nombre, nivel, cultivo):
    """(fraccion de EXP del nivel, fraccion de Skill EXP de cada habilidad)."""
    if nombre == 'water':
        return EXP_REGAR, 0
    if nombre == 'fertilize':
        return 0, SKILL_ABONAR
    riegos = int((cultivo or {}).get('riego_count') or 0)
    abonos = int((cultivo or {}).get('abono_count') or 0)
    return EXP_COSECHA + EXP_POR_RIEGO * riegos, SKILL_COSECHA + SKILL_POR_ABONO * abonos


def programar_cultivo(ses, plot, crop, sembrado, madura, marchita):
    import granja_liga as farm
    g = farm.liga_autorizada(ses)
    if not g:
        return
    key = (int(g['guild_id']), plot, sembrado)
    if key in _PROGRAMADOS:
        return
    _PROGRAMADOS.add(key)
    sala = farm.sala(ses)
    def actualizar(borrar=False):
        c = cuentas.db_obtener_cultivo(g['guild_id'], plot)
        if not c or c['sembrado_en'] != sembrado:
            return
        import combate
        eid = farm.CROP_BASE_EID + plot
        if borrar:
            cuentas.db_eliminar_cultivo(g['guild_id'], plot)
            _PROGRAMADOS.discard(key)
        receptores = [s for s in getattr(sala, 'sesiones', ())
                      if getattr(getattr(s, 'personaje', None), 'stage', None) == farm.STAGE
                      and farm.clave(s) == (farm.STAGE, 'league', key[0])]
        if not receptores:
            return
        receptor = receptores[0]
        if borrar:
            # Marchito: fuera el cultivo; la tierra (su propia entidad) sigue.
            difundir(receptor, combate.despawn_monstruo(eid),
                     combate.despawn_monstruo(farm.PARCELA_BASE_EID + int(plot)),
                     farm.paquete_tierra(plot))
        else:
            ahora = time.time() + 0.5
            difundir(receptor, combate.despawn_monstruo(eid), farm.paquete_cultivo(
                eid, crop, c['char_name'], farm.coordenadas_de_parcela(plot),
                farm.sprite_de_etapa(crop, sembrado, madura, ahora), maduro=ahora >= madura),
                paquete_estado_cultivo(c))
    try:
        loop = asyncio.get_running_loop()
        for t in [t for t in farm.cambios_de_etapa(sembrado, madura) if t > time.time()]:
            loop.call_later(max(0, t-time.time()), actualizar)
        loop.call_later(max(0, marchita-time.time()), lambda: actualizar(True))
    except RuntimeError:
        _PROGRAMADOS.discard(key)
        pass


def invocar_plagas(ses, cantidad=1):
    """Monstruo oficial 9845; aviso solo para los miembros de esta granja.

    No se fija una frecuencia automatica inventada: el evento puede invocarlo
    el control de granja. No es un BC ni consume Broadcasting.
    """
    import combate, granja_liga as farm, login, totem_war
    g = farm.liga_autorizada(ses)
    if not g or ses.personaje.stage != farm.STAGE:
        return False
    sala = farm.sala(ses)
    if sala.monstruos is None:
        sala.monstruos = {}
    cultivos = [c for c in cuentas.db_obtener_cultivos_gremio(g['guild_id']) if c['marchita_en'] > time.time()]
    if not cultivos:
        return False
    pkts = [totem_war.cartel_deslizante('Farm Pests have appeared! Protect your crops!', 'Farm')]
    for c in cultivos[:max(1, min(int(cantidad), 10))]:
        eid = 70_800_000 + int(c['plot_id'])
        if eid in sala.monstruos and sala.monstruos[eid].vivo:
            continue
        tile = farm.coordenadas_de_parcela(c['plot_id'])
        m = combate.Monstruo(eid, 9845, 'Farm Pests', tile, sprite=43405, stage=farm.STAGE)
        m.generado = True
        sala.monstruos[eid] = m
        pkts.append(login._monster_spawn(eid, 9845, m.nombre, tile, sprite=43405))
    difundir(ses, *pkts)
    return True
