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

import eventos as ev

log = logging.getLogger(__name__)

RUTA = pathlib.Path(__file__).parent / 'plantillas' / 'dialogos_mapa.json'
MAX_LINEAS = 8

_TODO = None


def _arbol(stage):
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
    if int(stage)==41:
        import olympus,recent_mall
        return {**result,**olympus.datos()['nodes'],**recent_mall.datos()['nodes']}
    return result


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
    arbol = _arbol(stage)
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
    arbol = _arbol(stage)
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
    arbol = _arbol(stage)
    for k in _raices(arbol):
        if (_acciones_debajo(arbol, k, 63, 0)
                and not _acciones_debajo(arbol, k, 63, 1)):
            return k
    return None


def zonas_de_inicio_de_juego(stage):
    """Las zonas que GENERA (accion 31) la raiz que empieza el NPCKILLGAME
    (63, 1): las marcas de "carrera en marcha". En el stage 74 es la 103, que
    la raiz de cierre (61102) mira con GENERATOR_ALIVE."""
    arbol = _arbol(stage)
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
