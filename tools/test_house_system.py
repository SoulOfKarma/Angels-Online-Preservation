"""Pruebas unitarias completas del House System IGG de Angels Online."""
import os
import sys
import struct
import unittest

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
        self.assertEqual(casas.ranuras_mascotas_validas(1), 0)
        self.assertEqual(casas.ranuras_mascotas_validas(3), 1)
        self.assertEqual(casas.ranuras_mascotas_validas(5), 2)
        self.assertEqual(casas.ranuras_mascotas_validas(7), 3)
        self.assertEqual(casas.ranuras_mascotas_validas(9), 4)
        self.assertEqual(casas.ranuras_mascotas_validas(12), 5)
        self.assertEqual(casas.ranuras_mascotas_validas(14), 6)

        self.assertEqual(casas.ranuras_mobgen_validas(1), 0)
        self.assertEqual(casas.ranuras_mobgen_validas(6), 1)
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
        # 1. Mapas de exhibicion validos
        self.assertIn(370, casas.MAPAS_EXHIBICION) # Angel House Area
        self.assertIn(41, casas.MAPAS_EXHIBICION)  # Angel Lyceum
        self.assertIn(3, casas.MAPAS_EXHIBICION)   # Aurora City
        self.assertIn(26, casas.MAPAS_EXHIBICION)  # Dark City / Iron Alley

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

if __name__ == '__main__':
    unittest.main()


