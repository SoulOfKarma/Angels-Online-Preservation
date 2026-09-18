import sqlite3, struct
db = sqlite3.connect('corpus/packets.db')
rows = [bytes(b) for (b,) in db.execute(
    "SELECT DISTINCT body FROM packets WHERE dir='s2c' AND opcode=8 AND chain_ok=1")]
print(f"{'nombre':<20} {'eid':>6} {'fl':>3} {'x':>5} {'y':>5} | "
      f"{'@32':>10} {'@36':>7} {'@40':>7} {'@44':>10} {'@48':>7}")
print("-" * 98)
seen = set()
for t in rows:
    eid, fl, x, y = struct.unpack_from('<IIII', t, 0)
    nm = t[16:32].split(b'\x00')[0].decode('ascii', 'replace')
    if nm in seen or not nm: continue
    seen.add(nm)
    f32, f36, f40, f44, f48 = struct.unpack_from('<IIIIH', t, 32)
    print(f"{nm:<20} {eid:>6} {fl:>3} {x:>5} {y:>5} | "
          f"{f32:>10} {f36:>7} {f40:>7} {f44:>10} {f48:>7}")
    if len(seen) >= 18: break
db.close()
