"""Los arboles de dialogo de los mapas: que dice cada NPC segun la mision.

Lo genera tools/propagar_dialogos_mapa.py en plantillas/dialogos_mapa.json. Aqui se recorre: se busca el nodo raiz del NPC
por su RETRATO, se elige la rama cuyas condiciones cumple el personaje -- con
el mismo evaluador que los eventos, que ya sabe pasar los pasos de mision de
la numeracion del servidor a la del cliente --, y se devuelve la cadena de
mensajes que toca.

POR QUE. Para los recordatorios de mision el servidor adivinaba la linea
dentro del bloque de mensajes de la mision, y en la 1590 le salia a Bella
Bulu la frase de Matia mandandote a buscarla (159013). El arbol de Clink
Harbor dice cual es: con la mision en el paso 3, el nodo 1000011, mensaje
159031, "consigue 20 Microcoins de los Transport Workers y daselos a Meow".

DE MOMENTO SOLO SE USA PARA LINEAS QUE NO HACEN NADA. Si el camino elegido
lleva acciones (dar objetos, cambiar de paso...), se devuelve None y sigue
mandando misiones.py, que es quien lleva el avance: ejecutar tambien las del
arbol avanzaria la mision dos veces.
"""
import json
import logging
import pathlib
from functools import lru_cache

import eventos as ev

log = logging.getLogger(__name__)

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'dialogos_mapa.json'
# Arbol de spmsg.xml (NPC de los sp_*.xml). Va debajo del de cada mapa.
RUTA_SP = pathlib.Path(__file__).parent / 'plantillas' / 'dialogos_sp.json'
MAX_LINEAS = 8

_TODO = None
_SP = None
_CON_SP = {}


@lru_cache(maxsize=None)
def es_comercio(stage, raiz):
    """Only native shop/dialogue paths, without quests or other services.

    Use the MPC root for the exact NPC, including each level-band submenu.
    Portraits and generic option IDs are shared by unrelated merchants.
    """
    tree=_arbol(stage);pending=[str(raiz)];seen=set();has_shop=False
    while pending and len(seen)<64:
        key=pending.pop()
        if key=='0' or key in seen:continue
        node=tree.get(key)
        if node is None or node.get('r'):return False
        seen.add(key)
        for action,args in node.get('a',()):
            if action not in (1,14,24):return False
            if action==14:
                if len(args)!=1 or args[0]<=0:return False
                has_shop=True
        pending.extend(str(target) for _,target in node.get('o',()))
        if node.get('s'):pending.append(str(node['s']))
    return not pending and has_shop


def _arbol(stage, con_sp=True):
    """El arbol del stage. con_sp=False: solo el del mapa, sin spmsg.xml --
    para BUSCAR raices (por retrato o por accion); con spmsg, el Breeze Totem
    de Bluesand y los del Lyceum cogian una raiz de spmsg con su mismo retrato
    ("You are not the angel of this totem...") estando vivo."""
    global _TODO
    if _TODO is None:
        try:
            _TODO = json.loads(RUTA.read_text(encoding='utf-8'))
        except Exception:
            _TODO = {}
        try:
            import totem_war as _tw
            if _tw.MODO == 'antigua':
                _terra_keeper_antiguo(_TODO)
        except Exception:
            log.exception('Terra Keeper antiguo')
    result=_TODO.get(str(int(stage)), {})
    if con_sp:
        result=_con_sp(int(stage), result)
    if int(stage)==41:
        import olympus,recent_mall
        return {**result,**olympus.datos()['nodes'],**recent_mall.datos()['nodes']}
    return result


def arbol_sp():
    global _SP
    if _SP is None:
        try:
            _SP = json.loads(RUTA_SP.read_text(encoding='utf-8'))
        except Exception:
            _SP = {}
    return _SP


def _con_sp(stage, propio):
    # El del mapa gana si un numero de nodo coincide. Se mezcla una vez por
    # mapa: son ~25.000 nodos y _arbol se llama en cada click.
    if stage not in _CON_SP:
        _CON_SP[stage] = {**arbol_sp(), **propio} if arbol_sp() else propio
    return _CON_SP[stage]


def raiz_sp(msgid):
    """El nodo raiz de un NPC de sp_*.xml si su arbol decide algo (ramas u
    opciones); si es una linea suelta sigue el dialogo de siempre."""
    n = arbol_sp().get(str(int(msgid or 0)))
    return int(msgid) if n and (n.get('r') or n.get('o')) else None


# EL TERRA KEEPER DE LA GUERRA ANTIGUA (totem_war.MODO = 'antigua'). Medido en
# Celestia (mundo_130319_646053): con el campo de tu faccion dice 5937 y ofrece
# 5961 / 5939 / 5938 / Quit, sin "Send me to the [Neo-Totem Defense]
# battlefield!" (8283); sin el campo, 5932 ("your guild has not captured any
# totems...") y nada mas, en vez de invitar a la arena (9013).
MSG_NEO_TOTEM = 8283
MSG_RAIZ_NEO_TOTEM = {5986, 5987, 5988, 9000, 9001, 9002, 9003, 9004}
MSG_SIN_TOTEM = 5932


def _terra_keeper_antiguo(todo):
    for arbol in todo.values():
        for n in arbol.values():
            if n.get('o'):
                n['o'] = [op for op in n['o'] if op[0] != MSG_NEO_TOTEM]
            if n.get('m') in MSG_RAIZ_NEO_TOTEM and n.get('r'):
                n['m'] = MSG_SIN_TOTEM
                # Fuera la rama "hay guerra -> a la arena" (IS_PVP_ON, 32).
                n['r'] = [r for r in n['r'] if not any(c[0] == 32 for c in r.get('si', ()))]


def _raices(arbol):
    """Los nodos a los que no lleva ningun otro: los de entrada de cada NPC."""
    destinos = set()
    for n in arbol.values():
        if n.get('s'):
            destinos.add(n['s'])
        for _m, s in n.get('o', ()):
            destinos.add(s)
        for r in n.get('r', ()):
            destinos.add(r.get('ir'))
    return [k for k in arbol if int(k) not in destinos]


def raiz_del_npc(stage, retrato):
    """El nodo de entrada del NPC con ese retrato, o None.

    Solo cuenta si hay uno y con ramas: dos raices con el mismo retrato no
    se pueden distinguir y entonces no se arriesga.
    """
    arbol = _arbol(stage, con_sp=False)
    if not arbol or not retrato:
        return None
    cands = [k for k in _raices(arbol)
             if arbol[k].get('c') == int(retrato) and arbol[k].get('r')]
    return cands[0] if len(cands) == 1 else None


def _cumple(rama, ctx):
    resultados = []
    for n, p, negada in rama.get('si', ()):
        r = ev.evaluar(n, p, ctx)
        if r is None:
            return False              # no se sabe: no se arriesga
        resultados.append((not r) if negada else bool(r))
    if not resultados:
        return False
    return any(resultados) if rama.get('o') else all(resultados)


def _elegir(arbol, k, ctx, profundidad=0):
    """Baja por las ramas hasta un nodo sin ramas que cumplir."""
    n = arbol.get(str(k))
    if n is None or profundidad > 6:
        return None
    for rama in n.get('r', ()):
        if _cumple(rama, ctx):
            return _elegir(arbol, rama['ir'], ctx, profundidad + 1)
    return str(k)


def lineas_sin_accion(stage, retrato, ctx):
    """(retrato, [mensajes]) de lo que el NPC dice ahora, o None.

    None si el NPC no tiene arbol, si no se reconoce su raiz, si la rama
    elegida es la de entrada (no depende de la mision) o si por el camino hay
    alguna accion o alguna pregunta con opciones.
    """
    arbol = _arbol(stage)
    raiz = raiz_del_npc(stage, retrato)
    if raiz is None:
        return None
    k = _elegir(arbol, raiz, ctx)
    if k is None or k == raiz:
        return None
    mensajes = []
    cara = None
    visto = set()
    while k and k not in visto and len(mensajes) < MAX_LINEAS:
        visto.add(k)
        n = arbol.get(str(k))
        if n is None:
            break
        if n.get('a') or n.get('o') or n.get('r'):
            return None               # hace algo o pregunta: no es solo texto
        if n.get('m'):
            mensajes.append(n['m'])
            cara = cara or n.get('c')
        k = str(n['s']) if n.get('s') else None
    if not mensajes:
        return None
    return (cara or int(retrato), mensajes)


def lineas_del_nodo(stage, nodo, ctx=None):
    """(retrato, [mensajes]) a partir de un nodo concreto: el que abre un
    evento con BEGIN_MESSAGE (la estatua del mono de la 262 abre el 26201).

    Si el nodo ramifica, se elige la rama con el estado del personaje. Se
    sigue la cadena de "siguiente" y se para en el primer nodo con opciones
    -- su texto se muestra, sus opciones todavia no se atienden -- o con
    acciones, que ya las ha ejecutado el evento que abrio el dialogo.
    """
    arbol = _arbol(stage)
    k = str(int(nodo))
    if k not in arbol:
        return None
    if ctx is not None and arbol[k].get('r'):
        k = _elegir(arbol, k, ctx) or k
    mensajes, cara, visto = [], None, set()
    while k and k not in visto and len(mensajes) < MAX_LINEAS:
        visto.add(k)
        n = arbol.get(str(k))
        if n is None:
            break
        if n.get('m'):
            mensajes.append(n['m'])
            cara = cara or n.get('c')
        if n.get('o') or n.get('r'):
            break
        k = str(n['s']) if n.get('s') else None
    return (cara, mensajes) if mensajes else None


def raiz_interactiva(stage, retrato):
    """El nodo de entrada de un NPC cuyo dialogo HACE algo: pregunta (opciones),
    tiene acciones o ramifica. None si no tiene.

    raiz_del_npc() solo vale para los recordatorios, que exigen ramas; el
    Annoying Clerk de la sala 2 de la Magic Kichen Path entra por un nodo con
    tres opciones y sin ramas (10001: "contame el juego" / "acepto" / salir).
    """
    arbol = _arbol(stage, con_sp=False)
    if not arbol or not retrato:
        return None
    for k in _raices(arbol):
        n = arbol[k]
        if n.get('c') == int(retrato) and (n.get('o') or n.get('a') or n.get('r')):
            return k
    return None


def _acciones_debajo(arbol, k, num, valor, visto=None):
    """Si desde el nodo k se llega a una accion `num` con primer parametro `valor`."""
    visto = visto if visto is not None else set()
    if k in visto or str(k) not in arbol:
        return False
    visto.add(k)
    n = arbol[str(k)]
    if any(a[0] == num and (a[1] or [None])[0] == valor for a in n.get('a', ())):
        return True
    sig = [n.get('s')] + [o[1] for o in n.get('o', ())] + [r.get('ir') for r in n.get('r', ())]
    return any(_acciones_debajo(arbol, str(x), num, valor, visto) for x in sig if x)


def nodo_fin_de_juego(stage):
    """La raiz que cierra el NPCKILLGAME (63, 0) y no lo empieza: la que el
    servidor abre cuando se acaba el tiempo. En el stage 74 es la 61102, que
    mira si ganaste (mas de 50 bajas) y te pasa al 75 o te devuelve."""
    arbol = _arbol(stage, con_sp=False)
    for k in _raices(arbol):
        if (_acciones_debajo(arbol, k, 63, 0)
                and not _acciones_debajo(arbol, k, 63, 1)):
            return k
    return None


def zonas_de_inicio_de_juego(stage):
    """Las zonas que GENERA (accion 31) la raiz que empieza el NPCKILLGAME
    (63, 1): las marcas de "carrera en marcha". En el stage 74 es la 103, que
    la raiz de cierre (61102) mira con GENERATOR_ALIVE."""
    arbol = _arbol(stage, con_sp=False)
    zonas = set()
    for n in arbol.values():
        if any(a[0] == 63 and (a[1] or [None])[0] == 1 for a in n.get('a', ())):
            zonas.update(int(a[1][0]) for a in n.get('a', ()) if a[0] == 31 and a[1])
    return zonas


def nodo_de_victoria(stage):
    """El nodo al que la raiz de cierre del NPCKILLGAME manda cuando ganas:
    el de la rama que mira la variable 8 del mapa (condicion 29 [0, 8, ...]).
    En el stage 74 es el 1000020: "You win!", la zona 101 y al mapa 75."""
    arbol = _arbol(stage)
    raiz = nodo_fin_de_juego(stage)
    pendientes, visto = [str(raiz)] if raiz else [], set()
    while pendientes:
        k = pendientes.pop()
        if k in visto or k not in arbol:
            continue
        visto.add(k)
        n = arbol[k]
        for r in n.get('r', ()):
            if any(c[0] == 29 and list(c[1][:2]) == [0, 8] for c in r.get('si', ())):
                return r.get('ir')
            pendientes.append(str(r.get('ir')))
        pendientes += [str(n['s'])] if n.get('s') else []
    return None


_PASOS_DE_ARBOL = None

# Misiones cuyos pasos de "ve a tal sitio" (el texto no nombra a ningun NPC)
# se han repasado contra el arbol del mapa, nodo por nodo. En ellas el paso
# solo se cumple en el mapa que dice el arbol; hablandole al NPC compilado en
# otro mapa se saltaban (10/11/2026, la tanda de la Magic Kichen Path):
#   603 paso 1  "Find Boship"            lo cumplia el Angel Inspector
#   609 paso 2  "Find the Annoying Clerk" lo cumplia Luxious Ba al entregar
#   610 paso 2  "Find strong human"      lo cumplia el Annoying Clerk, y de
#               ahi encadenaba el 3 y el 4: la mision entera sin la sangre
# No se aplica a todas porque en 40 pasos el mapa compilado y el del arbol no
# coinciden y habria que mirarlos uno a uno antes de cerrarlos.
MISIONES_POR_ARBOL = frozenset((603, 609, 610))


def pasos_de_arbol():
    """{(quest, paso de cliente): mapas} donde un nodo del arbol pone ese paso
    (accion 4, SET_STEP)."""
    global _PASOS_DE_ARBOL
    if _PASOS_DE_ARBOL is None:
        _arbol(0)
        donde = {}
        for st, arbol in (_TODO or {}).items():
            if not isinstance(arbol, dict) or not str(st).isdigit():
                continue
            for nodo in arbol.values():
                if not isinstance(nodo, dict):
                    continue
                for acc in nodo.get('a') or []:
                    if acc and acc[0] == 4 and len(acc[1]) >= 2:
                        donde.setdefault((int(acc[1][0]), int(acc[1][1])), set()).add(int(st))
        _PASOS_DE_ARBOL = {k: frozenset(v) for k, v in donde.items()}
    return _PASOS_DE_ARBOL


def _mismo_mapa(stage, mapas):
    """Si `stage` es uno de esos mapas (o su copia de canal, +100 / +200)."""
    return any(abs(int(stage or 0) - m) in (0, 100, 200) for m in mapas)


def paso_solo_del_mapa(quest, paso, stage_paso, stage_jugador):
    """Si el paso `paso` (el del servidor, 1 = el primero) de esa mision NO se
    puede cumplir hablando con un NPC desde donde esta el jugador, porque lo
    pone el arbol de un mapa:
      * de instancia (pasos_solo_instancia): nunca hablando;
      * de una mision repasada (MISIONES_POR_ARBOL): solo en ese mapa."""
    clave = (int(quest), int(paso))
    if clave in pasos_solo_instancia():
        return True
    mapas = pasos_de_arbol().get(clave)
    return bool(mapas and int(quest) in MISIONES_POR_ARBOL and stage_paso
                and _mismo_mapa(stage_paso, mapas)
                and not _mismo_mapa(stage_jugador, mapas))


def raiz_con_mision_en_curso(stage, retrato, ctx, quests):
    """El nodo de entrada del NPC con ese retrato cuya rama CUMPLIDA mira el
    paso de una mision en curso que el arbol pone en este mapa. None si no.

    Para el NPC que el compilador no asocio a la mision: Athlete Cliff es el
    "strong human" de la 610 y su arbol (83500) lo sabe, pero por nombre
    nadie lo encuentra y antes de llegar al arbol se le ofrecian sus otras
    misiones."""
    arbol = _arbol(stage, con_sp=False)
    if not arbol or not retrato:
        return None
    pasos = pasos_de_arbol()
    mias = {int(q): int(pa) for q, pa in (quests or [])}
    # Los nodos de entrada son los que llevan numero propio (los 1000xxx son
    # los interiores). No vale _raices(): al 83500 de Cliff vuelve una opcion
    # de su propio menu y deja de parecer raiz.
    for k, n in arbol.items():
        if int(k) >= 1000000 or n.get('c') != int(retrato):
            continue
        for rama in n.get('r', ()):
            if not _cumple(rama, ctx):
                continue
            for num, parms, negada in rama.get('si', ()):
                if num != 2 or negada or not parms:
                    continue
                q = int(parms[0])
                pa = mias.get(q)
                if (pa is not None and paso_solo_del_mapa(q, pa, stage, 0)
                        and _mismo_mapa(stage, pasos.get((q, pa), ()))):
                    return int(k)
            break       # la primera rama cumplida es la que seguiria el arbol
    return None


_SOLO_INSTANCIA = None


def pasos_solo_instancia():
    """{(quest, paso de cliente)}: los pasos que SOLO pone un nodo del arbol de
    un mapa de instancia (accion 4, SET_STEP). Son los de "haz algo dentro de
    la mazmorra" -- acercarse a la puerta de la Devil Kitchen, encontrar la
    llave en la Gulp Room (611) --, que no se cumplen hablando con el NPC que
    dio la mision. Ver misiones.interactuar_npc."""
    global _SOLO_INSTANCIA
    if _SOLO_INSTANCIA is None:
        import eventos_mundo as _em
        _arbol(0)
        donde = {}
        for st, arbol in (_TODO or {}).items():
            if not isinstance(arbol, dict) or not str(st).isdigit():
                continue
            for nodo in arbol.values():
                if not isinstance(nodo, dict):
                    continue
                for acc in nodo.get('a') or []:
                    if acc and acc[0] == 4 and len(acc[1]) >= 2:
                        donde.setdefault((int(acc[1][0]), int(acc[1][1])), set()).add(int(st))
        _SOLO_INSTANCIA = frozenset(
            k for k, sts in donde.items()
            if all(_em.grupo_de_instancia(x) is not None for x in sts))
    return _SOLO_INSTANCIA


# ---------------------------------------------------------------------------
# EL ARBOL DEL NPC COMO FUENTE DE SUS MISIONES (10/11/2026, decidido con el
# usuario: "lo mas recomendado y mejor para todo").
#
# Cada NPC de mision tiene en el mapa del cliente su arbol oficial: en que
# orden dice cada linea, cuando ofrece cada mision (el Angel Inspector solo da
# la 606 con la 605 terminada), con que nombre (SET_PLAYERNAME) y que premio
# da (ADD_PROPERTY 32 = exp, 49 = creditos, GIVE_MONEY, CREATE_ITEM) antes del
# SET_STEP que la cierra. La plantilla generica de dialogos.info_flujo_mision
# adivinaba todo eso por posicion y fallaba en ~775 misiones.
#
# Se usa el arbol solo cuando, para ESE jugador, hace algo de mision: entra por
# una rama que mira una mision o acaba en un SET_STEP. Si no, el NPC sigue
# como antes (sus misiones de misiones_completas.json, su dialogo propio).
# ---------------------------------------------------------------------------
CONDICIONES_DE_MISION = frozenset((2, 7, 11, 13))   # QUEST_STEP, QUESTITEM, QUEST_FINISH, QUEST_RUNNING
# Tutorial (51, 57) y Graduation Palace (58): sus NPC llevan un flujo medido
# en captura en app.py (Michael marca hablo_michael, que desbloquea el segundo
# dialogo de los Angeles de faccion; el arbol no lo hace).
STAGES_SIN_ARBOL_DE_MISION = frozenset((51, 57, 58))
ACCION_SET_STEP = 4
_RAICES_NPC = {}


def _destinos(arbol):
    out = set()
    for n in arbol.values():
        if n.get('s'):
            out.add(int(n['s']))
        for _m, d in n.get('o', ()):
            out.add(int(d))
        for r in n.get('r', ()):
            out.add(int(r.get('ir') or 0))
    return out


def raiz_de_mision(stage, retrato):
    """La raiz del arbol del NPC con ese retrato si es la UNICA que mira
    misiones (ramas QUEST_* o algun SET_STEP debajo), o None."""
    clave = (int(stage or 0), int(retrato or 0))
    if clave in _RAICES_NPC:
        return _RAICES_NPC[clave]
    arbol = _arbol(stage, con_sp=False)
    res = None
    if arbol and retrato:
        destinos = _destinos(arbol)
        cands = []
        for k, n in arbol.items():
            if (not str(k).isdigit() or int(k) >= 1000000 or int(k) in destinos
                    or n.get('c') != int(retrato)):
                continue
            if _mira_misiones(arbol, k):
                cands.append(int(k))
        res = cands[0] if len(cands) == 1 else None
    _RAICES_NPC[clave] = res
    return res


def _mira_misiones(arbol, k, visto=None, prof=0):
    """Si debajo de `k` hay ramas QUEST_* o un SET_STEP."""
    visto = set() if visto is None else visto
    if k in visto or prof > 40:
        return False
    visto.add(k)
    n = arbol.get(str(k))
    if not n:
        return False
    if any(a and a[0] == ACCION_SET_STEP for a in n.get('a') or ()):
        return True
    for r in n.get('r', ()):
        if any(c[0] in CONDICIONES_DE_MISION for c in r.get('si', ())):
            return True
    sig = [r.get('ir') for r in n.get('r', ())] + [d for _m, d in n.get('o', ())] + [n.get('s')]
    return any(_mira_misiones(arbol, str(x), visto, prof + 1) for x in sig if x)


def arbol_de_mision_para(stage, retrato, ctx, raiz=None):
    """La raiz del NPC si, para este jugador, su arbol hace algo de mision:
    baja por las ramas que se cumplen y mira si alguna miraba una mision o si
    lo que dice despues (siguiente / opciones) llega a un SET_STEP."""
    if int(stage or 0) in STAGES_SIN_ARBOL_DE_MISION:
        return None
    arbol = _arbol(stage, con_sp=False)
    if raiz is None:
        raiz = raiz_de_mision(stage, retrato)
    elif str(raiz) not in arbol or not _mira_misiones(arbol, str(raiz)):
        # La asociacion NPC -> nodo del MPC identifica al interlocutor,
        # aunque comparta retrato con otra raiz (Healing Lecturer, 60401).
        # Nunca elegir por ese retrato un arbol distinto del NPC conocido.
        return None
    if raiz is None:
        return None
    k, prof, de_mision = str(raiz), 0, False
    while prof < 8:
        n = arbol.get(k)
        if n is None:
            return None
        salto = None
        for rama in n.get('r', ()):
            if _cumple(rama, ctx):
                salto = rama.get('ir')
                if any(c[0] in CONDICIONES_DE_MISION for c in rama.get('si', ())):
                    de_mision = True
                break
        if not salto:
            break
        k, prof = str(salto), prof + 1
    if de_mision or _llega_a_set_step(arbol, k):
        return raiz
    return None


def _llega_a_set_step(arbol, k, visto=None, prof=0):
    """Si desde `k` (sin seguir ramas: lo que se dice y se elige) se llega a
    un SET_STEP."""
    visto = set() if visto is None else visto
    if k in visto or prof > 20:
        return False
    visto.add(k)
    n = arbol.get(str(k))
    if not n:
        return False
    if any(a and a[0] == ACCION_SET_STEP for a in n.get('a') or ()):
        return True
    sig = [d for _m, d in n.get('o', ())] + [n.get('s')]
    return any(_llega_a_set_step(arbol, str(x), visto, prof + 1) for x in sig if x)
