"""Los arboles de dialogo de cada mapa, a server/plantillas/dialogos_mapa.json.

POR QUE. Lo que dice un NPC de mision en cada momento esta escrito en el XML
de dialogos de su .mpc, como un arbol: el nodo raiz del NPC ramifica por el
estado de la mision (QUEST_STEP, QUEST_FINISH, objetos...) y cada rama lleva a
la linea exacta. Bella Bulu, en Clink Harbor:

    nodo 159016 (retrato 1572)
        si QUEST_STEP(1590, 3) -> nodo 1000011 -> mensaje 159031
            "Obtain 20 Microcoins from the Transport Workers, and then
             hand them over to Meow..."

El servidor elegia esa linea adivinando dentro del bloque de mensajes de la
mision, y le salia la de OTRO NPC: la 159013, la de Matia mandandote a
buscar a Bella.

COMO SE ATA EL NPC A SU ARBOL. El objeto del NPC en el mapa no lleva evento,
pero cada nodo lleva el RETRATO (臉譜), y el retrato sale del sprite del NPC:
Bella tiene el 40772 y su retrato es 1572, el mismo del nodo 159016.

Formato de cada nodo: {m: mensaje, c: retrato, s: siguiente, o: [[mensaje,
siguiente]...], r: [{si: [[cond, params, negada]...], o: basta_una, ir:
nodo}...], a: [[accion, params]...]}.

    python tools/propagar_dialogos_mapa.py
    python tools/propagar_dialogos_mapa.py --sp   # solo dialogos_sp.json

LOS NPC DE LOS sp_*.xml (Matia en las cuatro ciudades, los de la region de
Taiwan...) no viven en ningun .mpc: su arbol esta en setting/eng/spmsg.xml,
con el mismo formato. Va aparte, a dialogos_sp.json, y el servidor lo pone
debajo del arbol de cada mapa. Sin el, Matia decia siempre su linea raiz
("hace falta nivel 380") aunque el personaje tuviera 425.
"""
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'tools'))
import mapa_del_cliente as mc

SALIDA = RAIZ / 'server' / 'plantillas' / 'dialogos_mapa.json'
SALIDA_SP = RAIZ / 'server' / 'plantillas' / 'dialogos_sp.json'


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _nodos(xml):
    try:
        return list(ET.fromstring(xml).iter('對話'))
    except ET.ParseError:
        salida = []
        for trozo in re.findall(r'<對話 .*?(?:/>|</對話>)', xml, re.S):
            try:
                salida.append(ET.fromstring(trozo))
            except ET.ParseError:
                pass
        return salida


def _nodo(n):
    d = {}
    for clave, attr in (('m', '訊息'), ('c', '臉譜'), ('s', '下一句')):
        v = _int(n.get(attr))
        if v:
            d[clave] = v
    ops = [[_int(o.get('訊息')) or 0, _int(o.get('下一句')) or 0] for o in n.findall('選項')]
    if ops:
        d['o'] = ops
    ramas, acciones = [], []
    hijos = list(n)
    for i, h in enumerate(hijos):
        if h.tag != '觸發器':
            continue
        conds = [[_int(c.get('編號')) or 0,
                  [_int(p.get('數值')) or 0 for p in c.findall('參數')],
                  c.get('反向') == '1'] for c in h.findall('條件')]
        for a in h.findall('動作'):
            acciones.append([_int(a.get('編號')) or 0,
                             [_int(p.get('數值')) or 0 for p in a.findall('參數')]])
        sig = hijos[i + 1] if i + 1 < len(hijos) else None
        if conds and sig is not None and sig.tag == '成立':
            ramas.append({'si': conds, 'o': h.find('旗標') is not None,
                          'ir': _int(sig.get('下一句')) or 0})
    if ramas:
        d['r'] = ramas
    if acciones:
        d['a'] = acciones
    return d


def propagar():
    todo = {}
    total = mapas = 0
    for stage, ruta in sorted(mc.mapas_del_cliente().items()):
        try:
            m = mc.Mapa(stage, ruta)
        except Exception:
            continue
        if not m.dialogos_xml:
            continue
        nodos = {}
        for n in _nodos(m.dialogos_xml):
            k = _int(n.get('編號'))
            if k:
                nodos[str(k)] = _nodo(n)
        if not nodos:
            continue
        todo[str(stage)] = nodos
        total += len(nodos)
        mapas += 1
    # UN SOLO FICHERO: uno por mapa eran 385 en el repo para 2,6 MB.
    SALIDA.write_text(json.dumps(todo, ensure_ascii=False, separators=(',', ':')),
                      encoding='utf-8')
    peso = SALIDA.stat().st_size
    print('%d mapas, %d nodos de dialogo, %.1f MB en %s'
          % (mapas, total, peso / 1e6, SALIDA))


def propagar_sp():
    import paks
    nodos = {}
    for n in _nodos(paks.texto('spmsg.xml')):
        k = _int(n.get('編號'))
        if k:
            nodos[str(k)] = _nodo(n)
    SALIDA_SP.write_text(json.dumps(nodos, ensure_ascii=False, separators=(',', ':')),
                         encoding='utf-8')
    print('spmsg.xml: %d nodos, %.1f MB en %s'
          % (len(nodos), SALIDA_SP.stat().st_size / 1e6, SALIDA_SP))


if __name__ == '__main__':
    if '--sp' not in sys.argv:
        propagar()
    propagar_sp()
