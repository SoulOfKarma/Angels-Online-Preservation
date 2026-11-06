"""Hace que el angel.dat IGG monte tambien update32.pak.

MEDIDO CON REA (Ghidra 12.1, angel.dat desempaquetado con UPX, sha256
7c1f8cc1...): WinMain (0x533FD0) llama sub_74BBD0(nombre, 0) una vez por pak,
de data1.pak a update31.pak, y despues CoInitialize:

    0x5341f5  6a 00              push 0
    0x5341f7  68 b8708b00        push "update31.pak"
    0x5341fc  e8 cf792100        call 0x74BBD0
    0x534201  83 c4 08           add esp, 8
    0x534204  6a 00              push 0
    0x534206  ff 15 bc348b00     call [CoInitialize]
    0x53420c  ...

El parche cambia los 11 bytes de 0x534201 por un jmp a un hueco de .text
(0x8b29e0, ceros hasta el final de la seccion) que hace lo mismo y ademas
carga "update32.pak" (escrita en el relleno de ceros del final de .rdata,
0x9125e0), y vuelve a 0x53420c. Base fija 0x400000: el ejecutable no trae
.reloc ni DYNAMIC_BASE, asi que las direcciones absolutas valen.

El resultado es el ejecutable SIN empaquetar (UPX no hace falta para correr).

    python -I tools/parchear_angel_update32.py <angel_unpacked.exe> <salida>
"""
import struct
import sys

BASE = 0x400000
HOOK, VUELTA = 0x534201, 0x53420C
CUEVA, CADENA = 0x8B29E0, 0x9125E0
CARGAR_PAK, COINIT_IAT = 0x74BBD0, 0x8B34BC
ORIGINAL = bytes.fromhex('83c4086a00ff15bc348b00')


def secciones(pe):
    off = struct.unpack_from('<I', pe, 0x3C)[0]
    n = struct.unpack_from('<H', pe, off + 6)[0]
    opt = struct.unpack_from('<H', pe, off + 20)[0]
    dllch = struct.unpack_from('<H', pe, off + 24 + 70)[0]
    tab = off + 24 + opt
    out = []
    for i in range(n):
        nombre, vsz, va, rsz, rptr = struct.unpack_from('<8sIIII', pe, tab + 40 * i)
        out.append((nombre.rstrip(b'\0').decode(), BASE + va, vsz, rptr, rsz))
    return out, dllch


def a_fichero(secs, va):
    for nombre, v, vsz, rptr, rsz in secs:
        if v <= va < v + rsz:
            return rptr + va - v
    raise ValueError('0x%x fuera de las secciones del fichero' % va)


def ampliar_virtual(pe, va):
    """El hueco esta en el fichero (SizeOfRawData) pero pasa de VirtualSize:
    se sube VirtualSize hasta SizeOfRawData para que el cargador lo mapee.
    No pisa nada: la seccion siguiente empieza en la pagina de despues."""
    off = struct.unpack_from('<I', pe, 0x3C)[0]
    n = struct.unpack_from('<H', pe, off + 6)[0]
    tab = off + 24 + struct.unpack_from('<H', pe, off + 20)[0]
    for i in range(n):
        e = tab + 40 * i
        vsz, v, rsz = struct.unpack_from('<III', pe, e + 8)
        if BASE + v <= va < BASE + v + rsz and vsz < rsz:
            struct.pack_into('<I', pe, e + 8, rsz)


def rel32(desde, destino):
    return struct.pack('<i', destino - (desde + 5))


# --- Segundo parche: la region 30 del mapa del mundo (Sand Castle Tales) ---
# La funcion de la ventana del mapa (decompilado: 289393-289479) registra
# 29 regiones con sub_5AA1E0(this, region, resolucion, smap, mpc) y el
# objeto tiene hueco para 30 (memset de 0x438 = 30x3x12 bytes; el
# destructor 0x5AA120 recorre i < 30). Taiwan trae la 30: world*_30.mpc y
# smap\world88-90. Cada registro, medido con REA en 0x5aa07a:
#   68 <mpc> 68 <smap> 6a <res> 6a <region> 8b 4d a4 e8 <rel 0x5AA1E0>
# y tras el ultimo, en 0x5aa090, 68 e0728b00 (push "wnd01\w033_17").
REG_HOOK, REG_VUELTA = 0x5AA090, 0x5AA095
REG_ORIGINAL = bytes.fromhex('68e0728b00')
REGISTRAR = 0x5AA1E0
REG_CUEVA = 0x912500                       # relleno de .rdata, se hace ejecutable
REGION30 = [(0, 'smap\\world89', 'map\\world800x600_30.mpc'),
            (1, 'smap\\world88', 'map\\world1024x768_30.mpc'),
            (2, 'smap\\world90', 'map\\world1280x720_30.mpc')]

# Registrar recursos no amplia el switch de dibujo: la pagina Lua 30
# (region 29) quedaba descartada por `cmp [ebp-8],29; ja epilogo`.
DRAW_HOOK, DRAW_RESUME, DRAW_END = 0x5AA3E5, 0x5AA3EF, 0x5AA596
DRAW_ORIGINAL = bytes.fromhex('837df81d0f87a7010000')
DRAW_REGION = 0x5AC680


def parchear_dibujo_region30(pe: bytearray) -> bytearray:
    """Anade SOLO el despacho de pagina 30, sin cambiar los casos antiguos.

    Acepta el IGG medido y el cliente ya parcheado (update32 / tooltip).
    Una seccion propia evita pisar las cuevas usadas por esos parches.
    Rechaza ejecutables diferentes y es idempotente.
    """
    secs, dllch = secciones(pe)
    if dllch & 0x40 or any(s[0] == '.reloc' for s in secs):
        raise ValueError('el ejecutable es reubicable')
    hook = a_fichero(secs, DRAW_HOOK)
    existing = next((s for s in secs if s[0] == '.twmap'), None)

    def codigo(cave):
        # Pagina 30 -> dibujar region 29; resto -> switch original.
        code = bytearray.fromhex('837df81e750f6a1d8b4dfc')
        code += b'\xe8' + rel32(cave + len(code), DRAW_REGION)
        code += b'\xe9' + rel32(cave + len(code), DRAW_END)
        code += DRAW_ORIGINAL[:4]
        code += b'\x0f\x87' + struct.pack('<i', DRAW_END - (cave + len(code) + 6))
        code += b'\xe9' + rel32(cave + len(code), DRAW_RESUME)
        return code

    if existing:
        cave, raw = existing[1], existing[3]
        code = codigo(cave)
        expected = b'\xe9' + rel32(DRAW_HOOK, cave) + b'\x90' * 5
        if pe[hook:hook + 10] != expected or pe[raw:raw + len(code)] != code:
            raise ValueError('el parche .twmap existente no coincide')
        return pe
    if pe[hook:hook + len(DRAW_ORIGINAL)] != DRAW_ORIGINAL:
        raise ValueError('el switch de mapa no es el IGG medido')
    off = struct.unpack_from('<I', pe, 0x3C)[0]
    n, optsize = struct.unpack_from('<H', pe, off + 6)[0], struct.unpack_from('<H', pe, off + 20)[0]
    opt, table = off + 24, off + 24 + optsize
    header = table + n * 40
    section_align, file_align = struct.unpack_from('<II', pe, opt + 32)
    size_headers = struct.unpack_from('<I', pe, opt + 60)[0]
    if header + 40 > min(size_headers, min(s[3] for s in secs if s[3])):
        raise ValueError('no hay espacio para otra cabecera PE')
    if any(pe[header:header + 40]):
        raise ValueError('la nueva cabecera PE no esta vacia')
    def align(value, boundary):
        return (value + boundary - 1) // boundary * boundary
    rva = align(max(s[1] - BASE + max(s[2], s[4]) for s in secs), section_align)
    cave = BASE + rva
    code = codigo(cave)
    raw = align(len(pe), file_align)
    raw_size = align(len(code), file_align)
    pe.extend(bytes(raw - len(pe)) + code + bytes(raw_size - len(code)))
    pe[header:header + 40] = struct.pack('<8sIIIIIIHHI', b'.twmap\0\0', len(code), rva,
                                      raw_size, raw, 0, 0, 0, 0, 0x60000020)
    struct.pack_into('<H', pe, off + 6, n + 1)
    struct.pack_into('<I', pe, opt + 56, align(rva + len(code), section_align))
    struct.pack_into('<I', pe, opt + 4, struct.unpack_from('<I', pe, opt + 4)[0] + raw_size)
    struct.pack_into('<I', pe, opt + 64, 0)
    pe[hook:hook + 10] = b'\xe9' + rel32(DRAW_HOOK, cave) + b'\x90' * 5
    return pe


def parchear_region30(pe: bytearray, secs) -> None:
    h = a_fichero(secs, REG_HOOK)
    if pe[h:h + 5] != REG_ORIGINAL:
        raise SystemExit('los bytes de 0x5aa090 no son los medidos')
    # cadenas primero, detras el codigo
    cadenas, va = {}, REG_CUEVA
    blob = bytearray()
    for _, smap, mpc in REGION30:
        for s in (smap, mpc):
            cadenas[s] = va + len(blob)
            blob += s.encode('ascii') + b'\0'
    while len(blob) % 4:
        blob += b'\0'
    codigo_va = va + len(blob)
    cod = bytearray()
    for res, smap, mpc in REGION30:
        cod += b'\x68' + struct.pack('<I', cadenas[mpc])
        cod += b'\x68' + struct.pack('<I', cadenas[smap])
        cod += bytes([0x6A, res, 0x6A, 29]) + bytes.fromhex('8b4da4')
        cod += b'\xe8' + rel32(codigo_va + len(cod), REGISTRAR)
    cod += REG_ORIGINAL                                     # push "wnd01\w033_17"
    cod += b'\xe9' + rel32(codigo_va + len(cod), REG_VUELTA)
    todo = blob + cod
    o = a_fichero(secs, REG_CUEVA)
    if any(pe[o:o + len(todo)]) or REG_CUEVA + len(todo) > CADENA:
        raise SystemExit('el hueco de .rdata no esta vacio o no alcanza')
    pe[o:o + len(todo)] = todo
    pe[h:h + 5] = b'\xe9' + rel32(REG_HOOK, codigo_va)
    ampliar_virtual(pe, REG_CUEVA + len(todo))
    # .rdata ejecutable (IMAGE_SCN_MEM_EXECUTE)
    off = struct.unpack_from('<I', pe, 0x3C)[0]
    n = struct.unpack_from('<H', pe, off + 6)[0]
    tab = off + 24 + struct.unpack_from('<H', pe, off + 20)[0]
    for i in range(n):
        e = tab + 40 * i
        if pe[e:e + 6] == b'.rdata':
            car = struct.unpack_from('<I', pe, e + 36)[0]
            struct.pack_into('<I', pe, e + 36, car | 0x20000000)


def parchear(pe: bytearray) -> bytearray:
    secs, dllch = secciones(pe)
    if any(s[0] == '.reloc' for s in secs) or dllch & 0x40:
        raise SystemExit('el ejecutable es reubicable: este parche no vale')
    h = a_fichero(secs, HOOK)
    if pe[h:h + len(ORIGINAL)] != ORIGINAL:
        raise SystemExit('los bytes de 0x534201 no son los medidos: otro angel.dat?')
    c, s = a_fichero(secs, CUEVA), a_fichero(secs, CADENA)
    codigo = bytearray()
    codigo += bytes.fromhex('83c408')                    # add esp,8 (de update31)
    codigo += bytes.fromhex('6a00')                      # push 0
    codigo += b'\x68' + struct.pack('<I', CADENA)        # push "update32.pak"
    codigo += b'\xe8' + rel32(CUEVA + len(codigo), CARGAR_PAK)
    codigo += bytes.fromhex('83c408')                    # add esp,8
    codigo += bytes.fromhex('6a00ff15') + struct.pack('<I', COINIT_IAT)
    codigo += b'\xe9' + rel32(CUEVA + len(codigo), VUELTA)
    cadena = b'update32.pak\0'
    if any(pe[c:c + len(codigo)]) or any(pe[s:s + len(cadena)]):
        raise SystemExit('el hueco no esta vacio')
    pe[c:c + len(codigo)] = codigo
    pe[s:s + len(cadena)] = cadena
    ampliar_virtual(pe, CUEVA + len(codigo))
    ampliar_virtual(pe, CADENA + len(cadena))
    salto = b'\xe9' + rel32(HOOK, CUEVA)
    pe[h:h + len(ORIGINAL)] = salto + b'\x90' * (len(ORIGINAL) - len(salto))
    parchear_region30(pe, secciones(pe)[0])
    return parchear_dibujo_region30(pe)


if __name__ == '__main__':
    args = sys.argv[1:]
    solo_mapa = '--solo-mapa' in args
    args = [a for a in args if a != '--solo-mapa']
    if len(args) != 2:
        raise SystemExit('uso: parchear_angel_update32.py [--solo-mapa] entrada salida')
    datos = bytearray(open(args[0], 'rb').read())
    nuevo = parchear_dibujo_region30(datos) if solo_mapa else parchear(datos)
    open(args[1], 'wb').write(nuevo)
    print('escrito', args[1])
