"""Acceso directo a TODOS los canjes TW antes mezclados con Noryo."""
import datetime
import json
import pathlib
import shutil
import sys

sys.path.insert(0,str(pathlib.Path(__file__).parent))
import restaurar_canjes_tw as common
import tw_migracion as tw
import traducir
import fortunia_tw_nativo as native

STATE=tw.RAIZ/'work/fortunia_aniversario.json'
MESSAGE=994100
TITLE='TW Mall Anniversary - Coins, Keys and Lv 410 Sets'


def preparar():
    config=json.loads(common.CONFIG.read_text(encoding='utf-8'))
    group=config['group_map']['607']
    recipes=common.rows(native.BASE/'exchange.xml')
    ids=[int(k) for k,r in recipes.items() if r['群組']==str(group)]
    assert len(ids)==199
    assert {29611,29625,29627,29809}<=set(ids)
    assert str(MESSAGE) not in config['nodes']
    config['nodes'][str(MESSAGE)]={'a':[[98,[group]]]}
    config['node_owners'][str(MESSAGE)]='Fortunia'
    config['messages'][str(MESSAGE)]=TITLE
    config['nodes']['504131']['o'].insert(-1,[MESSAGE,MESSAGE])
    config['anniversary_catalog']=dict(group=group,recipe_ids=sorted(ids),message=MESSAGE,
                                     source='TW group 607 previously mixed into IGG Noryo')
    backup=tw.BACKUPS/('fortunia_aniversario_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    stage=backup/'preparado';stage.mkdir(parents=True)
    shutil.copy2(common.CONFIG,backup/'tw_exchanges.json')
    (stage/'tw_exchanges.json').write_text(json.dumps(config,ensure_ascii=False,indent=1),encoding='utf-8')
    raw=(native.BASE/'msg.xml').read_bytes();text=raw.decode('utf-8-sig')
    assert str(MESSAGE) not in tw.filas(text)
    offset=tw.punto_insercion(text)
    text=text[:offset]+'<字串 編號="%d" 文字="%s"/>\r\n'%(MESSAGE,traducir.escapar(TITLE))+text[offset:]
    resources={'setting\\eng\\msg.xml':b'\xef\xbb\xbf'*raw.startswith(b'\xef\xbb\xbf')+text.encode('utf-8')}
    state=dict(backup=str(backup),stage=str(stage),paks={},resources={k:common.digest(v) for k,v in resources.items()})
    for rel,value in resources.items():
        target=stage/pathlib.PureWindowsPath(rel);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(value)
    import pak_tool
    for filename in ('update26.pak','update26.pak.bak'):
        original=tw.CLIENTE/filename;saved=backup/filename;candidate=stage/filename
        shutil.copy2(original,saved);shutil.copy2(original,candidate)
        before=common.pak_contents(saved);pak_tool.actualizar(candidate,resources);after=common.pak_contents(candidate)
        assert before.keys()==after.keys()
        assert all(after[k]==v for k,v in before.items() if k not in resources)
        state['paks'][filename]=[common.digest(saved.read_bytes()),common.digest(candidate.read_bytes())]
    STATE.write_text(json.dumps(state,indent=1),encoding='utf-8')
    print('Preparado: Fortunia ->',TITLE,'->',len(ids),'canjes. Respaldo:',backup)


if __name__=='__main__':
    if sys.argv[1]=='preparar':preparar()
    elif sys.argv[1]=='instalar':native.instalar(STATE)
    else:raise SystemExit('Usar preparar o instalar')
