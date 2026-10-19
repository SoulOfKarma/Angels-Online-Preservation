import os
import pathlib
import re
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

import cliente_local


class TestClienteLocalItems(unittest.TestCase):

    def test_bound_equipment_gets_npc_sale_price_but_stays_untradeable(self):
        raw = (
            '<root><道具 編號="48357" 基本名稱="Silent Scream" '
            '物品類別="影刃" 價格="198200000" 右手裝備="是" '
            '不可交易="是" 裝備綁定="是" /></root>'
        ).encode('utf-8')
        patched = cliente_local._parchear_equipo_ligado_vendible_xml_bytes(raw).decode('utf-8')
        self.assertIn('不可交易="是"', patched)
        self.assertIn('收購價格="99100000"', patched)

    def test_non_equipment_and_existing_sale_price_are_unchanged(self):
        raw = (
            '<root>'
            '<道具 編號="1" 價格="100" 不可交易="是" />'
            '<道具 編號="2" 價格="100" 收購價格="12" '
            '右手裝備="是" 不可交易="是" />'
            '</root>'
        ).encode('utf-8')
        patched = cliente_local._parchear_equipo_ligado_vendible_xml_bytes(raw)
        self.assertEqual(patched, raw)

    def test_real_silent_scream_is_made_sellable(self):
        item5 = (pathlib.Path(__file__).parent.parent / 'extracted_paks' /
                 'update26' / 'setting' / 'eng' / 'item5.xml')
        if not item5.exists():
            self.skipTest('item5.xml not available')
        patched = cliente_local._parchear_equipo_ligado_vendible_xml_bytes(
            item5.read_bytes()).decode('utf-8')
        tag = re.search(r'<道具 編號="48357"[^>]*?/>', patched)
        self.assertIsNotNone(tag)
        self.assertIn('不可交易="是"', tag.group(0))
        self.assertIn('收購價格="99100000"', tag.group(0))


if __name__ == '__main__':
    unittest.main()
