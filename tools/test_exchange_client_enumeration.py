"""Ejecutar el bucle de la ventana IGG: termina en el primer GetExchange NULL."""
import collections
import json
import pathlib
import struct
import sys

import pefile
import restaurar_canjes_tw as build
import tw_migracion as tw
sys.path.insert(0,str(tw.RAIZ/'work/vendor'))
import unicorn as uc
from unicorn import x86_const as x

CONFIG=json.loads(build.CONFIG.read_text(encoding='utf-8'))


def native_selection(rows,group):
    """Codigo real 6704D6..670543, con GetExchange y map.insert sustituidos."""
    data=(tw.CLIENTE/'angel.dat').read_bytes();pe=pefile.PE(data=data)
    vm=uc.Uc(uc.UC_ARCH_X86,uc.UC_MODE_32)
    size=(pe.OPTIONAL_HEADER.SizeOfImage+4095)//4096*4096
    vm.mem_map(0x400000,size);vm.mem_write(0x400000,pe.get_memory_mapped_image())
    vm.mem_map(0x20000000,0x40000)
    blob=bytearray((max(map(int,rows))+1)*80)
    for key,row in rows.items():
        offset=int(key)*80
        struct.pack_into('<I',blob,offset+4,int(row['群組']))
        struct.pack_into('<I',blob,offset+76,int(row.get('排序') or 0))
    vm.mem_map(0x30000000,(len(blob)+4095)//4096*4096);vm.mem_write(0x30000000,bytes(blob))
    ebp=0x20010000
    def write(address,value):vm.mem_write(address,struct.pack('<I',value))
    def read(address):return struct.unpack('<I',vm.mem_read(address,4))[0]
    write(ebp-0x24,1);write(ebp-0x28,10000);write(ebp-0x2c,0x30000050)
    write(ebp-0x78c,0x20020000);write(0x20020000+0x151e4,group)
    vm.reg_write(x.UC_X86_REG_EBP,ebp);vm.reg_write(x.UC_X86_REG_ESP,0x20008000)
    selected=[]
    def insert(vm,address,size,opaque):
        selected.append(read(ebp-0x24))
        vm.reg_write(x.UC_X86_REG_EAX,0x20038000)
        vm.reg_write(x.UC_X86_REG_ESP,vm.reg_read(x.UC_X86_REG_ESP)+4)
        vm.reg_write(x.UC_X86_REG_EIP,address+5)
    def get(vm,address,size,opaque):
        key=read(vm.reg_read(x.UC_X86_REG_ESP))
        vm.reg_write(x.UC_X86_REG_EAX,0x30000000+key*80 if str(key) in rows else 0)
        vm.reg_write(x.UC_X86_REG_EIP,address+5)
    for address in (0x670503,0x670516):vm.hook_add(uc.UC_HOOK_CODE,insert,begin=address,end=address)
    vm.hook_add(uc.UC_HOOK_CODE,get,begin=0x670536,end=0x670536)
    vm.emu_start(0x6704d6,0x670543,timeout=10_000_000,count=2_000_000)
    assert vm.reg_read(x.UC_X86_REG_EIP)==0x670543
    return selected


def test_native_window_before_fix_has_no_45_star_rows_and_after_fix_has_all_60():
    state=json.loads((tw.RAIZ/'work/fortunia_tw_menu_fix.json').read_text(encoding='utf-8'))
    before=build.pak_contents(pathlib.Path(state['backup'])/'update26.pak')['setting\\eng\\exchange.xml']
    before={k:tw.atributos(v) for k,v in tw.filas(before.decode('utf-8-sig')).items()}
    after=build.rows(tw.IGG/'update26/setting/eng/exchange.xml')
    group=CONFIG['native_fortunia']['groups']['630']
    assert native_selection(before,group)==[]
    visible=native_selection(after,group)
    assert set(visible)=={int(k) for k,r in after.items() if r['群組']==str(group)}
    assert len(visible)==60


def test_both_installed_packages_reach_every_recipe_of_all_17_menus():
    groups=set(CONFIG['native_fortunia']['groups'].values())
    for filename in ('update26.pak','update26.pak.bak'):
        raw=build.pak_contents(tw.CLIENTE/filename)['setting\\eng\\exchange.xml']
        rows={int(k):tw.atributos(v) for k,v in tw.filas(raw.decode('utf-8-sig')).items()}
        reached={};key=1
        while key in rows:reached[key]=rows[key];key+=1
        assert len(reached)==len(rows)
        counts=collections.Counter(int(r['群組']) for r in reached.values())
        assert all(counts[group]>0 for group in groups)
        assert sum(counts[group] for group in groups)==838
