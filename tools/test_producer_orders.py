"""Producer-delivery atomicity: synthetic characters in temporary SQLite only."""
import ast
import copy
import json
import pathlib
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from unittest.mock import Mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
from producer_orders import apply_delivery, reward_progress
import house_services as hs


class ProducerOrdersTests(unittest.TestCase):
    def fixture(self):
        return dict(char_id=900001, nombre='Synthetic order fixture', nivel=302,
                    exp=0, oro=100, creditos=0, rango=1,
                    inventario={'20': 886, '21': 52, '22': 10115, '376': 10117},
                    cantidades={'20': 2, '21': 30},
                    mejoras={'22': {'keep': True}}, unrelated={'keep': True})

    def test_delta_preserves_other_inventory_metadata_and_character_fields(self):
        original = self.fixture()
        after, changed = apply_delivery(original, [(20, 886, 1, 2), (21, 52, 30, 30)],
                                        {'exp': 1300, 'oro': 250, 'creditos': 4})
        self.assertEqual(original, self.fixture())
        self.assertEqual(after['inventario']['376'], 10117)
        self.assertEqual(after['mejoras'], original['mejoras'])
        self.assertEqual(after['unrelated'], original['unrelated'])
        self.assertEqual(after['cantidades']['20'], 1)
        self.assertNotIn('21', after['inventario'])
        self.assertEqual(changed, {'20', '21'})

    def test_validation_rejects_stale_counts_and_negative_rewards(self):
        data = self.fixture()
        for consumption, rewards in [([(21, 52, 30, 31)], {}),
                                     ([(21, 53, 30, 30)], {}),
                                     ([(21, 52, 31, 30)], {}), ([], {'oro': -1})]:
            with self.assertRaises(ValueError):
                apply_delivery(data, consumption, rewards)
            self.assertEqual(data, self.fixture())

    def test_bonus_can_use_consumed_slot_but_never_overwrites_another_item(self):
        after, _ = apply_delivery(self.fixture(), [(21, 52, 30, 30)], {}, (21, 6005, 1))
        self.assertEqual(after['inventario']['21'], 6005)
        with self.assertRaises(ValueError):
            apply_delivery(self.fixture(), [], {}, (22, 6005, 1))

    def test_xml_float_bonus_probabilities_are_preserved(self):
        row = hs.xml_rows('order.xml')[96]
        self.assertEqual(float(row['獎賞機率']), 11.284)

    def test_exp_level_up_and_credit_rank_are_derived_from_rewards(self):
        data = dict(nivel=1, exp=0, hp_max=280, mp_max=154, rango=1)
        result = reward_progress(data, dict(exp=350, creditos=10),
                                 lambda level: (level - 1) * 100, 3,
                                 lambda credit: 2 if credit >= 10 else 1)
        self.assertEqual(result['nivel'], 3)
        self.assertEqual(result['rango'], 2)
        self.assertEqual((result['hp_max'], result['mp_max']), (330, 184))
        self.assertEqual(data['nivel'], 1)

    def test_real_delivery_transaction_rejects_replay_without_partial_rewards(self):
        tree = ast.parse((ROOT / 'server/cuentas.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'confirmar_entrega_productor')
        with tempfile.TemporaryDirectory(prefix='ao-order-unit-') as tmp:
            db = pathlib.Path(tmp) / 'synthetic.db'
            with closing(sqlite3.connect(db)) as connection, connection:
                connection.execute('CREATE TABLE personajes (usuario TEXT, char_id INTEGER, datos TEXT, actualizado_en TEXT)')
                connection.execute('INSERT INTO personajes VALUES (?,?,?,NULL)',
                                   ('unit-test-only', 900001, json.dumps(self.fixture())))
                connection.execute('INSERT INTO personajes VALUES (?,?,?,NULL)',
                                   ('unrelated-unit-only', 900002, json.dumps({'untouched': True})))
            env = dict(_LOCK=threading.Lock(), _get_conn=lambda: sqlite3.connect(db),
                       json=json, _notificar_cambio=Mock())
            exec(compile(ast.Module(body=[node], type_ignores=[]), 'isolated-order-db', 'exec'), env)
            submit = env['confirmar_entrega_productor']
            consumption = [(20, 886, 1, 2), (21, 52, 30, 30)]
            rewards = dict(exp=1300, oro=250, creditos=4)
            after, _ = submit('unit-test-only', 900001, consumption, rewards)
            self.assertEqual(after['oro'], 350)
            with self.assertRaises(ValueError):
                submit('unit-test-only', 900001, consumption, rewards)
            with self.assertRaises(ValueError):
                submit('unit-test-only', 900002, consumption, rewards)
            with closing(sqlite3.connect(db)) as connection, connection:
                rows = connection.execute('SELECT char_id, datos FROM personajes ORDER BY char_id').fetchall()
            self.assertEqual(json.loads(rows[0][1]), after)
            self.assertEqual(json.loads(rows[1][1]), {'untouched': True})


if __name__ == '__main__':
    unittest.main()
