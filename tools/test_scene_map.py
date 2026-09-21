import unittest
import struct
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'server'))
import login

class TestSceneMap(unittest.TestCase):
    def test_opcode_0014_map_flags_bit20(self):
        """Verifica que el opcode 0x0014 conserve los flags de mapa oficiales (0x0205)

        y NO tenga el bit 0x20 encendido, ya que Angel.exe lo interpreta como 'desactivar mapa'.
        """
        p = login.Personaje(entity_id=1003, stage=41)
        submsgs = login.secuencia(p)
        
        op14_found = False
        for sub in submsgs:
            op = struct.unpack_from('<H', sub, 0)[0]
            if op == 0x0014:
                op14_found = True
                flags = struct.unpack_from('<I', sub, 2)[0]
                self.assertEqual(flags & 0x20, 0, f"Bit 0x20 no debe estar encendido en flags de mapa (flags={flags:08x})")
                self.assertEqual(flags, 0x0205, f"Flags de mapa esperados 0x0205, se obtuvo {flags:08x}")
                break
        
        self.assertTrue(op14_found, "No se encontro el sub-mensaje 0x0014 en la secuencia")

    def test_poblar_stage_41_contains_npcs_and_resources(self):
        """Verifica que en el stage 41 se envien los spawns de NPC (0x0008) y recursos (0x000E)."""
        p = login.Personaje(entity_id=1001, stage=41)
        submsgs = login.secuencia(p)
        ops = [struct.unpack_from('<H', sub, 0)[0] for sub in submsgs]
        
        self.assertIn(0x0008, ops, "Debe enviar 0x0008 (NPC spawns) para poblar el mapa")
        self.assertIn(0x000E, ops, "Debe enviar 0x000E (recursos) para poblar el mapa")

if __name__ == '__main__':
    unittest.main()

