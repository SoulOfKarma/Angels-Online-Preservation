"""Tabla de funciones de los .so 'Smart Script' usados por el cliente IGG.

La cabecera contiene offset/cantidad de simbolos de 16 bytes y de entradas
de funcion de cuatro bytes. El simbolo guarda codigo, aridad y nombre NUL.
No se ejecuta ni se modifica bytecode al inspeccionarlo.
"""
import struct


def simbolos(data):
    if len(data) < 64 or not data.startswith(b'Smart Script\0'):
        raise ValueError('no es Smart Script')
    version, code, offset, count, functions, nfunctions, _, size = struct.unpack_from('<8I', data, 16)
    if version != 0x100 or code != 64 or size != len(data):
        raise ValueError('cabecera Smart Script incompatible')
    if offset + count * 16 != functions or functions + nfunctions * 4 != len(data):
        raise ValueError('tablas Smart Script fuera de limites')
    result = {}
    for i in range(count):
        address, arity, name, flags = struct.unpack_from('<4I', data, offset + i * 16)
        end = data.find(b'\0', name, offset)
        if not code <= address < offset or not code <= name < offset or end < 0:
            raise ValueError('simbolo Smart Script invalido')
        result[data[name:end].decode('ascii')] = (address, arity)
    return result


def compatible(old, new):
    before, after = simbolos(old), simbolos(new)
    missing = sorted(set(before) - set(after))
    changed = sorted(name for name in before.keys() & after.keys()
                     if before[name][1] != after[name][1])
    if missing or changed:
        raise ValueError('funciones antiguas ausentes/cambiadas: %s / %s' % (missing, changed))
    return set(after) - set(before)
