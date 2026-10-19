"""Lee registros Lua y paquetes de granja del ejecutable local con pefile/capstone."""
import struct
import pefile
import capstone


def main():
    pe = pefile.PE(r'G:\REA\binarios\play_angel_unpacked.exe')
    raw = bytes(pe.__data__)
    base = pe.OPTIONAL_HEADER.ImageBase
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    names = ('enterfarmmap', 'farmwater', 'farmfertilize', 'farmharvest', 'farmplant')
    for name in names:
        pos = raw.find(name.encode() + b'\0')
        if pos < 0:
            continue
        va = base + pe.get_rva_from_offset(pos)
        pointer = struct.pack('<I', va)
        at = raw.find(pointer)
        if at < 0:
            continue
        fn = struct.unpack_from('<I', raw, at + 4)[0]
        print(name, hex(fn))
        for instruction in md.disasm(pe.get_data(fn - base, 512), fn):
            print(' ', hex(instruction.address), instruction.mnemonic, instruction.op_str)
            if instruction.mnemonic == 'ret':
                break


if __name__ == '__main__':
    main()
