"""Completar item9 con cache, marcadores protegidos y vocabulario IGG."""
import concurrent.futures
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

sys.path.insert(0,str(pathlib.Path(__file__).parent))
import traducir
import tw_migracion as tw

TARGET=tw.RAIZ/'work/traduccion/manual/item9_completo_mt.json'
WIDE=tw.RE_CJK
TOKEN=re.compile(r'/c\$#|/c\*|%#|%[sdif]|%%|\\[nrt]|&#\w+;|#')


def protect(source):
    tokens={};number=[0]
    def sub(m):
        value=m[0]
        if '#' in value:
            value=value.replace('#','{%d}'%number[0]);number[0]+=1
        key='ZXQN%dQXZ'%len(tokens)
        tokens[key]=value
        return key
    return TOKEN.sub(sub,source),tokens


def ascii_text(text):
    text=unicodedata.normalize('NFKC',text)
    for old,new in {'’':"'",'‘':"'",'“':'"','”':'"','–':'-','—':'-',
                    '…':'...','※':'Note: ','　':' ','・':' / ','☆':'*','♪':'',
                    'Χ':'X','×':'x','–':'-','’':"'",'『':'"','』':'"'}.items():text=text.replace(old,new)
    text=re.sub('[\u200b-\u200d\ufeff]','',text)
    return text


def polish(source,value):
    value=ascii_text(value)
    for match in re.finditer(r'(?<!\$)#(時間|分間|秒間|日間)',source):
        index=source[:match.start()].count('#')
        placeholder='{%d}'%index
        unit={'時間':'hours','分間':'minutes','秒間':'seconds','日間':'days'}[match[1]]
        value=re.sub(re.escape(placeholder)+r'\s+time\b',placeholder+' '+unit,value)
        if not re.search(re.escape(placeholder)+r'\s+'+unit[:-1],value,re.I):
            value=value.replace(placeholder,placeholder+' '+unit)
    if '穴あけ' in source or '打孔' in source:
        for old,new in (('Drilling hammer','Piercing Hammer'),('drilling hammer','Piercing Hammer'),
                        ('open holes (slots)','add sockets'),('drilling stage','socket level')):
            value=value.replace(old,new)
    value=value.replace('own status will increase','your attributes are increased')
    value=value.replace('The support effect will remain even if you are unable to fight.',
                        'The effect persists after death.')
    value=value.replace('Does not overlap with some support effects.',
                        'Does not stack with certain other buffs.')
    assert set(map(int,re.findall(r'\{(\d+)\}',value)))==set(range(source.count('#'))),(source,value)
    return value


def translate_batch(entries):
    prepared={i:protect(s) for i,s in entries}
    query='\n'.join('ZXQT%dQXZ %s'%(i,prepared[i][0]) for i,_ in entries)
    endpoint='https://translate.googleapis.com/translate_a/single?'
    params=urllib.parse.urlencode(dict(client='gtx',sl='auto',tl='en',dt='t',q=query))
    error=None
    for attempt in range(4):
        try:
            req=urllib.request.Request(endpoint+params,headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req,timeout=30) as response:raw=json.load(response)
            result=re.sub('[\u200b-\u200d\ufeff]','',''.join(part[0] or '' for part in raw[0]))
            markers=list(re.finditer(r'ZXQT\s*(\d+)\s*QXZ\s*',result,re.I))
            assert {int(m[1]) for m in markers}==set(prepared),('batch markers',result[:200])
            translated={}
            for j,m in enumerate(markers):
                i=int(m[1]);value=result[m.end():markers[j+1].start() if j+1<len(markers) else len(result)].strip()
                for token,original in prepared[i][1].items():
                    pattern='\\s*'.join(map(re.escape,re.findall('[A-Z]+|[0-9]+',token)))
                    value,count=re.subn(pattern,lambda _:original,value,flags=re.I)
                    assert count==1,('lost marker',entries,value,token)
                value=ascii_text(value)
                assert value and not WIDE.search(value) and 'ZXQ' not in value,('untranslated',entries,value)
                translated[i]=value
            return translated
        except Exception as exc:
            error=exc
            time.sleep(min(4,attempt+1))
    if len(entries)>1:
        out={}
        for entry in entries:out.update(translate_batch([entry]))
        return out
    raise RuntimeError((entries,error))


def targets():
    base=tw.IGG/'update26/setting/eng'
    items={};selected=set()
    for path in sorted(base.glob('item*.xml')):
        if not re.fullmatch(r'item[2-9]?\.xml',path.name):continue
        for key,row in tw.filas(tw.leer(path)).items():
            items[int(key)]=(path.name,row)
            if path.name=='item9.xml':selected.add(int(key))
    config=tw.RAIZ/'server/plantillas/tw_exchanges.json'
    if config.exists():
        groups=set(json.loads(config.read_text(encoding='utf-8'))['exchange_owners'])
        for row in tw.filas(tw.leer(base/'exchange.xml')).values():
            attrs=tw.atributos(row)
            if attrs.get('群組') not in groups:continue
            selected.update(int(value) for key,value in attrs.items()
                            if re.fullmatch(r'(材料|獎賞)\d+',key) and value!='0')
    drops={}
    for name in ('drop.xml','serv_drop.xml'):
        path=base/name
        if path.exists():
            for key,row in tw.filas(tw.leer(path)).items():drops.setdefault(key,tw.atributos(row))
    pending=list(selected);seen=set()
    while pending:
        item=pending.pop()
        if item in seen or item not in items:continue
        seen.add(item);attrs=tw.atributos(items[item][1])
        if attrs.get('物品類別') not in ('紅包','禮物'):continue
        row=drops.get(attrs.get('動態資料1','').strip(),{})
        for key,value in row.items():
            if re.fullmatch('item\\d+',key) and value and value!='0':
                value=int(value)
                if value not in selected:selected.add(value);pending.append(value)
    return {i:items[i] for i in selected if i in items}


def main():
    trad=traducir.Traductor();pending={}
    for _,row in targets().values():
        for key,value in tw.atributos(row).items():
            if tw.es_texto(key) and WIDE.search(value):
                for segment in trad.segmentos_pendientes(value):pending[segment]=None
    existing=json.loads(TARGET.read_text(encoding='utf-8')) if TARGET.exists() else {}
    existing={key:polish(key,value) for key,value in existing.items()}
    todo=[(i,s) for i,s in enumerate(pending) if s not in existing]
    batches=[]
    for japanese in (False,True):
        current=[];size=0
        for entry in todo:
            if bool(re.search(r'[\u3040-\u30ff]',entry[1]))!=japanese:continue
            cost=len(urllib.parse.quote(entry[1]))+80
            if current and size+cost>5300:batches.append(current);current=[];size=0
            current.append(entry);size+=cost
        if current:batches.append(current)
    print('Pendientes',len(todo),'segmentos en',len(batches),'lotes',flush=True)
    source_by_id=dict(todo)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(translate_batch,batch):batch for batch in batches}
        for count,future in enumerate(concurrent.futures.as_completed(futures),1):
            try:
                for i,value in future.result().items():existing[source_by_id[i]]=polish(source_by_id[i],value)
            except Exception as exc:
                print('LOTE PENDIENTE',str(exc)[:500],flush=True)
            TARGET.write_text(json.dumps(existing,ensure_ascii=False,indent=1),encoding='utf-8')
            print('Lotes',count,'/',len(batches),'guardados',len(existing),flush=True)


if __name__=='__main__':main()
