"""Resource visibility follows the same shared depletion counter as gathering."""
import asyncio
import struct
import time

_TIMERS = {}


def _scope(s, stage):
    import app, eventos_mundo
    if int(stage) == 500:
        return ('house', app._casa_actual(s).owner_id)
    if app.es_instancia(stage):
        return ('instance', id(eventos_mundo.estado_de(s)))
    return ('world', int(stage))


def _viewers(s, stage, scope=None):
    import app
    scope = scope or _scope(s, stage)
    candidates = {id(v): v for v in app._tw_sesiones()}
    candidates[id(s)] = s
    for v in candidates.values():
        p = getattr(v, 'personaje', None)
        if (p and p.stage == stage and getattr(v, 'conectado', True)
                and not getattr(v, 'cerrada', False)
                and not getattr(v, 'desconectado', False)
                and not getattr(v, 'mapa_cargando', False)
                and _scope(v, stage) == scope):
            yield v


def _send(s, *packets):
    previous = getattr(s, '_espejando', False)
    s._espejando = True
    try:
        s.enviar(*packets)
    finally:
        s._espejando = previous


def _packets(stage, entity):
    import app, login
    row = next((r for r in app._recursos_de_plantilla(stage)
                if int(r['entity_id']) == int(entity)), None)
    if not row:
        return []
    spawn = (b'\x0e\0' + bytes.fromhex(row['hex']) if row.get('hex')
             else login.objeto_de_mapa(row))
    name = login.objeto_nombrado(row)
    return [spawn] + ([name] if name else [])


def depleted(s, stage, entity, mat, counter):
    """Despawn once, then restore the node for its current scene viewers."""
    if not mat['limite'] or counter[0] < mat['limite']:
        return
    key = id(counter)
    if key in _TIMERS:
        return
    stamp = counter[1]
    scope = _scope(s, stage)
    packet = struct.pack('<HI', 7, entity)
    for v in _viewers(s, stage, scope):
        _send(v, packet)

    def restore():
        _TIMERS.pop(key, None)
        # A reset/replacement belongs to a newer resource lifecycle.
        if counter[1] not in (stamp, 0.0):
            return
        if counter[1] == stamp:
            counter[:] = [0, 0.0]
        for v in _viewers(s, stage, scope):
            _send(v, *_packets(stage, entity))

    delay = max(0, stamp + int(mat.get('reponer') or 0) - time.time())
    _TIMERS[key] = asyncio.get_event_loop().call_later(delay, restore)


def hidden(s):
    import app, eventos_mundo
    stage = s.personaje.stage
    if int(stage) == 500:
        import house_services as hs
        owner = app._casa_actual(s).owner_id
        states = getattr(s, 'house_resource_state', {})
        counters = [(entity, mid, count) for (who, entity, mid), count in states.items()
                    if who == owner and entity in hs.RESOURCES
                    and mid == hs.resource_for(entity, s.personaje.nivel)['material']]
    elif app.es_instancia(stage):
        states = getattr(eventos_mundo.estado_de(s), 'vetas', {})
        counters = [(entity, None, count) for entity, count in states.items()]
    else:
        counters = [(entity, None, count) for (st, entity), count in app._VETAS_MUNDO.items()
                    if st == int(stage)]
    result = set()
    for entity, mid, count in counters:
        if not isinstance(count, list) or not count[1]:
            continue
        if mid is None:
            mid, _ = app._veta_de(stage, entity)
        mat = app._material(mid) if mid else None
        if mat:
            count = app._cuenta_de_veta(s, stage, entity, mat)
            if mat['limite'] and count[0] >= mat['limite']:
                result.add(int(entity))
    return result


def scene(s, packets):
    """Filter exhausted IDs once; do not rescan every resource on map load."""
    exhausted = hidden(s)
    for packet in packets:
        if (len(packet) >= 6 and packet[:2] in (b'\x0e\0', b'\x0f\0')
                and struct.unpack_from('<I', packet, 2)[0] in exhausted):
            continue
        yield packet
