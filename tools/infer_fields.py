"""
Infiere la estructura de un opcode a partir de sus muestras reales.

No adivina semantica: mide. Para cada offset reporta constancia, entropia,
si es ASCII, y propone agrupaciones LE16/LE32 segun rangos observados.
La interpretacion la pone el humano; la evidencia la pone esto.
"""
import sqlite3, struct, sys, collections

def analyze(rows, label):
    n = len(rows)
    L = len(rows[0])
    print(f"\n### {label}  ({n} muestras, {L} bytes)")
    const = {}
    for o in range(L):
        vals = collections.Counter(r[o] for r in rows)
        if len(vals) == 1:
            const[o] = vals.most_common(1)[0][0]
    # regiones ASCII
    ascii_off = [o for o in range(L)
                 if sum(1 for r in rows if 32 <= r[o] < 127 or r[o] == 0) / n > 0.95
                 and sum(1 for r in rows if 32 <= r[o] < 127) / n > 0.3]
    runs, cur = [], []
    for o in ascii_off:
        if cur and o == cur[-1] + 1: cur.append(o)
        else:
            if len(cur) >= 4: runs.append((cur[0], cur[-1]))
            cur = [o]
    if len(cur) >= 4: runs.append((cur[0], cur[-1]))

    print(f"  bytes constantes: {len(const)}/{L}" +
          (f"  ->  {', '.join(f'@{o}=0x{v:02x}' for o,v in list(const.items())[:10])}" if const else ""))
    if runs:
        print(f"  regiones ASCII (texto): {['@%d..%d' % r for r in runs]}")

    print(f"\n  {'off':>4} {'LE32':>26} {'LE16':>18}  lectura")
    o = 0
    while o < L:
        if any(a <= o <= b for a, b in runs):
            reg = next(r for r in runs if r[0] <= o <= r[1])
            ej = bytes(rows[0][reg[0]:reg[1]+1]).split(b'\x00')[0].decode('ascii','replace')
            print(f"  {o:>4} {'':>26} {'':>18}  char[{reg[1]-reg[0]+1}]  ej: \"{ej}\"")
            o = reg[1] + 1
            continue
        if o + 4 <= L:
            v32 = [struct.unpack_from('<I', bytes(r), o)[0] for r in rows]
            mn, mx, nd = min(v32), max(v32), len(set(v32))
            v16 = [struct.unpack_from('<H', bytes(r), o)[0] for r in rows]
            mn16, mx16, nd16 = min(v16), max(v16), len(set(v16))
            # heuristica: si el LE32 se mantiene chico, es un campo de 4 bytes
            plaus32 = mx < 0x1000000
            s32 = f"{mn}..{mx} ({nd} dist)"
            s16 = f"{mn16}..{mx16} ({nd16})"
            mark = "LE32" if plaus32 else "ver LE16"
            if nd == 1: mark = f"CONST {mn}"
            print(f"  {o:>4} {s32:>26} {s16:>18}  {mark}")
            o += 4
        else:
            print(f"  {o:>4} {'':>26} {'':>18}  {L-o} byte(s) de cola")
            break


db = sqlite3.connect('corpus/all.db')
op = int(sys.argv[1], 16); d = sys.argv[2]; src = sys.argv[3] if len(sys.argv) > 3 else None
q = "SELECT body FROM packets WHERE opcode=? AND dir=? AND chain_ok=1"
a = [op, d]
if src: q += " AND src=?"; a.append(src)
rows = [bytes(b) for (b,) in db.execute(q, a) if b]
if not rows: print("sin muestras"); sys.exit()
bylen = collections.Counter(len(r) for r in rows)
print(f"opcode 0x{op:04X} {d} {src or '(ambos)'}: {len(rows)} muestras, tamanos {dict(bylen.most_common(4))}")
L = bylen.most_common(1)[0][0]
analyze([r for r in rows if len(r) == L], f"0x{op:04X} {d} len={L}")
db.close()
