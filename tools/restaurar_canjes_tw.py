"""Reincorporar los canjes TW en grupos propios, sin contaminar los de IGG.

preparar no escribe en el cliente; instalar usa candidatos ya respaldados.
Los IDs de receta y todos los costes/premios originales se conservan.
"""
import collections
import datetime
import hashlib
import json
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tw_migracion as tw
import pak_tool
import traducir
import propagar_dialogos_mapa as pd

ROOT = tw.RAIZ
BASE = tw.IGG / 'update26/setting/eng'
STATE = ROOT / 'work/canjes_tw_restauracion.json'
CONFIG = ROOT / 'server/plantillas/tw_exchanges.json'
ORIGINAL = tw.BACKUPS / '20261026_160246/extracted_paks_update26/setting/eng/exchange.xml'
SOURCE = tw.BACKUPS / 'limpiar_canjes_20261026_215341/exchange.xml'
TITLES = {
181:'Weapon Coupon Rewards',182:'Armor Coupon Rewards',393:'Dailies Coin Rewards',
440:'Haunted Halloween Costumes',448:'Bottomless Pit Exploration',449:'Christmas Decorations',
450:'Crimson Christmas Costumes',451:'Radiant Hope Bells',453:'Daily Good Deeds',
454:'Blazing Dawn Realm Tickets',455:'Golden Soil',471:'Flower Spirit Costumes',
472:'Loyal Shiba Backpacks',473:'Tales of the Strange',474:'Early Summer Realm Tickets',
476:'Tales of the Strange',479:"Stranger's Clues",482:"Demeter's Newcomer Blessing",
483:'Roman Warrior Costumes',484:'Heavenly Ramen',485:'Summer Report Cards',
486:'Beachwear Costumes',487:'Heavenly Ramen',488:'Slimming Soup',489:'Midsummer Realm Tickets',
492:'Sakura and Forest Costumes',494:'Purple Heart Plush Hoods',501:'Slimming Medicines',
502:'Slimming Medicines',503:'Moon Rabbit Mount Costumes',504:'Moon Rabbit Costumes',
505:'Moon Rabbit Costumes',509:'Halloween Mage Costumes',520:'Sky Healer Costumes',
521:'Northern Sovereign Costumes',522:'Warm Christmas Costumes',523:'Northern Sovereign Costumes',
524:'Warm Christmas Costumes',525:'Golden Bell Ornaments',526:'Classic Hot Dogs',
527:'Crispy Golden Taiyaki',528:'Festival Firecrackers',536:'Lotus Summer Realm Tickets',
537:'Magic Crafting Materials',538:'Magic Crafting Materials',540:'Lavender and Thyme Pajamas',
550:'Silversteel Warrior Costumes',554:'Blue and Violet Jellyfish Costumes',
555:"Fatty's Taro",556:"Fatty's Gratitude",561:"Fatty's Letter Cards",
574:'Demon Costumes',577:"Queen's Feathers",585:'Exotic Food and Wine',586:'Five-Star Reviews',
587:'Night Watch Mage Costumes',599:'Angel Lover Costumes',600:'Love Essences and Macarons',
601:'Darkwing Mount Costumes',602:"Chick's Carnations",603:'Fishing Cleanup',604:'Festival Costumes',
611:'Snowy Stroll Costumes',616:'Christmas Firefighting',617:'Snowy Stroll Costumes',
618:'Snowy Grace Scriptures',620:'Springtime Pajama Costumes',621:'Neon Egg Paints',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def rows(path):
    return {k: tw.atributos(v) for k, v in tw.filas(tw.leer(path)).items()}


def pak_contents(path):
    data = path.read_bytes()
    return {tw.normal(e['nombre']): pak_tool.leer_entrada(data, e)
            for e in pak_tool.leer_indice(data)[0]}


def completar_servicios(config):
    # Estos numeros son grupos de exchange.xml; no son tiendas de shop.xml.
    for key, value in config['nodes'].items():
        for action in value.get('a', []):
            if action[0] == 14 and config['node_owners'].get(key) == 'Fortunia':
                action[0] = 98
                config['exchange_owners'][str(action[1][0])] = 'Fortunia'
    source = tw.indice_igg()['setting\\eng\\spmsg.xml'][1]
    tree = {str(n.get('編號')): pd._nodo(n) for n in pd._nodos(tw.leer(source))}
    pending=['513261'];seen=set()
    while pending:
        key=pending.pop()
        if key in seen or key=='0':continue
        seen.add(key);row=tree[key]
        pending.extend(str(target) for _,target in row.get('o', []))
        pending.extend(str(branch['ir']) for branch in row.get('r', []))
        if row.get('s'):pending.append(str(row['s']))
    mapping={key:992000+i for i,key in enumerate(sorted(seen,key=int))}
    mapping['513261']=513261
    for key in seen:
        row=json.loads(json.dumps(tree[key]))
        for option in row.get('o', []):option[1]=mapping.get(str(option[1]),option[1])
        for branch in row.get('r', []):branch['ir']=mapping.get(str(branch['ir']),branch['ir'])
        if row.get('s'):row['s']=mapping[str(row['s'])]
        for action,params in row.get('a', []):
            if action==98:config['exchange_owners'][str(params[0])]='Scrollmaker'
        dest=str(mapping[key]);config['nodes'][dest]=row;config['node_owners'][dest]='Scrollmaker'
    if not any(n['nombre']=='Scrollmaker' for n in config['npcs']):
        config['npcs'].append(dict(nombre='Scrollmaker',entity_id=404,npc_type=14888,
                                  sprite=40647,tile=[169,71],root=513261,face=1447,direccion=6))
    for entry in config['npcs']:
        if entry['nombre']=='Scrollmaker':
            entry.update(npc_type=14888,sprite=40647)
    return config


def preparar():
    backup = tw.BACKUPS / ('fortunia_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    stage = backup / 'preparado'
    stage.mkdir(parents=True)
    original, source, current = rows(ORIGINAL), rows(SOURCE), rows(BASE / 'exchange.xml')
    old_groups = {r['群組'] for r in original.values()}
    selected = {k: r for k, r in source.items() if k not in original and r['群組'] in old_groups}
    assert len(selected) == 8470
    group_map = {g: 2000 + index for index, g in enumerate(sorted({r['群組'] for r in selected.values()}, key=int))}
    assert not set(group_map.values()) & {int(r['群組']) for r in current.values()}
    items = {}
    for p in BASE.glob('item*.xml'):
        items.update(rows(p))
    translator = traducir.Traductor()
    def name(i):
        row = items.get(str(i), {})
        value = row.get('原型名稱', '') + row.get('基本名稱', '')
        return translator.traducir(value)[0]
    grouped = collections.defaultdict(list)
    for k, row in selected.items():
        grouped[row['群組']].append((k, row))
    config = dict(source=str(SOURCE.relative_to(ROOT)), group_map=group_map,
                  recipe_ids=sorted(map(int, selected)), nodes={}, node_owners={}, exchange_owners={},
                  npcs=[dict(nombre='Fortunia', entity_id=401, npc_type=8814, sprite=40002,
                             tile=[174,82], root=504131, face=2, direccion=6)], messages={})
    nodes, messages = config['nodes'], config['messages']
    counter = [991000]
    def message(value):
        counter[0] += 1
        messages[str(counter[0])] = value
        return counter[0]
    def node(data, key=None):
        counter[0] += 1
        key = key or counter[0]
        nodes[str(key)] = data
        return key
    categories = collections.defaultdict(list)
    label_counts = collections.Counter()
    for group, entries in sorted(grouped.items(), key=lambda x: int(x[0])):
        materials = collections.Counter(v for _, row in entries for k, v in row.items()
                                        if re.fullmatch('材料\\d+', k) and v != '0')
        names = [name(i) for i, _ in materials.most_common()]
        label = TITLES.get(int(group)) or names[0]
        if tw.RE_CJK.search(label):
            raise AssertionError(('translate menu title', group, label))
        label = label.replace('&amp;', '&')
        label = re.sub(r'^(20\d\d)Mall', r'\1 Mall', label)
        if 'Only for Little Angel Reference' in label:
            label = 'Equipment Collections'
        label_counts[label] += 1
        if label_counts[label] > 1:
            label += ' (%d)' % label_counts[label]
        if any('Runestone Voucher' in n for n in names): category = 'Runestones'
        elif any('Lucky ' in n and 'Voucher' in n for n in names): category = 'Lucky Hammers and Ride Feed'
        elif any('Scroll Voucher' in n for n in names): category = 'Spells and Stances V'
        elif any('Pet ' in n and 'Voucher' in n for n in names) or int(group) == 571: category = 'Pet Rewards'
        elif any('EXP Voucher' in n or 'Skill Bonus Voucher' in n for n in names): category = 'EXP and Skill Bonuses'
        elif int(group) in (181,182) or any('Only for Little Angel Reference' in n for n in names): category = 'Equipment and Weapons'
        elif any(w in label for w in ('Costume','Apparel','PD Voucher','Suitcase','Pajamas')): category = 'Costumes and Decorations'
        else: category = 'Event Rewards'
        mapped = group_map[group]
        config['exchange_owners'][str(mapped)] = 'Fortunia'
        target = node({'a': [[98, [mapped]]]})
        categories[category].append([message(label), target])
    root = 990200
    prompt = message('Which special exchange would you like to use?')
    back = message('Back')
    category_options = []
    for title, entries in categories.items():
        pages = [node({}) for _ in range((len(entries) + 4) // 5)]
        for index, key in enumerate(pages):
            options = entries[index*5:(index+1)*5]
            if index: options += [[message('Previous Page'), pages[index-1]]]
            if index + 1 < len(pages): options += [[5366, pages[index+1]]]
            options += [[back, root]]
            nodes[str(key)] = {'m': prompt, 'c': 2, 'o': options}
        category_options.append([message(title), pages[0]])
    node({'m': prompt, 'c': 2, 'o': category_options + [[5020, 0]]}, root)
    messages[str(root)] = 'Special Voucher and Event Exchanges'
    shop_nodes = {op: node({'a': [[14, [shop]]]}) for op, shop in
                  ((504825,45),(505907,132),(510922,538),(511419,539),(504141,596),
                   (512476,294),(510689,594),(504139,595),(504138,57),(504136,56))}
    node({'m':504134, 'c':2, 'o':[[op,shop_nodes[op]] for op in
         (504141,512476,510689,504139,504138,504136)] + [[root,root],[5020,0]]}, 504132)
    node({'m':504131, 'c':2, 'o':[[504132,504132]] + [[op,shop_nodes[op]] for op in
         (504825,505907,510922,511419)] + [[5020,0]]}, 504131)
    config['node_owners'] = {key:'Fortunia' for key in nodes}
    completar_servicios(config)
    text = tw.leer(BASE / 'exchange.xml')
    added = []
    for key, row in sorted(selected.items(), key=lambda x: int(x[0])):
        assert key not in current
        row = dict(row, 群組=str(group_map[row['群組']]))
        reward_name = name(row['獎賞1'])
        if reward_name and not tw.RE_CJK.search(reward_name):
            row['獎賞說明'] = reward_name.replace('&amp;', '&')
        added.append('<exchange ' + ' '.join('%s="%s"' % (k,traducir.escapar(v.replace('&amp;','&')))
                                             for k,v in row.items()) + '/>')
    offset = tw.punto_insercion(text)
    text = text[:offset] + '\r\n'.join(added) + '\r\n' + text[offset:]
    raw_msg = (BASE/'msg.xml').read_bytes()
    msg = raw_msg.decode('utf-8-sig')
    known = tw.filas(msg)
    assert not set(messages) & set(known)
    offset = tw.punto_insercion(msg)
    msg = msg[:offset] + ''.join('<字串 編號="%s" 文字="%s"/>\r\n' % (k,traducir.escapar(v))
                               for k,v in messages.items()) + msg[offset:]
    resources = {'setting\\eng\\exchange.xml': b'\xef\xbb\xbf' * tw.leer_bom(BASE/'exchange.xml') + text.encode('utf-8'),
                 'setting\\eng\\msg.xml': b'\xef\xbb\xbf' * raw_msg.startswith(b'\xef\xbb\xbf') + msg.encode('utf-8')}
    report = dict(backup=str(backup), stage=str(stage), paks={}, resources={k:digest(v) for k,v in resources.items()})
    for rel, raw in resources.items():
        dest = stage / pathlib.PureWindowsPath(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    (stage/'tw_exchanges.json').write_text(json.dumps(config, ensure_ascii=False, indent=1),encoding='utf-8')
    for filename in ('update26.pak','update26.pak.bak'):
        source, saved, dest = tw.CLIENTE/filename, backup/filename, stage/filename
        shutil.copy2(source,saved);shutil.copy2(source,dest)
        before = pak_contents(saved)
        pak_tool.actualizar(dest, resources)
        after = pak_contents(dest)
        assert before.keys() == after.keys()
        assert all(after[k] == v for k,v in before.items() if k not in resources)
        assert all(after[k] == v for k,v in resources.items())
        report['paks'][filename] = [digest(saved.read_bytes()),digest(dest.read_bytes())]
    STATE.write_text(json.dumps(report,indent=1),encoding='utf-8')
    print('Preparadas',len(selected),'recetas,',len(group_map),'grupos,',len(messages),'textos de menu. Respaldo:',backup)


def instalar():
    state = json.loads(STATE.read_text(encoding='utf-8'))
    stage, backup = pathlib.Path(state['stage']), pathlib.Path(state['backup'])
    for filename,(old,new) in state['paks'].items():
        assert digest((tw.CLIENTE/filename).read_bytes()) in (old,new), filename
        assert digest((stage/filename).read_bytes()) == new
    for filename in state['paks']:
        shutil.copy2(stage/filename,tw.CLIENTE/filename)
    for rel in state['resources']:
        target = tw.IGG/'update26'/pathlib.PureWindowsPath(rel)
        if not (backup/target.name).exists():shutil.copy2(target,backup/target.name)
        shutil.copy2(stage/pathlib.PureWindowsPath(rel),target)
    shutil.copy2(stage/'tw_exchanges.json', CONFIG)
    print('Instalados ambos PAK, XML y menus de Fortunia.')


def verificar():
    state = json.loads(STATE.read_text(encoding='utf-8'))
    for filename,(_,expected) in state['paks'].items():
        path = tw.CLIENTE/filename
        data = pak_contents(path)
        assert all(digest(data[k]) == value for k,value in state['resources'].items())
        print(filename,'CRC y recursos correctos')


def menus():
    state=json.loads(STATE.read_text(encoding='utf-8'))
    backup=pathlib.Path(state['backup'])/'tw_exchanges_antes_npcs.json'
    if not backup.exists():shutil.copy2(CONFIG,backup)
    config=completar_servicios(json.loads(CONFIG.read_text(encoding='utf-8')))
    raw=json.dumps(config,ensure_ascii=False,indent=1)
    CONFIG.write_text(raw,encoding='utf-8')
    (pathlib.Path(state['stage'])/'tw_exchanges.json').write_text(raw,encoding='utf-8')
    print('Fortunia: canjes originales; Scrollmaker: arbol nativo completo.')


if __name__ == '__main__':
    {'preparar':preparar,'instalar':instalar,'verificar':verificar,'menus':menus}[sys.argv[1]]()
