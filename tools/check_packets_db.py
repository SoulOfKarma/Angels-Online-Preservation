import sqlite3
import struct
import collections

db = sqlite3.connect('corpus/packets.db')
cur = db.cursor()

# Check all 0x0013 packets
kinds = collections.defaultdict(list)
for (b,) in cur.execute("SELECT body FROM packets WHERE dir='s2c' AND opcode=0x0013 LIMIT 1000"):
    raw = bytes(b)
    if len(raw) >= 10:
        eid, unk4, kind, val = struct.unpack_from('<IBBI', raw, 0)
        kinds[kind].append((eid, val))

print("0x0013 distinct kinds found in packets.db:")
for k, vals in kinds.items():
    samples = vals[:5]
    print(f"Kind {k}: count={len(vals)}, samples={samples}")

# Check all 0x001D packets
kinds_1d = collections.defaultdict(list)
for (b,) in cur.execute("SELECT body FROM packets WHERE dir='s2c' AND opcode=0x001D LIMIT 1000"):
    raw = bytes(b)
    if len(raw) >= 5:
        eid, n = struct.unpack_from('<IB', raw, 0)
        off = 5
        for _ in range(n):
            if off + 9 <= len(raw):
                k, a, c = struct.unpack_from('<BII', raw, off)
                kinds_1d[k].append((a, c))
                off += 9

print("\n0x001D distinct kinds found in packets.db:")
for k, vals in kinds_1d.items():
    samples = vals[:5]
    print(f"Kind {k}: count={len(vals)}, samples={samples}")

