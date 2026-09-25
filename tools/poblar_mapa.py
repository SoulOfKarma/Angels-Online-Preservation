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
    d = {'entity_id': e, 'capa': struct.unpack_from('<I', b, 4)[0],
         'px': px, 'medio': b[16:32].hex(), 'marca': b[32],
         'orient': b[33], 'sprite': sprite, 'cola': b[36:43].hex()}
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

    salida = {'_nota': a.nota, 'stage': a.stage, 'spawns': ds, 'recursos': dr}
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
