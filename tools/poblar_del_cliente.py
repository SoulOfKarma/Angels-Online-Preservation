"""Puebla un mapa SIN CAPTURARLO: los generadores estan en el cliente.

Hasta hoy poblar un mapa costaba una sesion de juego: entrar con el cliente
oficial, recorrerlo entero con el proxy grabando y sacar los monstruos de los
0x0008 que fueran llegando. Eso tiene dos problemas que se pagaron caros:

  * una captura solo trae lo que estuvo A LA VISTA. Commercial Street dio 71
    monstruos en el primer recorrido, 109 en el segundo y 125 en el tercero;
  * y a las instancias no se puede entrar a voluntad, asi que Gulp Room y
    las otras treinta y dos entradas de instancia quedaban en null.

No hacia falta. El generador de monstruos es un objeto mas del .mpc:

    +21 u8  TAG de la zona donde aparecen, o 0 = en su propia casilla
    +34 u16 id de monster.xml
    +38 u16 tiempo de reaparicion
    +42 u16 cuantos aparecen

La evidencia esta en mapa_del_cliente.Mapa.generadores(). Resumida: en el
stage 73, que es el unico mapa de instancia con captura y por eso sirve de
conjunto de prueba, los 283 valores del +34 resuelven los 283 en monster.xml,
la suma de los +42 da 384 donde la captura vio 375, y el generador mas cercano
a cada monstruo capturado es de su clase el 93% de las veces contra un 14% al
barajar.

DONDE SE PLANTA CADA UNO. El cliente dice cuantos y en que zona, no en que
casilla va cada uno; eso lo decide el servidor al generarlos. Aqui:

  * si el generador apunta a un TAG, los monstruos se reparten por los
    puntos de ese TAG, que son casillas del propio mapa;
  * si no apunta a ninguno, van en la casilla del generador, y los de mas
    se abren en anillo alrededor.

El anillo llega hasta radio 3, que no es un numero elegido a ojo: es la
distancia Chebyshev MEDIANA que hay entre cada monstruo capturado del stage
73 y el generador de su clase. O sea que es la dispersion que tiene el juego
de verdad.

HASTA DONDE LLEGA ESTO. Contra las 234 plantillas que si salieron de
capturas, la razon entre lo que declara el cliente y lo que vio la captura
tiene mediana 1.00, y 197 de los 234 mapas caen entre 0,9 y 1,1. Los que se
salen tienen explicacion y conviene conocerla antes de fiarse de un mapa
nuevo a ciegas:

  * los mapas de buceo (84 a 96) declaran la MITAD de lo capturado. Ahi la
    captura cuenta de mas, porque el entity_id cambia al reaparecer y un
    recorrido largo apunta el mismo sitio dos veces;
  * los de Cybertronica (398 a 421) declaran el DOBLE, porque esas capturas
    son de una sola sesion y lo dicen en su propia nota;
  * Sandy Heights (405) declara 5140 contra 155 capturados, treinta y tres
    veces mas. No es un generador raro: son 1036 generadores de cantidad 5
    cada uno. Ese mapa hay que mirarlo antes de poblarlo desde aqui.

Lo que NO sale del cliente y por tanto no se inventa: el entity_id. Los de
las plantillas capturadas son los del servidor de Celestia, que ademas no
sobreviven a la conexion. Aqui se fabrican con una cuenta fija a partir del
stage para que sean estables entre ejecuciones y no choquen con los de los
portales (720-807), los totems (300+) ni los NPC de los xml (900+).

Uso:
    python tools/poblar_del_cliente.py --stage 76 --nombre gulp_room
    python tools/poblar_del_cliente.py --validar
"""
import argparse
import collections
import json
import pathlib
import sqlite3
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
sys.path.insert(0, str(RAIZ / 'server'))
import mapa_del_cliente as cli

PLANTILLAS = RAIZ / 'server' / 'plantillas'
BASE_ENTIDAD = 50_000_000      # muy lejos de todo lo que ya se usa
BASE_OBJETO = 60_000_000       # y los objetos de mapa en su propia banda
RADIO_ANILLO = 3               # medido: ver el docstring
# SEPARACION MINIMA entre dos monstruos del mapa.
#
# No es un numero a ojo: sale de medir los mapas CAPTURADOS, que son como se
# ve el juego de verdad. En ellos cada monstruo tiene a su vecino mas cercano
# a 5 casillas de mediana, y en una celda de 10x10 hay 4 bichos de mediana,
# 6 en el percentil 90 y 10 en el peor caso de todos.
#
# Con separacion 2 salian 25 por celda -- la saturacion -- y eso en pantalla
# es un muro: en Dinosaur Arena no se veia el suelo. Con 5 salen 4 por celda,
# que es exactamente lo que miden los mapas capturados.
SEPARACION = 5
# TOPE DE LO QUE UN GENERADOR PONE A LA VEZ. El cliente declara cuantos le
# tocan, y para los mapas normales el dato es bueno: contra las 234 plantillas
# capturadas el total sale EXACTO en 164. Pero en esos 234 mapas ningun
# generador pasa de 40, y en las instancias hay doce que declaran entre 40 y
# 200 TODOS SOBRE UN SOLO PUNTO -- 200 Hell Beast Guardian en la casilla
# (209,124) de Hell Mahal Altar. Eso no es una plantacion de doscientos
# bichos en una casilla: es un generador de oleadas, que los va soltando. No
# sabemos a que ritmo, asi que se pone de golpe lo mas alto que se ha visto
# nunca en un mapa comprobado, que es 40, y se anota el numero real.
TOPE_POR_GENERADOR = 40
_OBJETOS = None


def _cuerpo_de(r):
    """Los 43 bytes del 0x000E de un recurso capturado.

    Lo normal es que la captura traiga el cuerpo entero en 'crudo'. Solo
    2499 de los 15232 recursos capturados lo tienen; el resto se guardo por
    campos. Rearmarlo por campos NO es equivalente en general -- lo avisa
    login.objeto_de_mapa() y se vio en pantalla con las estatuas de Seaside
    Grotto -- pero aqui no se esta rearmando otra cosa: se copian los campos
    opacos ('medio', 'marca', 'orient', 'cola') de una captura del MISMO
    objeto, que son justamente los bytes que no sabemos leer.
    """
    import struct
    if r.get('crudo'):
        c = bytes.fromhex(r['crudo'])[:43]
        if len(c) == 43:
            return c
    if not r.get('sprite') or r.get('orient') is None:
        return None
    b = bytearray(43)
    medio = bytes.fromhex(r.get('medio') or '')[:16]
    b[16:16 + len(medio)] = medio
    b[32] = int(r.get('marca', 0)) & 0xFF
    b[33] = int(r.get('orient', 6)) & 0xFF
    struct.pack_into('<H', b, 34, int(r['sprite']))
    cola = bytes.fromhex(r.get('cola') or '')[:7]
    b[36:36 + len(cola)] = cola
    return bytes(b)


def objetos_que_se_mandan():
    """id de objeto -> un cuerpo de 0x000E bueno, de los que ya se capturaron.

    EL SERVIDOR NO MANDA EL MAPA ENTERO. Lava Cave tiene 2069 objetos en su
    .mpc y Celestia solo manda 75: el decorado lo dibuja el cliente por su
    cuenta y por el cable van unicamente los objetos "vivos" -- tornados,
    vetas, cofres, totems.

    Y la regla es POR ID DE OBJETO, no por objeto. En Lava Cave, de las 19
    clases que manda, manda TODOS los que hay en el mapa en las 19; en
    Underground Square, en las 14 de 14. Contados sobre las 239 plantillas
    capturadas: 339 ids se mandan siempre, 8067 no se mandan nunca y solo 28
    dependen del mapa. De esos 28 se cogen los que se mandan la mayoria de
    las veces.

    La comprobacion: aplicando la regla a esas mismas 239 plantillas, en 180
    sale EXACTAMENTE el mismo numero de objetos que mando el servidor y en
    213 se queda dentro del 20%. Los que mas se desvian son los de
    Cybertronica, cuyas capturas son de una sola sesion y lo dicen en su nota.

    EL CUERPO SE COPIA, NO SE REARMA. objeto_de_mapa() ya avisa de que
    rearmar un 0x000E por campos no sale byte a byte igual que el original:
    el cuerpo lleva algo que no sabemos leer. Asi que se coge uno capturado
    del MISMO id de objeto y se le cambian el id de entidad, la posicion y la
    capa, que es el mismo truco que ya se usa para dibujar los tornados.
    Comprobado que se puede: quitando id y posicion, los cuerpos de un mismo
    objeto solo se diferencian en el byte 32.
    """
    global _OBJETOS
    if _OBJETOS is not None:
        return _OBJETOS
    import login
    mandado, nomandado, cuerpo = collections.Counter(), collections.Counter(), {}
    for stage, fichero in sorted(login.PLANTILLAS_POR_STAGE.items()):
        f = PLANTILLAS / fichero
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding='utf-8'))
        if 'POBLADO DESDE EL CLIENTE' in d.get('_nota', '') or not d.get('recursos'):
            continue
        m = cli.mapa(stage)
        if m is None:
            continue
        enviados = set()
        for r in d['recursos']:
            s = r.get('sprite')
            if s is None:
                continue
            enviados.add(s)
            if s not in cuerpo:
                c = _cuerpo_de(r)
                if c:
                    cuerpo[s] = c
        for i in {o['id'] for o in m.objetos}:
            (mandado if i in enviados else nomandado)[i] += 1
    _OBJETOS = {i: cuerpo[i] for i in set(mandado) | set(nomandado)
                if mandado[i] and mandado[i] >= nomandado[i] and i in cuerpo}
    return _OBJETOS


def recursos_de(stage):
    """Los objetos de mapa del stage, con el cuerpo copiado de una captura."""
    import struct
    m = cli.mapa(stage)
    cuerpos = objetos_que_se_mandan()
    salida, sin_cuerpo = [], collections.Counter()
    for o in m.objetos:
        # LOS TORNADOS NO, que esos los dibuja portales_de() desde
        # portales.json. Si salieran tambien por aqui, cada uno se mandaria
        # DOS VECES -- en el stage 77 son 52 -- con dos ids de entidad
        # distintos, y el clic solo funcionaria en uno de los dos.
        if o['id'] == cli.TORNADO:
            continue
        if o['id'] not in cuerpos:
            # Los que no estan en la lista es porque el servidor NO los
            # manda: son decorado que el cliente dibuja solo. No se cuentan
            # como falta. Solo se avisa de los que llevan evento, porque esos
            # si hacen algo y quedarse sin dibujar se nota.
            if o['evento']:
                sin_cuerpo[o['id']] += 1
            continue
        b = bytearray(cuerpos[o['id']])
        eid = BASE_OBJETO + stage * 100_000 + len(salida)
        # LA POSICION HAY QUE PASARLA AL SENTIDO DEL SERVIDOR. En el .mpc la
        # y se cuenta desde abajo. La x en pixeles vale tal cual -- casa
        # exacta en los 75 objetos de Lava Cave -- y la y se recompone desde
        # la casilla, centrada, que es lo mismo que hace portales_de() al
        # dibujar un tornado. El desplazamiento DENTRO de la casilla no se
        # puede deducir y no importa: es menos de una casilla.
        px = (o['px'][0], o['tile'][1] * 32 + 16)
        struct.pack_into('<I', b, 0, eid)
        struct.pack_into('<I', b, 4, o['capa'])
        struct.pack_into('<II', b, 8, px[0], px[1])
        # Objeto con evento: marca 40 80 justo detras del sprite (+38) y el
        # cursor del evento en +40, como las antorchas capturadas
        # (dc 06 | sprite | 40 80 | 14 | 00 00). Sin eso el cliente toma el
        # objeto por decorado y no deja pulsarlo (ver Mapa.cursores).
        if o.get('evento') and len(b) >= 43 and b[38:41] == b'\0\0\0':
            _cu = getattr(m, 'cursores', {}).get(o['evento'])
            if _cu is not None:
                b[38], b[39], b[40] = 0x40, 0x80, _cu
        salida.append({'entity_id': eid, 'sprite': o['id'],
                       'capa': o['capa'], 'px': [px[0], px[1]],
                       'tile': list(o['tile']),
                       'crudo': bytes(b).hex(),
                       'copiado_de': 'cuerpo de una captura del objeto %d' % o['id']})
    return salida, sin_cuerpo


def _catalogo():
    """id -> (nombre, nivel, sprite, es_monstruo) de monster.xml y npc.xml."""
    con = sqlite3.connect(RAIZ / 'corpus' / 'content.db')
    cat = {}
    for tabla, mob in (('npc', False), ('monster', True)):
        for i, s, n, l in con.execute(
                'select id, sprite_id, name, level from %s' % tabla):
            try:
                cat[int(i)] = (n, int(l or 0), int(s or 0), mob)
            except (TypeError, ValueError):
                continue
    con.close()
    return cat


def _repartir(puntos, cuantos, ancho, alto, ocupadas=None):
    """Reparte `cuantos` monstruos por la zona del generador, sin amontonarlos.

    EL FALLO QUE ARREGLA. Antes, cuando un generador pedia mas monstruos que
    puntos tiene su TAG -- y es lo normal: 25 bichos y tres puntos -- se
    ponian los tres primeros en los puntos y los veintidos restantes en
    anillo alrededor del PRIMERO. Resultado: un amasijo de veintitantos
    bichos apilados en una esquina, que es justo lo que se vio en
    Leviathan's Bedroom. En el juego de verdad estan repartidos por su zona.

    Ahora se reparten por TODOS los puntos del TAG por turnos, y a cada uno
    se le da una casilla distinta dentro de un anillo alrededor de su punto.
    El anillo llega hasta radio 3, que es la distancia Chebyshev MEDIANA
    medida entre cada monstruo capturado del stage 73 y el generador de su
    clase, o sea la dispersion que tiene el juego.
    """
    usadas = ocupadas if ocupadas is not None else set()
    salida = []
    for k in range(cuantos):
        base = puntos[k % len(puntos)]
        elegida = _libre_cerca(base, usadas, ancho, alto)
        usadas.add(elegida)
        salida.append(elegida)
    return salida


# SUELO. Si el servidor tiene el suelo transitable del mapa (transitable.bin),
# solo valen casillas que se pisan y cuyas ocho vecinas tambien: el anillo no
# miraba el suelo y en Gulp Room 4, Leviathan's Bedroom, Botti Palace o Poker
# Castle la mitad de los monstruos caian fuera de la plataforma o en su borde.
_PISABLE = None


def _suelo_de(stage):
    # El de server/, no el tools/transitable.py que lo construye: se llaman
    # igual y desde aqui el import normal cogeria el de tools.
    try:
        import importlib.util as _iu
        _sp = _iu.spec_from_file_location('transitable_servidor',
                                          RAIZ / 'server' / 'transitable.py')
        _tr = _iu.module_from_spec(_sp)
        _sp.loader.exec_module(_tr)
    except Exception:
        return None
    if not _tr.conocido(stage):
        return None
    return lambda t: all(_tr.se_pisa(stage, t[0] + dx, t[1] + dy)
                         for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def _libre_cerca(centro, usadas, ancho, alto):
    """La casilla libre mas cercana al centro, en cuadrados concentricos.

    El radio NO se corta en 3: se abre lo que haga falta hasta encontrar
    sitio. Cortarlo fue el fallo -- al agotarse el anillo se devolvia el
    centro una y otra vez y los bichos acababan apilados de doce en doce en
    la misma casilla.
    """
    for r in range(0, max(ancho, alto)):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if r and max(abs(dx), abs(dy)) != r:
                    continue
                t = (centro[0] + dx, centro[1] + dy)
                if not (0 <= t[0] < ancho and 0 <= t[1] < alto):
                    continue
                if t in usadas:
                    continue
                if _PISABLE is not None and not _PISABLE(t):
                    continue
                if any((t[0] + ex, t[1] + ey) in usadas
                       for ex in range(-SEPARACION + 1, SEPARACION)
                       for ey in range(-SEPARACION + 1, SEPARACION)):
                    continue
                return t
    return centro


def _anillo(centro, cuantos, ancho, alto):
    """`cuantos` casillas distintas alrededor del centro, el centro primero.

    En cuadrados concentricos hasta RADIO_ANILLO. Si aun faltan, se repite la
    casilla del centro: antes dejar dos monstruos juntos que plantarlos lejos
    de donde el cliente dice que van.
    """
    salida, vistas = [], set()
    for r in range(0, RADIO_ANILLO + 1):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if r and max(abs(dx), abs(dy)) != r:
                    continue
                t = (centro[0] + dx, centro[1] + dy)
                if t in vistas or not (0 <= t[0] < ancho and 0 <= t[1] < alto):
                    continue
                vistas.add(t)
                salida.append(t)
                if len(salida) == cuantos:
                    return salida
    while len(salida) < cuantos:
        salida.append(centro)
    return salida


def zonas_de_evento(stage):
    """Las zonas de generador que el mapa solo saca POR EVENTO.

    Son las que nombra un GENERATE (31) o un ENABLE_GENERATOR (33) de sus
    disparadores o de sus dialogos: oleadas y jefes de instancia. No van de
    inicio. En la Magic Kichen Path eran el Guard Fasit y los Mud Lord de la
    sala 1, las oleadas de Rock Slarm y el Rock God Mendun de la 2, y el
    Beelzebub de la 3; poblados de inicio, la instancia salia ya resuelta.
    """
    import json as _js
    zonas = set()
    f = RAIZ / 'server' / 'plantillas' / 'eventos.json'
    if f.exists():
        d = _js.loads(f.read_text(encoding='utf-8'))['stages'].get(str(stage), {})
        for x in d.get('disparadores', []):
            for n, parms in x['haz']:
                if n in (31, 33) and parms:
                    zonas.add(int(parms[0]))
    f = RAIZ / 'server' / 'plantillas' / 'dialogos_mapa.json'
    if f.exists():
        arbol = _js.loads(f.read_text(encoding='utf-8')).get(str(stage), {})
        for n in arbol.values():
            for num, parms in n.get('a', ()):
                if num in (31, 33) and parms:
                    zonas.add(int(parms[0]))
    return zonas


# Los cuatro elfos elementales (Wind, Fire, Water y Earth Elf, nivel 4-7)
# los usan los .mpc como MARCADORES de posicion: generadores de uno en su
# propia zona, en filas ordenadas, en instancias de nivel 300-465. En el
# cliente oficial no aparecen; poblandolos salian Fire Elf nivel 7 a la
# entrada de Rotwood Abyss (nivel 465), visto por el usuario el 26/10/2026.
MARCADORES = {1, 2, 3, 4}


def _nivel_tipico(m, cat):
    import statistics
    nv = [cat[g['tipo']][1] or 0 for g in m.generadores()
          if g['tipo'] in cat and cat[g['tipo']][3] and g['tipo'] not in MARCADORES]
    return statistics.median(nv) if nv else 0


def es_marcador(tipo, nivel_mapa):
    """Un elfo elemental en un mapa de nivel alto es un marcador, no un bicho."""
    return tipo in MARCADORES and nivel_mapa > 50


def spawns_de(stage, con_zonas_de_evento=False):
    """La lista de spawns del mapa, en el formato de las plantillas.

    Sin las zonas que solo salen por evento (zonas_de_evento), salvo que se
    pidan.
    """
    m = cli.mapa(stage)
    if m is None:
        return None, None
    global _PISABLE
    _PISABLE = _suelo_de(stage)
    fuera = set() if con_zonas_de_evento else zonas_de_evento(stage)
    cat = _catalogo()
    salida, sin_catalogo = [], collections.Counter()
    # LAS CASILLAS OCUPADAS SON DE TODO EL MAPA, no de cada generador. Al
    # llevarlas por generador, dos generadores distintos elegian la misma
    # casilla y se veian los bichos uno encima de otro: en Gulp Room 4
    # llegaron a caer 53 en una sola casilla.
    ocupadas = set()
    nivel_mapa = _nivel_tipico(m, cat)
    for k, g in enumerate(m.generadores()):
        if g['zona'] and g['zona'] in fuera:
            continue
        # Los de cantidad 0 no: esos los invoca un evento (Gulp Room 3).
        if g['cantidad'] and es_marcador(g['tipo'], nivel_mapa):
            continue
        info = cat.get(g['tipo'])
        if not info:
            # El +34 no resuelve en ninguna de las dos tablas. No se inventa
            # nada: se cuenta y se deja fuera.
            sin_catalogo[g['tipo']] += 1
            continue
        nombre, nivel, sprite, mob = info
        cuantos = max(1, min(TOPE_POR_GENERADOR, g['cantidad']))
        puntos = g['puntos'] or [g['tile']]
        casillas = _repartir(puntos, cuantos, m.ancho, m.alto, ocupadas)
        for t in casillas:
            e = {'entity_id': BASE_ENTIDAD + stage * 100_000 + len(salida),
                 'nombre': nombre, 'npc_type': g['tipo'], 'sprite': sprite,
                 'klass': 1 if mob else 200, 'monstruo': mob,
                 'tile': [t[0], t[1]], 'direccion': 2, 'visible': 0}
            if mob:
                e['nivel'] = nivel
            if g['cantidad'] > TOPE_POR_GENERADOR:
                e['declarados'] = g['cantidad']
            if g['cantidad'] == 0:
                # El cliente declara el generador con cantidad 0. Son los
                # tres Elf de Gulp Room 3, que los invoca otra cosa. Se
                # anotan apagados para no perderlos.
                e['apagado'] = True
            salida.append(e)
    return salida, sin_catalogo


NOTA = (
    '%s (stage %d). POBLADO DESDE EL CLIENTE, no desde una captura: los '
    'generadores de monstruos son objetos del propio map%03d.mpc -- el '
    'monstruo en el u16 del +34, la zona en el +21, el tiempo en el +38 y '
    'cuantos en el +42. Eso da el censo COMPLETO del mapa, que una captura '
    'no puede dar porque solo trae lo que estuvo a la vista. El entity_id es '
    'fabricado y estable, no el del servidor. Las casillas son las del TAG de '
    'cada generador; los que no declaran TAG ponen sus monstruos en la '
    'casilla del generador y en un anillo de radio 3 a su alrededor, que es '
    'la dispersion MEDIDA en el stage 73. Los objetos de mapa son los del '
    '.mpc cuyo id esta en la lista de los que el servidor manda de verdad, '
    'con el cuerpo del 0x000E copiado de una captura del mismo objeto. Los '
    'tornados se dibujan aparte, desde portales.json. '
    'Ver tools/poblar_del_cliente.py.')


def escribir(stage, nombre):
    sp, sin_cat = spawns_de(stage)
    if sp is None:
        print('el cliente no trae el mapa %d' % stage)
        return False
    rec, sin_cuerpo = recursos_de(stage)
    dest = PLANTILLAS / (nombre + '.json')
    dest.write_text(json.dumps({
        '_nota': NOTA % (nombre, stage, stage),
        'stage': stage,
        'spawns': sp,
        'recursos': rec,
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    mobs = sum(1 for e in sp if e['monstruo'])
    print('%s.json: %d spawns (%d monstruos, %d NPC) y %d objetos de mapa'
          % (nombre, len(sp), mobs, len(sp) - mobs, len(rec)))
    if sin_cuerpo:
        print('   objetos que el cliente pone y no tenemos cuerpo para armar: '
              '%d en %d clases' % (sum(sin_cuerpo.values()), len(sin_cuerpo)))
    for (n, lv), c in collections.Counter(
            (e['nombre'], e.get('nivel')) for e in sp).most_common():
        print('   %-28s nv %-5s x%d' % (n, lv, c))
    if sin_cat:
        print('   tipos que no estan en content.db: %s' % dict(sin_cat))
    return True


def validar():
    """El censo del cliente contra las plantillas que salieron de capturas.

    Las 234 plantillas con las que se compara se poblaron con el proxy
    delante, recorriendo cada mapa con el cliente oficial, y llevan el
    entity_id del servidor de Celestia. No son derivadas de esto, asi que la
    comparacion no se muerde la cola.
    """
    import login
    filas = []
    for stage, fichero in sorted(login.PLANTILLAS_POR_STAGE.items()):
        f = PLANTILLAS / fichero
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding='utf-8'))
        if 'POBLADO DESDE EL CLIENTE' in d.get('_nota', ''):
            continue        # esa salio de aqui: no vale como contraste
        cap = [e for e in d['spawns'] if e.get('monstruo')]
        if len(cap) < 20:
            continue
        m = cli.mapa(stage)
        if m is None:
            continue
        gen = [g for g in m.generadores()]
        if not gen:
            continue
        cat = _catalogo()
        cli_n = sum(g['cantidad'] for g in gen
                    if cat.get(g['tipo'], (0, 0, 0, False))[3])
        clases_cap = {e['nombre'] for e in cap}
        clases_cli = {cat[g['tipo']][0] for g in gen if g['tipo'] in cat}
        filas.append((stage, len(cap), cli_n,
                      len(clases_cap & clases_cli), len(clases_cap)))
    tc = sum(r[1] for r in filas)
    tx = sum(r[2] for r in filas)
    com = sum(r[3] for r in filas)
    tcl = sum(r[4] for r in filas)
    igual = sum(1 for r in filas if r[1] == r[2])
    print('mapas capturados con los que se compara : %d' % len(filas))
    print('monstruos: capturados %d, el cliente declara %d (%.0f%%)'
          % (tc, tx, 100.0 * tx / tc))
    print('mapas donde el total sale EXACTAMENTE igual : %d de %d'
          % (igual, len(filas)))
    print('clases capturadas que el cliente declara    : %d de %d (%.0f%%)'
          % (com, tcl, 100.0 * com / tcl))
    return igual >= 50 and 100.0 * com / tcl >= 75


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', type=int)
    ap.add_argument('--nombre')
    ap.add_argument('--censo', type=int, nargs='+',
                    help='solo contar, sin escribir nada')
    ap.add_argument('--validar', action='store_true')
    a = ap.parse_args()
    if a.validar:
        raise SystemExit(0 if validar() else 1)
    for st in (a.censo or []):
        m = cli.mapa(st)
        if m is None:
            print('stage %d: el cliente no lo trae' % st)
            continue
        cat = _catalogo()
        c = collections.Counter()
        for g in m.generadores():
            c[cat.get(g['tipo'], ('?? %d' % g['tipo'],))[0]] += g['cantidad']
        print('== stage %d: %d monstruos/NPC en %d clases'
              % (st, sum(c.values()), len(c)))
        for n, k in c.most_common():
            print('   %-28s x%d' % (n, k))
    if a.stage and a.nombre:
        raise SystemExit(0 if escribir(a.stage, a.nombre) else 1)


if __name__ == '__main__':
    main()
