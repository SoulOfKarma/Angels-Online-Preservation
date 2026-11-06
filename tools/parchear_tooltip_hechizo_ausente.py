"""Evitar el acceso NULL de 63C1D0 al mostrar un hechizo permanente ausente.

641360 pasa GetMagic(item+236) sin comprobarlo; 63C1D0 lee magic+16.
El parche retorna false si magic == NULL; con datos validos ejecuta el
prologo original y sigue sin cambios. No modifica objetos ni hechizos.
"""
import datetime
import hashlib
import json
import pathlib
import struct
import sys

sys.path.insert(0,str(pathlib.Path(__file__).parent))
import pefile
import tw_migracion as tw

HOOK=0x63C1D0
ORIGINAL=bytes.fromhex('558bec81ec740a0000')
STATE=tw.RAIZ/'work/tooltip_enma_patch.json'
TARGET=tw.CLIENTE/'angel.dat'


def sha(data):return hashlib.sha256(data).hexdigest()


def align(value,boundary):return (value+boundary-1)//boundary*boundary


def patch(data):
    pe=pefile.PE(data=data);base=pe.OPTIONAL_HEADER.ImageBase
    assert base==0x400000 and not pe.OPTIONAL_HEADER.DllCharacteristics & 0x40
    offset=pe.get_offset_from_rva(HOOK-base)
    existing=next((s for s in pe.sections if s.Name.rstrip(b'\0')==b'.twfix'),None)
    if existing:
        cave=base+existing.VirtualAddress
        assert data[offset:offset+5]==b'\xe9'+struct.pack('<i',cave-HOOK-5)
        return data,cave
    assert data[offset:offset+len(ORIGINAL)]==ORIGINAL,'El ejecutable no coincide con el medido'
    header=pe.sections[-1].get_file_offset()+40
    assert header+40<=pe.OPTIONAL_HEADER.SizeOfHeaders
    assert not any(data[header:header+40]),'No hay espacio libre para el encabezado de seccion'
    va=align(max(s.VirtualAddress+max(s.Misc_VirtualSize,s.SizeOfRawData) for s in pe.sections),
             pe.OPTIONAL_HEADER.SectionAlignment)
    cave=base+va
    # [esp+8] es el segundo argumento. El callee es stdcall de tres argumentos.
    code=bytes.fromhex('837c240800750531c0c20c00')+ORIGINAL
    code+=b'\xe9'+struct.pack('<i',(HOOK+len(ORIGINAL))-(cave+len(code)+5))
    raw=align(len(data),pe.OPTIONAL_HEADER.FileAlignment)
    raw_size=align(len(code),pe.OPTIONAL_HEADER.FileAlignment)
    result=bytearray(data)
    result.extend(bytes(raw-len(result))+code+bytes(raw_size-len(code)))
    result[header:header+40]=struct.pack('<8sIIIIIIHHI',b'.twfix\0\0',len(code),va,raw_size,raw,0,0,0,0,0x60000020)
    struct.pack_into('<H',result,pe.FILE_HEADER.get_field_absolute_offset('NumberOfSections'),pe.FILE_HEADER.NumberOfSections+1)
    struct.pack_into('<I',result,pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfImage'),align(va+len(code),pe.OPTIONAL_HEADER.SectionAlignment))
    struct.pack_into('<I',result,pe.OPTIONAL_HEADER.get_field_absolute_offset('SizeOfCode'),pe.OPTIONAL_HEADER.SizeOfCode+raw_size)
    struct.pack_into('<I',result,pe.OPTIONAL_HEADER.get_field_absolute_offset('CheckSum'),0)
    result[offset:offset+len(ORIGINAL)]=b'\xe9'+struct.pack('<i',cave-HOOK-5)+bytes.fromhex('90909090')
    changed=pefile.PE(data=bytes(result))
    assert changed.get_data(cave-base,len(code))==code
    assert changed.OPTIONAL_HEADER.AddressOfEntryPoint==pe.OPTIONAL_HEADER.AddressOfEntryPoint
    return bytes(result),cave


def preparar():
    backup=tw.BACKUPS/('tooltip_enma_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    backup.mkdir(parents=True)
    old=TARGET.read_bytes();new,cave=patch(old)
    (backup/'angel_antes.dat').write_bytes(old)
    (backup/'angel_corregido.dat').write_bytes(new)
    state=dict(backup=str(backup),target=str(TARGET),original=sha(old),patched=sha(new),hook=HOOK,cave=cave)
    STATE.write_text(json.dumps(state,indent=1),encoding='utf-8')
    print('Parche preparado:',backup,'proteccion en',hex(cave))


def instalar():
    state=json.loads(STATE.read_text(encoding='utf-8'))
    new=(pathlib.Path(state['backup'])/'angel_corregido.dat').read_bytes()
    assert sha(new)==state['patched']
    assert sha(TARGET.read_bytes()) in (state['original'],state['patched'])
    TARGET.write_bytes(new)
    assert sha(TARGET.read_bytes())==state['patched']
    print('Instalado: tooltip ignora el hechizo ausente y mantiene los validos.')


if __name__=='__main__':{'preparar':preparar,'instalar':instalar}[sys.argv[1]]()
