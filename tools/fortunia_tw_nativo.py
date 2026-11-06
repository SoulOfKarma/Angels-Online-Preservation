"""Catalogo completo de la cambiadora TW: arbol nativo, recetas y grupos propios."""
import datetime
import json
import pathlib
import re
import shutil
import sys
import importlib.util

sys.path[:0]=[str(pathlib.Path(__file__).parents[1]/'server'),str(pathlib.Path(__file__).parent)]
import tw_migracion as tw
import propagar_dialogos_mapa as pd
import traducir
import restaurar_canjes_tw as common
_spec=importlib.util.spec_from_file_location('server_transitable',tw.RAIZ/'server/transitable.py')
transitable=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(transitable)

STATE=tw.RAIZ/'work/fortunia_tw_nativo.json'
FIX_STATE=tw.RAIZ/'work/fortunia_tw_menu_fix.json'
BASE=tw.IGG/'update26/setting/eng'
NAME='TW Fortunia'
ENTITY=71410140
ROOT=993500
TEXTS={
5020:'Leave',5366:'Next Page',5367:'Previous Page',5368:'Leave',
504131:'Hello! I exchange lottery vouchers. Which exchange service would you like?',
504132:'Exchange vouchers for rewards.',504133:'Exchange collection tickets for rewards.',
504134:'Please select the items you wish to exchange:',
504135:'Weapons, armor and mounts',504136:'Robots, production gears and gathering cores',
504137:'Furniture, PD and Enchanted PD',504138:'Spell V Scrolls and special trinkets',
504139:'Enhancement items and bonus cards',504140:'General items',504141:'Runestones',
504142:'Equipment',504574:'2011 Dragon Boat Festival and Peach Garden rewards',
504830:'Exchange Lv 175 heavy armor for light armor or gowns',506148:'Special pets',
513503:'Which equipment level range are the runestones for?',
513504:'Lv 310 and above',513505:'Lv 210-300',513506:'Lv 60-200',
513800:'Which grade of enhancement items would you like to exchange?',
513801:'31-star and above',513802:'20-star to 30-star',513803:'19-star and below, and other items',
514463:'Other vouchers',
}


def preparar():
    backup=tw.BACKUPS/('fortunia_tw_nativo_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    stage=backup/'preparado';stage.mkdir(parents=True)
    idx=tw.indice_tw()
    tree={str(n.get('編號')):pd._nodo(n) for n in pd._nodos(tw.leer(idx['setting\\eng\\spmsg.xml'][1]))}
    seen=set();pending=['504131'];groups=set();messages=set()
    while pending:
        key=pending.pop()
        if key in seen or key=='0':continue
        seen.add(key);node=tree[key]
        if node.get('m'):messages.add(node['m'])
        for mid,target in node.get('o',[]):messages.add(mid);pending.append(str(target))
        pending.extend(str(branch['ir']) for branch in node.get('r',[]))
        if node.get('s'):pending.append(str(node['s']))
        for action,args in node.get('a',[]):
            assert action==98,(key,action,args)
            groups.add(args[0])
    assert messages<=TEXTS.keys()
    group_map={group:2400+i for i,group in enumerate(sorted(groups))}
    node_map={key:ROOT+i for i,key in enumerate(sorted(seen,key=int))}
    msg_map={key:994000+i for i,key in enumerate(sorted(messages))}
    config=json.loads(common.CONFIG.read_text(encoding='utf-8'))
    assert not any(n['nombre']==NAME for n in config['npcs']),'Ya instalado: usar verificar'
    for key in seen:
        node=json.loads(json.dumps(tree[key]))
        if node.get('m'):node['m']=msg_map[node['m']]
        for op in node.get('o',[]):op[:]=[msg_map[op[0]],node_map.get(str(op[1]),op[1])]
        for branch in node.get('r',[]):branch['ir']=node_map[str(branch['ir'])]
        if node.get('s'):node['s']=node_map[str(node['s'])]
        for action,args in node.get('a',[]):args[0]=group_map[args[0]]
        dest=str(node_map[key]);assert dest not in config['nodes']
        config['nodes'][dest]=node;config['node_owners'][dest]=NAME
    for old,new in group_map.items():
        assert str(new) not in config['exchange_owners']
        config['exchange_owners'][str(new)]=NAME
    for old,new in msg_map.items():config['messages'][str(new)]=TEXTS[old]
    tile=(170,82)
    assert transitable.se_pisa(41,*tile)
    config['npcs'].append(dict(nombre=NAME,entity_id=ENTITY,npc_type=8814,sprite=40002,
                              tile=list(tile),root=node_map['504131'],face=2,direccion=5,
                              spawn_template='Fortunia'))
    config['native_fortunia']=dict(root=node_map['504131'],groups={str(k):v for k,v in group_map.items()},
                                   recipes={},source='TW update32 spmsg.xml + exchange.xml')
    native=common.rows(idx['setting\\eng\\exchange.xml'][1]);current=common.rows(BASE/'exchange.xml')
    selected=[(key,row) for key,row in sorted(native.items(),key=lambda x:int(x[0])) if int(row['群組']) in groups]
    assert len(selected)==838
    # La ventana nativa enumera GetExchange(1), (2), ... hasta el primer NULL.
    # No basta con que el ID sea menor a 50000: no puede haber huecos previos.
    first_id=max(map(int,current))+1
    assert set(map(int,current))==set(range(1,first_id))
    additions=[]
    for index,(key,row) in enumerate(selected):
        new_id=first_id+index
        assert new_id<50000 and str(new_id) not in current
        new=dict(row,編號=str(new_id),群組=str(group_map[int(row['群組'])]))
        additions.append('<exchange '+' '.join('%s="%s"'%(k,traducir.escapar(v.replace('&amp;','&'))) for k,v in new.items())+'/>')
        config['native_fortunia']['recipes'][key]=new_id
    exchange=tw.leer(BASE/'exchange.xml');offset=tw.punto_insercion(exchange)
    exchange=exchange[:offset]+'\r\n'.join(additions)+'\r\n'+exchange[offset:]
    # Noryo usa Fashionable y un vale por caja de conjunto (M/F).
    # Los premios usan sus nombres IGG.
    item9=common.rows(BASE/'item9.xml')
    def noryo(match):
        attrs=tw.atributos(match[0])
        if attrs.get('群組')!='607':return match[0]
        item=item9[attrs['獎賞1']];title=item.get('原型名稱','')+item['基本名稱']
        return re.sub(r'(獎賞說明=")[^"]*"',lambda m:m[1]+traducir.escapar(title)+'"',match[0])
    exchange=tw.RE_FILA.sub(noryo,exchange)
    raw=(BASE/'msg.xml').read_bytes();text=raw.decode('utf-8-sig');known=tw.filas(text)
    assert not {str(x) for x in msg_map.values()}&known.keys()
    offset=tw.punto_insercion(text)
    text=text[:offset]+''.join('<字串 編號="%d" 文字="%s"/>\r\n'%(new,traducir.escapar(TEXTS[old]))
                             for old,new in msg_map.items())+text[offset:]
    resources={'setting\\eng\\exchange.xml':b'\xef\xbb\xbf'*tw.leer_bom(BASE/'exchange.xml')+exchange.encode('utf-8'),
               'setting\\eng\\msg.xml':b'\xef\xbb\xbf'*raw.startswith(b'\xef\xbb\xbf')+text.encode('utf-8')}
    for rel,value in resources.items():
        target=stage/pathlib.PureWindowsPath(rel);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(value)
    (stage/'tw_exchanges.json').write_text(json.dumps(config,ensure_ascii=False,indent=1),encoding='utf-8')
    shutil.copy2(common.CONFIG,backup/'tw_exchanges.json')
    state=dict(backup=str(backup),stage=str(stage),paks={},resources={k:common.digest(v) for k,v in resources.items()})
    import pak_tool
    for filename in ('update26.pak','update26.pak.bak'):
        original=tw.CLIENTE/filename;saved=backup/filename;candidate=stage/filename
        shutil.copy2(original,saved);shutil.copy2(original,candidate)
        before=common.pak_contents(saved);pak_tool.actualizar(candidate,resources);after=common.pak_contents(candidate)
        assert before.keys()==after.keys()
        assert all(after[k]==v for k,v in before.items() if k not in resources)
        state['paks'][filename]=[common.digest(saved.read_bytes()),common.digest(candidate.read_bytes())]
    STATE.write_text(json.dumps(state,indent=1),encoding='utf-8')
    print('TW Fortunia:',len(selected),'recetas,',len(groups),'grupos,',len(seen),'nodos. Respaldo:',backup)


def instalar(state_file=STATE):
    state=json.loads(state_file.read_text(encoding='utf-8'));stage=pathlib.Path(state['stage']);backup=pathlib.Path(state['backup'])
    for filename,(old,new) in state['paks'].items():
        assert common.digest((tw.CLIENTE/filename).read_bytes()) in (old,new)
        assert common.digest((stage/filename).read_bytes())==new
    for filename in state['paks']:shutil.copy2(stage/filename,tw.CLIENTE/filename)
    for rel in state['resources']:
        target=tw.IGG/'update26'/pathlib.PureWindowsPath(rel)
        shutil.copy2(target,backup/target.name);shutil.copy2(stage/pathlib.PureWindowsPath(rel),target)
    shutil.copy2(stage/'tw_exchanges.json',common.CONFIG)
    print('Instalados paquetes y menus de Fortunia:',state_file.name)


def verificar():
    config=json.loads(common.CONFIG.read_text(encoding='utf-8'))
    assert len(config['native_fortunia']['recipes'])==838
    assert len(config['native_fortunia']['groups'])==17
    assert sum(n['nombre']==NAME for n in config['npcs'])==1
    ids=set(map(int,common.rows(BASE/'exchange.xml')))
    assert ids==set(range(1,max(ids)+1)),'El cliente deja de enumerar al primer hueco'
    for filename in ('update26.pak','update26.pak.bak'):
        contents=common.pak_contents(tw.CLIENTE/filename)
        for name in ('msg.xml','exchange.xml'):
            assert contents['setting\\eng\\'+name]==(BASE/name).read_bytes(),(filename,name)
        print(filename,': mensajes y recetas coinciden con los XML del servidor; CRC correctos')


def reparar():
    config=json.loads(common.CONFIG.read_text(encoding='utf-8'))
    native=config['native_fortunia'];old_ids=set(native['recipes'].values())
    rows=common.rows(BASE/'exchange.xml');existing=set(map(int,rows))-old_ids
    first=max(existing)+1
    assert existing==set(range(1,first))
    mapping={old:first+i for i,old in enumerate(sorted(old_ids))}
    assert len(mapping)==838 and max(mapping.values())<50000
    exchange=tw.leer(BASE/'exchange.xml')
    def replace(match):
        key=int(match[2])
        if key not in mapping:return match[0]
        return re.sub(r'(編號=")\d+"',lambda m:m[1]+str(mapping[key])+'"',match[0],count=1)
    exchange=tw.RE_FILA.sub(replace,exchange)
    after=tw.filas(exchange)
    assert len(after)==len(rows) and set(map(int,after))==set(range(1,max(mapping.values())+1))
    for old,new in mapping.items():
        assert {k:v for k,v in rows[str(old)].items() if k!='編號'}=={
            k:v for k,v in tw.atributos(after[str(new)]).items() if k!='編號'}
    native['recipes']={source:mapping[old] for source,old in native['recipes'].items()}
    npc=next(n for n in config['npcs'] if n['nombre']==NAME)
    normal=next(n for n in json.loads((tw.RAIZ/'server/plantillas/lyceum.json').read_text(encoding='utf-8'))['spawns']
                if n['nombre']=='Fortunia')
    npc.update(tile=[normal['tile'][0]-4,normal['tile'][1]],
               direccion=bytes.fromhex(normal['hex'])[33],spawn_template='Fortunia')
    assert transitable.se_pisa(41,*npc['tile'])
    backup=tw.BACKUPS/('fortunia_menu_fix_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    stage=backup/'preparado';stage.mkdir(parents=True)
    shutil.copy2(common.CONFIG,backup/'tw_exchanges.json')
    (stage/'tw_exchanges.json').write_text(json.dumps(config,ensure_ascii=False,indent=1),encoding='utf-8')
    resources={'setting\\eng\\exchange.xml':b'\xef\xbb\xbf'*tw.leer_bom(BASE/'exchange.xml')+exchange.encode('utf-8')}
    for rel,raw in resources.items():
        target=stage/pathlib.PureWindowsPath(rel);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    state=dict(backup=str(backup),stage=str(stage),paks={},resources={k:common.digest(v) for k,v in resources.items()})
    import pak_tool
    for filename in ('update26.pak','update26.pak.bak'):
        original=tw.CLIENTE/filename;saved=backup/filename;candidate=stage/filename
        shutil.copy2(original,saved);shutil.copy2(original,candidate)
        before=common.pak_contents(saved);pak_tool.actualizar(candidate,resources);after=common.pak_contents(candidate)
        assert before.keys()==after.keys()
        assert all(after[k]==v for k,v in before.items() if k not in resources)
        state['paks'][filename]=[common.digest(saved.read_bytes()),common.digest(candidate.read_bytes())]
    FIX_STATE.write_text(json.dumps(state,indent=1),encoding='utf-8')
    print('Preparadas 838 recetas consecutivas:',first,'a',max(mapping.values()),'; orientacion/altura de Fortunia original.')


if __name__=='__main__':
    {'preparar':preparar,'instalar':instalar,'verificar':verificar,'reparar':reparar,
     'instalar_reparacion':lambda:instalar(FIX_STATE)}[sys.argv[1]]()
