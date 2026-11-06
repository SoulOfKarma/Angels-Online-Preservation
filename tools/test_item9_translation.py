"""El paquete preparado conserva datos jugables y tooltips legibles/seguros."""
import collections
import html
import json
import pathlib
import re
import unicodedata
import xml.etree.ElementTree as ET

import instalar_item9_traducido as install
import tw_migracion as tw

REPORT=json.loads(install.STATE.read_text(encoding='utf-8'))
STAGE=pathlib.Path(REPORT['stage'])
BACKUP=pathlib.Path(REPORT['backup'])


def installed_or_staged(filename):
    path=STAGE/'setting/eng'/filename
    return path if path.exists() else install.BASE/filename


def test_entire_item9_has_english_names_and_descriptions_without_printf_expansion():
    path=installed_or_staged('item9.xml')
    ET.parse(path)
    rows=tw.filas(tw.leer(path))
    assert len(rows)==3700
    for item,row in rows.items():
        for key,value in tw.atributos(row).items():
            if tw.es_texto(key):
                assert not tw.RE_CJK.search(value),(item,key,value)
                assert not install.UNSAFE.search(value),(item,key,value)


def test_item_types_flags_stats_drops_and_unrelated_rows_are_preserved():
    for rel in REPORT['resources']:
        filename=pathlib.PureWindowsPath(rel).name
        if filename=='exchange.xml':continue
        original=BACKUP/filename
        if not original.exists():original=install.BASE/filename
        before=tw.filas(tw.leer(original));after=tw.filas(tw.leer(STAGE/pathlib.PureWindowsPath(rel)))
        assert before.keys()==after.keys()
        for item,row in after.items():
            left,right=tw.atributos(before[item]),tw.atributos(row)
            assert {k:v for k,v in left.items() if not tw.es_texto(k)}=={
                k:v for k,v in right.items() if not tw.es_texto(k)}


def test_reported_great_enma_and_core_tooltips_use_reviewed_text_and_safe_formats():
    rows=tw.filas(tw.leer(installed_or_staged('item9.xml')))
    for item,expected in install.REVIEWED.items():
        row=tw.atributos(rows[str(item)])
        assert html.unescape(row['說明定義'])==expected
        assert '%s' not in row['說明定義']
    assert tw.atributos(rows['82776'])['常駐法術']=='23355'


def test_material_and_reward_labels_for_both_npcs_have_no_untranslated_text():
    config=json.loads((tw.RAIZ/'server/plantillas/tw_exchanges.json').read_text(encoding='utf-8'))
    groups=set(config['exchange_owners'])
    rows=tw.filas(tw.leer(STAGE/'setting/eng/exchange.xml'))
    for key,value in rows.items():
        row=tw.atributos(value)
        if row.get('群組') in groups:
            assert not tw.RE_CJK.search(row['獎賞說明']),(key,row['獎賞說明'])


def test_translation_does_not_lose_visible_numeric_values():
    def numbers(value):
        value=unicodedata.normalize('NFKC',html.unescape(value))
        value=re.sub(r'/c\$\d+|%\d+','',value)
        return collections.Counter(re.findall(r'\d+',value))
    for table,entries in REPORT['tables'].items():
        before=tw.filas(tw.leer(BACKUP/(table+'.xml')))
        after=tw.filas(tw.leer(STAGE/'setting/eng'/(table+'.xml')))
        for item,changes in entries.items():
            left,right=tw.atributos(before[item]),tw.atributos(after[item])
            for key in changes:
                assert not numbers(left.get(key,''))-numbers(right.get(key,'')),(item,key)
