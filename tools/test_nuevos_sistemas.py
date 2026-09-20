import sys
sys.path.insert(0, 'server')
sys.stdout.reconfigure(encoding='utf-8')
import struct
import combate as cb
import dialogos as dlg

print("=== Test 1: Habilidades de Healer / Curacion ===")
# Magia 601 (Slicing Hit I) es ataque, no cura
d_mag601 = cb.datos_magia(601)
assert d_mag601.get('es_ataque') is True and d_mag601.get('es_cura') is False
print(f"Magia 601 ({d_mag601.get('nombre')}): es_ataque=True, es_cura=False (OK)")

# Magia 2 (Cure Spell I) es curacion
d_mag2 = cb.datos_magia(2)
assert d_mag2.get('es_cura') is True
print(f"Magia 2 ({d_mag2.get('nombre')}): es_cura=True (OK)")

# Efecto de curacion (2 fases: 0x00 y 0x80)
ef_cura = cb.efecto_curacion(1001, 1001, 50, efecto=165)
assert len(ef_cura) == 2
assert ef_cura[0][:2] == b'\x11\x00'
assert ef_cura[1][:2] == b'\x11\x00'
assert ef_cura[0][3] == 0x00  # Fase 0x00
assert ef_cura[1][3] == 0x80  # Fase 0x80
print("Efecto de curacion 0x0011 con 2 fases (0x00 y 0x80) generado correctamente.")


print("\n=== Test 2: Paquetes nativos de EXP y Atributos ===")
# Barra de Exp del jugador: 0x0013 kind=4
attr_exp = cb.atributo(1001, 1500, cb.KIND_EXP)
ent, cnt, kind, val = struct.unpack_from('<IBBI', attr_exp, 2)
assert kind == 4 and val == 1500
print(f"Atributo EXP 0x0013: kind={kind}, val={val} (OK)")

# Skill Exp nativo para el chat
sk_pkg = cb.skill_exp_paquete(1001, 25)
s_op, s_ent, s_kind, s_val = struct.unpack_from('<HIBI', sk_pkg, 0)
assert s_op == 0x000B and s_kind == 4 and s_val == 25
print(f"Paquete Skill Exp 0x000B: op=0x{s_op:04X}, kind={s_kind}, val={s_val} (OK)")

print("\n=== Test 3: Dialogos y NPCs Nuevos ===")
# Repair Angel
res_repair = dlg.respuesta_a(5101, entidad=10)
op_rep = struct.unpack_from('<H', res_repair[0], 0)[0]
assert op_rep == 0x004F, f"Esperaba 0x004F para Repair, obtuve {hex(op_rep)}"
print(f"Repair Angel opcion 5101 abre ventana de reparacion (0x{op_rep:04X}) (OK)")

# Cupid Savepoint
res_cupid = dlg.respuesta_a(5747, entidad=33)
assert len(res_cupid) == 2
print("Cupid opcion 5747 confirma revival point y cierra dialogo (OK)")

# Director Wolay en Heaven vs Faccion elegida
dlg_wolay_heaven = dlg.propio('Director Wolay', faccion='Heaven')
mid_w_h = struct.unpack_from('<I', dlg_wolay_heaven[0], 0)[0]
assert mid_w_h == 10004, f"Esperaba 10004 para Wolay en Heaven, obtuve {mid_w_h}"
print("Director Wolay da bienvenida 10004 en faccion Heaven (OK)")

dlg_wolay_aurora = dlg.propio('Director Wolay', faccion='Aurora')
mid_w_a = struct.unpack_from('<I', dlg_wolay_aurora[0], 0)[0]
assert mid_w_a == 5079, f"Esperaba 5079 para Wolay en Aurora, obtuve {mid_w_a}"
print("Director Wolay ofrece retorno 5079 en faccion Aurora (OK)")

# Angels' Tutor saludo inicial
dlg_tutor = dlg.propio("Angels' Tutor")
mid_tutor = struct.unpack_from('<I', dlg_tutor[0], 0)[0]
assert mid_tutor == 10101, f"Esperaba 10101 para Tutor, obtuve {mid_tutor}"
print("Angels' Tutor inicia con dialogo 10101 ('I am your tutor in the Angel Lyceum') (OK)")

print("\n¡TODAS LAS VERIFICACIONES PASARON EXITOSAMENTE!")

