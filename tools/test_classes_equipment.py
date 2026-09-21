"""
Verificacion de entregas de equipo por clase y preservacion de objetos previos (Students' Uniform).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'server'))

import clases
from app import _con_oro, _nombre_item
import inventario as _iv


def test_classes_weapons():
    test_classes = {
        'Swordsman': ([9, 12, 13, 15, 16, 33], [(3, 10), (4, 10)]),
        'Warrior': ([10, 12, 13, 15, 16, 33], [(3, 19832), (4, 19832)]),
        'Protector': ([10, 14, 12, 13, 15, 33], [(3, 19832), (4, 19820)]),
        'Spearman': ([11, 12, 13, 15, 16, 33], [(3, 19838)]),
        'Bowman': ([17, 12, 13, 15, 16, 33], [(3, 19844), (4, 458)]),
        'Shadowblade': ([32, 12, 13, 15, 16, 33], [(3, 19856), (4, 19856)]),
        'Mage': ([1, 2, 3, 4, 15, 16], [(3, 19850)]),
        'Producer': ([24, 25, 26, 27, 28, 29], [(3, 19814)]),
    }

    for name, (ids, expected) in test_classes.items():
        actual = clases.regalo(ids)
        assert actual == expected, f"Fallo en {name}: esperado {expected}, obtenido {actual}"
        print(f"[PASS] {name}: {actual}")


def test_inventory_preservation():
    # El personaje arranca con oro (0) y Students' Uniform (2: 26)
    inv = {0: 1, 2: 26}
    class MockSes:
        inventario = dict(inv)
        oro = 0

    # Simular eleccion de Warrior (10)
    regalo = clases.regalo([10, 12, 13, 15, 16, 33])
    for ranura, item_id in regalo:
        MockSes.inventario[ranura] = item_id

    # Comprobar que ranura 2 (Uniform) sigue estando equipada
    assert MockSes.inventario.get(2) == 26, "Students' Uniform (26) debe permanecer equipado en ranura 2"
    assert MockSes.inventario.get(3) == 19832, "FreshmanStick debe estar en ranura 3"
    assert MockSes.inventario.get(4) == 19832, "FreshmanStick debe estar en ranura 4"

    # Verificar construccion de 0x001A
    out = _con_oro(MockSes)
    pkt = _iv.completo(1001, out)
    assert len(pkt) > 0, "0x001A debe generarse correctamente"
    print("[PASS] Inventory preservation (Uniform 26 preserved in slot 2)")


if __name__ == '__main__':
    test_classes_weapons()
    test_inventory_preservation()
    print("ALL CLASS REWARD TESTS PASSED!")

