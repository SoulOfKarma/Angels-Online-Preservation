import sys
import struct
import pathlib

# Ensure server is in sys.path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'server'))

import dialogos
import clases
import inventario as inv

def test_tutorial_dialogues():
    print("--- 1. Testing Interface Tutor Dialogue ---")
    g_tutor = dialogos.guion_etapa(20, 0)
    assert g_tutor is not None, "Tutor guion not found"
    assert len(g_tutor) == 12, f"Expected 12 lines for Tutor, got {len(g_tutor)}"
    
    # Line 0 should be 5240 with options 5241 and 5242
    mid_0 = struct.unpack_from('<I', g_tutor[0], 0)[0]
    ops_0 = dialogos.opciones_de(g_tutor[0])
    assert mid_0 == 5240, f"Expected 5240, got {mid_0}"
    assert ops_0 == [5241, 5242], f"Expected [5241, 5242], got {ops_0}"
    
    # Lines 1 to 11 should be 5243 to 5253
    for idx, expected_id in enumerate(range(5243, 5254), start=1):
        mid = struct.unpack_from('<I', g_tutor[idx], 0)[0]
        assert mid == expected_id, f"Line {idx}: expected {expected_id}, got {mid}"
    print("Interface Tutor 12 lines verified successfully!")

    print("\n--- 2. Testing Angel Aide Conditional Dialogue ---")
    # Etapa 0: 0 gold or tutorial < 2 -> 5022 with 0 options
    g_aide_0 = dialogos.guion_etapa(21, 0)
    mid_a0 = struct.unpack_from('<I', g_aide_0[0], 0)[0]
    ops_a0 = dialogos.opciones_de(g_aide_0[0])
    assert mid_a0 == 5022, f"Expected 5022, got {mid_a0}"
    assert len(ops_a0) == 0, f"Expected 0 options for Aide etapa 0, got {ops_a0}"
    print("Aide etapa 0 (0 options) verified!")

    # Etapa 1: tutorial >= 2 and oro >= 10 -> 5022 with options 5045, 5046
    g_aide_1 = dialogos.guion_etapa(21, 1)
    mid_a1 = struct.unpack_from('<I', g_aide_1[0], 0)[0]
    ops_a1 = dialogos.opciones_de(g_aide_1[0])
    assert mid_a1 == 5022, f"Expected 5022, got {mid_a1}"
    assert ops_a1 == [5045, 5046], f"Expected [5045, 5046] for Aide etapa 1, got {ops_a1}"
    print("Aide etapa 1 (Buy/Quit options) verified!")

    # Etapa 2: has item 1386 -> 5047 with 0 options
    g_aide_2 = dialogos.guion_etapa(21, 2)
    mid_a2 = struct.unpack_from('<I', g_aide_2[0], 0)[0]
    ops_a2 = dialogos.opciones_de(g_aide_2[0])
    assert mid_a2 == 5047, f"Expected 5047, got {mid_a2}"
    assert len(ops_a2) == 0, f"Expected 0 options for Aide etapa 2, got {ops_a2}"
    print("Aide etapa 2 (5047 Good for you!) verified!")

    print("\n--- 3. Testing Angel Raphael Dialogue Stages ---")
    # Stage 0: 5001..5005
    g_raph_0 = dialogos.guion_etapa(19, 0)
    assert len(g_raph_0) == 5
    assert [struct.unpack_from('<I', l, 0)[0] for l in g_raph_0] == [5001, 5002, 5003, 5004, 5005]
    print("Raphael Stage 0 verified!")

    # Stage 1: 5006, 5007 (opts 5008, 5009), 5014..5018
    g_raph_1 = dialogos.guion_etapa(19, 1)
    assert len(g_raph_1) == 7
    ids_1 = [struct.unpack_from('<I', l, 0)[0] for l in g_raph_1]
    assert ids_1 == [5006, 5007, 5014, 5015, 5016, 5017, 5018], f"Got {ids_1}"
    ops_5007 = dialogos.opciones_de(g_raph_1[1])
    assert ops_5007 == [5008, 5009], f"Expected [5008, 5009], got {ops_5007}"
    print("Raphael Stage 1 verified!")

    # Option 5009 response: 5010 with [5011, 5012]
    res_5009 = dialogos.respuesta_a(5009)
    assert len(res_5009) == 1
    mid_5010 = struct.unpack_from('<I', res_5009[0], 2)[0]
    assert mid_5010 == 5010, f"Expected 5010, got {mid_5010}"
    ops_5010 = dialogos.opciones_de(res_5009[0][2:])
    assert ops_5010 == [5011, 5012], f"Expected [5011, 5012], got {ops_5010}"
    print("Raphael Option 5009 -> 5010 ([5011, 5012]) verified!")

    # Stage 2: 5021, 5039..5043
    g_raph_2 = dialogos.guion_etapa(19, 2)
    assert len(g_raph_2) == 6
    ids_2 = [struct.unpack_from('<I', l, 0)[0] for l in g_raph_2]
    assert ids_2 == [5021, 5039, 5040, 5041, 5042, 5043], f"Got {ids_2}"
    print("Raphael Stage 2 (Buying goods + 10 Gold) verified!")

    # Stage 3: 5048..5054
    g_raph_3 = dialogos.guion_etapa(19, 3)
    assert len(g_raph_3) == 7
    ids_3 = [struct.unpack_from('<I', l, 0)[0] for l in g_raph_3]
    assert ids_3 == [5048, 5049, 5050, 5051, 5052, 5053, 5054], f"Got {ids_3}"
    print("Raphael Stage 3 (Final exam delivery & battle tutorial) verified!")

    print("\n--- 4. Testing Swordsman Class Reward ---")
    regalo = clases.regalo([9, 12, 13, 15, 16, 33])
    assert regalo == [(3, 10), (4, 10)], f"Expected only weapons [(3, 10), (4, 10)], got {regalo}"
    print("Swordsman weapons: [(3, 10), (4, 10)] without duplicate clothes verified!")

    print("\nALL AUTOMATED TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    test_tutorial_dialogues()

