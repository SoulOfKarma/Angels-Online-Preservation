"""Color valido, cantidades y dialogos de mision conservados."""
import pytest

from colores_texto import normalizar_colores
from reparar_colores_dialogo import corregir_xml
import traducir
import tw_migracion


@pytest.mark.parametrize('old,new', [
    ('Ask the /c$ 2Medicine Lecturer/c*.', 'Ask the /c$2Medicine Lecturer/c*.'),
    ('[/c$ 2 Gagabu Clan/c*]', '[/c$2 Gagabu Clan/c*]'),
    ('[/c$ 2 Magic Eye /c*]', '[/c$2 Magic Eye /c*]'),
    ('Get /c$ 25 Pink Diamonds/c*', 'Get /c$25 Pink Diamonds/c*'),
    ('/c$ Level 50 and lower/c*', '/c$2 Level 50 and lower/c*'),
    ('/c$ Level 51 and higher/c*', '/c$2 Level 51 and higher/c*'),
    ('try /c$ fishing/c* there', 'try /c$2 fishing/c* there'),
    ('/c$2Medicine Lecturer/c*', '/c$2Medicine Lecturer/c*'),
    ('%1: /c$25 Pink Diamonds/c*&#xA;Lv 50\\n', '%1: /c$25 Pink Diamonds/c*&#xA;Lv 50\\n'),
])
def test_repair_preserves_visible_quantities_and_other_markers(old, new):
    assert normalizar_colores(old) == new
    assert normalizar_colores(new) == new


def test_xml_changes_only_the_visible_field():
    old = ('\ufeff<root>\r\n<字串 編號="60407" 文字="Hello %1, /c$ 2Medicine Lecturer/c* &amp; 5 pies!" '
           '其他="/c$ 2"/>\r\n<字串 編號="9" 文字="Unchanged"/></root>').encode('utf-8')
    new, changes = corregir_xml(old)
    assert new == old.replace(b'/c$ 2Medicine', b'/c$2Medicine')
    assert [(c['id'], c['field']) for c in changes] == [('60407', '文字')]
    assert corregir_xml(new) == (new, [])


@pytest.fixture
def translator(tmp_path, monkeypatch):
    memory = tmp_path / 'memoria.json'
    memory.write_text('{"藥劑老師": "/c$ 2Medicine Lecturer/c*"}', encoding='utf-8')
    monkeypatch.setattr(traducir.tw, 'MEMORIA', memory)
    monkeypatch.setattr(traducir, 'MANUAL', tmp_path / 'manual')
    return traducir.Traductor()


def test_translation_memory_cannot_reintroduce_invalid_color(translator):
    assert translator.traducir('藥劑老師') == ('/c$2Medicine Lecturer/c*', True)
    assert translator.traducir('/c$ 2Medicine Lecturer/c*') == ('/c$2Medicine Lecturer/c*', True)


def test_rebuild_also_fixes_existing_english_rows(translator):
    original = '<字串 編號="60407" 文字="/c$ 2Medicine Lecturer/c*" 不變="/c$ 2"/>'
    assert tw_migracion.traducir_xml(original, translator) == original.replace(
        '/c$ 2Medicine', '/c$2Medicine')
