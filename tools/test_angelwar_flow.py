import sys
sys.path.insert(0, 'server')
sys.path.insert(0, 'proto')

import struct
import personajes
import login
import clases
import inventario
import cuentas

def test_character_defaults():
    print("1. Testing character creation & defaults...")
    p_dict = personajes.personaje_nuevo("Karmav2", 0, 1001)
    assert p_dict['stage_id'] == 51, f"Expected stage 51, got {p_dict['stage_id']}"
    assert p_dict['tile_x'] == 247 and p_dict['tile_y'] == 24, f"Expected (247, 24), got ({p_dict['tile_x']}, {p_dict['tile_y']})"
    assert p_dict['hp'] == 205 and p_dict['hp_max'] == 205, f"Expected HP 205, got {p_dict['hp']}"
    assert p_dict['mp'] == 154 and p_dict['mp_max'] == 154, f"Expected MP 154, got {p_dict['mp']}"
    assert p_dict['oro'] == 0, f"Expected 0 gold initially, got {p_dict['oro']}"
    print("  PASS: Initial character defaults exactly match AngelWar card select.")

def test_guide_palace_spawns():
    print("2. Testing Guide Palace sequence & NPC positions...")
    p = login.Personaje(char_id=1001, stage=51, tile_x=247, tile_y=24)
    sec = login.secuencia(p)
    npcs = {}
    for sub in sec:
        op = struct.unpack_from('<H', sub, 0)[0]
        if op == 0x0008:
            ent, unk, tx, ty = struct.unpack_from('<IIII', sub, 2)
            name = sub[18:34].split(b'\x00')[0].decode('ascii', 'ignore')
            npcs[name] = (tx, ty)
    
    assert npcs.get('Angel Raphael') == (244, 30), f"Raphael at {npcs.get('Angel Raphael')} instead of (244, 30)"
    assert npcs.get('Interface Tutor') == (236, 27), f"Tutor at {npcs.get('Interface Tutor')} instead of (236, 27)"
    assert npcs.get('Angel Aide') == (252, 27), f"Aide at {npcs.get('Angel Aide')} instead of (252, 27)"
    print("  PASS: Guide Palace NPCs are accurately positioned: Raphael (244, 30), Tutor (236, 27), Aide (252, 27).")

def test_swordsman_class_selection():
    print("3. Testing Swordsman class selection & rewards...")
    # Client sends [09, 0c, 0d, 0f, 10, 21, 0, 0, 0]
    ids = [9, 12, 13, 15, 16, 33]
    # Spells learned
    hechizos = clases.hechizos_iniciales(ids)
    spell_ids = [n for n, _ in hechizos]
    assert spell_ids == [601, 602, 603], f"Expected spells [601, 602, 603], got {spell_ids}"
    
    # Class ID
    cid = clases.class_id(ids[0])
    assert cid == 7, f"Expected Swordsman class_id 7, got {cid}"
    
    # Weapons delivered
    regalo = clases.regalo(ids)
    assert (3, 10) in regalo and (4, 10) in regalo, f"Expected two FreshmanSabre (item 10) in slots 3 & 4, got {regalo}"
    
    # Stats packet 0x0042
    bolsa = {2: 26, 3: 10, 4: 10} # Uniform + dual Sabres
    st_sub = inventario.stats(bolsa, [(sid, 1, 0) for sid in ids], hp=280, hp_max=304, mp=154, mp_max=154, oro=160)
    assert len(st_sub) == 107 # 2 opcode + 105 payload
    hp, hp_max, mp, mp_max = struct.unpack_from('<IIII', st_sub, 2)
    assert (hp, hp_max, mp, mp_max) == (280, 304, 154, 154), f"Stats mismatch: {(hp, hp_max, mp, mp_max)}"
    
    base_atk = struct.unpack_from('<I', st_sub, 2 + 20)[0]
    r_atk = struct.unpack_from('<I', st_sub, 2 + 24)[0]
    l_atk = struct.unpack_from('<I', st_sub, 2 + 28)[0]
    base_def = struct.unpack_from('<I', st_sub, 2 + 32)[0]
    dfs = struct.unpack_from('<I', st_sub, 2 + 36)[0]
    # El offset 100 NO es el oro: es la carga actual. Se comprobo de dos
    # maneras. En la captura de Celestia el 0x0042 lleva el tope en el 92 y
    # en el 96 (los dos 8096) y en el 100 un numero que sube de a uno segun
    # se recoge botin. Y cuando aqui se escribia el oro en el 100, el cliente
    # lo enseñaba como peso: la barra decia "5447/2648" con 5447 de oro. El
    # oro no viaja en este mensaje, sino en la ranura 0 del inventario.
    peso = struct.unpack_from('<I', st_sub, 2 + 100)[0]
    tope = struct.unpack_from('<I', st_sub, 2 + 96)[0]
    assert base_atk == 13, f"Expected base_atk 13, got {base_atk}"
    assert r_atk == 40 and l_atk == 40, f"Expected R.Atk/L.Atk 40/40, got {r_atk}/{l_atk}"
    assert base_def == 12, f"Expected base_def 12, got {base_def}"
    assert dfs == 22, f"Expected Dfs 22, got {dfs}"
    esperado = sum(inventario.peso_de(i) for i in bolsa.values())
    assert peso == esperado, f"Expected weight {esperado}, got {peso}"
    assert tope > 0 and peso <= tope, f"Weight {peso} over cap {tope}"
    print("  PASS: Swordsman rewards, dual Sabres (10), and 0x0042 stats "
          f"(HP 280/304, Atk 40, Dfs 22, peso {peso}/{tope}) verified!")

if __name__ == '__main__':
    test_character_defaults()
    test_guide_palace_spawns()
    test_swordsman_class_selection()
    print("\nALL ANGELWAR STEP-BY-STEP VERIFICATION TESTS PASSED!")

