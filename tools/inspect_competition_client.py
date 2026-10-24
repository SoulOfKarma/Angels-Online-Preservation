"""Read-only, bounded native competition fields. Never reads auth/session data.

Usage: python tools/inspect_competition_client.py <angel.dat PID> [...]
Offsets verified against G:/Angel.exe (the loaded competition routines match).
No writes, injection, function calls in the client, or process suspension.
"""
import ctypes
import json
import struct
import sys


def inspect(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1010, False, pid)
    if not handle:
        raise OSError(ctypes.get_last_error(), 'OpenProcess read-only')

    def read(address, size=4):
        buffer = ctypes.create_string_buffer(size)
        count = ctypes.c_size_t()
        if not kernel.ReadProcessMemory(handle, address, buffer, size, ctypes.byref(count)) or count.value != size:
            raise OSError(ctypes.get_last_error(), 'ReadProcessMemory')
        return buffer.raw

    def uint(address):
        return struct.unpack('<I', read(address))[0]

    try:
        arena_mode=read(0xa38119,1)[0]
        world = uint(0xa36f08)
        own_id = uint(world + 0x23c8)
        table, maximum = uint(world + 0x23ac), uint(world + 0x23dc)
        if maximum > 100000:
            raise ValueError('Unexpected entity table; unsupported client')
        def network_lookup(network_id):
            # Native535450 ->4ED140: bounded lower-bound traversal of the
            # network-ID map. Only key/handle fields, never actor payloads.
            head=uint(world+9184+24)
            node=uint(head+4)
            for _ in range(64):
                if read(node+21,1)[0]:return 0
                key=uint(node+12)
                if key==network_id:return uint(node+16)
                node=uint(node+(8 if key<network_id else 0))
            raise ValueError('Unexpected network-ID tree depth')
        actors = []
        for index in range(maximum + 1):
            actor = uint(table + index * 4)
            if not actor:
                continue
            # The virtual class checker004ABDC0 reads actor+4. The remote
            # network ID is+476, NOT self-only character field+792.
            native_class=uint(actor+4)
            if native_class not in (0x1102,0x80000102):
                continue
            network_id=uint(actor+476)
            fields = {'self': uint(actor + 0xbc) == own_id,
                'native_class':hex(native_class),
                'network_id': network_id, 'faction': hex(uint(actor + 744)),
                'team': struct.unpack('<H', read(actor + 752, 2))[0],
                'flags_lo': hex(uint(actor + 600)), 'flags_hi': hex(uint(actor + 604)),
                'ring_hidden': read(actor + 772, 1)[0]}
            fields['network_lookup_valid']=network_lookup(fields['network_id'])==uint(actor+0xbc)
            faction=uint(actor+744)
            fields['arena_ring_expected']=bool(arena_mode and faction & 0x80000000
                and 1 <= (faction & 0x7fffffff) <= 4
                and not uint(actor+604) & 0x40
                and not uint(actor+600) & 0x100100 and not fields['ring_hidden'])
            actors.append(fields)
        return {'pid': pid, 'arena_mode': arena_mode, 'players': actors}
    finally:
        kernel.CloseHandle(handle)


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        print(json.dumps(inspect(int(arg))))
