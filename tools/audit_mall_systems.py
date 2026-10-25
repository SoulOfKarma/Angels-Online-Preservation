"""Read-only targeted evidence for Mall, Star Blessing and Daily Events."""
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from house_services import xml_rows
from mapa_del_cliente import _orden


def inspect():
    if '--starwire' in sys.argv:
        import struct
        raw=pathlib.Path('G:/Angel.exe').read_bytes();pe=struct.unpack_from('<I',raw,60)[0]
        sections=struct.unpack_from('<H',raw,pe+6)[0];opt=struct.unpack_from('<H',raw,pe+20)[0]
        base=struct.unpack_from('<I',raw,pe+52)[0]
        for k in range(sections):
            off=pe+24+opt+k*40
            size,rva,rsz,ptr=struct.unpack_from('<IIII',raw,off+8)
            if not struct.unpack_from('<I',raw,off+36)[0]&0x20000000:continue
            data=raw[ptr:ptr+rsz]
            for i in range(len(data)-5):
                if data[i]!=0xe8:continue
                va=base+rva+i
                if va+5+struct.unpack_from('<i',data,i+1)[0]==0x4936b0 and b'\x6a\x05' in data[max(0,i-12):i]:
                    print('STAR_MODULE_CALL',hex(va),data[max(0,i-12):i+5].hex())
        return
    items={i:r for n in range(1,10) for i,r in xml_rows('item%s.xml'%(n if n>1 else '')).items()}
    name=lambda r:r.get('\u539f\u578b\u540d\u7a31','')+r.get('\u57fa\u672c\u540d\u7a31','')
    if '--catalog' in sys.argv:
        data=json.loads((ROOT/'server/plantillas/item_mall.json').read_text('utf8'))
        from collections import Counter
        print('CATEGORIES',Counter(r['category'] for r in data['rows']))
        for cat in sorted({r['category'] for r in data['rows']}):
            rows=[(r['id'],r['item'],name(items.get(r['item'],{})),r['quantity'],r['price']) for r in data['rows'] if r['category']==cat]
            print(cat,json.dumps(rows[:10],ensure_ascii=True))
        return
    if '--daily-tree' in sys.argv:
        from propagar_dialogos_mapa import _nodo
        source=max((ROOT/'extracted_paks').glob('*/setting/eng/spmsg.xml'),key=lambda p:_orden(p.parents[2]))
        nodes={n.get('\u7de8\u865f'):_nodo(n) for n in ET.parse(source).getroot() if n.tag=='\u5c0d\u8a71'}
        todo=[504318];seen=set();messages=xml_rows('msg.xml')
        while todo:
            k=str(todo.pop(0))
            if k=='0' or k in seen:continue
            seen.add(k);r=nodes[k]
            print(k,json.dumps(r,ensure_ascii=True),json.dumps(messages.get(r.get('m'),{}),ensure_ascii=True))
            todo.extend([r['s']] if r.get('s') else [])
            todo.extend(v[1] for v in r.get('o',[]));todo.extend(v['ir'] for v in r.get('r',[]))
        return
    if '--npc' in sys.argv:
        for p in (ROOT/'extracted_paks').glob('*/setting/eng/sp*.xml'):
            if b'id="8912"' not in p.read_bytes()[:1500]:continue
            root=ET.parse(p).getroot()
            print('NPC_SOURCE',json.dumps(dict(path=str(p.relative_to(ROOT)),npc=[e.attrib for e in root if e.tag=='npc']),ensure_ascii=True))
        messages=xml_rows('msg.xml')
        for i,r in messages.items():
            if re.search('daily event|Daily Events Clerk',r.get('\u6587\u5b57',''),re.I):
                print('MESSAGE',json.dumps(r,ensure_ascii=True))
        return
    if '--summary' in sys.argv:
        from collections import Counter
        recent={i:r for i,r in items.items() if i>=70000 and r.get('\u4e0d\u53ef\u4ea4\u6613')!='\u662f' and re.search('[a-zA-Z]',name(r))}
        print('CATEGORIES',json.dumps(Counter(r.get('\u7269\u54c1\u985e\u5225') for r in recent.values()),ensure_ascii=True))
        for category in ('\u7d05\u5305','\u79ae\u7269','\u5bf5\u7269','\u5f37\u5316\u9053\u5177','\u5e78\u904b\u9ab0','\u4e00\u822c'):
            print('SAMPLE',json.dumps([dict(id=i,name=name(r)) for i,r in sorted(recent.items(),reverse=True) if r.get('\u7269\u54c1\u985e\u5225')==category][:18],ensure_ascii=True))
        return
    if '--mall' in sys.argv:
        names=('Taurus','Lucky Hammer','Attribute Lucky','Enhanced Pestle','Playful-Lizard','Dark Devil Egg')
        print('TARGETS',json.dumps({i:dict(name=name(r),category=r.get('\u7269\u54c1\u985e\u5225'),dynamic=r.get('\u52d5\u614b\u8cc7\u65991')) for i,r in items.items() if (i>=79000 or name(r)=='Dark Devil Egg') and any(s in name(r) for s in names)},ensure_ascii=True))
        latest={i:dict(name=name(r),category=r.get('\u7269\u54c1\u985e\u5225'),dynamic=r.get('\u52d5\u614b\u8cc7\u65991'),desc=r.get('\u8aaa\u660e\u5b9a\u7fa9','')) for i,r in sorted(items.items()) if i>=79000 and r.get('\u53ef\u4f7f\u7528')=='\u662f' and r.get('\u7269\u54c1\u985e\u5225') in ('\u79ae\u7269','\u7d05\u5305')}
        print('LATEST',json.dumps(latest,ensure_ascii=True))
    if '--daily' in sys.argv or '--star' in sys.argv:
        for folder in (ROOT/'extracted_paks').iterdir():
            for p in (folder/'setting/eng').glob('*.xml'):
                if re.search('daily|star',p.name,re.I):
                    root=ET.parse(p).getroot()
                    print('TABLE',json.dumps(dict(path=str(p.relative_to(ROOT)),count=len(root),sample=[dict(tag=e.tag,row=e.attrib,children=[dict(tag=c.tag,row=c.attrib) for c in list(e)[:3]]) for e in list(root)[:3]]),ensure_ascii=True))
        print('DAILY_NPCS',json.dumps({i:r for i,r in xml_rows('npc.xml').items() if 'daily' in r.get('\u540d\u7a31','').lower()},ensure_ascii=True))
    if '--pet' in sys.argv:
        print('PET_ITEM',json.dumps({i:r for i,r in items.items() if name(r)=='Dark Devil Egg'},ensure_ascii=True))
        print('PET_ROWS',json.dumps({i:r for i,r in xml_rows('pet.xml').items() if any(s in r.get('\u540d\u7a31','') for s in ('Devil','Forest'))},ensure_ascii=True))


if __name__=='__main__':inspect()
