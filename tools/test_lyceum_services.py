"""Servicios Lyceum contra SQLite temporal; no toca cuentas ni el cliente real."""
import datetime
import gc
import json
import pathlib
import struct
import sys
import time
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT/'server'), str(ROOT/'tools')]
import test_banco_liga_transacciones as banco
import app
import configuracion
import cuentas
import dialogos
import login
import logros
import lyceum_services as ly


class TestLyceum(unittest.TestCase):
    def setUp(self):
        banco.TestBancoLiga.setUp(self)
        self.s = self.jefe
        self.s.personaje.stage = 41
        self.s.oro = self.s.personaje.oro = 10_000_000
        self.s.dlg_val, self.s.dlg_ent = 422, 405
        self.actualizar = patch('app._logros_actualizar')
        self.actualizar.start()

    def tearDown(self):
        self.actualizar.stop()
        gc.collect()
        banco.TestBancoLiga.tearDown(self)

    def datos(self):
        con = cuentas._get_conn()
        try:
            return json.loads(con.execute('SELECT datos FROM personajes WHERE char_id=?',
                                           (self.s.personaje.char_id,)).fetchone()[0])
        finally:
            con.close()

    def astro(self):
        return ly.confirmar(self.s, 'astro', (datetime.date.today().isoformat(), ly.usos_hoy(self.s)))

    def test_primero_gratis_buff_dura_12_horas_y_se_guarda(self):
        antes = time.time()
        with patch('random.randrange', return_value=0), patch('random.choices', return_value=[2]):
            mid = self.astro()
        self.assertEqual(mid, 14535)
        self.assertEqual(self.s.oro, 10_000_000)
        self.assertEqual(ly.usos_hoy(self.s), 1)
        self.assertAlmostEqual(self.s.personaje.buffs[mid]['fin']-antes, 43200, delta=2)
        self.assertIn(str(mid), self.datos()['buffs'])
        self.assertEqual(self.datos()['logros_cont']['buff:14535'], 1)

    def test_cinco_lecturas_tarifas_cristal_limite_y_reemplazo(self):
        self.s.inventario[21] = ly.CRISTAL
        self.s.cantidades[21] = 2
        self.s.personaje.buffs = {999: {'fin': time.time()+500}}
        for _ in range(5):
            self.astro()
        self.assertEqual(self.s.oro, 1_500_000)
        self.assertEqual(self.s.cantidades[21], 1)
        self.assertIn(999, self.s.personaje.buffs)
        self.assertEqual(sum(mid in ly.ASTRO_IDS for mid in self.s.personaje.buffs), 1)
        antes = self.datos()
        with self.assertRaises(ly.Rechazo) as e:
            self.astro()
        self.assertEqual(e.exception.mensaje, 142506)
        self.assertEqual(antes, self.datos())

    def test_sin_oro_no_gasta_cuota_ni_reemplaza_buff(self):
        self.astro()
        antes = self.datos()
        self.s.oro = self.s.personaje.oro = 0
        with self.assertRaises(ly.Rechazo) as e:
            self.astro()
        self.assertEqual(e.exception.mensaje, 142515)
        self.assertEqual(self.datos(), antes)

    def test_sin_cristal_no_gasta_quinta_lectura(self):
        for _ in range(4):
            self.astro()
        antes = self.datos()
        with self.assertRaises(ly.Rechazo) as e:
            self.astro()
        self.assertEqual(e.exception.mensaje, 142510)
        self.assertEqual(self.datos(), antes)

    def test_repetir_confirmacion_no_cobra_de_nuevo(self):
        esperado = datetime.date.today().isoformat(), 0
        ly.confirmar(self.s, 'astro', esperado)
        antes = self.datos()
        self.assertIsNone(ly.confirmar(self.s, 'astro', esperado))
        self.assertEqual(self.datos(), antes)

    def test_dia_nuevo_reinicia_cuota_sin_borrar_otros_datos(self):
        self.astro()
        cuentas._actualizar_personaje(self.s.usuario, self.s.personaje.char_id,
                                     lambda d: d['astrologer'].update(dia='2000-01-01', usos=5))
        self.assertEqual(ly.usos_hoy(self.s), 0)
        oro = self.s.oro
        self.astro()
        self.assertEqual(self.s.oro, oro)

    def test_go_green_cortes_de_nivel_sin_acumular_y_cuesta_30(self):
        self.s.inventario[21] = ly.STRAW
        self.s.cantidades[21] = 150
        for nivel, mid in ((99, 20428), (100, 20429), (209, 20429), (210, 20430)):
            self.s.personaje.nivel = nivel
            self.assertEqual(ly.confirmar(self.s, 'green_buff'), mid)
            self.assertEqual(sum(b in ly.GREEN_IDS for b in self.s.personaje.buffs), 1)
            self.assertAlmostEqual(self.s.personaje.buffs[mid]['fin']-time.time(), 86400, delta=2)
        self.assertEqual(self.s.cantidades[21], 30)
        self.assertEqual(self.s.personaje.buffs[20430]['atk'], 1500)
        self.assertEqual(ly.bono(self.s.personaje.buffs, 'recoleccion_pct'), 3)

    def test_sello_consume_varios_montones_y_registra_logro_no_item_visible(self):
        self.s.inventario.update({21: ly.STRAW, 22: ly.STRAW})
        self.s.cantidades.update({21: 60, 22: 50})
        self.assertEqual(ly.confirmar(self.s, 'green_stamp'), ly.SELLO)
        self.assertNotIn(21, self.s.inventario)
        self.assertEqual(self.s.cantidades[22], 10)
        self.assertNotIn(ly.SELLO, self.s.inventario.values())
        self.assertEqual(self.datos()['logros_cont']['obtiene:60470'], 1)
        # El evaluador real debe reconocer el contador, no inventar un titulo.
        fila = next(f for f in logros.tabla() if f['id'] == 3603)
        self.assertEqual(logros.medir(fila, self.s.personaje, {'cont': self.s.personaje.logros_cont}), (1, 1))

    def test_no_consumir_si_faltan_straws(self):
        self.s.inventario[21] = ly.STRAW
        self.s.cantidades[21] = 29
        antes = dict(self.s.inventario), dict(self.s.cantidades)
        with self.assertRaises(ly.Rechazo):
            ly.confirmar(self.s, 'green_buff')
        self.assertEqual(antes, (self.s.inventario, self.s.cantidades))

    def test_bonos_reales_xml_exp_skill_carga_y_caducidad(self):
        with patch('configuracion.es_fin_de_semana', return_value=False):
            for mid, clave, campo, factor in ((14562, 'exp', 'exp_extra_pct', 2),
                                             (14565, 'skill', 'skill_exp_extra_pct', 4)):
                e = ly.entrada_buff(mid)
                fn = configuracion.multiplicador_exp if clave == 'exp' else configuracion.multiplicador_skill_exp
                # Los % de los buffs se SUMAN a la tasa: +100 % es +1 y +300 % es +3.
                self.assertEqual(fn({mid: e}), fn() + (factor - 1))
                e['fin'] = 0
                self.assertEqual(fn({mid: e}), fn())
        self.assertEqual(ly.entrada_buff(14535)['carga'], 10000)
        self.assertEqual(ly.entrada_buff(14559)['atk'], 2000)

    def test_npc_saludos_giro_posiciones_sin_ids_duplicados(self):
        rows = json.loads((ROOT/'server/plantillas/lyceum.json').read_text(encoding='utf-8'))['spawns']
        self.assertEqual(len(rows), len({r['entity_id'] for r in rows}))
        por_nombre = {r['nombre']: r for r in rows}
        self.assertEqual(por_nombre['Astrologer']['direccion'], 7)
        self.assertEqual(por_nombre['Astrologer']['tile'], [144, 107])
        self.assertEqual(por_nombre['Login Rewarder']['tile'], [141, 106])
        self.assertLess(por_nombre['Login Rewarder']['tile'][0], por_nombre['Astrologer']['tile'][0])
        self.assertEqual(por_nombre['Green Angel']['tile'], [215, 74])
        for nombre in ly.NOMBRES:
            g = dialogos.propio(nombre, stage=41)
            self.assertEqual(dialogos.opciones_de(g[0]), ly.saludo(nombre)[1])
            r = por_nombre[nombre]
            pkt = login._npc_spawn(r['entity_id'], r['npc_type'], nombre, r['tile'],
                                   sprite=r['sprite'], direccion=r['direccion'])
            self.assertEqual(pkt[35], 7)
            self.assertEqual(struct.unpack_from('<I', pkt, 36)[0], r['sprite'])
            self.assertEqual(app._nombre_entidad(self.s, r['entity_id']), nombre)

    def test_login_rewarder_abre_tres_grupos_de_recetas_reales(self):
        for opcion, grupo in ly.GRUPOS_LOGIN.items():
            self.s.enviados.clear()
            self.assertTrue(ly.procesar_opcion(self.s, 'Login Rewarder', opcion))
            self.assertIn(struct.pack('<HI', 0x151, grupo), self.s.enviados)
            recetas = [i for i,r in ly.xml_rows('exchange.xml').items()
                       if int(r.get('\u7fa4\u7d44') or 0) == grupo]
            self.assertTrue(recetas)
            self.assertTrue(all(app._obtener_receta_exchange(i)['materiales'] for i in recetas))

    def test_drop_21_ambas_fuentes_solo_mapas_normales_con_chance(self):
        with patch('random.random', return_value=0):
            self.assertEqual(ly.straw_drop(21, 20), [])
            self.assertEqual(ly.straw_drop(21, 21), [(60469, 1)])
            self.assertEqual(ly.straw_drop(176, 400), [])
            self.assertEqual(ly.straw_drop(413, 400), [])
            self.assertEqual(ly.straw_drop(500, 400), [])
        with patch('random.random', return_value=0.999999):
            self.assertEqual(ly.straw_drop(21, 21), [])

    def test_canje_real_online_scroll(self):
        self.s.inventario[21] = 66361
        self.s.cantidades[21] = 5
        self.s._lyceum_exchange = 526
        self.assertTrue(ly.canjear(self.s, 18976, 2))
        self.assertEqual(self.s.cantidades[21], 3)
        slot = next(s for s,it in self.s.inventario.items() if it == 25832)
        self.assertEqual(self.s.cantidades[slot], 10)
        self.assertEqual(self.datos()['cantidades'][str(slot)], 10)

    def test_canje_mochila_llena_no_consume_pergaminos(self):
        self.s.inventario = {s: 4 for s in range(20,45)}
        self.s.inventario[21] = 66361
        self.s.cantidades[21] = 5
        self.s._lyceum_exchange = 526
        antes = dict(self.s.inventario), dict(self.s.cantidades), self.datos()
        self.assertTrue(ly.canjear(self.s, 18976, 1))
        self.assertEqual(antes, (self.s.inventario, self.s.cantidades, self.datos()))

    def test_canje_reutiliza_casilla_consumida_y_rechaza_grupo_no_abierto(self):
        self.s.inventario = {s: 4 for s in range(20,45)}
        self.s.inventario[21] = 66361
        self.s._lyceum_exchange = 527
        self.assertTrue(ly.canjear(self.s, 18976, 1))
        self.assertEqual(self.s.inventario[21], 66361)
        self.s._lyceum_exchange = 526
        self.assertTrue(ly.canjear(self.s, 18976, 1))
        self.assertEqual(self.s.inventario[21], 25832)
        self.assertEqual(self.s.cantidades[21], 5)

    def test_dispatcher_dialogo_confirmacion_y_replay(self):
        self.s.rol = 'mundo'
        self.s.dlg_guion = dialogos.propio('Astrologer', stage=41)
        self.s.dlg_paso = 1
        srv = app.Servidor.__new__(app.Servidor)
        with patch('app._nombre_entidad', return_value='Astrologer'):
            # Opcion 1 -> tarifa gratis, aun no aplica ningun buff.
            srv.manejar(self.s, 0x000B, None, {'valor': 10}, 'test')
            self.assertEqual(ly.usos_hoy(self.s), 0)
            self.assertEqual(dialogos.opciones_de(self.s.dlg_guion[-1]), [142508, 142509])
            # Confirmacion -> un buff. Repetir ID crudo no puede confirmarlo otra vez.
            srv.manejar(self.s, 0x000B, None, {'valor': 10}, 'test')
            self.assertEqual(ly.usos_hoy(self.s), 1)
            srv.manejar(self.s, 0x000B, None, {'valor': 142508}, 'test')
            self.assertEqual(ly.usos_hoy(self.s), 1)

    def test_buff_taurus_afecta_recoleccion_no_solo_tooltip(self):
        self.s.personaje.buffs = {14538: ly.entrada_buff(14538)}
        puede, _, velocidad = app._herramienta_para(self.s, None)
        self.assertTrue(puede)
        self.assertEqual(velocidad, 10)

    def test_logro_astrologer_usa_contador_real(self):
        fila = next(f for f in logros.tabla() if f['id'] == 3302)
        self.assertEqual(logros.medir(fila, self.s.personaje, {'cont': {'buff:14535': 10}}), (10, 10))

    def test_error_sql_no_consume_cristal_ni_cambia_buff_o_cuota(self):
        for _ in range(4):
            self.astro()
        self.s.inventario[21] = ly.CRISTAL
        antes = dict(self.s.inventario), dict(self.s.personaje.buffs), self.datos()
        con = cuentas._get_conn()
        try:
            con.execute("CREATE TRIGGER fallo_update BEFORE UPDATE ON personajes "
                        "BEGIN SELECT RAISE(ABORT, 'fallo simulado'); END")
            con.commit()
        finally:
            con.close()
        with self.assertRaises(Exception):
            self.astro()
        self.assertEqual(antes, (self.s.inventario, self.s.personaje.buffs, self.datos()))

    def test_recoleccion_real_usa_nivel_de_recurso_no_del_jugador(self):
        self.s.personaje.nivel = 410
        self.s.personaje.stage = 21
        material = dict(limite=0, items=[(35, 100)], no_produce=0, nombre='Prueba')
        mid21 = next(i for i,r in ly.xml_rows('material.xml').items()
                     if int(r.get('\u7b49\u7d1a\u9650\u5236') or 0) == 21)
        with patch('app._cuenta_de_veta', return_value=[0, 0]), patch('random.random', return_value=0), \
             patch('misiones.verificar_progreso_recoleccion', return_value=[]):
            self.assertTrue(app._sacar_de_veta(self.s, 'test', 21, 123, material, 1))
            self.assertNotIn(ly.STRAW, self.s.inventario.values())
            self.assertTrue(app._sacar_de_veta(self.s, 'test', 21, 123, material, mid21))
            self.assertIn(ly.STRAW, self.s.inventario.values())

    def test_green_abre_catalogo_completo_con_nueve_monturas(self):
        self.assertTrue(ly.procesar_opcion(self.s, 'Green Angel', 513642))
        self.assertIn(struct.pack('<HI', 0x151, 401), self.s.enviados)
        self.assertEqual(self.s._lyceum_exchange, 401)
        for receta, item, coste in [(15337+i, 65842+i, 1800) for i in range(3)] + \
                                  [(15340+i, 65839+i, 1400) for i in range(3)] + \
                                  [(15343+i, 15324+i, 1000) for i in range(3)]:
            r = app._obtener_receta_exchange(receta)
            self.assertEqual(r['materiales'], [(ly.STRAW, coste)])
            self.assertEqual(r['premios'], [(item, 1)])

    def test_canjear_oso_consumo_persistencia_y_mochila_llena(self):
        self.s._lyceum_exchange = 401
        self.s.inventario = {s: 4 for s in range(20,45)}
        self.s.inventario[21] = ly.STRAW
        self.s.cantidades[21] = 2000
        antes = dict(self.s.inventario), dict(self.s.cantidades), self.datos()
        self.assertTrue(ly.canjear(self.s, 15337, 1))
        self.assertEqual(antes, (self.s.inventario, self.s.cantidades, self.datos()))
        del self.s.inventario[22]
        self.assertTrue(ly.canjear(self.s, 15337, 1))
        self.assertEqual(self.s.cantidades[21], 200)
        self.assertEqual(self.s.inventario[22], 65842)
        self.assertEqual(self.datos()['inventario']['22'], 65842)
        self.assertEqual(self.s.cantidades[22], 1)

    def test_drac_drax_reales_sin_atributo_nivel_tienen_chance_de_straw(self):
        import combate
        for tipo, nombre in ((20754, 'Drac'), (20755, 'Drax')):
            m = combate.Monstruo(12345, tipo, nombre, (64,140), stage=336)
            self.assertFalse(hasattr(m, 'nivel'))  # Reproduce el fallo del log.
            with patch('random.random', return_value=0):
                self.assertEqual(ly.straw_drop_monstruo(336, m), [(60469, 1)])
                self.assertEqual(ly.straw_drop_monstruo(413, m), [])
            with patch('random.random', return_value=0.99):
                self.assertEqual(ly.straw_drop_monstruo(336, m), [])

    def test_astrologer_rotacion_explicita_despues_del_spawn_sin_moverlo(self):
        paquetes = login.poblar(41)
        giro = login.rotar(405, 7)
        self.assertIn(giro, paquetes)
        idx = paquetes.index(giro)
        spawn = paquetes[idx-1]
        self.assertEqual(struct.unpack_from('<HI', spawn), (8, 405))
        self.assertEqual(struct.unpack_from('<II', spawn, 10), (144,107))


if __name__ == '__main__':
    unittest.main()
