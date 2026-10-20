"""Enchufa el interprete de eventos al mundo: estado del mapa y contexto.

QUE HACE FALTA PARA EJECUTAR UN EVENTO. server/eventos.py sabe leer la logica
pero no sabe nada del mundo: pregunta por un Contexto y devuelve efectos.
Aqui esta la mitad que mira: de donde sale cada respuesta y donde se apunta
lo que el mapa va cambiando.

LO QUE MAS CUESTA ES GENERATOR_ALIVE, y es justo el que abre las instancias.
En los mapas la mecanica es casi siempre la misma:

    mapa 73, evento 150:  si GENERATOR_ALIVE(218, =, 0)
                          entonces CHANGE_STATICOBJ(118, 60037)

o sea "cuando la zona 218 se queda sin bichos, pon el objeto 60037 en el TAG
118", que en el mapa 73 es la casilla (119,177): la puerta que se abre al
limpiar la sala. El problema es que las plantillas de monstruos no guardan a
que generador pertenece cada bicho -- se generaron a partir de ellos, pero el
dato no viajo --, y volver a generarlas pisaria las que vinieron de capturas.

Asi que la relacion se reconstruye por posicion, que es como se creo. El TAG
de la zona trae sus casillas, y poblar_del_cliente reparte los monstruos en
un anillo de radio 3 alrededor con 5 de separacion; con eso, un bicho es de
la zona cuya casilla mas cercana este a RADIO o menos de su casilla DE
APARICION. Se usa la de aparicion y no la actual a proposito: los monstruos
pasean, y uno que se haya alejado seguiria contando en su zona, que es lo que
el evento quiere saber.

EL ESTADO DEL MAPA NO ES DEL MAPA, ES DE LA SESION. Mientras los monstruos
sean por sesion -- cada jugador ve los suyos -- las variables, los
temporizadores y las puertas tambien tienen que serlo, o un jugador abriria
la puerta del otro. Cuando el mundo pase a ser compartido, esto se mueve a
una sola instancia por mapa y el resto no cambia.

LOS EVENTOS DE DISPARO 0 son los que nadie dispara: se comprueban solos. Son
53 y son los que llevan las mecanicas de instancia. Por eso hay
`pendientes()`, que los repasa, y una marca de los que ya saltaron para no
repetir la puerta en cada paso.
"""
import logging

import eventos as ev

log = logging.getLogger(__name__)

# Cuanto se aleja un monstruo de su zona al nacer. poblar_del_cliente usa un
# anillo de radio 3; se deja uno mas de margen y no mas, porque las zonas de
# una misma instancia estan a pocas casillas y pasarse mezclaria dos salas.
RADIO_ZONA = 4

# Las condiciones que este contexto puede contestar de verdad. Lo que no
# este aqui sale como "no se sabe" y su disparador no salta.
SABE = frozenset((
    32,     # IS_PVP_ON (Totem War)
    75,     # SPEC_MAP_OWN_ALIGNMENT
    77,     # PVP_IS_GUARD_OWNER
    2,      # QUEST_STEP
    6,      # BAGITEM
    7,      # QUESTITEM (ranuras ocultas 497..556)
    8,      # EMPTYSLOT_COUNT
    10,     # PROB100
    11,     # QUEST_FINISH
    12,     # ALIGNMENT
    13,     # QUEST_RUNNING
    14,     # GENERATOR_ALIVE
    17,     # MONEY
    29,     # MAPVAR
    30,     # TIMER_ENABLE   (los temporizadores ya corren: app._arrancar_temporizador)
    31,     # TIMER_COUNTER
    39,     # GROUP
    48,     # TEAMID
    21,     # HAVE_GUILD
    28,     # HAVE_GUILD_REGION
    33,     # GUILD_PERM
    34,     # GUILD_LEVEL
    76,     # SPEC_MAP_OWN_GUILD
    82,     # GUILD_MEMBER_TIME
    56,     # IS_LIVE
    3,      # PROPERTY (solo nivel y rango)
    4,      # SKILL_LEVEL: las puertas rojas y la de magia de Gulp Room 2
    5,      # EQUIPITEM
    58,     # HOUSE_IS_OWNER
    59,     # HOUSE_LEVEL
    60,     # DISCO_PARTY
    61,     # COMPOUND_BUFF
    62,     # HOUSE_HAVE_VOTE
    63,     # HOUSE_NEATNESS
    64,     # HOUSE_OWNER_AT_HOME
    65,     # HOUSE_OWNER_PARTNER
    70,     # HOUSE_SIZE
))

# Las ranuras ocultas donde misiones.py ya pone los contadores de caceria.
# No ocupan mochila y el cliente las muestra en el HUD.
OCULTA_PRIMERA, OCULTA_ULTIMA = 497, 556

# La mochila empieza en la 20; de 0 a 19 va el equipo.
BOLSA_PRIMERA = 20
BOLSA_ULTIMA = 199

# Lo que contesta paso_de_mision cuando el personaje NO lleva esa mision.
# No puede ser 0, que es el primer paso en la numeracion del cliente.
PASO_SIN_MISION = -1

# Los codigos de ALIGNMENT del eventdef (1 聖光, 2 大地, 3 鋼鐵, 4 暗影, 5 天國)
# con los NOMBRES que guarda el servidor, que son los de la ficha
# (login.CODIGO_FACCION): Aurora, Beasts, Steel, Shadow, Heaven. Solo con
# Holy/Earth, un personaje de Aurora o de Beasts salia como faccion 0 y no
# cumplia ninguna condicion de faccion de los mapas.
_FACCIONES = {'Aurora': 1, 'Holy': 1, 'Beasts': 2, 'Earth': 2, 'Steel': 3,
              'Shadow': 4, 'Heaven': 5, 'Graduated': 5, 'Neutral': 5,
              'Neutrally': 5}


class EstadoDeMapa:
    """Lo que el mapa va cambiando mientras se juega.

    Vive colgado de la sesion y se tira al cambiar de mapa, que es lo que
    hace que entrar de nuevo en una instancia la encuentre cerrada otra vez.
    """

    def __init__(self, stage):
        self.stage = stage
        self.variables = {}          # (mapa, var) -> valor
        self.temporizadores = {}     # tag -> [activo, veces]
        self.objetos = {}            # tag -> id de objeto puesto
        self.ya_saltaron = set()     # eventos de disparo 0 que ya se hicieron
        # Solo en las instancias: los bichos de la sala, COMPARTIDOS por todos
        # los de la corrida que esten en ella (el mismo dict es su
        # ses.monstruos), y quienes estan dentro ahora mismo.
        self.monstruos = None
        self.sesiones = []
        self.por_restaurar = False
        self._zonas = None

    # -- a que zona de generador pertenece una casilla --------------------
    def _indice_de_zonas(self):
        """casilla -> TAG de la zona, construido una vez por mapa.

        Se guarda la zona MAS CERCANA, no la primera que toque, porque las
        zonas de una instancia estan pegadas y la primera que apareciera
        dependeria del orden del json.
        """
        if self._zonas is not None:
            return self._zonas
        self._zonas = {}
        d = ev.del_stage(self.stage) or {}
        mejor = {}
        for tag, g in (d.get('generadores') or {}).items():
            t = int(tag)
            for px, py in g['puntos']:
                for dx in range(-RADIO_ZONA, RADIO_ZONA + 1):
                    for dy in range(-RADIO_ZONA, RADIO_ZONA + 1):
                        dist = max(abs(dx), abs(dy))
                        c = (px + dx, py + dy)
                        if c not in mejor or dist < mejor[c][0]:
                            mejor[c] = (dist, t)
        self._zonas = {c: t for c, (_d, t) in mejor.items()}
        return self._zonas

    def zona_de(self, tile):
        return self._indice_de_zonas().get((int(tile[0]), int(tile[1])))

    def vivos_por_zona(self, monstruos):
        """TAG de zona -> cuantos bichos siguen vivos en ella."""
        cuenta = {}
        for m in (monstruos or {}).values():
            if not getattr(m, 'vivo', False):
                continue
            # La zona apuntada en la plantilla manda (tools/zonas_de_plantilla.py);
            # 0 = de la plantilla y sin zona. Si no hay, por cercania, como siempre.
            z = getattr(m, 'zona_plantilla', None)
            if z is None:
                z = self.zona_de(getattr(m, 'spawn_tile', None)
                                 or (getattr(m, 'spawn_x', 0), getattr(m, 'spawn_y', 0)))
            elif z == 0:
                z = None
            if z is not None:
                cuenta[z] = cuenta.get(z, 0) + 1
        return cuenta

    # -- variables de mapa ------------------------------------------------
    def variable(self, mapa, var):
        return int(self.variables.get((int(mapa), int(var)), 0))

    def poner_variable(self, mapa, var, valor):
        self.variables[(int(mapa), int(var))] = int(valor)

    def sumar_variable(self, mapa, var, valor):
        self.variables[(int(mapa), int(var))] = self.variable(mapa, var) + int(valor)

    # -- temporizadores ---------------------------------------------------
    def temporizador(self, tag):
        return self.temporizadores.setdefault(int(tag), [False, 0])


# LAS INSTANCIAS RECUERDAN LO HECHO mientras dure la "corrida": puertas
# abiertas, antorchas encendidas, bichos muertos que no vuelven, variables.
# Asi lo describio el usuario, jugando en el oficial:
#   * solo: mientras sigas dentro de la instancia (pasar de la sala 2 a la 1
#     de la Magic Kichen Path no la reinicia); al salir de ella, se reinicia;
#   * en grupo: se mantiene aunque salgas, hasta que el grupo se deshace, y es
#     la misma para todos los del grupo.
# Una instancia son todas sus salas: las que comparten nombre en
# instancias.json (Magic Kichen Path = 73, 74 y 75) mas las que se unen por
# portales entre salas de instancia.
_CORRIDAS = {}          # ('solo', char_id) | ('equipo', lider) -> corrida
_GRUPOS_INSTANCIA = None


def grupo_de_instancia(stage):
    """Las salas (stages) de la instancia a la que pertenece ese mapa, o None."""
    global _GRUPOS_INSTANCIA
    if _GRUPOS_INSTANCIA is None:
        import json
        import pathlib
        base = pathlib.Path(__file__).parent / 'plantillas'
        try:
            mapas = json.loads((base / 'instancias.json').read_text(encoding='utf-8')).get('mapas') or {}
        except Exception:
            mapas = {}
        dinamicas = {int(k): v.get('nombre') for k, v in mapas.items() if v.get('dinamica')}
        padre = {s: s for s in dinamicas}

        def raiz(s):
            while padre[s] != s:
                padre[s] = padre[padre[s]]
                s = padre[s]
            return s

        def unir(a, b):
            padre[raiz(a)] = raiz(b)
        por_nombre = {}
        for s, n in dinamicas.items():
            if n:
                if n in por_nombre:
                    unir(s, por_nombre[n])
                por_nombre.setdefault(n, s)
        try:
            portales = json.loads((base / 'portales.json').read_text(encoding='utf-8')).get('mapas') or {}
        except Exception:
            portales = {}
        for origen, lista in portales.items():
            for p in lista or []:
                o, d = int(origen), p.get('destino')
                if d is not None and o in padre and int(d) in padre and o != int(d):
                    unir(o, int(d))
        grupos = {}
        for s in dinamicas:
            grupos.setdefault(raiz(s), set()).add(s)
        _GRUPOS_INSTANCIA = {s: frozenset(g) for g in grupos.values() for s in g}
    return _GRUPOS_INSTANCIA.get(int(stage or 0))


def _clave_corrida(ses):
    try:
        import equipos as _eq
        cid = _eq._char_id(ses)
        lider = _eq._DE_QUIEN.get(cid)
        if lider and lider in _eq._GRUPOS:
            return ('equipo', lider)
    except Exception:
        cid = int(getattr(getattr(ses, 'personaje', None), 'char_id', 0) or 0)
    return ('solo', cid)


def _olvidar_corridas_de_grupos_deshechos():
    try:
        import equipos as _eq
    except Exception:
        return
    for k in [k for k in _CORRIDAS if k[0] == 'equipo' and k[1] not in _eq._GRUPOS]:
        _CORRIDAS.pop(k, None)


def corrida_de(ses, grupo):
    """La corrida de esa sesion en esa instancia, creandola si hace falta."""
    _olvidar_corridas_de_grupos_deshechos()
    clave = _clave_corrida(ses)
    c = _CORRIDAS.get(clave)
    if c is None and clave[0] == 'equipo':
        # Iba solo y acaba de formar grupo dentro: se lleva lo que llevaba.
        solo = ('solo', int(getattr(getattr(ses, 'personaje', None), 'char_id', 0) or 0))
        if _CORRIDAS.get(solo, {}).get('grupo') == grupo:
            c = _CORRIDAS[clave] = _CORRIDAS.pop(solo)
    if c is None or c['grupo'] != grupo:
        c = _CORRIDAS[clave] = {'grupo': grupo, 'estados': {}}
    return c


def estado_de(ses):
    """El estado del mapa en el que esta la sesion, creandolo si hace falta.

    Fuera de las instancias se rehace al cambiar de stage sin que nadie
    tenga que acordarse de limpiarlo: la comprobacion es el propio numero de
    mapa. En una instancia sale de su corrida (ver _CORRIDAS), y la marca
    `por_restaurar` le dice al 0x0009 que el cliente acaba de recibir el
    mapa limpio y hay que volver a ponerle lo hecho.
    """
    stage = getattr(getattr(ses, 'personaje', None), 'stage', 0) or 0
    if stage == 501:
        import granja_liga
        return granja_liga.sala(ses)
    e = getattr(ses, 'estado_mapa', None)
    if e is not None and e.stage == stage:
        return e
    grupo = grupo_de_instancia(stage)
    if grupo:
        c = corrida_de(ses, grupo)
        e = c['estados'].get(stage)
        if e is None:
            e = c['estados'][stage] = EstadoDeMapa(stage)
        else:
            e.por_restaurar = True
    else:
        clave = _clave_corrida(ses)
        if clave[0] == 'solo':
            _CORRIDAS.pop(clave, None)
        e = EstadoDeMapa(stage)
    ses.estado_mapa = e
    return e


class ContextoSesion(ev.Contexto):
    """Contesta las condiciones mirando la sesion de verdad."""

    sabe = SABE

    def __init__(self, ses, estado=None):
        self.ses = ses
        self.p = getattr(ses, 'personaje', None)
        self.estado = estado if estado is not None else estado_de(ses)
        self.stage = self.estado.stage
        self.casilla = (getattr(self.p, 'tile_x', 0) or 0,
                        getattr(self.p, 'tile_y', 0) or 0)
        self.es_alma = bool(getattr(ses, 'muerto', False))
        self._vivos = None
        self._deltas_mision = {}
        self._deltas_bolsa = {}
        self._pasos_mision = {}
        self._deltas_vars = {}

    # -- misiones ---------------------------------------------------------
    def paso_de_mision(self, quest):
        """El paso EN LA NUMERACION DEL CLIENTE, que no es la del servidor.

        Esto es un desajuste de los que rompen todo sin hacer ruido. El
        servidor guarda el primer paso como 1 y lo manda por red como 0:
        misiones.avanzar_paso hace `paso_red = nuevo_paso - 1` y lo dice en
        un comentario. Los eventos del cliente usan la numeracion DE RED:
        el drop del Mushroom de The Reivers pide QUEST_STEP(502, 0) y eso
        es el primer paso, el que el jugador ve como "1." en su diario.

        Si se compararan sin convertir, ninguna condicion de mision casaria
        nunca y los disparadores no saltarian jamas -- que es exactamente
        como se veia: la mision aceptada y el objeto sin caer.
        """
        if int(quest) in self._pasos_mision:
            return self._pasos_mision[int(quest)]
        if not self.p:
            return PASO_SIN_MISION
        for q, pa in (getattr(self.p, 'quests', None) or []):
            if q == quest:
                return max(0, int(pa) - 1)
        # No tenerla no es ir por el primer paso, asi que tiene que ser un
        # valor que no case con ningun QUEST_STEP.
        return PASO_SIN_MISION

    def mision_terminada(self, quest):
        try:
            import misiones as _mis
            return bool(_mis.mision_completada(self.p, quest))
        except Exception:
            return False

    def mision_en_curso(self, quest):
        return self.paso_de_mision(quest) >= 0 and not self.mision_terminada(quest)

    # -- objetos ----------------------------------------------------------
    def _contar(self, item, desde, hasta):
        if not self.p:
            return 0
        inv = getattr(self.p, 'inventario', None) or {}
        cant = getattr(self.p, 'cantidades', None) or {}
        total = 0
        for ranura, iid in inv.items():
            r = int(ranura)
            if desde <= r <= hasta and int(iid) == int(item):
                total += max(1, int(cant.get(r, cant.get(str(r), 1))))
        return total

    def en_bolsa(self, item):
        return max(0, self._contar(item, BOLSA_PRIMERA, BOLSA_ULTIMA)
                     + self._deltas_bolsa.get(int(item), 0))

    def objeto_de_mision(self, item):
        delta = self._deltas_mision.get(int(item), 0)
        c = self._contar(item, OCULTA_PRIMERA, OCULTA_ULTIMA)
        if c > 0 or delta != 0:
            return max(0, c + delta)
        if self.p:
            qk = getattr(self.p, 'quest_kills', None) or {}
            for q, pa in (getattr(self.p, 'quests', None) or []):
                k = f"{q}_{pa}"
                try:
                    import misiones as _mis
                    _mis._cargar_db()
                    c_data = getattr(_mis, '_CACERIAS', {}).get(k, {})
                    if c_data.get('token_id') == int(item) or (int(item) == 16075 and q == 142):
                        return max(0, int(qk.get(k, 0)) + delta)
                except Exception:
                    pass
        return max(0, delta)

    def equipado(self, item):
        # De 0 a 19 va el equipo puesto.
        return self._contar(item, 0, BOLSA_PRIMERA - 1)

    def nivel_de_skill(self, skill):
        # habilidades = [(rama, nivel, exp)]; la rama es la de skills.NOMBRE_RAMA,
        # la misma numeracion que el SKILL_LEVEL del eventdef (9 Sword, 10 Axe,
        # 11 Spear, 17 Longbow; 1 Life, 2 Wraith, 3 Chaos, 4 Earth).
        for h in (getattr(self.p, 'habilidades', None) or []):
            try:
                if int(h[0]) == int(skill):
                    return int(h[1])
            except (TypeError, ValueError, IndexError):
                continue
        return 0

    def huecos_libres(self):
        if not self.p:
            return 0
        inv = getattr(self.p, 'inventario', None) or {}
        usadas = sum(1 for r in inv if BOLSA_PRIMERA <= int(r) <= BOLSA_ULTIMA)
        return max(0, (BOLSA_ULTIMA - BOLSA_PRIMERA + 1) - usadas)

    def oro(self):
        return int(getattr(self.p, 'oro', 0) or 0)

    # -- personaje --------------------------------------------------------
    def nivel(self):
        return int(getattr(self.p, 'nivel', 0) or 0)

    def rango(self):
        return int(getattr(self.p, 'rango', 0) or 0)

    def faccion(self):
        f = getattr(self.p, 'faction', None)
        return _FACCIONES.get(f, 0) if isinstance(f, str) else int(f or 0)

    def vivo(self):
        return not self.es_alma

    # -- mapa -------------------------------------------------------------
    def vivos_del_generador(self, tag):
        if self._vivos is None:
            self._vivos = self.estado.vivos_por_zona(
                getattr(self.ses, 'monstruos', None))
        return int(self._vivos.get(int(tag), 0))

    def variable_de_mapa(self, mapa, var):
        k = (int(mapa), int(var))
        if k in self._deltas_vars:
            return self._deltas_vars[k]
        return self.estado.variable(mapa, var)

    def temporizador_activo(self, tag):
        return bool(self.estado.temporizador(tag)[0])

    def veces_del_temporizador(self, tag):
        return int(self.estado.temporizador(tag)[1])

    # -- grupo ------------------------------------------------------------
    def miembros_del_grupo(self, que=0):
        if que != 0:
            return 0       # cuantos chicos o chicas: todavia no se sabe
        try:
            import equipos as _eq
            n = _eq.cuantos(self.ses)
            return max(1, int(n or 1))
        except Exception:
            return 1

    def teamid(self):
        try:
            import equipos as _eq
            return _eq.lider_de(self.ses)
        except Exception:
            return 0

    def tiene_guild(self):
        if not self.p:
            return False
        try:
            import gremios as _grm
            return bool(_grm.obtener_gremio_de(self.p.char_id))
        except Exception:
            return False

    def nivel_liga(self):
        import gremios
        g = gremios.obtener_gremio_de(self.p.char_id) if self.p else None
        return int(g['nivel']) if g else 0

    def permiso_liga(self, permiso):
        import gremios
        g = gremios.obtener_gremio_de(self.p.char_id) if self.p else None
        return bool(g and gremios._tiene_permiso(g, self.p.char_id, permiso))

    def tiene_region_liga(self):
        """Condicion 28: HAVE_GUILD_REGION(). Si la liga del jugador posee algun territorio."""
        if not self.p:
            return False
        try:
            import gremios as _grm
            g = _grm.obtener_gremio_de(self.p.char_id)
            if not g:
                return False
            import cuentas as _cta
            return _cta.db_gremio_tiene_territorio(g['guild_id'])
        except Exception:
            return False

    def liga_posee_territorio(self, tw_stage):
        """Condicion 76: SPEC_MAP_OWN_GUILD(tw_stage). Si la liga del jugador posee ese campo de batalla."""
        if not self.p:
            return False
        try:
            import gremios as _grm
            g = _grm.obtener_gremio_de(self.p.char_id)
            if not g:
                return False
            import cuentas as _cta
            dueno = _cta.db_obtener_dueno_de_territorio(tw_stage)
            return dueno == g['guild_id']
        except Exception:
            return False

    def antiguedad_en_liga(self):
        """Condicion 82: segundos que el personaje lleva como miembro de su liga."""
        if not self.p:
            return 0
        try:
            import cuentas as _cta
            return _cta.db_antiguedad_miembro_gremio(self.p.char_id)
        except Exception:
            return 0

    # -- casas ------------------------------------------------------------
    def _obtener_casa_actual(self):
        cv = getattr(self.ses, 'casa_visitando', None)
        if cv:
            return cv
        if self.p:
            try:
                import casas as _cas
                return _cas.obtener_o_crear_casa(
                    self.p.char_id, self.p.nombre,
                    raw_data=getattr(self.p, 'casa', None))
            except Exception:
                return None
        return None

    def es_dueno_casa(self):
        c = self._obtener_casa_actual()
        if not c or not self.p:
            return False
        return int(getattr(c, 'owner_id', 0)) == int(getattr(self.p, 'char_id', 0))

    def nivel_casa(self):
        c = self._obtener_casa_actual()
        if not c:
            return 1
        try:
            import casas as _cas
            return _cas.nivel_de_magia(c.calcular_magia())
        except Exception:
            return 1

    def casa_disco_party(self):
        c = self._obtener_casa_actual()
        return bool(c and getattr(c, 'ball_active', False))

    def casa_puede_buff_diario(self):
        c = self._obtener_casa_actual()
        if not c or not self.p:
            return False
        import time
        hoy = time.strftime('%Y-%m-%d')
        ultimo = getattr(self.p, 'ultimo_house_buff', None)
        return ultimo != hoy

    def casa_tiene_voto(self):
        c = self._obtener_casa_actual()
        if not c or not self.p:
            return False
        c.check_daily_reset()
        cid = int(getattr(self.p, 'char_id', 0))
        return cid not in c.voted_users_today

    def casa_limpieza(self):
        c = self._obtener_casa_actual()
        return int(getattr(c, 'cleanliness', 1000) if c else 1000)

    def casa_dueno_en_casa(self):
        c = self._obtener_casa_actual()
        if not c:
            return False
        owner_id = int(getattr(c, 'owner_id', 0))
        if self.p and int(getattr(self.p, 'char_id', 0)) == owner_id:
            return True
        return False

    def casa_es_pareja(self):
        return False

    def casa_tamano(self):
        c = self._obtener_casa_actual()
        return int(getattr(c, 'size_level', 0) if c else 0)

    # -- aplicacion local de efectos durante la ejecucion de un evento ----
    def aplicar_efecto_local(self, ef):
        que = ef[0]
        if que == 'dar':
            for item, cant in ef[1]:
                iid = int(item)
                self._deltas_mision[iid] = self._deltas_mision.get(iid, 0) + int(cant)
                self._deltas_bolsa[iid] = self._deltas_bolsa.get(iid, 0) + int(cant)
        elif que == 'quitar':
            for item, cant in ef[1]:
                iid = int(item)
                self._deltas_mision[iid] = self._deltas_mision.get(iid, 0) - int(cant)
                self._deltas_bolsa[iid] = self._deltas_bolsa.get(iid, 0) - int(cant)
        elif que == 'paso':
            self._pasos_mision[int(ef[1])] = int(ef[2])
        elif que == 'variable':
            op = ef[1]
            mapa, var, val = int(ef[2]), int(ef[3]), int(ef[4])
            k = (mapa, var)
            curr = self.variable_de_mapa(mapa, var)
            if op == 'poner':
                self._deltas_vars[k] = val
            elif op == 'sumar':
                self._deltas_vars[k] = curr + val
            elif op == 'restar':
                self._deltas_vars[k] = curr - val


# PUERTAS QUE EL SERVIDOR ABRE SIN LA MISION QUE PIDEN. Decision del usuario
# (14/10/2026): no quiere que la instancia se corte por una mision.
#   (74, 61101) la puerta de la cara de demonio de la sala 2 de la Magic
#     Kichen Path (64967 "There is a huge metal gate carved with a cruel
#     Devil's face..."). El mapa solo la abre con la Main Angel Quest (611)
#     en el paso 2 con el item 4594, o en el 3-4. Abrirla es
#     CHANGE_STATICOBJ(153, 60295), lo mismo que hacen esos disparadores.
# (stage, evento) -> (efectos que se anaden, dialogos que se quitan)
SIN_MISION = {
    (74, 61101): ([('objeto_estatico', 153, 60295)], {61100}),
    # El TRONO de Sunshine Palace (286,168) a Mystic Space (132). En el
    # cliente pide la mision 988 en el paso 2 o 3, o hecha; si no, dice
    # "It seems that it has been sealed by some unknown magic" (98801).
    # Pedido del usuario (15/10/2026): que deje pasar. Restaurar con la otra.
    (131, 2): ([('viajar', 132, 1)], {98801}),
}


# PUERTAS QUE SE ABREN PARA SIEMPRE. En el oficial la mision se pide SOLO la
# primera vez: cuando el personaje pasa con ella, la puerta le queda abierta y
# despues entra y sale sin la mision (lo conto el usuario, que lo tiene hecho
# en otra cuenta). Por puerta: (efecto de pasar, dialogos de "cerrado").
PERMISO_UNA_VEZ = {
    (74, 61101): (('objeto_estatico', 153, 60295), {61100}),
    (131, 2): (('viajar', 132, 1), {98801}),
}


def _permiso_una_vez(ses, stage, evento, efectos):
    clave = (int(stage), int(evento))
    puerta = PERMISO_UNA_VEZ.get(clave)
    p = getattr(ses, 'personaje', None)
    if not puerta or p is None:
        return efectos
    pasar, cerrado = puerta
    marca = '%d:%d' % clave
    permisos = getattr(p, 'permisos', None)
    if permisos is None:
        permisos = p.permisos = []
    if pasar in efectos:
        # Pasa con la mision: se le apunta la puerta para siempre.
        if marca not in permisos:
            permisos.append(marca)
            try:
                import cuentas
                cuentas.guardar_sistemas(getattr(ses, 'usuario', None), p.char_id, p)
            except Exception:
                log.exception('no se pudo guardar el permiso %s', marca)
        return efectos
    if marca in permisos:
        efectos = [e for e in efectos if not (e[0] == 'dialogo' and int(e[1]) in cerrado)]
        efectos.append(pasar)
    return efectos


def _sin_mision(stage, evento, efectos):
    extra = SIN_MISION.get((int(stage), int(evento)))
    if not extra:
        return efectos
    poner, quitar = extra
    efectos = [e for e in efectos if not (e[0] == 'dialogo' and int(e[1]) in quitar)]
    for e in poner:
        if e not in efectos:
            efectos.append(e)
    return efectos


def al_pisar(ses, tile, solo_chocar=False):
    """Los efectos de pisar una casilla. Lista vacia si ahi no hay nada.

    Con `solo_chocar` (el objeto esta AL LADO, no debajo) solo valen los
    disparadores de chocar: los de pisar piden estar encima."""
    estado = estado_de(ses)
    evento = ev.evento_en(estado.stage, tile[0], tile[1])
    if not evento:
        return []
    ctx = ContextoSesion(ses, estado)
    # El VIVO solo pisa y choca; los de alma (8 y 9) son para el muerto. Antes
    # el vivo disparaba tambien los de alma, y en los 61 eventos en que son
    # distintos eso saltaba la mecanica: en la Dinosaur Arena el tornado del
    # Asiento del Rey Dragon ("solo se sale convertido en alma") devolvia al
    # vivo a la entrada, y en Gulp Room el vivo recibia el "no se puede" Y
    # ademas el GOTO del alma. Ningun evento tiene solo disparos de alma.
    disparo = (ev.PISAR, ev.CHOCAR) if not ctx.es_alma else (ev.ALMA_PISA,
                                                             ev.ALMA_CHOCA)
    if solo_chocar:
        disparo = (ev.CHOCAR,) if not ctx.es_alma else (ev.ALMA_CHOCA,)
    return _sin_mision(estado.stage, evento, _permiso_una_vez(
        ses, estado.stage, evento, ev.ejecutar(estado.stage, evento, disparo, ctx)))


def al_pulsar(ses, tile):
    """Los efectos de pulsar sobre lo que haya en una casilla."""
    estado = estado_de(ses)
    evento = ev.evento_en(estado.stage, tile[0], tile[1])
    if not evento:
        return []
    ctx = ContextoSesion(ses, estado)
    disparo = ev.DISPAROS_AL_PULSAR if not ctx.es_alma else (ev.ALMA_PULSA,)
    return _sin_mision(estado.stage, evento, _permiso_una_vez(
        ses, estado.stage, evento, ev.ejecutar(estado.stage, evento, disparo, ctx)))


def evento_del_monstruo(stage, npc_type):
    """El evento que dispara ese tipo de bicho al morir, o None.

    NO es el evento del objeto de su casilla. Los disparadores de muerte
    citan eventos que ningun objeto del mapa referencia -- en Dense Forest
    los objetos solo nombran el 1, 2, 3, 4 y 1001, y los botines cuelgan del
    501 al 505 --, y el enlace esta en el registro del generador, en un
    campo que no se leia. Cada tipo de monstruo lleva uno y siempre el mismo.
    """
    d = ev.del_stage(stage)
    if not d:
        return None
    return (d.get('monstruos') or {}).get(str(int(npc_type)))


def al_morir_monstruo(ses, monstruo):
    """Los efectos de que muera un bicho: botines y pasos de mision."""
    estado = estado_de(ses)
    # Los de MAKE_REVENGE_DNA_MONSTER llevan su propio evento de muerte.
    evento = getattr(monstruo, 'evento_muerte', None) or evento_del_monstruo(
        estado.stage, getattr(monstruo, 'npc_type', 0) or 0)
    if not evento:
        return []
    ctx = ContextoSesion(ses, estado)
    return ev.ejecutar(estado.stage, evento, ev.DISPAROS_AL_MORIR, ctx)


def pendientes(ses):
    """Los eventos que se comprueban solos (disparo 0) y todavia no saltaron.

    Son 53 en todo el juego y son los que abren las instancias. Se repasan
    cuando algo pudo cambiar -- tipicamente al morir un bicho -- y el que
    salta queda marcado para que la puerta no se vuelva a poner en cada paso.
    """
    estado = estado_de(ses)
    ctx = ContextoSesion(ses, estado)
    efectos = []
    for d in ev.disparadores(estado.stage, disparo=ev.NINGUNO):
        if d['ev'] in estado.ya_saltaron:
            continue
        salen = ev.ejecutar(estado.stage, d['ev'], ev.NINGUNO, ctx)
        if salen:
            estado.ya_saltaron.add(d['ev'])
            efectos += salen
    return efectos
