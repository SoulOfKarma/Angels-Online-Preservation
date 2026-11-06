"""Reproducir el fallo real y ejecutar la proteccion en x86 emulado."""
import json
import pathlib
import struct
import sys

import pefile
import pytest
import parchear_tooltip_hechizo_ausente as patcher

sys.path.insert(0,str(patcher.tw.RAIZ/'work/vendor'))
import unicorn as uc
from unicorn import x86_const as x

STATE=json.loads(patcher.STATE.read_text(encoding='utf-8'))
BACKUP=pathlib.Path(STATE['backup'])


def execute(data,magic):
    pe=pefile.PE(data=data);vm=uc.Uc(uc.UC_ARCH_X86,uc.UC_MODE_32)
    vm.mem_map(0x400000,patcher.align(pe.OPTIONAL_HEADER.SizeOfImage,4096))
    vm.mem_write(0x400000,pe.get_memory_mapped_image())
    vm.mem_map(0x10000000,0x20000);vm.mem_map(0x20000000,0x2000)
    esp=0x10010000;stop=0x12345678
    vm.mem_write(esp,struct.pack('<IIII',stop,0x30000000,magic,0))
    vm.reg_write(x.UC_X86_REG_ESP,esp);vm.reg_write(x.UC_X86_REG_EBP,0xFEED1234)
    invalid=[]
    def fault(vm,kind,address,size,value,opaque):invalid.append(address);return False
    vm.hook_add(uc.UC_HOOK_MEM_READ_UNMAPPED|uc.UC_HOOK_MEM_WRITE_UNMAPPED,fault)
    error=None
    try:vm.emu_start(patcher.HOOK,stop,timeout=1_000_000,count=10000)
    except uc.UcError as exc:error=exc
    return vm,error,invalid


def test_original_client_reproduces_null_magic_crash():
    _,error,invalid=execute((BACKUP/'angel_antes.dat').read_bytes(),0)
    assert error is not None and invalid==[0x10]


def test_patched_client_returns_false_without_dereferencing_missing_magic():
    vm,error,invalid=execute((BACKUP/'angel_corregido.dat').read_bytes(),0)
    assert error is None and invalid==[]
    assert vm.reg_read(x.UC_X86_REG_EAX)==0
    assert vm.reg_read(x.UC_X86_REG_ESP)==0x10010010
    assert vm.reg_read(x.UC_X86_REG_EBP)==0xFEED1234


def test_valid_magic_keeps_original_native_behavior():
    original=(BACKUP/'angel_antes.dat').read_bytes();patched=(BACKUP/'angel_corregido.dat').read_bytes()
    left,e1,f1=execute(original,0x20000000);right,e2,f2=execute(patched,0x20000000)
    assert e1 is None and e2 is None and f1==f2==[]
    for register in (x.UC_X86_REG_EAX,x.UC_X86_REG_EBX,x.UC_X86_REG_ESI,x.UC_X86_REG_EDI,
                     x.UC_X86_REG_ESP,x.UC_X86_REG_EBP):
        assert left.reg_read(register)==right.reg_read(register)


def test_patch_preserves_every_existing_section_except_entry_guard():
    old=(BACKUP/'angel_antes.dat').read_bytes();new=(BACKUP/'angel_corregido.dat').read_bytes()
    pe=pefile.PE(data=old);offset=pe.get_offset_from_rva(patcher.HOOK-0x400000)
    for section in pe.sections:
        a,b=section.PointerToRawData,section.PointerToRawData+section.SizeOfRawData
        expected=bytearray(old[a:b])
        if a<=offset<b:expected[offset-a:offset-a+9]=new[offset:offset+9]
        assert new[a:b]==expected
    assert patcher.patch(new)[0]==new
