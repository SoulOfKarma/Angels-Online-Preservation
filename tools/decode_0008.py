"""Decodifica los 63 bytes completos de 0x0008 NPC_SPAWN."""
import sqlite3, struct, collections
db = sqlite3.connect('corpus/packets.db')
rows = [bytes(b) for (b,) in db.execute(
    "SELECT body FROM packets WHERE dir='s2c' AND opcode=8 AND chain_ok=1")]
print(f"muestras: {len(rows)}  (todas de 63 bytes)\n")

# donde termina el nombre? buscar el ultimo byte no-nulo dentro de 16..63
ends = collections.Counter()
for t in rows:
    z = t[16:].find(b'\x00')
    ends[16 + (z if z >= 0 else len(t) - 16)] += 1
print("fin del nombre (offset del primer NUL):", dict(list(ends.most_common(6))))

# el campo nombre parece de largo fijo; ver donde vuelven a aparecer datos
print("\nbytes no-nulos por offset (sobre todas las muestras):")
nz = [sum(1 for t in rows if t[o]) for o in range(63)]
for o in range(0, 63, 1):
    bar = '#' * int(40 * nz[o] / len(rows))
    if o == 16: print("   --- inicio nombre ---")
    print(f"   {o:>3} {100*nz[o]/len(rows):5.1f}% {bar}")
db.close()
