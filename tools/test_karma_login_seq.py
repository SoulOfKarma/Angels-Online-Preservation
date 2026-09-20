import sys
sys.path.insert(0, 'server')
import json, struct
import login, cuentas

c = cuentas.cargar()
p_dict = c['cuentas']['karma']['personajes'][0]
print("Personaje:", p_dict['nombre'], "char_id:", p_dict['char_id'])

# Crear objeto Personaje
p = login.Personaje(
    entity_id=1001,
    char_id=p_dict['char_id'],
    nombre=p_dict['nombre'],
    nivel=p_dict.get('nivel', 1),
    stage=p_dict.get('stage_id', 41),
    tile_x=p_dict.get('tile_x', 154),
    tile_y=p_dict.get('tile_y', 79),
    hp=p_dict.get('hp', 396),
    hp_max=p_dict.get('hp_max', 396),
    mp=p_dict.get('mp', 232),
    mp_max=p_dict.get('mp_max', 278),
    oro=p_dict.get('oro', 277),
    exp=p_dict.get('exp', 3010),
    tutorial=p_dict.get('tutorial', 1),
    habilidades=p_dict.get('habilidades', []),
    inventario=p_dict.get('inventario', {}),
    faction=p_dict.get('faction', 'Heaven'),
)

sec = login.secuencia(p)
print(f"Total paquetes en secuencia: {len(sec)}")
for idx, s in enumerate(sec):
    op = struct.unpack_from('<H', s, 0)[0]
    print(f"  [{idx:2d}] opcode=0x{op:04X} ({op:3d}) len={len(s)}")

