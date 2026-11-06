"""Escribe en portales.json los tornados de un mapa, leidos del cliente.

Lo que hacia falta medir cruzando cada tornado con el cliente oficial delante
esta en el .mpc del propio mapa: la casilla del tornado, a que mapa manda y a
que TAG llega. Ver tools/mapa_del_cliente.py, que ademas comprueba el metodo
contra las 546 llegadas que portales.json tiene medidas a mano y reproduce
todas.

QUE RESPETA Y QUE NO:

  * una entrada que ya tiene llegada MEDIDA y cuadra con el cliente se deja
    intacta, con su nota y su entidad. Las medidas no se pisan;
  * una entrada con destino en null -- las 35 que hay, casi todas entradas de
    instancia sin cruzar -- se rellena;
  * los tornados que el cliente declara y no estan en el json se anaden.

DE LAS CASILLAS DEL TAG se elige una, porque portales.json guarda una sola y
el servidor real coge una al azar (medido: de 546 llegadas, 183 cayeron en la
primera, 190 en la segunda y 173 en la tercera). Se prefiere, por orden:

  1. la que confirme jumpmap.xml, si hay una fila suya para ese mapa. Son
     dos fuentes independientes del cliente diciendo lo mismo;
  2. la que quede mas lejos de todos los tornados del mapa de destino, para
     que el jugador no aterrice dentro de uno y rebote.

Uso:
    python tools/propagar_portales.py --stages 71 76 77 78 79
    python tools/propagar_portales.py --stages 76 --seco
"""
import argparse
import collections
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import mapa_del_cliente as cli

TORNADO_ID = cli.TORNADO

PORTALES = RAIZ / 'server' / 'plantillas' / 'portales.json'
RADIO = 3
# DE DONDE SALEN LOS IDS DE ENTIDAD de los tornados que se dibujan.
#
# Los primeros que se dibujaron a mano fueron al bloque 700-899: el 700-718
# para los de Cybertronica y el 720-732 para Magic Kichen Path. Ese bloque se
# agoto en cuanto se abrieron las instancias de verdad -- Floral Palace tiene
# 103 tornados en un solo mapa y Limitless Tower 23 -- asi que los nuevos van
# a una banda propia, calculada y no repartida:
#
#     70_000_000 + stage * 1000 + k
#
# Queda globalmente unico mientras un mapa no pase de 1000 tornados (el que
# mas tiene son 103), y eso importa porque el manejador del clic busca la
# entidad en TODOS los mapas, no solo en el del jugador. Y no choca con nada:
# los monstruos del cliente van en 50_000_000, los objetos de mapa en
# 60_000_000, los NPC de los xml a partir del 900 y los totems del 300.
#
# Lo que ya tiene entidad NO se le cambia: si un tornado estaba capturado del
# servidor real, se conserva su id.
ENTIDAD_MIN, ENTIDAD_MAX = 700, 899
BASE_ENTIDAD = 70_000_000


def _entidades_de(stage, ya_usadas=()):
    """Ids libres para los tornados de ese mapa.

    Hay que saltarse los que ya tiene el mapa: al volver a pasar por un
    stage, las entradas que se conservan guardan su id y el contador
    empezaba otra vez desde cero, asi que los nuevos chocaban con ellas.
    Paso en Leviathan's Bedroom y dos tornados quedaron con la misma
    entidad."""
    usadas = set(ya_usadas)
    k = 0
    while True:
        n = BASE_ENTIDAD + stage * 1000 + k
        if n not in usadas:
            yield n
        k += 1


def jumpmap():
    """(stage, x, y) de cada fila de jumpmap.xml, la version mas nueva.

    Es la ventana de salto del cliente. Sirve de segunda fuente: de sus 32
    filas de categoria 19 ("Instance"), 16 caen EXACTAMENTE sobre un TAG del
    .mpc y el resto a entre 1 y 9 casillas.
    """
    cands = sorted((RAIZ / 'extracted_paks').glob('*/setting/*/jumpmap.xml'),
                   key=lambda p: p.stat().st_size)
    if not cands:
        return {}
    t = cands[-1].read_text(encoding='utf-8', errors='replace')
    por_stage = {}
    # OJO: estas cadenas NO pueden llevar r''. En una cadena cruda el \u no
    # se interpreta y la regex buscaria el texto literal "跳". Ya paso:
    # jumpmap() devolvia cero filas sin dar ningun error.
    etiqueta = '跳地圖'            # el nodo
    c_stage = '場景編號'       # el mapa
    c_x = '傳送座標X'          # el 5ea7 es ZUO de "asiento",
    c_y = '傳送座標Y'          # no el 5750, que se parece
    for s in re.findall('<' + etiqueta + '([^>]*)/>', t):
        def at(k):
            m = re.search(k + '="([^"]*)"', s)
            return m.group(1) if m else None
        st = at(c_stage)
        x, y = at(c_x), at(c_y)
        if st and x and y:
            por_stage.setdefault(int(st), []).append((int(x), int(y)))
    return por_stage


def elegir_llegada(destino, tag, jm):
    """La casilla de llegada, por que esa, y cuanto radio aguanta el tornado.

    La holgura es el radio MAS GRANDE con el que ningun tornado del mapa de
    destino alcanza la casilla de llegada. Hace falta porque con el radio 3
    de siempre hay tres portales internos -- uno de Blizarro Castle y dos de
    Dragon's Lair -- cuyas casillas de llegada caen TODAS dentro del radio de
    otro tornado del mismo mapa. Ahi el radio se baja a lo que quepa.
    """
    pts = cli.llegada(destino, tag)
    if not pts:
        return None, None, RADIO
    m = cli.mapa(destino)
    tornados = [e['tile'] for e in m.portales() if e['pisar']] if m else []

    def holgura(p):
        if not tornados:
            return 99
        return min(max(abs(t[0] - p[0]), abs(t[1] - p[1]))
                   for t in tornados) - 1

    confirmadas = [p for p in pts if p in jm.get(destino, [])]
    if confirmadas:
        p = max(confirmadas, key=holgura)
        return p, 'la confirma jumpmap.xml', holgura(p)
    p = max(pts, key=holgura)
    return (p, 'la mas despejada de las %d del TAG' % len(pts), holgura(p))


NOTA = (
    'Del mapa del cliente: map%03d.mpc, objeto 60001 en esa casilla, evento '
    '%d, que hace %s. %s %s Metodo comprobado contra las 546 llegadas que '
    'este json tiene medidas cruzando portales una por una: reproduce todas. '
    'Ver tools/mapa_del_cliente.py y tools/propagar_portales.py.')


def _agrupar(pasos):
    """Una escalera es UN paso, no seis.

    Los pasos que no son el tornado 60001 vienen en racimos: en Botti Palace
    hay seis objetos pegados -- de (151,124) a (156,129) -- colgados todos
    del mismo evento, porque juntos dibujan una escalera. Metiendolos uno a
    uno salian seis entradas para el mismo sitio, con casillas repetidas, y
    ademas la llegada del otro extremo caia pegada a uno de ellos y no habia
    radio que lo evitara: el minimo es 1 y con 1 ya lo tocaba.

    Se juntan los del mismo evento que esten a dos casillas o menos y se
    deja uno por racimo, el mas cercano al centro.
    """
    porevento = collections.defaultdict(list)
    for x in pasos:
        porevento[(x['evento'], x['objeto'])].append(x)
    salida = []
    for grupo in porevento.values():
        if grupo[0]['objeto'] == TORNADO_ID or len(grupo) == 1:
            salida.extend(grupo)
            continue
        quedan = list(grupo)
        while quedan:
            racimo, cola = [quedan.pop(0)], None
            cambio = True
            while cambio:
                cambio = False
                for x in list(quedan):
                    if any(max(abs(x['tile'][0] - y['tile'][0]),
                               abs(x['tile'][1] - y['tile'][1])) <= 2
                           for y in racimo):
                        racimo.append(x)
                        quedan.remove(x)
                        cambio = True
            cx = sum(y['tile'][0] for y in racimo) / len(racimo)
            cy = sum(y['tile'][1] for y in racimo) / len(racimo)
            salida.append(min(racimo, key=lambda y: (y['tile'][0] - cx) ** 2
                              + (y['tile'][1] - cy) ** 2))
    return salida


MARCA = 'propagar_portales.py'       # los que escribio esta herramienta


def arreglar_entidades(mapas):
    """Que no haya dos tornados con el mismo id dentro de un mapa.

    El cliente identifica cada objeto por su id, asi que dos con el mismo son
    uno solo: el segundo no se dibuja y clicarlo lleva al primero. Se renumera
    el repetido, y solo si lo escribio esta herramienta -- un id capturado del
    servidor real no se toca."""
    tocados = 0
    for s, lista in mapas.items():
        vistos = set()
        libres = _entidades_de(int(s), {p.get('entity') for p in (lista or [])})
        for p in lista or []:
            e = p.get('entity')
            if e is not None and e not in vistos:
                vistos.add(e)
                continue
            if MARCA not in (p.get('nota') or ''):
                continue
            nuevo = next(libres)
            while nuevo in vistos:
                nuevo = next(libres)
            p['entity'] = nuevo
            vistos.add(nuevo)
            tocados += 1
    return tocados


def ajustar_radios(mapas):
    """Encoge el radio de cada tornado para que no pise una casilla de llegada.

    Elegir bien la casilla de llegada NO basta, y se vio: en Blizarro Castle
    y en Dragon's Lair quedaban tres rebotes aunque se cogiera la casilla mas
    despejada del TAG. El motivo es que el rebote no lo causa el radio del
    tornado por el que viajas, sino el del OTRO tornado sobre cuya zona
    aterrizas, y ese esta en otra entrada del json -- o incluso en otro mapa,
    porque a un mapa se llega desde varios.

    Asi que al final se recogen TODAS las casillas de llegada que caen en cada
    mapa, vengan de donde vengan, y se baja el radio de cada tornado hasta que
    no alcance ninguna.

    Los radios MEDIDOS no se tocan: solo los de las entradas que escribio
    esta herramienta. Un radio medido ya se eligio en su dia para no rebotar
    -- el de Majestic Mansion vale 1 justo por eso -- y pisarlo seria tirar
    una medida.
    """
    llegadas = collections.defaultdict(set)
    for lista in mapas.values():
        for p in lista or []:
            cand = [(p.get('destino'), p.get('llegada'))]
            cand += [(v.get('destino'), v.get('llegada'))
                     for v in (p.get('destinos') or {}).values()]
            for dest, lleg in cand:
                if dest is not None and lleg:
                    llegadas[int(dest)].add((lleg[0], lleg[1]))
    tocados = 0
    for s, lista in mapas.items():
        aqui = llegadas.get(int(s), set())
        for p in lista or []:
            if MARCA not in (p.get('nota') or ''):
                continue
            tx, ty = p['tile']
            propia = tuple(p['llegada']) if p.get('llegada') else None
            tope = RADIO
            for (lx, ly) in aqui:
                if (lx, ly) == propia and int(s) != (p.get('destino') or -1):
                    # La llegada de ESTE tornado en OTRO mapa no cuenta.
                    continue
                tope = min(tope, max(abs(tx - lx), abs(ty - ly)) - 1)
            nuevo = max(1, min(RADIO, tope))
            if nuevo != p.get('radio'):
                p['radio'] = nuevo
                if 'RADIO ajustado' not in p['nota']:
                    p['nota'] += (' RADIO ajustado a %d para que no alcance '
                                  'ninguna casilla de llegada de este mapa.'
                                  % nuevo)
                tocados += 1
    return tocados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stages', type=int, nargs='+', required=True)
    ap.add_argument('--seco', action='store_true', help='no escribir')
    a = ap.parse_args()

    d = json.loads(PORTALES.read_text(encoding='utf-8'))
    mapas = d['mapas']
    jm = jumpmap()

    for stage in a.stages:
        m = cli.mapa(stage)
        if m is None:
            print('stage %d: el cliente no trae el mapa' % stage)
            continue
        viejas = {tuple(p['tile']): p for p in (mapas.get(str(stage)) or [])}
        libres = _entidades_de(stage, {p.get('entity') for p in viejas.values()})
        nuevas, resumen, gastadas = [], [], set()
        # NO TODO LO QUE TELETRANSPORTA ES UN TORNADO. Mirando solo el objeto
        # 60001 se quedaban fuera 429 pasos repartidos por doce instancias:
        # las escaleras 60305, las 60461, la 60416 de Leviathan's Bedroom que
        # lleva a la zona de los jefes... y sin ellas media instancia no se
        # puede recorrer. Se meten todos.
        #
        # MENOS LAS ALFOMBRAS. Cuando el MISMO evento lo disparan mas de
        # veinte objetos no es un paso, es una superficie: en Gulp Room 3 hay
        # 274 objetos 60157 colgados del evento 101. Poner 274 teletransportes
        # con radio alcanzaria casi cualquier casilla del mapa y no se podria
        # ni andar, asi que esos se dejan fuera y se cuentan aparte.
        todos = m.portales(solo_tornados=False)
        porevento = collections.Counter(x['evento'] for x in todos)
        alfombras = sum(1 for x in todos if porevento[x['evento']] > 20)
        if alfombras:
            print('   (%d objetos de superficie, con mas de 20 por evento, '
                  'se dejan fuera)' % alfombras)
        for e in sorted(_agrupar([x for x in todos
                                  if porevento[x['evento']] <= 20]),
                        key=lambda e: e['evento']):
            t = tuple(e['tile'])
            # UNA ENTRADA VIEJA SOLO SE HEREDA UNA VEZ. Se busca por
            # cercania (+-3 casillas) y, con los pasos que no son tornado,
            # dos objetos distintos caian dentro del margen de la MISMA
            # entrada vieja: los dos se quedaban con su id de entidad y el
            # mapa acababa con tornados duplicados. En Gulp Room 3 fueron 25.
            previa = None
            for vt, vp in viejas.items():
                if (vt not in gastadas
                        and abs(vt[0] - t[0]) <= 3 and abs(vt[1] - t[1]) <= 3):
                    previa = vp
                    gastadas.add(vt)
                    break
            menu = None
            tras_dialogo = None
            if e['destino'] is None:
                # ESCALERA CON CONDICION. Un tornado cuyo evento solo abre un
                # dialogo no siempre es una puerta muerta: muchas veces el
                # dialogo lleva el viaje detras, pasando por una condicion.
                # Las de Limitless Tower son asi -- dialogo 5002, mensaje
                # 65390 "The monsters nearby are staring menacingly at you.
                # You had better not go upstairs!", condicion 14
                # (GENERATOR_ALIVE del tag 93) y, si el piso esta limpio,
                # GOTO_TAG(3). Dejandolas inertes la torre no se puede subir,
                # que es justo lo que paso.
                #
                # LA CONDICION NO SE MODELA: aqui se deja pasar siempre. Es lo
                # mismo que ya se hace con PARA_ENTER en los menus. Queda
                # anotado en la nota de cada una para cuando se implemente.
                for n, p in e['acciones']:
                    if n == 25 and p:
                        tras_dialogo = (m._viaje_tras(p[0]), p[0])
                        if tras_dialogo[0]:
                            break
                        tras_dialogo = None
            if e['destino'] is None:
                # PORTAL CON MENU. Su evento no viaja: abre un dialogo, y las
                # opciones de ese dialogo son las que llevan a un sitio o a
                # otro. Es como esta el de Blue Ocean, que ofrece Lost Region
                # y Horrible Lost Region con el mismo tornado.
                for n, p in e['acciones']:
                    if n == 25 and p:
                        menu = m.menu_de(p[0])
                        if menu:
                            menu['dialogo'] = p[0]
                            break
            if menu:
                destinos = {}
                for o in menu['opciones']:
                    if not o['viaje']:
                        continue
                    pt, _pq, _h = elegir_llegada(o['viaje'][0], o['viaje'][1], jm)
                    destinos[str(o['msg'])] = {'destino': o['viaje'][0],
                                               'llegada': list(pt) if pt else None}
                nuevas.append({
                    'entity': (previa or {}).get('entity') or next(libres),
                    'tile': [t[0], t[1]],
                    'destino': None,
                    'llegada': None,
                    'radio': (previa or {}).get('radio') or RADIO,
                    'dibujar': bool((previa or {}).get('dibujar', True)),
                    'preguntar': True,
                    'msg': menu['msg'],
                    'opciones': [o['msg'] for o in menu['opciones']],
                    'acciones': [o['siguiente'] for o in menu['opciones']],
                    'destinos': destinos,
                    'nota': (
                        'PORTAL CON MENU, del mapa del cliente: map%03d.mpc, '
                        'objeto 60001 en esa casilla, evento %d, y su unica '
                        'accion es abrir el dialogo %d. Ese dialogo es el que '
                        'lleva a un sitio o a otro: cada opcion apunta con '
                        '"siguiente" a otro nodo, que comprueba EVENT_COND 22 '
                        '(PARA_ENTER, si cabe alguien en la instancia) y, si '
                        'se cumple, hace el CHANGE_MAP. La capacidad NO se '
                        'modela: aqui siempre se deja entrar. Destinos: %s. '
                        'Ver tools/mapa_del_cliente.py (menu_de) y '
                        'tools/propagar_portales.py.'
                        % (stage, e['evento'], menu['dialogo'],
                           {k: (v['destino'], v['llegada'])
                            for k, v in destinos.items()})),
                })
                resumen.append(('M', t, 'menu',
                                [(v['destino'], v['llegada'])
                                 for v in destinos.values()],
                                'dialogo %d' % menu['dialogo']))
                continue
            if tras_dialogo:
                (dmapa, dtag), ddlg = tras_dialogo
                llegada, porque, holgura = elegir_llegada(dmapa, dtag, jm)
                accion = ('abrir el dialogo %d, que detras lleva %s'
                          % (ddlg, ('CHANGE_MAP(%d, %d)' % (dmapa, dtag)
                                    if dmapa != stage
                                    else 'GOTO_TAG(%d)' % dtag)))
                porque = (porque + '. ESCALERA CON CONDICION: en el juego de '
                          'verdad el dialogo comprueba algo antes de dejar '
                          'pasar -- en Limitless Tower, que el piso este '
                          'limpio de bichos. Esa condicion NO se modela y '
                          'aqui se pasa siempre; sin esto el tornado quedaba '
                          'muerto y la instancia no se podia recorrer')
                e = dict(e, destino=dmapa, tag=dtag)
            elif e['destino'] is None:
                llegada, porque, holgura = (
                    None, 'su evento no viaja, solo saca dialogo', RADIO)
                accion = 'sacar el dialogo %s' % (
                    [p for n, p in e['acciones'] if n == 25] or '?')
            else:
                llegada, porque, holgura = elegir_llegada(e['destino'],
                                                          e['tag'], jm)
                accion = ('CHANGE_MAP(%d, %d)' % (e['destino'], e['tag'])
                          if e['destino'] != stage
                          else 'GOTO_TAG(%d)' % e['tag'])
            # Una entrada ya MEDIDA que cuadra con el cliente no se toca.
            if (previa and previa.get('destino') == e['destino']
                    and previa.get('llegada')
                    and tuple(previa['llegada']) in cli.llegada(e['destino'],
                                                                e['tag'])):
                nuevas.append(previa)
                resumen.append(('=', t, previa['destino'], previa['llegada'],
                                'ya medida, se deja'))
                continue
            entidad = (previa or {}).get('entity') or next(libres)
            nota = NOTA % (stage, e['evento'], accion,
                           ('Llegada %s: %s.' % (llegada, porque)
                            if llegada else (porque or 'sin llegada en el cliente') + '.'),
                           ('Las casillas del TAG son %s y el servidor coge '
                            'una al azar.' % (cli.llegada(e['destino'],
                                                          e['tag']),)
                            if llegada else ''))
            if previa and previa.get('destino') is None and previa.get('nota'):
                nota = ('ACTIVADA desde el cliente. ' + nota
                        + ' Lo que decia antes: ' + previa['nota'])
            nuevas.append({
                'entity': entidad,
                'tile': [t[0], t[1]],
                'destino': e['destino'],
                'llegada': list(llegada) if llegada else None,
                # El radio NO se hereda del json: las entradas que este
                # propagador toca son las que no estan medidas, y la medida
                # buena es la que sale del cliente. Las que SI estan medidas
                # salen antes por el camino del '=' y no llegan aqui.
                # Los que no son el tornado 60001 van con RADIO 1 -- hay que
                # pisarlos -- y SIN dibujar: el cliente ya pinta ese objeto
                # por su cuenta, y dibujarlo lo sacaria con la figura del
                # tornado, que no es la suya.
                'radio': (1 if e['objeto'] != cli.TORNADO
                          else max(1, min(RADIO, holgura))),
                'dibujar': bool((previa or {}).get(
                    'dibujar', e['objeto'] == cli.TORNADO)),
                'preguntar': bool((previa or {}).get('preguntar', False)),
                'nota': nota + (
                    ' RADIO %d y no %d: con el de siempre la casilla de '
                    'llegada de este tornado caeria dentro de otro del mismo '
                    'mapa y el jugador rebotaria.'
                    % (max(1, min(RADIO, holgura)), RADIO)
                    if holgura < RADIO else ''),
            })
            resumen.append(('+' if previa is None else '*', t, e['destino'],
                            llegada, porque))
        # Los tornados que el json tenia y el cliente no declara se conservan.
        decliente = {tuple(p['tile']) for p in nuevas}
        for vt, vp in viejas.items():
            if not any(abs(vt[0] - t[0]) <= 3 and abs(vt[1] - t[1]) <= 3
                       for t in decliente):
                nuevas.append(vp)
                resumen.append(('?', vt, vp.get('destino'), vp.get('llegada'),
                                'no esta en el .mpc, se conserva'))
        mapas[str(stage)] = nuevas
        print('== stage %d: %d tornados' % (stage, len(nuevas)))
        for marca, t, dest, lleg, porque in resumen:
            print('   %s %-12s -> %-5s %-12s %s'
                  % (marca, t, dest, lleg, porque))

    tocados = ajustar_radios(mapas)
    repetidas = arreglar_entidades(mapas)
    if a.seco:
        print('\n(seco: no se escribio nada; se habrian ajustado %d radios)'
              % tocados)
        return
    PORTALES.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                        encoding='utf-8')
    print('\nradios ajustados para que nadie rebote: %d' % tocados)
    print('portales.json reescrito')


if __name__ == '__main__':
    main()
