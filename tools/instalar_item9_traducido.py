"""Instalar traducciones completas de item9 y contenido de los dos cambiadores.

Solo cambia texto visible. No modifica tipos, estadisticas, drops ni cuentas.
Mantiene descripciones planas; el fallo por hechizos ausentes se corrige
en parchear_tooltip_hechizo_ausente.py, no mediante la traduccion.
"""
import datetime
import hashlib
import html
import json
import pathlib
import re
import shutil
import sqlite3
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0,str(pathlib.Path(__file__).parent))
import tw_migracion as tw
import traducir
import traducir_item9_pendientes as source
import restaurar_canjes_tw as restore

BASE=tw.IGG/'update26/setting/eng'
STATE=tw.RAIZ/'work/item9_instalacion.json'
UNSAFE=re.compile(r'%(?:[-+0-9.*]*)(?:[hlL]*)(?:s|d|n|f|p)(?![A-Za-z])')
REVIEWED={
82770:'Iron ore imbued with the power of the Ninja God. Use to obtain a random Lv 450 Shadow Blade weapon.',
82771:"When taking physical or spell damage, has a chance to reduce the attacker's physical and spell damage. Equipping multiple copies does not stack the effect or increase its trigger chance.",
82772:'When using a stance or spell while wielding a sword, has a chance to restore 5000 HP.',
82773:'When using a stance or spell while wielding an axe or hammer, has a chance to deal 5000 additional damage.',
82774:'When using a stance or spell while wielding a spear, has a chance to increase Attack by 4220, Defense by 2360 and Magic Defense by 1210 for 5 seconds.',
82775:'When using a stance or spell while wielding a bow, has a chance to inflict damage over time for 15 seconds.',
82776:'When using a stance or spell while wielding a staff, has a chance to restore 3600 MP and increase Spell Attack by 1210 for 5 seconds.',
82777:'When using a stance or spell while wielding a Shadow Blade, has a chance to increase Attack by 4220, Evasion by 120 and Movement Speed by 20% for 5 seconds.',
}


def sha(data):return hashlib.sha256(data).hexdigest()


def preparar():
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=tw.BACKUPS/('item9_completo_'+stamp);stage=backup/'preparado';stage.mkdir(parents=True)
    trad=traducir.Traductor();selected=source.targets();by_file={};names={};changed=0;sanitized=[]
    for item,(filename,row) in selected.items():by_file.setdefault(filename,set()).add(str(item))
    resources={};changes={};pending=[]
    for filename,ids in by_file.items():
        path=BASE/filename;original=path.read_bytes();text=original.decode('utf-8-sig')
        updates={}
        def translate(match):
            nonlocal changed
            item=match.group(2)
            if item not in ids:return match[0]
            old=tw.atributos(match[0]);new=dict(old)
            for key,value in old.items():
                if not tw.es_texto(key):continue
                result,complete=trad.traducir(value)
                if key=='說明定義' and int(item) in REVIEWED:
                    result=traducir.escapar(REVIEWED[int(item)]);complete=True
                result=traducir.escapar(source.ascii_text(html.unescape(result)))
                # Mantener la normalizacion previa a descripciones planas.
                # %s tiene un expansor nativo: no era la causa del acceso NULL.
                result=re.sub(r'/c\$\d+%s/c\*','',result)
                if UNSAFE.search(result):
                    result=UNSAFE.sub('the contents',result)
                if not complete or tw.RE_CJK.search(result):pending.append((item,key,value))
                if result!=value:
                    if UNSAFE.search(value):sanitized.append(int(item))
                    new[key]=result;changed+=1
            names[int(item)]=html.unescape(new.get('原型名稱','')+new.get('基本名稱',''))
            if new==old:return match[0]
            updates[item]={k:html.unescape(v) for k,v in new.items() if tw.es_texto(k) and old.get(k)!=v}
            return tw.RE_ATTR.sub(lambda m:' %s="%s"'%(m[1],new[m[1]]),match[0])
        text=tw.RE_FILA.sub(translate,text)
        if updates:
            raw=b'\xef\xbb\xbf'*original.startswith(b'\xef\xbb\xbf')+text.encode('utf-8')
            ET.fromstring(raw)
            before,after=tw.filas(original.decode('utf-8-sig')),tw.filas(text)
            assert before.keys()==after.keys()
            for item,row in after.items():
                old,new=tw.atributos(before[item]),tw.atributos(row)
                assert {k:v for k,v in old.items() if not tw.es_texto(k)}=={k:v for k,v in new.items() if not tw.es_texto(k)}
                if item not in ids:assert row==before[item]
            resources['setting\\eng\\'+filename]=raw;changes[filename[:-4]]=updates
    if pending:
        (backup/'pendientes.json').write_text(json.dumps(pending,ensure_ascii=False,indent=1),encoding='utf-8')
        raise AssertionError(('quedan textos sin traducir',len(pending),pending[:5]))
    path=BASE/'exchange.xml';original=path.read_bytes()
    groups=set(json.loads(restore.CONFIG.read_text(encoding='utf-8'))['exchange_owners'])
    exchanges=0
    def exchange(match):
        nonlocal exchanges
        row=tw.atributos(match[0]);item=int(row.get('獎賞1') or 0)
        if row.get('群組') not in groups or item not in names:return match[0]
        value=traducir.escapar(names[item])
        if tw.RE_CJK.search(value):raise AssertionError((item,value))
        exchanges+=1
        return re.sub(r'(獎賞說明=")[^"]*"',lambda m:m[1]+value+'"',match[0])
    text=tw.RE_FILA.sub(exchange,original.decode('utf-8-sig'))
    resources['setting\\eng\\exchange.xml']=b'\xef\xbb\xbf'*original.startswith(b'\xef\xbb\xbf')+text.encode('utf-8')
    for rel,raw in resources.items():
        dest=stage/pathlib.PureWindowsPath(rel);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    db=tw.RAIZ/'corpus/content.db'
    with sqlite3.connect(db) as con, sqlite3.connect(backup/'content.db') as saved:con.backup(saved)
    report=dict(backup=str(backup),stage=str(stage),paks={},resources={rel:sha(raw) for rel,raw in resources.items()},
                tables=changes,items=sorted(selected),sanitized=sorted(set(sanitized)))
    for filename in ('update26.pak','update26.pak.bak'):
        path=tw.CLIENTE/filename;saved=backup/filename;dest=stage/filename
        shutil.copy2(path,saved);shutil.copy2(path,dest)
        before=restore.pak_contents(saved)
        import pak_tool
        pak_tool.actualizar(dest,resources);after=restore.pak_contents(dest)
        assert after.keys()==before.keys()|resources.keys()
        assert all(after[k]==v for k,v in before.items() if k not in resources)
        assert all(after[k]==v for k,v in resources.items())
        report['paks'][filename]=[sha(saved.read_bytes()),sha(dest.read_bytes())]
    STATE.write_text(json.dumps(report,ensure_ascii=False,indent=1),encoding='utf-8')
    print('Preparados',changed,'campos;',len(selected),'objetos revisados;',exchanges,'rotulos de canje;',len(set(sanitized)),'tooltips saneados. Respaldo:',backup)


def instalar():
    report=json.loads(STATE.read_text(encoding='utf-8'));stage=pathlib.Path(report['stage']);backup=pathlib.Path(report['backup'])
    for filename,(old,new) in report['paks'].items():
        assert sha((tw.CLIENTE/filename).read_bytes()) in (old,new),filename
        assert sha((stage/filename).read_bytes())==new
    for filename in report['paks']:shutil.copy2(stage/filename,tw.CLIENTE/filename)
    for rel in report['resources']:
        target=tw.IGG/'update26'/pathlib.PureWindowsPath(rel)
        if not (backup/target.name).exists():shutil.copy2(target,backup/target.name)
        shutil.copy2(stage/pathlib.PureWindowsPath(rel),target)
    with sqlite3.connect(tw.RAIZ/'corpus/content.db') as con:
        for table,entries in report['tables'].items():
            columns={r[1] for r in con.execute('PRAGMA table_info("%s")'%table)}
            for item,fields in entries.items():
                fields={k:v for k,v in fields.items() if k in columns}
                if fields:
                    con.execute('UPDATE "%s" SET %s WHERE id=?'%(table,','.join('"%s"=?'%k for k in fields)),[*fields.values(),item])
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    print('Instalados PAK, XML y textos de contenido; cuentas sin modificar.')


def verificar():
    report=json.loads(STATE.read_text(encoding='utf-8'))
    for filename in report['paks']:
        data=restore.pak_contents(tw.CLIENTE/filename)
        assert all(sha(data[k])==v for k,v in report['resources'].items())
        print(filename,'CRC y textos verificados')


if __name__=='__main__':{'preparar':preparar,'instalar':instalar,'verificar':verificar}[sys.argv[1]]()
