"""El interprete de los eventos del cliente: misiones e instancias de verdad.

POR QUE EXISTE. misiones.py lleva las misiones A MANO, en diccionarios como
QUEST_REGISTRO, QUEST_CONOCER u OBJETIVOS_CACERIA, y app.py tiene tramos con
numeros de NPC y de mision escritos en el propio if. Funciona para las que
estan puestas y no puede funcionar para las demas: los mapas del cliente
traen 1.788 SET_STEP repartidos por 260 escenarios, y eso a mano no se cubre
nunca. Las instancias estan igual: pobladas, pero sin la mecanica que abre la
puerta o suelta al jefe.

La logica ya estaba escrita, en los .mpc, solo que con los codigos en crudo.
Desde que se leyo el bloque DEFINE de setting/eventdef.xml hay nombre para
las 103 acciones y las 71 condiciones (tools/eventos_del_cliente.py), y
firma documentada para cada una, con el nombre de cada parametro. Este
fichero las ejecuta.

COMO ENCAJA, QUE ES LO DELICADO. Este modulo NO toca el mundo. Lee el estado
por un Contexto y devuelve una lista de EFECTOS; quien los aplica es app.py.
Se hace asi por tres razones: no hay import circular, se puede probar sin
levantar un servidor, y sobre todo se puede meter poco a poco -- app.py
decide que efectos obedece y cuales ignora todavia.

Y NO SUSTITUYE A portales.json. Los portales siguen resolviendose como
siempre, con sus radios medidos uno a uno. Aqui aparecen CHANGE_MAP y
GOTO_TAG porque un evento puede dar un objeto Y mover, pero si app.py ya ha
resuelto el portal por el camino de siempre, ignora el efecto de viaje.

LOS MODOS DE DISPARO, que vienen de la lista de 觸發方式 del propio eventdef:

    0 ninguno        1 pisar          2 pulsar         3 chocar
    4 muerte(grupo)  5 a intervalos   6 alma pulsa     7 mirar
    8 alma pisa      9 alma choca    10 tras crearse  11 muerte(individual)
   12 recolectar    13 recolectar(grupo)

OJO CON ESTO. tools/mapa_del_cliente.py tiene desde hace tiempo
PISAR, CLIC = '9', '3', y segun el eventdef eso esta mal: el 3 es CHOCAR
-- que es lo que haces al meterte en un tornado andando -- y el 9 es CHOCAR
SIENDO ALMA, la copia del mismo portal para cuando estas muerto. Por eso los
dos salen con miles de usos. Aqui se usan los nombres buenos. Alli no se ha
tocado nada, porque los portales funcionan y ese cambio no es mio de decidir.

CUANDO UNA CONDICION NO SE SABE EVALUAR, EL DISPARADOR NO SALTA. Es a
proposito y es la decision conservadora: saltar de mas puede teletransportar
a alguien o regalarle objetos, y no saltar solo deja las cosas como ya
estaban. Las condiciones que mandan -- QUESTITEM, QUEST_STEP, PROB100,
GENERATOR_ALIVE, MAPVAR, BAGITEM, EMPTYSLOT_COUNT -- estan todas puestas; lo
que falta es campo de batalla, casas y social, que son otros mapas.
"""
import json
import logging
import pathlib
import random

log = logging.getLogger(__name__)

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'eventos.json'

# -- modos de disparo --------------------------------------------------------
NINGUNO, PISAR, PULSAR, CHOCAR = 0, 1, 2, 3
MUERTE_GRUPO, INTERVALO, ALMA_PULSA, MIRAR = 4, 5, 6, 7
ALMA_PISA, ALMA_CHOCA, TRAS_CREARSE, MUERTE = 8, 9, 10, 11
RECOLECTAR, RECOLECTAR_GRUPO = 12, 13

# Al andar sobre algo el cliente manda CHOCAR; el 1 existe pero casi no se
# usa (147 veces contra 2.580). Se aceptan los dos, y sus copias de alma.
DISPAROS_AL_PASAR = (PISAR, CHOCAR, ALMA_PISA, ALMA_CHOCA)
DISPAROS_AL_PULSAR = (PULSAR, ALMA_PULSA, MIRAR)
DISPAROS_AL_MORIR = (MUERTE, MUERTE_GRUPO)
DISPAROS_AL_RECOLECTAR = (RECOLECTAR, RECOLECTAR_GRUPO)

# -- comparadores (los COMPARE_* del eventdef) -------------------------------
IGUAL, MENOR, MAYOR, MENOR_IGUAL, MAYOR_IGUAL, DISTINTO = 0, 1, 2, 3, 4, 5

_COMPARA = {
    IGUAL: lambda a, b: a == b,
    MENOR: lambda a, b: a < b,
    MAYOR: lambda a, b: a > b,
    MENOR_IGUAL: lambda a, b: a <= b,
    MAYOR_IGUAL: lambda a, b: a >= b,
    DISTINTO: lambda a, b: a != b,
}

# -- atributos de ADD_PROPERTY y SET_PROPERTY --------------------------------
ATR_HP, ATR_MP, ATR_SP = 0, 2, 4
ATR_NIVEL, ATR_EXP = 29, 32
ATR_PEINADO, ATR_COLOR_PELO, ATR_COLOR_PIEL = 36, 37, 38
ATR_FUNCION, ATR_RANGO = 49, 51
ATR_HP_PORCENTAJE = 1000

# -- objetivo de CAST --------------------------------------------------------
OBJ_DISPARADOR, OBJ_GRUPO, OBJ_LANZADOR = 0, 1, 2

# -- posicion de GENERATE ----------------------------------------------------
POS_DEL_GENERADOR, POS_DEL_OBJETO = 0, 1

_DATOS = None


def _datos():
    global _DATOS
    if _DATOS is None:
        if not RUTA.exists():
            log.warning('no hay %s: corre tools/propagar_eventos.py', RUTA)
            _DATOS = {'stages': {}, 'acciones': {}, 'condiciones': {}}
        else:
            _DATOS = json.loads(RUTA.read_text(encoding='utf-8'))
    return _DATOS


def nombre_accion(n):
    return _datos()['acciones'].get(str(n), '?%d' % n)


def nombre_condicion(n):
    return _datos()['condiciones'].get(str(n), '?%d' % n)


def del_stage(stage):
    return _datos()['stages'].get(str(stage))


def evento_en(stage, tx, ty):
    """El numero de evento del objeto que hay en esa casilla, o None."""
    d = del_stage(stage)
    if not d:
        return None
    o = d['objetos'].get('%d,%d' % (int(tx), int(ty)))
    return o[0] if o else None


def casillas_de_tag(stage, tag):
    d = del_stage(stage)
    if not d:
        return []
    return [tuple(c) for c in d['tags'].get(str(tag), [])]


def disparadores(stage, evento=None, disparo=None):
    """Los disparadores de un mapa, filtrados por evento y por modo."""
    d = del_stage(stage)
    if not d:
        return []
    salida = []
    for x in d['disparadores']:
        if evento is not None and x['ev'] != evento:
            continue
        if disparo is not None:
            if isinstance(disparo, (tuple, list, set, frozenset)):
                if x['d'] not in disparo:
                    continue
            elif x['d'] != disparo:
                continue
        salida.append(x)
    return salida


class Contexto:
    """De donde saca el interprete el estado del que dispara.

    Todo devuelve un valor neutro por defecto para que un servidor que
    todavia no sepa contestar algo no reviente: lo que pasa es que la
    condicion que dependa de eso no se cumple y el disparador no salta.

    `sabe` es la lista de condiciones que esta instancia SI puede contestar.
    Lo que no este ahi se trata como desconocido, se apunta en el registro y
    corta el disparador. Asi un contexto a medio hacer no dispara de mas.
    """

    sabe = frozenset()

    # quien dispara
    stage = 0
    casilla = (0, 0)
    es_alma = False

    # -- misiones --
    def paso_de_mision(self, quest):
        return -1

    def mision_terminada(self, quest):
        return False

    def mision_en_curso(self, quest):
        return False

    # -- objetos --
    def en_bolsa(self, item):
        return 0

    def objeto_de_mision(self, item):
        return 0

    def equipado(self, item):
        return 0

    def huecos_libres(self):
        return 0

    def oro(self):
        return 0

    # -- personaje --
    def nivel(self):
        return 0

    def rango(self):
        return 0

    def sexo(self):
        return 0

    def faccion(self):
        return 0

    def nivel_de_skill(self, skill):
        return 0

    def vivo(self):
        return True

    def es_gm(self):
        return False

    def tiene_guild(self):
        return False

    def nivel_liga(self):
        return 0

    def permiso_liga(self, permiso):
        return False

    def tiene_region_liga(self):
        return False

    def liga_posee_territorio(self, tw_stage):
        return False

    def antiguedad_en_liga(self):
        return 0

    def tiene_estado_magico(self, estado):
        return False

    # -- mapa --
    def vivos_del_generador(self, tag):
        return 0

    def generador_activo(self, tag):
        return False

    def variable_de_mapa(self, mapa, var):
        return 0

    def temporizador_activo(self, tag):
        return False

    def veces_del_temporizador(self, tag):
        return 0

    def puede_entrar_en_paralelo(self, mapa):
        return False

    # -- grupo --
    def miembros_del_grupo(self, que=0):
        return 1

    def teamid(self):
        return 0

    def dueno_del_tesoro(self):
        return True

    # -- casas --
    def es_dueno_casa(self):
        return True

    def nivel_casa(self):
        return 1

    def casa_disco_party(self):
        return False

    def casa_puede_buff_diario(self):
        return True

    def casa_tiene_voto(self):
        return True

    def casa_limpieza(self):
        return 1000

    def casa_dueno_en_casa(self):
        return True

    def casa_es_pareja(self):
        return False

    def casa_tamano(self):
        return 0

    # -- azar, aparte para poder fijarlo en las pruebas --
    def sorteo100(self):
        return random.randint(1, 100)

    # -- actualizacion local durante la ejecucion de un evento --
    def aplicar_efecto_local(self, ef):
        pass


def _p(parms, i, por_defecto=0):
    return parms[i] if len(parms) > i else por_defecto


def _cmp(modo, a, b):
    f = _COMPARA.get(modo)
    return bool(f(a, b)) if f else None


def evaluar(numero, parms, ctx):
    """Una condicion. True, False, o None si no se sabe contestar."""
    if numero not in ctx.sabe:
        return None

    if numero == 1:                                     # SEX(cmp, sexo)
        return _cmp(_p(parms, 0), ctx.sexo(), _p(parms, 1))
    if numero == 2:                                     # QUEST_STEP(q, paso)
        return ctx.paso_de_mision(_p(parms, 0)) == _p(parms, 1)
    if numero == 3:                                     # PROPERTY(atr, cmp, v)
        atr = _p(parms, 0)
        val = ctx.nivel() if atr == ATR_NIVEL else (
            ctx.rango() if atr == ATR_RANGO else None)
        return None if val is None else _cmp(_p(parms, 1), val, _p(parms, 2))
    if numero == 4:                                     # SKILL_LEVEL(s, cmp, n)
        return _cmp(_p(parms, 1), ctx.nivel_de_skill(_p(parms, 0)), _p(parms, 2))
    if numero == 5:                                     # EQUIPITEM(item, cmp, n)
        return _cmp(_p(parms, 1), ctx.equipado(_p(parms, 0)), _p(parms, 2))
    if numero == 6:                                     # BAGITEM(item, cmp, n)
        return _cmp(_p(parms, 1), ctx.en_bolsa(_p(parms, 0)), _p(parms, 2))
    if numero == 7:                                     # QUESTITEM(item, cmp, n)
        return _cmp(_p(parms, 1), ctx.objeto_de_mision(_p(parms, 0)), _p(parms, 2))
    if numero == 8:                                     # EMPTYSLOT_COUNT(cmp, n)
        return _cmp(_p(parms, 0), ctx.huecos_libres(), _p(parms, 1))
    if numero == 10:                                    # PROB100(prob)
        return ctx.sorteo100() <= _p(parms, 0)
    if numero == 11:                                    # QUEST_FINISH(q)
        return ctx.mision_terminada(_p(parms, 0))
    if numero == 12:                                    # ALIGNMENT(faccion)
        return ctx.faccion() == _p(parms, 0)
    if numero == 13:                                    # QUEST_RUNNING(q)
        return ctx.mision_en_curso(_p(parms, 0))
    if numero == 14:                                    # GENERATOR_ALIVE(tag, cmp, n)
        return _cmp(_p(parms, 1), ctx.vivos_del_generador(_p(parms, 0)),
                    _p(parms, 2))
    if numero == 15:                                    # GENERATOR_ENABLE(tag, cmp, est)
        return _cmp(_p(parms, 1), int(ctx.generador_activo(_p(parms, 0))),
                    _p(parms, 2))
    if numero == 16:                                    # TREASURE_OWNER()
        return ctx.dueno_del_tesoro()
    if numero == 17:                                    # MONEY(cmp, cantidad)
        return _cmp(_p(parms, 0), ctx.oro(), _p(parms, 1))
    if numero == 20:                                    # GM()
        return ctx.es_gm()
    if numero == 21:                                    # HAVE_GUILD()
        return ctx.tiene_guild()
    if numero == 28:                                    # HAVE_GUILD_REGION()
        return ctx.tiene_region_liga()
    if numero == 33:                                    # GUILD_PERM(permiso)
        return ctx.permiso_liga(_p(parms, 0))
    if numero == 34:                                    # GUILD_LEVEL(cmp, nivel)
        return _cmp(_p(parms, 0), ctx.nivel_liga(), _p(parms, 1))
    if numero == 76:                                    # SPEC_MAP_OWN_GUILD(tw_stage)
        return ctx.liga_posee_territorio(_p(parms, 0))
    if numero == 82:                                    # GUILD_MEMBER_TIME(segundos)
        return ctx.antiguedad_en_liga() >= _p(parms, 0)
    if numero == 22:                                    # PARA_ENTER(mapa)
        return ctx.puede_entrar_en_paralelo(_p(parms, 0))
    if numero == 29:                                    # MAPVAR(mapa, var, cmp, v)
        return _cmp(_p(parms, 2),
                    ctx.variable_de_mapa(_p(parms, 0), _p(parms, 1)),
                    _p(parms, 3))
    if numero == 30:                                    # TIMER_ENABLE(tag, cmp, est)
        return _cmp(_p(parms, 1), int(ctx.temporizador_activo(_p(parms, 0))),
                    _p(parms, 2))
    if numero == 31:                                    # TIMER_COUNTER(tag, cmp, n)
        return _cmp(_p(parms, 1), ctx.veces_del_temporizador(_p(parms, 0)),
                    _p(parms, 2))
    if numero == 38:                                    # HAVE_MAGIC_STATE(estado)
        return ctx.tiene_estado_magico(_p(parms, 0))
    if numero == 39:                                    # GROUP(que, cmp, v)
        return _cmp(_p(parms, 1), ctx.miembros_del_grupo(_p(parms, 0)),
                    _p(parms, 2))
    if numero == 48:                                    # TEAMID(cmp, teamid)
        return _cmp(_p(parms, 0), ctx.teamid(), _p(parms, 1))
    if numero == 56:                                    # IS_LIVE()
        return ctx.vivo()
    if numero == 58:                                    # HOUSE_IS_OWNER()
        return ctx.es_dueno_casa()
    if numero == 59:                                    # HOUSE_LEVEL(cmp, lv)
        return _cmp(_p(parms, 0), ctx.nivel_casa(), _p(parms, 1))
    if numero == 60:                                    # DISCO_PARTY(is_active)
        return ctx.casa_disco_party() == bool(_p(parms, 0))
    if numero == 61:                                    # COMPOUND_BUFF()
        return ctx.casa_puede_buff_diario()
    if numero == 62:                                    # HOUSE_HAVE_VOTE()
        return ctx.casa_tiene_voto()
    if numero == 63:                                    # HOUSE_NEATNESS(cmp, val)
        return _cmp(_p(parms, 0), ctx.casa_limpieza(), _p(parms, 1))
    if numero == 64:                                    # HOUSE_OWNER_AT_HOME()
        return ctx.casa_dueno_en_casa()
    if numero == 65:                                    # HOUSE_OWNER_PARTNER()
        return ctx.casa_es_pareja()
    if numero == 70:                                    # HOUSE_SIZE(cmp, sz)
        return _cmp(_p(parms, 0), ctx.casa_tamano(), _p(parms, 1))
    return None


# Las condiciones que evaluar() sabe contestar. Un Contexto declara en su
# `sabe` las que de verdad puede alimentar, que siempre es un subconjunto.
SE_EVALUAN = frozenset((1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16,
                        17, 20, 21, 22, 28, 29, 30, 31, 33, 34, 38, 39, 48, 56,
                        58, 59, 60, 61, 62, 63, 64, 65, 70, 76, 82))


def _pares(parms):
    """Las acciones de objetos vienen en cinco pares (item, cantidad)."""
    return [(parms[i], parms[i + 1])
            for i in range(0, min(len(parms) - 1, 10), 2)
            if parms[i] and parms[i + 1]]


def traducir(numero, parms):
    """Una accion a efecto. None si todavia no se traduce.

    El efecto es una tupla que empieza por el nombre, para que app.py pueda
    obedecer los que entienda e ignorar los demas sin romperse.
    """
    if numero == 1:
        return ('parar',)
    if numero == 3:
        return ('viajar', _p(parms, 0), _p(parms, 1))
    if numero == 37:
        # CHANGE_PARA_MAP (mapa, paralelo, tag). Usado por los Terra Keeper de
        # mapas de territorio (map016, etc.) para saltar a Area I..IV (50, 100, 117, 377).
        return ('cambiar_mapa_paralelo', _p(parms, 0), _p(parms, 1), _p(parms, 2))
    if numero == 50:
        # GOTO_GUILD_REGION: teletransporte al territorio o area de liga.
        return ('ir_a_region_liga',)
    if numero == 4:
        return ('paso', _p(parms, 0), _p(parms, 1))
    if numero == 7:
        return ('propiedad', 'sumar', _p(parms, 0), _p(parms, 1))
    if numero == 8:
        return ('propiedad', 'poner', _p(parms, 0), _p(parms, 1))
    if numero == 9:
        return ('quitar', _pares(parms))
    if numero in (10, 51, 81):
        return ('dar', _pares(parms))
    if numero == 12:
        return ('premio', 'mostrar', _pares(parms))
    if numero in (13, 47):
        return ('premio', 'elegir', _pares(parms))
    if numero == 14:
        return ('tienda', _p(parms, 0))
    if numero == 18:
        return ('fabricar', _p(parms, 0))
    if numero == 19:
        return ('oro', _p(parms, 0))
    if numero == 20:
        return ('oro', -_p(parms, 0))
    if numero == 21:
        return ('npc', _p(parms, 0), _p(parms, 1), _p(parms, 2),
                _p(parms, 3), _p(parms, 4))
    if numero == 22:
        # OPEN_BANK(tipo): 0 personal, 1 liga. Usado por el Governor de Areas 50/100/117/377.
        return ('abrir_banco', _p(parms, 0))
    if numero == 24:
        return ('cerrar_dialogo',)
    if numero == 34:
        # EVENT_ACT_OPEN_CREATE_GUILD (eventdef.xml): abre la ventana de crear
        # liga. La del League Clerk de las cuatro ciudades (dialogo 5776).
        return ('abrir_crear_liga',)
    if numero == 25:
        return ('dialogo', _p(parms, 0))
    if numero == 29:
        return ('faccion', _p(parms, 0))
    if numero == 30:
        return ('nota', _p(parms, 0))
    if numero == 31:
        return ('generar', _p(parms, 0), _p(parms, 1))
    if numero == 33:
        return ('generador', _p(parms, 0), _p(parms, 1))
    if numero == 36:
        return ('tesoro', _p(parms, 0))
    if numero == 39:
        return ('revivir',)
    if numero == 41:
        return ('matar_para_avanzar', _p(parms, 0), _p(parms, 1),
                _p(parms, 2), _p(parms, 3), _p(parms, 4), _p(parms, 5))
    if numero == 42:
        return ('soltar_objeto_mision', _p(parms, 0), _p(parms, 1),
                _p(parms, 2), _p(parms, 3), _p(parms, 4), _p(parms, 5))
    if numero == 52:
        return ('objeto_estatico', _p(parms, 0), _p(parms, 1))
    if numero == 53:
        return ('ir_a_tag', _p(parms, 0))
    if numero == 54:
        return ('magia', _p(parms, 0), _p(parms, 1), _p(parms, 2))
    if numero == 55:
        return ('chat', _p(parms, 0), [m for m in parms[1:6] if m])
    if numero == 56:
        return ('variable', 'poner', _p(parms, 0), _p(parms, 1), _p(parms, 2))
    if numero == 57:
        return ('variable', 'sumar', _p(parms, 0), _p(parms, 1), _p(parms, 2))
    if numero == 60:
        return ('temporizador', _p(parms, 0), _p(parms, 1), _p(parms, 2))
    if numero == 63:
        # NPCKILLGAME(1 empieza / 0 termina): la carrera de bajas contra los
        # NPC del Evil Lyceum (sala 2 de la Magic Kichen Path). Las bajas y
        # el tiempo los lleva el servidor; ver app.py, 'juego_matar'.
        return ('juego_matar', _p(parms, 0))
    if numero == 67:
        return ('botin', _p(parms, 0))
    if numero == 70:
        return ('botin_sorteo', _p(parms, 0))
    if numero == 72:
        return ('cambiar_evento', _p(parms, 0))
    if numero == 78:
        return ('chat_npc', [m for m in parms[0:5] if m])
    if numero == 89:
        return ('salir_de_casa',)
    if numero == 90:
        return ('casa_buff_diario',)
    if numero == 91:
        return ('casa_abrir_pets',)
    if numero == 92:
        return ('casa_abrir_mobgen',)
    if numero == 93:
        return ('casa_limpiar', _p(parms, 0), _p(parms, 1), _p(parms, 2))
    if numero == 94:
        return ('casa_abrir_voto',)
    if numero == 95:
        return ('casa_ver_notas',)
    if numero == 96:
        return ('casa_hitparade',)
    if numero == 104:
        return ('variable', 'restar', _p(parms, 0), _p(parms, 1), _p(parms, 2))
    return None


# Las acciones que traducir() convierte en efecto.
SE_TRADUCEN = frozenset((1, 3, 4, 7, 8, 9, 10, 12, 13, 14, 18, 19, 20, 21, 22, 24,
                         25, 34, 37, 29, 30, 31, 33, 36, 39, 41, 42, 47, 50, 51, 52, 53,
                         54, 55, 56, 57, 60, 63, 67, 70, 72, 78, 81,
                         89, 90, 91, 92, 93, 94, 95, 96, 104))
def _alguna(condiciones, ctx):
    for c in condiciones:
        r = evaluar(c[0], c[1], ctx)
        if r is not None and len(c) > 2 and c[2]:
            r = not r
        if r:
            return True
    return False


def ejecutar(stage, evento, disparo, ctx):
    """Los efectos de disparar un evento. No cambia nada por si mismo.

    Recorre los disparadores de ese evento con ese modo, en el orden del
    mapa. De cada uno comprueba las condiciones: si alguna sale False no se
    hace nada de ese disparador, y si alguna sale None -- no se sabe -- se
    corta igual y se apunta. STOP corta el resto.
    """
    efectos = []
    for d in disparadores(stage, evento, disparo):
        if d.get('o') and d['si']:
            # 一項成立算成立: con UNA que se cumpla basta.
            if not _alguna(d['si'], ctx):
                continue
            for n, parms in d['haz']:
                ef = traducir(n, parms)
                if ef is None:
                    continue
                if ef[0] == 'parar':
                    return efectos
                efectos.append(ef)
                if hasattr(ctx, 'aplicar_efecto_local'):
                    ctx.aplicar_efecto_local(ef)
            continue
        corta = False
        for c in d['si']:
            n, parms = c[0], c[1]
            r = evaluar(n, parms, ctx)
            # negada en el mapa (反向): se cumple si NO se cumple
            if r is not None and len(c) > 2 and c[2]:
                r = not r
            if r is None:
                log.debug('evento %s/%s: condicion %s%s sin resolver',
                          stage, evento, nombre_condicion(n), tuple(parms))
                corta = True
                break
            if not r:
                corta = True
                break
        if corta:
            continue
        for n, parms in d['haz']:
            ef = traducir(n, parms)
            if ef is None:
                log.debug('evento %s/%s: accion %s%s sin traducir',
                          stage, evento, nombre_accion(n), tuple(parms))
                continue
            if ef[0] == 'parar':
                return efectos
            efectos.append(ef)
            if hasattr(ctx, 'aplicar_efecto_local'):
                ctx.aplicar_efecto_local(ef)
    return efectos


_TOKENS = None
_PASOS_POR_MUERTE = None


def es_objeto_de_mision(item_id):
    """Si ese objeto es un TOKEN de mision: de los que van a las ranuras
    ocultas 497..556 y no a la mochila.

    No se adivina por el nombre ni por la categoria del objeto: es token todo
    lo que alguna condicion QUESTITEM de los mapas pregunta. Asi es como el
    propio juego los trata -- la 901 da el 8461 al matar un dragon y luego
    mira QUESTITEM(8461) para saber si ya van 30 --, y el HUD lee el contador
    de esas mismas ranuras.
    """
    global _TOKENS
    if _TOKENS is None:
        _TOKENS = set()
        for d in _datos()['stages'].values():
            for x in d['disparadores']:
                for c in x['si']:
                    n, p = c[0], c[1]
                    if n == 7 and p:
                        _TOKENS.add(int(p[0]))
    return int(item_id) in _TOKENS


def paso_definido_por_muertes(quest, paso_cliente):
    """Si los mapas ya definen que pasa al matar bichos en ese paso.

    Sirve para no contar dos veces: cuando el mapa lo trae, es la fuente
    exacta -- que bicho da que token y cuando se avanza -- y el conteo viejo
    de misiones.py sobra.
    """
    global _PASOS_POR_MUERTE
    if _PASOS_POR_MUERTE is None:
        _PASOS_POR_MUERTE = set()
        for d in _datos()['stages'].values():
            for x in d['disparadores']:
                if x['d'] not in DISPAROS_AL_MORIR:
                    continue
                for c in x['si']:
                    n, p = c[0], c[1]
                    if n == 2 and len(p) > 1 and not (len(c) > 2 and c[2]):
                        _PASOS_POR_MUERTE.add((int(p[0]), int(p[1])))
                # y los de KILLTO_NEXTSTEP, que llevan mision y paso en la
                # propia accion y no en una condicion
                for n, p in x['haz']:
                    if n == 41 and len(p) > 1:
                        _PASOS_POR_MUERTE.add((int(p[0]), int(p[1])))
    return (int(quest), int(paso_cliente)) in _PASOS_POR_MUERTE


def cobertura():
    """Que parte de lo que usan los mapas sabe este interprete.

    Sirve para no enganarse con la sensacion de avance: dice el porcentaje
    de USOS, que es lo que se nota jugando, no el de codigos distintos.
    """
    acc = acc_ok = con = con_ok = 0
    for d in _datos()['stages'].values():
        for x in d['disparadores']:
            for n, _q in x['haz']:
                acc += 1
                acc_ok += n in SE_TRADUCEN
            for c in x['si']:
                n = c[0]
                con += 1
                con_ok += n in SE_EVALUAN
    return {'acciones': (acc_ok, acc), 'condiciones': (con_ok, con)}
