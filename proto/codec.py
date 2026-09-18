"""
Codec declarativo del protocolo Angels Online.

Cada mensaje se define UNA sola vez. El parser y el constructor se derivan de
esa definicion, asi que no pueden divergir. Los dos crashes del emulador
anterior -- struct.pack('<HIIIIIB', ...) con 6 argumentos para 7 campos, y un
'<HIIIIIH' recibiendo una coordenada negativa -- son imposibles de expresar
aqui: la aridad la garantiza la definicion y el rango lo valida cada campo.
"""
import struct


class Field:
    fmt = None
    def __init__(self, name, const=None):
        self.name, self.const = name, const
    @property
    def size(self): return struct.calcsize('<' + self.fmt)
    def parse(self, buf, off): return struct.unpack_from('<' + self.fmt, buf, off)[0]
    def build(self, val):
        lo, hi = self.range
        if not (lo <= val <= hi):
            raise ValueError(f"{self.name}={val} fuera de rango [{lo},{hi}] para {type(self).__name__}")
        return struct.pack('<' + self.fmt, val)


class U8(Field):  fmt = 'B'; range = (0, 0xFF)
class U16(Field): fmt = 'H'; range = (0, 0xFFFF)
class U32(Field): fmt = 'I'; range = (0, 0xFFFFFFFF)
class I16(Field): fmt = 'h'; range = (-0x8000, 0x7FFF)
class I32(Field): fmt = 'i'; range = (-0x80000000, 0x7FFFFFFF)


class Bytes(Field):
    def __init__(self, name, n, const=None):
        super().__init__(name, const); self.n = n
    @property
    def size(self): return self.n
    def parse(self, buf, off): return bytes(buf[off:off + self.n])
    def build(self, val):
        v = bytes(val)
        if len(v) != self.n:
            raise ValueError(f"{self.name}: se esperaban {self.n} bytes, hay {len(v)}")
        return v


class Str(Bytes):
    """Cadena ASCII de largo fijo, rellenada con NUL."""
    def parse(self, buf, off):
        return bytes(buf[off:off + self.n]).split(b'\x00')[0].decode('ascii', 'replace')
    def build(self, val):
        if isinstance(val, str): val = val.encode('ascii', 'replace')
        if len(val) > self.n:
            raise ValueError(f"{self.name}: '{val}' excede {self.n} bytes")
        return val + b'\x00' * (self.n - len(val))


class Msg:
    registry = {}

    def __init__(self, opcode, dir, name, fields, note="", rev="*", puertos=None):
        # rev: '*' = vale para todos los servidores; 'privado'/'igg' = solo esa
        # revision. IGG y el servidor privado NO corren el mismo protocolo.
        self.opcode, self.dir, self.name = opcode, dir, name
        self.fields, self.note, self.rev = fields, note, rev
        # Los opcodes estan acotados POR SERVICIO: el mismo numero significa
        # cosas distintas en puertos distintos. Ej: 0x0002 es la ficha del
        # personaje en 24131/24132 y un nombre de archivo PNG en 30007.
        self.puertos = tuple(puertos) if puertos else None
        self.size = sum(f.size for f in fields)
        Msg.registry[(opcode, dir, rev)] = self

    def parse(self, body):
        out, off = {}, 0
        for f in self.fields:
            out[f.name] = f.parse(body, off)
            off += f.size
        out['_extra'] = bytes(body[off:])
        return out

    def build(self, **kw):
        parts = []
        for f in self.fields:
            if f.name in kw: v = kw[f.name]
            elif f.const is not None: v = f.const
            else: raise KeyError(f"{self.name}: falta el campo '{f.name}'")
            parts.append(f.build(v))
        return struct.pack('<H', self.opcode) + b''.join(parts) + kw.get('_extra', b'')

    def roundtrip(self, body):
        """build(parse(x)) == x ?  Es la prueba de que el esquema es exacto."""
        d = self.parse(body)
        return self.build(**d)[2:] == bytes(body)

    def __repr__(self):
        return f"<Msg 0x{self.opcode:04X} {self.dir} {self.name} {self.size}B rev={self.rev}>"


# --------------------------------------------------------------- longitud variable

class Count(Field):
    """Contador de un array. Al construir NO se pasa: se deriva de len(array).

    Asi es imposible el bug clasico de que el contador y el array digan cosas
    distintas -- que es la misma clase de error que los dos crashes originales,
    solo que en vez de reventar el struct corrompe el stream del cliente.
    """
    def __init__(self, name, of, fmt='B'):
        super().__init__(name)
        self.of, self.fmt = of, fmt
    @property
    def range(self): return (0, (1 << (8 * struct.calcsize('<' + self.fmt))) - 1)


class Array(Field):
    """N repeticiones de un grupo de campos. N lo fija el Count asociado."""
    def __init__(self, name, fields):
        super().__init__(name)
        self.fields = fields
        self.rec_size = sum(f.size for f in fields)
    @property
    def size(self): return 0          # variable: se resuelve en parse/build

    def parse_n(self, buf, off, n):
        out = []
        for _ in range(n):
            rec, o = {}, off
            for f in self.fields:
                rec[f.name] = f.parse(buf, o); o += f.size
            out.append(rec); off = o
        return out, off

    def build_list(self, items):
        parts = []
        for it in items:
            for f in self.fields:
                if f.name not in it:
                    raise KeyError(f"{self.name}[]: falta el campo '{f.name}'")
                parts.append(f.build(it[f.name]))
        return b''.join(parts)


class VarMsg(Msg):
    """Mensaje con un array de largo variable gobernado por un Count."""

    def parse(self, body):
        out, off = {}, 0
        for f in self.fields:
            if isinstance(f, Count):
                out[f.name] = struct.unpack_from('<' + f.fmt, body, off)[0]
                off += f.size
            elif isinstance(f, Array):
                cnt = next(c for c in self.fields if isinstance(c, Count) and c.of == f.name)
                out[f.name], off = f.parse_n(body, off, out[cnt.name])
            else:
                out[f.name] = f.parse(body, off); off += f.size
        out['_extra'] = bytes(body[off:])
        return out

    def build(self, **kw):
        parts = []
        for f in self.fields:
            if isinstance(f, Count):
                items = kw.get(f.of)
                if items is None:
                    raise KeyError(f"{self.name}: falta el array '{f.of}'")
                parts.append(struct.pack('<' + f.fmt, len(items)))   # derivado
            elif isinstance(f, Array):
                parts.append(f.build_list(kw[f.name]))
            else:
                v = kw[f.name] if f.name in kw else f.const
                if v is None: raise KeyError(f"{self.name}: falta el campo '{f.name}'")
                parts.append(f.build(v))
        return struct.pack('<H', self.opcode) + b''.join(parts) + kw.get('_extra', b'')


class FixedArray(Array):
    """Array de N repeticiones con N constante (no lo gobierna ningun Count)."""
    def __init__(self, name, n, fields):
        super().__init__(name, fields)
        self.n = n
    @property
    def size(self): return self.n * self.rec_size
    def parse(self, buf, off):
        return self.parse_n(buf, off, self.n)[0]
    def build(self, val):
        if len(val) != self.n:
            raise ValueError(f"{self.name}: se esperaban {self.n} elementos, hay {len(val)}")
        return self.build_list(val)
