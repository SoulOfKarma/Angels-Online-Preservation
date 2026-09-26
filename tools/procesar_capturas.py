"""Encadena las sesiones de una tanda y las reparte por mapa, sin adivinar.

El problema que resuelve. Cada cruce de portal abre CONEXION NUEVA, asi que
una tarde de capturas deja diez o quince archivos, cada uno empezando en un
mapa distinto. separar_por_mapa.py necesita saber en cual empieza cada uno, y
hasta ahora eso se le pasaba a mano. Tres errores de la misma tarde salieron
de ahi:

  - Se le dijo que una sesion empezaba en el 397 y era de OTRO SERVIDOR. Sus
    veinte Pyramid Cat acabaron en un mapa de pulpos.
  - Se genero una plantilla con una captura incompleta y no se volvio a
    generar; quedo con 105 objetos cuando su captura ya tenia 174, y entre
    los que faltaban estaba su tornado.
  - Se junto con un comodin todo lo que se llamara stage397, sin mirar de
    donde venia cada trozo.

Aqui no se adivina nada. El mapa de partida de una sesion es el mapa al que
apuntaba el ULTIMO 0x000C de la sesion anterior, y las sesiones se ordenan
por fecha de modificacion. Solo hace falta decir en que mapa empezo la
PRIMERA, y ni eso si esa primera trae un 0x000C antes de sus spawns.

Ademas comprueba que la tanda sea homogenea. El 0x0008 de Taiwan mide 63
bytes y sus entity_id van por los cientos de millones; el de Celestia mide 62
o 64 y sus ids por el millon. Una sesion que no encaje se SEPARA IGUAL pero
se avisa por pantalla y se deja fuera de lo que se recomienda juntar.

    python tools/procesar_capturas.py --desde 13:00 --stage-inicial 397
    python tools/procesar_capturas.py logs/proxy/mundo_13*.jsonl --stage-inicial 397
"""
import argparse
import collections
import datetime
import glob
import json
import os
import pathlib
import struct
import subprocess
import sys

RAIZ = pathlib.Path(__file__).parent.parent
SALIDA = RAIZ / 'logs' / 'proxy' / 'partido'


def resumen(f):
    """Cambios de mapa, spawns por tamano y rango de entity_id de una sesion."""
    cambios, tam, ids, movs = [], collections.Counter(), [], 0
    wings, ultimo_wing = [], -999
    regs = []
    for linea in pathlib.Path(f).open(encoding='utf-8'):
        try:
            regs.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    for k, r in enumerate(regs):
        h = r.get('hex') or ''
        # SUPERWING. El 0x0151 teletransporta y provoca un 0x000C igual que un
        # portal, asi que sin mirarlo se toma por un cruce y se acaba midiendo
        # un portal que no existe. Paso: dos saltos con Superwing aparecieron
        # como "402 -> 21" y "21 -> 276", y el usuario tuvo que avisar.
        if r.get('dir') == 'c2s' and r.get('opcode') == 0x0151:
            ultimo_wing = k
        if r.get('dir') == 's2c' and r.get('opcode') == 0x000C and len(h) >= 8:
            st = struct.unpack_from('<I', bytes.fromhex(h), 0)[0]
            cambios.append(st)
            if k - ultimo_wing <= 40:
                wings.append(st)
        elif r.get('dir') == 's2c' and r.get('opcode') == 0x0008:
            b = bytes.fromhex(h)
            tam[len(b)] += 1
            if len(b) >= 4:
                ids.append(struct.unpack_from('<I', b, 0)[0])
        elif r.get('dir') == 'c2s' and r.get('opcode') == 0x0004:
            movs += 1
    return {'cambios': cambios, 'wings': wings, 'tam': tam, 'movs': movs,
            'ids': (min(ids), max(ids)) if ids else None,
            'spawns': sum(tam.values())}


# Nombres conocidos, SOLO para que el informe se lea. La separacion NO depende
# de esta tabla: si aparece un servidor nuevo se agrupa igual, con su huella.
CONOCIDOS = {
    (63, 8): 'taiwan',       # 0x0008 de 63 bytes, entity_id de nueve cifras
    (63, 9): 'taiwan',
    (63, 10): 'taiwan',
    (64, 6): 'celestia',     # 0x0008 de 64 bytes, entity_id de siete cifras
    (64, 7): 'celestia',
    (62, 6): 'celestia',
    (62, 7): 'celestia',
}


def huella(r):
    """Identifica de QUE servidor es una sesion, sin saber su nombre.

    Se calcula, no se declara. Son dos rasgos que cada servidor tiene fijos y
    que resultaron suficientes para separar los dos que se han capturado:

      - el TAMANO del 0x0008, que depende de la version del protocolo
      - el ORDEN DE MAGNITUD del entity_id, o sea cuantas cifras tiene

    De ahi salio el caso que motivo todo esto: una sesion de 64 bytes con ids
    de siete cifras se colo entre otras de 63 bytes con ids de nueve, y metio
    veinte Pyramid Cat en un mapa de pulpos.

    Devolver una huella en vez de un nombre es lo que permite que esto siga
    funcionando si manana se captura de un tercer servidor: no hara falta
    tocar nada, se agrupara solo y saldra con su huella en el informe.
    """
    if not r['spawns']:
        return None
    tam = r['tam'].most_common(1)[0][0]
    cifras = len(str(r['ids'][1])) if r['ids'] else 0
    return (tam, cifras)


def nombre_huella(h):
    if h is None:
        return 'sin datos'
    return CONOCIDOS.get(h, 'desconocido(%dB,%d cifras)' % h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sesiones', nargs='*', help='si no se dan, se usa --desde')
    ap.add_argument('--desde', default=None,
                    help='hora HH:MM de hoy; coge las sesiones posteriores')
    ap.add_argument('--stage-inicial', type=int, default=None,
                    help='mapa en el que empieza la PRIMERA sesion')
    ap.add_argument('--separar', action='store_true',
                    help='ademas de informar, escribe los tramos por mapa')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')

    fs = list(a.sesiones)
    if not fs:
        fs = glob.glob(str(RAIZ / 'logs' / 'proxy' / 'mundo_*_orden.jsonl'))
        if a.desde:
            hh, mm = (int(x) for x in a.desde.split(':'))
            hoy = datetime.date.today()
            corte = datetime.datetime.combine(hoy, datetime.time(hh, mm)).timestamp()
            fs = [f for f in fs if os.path.getmtime(f) >= corte]
    fs.sort(key=os.path.getmtime)
    if not fs:
        print('no hay sesiones que procesar')
        return

    # CUAL ES LA FUENTE DE ESTA TANDA. Antes estaba fijo en "taiwan" y todo lo
    # que fuera de Celestia se descartaba, lo que dejaba el tool inservible
    # justo al volver a capturar en Celestia. Ahora la fuente la decide la
    # MAYORIA de las sesiones, y se avisa de las que no encajan, sea cual sea.
    votos = collections.Counter()
    for f in fs:
        h = huella(resumen(f))
        if h is not None:
            votos[h] += 1
    fuente = votos.most_common(1)[0][0] if votos else None
    if fuente:
        print('fuente de la tanda: %s  %s' % (nombre_huella(fuente),
              {nombre_huella(k): v for k, v in votos.items()}))
        print()

    actual = a.stage_inicial
    buenas, mapas = [], collections.defaultdict(list)
    print(f'{"sesion":<22} {"hora":<6} {"origen":<9} {"empieza":>8} '
          f'{"cambios":<22} {"spawns":>7}')
    for f in fs:
        r = resumen(f)
        h = huella(r)
        org = nombre_huella(h)
        hora = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime('%H:%M')
        nom = pathlib.Path(f).name.replace('_orden.jsonl', '')[6:]
        ajena = fuente is not None and h is not None and h != fuente
        ini = None if ajena else actual
        print(f'{nom:<22} {hora:<6} {org:<9} {str(ini):>8} '
              f'{str(r["cambios"])[:22]:<22} {r["spawns"]:>7}')
        if r.get('wings'):
            print(f'     AVISO: los stages {r["wings"]} se alcanzaron con '
                  'SUPERWING, no cruzando un portal. No medir portales ahi.')
        if ajena:
            print('     AVISO: esta sesion NO es de la misma fuente que el '
                  'resto. No se encadena ni se recomienda juntarla.')
        else:
            buenas.append((f, ini))
            en = ini
            for c in r['cambios']:
                en = c
            if r['cambios']:
                actual = r['cambios'][-1]
            # que mapas tocaron datos en esta sesion
            if r['spawns'] and ini is not None:
                mapas[ini].append(f)
            for c in r['cambios']:
                mapas[c].append(f)

    print('\nmapas con datos en esta tanda:')
    for st in sorted(k for k in mapas if k is not None):
        print(f'   stage {st}: {len(set(mapas[st]))} sesiones')

    if not a.separar:
        print('\n(solo informe; con --separar se escriben los tramos)')
        return

    print()
    for f, ini in buenas:
        cmd = [sys.executable, str(RAIZ / 'tools' / 'separar_por_mapa.py'), f]
        if ini is not None:
            cmd += ['--stage-inicial', str(ini)]
        subprocess.run(cmd, check=False)

    print('\nAhora, por cada mapa, juntar TODOS sus tramos:')
    for st in sorted(k for k in mapas if k is not None):
        trozos = sorted(SALIDA.glob(f'*_stage{st}_orden.jsonl'))
        if trozos:
            print(f'   stage {st}: {len(trozos)} tramos')


if __name__ == '__main__':
    main()
