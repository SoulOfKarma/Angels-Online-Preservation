"""Lee las asignaciones de constantes globales de un script Lua 5.1 compilado
(los .l del cliente, cabecera 'LuaQ').

Para sacar, por ejemplo, los valores de GUILD_PERM_* y GLD_EVENT_* de
script/guild.l: el cliente los define como globales en su funcion principal
(LOADK numero -> SETGLOBAL nombre), y la tabla de constantes de esa funcion
trae los nombres y los numeros.

    python tools/lua51_constantes.py extracted_paks/data1/script/guild.l
"""
import struct
import sys


class Lector:
    def __init__(self, d):
        self.d, self.p = d, 0
        assert d[:4] == b'\x1bLua' and d[4] == 0x51, 'no es Lua 5.1'
        self.endian = '<' if d[6] == 1 else '>'
        self.sz_int, self.sz_size, self.sz_instr, self.sz_num = d[7], d[8], d[9], d[10]
        self.integral = d[11]
        self.p = 12

    def u(self, n):
        v = self.d[self.p:self.p + n]
        self.p += n
        return v

    def int_(self):
        return int.from_bytes(self.u(self.sz_int), 'little')

    def size(self):
        return int.from_bytes(self.u(self.sz_size), 'little')

    def string(self):
        n = self.size()
        s = self.u(n)
        return s[:-1].decode('latin-1') if n else None

    def numero(self):
        b = self.u(self.sz_num)
        return struct.unpack(self.endian + ('d' if self.sz_num == 8 else 'f'), b)[0]

    def funcion(self):
        f = {}
        f['fuente'] = self.string()
        self.int_(); self.int_()
        self.u(4)                               # nups, params, vararg, maxstack
        n = self.int_()
        f['codigo'] = [int.from_bytes(self.u(self.sz_instr), 'little') for _ in range(n)]
        n = self.int_()
        k = []
        for _ in range(n):
            t = self.u(1)[0]
            if t == 0:
                k.append(None)
            elif t == 1:
                k.append(bool(self.u(1)[0]))
            elif t == 3:
                k.append(self.numero())
            elif t == 4:
                k.append(self.string())
        f['k'] = k
        f['hijas'] = [self.funcion() for _ in range(self.int_())]
        for _ in range(self.int_()):            # lineinfo
            self.int_()
        for _ in range(self.int_()):            # locvars
            self.string(); self.int_(); self.int_()
        for _ in range(self.int_()):            # upvalues
            self.string()
        return f


def globales(f):
    """{nombre: valor} de los LOADK/SETGLOBAL de la funcion principal."""
    reg, out = {}, {}
    for ins in f['codigo']:
        op, a = ins & 0x3F, (ins >> 6) & 0xFF
        bx = ins >> 14
        if op == 1:                              # LOADK
            reg[a] = f['k'][bx]
        elif op == 7 and a in reg:               # SETGLOBAL
            nombre = f['k'][bx]
            if isinstance(reg[a], (int, float)) and not isinstance(reg[a], bool):
                out[nombre] = int(reg[a]) if float(reg[a]).is_integer() else reg[a]
        elif op not in (1, 7):
            reg.pop(a, None)
    return out


if __name__ == '__main__':
    f = Lector(open(sys.argv[1], 'rb').read()).funcion()
    for nombre, valor in globales(f).items():
        print('%-32s %s' % (nombre, valor))
