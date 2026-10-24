"""Read-only, versioned Taiwan PAK/XML evidence. No production table writes."""
import argparse
import json
import pathlib
import re
import struct
import xml.etree.ElementTree as ET
import zlib


def directory(path):
    with path.open('rb') as stream:
        stream.seek(0,2)
        size=stream.tell()
        stream.seek(-22,2)
        footer=bytearray(stream.read(22))
        if footer[:4]!=b'OD\x05\x06':return []
        for i in range(4,22):footer[i]^=(3*i-91)&255
        lo,hi,_,_,usize,offset,_=struct.unpack('<HHHHIIH',footer[4:])
        compressed=lo | hi<<16
        if offset+4+compressed>size-22:raise ValueError('Invalid PAK index bounds')
        stream.seek(offset+4)
        raw=bytearray(stream.read(compressed))
        raw[0]^=0x7a
        data=zlib.decompress(raw)
        if len(data)!=usize:raise ValueError('Invalid PAK index size')
    result=[]
    cursor=0
    while cursor+46<=len(data):
        fields=struct.unpack_from('<IHHHHHHIIIHHHHHII',data,cursor)
        crc,csize,usize=fields[7:10]
        nlen,extra,comment=fields[10:13]
        name=data[cursor+46:cursor+46+nlen].decode('big5',errors='replace').replace('\\','/').lower()
        if not name.endswith('/') and fields[-1]+csize>size:
            raise ValueError('Invalid PAK entry bounds: '+ascii((str(path),name,fields[-1],csize,size)))
        result.append((name,crc,csize,usize,fields[-1]))
        cursor+=46+nlen+extra+comment
    if cursor!=len(data):raise ValueError('Invalid PAK index tail')
    return result


def order(path):
    stem=path.stem.lower()
    if stem=='data1':return -1
    match=re.fullmatch(r'update(\d*)',stem)
    return int(match.group(1) or 0) if match else -2


def index(root):
    result={}
    for path in sorted((p for p in root.glob('*.pak') if order(p)>=-1),key=order):
        for entry in directory(path):
            if entry[0].startswith('setting/'):
                result[entry[0]]=(path,entry)
    return result


def read_bytes(source):
    path,(name,crc,csize,usize,offset)=source
    with path.open('rb') as stream:
        stream.seek(offset)
        data=zlib.decompress(stream.read(csize),-15)
    if len(data)!=usize or zlib.crc32(data)&0xffffffff!=crc:
        raise ValueError('Invalid content size/CRC: '+name)
    return data


def read(source):
    # Taiwan XML declarations specify their encoding (normally BIG5).
    return ET.fromstring(read_bytes(source))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--client',type=pathlib.Path,default=pathlib.Path('G:/ALO Taiwan/\u5929\u4f7f\u4e4b\u6200Online'))
    parser.add_argument('--tables',nargs='+',default=['msg.xml','item.xml','item2.xml','item3.xml','item4.xml','item5.xml','item6.xml','item7.xml','item8.xml','item9.xml'])
    parser.add_argument('--pattern',default='\u6230\u5929\u4f7f|\u64c2\u53f0|\u7af6\u6280\u5834')
    parser.add_argument('--ids',nargs='*',type=int,default=[])
    parser.add_argument('--limit',type=int,default=80)
    args=parser.parse_args()
    sources=index(args.client)
    count=0
    for table in args.tables:
        name='setting/big5/'+table
        if name not in sources:name='setting/'+table
        if name not in sources:continue
        source=sources[name]
        for row in read(source):
            attrs=dict(row.attrib)
            ident=attrs.get('\u7de8\u865f',attrs.get('id',''))
            text=' '.join(attrs.values())
            if (args.ids and ident.isdigit() and int(ident) in args.ids) or (not args.ids and re.search(args.pattern,text,re.I)):
                useful={k:v for k,v in attrs.items() if v not in ('','0','0.0')}
                print(json.dumps(dict(pak=source[0].name,table=table,row=useful),ensure_ascii=True))
                count+=1
                if count>=args.limit:raise SystemExit()
