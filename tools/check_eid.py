"""Los entity_id difieren entre el servidor de IGG y el privado?"""
import sqlite3, struct, collections
db = sqlite3.connect('corpus/packets.db')

print("entity_id por SERVIDOR (extraidos de 0x0005 y 0x0008):\n")
for srv, in db.execute("SELECT DISTINCT server FROM packets"):
    ids = []
    for op in (5, 8):
        for (b,) in db.execute(
            "SELECT body FROM packets WHERE dir='s2c' AND opcode=? AND server=? AND chain_ok=1", (op, srv)):
            if len(b) >= 4:
                ids.append(struct.unpack_from('<I', bytes(b), 0)[0])
    if not ids: 
        print(f"  {srv}: sin muestras"); continue
    his = collections.Counter(i >> 16 for i in ids)
    print(f"  {srv}")
    print(f"     muestras={len(ids)}  rango=0x{min(ids):08X}..0x{max(ids):08X}")
    print(f"     hi-words: {[f'0x{h:04X}(x{n})' for h,n in his.most_common(4)]}")
    grandes = sum(1 for i in ids if i > 0xFFFF)
    print(f"     ids > 0xFFFF: {grandes} ({100*grandes/len(ids):.1f}%)\n")

print("Estructura 0x0008 decodificada (10 muestras):")
print(f"  {'entity_id':>10} {'flags':>6} {'tile_x':>7} {'tile_y':>7}  nombre")
seen = set()
for (b,) in db.execute("SELECT body FROM packets WHERE dir='s2c' AND opcode=8 AND chain_ok=1 LIMIT 3000"):
    t = bytes(b)
    eid, fl, x, y = struct.unpack_from('<IIII', t, 0)
    nm = t[16:].split(b'\x00')[0].decode('ascii', 'replace')
    if nm in seen or not nm: continue
    seen.add(nm)
    print(f"  {eid:>10} {fl:>6} {x:>7} {y:>7}  {nm}")
    if len(seen) >= 10: break
db.close()
