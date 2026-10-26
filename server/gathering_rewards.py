"""Local 10% producer-order rate, retaining each resource's original pool."""
import functools
import math
import random

ORDER_PERCENT = 10


@functools.lru_cache(maxsize=1)
def order_items():
    from house_services import xml_rows
    return frozenset(int(r.get('\u8a02\u55ae\u539f\u578b') or 0)
                     for r in xml_rows('order.xml').values()) - {0}


@functools.lru_cache(maxsize=2048)
def _pool(items, empty, percent):
    orders = order_items()
    order_weight = sum(w for i, w in items if i in orders)
    other_weight = empty + sum(w for i, w in items if i not in orders)
    if not order_weight or not other_weight:
        return items, empty
    # Integer arithmetic keeps the exact conditional probabilities for both
    # orders and ordinary/rare resources (including an unsuccessful attempt).
    values = [(i, w * other_weight * percent if i in orders
               else w * order_weight * (100 - percent)) for i, w in items]
    empty *= order_weight * (100 - percent)
    divisor = math.gcd(empty, *(w for _, w in values)) or 1
    return tuple((i, w // divisor) for i, w in values), empty // divisor


def pool(mat):
    return _pool(tuple((int(i), int(w)) for i, w in mat['items']),
                 int(mat.get('no_produce') or 0), ORDER_PERCENT)


def roll(mat):
    items, empty = pool(mat)
    ticket = random.randint(1, max(1, sum(w for _, w in items) + empty))
    for item, weight in items:
        ticket -= weight
        if ticket <= 0:
            return item
    return None
