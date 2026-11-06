"""Parche de textos de las 18 skills nuevas, sin reconstruir otras tablas.

preparar crea copias verificadas; local aplica XML y textos de content.db;
cliente instala exclusivamente update26.pak y su .bak; verificar comprueba todo.
"""
import datetime
import hashlib
import json
import pathlib
import re
import shutil
import sqlite3
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import pak_tool
import traducir
import tw_migracion as tw
import extract_content

HERE = pathlib.Path(__file__).resolve().parent
STATE = HERE / 'skills_instalacion.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def patch_xml(raw, changes):
    text = raw.decode('utf-8-sig')
    found = set()

    def row(match):
        rid = match.group(2)
        if rid not in changes:
            return match.group(0)
        found.add(rid)
        edits = changes[rid]

        def attr(m):
            space, key, value = m.groups()
            if key not in edits:
                return m.group(0)
            old, new = edits[key]
            assert value in (old, new), (rid, key, value, old)
            return '%s%s="%s"' % (space, key, new)

        result = tw.RE_VALOR.sub(attr, match.group(0))
        attrs = tw.atributos(result)
        assert all(attrs.get(k) == new for k, (_, new) in edits.items()), rid
        return result

    result = tw.RE_FILA.sub(row, text)
    assert found == set(changes), ('missing IDs', set(changes) - found)
    ET.fromstring(result)
    return (b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'') + result.encode('utf-8')


def check_pak(before_raw, after_raw, changes):
    before, _ = pak_tool.leer_indice(before_raw)
    after, _ = pak_tool.leer_indice(after_raw)
    assert [e['nombre'] for e in before] == [e['nombre'] for e in after]
    seen = set()
    for a, b in zip(before, after):
        old = pak_tool.leer_entrada(before_raw, a)
        new = pak_tool.leer_entrada(after_raw, b)
        rel = tw.normal(a['nombre'])
        if rel in changes:
            assert new == patch_xml(old, changes[rel]), rel
            seen.add(rel)
        else:
            assert old == new, rel
    assert seen == set(changes)
    return len(after)


def preparar():
    trad = traducir.Traductor()
    indices = tw.indice_tw(True)
    source_items = tw.filas(tw.leer(indices['setting\\eng\\item9.xml'][1]))
    source_magic = tw.filas(tw.leer(indices['setting\\eng\\magic.xml'][1]))
    names = {traducir.PERGAMINO.fullmatch(
        tw.atributos(source_items[str(i)])['說明定義']).group(1)
        for i in range(80625, 80715)}
    assert len(names) == 18
    skill_ids = {i for i, row in source_magic.items()
                 if any(tw.atributos(row).get('名稱', '').startswith(n) for n in names)}
    assert len(skill_ids) == 276
    scopes = {'setting\\eng\\item9.xml': {str(i) for i in range(80625, 80715)},
              'setting\\eng\\magic.xml': skill_ids}
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = tw.BACKUPS / ('skills_' + stamp)
    stage = backup / 'preparado'
    stage.mkdir(parents=True)
    report = dict(backup=str(backup), stage=str(stage), changes={}, local={}, paks={}, db=[])

    for rel, ids in scopes.items():
        path = tw.IGG / 'update26' / pathlib.PureWindowsPath(rel)
        raw = path.read_bytes()
        rows = tw.filas(raw.decode('utf-8-sig'))
        changes = {}
        for rid in sorted(ids, key=int):
            attrs = tw.atributos(rows[rid])
            edits = {}
            for key, old in attrs.items():
                if not tw.es_texto(key):
                    continue
                new, complete = trad.traducir(old)
                assert complete and not tw.RE_CJK.search(new), (rel, rid, key, new)
                if old == new:
                    continue
                if key in ('說明', '說明定義'):
                    body = traducir.PERGAMINO.fullmatch(old)
                    if body:
                        old_nums = traducir.RN.findall(body.group(3))
                        new_nums = traducir.RN.findall(new.split('[', 1)[1].rsplit(']', 1)[0])
                    else:
                        old_nums, new_nums = traducir.RN.findall(old), traducir.RN.findall(new)
                    assert old_nums == new_nums, (rid, old_nums, new_nums)
                    assert re.findall(r'%\d+', old) == re.findall(r'%\d+', new), rid
                    assert traducir.SEP.findall(old) == traducir.SEP.findall(new), rid
                edits[key] = [old, new]
            if edits:
                changes[rid] = edits
        assert changes, rel
        report['changes'][rel] = changes
        prepared = patch_xml(raw, changes)
        dest = stage / pathlib.PureWindowsPath(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(prepared)
        saved = backup / 'extraidos' / pathlib.PureWindowsPath(rel)
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(raw)
        report['local'][rel] = [sha(raw), sha(prepared)]
        print(rel, len(changes), 'filas,', sum(map(len, changes.values())), 'campos')

    # Copias completas de ambos PAK antes de modificar nada instalado.
    for name in ('update26.pak', 'update26.pak.bak'):
        original = tw.CLIENTE / name
        saved = backup / 'cliente' / name
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, saved)
        dest = stage / name
        shutil.copy2(saved, dest)
        raw = saved.read_bytes()
        entries, _ = pak_tool.leer_indice(raw)
        updates = {e['nombre']: patch_xml(pak_tool.leer_entrada(raw, e), report['changes'][tw.normal(e['nombre'])])
                   for e in entries if tw.normal(e['nombre']) in report['changes']}
        assert len(updates) == 2
        assert pak_tool.actualizar(dest, updates) == (2, 0)
        prepared = dest.read_bytes()
        count = check_pak(raw, prepared, report['changes'])
        report['paks'][name] = [sha(raw), sha(prepared)]
        print(name, count, 'entradas CRC OK; solo dos tablas modificadas')

    with sqlite3.connect('file:%s?mode=ro' % (ROOT / 'corpus' / 'content.db').as_posix(), uri=True) as db:
        for rel, rows in report['changes'].items():
            table = pathlib.PureWindowsPath(rel).stem
            for rid, edits in rows.items():
                for key, (old, new) in edits.items():
                    col = extract_content.TRAD.get(key, key)
                    prior = db.execute('SELECT "%s" FROM "%s" WHERE id=?' % (col, table), (rid,)).fetchone()
                    assert prior is not None, (table, rid)
                    old_decoded = ET.fromstring('<x v="%s"/>' % old).attrib['v']
                    new_decoded = ET.fromstring('<x v="%s"/>' % new).attrib['v']
                    assert prior[0] in (old, old_decoded, new_decoded), (table, rid, col, prior[0])
                    if prior[0] != new_decoded:
                        report['db'].append([table, rid, col, prior[0], new_decoded])
    STATE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Preparado:', backup)
    print('Cambios de texto en content.db:', len(report['db']))


def load():
    return json.loads(STATE.read_text(encoding='utf-8'))


def local():
    report = load()
    backup, stage = pathlib.Path(report['backup']), pathlib.Path(report['stage'])
    for rel, (old_hash, new_hash) in report['local'].items():
        path = tw.IGG / 'update26' / pathlib.PureWindowsPath(rel)
        prepared = stage / pathlib.PureWindowsPath(rel)
        assert sha(path.read_bytes()) in (old_hash, new_hash), path
        assert sha(prepared.read_bytes()) == new_hash, prepared
    db = sqlite3.connect(ROOT / 'corpus' / 'content.db')
    if not (backup / 'content.db').exists():
        with sqlite3.connect(backup / 'content.db') as dest:
            db.backup(dest)
    with db:
        for table, rid, col, old, new in report['db']:
            value = db.execute('SELECT "%s" FROM "%s" WHERE id=?' % (col, table), (rid,)).fetchone()[0]
            assert value in (old, new), (table, rid, col)
            db.execute('UPDATE "%s" SET "%s"=? WHERE id=?' % (table, col), (new, rid))
    assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    db.close()
    for rel in report['local']:
        shutil.copy2(stage / pathlib.PureWindowsPath(rel), tw.IGG / 'update26' / pathlib.PureWindowsPath(rel))
    print('XML locales y content.db actualizados; respaldo:', backup)


def cliente():
    report = load()
    stage = pathlib.Path(report['stage'])
    for name, (old_hash, new_hash) in report['paks'].items():
        assert sha((tw.CLIENTE / name).read_bytes()) in (old_hash, new_hash), name
        assert sha((stage / name).read_bytes()) == new_hash, name
    for name in report['paks']:
        shutil.copy2(stage / name, tw.CLIENTE / name)
        print('Instalado:', tw.CLIENTE / name)


def verificar():
    report = load()
    backup = pathlib.Path(report['backup'])
    for rel, (_, expected) in report['local'].items():
        assert sha((tw.IGG / 'update26' / pathlib.PureWindowsPath(rel)).read_bytes()) == expected, rel
    for name, (_, expected) in report['paks'].items():
        raw = (tw.CLIENTE / name).read_bytes()
        assert sha(raw) == expected, name
        check_pak((backup / 'cliente' / name).read_bytes(), raw, report['changes'])
    with sqlite3.connect(ROOT / 'corpus' / 'content.db') as db:
        for table, rid, col, _, expected in report['db']:
            assert db.execute('SELECT "%s" FROM "%s" WHERE id=?' % (col, table), (rid,)).fetchone()[0] == expected
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    print('Verificado: cliente, .bak, XML y content.db coinciden; datos ajenos al parche intactos en ambos PAK.')


if __name__ == '__main__':
    {'preparar': preparar, 'local': local, 'cliente': cliente, 'verificar': verificar}[sys.argv[1]]()
