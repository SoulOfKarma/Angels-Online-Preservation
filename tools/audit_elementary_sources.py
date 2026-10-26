"""Recover native Elementary questions, prizes and map from current client."""
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'server'),str(ROOT/'tools')]
from house_services import xml_rows
from mapa_del_cliente import Mapa, _orden, mapa
from nativas_lua import Pe


def recover():
    source=max((ROOT/'extracted_paks').glob('*/map/question.mpc'),key=lambda p:_orden(p.parents[1]))
    m=Mapa(502,source)
    questions=[]
    for ident,row in xml_rows('question.xml').items():
        if row.get('\u95dc\u9589')!='Open':continue
        text=row.get('\u984c\u76ee','')
        answers=[row.get('\u7b54\u6848%d'%i,'') for i in (1,2,3)]
        if not text or not all(answers):continue
        questions.append(dict(id=ident,text=text,answers=answers,category=row.get('\u984c\u76ee\u985e\u578b','')))
    prizes=[]
    for row in xml_rows('bufprize.xml').values():
        if int(row.get('\u985e\u578b') or 0)!=2:continue
        prizes.append(dict(place=int(row['\u6392\u540d']),spell=int(row.get('\u6cd5\u8853') or 0),
            items=[[int(row['\u734e\u8cde%d'%i]),int(row.get('\u734e\u8cde%d\u6578\u91cf'%i) or 1)]
                   for i in (1,2,3) if row.get('\u734e\u8cde%d'%i)]))
    return dict(source=str(source.relative_to(ROOT)),stage=502,registration='18:45',start='19:00',
                question_seconds=10,question_count=30,tags=m.tags,
                return_tile=(mapa(41).tags.get(8) or mapa(41).tags[1])[0],
                exits=[dict(tile=o['tile'],sprite=o['id']) for o in m.objetos if o['evento']==3],
                prizes=sorted(prizes,key=lambda p:p['place']),questions=questions,
                experience_note='Quiz coefficient type2 is1 in expprize.xml; original server formula is not in the client. Local formula is documented in elementary.py.')


def pi_words(exe):
    """The public mathematical pi constants used by native Blowfish8074b0."""
    pe=Pe(Path(exe).read_bytes())
    off=next(raw+0x8cd078-pe.base-va for va,sz,raw,n in pe.secs if va<=0x8cd078-pe.base<va+n)
    words=struct.unpack_from('<1042I',pe.b,off)
    if words[:3]!=(0x243f6a88,0x85a308d3,0x13198a2e):raise ValueError('Not the native Blowfish pi table')
    return ''.join('%08x'%word for word in words)


def write_floor(source):
    """Add just502 to the floor database, preserving every existing map."""
    import importlib.util
    spec=importlib.util.spec_from_file_location('floor_exporter',ROOT/'tools/transitable.py')
    exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter)
    target=ROOT/'server/plantillas/transitable.bin'
    raw=target.read_bytes();count=struct.unpack_from('<I',raw)[0];pos=4;records=[]
    for _ in range(count):
        stage,w,h=struct.unpack_from('<HHH',raw,pos);end=pos+6+(w*h+7)//8
        if stage!=502:records.append(raw[pos:end])
        pos=end
    if pos!=len(raw):raise ValueError('Invalid existing floor database')
    w,h,bits=exporter.capa(ROOT/source)
    records.append(struct.pack('<HHH',502,w,h)+bits)
    target.write_bytes(struct.pack('<I',len(records))+b''.join(records))


if __name__=='__main__':
    result=recover()
    if '--write' in sys.argv:
        (ROOT/'server/plantillas/elementary.json').write_text(json.dumps(result,ensure_ascii=True)+'\n',encoding='utf8')
        (ROOT/'server/plantillas/blowfish_pi.hex').write_text(pi_words('G:/Angel.exe')+'\n',encoding='ascii')
        write_floor(result['source'])
        print('Recovered',len(result['questions']),'questions,',len(result['prizes']),'ranked prizes and native map exits')
    else:print(json.dumps(result,ensure_ascii=True))
