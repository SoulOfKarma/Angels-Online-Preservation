"""Regression coverage for the IGG house fixes; no account database is opened."""
import ast
import asyncio
import logging
import pathlib
import struct
import sys
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
import casas
import house_services as hs

def runtime():
    tree = ast.parse((ROOT / 'server/app.py').read_text(encoding='utf-8'))
    needed = {'_casa_actual', '_casa_click', '_casa_tick_limpieza',
              '_casa_recibir_token', '_casa_invocar_mercenario',
              '_casa_fabricar', '_casa_tick_monstruos', '_casa_sincronizar_token',
              '_paquetes_ocultar_interactivos_casa', '_casa_paquetes_decorar',
              '_casa_salir_editor', '_casa_usar_token', '_casa_submit_order'}
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in needed]
    env = dict(struct=struct, time=time, asyncio=asyncio, random=Mock(randrange=lambda _: 0),
               log=logging.getLogger('house-test'), cuentas=Mock())
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / 'server/app.py'), 'exec'), env)
    return env

def session(casa, inventory=None):
    sent = []
    p = SimpleNamespace(char_id=casa.owner_id, entity_id=1001, nombre=casa.owner_name,
                        stage=500, nivel=302, habilidades=[(26, 100, 0)],
                        buffs={}, casa=casa.serializar(), mejoras={}, inventario={}, tile_x=85, tile_y=25)
    s = SimpleNamespace(personaje=p, casa_visitando=casa,
                        inventario={} if inventory is None else inventory,
                        cantidades={}, instancias={}, house_furnishing=False,
                        usuario=None, monstruos={}, house_room_ready=True,
                        enviar=lambda *pk: sent.extend(pk),
                        enviar_inmediato=lambda *pk: sent.extend(pk))
    s.sent = sent
    return s

class HouseServicesTests(unittest.TestCase):
    def setUp(self):
        self.env = runtime()
        self.casa = casas.CasaData(987654321, 'HouseTest')
        self.casa.cleanliness = 500
        self.casa.calcular_magia = lambda: 9000

    def test_house_visual_orientation_uses_mirror_flags_and_available_maid_direction(self):
        import login
        packets = login.interactivos_casa()
        maid = next(p for p in packets if b'Maid Eilian' in p)
        self.assertEqual(maid[35], 7)  # opposite the visible but back-facing direction 3
        self.assertEqual(struct.unpack_from('<I', maid, 36)[0], 40262)
        objects = {struct.unpack_from('<I', p, 2)[0]: p for p in packets if p[:2] == b'\x0e\x00'}
        for entity in (500023, 500024, 723):
            self.assertFalse(struct.unpack_from('<I', objects[entity], 6)[0] & 2)
        for entity in (701, 500021):
            self.assertTrue(struct.unpack_from('<I', objects[entity], 6)[0] & 2)
        self.assertEqual(hs.PRODUCTION[500022][1], (10, 24))
        self.assertGreater(hs.PRODUCTION[500021][1][1], hs.PRODUCTION[500022][1][1])
        self.assertGreaterEqual(hs.PRODUCTION[500021][1][0] - hs.PRODUCTION[500022][1][0], 6)
        self.assertEqual(hs.PRODUCTION[500023][1], (12, 19))
        self.assertGreaterEqual(hs.PRODUCTION[500024][1][0] - hs.PRODUCTION[500023][1][0], 5)
        self.assertEqual(struct.unpack_from('<II', objects[721], 10), (32 * 32 + 16, 31 * 32 + 16))

    def test_all_maid_greetings_and_dialogue_branches_keep_the_same_portrait(self):
        import dialogos
        self.assertEqual(dialogos.val_por_entidad(260300), hs.MAID_PORTRAIT)
        for cleanliness in (0, 500):
            line = dialogos.propio('Maid Eilian', entidad=260300, cleanliness=cleanliness)[0]
            self.assertEqual(struct.unpack_from('<H', line, 4)[0], hs.MAID_PORTRAIT)
        for option in (7872, 7901, 7916, 7905, 7904, 7903):
            packets = dialogos.respuesta_a(option, entidad=260300)
            self.assertEqual(struct.unpack_from('<H', packets[0], 6)[0], hs.MAID_PORTRAIT)
        # Also cover replies emitted directly by app (soap, tokens, blessing),
        # rather than passing through respuesta_a.
        tree = ast.parse((ROOT / 'server/app.py').read_text(encoding='utf-8'))
        maid_messages = {7915, 7916, 7917, 7918, 7920, 7921, 7926}
        found = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'armar_linea' and len(node.args) >= 2
                    and isinstance(node.args[0], ast.Constant) and node.args[0].value in maid_messages):
                found.add(node.args[0].value)
                self.assertIsInstance(node.args[1], ast.Attribute)
                self.assertEqual(node.args[1].attr, 'MAID_PORTRAIT')
        self.assertEqual(found, maid_messages)

    def prepare_submission(self, option=7854):
        import combate
        s = session(self.casa)
        s.dlg_ent = 721
        s.oro = 100
        s.personaje.oro, s.personaje.creditos, s.personaje.rango = 100, 0, 1
        s.personaje.exp = combate.exp_para_nivel(s.personaje.nivel)
        s.personaje.hp_max, s.personaje.mp_max = 280, 154
        row = next(r for r in hs.xml_rows('order.xml').values()
                   if r['訂單類別'] == hs.ORDER_CATEGORIES[option])
        s.inventario.update({20: int(row['訂單原型']), 21: int(row['成品編號']), 22: 10115})
        s.cantidades.update({20: 2, 21: int(row['成品數量']) + 2})
        self.env.update(_cantidades=lambda target: target.cantidades,
                        _cant_de=lambda target, slot: target.cantidades.get(slot, 1),
                        _instancias=lambda target: target.instancias,
                        _tope_bolsa=lambda bag: 100, _refrescar=lambda *args, **kw: [],
                        _stats_ses=lambda target: b'stats')
        return s, row

    def test_submit_handles_all_five_xml_categories_and_consumes_only_one_order(self):
        for option in hs.ORDER_CATEGORIES:
            s, row = self.prepare_submission(option)
            before = s.personaje.exp
            self.assertTrue(self.env['_casa_submit_order'](s, option))
            self.assertEqual(s.cantidades[20], 1)
            self.assertEqual(s.cantidades[21], 2)
            self.assertEqual(s.inventario[22], 10115)
            self.assertEqual(s.oro, 100 + int(row['金錢']))
            self.assertEqual(s.personaje.exp, before + int(row['經驗值']))
            self.assertEqual(s.personaje.creditos, int(row['功勳值']))

    def test_submit_missing_products_wrong_category_and_locked_level_do_not_charge(self):
        for mode in ('missing', 'category', 'level', 'dirty', 'editor', 'visitor'):
            s, row = self.prepare_submission()
            option = 7854
            if mode == 'missing': s.cantidades[21] = int(row['成品數量']) - 1
            if mode == 'category': option = 7855
            if mode == 'level': self.casa.calcular_magia = lambda: 900
            if mode == 'dirty': self.casa.cleanliness = 0
            if mode == 'editor': s.house_furnishing = True
            if mode == 'visitor': s.personaje.char_id += 1
            before = (dict(s.inventario), dict(s.cantidades), s.oro, s.personaje.exp)
            self.env['_casa_submit_order'](s, option)
            self.assertEqual(before, (s.inventario, s.cantidades, s.oro, s.personaje.exp))
            self.casa.calcular_magia = lambda: 9000
            self.casa.cleanliness = 500

    def test_submit_storage_failure_leaves_local_inventory_and_rewards_unchanged(self):
        s, row = self.prepare_submission()
        s.usuario = 'isolated-unit-test'
        self.env['cuentas'].confirmar_entrega_productor.side_effect = RuntimeError('simulated storage failure')
        before = (dict(s.inventario), dict(s.cantidades), s.oro)
        with self.assertLogs('house-test', level='ERROR'):
            self.env['_casa_submit_order'](s, 7854)
        self.assertEqual(before, (s.inventario, s.cantidades, s.oro))

    def test_high_tier_submit_rolls_the_xml_bonus_and_uses_a_freed_slot(self):
        s, _ = self.prepare_submission(7856)
        row = hs.xml_rows('order.xml')[96]
        s.inventario[20], s.inventario[21] = int(row['訂單原型']), int(row['成品編號'])
        s.cantidades[21] = int(row['成品數量'])
        s.personaje.mejoras[21] = {'extra': {'atk': 3}}
        s.instancias[21] = b'old-product'
        self.env['random'] = SimpleNamespace(random=lambda: 0.0)
        self.env['_ranura_libre'] = lambda bag: next((r for r in range(20, 101) if r not in bag), None)
        self.env['_casa_submit_order'](s, 7856)
        self.assertEqual(s.inventario[21], int(row['額外獎賞']))
        self.assertEqual(s.cantidades[21], 1)
        self.assertEqual(s.cantidades[20], 1)
        self.assertNotIn(21, s.personaje.mejoras)
        self.assertNotEqual(s.instancias[21], b'old-product')

    def test_editor_hides_objects_with_real_despawn_not_truncated_named_spawn(self):
        packets = self.env['_paquetes_ocultar_interactivos_casa']()
        for packet in packets:
            self.assertEqual(len(packet), 7)
            self.assertEqual(struct.unpack_from('<H', packet)[0], 7)
        ids = {struct.unpack_from('<I', p, 2)[0] for p in packets}
        self.assertTrue({701, 702, 703, 260300, *hs.PRODUCTION, *hs.RESOURCES} <= ids)

    def test_equipped_deed_refresh_follows_editor_open_and_changes_on_reopen(self):
        s = session(self.casa)
        self.env['_refrescar'] = lambda target, slots: [struct.pack('<HI', 0x001B, target.inventario[slots[0]])]
        for deed in (10115, 10117, 10116):
            self.casa.deed_id = deed
            self.casa.house_name = 'Custom name'
            packets = self.env['_casa_paquetes_decorar'](s, self.casa)
            self.assertEqual(packets[0][7:24].rstrip(b'\0'), b'Custom name')
            self.assertEqual(packets[1], struct.pack('<HI', 0x001A, deed))
            self.assertEqual(s.personaje.inventario[376], deed)
            self.assertEqual(casas.CasaData.deserializar(self.casa.serializar()).deed_id, deed)

    def test_leave_callback_does_not_exit_a_reopened_editor(self):
        s = session(self.casa)
        callbacks = []
        self.env['_salir_de_casa'] = Mock()
        loop = Mock(call_later=lambda seconds, fn: callbacks.append(fn))
        with patch.object(asyncio, 'get_event_loop', return_value=loop):
            self.env['_casa_salir_editor'](s, None)
        s.house_furnishing = True
        s.house_transition = 1
        callbacks.pop()()
        self.env['_salir_de_casa'].assert_not_called()
        with patch.object(asyncio, 'get_event_loop', return_value=loop):
            self.env['_casa_salir_editor'](s, None)
        callbacks.pop()()
        self.env['_salir_de_casa'].assert_called_once_with(s, None)

    def test_cleanliness_only_counts_online_and_retains_partial_interval(self):
        c = casas.CasaData(1, 'Test')
        c.cleanliness = 100
        self.assertFalse(c.avanzar_tiempo_conectado(179))
        restored = casas.CasaData.deserializar(c.serializar())
        self.assertTrue(restored.avanzar_tiempo_conectado(1))
        self.assertEqual(restored.cleanliness, 99)
        restored.last_clean_day = '2000-01-01'
        restored.check_daily_reset()
        self.assertEqual(restored.cleanliness, 99)
        restored.avanzar_tiempo_conectado(540)
        self.assertEqual(restored.cleanliness, 96)

    def test_connection_clock_is_per_character(self):
        s = session(self.casa)
        with patch.object(casas, 'obtener_o_crear_casa', return_value=self.casa):
            self.env['_casa_tick_limpieza'](s, now=1000)
            self.env['_casa_tick_limpieza'](s, now=1179)
            self.assertEqual(self.casa.cleanliness, 500)
            self.env['_casa_tick_limpieza'](s, now=1180)
            self.assertEqual(self.casa.cleanliness, 499)
            # A new connection starts a new monotonic interval, not offline debt.
            s2 = session(self.casa)
            self.env['_casa_tick_limpieza'](s2, now=999999)
            self.assertEqual(self.casa.cleanliness, 499)

    def test_clean_bonus_matches_igg_ui_boundaries(self):
        self.assertEqual([hs.clean_bonus(x) for x in (0, 89, 90, 100, 101, 500, 1000)],
                         [0, 0, 10, 10, 20, 20, 20])

    def test_blessing_xml_is_not_exp_and_duration_is_minutes(self):
        a, b = hs.blessing_profile(4), hs.blessing_profile(9)
        self.assertEqual((a['magic_id'], a['duration_seconds']), (2292, 10800))
        self.assertEqual((a['enhance_fourth_pct'], a['pierce_first_pct']), (5, 4))
        self.assertEqual((b['enhance_fourth_pct'], b['pierce_first_pct']), (10, 8))
        self.assertNotIn('exp_bonus_pct', a)

    def test_monster_machine_never_reaches_global_portal_search(self):
        s = session(self.casa)
        s.dlg_portal = {'destino': 73}
        self.assertTrue(self.env['_casa_click'](s, 731))
        self.assertEqual(s.personaje.stage, 500)
        self.assertIsNone(s.dlg_portal)
        self.assertEqual(s.dlg_ent, 731)
        self.assertIn(7884, __import__('dialogos').opciones_de(s.dlg_guion[0]))

    def test_stations_require_house_level_two_and_a_matching_skill(self):
        s = session(self.casa)
        self.casa.calcular_magia = lambda: 499
        self.env['_casa_click'](s, 500022)
        self.assertNotIn(struct.pack('<HB', 0x004B, 6), s.sent)
        self.casa.calcular_magia = lambda: 500
        self.env['_casa_click'](s, 500022)
        self.assertIn(struct.pack('<HB', 0x004B, 6), s.sent)
        self.assertEqual(s.house_make_station, 500022)

    def test_mercenary_roster_uses_xml_level_and_actual_stats(self):
        row = hs.mercenary_for(302)
        self.assertEqual(int(row['等級']), 295)
        stats = hs.summon_stats(row)
        self.assertEqual(stats['nombre'], 'Mercenary - Diamond Pawn')
        self.assertGreater(stats['hp'], 1000)
        self.assertEqual(hs.mercenary_for(30)['id'], 4725)

    def test_token_grant_uses_inventory_helper_and_does_not_mark_phantom_claim(self):
        s = session(self.casa, {11: 222, 20: 333})
        self.env['_meter'] = lambda target, item, qty: target.inventario.setdefault(21, item) and 21
        self.env['_refrescar'] = lambda *args: []
        self.env['_guardar_bolsa'] = Mock()
        self.env['_casa_recibir_token'](s, None)
        self.assertEqual(s.inventario[11], 222)
        self.assertEqual(s.inventario[21], 10581)
        self.assertNotIn(12, s.inventario)

    def test_wrong_inventory_slot_from_old_grant_is_recovered(self):
        s = session(self.casa, {11: 10581, 20: 333})
        self.env.update(_ranura_libre=lambda bag: 21, _cantidades=lambda target: target.cantidades,
                        _mover_inst=Mock(), _refrescar=lambda *args: [], _guardar_bolsa=Mock())
        self.env['_casa_recibir_token'](s, None)
        self.assertNotIn(11, s.inventario)
        self.assertEqual(s.inventario[21], 10581)

    def test_crafting_consumes_xml_materials_only_after_timer_and_confirms_recipe(self):
        import random
        s = session(self.casa, {20: 35})
        s.house_make_station = 500022
        callbacks = []
        task = Mock(cancelled=lambda: False)
        loop = Mock(call_later=lambda delay, fn: callbacks.append((delay, fn)) or task)
        self.env.update(_cant_de=lambda target, slot: 1, _tope_bolsa=lambda bag: 100,
                        _ranura_libre=lambda bag: 21, _sacar=lambda target, slot, qty: target.inventario.pop(slot),
                        _meter=lambda target, item, qty: target.inventario.setdefault(21, item) and 21,
                        _guardar_bolsa=Mock(), _refrescar=lambda *args: [])
        with patch.object(asyncio, 'get_event_loop', return_value=loop):
            self.env['_casa_fabricar'](s, 1)
        self.assertIn(20, s.inventario)
        self.assertEqual(callbacks[0][0], 3)
        callbacks[0][1]()
        self.assertNotIn(20, s.inventario)
        self.assertEqual(s.inventario[21], 52)
        self.assertIn(struct.pack('<HBI', 0x004C, 1, 1), s.sent)

    def test_monster_egg_spawns_xml_monster_and_does_not_reset_deadline(self):
        s = session(self.casa, {487: 10595})
        self.env.update(_inst=lambda *args: b'egg-instance', _guardar_bolsa=Mock())
        self.env['_casa_tick_monstruos'](s)
        self.assertEqual(len(s.monstruos), 1)
        mob = next(iter(s.monstruos.values()))
        self.assertEqual(mob.npc_type, 3642)
        deadline = s.personaje.mejoras[487]['house_egg_deadline']
        self.env['_casa_tick_monstruos'](s)
        self.assertEqual(s.personaje.mejoras[487]['house_egg_deadline'], deadline)
        s.inventario.pop(487)
        self.env['_casa_tick_monstruos'](s)
        self.assertFalse(s.monstruos)

    def test_egg_deadline_survives_equipment_metadata_filter(self):
        tree = ast.parse((ROOT / 'server/cuentas.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'guardar_mejoras')
        saved = {}
        env = dict(_slot_sort_key=lambda pair: int(pair[0]),
                   _actualizar_personaje=lambda user, cid, fn: fn(saved))
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'cuentas.py', 'exec'), env)
        env['guardar_mejoras']('test', 123, {487: {'house_egg_deadline': 1234567890},
                                           20: {'mercenary_token_deadline': 1234567890,
                                                'mercenary_next_summon': 1234500000}})
        self.assertEqual(saved['mejoras']['487']['house_egg_deadline'], 1234567890)
        self.assertEqual(saved['mejoras']['20']['mercenary_next_summon'], 1234500000)

    def token_runtime(self, s):
        self.env.update(_meter=lambda target, item, qty: target.inventario.setdefault(20, item) and 20,
                        _sacar=lambda target, slot, qty: target.inventario.pop(slot),
                        _cant_de=lambda target, slot: 1,
                        _refrescar=lambda *args: [], _guardar_bolsa=Mock())

    def test_legacy_contract_restores_inventory_token_with_remaining_lifetime(self):
        s = session(self.casa)
        self.token_runtime(s)
        deadline = time.time() + 100
        s.personaje.buffs[2254] = {'fin': deadline}
        self.env['_casa_sincronizar_token'](s)
        self.assertEqual(s.inventario[20], 10581)
        self.assertEqual(s.personaje.mejoras[20]['mercenary_token_deadline'], deadline)
        self.assertEqual(s.sent[-1], struct.pack('<HIBBII', 0x001D, 1001, 1, 9, 2254, 0))
        s.personaje.mejoras[20]['mercenary_token_deadline'] = time.time() - 1
        self.env['_casa_sincronizar_token'](s)
        self.assertNotIn(20, s.inventario)

    def test_token_is_reusable_cooldown_survives_reconnect_and_expires(self):
        s = session(self.casa, {20: 10581})
        self.token_runtime(s)
        # Native data/spawn helpers are read-only; presence must not affect other sessions.
        import presencia
        with patch.object(presencia, 'notificar_invocacion_spawn'):
            self.env['_casa_usar_token'](s, 20)
            first = s.invocacion
            deadline = s.personaje.mejoras[20]['mercenary_token_deadline']
            self.assertAlmostEqual(deadline - time.time(), hs.TOKEN_SECONDS, delta=2)
            self.assertEqual(s.inventario[20], 10581)
            self.env['_casa_usar_token'](s, 20)
            self.assertIs(s.invocacion, first)
            s2 = session(self.casa, {20: 10581})
            s2.personaje.mejoras = {20: dict(s.personaje.mejoras[20])}
            self.env['_casa_usar_token'](s2, 20)
            self.assertFalse(getattr(s2, 'invocacion', None))
            s.personaje.mejoras[20]['mercenary_next_summon'] = time.time() - 1
            s.invocacion = None  # killed/dismissed
            self.env['_casa_usar_token'](s, 20)
            self.assertTrue(s.invocacion['es_mercenario'])
            self.assertEqual(s.personaje.mejoras[20]['mercenary_token_deadline'], deadline)
            s.personaje.stage = 41
            self.env['_casa_sincronizar_token'](s)
            self.assertIsNone(s.invocacion)
            self.assertEqual(s.inventario[20], 10581)

    def test_resources_follow_player_level_and_cap_at_client_defined_last_tier(self):
        for eid, (_, _, first) in hs.RESOURCES.items():
            self.assertEqual(hs.resource_for(eid, 1)['material'], first)
            self.assertEqual(hs.resource_for(eid, 11)['material'], first + 1)
            last = hs.resource_for(eid, 302)
            self.assertEqual(last['material'], first + 11)
            self.assertTrue(last['nombre_visible'])

    def test_token_tooltip_expiry_is_encoded_without_corrupting_entry_length(self):
        import inventario
        deadline = int(time.time()) + 28800
        state = {'mercenary_token_deadline': deadline}
        entry = inventario._entrada(123, 20, 10581, 1, dueno=1001)
        marked = inventario.marcar_caducidad_mercenario(entry, state)
        self.assertEqual(len(marked), len(entry))
        self.assertEqual(struct.unpack_from('<I', marked, 47)[0], deadline)
        self.assertEqual(marked[51:53], entry[51:53])
        updated = inventario.marcar_caducidad_mercenario(
            inventario.actualizar_ranura(123, 20, 10581, 1, dueno=1001), state)
        self.assertEqual(struct.unpack_from('<I', updated, 6 + 47)[0], deadline)
        full = inventario.completo(123, [(20, 10581, 1)], dueno=1001, mejoras={20: state})
        self.assertEqual(struct.unpack_from('<I', full, 6 + 47)[0], deadline)

    def test_resource_names_are_full_packets_and_mailbox_has_no_duplicate_npc(self):
        import login
        packets = login.interactivos_casa(player_level=11)
        names = [p for p in packets if p[:2] == struct.pack('<H', 15)]
        self.assertEqual(len(names), 5)
        self.assertTrue(all(len(p) == 46 and p[18:34].rstrip(b'\0') for p in names))
        self.assertFalse(any(b"Suft's Mailbox" in p for p in packets))

    def test_egg_dialogues_have_no_character_portraits(self):
        import dialogos
        for name, level in [('Pet Care Machine', 2), ('Monster Hatching Machine', 5)]:
            for house_level in (level, level + 1):
                line = dialogos.propio(name, house_level=house_level)[0]
                self.assertEqual(struct.unpack_from('<H', line, 2)[0], 0)
        for option in (7875, 7883):
            line = dialogos.respuesta_a(option)[0]
            self.assertEqual(struct.unpack_from('<H', line, 4)[0], 0)

if __name__ == '__main__':
    unittest.main()

