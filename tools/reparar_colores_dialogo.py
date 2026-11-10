"""Preparar un lote de textos de color para G, F y el cliente, con respaldo.

No importa el servidor ni modifica bases de datos, misiones o Rust.
Instalar cada manifiesto mediante recuperar_traducciones_update32.py.
"""
import argparse
import datetime
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pak_tool
import recuperar_traducciones_update32 as recovery
import tw_migracion as tw
from colores_texto import normalizar_colores

ROOT = pathlib.Path(__file__).resolve().parents[1]


def corregir_xml(original):
    text = original.decode('utf-8-sig')
    changes = []

    def row(match):
        def attr(m):
            if not tw.es_texto(m[1]):
                return m[0]
            value = normalizar_colores(m[2])
            if value == m[2]:
                return m[0]
            changes.append({'id': match[2], 'field': m[1], 'before': m[2], 'after': value})
            return m[0][:m[0].index('=') + 1] + '"' + value + '"'
        return tw.RE_ATTR.sub(attr, match[0])

    new = tw.RE_FILA.sub(row, text)
    if new == text:
        return original, changes
    # Una sola pasada: ni reserializar XML ni tocar escapes/saltos/otros campos.
    bom = b'\xef\xbb\xbf' if original.startswith(b'\xef\xbb\xbf') else b''
    return bom + new.encode('utf-8'), changes


def preparar(project, client, output):
    project, client, output = project.resolve(), client.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    local = {'project': str(ROOT), 'client': str(ROOT), 'files': []}
    external = {'project': str(project), 'client': str(client), 'files': []}
    details = {'xml': {}, 'paks': {}, 'protected': {}}

    def stage(target, data, manifest):
        before = target.read_bytes() if target.exists() else None
        if before == data:
            return
        i = len(local['files']) + len(external['files'])
        saved, prepared = 'before_%03d' % i, 'after_%03d' % i
        if before is not None:
            (output / saved).write_bytes(before)
        (output / prepared).write_bytes(data)
        manifest['files'].append({'target': str(target), 'before': recovery.sha(before) if before is not None else None,
                                 'after': recovery.sha(data), 'backup': saved if before is not None else None,
                                 'prepared': prepared})

    for root, manifest in ((ROOT, local), (project, external)):
        # Registrar el trabajo de Claude para comprobar que queda intacto.
        for rel in ('server/app.py', 'server/misiones.py', 'server/dialogos_mapa.py',
                    'server/plantillas/eventos.json'):
            path = root / rel
            if path.exists():
                details['protected'][str(path)] = recovery.sha(path.read_bytes())
        for key, (_, path) in recovery.vista(root).items():
            if not key.startswith('setting\\eng\\') or path.suffix.lower() != '.xml':
                continue
            data, changes = corregir_xml(path.read_bytes())
            if changes:
                stage(path, data, manifest)
                details['xml'][str(path)] = changes
        # La salida ya preparada tambien debe conservar el arreglo al instalarse.
        path = root / 'work/salida/setting_update26/setting/eng/msg.xml'
        if path.exists():
            data, changes = corregir_xml(path.read_bytes())
            if changes:
                stage(path, data, manifest)
                details['xml'][str(path)] = changes

    # Comprobar que F conserva la misma version de las herramientas que G
    # antes de estos cambios; rechazar otros avances en lugar de sobrescribirlos.
    for name in ('traducir.py', 'tw_migracion.py'):
        new = (ROOT / 'tools' / name).read_text(encoding='utf-8')
        old = new.replace('from colores_texto import normalizar_colores  # noqa: E402\n', '')
        if name == 'traducir.py':
            old = old.replace('return normalizar_colores(v), True', 'return v, True')
            old = old.replace('return normalizar_colores(r), True', 'return r, True')
            old = old.replace("return normalizar_colores(''.join(trozos)), completo", "return ''.join(trozos), completo")
        else:
            old = old.replace('        if es_texto(a):\n            if RE_CJK.search(v):\n'
                              '                v = trad.traducir(v)[0]\n            v = normalizar_colores(v)',
                              '        if es_texto(a) and RE_CJK.search(v):\n            v = trad.traducir(v)[0]')
        target = project / 'tools' / name
        if target.read_text(encoding='utf-8') not in (old, new):
            raise ValueError('la herramienta de F tiene otros cambios: ' + str(target))
        stage(target, (ROOT / 'tools' / name).read_bytes(), external)
    for name in ('colores_texto.py', 'reparar_colores_dialogo.py', 'test_colores_texto.py'):
        stage(project / 'tools' / name, (ROOT / 'tools' / name).read_bytes(), external)

    # Se revisan los paquetes capaces de tapar update26, ademas del .bak que
    # usa cliente_local. Solo se sustituye el recurso de mensajes que cambia.
    paths = [client / ('update%d.pak' % n) for n in range(26, 33)]
    paths.append(client / 'update26.pak.bak')
    for path in paths:
        if not path.exists():
            continue
        original = path.read_bytes()
        entries, _ = pak_tool.leer_indice(original)
        changes, replacements = [], {}
        for entry in entries:
            key = tw.normal(entry['nombre'])
            if not key.startswith('setting\\eng\\') or not key.endswith('.xml'):
                continue
            raw = pak_tool.leer_entrada(original, entry)
            updated, fields = corregir_xml(raw)
            if fields:
                replacements[entry['nombre']] = updated
                changes.append({'resource': entry['nombre'], 'fields': fields})
        if not replacements:
            continue
        prepared = output / path.name
        prepared.write_bytes(original)
        pak_tool.actualizar(prepared, replacements)
        data = prepared.read_bytes()
        rebuilt, _ = pak_tool.leer_indice(data)
        if [e['nombre'] for e in rebuilt] != [e['nombre'] for e in entries]:
            raise ValueError('cambiaron las rutas del PAK')
        expect = {tw.normal(k): v for k, v in replacements.items()}
        for before, after in zip(entries, rebuilt):
            key = tw.normal(before['nombre'])
            expected = expect.get(key, pak_tool.leer_entrada(original, before))
            if pak_tool.leer_entrada(data, after) != expected:
                raise ValueError('recurso no esperado: ' + key)
        stage(path, data, external)
        details['paks'][str(path)] = changes

    for name, obj in [('local.json', local), ('externo.json', external), ('informe.json', details)]:
        (output / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')
    print('Preparados', len(local['files']), 'archivos locales y', len(external['files']),
          'para F/cliente. Respaldo:', output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=pathlib.Path, default=pathlib.Path(r'F:\Ao Proyect\AO 2'))
    parser.add_argument('--client', type=pathlib.Path, default=pathlib.Path(r'C:\AO\Angels Online'))
    parser.add_argument('--output', type=pathlib.Path, default=ROOT / 'work/backup' /
                        ('colores_dialogo_' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%SUTC')))
    args = parser.parse_args()
    preparar(args.project, args.client, args.output)
