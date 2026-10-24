"""Isolated validation for the read-only Taiwan PAK evidence reader."""
import pathlib
import random
import struct
import zlib

import pytest
from audit_arena_tw_rewards import directory,index,order,read,read_bytes


def pak(path,names=(),bad_crc=False,directory_entry=False):
    payload=b'<root><row id="1" name="arena"/></root>'
    compressed=zlib.compress(payload)[2:-4]
    entries=[]
    for name in ['setting/big5/msg.xml',*names]:
        raw=name.encode('ascii')
        entries.append(struct.pack('<IHHHHHHIIIHHHHHII',0x02014b50,
            0,0,0,8,0,0,(zlib.crc32(payload)+(1 if bad_crc else 0))&0xffffffff,
            len(compressed),len(payload),len(raw),0,0,0,0,0,0)+raw)
    if directory_entry:
        raw=b'map/unused/'
        entries.append(struct.pack('<IHHHHHHIIIHHHHHII',0x02014b50,
            0,0,0,0,0,0,0,0,0,len(raw),0,0,0,0,0,0xffffffff)+raw)
    central=b''.join(entries)
    cd=bytearray(zlib.compress(central));cd[0]^=0x7a
    offset=len(compressed)
    footer=bytearray(b'OD\x05\x06'+struct.pack('<HHHHIIH',len(cd)&65535,
        len(cd)>>16,len(entries),len(entries),len(central),offset,0))
    for i in range(4,22):footer[i]^=(3*i-91)&255
    path.write_bytes(compressed+b'OD\x01\x02'+cd+footer)
    return payload


def test_read_crc_and_directory_marker(tmp_path):
    path=tmp_path/'data1.pak'
    expected=pak(path,directory_entry=True)
    entries=directory(path)
    assert entries[-1][0]=='map/unused/'
    assert read_bytes((path,entries[0]))==expected
    assert read((path,entries[0]))[0].get('name')=='arena'


def test_large_compressed_directory_combines_high_and_low_size_words(tmp_path):
    rng=random.Random(73)
    names=['setting/'+''.join(rng.choices('abcdefghijklmnopqrstuvwxyz0123456789',k=55))+'.xml'
           for _ in range(2500)]
    path=tmp_path/'update32.pak'
    pak(path,names)
    assert len(directory(path))==2501


def test_bad_content_crc_is_rejected(tmp_path):
    path=tmp_path/'update.pak'
    pak(path,bad_crc=True)
    with pytest.raises(ValueError,match='CRC'):read_bytes((path,directory(path)[0]))


def test_numeric_last_patch_wins_without_writing_client(tmp_path):
    for name in ('update9.pak','update32.pak','update.pak','update10.pak','data1.pak'):
        pak(tmp_path/name)
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    assert index(tmp_path)['setting/big5/msg.xml'][0].name=='update32.pak'
    assert sorted(before,key=lambda name:order(pathlib.Path(name)))==[
        'data1.pak','update.pak','update9.pak','update10.pak','update32.pak']
    assert before=={p.name:p.read_bytes() for p in tmp_path.iterdir()}
