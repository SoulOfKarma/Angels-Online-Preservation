"""Lee los mapas .mpc del cliente: objetos, TAGs, disparadores y dialogos.

POR QUE EXISTE. Hasta ahora cada portal del juego se ha sacado cruzandolo con
el cliente oficial delante y mirando la captura: una medida por tornado, dos
si se podia, y una nota explicando de donde sale cada casilla. Funciona, pero
cuesta una sesion de juego por portal y no sirve para lo que no se puede
cruzar -- una instancia a la que hay que llegar con el grupo montado, por
ejemplo.

No hacia falta. El cliente trae los mapas enteros en data1/map/mapNNN.mpc, y
ahi dentro esta el grafo de portales completo: que objeto hay en que casilla,
que evento dispara, y a que mapa y a que punto de llegada manda ese evento.

EL FORMATO. El .mpc no esta cifrado ni comprimido:

    +0   'MAP\\0'
    +4   u32 ancho, u32 alto  (en casillas)
    +12  u32 version (0x00010005)
    +16  u32 ancho de casilla, u32 alto de casilla (32 y 32 siempre)
    +24  u32 off_objetos, u32 N_OBJETOS      <- cuenta, no bytes
    +32  u32 off_xml_eventos, u32 bytes
    +52  u32 off_firma, u32 bytes (12: '#EDCLBK\\0' + u32)
    +60  u32 off_xml_dialogos, u32 bytes
    +68  u32 off_?, u32 bytes
    +76  u32 off_tags, u32 N_TAGS            <- cuenta, no bytes
    +96  la capa de casillas: ancho*alto registros de 6 bytes

Los dos pares de "longitud" que son CUENTA y no bytes se delataron solos: en
map073 el campo vale 3168 y 3168*74 cae EXACTAMENTE sobre el offset del xml
de eventos siguiente. Lo mismo con los TAGs, que cierran justo al final del
archivo: el parseo termina en el ultimo byte en los seis mapas que se
probaron a mano, y en los 399 que trae el cliente.

Objeto, 74 bytes:

    +0  u32 id de objeto (60001 = el tornado de los portales)
    +4  u32 pixel x    +8  u32 pixel y
    +20 u8  0xc0 constante
    +24 u32 NUMERO DE EVENTO, o 0 si el objeto no dispara nada

TAG, longitud variable: [u32 numero][u32 cuantos][cuantos * (u32 px, u32 py)].
Un TAG es un punto de llegada con dos o tres casillas alternativas; los que
pasan de 50 suelen tener muchas mas y son zonas de generador de monstruos.

LA Y VA DEL REVES. El .mpc cuenta la y desde ABAJO y el servidor desde
arriba:

    casilla_servidor = (px // 32, alto - 1 - py // 32)

Eso no es una suposicion. lava_cave.json tiene 70 objetos de mapa capturados
del servidor de Celestia con su pixel exacto: sin voltear casan 2 de 70, y
volteando casan LOS 70.

EL XML DE EVENTOS. En off_xml_eventos hay [u32 longitud][xml utf-8] con la
lista de eventos del mapa. Cada evento son disparadores (觸發="3" clic,
"9" pisar) con condiciones y acciones. Los codigos los nombra
setting/eventdef.xml. De las acciones aqui solo se usan las dos que estan
COMPROBADAS contra medidas nuestras:

    accion 3   CHANGE_MAP(mapa, tag)  -> portal a otro escenario
    accion 53  GOTO_TAG(tag)          -> portal interno, mismo mapa

Y comprobadas de verdad: `--validar` cruza el grafo que sale de aqui contra
las 528 llegadas que el proyecto tiene medidas una por una en portales.json.
Cuadran 527. La unica que no es la entrada a Magic Kichen Path, que no se
midio cruzando sino leyendo un paquete de una captura del cliente Global.

Las demas acciones se devuelven con su numero crudo a proposito: eventdef
las ordena de un modo que NO coincide con el numero que usa el mapa -- el 3
sale CHANGE_MAP cuando en eventdef va en la posicion 2 -- asi que ponerles
nombre por posicion seria inventarse la tabla.

Uso:
    python tools/mapa_del_cliente.py --stage 73
    python tools/mapa_del_cliente.py --stage 73 --objetos 60001
    python tools/mapa_del_cliente.py --portales 73 74 75
    python tools/mapa_del_cliente.py --validar
"""
import argparse
import collections
import glob
import json
import os
import pathlib
import re
import struct
import xml.etree.ElementTree as ET

RAIZ = pathlib.Path(__file__).parent.parent
PAKS = RAIZ / 'extracted_paks'

TORNADO = 60001         # el objeto de los portales, el mismo en todos los mapas
ACC_CHANGE_MAP = 3      # (mapa, tag)
ACC_GOTO_TAG = 53       # (tag) en el mismo mapa
# Abrir un dialogo del mapa. El numero NO sale de la posicion en eventdef.xml
# -- ahi BEGIN_MESSAGE va en la 21 -- sino de mirar que hace: sus 35 usos en
# map073 llevan todos un id que existe como <對話> en el xml de ese mismo
# mapa, y en Blue Ocean y Limitless Tower abren un menu y unas escaleras que
# se comportan exactamente como tales.
ACC_DIALOGO = 25
PISAR, CLIC = '9', '3'  # valores de 觸發


def _orden(carpeta):
    """Cuanto manda cada carpeta de pak. El cliente las aplica en orden, asi
    que si un mapa esta en data1 y en UPDATE19, vale el de UPDATE19."""
    n = os.path.basename(carpeta).lower()
    if n == 'data1':
        return 0
    m = re.fullmatch(r'update(\d*)', n)
    return int(m.group(1) or 1) if m else -1


def mapas_del_cliente():
    """stage -> ruta del .mpc mas nuevo que trae el cliente."""
    salida = {}
    for p in glob.glob(str(PAKS / '*' / 'map' / '*.mpc')):
        m = re.fullmatch(r'map(\d+)\.mpc', os.path.basename(p))
        if os.path.basename(p).lower() == 'farm.mpc':
            o = _orden(os.path.dirname(os.path.dirname(p)))
            if 501 not in salida or o > salida[501][0]:
                salida[501] = (o, p)
            continue
        if not m:
            continue        # 1map906.mpc y companía: no son escenarios
        st = int(m.group(1))
        o = _orden(os.path.dirname(os.path.dirname(p)))
        if st not in salida or o > salida[st][0]:
            salida[st] = (o, p)
    return {k: v[1] for k, v in salida.items()}


class Mapa:
    """Un mapNNN.mpc ya leido, con la y en el sentido del servidor."""

    def __init__(self, stage, ruta):
        self.stage = stage
        self.ruta = ruta
        b = pathlib.Path(ruta).read_bytes()
        if b[:4] != b'MAP\0':
            raise ValueError('%s no empieza por MAP\\0' % ruta)
        self.ancho, self.alto = struct.unpack_from('<II', b, 4)
        c = struct.unpack_from('<24I', b, 12)
        self.off_objetos, self.n_objetos = c[3], c[4]
        self.objetos = self._objetos(b)
        self.tags = self._tags(b, c[16], c[17])
        self.eventos = self._eventos(b, c[5], c[6])
        # El 游標 (cursor) de cada evento. Va en el cuerpo del 0x000E detras
        # del sprite, con la marca 40 80: sin eso el cliente toma el objeto
        # por decorado y no deja pulsarlo (el altar de Qiuaner del Training
        # Palace, las estatuas...). 20 = pulsar, 3 = chocar (tornados).
        try:
            import re as _re
            self.cursores = {int(a): int(g) for a, g in _re.findall(
                r'<事件 編號="(\d+)" 游標="(\d+)"', self._xml(b, c[5], c[6]) or '')}
        except Exception:
            self.cursores = {}
        self.dialogos_xml = self._xml(b, c[12], c[13])

    # -- lectura ---------------------------------------------------------
    def casilla(self, px, py):
        return (px // 32, self.alto - 1 - py // 32)

    def _objetos(self, b):
        salida = []
        for i in range(self.n_objetos):
            o = self.off_objetos + i * 74
            oid, px, py = struct.unpack_from('<I', b, o)[0], *struct.unpack_from('<II', b, o + 4)
            salida.append({'i': i, 'id': oid, 'tile': self.casilla(px, py),
                           'px': (px, py),
                           'evento': struct.unpack_from('<I', b, o + 24)[0],
                           # La capa del 0x000E. Es el byte 16 del registro:
                           # comprobado contra los 75 objetos de mapa que
                           # Celestia manda en Lava Cave, coincide en 75 de 75.
                           'capa': b[o + 16],
                           'zona': b[o + 21],
                           'tipo': struct.unpack_from('<H', b, o + 34)[0],
                           # EL EVENTO DEL BICHO, que no es el del objeto.
                           # El +24 es el evento que dispara el objeto al
                           # pisarlo o pulsarlo; este otro es el que se
                           # dispara cuando MUERE lo que sale del generador,
                           # y es donde estan los botines de mision.
                           #
                           # Hacia falta porque los disparadores de muerte
                           # citan eventos que ningun objeto del mapa
                           # referencia: en Dense Forest los objetos solo
                           # nombran el 1, 2, 3, 4 y 1001, y los botines
                           # cuelgan del 501 al 505 y del 542. Buscando esos
                           # numeros dentro de los 74 bytes salieron todos
                           # en el +50, y cada tipo de monstruo lleva uno
                           # solo y siempre el mismo: 112->501, 113->505,
                           # 114->502, 116->542, 117->503.
                           #
                           # Es u32, NO u16: leido en 16 bits los eventos por
                           # encima de 65535 salian truncados. El de los Stab
                           # Jellyfish de Wave Harbor es el 70501 y se leia
                           # 4965, un evento que no existe: matarlos no sumaba
                           # a la mision 976 ("Nature is Crying for Help").
                           'evento_monstruo':
                               struct.unpack_from('<I', b, o + 50)[0],
                           'tiempo': struct.unpack_from('<H', b, o + 38)[0],
                           'cantidad': struct.unpack_from('<H', b, o + 42)[0]})
        return salida

    def _tags(self, b, off, cuantos):
        salida, p = {}, off
        for _ in range(cuantos):
            num, n = struct.unpack_from('<II', b, p)
            p += 8
            pts = []
            for k in range(n):
                px, py = struct.unpack_from('<II', b, p + k * 8)
                pts.append(self.casilla(px, py))
            p += 8 * n
            salida[num] = pts
        self.fin_tags = p
        return salida

    @staticmethod
    def _xml(b, off, largo):
        if largo <= 4:
            return None
        n = struct.unpack_from('<I', b, off)[0]
        return b[off + 4:off + 4 + n].decode('utf-8', 'replace')

    def _eventos(self, b, off, largo):
        """numero de evento -> lista de (disparo, accion, parametros)."""
        txt = self._xml(b, off, largo)
        if not txt:
            return {}
        salida = {}
        try:
            raiz = ET.fromstring(txt)
        except ET.ParseError:
            return {}
        for ev in raiz.findall('事件'):
            acc = []
            for tr in ev.findall('觸發器'):
                disparo = tr.get('觸發')
                for a in tr.findall('動作'):
                    acc.append((disparo, int(a.get('編號')),
                                tuple(int(q.get('數值'))
                                      for q in a.findall('參數'))))
            salida[int(ev.get('編號'))] = acc
        return salida

    # -- lo que interesa -------------------------------------------------
    def portales(self, solo_tornados=True):
        """Los objetos que mueven al jugador, resueltos.

        Devuelve dicts con la casilla del objeto, a que mapa manda y el TAG
        de llegada. El tornado sin destino -- el que solo saca un dialogo --
        sale con destino None y las acciones crudas, para no perderlo.

        SOLO EL OBJETO 60001 por defecto, que es el tornado con alas, el
        unico que portales.json llama portal. Hay otros objetos que tambien
        mueven al jugador y NO son portales: en map078.mpc hay 140 objetos
        60157 colgados todos del mismo evento 101, que hace GOTO_TAG a un
        tag de diez casillas. Eso no es un tornado, es otra cosa -- una
        trampa o una corriente -- y meterlo en portales.json ensuciaria el
        json con 140 entradas falsas. Con solo_tornados=False salen todos,
        para poder mirarlos.
        """
        salida = []
        for o in self.objetos:
            if not o['evento']:
                continue
            if solo_tornados and o['id'] != TORNADO:
                continue
            acc = self.eventos.get(o['evento'])
            if not acc:
                continue
            mueve = [(n, p) for _d, n, p in acc
                     if n in (ACC_CHANGE_MAP, ACC_GOTO_TAG)]
            if not mueve and o['id'] != TORNADO:
                continue
            e = {'tile': o['tile'], 'objeto': o['id'], 'evento': o['evento'],
                 'pisar': any(d == PISAR for d, _n, _p in acc),
                 'destino': None, 'tag': None,
                 'acciones': sorted({(n, p) for _d, n, p in acc})}
            for n, p in mueve:
                if n == ACC_CHANGE_MAP and len(p) >= 2:
                    e['destino'], e['tag'] = p[0], p[1]
                elif n == ACC_GOTO_TAG and p:
                    e['destino'], e['tag'] = self.stage, p[0]
            if e['destino'] is None:
                # EL VIAJE PUEDE ESTAR DETRAS DEL DIALOGO. Un tornado cuya
                # unica accion es abrir un dialogo no tiene por que ser una
                # puerta muerta: las escaleras de Limitless Tower abren el
                # dialogo 5002, que comprueba si el piso esta limpio y
                # entonces hace GOTO_TAG. Son 27 tornados de las instancias
                # abiertas, y dejandolos mudos la torre no se puede subir.
                for n, p in e['acciones']:
                    if n == ACC_DIALOGO and p:
                        v = self._viaje_tras(p[0])
                        if v:
                            e['destino'], e['tag'] = v
                            e['por_dialogo'] = p[0]
                            break
            salida.append(e)
        return salida


    def generadores(self):
        """LOS GENERADORES DE MONSTRUOS DEL MAPA.

        Esto es lo que se creia que no estaba y habia que capturar mapa a
        mapa recorriendolo con el cliente oficial. Si esta: cada generador es
        un objeto mas del array, con el monstruo en el u16 del +34.

            +21 u8  TAG de la zona donde aparecen, o 0 = en su propia casilla
            +34 u16 id de monster.xml
            +38 u16 tiempo de reaparicion (7200, 180 o 65535)
            +42 u16 CUANTOS aparecen

        Como se comprobo, usando el stage 73 de conjunto de prueba porque
        tiene una captura con 375 monstruos etiquetados:

          * los 283 valores del +34 resuelven LOS 283 en monster.xml, sin un
            solo numero que no sea un monstruo;
          * la suma de los +42 da 384 donde la captura vio 375;
          * el generador MAS CERCANO a cada monstruo capturado es de su misma
            clase el 93% de las veces, y barajando las clases de los
            generadores esa cifra se cae al 14%;
          * los 80 TAG que referencia el +21 existen los 80 en la tabla de
            TAGs del mapa.

        Y no es solo ese mapa: contra las 234 plantillas capturadas que tiene
        el proyecto, el total que declara el cliente sale IGUAL AL CAPTURADO
        en decenas de mapas -- 213 y 213, 228 y 228, 238 y 238 -- y el 81% de
        las clases que vio cada captura las declara tambien el cliente.

        El resto de las plantillas salio de capturas, con entity_id del
        servidor de Celestia, asi que la comparacion no es circular.
        """
        salida = []
        for o in self.objetos:
            if not o['tipo']:
                continue
            salida.append({'tipo': o['tipo'], 'tile': o['tile'],
                           'cantidad': o['cantidad'], 'tiempo': o['tiempo'],
                           'zona': o['zona'],
                           'puntos': list(self.tags.get(o['zona'], []))
                                     if o['zona'] else [o['tile']]})
        return salida


    # -- menus de dialogo ------------------------------------------------
    def _nodo_dialogo(self, num):
        if self.dialogos_xml is None:
            return None
        i = self.dialogos_xml.find('<對話 編號="%d"' % num)
        if i < 0:
            return None
        # El nodo puede venir cerrado en si mismo -- <對話 ... /> -- o con
        # hijos y su etiqueta de cierre. Se mira donde acaba la etiqueta de
        # apertura para saber cual de los dos es.
        fin_apertura = self.dialogos_xml.find('>', i)
        if self.dialogos_xml[fin_apertura - 1] == '/':
            trozo = self.dialogos_xml[i:fin_apertura + 1]
        else:
            cierre = '</對話>'
            j = self.dialogos_xml.find(cierre, fin_apertura)
            if j < 0:
                return None
            trozo = self.dialogos_xml[i:j + len(cierre)]
        try:
            return ET.fromstring(trozo)
        except ET.ParseError:
            return None

    def _viaje_tras(self, num, saltos=6):
        """A donde acaba llevando una rama del dialogo: (mapa, tag) o None.

        Una opcion de menu no lleva el CHANGE_MAP encima: apunta con
        `下一句` a otro nodo de dialogo, y ese nodo puede ser una condicion
        con dos ramas. El de Blue Ocean, por ejemplo:

            opcion -> 1000052 -> si EVENT_COND 22 (PARA_ENTER) de 98
                                 -> 1000054 -> CHANGE_MAP(98, 1)
                                 si no -> 1000055 -> aviso 1889

        Asi que se sigue la cadena por la rama que SI se cumple -- la que no
        es `反向="1"` -- hasta encontrar la accion 3. Lo de la capacidad de
        la instancia no se modela: aqui siempre se deja entrar.
        """
        if saltos <= 0:
            return None
        n = self._nodo_dialogo(num)
        if n is None:
            return None
        for tr in n.findall('觸發器'):
            for a in tr.findall('動作'):
                cod = int(a.get('編號'))
                p = [int(q.get('數值'))
                     for q in a.findall('參數')]
                if cod == ACC_CHANGE_MAP and len(p) >= 2:
                    return (p[0], p[1])
                # Y TAMBIEN EL GOTO_TAG. Se escapo la primera vez y el precio
                # fue caro: las escaleras de Limitless Tower van por aqui --
                # dialogo 5002, condicion 14 (GENERATOR_ALIVE del tag 93) y, si
                # el piso esta limpio, GOTO_TAG(3) -- asi que buscando solo el
                # CHANGE_MAP quedaban todas muertas y no se podia subir.
                if cod == ACC_GOTO_TAG and p:
                    return (self.stage, p[0])
        # las ramas: <觸發器> con su <條件> y el <成立 下一句="..."> que sigue
        inverso = [tr.find('條件') is not None
                   and tr.find('條件').get('反向') == '1'
                   for tr in n.findall('觸發器')]
        ramas = [int(s.get('下一句'))
                 for s in n.findall('成立')]
        for k, r in enumerate(ramas):
            if k < len(inverso) and inverso[k]:
                continue        # esa es la rama del "no puedes entrar"
            v = self._viaje_tras(r, saltos - 1)
            if v:
                return v
        return None

    def menu_de(self, dialogo):
        """Un menu de portal resuelto: el mensaje y a donde va cada opcion.

        Devuelve None si ese dialogo no es un menu que lleve a algun sitio.
        """
        n = self._nodo_dialogo(dialogo)
        if n is None:
            return None
        ops = []
        for o in n.findall('選項'):
            sig = int(o.get('下一句') or 0)
            ops.append({'msg': int(o.get('訊息')),
                        'siguiente': sig,
                        'viaje': self._viaje_tras(sig) if sig else None})
        if not any(o['viaje'] for o in ops):
            return None
        return {'msg': int(n.get('訊息') or 0), 'opciones': ops}


_CACHE = {}
_RUTAS = None


def mapa(stage):
    global _RUTAS
    if _RUTAS is None:
        _RUTAS = mapas_del_cliente()
    if stage not in _CACHE:
        r = _RUTAS.get(stage)
        _CACHE[stage] = Mapa(stage, r) if r else None
    return _CACHE[stage]


def llegada(stage_destino, tag):
    """Las casillas de llegada de ese TAG, o [] si no se sabe."""
    m = mapa(stage_destino)
    return list(m.tags.get(tag, [])) if m else []


# -- validacion ----------------------------------------------------------
def validar():
    """Cruza el grafo del cliente contra las llegadas medidas a mano.

    portales.json es el registro de 528 llegadas medidas cruzando portales
    con el cliente oficial delante, una por una, a lo largo de meses. Si el
    grafo que sale del .mpc es bueno, tiene que reproducirlas.
    """
    f = RAIZ / 'server' / 'plantillas' / 'portales.json'
    d = json.loads(f.read_text(encoding='utf-8'))
    bien, lejos, sin_objeto = 0, [], 0
    cual = collections.Counter()
    for s, lst in d.get('mapas', {}).items():
        st = int(s)
        m = mapa(st)
        if not m:
            continue
        # Con solo_tornados=False, porque portales.json ya no lleva solo
        # tornados: tambien las escaleras y los pasos que son otro objeto.
        porcasilla = m.portales(solo_tornados=False)
        for p in lst or []:
            if not p.get('llegada') or p.get('destino') is None:
                continue
            tx, ty = p['tile']
            L = tuple(p['llegada'])
            cerca = [e for e in porcasilla
                     if e['destino'] == p['destino']
                     and abs(e['tile'][0] - tx) <= 3
                     and abs(e['tile'][1] - ty) <= 3]
            if not cerca:
                sin_objeto += 1
                continue
            mejor = None
            for e in cerca:
                pts = llegada(e['destino'], e['tag'])
                if not pts:
                    continue
                ds = [abs(q[0] - L[0]) + abs(q[1] - L[1]) for q in pts]
                if mejor is None or min(ds) < mejor[0]:
                    mejor = (min(ds), ds.index(min(ds)), e, pts)
            if mejor is None:
                sin_objeto += 1
            elif mejor[0] <= 10:
                bien += 1
                cual[mejor[1]] += 1
            else:
                lejos.append((st, p, mejor))
    print('llegadas medidas que el cliente reproduce : %d' % bien)
    print('llegadas que NO cuadran                   : %d' % len(lejos))
    print('portales sin objeto en el .mpc            : %d' % sin_objeto)
    print('punto del TAG que casa con lo medido      : %s'
          % dict(sorted(cual.items())))
    for st, p, mejor in lejos:
        print('   stage %-4s %s -> %s (dest %s): el cliente dice %s, a %d'
              % (st, p['tile'], p['llegada'], p['destino'], mejor[3], mejor[0]))
    return not lejos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stage', type=int)
    ap.add_argument('--objetos', type=int, nargs='*',
                    help='solo los objetos con estos ids')
    ap.add_argument('--portales', type=int, nargs='+')
    ap.add_argument('--tags', type=int, nargs='+')
    ap.add_argument('--validar', action='store_true')
    a = ap.parse_args()

    if a.validar:
        raise SystemExit(0 if validar() else 1)

    if a.stage:
        m = mapa(a.stage)
        if not m:
            raise SystemExit('el cliente no trae el mapa %d' % a.stage)
        print('stage %d  %s' % (a.stage, m.ruta))
        print('  %d x %d casillas, %d objetos, %d tags, %d eventos'
              % (m.ancho, m.alto, m.n_objetos, len(m.tags), len(m.eventos)))
        if a.objetos is not None:
            pedidos = set(a.objetos) or {TORNADO}
            for o in m.objetos:
                if o['id'] in pedidos:
                    print('   objeto %-6d %s evento %d'
                          % (o['id'], o['tile'], o['evento']))

    for st in (a.portales or []):
        m = mapa(st)
        if not m:
            print('stage %d: el cliente no lo trae' % st)
            continue
        print('== stage %d (%dx%d)' % (st, m.ancho, m.alto))
        for e in sorted(m.portales(), key=lambda e: e['evento']):
            dest = ('%s tag %s -> %s' % (e['destino'], e['tag'],
                                         llegada(e['destino'], e['tag']))
                    if e['destino'] is not None else 'SIN DESTINO')
            print('   %s objeto %-6d evento %-6d %s%s'
                  % (e['tile'], e['objeto'], e['evento'], dest,
                     '' if e['pisar'] else '  (solo al clicar)'))
            if e['destino'] is None:
                print('        acciones %s' % (e['acciones'],))

    for st in (a.tags or []):
        m = mapa(st)
        if not m:
            continue
        print('== tags de stage %d' % st)
        for k in sorted(m.tags):
            print('   tag %-4d %s' % (k, m.tags[k]))


if __name__ == '__main__':
    main()
