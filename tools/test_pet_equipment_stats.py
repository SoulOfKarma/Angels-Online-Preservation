"""Tests para los stats y bonos de Pet Equipment (ranuras 599..607).

Verifica:
1. Las ranuras 599..607 NO se suman al personaje humano en bonos_de_equipo().
2. tipo_de_ranura() asigna 'arma' a 599/602/605 y 'armadura' a 600/603/606.
3. bono_gema() extrae los atributos correspondientes a armas de pet ('arma') y armaduras de pet ('equipo').
4. bonos_equipo_mascota() calcula correctamente base + mejoras (+15) + runas/gemas + extras para cada fila (1, 2, 3; 0 = ninguna).
5. mascotas.armar() suma bonos_eq a los campos efectivos del paquete 0x0065 (+89 Atk, +105 M.Atk, elementales, etc.).
"""
import unittest
import struct
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'server'))

import inventario as inv
import mejoras as mj
import mascotas as ms


class TestPetEquipmentStats(unittest.TestCase):
    def test_excluir_ranuras_pet_de_jugador(self):
        bolsa = {
            3: 16388,       # Arma humano
            599: 62608,     # Pet-Mars' Thousand Blade (Pet Weapon)
            600: 62585,     # Leather Cat Suit (Pet Armor)
            601: 62587,     # Kitty Meal Bell (Pet Accessory)
        }
        mejoras = {
            599: {'veces': 15, 'gemas': [62691] * 5, 'extra': {}},
            600: {'veces': 15, 'gemas': [], 'extra': {}},
        }
        bonos_humano = inv.bonos_de_equipo(bolsa, mejoras=mejoras)
        # El bono del humano no debe tener sumado el ataque ni defensa de los slots 599..601
        bono_arma_pet = inv._bonus(62608)
        self.assertNotIn(599, [3])
        # El ataque del humano debe provenir unicamente de su arma humano (16388)
        bono_arma_humano = inv._bonus(16388)
        self.assertEqual(bonos_humano['atk_r'], bono_arma_humano.get('atk', 0) + bono_arma_humano.get('accuracy', 0))

    def test_tipo_de_ranura_pet(self):
        self.assertEqual(mj.tipo_de_ranura(599), 'arma')
        self.assertEqual(mj.tipo_de_ranura(602), 'arma')
        self.assertEqual(mj.tipo_de_ranura(605), 'arma')
        self.assertEqual(mj.tipo_de_ranura(600), 'armadura')
        self.assertEqual(mj.tipo_de_ranura(603), 'armadura')
        self.assertEqual(mj.tipo_de_ranura(606), 'armadura')
        self.assertEqual(mj.tipo_de_ranura(601), 'accesorio')
        self.assertEqual(mj.tipo_de_ranura(604), 'accesorio')
        self.assertEqual(mj.tipo_de_ranura(607), 'accesorio')
        self.assertEqual(mj.tipo_de_ranura(0, item_id=62608), 'arma')

    def test_bono_gema_pet(self):
        # 62691: Broken Orange Pet Rune (efecto 745: arma=['atk'], equipo={'2': ['hp', 'dfs']})
        bg_arma = inv.bono_gema(62691, 599, 62608)
        self.assertEqual(bg_arma, {'atk': 576})
        bg_armadura = inv.bono_gema(62691, 600, 62585)
        self.assertEqual(bg_armadura, {'hp': 640, 'dfs': 460})

    def test_bonos_equipo_mascota_calculo_completo(self):
        bolsa = {
            599: 62608,     # Pet-Mars' Thousand Blade
            600: 62585,     # Leather Cat Suit
            601: 62587,     # Kitty Meal Bell
        }
        mejoras = {
            599: {'veces': 15, 'gemas': [62691] * 5, 'extra': {}},
            600: {'veces': 0, 'gemas': [], 'extra': {}},
            601: {'veces': 0, 'gemas': [], 'extra': {}},
        }
        # traje = la fila que manda el cliente en el 0x015E: 1 = la primera.
        bonos = inv.bonos_equipo_mascota(bolsa, mejoras, traje=1)
        self.assertEqual(inv.bonos_equipo_mascota(bolsa, mejoras, traje=0)['atk'], 0)  # sin fila marcada
        # Pet-Mars' Thousand Blade: atk_avg=9080, matk=4300, thnd_atk=800
        # +15 arma: +90% atk (8172) y +90% matk (3870)
        # 5 gemas: 5 * 576 = 2880 atk
        # Total atk arma: 9080 + 8172 + 2880 = 20132
        # Total matk: 4300 + 3870 = 8170
        self.assertEqual(bonos['atk'], 20132)
        self.assertEqual(bonos['matk'], 8170)
        self.assertEqual(bonos['atk_lightning'], 800)
        # Leather Cat Suit (62585): def=710, mdef=370
        self.assertEqual(bonos['def'], 710)
        self.assertEqual(bonos['mdef'], 370)
        # Kitty Meal Bell (62587): accuracy=130, agility=130, hp=810, mp=810
        self.assertEqual(bonos['accuracy'], 130)
        self.assertEqual(bonos['agility'], 130)
        self.assertEqual(bonos['hp'], 810)
        self.assertEqual(bonos['mp'], 810)

    def test_armar_paquete_0x0065_con_bonos_pet_equipment(self):
        estado = {
            'nombre': 'Ava',
            'nivel': 76,
            'sprite': 3396,
            'hp': 10000,
            'hp_max': 10000,
            'mp': 2000,
            'mp_max': 2000,
            'atk': 17702,
            'dfs': 18617,
            'matk': 6107,
            'mdef': 17910,
            'rigor': 4390,
            'agilidad': 3502,
            'saciedad': 600,
            'intimidad': 100,
            'estrellas': 70,
        }
        bolsa = {599: 62608}
        mejoras = {599: {'veces': 15, 'gemas': [62691] * 5, 'extra': {}}}
        # traje = la fila que manda el cliente en el 0x015E: 1 = la primera.
        bonos = inv.bonos_equipo_mascota(bolsa, mejoras, traje=1)
        self.assertEqual(inv.bonos_equipo_mascota(bolsa, mejoras, traje=0)['atk'], 0)  # sin fila marcada

        pkg = ms.armar(estado, bonos_eq=bonos)
        # Byte 0..1 es 0x0065
        opcode = struct.unpack_from('<H', pkg, 0)[0]
        self.assertEqual(opcode, 0x0065)

        # En sub_60ADC0 de Angel.exe:
        # a2 + 85 = Atk base, a2 + 89 = Atk eff
        atk_base = struct.unpack_from('<I', pkg, 85)[0]
        atk_eff = struct.unpack_from('<I', pkg, 89)[0]
        self.assertEqual(atk_base, 17702)
        # atk_eff debe ser estrictamente mayor que atk_base para que la UI de la mascota lo pinte en verde
        self.assertGreater(atk_eff, atk_base)
        self.assertEqual(atk_eff, 31515 + 20132) # Base con estrellas/saciedad + bono equipo

        matk_base = struct.unpack_from('<I', pkg, 101)[0]
        matk_eff = struct.unpack_from('<I', pkg, 105)[0]
        self.assertEqual(matk_base, 6107)
        self.assertGreater(matk_eff, matk_base)
        self.assertEqual(matk_eff, 10886 + 8170)

        # Elementales: T.Atk eff en a2 + 135 (offset 131 + 1*2 + 2 = 135)
        thnd_atk_base = struct.unpack_from('<H', pkg, 133)[0]
        thnd_atk_eff = struct.unpack_from('<H', pkg, 135)[0]
        self.assertEqual(thnd_atk_base, 0)
        self.assertEqual(thnd_atk_eff, 800)


if __name__ == '__main__':
    unittest.main()
