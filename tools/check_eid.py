import struct

data = open("server/plantillas/mundo_real/init_01_0002.bin", 'rb').read()
eid = struct.unpack_from('<I', data, 0)[0]
print(f"Entity ID in init_01_0002.bin: {eid}")

