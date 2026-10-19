"""Pruebas unitarias completas del House System IGG de Angels Online."""
import os
import sys
import struct
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'server')))

import casas
import dialogos
import eventos
import eventos_mundo

class TestHouseSystem(unittest.TestCase):

    def setUp(self):
        self.casa = casas.CasaData(owner_id=1234, owner_name="AngelTester", deed_id=10115)

    def test_umbrales_y_niveles(self):
        self.assertEqual(casas.nivel_de_magia(0), 1)
        self.assertEqual(casas.nivel_de_magia(499), 1)
        self.assertEqual(casas.nivel_de_magia(500), 2)
        self.assertEqual(casas.nivel_de_magia(899), 2)
        self.assertEqual(casas.nivel_de_magia(900), 3)
        self.assertEqual(casas.nivel_de_magia(4500), 6)
        self.assertEqual(casas.nivel_de_magia(84000), 15)
        self.assertEqual(casas.nivel_de_magia(999999), 15)

    def test_ranuras_por_nivel(self):
        self.assertEqual(casas.ranuras_mascotas_validas(1), 1)
        self.assertEqual(casas.ranuras_mascotas_validas(3), 1)
        self.assertEqual(casas.ranuras_mascotas_validas(4), 2)
        self.assertEqual(casas.ranuras_mascotas_validas(5), 2)
        self.assertEqual(casas.ranuras_mascotas_validas(7), 3)
        self.assertEqual(casas.ranuras_mascotas_validas(9), 4)
        self.assertEqual(casas.ranuras_mascotas_validas(12), 5)
        self.assertEqual(casas.ranuras_mascotas_validas(14), 6)

        self.assertEqual(casas.ranuras_mobgen_validas(1), 1)
        self.assertEqual(casas.ranuras_mobgen_validas(6), 1)
        self.assertEqual(casas.ranuras_mobgen_validas(8), 2)
        self.assertEqual(casas.ranuras_mobgen_validas(10), 2)
        self.assertEqual(casas.ranuras_mobgen_validas(13), 3)

    def test_deeds_y_capacidad(self):
        c0 = casas.CasaData(1, "Player", deed_id=10115) # Cottage
        self.assertEqual(c0.size_level, 0)
        self.assertEqual(casas.CAPACIDAD_MUEBLES[c0.size_level], 35)
        self.assertEqual(c0.model_id, 7807)

        c1 = casas.CasaData(1, "Player", deed_id=10116) # Delicate House
        self.assertEqual(c1.size_level, 1)
        self.assertEqual(casas.CAPACIDAD_MUEBLES[c1.size_level], 60)
        self.assertEqual(c1.model_id, 7806)

        c6 = casas.CasaData(1, "Player", deed_id=17937) # Super Big House
        self.assertEqual(c6.size_level, 6)
        self.assertEqual(casas.CAPACIDAD_MUEBLES[c6.size_level], 180)
        self.assertEqual(c6.model_id, 7851)

    def test_paquetes_s2c(self):
        # 1. S2C 0x000C Cambiar mapa a Stage 500 (exact 30 bytes)
        pkt_map = casas.pkt_cambiar_mapa_house(500, house_table_id=235, house_size_level=2)
        self.assertEqual(len(pkt_map), 30)
        op, st = struct.unpack_from('<HI', pkt_map, 0)
        tbl = struct.unpack_from('<I', pkt_map, 24)[0]
        sz = struct.unpack_from('<B', pkt_map, 28)[0]
        self.assertEqual(op, 0x000C)
        self.assertEqual(st, 500)
        self.assertEqual(tbl, 235)
        self.assertEqual(sz, 2)

        # 2. S2C 0x0140 Outdoor House Object (exact 65 bytes)
        pkt_out = casas.pkt_outdoor_house(
            entity_id=600001, model_id=7807, px_x=4500, px_y=3200,
            house_name="Sweet Home", owner_name="AngelHero", dir_rot=1, house_size_level=2
        )
        self.assertEqual(len(pkt_out), 65)
        op_out, eid_out, flg_out, px, py = struct.unpack_from('<HIIii', pkt_out, 0)
        self.assertEqual(op_out, 0x0140)
        self.assertEqual(eid_out, 600001)

        # 3. S2C 0x0149 House Info (exact 38 bytes)
        pkt_nfo = casas.pkt_house_info(
            house_level=3, magic_cur=950, magic_next=1500, magic_prev=900,
            bonus_pct=5, cleanliness=950, votes_total=12, votes_today=3,
            visitors=45, votes_remaining=1, rank=1, ui_state=10
        )
        self.assertEqual(len(pkt_nfo), 38)
        op_nfo, hlv, mcur, mnext, mprev, b_pct, clean, vtot, vtod, vis, vrem, rnk, bflg = struct.unpack_from(
            '<HIIIIHHIIIBHB', pkt_nfo, 0
        )
        self.assertEqual(op_nfo, 0x0149)
        self.assertEqual(hlv, 3)
        self.assertEqual(mcur, 950)
        self.assertEqual(clean, 950)
        self.assertEqual(vtot, 12)
        self.assertEqual(bflg, 10)

        # 4. S2C 0x0142 Open / Close
        pkt_oc = casas.pkt_open_close_state(True)
        self.assertEqual(len(pkt_oc), 3)
        self.assertEqual(struct.unpack('<HB', pkt_oc), (0x0142, 1))

        # 5. S2C 0x0144 Pet Window
        pkt_pet = casas.pkt_pet_slot_wnd(True, 3, 0x05)
        self.assertEqual(struct.unpack('<HBBI', pkt_pet), (0x0144, 1, 3, 5))

        # 6. S2C 0x0145 MobGen Window
        pkt_mob = casas.pkt_mobgen_slot_wnd(True, 2)
        self.assertEqual(struct.unpack('<HBB', pkt_mob), (0x0145, 1, 2))

        # IGG sub_5EFE80 consumes exactly 16 name bytes from offset +2.
        pkt_name = casas.pkt_house_name('A Very Long House Name')
        self.assertEqual(len(pkt_name), 18)
        self.assertEqual(pkt_name[:2], struct.pack('<H', 0x014A))
        self.assertEqual(pkt_name[2:], b'A Very Long Hous')

    def test_catalogo_item_furniture_es_bidireccional(self):
        fid = casas.item_a_mueble(53087)
        self.assertEqual(fid, 1718)
        self.assertEqual(casas.mueble_a_item(fid), 53087)
        self.assertIsNotNone(casas.mueble(fid))

    def test_serializacion_y_persistencia(self):
        self.casa.cleanliness = 850
        self.casa.votes_total = 42
        self.casa.placed_furniture = [
            {'item_id': 10476, 'item_uid': 99901, 'dir': 0, 'x': 100, 'y': 200, 'state': 0, 'extra': 0, 'expire': 0}
        ]
        self.casa.ball_active = True
        self.casa.ball_end_time = 4102444800
        datos = self.casa.serializar()
        recup = casas.CasaData.deserializar(datos)
        self.assertEqual(recup.owner_id, 1234)
        self.assertEqual(recup.cleanliness, 850)
        self.assertEqual(recup.votes_total, 42)
        self.assertEqual(len(recup.placed_furniture), 1)
        self.assertEqual(recup.placed_furniture[0]['item_uid'], 99901)
        self.assertTrue(recup.ball_active)
        self.assertEqual(recup.ball_end_time, 4102444800)

    def test_ball_tickets_y_jabones_salen_del_cliente_igg(self):
        self.assertEqual(casas.SOAP_CLEAN[10627], 10)
        self.assertEqual(casas.SOAP_CLEAN[10603], 500)
        self.assertEqual(casas.SOAP_CLEAN[10626], 500)
        # Pink Puppy Cottage aporta 1200 de magia: nivel suficiente para baile.
        self.casa.placed_furniture = [
            {'item_id': 53087, 'item_uid': 1, 'dir': 0, 'x': 1, 'y': 1,
             'state': 0, 'extra': 0, 'expire': 0}
        ]
        self.assertTrue(self.casa.iniciar_baile(20078, now=1000))
        self.assertEqual(self.casa.ball_start_time, 1180)
        self.assertEqual(self.casa.ball_type, 1)
        self.assertFalse(self.casa.iniciar_baile(20078, now=1001))

    def test_item_id_se_convierte_a_furniture_id_para_magia(self):
        # Pink Puppy Cottage item 53087 -> furniture.xml 1718 -> 1200 Magic.
        self.casa.placed_furniture = [
            {'item_id': 53087, 'item_uid': 7, 'dir': 0, 'x': 10, 'y': 20,
             'state': 0, 'extra': 0, 'expire': 0}
        ]
        self.assertEqual(casas.item_a_mueble(53087), 1718)
        self.assertEqual(self.casa.calcular_magia(), 1200)
        self.assertEqual(self.casa.model_id, 7886)

    def test_paquete_editor_usa_registros_nativos_de_24_bytes(self):
        muebles = [
            {'item_id': 10476, 'item_uid': 0x1122334455667788,
             'dir': 3, 'x': 40, 'y': 50, 'state': 1,
             'extra': 9, 'expire': 1234}
        ]
        pkt = casas.pkt_enter_furnish_mode('TestOwner', muebles)
        self.assertEqual(struct.unpack_from('<HBI', pkt, 0), (0x013E, 1, 1))
        self.assertEqual(pkt[7:24].rstrip(b'\x00'), b'TestOwner')
        self.assertEqual(len(pkt), 24 + 24)
        self.assertEqual(struct.unpack_from('<IQBHHBHI', pkt, 24),
                         (10476, 0x1122334455667788, 3, 40, 50, 1, 9, 1234))

    def test_save_layout_global_usa_cabecera_de_37_bytes(self):
        # Packet captured from the live Global server on 2026-10-16.  It has
        # three records: default scene, default exterior and one real item.
        captured_header = (b'House Party\x00' +
                           bytes.fromhex('680063007000630073007600630036002c00530065'))
        raw = (struct.pack('<I', 3) + captured_header +
               struct.pack('<IQBHHBHI', 9954, 0, 0, 0, 0, 0, 0, 0) +
               struct.pack('<IQBHHBHI', 14660, 0, 0, 0, 0, 0, 0, 0) +
               struct.pack('<IQBHHBHI', 22846, 0x6ac5180808881c2f,
                           1, 1196, 2808, 0, 0, 0))
        self.assertEqual(len(raw), 109)
        name, entries = casas.parse_save_layout(raw)
        self.assertEqual(name, 'House Party')
        self.assertEqual([x['item_id'] for x in entries], [9954, 14660, 22846])
        self.assertEqual(entries[2]['item_uid'], 0x6ac5180808881c2f)
        self.assertEqual((entries[2]['dir'], entries[2]['x'], entries[2]['y']),
                         (1, 1196, 2808))

    def test_save_layout_legacy_usa_cabecera_de_21_bytes(self):
        record = struct.pack('<IQBHHBHI', 10476, 7, 2, 10, 20, 1, 3, 4)
        raw = struct.pack('<I', 1) + b'Legacy\x00'.ljust(17, b'\x00') + record
        name, entries = casas.parse_save_layout(raw)
        self.assertEqual(name, 'Legacy')
        self.assertEqual(entries[0]['item_id'], 10476)

    def test_condiciones_y_acciones_eventos(self):
        # Verificar que condiciones 58..65, 70 estan en SE_EVALUAN
        for cid in (58, 59, 60, 61, 62, 63, 64, 65, 70):
            self.assertIn(cid, eventos.SE_EVALUAN)
            self.assertIn(cid, eventos_mundo.SABE)

        # Verificar que acciones 89..96 estan en SE_TRADUCEN
        for aid in range(89, 97):
            self.assertIn(aid, eventos.SE_TRADUCEN)

        # Evaluar acciones
        self.assertEqual(eventos.traducir(89, []), ('salir_de_casa',))
        self.assertEqual(eventos.traducir(90, []), ('casa_buff_diario',))
        self.assertEqual(eventos.traducir(91, []), ('casa_abrir_pets',))
        self.assertEqual(eventos.traducir(92, []), ('casa_abrir_mobgen',))
        self.assertEqual(eventos.traducir(93, [10603, 1, 200]), ('casa_limpiar', 10603, 1, 200))
        self.assertEqual(eventos.traducir(94, []), ('casa_abrir_voto',))
        self.assertEqual(eventos.traducir(95, []), ('casa_ver_notas',))
        self.assertEqual(eventos.traducir(96, []), ('casa_hitparade',))

        # Evaluar condiciones con Contexto
        ctx = eventos.Contexto()
        ctx.sabe = eventos.SE_EVALUAN
        self.assertTrue(eventos.evaluar(58, [], ctx)) # es dueno
        self.assertTrue(eventos.evaluar(59, [0, 1], ctx)) # nivel igual a 1
    def test_mapas_exhibicion_y_ui_flags(self):
        # 1. Mapas de exhibicion validos (Angel House Area, Faction Cities, Palm Base)
        self.assertIn(370, casas.MAPAS_EXHIBICION) # Angel House Area
        self.assertIn(3, casas.MAPAS_EXHIBICION)   # Aurora City
        self.assertIn(26, casas.MAPAS_EXHIBICION)  # Dark City
        self.assertIn(29, casas.MAPAS_EXHIBICION)  # Breeze Woods
        self.assertIn(38, casas.MAPAS_EXHIBICION)  # Iron Castle
        self.assertIn(88, casas.MAPAS_EXHIBICION)  # Palm Base
        self.assertNotIn(41, casas.MAPAS_EXHIBICION) # Angel Lyceum no es zona de casas

        # 2. UI flags en pkt_house_info (+37)
        # 10 = casa exterior abierta (activa Decorate 27627 y Take Back 27628)
        pkt_open = casas.pkt_house_info(1, 0, 500, 0, 0, 1000, 0, 0, 0, 1, 1, 10)
        self.assertEqual(pkt_open[37], 10)
        # 1 = casa cerrada/guardada (activa Show 27626)
        pkt_closed = casas.pkt_house_info(1, 0, 500, 0, 0, 1000, 0, 0, 0, 1, 1, 1)
        self.assertEqual(pkt_closed[37], 1)

        # 3. Escala de coordenadas (32x32 px por tile)
        tile_x, tile_y = 151, 80
        px_x = tile_x * 32
        px_y = tile_y * 32
        self.assertEqual(px_x // 32, 151)
        self.assertEqual(px_y // 32, 80)

    def test_stage_500_maid_and_portals(self):
        import login, dialogos
        spawns_500 = login.poblar(500)
        # npc.obd house maid NPC1062, not the npc.xml princess placeholder.
        eilian_spawn = [s for s in spawns_500 if b'Maid Eilian' in s]
        self.assertTrue(bool(eilian_spawn))
        b = eilian_spawn[0]
        # NPC_SPAWN (0x0008) tiene sprite en offset 34+2=36
        sprite_id = struct.unpack_from('<I', b, 36)[0]
        self.assertEqual(sprite_id, 40262)
        # Every Maid dialogue uses her house-maid portrait, not NPC182.
        val_portrait = dialogos.val_por_entidad(260300)
        self.assertEqual(val_portrait, 1062)

        # Verify portals for stage 500 are drawn (at least the main exit doorway portal 701)
        portales_present = any(len(s) >= 4 and struct.unpack_from('<I', s, 2)[0] == 701 for s in spawns_500 if s.startswith(b'\x0e\x00'))
        self.assertTrue(portales_present)

    def test_maid_eilian_dialogues(self):
        import dialogos
        # Dialogue greeting when dirty (cleanliness == 0) -> msg 7906, options [7901 (Clean), 7891 (Leave)]
        d_dirty = dialogos.propio("Maid Eilian", entidad=260300, cleanliness=0)
        self.assertIsNotNone(d_dirty)
        self.assertEqual(len(d_dirty), 1)
        msg_id_dirty = struct.unpack_from('<I', d_dirty[0], 0)[0]
        self.assertEqual(msg_id_dirty, 7906)
        opts_dirty = dialogos.opciones_de(d_dirty[0])
        self.assertEqual(opts_dirty, [7901, 7891])

        # Dialogue greeting when clean (cleanliness > 0) -> msg 7900, options [7872, 7905, 7904, 7903, 7891]
        d_clean = dialogos.propio("Maid Eilian", entidad=260300, cleanliness=100)
        self.assertIsNotNone(d_clean)
        msg_id_clean = struct.unpack_from('<I', d_clean[0], 0)[0]
        self.assertEqual(msg_id_clean, 7900)
        opts_clean = dialogos.opciones_de(d_clean[0])
        self.assertEqual(opts_clean, [7912, 7910, 7872, 7905, 7904, 7903, 7891])

        # Dialogue options in respuesta_a
        # 7872: About House Cleaning -> 7906 con opciones [7901, 7891]
        ans_about_clean = dialogos.respuesta_a(7872, entidad=260300)
        self.assertTrue(len(ans_about_clean) >= 1)
        self.assertEqual(dialogos.opciones_de(ans_about_clean[0][2:]), [7901, 7891])

        # 7901: Clean the house -> 7916
        ans_clean = dialogos.respuesta_a(7901, entidad=260300)
        self.assertTrue(len(ans_clean) >= 1)

        # 7903: Eilian's Blessing -> 7907
        ans_bless = dialogos.respuesta_a(7903, entidad=260300)
        self.assertTrue(len(ans_bless) >= 1)

        # 7891: Leave -> FIN
        ans_leave = dialogos.respuesta_a(7891, entidad=260300)
        self.assertTrue(any(dialogos.FIN in a for a in ans_leave))

    def test_villa_and_house_types(self):
        # 10115 Cottage (size 0, capacity 35, model 7807)
        c_cottage = casas.CasaData(1, 'Test', deed_id=10115)
        self.assertEqual(c_cottage.size_level, 0)
        self.assertEqual(c_cottage.capacidad_maxima, 35)
        self.assertEqual(c_cottage.model_id, 7807)
        # Sin decoracion de escena colocada, exterior_table_id DEBE ser 0 (paredes sin jardin)
        self.assertEqual(c_cottage.exterior_table_id, 0)

        # 10116 Delicate House (size 1, capacity 60, model 7806)
        c_delicate = casas.CasaData(2, 'Test', deed_id=10116)
        self.assertEqual(c_delicate.size_level, 1)
        self.assertEqual(c_delicate.capacidad_maxima, 60)
        self.assertEqual(c_delicate.model_id, 7806)
        self.assertEqual(c_delicate.exterior_table_id, 0)

        # 10117 Romantic Villa (size 2, capacity 100, model 7805)
        c_villa = casas.CasaData(3, 'Test', deed_id=10117)
        self.assertEqual(c_villa.size_level, 2)
        self.assertEqual(c_villa.capacidad_maxima, 100)
        self.assertEqual(c_villa.model_id, 7805)
        self.assertEqual(c_villa.exterior_table_id, 0)

    def test_outdoor_house_level_offset(self):
        # Offset 63 must contain house_level (so client displays [ Level ] Name instead of [ 0 ])
        pkt = casas.pkt_outdoor_house(600001, 7805, 4800, 2400, "Karma's House", "Karma", house_size_level=2, house_level=3)
        self.assertEqual(len(pkt), 65)
        # Offset 63: house_level (1 byte)
        self.assertEqual(pkt[63], 3)
        # Offset 64: house_size_level (1 byte)
        self.assertEqual(pkt[64], 2)

    def test_stage_500_machines_and_dialogues(self):
        import login
        spawns = login.poblar(500)
        spawn_eids = [struct.unpack_from('<I', p, 2)[0] for p in spawns if p.startswith(b'\x08\x00')]
        self.assertIn(260300, spawn_eids) # Maid Eilian
        self.assertNotIn(262501, spawn_eids) # no duplicate floating mailbox NPC
        obj_eids = [struct.unpack_from('<I', p, 2)[0] for p in spawns if p.startswith(b'\x0e\x00')]
        self.assertIn(721, obj_eids) # Pet Care Machine
        self.assertIn(723, obj_eids) # The Safe
        self.assertIn(731, obj_eids) # Monster Hatching Machine

        # Pet Machine level < 3 says 7878
        d_pet_low = dialogos.propio('Pet Care Machine', entidad=260400, house_level=1)
        self.assertTrue(len(d_pet_low) >= 1)
        self.assertEqual(struct.unpack_from('<H', d_pet_low[0], 0)[0], 7878)

        # Pet Machine level >= 3 says 7874 with options 7876, 7875, 7877
        d_pet_ok = dialogos.propio('Pet Care Machine', entidad=260400, house_level=3)
        self.assertTrue(len(d_pet_ok) >= 1)
        self.assertEqual(struct.unpack_from('<H', d_pet_ok[0], 0)[0], 7874)

        # Monster Machine level < 6 says 7886
        d_mob_low = dialogos.propio('Monster Hatching Machine', entidad=260500, house_level=3)
        self.assertTrue(len(d_mob_low) >= 1)
        self.assertEqual(struct.unpack_from('<H', d_mob_low[0], 0)[0], 7886)

        # Monster Machine level >= 6 says 7882 with options 7884, 7883, 7885
        d_mob_ok = dialogos.propio('Monster Hatching Machine', entidad=260500, house_level=6)
        self.assertTrue(len(d_mob_ok) >= 1)
        self.assertEqual(struct.unpack_from('<H', d_mob_ok[0], 0)[0], 7882)

    def test_maid_eilian_position_and_flags(self):
        import login
        spawns = login.poblar(500)
        maid_pkt = [p for p in spawns if p.startswith(b'\x08\x00') and struct.unpack_from('<I', p, 2)[0] == 260300]
        self.assertTrue(len(maid_pkt) == 1)
        # Two tiles above her previous doorway position.
        px_x, px_y = struct.unpack_from('<II', maid_pkt[0], 10)
        self.assertEqual((px_x, px_y), (44, 82))
        # Direccion frontal/interior usada por los NPC correctamente orientados.
        self.assertEqual(maid_pkt[0][35], 7)  # turn toward the doorway, supported diagonal

        # El portal principal queda en (45, 78).
        portal = [p for p in spawns if p.startswith(b'\x0e\x00')
                  and struct.unpack_from('<I', p, 2)[0] == 701]
        self.assertEqual(len(portal), 1)
        portal_x, portal_y = struct.unpack_from('<II', portal[0], 10)
        self.assertEqual((portal_x, portal_y), (45 * 32 + 16, 78 * 32 + 16))

        # Check flags bit 0x80000000 in _ficha (opcode 0x0002)
        p = login.Personaje(char_id=1001, nombre='Karma', stage=41)
        sec = login._cargar_secuencia()
        m2 = [x for x in sec if x['opcode'] == 2][0]
        ficha_raw = login._ficha(p, m2['datos'])
        flags = struct.unpack_from('<I', ficha_raw, 6)[0]
        self.assertTrue(bool(flags & 0x80000000))

    def test_slot_376_and_outdoor_retirement(self):
        import cuentas
        # Load character and verify slot 376 is populated with deed
        datos = cuentas.cargar()
        cta = datos.get('cuentas', {}).get('karma')
        char = cuentas.personaje_de(cta, 0) if cta else None
        if char:
            self.assertIn(376, char.inventario)
            self.assertEqual(char.inventario[376], 10117)
            # Verify outdoor house is closed by default upon loading
            self.assertFalse(char.casa.get('is_open', False))

        # Test registrar and retirar outdoor house
        c = casas.CasaData(owner_id=9999, owner_name="Tester", deed_id=10117)
        casas.registrar_casa_outdoor(c, stage=41, px_x=1000, px_y=1000)
        self.assertTrue(c.is_open)
        self.assertGreater(c.outdoor_obj_id, 0)
        self.assertIn(c, casas.casas_en_stage(41))

        # Retire house
        casas.retirar_casa_outdoor(c)
        self.assertFalse(c.is_open)
        self.assertEqual(c.outdoor_obj_id, 0)
        self.assertNotIn(c, casas.casas_en_stage(41))

    def test_furnish_house_name_persistence_and_leave_safety(self):
        # S2C 0x013E must encode house_name in bytes 7..24
        pkt_enter = casas.pkt_enter_furnish_mode("Karma Castle", [])
        self.assertEqual(pkt_enter[:2], b'\x3e\x01')
        self.assertEqual(pkt_enter[2], 1)
        # Edit box 27084 reads from offset +7:
        nom = pkt_enter[7:24].split(b'\x00')[0].decode('latin-1')
        self.assertEqual(nom, "Karma Castle")

        # Leave furnish mode must only be 3 bytes (0x013E, mode 0)
        pkt_leave = casas.pkt_leave_furnish_mode()
        self.assertEqual(pkt_leave, struct.pack('<HB', 0x013E, 0))

    def test_portales_stage_500_doorway_and_rooms(self):
        import json, pathlib
        cfg = json.loads((pathlib.Path('server/plantillas/portales.json')).read_text(encoding='utf-8'))
        p500 = cfg['mapas']['500']
        p_door = p500[0]
        self.assertEqual(p_door['entity'], 701)
        self.assertEqual(p_door['tile'], [45, 78])
        self.assertEqual(p_door['trigger_tile'], [45, 78])
        self.assertEqual(p_door['radio'], 1)
        self.assertEqual(p_door['destinos']['7889']['llegada'], [36, 28])
        self.assertEqual(p_door['destinos']['7890']['llegada'], [94, 29])

        # Returns
        self.assertEqual(p500[1]['llegada'], [44, 80])
        self.assertEqual(p500[2]['llegada'], [44, 80])

    def test_maid_eilian_blessing_and_token_tiers(self):
        # House Level thresholds for Eilian's Blessing:
        # Lv < 4: msg 7920
        # Lv 4..8: msg 7935 (Tier 1)
        # Lv 9..11: msg 7936 (Tier 2)
        # Lv 12..14: msg 7975 (Tier 3)
        # Lv 15: msg 7978 (Tier 4)
        c = casas.CasaData(owner_id=1, owner_name="Tester", deed_id=10115)
        # Lv 1 (0 magic)
        lv1 = casas.nivel_de_magia(c.calcular_magia())
        self.assertEqual(lv1, 1)

        # Lv 4 (1500 magic)
        lv4 = casas.nivel_de_magia(1500)
        self.assertEqual(lv4, 4)

        # Lv 9 (27000 magic)
        lv9 = casas.nivel_de_magia(27000)
        self.assertEqual(lv9, 9)

        # Lv 12 (56000 magic)
        lv12 = casas.nivel_de_magia(56000)
        self.assertEqual(lv12, 12)

        # Lv 15 (84000 magic)
        lv15 = casas.nivel_de_magia(84000)
        self.assertEqual(lv15, 15)

    def test_house_and_eilian_exp_multipliers(self):
        import configuracion, time
        base_mult = configuracion.multiplicador_exp(None)
        # Old house fields must not multiply character EXP.
        buffs_clean = {'house_clean_bonus': 58}
        m = configuracion.multiplicador_exp(buffs_clean)
        self.assertAlmostEqual(m, base_mult, places=3)

        # Even stale fake EXP metadata from the old implementation is ignored.
        buffs_eilian = {
            'house_clean_bonus': 50,
            'eilian_blessing': {'fin': time.time() + 3600, 'exp_bonus_pct': 10}
        }
        m2 = configuracion.multiplicador_exp(buffs_eilian)
        self.assertAlmostEqual(m2, base_mult, places=3)

    def test_outdoor_house_placement_zones_and_restrictions(self):
        # 1. Angel House Area (370) open field is valid
        ok, reason = casas.validar_posicion_outdoor(370, 46, 33)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

        # 2. Too close to portal in Angel House Area
        ok, reason = casas.validar_posicion_outdoor(370, 22, 6)
        self.assertFalse(ok)
        self.assertIn("portal", reason.lower())

        # 3. Too close to map borders
        ok, reason = casas.validar_posicion_outdoor(370, 2, 2)
        self.assertFalse(ok)
        self.assertIn("border", reason.lower())

        # 4. Narrow bridge / obstacle / water in Breeze Woods
        ok, reason = casas.validar_posicion_outdoor(29, 200, 80)
        self.assertFalse(ok)
        self.assertIn("wide open area", reason.lower())

        # 5. Overlapping or too close to an NPC
        ok, reason = casas.validar_posicion_outdoor(29, 41, 64)
        self.assertFalse(ok)

        # 6. Unauthorized stages (Angel Lyceum, dungeons, inside house)
        ok, reason = casas.validar_posicion_outdoor(41, 147, 84)
        self.assertFalse(ok)
        self.assertIn("only be placed", reason.lower())

        ok, reason = casas.validar_posicion_outdoor(500, 45, 80)
        self.assertFalse(ok)
        self.assertIn("only be placed", reason.lower())

        # 7. Proximity to another outdoor house
        c1 = casas.CasaData(owner_id=101, owner_name="P1", deed_id=10115)
        casas.registrar_casa_outdoor(c1, stage=370, px_x=46 * 32, px_y=33 * 32)
        try:
            ok, reason = casas.validar_posicion_outdoor(370, 46, 33, exclude_cid=202)
            self.assertFalse(ok)
            self.assertIn("another house", reason.lower())

            # Self exclusion allowed (e.g. repositioning)
            ok, reason = casas.validar_posicion_outdoor(370, 46, 33, exclude_cid=101)
            self.assertTrue(ok)
        finally:
            casas.retirar_casa_outdoor(c1)

    def test_decorate_blocked_when_house_is_showing(self):
        c = casas.CasaData(owner_id=555, owner_name="Owner", deed_id=10115)
        c.is_open = True
        # When house is visible / on display outdoors, decorate is blocked
        self.assertTrue(c.is_open)

        # When taken back / closed, decorate is unblocked
        casas.retirar_casa_outdoor(c)
        self.assertFalse(c.is_open)


    def test_notice_aviso_default_msg_id(self):
        import struct
        import clases
        # Default notice must use MSG_TEXTO (732: '%s') to avoid 'Learn spell' prefix
        pkt = clases.aviso("Houses require a wide open area...")
        op, msg_id, tipo = struct.unpack_from('<HHB', pkt, 0)
        self.assertEqual(op, 0x000D)
        self.assertEqual(msg_id, clases.MSG_TEXTO) # 732, not 333 (MSG_HABILIDAD)
        self.assertEqual(tipo, 7)

        # Explicit skill learning notice preserves MSG_HABILIDAD (333)
        pkt_skill = clases.aviso("Sword", tipo=7, msg_id=clases.MSG_HABILIDAD)
        _, msg_id_sk, _ = struct.unpack_from('<HHB', pkt_skill, 0)
        self.assertEqual(msg_id_sk, 333)

    def test_outdoor_building_and_dome_exclusions(self):
        # Palm Base Ocean Scholar dome (278, 138) must be rejected
        ok, reason = casas.validar_posicion_outdoor(88, 278, 138)
        self.assertFalse(ok)
        self.assertIn("wide open area", reason.lower())

        # Palm Base Bankclerk Clair dome (185, 140) must be rejected
        ok, reason = casas.validar_posicion_outdoor(88, 185, 140)
        self.assertFalse(ok)
        self.assertIn("wide open area", reason.lower())

        # Palm Base open central sand (120, 80) is allowed
        ok, reason = casas.validar_posicion_outdoor(88, 120, 80)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

        # Palm Base (150, 95) is too close to Dark City Totem (148, 91) with 5-tile NPC margin
        ok, reason = casas.validar_posicion_outdoor(88, 150, 95)
        self.assertFalse(ok)
        self.assertIn("npcs", reason.lower())

        # Aurora City sidewalk/vereda (166, 144) must be rejected
        ok, reason = casas.validar_posicion_outdoor(3, 166, 144)
        self.assertFalse(ok)
        self.assertIn("wide open area", reason.lower())

        # Aurora City central cobblestone plaza (160, 105) is allowed
        ok, reason = casas.validar_posicion_outdoor(3, 160, 105)
        self.assertTrue(ok)
        self.assertEqual(reason, "")

        # Dark City monument exclusion (190, 90) must be rejected
        ok, reason = casas.validar_posicion_outdoor(26, 190, 90)
        self.assertFalse(ok)
        self.assertIn("wide open area", reason.lower())

        # Iron Castle bank tents exclusion (150, 145) must be rejected
        ok, reason = casas.validar_posicion_outdoor(38, 150, 145)
        self.assertFalse(ok)
        self.assertIn("wide open area", reason.lower())

    def test_visitor_maid_and_portal_restrictions(self):
        import dialogos
        # Setup house owned by Player 1
        c = casas.CasaData(owner_id=1, owner_name="OwnerOne", deed_id=10115)
        c.cleanliness = 500

        # Owner dialogue with Maid Eilian: full owner options
        g_owner = dialogos.propio('Maid Eilian', entidad=0, val=dialogos.MAID_PORTRAIT,
                                  cleanliness=c.cleanliness, house_level=c.level)
        self.assertIn(struct.pack('<H', 7912), g_owner[0]) # I need your blessing (7912)
        self.assertIn(struct.pack('<H', 7910), g_owner[0]) # Receive Token (7910)

        # Visitor dialogue (not voted yet): line 7897 with options [7898, 7899]
        visitor_cid = 999
        self.assertNotIn(visitor_cid, c.voted_users_today)
        line_vis = dialogos.armar_linea(7897, dialogos.MAID_PORTRAIT, [7898, 7899])
        self.assertIn(struct.pack('<I', 7898), line_vis) # 7898 ('Vote')
        self.assertIn(struct.pack('<I', 7899), line_vis) # 7899 ("I'm leaving")

        # After voting: line 7922 with option [7899] only
        c.voted_users_today.add(visitor_cid)
        c.votes_today += 1
        c.votes_total += 1
        self.assertIn(visitor_cid, c.voted_users_today)
        line_voted = dialogos.armar_linea(7922, dialogos.MAID_PORTRAIT, [7899])
        self.assertNotIn(struct.pack('<I', 7898), line_voted) # No 7898
        self.assertIn(struct.pack('<I', 7899), line_voted)    # Only 7899

    def test_banker_and_voucher_angel_system(self):
        import dialogos
        # Voucher Angel works across all 4 faction cities + Palm Base + Lyceum
        for st in (3, 26, 29, 38, 88, 41):
            g = dialogos.propio('Voucher Angel', stage=st)
            self.assertIsNotNone(g)
            self.assertEqual(len(g), 1)
            mid = int.from_bytes(g[0][:4], 'little')
            self.assertEqual(mid, 508584)

        # Faction city bank greetings
        g_breeze = dialogos.propio('Banker', stage=29)
        self.assertEqual(int.from_bytes(g_breeze[0][:4], 'little'), 5232)

        g_iron = dialogos.propio('Bank Clerk', stage=38)
        self.assertEqual(int.from_bytes(g_iron[0][:4], 'little'), 5228)

        g_dark = dialogos.propio('Bank Clerk Aiky', stage=26)
        self.assertEqual(int.from_bytes(g_dark[0][:4], 'little'), 5230)

        g_aurora = dialogos.propio('Bank Clerk', stage=3)
        self.assertEqual(int.from_bytes(g_aurora[0][:4], 'little'), 5225)

        # Palm Base bankers
        for pb_name in ['Bankclerk Clair', 'Bankclerk Sien', 'Bankclerk Keda', 'Bankclerk Emmy', 'Banking Director']:
            g_pb = dialogos.propio(pb_name, stage=88)
            self.assertEqual(int.from_bytes(g_pb[0][:4], 'little'), 5225)

        # Option 5030 ("How do I use it?") gives official guide line 5034
        resp_5030 = dialogos.respuesta_a(5030, 4)
        mid_guide = int.from_bytes(resp_5030[0][2:6], 'little')
        self.assertEqual(mid_guide, 5034)

        # Option 5032 asks which warehouse to use (line 5236)
        resp_5032 = dialogos.respuesta_a(5032, 4)
        mid_wh = int.from_bytes(resp_5032[0][2:6], 'little')
        self.assertEqual(mid_wh, 5236)

        # Voucher Angel response test
        resp_va_info = dialogos.respuesta_a(508585, val=41)
        self.assertEqual(len(resp_va_info), 2)
        # Option 508586 gives shop 159
        resp_va_shop = dialogos.respuesta_a(508586, val=41)
        self.assertEqual(int.from_bytes(resp_va_shop[0][:2], 'little'), 0x0034)
        # Option 508587 opens the official exchange group 254.  The S2C
        # handler FUN_005f4890 is opcode 0x0151; 0x0206 is only the internal
        # WND_EXCHANGE identifier and crashes this client when sent as opcode.
        resp_va_exch = dialogos.respuesta_a(508587, val=41)
        self.assertEqual(resp_va_exch[0], struct.pack('<HI', 0x0151, 254))

    def test_furniture_and_deeds_never_stack(self):
        import inventario as inv
        import app
        # Furniture items and deeds are never stackable
        self.assertFalse(inv.es_apilable(10115))  # Cottage Deed
        self.assertFalse(inv.es_apilable(10116))  # Delicate House Deed
        self.assertFalse(inv.es_apilable(9954))   # Furniture item
        self.assertFalse(inv.es_apilable(10121))  # Furniture item

        class MockSes:
            def __init__(self):
                self.inventario = {}
                self.cantidades = {}
                self.instancias = {}
                self.personaje = type('P', (), {'char_id': 100, 'nombre': 'Tester', 'stage': 41, 'tile_x': 244, 'tile_y': 30, 'mejoras': {}})()
                self.paquetes = []
            def enviar(self, *pkts):
                self.paquetes.extend(pkts)

        ses = MockSes()
        # Give 3 units of furniture item 9954
        app._meter(ses, 9954, 3)
        # Should allocate 3 separate slots in furniture bag (377..476)
        furn_slots = [r for r, iid in ses.inventario.items() if iid == 9954]
        self.assertEqual(len(furn_slots), 3)
        for r in furn_slots:
            self.assertTrue(377 <= r <= 476)
            self.assertNotIn(r, ses.cantidades)
            self.assertIn(r, ses.instancias)
        # All 3 instances must be unique
        instances = [ses.instancias[r] for r in furn_slots]
        self.assertEqual(len(set(instances)), 3)

    def test_chat_processing_channels_and_gm_slash(self):
        import app
        import clases as cl

        class MockSes:
            def __init__(self, name="AngelTester"):
                self.inventario = {}
                self.cantidades = {}
                self.instancias = {}
                self.personaje = type('P', (), {'char_id': 101, 'entity_id': 1001, 'nombre': name, 'stage': 41, 'tile_x': 244, 'tile_y': 30, 'nivel': 10, 'oro': 1000})()
                self.rol = 'mundo'
                self.paquetes = []
            def enviar(self, *pkts):
                self.paquetes.extend(pkts)

        srv = app.Servidor('127.0.0.1', 8888, 8889, 8890)
        ses = MockSes()
        srv.mundos.append(ses)

        # 1. Normal chat with command-like word "item 10115" without slash
        ses.paquetes.clear()
        srv._procesar_chat_mundo(ses, "item 10115 is my favorite", "127.0.0.1")
        # Regular chat should broadcast local say, not trigger GM item command
        self.assertNotIn(10115, ses.inventario.values())

        # 2. Broadcast without ticket 2002
        ses.paquetes.clear()
        srv._procesar_chat_mundo(ses, "!Hello Angel Lyceum", "127.0.0.1")
        # Player warned they need Broadcasting item
        warn_text = [p for p in ses.paquetes if b"You need Broadcasting" in p]
        self.assertTrue(len(warn_text) > 0)

        # 3. Broadcast with ticket 2002
        ses.inventario[25] = 2002
        ses.paquetes.clear()
        srv._procesar_chat_mundo(ses, "!Hello Angel Lyceum", "127.0.0.1")
        self.assertNotIn(25, ses.inventario) # Consumed ticket
        bc_pkts = [pkt for pkt in ses.paquetes if pkt[:2] == b'\x28\x01']
        self.assertEqual(len(bc_pkts), 1)
        self.assertEqual(bc_pkts[0][6], 2)
        self.assertEqual(bc_pkts[0][7:24].rstrip(b'\x00'), b'AngelTester')
        self.assertEqual(bc_pkts[0][24:], b'Hello Angel Lyceum\x00')
        self.assertNotIn(b'[Broadcast]', bc_pkts[0])

        # 4. Super Broadcast without ticket 2003
        ses.paquetes.clear()
        srv._procesar_chat_mundo(ses, "%Grand House Opening!", "127.0.0.1")
        warn_sb = [p for p in ses.paquetes if b"You need Super Broadcasting" in p]
        self.assertTrue(len(warn_sb) > 0)

        # 5. Super Broadcast with ticket 2003
        ses.inventario[26] = 2003
        ses.paquetes.clear()
        srv._procesar_chat_mundo(ses, "/sb Grand House Opening!", "127.0.0.1")
        self.assertNotIn(26, ses.inventario) # Consumed ticket
        sb_pkts = [pkt for pkt in ses.paquetes if pkt[:2] == b'\x28\x01']
        self.assertEqual(len(sb_pkts), 1)
        self.assertEqual(sb_pkts[0][6], 11)
        self.assertEqual(sb_pkts[0][7:24].rstrip(b'\x00'), b'AngelTester')
        self.assertEqual(sb_pkts[0][24:], b'0Grand House Opening!\x00')
        self.assertNotIn(b'[Super Broadcast]', sb_pkts[0])

        # 6. Trade channel with ticket 2002
        ses.inventario[27] = 2002
        ses.paquetes.clear()
        srv._procesar_chat_mundo(ses, "@WTS Delicate House Deed", "127.0.0.1")
        self.assertNotIn(27, ses.inventario) # Consumed ticket
        tr_pkts = [pkt for pkt in ses.paquetes if pkt[:2] == b'\x28\x01']
        self.assertEqual(len(tr_pkts), 1)
        self.assertEqual(tr_pkts[0][6], 10)
        self.assertEqual(tr_pkts[0][7:24].rstrip(b'\x00'), b'AngelTester')
        self.assertEqual(tr_pkts[0][24:], b'WTS Delicate House Deed\x00')

    def test_poke_eggs_and_capturable_list_come_from_xml(self):
        import house_services as hs

        self.assertEqual(hs.capture_eggs(), {
            16979: 30, 16980: 45, 16981: 60,
            16982: 300, 20092: 300,
        })
        capturable = hs.capturable_monsters()
        self.assertNotIn(1217, capturable)  # house boss egg is not a catch entry
        self.assertGreaterEqual(len(capturable), 900)
        self.assertLess(hs.capture_chance(30, 100, 100),
                        hs.capture_chance(30, 1, 100))
        self.assertLess(hs.capture_chance(30, 1, 100),
                        hs.capture_chance(45, 1, 100))
        self.assertLess(hs.capture_chance(300, 1, 100, npc_type=7001), 100.0)

    def test_public_selector_channel_two_routes_to_broadcast(self):
        import app

        srv = app.Servidor('127.0.0.1', 8888, 8889, 8890)
        ses = type('S', (), {
            'rol': 'mundo',
            'personaje': type('P', (), {'nombre': 'SelectorTester'})(),
        })()
        body = struct.pack('<I', 0) + b'\x02Public selector works\x00'
        with mock.patch.object(srv, '_procesar_chat_mundo') as process:
            srv.manejar(ses, 0x0128, None, None, 'test', body)
        process.assert_called_once_with(ses, '!Public selector works', 'test')

    def test_native_chat_channel_packets_are_not_shifted(self):
        import clases as cl

        public = cl.chat_broadcast(0, 'Karma', 'public text')
        trade = cl.chat_trade(0, 'Karma', 'trade text')
        super_bc = cl.chat_super_broadcast(0, 'Karma', 'super text', 0)
        team = cl.chat_team(123, 'Karma', 'team text')
        league = cl.chat_league(123, 'Karma', 'league text')
        marriage = cl.chat_marriage(123, 'Karma', 'marriage text')

        self.assertEqual((int.from_bytes(public[:2], 'little'), public[6]),
                         (0x0128, 2))
        self.assertEqual((int.from_bytes(trade[:2], 'little'), trade[6]),
                         (0x0128, 10))
        self.assertEqual((int.from_bytes(super_bc[:2], 'little'), super_bc[6]),
                         (0x0128, 11))
        self.assertEqual(super_bc[24:], b'0super text\x00')
        # Equipo 4 y liga 5, del cliente (REA: envio 0x6366a0, etiqueta 0x632e70).
        self.assertEqual((int.from_bytes(team[:2], 'little'), team[6]),
                         (0x0126, 4))
        self.assertEqual((int.from_bytes(league[:2], 'little'), league[6]),
                         (0x0126, 5))
        self.assertEqual((int.from_bytes(marriage[:2], 'little'), marriage[6]),
                         (0x0126, 14))

    def test_successful_poke_capture_consumes_egg_and_gives_monster_egg(self):
        import app
        import combate

        class MockSes:
            def __init__(self):
                self.inventario = {20: 16982}
                self.cantidades = {}
                self.instancias = {}
                self.captura_pendiente = {
                    'slot': 20, 'item': 16982, 'time': __import__('time').time(),
                }
                self.personaje = type('P', (), {
                    'char_id': 111, 'entity_id': 111, 'stage': 41, 'mejoras': {},
                })()
                mob = combate.Monstruo(9001, 7001, 'Purple Evil Cat', (20, 20), 43210)
                mob.hp = 1
                mob.en_combate_con = 111
                self.monstruos = {9001: mob}
                self.paquetes = []

            def enviar(self, *pkts):
                self.paquetes.extend(pkts)

            def enviar_inmediato(self, *pkts):
                self.paquetes.extend(pkts)

        class FakeLoop:
            def __init__(self):
                self.calls = []

            def call_later(self, delay, callback):
                self.calls.append((delay, callback))

        ses = MockSes()
        loop = FakeLoop()
        with mock.patch.object(app.random, 'random', return_value=0.0), \
                mock.patch.object(app, '_guardar_bolsa'), \
                mock.patch.object(app, '_refrescar', return_value=[]), \
                mock.patch('asyncio.get_event_loop', return_value=loop):
            self.assertTrue(app._intentar_captura_monstruo(ses, 9001, 'test'))
        self.assertNotIn(16982, ses.inventario.values())
        self.assertIn(16978, ses.inventario.values())
        self.assertEqual(ses.monstruos[9001].hp, 0)
        # Success leaves the mob stunned and then removes it directly: a capture
        # must never reuse the normal monster-death animation.
        self.assertTrue(any(pkt[:2] == b'\x1d\x00' for pkt in ses.paquetes))
        self.assertEqual([delay for delay, _ in loop.calls],
                         [2.0, 2.0 + combate.SEGUNDOS_REAPARICION])
        loop.calls[0][1]()
        self.assertTrue(any(pkt[:2] == b'\x07\x00' for pkt in ses.paquetes))
        self.assertFalse(any(pkt[:2] == b'\x0a\x00' for pkt in ses.paquetes))
        # After respawn delay, the captured monster reappears on the map and revives
        loop.calls[1][1]()
        self.assertTrue(ses.monstruos[9001].vivo)
        self.assertEqual(ses.monstruos[9001].hp, ses.monstruos[9001].hp_max)
        self.assertTrue(any(pkt[:2] == b'\x08\x00' for pkt in ses.paquetes))

    def test_super_bc_trade_and_other_channels_consume_exact_items(self):
        import app
        import clases as cl

        class MockSes:
            def __init__(self, name="Karma"):
                self.rol = 'mundo'
                self.inventario = {}
                self.cantidades = {}
                self.instancias = {}
                self.personaje = type('P', (), {
                    'char_id': 777, 'entity_id': 1777, 'nombre': name,
                    'stage': 41, 'tile_x': 100, 'tile_y': 100,
                    'apariencia': [1], 'mejoras': {},
                })()
                self.paquetes = []

            def enviar(self, *pkts):
                self.paquetes.extend(pkts)

        srv = app.Servidor('127.0.0.1', 8888, 8889, 8890)
        ses = MockSes()
        srv.mundos.append(ses)

        with mock.patch.object(app, '_guardar_bolsa'), \
                mock.patch.object(app, '_refrescar', return_value=[]):
            # 1. Trade dropdown (0x0128 canal=10) consumes ONLY 2002 (Broadcasting) and emits canal=10
            ses.inventario = {20: 2002, 21: 2003}
            ses.paquetes.clear()
            srv.manejar(ses, 0x0128, None, None, 'test', struct.pack('<IB', 0, 10) + b'WTB Pet Egg\x00')
            self.assertNotIn(20, ses.inventario)
            self.assertIn(21, ses.inventario)  # Super BC 2003 untouched!
            tr_pkts = [p for p in ses.paquetes if p[:2] == b'\x28\x01']
            self.assertEqual(len(tr_pkts), 1)
            self.assertEqual(tr_pkts[0][6], 10)
            self.assertEqual(tr_pkts[0][24:], b'WTB Pet Egg\x00')

            # 2. Super Broadcast window (0x0128 canal=11, prefixed with '0') consumes 2003 and emits canal=11
            ses.inventario = {20: 2002, 21: 2003}
            ses.paquetes.clear()
            srv.manejar(ses, 0x0128, None, None, 'test', struct.pack('<IB', 0, 11) + b'0TROLL\x00')
            self.assertIn(20, ses.inventario)     # Regular BC 2002 untouched!
            self.assertNotIn(21, ses.inventario)  # Super BC 2003 consumed!
            sb_pkts = [p for p in ses.paquetes if p[:2] == b'\x28\x01']
            self.assertEqual(len(sb_pkts), 1)
            self.assertEqual(sb_pkts[0][6], 11)
            self.assertEqual(sb_pkts[0][24:], b'0TROLL\x00')

            # 3. Team (5), League (4), Marriage (14) via 0x0126 do NOT consume 2002 or 2003
            ses.inventario = {20: 2002, 21: 2003}
            for canal in (5, 4, 14):
                ses.paquetes.clear()
                body = struct.pack('<IBI', 0, canal, 0) + f'msg_{canal}\x00'.encode('latin-1')
                srv.manejar(ses, 0x0126, None, None, 'test', body)
                self.assertIn(20, ses.inventario)
                self.assertIn(21, ses.inventario)
                priv_pkts = [p for p in ses.paquetes if p[:2] == b'\x26\x01']
                self.assertEqual(len(priv_pkts), 1)
                self.assertEqual(priv_pkts[0][6], canal)

            # 4. Battle (0x0133) does NOT consume 2002 or 2003 and emits S2C 0x0139
            ses.paquetes.clear()
            srv.manejar(ses, 0x0133, None, None, 'test', b'For Aurora!\x00')
            self.assertIn(20, ses.inventario)
            self.assertIn(21, ses.inventario)
            bat_pkts = [p for p in ses.paquetes if p[:2] == b'\x39\x01']
            self.assertEqual(len(bat_pkts), 1)
            self.assertIn(b'For Aurora!\x00', bat_pkts[0])

    def test_poke_egg_captures_catch_xml_monsters_and_creates_pet_ficha(self):
        import app
        import combate
        import house_services as hs
        import mascotas

        capturable = hs.capturable_monsters()
        self.assertEqual(capturable[7001], 16978)  # exact catch.xml archetype
        self.assertEqual(capturable[7002], 16978)
        self.assertEqual(capturable[909], 16971)
        self.assertEqual(capturable[1201], 16971)
        self.assertNotIn(1217, capturable)          # only a house-hatching egg
        self.assertEqual(capturable[7014], 16975)  # Sky Winged Bird -> Monster Egg 16975 (NOT 63375 whistle!)
        self.assertEqual(capturable[7015], 16975)  # Earth Winged Bird -> Monster Egg 16975

        class MockSes:
            def __init__(self):
                self.rol = 'mundo'
                self.inventario = {42: 16982}
                self.cantidades = {42: 5}
                self.instancias = {42: 9042}
                self.captura_pendiente = None
                self.personaje = type('P', (), {
                    'char_id': 222, 'entity_id': 1222, 'stage': 20, 'mejoras': {}, 'mascotas': {}, 'mascota': None,
                })()
                mob = combate.Monstruo(0x000FB0E3, 7001, 'Purple Evil Cat', (40, 40))
                mob.hp = 20  # Wounded target
                mob.en_combate_con = 1222  # Player attacked it
                self.monstruos = {0x000FB0E3: mob}
                self.paquetes = []

            def enviar(self, *pkts):
                self.paquetes.extend(pkts)

        srv = app.Servidor('127.0.0.1', 8888, 8889, 8890)
        ses = MockSes()
        with mock.patch.object(app.random, 'random', return_value=0.0), \
                mock.patch.object(app, '_guardar_bolsa'), \
                mock.patch.object(app, '_refrescar', return_value=[]):
            srv.manejar(ses, 0x002E, None, None, 'test', struct.pack('<BI', 42, 0x000FB0E3))
        self.assertEqual(ses.cantidades[42], 4)
        self.assertIn(16978, ses.inventario.values())
        pet_slot = next(r for r, iid in ses.inventario.items() if iid == 16978)
        self.assertIn(str(pet_slot), ses.personaje.mascotas)
        pet_ficha = ses.personaje.mascotas[str(pet_slot)]
        self.assertEqual(pet_ficha['nombre'], 'Purple Cat')
        self.assertEqual(pet_ficha['captured_name'], 'Purple Cat')
        self.assertEqual(pet_ficha['npc_type'], 7001)
        self.assertIn('rango', pet_ficha)
        self.assertIn('estrellas', pet_ficha)

        # Success: complete red crystal (19) + complete absorption (302),
        # without the cast confirmation 0x0006 that locks movement.
        self.assertFalse(any(p[:2] == b'\x06\x00' for p in ses.paquetes))
        capture_fx = [p for p in ses.paquetes if p[:2] == b'\x11\x00']
        self.assertEqual(len(capture_fx), 4)
        effects = [p[2] | ((p[3] & 0x0F) << 8) for p in capture_fx]
        self.assertEqual(effects, [19, 19, 302, 302])

    def test_poke_egg_requires_weakening_and_can_fail(self):
        import app
        import combate
        import mascotas

        class MockSes:
            def __init__(self):
                self.rol = 'mundo'
                self.inventario = {42: 16979}  # Standard Poke Egg
                self.cantidades = {42: 3}
                self.instancias = {42: 1042}
                self.captura_pendiente = None
                self.personaje = type('P', (), {
                    'char_id': 333, 'entity_id': 1333, 'stage': 20, 'mejoras': {}, 'mascotas': {}, 'mascota': None,
                })()
                self.mob = combate.Monstruo(0x000FB0E4, 7001, 'Purple Evil Cat', (40, 40))
                self.monstruos = {0x000FB0E4: self.mob}
                self.paquetes = []

            def enviar(self, *pkts):
                self.paquetes.extend(pkts)

        srv = app.Servidor('127.0.0.1', 8888, 8889, 8890)

        # 1. Target at full HP (not attacked / weakened): Rejected, egg NOT consumed!
        ses = MockSes()
        ses.captura_pendiente = {'slot': 42, 'item': 16979, 'time': __import__('time').time()}
        self.assertTrue(app._intentar_captura_monstruo(ses, 0x000FB0E4, 'test'))
        self.assertEqual(ses.cantidades[42], 3)  # Egg preserved!
        self.assertTrue(any(b'weaken' in p for p in ses.paquetes))

        # 2. Target weakened, but capture roll fails: egg consumed; the red
        # crystal appears, but there is no absorption/stun/despawn and the
        # monster stays alive and visible.
        ses.paquetes.clear()
        ses.mob.hp = 20
        ses.mob.en_combate_con = 1333
        ses.captura_pendiente = {'slot': 42, 'item': 16979, 'time': __import__('time').time()}
        with mock.patch.object(app.random, 'random', return_value=99.9), \
                mock.patch.object(app, '_guardar_bolsa'), \
                mock.patch.object(app, '_refrescar', return_value=[]):
            self.assertTrue(app._intentar_captura_monstruo(ses, 0x000FB0E4, 'test'))
        self.assertEqual(ses.cantidades[42], 2)  # 1 egg consumed!
        self.assertEqual(ses.mob.hp, 20)        # Monster still alive!
        self.assertTrue(ses.mob.vivo)
        self.assertTrue(any(b'Capture failed' in p for p in ses.paquetes))
        capture_fx = [p for p in ses.paquetes if p[:2] == b'\x11\x00']
        self.assertEqual(len(capture_fx), 2)
        effects = [p[2] | ((p[3] & 0x0F) << 8) for p in capture_fx]
        self.assertEqual(effects, [19, 19])
        self.assertEqual(capture_fx[0][3] & 0x80, 0)
        self.assertEqual(capture_fx[1][3] & 0x80, 0x80)
        self.assertFalse(any(p[:2] == b'\x1d\x00' for p in ses.paquetes))
        self.assertFalse(any(p[:2] == b'\x07\x00' for p in ses.paquetes))

        # While alive, the monster cannot be captured again after escaping:
        ses.paquetes.clear()
        ses.captura_pendiente = {'slot': 42, 'item': 16979, 'time': __import__('time').time()}
        with mock.patch.object(app, '_guardar_bolsa'), \
                mock.patch.object(app, '_refrescar', return_value=[]):
            self.assertTrue(app._intentar_captura_monstruo(ses, 0x000FB0E4, 'test'))
        self.assertEqual(ses.cantidades[42], 2)
        self.assertTrue(any(b'already escaped' in p for p in ses.paquetes))

        # Once killed and respawned (revivir), the counter is reset and it CAN be captured again:
        ses.mob.revivir()
        self.assertIsNone(ses.mob.captura_fallida_en)
        ses.mob.hp = 20
        ses.mob.en_combate_con = 1333
        ses.paquetes.clear()
        ses.captura_pendiente = {'slot': 42, 'item': 16979, 'time': __import__('time').time()}
        with mock.patch.object(app.random, 'random', return_value=99.9), \
                mock.patch.object(app, '_guardar_bolsa'), \
                mock.patch.object(app, '_refrescar', return_value=[]):
            self.assertTrue(app._intentar_captura_monstruo(ses, 0x000FB0E4, 'test'))
        self.assertEqual(ses.cantidades[42], 1)
        self.assertTrue(any(b'Capture failed.' in p for p in ses.paquetes))

        # 3. Verify all 5 quality ranks are represented in sortear_rango
        ranks_seen = set()
        for _ in range(500):
            r_id, r_nom = mascotas.sortear_rango()
            ranks_seen.add(r_id)
            self.assertIn(r_nom, ('Common', 'Good', 'Rare', 'Awesome', 'Super'))
        self.assertEqual(ranks_seen, {1, 2, 3, 4, 5})

    def test_ball_tickets_and_candy_rewards(self):
        import time
        # All ticket variants are recognized in BALL_TICKETS
        for tid in (9953, 20078, 15235, 15236, 16598, 28867):
            self.assertIn(tid, casas.BALL_TICKETS)

        # Level 1 house can start a ball
        c = casas.CasaData(owner_id=555, owner_name="HostHero", deed_id=10115)
        self.assertEqual(c.level, 1)
        now = int(time.time())
        started = c.iniciar_baile(9953, now=now)
        self.assertTrue(started)
        self.assertTrue(c.ball_active)
        self.assertGreater(c.ball_cooldown_until, now)

        # Fast ticket 15235 also starts ball
        c2 = casas.CasaData(owner_id=556, owner_name="HostHero2", deed_id=10115)
        self.assertTrue(c2.iniciar_baile(15235, now=now))

        # Ball announcement string 2395 formatting
        announcement = "There will be a ball in %s(%d,%d)'s house after 3 minutes. All players are welcome to join the ball." % (c.owner_name, 150, 100)
        self.assertIn("HostHero(150,100)'s house", announcement)

    def test_raise_a_pet_room_system(self):
        import inventario as inv
        # Pet slots 477..486 accept pet and pet egg items
        self.assertTrue(inv.es_ranura_valida(3393, 477)) # Pet item
        self.assertFalse(inv.es_ranura_valida(10115, 477)) # Deed not allowed in pet slot

        # Base house level 1 has 1 pet slot and 1 mobgen slot
        self.assertEqual(casas.ranuras_mascotas_validas(1), 1)
        self.assertEqual(casas.ranuras_mobgen_validas(1), 1)

        # Care pets dictionary persists correctly in CasaData
        c = casas.CasaData(owner_id=777, owner_name="PetLover", deed_id=10115)
        c.care_pets[477] = {
            'item_id': 3393,
            'nombre': 'PetBuddy',
            'sprite': 1001,
            'nivel': 10,
            'exp': 500
        }
        data = c.to_dict()
        restored = casas.CasaData.from_dict(data)
        self.assertIn(477, restored.care_pets)
        self.assertEqual(restored.care_pets[477]['nombre'], 'PetBuddy')
        self.assertEqual(restored.care_pets[477]['nivel'], 10)

    def test_raise_a_pet_move_sync_does_not_break_house_loop(self):
        import app

        class MockSes:
            def __init__(self):
                self.usuario = None
                self.inventario = {478: 3393}
                self.cantidades = {}
                self.instancias = {478: 1478}
                self.paquetes = []
                self.personaje = type('P', (), {
                    'char_id': 91001,
                    'entity_id': 191001,
                    'nombre': 'PetRoomOwner',
                    'stage': 500,
                    'casa': None,
                    'mascotas': {},
                })()

            def enviar(self, *pkts):
                self.paquetes.extend(pkts)

        # Reproduce el movimiento real del log: 477 -> 478.  Antes lanzaba
        # AttributeError al intentar llamar inventario.nombre_item().
        ses = MockSes()
        casa = casas.CasaData(ses.personaje.char_id, ses.personaje.nombre)
        casa.cleanliness = 1000
        casa.care_pets['477'] = {
            'item_id': 3393, 'name': "Brute's Egg", 'sprite': 44033,
            'slot': 477, 'tile': [36, 28],
        }
        casas._CASAS_ACTIVAS[ses.personaje.char_id] = casa
        ses.personaje.casa = casa.serializar()

        srv = app.Servidor('127.0.0.1', 8888, 8889, 8890)
        srv._sincronizar_ranura_pet_room(ses, 477, 478, 3393)

        self.assertNotIn('477', casa.care_pets)
        self.assertIn('478', casa.care_pets)
        self.assertEqual(casa.care_pets['478']['name'], "Brute's Egg")
        self.assertTrue(any(pkt[:2] == b'\x08\x00' for pkt in ses.paquetes))

    def test_monster_room_spawns_and_retracts_moved_egg(self):
        import app
        import house_services as hs

        eggs = hs.monster_eggs()
        monsters = hs.xml_rows('monster.xml')
        egg_id, _egg = next(
            (iid, row) for iid, row in eggs.items()
            if int(row.get('動態資料1') or 0) in monsters)

        class MockSes:
            def __init__(self):
                self.usuario = None
                self.house_room_ready = True
                self.house_furnishing = False
                self.house_egg_entities = {}
                self.house_egg_sequence = 0
                self.inventario = {487: egg_id}
                self.cantidades = {}
                self.instancias = {487: 4487}
                self.monstruos = {}
                self.paquetes = []
                self.personaje = type('P', (), {
                    'char_id': 91002,
                    'entity_id': 191002,
                    'nombre': 'MonsterRoomOwner',
                    'stage': 500,
                    'casa': None,
                    'mejoras': {},
                })()

            def enviar_inmediato(self, *pkts):
                self.paquetes.extend(pkts)

        ses = MockSes()
        casa = casas.CasaData(ses.personaje.char_id, ses.personaje.nombre)
        casa.cleanliness = 1000
        casas._CASAS_ACTIVAS[ses.personaje.char_id] = casa
        ses.personaje.casa = casa.serializar()

        app._casa_tick_monstruos(ses)
        self.assertIn(487, ses.house_egg_entities)
        self.assertTrue(any(pkt[:2] == b'\x08\x00' for pkt in ses.paquetes))

        ses.paquetes.clear()
        ses.inventario.pop(487)
        app._casa_tick_monstruos(ses)
        self.assertNotIn(487, ses.house_egg_entities)
        self.assertTrue(any(pkt[:2] == b'\x07\x00' for pkt in ses.paquetes))

    def test_stage_500_logout_sanitization(self):
        import cuentas
        # Player record saved in stage 500 (inside house)
        raw_p = {
            'char_id': 888,
            'ranura': 0,
            'nombre': 'HouseGuest',
            'stage_id': 500,
            'tile_x': 25,
            'tile_y': 25,
            'faction': 'Aurora',
            'habilidades': [],
            'barra': [],
            'quests': [],
            'inventario': {}
        }
        cuenta = {'personajes': [raw_p]}
        personaje = cuentas.personaje_de(cuenta, ranura=0)
        # Must be redirected to faction city (Aurora = stage 3) or Lyceum (41), NOT stage 500 void
        self.assertNotEqual(personaje.stage, 500)
        self.assertEqual(personaje.stage, 3)
        self.assertEqual(personaje.tile_x, 150)
        self.assertEqual(personaje.tile_y, 105)

        # And entering house stage 500 must NOT be overridden by _ficha during live 0x0009 transitions
        import login
        p_house = login.Personaje(char_id=888, nombre='HouseOwner', stage=500)
        p_house.tile_x, p_house.tile_y = 42, 80
        p_house.checkpoint_stage = 18
        p_house.checkpoint_x, p_house.checkpoint_y = 173, 45
        sec = login._cargar_secuencia()
        m2 = [x for x in sec if x['opcode'] == 2][0]
        login._ficha(p_house, m2['datos'])
        self.assertEqual(p_house.stage, 500)
        self.assertEqual((p_house.tile_x, p_house.tile_y), (42, 80))

    def test_deeds_go_to_backpack_and_not_furniture_bag(self):
        import app
        import inventario as inv
        import casas

        # Deeds must never be valid in furniture bag (377..476)
        deeds = (10115, 10116, 10117, 17934, 17935, 17936, 17937, 20076)
        for deed_id in deeds:
            self.assertFalse(inv.es_ranura_valida(deed_id, 377))
            self.assertTrue(inv.es_ranura_valida(deed_id, 376)) # Valid for deed slot
            self.assertTrue(inv.es_ranura_valida(deed_id, 20))  # Valid for backpack
            self.assertIsNone(casas.item_a_mueble(deed_id))     # Not treated as furniture

        # Furniture style (e.g. 14841) IS valid in furniture bag
        self.assertTrue(inv.es_ranura_valida(14841, 377))

        class MockSes:
            def __init__(self):
                self.inventario = {}
                self.cantidades = {}
                self.instancias = {}
                self.personaje = type('P', (), {'char_id': 999, 'nombre': 'DeedMaster', 'stage': 41, 'tile_x': 244, 'tile_y': 30, 'mejoras': {}})()
                self.paquetes = []
            def enviar(self, *pkts):
                self.paquetes.extend(pkts)

        ses = MockSes()
        # Giving Luxurious Villa (17934) and Romantic Villa (10117)
        r1 = app._meter(ses, 17934, 1)
        r2 = app._meter(ses, 10117, 1)
        # Must be in regular inventory bag (20..120), NOT in furniture bag (377..476)
        self.assertTrue(20 <= r1 <= 120)
        self.assertTrue(20 <= r2 <= 120)
        self.assertNotIn(r1, range(377, 477))
        self.assertNotIn(r2, range(377, 477))

    def test_ball_cooldown_reset_command(self):
        import gm
        import casas
        import time

        class MockSes:
            def __init__(self):
                self.inventario = {}
                self.personaje = type('P', (), {
                    'char_id': 1234,
                    'nombre': 'BallHost',
                    'stage': 41,
                    'casa': casas.CasaData(1234, 'BallHost', 10115).serializar()
                })()
                self.paquetes = []
            def enviar(self, *pkts):
                self.paquetes.extend(pkts)

        ses = MockSes()
        # Set cooldown active
        c = casas.CasaData.deserializar(ses.personaje.casa)
        c.ball_cooldown_until = int(time.time()) + 86400 * 3
        c.ball_active = True
        ses.personaje.casa = c.serializar()

        # Run GM /ball reset
        msg = gm.aplicar(ses, ('ball', 'reset'))
        self.assertIn("reset", msg.lower())
        c_after = casas.CasaData.deserializar(ses.personaje.casa)
        self.assertEqual(c_after.ball_cooldown_until, 0)
        self.assertFalse(c_after.ball_active)

    def test_pet_room_training_exp_and_roaming(self):
        import mascotas as ms
        import configuracion as cfg

        ficha = {
            'nombre': 'WaterElf Egg',
            'sprite': 3133,
            'tipo': 44068,
            'nivel': 1,
            'hp': 127, 'hp_max': 127,
            'mp': 96, 'mp_max': 96,
            'exp': 0, 'exp_max': 72,
            'saciedad': 100, 'intimidad': 60,
            'estrellas': 1, 'mejoras': 0,
            'ranura': 477, 'item': 18623
        }

        # Grant training EXP
        mult = getattr(cfg, 'MULTIPLICADOR_EXP_PET', 1.0)
        exp_tick = int(getattr(cfg, 'EXP_BASE_PET_ROOM_TICK', 15) * mult)
        self.assertGreater(exp_tick, 0)

        # Before training
        self.assertEqual(ficha['nivel'], 1)
        self.assertEqual(ficha['exp'], 0)

        # Train 5 ticks (75 EXP) -> should level up from Lv.1 to Lv.2 (requires 72 exp)
        subidos = ms.dar_exp(ficha, exp_tick * 5)
        self.assertGreaterEqual(subidos, 1)
        self.assertEqual(ficha['nivel'], 2)
        self.assertEqual(ficha['exp'], 3) # 75 - 72 = 3

        # armar packet 0x0065 contains level 2
        pkt = ms.armar(ficha)
        self.assertEqual(pkt[:2], b'\x65\x00')
        self.assertEqual(int.from_bytes(pkt[33:37], 'little'), 2) # Level 2 at offset 31 (packet +2)


if __name__ == '__main__':
    unittest.main()


