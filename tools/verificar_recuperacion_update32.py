"""Verificar el lote preparado/instalado y todos los campos SQLite conservados."""
import argparse
import hashlib
import itertools
import json
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import recuperar_traducciones_update32 as recovery


def verificar(state, installed=False):
    manifest = json.loads(state.read_text(encoding='utf-8'))
    checked = 0
    for item in manifest['files']:
        path = pathlib.Path(item['target']) if installed else state.parent / item['prepared']
        if recovery.sha(path.read_bytes()) != item['after']:
            raise ValueError('hash incorrecto: ' + str(path))
        if item['backup'] and recovery.sha((state.parent / item['backup']).read_bytes()) != item['before']:
            raise ValueError('respaldo alterado')
        checked += 1

    item = next(f for f in manifest['files'] if f['target'].endswith('corpus\\content.db'))
    before = state.parent / item['backup']
    after = pathlib.Path(item['target']) if installed else state.parent / item['prepared']
    a = sqlite3.connect(before.resolve().as_uri() + '?mode=ro', uri=True)
    b = sqlite3.connect(after.resolve().as_uri() + '?mode=ro', uri=True)
    total, texts = 0, 0
    try:
        schema = 'SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name'
        if a.execute(schema).fetchall() != b.execute(schema).fetchall():
            raise ValueError('cambio el esquema SQLite')
        for (table,) in a.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            columns = [r[1] for r in a.execute('PRAGMA table_info("%s")' % table)]
            changes = manifest.get('db_fields_changed', {}).get(table, {})
            query = 'SELECT rowid,* FROM "%s" ORDER BY rowid' % table
            for old, new in itertools.zip_longest(a.execute(query), b.execute(query)):
                if old is None or new is None or old[0] != new[0]:
                    raise ValueError('cambiaron las filas: ' + table)
                expected = changes.get(str(old[0]), {})
                for col, x, y in zip(columns, old[1:], new[1:]):
                    if x != y:
                        if expected.get(col) != y:
                            raise ValueError('campo no autorizado: %s.%s fila %s' % (table, col, old[0]))
                        texts += 1
                total += 1
        if b.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('integridad SQLite')
    finally:
        a.close()
        b.close()
    report = {'installed': installed, 'files': checked, 'db_rows_checked': total,
              'text_cells_changed': texts, 'mechanical_changes': 0}
    print(json.dumps(report))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=pathlib.Path)
    parser.add_argument('--instalado', action='store_true')
    args = parser.parse_args()
    verificar(args.manifest.resolve(), args.instalado)
