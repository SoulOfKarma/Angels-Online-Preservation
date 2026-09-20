import sys
import struct
sys.path.insert(0, 'server')
sys.stdout.reconfigure(encoding='utf-8')

print("=== 1. Test Configuracion ===")
import configuracion
print("Tasa EXP base:", configuracion.TASA_EXP_BASE)
print("Multiplicador EXP normal:", configuracion.multiplicador_exp())
print("Multiplicador EXP con tarjeta doble exp:", configuracion.multiplicador_exp({'doble_exp': True}))
print("Multiplicador Skill EXP:", configuracion.multiplicador_skill_exp())

print("\n=== 2. Test Inventario y Mascotas ===")
import inventario as inv
egg_id = 3605 # Fire Elf Egg
print(f"Item {egg_id} es_equipable:", inv.es_equipable(egg_id))
slot = inv.ranura_equipo_de(egg_id)
print(f"Item {egg_id} ranura_equipo_de:", slot)
assert slot == 9, f"Esperaba ranura 9, obtuve {slot}"
sprite = inv.sprite_de_mascota(egg_id)
print(f"Item {egg_id} sprite de mascota:", sprite)
assert sprite > 0, "Sprite debe ser positivo"

print("\n=== 3. Test Combate y EXP ===")
import combate as cb
d_lily = cb._datos(7)
d_slarm = cb._datos(19)
print("Lily stats:", d_lily)
print("Slarm stats:", d_slarm)
assert d_lily['exp'] > 0 and d_slarm['exp'] > 0, "Monstruos deben tener EXP"
exp_slarm = cb.calcular_exp(19)
sk_exp = cb.calcular_skill_exp()
print(f"EXP obtenida de Slarm (con mult {configuracion.multiplicador_exp()}x): {exp_slarm}")
print(f"Skill EXP obtenida: {sk_exp}")
despawn = cb.despawn_monstruo(500)
print("Despawn paquete (0x0007) len:", len(despawn), "hex:", despawn.hex())
assert despawn[:2] == b'\x07\x00', "Debe ser opcode 0x0007"

print("\n=== 4. Test Dialogos y Tiendas ===")
import dialogos
# Scroll Seller entidad 11
res_scroll = dialogos.respuesta_a(12103, entidad=11)
assert len(res_scroll) == 2, "Debe abrir tienda y cerrar dialogo"
shop_id_scroll = struct.unpack_from('<H', res_scroll[0], 2)[0]
assert shop_id_scroll == 17, f"Esperaba Shop 17 para Scroll Seller, obtuve {shop_id_scroll}"


# Magic Seller entidad 19
res_magic = dialogos.respuesta_a(12103, entidad=19)
shop_id_magic = struct.unpack_from('<H', res_magic[0], 2)[0]
print("Magic Seller abre Shop ID:", shop_id_magic)
assert shop_id_magic == 18, f"Esperaba Shop 18 para Magic Seller, obtuve {shop_id_magic}"

# Pet Expert opcion 6102
res_pet_shop = dialogos.respuesta_a(6102, entidad=48)
shop_id_pet = struct.unpack_from('<H', res_pet_shop[0], 2)[0]
print("Pet Expert abre Shop ID:", shop_id_pet)
assert shop_id_pet == 69, f"Esperaba Shop 69 para Pet Expert, obtuve {shop_id_pet}"

# Pet Expert retrato 6101
res_pet_talk = dialogos.respuesta_a(6101, entidad=48, val=4)[0]
val_portrait = struct.unpack_from('<H', res_pet_talk, 6)[0] # mid=LE32@2, val=LE16@6
print("Pet Expert 'Tell me about pets' portrait val:", val_portrait)
assert val_portrait == 48, f"Esperaba portrait 48, obtuve {val_portrait}"

# Angels' Tutor 10110 -> 10123
res_tutor_quit = dialogos.respuesta_a(10110, entidad=25, val=4)[0]
mid_tutor = struct.unpack_from('<I', res_tutor_quit, 2)[0]
print("Angels' Tutor opcion 10110 lleva a mid:", mid_tutor)
assert mid_tutor == 10123, f"Esperaba mid 10123, obtuve {mid_tutor}"

# Angels' Tutor confirmar Yes 10125 -> 10130
res_tutor_yes = dialogos.respuesta_a(10125, entidad=25, val=4)[0]
mid_tutor_grad = struct.unpack_from('<I', res_tutor_yes, 2)[0]
print("Angels' Tutor confirmar 10125 lleva a mid:", mid_tutor_grad)
assert mid_tutor_grad == 10130, f"Esperaba mid 10130, obtuve {mid_tutor_grad}"

print("\nTODOS LOS TESTS PASARON EXITOSAMENTE!")

