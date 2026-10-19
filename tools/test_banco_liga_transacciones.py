"""Regresiones del banco de liga contra una base temporal, sin tocar cuentas reales."""
import json
import pathlib
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'server'))
import app
import cuentas
import gremios
import login


class Sesion:
    def __init__(self, cid, nombre):
        self.usuario = nombre
        self.personaje = login.Personaje(nombre=nombre, char_id=cid, nivel=50, rango=3, entity_id=cid + 1000)
        self.oro = self.personaje.oro = 100000
        self.inventario = {20: 4}
        self.cantidades = {}
        self.instancias = {}
        self.enviados = []
        self.banco_activo = 'liga'

    def enviar(self, *p):
        self.enviados.extend(p)


class TestBancoLiga(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = (cuentas.BASE, cuentas.DB_PATH, cuentas.BACKUPS_DIR,
                         cuentas.ARCHIVO, cuentas._notificar_cambio)
        cuentas.BASE = pathlib.Path(self.tmp.name)
        cuentas.DB_PATH = cuentas.BASE / 'cuentas.db'
        cuentas.BACKUPS_DIR = cuentas.BASE / 'backups'
        cuentas.ARCHIVO = cuentas.BASE / 'cuentas.json'
        cuentas._notificar_cambio = lambda: None
        cuentas._init_db()
        self.jefe, self.miembro = Sesion(9901, 'Jefe'), Sesion(9902, 'Miembro')
        with cuentas._get_conn() as con:
            for ses in (self.jefe, self.miembro):
                con.execute('INSERT INTO cuentas(usuario) VALUES (?)', (ses.usuario,))
                con.execute('INSERT INTO personajes(usuario, char_id, ranura, nombre, datos) VALUES (?, ?, ?, ?, ?)',
                            (ses.usuario, ses.personaje.char_id, 0, ses.personaje.nombre, json.dumps({})))
        self.gid = cuentas.db_crear_gremio('BancoTest', 9901, 'Jefe', 50, 1)
        cuentas.db_agregar_miembro_gremio(self.gid, 9902, 'Miembro', 50, 1, rango=3)
        self.stats = patch('app._stats_ses', return_value=b'')
        self.stats.start()

    def tearDown(self):
        self.stats.stop()
        (cuentas.BASE, cuentas.DB_PATH, cuentas.BACKUPS_DIR,
         cuentas.ARCHIVO, cuentas._notificar_cambio) = self.original
        self.tmp.cleanup()

    def test_objeto_mejorado_y_permisos(self):
        self.jefe.personaje.mejoras = {20: {'veces': 7, 'huecos': 1, 'gemas': [42]}}
        app._banco_liga_depositar(self.jefe, 'test', 20, 1, 0)
        self.assertNotIn(20, self.jefe.inventario)
        self.assertEqual(cuentas.db_banco_gremio_detallado(self.gid)[1][2]['mejora']['veces'], 7)
        app._banco_liga_retirar(self.miembro, 'test', 1, 0, 0)
        self.assertIn(1, cuentas.db_banco_gremio(self.gid))
        app._banco_liga_retirar(self.jefe, 'test', 1, 20, 0)
        self.assertEqual(self.jefe.personaje.mejoras[20]['veces'], 7)
        self.assertEqual(self.jefe.personaje.mejoras[20]['gemas'], [42])
        self.assertFalse(cuentas.db_banco_gremio(self.gid))
        with cuentas._get_conn() as con:
            data = json.loads(con.execute('SELECT datos FROM personajes WHERE char_id=9901').fetchone()[0])
        self.assertEqual(data['inventario']['20'], 4)
        self.assertEqual(data['mejoras']['20']['veces'], 7)

    def test_oro_y_limite(self):
        app._banco_liga_depositar(self.jefe, 'test', 0, 0, 5000)
        self.assertEqual(self.jefe.oro, 95000)
        app._banco_liga_retirar(self.miembro, 'test', 0, 0, 1000)
        self.assertEqual(cuentas.db_obtener_gremio(self.gid)['fondos'], 5000)
        self.jefe.oro = 1999999900
        app._banco_liga_retirar(self.jefe, 'test', 0, 0, 1000)
        self.assertEqual(self.jefe.oro, 2000000000)
        self.assertEqual(cuentas.db_obtener_gremio(self.gid)['fondos'], 4900)

    def test_permisos_separados_para_objetos_y_oro(self):
        app._banco_liga_depositar(self.jefe, 'test', 0, 0, 5000)
        app._banco_liga_depositar(self.jefe, 'test', 20, 1, 0)
        cuentas.db_actualizar_permisos_gremio(self.gid, 3, gremios.GUILD_PERM_WITHDRAW_ITEM)
        app._banco_liga_retirar(self.miembro, 'test', 0, 0, 1000)
        self.assertEqual(cuentas.db_obtener_gremio(self.gid)['fondos'], 5000)
        app._banco_liga_retirar(self.miembro, 'test', 1, 21, 0)
        self.assertEqual(self.miembro.inventario[21], 4)
        cuentas.db_actualizar_permisos_gremio(self.gid, 3, gremios.GUILD_PERM_WITHDRAW_MONEY)
        app._banco_liga_retirar(self.miembro, 'test', 0, 0, 1000)
        self.assertEqual(cuentas.db_obtener_gremio(self.gid)['fondos'], 4000)

    def test_mascota_guardada_recupera_su_identidad(self):
        self.jefe.inventario[20] = 18624
        pet = {'ranura': 20, 'fuera': False, 'sprite': 3049, 'nombre': 'MiPet', 'nivel': 9}
        self.jefe.personaje.mascota = pet
        self.jefe.personaje.mascotas = {'20': pet}
        app._banco_liga_depositar(self.jefe, 'test', 20, 1, 0)
        self.assertEqual(cuentas.db_banco_gremio_detallado(self.gid)[1][2]['mascota']['nombre'], 'MiPet')
        app._banco_liga_retirar(self.jefe, 'test', 1, 22, 0)
        self.assertEqual(self.jefe.personaje.mascotas['22']['nombre'], 'MiPet')
        self.assertEqual(self.jefe.personaje.mascotas['22']['nivel'], 9)
        self.assertEqual(self.jefe.personaje.mascotas['22']['ranura'], 22)

    def test_error_db_no_mueve_objeto(self):
        with patch.object(cuentas, 'db_mover_banco_gremio', side_effect=ValueError('fallo simulado')):
            app._banco_liga_depositar(self.jefe, 'test', 20, 1, 0)
        self.assertEqual(self.jefe.inventario[20], 4)
        self.assertFalse(cuentas.db_banco_gremio(self.gid))

    def test_no_permite_guardar_mascota_invocada(self):
        self.jefe.inventario[20] = 18624
        self.jefe.personaje.mascota = {'ranura': 20, 'fuera': True, 'sprite': 3049}
        self.jefe.personaje.mascotas = {'20': {'ranura': 20, 'fuera': False, 'sprite': 3049}}
        app._banco_liga_depositar(self.jefe, 'test', 20, 1, 0)
        self.assertEqual(self.jefe.inventario[20], 18624)
        self.assertFalse(cuentas.db_banco_gremio(self.gid))

    def test_creacion_fallida_no_descuenta_oro(self):
        ses = self.miembro
        cuentas.db_remover_miembro_gremio(ses.personaje.char_id)
        with patch.object(cuentas, 'db_crear_gremio', side_effect=ValueError('fallo simulado')):
            cuerpo = b'OtraLiga'.ljust(17, b'\0') + struct.pack('<I', 0)
            gremios.procesar_crear_gremio(ses, cuerpo, [ses])
        self.assertEqual(ses.oro, 100000)
        self.assertIsNone(gremios.obtener_gremio_de(ses.personaje.char_id))

    def test_creacion_nombre_duplicado_hace_rollback_del_oro(self):
        cuentas.db_remover_miembro_gremio(9902)
        cuentas.guardar_oro(self.miembro.usuario, 9902, 100000)
        with self.assertRaises(Exception):
            cuentas.db_crear_gremio('BancoTest', 9902, 'Miembro', 50, 1,
                                    usuario=self.miembro.usuario, oro_final=40000)
        with cuentas._get_conn() as con:
            data = json.loads(con.execute('SELECT datos FROM personajes WHERE char_id=9902').fetchone()[0])
        self.assertEqual(data['oro'], 100000)
        self.assertIsNone(gremios.obtener_gremio_de(9902))


if __name__ == '__main__':
    unittest.main()
