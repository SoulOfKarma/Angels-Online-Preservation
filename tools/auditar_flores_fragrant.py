"""Todas las flores de Fragrant Greenhouse: grafo, cuidado y zonas nativas."""
import collections
import json
import pathlib
import sys

sys.path[:0] = [str(pathlib.Path(__file__).parents[1] / 'server'), str(pathlib.Path(__file__).parent)]
import mapa_del_cliente as mc
import eventos_del_cliente as ec
import dialogos_mapa as dm
import eventos
import transitable


def rutas(tree, root):
    pending = collections.deque([(str(root), [])])
    seen, results = set(), []
    while pending:
        key, choices = pending.popleft()
        if key in seen or key == '0':
            continue
        seen.add(key)
        assert key in tree, ('missing dialogue node', key)
        node = tree[key]
        for action, params in node.get('a', ()):
            if action == 53:
                results.append(dict(nodo=int(key), tag=int(params[0]), cuidados=choices,
                                    mensaje=node.get('m')))
        pending.extend((str(target), choices + [int(message)]) for message, target in node.get('o', ()))
        pending.extend((str(branch['ir']), choices) for branch in node.get('r', ()))
        if node.get('s'):
            pending.append((str(node['s']), choices))
    return results


def auditar():
    path = mc.mapas_del_cliente()[428]
    m = mc.Mapa(428, path)
    tree = dm._arbol(428)
    openers = collections.defaultdict(set)
    for event in ec.disparadores_del_mapa(path):
        for action, params in event['acciones']:
            if action == 25 and params and str(params[0]) in tree:
                if [mid for mid, _ in tree[str(params[0])].get('o', ())] == [517400, 517401, 517402, 517403]:
                    openers[event['evento']].add(params[0])
    data = json.loads((pathlib.Path(__file__).parents[1] / 'server' / 'plantillas' /
                       'fragrant_greenhouse.json').read_text(encoding='utf-8'))
    flowers = []
    native = [o for o in m.objetos if o['evento'] in openers]
    bound_events = set()
    for resource in data['recursos']:
        tile = tuple(resource['tile'])
        event = eventos.evento_en(428, *tile)
        for root in sorted(openers.get(event, ())):
            assert any([25, [root]] in trigger['haz'] for trigger in
                       eventos.disparadores(428, event, eventos.DISPAROS_AL_PULSAR)), (tile, root)
            body = bytes.fromhex(resource['crudo'])
            assert body[38:41] == bytes((0x40, 0x80, m.cursores[event])), (tile, root)
            bound_events.add(event)
            native_routes = rutas(tree, root)
            assert native_routes
            for route in native_routes:
                tag = route['tag']
                native_points = [list(tile) for tile in m.tags[tag]]
                runtime_points = [list(tile) for tile in eventos.casillas_de_tag(428, tag)]
                assert native_points == runtime_points, tag
                route['destinos'] = native_points
                route['destinos_transitables'] = [tile for tile in native_points if transitable.se_pisa(428, *tile)]
                assert route['destinos_transitables'], (root, tag, native_points)
                # _aplicar_efectos toma el primer TAG: comprobar tambien ese.
                assert transitable.se_pisa(428, *native_points[0]), (root, tag, native_points[0])
            flowers.append(dict(tile=list(tile), entidad=resource['entity_id'],
                                sprite=resource['sprite'], evento=event,
                                raiz=root, mensaje=tree[str(root)].get('m'), rutas=native_routes))
    assert flowers
    assert bound_events == set(openers), ('eventos de flores sin punto de clic', set(openers) - bound_events)
    return dict(stage=428, archivo=str(path), referencias_nativas=len(native), flores=flowers,
                destinos=sorted({r['tag'] for f in flowers for r in f['rutas']}))


if __name__ == '__main__':
    report = auditar()
    path = pathlib.Path(__file__).parents[1] / 'work' / 'flores_fragrant.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Flores:', len(report['flores']), 'destinos TAG:', report['destinos'])
    grouped = collections.Counter((f['mensaje'], tuple(sorted({r['tag'] for r in f['rutas']}))) for f in report['flores'])
    print('Por color/destinos:', dict(grouped))
    print('Todos los eventos tienen punto de clic; las rutas y destinos transitables coinciden con los TAG nativos.')
    print(path)
