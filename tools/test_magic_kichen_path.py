"""Magic Kichen Path: que la instancia se pueda recorrer de verdad.

Lo que estaba roto. La instancia se dio por hecha con una sola conexion: la
entrada desde Lava Cave y una salida de vuelta, las dos sacadas de los 0x0004
de movimiento de una captura del cliente Global. Y de esa captura salio mal
lo uno y lo otro:

  * la llegada anotada era (67,27) y el mapa del cliente dice (40,14) -- casi
    exactamente la mitad, o sea que esas x/y no venian en casillas;
  * la salida se puso en (62,18) con radio 6, el punto medio de dos casillas
    medidas, cuando el tornado esta en (27,5);
  * 73 <-> 74 se dejo SIN ENLAZAR porque las salidas medidas daban (673,56) y
    (747,468), fuera de un mapa de 345x210.

Nada de eso habia que medirlo: el grafo entero esta en map073.mpc,
map074.mpc y map075.mpc. Ver tools/mapa_del_cliente.py.
"""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))
sys.path.insert(0, str(RAIZ / 'tools'))
import app
import login
import mapa_del_cliente as cli

SALAS = (73, 74, 75)


def _portales(stage):
    return json.loads((RAIZ / 'server' / 'plantillas' / 'portales.json')
                      .read_text(encoding='utf-8'))['mapas'][str(stage)]


def test_el_decodificador_reproduce_lo_medido():
    """La prueba de fondo: el grafo que sale del cliente contra las llegadas
    que el proyecto tiene medidas una por una cruzando portales.

    Si esto se cae, no vale ninguna casilla de las de aqui."""
    assert cli.validar(), 'el cliente ya no reproduce las llegadas medidas'


def test_cada_portal_esta_donde_dice_el_cliente():
    """Casilla, destino y llegada: las tres salen del .mpc, no de una captura."""
    for stage in (69,) + SALAS:
        delcliente = {tuple(e['tile']): e for e in cli.mapa(stage).portales()}
        for p in _portales(stage):
            e = delcliente.get(tuple(p['tile']))
            assert e is not None, (stage, p['tile'], 'no hay objeto ahi')
            assert e['destino'] == p['destino'], (stage, p['tile'],
                                                  e['destino'], p['destino'])
            if p['destino'] is None:
                continue
            pts = cli.llegada(e['destino'], e['tag'])
            assert tuple(p['llegada']) in pts, (stage, p['tile'],
                                                p['llegada'], pts)


def test_las_dos_primeras_salas_van_y_vuelven():
    """Lava Cave -> 73 -> 74 -> 73 -> Lava Cave, sin agujeros."""
    def salidas(stage):
        return {p['destino'] for p in _portales(stage)}
    assert 73 in salidas(69), 'no se entra desde Lava Cave'
    assert 69 in salidas(73), 'no se sale de la sala 1'
    assert 74 in salidas(73), 'la sala 1 no lleva a la 2'
    assert 73 in salidas(74), 'la sala 2 no vuelve a la 1'
    # dos rutas en cada sentido entre 73 y 74, no una
    assert sum(1 for p in _portales(73) if p['destino'] == 74) == 2
    assert sum(1 for p in _portales(74) if p['destino'] == 73) == 2


def test_las_dos_salas_estan_pobladas():
    for stage in (73, 74):
        assert stage in login.PLANTILLAS_POR_STAGE, stage
        d = json.loads((RAIZ / 'server' / 'plantillas'
                        / login.PLANTILLAS_POR_STAGE[stage])
                       .read_text(encoding='utf-8'))
        assert d['stage'] == stage
        assert sum(1 for e in d['spawns'] if e.get('monstruo')) > 50, stage


def test_ningun_spawn_se_sale_del_mapa():
    """Los monstruos vienen de una captura del cliente Global, cuyo 0x0008 se
    dedujo a mano. El mapa del cliente da la medida de verdad."""
    for stage in (73, 74):
        m = cli.mapa(stage)
        d = json.loads((RAIZ / 'server' / 'plantillas'
                        / login.PLANTILLAS_POR_STAGE[stage])
                       .read_text(encoding='utf-8'))
        for e in d['spawns']:
            x, y = e['tile']
            assert 0 <= x < m.ancho and 0 <= y < m.alto, (stage, e['nombre'],
                                                          e['tile'],
                                                          (m.ancho, m.alto))


def test_ninguna_llegada_cae_en_un_tornado():
    """El rebote de Majestic Mansion, pero aqui hay cinco tornados por mapa."""
    for stage in (69,) + SALAS:
        for p in _portales(stage):
            if p['destino'] is None:
                continue
            assert app._portal_en(p['destino'], *p['llegada']) is None, \
                (stage, p['tile'], '->', p['destino'], p['llegada'])


def test_los_tornados_se_dibujan():
    """En 73 y 74 no se veia NINGUN tornado: sus plantillas tienen la lista de
    objetos de mapa vacia, porque los 0x000E del Global miden 26 bytes y no se
    pueden reenviar. Se dibujan desde portales.json, como los de Cybertronica."""
    for stage in (73, 74):
        assert len(login.portales_de(stage)) == len(_portales(stage)), stage
        for b in login.portales_de(stage):
            assert b[:2] == b'\x0e\x00', b[:2].hex()


def test_la_puerta_de_la_devil_kitchen_abre_su_menu():
    """El tornado de (29,203) parecia muerto: su evento solo abre el dialogo
    10109. Pero ese dialogo es un MENU -- mensaje 64932, dos opciones -- y la
    primera entra. Se resolvio al seguir la cadena de dialogos del mapa, que
    es lo mismo que hizo falta para las escaleras de Limitless Tower."""
    puerta = [p for p in _portales(73) if p['tile'] == [29, 203]]
    assert puerta, 'desaparecio la puerta'
    p = puerta[0]
    assert p['preguntar'] is True
    assert p['msg'] == 64932, p['msg']
    assert p['destinos'], 'el menu no lleva a ningun sitio'
    assert app._portal_en(73, 29, 203) is not None, 'no abre al pisarla'


def test_a_la_tercera_sala_solo_se_entra_ganando_la_carrera():
    """La sala 3 (75) ya esta poblada (magic_kichen_path_3.json), pero sigue
    sin tornado que lleve a ella: se entra por el dialogo de victoria de la
    carrera del Annoying Clerk (61102, "You win!"). El paso 74 -> 75 es el
    evento 5 de map074.mpc y NINGUN objeto del mapa lo dispara."""
    assert 75 in login.PLANTILLAS_POR_STAGE
    # los de 75 a 75 son sus dos portales internos, que no cuentan: solo
    # importa que no haya nada que LLEVE a 75 desde fuera.
    assert not any(p['destino'] == 75
                   for s in (69,) + SALAS if s != 75
                   for p in _portales(s))
    e5 = [e for e in cli.mapa(74).portales() if e['evento'] == 5]
    assert not e5, 'ya hay un objeto que dispara el paso a la sala 3'


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
