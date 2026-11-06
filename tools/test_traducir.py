"""Regresiones de pergaminos IGG, marcadores y correcciones manuales."""
import json

import pytest

import traducir


@pytest.fixture
def trad(tmp_path, monkeypatch):
    memory = tmp_path / 'memoria.json'
    memory.write_text(json.dumps({'反連鎖戰術Ⅴ': 'Wallpaper Frame Egg'}), encoding='utf-8')
    manual = tmp_path / 'manual'
    manual.mkdir()
    entries = {
        '反連鎖戰術Ⅴ': 'Anti-Chain Tactics V',
        '對目標進行治療，若於恢復後目標血量仍低於#%，則再恢復額外血量。':
            "Heals the target. If the target's HP is still below #% after healing, restores additional HP.",
        '效用持續%#。': 'Lasts %#.',
        '提升HP與MP。': 'Increases HP & MP.',
    }
    for zh, en in zip('ⅠⅡⅢⅣⅤ', ('I', 'II', 'III', 'IV', 'V')):
        entries['極限療癒' + zh] = 'Ultimate Healing ' + en
    (manual / 'skills.json').write_text(json.dumps(entries), encoding='utf-8')
    monkeypatch.setattr(traducir.tw, 'MEMORIA', memory)
    monkeypatch.setattr(traducir, 'MANUAL', manual)
    return traducir.Traductor()


def test_manual_correction_overrides_reused_id(trad):
    assert trad.traducir('反連鎖戰術Ⅴ') == ('Anti-Chain Tactics V', True)


@pytest.mark.parametrize('ordinal,rank', list(zip('一二三四五', range(1, 6))))
def test_scroll_uses_igg_rank_and_keeps_threshold(trad, ordinal, rank):
    source = ('極限療癒第%s階，「對目標進行治療，若於恢復後目標血量仍低於30%%，'
              '則再恢復額外血量。」的招式，對卷軸按下右鍵即可學會。') % ordinal
    expected = ("Ultimate Healing rank %d, [Heals the target. If the target's HP is still "
                'below 30%% after healing, restores additional HP.], right click the scroll to learn.') % rank
    assert trad.traducir(source) == (expected, True)
    assert trad.segmentos_pendientes(source) == []


def test_existing_igg_scroll_translation_is_preserved(trad):
    source = '極限療癒第一階，「效用持續%1。」的法術，對卷軸按下右鍵即可學會。'
    trad.tm[source] = 'Existing IGG scroll wording.'
    assert trad.traducir(source) == ('Existing IGG scroll wording.', True)


@pytest.mark.parametrize('source', [
    '極限療癒第一階，「尚未翻譯的說明。」的招式，對卷軸按下右鍵即可學會。',
    '未知法術第一階，「效用持續%1。」的法術，對卷軸按下右鍵即可學會。',
])
def test_incomplete_scroll_stays_pending(trad, source):
    assert trad.traducir(source) == (source, False)
    assert trad.segmentos_pendientes(source)


def test_xml_separators_and_duration_markers_are_preserved(trad):
    source = '效用持續%1。&#xA;提升HP與MP。\\n效用持續%2。'
    assert trad.traducir(source) == (
        'Lasts %1.&#xA;Increases HP &amp; MP.\\nLasts %2.', True)
