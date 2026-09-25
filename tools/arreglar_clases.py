"""Corrige los spawns que Celestia marca con el klass equivocado.

El clasificador miraba solo el klass del 0x0008: 199 y 200 son NPC, 0 es
decorado y cualquier otro valor es el NIVEL del bicho. Eso falla: hay
monstruos que llegan con klass 199, asi que acababan como NPC y sin IA.

El usuario lo encontro con los Bloody Croc y Moody Croc de Lost Trail.

Quien manda de verdad es el cliente:

  - setting/eng/npc.xml     ids del 1500 al 24893
  - setting/eng/monster.xml ids del 1 al 23860, con 陣營="怪物陣營"

Y NO comparten ni un solo id. Asi que para npc_type >= 1500 se sabe con
certeza: si esta en npc.xml es NPC y si esta en monster.xml es monstruo,
diga lo que diga el klass.

Por debajo de 1500 no se toca nada: npc.xml no llega ahi, asi que un
npc_type bajo que aparezca en monster.xml no prueba nada -- los NPC del
Lyceum usan numeros de dos y tres cifras que chocan con los de monster.xml.
"""
import glob
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).parent.parent
PAKS = pathlib.Path('G:/extracted_paks')
DESDE = 1500          # por debajo de aqui npc.xml no tiene nada que decir


def tablas():
    mons, npcs = {}, {}
    for f in sorted(glob.glob(str(PAKS / '*/setting/eng/monster.xml'))):
        for m in re.finditer(r'<npc([^>]*?)/>',
                             open(f, encoding='utf-8', errors='replace').read()):
            a = dict(re.findall(r'(\S+?)="([^"]*)"', m.group(1)))
            if a.get('編號') and a.get('陣營') == '怪物陣營':
                mons[int(a['編號'])] = a
    for f in sorted(glob.glob(str(PAKS / '*/setting/eng/npc.xml'))):
        for m in re.finditer(r'<npc([^>]*?)/>',
                             open(f, encoding='utf-8', errors='replace').read()):
            a = dict(re.findall(r'(\S+?)="([^"]*)"', m.group(1)))
            if a.get('編號'):
                npcs[int(a['編號'])] = a
    return mons, npcs


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.path.insert(0, str(RAIZ / 'server'))
    import login
    mons, npcs = tablas()
    total = 0
    for st, fn in sorted(login.PLANTILLAS_POR_STAGE.items()):
        p = RAIZ / 'server' / 'plantillas' / fn
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding='utf-8'))
        cambios = {}
        for e in d.get('spawns', []):
            t = e.get('npc_type')
            if t is None or t < DESDE:
                continue
            if t not in mons or t in npcs:
                continue
            if e.get('monstruo') and e.get('klass') not in (0, 199, 200):
                continue        # ya estaba bien
            # No basta con marcarlo como monstruo: el klass del 0x0008 es lo
            # que el cliente usa para PINTARLO, y con 199 lo sigue dibujando
            # azul, como un NPC. Los monstruos van con klass 1 y el nivel
            # aparte, igual que los que ya salian bien.
            k = e.get('klass_original', e.get('klass'))
            e['monstruo'] = True
            e['klass_original'] = k
            e['klass'] = 1
            e['nivel'] = int(mons[t].get('等級') or 1)
            e['nombre_cliente'] = mons[t].get('名稱')
            cambios[(e['nombre'], t, k, e['nivel'])] =                 cambios.get((e['nombre'], t, k, e['nivel']), 0) + 1
        if cambios:
            p.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                         encoding='utf-8')
            for (nom, t, k, lv), n in sorted(cambios.items()):
                print('  stage %-4d %-24s %-18s type=%-6d klass %s -> 1, nivel %-4d x%d'
                      % (st, fn[:-5][:24], nom[:18], t, k, lv, n))
                total += n
    print('\n%d spawns pasados de NPC a monstruo' % total)


if __name__ == '__main__':
    main()
