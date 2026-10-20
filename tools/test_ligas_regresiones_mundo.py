"""Regresiones en DB temporal: guerra, territorios, granja, PvP y colisiones."""
import json
import pathlib
import struct
import sys
import time
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / 'server'), str(ROOT / 'tools')]
import app
import combate
import cuentas
import farm_mecanicas
import granja_liga as farm
import login
import presencia
import pvp_liga
import territorios_liga as territorio
import totem_war as tw
import transitable
from test_banco_liga_transacciones import TestBancoLiga as Fixture


class TestMundoLiga(unittest.TestCase):
    def setUp(self):
        Fixture.setUp(self)
        tw._DUENAS.clear()
        tw._DISPUTADAS.clear()
        tw._ESTADO.update(fin=0, por=None)
        farm._SALAS.clear()
        farm_mecanicas._PROGRAMADOS.clear()
        with cuentas._get_conn() as con:
            con.execute('UPDATE gremios SET nivel=6 WHERE guild_id=?', (self.gid,))
        for s in (self.jefe, self.miembro):
            s.personaje.stage = 501
            s.personaje.tile_x, s.personaje.tile_y = farm.coordenadas_de_parcela(1)
            s.personaje.faction = 'Aurora'
            s.sp = 1000
        self.jefe.personaje.habilidades = [(1, 1, 0)]

    def tearDown(self):
        tw._ESTADO['fin'] = 0
        tw._DISPUTADAS.clear()
        tw._DUENAS.clear()
        farm._SALAS.clear()
        farm_mecanicas._PROGRAMADOS.clear()
        Fixture.tearDown(self)

    def test_propiedad_unica_rechaza_sin_perder_el_dueno(self):
        cuentas.db_asignar_territorio_gremio(205, self.gid)
        with self.assertRaises(ValueError):
            cuentas.db_asignar_territorio_gremio(207, self.gid)
        self.assertEqual(cuentas.db_obtener_territorios_de_gremio(self.gid), [205])
        self.assertTrue(tw.puede_disputar(self.jefe, 205))
        self.assertFalse(tw.puede_disputar(self.jefe, 207))

    def test_asignacion_no_acepta_ligas_fantasma(self):
        with self.assertRaises(ValueError):
            cuentas.db_asignar_territorio_gremio(205, 999999)

    def test_inicio_no_viaja_a_los_jugadores(self):
        self.jefe.personaje.stage = 8
        with patch('app._tw_sesiones', return_value=[self.jefe]), patch('app._tw_difundir'), \
                patch('app._tw_relevantar'), patch('app._sincronizar_cambio_mapa') as viaje:
            tw.iniciar()
            viaje.assert_not_called()
        self.assertEqual(self.jefe.personaje.stage, 8)

    def test_captura_se_confirma_al_terminar(self):
        with patch('app._tw_difundir'), patch('app._tw_levantar_todos'), patch('app._tw_sacar_de_las_arenas'):
            tw.iniciar()
            self.assertTrue(tw.capturado(self.jefe, tw.crear_totem(205)))
            self.assertIsNone(cuentas.db_obtener_dueno_de_territorio(205))
            self.assertFalse(tw.puede_disputar(self.jefe, 207))
            tw.terminar()
        self.assertEqual(cuentas.db_obtener_dueno_de_territorio(205), self.gid)

    def test_el_mapa_no_repite_ligas_del_servidor_grabado(self):
        pkts = login.secuencia(login.Personaje(nombre='Test', char_id=9901))
        pkt = next(p for p in pkts if p[:2] == b'1\x01')
        self.assertNotIn(b'Degenerates', pkt)
        self.assertNotIn(b'AllStars', pkt)
        # 8 campos + 8 arenas (200..207, como Celestia) + la fila vacia de Megalith Plain.
        self.assertEqual(len(pkt), 4+29*17)

    def test_area_iv_solo_dueno_y_paralelo_correcto(self):
        cuentas.db_asignar_territorio_gremio(205, self.gid)
        self.assertTrue(territorio.autorizado(self.jefe, 377, 0))
        self.assertFalse(territorio.autorizado(self.jefe, 377, 1))
        self.assertEqual(territorio.territorio_de_area(117, 1), 205)
        self.assertIsNone(territorio.territorio_de_area(117, 7))

    def test_areas_pobladas_y_con_salida(self):
        for stage in territorio.AREAS:
            self.assertTrue(app._monstruos_de(stage), stage)
            portal = app._portal_en(stage, *territorio.PORTALES[stage])
            self.assertTrue(portal['salir_territorio'])
            self.assertTrue(territorio.paquetes(stage))

    def test_solo_hay_70_parcelas_cultivables(self):
        self.assertEqual(len(farm._objetos_parcela()), 200)
        self.assertEqual(sum(v[0] == 60005 for v in farm._objetos_parcela().values()), 70)
        self.jefe.personaje.tile_x, self.jefe.personaje.tile_y = farm.coordenadas_de_parcela(71)
        self.assertFalse(farm.plantar(self.jefe, 71, 6))

    def test_no_sembrar_lejos_ni_dos_parcelas(self):
        self.assertTrue(farm.plantar(self.jefe, 1, 6))
        self.jefe.personaje.tile_x, self.jefe.personaje.tile_y = farm.coordenadas_de_parcela(2)
        self.assertFalse(farm.plantar(self.jefe, 2, 6))
        self.assertFalse(farm.plantar(self.miembro, 70, 6))

    def test_selector_rea_reenvia_parcela_no_tipo_de_semilla(self):
        pkt = farm.paquete_cultivo(farm.CROP_BASE_EID+3, 6, 'Jefe', (50,30), 66914)
        self.assertEqual(struct.unpack_from('<I', pkt, 46)[0], 3)

    def test_limite_diario_no_se_reinicia_al_reconectar(self):
        self.assertTrue(farm.plantar(self.jefe, 1, 6))
        for _ in range(5):
            self.assertTrue(farm.regar(self.jefe, 1))
        self.assertFalse(farm.regar(self.jefe, 1))
        self.assertEqual(cuentas.db_obtener_cultivo(self.gid, 1)['riego_count'], 5)
        self.assertTrue(farm.regar(self.miembro, 1))
        self.assertEqual(cuentas.db_obtener_cultivo(self.gid, 1)['riego_count'], 6)

    def test_abono_modifica_skill_real_y_respeta_madurez(self):
        self.assertTrue(farm.plantar(self.jefe, 1, 6))
        anterior = self.jefe.personaje.habilidades[0]
        self.assertTrue(farm.abonar(self.jefe, 1))
        self.assertNotEqual(self.jefe.personaje.habilidades[0], anterior)
        with cuentas._get_conn() as con:
            con.execute('UPDATE liga_granja_cultivos SET madura_en=0 WHERE guild_id=?', (self.gid,))
        self.assertFalse(farm.abonar(self.jefe, 1))

    def test_mochila_llena_no_borra_ni_gasta_cosecha(self):
        self.assertTrue(farm.plantar(self.jefe, 1, 6))
        with cuentas._get_conn() as con:
            con.execute('UPDATE liga_granja_cultivos SET madura_en=0 WHERE guild_id=?', (self.gid,))
        with patch('app._meter', return_value=None):
            self.assertFalse(farm.cosechar(self.jefe, 1))
        c = cuentas.db_obtener_cultivo(self.gid, 1)
        self.assertIsNotNone(c)
        self.assertEqual(c['cosechado_count'], 0)

    def test_riego_rechaza_jugador_fuera_de_granja(self):
        self.assertTrue(farm.plantar(self.jefe, 1, 6))
        self.jefe.personaje.stage = 3
        self.assertFalse(farm.regar(self.jefe, 1))
        self.assertEqual(cuentas.db_obtener_cultivo(self.gid, 1)['riego_count'], 0)

    def test_pvp_no_admite_aliados_ni_mapas_seguros(self):
        for s in (self.jefe, self.miembro):
            s.personaje.stage = 205
            s.personaje.hp = 100
        tw._ESTADO['fin'] = time.time()+60
        self.assertFalse(pvp_liga.permitido(self.jefe, self.miembro))
        cuentas.db_salir_gremio(self.miembro.personaje.char_id) if hasattr(cuentas, 'db_salir_gremio') else None
        self.miembro.personaje.faction = 'Shadow'
        self.jefe.personaje.stage = self.miembro.personaje.stage = 3
        self.assertFalse(pvp_liga.permitido(self.jefe, self.miembro))

    def test_instancias_no_tienen_spawns_en_paredes(self):
        for stage, name in ((168,'dinosaur_arena.json'),(413,'c_dinosaur_arena.json'),(176,'unknown_chambers.json')):
            d = json.loads((ROOT/'server/plantillas'/name).read_text(encoding='utf-8'))
            for e in d['spawns']:
                if e.get('monstruo'):
                    self.assertTrue(transitable.se_pisa(stage, *e['tile']), (stage, e['tile']))

    def test_dino_conserva_sus_tipos_y_posiciones_chaos(self):
        base = ROOT/'server/plantillas'
        normal = json.loads((base/'dinosaur_arena.json').read_text(encoding='utf-8'))
        chaos = json.loads((base/'c_dinosaur_arena.json').read_text(encoding='utf-8'))
        referencias = {(e['sprite'],e.get('zona'),tuple(e['tile'])) for e in chaos['spawns'] if e.get('monstruo')}
        for e in normal['spawns']:
            if e.get('monstruo'):
                self.assertLess(e['npc_type'], 10000)
                self.assertIn((e['sprite'],e.get('zona'),tuple(e['tile'])), referencias)


if __name__ == '__main__':
    unittest.main()
