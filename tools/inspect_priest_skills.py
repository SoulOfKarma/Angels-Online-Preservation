"""Buscar las habilidades de Priest/Healer en content.db para ver sus efectos."""
import sqlite3, pathlib

db = pathlib.Path('corpus/content.db')
con = sqlite3.connect(db)

# Buscar magias de curacion y buffs de Priest
print("--- Magias con hp > 0 o nombre de cura/buff ---")
rows = con.execute('select id, name, mp_cost, sp_cost, hp, cool_time, effect_target, effect_caster from magic where name like "%Heal%" or name like "%Bless%" or name like "%Prayer%" or name like "%Light%" or hp > 0 limit 30').fetchall()
for r in rows:
    print(f"ID={r[0]:4s} Name={r[1]:25s} MP={r[2]} SP={r[3]} HP={r[4]} CD={r[5]} target_ef={r[6]} caster_ef={r[7]}")

