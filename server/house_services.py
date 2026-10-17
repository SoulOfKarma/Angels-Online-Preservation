"""House-specific client data. Read the latest IGG XML revision, never Global IDs."""
import functools
import pathlib
import re
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLEAN_SECONDS_PER_POINT = 180.0  # Online character time; configurable pending IGG capture.
TOKEN_SECONDS = 8 * 60 * 60
TOKEN_COOLDOWN = 180
MAID_TILE = (44, 82)
MAID_SPRITE = 40262  # npc.obd: NPC1062 / house maid, directory npc/n262.
# update3.pak contains ONLY w014/w016, w024/w026, w034/w036.
# Keep a supported diagonal; turn the visible direction 3 through 180 degrees
# to face the doorway/down-left, as confirmed by the user's screenshot.
MAID_DIRECTION = 7
MAID_PORTRAIT = 1062
MAILBOX_TILE = (32, 31)
# default.mpc UPDATE18: event 20..24 -> OPEN_MAKE(3,1,6,5,2).
PRODUCTION = {
    500020: (60060, (19, 29), 29, 3, 695),
    500021: (60078, (16, 27), 27, 1, 693),
    500022: (60058, (10, 24), 26, 6, 691),
    500023: (60068, (12, 19), 31, 5, 696),
    500024: (60067, (17, 16), 28, 2, 694),
}
PRODUCTION_MIRROR = {500023: False, 500024: False}
ORDER_CATEGORIES = {7854: '武器', 7855: '防具', 7856: '工藝',
                    7857: '裁縫', 7858: '烹飪'}
# Sprite, tile and material ID read from the same map records (+22 u16).
RESOURCES = {
    500025: (60195, (28, 16), 329),
    500026: (60222, (32, 17), 305),
    500027: (60174, (35, 19), 317),
    500028: (60161, (38, 21), 281),
    500029: (60176, (42, 22), 293),
}

@functools.lru_cache(maxsize=None)
def xml_rows(name):
    candidates = []
    for folder in (ROOT / 'extracted_paks').iterdir():
        low = folder.name.lower()
        match = re.fullmatch(r'update(\d*)', low)
        if low != 'data1' and not match:
            continue
        order = -1 if low == 'data1' else int(match.group(1) or 0)
        for localized in (False, True):
            path = folder / 'setting' / ('eng/' + name if localized else name)
            if path.is_file():
                candidates.append((order, localized, path))
    if not candidates:
        return {}
    path = max(candidates, key=lambda x: (x[0], x[1]))[2]
    return {int(e.get('編號')): dict(e.attrib)
            for e in ET.parse(path).getroot() if str(e.get('編號', '')).isdigit()}

@functools.lru_cache(maxsize=1)
def mercenaries():
    return sorted((dict(row, id=ident) for ident, row in xml_rows('monster.xml').items()
                   if row.get('名稱', '').lower().startswith('mercenary')
                   and row.get('名稱', '').lower() != 'mercenary brett'),
                  key=lambda row: (int(row.get('等級') or 1), -row['id']))

def mercenary_for(player_level):
    candidates = [r for r in mercenaries() if int(r.get('等級') or 1) <= player_level]
    return candidates[-1] if candidates else None

def summon_stats(row):
    def number(key, default=0):
        return int(row.get(key) or default)
    return {
        'nombre': row.get('名稱', 'Mercenary'), 'sprite': number('圖號'),
        'hp': number('HP', 1), 'atk': number('平均攻擊'),
        'def': number('防禦'), 'matk': number('魔攻'), 'mdef': number('魔防'),
        'level': number('等級', 1), 'accuracy': number('精準'),
        'agility': number('靈敏'), 'crit_rate': number('重擊機率'),
        'atk_range': number('攻擊範圍', 1), 'move_speed': number('移動速度', 70),
        'atk_speed': number('攻擊速度', 70),
        'skills': [number('攻擊法術%d' % n) for n in range(1, 5)
                   if number('攻擊法術%d' % n)],
    }

@functools.lru_cache(maxsize=1)
def monster_eggs():
    return {ident: row for i in range(1, 10)
            for ident, row in xml_rows('item%s.xml' % (i if i > 1 else '')).items()
            if row.get('物品類別') == '怪物蛋'}

def clean_bonus(cleanliness):
    # IGG sub_66A8B0: >100 -> +20%; 90..100 -> +10%; otherwise hidden.
    return 20 if cleanliness > 100 else 10 if cleanliness >= 90 else 0

def blessing_profile(house_level):
    tier = 4 if house_level >= 15 else 3 if house_level >= 12 else 2 if house_level >= 9 else 1
    row = xml_rows('magic.xml')[2291 + tier]
    # magic.xml durations are minutes. No EXP bonus exists on these spells.
    result = {'magic_id': 2291 + tier, 'tier': tier,
              'nombre': row['名稱'], 'duration_seconds': int(row['持續時間']) * 60}
    desc = row.get('說明', '')
    enhance = re.search(r'4th time.*?by (\d+)%', desc)
    pierce = re.search(r'first hole.*?by (\d+)%', desc)
    lucky = re.search(r'(\d+)% chance to add', desc)
    for key, match in [('enhance_fourth_pct', enhance), ('pierce_first_pct', pierce),
                       ('lucky_extra_pct', lucky)]:
        if match:
            result[key] = int(match.group(1))
    return result

def recipe(ident):
    return xml_rows('make.xml').get(int(ident))


def resource_for(entity_id, player_level):
    """The twelve client house tiers (L), capped at the last defined tier."""
    sprite, tile, first = RESOURCES[entity_id]
    rows = xml_rows('material.xml')
    tiers = [(mid, rows[mid]) for mid in range(first, first + 12)
             if mid in rows and int(rows[mid].get('等級限制') or 1) <= max(1, player_level)]
    mid, row = max(tiers, key=lambda pair: int(pair[1].get('等級限制') or 1))
    return dict(entity_id=entity_id, sprite=int(row.get('圖號') or sprite),
                tile=tile, px=(tile[0] * 32 + 16, tile[1] * 32 + 16),
                material=mid, nombre_visible=row['名稱'])


def producer_order_plan(option, inventory, quantities, last_slot):
    """One complete owned order, never items from equipment/bank/other bags."""
    from collections import Counter
    category = ORDER_CATEGORIES.get(option)
    if category is None:
        return None
    bag = {int(s): int(i) for s, i in inventory.items() if 20 <= int(s) <= last_slot}
    counts = Counter()
    for slot, item in bag.items():
        counts[item] += max(1, int(quantities.get(slot, 1)))
    for row in xml_rows('order.xml').values():
        receipt = int(row.get('訂單原型') or 0)
        if row.get('訂單類別') != category or not receipt or not counts[receipt]:
            continue
        required = Counter({receipt: 1})
        required[int(row['成品編號'])] += int(row['成品數量'])
        if any(counts[item] < qty for item, qty in required.items()):
            continue
        consume = []
        for item, qty in required.items():
            for slot, candidate in sorted(bag.items()):
                if candidate == item:
                    take = min(qty, max(1, int(quantities.get(slot, 1))))
                    consume.append((slot, take))
                    qty -= take
                    if qty == 0:
                        break
        return row, consume
    return None

