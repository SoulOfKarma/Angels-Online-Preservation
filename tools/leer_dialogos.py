"""Saca de una captura los dialogos y las tiendas de los NPC de un mapa.

Con UN clic por NPC se obtiene todo lo que hace falta para que funcione:

  c2s 0x0005  [u32 entidad][u16 0]        el jugador hace clic en el NPC
  s2c 0x0012  el dialogo                  saludo, opciones y acciones
  s2c 0x0034  [u16 shop_id]               si la opcion abre una tienda

El cuerpo del 0x0012, ya medido:

  [u32 mid][u16 val][u16 ?][u8 n][u8 ?]  n x [u32 opcion]  n x [u32 accion]

'mid' es el id del texto en setting/eng/msg.xml, que trae los 42.037 textos
del juego. O sea que el TEXTO no hay que capturarlo: sale del cliente. Lo
unico que el clic aporta es el ENLACE entre el NPC y su dialogo, que no esta
en ningun xml (se comprobo en npc.xml, quest.xml, stage.xml y order.xml).

    python tools/leer_dialogos.py --mapa hoca_village \
        --sesiones logs/proxy/mundo_125834_539855_orden.jsonl
"""
import argparse
import glob
import json
import pathlib
import re
import struct
import sys

RAIZ = pathlib.Path(__file__).parent.parent
PAKS = pathlib.Path('G:/extracted_paks')


def textos():
    """msg.xml: id -> texto en ingles."""
    out = {}
    for f in sorted(glob.glob(str(PAKS / '*/setting/eng/msg.xml'))):
        t = open(f, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'<[^>]*?編號="(\d+)"[^>]*?(?:內容|訊息|文字)="([^"]*)"', t):
            out[int(m.group(1))] = m.group(2)
    return out


def tiendas():
    """shop.xml: shop_id -> [item_id]."""
    out = {}
    for f in sorted(glob.glob(str(PAKS / '*/setting/shop.xml'))):
        t = open(f, encoding='utf-8', errors='replace').read()
        for m in re.finditer(r'<商店 編號="(\d+)">(.*?)</商店>', t, re.S):
            out[int(m.group(1))] = [int(x) for x in
                                    re.findall(r'<item\d+>(\d+)</item\d+>', m.group(2))]
    return out


def parsear_dialogo(b: bytes) -> dict:
    """El cuerpo del 0x0012, sin el opcode."""
    if len(b) < 9:
        return None
    # La cabecera son NUEVE bytes y el numero de opciones esta en el 7:
    #     [u32 mid][u16 val][u8 ?][u8 n][u8 ?]
    # y luego n ids de opcion y n codigos de accion, todos u32. Comprobado
    # contra el 10124 del Angels' Tutor, que ya estaba medido byte a byte.
    mid, val, unk6, n, unk8 = struct.unpack_from('<IHBBB', b, 0)
    if n > 8 or 9 + n * 8 > len(b):
        return None
    ops = list(struct.unpack_from('<%dI' % n, b, 9)) if n else []
    acc = list(struct.unpack_from('<%dI' % n, b, 9 + n * 4)) if n else []
    return {'mid': mid, 'val': val, 'opciones': ops, 'acciones': acc}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mapa', required=True, help='nombre de la plantilla, sin .json')
    ap.add_argument('--sesiones', nargs='+', required=True)
    ap.add_argument('--salida', default=None)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')

    plant = json.loads((RAIZ / 'server' / 'plantillas' /
                        (a.mapa + '.json')).read_text(encoding='utf-8'))
    quien = {e['entity_id']: (e['nombre'], e['npc_type'])
             for e in plant['spawns'] if not e['monstruo']}
    msg, sh = textos(), tiendas()

    salida = {}
    for f in a.sesiones:
        regs = [json.loads(l) for l in open(f, encoding='utf-8', errors='replace')
                if l.strip()]
        ult = None
        for r in regs:
            if r['dir'] == 'c2s' and r['opcode'] in (0x05, 0x0B) and r.get('hex'):
                b = bytes.fromhex(r['hex'])
                if len(b) >= 4:
                    e = struct.unpack_from('<I', b, 0)[0]
                    if e in quien:
                        ult = e
            if ult is None or r['dir'] != 's2c':
                continue
            if r['opcode'] == 0x12 and r['len'] >= 12:
                d = parsear_dialogo(bytes.fromhex(r['hex']))
                if d:
                    nom, tipo = quien[ult]
                    salida.setdefault(str(tipo), {'nombre': nom, 'entidad': ult})
                    salida[str(tipo)]['dialogo'] = d
            elif r['opcode'] == 0x34 and r['len'] >= 2:
                sid = struct.unpack_from('<H', bytes.fromhex(r['hex']), 0)[0]
                nom, tipo = quien[ult]
                salida.setdefault(str(tipo), {'nombre': nom, 'entidad': ult})
                salida[str(tipo)]['tienda'] = sid

    for tipo, v in sorted(salida.items(), key=lambda x: x[1]['nombre']):
        print('\n%s  (npc_type %s)' % (v['nombre'], tipo))
        d = v.get('dialogo')
        if d:
            print('   mid %-7d %r' % (d['mid'], (msg.get(d['mid']) or '?')[:95]))
            for o, ac in zip(d['opciones'], d['acciones']):
                print('     opcion %-7d accion 0x%06X  %r'
                      % (o, ac, (msg.get(o) or '?')[:70]))
        if 'tienda' in v:
            it = sh.get(v['tienda'], [])
            print('   TIENDA %d con %d articulos' % (v['tienda'], len(it)))

    if a.salida:
        p = RAIZ / a.salida
        p.write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding='utf-8')
        print('\n%d NPC guardados en %s' % (len(salida), a.salida))


if __name__ == '__main__':
    main()
