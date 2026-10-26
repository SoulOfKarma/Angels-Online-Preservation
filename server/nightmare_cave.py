"""Nightmare Cave: original NPC trees, paid permit and Dream Piece rewards."""
import functools
import json
import pathlib
import struct

STAGE = 61
HEAD_STAGES = {3, 26, 29, 38}
ENTRANCE_STAGES = {8, 9, 25, 28}
SPIRIT_ROOTS = {1924: 60101, 1925: 60201, 1926: 60301, 1927: 60401}


@functools.lru_cache(maxsize=None)
def npcs(stage):
    import app
    file = app.mapas_poblados().get(stage)
    if not file:
        return {}
    data = json.loads((pathlib.Path(__file__).parent / 'plantillas' / file).read_text('utf8'))
    return {r['entity_id']: r for r in data.get('spawns', [])
            if not r.get('monstruo') and r.get('npc_type') in range(1920, 1928)}


def _near(s, context):
    p = getattr(s, 'personaje', None)
    return bool(p and context and p is context['character'] and p.stage == context['stage']
                and not getattr(s, 'muerto', False)
                and max(abs(p.tile_x - context['tile'][0]), abs(p.tile_y - context['tile'][1])) <= 8)


def pulsar(s, entity, addr):
    import app
    p = s.personaje
    row = npcs(p.stage).get(entity)
    if not row:
        return False
    root = SPIRIT_ROOTS.get(row['npc_type']) or app.DIALOGO_DE_NPC.get((p.stage, row['npc_type']))
    if not root:
        return False
    context = dict(character=p, stage=p.stage, tile=row['tile'], npc=row['npc_type'])
    s._nightmare_reward = None
    s._nightmare_entry = None
    s._nightmare_npc = context
    if _near(s, context):
        s.dlg_mapa = None
        s.dlg_quest_ofrecida = s.dlg_quest_fase = None
        app._recorrer_dialogo_mapa(s, addr, p.stage, root)
    return True


def _line(s, node, rewards=(), select=False, follow=False):
    import dialogos
    opts = node.get('o') or []
    packet = bytearray(dialogos.armar_linea(node['m'], node.get('c', 0),
                         [m for m, _ in opts], acciones=[target for _, target in opts]))
    packet[10] = len(rewards) | (0x80 if select else 0)
    packet += b''.join(struct.pack('<II', item, qty) for item, qty in rewards)
    guion = [bytes(packet[2:])]
    if follow:
        import dialogos_mapa
        tree = dialogos_mapa._arbol(s.personaje.stage)
        current, seen = node.get('s'), set()
        while current and current not in seen and len(guion) < 8:
            seen.add(current)
            following = tree.get(str(current), {})
            if following.get('m'):
                guion.append(dialogos.armar_linea(following['m'], following.get('c', node.get('c', 0)), [])[2:])
            current = following.get('s')
    s.dlg_ent, s.dlg_guion, s.dlg_paso = s.personaje.entity_id, guion, 1
    s.dlg_mapa = dict(stage=s.personaje.stage, opciones=opts, guion=guion) if opts else None
    s.enviar(bytes(packet))


def _pairs(args):
    return [(int(args[i]), int(args[i+1])) for i in range(0, len(args)-1, 2)
            if int(args[i]) > 0 and int(args[i+1]) > 0]


def before_dialogue(s, stage, key):
    import app, clases, dialogos, dialogos_mapa, recent_mall
    if stage not in HEAD_STAGES | ENTRANCE_STAGES | {STAGE}:
        return False
    tree = dialogos_mapa._arbol(stage)
    node = tree.get(str(key), {})
    actions = dict(node.get('a', []))
    # Buy the original permit atomically with its 50,000 gold charge.
    permit = stage in HEAD_STAGES and 20 in actions and (2852, 1) in _pairs(actions.get(10, []))
    preview = stage == STAGE and 12 in actions
    select = stage == STAGE and 47 in actions
    summon = stage == STAGE and 31 in actions and 9 in actions
    entry = stage in ENTRANCE_STAGES and node.get('m') == 6022
    if not (permit or preview or select or summon or entry):
        return False
    context = getattr(s, '_nightmare_npc', None)
    if not _near(s, context):
        return True
    if entry:
        if context['npc'] != 1923:
            return True
        import eventos_mundo
        if eventos_mundo.ContextoSesion(s).en_bolsa(2852) < 1:
            app._recorrer_dialogo_mapa(s, getattr(s, 'addr', 'nightmare'), stage, 6019)
            return True
        destination = next((args for action, args in tree.get(str(node.get('s')), {}).get('a', [])
                            if action == 3 and len(args) == 2 and args[0] == STAGE), None)
        if destination:
            _line(s, node)
            # CHANGE_MAP follows message6022 in the native tree. Execute it
            # only when the player finishes this exact warning dialogue.
            s._nightmare_entry = dict(context=context, guion=s.dlg_guion,
                                      destination=tuple(destination))
        return True
    if summon:
        if context['npc'] not in SPIRIT_ROOTS:
            return True
        import eventos_mundo
        ctx = eventos_mundo.ContextoSesion(s)
        for branch in node.get('r', []):
            if dialogos_mapa._cumple(branch, ctx):
                app._recorrer_dialogo_mapa(s, getattr(s, 'addr', 'nightmare'), stage, branch['ir'])
                return True
        try:
            recent_mall.cambiar(s, _consumption(s, _pairs(actions[9])), [])
        except recent_mall.Rechazo as exc:
            s.enviar(clases.aviso(str(exc), tipo=0))
            return True
        _line(s, node, follow=True)
        app._generar_zona(s, getattr(s, 'addr', 'nightmare'), stage, int(actions[31][0]), cuantos=1)
        return True
    if permit:
        if context['npc'] != 1920:
            return True
        if s.personaje.nivel < 40:
            _line(s, dict(m=6018, c=node.get('c', 0)))
            return True
        balance = []
        def pay(con, data):
            if sum(int(data['cantidades'].get(slot, 1)) for slot, item in data['inventario'].items() if int(item) == 2852) > 1:
                raise recent_mall.Rechazo('You already have an Ancient Crypt Passport.')
            gold = int(data.get('oro', 0))
            if gold < 50000:
                raise recent_mall.Rechazo("You don't have enough gold for the passport.")
            data['oro'] = gold - 50000
            balance.append(data['oro'])
        try:
            recent_mall.cambiar(s, {}, [(2852, 1)], transaccion=pay)
        except recent_mall.Rechazo as exc:
            s.enviar(clases.aviso(str(exc), tipo=0))
            return True
        s.personaje.oro = s.oro = balance[0]
        s.enviar(*app._refrescar(s, [], con_oro=True))
        _line(s, node)
        return True
    if context['npc'] not in (1921, 1922):
        return True
    rewards = _pairs(actions[47 if select else 12])
    if select:
        next_node = tree.get(str(node.get('s')), {})
        costs = _pairs(dict(next_node.get('a', [])).get(48, []))
        if not costs:
            return True
        s._nightmare_reward = dict(context=context, rewards=rewards, costs=costs,
                                  message=next_node.get('m', 6059), face=node.get('c', 0))
    _line(s, node, rewards, select)
    if select:
        s._nightmare_reward['guion'] = s.dlg_guion
    return True


def _consumption(s, costs):
    import app, recent_mall
    result = {}
    for item, qty in costs:
        for slot, owned in sorted(s.inventario.items()):
            if owned != item or not 20 <= slot <= app._tope_bolsa(s.inventario):
                continue
            take = min(qty, app._cantidades(s).get(slot, 1))
            result[slot] = take
            qty -= take
            if not qty:
                break
        if qty:
            raise recent_mall.Rechazo('Not enough required items. Nothing was consumed.')
    return result


def _finish_entry(s, value):
    import app, dialogos, eventos_mundo
    pending = getattr(s, '_nightmare_entry', None)
    if not pending:
        return False
    s._nightmare_entry = None
    if getattr(s, 'dlg_guion', None) is not pending['guion']:
        return False
    s.dlg_ent = s.dlg_mapa = None
    s.enviar(struct.pack('<H', 0x12) + dialogos.FIN)
    if (value == 1 and _near(s, pending['context'])
            and eventos_mundo.ContextoSesion(s).en_bolsa(2852) >= 1):
        stage, tag = pending['destination']
        app._aplicar_efectos(s, getattr(s, 'addr', 'nightmare'), [('viajar', stage, tag)])
    return True


def choose(s, value):
    import app, clases, recent_mall
    if _finish_entry(s, value):
        return True
    pending = getattr(s, '_nightmare_reward', None)
    if not pending:
        return False
    s._nightmare_reward = None
    if getattr(s, 'dlg_guion', None) is not pending.get('guion'):
        return False
    if not 20 <= value < 20 + len(pending['rewards']) or not _near(s, pending['context']):
        return True
    try:
        consume = _consumption(s, pending['costs'])
    except recent_mall.Rechazo as exc:
        s.enviar(clases.aviso(str(exc), tipo=0))
        return True
    try:
        recent_mall.cambiar(s, consume, [pending['rewards'][value-20]])
    except recent_mall.Rechazo as exc:
        s.enviar(clases.aviso(str(exc), tipo=0))
        return True
    _line(s, dict(m=pending['message'], c=pending['face']))
    return True


def created(s, monster):
    """The four original bosses spawn attendants through TRAS_CREARSE(10)."""
    import app, eventos, eventos_mundo
    if s.personaje.stage != STAGE:
        return
    event = eventos_mundo.evento_del_monstruo(STAGE, monster.npc_type)
    if event:
        effects = eventos.ejecutar(STAGE, event, eventos.TRAS_CREARSE,
                                  eventos_mundo.ContextoSesion(s))
        if effects:
            app._aplicar_efectos(s, getattr(s, 'addr', 'nightmare'), effects)
