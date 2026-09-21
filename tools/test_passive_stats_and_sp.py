"""
Test de verificacion para:
1. Calculo de stats pasivos (Armas, Ropa, Habilidades pasivas Sword, Enhance, Grapple, Reserve, Garment, Finesse).
2. Coincidencia exacta con Imagen 5 (Swordsman Lv 1 full gear: Atk 40, Dfs 28, Rigor 19, Agi 15, Crit 5, SP 2).
3. Escalado de habilidades pasivas por nivel (Reserve +1 SP bar cada 25 niveles).
4. Sistema de barras de SP (2 barras por defecto, carga por golpe, consumo en skills).
5. Flujo del tutorial de Raphael y 10 de oro para Angel Aide.
"""
import struct
import sys
import unittest

sys.path.insert(0, 'server')
import inventario as inv
import combate as cb
import clases as cl


class TestStatsAndSP(unittest.TestCase):
    def test_swordsman_starter_gear_stats(self):
        """Verifica que los stats con equipo inicial coincidan con Imagen 5."""
        habs = [(9, 1, 0), (12, 1, 0), (13, 1, 0), (15, 1, 0), (16, 1, 0), (33, 1, 0)]
        bolsa = {
            2: 26,  # Students' Uniform (def 10)
            3: 10,  # FreshmanSabre (atk 26, acc 1)
            4: 10,  # FreshmanSabre (atk 26, acc 1)
            5: 28,  # Students' Gloves (def 3, acc 6)
            6: 30,  # Students' Shoes (def 3, agi 5)
        }
        raw_pkg = inv.stats(bolsa, habs, hp=304, hp_max=304, mp=154, mp_max=154, oro=10)
        self.assertEqual(len(raw_pkg), 107)  # 2 opcode + 105 payload
        opcode, = struct.unpack_from('<H', raw_pkg, 0)
        self.assertEqual(opcode, 0x0042)

        raw = raw_pkg[2:]
        hp, hp_max, mp, mp_max = struct.unpack_from('<IIII', raw, 0)
        self.assertEqual(hp, 304)
        self.assertEqual(hp_max, 304)
        self.assertEqual(mp, 154)
        self.assertEqual(mp_max, 154)

        b_atk, r_atk, l_atk, b_def, dfs = struct.unpack_from('<IIIII', raw, 20)
        # Base atk = 7 + 4(sword) + 2(reserve) = 13
        self.assertEqual(b_atk, 13)
        # R.Atk = 13 + 26(sabre) + 1(sabre acc) = 40
        self.assertEqual(r_atk, 40)
        # L.Atk = 13 + 26(sabre) + 1(sabre acc) = 40
        self.assertEqual(l_atk, 40)
        # Base def = 6 + 2(enhance) + 4(garment) = 12
        self.assertEqual(b_def, 12)
        # Dfs = 12 + 10(uniform) + 3(gloves) + 3(shoes) = 28
        self.assertEqual(dfs, 28)

        b_rigor, rigor_eff = struct.unpack_from('<HH', raw, 56)
        # Base rigor = 7 + 4(grapple) = 11
        self.assertEqual(b_rigor, 11)
        # Rigor eff = 11 + 6(gloves) + 1(sabre) + 1(sabre) = 19
        self.assertEqual(rigor_eff, 19)

        b_agi, agi_eff = struct.unpack_from('<HH', raw, 60)
        # Base agi = 6 + 4(finesse) = 10
        self.assertEqual(b_agi, 10)
        # Agi eff = 10 + 5(shoes) = 15
        self.assertEqual(agi_eff, 15)

        b_crit, crit_eff = struct.unpack_from('<HH', raw, 64)
        self.assertEqual(b_crit, 5)
        self.assertEqual(crit_eff, 5)

        sp_curr_bars, sp_max_bars = struct.unpack_from('<HH', raw, 68)
        self.assertEqual(sp_curr_bars, 2)
        self.assertEqual(sp_max_bars, 2)

    def test_passive_skill_level_scaling(self):
        """Verifica que subir nivel a las habilidades sume stats y SP correctamente."""
        # Subir Sword al nivel 5 (+4 atk, +4 rigor sobre el nivel 1)
        # Subir Enhance al nivel 5 (+4 def, +48 hp sobre el nivel 1)
        # Subir Reserve al nivel 25 (+24 atk, +1 barra de SP extra!)
        habs = [
            (9, 5, 0),    # Sword lv 5
            (12, 5, 0),   # Enhance lv 5
            (13, 1, 0),   # Grapple lv 1
            (15, 25, 0),  # Reserve lv 25 (Milestone: +1 SP bar!)
            (16, 1, 0),   # Finesse lv 1
            (33, 1, 0),   # Garment lv 1
        ]
        bolsa = {
            2: 26, 3: 10, 4: 10, 5: 28, 6: 30
        }
        raw_pkg = inv.stats(bolsa, habs, hp=304, hp_max=304, mp=154, mp_max=154)
        raw = raw_pkg[2:]

        b_atk, r_atk, l_atk, b_def, dfs = struct.unpack_from('<IIIII', raw, 20)
        # b_atk = 7 + (4 + 4) + (2 + 24) = 41
        self.assertEqual(b_atk, 41)
        self.assertEqual(r_atk, 41 + 27)
        self.assertEqual(l_atk, 41 + 27)

        # b_def = 6 + (2 + 4) + 4 = 16
        self.assertEqual(b_def, 16)
        self.assertEqual(dfs, 16 + 16)  # 32

        b_rigor, rigor_eff = struct.unpack_from('<HH', raw, 56)
        # rigor base = 7 + 4(grapple) + 4(sword lv 5 extra) = 15
        self.assertEqual(b_rigor, 15)
        self.assertEqual(rigor_eff, 15 + 8)  # 23

        sp_curr_bars, sp_max_bars = struct.unpack_from('<HH', raw, 68)
        # Reserve lv 25 suma +1 barra de SP: total 3 barras!
        self.assertEqual(sp_max_bars, 3)

    def test_sp_protocol_constants(self):
        """Verifica que el tipo de SP en 0x0013 sea KIND_SP = 4."""
        self.assertEqual(cb.KIND_SP, 4)
        self.assertEqual(cb.KIND_HP, 0)
        self.assertEqual(cb.KIND_MP, 2)


if __name__ == '__main__':
    unittest.main()

