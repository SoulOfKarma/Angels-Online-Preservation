"""Callbacks reales de captura: una copia, sala original e identidad del spawn."""
import asyncio
import os
import pathlib
import struct
import sys
import tempfile
import unittest
from contextlib import ExitStack
from types import SimpleNamespace as S
from unittest.mock import patch


class CapturaCiclo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='ao_captura_ciclo_', ignore_cleanup_errors=True)
        cls.old = os.environ.get('AO_DATOS')
        os.environ['AO_DATOS'] = cls.tmp.name
        root = pathlib.Path(__file__).resolve().parent.parent
        sys.path[:0] = [str(root / 'server'), str(root / 'proto')]
        import app, combate, house_services
        cls.app, cls.cb, cls.hs = app, combate, house_services

    @classmethod
    def tearDownClass(cls):
        if cls.old is None:
            os.environ.pop('AO_DATOS', None)
        else:
            os.environ['AO_DATOS'] = cls.old
        cls.tmp.cleanup()

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.m = self.cb.Monstruo(123, 129, 'Unicorn Rabbit', (270, 25), 40001, stage=13)
        self.m.hp -= 1
        self.m.dano_por = {1001: 1}
        self.owner = S(personaje=S(stage=13, nivel=450, entity_id=1001, char_id=1001, mascotas={}),
                       inventario={20: 16982}, cantidades={20: 2}, captura_pendiente={'slot': 20, 'item': 16982, 'time': 100}, cerrada=False)
        self.peer = S(personaje=S(stage=13, entity_id=1002), cerrada=False)
        self.room = S(stage=13, monstruos={123: self.m}, sesiones=[self.owner, self.peer])
        for s in (self.owner, self.peer):
            s._sala, s.monstruos, s.sent = self.room, self.room.monstruos, []
            s.enviar = lambda *ps, s=s: s.sent.extend(ps)
            s.enviar_sin_espejo = s.enviar
            s.volcar = lambda: None
        self.timers = []
        loop = S(call_later=lambda delay, fn: self.timers.append((delay, fn)))
        patches = [patch('time.time', return_value=100.), patch.object(asyncio, 'get_running_loop', return_value=loop),
                   patch.object(self.app.random, 'random', return_value=0.),
                   patch.object(self.app, '_sacar'), patch.object(self.app, '_refrescar', return_value=[]),
                   patch.object(self.app, '_meter', return_value=21), patch.object(self.app, '_logros_contar'),
                   patch.object(self.app, '_guardar_bolsa'), patch.object(self.app, '_nombre_item', return_value='Pet')]
        for p in patches:
            self.stack.enter_context(p)
        self.assertTrue(self.app._intentar_captura_monstruo(self.owner, 123))
        self.assertEqual([t[0] for t in self.timers], [2., 22.])
        for s in (self.owner, self.peer):
            fx = [b for b in s.sent if b[:2] == b'\x11\0']
            self.assertEqual([b[2] | ((b[3] & 15) << 8) for b in fx], [36, 36, 302, 302])
            s.sent.clear()

    def callbacks(self):
        for _, fn in self.timers:
            fn()

    def assert_cycle(self, s):
        self.assertEqual(sum(b[:2] == b'\x07\0' and b[6] == 0 for b in s.sent), 1)
        self.assertEqual(sum(b[:2] == b'\x08\0' for b in s.sent), 1)

    def test_ciclo_normal_una_copia_por_cliente(self):
        self.callbacks()
        self.assertTrue(self.m.vivo)
        self.assertIsNone(self.m.capturado_en)
        self.assert_cycle(self.owner)
        self.assert_cycle(self.peer)

    def test_desconexion_no_cancela_ciclo_de_la_sala(self):
        self.owner.cerrada = True
        self.room.sesiones.remove(self.owner)
        self.callbacks()
        self.assertEqual(self.owner.sent, [])
        self.assert_cycle(self.peer)

    def test_viaje_no_envia_a_la_escena_nueva(self):
        self.owner.personaje.stage = 41
        self.owner._sala, self.owner.monstruos = None, {}
        self.callbacks()
        self.assertEqual(self.owner.sent, [])
        self.assert_cycle(self.peer)
        self.assertTrue(self.m.vivo)

    def test_generado_se_retira_y_no_reaparece(self):
        self.m.generado = True
        self.callbacks()
        self.assertNotIn(123, self.room.monstruos)
        for s in (self.owner, self.peer):
            self.assertEqual(sum(b[:2] == b'\x07\0' for b in s.sent), 1)
            self.assertFalse(any(b[:2] == b'\x08\0' for b in s.sent))

    def test_reasignar_eid_no_retira_ni_revive_otro_objeto(self):
        nuevo = self.cb.Monstruo(123, 129, 'Nuevo', (270, 25), 40001, stage=13)
        nuevo.hp = 0
        self.room.monstruos[123] = nuevo
        self.callbacks()
        self.assertEqual(nuevo.hp, 0)
        self.assertEqual(self.owner.sent + self.peer.sent, [])

    def test_sustituir_diccionario_de_sala_no_afecta_la_poblacion_nueva(self):
        nuevo = self.cb.Monstruo(123, 129, 'Nuevo', (270, 25), 40001, stage=13)
        nuevo.hp = 0
        self.room.monstruos = {123: nuevo}
        self.owner.monstruos = self.peer.monstruos = self.room.monstruos
        self.callbacks()
        self.assertEqual(nuevo.hp, 0)
        self.assertEqual(self.owner.sent + self.peer.sent, [])

    def test_otra_captura_invalida_ambos_callbacks_anteriores(self):
        self.m.capturado_en = 101.
        self.callbacks()
        self.assertFalse(self.m.vivo)
        self.assertEqual(self.owner.sent + self.peer.sent, [])

    def test_sin_mascota_no_atribuye_el_golpe_de_otro(self):
        self.m.hp = self.m.hp_max - 1
        self.m.muerto_en = self.m.capturado_en = None
        self.m.en_combate_con = None
        self.m.dano_por = {1002: 1}
        self.owner.captura_pendiente = {'slot': 20, 'item': 16982, 'time': 100}
        self.assertTrue(self.app._intentar_captura_monstruo(self.owner, 123))
        mensajes = [p[5:].split(b'\0')[0].decode('latin1') for p in self.owner.sent if p[:2] == b'\x0d\0']
        self.assertEqual(mensajes, ['You must attack and weaken the monster before capturing it!'])
        self.assertFalse(any(p[:2] == b'\x11\0' for p in self.owner.sent + self.peer.sent))

    def test_cursor_vencido_no_consume_ni_produce_efecto(self):
        self.owner.captura_pendiente = {'slot': 20, 'item': 16982, 'time': 69.}
        self.assertTrue(self.app._intentar_captura_monstruo(self.owner, 123))
        self.assertIsNone(self.owner.captura_pendiente)
        self.assertIn(b'The Poke Egg selection expired.', self.owner.sent[0])
        self.assertEqual(len(self.owner.sent), 1)
        self.assertEqual(self.peer.sent, [])

    def test_huevo_sustituido_invalida_cursor(self):
        self.owner.inventario[20] = 339
        self.owner.captura_pendiente = {'slot': 20, 'item': 16982, 'time': 100.}
        self.assertTrue(self.app._intentar_captura_monstruo(self.owner, 123))
        self.assertIsNone(self.owner.captura_pendiente)
        self.assertIn(b'The Poke Egg is no longer available.', self.owner.sent[0])
        self.assertEqual(len(self.owner.sent), 1)
        self.assertEqual(self.peer.sent, [])


if __name__ == '__main__':
    unittest.main()
