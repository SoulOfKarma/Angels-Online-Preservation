import struct

samples = [
    ("0901000100000000000300000001", "Sword lv1 exp0"),
    ("0902000200610000000600000001", "Sword lv2 exp61h=97"),
    ("0c03000300bf0000000800000002", "Enhance lv3 expbfh=191"),
    ("0c040004001b0100000c00000002", "Enhance lv4"),
]

for hx, label in samples:
    b = bytes.fromhex(hx)
    print(label, struct.unpack('>7H', b))

