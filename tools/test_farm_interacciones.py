"""Regresion del rechazo silencioso de Farm del 21/10/2026."""
import pathlib
import struct
import sys
import unittest
import gc
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / 'server'), str(ROOT / 'tools')]
import test_banco_liga_transacciones as banco
import cuentas
import granja_liga as farm
import farm_mecanicas as acciones


class TestFarmInteracciones(unittest.TestCase):
    def setUp(self):
        banco.TestBancoLiga.setUp(self)
        farm._SALAS.clear()
        acciones._PROGRAMADOS.clear()
        with cuentas._get_conn() as con:
            con.execute('UPDATE gremios SET nivel=6 WHERE guild_id=?', (self.gid,))
        self.ses = self.jefe
        self.ses.personaje.stage = farm.STAGE
        self.ses.personaje.tile_x, self.ses.personaje.tile_y = farm.coordenadas_de_parcela(67)
        self.assertTrue(farm.plantar(self.ses, 67, 1))
        self.ses.enviados.clear()

    def tearDown(self):
        acciones._PROGRAMADOS.clear()
        farm._SALAS.clear()
        gc.collect()  # sqlite3.Connection context managers no cierran el handle.
        banco.TestBancoLiga.tearDown(self)

    def posicion_del_log(self):
        # MOVE_REQ del 21/10 13:24:50: (2384,911)px -> (74,28).
        self.ses.personaje.tile_x, self.ses.personaje.tile_y = 74, 28

    def test_regar_desde_la_posicion_donde_se_detiene_el_cliente(self):
        self.posicion_del_log()
        self.assertTrue(farm.regar(self.ses, 67))
        self.assertEqual(cuentas.db_obtener_cultivo(self.gid, 67)['riego_count'], 1)

    def test_fertilizar_desde_el_borde(self):
        self.posicion_del_log()
        self.assertTrue(farm.abonar(self.ses, 67))
        self.assertEqual(cuentas.db_obtener_cultivo(self.gid, 67)['abono_count'], 1)

    def test_cosechar_maduro_desde_el_borde(self):
        self.posicion_del_log()
        with cuentas._get_conn() as con:
            con.execute('UPDATE liga_granja_cultivos SET madura_en=0 WHERE guild_id=?', (self.gid,))
        antes = cuentas.db_obtener_cultivo(self.gid, 67)
        with patch('bolsas._sorteo', return_value=(1359, 1)):
            self.assertTrue(farm.cosechar(self.ses, 67))
        # La primera cosecha garantizada no elimina la planta ni cambia su generacion.
        self.assertEqual(antes, cuentas.db_obtener_cultivo(self.gid, 67))
        self.assertEqual(self.paquetes_visuales()[-1][:2], b'\x5d\x01')

    def test_demasiado_lejos_da_aviso_y_no_gasta_accion(self):
        self.ses.personaje.tile_x, self.ses.personaje.tile_y = 90, 40
        self.assertFalse(farm.regar(self.ses, 67))
        self.assertTrue(self.ses.enviados, 'El rechazo no debe ser silencioso')
        self.assertEqual(cuentas.db_obtener_cultivo(self.gid, 67)['riego_count'], 0)

    def test_no_cosechar_antes_de_madurar(self):
        self.posicion_del_log()
        self.assertFalse(farm.cosechar(self.ses, 67))
        self.assertTrue(self.ses.enviados)

    def test_no_actuar_desde_otro_mapa(self):
        self.ses.personaje.stage = 3
        self.assertFalse(farm.regar(self.ses, 67))
        self.assertEqual(cuentas.db_obtener_cultivo(self.gid, 67)['riego_count'], 0)

    def paquetes_visuales(self, ses=None):
        return [p for p in (ses or self.ses).enviados
                if p[:2] in (b'\x07\x00', b'\x5d\x01', b'\x10\x00', b'\x11\x00')]

    def test_accion_fallida_no_retira_ni_redibuja_la_planta(self):
        self.posicion_del_log()
        antes = cuentas.db_obtener_cultivo(self.gid, 67)
        self.assertFalse(farm.cosechar(self.ses, 67))
        self.assertFalse(self.paquetes_visuales())
        self.assertEqual(antes, cuentas.db_obtener_cultivo(self.gid, 67))

    def test_regar_recrea_tierra_antes_de_planta_y_conserva_siembra(self):
        self.posicion_del_log()
        antes = cuentas.db_obtener_cultivo(self.gid, 67)
        self.assertTrue(farm.regar(self.ses, 67))
        despues = cuentas.db_obtener_cultivo(self.gid, 67)
        self.assertEqual(despues, dict(antes, riego_count=1))
        visuales = self.paquetes_visuales()
        self.assertEqual([(struct.unpack_from('<H', p)[0], struct.unpack_from('<I', p, 2)[0])
                          for p in visuales],
                         [(7, farm.CROP_BASE_EID+67), (7, farm.PARCELA_BASE_EID+67),
                          (0x15D, farm.PARCELA_BASE_EID+67), (0x15D, farm.CROP_BASE_EID+67)])
        self.assertEqual(struct.unpack_from('<I', visuales[2], 36)[0], farm.SPRITE_TIERRA_MOJADA)
        self.assertEqual(struct.unpack_from('<I', visuales[3], 36)[0], farm.sprite_de_etapa(
            antes['crop_id'], antes['sembrado_en'], antes['madura_en']))

    def test_abonar_restaura_planta_sin_efecto_experimental_ni_timer(self):
        self.posicion_del_log()
        antes = cuentas.db_obtener_cultivo(self.gid, 67)
        with patch('asyncio.get_running_loop') as bucle:
            self.assertTrue(farm.abonar(self.ses, 67))
            bucle.assert_not_called()
        visuales = self.paquetes_visuales()
        self.assertEqual([p[:2] for p in visuales], [b'\x07\x00', b'\x5d\x01'])
        self.assertEqual(cuentas.db_obtener_cultivo(self.gid, 67), dict(antes, abono_count=1))

    def test_companero_ve_la_misma_planta_despues_del_riego(self):
        self.posicion_del_log()
        self.miembro.personaje.stage = farm.STAGE
        sala = SimpleNamespace(sesiones=[self.ses, self.miembro])
        self.ses._sala = self.miembro._sala = sala
        self.miembro.enviados.clear()
        self.assertTrue(farm.regar(self.ses, 67))
        self.assertEqual(self.paquetes_visuales(), self.paquetes_visuales(self.miembro))
        self.assertEqual(struct.unpack_from('<I', self.paquetes_visuales(self.miembro)[-1], 2)[0],
                         farm.CROP_BASE_EID+67)

    def test_refresco_no_se_filtra_a_otro_mapa(self):
        self.posicion_del_log()
        self.miembro.personaje.stage = 3
        self.ses._sala = SimpleNamespace(sesiones=[self.ses, self.miembro])
        self.miembro.enviados.clear()
        self.assertTrue(farm.regar(self.ses, 67))
        self.assertFalse(self.miembro.enviados)

    def test_refresco_de_maduro_conserva_sprite_y_bandera_de_cosecha(self):
        with cuentas._get_conn() as con:
            con.execute('UPDATE liga_granja_cultivos SET madura_en=0 WHERE guild_id=?', (self.gid,))
        c = cuentas.db_obtener_cultivo(self.gid, 67)
        acciones.refrescar_cultivo(self.ses, c, actualizar_tierra=True)
        planta = self.paquetes_visuales()[-1]
        self.assertEqual(struct.unpack_from('<I', planta, 36)[0], farm.sprite_de_etapa(
            c['crop_id'], c['sembrado_en'], c['madura_en']))
        self.assertEqual(planta[45], 1)
        self.assertEqual(cuentas.db_obtener_cultivo(self.gid, 67), c)

    def test_cuota_agotada_no_oculta_planta_ni_reinicia_contadores(self):
        self.posicion_del_log()
        for _ in range(5):
            self.assertTrue(farm.regar(self.ses, 67))
        antes = cuentas.db_obtener_cultivo(self.gid, 67)
        self.ses.enviados.clear()
        self.assertFalse(farm.regar(self.ses, 67))
        self.assertFalse(self.paquetes_visuales())
        self.assertEqual(antes, cuentas.db_obtener_cultivo(self.gid, 67))


if __name__ == '__main__':
    unittest.main()
