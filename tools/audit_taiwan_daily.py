"""Read-only search of Taiwan PAK directories; never mix their item IDs."""
import json
import pathlib
import re
import sys
import zlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
from paks_cliente import _directorio,numero


def inspect():
    folder=pathlib.Path('G:/ALO Taiwan/\u5929\u4f7f\u4e4b\u6200Online')
    names={};targets={}
    for path in sorted(folder.glob('*.pak'),key=lambda p:numero(p.name)):
        if numero(path.name)<-1:continue
        data=path.read_bytes()
        for name,crc,csize,usize,off in _directorio(data):
            low=name.lower()
            if low.startswith('setting\\') and re.search('daily|star|mall|event',low):names[low]=path.name
            if low.startswith('setting\\') and re.search(r'(daily[^\\]*|star_client|mall)\.xml$',low):
                try:targets[low]=zlib.decompress(data[off:off+csize],-15)
                except zlib.error:pass
    out=ROOT/'scratch/daily_evidence';out.mkdir(parents=True,exist_ok=True)
    for name,raw in targets.items():(out/('tw_'+name.replace('\\','_'))).write_bytes(raw)
    print(json.dumps(names,ensure_ascii=True))
    print('Saved targeted evidence files:',len(targets))


if __name__=='__main__':inspect()
