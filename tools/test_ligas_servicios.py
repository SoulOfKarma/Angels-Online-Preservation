"""Pruebas de niveles, acceso a Farm y servicios extraidos del cliente."""
import pathlib
import struct
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / 'server'),
                str(pathlib.Path(__file__).resolve().parent)]
import test_banco_liga_transacciones as banco_tests
import app
import cuentas
import gremios
import granja_liga as farm
import presencia
import dialogos_mapa
import login
import eventos
import eventos_mundo


class TestServiciosLiga(unittest.TestCase):
    def setUp(self):
        farm._SALAS.clear()
        banco_tests.TestBancoLiga.setUp(self)

    def tearDown(self):
        farm._SALAS.clear()
        try:
            banco_tests.TestBancoLiga.tearDown(self)
        except Exception:
            pass

    def test_umbrales_originales_y_cruce_atomico(self):
        self.assertEqual(gremios.umbrales_nivel(),
                         (0, 10000, 25000, 67500, 140000, 300500, 600000, 1500000, 3750000, 9375000))
        for level, threshold in enumerate(gremios.umbrales_nivel(), 1):
            self.assertEqual(gremios.nivel_por_reputacion(threshold), level)
            if threshold:
                self.assertEqual(gremios.nivel_por_reputacion(threshold - 1), level - 1)
        with cuentas._get_conn() as con:
            con.execute('UPDATE gremios SET reputacion=300499, nivel=5 WHERE guild_id=?', (self.gid,))
        cuentas.db_contribuir_gremio(self.jefe.usuario, 9901, self.gid, 1, {}, {})
        g = cuentas.db_obtener_gremio(self.gid)
        self.assertEqual((g['reputacion'], g['nivel']), (300500, 6))
        with self.assertRaises(ValueError):
            cuentas.db_contribuir_gremio('no-existe', 9901, self.gid, 99999999, {}, {})
        self.assertEqual(cuentas.db_obtener_gremio(self.gid)['nivel'], 6)

    def test_granja_requisito_y_retorno_persistente(self):
        ses = self.jefe
        ses.personaje.stage = 3
        ses.personaje.tile_x, ses.personaje.tile_y = 190, 180
        app._entrar_granja_liga(ses, 'test')
        self.assertEqual(ses.personaje.stage, 3)
        with cuentas._get_conn() as con:
            con.execute('UPDATE gremios SET nivel=6 WHERE guild_id=?', (self.gid,))
        app._entrar_granja_liga(ses, 'test')
        self.assertEqual(ses.personaje.stage, 501)
        self.assertEqual((ses.personaje.tile_x, ses.personaje.tile_y), farm.llegada())
        self.assertEqual(farm.retorno(ses), (3, 190, 180))
        por = app._portal_en(501, *farm.PORTAL_TILE)
        self.assertTrue(por['salir_granja'])
        app._viajar_por_portal(ses, 'test', por)
        self.assertEqual((ses.personaje.stage, ses.personaje.tile_x, ses.personaje.tile_y), (3, 190, 180))

    def test_aislamiento_salas_y_presencia_por_liga(self):
        with cuentas._get_conn() as con:
            con.execute('UPDATE gremios SET nivel=6 WHERE guild_id=?', (self.gid,))
        for ses in (self.jefe, self.miembro):
            ses.personaje.stage = 501
        self.assertIs(app._sala_para(self.jefe), app._sala_para(self.miembro))
        self.assertEqual(presencia.clave_de_mapa(self.jefe, 501), presencia.clave_de_mapa(self.miembro, 501))
        cuentas.db_remover_miembro_gremio(9902)
        self.assertIsNot(app._sala_para(self.jefe), app._sala_para(self.miembro))
        self.assertNotEqual(presencia.clave_de_mapa(self.jefe, 501), presencia.clave_de_mapa(self.miembro, 501))

    def test_heaven_insignias_usan_tienda_original(self):
        self.jefe.personaje.stage = 3
        for stage in (3, 26, 29, 38):
            arbol = dialogos_mapa._arbol(stage)
            opcion = next(node for msg, node in arbol['5920']['o'] if msg == 5959)
            self.assertIn([14, [71]], arbol[str(opcion)]['a'])
        app._recorrer_dialogo_mapa(self.jefe, 'test', 3, 1000403)
        self.assertIn(struct.pack('<HH', 0x0034, 71), self.jefe.enviados)
        self.assertTrue(login.poblar(501))

    def test_condiciones_de_nivel_y_permiso_del_mapa(self):
        ctx = eventos_mundo.ContextoSesion(self.miembro)
        self.assertTrue(eventos.evaluar(34, [0, 1], ctx))
        self.assertFalse(eventos.evaluar(33, [gremios.GUILD_PERM_WITHDRAW_ITEM], ctx))
        cuentas.db_actualizar_permisos_gremio(self.gid, 3, gremios.GUILD_PERM_WITHDRAW_ITEM)
        self.assertTrue(eventos.evaluar(33, [gremios.GUILD_PERM_WITHDRAW_ITEM], ctx))
        cuentas.db_remover_miembro_gremio(9902)
        self.assertFalse(eventos.evaluar(33, [gremios.GUILD_PERM_WITHDRAW_ITEM], ctx))
        self.assertFalse(eventos.evaluar(34, [4, 6], ctx))

    def test_expulsado_de_granja_regresa_sin_ejecutar_accion(self):
        ses = self.miembro
        with cuentas._get_conn() as con:
            con.execute('UPDATE gremios SET nivel=6 WHERE guild_id=?', (self.gid,))
        ses.personaje.stage = 3
        farm.guardar_retorno(ses)
        ses.personaje.stage = 501
        cuentas.db_remover_miembro_gremio(9902)
        ses.rol = 'mundo'
        srv = app.Servidor('127.0.0.1', 9999)
        srv.manejar(ses, 0x014C, None, None, 'test', b'')
        self.assertEqual(ses.personaje.stage, 3)


    def test_territorio_condiciones_y_heaven_general_premios(self):
        ctx = eventos_mundo.ContextoSesion(self.jefe)
        self.assertFalse(eventos.evaluar(28, [], ctx))
        self.assertFalse(eventos.evaluar(76, [205], ctx))

        # Asignar territorio 205 a la liga
        cuentas.db_asignar_territorio_gremio(205, self.gid)
        self.assertTrue(eventos.evaluar(28, [], ctx))
        self.assertTrue(eventos.evaluar(76, [205], ctx))
        self.assertFalse(eventos.evaluar(76, [200], ctx))

        # Condicion 82: antiguedad en liga
        # Recien creado: antiguedad < 259200s (3 dias)
        self.assertFalse(eventos.evaluar(82, [259200], ctx))

        # Modificar ingreso_en para simular 4 dias de antiguedad
        with cuentas._get_conn() as con:
            con.execute("UPDATE gremio_miembros SET ingreso_en = datetime('now', '-4 days') WHERE char_id = ?",
                        (self.jefe.personaje.char_id,))
        self.assertTrue(eventos.evaluar(82, [259200], ctx))

        # Verificar arbol de Heaven General (nodo 1000358 en map003)
        self.jefe.personaje.stage = 3
        arbol = dialogos_mapa._arbol(3)
        self.assertIn('5920', arbol)
        self.assertIn('1000358', arbol)

    def test_governor_servicios_bancos_y_scroll(self):
        cuentas.db_asignar_territorio_gremio(205, self.gid)
        self.jefe.personaje.stage = 50
        self.jefe.rol = 'mundo'
        self.jefe.inventario = {1: 0}
        srv = app.Servidor('127.0.0.1', 9999)

        # Probar aplicacion de efecto abrir_banco personal (tipo 0)
        app._aplicar_efectos(self.jefe, 'test', [('abrir_banco', 0)])
        self.assertEqual(self.jefe.banco_activo, 'personal')

        # Probar aplicacion de efecto abrir_banco liga (tipo 1)
        app._aplicar_efectos(self.jefe, 'test', [('abrir_banco', 1)])
        self.assertEqual(self.jefe.banco_activo, 'liga')

        # Probar uso de Regression Scroll (item 3734) desde otro mapa
        self.jefe.personaje.stage = 3
        self.jefe.personaje.tile_x, self.jefe.personaje.tile_y = 100, 100
        self.jefe.inventario[25] = 3734
        self.jefe.enviados.clear()
        cuerpo_3734 = struct.pack('<I', 25)
        srv.manejar(self.jefe, 0x002E, None, None, 'test', cuerpo_3734)
        self.assertEqual(self.jefe.personaje.stage, 50)
        self.assertEqual(self.jefe.paralelo_actual, 5)  # 205 - 200 = 5

    def test_granja_cultivos_ciclo_completo(self):
        with cuentas._get_conn() as con:
            con.execute('UPDATE gremios SET nivel=6 WHERE guild_id=?', (self.gid,))
        self.jefe.personaje.stage = 501
        self.jefe.rol = 'mundo'
        self.jefe.inventario = {}
        srv = app.Servidor('127.0.0.1', 9999)

        # 1. Sembrar en parcela 1
        self.jefe.personaje.tile_x, self.jefe.personaje.tile_y = farm.coordenadas_de_parcela(1)
        ok = farm.plantar(self.jefe, 1, crop_id=6)
        self.assertTrue(ok)
        c = cuentas.db_obtener_cultivo(self.gid, 1)
        self.assertIsNotNone(c)
        self.assertEqual(c['crop_id'], 6)

        # 2. Poblar cultivos
        spawns = farm.poblar_cultivos(self.jefe)
        # La tierra de las 70 parcelas es permanente; el cultivo de la 1 va
        # encima en su propia entidad.
        sprites = [int.from_bytes(x[36:40], 'little') for x in spawns
                   if x[:2] == (0x015D).to_bytes(2, 'little')]
        self.assertEqual(sprites.count(farm.SPRITE_TIERRA), 70)
        self.assertEqual(len(sprites) - sprites.count(farm.SPRITE_TIERRA), 1)

        # 3. Regar con C2S 0x014D
        eid = farm.CROP_BASE_EID + 1
        srv.manejar(self.jefe, 0x014D, None, None, 'test', struct.pack('<I', eid))
        c_regado = cuentas.db_obtener_cultivo(self.gid, 1)
        self.assertEqual(c_regado['riego_count'], 1)

        # 4. Abonar con C2S 0x014E
        srv.manejar(self.jefe, 0x014E, None, None, 'test', struct.pack('<I', eid))
        c_abonado = cuentas.db_obtener_cultivo(self.gid, 1)
        self.assertEqual(c_abonado['abono_count'], 1)

        # 5. Cosechar con C2S 0x014F (antes de madurar rechaza)
        self.jefe.enviados.clear()
        srv.manejar(self.jefe, 0x014F, None, None, 'test', struct.pack('<I', eid))
        self.assertIsNotNone(cuentas.db_obtener_cultivo(self.gid, 1))

        # Adelantar el tiempo de maduracion en DB
        with cuentas._get_conn() as con:
            con.execute('UPDATE liga_granja_cultivos SET madura_en = 0 WHERE guild_id=? AND plot_id=1', (self.gid,))

        srv.manejar(self.jefe, 0x014F, None, None, 'test', struct.pack('<I', eid))
        # La primera cosecha del propietario es reservada; no borra las seis
        # cosechas normales de los companeros (string.xml3166).
        self.assertIsNotNone(cuentas.db_obtener_cultivo(self.gid, 1))
        # Y se recibe el objeto cosechado en la bolsa
        self.assertTrue(any(v > 0 for v in self.jefe.inventario.values()))

    def test_chat_league_and_team_routing(self):
        srv = app.Servidor('127.0.0.1', 9999)
        srv.mundos = {self.jefe, self.miembro}
        for s in (self.jefe, self.miembro):
            s.rol = 'mundo'
            s.enviados.clear()

        # Chat de Liga con prefijo @
        srv._procesar_chat_mundo(self.jefe, '@Hola a toda la liga', 'test')
        self.assertTrue(any(b'Hola a toda la liga' in pkt for pkt in self.miembro.enviados))

        # Chat de Liga con prefijo /g
        self.miembro.enviados.clear()
        srv._procesar_chat_mundo(self.jefe, '/g Saludos miembros', 'test')
        self.assertTrue(any(b'Saludos miembros' in pkt for pkt in self.miembro.enviados))

        # Chat de Equipo con prefijo #
        import equipos as _eq
        _eq._DE_QUIEN[self.jefe.personaje.char_id] = self.jefe.personaje.char_id
        _eq._DE_QUIEN[self.miembro.personaje.char_id] = self.jefe.personaje.char_id
        _eq._GRUPOS[self.jefe.personaje.char_id] = {self.jefe, self.miembro}

        self.miembro.enviados.clear()
        srv._procesar_chat_mundo(self.jefe, '#Vamos al calabozo', 'test')
        self.assertTrue(any(b'Vamos al calabozo' in pkt for pkt in self.miembro.enviados))


if __name__ == '__main__':
    unittest.main()

