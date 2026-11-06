"""Restaurar scripts visuales y dialogos omitidos de la region TW.

preparar: respalda y prepara ambos PAK sin escribir en el cliente.
textos: prepara solo las traducciones de flores, libro y comerciantes.
instalar: instala solo los dos PAK verificados y sincroniza sus extraidos.
verificar: comprueba el recurso realmente instalado y todos sus exports.
"""
import datetime
import hashlib
import json
import pathlib
import shutil
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tw_migracion as tw
import traducir
import pak_tool
import smart_script
import mapa_del_cliente as mc
import propagar_dialogos_mapa as pd
import dialogo_npc_del_cliente as dn
import npcs_del_cliente as nd

STATE = tw.RAIZ / 'work' / 'region_tw_reparacion.json'
PL = tw.RAIZ / 'server' / 'plantillas'
REGION = range(423, 430)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_json(path, data):
    if path.name == 'dialogos_mapa.json':
        text = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    else:
        text = json.dumps(data, ensure_ascii=False, indent=1)
    path.write_text(text, encoding='utf-8')


def server_data(backup):
    trees_path, roots_path = PL / 'dialogos_mapa.json', PL / 'dialogo_npc_mapa.json'
    trees = json.loads(trees_path.read_text(encoding='utf-8'))
    roots = json.loads(roots_path.read_text(encoding='utf-8'))
    for path in (trees_path, roots_path):
        shutil.copy2(path, backup / path.name)
    maps = mc.mapas_del_cliente()
    for stage in REGION:
        m = mc.Mapa(stage, maps[stage])
        nodes = {str(n.get('編號')): pd._nodo(n) for n in pd._nodos(m.dialogos_xml)}
        assert nodes, stage
        trees.setdefault(str(stage), {}).update(nodes)
        native_roots = dn.raices(stage, maps[stage], nodes, nd._npcs())
        roots.setdefault(str(stage), {}).update(native_roots)
        print('stage', stage, 'dialogos', len(nodes), 'NPC', len(native_roots))
    save_json(trees_path, trees)
    save_json(roots_path, roots)
    changed = 0
    for path in PL.glob('*.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, UnicodeError):
            continue
        if not isinstance(data, dict) or data.get('stage') not in REGION:
            continue
        totems = [r for r in data.get('spawns', []) if r.get('npc_type') in (1937, 1938, 1939, 1940)]
        if any(r.get('visible', 1) != 0 for r in totems):
            shutil.copy2(path, backup / path.name)
            for r in totems:
                r['visible'] = 0  # El mismo flag de los cuatro totems capturados en Lyceum.
            changed += len(totems)
            save_json(path, data)
    print('Rotulos de totem: restaurado hover nativo en', changed, 'entidades')
    flores(backup)


def flores(backup):
    """Conecta los dialogos de flores que solo tienen decorado en el MPC."""
    path = PL / 'fragrant_greenhouse.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    m = mc.Mapa(428, mc.mapas_del_cliente()[428])
    trees = json.loads((PL / 'dialogos_mapa.json').read_text(encoding='utf-8'))['428']
    import eventos_del_cliente as ec
    flower_events = {event['evento'] for event in ec.disparadores_del_mapa(m.ruta)
                     for action, params in event['acciones']
                     if action == 25 and params and
                     [mid for mid, _ in trees.get(str(params[0]), {}).get('o', ())]
                     == [517400, 517401, 517402, 517403]}
    native_by_tile = {tuple(o['tile']): o for o in m.objetos if o['evento']}
    resources = data['recursos']
    bound = {native_by_tile[tuple(r['tile'])]['evento'] for r in resources
             if tuple(r['tile']) in native_by_tile}
    added = 0
    for event in sorted(flower_events - bound):
        # En 5011 el evento esta en el decorado 12986; las otras flores
        # usan el interactivo 60305 sobre el decorado. Conservar el arte
        # y anadir ese mismo punto de clic con la casilla y cursor nativos.
        obj, = [o for o in m.objetos if o['evento'] == event]
        sample = next(r for r in resources if r['sprite'] == 60305 and r.get('crudo'))
        eid = max(r['entity_id'] for r in resources) + 1
        px = (obj['px'][0], obj['tile'][1] * 32 + 16)
        body = bytearray.fromhex(sample['crudo'])
        struct.pack_into('<II', body, 0, eid, obj['capa'])
        struct.pack_into('<II', body, 8, *px)
        body[38:41] = bytes((0x40, 0x80, m.cursores[event]))
        resources.append(dict(entity_id=eid, sprite=60305, capa=obj['capa'],
                              px=list(px), tile=list(obj['tile']), crudo=body.hex(),
                              evento=event, copiado_de='interactivo 60305 de las otras flores; evento nativo %d' % event))
        added += 1
    if added:
        saved = backup / path.name
        if not saved.exists():
            shutil.copy2(path, saved)
        save_json(path, data)
    print('Flores: anadidos', added, 'puntos de clic para eventos sin interactivo')


def contents(pak):
    data = pak.read_bytes()
    entries, _ = pak_tool.leer_indice(data)
    return {tw.normal(e['nombre']): pak_tool.leer_entrada(data, e) for e in entries}


def preparar(solo_textos=False):
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = tw.BACKUPS / ('region_tw_' + stamp)
    stage = backup / 'preparado'
    stage.mkdir(parents=True)
    resources = {}
    if not solo_textos:
        index = tw.indice_igg()
        native = tw.indice_tw()['script\\magic.so'][1].read_bytes()
        old = index['script\\magic.so'][1].read_bytes()
        added = smart_script.compatible(old, native)
        symbols = smart_script.simbolos(native)
        assert all('%s%03d' % (prefix, number) in symbols
                   for number in range(715, 734) for prefix in ('cast', 'magic'))
        print('magic.so: conserva', len(smart_script.simbolos(old)), 'simbolos antiguos; anade', len(added))
        resources['script\\magic.so'] = native
    msg_path = tw.IGG / 'update26' / 'setting' / 'eng' / 'msg.xml'
    raw_msg = msg_path.read_bytes()
    trad = traducir.Traductor()
    ids = {str(i) for i in (*range(517382, 517406), *range(516871, 516876))}
    def translate(match):
        if match.group(2) not in ids:
            return match.group(0)
        row = tw.traducir_xml(match.group(0), trad)
        assert not tw.RE_CJK.search(tw.atributos(row).get('文字', ''))
        return row
    text = tw.RE_FILA.sub(translate, raw_msg.decode('utf-8-sig'))
    resources['setting\\eng\\msg.xml'] = (b'\xef\xbb\xbf' if raw_msg.startswith(b'\xef\xbb\xbf') else b'') + text.encode('utf-8')
    for rel, raw in resources.items():
        dest = stage / pathlib.PureWindowsPath(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    report = dict(backup=str(backup), stage=str(stage), paks={}, resources={rel: sha(raw) for rel, raw in resources.items()})
    for name in ('update26.pak', 'update26.pak.bak'):
        path = tw.CLIENTE / name
        original = backup / name
        shutil.copy2(path, original)
        candidate = stage / name
        shutil.copy2(path, candidate)
        before = contents(original)
        pak_tool.actualizar(candidate, resources)
        after = contents(candidate)
        assert set(after) == set(before) | set(resources)
        assert all(after[rel] == raw for rel, raw in resources.items())
        assert all(after[rel] == raw for rel, raw in before.items() if rel not in resources)
        report['paks'][name] = [sha(original.read_bytes()), sha(candidate.read_bytes())]
        print(name, len(after), 'entradas CRC OK; alcance:', sorted(resources))
    # Un archivo suelto tendria prioridad sobre los PAK: no ocultar ese caso.
    assert not (tw.CLIENTE / 'script' / 'magic.so').exists(), 'Hay un magic.so suelto que debe revisarse'
    if not solo_textos:
        server_data(backup)
    if STATE.exists():
        shutil.copy2(STATE, backup / 'region_tw_reparacion_anterior.json')
    save_json(STATE, report)
    print('Respaldo y preparado:', backup)


def instalar():
    report = json.loads(STATE.read_text(encoding='utf-8'))
    stage = pathlib.Path(report['stage'])
    for name, (old, new) in report['paks'].items():
        assert sha((tw.CLIENTE / name).read_bytes()) in (old, new), name
        assert sha((stage / name).read_bytes()) == new, name
    for name in report['paks']:
        shutil.copy2(stage / name, tw.CLIENTE / name)
        print('Instalado:', tw.CLIENTE / name)
    for rel in report['resources']:
        dest = tw.IGG / 'update26' / pathlib.PureWindowsPath(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(stage / pathlib.PureWindowsPath(rel), dest)


def verificar():
    report = json.loads(STATE.read_text(encoding='utf-8'))
    for name, (_, expected) in report['paks'].items():
        path = tw.CLIENTE / name
        assert sha(path.read_bytes()) == expected
        files = contents(path)
        for rel, checksum in report['resources'].items():
            assert sha(files[rel]) == checksum, (name, rel)
        exports = smart_script.simbolos(files['script\\magic.so'])
        assert all('%s%03d' % (prefix, number) in exports
                   for number in range(715, 734) for prefix in ('cast', 'magic'))
        print(name, 'funciones cast715..733 y magic715..733 presentes y CRC valido')


if __name__ == '__main__':
    def instalar_flores():
        flores(pathlib.Path(json.loads(STATE.read_text(encoding='utf-8'))['backup']))
    {'preparar': preparar, 'textos': lambda: preparar(solo_textos=True),
     'instalar': instalar, 'verificar': verificar,
     'flores': instalar_flores}[sys.argv[1]]()
