import struct

def armar_hex(mid, val, opts=[]):
    hdr = struct.pack('<IHBBB', mid, val, 0, len(opts), 0)
    body = b''.join(struct.pack('<I', o) for o in opts)
    return (hdr + body).hex()

print("Angels' Tutor:", armar_hex(10101, 4, [10107, 10108, 10109, 10110, 10111]))
print("Scroll Seller:", armar_hex(5628, 4, [12103, 12105]))
print("Magic Seller:", armar_hex(5235, 4, [12103, 12105]))
print("C. Plan Seller:", armar_hex(5234, 4, [12103, 12105]))
print("Bao Clerk:", armar_hex(5236, 4, [5237, 5238, 12105]))

