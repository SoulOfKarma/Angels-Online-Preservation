import sys
import os
import json
import struct
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

import dialogos
import misiones
import login
import clases
import combate
import app


class TestPastTheTimeAndQuestRewards(unittest.TestCase):

    def test_past_the_time_spirit_dialogue_level_requirement(self):
        """NPC 24798 (Past the Time Spirit) requires Lv 250."""
        # Under level 250: message 158401
        lineas_bajo = dialogos.propio('Past the Time Spirit', nivel=200)
        self.assertIsNotNone(lineas_bajo)
        self.assertEqual(len(lineas_bajo), 1)
        submsg_id = struct.unpack_from('<I', lineas_bajo[0], 0)[0]
        self.assertEqual(submsg_id, 158401)
        ops = dialogos.opciones_de(lineas_bajo[0])
        self.assertIn(158418, ops)

        # Level 250+: message 158421 with warp and shop options
        lineas_alto = dialogos.propio('Past the Time Spirit', nivel=250)
        self.assertIsNotNone(lineas_alto)
        self.assertEqual(len(lineas_alto), 1)
        submsg_id = struct.unpack_from('<I', lineas_alto[0], 0)[0]
        self.assertEqual(submsg_id, 158421)
        ops = dialogos.opciones_de(lineas_alto[0])
        self.assertIn(158416, ops)  # Chaos-Dinosaur Arena
        self.assertIn(158417, ops)  # Chaos-End Time
        self.assertIn(158514, ops)  # Exchange Time Crystal
        self.assertIn(158418, ops)  # Leave

    def test_stage_308_local_entity_resolves_to_past_not_global_npc_900(self):
        """The real map click uses local entity 900, not npc_type 24798."""
        ses = SimpleNamespace(personaje=SimpleNamespace(stage=308))
        self.assertEqual(app._nombre_entidad(ses, 900), 'Past the Time Spirit')
        spawned = login.npc_de_los_xml(308)
        self.assertEqual(len(spawned), 1)
        pkt = spawned[0]
        self.assertEqual(struct.unpack_from('<I', pkt, 2)[0], 900)
        self.assertEqual(struct.unpack_from('<I', pkt, 36)[0], 40542)
        self.assertEqual(pkt[35], 6)
        self.assertEqual(struct.unpack_from('<I', pkt, 42)[0], 199)
        self.assertEqual(struct.unpack_from('<H', pkt, 47)[0], 24798)

        # The local entity id 900 must not select another NPC's portrait.
        lineas = dialogos.propio('Past the Time Spirit', entidad=900, nivel=250)
        self.assertEqual(struct.unpack_from('<H', lineas[0], 4)[0], 1342)

    def test_past_the_time_spirit_warps_and_exchange(self):
        """Test warps and the official Time Crystal exchange group 659."""
        # Warps from Rainbow Town (Stage 308)
        self.assertEqual(dialogos.VIAJES_POR_OPCION.get((308, 158416)), (413, [20, 11]))
        self.assertEqual(dialogos.VIAJES_POR_OPCION.get((308, 158417)), (414, [289, 7]))

        # 659 is an exchange group, not a shop (shop.xml ends at 226).
        self.assertNotIn(158514, dialogos.TIENDAS_POR_OPCION)
        resp_exchange = dialogos.respuesta_a(158514)
        # FUN_005f4890 (S2C 0x0151) receives one u32 exchange-group ID and
        # constructs WND_EXCHANGE from the client's local exchange.xml.
        self.assertEqual(resp_exchange[0], struct.pack('<HI', 0x0151, 659))
        # FUN_005f4ac0 (S2C 0x018B) initializes the per-recipe counters.
        # Without these entries, daily recipes are rendered in red as
        # "Temporary can't exchange" even when the player has materials.
        self.assertEqual(
            resp_exchange[1],
            struct.pack('<HI', 0x018B, 2)
            + struct.pack('<II', 21576, 0)
            + struct.pack('<II', 21577, 0),
        )
        recetas = [21575, 21576, 21577]
        self.assertEqual(recetas, [21575, 21576, 21577])
        for recipe_id in recetas:
            receta = app._obtener_receta_exchange(recipe_id)
            self.assertIsNotNone(receta)
            self.assertTrue(receta['materiales'])
            self.assertTrue(receta['premios'])

        # Close options cleanly return FIN
        resp = dialogos.respuesta_a(158418)
        self.assertEqual(resp, (struct.pack('<H', 0x0012) + dialogos.FIN,))
        resp2 = dialogos.respuesta_a(158515)
        self.assertEqual(resp2, (struct.pack('<H', 0x0012) + dialogos.FIN,))

    def test_chaotic_instances_portals_and_templates(self):
        """Verify Stage 413 and 414 templates and portals."""
        self.assertIn(413, login.PLANTILLAS_POR_STAGE)
        self.assertIn(414, login.PLANTILLAS_POR_STAGE)
        self.assertEqual(login.PLANTILLAS_POR_STAGE[413], 'c_dinosaur_arena.json')
        self.assertEqual(login.PLANTILLAS_POR_STAGE[414], 'c_end_time.json')

        # Portals
        f_port = os.path.join(os.path.dirname(__file__), '..', 'server', 'plantillas', 'portales.json')
        with open(f_port, encoding='utf-8') as fp:
            portales = json.load(fp).get('mapas', {})
        self.assertIn('413', portales)
        self.assertIn('414', portales)

        # 413 exit to 308
        exit_413 = [p for p in portales['413'] if p['destino'] == 308]
        self.assertTrue(len(exit_413) > 0)
        self.assertEqual(exit_413[0]['tile'], [9, 6])
        self.assertEqual(exit_413[0]['llegada'], [165, 77])

        # 414 exit to 308
        exit_414 = [p for p in portales['414'] if p['destino'] == 308]
        self.assertTrue(len(exit_414) > 0)
        self.assertEqual(exit_414[0]['tile'], [295, 2])
        self.assertEqual(exit_414[0]['llegada'], [165, 77])

        # Verify monster templates have spawns and bosses
        f_413 = os.path.join(os.path.dirname(__file__), '..', 'server', 'plantillas', 'c_dinosaur_arena.json')
        with open(f_413, encoding='utf-8') as f:
            d413 = json.load(f)
        self.assertGreater(len(d413['spawns']), 300)
        mob_names_413 = {s['nombre'] for s in d413['spawns']}
        self.assertIn('C-Dragon Emperor', mob_names_413)
        self.assertIn('C-Cartastolov', mob_names_413)

        f_414 = os.path.join(os.path.dirname(__file__), '..', 'server', 'plantillas', 'c_end_time.json')
        with open(f_414, encoding='utf-8') as f:
            d414 = json.load(f)
        self.assertGreater(len(d414['spawns']), 300)
        mob_names_414 = {s['nombre'] for s in d414['spawns']}
        self.assertIn('C-Ghost King', mob_names_414)
        self.assertIn('C-Time Lady', mob_names_414)
        self.assertIn("Ba'shin", mob_names_414)

    def test_quest_976_rewards_scaling_and_items(self):
        """Test Quest 976 EXP scaling by level, Weekly Quest Mark item, and no pay gold message."""
        char_id = 99999
        personaje = SimpleNamespace(
            char_id=char_id,
            entity_id=char_id,
            nombre='TestHero',
            nivel=95,
            exp=0,
            oro=1000,
            creditos=100,
            rango=1,
            quests=[(976, 8)],
            misiones_completas=[],
            misiones_progreso={},
            inventario={},
            cantidades={},
            mejoras={},
        )
        sesion = SimpleNamespace(
            char_id=char_id,
            entity_id=char_id,
            usuario='testuser',
            personaje=personaje,
            oro=1000,
            inventario={},
            cantidades={},
            tokens_mision={},
            enviados=[],
            enviar=lambda *pkts: sesion.enviados.extend(pkts)
        )

        # Complete Quest 976 for level 95 player
        res = misiones.completar_mision(sesion, 976)
        self.assertTrue(res)
        
        # Level 95: 72,000,000 EXP
        self.assertEqual(personaje.exp, 72000000)

        # Item 12611 (Weekly Quest Mark) was granted
        self.assertIn(12611, personaje.inventario.values())

        # Gold was NOT deducted (oro should remain 1000)
        self.assertEqual(sesion.oro, 1000)

        # Verify no MSG_PAGO (500) packet was generated
        for pkt in sesion.enviados:
            if len(pkt) >= 4 and struct.unpack_from('<H', pkt, 0)[0] == 0x000D:
                msg_id = struct.unpack_from('<H', pkt, 2)[0]
                self.assertNotEqual(msg_id, clases.MSG_PAGO, "Must NOT send MSG_PAGO when completing quest")

        # Now test level 92 scaling (48,000,000 EXP)
        personaje.nivel = 92
        personaje.exp = 0
        personaje.inventario = {}
        sesion.inventario = {}
        personaje.quests = [(976, 8)]
        misiones.completar_mision(sesion, 976)
        self.assertEqual(personaje.exp, 48000000)

        # Now test level 85 scaling (36,000,000 EXP)
        personaje.nivel = 85
        personaje.exp = 0
        personaje.inventario = {}
        sesion.inventario = {}
        personaje.quests = [(976, 8)]
        misiones.completar_mision(sesion, 976)
        self.assertEqual(personaje.exp, 36000000)


if __name__ == '__main__':
    unittest.main()
