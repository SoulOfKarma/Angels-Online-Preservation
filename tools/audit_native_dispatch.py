"""Disassemble only protocol-registration code; no account or heap memory."""
import pathlib
import struct
import sys
import capstone


def inspect(path='G:/Angel.exe'):
    raw=pathlib.Path(path).read_bytes();pe=struct.unpack_from('<I',raw,60)[0]
    start=pe+24+struct.unpack_from('<H',raw,pe+20)[0]
    base=struct.unpack_from('<I',raw,pe+52)[0]
    sections=[struct.unpack_from('<IIII',raw,start+k*40+8) for k in range(struct.unpack_from('<H',raw,pe+6)[0])]
    def offset(va):return next(ptr+va-base-rva for size,rva,n,ptr in sections if rva<=va-base<rva+n)
    md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
    if '--calls' in sys.argv:
        target=int(sys.argv[-1],16)
        for sz,rva,n,ptr in sections:
            for i in range(ptr,ptr+n-5):
                if raw[i]!=0xe8:continue
                va=base+rva+i-ptr
                if va+5+struct.unpack_from('<i',raw,i+1)[0]==target:print('CALL',hex(va))
        return
    if '--refs' in sys.argv:
        va=int(sys.argv[-1],16);needle=struct.pack('<I',va);off=0
        while True:
            off=raw.find(needle,off)
            if off<0:break
            refva=next((base+r+off-d for sz,r,n,d in sections if d<=off<d+n),off)
            print(hex(refva),raw[max(0,off-8):off+12].hex());off+=4
        return
    if '--lua' in sys.argv:
        labels=sys.argv[sys.argv.index('--lua')+1:] or ('getStarPower','showTempSlot','showMainStarCard')
        for label in labels:
            i=raw.find(label.encode()+b'\0')
            if i<0:print('No native label',label);continue
            sva=next(base+rva+i-ptr for sz,rva,n,ptr in sections if ptr<=i<ptr+n)
            ref=raw.find(struct.pack('<I',sva));fn=struct.unpack_from('<I',raw,ref+4)[0]
            print(label,hex(fn))
            for ins in md.disasm(raw[offset(fn):offset(fn)+180],fn):print(hex(ins.address),ins.mnemonic,ins.op_str)
        return
    if '--strings' in sys.argv:
        for value in sys.argv[sys.argv.index('--strings')+1:]:
            va=int(value,16);o=offset(va);print(value,repr(raw[o:raw.index(b'\0',o)]))
        return
    end=sys.argv.index('--size') if '--size' in sys.argv else len(sys.argv)
    size=int(sys.argv[end+1],0) if end<len(sys.argv) else 1200
    regions=[(int(v,16),size) for v in sys.argv[2:end] if not v.startswith('--')] if len(sys.argv)>2 else [(v,155) for v in (0x5e8fe6,0x5e8662,0x5e7978)]
    for va,size in regions:
        off=offset(va)
        if '--focus' in sys.argv:
            ins=list(md.disasm(raw[off:off+4000],va))
            hits={j for i,x in enumerate(ins) if '0xf8' in x.op_str for j in range(max(0,i-12),min(len(ins),i+20))}
            for j in sorted(hits):print(hex(ins[j].address),ins[j].mnemonic,ins[j].op_str)
        else:
            for i in md.disasm(raw[off:off+size],va):print(hex(i.address),i.mnemonic,i.op_str)


def compare_live(pid):
    """Read only three executable-code ranges, never player/account memory."""
    import ctypes as c
    k=c.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[c.c_uint32,c.c_int,c.c_uint32];k.OpenProcess.restype=c.c_void_p
    k.ReadProcessMemory.argtypes=[c.c_void_p,c.c_void_p,c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)]
    k.CloseHandle.argtypes=[c.c_void_p]
    h=k.OpenProcess(0x10|0x400,False,int(pid))
    if not h:raise OSError(c.get_last_error())
    try:
        md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
        for va in (0x5e8fe6,0x5e8662,0x6248a0):
            buf=c.create_string_buffer(120);got=c.c_size_t()
            if not k.ReadProcessMemory(h,va,buf,120,c.byref(got)):raise OSError(c.get_last_error())
            print('LIVE CODE',hex(va),buf.raw[:12].hex())
            for i in md.disasm(buf.raw[:got.value],va):print(hex(i.address),i.mnemonic,i.op_str)
    finally:k.CloseHandle(h)


if __name__=='__main__':
    if '--live' in sys.argv:compare_live(sys.argv[-1])
    else:inspect(sys.argv[1] if len(sys.argv)>1 else 'G:/Angel.exe')
