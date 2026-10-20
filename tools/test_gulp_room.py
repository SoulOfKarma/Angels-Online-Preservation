"""Gulp Room: la instancia de Underground Square, abierta y poblada.

La entrada, el tornado de (252,24) del stage 71, llevaba meses en
portales.json con destino en null y una nota que decia que estaba
"identificada por descarte" y "NO SE CRUZO". Y los cuatro cuartos -- 76, 77,
78 y 79 -- no tenian plantilla ninguna.

Ninguna captura del proyecto entro ahi jamas: de las 1230 sesiones de mundo
grabadas, cero paquetes 0x0008 en esos cuatro mapas. Asi que no salio de una
captura, salio del cliente:

  * los portales, de los eventos de los .mpc (tools/mapa_del_cliente.py);
  * la llegada del 76 al 71, confirmada ADEMAS por jumpmap.xml, que es una
    segunda fuente independiente dentro del propio cliente;
  * los monstruos, de los generadores que trae cada .mpc
    (tools/poblar_del_cliente.py).

Y el censo que sale cuadra con la ficha de Gulp Room de la wiki del juego,
que es una tercera fuente, de fuera del cliente: Fire Mummy, Dark Protector,
Earl Makice, Overlord Legte, Lion Dragon, Flamen Tomomy, Trapped Shar, Evil
Eye, Demon Kidace, Glutton, Demon Bazac...
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
import poblar_del_cliente as pob
import propagar_portales as prop

CUARTOS = (76, 77, 78, 79)
ENTRADA = 71


def _portales(stage):
    return json.loads((RAIZ / 'server' / 'plantillas' / 'portales.json')
                      .read_text(encoding='utf-8'))['mapas'][str(stage)]


def _plantilla(stage):
    return json.loads((RAIZ / 'server' / 'plantillas'
                       / login.PLANTILLAS_POR_STAGE[stage])
                      .read_text(encoding='utf-8'))


def test_la_entrada_ya_no_esta_en_null():
    """Era el unico tornado sin destino de Underground Square."""
    p = [x for x in _portales(ENTRADA) if x['tile'] == [252, 24]]
    assert p, 'desaparecio el tornado de (252,24)'
    assert p[0]['destino'] == 76, p[0]['destino']
    assert p[0]['llegada'], 'sin casilla de llegada'
    assert not any(x['destino'] is None for x in _portales(ENTRADA)), \
        'quedan tornados sin destino en Underground Square'


def test_las_dos_medidas_de_underground_square_siguen_intactas():
    """Propagar no puede pisar lo que se midio cruzando. Los otros dos
    tornados del 71 estaban medidos: a Flaming Door y a Hell Palace."""
    por = {tuple(p['tile']): p for p in _portales(ENTRADA)}
    assert por[(9, 9)]['destino'] == 70 and por[(9, 9)]['llegada'] == [287, 149]
    assert por[(264, 149)]['destino'] == 72 and por[(264, 149)]['llegada'] == [28, 29]


def test_jumpmap_confirma_la_vuelta_al_71():
    """Dos fuentes del cliente diciendo lo mismo: el TAG 2 de map071.mpc y la
    fila 73 de jumpmap.xml, que es la de categoria 19 ("Instance")."""
    jm = prop.jumpmap()
    assert (244, 20) in jm.get(71, []), jm.get(71)
    assert (244, 20) in cli.llegada(71, 2), cli.llegada(71, 2)
    vuelta = [p for p in _portales(76) if p['destino'] == 71]
    assert vuelta and vuelta[0]['llegada'] == [244, 20], vuelta


def test_los_cuatro_cuartos_se_recorren():
    def dest(st):
        return {p['destino'] for p in _portales(st)}
    assert 76 in dest(71), 'no se entra'
    assert 71 in dest(76), 'no se sale'
    assert 77 in dest(76) and 76 in dest(77), '76 <-> 77'
    assert 78 in dest(76) and 76 in dest(78), '76 <-> 78'
    assert 79 in dest(78) and 78 in dest(79), '78 <-> 79'


def test_el_laberinto_del_77_esta_entero():
    """El cuarto 2 es un laberinto de tornados: 52 en total, 46 internos y
    seis que sacan al 76. Si faltan, no se puede atravesar."""
    por = _portales(77)
    assert len(por) == 52, len(por)
    internos = [p for p in por if p['destino'] == 77]
    assert len(internos) == 46, len(internos)
    assert sum(1 for p in por if p['destino'] == 76) == 6


def test_los_cuartos_estan_poblados():
    # Sin las zonas que solo salen POR EVENTO (jefes y oleadas, ver
    # poblar_del_cliente.zonas_de_evento) y con los cristales del Evil Eye
    # recortados a uno por generador (gulp_room_4.json, 'recortados').
    esperado = {76: 209, 77: 0, 78: 69, 79: 309}
    for st in CUARTOS:
        assert st in login.PLANTILLAS_POR_STAGE, st
        d = _plantilla(st)
        assert d['stage'] == st
        mobs = sum(1 for e in d['spawns'] if e.get('monstruo'))
        assert mobs == esperado[st], (st, mobs, esperado[st])


def test_el_censo_es_el_que_declara_el_cliente():
    """Nada de monstruos inventados: uno a uno salen del .mpc."""
    import collections
    cat = pob._catalogo()
    for st in CUARTOS:
        m = cli.mapa(st)
        fuera = pob.zonas_de_evento(st)
        delcliente = collections.Counter()
        for g in m.generadores():
            if g['tipo'] in cat and not (g['zona'] and g['zona'] in fuera):
                delcliente[cat[g['tipo']][0]] += max(
                    1, min(pob.TOPE_POR_GENERADOR, g['cantidad']))
        d = _plantilla(st)
        for nombre, n in (d.get('recortados') or {}).items():
            assert n <= delcliente.get(nombre, 0), (st, nombre, n)
            delcliente[nombre] = n
        dela = collections.Counter(e['nombre'] for e in d['spawns']
                                   if e.get('puesto_por') != 'npcs_del_cliente')
        assert dela == delcliente, (st, dela - delcliente, delcliente - dela)


def test_los_cuartos_tienen_sus_objetos_de_mapa():
    """Un mapa sin objetos se ve vacio. Los que el servidor manda de verdad
    se sacan del .mpc y su cuerpo se copia de una captura del mismo objeto."""
    esperado = {76: 33, 77: 91, 78: 281, 79: 32}
    for st in CUARTOS:
        rec = _plantilla(st)['recursos']
        assert len(rec) == esperado[st], (st, len(rec), esperado[st])
        for r in rec:
            assert len(bytes.fromhex(r['crudo'])) == 43, (st, r['sprite'])


def test_los_tornados_no_se_mandan_dos_veces():
    """El 60001 esta en la lista de objetos que el servidor manda, asi que
    salia por recursos Y por portales.json: en el cuarto 2 habrian sido 52
    tornados duplicados, con dos entidades cada uno y el clic funcionando
    solo en una."""
    import struct
    for st in CUARTOS:
        assert not [r for r in _plantilla(st)['recursos']
                    if r['sprite'] == 60001], st
        ids = [struct.unpack_from('<I', b, 2)[0]
               for b in login.poblar(st) if b[:2] == b'\x0e\x00']
        assert len(ids) == len(set(ids)), st
        # Solo cuentan los portales que SE DIBUJAN: los pasos que no son el
        # tornado 60001 van sin dibujar, porque el cliente ya pinta ese objeto
        # y volver a sacarlo lo pondria con figura de tornado.
        dibujados = [p for p in _portales(st) if p.get('dibujar')]
        assert len(ids) == (len(_plantilla(st)['recursos'])
                            + len(dibujados)), st


def test_clicar_un_tornado_sin_destino_no_tumba_la_sesion():
    """El fallo que se vio en vivo: HABLAR_NPC sobre la entidad 714, que es
    una de las puertas del 76, y _viajar_por_portal desempaquetando un None.

        TypeError: Value after * must be an iterable, not NoneType

    Afectaba a TODOS los tornados anotados sin destino que no preguntan, y
    ninguno se habia clicado nunca. Quedan diez en el json."""
    class Falsa:
        personaje = None
    todos = json.loads((RAIZ / 'server' / 'plantillas' / 'portales.json')
                       .read_text(encoding='utf-8'))['mapas']
    n = 0
    for lista in todos.values():
        for p in lista or []:
            if p.get('destino') is None and not p.get('preguntar'):
                n += 1
                app._viajar_por_portal(Falsa(), 'test', p, '(clic)')
    assert n >= 1, n
    fuente = (RAIZ / 'server' / 'app.py').read_text(encoding='utf-8')
    assert "portal_match.get('destino') is None" in fuente, \
        'volvio a desaparecer el filtro del manejador del clic'
    assert 'if dst is None or not lleg:' in fuente, \
        'volvio a desaparecer la red de seguridad de _viajar_por_portal'


def test_ningun_spawn_se_sale_del_mapa():
    for st in CUARTOS:
        m = cli.mapa(st)
        for e in _plantilla(st)['spawns']:
            x, y = e['tile']
            assert 0 <= x < m.ancho and 0 <= y < m.alto, (st, e['nombre'],
                                                          e['tile'])


def test_los_entity_id_no_se_repiten_ni_chocan():
    """Se fabrican, asi que hay que comprobarlo: dentro de cada mapa unicos, y
    fuera del 300-899 que usan totems, portales dibujados y NPC de los xml."""
    for st in CUARTOS:
        ids = [e['entity_id'] for e in _plantilla(st)['spawns']]
        assert len(ids) == len(set(ids)), st
        assert min(ids) > 1000, (st, min(ids))


def test_ninguna_llegada_cae_en_un_tornado():
    """El 77 tiene 52 tornados en un mapa de 356x260: el riesgo de aterrizar
    dentro de otro y rebotar es real."""
    for st in (ENTRADA,) + CUARTOS:
        for p in _portales(st):
            if p['destino'] is None:
                continue
            assert app._portal_en(p['destino'], *p['llegada']) is None, \
                (st, p['tile'], '->', p['destino'], p['llegada'])


def test_las_cinco_puertas_del_cuarto_1_llevan_a_algun_sitio():
    """Los cinco tornados del 76 cuyo evento solo abre un dialogo (1004,
    1006, 1008, 1013 y 1014) NO son puertas muertas: el dialogo lleva el
    viaje detras. Dejarlos inertes fue el error que dejo medias instancias
    sin recorrer, y se vio en Limitless Tower."""
    conmenu = [p for p in _portales(76)
               if p.get('preguntar') or p.get('destinos')]
    muertos = [p for p in _portales(76)
               if p['destino'] is None and not p.get('preguntar')]
    assert len(conmenu) + len([p for p in _portales(76)
                               if p['destino'] is not None]) == len(_portales(76)),         [p['tile'] for p in muertos]
    assert not muertos, [p['tile'] for p in muertos]


def test_el_metodo_sigue_reproduciendo_lo_medido():
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
