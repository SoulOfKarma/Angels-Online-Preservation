"""Recuperar texto de un proyecto traducido sin sustituir datos de TW.

Preparar no escribe en el proyecto destino ni en el cliente. Instalar solo
aplica el manifiesto preparado, comprueba hashes y conserva los originales.
No importa el servidor, no abre cuentas.db y no ejecuta herramientas Rust.
"""
import argparse
import datetime
import hashlib
import html
import json
import pathlib
import re
import shutil
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pak_tool
import tw_migracion as tw
import extract_content
import parchear_angel_update32 as angel

# Evitar reutilizaciones de ID: precios/estadisticas pueden haber cambiado,
# pero un objeto con otro icono, tipo o efecto no es la misma traduccion.
IDENTIDAD = ('原型介面', '物品類別', '動態資料1', '動態資料2', '常駐法術')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def vista(project):
    base = project / 'extracted_paks'
    return tw.indice(base, [p.name for p in base.iterdir() if p.is_dir()], True)


def recuperar(original, source):
    """Sustituir exclusivamente atributos de texto ya traducidos en source.

    No insertar/eliminar filas ni cambiar atributos mecanicos. No convertir
    enums chinos. Las filas exclusivas del destino quedan intactas.
    """
    reference = tw.filas(source.decode('utf-8-sig'))
    changes, conflicts = {}, []

    def row(match):
        ident = match[2]
        if ident not in reference:
            return match[0]
        old, translated = tw.atributos(match[0]), tw.atributos(reference[ident])
        identity = [k for k in IDENTIDAD if old.get(k) != translated.get(k)]
        if identity:
            conflicts.append({'id': ident, 'fields': identity})
            return match[0]
        fields = {k: v for k, v in translated.items() if k in old and tw.es_texto(k)
                  and v.strip() and not tw.RE_CJK.search(v) and old[k] != v}
        if not fields:
            return match[0]
        changes[ident] = fields
        # Conservar exactamente todo el resto de la fila y su espaciado.
        return tw.RE_ATTR.sub(lambda m: m[0] if m[1] not in fields else
                              m[0][:m[0].index('=') + 1] + '"' + fields[m[1]] + '"', match[0])

    text = original.decode('utf-8-sig')
    result = tw.RE_FILA.sub(row, text)
    raw = (b'\xef\xbb\xbf' if original.startswith(b'\xef\xbb\xbf') else b'') + result.encode('utf-8')
    before, after = list(tw.RE_FILA.finditer(text)), list(tw.RE_FILA.finditer(result))
    if len(before) != len(after):
        raise ValueError('cambio el numero de filas')
    for a, b in zip(before, after):
        a, b = tw.atributos(a[0]), tw.atributos(b[0])
        if {k: v for k, v in a.items() if not tw.es_texto(k)} != {
                k: v for k, v in b.items() if not tw.es_texto(k)}:
            raise ValueError('cambio un atributo mecanico')
    return raw, changes, conflicts


def preparar(source, project, client, output):
    source, project, client, output = [p.resolve() for p in (source, project, client, output)]
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'source': str(source), 'project': str(project), 'client': str(client),
                'files': [], 'tables': {}, 'conflicts': {}, 'pak_changes': {}}

    def stage(target, data):
        if target.exists() and target.read_bytes() == data:
            return
        index = len(manifest['files'])
        saved, prepared = output / ('before_%03d' % index), output / ('after_%03d' % index)
        old = None
        if target.exists():
            shutil.copy2(target, saved)
            old = sha(saved.read_bytes())
        prepared.write_bytes(data)
        manifest['files'].append({'target': str(target), 'before': old,
                                 'after': sha(data), 'prepared': prepared.name,
                                 'backup': saved.name if old else None})

    g, f = vista(source), vista(project)
    translations, db_fields = {}, {}
    for key in sorted(g.keys() & f.keys()):
        if not key.startswith('setting\\eng\\') or not key.endswith('.xml'):
            continue
        # No cambiar enlaces locales ni menus del pase/eventos.
        if key.rsplit('\\', 1)[-1] in ('activityurl.xml', 'actboard.xml', 'battlepass.xml'):
            continue
        reference = g[key][1].read_bytes()
        raw, changes, conflicts = recuperar(f[key][1].read_bytes(), reference)
        translations[key] = reference
        current_rows = tw.filas(raw.decode('utf-8-sig'))
        reference_rows = tw.filas(reference.decode('utf-8-sig'))
        known = {}
        for ident in current_rows.keys() & reference_rows.keys():
            old, ref = tw.atributos(current_rows[ident]), tw.atributos(reference_rows[ident])
            if any(old.get(k) != ref.get(k) for k in IDENTIDAD):
                continue
            known[ident] = {k: v for k, v in ref.items() if k in old and tw.es_texto(k)
                            and v.strip() and not tw.RE_CJK.search(v)}
        db_fields[key] = known
        if conflicts:
            manifest['conflicts'][key] = conflicts
        if changes:
            target = project / 'extracted_paks/update26' / pathlib.PureWindowsPath(key)
            stage(target, raw)
            manifest['tables'][key] = changes

    # Restaurar tambien la memoria/manuales para que una reconstruccion futura
    # no vuelva a perder los textos. Conservar claves exclusivas del destino.
    memory = source / 'work/traduccion'
    for p in sorted(memory.glob('manual/*.json')) + [memory / 'memoria.json']:
        if not p.is_file():
            continue
        target = project / p.relative_to(source)
        old = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
        entries = json.loads(p.read_text(encoding='utf-8'))
        merged = {**old, **entries}
        if old != merged:
            stage(target, json.dumps(merged, ensure_ascii=False, indent=1).encode('utf-8'))

    # Base de contenido: copia SQLite consistente; actualizar solo los mismos
    # atributos visibles, sin reimportar tablas ni sustituir datos del parche.
    db = project / 'corpus/content.db'
    temporary = output / 'content_preparado.db'
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as src:
        con = sqlite3.connect(temporary)
        src.backup(con)
    updates = 0
    try:
        manifest['db_fields_changed'] = {}
        for key, rows in db_fields.items():
            table = pathlib.PureWindowsPath(key).stem
            columns = {r[1] for r in con.execute('PRAGMA table_info("%s")' % table)}
            if 'id' not in columns:
                continue
            # Las tablas exportadas no tienen indice por id: resolver rowid
            # una vez evita miles de barridos completos sin alterar el esquema.
            text_columns = sorted({extract_content.TRAD.get(k, k) for fields in rows.values()
                                   for k in fields} & columns)
            if not text_columns:
                continue
            rowids = {}
            query = 'SELECT rowid,id,%s FROM "%s"' % (
                ','.join('"%s"' % c for c in text_columns), table)
            for values in con.execute(query):
                rowids.setdefault(str(values[1]), []).append(
                    (values[0], dict(zip(text_columns, values[2:]))))
            for ident, fields in rows.items():
                fields = {extract_content.TRAD.get(k, k): html.unescape(v) for k, v in fields.items()}
                fields = {k: v for k, v in fields.items() if k in columns}
                for rowid, previous in rowids.get(ident, []):
                    changed = {k: v for k, v in fields.items() if previous.get(k) != v}
                    if not changed:
                        continue
                    query = 'UPDATE "%s" SET %s WHERE rowid=?' % (
                        table, ','.join('"%s"=?' % k for k in changed))
                    updates += con.execute(query, [*changed.values(), rowid]).rowcount
                    manifest['db_fields_changed'].setdefault(table, {})[str(rowid)] = changed
        con.commit()
        if con.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('integridad SQLite')
    finally:
        con.close()
    stage(db, temporary.read_bytes())
    manifest['db_rows_updated'] = updates

    # Mantener MAIN.L, mapas, graficos, tooltip y todos los assets existentes.
    # Los PAK nuevos no contienen setting/eng (verificar precedencia).
    for i in range(27, 33):
        p = client / ('update%d.pak' % i)
        if not p.exists():
            continue
        entries, _ = pak_tool.leer_indice(p.read_bytes())
        if any(tw.normal(e['nombre']) in translations for e in entries):
            raise ValueError('hay tablas que taparian update26 en ' + str(p))
    for name in ('update26.pak', 'update26.pak.bak'):
        path = client / name
        data = path.read_bytes()
        entries, _ = pak_tool.leer_indice(data)
        replacement, counts = {}, {}
        for e in entries:
            key = tw.normal(e['nombre'])
            if key not in translations:
                continue
            raw, changes, _ = recuperar(pak_tool.leer_entrada(data, e), translations[key])
            if changes:
                replacement[e['nombre']] = raw
                counts[key] = sum(len(v) for v in changes.values())
        prepared = output / name
        prepared.write_bytes(data)
        pak_tool.actualizar(prepared, replacement)
        # CRC de TODOS los recursos y prueba de que solo se modifico texto.
        rebuilt = prepared.read_bytes()
        current = {tw.normal(e['nombre']): pak_tool.leer_entrada(rebuilt, e)
                   for e in pak_tool.leer_indice(rebuilt)[0]}
        expected = {tw.normal(k): v for k, v in replacement.items()}
        if set(current) != {tw.normal(e['nombre']) for e in entries}:
            raise ValueError('cambiaron las rutas del PAK')
        for e in entries:
            key = tw.normal(e['nombre'])
            if current[key] != expected.get(key, pak_tool.leer_entrada(data, e)):
                raise ValueError('recurso alterado: ' + key)
        stage(path, rebuilt)
        manifest['pak_changes'][name] = counts

    path = client / 'angel.dat'
    stage(path, bytes(angel.parchear_dibujo_region30(bytearray(path.read_bytes()))))
    # La herramienta nueva queda disponible tambien en el proyecto Python.
    for name in ('recuperar_traducciones_update32.py', 'parchear_angel_update32.py',
                 'verificar_recuperacion_update32.py', 'test_recuperar_update32.py'):
        stage(project / 'tools' / name, (source / 'tools' / name).read_bytes())
    state = output / 'manifiesto.json'
    state.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    total = sum(len(fields) for rows in manifest['tables'].values() for fields in rows.values())
    print('Preparados:', total, 'textos en', len(manifest['tables']), 'tablas;', updates,
          'filas SQLite;', len(manifest['files']), 'archivos. Manifiesto:', state)
    return manifest


def instalar(state):
    manifest = json.loads(state.read_text(encoding='utf-8'))
    roots = [pathlib.Path(manifest[k]).resolve() for k in ('project', 'client')]
    # Comprobar el lote entero ANTES de escribir: no sobrescribir avances
    # ajenos ni una base de contenido cambiada desde la preparacion.
    for item in manifest['files']:
        target = pathlib.Path(item['target']).resolve()
        if not any(target.is_relative_to(root) for root in roots):
            raise ValueError('destino fuera de los proyectos autorizados')
        if target.name.lower() == 'cuentas.db' or 'rust' in target.parts:
            raise ValueError('destino excluido')
        actual = sha(target.read_bytes()) if target.exists() else None
        if actual not in (item['before'], item['after']):
            raise ValueError('cambio desde la preparacion: ' + str(target))
        if sha((state.parent / item['prepared']).read_bytes()) != item['after']:
            raise ValueError('preparado alterado')
        if actual != item['after'] and target.exists():
            # Detectar PAK/ejecutable bloqueados antes de instalar tablas o DB.
            with target.open('r+b'):
                pass
    done = []
    try:
        for item in manifest['files']:
            target = pathlib.Path(item['target'])
            if target.exists() and sha(target.read_bytes()) == item['after']:
                continue
            # Registrar antes: tambien restaurar si la copia se interrumpe.
            done.append(item)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(state.parent / item['prepared'], target)
            if sha(target.read_bytes()) != item['after']:
                raise ValueError('hash instalado incorrecto: ' + str(target))
    except Exception:
        for item in reversed(done):
            target = pathlib.Path(item['target'])
            if item['backup']:
                shutil.copy2(state.parent / item['backup'], target)
            elif target.exists():
                target.unlink()
        raise
    (state.parent / 'instalado.json').write_text(json.dumps(
        {'date': datetime.datetime.now().isoformat(), 'files': len(done)}), encoding='utf-8')
    print('Instalados y verificados', len(done), 'archivos; respaldos en', state.parent)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('preparar')
    for name in ('source', 'project', 'client', 'output'):
        prep.add_argument('--' + name, type=pathlib.Path, required=True)
    apply = sub.add_parser('instalar')
    apply.add_argument('manifest', type=pathlib.Path)
    args = parser.parse_args()
    if args.command == 'preparar':
        preparar(args.source, args.project, args.client, args.output)
    else:
        instalar(args.manifest.resolve())


if __name__ == '__main__':
    main()
