import unittest
import sys
import asyncio
import struct
import time

sys.path.insert(0, 'server')
import combate as _cb
import dialogos
import app
from session import Session
from login import Personaje

class TestTotemsAndSkills(unittest.TestCase):
    def test_totem_entities(self):
        srv = app.Servidor('127.0.0.1', 9999)
        ses = Session(('127.0.0.1', 12345))
        # Spawns
        self.assertEqual(app._nombre_entidad(ses, 41), 'Aurora Totem')
        self.assertEqual(app._nombre_entidad(ses, 43), 'Iron Totem')
        self.assertEqual(app._nombre_entidad(ses, 44), 'Dark City Totem')
        self.assertEqual(app._nombre_entidad(ses, 45), 'Breeze Totem')
        # Recursos
        self.assertEqual(app._nombre_entidad(ses, 150), 'Aurora Totem')
        self.assertEqual(app._nombre_entidad(ses, 121), 'Iron Totem')
        self.assertEqual(app._nombre_entidad(ses, 122), 'Dark City Totem')
        self.assertEqual(app._nombre_entidad(ses, 120), 'Breeze Totem')

    def test_totem_dialogues(self):
        # Un totem dice SIEMPRE su frase, sea cual sea la faccion. Antes,
        # con faccion Heaven, devolvia el 10201, que es el dialogo del Angel
        # Protector ("I'm the Angel Protector from Aurora City") y se veia al
        # hablarle al totem del Lyceum.
        for faccion in ("Heaven", "Aurora", "Dark"):
            for nombre, esperado in (('Aurora Totem', 5136),
                                     ('Dark City Totem', 5137),
                                     ('Iron Totem', 5138),
                                     ('Breeze Totem', 5139)):
                d = dialogos.propio(nombre, faccion=faccion)
                self.assertIsNotNone(d)
                self.assertEqual(struct.unpack_from('<I', d[0], 0)[0], esperado,
                                 f'{nombre} con faccion {faccion}')

        # Confirm choice option 10205 maps correctly for all entities
        resp_41 = dialogos.respuesta_a(10205, entidad=41)
        self.assertEqual(struct.unpack_from('<I', resp_41[0], 2)[0], 10231)
        resp_150 = dialogos.respuesta_a(10205, entidad=150)
        self.assertEqual(struct.unpack_from('<I', resp_150[0], 2)[0], 10231)

    def test_skill_effects_and_data(self):
        # Swiftness Song 602
        d602 = _cb.datos_magia(602)
        self.assertEqual(d602['efecto'], 133)
        self.assertEqual(d602['mp'], 15)
        self.assertTrue(d602['es_buff'])
        self.assertFalse(d602['es_cura'])
        self.assertFalse(d602['es_ataque'])

        # Slicing Hit 601
        d601 = _cb.datos_magia(601)
        self.assertEqual(d601['efecto'], 136)
        self.assertTrue(d601['es_ataque'])

        # Swift Slash 606
        d606 = _cb.datos_magia(606)
        self.assertEqual(d606['efecto'], 151)
        self.assertTrue(d606['es_ataque'])

        # Cure Spell 2
        d2 = _cb.datos_magia(2)
        self.assertEqual(d2['efecto'], 17)
        self.assertTrue(d2['es_cura'])

        # Test phase separation
        p_ini = _cb.efecto_magia_self_inicio(1001, 133, 602, 100)
        self.assertEqual(p_ini[0:2], bytes([0x11, 0x00]))
        self.assertEqual(p_ini[2], 133)
        self.assertEqual(p_ini[3], 0x00) # fase 0x00

        p_fin = _cb.efecto_magia_self_fin(1001, 133, 602)
        self.assertEqual(p_fin[2], 133)
        self.assertEqual(p_fin[3], 0x80) # fase 0x80

    def test_regen_passive(self):
        srv = app.Servidor('127.0.0.1', 9999)
        ses = Session(('127.0.0.1', 12345))
        p = Personaje(char_id=1, nombre='Karma', hp=100, hp_max=280, mp=50, mp_max=154, stage=41)
        p.entity_id = 1001
        ses.personaje = p

        async def run_regen():
            task = asyncio.create_task(srv._bucle_regeneracion(ses))
            await asyncio.sleep(2.2)
            self.assertGreater(p.mp, 50)
            self.assertGreater(p.hp, 100)
            ses.sentado = True
            mp_sit_before = p.mp
            await asyncio.sleep(1.2)
            self.assertGreater(p.mp, mp_sit_before)
            task.cancel()

        asyncio.run(run_regen())

if __name__ == '__main__':
    unittest.main()

