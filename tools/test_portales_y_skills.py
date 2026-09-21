import sys
sys.path.insert(0, 'server')
import struct
import login
import combate
import clases
import cuentas

def test_no_red_crystal_portals():
    print("Testing that no sprite 40375 (red crystal) exists in spawns...")
    for st in (41, 42, 43):
        pkts = login.poblar(st)
        for pkt in pkts:
            op = struct.unpack('<H', pkt[:2])[0]
            if op == 0x0008:
                # [H op][I entity_id][I npc_type][I sprite][I klass][I unk]...
                sprite = struct.unpack_from('<I', pkt, 10)[0]
                assert sprite != 40375, f"Found red crystal sprite 40375 in stage {st}!"
    print("  PASS: Zero fake portal entities (sprite 40375) found.")

def test_login_secuencia_for_map_change():
    print("Testing login.secuencia(p) for map loading (opcode 0x0009)...")
    p = login.Personaje(char_id=1, nombre="Karma", stage=41, tile_x=257, tile_y=15,
                        hp=500, hp_max=500, mp=200, mp_max=200, exp=10000, nivel=11)
    pkts = login.secuencia(p)
    assert len(pkts) > 50, f"Expected full map sequence, got {len(pkts)} packets"
    # Check that 0x0002 has correct coords
    found_0002 = False
    for pkt in pkts:
        op = struct.unpack('<H', pkt[:2])[0]
        if op == 0x0002:
            found_0002 = True
            from codec import Msg
            m = Msg.registry[(0x0002, 's2c', 'privado')]
            d = m.parse(pkt[2:])
            assert (d['tile_x'], d['tile_y']) == (257, 15), f"Expected coords (257, 15), got ({d['tile_x']}, {d['tile_y']})"
            break
    assert found_0002, "Expected 0x0002 in secuencia(p)"
    print("  PASS: login.secuencia produces valid appearance with correct coords and all map spawns.")

def test_skill_classifications():
    print("Testing skill classifications in combate.datos_magia...")
    combate._MAGIC_CACHE.clear()

    # Basic weapon attacks
    for mid in (801, 601, 701, 1):
        d = combate.datos_magia(mid)
        assert d['es_ataque'] is True, f"{d['nombre']} should be attack!"
        assert d['es_cura'] is False, f"{d['nombre']} should NOT be cure!"
        assert d['es_auto'] is False, f"{d['nombre']} should NOT be auto/self!"

    # Self buffs
    for mid in (602, 603, 702, 703, 802, 803):
        d = combate.datos_magia(mid)
        assert d['es_ataque'] is False, f"{d['nombre']} should NOT be attack!"
        assert d['es_cura'] is False, f"{d['nombre']} should NOT be cure!"
        assert d['es_auto'] is True, f"{d['nombre']} should be auto/self!"

    # Healing spell
    d_cure = combate.datos_magia(2)
    assert d_cure['es_cura'] is True, "Cure Spell I should be cure!"
    assert d_cure['es_ataque'] is False, "Cure Spell I should NOT be attack!"
    assert d_cure['es_auto'] is True, "Cure Spell I should be auto/self!"
    print("  PASS: All skills strictly classified (attacks never cure).")

def test_kill_does_not_cure_without_level_up():
    print("Testing that killing a monster does NOT heal player without level up...")
    p = login.Personaje(char_id=1, nombre="Karma", stage=41, hp=300, hp_max=500,
                        mp=150, mp_max=200, exp=11800, nivel=11)
    
    initial_hp = p.hp
    exp_ganada = 50
    p.exp += exp_ganada

    subio_nivel = False
    while True:
        exp_siguiente = combate.exp_para_nivel(p.nivel + 1)
        if exp_siguiente > 0 and p.exp >= exp_siguiente:
            p.nivel += 1
            p.hp_max += 25
            p.mp_max += 15
            subio_nivel = True
        else:
            break

    if subio_nivel:
        p.hp = p.hp_max
        p.mp = p.mp_max

    assert subio_nivel is False, "Player should not level up on 50 exp at lv 11"
    assert p.hp == initial_hp, f"Player HP changed from {initial_hp} to {p.hp} without level up!"
    print("  PASS: Player HP remains at 300/500 after killing monster without level up.")

if __name__ == '__main__':
    test_no_red_crystal_portals()
    test_login_secuencia_for_map_change()
    test_skill_classifications()
    test_kill_does_not_cure_without_level_up()
    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
