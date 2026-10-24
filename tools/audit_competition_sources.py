"""Read-only, compact original competition evidence (no account access)."""
import argparse
import json
import pathlib
import sys
import struct
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mapa_del_cliente as maps
import eventos_del_cliente as events


def node(n, actions, conditions):
    values = list(n.attrib.values())
    out = {'attrs': values}
    children = []
    for ch in n:
        row = node(ch, actions, conditions)
        if ch.tag in ('動作', '條件') and values:
            lookup = actions if ch.tag == '動作' else conditions
            row['name'] = lookup.get(int(list(ch.attrib.values())[0]), '?')
        row['kind'] = {'對話': 'dialogue', '選項': 'option', '觸發器': 'trigger',
                       '動作': 'action', '條件': 'condition', '參數': 'parameter',
                       '成立': 'next'}.get(ch.tag, ch.tag)
        children.append(row)
    if children:
        out['children'] = children
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', type=int)
    parser.add_argument('ids', nargs='*', type=int)
    parser.add_argument('--holy-data', action='store_true')
    args = parser.parse_args()
    m = maps.mapa(args.stage)
    a, c = events.diccionario()
    if args.holy_data:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'server'))
        from house_services import xml_rows
        blob = pathlib.Path(m.ruta).read_bytes()
        monster_rows, npc_rows = xml_rows('monster.xml'), xml_rows('npc.xml')
        generators = {g['tipo']: g for g in m.generadores()}
        structures = []
        for typ, g in sorted(generators.items()):
            if not 3902 <= typ <= 3985:
                continue
            row = monster_rows[typ]
            team = 1 if typ <= 3925 or 3936 <= typ <= 3960 else 2
            idol = typ >= 3936
            number = typ - (3935 if team == 1 else 3960) if idol else g['zona'] - (30 if team == 1 else 40)
            for index, tile in enumerate(sorted(set(g['puntos'])) if not idol else [g['tile']]):
                structures.append(dict(entity=71200000+typ*10+index, npc_type=typ,
                    sprite=int(row['圖號']), nombre=row['名稱'], hp=int(row['HP']),
                    tile=tile, team=team, kind='idol' if idol else 'guard', number=number))
        npcs = []
        for o in m.objetos:
            if not 40000 < o['id'] < 50000:
                continue
            typ = struct.unpack_from('<H', blob, m.off_objetos+o['i']*74+22)[0]
            if typ in (1892, 2433):
                continue
            npcs.append(dict(entity=71120000+typ, npc_type=typ, sprite=o['id'],
                tile=o['tile'], nombre=npc_rows[typ]['名稱'], team=1 if o['tile'][0]>200 else 2))
        walls = [dict(sprite=o['id'], tile=o['tile'], team=1 if o['zona']<21 else 2,
                      number=o['zona']-(10 if o['zona']<21 else 20), entity=71300000+o['zona'])
                 for o in m.objetos if o['id']>=60000 and 11<=o['zona']<=30]
        resources = []
        for o in m.objetos:
            mid = struct.unpack_from('<H',blob,m.off_objetos+o['i']*74+22)[0]
            if o['id']>=60000 and 248<=mid<=257:
                resources.append(dict(entity_id=71400000+o['i'],sprite=o['id'],
                    tile=o['tile'],px=[o['tile'][0]*32+16,o['tile'][1]*32+16],material=mid))
        barriers = [dict(tile=o['tile'], event=o['evento']) for o in m.objetos if 51<=o['evento']<=90]
        recipes = [dict(item=int(r['成品編號']), amount=int(r['成品數量']),
                        output=int(r['\u734e\u8cde\u6578\u91cf'])) for r in xml_rows('order.xml').values()
                   if r.get('\u984d\u5916\u734e\u8cde')=='8536' and r.get('\u734e\u8cde\u6a5f\u7387')=='100']
        print(json.dumps(dict(source=str(pathlib.Path(m.ruta).relative_to(maps.RAIZ)),
                              structures=structures,npcs=npcs,walls=walls,barriers=barriers,resources=resources,
                              tags=m.tags,recipes=recipes),ensure_ascii=True,indent=2))
        sys.exit()
    root = ET.fromstring(m.dialogos_xml)
    for n in root:
        if n.tag != '對話':
            continue
        if not args.ids or int(list(n.attrib.values())[0]) in args.ids:
            print(json.dumps(node(n, a, c), ensure_ascii=True))
