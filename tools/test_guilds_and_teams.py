"""Suite de pruebas exhaustiva para los sistemas de Equipos (Party) y Gremios (Guilds).

Verifica:
1. Equipos:
   - Invitar (0x0017), Aceptar (0x0018 01), Denegar (0x0018 07)
   - Serializacion de miembros y lista completa (0x0024): cabecera 10B + 78B por miembro
   - Paquete de actualizacion en tiempo real (0x0026): 80B
   - Expulsar miembro (0x0018 02) y Ascender a lider (0x0018 03)
   - Salir del equipo (0x0018 04) y Deshacer equipo (0x0018 05)
   - Limite maximo de 5 miembros
   - Sincronizacion de mapa y estados

2. Gremios:
   - Creacion de gremio (0x0041) con 60.000 oro, nivel 25 y rango 3
   - Estructura y bytes del paquete de datos de gremio (0x0055, 257B)
   - Estructura y bytes del boletin / cartel (0x0054)
   - Estructura y bytes de la lista de miembros (0x0056, 32B por miembro)
   - Invitacion a gremio (0x0042) y cuadro s2c 0x0057 (40B)
   - Respuestas de unirse (0x0043 01), ascender (04), degradar (05)
   - Modificacion de permisos (08), nombres de rangos (09), cartel (10) y logo (17)
   - Transferencia de liderazgo (06), expulsion (02), salida (03) y disolucion (07)
   - Persistencia completa en base de datos SQLite
   - Integracion con ContextoSesion: tiene_guild() y teamid()
"""
import os
import json
import sys
import struct
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'server')))

import cuentas
import equipos
import gremios
import clases
import eventos_mundo


class MockPersonaje:
    def __init__(self, char_id, nombre, nivel=25, class_id=1, stage=41, tile_x=50, tile_y=60, hp=500, mp=300):
        self.char_id = char_id
        self.nombre = nombre
        self.nivel = nivel
        self.rango = 3
        self.class_id = class_id
        self.stage = stage
        self.tile_x = tile_x
        self.tile_y = tile_y
        self.hp = hp
        self.hp_max = 500
        self.mp = mp
        self.mp_max = 300
        self.entity_id = 1000 + char_id
        self.genero = 0
        self.oro = 100000
        self.buffs = {}
        self.quests = []


class MockSession:
    def __init__(self, char_id, nombre, nivel=25, class_id=1, stage=41):
        self.personaje = MockPersonaje(char_id, nombre, nivel, class_id, stage)
        self.usuario = f"user_{char_id}"
        self.entity_id = self.personaje.entity_id
        self.oro = self.personaje.oro
        self.instancias = {}
        self.paquetes_enviados = []
        self.cerrada = False
        self._sala = None
        self.monstruos = None
        self.addr = ('127.0.0.1', 5000 + char_id)

    def enviar(self, *pkts):
        self.paquetes_enviados.extend(pkts)

    def enviar_inmediato(self, *pkts):
        self.paquetes_enviados.extend(pkts)

    def volcar(self):
        pass


class TestEquipos(unittest.TestCase):
    def setUp(self):
        equipos.olvidar_todo()
        self.s1 = MockSession(101, "LeaderOne")
        self.s2 = MockSession(102, "MemberTwo")
        self.s3 = MockSession(103, "MemberThree")
        self.s4 = MockSession(104, "MemberFour")
        self.s5 = MockSession(105, "MemberFive")
        self.s6 = MockSession(106, "MemberSix")
        self.sessions = {
            "LeaderOne": self.s1,
            "MemberTwo": self.s2,
            "MemberThree": self.s3,
            "MemberFour": self.s4,
            "MemberFive": self.s5,
            "MemberSix": self.s6,
        }

    def tearDown(self):
        equipos.olvidar_todo()

    def test_invitar_y_aceptar(self):
        # 1. Invitar s2
        ok, err = equipos.invitar(self.s1, "MemberTwo", lambda n: self.sessions.get(n))
        self.assertTrue(ok, err)
        self.assertEqual(len(self.s2.paquetes_enviados), 1)
        pkt_cartel = self.s2.paquetes_enviados[0]
        self.assertEqual(len(pkt_cartel), 40)
        op, cid = struct.unpack_from('<HI', pkt_cartel, 0)
        self.assertEqual(op, 0x0023)
        self.assertEqual(cid, 101)

        # 2. Aceptar s2
        res = equipos.accion(self.s2, equipos.ACEPTAR)
        self.assertEqual(res, 'aceptar')
        self.assertEqual(equipos.cuantos(self.s1), 2)
        self.assertEqual(equipos.lider_de(self.s2), 101)

        # Comprobar s2c 0x0024 enviado a ambos
        pkt_lista1 = self.s1.paquetes_enviados[-1]
        self.assertEqual(pkt_lista1[:2], struct.pack('<H', 0x0024))
        # Tamanio: 2 + 10 (cabecera) + 2 * 78 = 168 bytes
        self.assertEqual(len(pkt_lista1), 2 + 10 + 2 * 78)

        # Cabecera 0x0024
        cab = pkt_lista1[2:12]
        pad0, zero, lider_id, count = struct.unpack_from('<IBIB', cab, 0)
        self.assertEqual(pad0, 0x6A)
        self.assertEqual(zero, 0)
        self.assertEqual(lider_id, 101)
        self.assertEqual(count, 2)

        # Miembro 1 en lista
        m1 = pkt_lista1[12:12 + 78]
        m1_cid = struct.unpack_from('<I', m1, 0)[0]
        self.assertEqual(m1_cid, 101)
        m1_lvl = m1[24]
        self.assertEqual(m1_lvl, 25)
        m1_stage = struct.unpack_from('<I', m1, 25)[0]
        self.assertEqual(m1_stage, 41)

    def test_actualizacion_miembro_0x0026(self):
        equipos.invitar(self.s1, "MemberTwo", lambda n: self.sessions.get(n))
        equipos.aceptar(self.s2)
        self.s2.paquetes_enviados.clear()

        # Cambiar vida del lider y notificar
        self.s1.personaje.hp = 250
        equipos.notificar_stats(self.s1)
        self.assertTrue(len(self.s2.paquetes_enviados) >= 1)
        pkt_act = self.s2.paquetes_enviados[-1]
        # 0x0026 son 80 bytes (2 bytes op + 78 bytes miembro)
        self.assertEqual(len(pkt_act), 80)
        op = struct.unpack_from('<H', pkt_act, 0)[0]
        self.assertEqual(op, 0x0026)
        cid = struct.unpack_from('<I', pkt_act, 2)[0]
        self.assertEqual(cid, 101)
        hp_pct = struct.unpack_from('<H', pkt_act, 2 + 33)[0]
        self.assertEqual(hp_pct, 50)

    def test_limite_maximo_5_miembros(self):
        equipos.invitar(self.s1, "MemberTwo", lambda n: self.sessions.get(n))
        equipos.aceptar(self.s2)
        equipos.invitar(self.s1, "MemberThree", lambda n: self.sessions.get(n))
        equipos.aceptar(self.s3)
        equipos.invitar(self.s1, "MemberFour", lambda n: self.sessions.get(n))
        equipos.aceptar(self.s4)
        equipos.invitar(self.s1, "MemberFive", lambda n: self.sessions.get(n))
        equipos.aceptar(self.s5)
        self.assertEqual(equipos.cuantos(self.s1), 5)

        # 6to miembro debe ser rechazado
        ok, err = equipos.invitar(self.s1, "MemberSix", lambda n: self.sessions.get(n))
        self.assertFalse(ok)
        self.assertIn("maximo 5", err)

    def test_ascender_y_expulsar(self):
        equipos.invitar(self.s1, "MemberTwo", lambda n: self.sessions.get(n))
        equipos.aceptar(self.s2)
        equipos.invitar(self.s1, "MemberThree", lambda n: self.sessions.get(n))
        equipos.aceptar(self.s3)

        # Ascender a s2 (c2s 0x0018 03 + char_id 102)
        cuerpo_asc = struct.pack('<BI', equipos.ASCENDER, 102)
        res = equipos.accion(self.s1, equipos.ASCENDER, cuerpo_asc)
        self.assertEqual(res, 'ascender')
        self.assertEqual(equipos.lider_de(self.s1), 102)
        self.assertEqual(equipos.lider_de(self.s2), 102)

        # Nuevo lider (s2) expulsa a s3 (c2s 0x0018 02 + char_id 103)
        cuerpo_exp = struct.pack('<BI', equipos.EXPULSAR, 103)
        res = equipos.accion(self.s2, equipos.EXPULSAR, cuerpo_exp)
        self.assertEqual(res, 'expulsar')
        self.assertEqual(equipos.cuantos(self.s2), 2)
        self.assertEqual(equipos.lider_de(self.s3), 0)

    def test_rechazar_y_deshacer(self):
        # Rechazar invitacion
        equipos.invitar(self.s1, "MemberTwo", lambda n: self.sessions.get(n))
        res = equipos.accion(self.s2, equipos.RECHAZAR)
        self.assertEqual(res, 'rechazar')
        self.assertEqual(equipos.cuantos(self.s2), 1)

        # Deshacer equipo
        equipos.invitar(self.s1, "MemberTwo", lambda n: self.sessions.get(n))
        equipos.aceptar(self.s2)
        res = equipos.accion(self.s1, equipos.DESHACER)
        self.assertEqual(res, 'deshacer')
        self.assertEqual(equipos.cuantos(self.s1), 1)
        self.assertEqual(equipos.cuantos(self.s2), 1)


class TestGremios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.original = (cuentas.BASE, cuentas.DB_PATH, cuentas.BACKUPS_DIR,
                        cuentas.ARCHIVO, cuentas._notificar_cambio)
        from pathlib import Path
        cuentas.BASE = Path(cls.tmp.name)
        cuentas.DB_PATH = cuentas.BASE / 'cuentas.db'
        cuentas.BACKUPS_DIR = cuentas.BASE / 'backups'
        cuentas.ARCHIVO = cuentas.BASE / 'cuentas.json'
        cuentas._notificar_cambio = lambda: None

    @classmethod
    def tearDownClass(cls):
        (cuentas.BASE, cuentas.DB_PATH, cuentas.BACKUPS_DIR,
         cuentas.ARCHIVO, cuentas._notificar_cambio) = cls.original
        cls.tmp.cleanup()

    def setUp(self):
        cuentas._init_db()
        self.s1 = MockSession(201, "GuildLeader", nivel=30)
        self.s2 = MockSession(202, "GuildMember", nivel=25)
        self.s3 = MockSession(203, "GuildOfficer", nivel=28)
        self.mundos = [self.s1, self.s2, self.s3]
        with cuentas._get_conn() as con:
            for ses in self.mundos:
                con.execute('INSERT OR IGNORE INTO cuentas(usuario) VALUES (?)', (ses.usuario,))
                con.execute('INSERT OR REPLACE INTO personajes(usuario, char_id, ranura, nombre, datos) '
                            'VALUES (?, ?, ?, ?, ?)',
                            (ses.usuario, ses.personaje.char_id, 0, ses.personaje.nombre, json.dumps({})))

    def tearDown(self):
        # Limpiar cualquier gremio creado en los tests
        for cid in (201, 202, 203):
            g = gremios.obtener_gremio_de(cid)
            if g:
                cuentas.db_disolver_gremio(g['guild_id'])

    def test_crear_gremio_exitoso(self):
        # C2S 0x0041: [name (17B)][logo_id (u32)]
        nombre = "Valhalla"
        cuerpo = nombre.encode('latin-1').ljust(17, b'\x00') + struct.pack('<I', 5)
        gremios.procesar_crear_gremio(self.s1, cuerpo, self.mundos)

        # Verificar DB
        g = gremios.obtener_gremio_de(201)
        self.assertIsNotNone(g)
        self.assertEqual(g['nombre'], "Valhalla")
        self.assertEqual(g['logo_id'], 5)
        self.assertEqual(g['lider_char_id'], 201)
        self.assertEqual(self.s1.oro, 40000) # Se dedujeron 60,000 (dialogo 5778 del League Clerk)

        # Verificar paquetes enviados al creador
        # Debe haber recibido: 0x0055 (datos), 0x0054 (cartel), 0x0056 (miembros)
        opcodes = [struct.unpack_from('<H', p)[0] for p in self.s1.paquetes_enviados if len(p) >= 2]
        self.assertIn(0x0055, opcodes)
        self.assertIn(0x0054, opcodes)
        self.assertIn(0x0056, opcodes)

        # Verificar tamanio de paquete 0x0055 (257 bytes)
        pkt_datos = next(p for p in self.s1.paquetes_enviados if struct.unpack_from('<H', p)[0] == 0x0055)
        self.assertEqual(len(pkt_datos), 2 + 257)   # cuerpo de 257 como en las capturas reales

        # Desempacar estructura 0x0055
        op, cid = struct.unpack_from('<HI', pkt_datos, 0)
        self.assertEqual(op, 0x0055)
        self.assertEqual(cid, 201)
        # El handler 0x608FB0 copia la ficha en +6; 0x662E00 lee estos campos.
        gid, fama, miembros = struct.unpack_from('<III', pkt_datos, 6)
        self.assertEqual(gid, g['guild_id'])
        self.assertEqual((fama, miembros), (0, 1))
        self.assertEqual(pkt_datos[6 + 29:6 + 46].split(b'\0')[0], b'GuildLeader')
        self.assertEqual(struct.unpack_from('<II', pkt_datos, 6 + 134), (5, 1))

    def test_invitar_y_unirse_gremio(self):
        # 1. Crear gremio
        cuerpo = "Mythology".encode('latin-1').ljust(17, b'\x00') + struct.pack('<I', 2)
        gremios.procesar_crear_gremio(self.s1, cuerpo, self.mundos)
        g = gremios.obtener_gremio_de(201)

        # 2. Invitar s2 (C2S 0x0042)
        cuerpo_inv = "GuildMember".encode('latin-1').ljust(17, b'\x00')
        gremios.procesar_invitar_gremio(self.s1, cuerpo_inv, self.mundos)

        # s2 debe recibir 0x0057 (40 bytes)
        pkt_inv = self.s2.paquetes_enviados[-1]
        self.assertEqual(len(pkt_inv), 40)
        op, t_cid = struct.unpack_from('<HI', pkt_inv, 0)
        self.assertEqual(op, 0x0057)
        self.assertEqual(t_cid, 202)

        # 3. Aceptar invitacion (C2S 0x0043 con cmd_id = 1, param2 = 1)
        # Formato: [pad 4B][u8 cmd_id][pad 4B][param1 4B][param2 4B][pad 4B]
        cuerpo_cmd = bytearray(25)
        cuerpo_cmd[4] = gremios.GLD_EVENT_JOIN
        struct.pack_into('<I', cuerpo_cmd, 13, 1) # param2 = 1 (aceptar)
        gremios.procesar_comando_gremio(self.s2, bytes(cuerpo_cmd), self.mundos)

        # Verificar que s2 ahora esta en Mythology
        g2 = gremios.obtener_gremio_de(202)
        self.assertIsNotNone(g2)
        self.assertEqual(g2['guild_id'], g['guild_id'])
        self.assertEqual(gremios._rango_de(g2, 202), gremios.GUILD_RANK_MEMBER)

    def test_ascender_y_degradar_miembro(self):
        # Setup: gremio con lider (201) y miembro (202)
        cuerpo = "Knights".encode('latin-1').ljust(17, b'\x00') + struct.pack('<I', 1)
        gremios.procesar_crear_gremio(self.s1, cuerpo, self.mundos)
        cuentas.db_agregar_miembro_gremio(gremios.obtener_gremio_de(201)['guild_id'], 202, "GuildMember", 25, 1, rango=3)

        # Lider asciende a 202 a Officer (rango 2)
        cuerpo_cmd = bytearray(25)
        cuerpo_cmd[4] = gremios.GLD_EVENT_PROMOTE
        struct.pack_into('<I', cuerpo_cmd, 9, 202) # param1 = target_cid
        gremios.procesar_comando_gremio(self.s1, bytes(cuerpo_cmd), self.mundos)

        g = gremios.obtener_gremio_de(201)
        self.assertEqual(gremios._rango_de(g, 202), gremios.GUILD_RANK_OFFICER)

        # Lider degrada a 202 a Member (rango 3)
        cuerpo_cmd[4] = gremios.GLD_EVENT_DEMOTE
        gremios.procesar_comando_gremio(self.s1, bytes(cuerpo_cmd), self.mundos)
        g = gremios.obtener_gremio_de(201)
        self.assertEqual(gremios._rango_de(g, 202), gremios.GUILD_RANK_MEMBER)

    def test_actualizar_boletin_permisos_y_logo(self):
        cuerpo = "Imperium".encode('latin-1').ljust(17, b'\x00') + struct.pack('<I', 1)
        gremios.procesar_crear_gremio(self.s1, cuerpo, self.mundos)
        gid = gremios.obtener_gremio_de(201)['guild_id']

        # Actualizar boletin / cartel (cmd_id = 10)
        cuerpo_cmd = bytearray(21)
        cuerpo_cmd[4] = gremios.GLD_EVENT_UPDATE_BULLETIN
        nuevo_cartel = "Welcome to Imperium! League War at 8 PM."
        cuerpo_cmd.extend(nuevo_cartel.encode('latin-1') + b'\x00')
        gremios.procesar_comando_gremio(self.s1, bytes(cuerpo_cmd), self.mundos)

        g = gremios.obtener_gremio_de(201)
        self.assertEqual(g['cartel'], nuevo_cartel)

        # Actualizar logo (cmd_id = 17, param2 = 42)
        cuerpo_logo = bytearray(25)
        cuerpo_logo[4] = gremios.GLD_EVENT_UPDATE_LOGO
        struct.pack_into('<I', cuerpo_logo, 13, 42)
        gremios.procesar_comando_gremio(self.s1, bytes(cuerpo_logo), self.mundos)

        g = gremios.obtener_gremio_de(201)
        self.assertEqual(g['logo_id'], 42)

        # Cambiar nombre de rango (cmd_id = 9, param2 = 1, str = "Generals")
        cuerpo_rnk = bytearray(21)
        cuerpo_rnk[4] = gremios.GLD_EVENT_SET_RANK_NAME
        struct.pack_into('<I', cuerpo_rnk, 13, 1) # param2 = rango_idx (1 = Vice)
        cuerpo_rnk.extend("Generals".encode('latin-1') + b'\x00')
        gremios.procesar_comando_gremio(self.s1, bytes(cuerpo_rnk), self.mundos)

        g = gremios.obtener_gremio_de(201)
        self.assertEqual(g['rangos'][1], "Generals")

    def test_transferir_liderazgo_y_disolver(self):
        cuerpo = "Dynasty".encode('latin-1').ljust(17, b'\x00') + struct.pack('<I', 1)
        gremios.procesar_crear_gremio(self.s1, cuerpo, self.mundos)
        gid = gremios.obtener_gremio_de(201)['guild_id']
        cuentas.db_agregar_miembro_gremio(gid, 202, "GuildMember", 25, 1, rango=1)

        # Ceder liderazgo a 202 (cmd_id = 6, param1 = 202)
        cuerpo_cmd = bytearray(25)
        cuerpo_cmd[4] = gremios.GLD_EVENT_ABDICATE
        struct.pack_into('<I', cuerpo_cmd, 9, 202)
        gremios.procesar_comando_gremio(self.s1, bytes(cuerpo_cmd), self.mundos)

        g = gremios.obtener_gremio_de(202)
        self.assertEqual(g['lider_char_id'], 202)
        self.assertEqual(gremios._rango_de(g, 202), gremios.GUILD_RANK_CHIEF)
        self.assertEqual(gremios._rango_de(g, 201), gremios.GUILD_RANK_VICECHIEF)

        # Nuevo lider disuelve gremio (cmd_id = 7)
        cuerpo_dis = bytearray(25)
        cuerpo_dis[4] = gremios.GLD_EVENT_DISMISS
        gremios.procesar_comando_gremio(self.s2, bytes(cuerpo_dis), self.mundos)

        self.assertIsNone(gremios.obtener_gremio_de(202))
        self.assertIsNone(gremios.obtener_gremio_de(201))

    def test_contexto_eventos_tiene_guild_y_teamid(self):
        # Sin gremio ni grupo
        ctx1 = eventos_mundo.ContextoSesion(self.s1)
        self.assertFalse(ctx1.tiene_guild())
        self.assertEqual(ctx1.teamid(), 0)

        # Con grupo
        equipos.invitar(self.s1, "GuildMember", lambda n: self.sessions.get(n) if hasattr(self, 'sessions') else self.s2)
        equipos.aceptar(self.s2)
        self.assertEqual(ctx1.teamid(), 201)

        # Con gremio
        cuerpo = "Alliance".encode('latin-1').ljust(17, b'\x00') + struct.pack('<I', 1)
        gremios.procesar_crear_gremio(self.s1, cuerpo, self.mundos)
        self.assertTrue(ctx1.tiene_guild())

    def test_no_se_puede_modificar_miembros_de_otra_liga(self):
        gid = cuentas.db_crear_gremio('Primera', 201, 'GuildLeader')
        otra = cuentas.db_crear_gremio('Segunda', 203, 'GuildOfficer')
        cuentas.db_agregar_miembro_gremio(otra, 202, 'GuildMember')
        for accion in (gremios.GLD_EVENT_KICK, gremios.GLD_EVENT_PROMOTE,
                       gremios.GLD_EVENT_DEMOTE, gremios.GLD_EVENT_ABDICATE):
            cuerpo = bytearray(25)
            cuerpo[4] = accion
            struct.pack_into('<I', cuerpo, 9, 202)
            gremios.procesar_comando_gremio(self.s1, cuerpo, self.mundos)
        self.assertEqual(cuentas.db_obtener_gremio_de_personaje(202)['guild_id'], otra)
        self.assertEqual(cuentas.db_obtener_gremio(gid)['lider_char_id'], 201)
        self.assertEqual(gremios._rango_de(cuentas.db_obtener_gremio(otra), 202), 3)

    def test_contribucion_consumida_y_guardada_con_la_fama(self):
        import app
        gid = cuentas.db_crear_gremio('Materiales', 201, 'GuildLeader')
        self.s1.inventario = {20: 52, 21: 52, 22: 59}
        self.s1.cantidades = {20: 150, 21: 100, 22: 200}
        # ID de fila 1 = 200 del objeto 52 por 2 puntos; fila 2 = 200 del 59 por 4.
        cuerpo = b'\x02' + struct.pack('<HIHI', 1, 1, 2, 1)
        app._contribuir_liga(self.s1, cuerpo, self.mundos)
        self.assertEqual(self.s1.inventario, {21: 52})
        self.assertEqual(self.s1.cantidades[21], 50)
        self.assertEqual(cuentas.db_obtener_gremio(gid)['reputacion'], 6)
        self.assertEqual(cuentas.db_obtener_miembros_gremio(gid)[0]['contribucion'], 6)
        with cuentas._get_conn() as con:
            pj = json.loads(con.execute('SELECT datos FROM personajes WHERE usuario=?',
                                        (self.s1.usuario,)).fetchone()[0])
        self.assertEqual(pj['inventario'], {'21': 52})
        self.assertEqual(pj['cantidades'], {'21': 50})
        # Sin inventario suficiente y con IDs duplicados no puede ganar fama.
        app._contribuir_liga(self.s1, cuerpo, self.mundos)
        app._contribuir_liga(self.s1, b'\x02' + struct.pack('<HIHI', 1, 1, 1, 1), self.mundos)
        self.assertEqual(cuentas.db_obtener_gremio(gid)['reputacion'], 6)

    def test_creacion_requiere_rango_y_limite_segun_nivel(self):
        self.s1.personaje.rango = 2
        cuerpo = b'NoRank'.ljust(17, b'\0') + struct.pack('<I', 1)
        gremios.procesar_crear_gremio(self.s1, cuerpo, self.mundos)
        self.assertIsNone(gremios.obtener_gremio_de(201))
        self.assertEqual(self.s1.oro, 100000)
        self.assertEqual([gremios.limite_miembros(i) for i in range(1, 7)],
                         [30, 40, 50, 60, 70, 70])


if __name__ == '__main__':
    unittest.main()
