"""Contrasta las afirmaciones de src/area_entity_data.py contra el corpus real."""
import sqlite3, struct, collections, sys

db = sqlite3.connect('corpus/packets.db')
Q = lambda s, *a: db.execute(s, a).fetchall()

print("=" * 84)
print("AFIRMACION 1: '0x0008 NPC spawn es un sub-mensaje de 65 bytes'")
print("=" * 84)
r = Q("SELECT COUNT(*), MIN(size), MAX(size) FROM packets WHERE dir='s2c' AND opcode=8 AND chain_ok=1")[0]
print(f"  corpus: {r[0]} muestras, body {r[1]}..{r[2]} bytes -> sub_len = {r[1]+2}")
print(f"  VEREDICTO: {'CONFIRMADO' if r[1]==r[2]==63 else 'REFUTADO'} (63 body + 2 opcode = 65)")

print("\n" + "=" * 84)
print("AFIRMACION 2: 'los campos de posicion de 0x0008 son escala TILE, no pixeles'")
print("=" * 84)
rows = Q("SELECT body FROM packets WHERE dir='s2c' AND opcode=8 AND chain_ok=1 LIMIT 4000")
print("  Muestra de cuerpos 0x0008 (con nombre ASCII embebido):")
shown = 0
fields = collections.defaultdict(list)
for (b,) in rows:
    txt = bytes(b)
    # nombre = primera cadena ASCII imprimible de >=3 chars
    name, cur = None, b''
    for ch in txt:
        if 32 <= ch < 127: cur += bytes([ch])
        else:
            if len(cur) >= 3 and name is None: name = cur.decode('ascii')
            cur = b''
    if name and shown < 6:
        print(f"    {name:<22} {txt[:24].hex(' ')}")
        shown += 1
    for off in range(0, min(len(txt)-4, 40), 2):
        fields[off].append(struct.unpack_from('<H', txt, off)[0])

print("\n  Rango de cada campo LE16 (los candidatos a posicion):")
print(f"    {'offset':>6} {'min':>8} {'max':>8} {'distintos':>10}  escala")
for off in sorted(fields):
    v = fields[off]
    mn, mx, nd = min(v), max(v), len(set(v))
    if nd < 3: continue
    esc = "TILE (<2048)" if mx < 2048 else ("PIXEL (>4096)" if mx > 4096 else "?")
    print(f"    {off:>6} {mn:>8} {mx:>8} {nd:>10}  {esc}")

print("\n" + "=" * 84)
print("AFIRMACION 3: 'entity_id = hi-word fijo + lo-word incremental' (ej 0x13b00e85)")
print("=" * 84)
ids = [struct.unpack_from('<I', bytes(b), 0)[0]
       for (b,) in Q("SELECT body FROM packets WHERE dir='s2c' AND opcode=5 AND chain_ok=1")]
his = collections.Counter(i >> 16 for i in ids)
print(f"  entity_ids extraidos de 0x0005 ENTITY_MOVE: {len(ids)} muestras")
print(f"  valores distintos de hi-word: {len(his)}")
print(f"  hi-words mas comunes: {[f'0x{h:04X} (x{n})' for h, n in his.most_common(5)]}")
print(f"  rango de entity_id: 0x{min(ids):08X} .. 0x{max(ids):08X}")
veredicto = "CONFIRMADO" if len(his) <= 3 else "REFUTADO: los entity_id son valores chicos, no hi/lo"
print(f"  VEREDICTO: {veredicto}")
db.close()
