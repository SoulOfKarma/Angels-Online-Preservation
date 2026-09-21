"""
Verificacion de la ficha de creacion de personaje y bloque de cuenta.
Garantiza que la respuesta de creacion (0x0001) incluya el bit 0x10000000 en el offset 15 de la ficha,
necesario para que Angel.exe inicialice HP Max = 205, MP Max = 154 y Job = Novice en la tarjeta.
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'server'))

import lista_personajes
import personajes


def test_respuesta_creacion_flags():
    p = personajes.personaje_nuevo('KarmaV5', 2, 1006)
    pkt = personajes.respuesta_creacion(2, p)
    
    assert len(pkt) == 154, f"Longitud esperada 154, obtenida {len(pkt)}"
    op, err = struct.unpack_from('<HH', pkt, 0)
    assert op == 0x0001, f"Opcode esperado 0x0001, obtenido 0x{op:04X}"
    assert err == 0x0000, f"Error esperado 0, obtenido {err}"
    
    # Ficha empieza en offset 4
    # offset 15 de la ficha es pkt[4 + 15 : 4 + 19] = pkt[19 : 23]
    flags = struct.unpack_from('<I', pkt, 19)[0]
    assert (flags & 0x10000000) != 0, f"Bit 0x10000000 debe estar activo, flags=0x{flags:08X}"
    
    # Slot en ficha[0]
    assert pkt[4] == 2, f"Ranura esperada 2, obtenida {pkt[4]}"
    # Nivel en ficha[1:5]
    assert struct.unpack_from('<I', pkt, 5)[0] == 1, "Nivel debe ser 1"
    # Stage id en ficha[11:15]
    assert struct.unpack_from('<I', pkt, 15)[0] == 51, "Stage id debe ser 51 (Guide Palace)"
    print("[PASS] test_respuesta_creacion_flags")


def test_bloque_cuenta_chars():
    p = personajes.personaje_nuevo('KarmaV5', 2, 1006)
    cuenta_payload = lista_personajes.bloque_cuenta([p])
    
    # En bloque_cuenta (sin el opcode 0x0000), las fichas arrancan en payload[3] (5 - 2 = 3)
    f0_flags = struct.unpack_from('<I', cuenta_payload, 3 + 15)[0]
    assert f0_flags == 0, f"En bloque_cuenta las fichas deben tener flags=0, obtenido 0x{f0_flags:08X}"
    
    # El HP Max se manda en el arreglo OFF_HP_MAX
    hp_max = struct.unpack_from('<I', cuenta_payload, lista_personajes.OFF_HP_MAX - 2)[0]
    assert hp_max == 205, f"HP max en bloque_cuenta esperado 205, obtenido {hp_max}"
    print("[PASS] test_bloque_cuenta_chars")


if __name__ == '__main__':
    test_respuesta_creacion_flags()
    test_bloque_cuenta_chars()
    print("ALL CHARACTER CARD TESTS PASSED!")

