import unittest
import struct
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / 'server'))
import login
import dialogos
import combate

class TestFightingPalaceTutorial(unittest.TestCase):
    def test_fighting_palace_spawns(self):
        # Verificar que el stage 57 tiene a Little Slarm (224) y a Raphael (500)
        self.assertIn(57, login.PLAYGROUND_MONSTERS)
        slarms = login.PLAYGROUND_MONSTERS[57]
        self.assertGreaterEqual(len(slarms), 2)
        for eid, ntype, nom, tile in slarms:
            self.assertEqual(ntype, 224)
            self.assertEqual(nom, "Little Slarm")
            self.assertTrue(tile[0] > 0 and tile[1] > 0)
        
        spawns_57 = login.poblar(57)
        # Debe contener a Angel Raphael (entidad 500) y a los Little Slarm
        eids = [struct.unpack_from('<I', s, 2)[0] for s in spawns_57 if len(s) >= 6]
        self.assertIn(500, eids)
        self.assertIn(901, eids)

    def test_fighting_palace_dialogues(self):
        # Antes de matar 2 Little Slarm
        g0 = dialogos.guion_fighting_palace(0, "TestHero")
        self.assertIsNotNone(g0)
        # Primera linea debe ser 5048
        mid0 = struct.unpack_from('<I', g0[0], 0)[0]
        self.assertEqual(mid0, 5048)
        # Ultima linea debe ser 5056 con opciones 5058 y 5059
        mid_last = struct.unpack_from('<I', g0[-1], 0)[0]
        self.assertEqual(mid_last, 5056)
        opts = dialogos.opciones_de(g0[-1])
        self.assertEqual(opts, [5058, 5059])

        # Despues de matar 2 Little Slarm
        g2 = dialogos.guion_fighting_palace(2, "TestHero")
        self.assertIsNotNone(g2)
        # Primera linea debe ser 5060
        mid0_g2 = struct.unpack_from('<I', g2[0], 0)[0]
        self.assertEqual(mid0_g2, 5060)
        # Ultima linea debe ser 5062 con opcion 5063 (ir al Lyceum)
        mid_last_g2 = struct.unpack_from('<I', g2[-1], 0)[0]
        self.assertEqual(mid_last_g2, 5062)
        opts_g2 = dialogos.opciones_de(g2[-1])
        self.assertIn(5063, opts_g2)

    def test_dialogue_responses(self):
        # 5063 "I'm ready to go to the Angel Lyceum."
        res_5063 = dialogos.respuesta_a(5063)
        self.assertTrue(len(res_5063) > 0)
        mid = struct.unpack_from('<I', res_5063[0], 2)[0]
        self.assertEqual(mid, 5065)

        # 5059 Quit
        res_5059 = dialogos.respuesta_a(5059)
        self.assertTrue(res_5059[0].endswith(dialogos.FIN))

if __name__ == '__main__':
    unittest.main()

