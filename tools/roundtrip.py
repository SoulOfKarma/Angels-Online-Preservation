"""
Harness de conformidad: valida cada esquema contra TODAS sus muestras reales.

Un esquema no se da por bueno hasta que pasa. Tres pruebas por opcode:

  1. TAMANO   el tamano declarado coincide con cada muestra
  2. ROUNDTRIP  build(parse(x)) == x  byte a byte
  3. CONSTANTES  los campos declarados const se cumplen SIEMPRE

La 3 es la que de verdad falsa hipotesis: si afirmo "@4 vale siempre 1" y una
sola muestra de 48.950 dice lo contrario, el esquema esta mal.

Aclaracion honesta sobre el alcance: el roundtrip prueba que la estructura es
exacta y reversible, NO que los nombres de los campos sean semanticamente
correctos. Un Bytes(63) opaco pasaria igual. El valor esta en la combinacion
con las constantes declaradas y el cruce de entity_id.
"""
import sqlite3, sys, collections, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'proto'))
from codec import Msg, VarMsg
import messages  # noqa: registra los esquemas

db = sqlite3.connect('corpus/all.db')

# universo de entity_id conocidos, tomado de opcodes ya confirmados
known = set()
for (b,) in db.execute("SELECT body FROM packets WHERE opcode IN (5,8) AND dir='s2c' AND chain_ok=1"):
    if len(b) >= 4:
        known.add(int.from_bytes(bytes(b)[:4], 'little'))

print("=" * 90)
print("HARNESS DE CONFORMIDAD  -  cada esquema contra todas sus muestras reales")
print("=" * 90)
print(f"{'opcode':<9} {'nombre':<15} {'dir':<5} {'muestras':>9} {'tam':>6} "
      f"{'roundtrip':>10} {'const':>8}  veredicto")
print("-" * 90)

tot_ok = tot_msg = tot_samples = 0
fallos = []
for (op, d, rev), m in sorted(Msg.registry.items()):
    q = "SELECT body FROM packets WHERE opcode=? AND dir=? AND chain_ok=1"
    a = [op, d]
    if rev != '*': q += " AND src=?"; a.append(rev)
    if m.puertos:                      # opcode acotado a un servicio
        q += " AND port IN (%s)" % ",".join("?" * len(m.puertos))
        a.extend(m.puertos)
    rows = [bytes(b) for (b,) in db.execute(q, a) if b is not None]
    lbl = d + "/" + rev[:4]
    variable = isinstance(m, VarMsg)
    szl = str(m.size) + ("+" if variable else "")
    if not rows:
        print(f"0x{op:04X}    {m.name:<15} {lbl:<10} {'0':>9} {szl:>6} "
              f"{'-':>10} {'-':>8}  sin muestras")
        continue
    # los mensajes de largo variable no se filtran por tamano: se validan
    # por roundtrip, que es lo que de verdad prueba que el largo se deriva bien
    exactos = rows if variable else [r for r in rows if len(r) == m.size]
    rt = cons = 0
    for r in exactos:
        try:
            if m.roundtrip(r): rt += 1
            dd = m.parse(r)
            if all(getattr(f, 'const', None) is None or dd[f.name] == f.const
                   for f in m.fields): cons += 1
        except Exception: pass
    n = len(exactos)
    pct_t = 100 * n / len(rows)
    ok = n == len(rows) and rt == n and cons == n
    acept = rt == n and cons == n and pct_t >= 99.9   # variantes raras toleradas
    tot_msg += 1; tot_ok += acept; tot_samples += n
    if ok:                          v = "VALIDADO"
    elif cons < n:                  v = "CONSTANTE REFUTADA"
    elif rt < n:                    v = "ROUNDTRIP FALLA"
    elif pct_t >= 99.9:             v = f"VALIDADO ({len(rows)-n} var. raras)"
    else:                           v = "TAMANO VARIABLE"
    if not acept: fallos.append((op, d, m, rows, exactos, rt, cons))
    print(f"0x{op:04X}    {m.name:<15} {lbl:<10} {len(rows):>9} {szl:>6} "
          f"{rt}/{n:<9} {cons}/{n:<7}  {v}")

print("-" * 90)
print(f"esquemas validados: {tot_ok}/{tot_msg}   |   muestras cubiertas: {tot_samples}")

cov = db.execute("SELECT COUNT(*) FROM packets WHERE chain_ok=1").fetchone()[0]
print(f"cobertura del corpus: {tot_samples}/{cov} = {100*tot_samples/cov:.1f}%")

if fallos:
    print("\n--- DETALLE DE FALLOS ---")
    for op, d, m, rows, exactos, rt, cons in fallos:
        tam = collections.Counter(len(r) for r in rows)
        print(f"\n0x{op:04X} {m.name} ({d}): tamanos reales {dict(tam.most_common(4))}, "
              f"declarado {m.size}")
        if cons < len(exactos):
            for f in m.fields:
                if f.const is None: continue
                mal = collections.Counter(m.parse(r)[f.name] for r in exactos
                                          if m.parse(r)[f.name] != f.const)
                if mal:
                    print(f"   campo '{f.name}' declarado const={f.const} pero "
                          f"{sum(mal.values())} muestras dicen {dict(list(mal.items())[:4])}")

# cruce de entity_id -- SIEMPRE por servidor.
# Mezclar servidores produjo dos falsas refutaciones (0x0013 y 0x001D): cada
# servidor tiene su propio espacio de entity_id, y un universo de referencia
# incompleto baja el cruce sin que el campo este mal definido.
print()
print("--- CRUCE DE entity_id (por servidor) ---")
for src in ('privado', 'igg'):
    uni = set()
    for (b,) in db.execute(
            "SELECT body FROM packets WHERE opcode IN (5,8) AND dir='s2c' "
            "AND chain_ok=1 AND src=?", (src,)):
        if b and len(b) >= 4:
            uni.add(int.from_bytes(bytes(b)[:4], 'little'))
    print()
    print(f"  [{src}]  universo de referencia: {len(uni)} entity_id distintos")
    for (op, d, rev), m in sorted(Msg.registry.items()):
        if not any(f.name == 'entity_id' for f in m.fields):
            continue
        if rev != '*' and rev != src:
            continue
        rows = [bytes(b) for (b,) in db.execute(
            "SELECT body FROM packets WHERE opcode=? AND dir=? AND chain_ok=1 "
            "AND src=?", (op, d, src)) if b]
        if not isinstance(m, VarMsg):
            rows = [r for r in rows if len(r) == m.size]
        if not rows:
            continue
        hit = 0
        for r in rows:
            try:
                if m.parse(r)['entity_id'] in uni:
                    hit += 1
            except Exception:
                pass
        pct = 100 * hit / len(rows)
        flag = "OK" if pct >= 90 else ("revisar" if pct >= 50 else "SOSPECHOSO")
        print(f"    0x{op:04X} {m.name:<15} {d}: {pct:5.1f}%  "
              f"({len(rows)} muestras)  {flag}")
db.close()
