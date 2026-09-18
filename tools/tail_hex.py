import sqlite3, struct
db = sqlite3.connect('corpus/packets.db')
seen = set()
print("nombre               | bytes 30..62")
print("-" * 92)
for (b,) in db.execute("SELECT DISTINCT body FROM packets WHERE dir='s2c' AND opcode=8 AND chain_ok=1"):
    t = bytes(b)
    nm = t[16:32].split(b'\x00')[0].decode('ascii','replace')
    if nm in seen or not nm: continue
    seen.add(nm)
    print(f"{nm:<20} | {t[30:50].hex(' ')}")
    if len(seen) >= 10: break
db.close()
