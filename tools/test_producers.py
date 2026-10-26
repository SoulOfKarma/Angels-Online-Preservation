import asyncio
import pathlib
import struct
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'server'))

import app
import clases
import house_services as hs
import inventario as inv
import skills


class MockPersonaje:
    def __init__(self, char_id=1, nombre="TestCraft", nivel=20, habilidades=None, stage=41):
        self.char_id = char_id
        self.nombre = nombre
        self.nivel = nivel
        self.exp = 1000
        self.habilidades = habilidades or []
        self.banco_habilidades = {}
        self.stage = stage
        self.entity_id = 100
        self.tile_x = 10
        self.tile_y = 10
        self.buffs = {}
        self.class_id = skills.calcular_class_id(self.habilidades)
        self.hp = 500
        self.hp_max = 500
        self.mp = 500
        self.mp_max = 500
        self.barra = []
        self.mejoras = {}


class MockSession:
    def __init__(self, personaje, inventario=None):
        self.personaje = personaje
        self.inventario = inventario or {}
        self.cantidades = {k: 1 for k in self.inventario}
        self.sent = []
        self.rol = 'mundo'
        self.conectado = True
        self.usuario = 'test_user'

    def enviar(self, *pkgs):
        self.sent.extend(pkgs)

    def enviar_inmediato(self, *pkgs):
        self.sent.extend(pkgs)

    def volcar(self):
        pass


class TestProducers(unittest.TestCase):

    def test_calcular_class_id_producer_classes(self):
        # 1. Weaponsmith (26) with Sword (9)
        self.assertEqual(skills.calcular_class_id([26, 22, 24, 25, 9]), 10)
        # 2. Armorsmith (27)
        self.assertEqual(skills.calcular_class_id([27, 22, 23]), 11)
        # 3. Tailor (28)
        self.assertEqual(skills.calcular_class_id([28, 20]), 12)
        # 4. Chef (31) with Mantle (32) (exact setup from screenshot)
        self.assertEqual(skills.calcular_class_id([20, 21, 24, 25, 31, 32]), 15)
        # 5. Technician / Craft (29)
        self.assertEqual(skills.calcular_class_id([29, 24, 25]), 13)
        # 6. Miner (22)
        self.assertEqual(skills.calcular_class_id([22, 24, 25]), 19)
        # 7. Producer (20, 21, 23, 25)
        self.assertEqual(skills.calcular_class_id([20, 21, 23, 25]), 20)
        # 8. Pure combat: Swordsman (9), Warrior (10), Wizard Jr (1, 2, 3)
        self.assertEqual(skills.calcular_class_id([9, 12, 13]), 7)
        self.assertEqual(skills.calcular_class_id([10, 12, 13]), 6)
        self.assertEqual(skills.calcular_class_id([1, 2, 3]), 16)

    def test_gathering_skill_and_level_requirement(self):
        # Material 4: Tin(S) requires Dig (22) level 11
        pj = MockPersonaje(nivel=20, habilidades=[(22, 5, 0)]) # Dig lv 5
        ses = MockSession(pj, {3: 21}) # Tool 21 is Moyle (pickaxe) in weapon slot 3

        # Node check for ent with material 4
        with patch.object(app, '_veta_de', return_value=(4, (10 * 32, 10 * 32))), \
             patch.object(app, '_cuenta_de_veta', return_value=[0, 0.0]):
            res = app._recolectar(ses, '127.0.0.1:1000', 41, 1001)
            self.assertTrue(res)
            # Gathering should be blocked because Dig level 5 < 11
            self.assertFalse(hasattr(ses, 'recoleccion') and ses.recoleccion is not None)
            # aviso_doble(356, "Dig", "11") should be sent
            has_356 = any(len(p) >= 5 and struct.unpack_from('<HH', p)[1] == 356 for p in ses.sent)
            self.assertTrue(has_356)

        # Now level up Dig to 11
        pj.habilidades = [(22, 11, 0)]
        ses.sent.clear()
        with patch.object(app, '_veta_de', return_value=(4, (10 * 32, 10 * 32))), \
             patch.object(app, '_cuenta_de_veta', return_value=[0, 0.0]), \
             patch('asyncio.get_event_loop'):
            res = app._recolectar(ses, '127.0.0.1:1000', 41, 1001)
            self.assertTrue(res)
            self.assertIsNotNone(ses.recoleccion)
            # MSG_EMPIEZA_RECOLECCION (345) and 0x000A sent
            has_000a = any(len(p) >= 2 and struct.unpack_from('<H', p)[0] == 0x000A for p in ses.sent)
            self.assertTrue(has_000a)

    def test_gathering_robot_ride_optimization_and_exp(self):
        # Robot mount (item 19814 FreshmanCask, category 機甲) in mount slot 10
        # Character has Dig (22), Mechanism (24), and Drive (25)
        pj = MockPersonaje(nivel=20, habilidades=[(22, 1, 0), (24, 1, 0), (25, 15, 0)])
        ses = MockSession(pj, {10: 19814}) # Robot mounted, no pickaxe needed!

        # 1. Drive skill (level 15) increases gathering speed
        puede, msg, vel = app._herramienta_para(ses, '鐵鍬')
        self.assertTrue(puede)
        self.assertIsNone(msg)
        self.assertGreaterEqual(vel, 3) # drive_lv // 5 = 3 bonus

        # 2. Extracting from node awards skill EXP to Dig, Mechanism, and Drive
        mat = app._material(1) # Copper
        with patch.object(app, '_cuenta_de_veta', return_value=[0, 0.0]), \
             patch.object(app, '_meter', return_value=20), \
             patch.object(app, '_guardar_bolsa'), \
             patch('random.randint', return_value=1), \
             patch('cuentas.guardar_progreso'):
            app._sacar_de_veta(ses, '127.0.0.1:1000', 41, 1001, mat, 1)

            # Check that skills in pj.habilidades gained EXP
            dig_exp = next(h[2] for h in pj.habilidades if h[0] == 22)
            mech_exp = next(h[2] for h in pj.habilidades if h[0] == 24)
            drive_exp = next(h[2] for h in pj.habilidades if h[0] == 25)
            self.assertGreater(dig_exp, 0)
            self.assertGreater(mech_exp, 0)
            self.assertGreater(drive_exp, 0)

    def test_crafting_weaponsmith_success_and_exp(self):
        # Recipe 1: requires skill 26 (Weapon) level 1, 1x item 35 (Copper Mine) -> 1x item 52 (Iron Dagger)
        pj = MockPersonaje(nivel=20, habilidades=[(26, 5, 0)])
        ses = MockSession(pj, {20: 35}) # slot 20 has Copper Mine (35)
        ses.cantidades[20] = 1

        callbacks = []
        task = Mock(cancelled=lambda: False)
        loop = Mock(call_later=lambda delay, fn: callbacks.append((delay, fn)) or task)

        with patch('asyncio.get_event_loop', return_value=loop), \
             patch.object(app, '_guardar_bolsa'), \
             patch('cuentas.guardar_progreso'):
            app._fabricar_receta(ses, 1)

        # Delay scheduled
        self.assertTrue(len(callbacks) > 0)
        # Execute finish callback
        callbacks[0][1]()

        # Copper Mine (35) consumed, product 52 created in backpack
        self.assertNotIn(35, ses.inventario.values())
        self.assertIn(52, ses.inventario.values())
        # 0x004C success packet sent
        has_004c = any(len(p) == 7 and struct.unpack_from('<HBI', p) == (0x004C, 1, 1) for p in ses.sent)
        self.assertTrue(has_004c)
        # Weapon skill gained skill EXP
        weapon_exp = next(h[2] for h in pj.habilidades if h[0] == 26)
        self.assertGreater(weapon_exp, 0)

    def test_crafting_insufficient_skill_level_rejected(self):
        # Recipe 50 requires skill 26 level 25
        pj = MockPersonaje(nivel=20, habilidades=[(26, 5, 0)]) # only level 5
        ses = MockSession(pj, {20: 53})

        app._fabricar_receta(ses, 50)
        # Rejected with 0x004D
        has_004d = any(len(p) == 2 and struct.unpack_from('<H', p)[0] == 0x004D for p in ses.sent)
        self.assertTrue(has_004d)

    def test_crafting_missing_materials_rejected(self):
        # Recipe 1 requires Copper Mine (35), but inventory has none
        pj = MockPersonaje(nivel=20, habilidades=[(26, 1, 0)])
        ses = MockSession(pj, {20: 9999})

        app._fabricar_receta(ses, 1)
        has_004d = any(len(p) == 2 and struct.unpack_from('<H', p)[0] == 0x004D for p in ses.sent)
        self.assertTrue(has_004d)

    def test_skill_angel_skill_swap_for_producer(self):
        # Character is Chef with Cook (31), wants to swap slot 0 (Cook 31) for Weaponsmith (26)
        pj = MockPersonaje(nivel=20, habilidades=[(31, 10, 50), (20, 5, 0)])
        ses = MockSession(pj)

        # 0x002F container 10: out 31, in 26
        cuerpo = struct.pack('<BII', 10, 31, 26)
        with patch('cuentas.guardar_habilidades'), \
             patch('cuentas.guardar_clase'), \
             patch('cuentas.guardar_banco_habilidades'):
            app.Servidor.manejar(None, ses, 0x002F, None, None, '127.0.0.1:1000', cuerpo)

        # Cook 31 should be saved in banco with level 10, exp 50
        self.assertEqual(pj.banco_habilidades.get(31), [10, 50])
        # Slot 0 now has Weaponsmith (26)
        self.assertEqual(pj.habilidades[0][0], 26)
        # Class recalculated to Weaponsmith (10)
        self.assertEqual(pj.class_id, 10)

    def test_freshman_cask_for_producer_classes(self):
        # 1. Swordsman: no robot mount (slot 10)
        swordsman_regalo = clases.regalo([9, 14, 12, 13, 15, 16])
        self.assertNotIn(19814, [item for slot, item in swordsman_regalo])
        self.assertNotIn(10, [slot for slot, item in swordsman_regalo])

        # 2. Weaponsmith (26): gets Freshman Cask (19814) in slot 10
        weaponsmith_regalo = dict(clases.regalo([26, 22, 24, 25, 9, 14]))
        self.assertEqual(weaponsmith_regalo.get(10), 19814)

        # 3. Chef (31): gets Freshman Cask (19814) in slot 10
        chef_regalo = dict(clases.regalo([31, 21, 24, 25, 32, 16]))
        self.assertEqual(chef_regalo.get(10), 19814)

        # 4. Tailor (28): gets Freshman Cask in slot 10
        tailor_regalo = dict(clases.regalo([28, 20, 24, 25, 30, 31]))
        self.assertEqual(tailor_regalo.get(10), 19814)

        # 5. premio_final also includes Freshman Cask (19814) in slot 10 for producers
        chef_premio = dict(clases.premio_final([31, 21, 24, 25, 32, 16]))
        self.assertEqual(chef_premio.get(10), 19814)
        swordsman_premio = dict(clases.premio_final([9, 14, 12, 13, 15, 16]))
        self.assertNotIn(10, swordsman_premio)

    def test_tutorial_quit_option_5011_warps_to_lyceum(self):
        import dialogos
        # Character in Guide Palace (51), talks to Raphael (19) and selects "Yes." to quit tutorial
        pj = MockPersonaje(nivel=1, habilidades=[(31, 1, 0), (21, 1, 0)], stage=51)
        ses = MockSession(pj, {20: 100})
        ses.dlg_ent = 19
        ses.dlg_guion = [dialogos.armar_linea(5010, 3, [5011, 5012])[2:]]
        ses.dlg_paso = 1

        with patch('cuentas.guardar_inventario'), \
             patch('cuentas.guardar_mapa'):
            app.Servidor.manejar(None, ses, 0x000B, None, {'valor': 10}, '127.0.0.1:1000', b'\x0a')

        # Teleported to Lyceum (41, (152, 74))
        self.assertEqual(pj.stage, 41)
        self.assertEqual((pj.tile_x, pj.tile_y), (152, 74))
        # Received Freshman Cask (19814) in slot 10
        self.assertEqual(ses.inventario.get(10), 19814)
        # Received graduation gloves (28) and shoes (30) in slots 5 and 6
        self.assertEqual(ses.inventario.get(5), 28)
        self.assertEqual(ses.inventario.get(6), 30)



if __name__ == '__main__':
    unittest.main()

