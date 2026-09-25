"""Arma la plantilla de un mapa a partir de capturas del proxy.

Hasta ahora cada mapa se sacaba a mano, con un script de usar y tirar. Son
siempre los mismos tres pasos, asi que aqui quedan hechos una vez:

  1. juntar los 0x0008 (NPC y monstruos) y los 0x000E (objetos de mapa) de
     todas las sesiones que se le pasen, sin repetir entity_id
  2. separar NPC de monstruos: en el 0x0008 el offset 40 trae 199/200 para los
     NPC y el NIVEL del bicho para los monstruos
  3. ponerle nombre a los recursos de productor cruzando el sprite con el
     圖號 de material.xml

Se guardan los DATOS, no los bytes: el 0x0008 de Celestia mide 62/64 y el
nuestro 63, asi que reenviar sus bytes rompe el cliente.

    python tools/poblar_mapa.py --stage 13 --nombre jade_vale \
        --sesiones logs/proxy/mundo_115002_343786_orden.jsonl ...
"""
import argparse
import collections
import glob
import json
import pathlib
import re
import sqlite3
import struct
import sys

RAIZ = pathlib.Path(__file__).parent.parent
PAKS = pathlib.Path('G:/extracted_paks')
ORDEN = (['data1', 'update', 'update2', 'update3']
         + ['UPDATE%d' % i for i in range(4, 22)]
         + ['update%d' % i for i in range(22, 27)])

# Sprites del espacio 6xxxx que NO son recursos de productor. Estan medidos en
# el juego y por eso pisan cualquier cosa que diga material.xml.
SPRITE_FIJO = {60001: 'tornado (portal)', 60051: 'Aurora Totem',
               60052: 'Dark City Totem', 60053: 'Iron Totem',
               60054: 'Breeze Totem', 60241: 'totem (NPC)'}


def materiales():
    """sprite -> nombre del recurso, desde el 圖號 de material.xml.

    Un sprite puede aparecer en varias filas porque cada parche vuelve a
    declarar el mismo recurso con id nuevo. Si todas coinciden en el nombre se
    da por bueno; si no, se deja marcado como ambiguo en vez de elegir al azar.
    """
    filas = {}
    for pak in ORDEN:
        for sub in ('setting/eng', 'setting'):
            p = PAKS / pak / sub / 'material.xml'
            if not p.exists():
                continue
            txt = p.read_text(encoding='utf-8', errors='replace')
            for m in re.finditer(r'<\S+\s([^>]*?)/>', txt):
                a = dict(re.findall(r'([^\s=]+)="([^"]*)"', m.group(1)))
                if a.get('\u7de8\u865f', '').isdigit():
                    filas[int(a['\u7de8\u865f'])] = a
            break
    porspr = collections.defaultdict(set)
    for a in filas.values():
        spr = a.get('\u5716\u865f')
        if spr and spr.isdigit():
            porspr[int(spr)].add(a.get('\u540d\u7a31', ''))
    salida = {}
    for spr, noms in porspr.items():
        salida[spr] = sorted(noms)[0] if len(noms) == 1 else sorted(noms)
    return salida


def leer(sesiones):
    spawns, recursos, carteles = {}, {}, {}
    for f in sesiones:
        for l in open(f, encoding='utf-8'):
            x = json.loads(l)
            if x.get('dir') != 's2c' or 'hex' not in x:
                continue
            b = bytes.fromhex(x['hex'])
            if x['opcode'] == 0x0008 and len(b) >= 47:
                spawns.setdefault(struct.unpack_from('<I', b, 0)[0], b)
            elif x['opcode'] == 0x000E and len(b) >= 36:
                recursos.setdefault(struct.unpack_from('<I', b, 0)[0], b)
            elif x['opcode'] == 0x000F and len(b) >= 40:
                # El cartel con el nombre. Es el mismo mensaje que el 0x000E
                # pero con el nombre en ascii en los offsets 16..31; sin el,
                # el recurso se dibuja pero no tiene nombre al pasar el raton.
                carteles.setdefault(struct.unpack_from('<I', b, 0)[0], b)
    return spawns, recursos, carteles


def nombre_del_spawn(crudo):
    """Nombre de los 16 bytes del 0x0008, venga de donde venga.

    Celestia manda los nombres en ingles ASCII, asi que hasta ahora bastaba
    con decodificar ascii. El cliente oficial de Taiwan los manda en BIG5 y
    ascii los destroza: 'Hardworking Pig' salia como una fila de rombos.
    Big5 es compatible con ascii por debajo de 0x80, asi que decodificarlo
    siempre da lo mismo para los nombres ingleses y ademas arregla los chinos.
    """
    return crudo.split(b'\x00')[0].decode('big5', 'replace')


def spawn_a_datos(e, b):
    nom = nombre_del_spawn(b[16:32])
    visible = struct.unpack_from('<I', b, 4)[0]
    tile = list(struct.unpack_from('<II', b, 8))
    sprite = struct.unpack_from('<I', b, 34)[0]
    klass = struct.unpack_from('<I', b, 40)[0]
    npc_type = struct.unpack_from('<H', b, 45)[0]
    # El offset 40 trae 199/200 en los NPC y el NIVEL en los monstruos. Es el
    # unico campo que los separa; el nombre no sirve porque hay NPC hostiles.
    # El CERO tambien es NPC: un monstruo de nivel 0 no existe. Son los bichos
    # decorativos de las ciudades -- el Catkin y el White Horse de Aurora City
    # e Iron Castle --, que viven en npc.xml y no en monster.xml. Tratandolos
    # como monstruos se les daba IA de combate y se les buscaban estadisticas
    # que no tienen.
    es_mob = klass not in (0, 199, 200)
    # PERO EL KLASS MIENTE. Hay monstruos que llegan con klass 199, o sea
    # marcados como NPC: los Bloody Croc y Moody Croc de Lost Trail, los
    # Stealth Searcher de Forbidden Sector, los Draconan de Ninja Land... 88
    # spawns en ocho mapas. Se colaban como NPC y se quedaban sin IA.
    # Quien manda es el cliente: npc.xml va del 1500 al 24893 y monster.xml
    # del 1 al 23860, y NO comparten ni un solo id. Asi que de 1500 para
    # arriba se sabe con certeza cual es cual.
    # Por debajo de 1500 no se toca: npc.xml no llega ahi, y los NPC del
    # Lyceum usan numeros de dos y tres cifras que chocan con monster.xml.
    if npc_type >= 1500:
        _m, _n = _clases_del_cliente()
        if npc_type in _n:
            es_mob = False
        elif npc_type in _m:
            es_mob = True
    return {'entity_id': e, 'nombre': nom, 'npc_type': npc_type,
            'sprite': sprite, 'klass': 1 if es_mob else klass,
            'monstruo': es_mob, 'tile': tile,
            'direccion': b[33], 'visible': visible,
            **({'nivel': klass} if es_mob else {})}


_CLASES = None


def _clases_del_cliente():
    """(monstruos, npcs) por npc_type, sacados de monster.xml y npc.xml."""
    global _CLASES
    if _CLASES is None:
        mons, npcs = set(), set()
        for f in sorted(glob.glob(str(PAKS / '*/setting/eng/monster.xml'))):
            for m in re.finditer(r'<npc([^>]*?)/>',
                                 open(f, encoding='utf-8', errors='replace').read()):
                a = dict(re.findall(r'(\S+?)="([^"]*)"', m.group(1)))
                if a.get('編號') and a.get('陣營') == '怪物陣營':
                    mons.add(int(a['編號']))
        for f in sorted(glob.glob(str(PAKS / '*/setting/eng/npc.xml'))):
            for m in re.finditer(r'<npc([^>]*?)/>',
                                 open(f, encoding='utf-8', errors='replace').read()):
                a = dict(re.findall(r'(\S+?)="([^"]*)"', m.group(1)))
                if a.get('編號'):
                    npcs.add(int(a['編號']))
        _CLASES = (mons, npcs)
    return _CLASES


def recurso_a_datos(e, b, mats, cartel=None):
    px = list(struct.unpack_from('<II', b, 8))
    sprite = struct.unpack_from('<H', b, 34)[0]
    # CRUDO: el cuerpo entero tal cual llego. Los campos sueltos se siguen
    # guardando porque son legibles y se usan para buscar, pero lo que el
    # servidor reenvia es esto. Rearmar por campos parecia equivalente y no
    # lo es: el cuerpo tiene bytes que no sabemos interpretar y que al
    # reconstruir se perdian, y ademas alguno cambia con el tiempo, asi que
    # dos capturas del mismo objeto no dan lo mismo. Con el crudo, lo que ve
    # el jugador es exactamente lo que mandaba el servidor original.
    d = {'entity_id': e, 'capa': struct.unpack_from('<I', b, 4)[0],
         'px': px, 'medio': b[16:32].hex(), 'marca': b[32],
         'orient': b[33], 'sprite': sprite, 'cola': b[36:43].hex(),
         'crudo': b[:43].hex()}
    if cartel is not None:
        nombre = cartel[16:32].split(bytes(1))[0].decode('ascii', 'replace')
        if nombre.strip():
            d['nombre_visible'] = nombre
            d['estado'] = struct.unpack_from('<I', cartel, 4)[0]
            d['marca_nombre'] = cartel[32]
            d['cola_nombre'] = cartel[36:].hex()
    if sprite in SPRITE_FIJO:
        d['que_es'] = SPRITE_FIJO[sprite]
    else:
        n = mats.get(sprite)
        if isinstance(n, str):
            d['material'] = n
        elif n:
            d['material_posibles'] = n
    return d


TOLERANCIA = 0   # casillas; MEDIDO, ver quitar_repetidos_de_otra_sesion()


def quitar_repetidos_de_otra_sesion(spawns):
    """Junta el mismo bicho visto en dos sesiones distintas.

    EL ENTITY_ID NO SOBREVIVE A LA SESION. Medido en Floating Station: entre
    dos sesiones del mismo mapa hay CERO ids en comun, y entre otras dos solo
    11 de 176. O sea que el servidor renumera las entidades en cada conexion,
    y como cada cruce de portal abre conexion nueva, juntar tramos de varias
    sesiones deduplicando por entidad no deduplica nada: 176 + 64 + 146
    entidades quedaban en 366, casi todas el mismo bicho contado tres veces.

    Se notaba en el juego antes que en los datos: el usuario vio los enemigos
    "hacinados" y amontonados. Medido despues, Floating Station tenia 165
    pares del mismo tipo a dos casillas o menos, cuando un mapa de Celestia
    de tamano parecido tiene una o dos casillas compartidas en total.

    Aqui se deduplica por TIPO Y CERCANIA en vez de por id: dos avistamientos
    del mismo npc_type a TOLERANCIA casillas o menos se consideran el mismo
    bicho, que se movio entre una sesion y otra. Se queda el primero.

    LA TOLERANCIA VA EN 0, O SEA SOLO LA MISMA CASILLA EXACTA, y eso esta
    medido. Se probo con 3 y borraba POBLACION REAL: aplicada a mapas de
    Celestia, que salen de UNA sola sesion y por tanto no pueden tener
    duplicados, se cargaba el 23% de niro_river, el 18% de karang_desert y el
    16% de pharaoh_village. Los monstruos del mismo tipo se paran juntos de
    forma legitima, asi que la cercania NO distingue un duplicado de un
    vecino. El usuario lo noto antes que la medicion: dijo que faltaban
    bichos en Majestic Mansion, Warm Villa y Floral Alley.

    Con 0 esto ya casi no hace nada, y esta bien que asi sea: la conclusion
    de verdad es que JUNTAR SESIONES DEL MISMO MAPA NO ES FIABLE. Un bicho
    visto en dos sesiones tiene ids distintos y ademas se ha movido, asi que
    no hay forma de reconocerlo. Lo correcto es recorrer el mapa entero en
    UNA sola sesion y poblar con esa; si hace falta mas cobertura, conviene
    un recorrido mas largo, no dos recorridos sumados.
    """
    buenos, fuera = [], []
    porTipo = collections.defaultdict(list)
    for e in spawns:
        t = e['npc_type']
        x, y = e['tile']
        gemelo = next((o for o in porTipo[t]
                       if max(abs(o['tile'][0] - x), abs(o['tile'][1] - y)) <= TOLERANCIA),
                      None)
        if gemelo is None:
            porTipo[t].append(e)
            buenos.append(e)
        else:
            fuera.append(dict(e, _motivo='mismo npc_type que la entidad %s, a %d '
                                         'casillas: es el mismo bicho visto en otra '
                                         'sesion, donde llevaba otro entity_id'
                                         % (gemelo['entity_id'],
                                            max(abs(gemelo['tile'][0] - x),
                                                abs(gemelo['tile'][1] - y)))))
    return buenos, fuera


def filtrar_irrepresentables(spawns):
    """Saca los spawns que nuestro cliente no puede dibujar.

    El cliente de Taiwan es de una rama posterior y manda alguna entidad que
    el nuestro no sabe representar. Mandarsela igual lo CRASHEA al entrar al
    mapa, y el fallo no dice nada: la ventana se cierra y ya.

    Lo que los delata es el sprite. En los 1.016 spawns de los siete mapas
    sacados de Taiwan los graficos caen en tres grupos -- 40xxx los NPC, 60xxx
    los totems y 110xxx los monstruos -- y aparecio UNO con sprite 999, que no
    es un id de grafico de nada. Traia ademas un entity_id de 3.404 millones,
    muy por encima de los 439 millones del resto de su mapa, y su npc_type
    (6269) es en nuestros datos una ficha vacia: tiene nombre y sprite pero no
    tiene ni HP ni ataque, o sea que en nuestra version ese bicho no existe de
    verdad. El nombre que manda Taiwan tampoco coincide con el nuestro para
    ese id, asi que en su version el id significa otra cosa.

    No se borran en silencio: se devuelven aparte y se guardan en la plantilla
    bajo _descartados, para que quede constancia de que existen y por que no
    se sirven.
    """
    buenos, fuera = [], []
    for e in spawns:
        if e.get('sprite', 0) < 10000:
            fuera.append(dict(e, _motivo='sprite %s: no es un id de grafico; '
                                         'el cliente no puede dibujarlo'
                                         % e.get('sprite')))
        else:
            buenos.append(e)
    return buenos, fuera


def traducir_nombres(spawns):
    """Pasa los nombres chinos a los ingleses que ya tenemos, por npc_type.

    El cliente de Taiwan manda los nombres en chino; el de Celestia, en
    ingles. Las plantillas del proyecto estan todas en ingles, asi que un
    mapa capturado en Taiwan quedaria con los bichos en chino y no se podria
    comparar con el resto ni buscar por nombre.

    No hay que traducir nada a mano: el npc_type es el mismo en las dos
    versiones y nuestro content.db, sacado de los XML del cliente, ya trae el
    nombre ingles de cada id. Se cruza por ahi. El chino original se guarda en
    nombre_original por si hiciera falta.
    """
    db = RAIZ / 'corpus' / 'content.db'
    if not db.exists():
        return 0
    con = sqlite3.connect(db)
    cambiados = 0
    for e in spawns:
        if e['nombre'].isascii():
            continue                       # ya viene en ingles (Celestia)
        t = str(e['npc_type'])
        fila = (con.execute('select name from monster where id=?', (t,)).fetchone()
                if e['monstruo'] else None)
        if fila is None:
            fila = con.execute('select name from npc where id=?', (t,)).fetchone()
        if fila is None:
            fila = con.execute('select name from monster where id=?', (t,)).fetchone()
        if fila and fila[0] and fila[0] != e['nombre']:
            e['nombre_original'] = e['nombre']
            e['nombre'] = fila[0]
            cambiados += 1
    con.close()
    return cambiados


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', type=int, required=True)
    ap.add_argument('--nombre', required=True, help='sin .json')
    ap.add_argument('--sesiones', nargs='+', required=True)
    ap.add_argument('--nota', default='')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')

    mats = materiales()
    spawns, recursos, carteles = leer(a.sesiones)
    ds = [spawn_a_datos(e, b) for e, b in sorted(spawns.items())]
    dr = [recurso_a_datos(e, b, mats, carteles.get(e))
          for e, b in sorted(recursos.items())]

    traducir_nombres(ds)
    ds, descartados = filtrar_irrepresentables(ds)
    ds, repetidos = quitar_repetidos_de_otra_sesion(ds)
    descartados += repetidos

    salida = {'_nota': a.nota, 'stage': a.stage, 'spawns': ds, 'recursos': dr}
    if descartados:
        salida['_descartados'] = descartados
    f = RAIZ / 'server' / 'plantillas' / (a.nombre + '.json')
    f.write_text(json.dumps(salida, ensure_ascii=False, indent=1),
                 encoding='utf-8')

    mobs = [e for e in ds if e['monstruo']]
    print('%s: %d spawns (%d monstruos, %d NPC) y %d objetos de mapa'
          % (f.name, len(ds), len(mobs), len(ds) - len(mobs), len(dr)))
    for n, c in collections.Counter(e['nombre'] for e in mobs).most_common():
        print('   mob  %-20s x%d' % (n, c))
    for e in ds:
        if not e['monstruo']:
            print('   npc  %-20s tile %s' % (e['nombre'], e['tile']))
    print('   -- objetos de mapa --')
    cnt = collections.Counter()
    for r in dr:
        cnt[(r['sprite'], r.get('que_es') or r.get('material')
             or (' | '.join(r['material_posibles'])
                 if r.get('material_posibles') else '?'))] += 1
    for (spr, n), c in sorted(cnt.items()):
        print('   %-6d %-34s x%d' % (spr, n, c))
    tor = [r for r in dr if r['sprite'] == 60001]
    for r in tor:
        print('   TORNADO en tile (%d,%d) entity %d'
              % (r['px'][0] // 32, r['px'][1] // 32, r['entity_id']))


if __name__ == '__main__':
    main()
