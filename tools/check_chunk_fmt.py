import struct

# Chunk from packet 2: 09 02 00 02 00 61 00 00 00 06 00 00 00 01
chunk = bytes.fromhex("0902000200610000000600000001")
print("len:", len(chunk))
print("Bytes:", list(chunk))
# If it's:
# U8: 9
# U8: 2
# >H: 2
# >I: ? or 7 fields of 2 bytes?
# 14 bytes = 7 * U16!
for fmt in ['>7H', '<7H']:
    print(fmt, struct.unpack(fmt, chunk))

