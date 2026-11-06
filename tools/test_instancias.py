"""Las instancias, todas: entrada abierta, cuartos poblados y sin rebotes.

De que va esto. Durante meses portales.json llevo 35 tornados con el destino
en null, y casi todos eran entradas de instancia con una nota que decia "NO
SE CRUZO" o "identificada por descarte". La razon era siempre la misma: a una
instancia no se entra a voluntad para grabarla con el proxy, asi que no habia
captura y sin captura no se ponia nada.

Resulta que no hacia falta ninguna captura. El mapa del cliente trae:

  * el grafo de portales -- casilla, mapa de destino y TAG de llegada --
    en los eventos del .mpc (tools/mapa_del_cliente.py);
  * y los generadores de monstruos, con el bicho, cuantos, cada cuanto y en
    que zona (tools/poblar_del_cliente.py).

De las 26 entradas que quedaban, 24 traian el CHANGE_MAP escrito en el objeto
del mapa desde el primer dia y dos iban por un menu de dialogo. Lo unico que
faltaba era leerlo.

Este fichero no comprueba una instancia concreta: recorre TODAS y verifica lo
que tiene que cumplirse en cualquiera. Los casos particulares -- el menu de
Blue Ocean, el laberinto de Gulp Room, la puerta dinamica de Magic Kichen --
tienen su propio fichero.
"""
import collections
import json
import pathlib
import struct
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))
import app
import login
import mapa_del_cliente as cli
import poblar_del_cliente as pob

# Los cuartos de instancia que se han abierto, y por donde se entra a cada uno.
CUARTOS = {
    73: 69, 74: 73,                                   # Magic Kichen Path
    76: 71, 77: 76, 78: 76, 79: 78,                   # Gulp Room
    97: 96,                                           # Evil Ship
    98: 90, 101: 90,                                  # las dos Lost Region
    110: 107, 111: 109, 127: 126, 158: 157, 168: 167,
    176: 175, 199: 198, 216: 215, 229: 228, 238: 237,
    252: 251, 281: 280, 292: 291, 302: 301, 313: 312,
    325: 324, 340: 339, 351: 350, 360: 359, 369: 368,
    387: 386, 395: 394, 403: 402, 411: 410, 422: 420,
    # Estas tres no estaban ni anotadas en portales.json: su tornado faltaba
    # entero. Salieron barriendo el cliente en busca de tornados que el json
    # no tuviera, y son las dos mitades del mismo sitio -- Siam Square va a
    # Mahal Altar y Hell Siam Square a Hell Mahal Altar -- mas Botti Palace.
    145: 148, 263: 261, 264: 262,
}


def _portales(stage):
    return json.loads((RAIZ / 'server' / 'plantillas' / 'portales.json')
                      .read_text(encoding='utf-8'))['mapas'].get(str(stage), [])


def _plantilla(stage):
    return json.loads((RAIZ / 'server' / 'plantillas'
                       / login.PLANTILLAS_POR_STAGE[stage])
                      .read_text(encoding='utf-8'))


def test_no_queda_ninguna_entrada_de_instancia_sin_abrir():
    """Ni una. La ultima en caer fue la puerta de la Devil Kitchen de Magic
    Kichen Path: parecia muerta porque su evento solo abre el dialogo 10109,
    pero ese dialogo es un MENU -- mensaje 64932 con dos opciones -- y la
    primera lleva dentro. Se resolvio sola al enseniar al lector de mapas a
    seguir la cadena de dialogos."""
    todos = json.loads((RAIZ / 'server' / 'plantillas' / 'portales.json')
                       .read_text(encoding='utf-8'))['mapas']
    sueltas = []
    for s, lista in todos.items():
        for p in lista or []:
            if (p.get('destino') is None and not p.get('preguntar')
                    and 'INSTANCIA' in (p.get('nota') or '').upper()):
                sueltas.append((int(s), tuple(p['tile'])))
    assert sueltas == [], sueltas


def test_todos_los_cuartos_estan_registrados_y_poblados():
    for st in CUARTOS:
        assert st in login.PLANTILLAS_POR_STAGE, st
        d = _plantilla(st)
        assert d['stage'] == st, st
        mobs = sum(1 for e in d['spawns'] if e.get('monstruo'))
        # Una sala puede empezar vacia si TODO lo suyo sale por evento: el
        # laberinto de Gulp Room (77) solo tiene la zona del Sleeper Nalica,
        # que saca un dialogo.
        if mobs == 0 and 'OLEADAS' in d.get('_nota', ''):
            zonas = {g.get('zona') for g in cli.mapa(st).generadores()}
            assert zonas <= pob.zonas_de_evento(st), st
            continue
        assert mobs > 0, st


def test_el_censo_de_cada_cuarto_es_el_del_cliente():
    """Ni un monstruo inventado: se recuenta contra los generadores del .mpc.

    Se salta los dos de Magic Kichen Path, que son los unicos que se poblaron
    desde una captura (del cliente Global) y no desde aqui."""
    cat = pob._catalogo()
    for st in CUARTOS:
        d = _plantilla(st)
        if 'POBLADO DESDE EL CLIENTE' not in d.get('_nota', ''):
            continue
        delcliente = collections.Counter()
        # Las zonas que saca un evento (GENERATE / ENABLE_GENERATOR) no van en
        # la plantilla: salen con su mecanica. Ver tools/quitar_oleadas.py.
        # Solo en las salas ya limpiadas (las que lo dicen en su nota).
        de_evento = pob.zonas_de_evento(st) if 'OLEADAS' in d.get('_nota', '') else set()
        nivel_mapa = pob._nivel_tipico(cli.mapa(st), cat)
        for g in cli.mapa(st).generadores():
            if g.get('zona') in de_evento:
                continue
            # Los elfos elementales marcadores no son monstruos
            # (pob.MARCADORES): no van en la plantilla.
            if g['cantidad'] and pob.es_marcador(g['tipo'], nivel_mapa):
                continue
            if g['tipo'] in cat:
                # Con el tope: doce generadores de las instancias declaran
                # entre 40 y 200 sobre UN SOLO punto y son de oleada, no una
                # plantacion. Ver TOPE_POR_GENERADOR.
                delcliente[cat[g['tipo']][0]] += max(
                    1, min(pob.TOPE_POR_GENERADOR, g['cantidad']))
        # Los NPC que pone tools/npcs_del_cliente.py tambien salen del .mpc,
        # pero de otro campo (el +22 del objeto, no los generadores), asi que
        # no entran en este recuento de generadores. Lo que se vigila aqui
        # -- ni un monstruo inventado -- sigue igual de estricto.
        # RECORTES PEDIDOS: la plantilla puede bajar a mano lo que el cliente
        # declara, y lo dice en 'recortados' con su motivo en la nota. Los
        # cristales del Evil Eye (79) declaran 30 por zona sobre un solo
        # punto y el usuario los vio amontonados. Solo se puede BAJAR.
        for nombre, n in (d.get('recortados') or {}).items():
            assert n <= delcliente.get(nombre, 0), (st, nombre, n)
            delcliente[nombre] = n
        dela = collections.Counter(e['nombre'] for e in d['spawns']
                                   if e.get('puesto_por') != 'npcs_del_cliente')
        assert dela == delcliente, (st, dela - delcliente, delcliente - dela)


def test_ningun_spawn_se_sale_de_su_mapa():
    for st in CUARTOS:
        m = cli.mapa(st)
        for e in _plantilla(st)['spawns']:
            x, y = e['tile']
            assert 0 <= x < m.ancho and 0 <= y < m.alto, (st, e['nombre'],
                                                          e['tile'])


def test_de_cada_cuarto_se_puede_salir():
    """Una instancia sin salida es una trampa.

    No vale pedir que CADA cuarto tenga un tornado al mundo: el cuarto 2 de
    Magic Kichen Path solo vuelve al cuarto 1, y es el cuarto 1 el que sale a
    Lava Cave. Eso esta bien. Lo que hay que comprobar es que andando por los
    portales se LLEGUE a un mapa que no sea de instancia."""
    for st in CUARTOS:
        vistos, cola, salida = set(), [st], None
        while cola and salida is None:
            x = cola.pop(0)
            if x in vistos:
                continue
            vistos.add(x)
            for p in _portales(x):
                candidatos = [p.get('destino')]
                candidatos += [v.get('destino')
                               for v in (p.get('destinos') or {}).values()]
                for dest in candidatos:
                    if dest is None:
                        continue
                    if dest not in CUARTOS:
                        salida = (x, dest)
                        break
                    cola.append(dest)
        assert salida, (st, 'no se llega a ningun mapa de fuera',
                        sorted(vistos))


def test_la_entrada_lleva_al_cuarto_y_el_cuarto_devuelve():
    for cuarto, entrada in CUARTOS.items():
        ida = [p for p in _portales(entrada)
               if p.get('destino') == cuarto
               or str(cuarto) in {str(v.get('destino'))
                                  for v in (p.get('destinos') or {}).values()}]
        assert ida, (entrada, '->', cuarto, 'no hay ida')


def test_ninguna_llegada_nueva_cae_en_un_tornado():
    """El rebote de Majestic Mansion, comprobado en todo lo que se ha abierto.

    Los cuatro rebotes que quedan en el json son ANTERIORES a esto y ninguno
    esta en un mapa de instancia; uno de ellos, el del nudo de Teddy
    Amusement, esta documentado como esperado en su propia nota."""
    for st in list(CUARTOS) + sorted(set(CUARTOS.values())):
        for p in _portales(st):
            destinos = [{'destino': p.get('destino'), 'llegada': p.get('llegada')}]
            destinos += list((p.get('destinos') or {}).values())
            for d in destinos:
                if d.get('destino') is None or not d.get('llegada'):
                    continue
                assert app._portal_en(d['destino'], *d['llegada']) is None, \
                    (st, p['tile'], '->', d['destino'], d['llegada'],
                     'radio', p.get('radio'))


def test_los_tornados_inertes_no_disparan():
    for st in CUARTOS:
        for p in _portales(st):
            if p.get('destino') is None and not p.get('preguntar'):
                assert app._portal_en(st, *p['tile']) is None, (st, p['tile'])


def test_cada_cuarto_manda_sus_objetos_una_sola_vez():
    """poblar() junta los objetos de la plantilla y los tornados dibujados
    desde portales.json. Si un tornado saliera por los dos lados tendria dos
    ids de entidad y el clic solo funcionaria en uno."""
    for st in CUARTOS:
        ids = [struct.unpack_from('<I', b, 2)[0]
               for b in login.poblar(st) if b[:2] == b'\x0e\x00']
        assert len(ids) == len(set(ids)), st
        # Solo los portales que SE DIBUJAN cuentan: los pasos que no son
        # el tornado 60001 van sin dibujar, porque el cliente ya pinta ese
        # objeto por su cuenta y sacarlo otra vez lo pondria con figura de
        # tornado.
        dibujados = [p for p in _portales(st) if p.get('dibujar')]
        assert len(ids) == len(_plantilla(st)['recursos']) + len(dibujados), st
        assert not [r for r in _plantilla(st)['recursos']
                    if r['sprite'] == cli.TORNADO], st


def test_los_entity_id_no_chocan_entre_si():
    """Monstruos en 50_000_000, objetos de mapa en 60_000_000 y tornados en
    70_000_000: bandas separadas a proposito."""
    for st in CUARTOS:
        d = _plantilla(st)
        ids = [e['entity_id'] for e in d['spawns']]
        ids += [r['entity_id'] for r in d['recursos']]
        ids += [p['entity'] for p in _portales(st) if p.get('entity')]
        assert len(ids) == len(set(ids)), (st, len(ids), len(set(ids)))


def test_los_bichos_no_salen_amontonados():
    """La densidad se calibra con los mapas CAPTURADOS, que son como se ve el
    juego: ahi hay 4 monstruos por celda de 10x10 de mediana, 6 en el p90 y
    10 en el peor. Con la separacion mal puesta salian 25 -- la saturacion --
    y en pantalla era un muro de bichos sin ver el suelo."""
    for st in CUARTOS:
        d = _plantilla(st)
        if 'POBLADO DESDE EL CLIENTE' not in d.get('_nota', ''):
            continue
        sp = [e for e in d['spawns'] if e.get('monstruo')]
        celda = collections.Counter(((e['tile'][0] // 10) * 10,
                                     (e['tile'][1] // 10) * 10) for e in sp)
        peor = celda.most_common(1)[0][1] if celda else 0
        assert peor <= 10, (st, peor, 'mas apretados que el peor mapa real')


def test_en_las_instancias_los_bichos_no_reviven():
    """Una instancia se limpia y se queda limpia: lo que matas no vuelve
    hasta que sales y entras otra vez, y entonces el servidor te rehace el
    mapa entero con _monstruos_de(). Lo conto el usuario jugando."""
    for st in CUARTOS:
        assert app.es_instancia(st), st
    fuente = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')
    assert 'if not _en_instancia and m.toca_reaparecer():' in fuente,         'volvio el respawn dentro de las instancias'
    assert 'En una instancia lo que matas se queda muerto' in fuente,         'volvio el respawn del monstruo recien muerto'


def test_la_ia_no_piensa_los_bichos_de_lejos():
    """El bucle de IA corre diez veces por segundo sobre los monstruos del
    mapa. Con 584 en Leviathan's Bedroom eran casi seis mil vueltas por
    segundo y el juego iba a tirones."""
    fuente = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')
    assert 'RADIO_IA' in fuente and 'abs(m.tile_y - _py)) > RADIO_IA' in fuente,         'desaparecio la puerta de distancia de la IA'
    assert "getattr(m, 'en_combate_con', None)" in fuente,         'la puerta tiene que dejar pasar a los que estan peleando'


def test_el_metodo_sigue_reproduciendo_lo_medido():
    """La prueba de fondo de todo esto: el grafo del cliente contra las
    llegadas que el proyecto midio cruzando portales a mano."""
    assert cli.validar()
    assert pob.validar()


if __name__ == '__main__':
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith('test_') and callable(fn):
            try:
                fn()
                print('  OK    %s' % nombre)
            except AssertionError as e:
                fallos += 1
                print('  FALLA %s: %s' % (nombre, e))
    print('fallos:', fallos)
    raise SystemExit(1 if fallos else 0)
