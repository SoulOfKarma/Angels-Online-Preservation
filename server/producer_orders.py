"""Validated deltas for producer deliveries; no database or account access."""
import copy


def reward_progress(data, rewards, level_curve=None, level_cap=None, rank_curve=None):
    result = dict(data)
    if level_curve:
        result['exp'] = max(int(result.get('exp', 0)), level_curve(int(result.get('nivel', 1))))
    for key in ('exp', 'oro', 'creditos'):
        value = int(rewards.get(key, 0))
        if value < 0:
            raise ValueError('Invalid producer reward')
        result[key] = int(result.get(key, 0)) + value
    if level_curve and level_cap:
        old_level = level = int(result.get('nivel', 1))
        while level < level_cap:
            threshold = level_curve(level + 1)
            if threshold <= 0 or result['exp'] < threshold:
                break
            level += 1
        result['nivel'] = level
        if level > old_level:
            result['hp_max'] = int(result.get('hp_max', 280)) + (level - old_level) * 25
            result['mp_max'] = int(result.get('mp_max', 154)) + (level - old_level) * 15
    if rank_curve:
        result['rango'] = max(int(result.get('rango', 1)), rank_curve(result['creditos']))
    return result


def apply_delivery(data, consumption, rewards, bonus=None,
                   level_curve=None, level_cap=None, rank_curve=None):
    """Edit only validated delivery slots and increment its three rewards.

    consumption: (slot, item, amount, expected_count). A stale request raises
    before changing anything. Unrelated inventory and character data survive.
    """
    inventory = data.get('inventario', {})
    quantities = data.get('cantidades', {})
    for slot, item, amount, expected in consumption:
        key = str(slot)
        if (inventory.get(key) != item or int(quantities.get(key, 1)) != expected
                or amount <= 0 or amount > expected):
            raise ValueError('Producer delivery inventory changed')
    after = copy.deepcopy(data)
    inventory = after.setdefault('inventario', {})
    quantities = after.setdefault('cantidades', {})
    touched = set()
    for slot, item, amount, expected in consumption:
        key = str(slot)
        touched.add(key)
        if amount == expected:
            inventory.pop(key)
            quantities.pop(key, None)
            after.setdefault('mejoras', {}).pop(key, None)
        else:
            quantities[key] = expected - amount
    if bonus:
        slot, item, amount = bonus
        key = str(slot)
        if key in inventory and inventory[key] != item:
            raise ValueError('No space for producer delivery reward')
        quantities[key] = (int(quantities.get(key, 1)) if key in inventory else 0) + amount
        inventory[key] = item
        touched.add(key)
    after = reward_progress(after, rewards, level_curve, level_cap, rank_curve)
    return after, touched
