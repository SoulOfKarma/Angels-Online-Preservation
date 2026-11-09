import datetime
import pathlib
import re
import shutil
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
sys.path.insert(0, str(ROOT / 'tools'))

import pase
import tw_migracion


def test_missing_current_pass_quest_lists_are_rebuilt():
    now = datetime.datetime(2026, 11, 5, 21)
    day, week = pase._periodos(now)
    state = pase.Estado(12345, {'dia': day, 'semana': week, 'listas': {}})

    assert state.al_dia(now) == [1, 2]
    assert [len(state.listas[n]) for n in range(1, 5)] == [3, 7, 4, 6]

    packet = pase.paquete_estado(state)
    assert len(packet) == 344
    assert int.from_bytes(packet[24:28], 'little') == state.listas[1][0][0]
    assert state.al_dia(now) == []


def test_map_tabs_use_taiwan_page_and_have_clear_spacing(tmp_path, monkeypatch):
    source = ROOT / 'extracted_paks' / 'update26' / 'setting' / 'eng'
    legacy = tmp_path / 'legacy'
    legacy.mkdir()
    text = (source / 'wnd01.xml').read_text(encoding='utf-8-sig')
    text, removed = re.subn(
        r'\t<window class="WND_CLASS_BUTTON" id="25516".*?</window>\r?\n?',
        '', text, count=1, flags=re.DOTALL)
    assert removed == 1
    text = text.replace('\t\t<child>25516</child>\r\n', '')
    night = text.find('id="25515"')
    night_end = text.find('</window>', night)
    text = (text[:night] + text[night:night_end].replace(
        'wsTab=""/>', 'wsTab="" bsRadioEnd=""/>') + text[night_end:])
    for ident, x in {'25513': 134, '25514': 234, '25515': 334, '25516': 434}.items():
        text = re.sub(r'(id="%s" range=")\d+,561,\d+,17(")' % ident,
                      r'\g<1>%d,561,98,17\2' % x, text)
        text = re.sub(r'(<window class="WND_CLASS_BUTTON" id="%s"[^>]*\bappdata=")\d+(")' % ident,
                      r'\g<1>7\2', text)
    text = re.sub(r'(id="24750" range=")\d+,561,70,18(")',
                  r'\g<1>545,561,70,18\2', text)
    (legacy / 'wnd01.xml').write_text(text, encoding='utf-8')
    shutil.copy2(source / 'wnd05.xml', legacy / 'wnd05.xml')
    monkeypatch.setattr(tw_migracion.paks, 'vigente',
                        lambda name: legacy / name)
    monkeypatch.setattr(tw_migracion, 'IGG', tmp_path / 'extracted_paks')
    monkeypatch.setattr(tw_migracion, 'CLIENTE', tmp_path / 'client')

    tw_migracion.ajustes_wnd()
    wnd = tmp_path / 'extracted_paks' / 'update26' / 'setting' / 'eng' / 'wnd01.xml'
    root = ET.parse(wnd).getroot()
    tabs = {e.attrib['id']: e for e in root.iter()
            if e.attrib.get('id') in {'25513', '25514', '25515', '25516'}}

    assert set(tabs) == {'25513', '25514', '25515', '25516'}
    ranges = {}
    for ident, button in tabs.items():
        assert button.attrib['appdata'] == '5'
        ranges[ident] = [int(value) for value in button.attrib['range'].split(',')]
    assert [ranges[str(ident)][0] for ident in (25513, 25514, 25515, 25516)] == [
        134, 254, 374, 494]
    assert all(ranges[str(ident)][2] == 105 for ident in (25513, 25514, 25515, 25516))

    switch = next(e for e in root.iter() if e.attrib.get('id') == '24750')
    switch_x = int(switch.attrib['range'].split(',')[0])
    assert switch_x >= ranges['25516'][0] + ranges['25516'][2] + 15
    assert '<child>25516</child>' in wnd.read_text(encoding='utf-8-sig')
