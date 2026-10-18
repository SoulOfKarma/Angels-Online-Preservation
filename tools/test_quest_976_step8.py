import unittest
import struct
import sys
import os

# Ensure server module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'server')))

import inventario as inv
import misiones as mis
import cuentas


class DummyPersonaje:
    def __init__(self, char_id=4980, entity_id=1234, nombre="Tester"):
        self.char_id = char_id
        self.entity_id = entity_id
        self.nombre = nombre
        self.nivel = 100
        self.exp = 0
        self.oro = 1000
        self.quests = [(976, 8)]
        self.quest_kills = {}
        self.mejoras = {}
        self.mascota = None
        self.mascotas = {}
        self.stage = 88


class DummySession:
    def __init__(self, p=None):
        self.personaje = p or DummyPersonaje()
        self.entity_id = self.personaje.entity_id
        self.char_id = self.personaje.char_id
        self.inventario = {}
        self.cantidades = {}
        self.instancias = {}
        self.quest_kills = self.personaje.quest_kills
        self.usuario = "test_user"
        self.enviados = []

    def enviar(self, *paquetes):
        for p in paquetes:
            if isinstance(p, (bytes, bytearray)):
                self.enviados.append(bytes(p))


class TestQuest976Step8AndCrashFix(unittest.TestCase):

    def setUp(self):
        mis._cargar_db()

    def test_actualizar_ranura_zero_item_safety(self):
        """0x001B must never serialize an item entry with item_id == 0."""
        # When item_id == 0, actualizar_ranura must return vaciar_ranura instead of updating with 0
        pkg = inv.actualizar_ranura(4980, 43, 0, 1)
        # vaciar_ranura is [u16 0x001B][u32 1][u8 2 = VACIAR]...
        op, n, sub_op = struct.unpack_from('<HIB', pkg, 0)
        self.assertEqual(op, 0x001B)
        self.assertEqual(sub_op, 2)  # 2 is empty slot

        # Plural actualizar_ranuras must skip entries with item_id <= 0
        pkg_pl = inv.actualizar_ranuras(4980, [(43, 12605, 1, None), (50, 0, 1, None)])
        op, count = struct.unpack_from('<HI', pkg_pl, 0)
        self.assertEqual(op, 0x001B)
        self.assertEqual(count, 1)  # Only 1 entry (12605), entry with 0 skipped!

    def test_verificar_botin_mision_boss_drops(self):
        """Each of the 5 bosses must drop its own specific Life Diamond piece."""
        ses = DummySession()
        ses.inventario = {}

        # 1. Destroyer Wesley (4491) -> 12609 (Life Diamond Core)
        drops = mis.verificar_botin_mision(ses, 4491, "Destroyer Wesley")
        self.assertEqual(drops, [(12609, 1)])

        # Once player has 12609, Wesley drops nothing further
        ses.inventario[42] = 12609
        drops = mis.verificar_botin_mision(ses, 4491, "Destroyer Wesley")
        self.assertEqual(drops, [])

        # 2. Sword Jellyfish (1220) -> 12605 (Life Diamond Shard)
        drops = mis.verificar_botin_mision(ses, 1220, "Sword Jellyfish")
        self.assertEqual(drops, [(12605, 1)])

        # 3. Leech Mrs. Dorsa (3587) -> 12606 (Life Diamond Chunk)
        drops = mis.verificar_botin_mision(ses, 3587, "Leech Mrs. Dorsa")
        self.assertEqual(drops, [(12606, 1)])

        # 4. Hermit Hezon (3596) -> 12607 (Life Diamond Fragment)
        drops = mis.verificar_botin_mision(ses, 3596, "Hermit Hezon")
        self.assertEqual(drops, [(12607, 1)])

        # 5. Purple Scorpion Issac (4483) -> 12608 (Life Diamond Chip)
        drops = mis.verificar_botin_mision(ses, 4483, "Purple Scorpion Issac")
        self.assertEqual(drops, [(12608, 1)])

    def test_boss_kill_does_not_advance_step_prematurely(self):
        """Killing Wesley or other bosses must not advance step 8 to 9 (it requires collection & turn-in)."""
        ses = DummySession()
        ses.inventario = {}
        # registrar_baja_monstruo should return False since 976_8 is now in _RECOLECCIONES
        updated = mis.registrar_baja_monstruo(ses, 4491, "Destroyer Wesley")
        self.assertFalse(updated)
        # Quest must still be at (976, 8)
        self.assertEqual(ses.personaje.quests, [(976, 8)])

    def test_verificar_entrega_items_and_pop(self):
        """verificar_entrega_items requires all 5 pieces and consumes them without leaving zeros."""
        ses = DummySession()
        # Missing pieces
        ses.inventario = {42: 12609, 43: 12605}
        self.assertFalse(mis.verificar_entrega_items(ses, 976, 8))

        # Give all 5 pieces
        ses.inventario = {
            20: 12605,
            21: 12606,
            22: 12607,
            23: 12608,
            24: 12609,
        }
        res = mis.verificar_entrega_items(ses, 976, 8)
        self.assertTrue(res)

        # Inventory must NOT contain keys 20..24 with value 0
        for slot in (20, 21, 22, 23, 24):
            self.assertNotIn(slot, ses.inventario)
            self.assertNotIn(str(slot), ses.inventario)

    def test_interactuar_npc_villiersas_completion(self):
        """Talking to Villiersas with all 5 pieces completes Quest 976."""
        ses = DummySession()
        ses.inventario = {
            20: 12605,
            21: 12606,
            22: 12607,
            23: 12608,
            24: 12609,
        }
        proc, tipo_proc, datos_proc = mis.interactuar_npc(ses, "Villiersas")
        self.assertTrue(proc)
        self.assertEqual(tipo_proc, "completada")
        self.assertEqual(datos_proc.get('qid'), 976)
        self.assertTrue(mis.mision_completada(ses.personaje, 976))


if __name__ == '__main__':
    unittest.main()
