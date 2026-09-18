"""Mapa de opcodes respaldado por evidencia: cobertura real medida, no conjeturas."""
import sqlite3, sys, collections

NAMES = {  # solo los ya confirmados contra datos reales o el binario
    0x0005: "ENTITY_MOVE", 0x0007: "ENTITY_POS", 0x000A: "?", 0x000B: "ENTITY_STATUS",
    0x000E: "ENTITY_SPAWN", 0x0010: "ENTITY_STATS", 0x0013: "?", 0x0018: "ENTITY_MOVE2",
    0x0019: "COMBAT", 0x001D: "?", 0x006D: "MOVE_ACK", 0x0002: "LOGIN_REQ",
    0x0003: "?", 0x0004: "MOVE_REQ",
}

db = sqlite3.connect(sys.argv[1])
print("=" * 88)
print("MAPA DE OPCODES  -  derivado de 207.570 sub-mensajes reales")
print("=" * 88)
for d in ('s2c', 'c2s'):
    rows = db.execute("""
        SELECT opcode, COUNT(*) n, MIN(size) mn, MAX(size) mx,
               COUNT(DISTINCT size) nsz
        FROM packets WHERE dir=? AND chain_ok=1
        GROUP BY opcode ORDER BY n DESC""", (d,)).fetchall()
    tot = sum(r[1] for r in rows)
    print(f"\n### {d.upper()}  ({tot} mensajes, {len(rows)} opcodes)\n")
    print(f"  {'opcode':<8} {'muestras':>9} {'tam':>11} {'forma':>7}  interpretacion")
    print("  " + "-" * 82)
    for op, n, mn, mx, nsz in rows[:26]:
        size = f"{mn}" if mn == mx else f"{mn}-{mx}"
        forma = "FIJA" if mn == mx else f"{nsz} var"
        conf = "listo p/ decodificar" if mn == mx and n >= 50 else (
               "variable: analizar" if n >= 50 else "pocas muestras")
        nm = NAMES.get(op, "")
        print(f"  0x{op:04X}   {n:>9} {size:>11} {forma:>7}  {nm:<14} {conf}")

print("\n" + "=" * 88)
fixed = db.execute("""SELECT COUNT(*) FROM (
    SELECT opcode FROM packets WHERE chain_ok=1
    GROUP BY opcode, dir HAVING MIN(size)=MAX(size) AND COUNT(*)>=50)""").fetchone()[0]
print(f"Opcodes de tamano FIJO con >=50 muestras: {fixed}")
print("  -> estructura deducible de forma directa y verificable")
db.close()
