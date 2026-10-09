"""Build a local item wiki from corpus/content.db.

Same idea as the JzJad-style bestiary: search, filter by category, show IDs
for /item, and embed icons decoded from the client SHP files.
"""
from __future__ import annotations

import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from shp_icon import convert_all

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "corpus" / "content.db"
OUT = ROOT / "docs" / "items.html"
SHARE = ROOT / "share" / "items" / "Angels Online Items.html"
ICON_DIR = ROOT / "docs" / "icons"
SHARE_ICONS = ROOT / "share" / "items" / "icons"
DRESS_DIR = ROOT / "docs" / "dress"
SHARE_DRESS = ROOT / "share" / "items" / "dress"
EXTRACT = Path(r"C:\Program Files (x86)\Angels Online\extracted")

TABLES = ("item", "item2", "item3", "item4", "item5", "item6", "item7", "item8", "item9")
JUNK_NAME = re.compile(r"^(基本名稱|名稱|name|編號)$", re.I)
LV_NAME = re.compile(r"(?i)\blv\.?\s*(\d+)\b")
# Gem tooltips put the socket level in the description, not 物品等級.
# "Level 60", "Required Level: 20", "Level Requirement: Lvl 150",
# "Level Requirement：160", "裝備等限：100級".
GEM_LEVEL = re.compile(
    r"(?i)(?:"
    r"required\s+level\s*[:：]\s*(\d+)"
    r"|level\s+requirement\s*[:：]\s*(?:lvl\.?\s*)?(\d+)"
    r"|level\s+(\d+)"
    r"|lvl\.?\s*(\d+)"
    r"|等限\s*[:：]\s*(\d+)"
    r"|レベル\s*(\d+)"
    r")"
)
_GEM_SLOT = re.compile(r"(?i)(weapon|armor|shield|武器|防具|盾)\s*[:：]\s*([^\n]+)")
_GEM_BONUS = re.compile(r"([^,、+＋]+?)\s*[+＋]\s*(\d+)")
_GEM_SLOT_KEY = {"weapon": "w", "armor": "a", "shield": "s", "武器": "w", "防具": "a", "盾": "s"}
_RANK_TAIL = re.compile(r"(?i)\s+(?:I{1,3}|IV|V|[1-5])$")

# magic.技能限制1 -> the skill a scroll is learned under.
CHINO_SKILL = {
    "生命技能": "Life", "死靈技能": "Wraith", "混亂技能": "Chaos", "大地技能": "Earth",
    "吟咒技能": "Curse", "冥想技能": "Meditate", "魔導技能": "Hit", "法杖技能": "Staff Hit",
    "劍術技能": "Sword", "斧錘技能": "Axe", "槍術技能": "Spear", "強身技能": "Enhance",
    "格鬥技能": "Grapple", "盾防技能": "Shield", "蓄勁技能": "Reserve", "巧手技能": "Finesse",
    "弓箭技能": "Longbow", "狙擊技能": "Snipe", "鷹眼技能": "Eagle Eye", "影刃技能": "Mantle",
    "幻化技能": "Avatar", "奇襲技能": "Assault",
}
SKILL_FAMILIES = [
    ("Magic", ["Life", "Wraith", "Chaos", "Earth", "Curse", "Meditate", "Hit", "Staff Hit"]),
    ("Combat", ["Sword", "Axe", "Spear", "Enhance", "Grapple", "Shield", "Reserve",
                "Finesse", "Longbow", "Snipe", "Eagle Eye", "Mantle", "Avatar", "Assault"]),
]

CAT_EN = {
    "劍": "Sword", "刀": "Sabre", "斧": "Axe", "錘": "Hammer", "槍": "Spear",
    "杖": "Staff", "弓箭": "Bow", "彈弓": "Slingshot", "影刃": "Shadow Blade",
    "盾": "Shield", "衣服": "Body Armor", "頭飾": "Headgear", "手套": "Gloves",
    "鞋子": "Boots", "披風": "Cloak", "飾品": "Accessory", "背包": "Backpack",
    "寵物": "Pet", "座騎": "Mount", "寵物武器": "Pet Weapon", "寵物飾品": "Pet Accessory",
    "寵物防具": "Pet Armor", "寵物寶石": "Pet Gem", "寵物強化": "Pet Enhance",
    "寵物復活": "Pet Revive", "寵物裝備": "Pet Gear", "抓寵空蛋": "Empty Catch Egg",
    "怪物蛋": "Monster Egg", "一般": "General", "經驗卷": "EXP Scroll",
    "經驗球": "EXP Orb", "技能經驗球": "Skill EXP Orb", "寵物經驗球": "Pet EXP Orb",
    "卷軸": "Scroll", "配方": "Recipe", "卡片": "Card", "字卡": "Letter Card",
    "寶石": "Gem", "紙娃娃": "Fashion", "紅包": "Red Packet", "禮物": "Gift",
    "扭蛋": "Gacha Egg", "傢俱": "Furniture", "房屋": "House", "房屋外觀": "House Skin",
    "隱藏": "Hidden", "農場種子": "Farm Seed", "彈藥": "Ammo", "箭矢": "Arrow",
    "徽章": "Badge", "幸運骰": "Lucky Dice", "機甲": "Mecha", "機甲零件": "Mecha Part",
    "訂單": "Order", "強化道具": "Enhance Tool", "強化飼料": "Enhance Feed",
    "防禦塔": "Defense Tower", "計時道具": "Timed Item", "附魔": "Enchant",
    "表情卡": "Emote Card", "對話泡泡": "Chat Bubble", "打孔道具": "Socket Tool",
    "融合劑": "Fusion Agent", "DNA道具": "DNA Item", "地圖碎片": "Map Piece",
    "挖寶石道具": "Gem Dig Tool", "加速肥料": "Speed Fertilizer", "驅蟲劑": "Bug Spray",
    "鐵鍬": "Shovel", "釣竿": "Fishing Rod", "星盤金幣抽": "Astrolabe Draw",
    "星盤賓果": "Astrolabe Bingo", "儲值道具": "Cash Item", "小鋼珠": "Pachinko Ball",
    "魯易浮標": "Fishing Float", "金錢": "Gold", "更名道具": "Rename",
    "小遊戲道具": "Minigame", "特殊碎片": "Special Shard", "魔力骰": "Magic Dice",
    "階級裝備": "Rank Gear",
}

GROUP_OF = {
    "Sword": "Weapons", "Sabre": "Weapons", "Axe": "Weapons", "Hammer": "Weapons",
    "Spear": "Weapons", "Staff": "Weapons", "Bow": "Weapons", "Slingshot": "Weapons",
    "Shadow Blade": "Weapons", "Shield": "Weapons",
    "Body Armor": "Armor", "Headgear": "Armor", "Gloves": "Armor", "Boots": "Armor",
    "Cloak": "Armor", "Rank Gear": "Armor",
    "Mecha": "Mecha", "Mecha Part": "Mecha",
    "Accessory": "Accessories", "Backpack": "Accessories", "Badge": "Accessories",
    "Pet": "Pets", "Pet Weapon": "Pets", "Pet Accessory": "Pets", "Pet Armor": "Pets",
    "Pet Gem": "Pets", "Pet Enhance": "Pets", "Pet Revive": "Pets", "Pet Gear": "Pets",
    "Empty Catch Egg": "Pets", "Monster Egg": "Pets", "Pet EXP Orb": "Pets",
    "Enhance Feed": "Pets",
    "Mount": "Mounts",
    "General": "Consumables", "HP Potion": "Consumables", "MP Potion": "Consumables",
    "Potion": "Consumables", "Food": "Consumables", "Buff": "Consumables",
    "Advancement Stone": "Consumables", "Skill Leveling Stone": "Consumables",
    "EXP Stone": "Consumables", "EXP Scroll": "Consumables", "EXP Orb": "Consumables",
    "Skill EXP Orb": "Consumables", "Timed Item": "Consumables", "Gold": "Consumables",
    "Token": "Consumables", "Key": "Consumables", "Teleport": "Consumables",
    "Antidote": "Consumables", "Elixir": "Consumables",
    "Skill Scroll": "Scrolls & Recipes", "Magic Scroll": "Scrolls & Recipes",
    "Scroll": "Scrolls & Recipes", "Recipe": "Scrolls & Recipes", "Order": "Scrolls & Recipes",
    "Monster Card": "Cards", "EXP Card": "Cards", "Card": "Cards",
    "Letter Card": "Cards", "Emote Card": "Cards",
    "Gem": "Gems", "Enchant": "Gems", "Socket Tool": "Gems",
    "Fashion": "Fashion", "Fashion Head": "Fashion", "Fashion Body": "Fashion",
    "Fashion Feet": "Fashion", "Fashion Hands": "Fashion", "Fashion Wings": "Fashion",
    "Shapeshift": "Fashion", "Chat Bubble": "Fashion",
    "Red Packet": "Eggs & Gifts", "Gift": "Eggs & Gifts", "Gacha Egg": "Eggs & Gifts",
    "Suit Egg": "Eggs & Gifts", "Weapon Egg": "Eggs & Gifts", "Furniture Egg": "Eggs & Gifts",
    "Lucky Bag": "Eggs & Gifts",
    "Furniture": "Housing", "House": "Housing", "House Skin": "Housing",
    "Chair": "Housing", "Table": "Housing", "Wall": "Housing", "Floor": "Housing",
    "Farm Seed": "Farming", "Speed Fertilizer": "Farming", "Bug Spray": "Farming",
    "Ore": "Materials", "Cloth": "Materials", "Herb": "Materials", "Wood": "Materials",
    "Fish": "Materials", "Meat": "Materials", "Crystal": "Materials",
    "Hidden": "Materials", "Special Shard": "Materials",
    "Map Piece": "Materials", "Fusion Agent": "Materials", "DNA Item": "Materials",
    "Ammo": "Tools", "Arrow": "Tools", "Enhance Tool": "Tools",
    "Defense Tower": "Tools",
    "Lucky Dice": "Tools", "Magic Dice": "Tools", "Shovel": "Tools",
    "Fishing Rod": "Tools", "Fishing Float": "Tools", "Gem Dig Tool": "Tools",
    "Rename": "Tools",
    "Cash Item": "Tools", "Pachinko Ball": "Tools", "Astrolabe Draw": "Tools",
    "Astrolabe Bingo": "Tools", "Minigame": "Tools",
}

GROUP_ORDER = [
    "Weapons", "Armor", "Mecha", "Accessories", "Pets", "Mounts", "Consumables",
    "Scrolls & Recipes", "Cards", "Gems", "Fashion", "Eggs & Gifts",
    "Housing", "Farming", "Materials", "Tools", "Other",
]


NAME_KIND = [
    (r"advancement\s+stone", "Advancement Stone"),
    (r"skill\s+leveling\s+stone", "Skill Leveling Stone"),
    (r"(double|triple|2x|3x).{0,16}skill.{0,8}exp", "Skill EXP Orb"),
    (r"(double|triple|2x|3x).{0,16}exp\s+stone", "EXP Stone"),
    (r"\bexp\s+stone\b", "EXP Stone"),
    (r"skill\s+scroll|book of ", "Skill Scroll"),
    (r"magic\s+scroll", "Magic Scroll"),
    (r"furniture\s+egg", "Furniture Egg"),
    (r"suit\s+egg|costume\s+egg", "Suit Egg"),
    (r"weapon\s+egg", "Weapon Egg"),
    (r"lucky\s+bag|lucky\s+pack", "Lucky Bag"),
    (r"exp\s+card", "EXP Card"),
    (r"monster\s+card|collect(?:ion|able)\s+card", "Monster Card"),
    (r"\bteleport\b|superwing|town scroll|return scroll", "Teleport"),
    (r"\bkey\b|钥匙", "Key"),
    (r"coupon|ticket|token|voucher", "Token"),
]


def refine_kind(name: str, kind: str, desc: str = "") -> str:
    """Every group gets subtypes. Catch-alls (General, Fashion, Hidden, Gift) split by name."""
    n = f"{name} {desc}".lower()
    for pat, new_kind in NAME_KIND:
        if re.search(pat, n):
            return new_kind
    if kind in ("General", "Timed Item"):
        if any(w in n for w in ("antidote", "cure poison", "detox")):
            return "Antidote"
        if "elixir" in n:
            return "Elixir"
        if any(w in n for w in ("red potion", "hp potion", "health potion", "restore", "recover hp", "increase hp")):
            return "HP Potion"
        if any(w in n for w in ("blue potion", "mp potion", "mana potion", "recover mp", "increase mp")):
            return "MP Potion"
        if "potion" in n:
            if any(w in n for w in ("attack", "defence", "defense", "accuracy", "agility", "speed", "crit")):
                return "Buff"
            return "Potion"
        if any(w in n for w in ("biscuit", "cookie", "bread", "food", "meal", "cake", "candy",
                                 "fruit", "meat", "fish", "soup", "rice", "noodle", "drink",
                                 "juice", "tea", "wine", "milk", "honey")):
            return "Food"
        if any(w in n for w in ("buff", "lasts ", "minutes", "increase the")) and "potion" not in n:
            if any(w in n for w in ("attack", "defence", "defense", "exp", "drop")):
                return "Buff"
        if "box" in n or "chest" in n or "pack" in n:
            return "Gift"
        return "General" if kind == "Timed Item" else kind
    if kind == "Fashion":
        if any(w in n for w in ("shapeshift", "transform", "morph")):
            return "Shapeshift"
        if any(w in n for w in ("wing", "halo")):
            return "Fashion Wings"
        if any(w in n for w in ("hat", "helm", "circlet", "tiara", "horn", "crown", "ear", "hair")):
            return "Fashion Head"
        if any(w in n for w in ("dress", "coat", "robe", "suit", "shirt", "armor", "cloth")):
            return "Fashion Body"
        if any(w in n for w in ("shoe", "boot", "sandal")):
            return "Fashion Feet"
        if any(w in n for w in ("glove", "sleeve", "gauntlet", "hand")):
            return "Fashion Hands"
        return kind
    if kind in ("Hidden", "Gift"):
        if any(w in n for w in ("ore", "iron", "copper", "silver", "gold", "ingot")):
            return "Ore"
        if any(w in n for w in ("cloth", "silk", "thread", "cotton", "wool")):
            return "Cloth"
        if any(w in n for w in ("herb", "flower", "leaf", "petal", "grass")):
            return "Herb"
        if any(w in n for w in ("wood", "log", "plank", "branch")):
            return "Wood"
        if any(w in n for w in ("fish", "shrimp", "crab")):
            return "Fish"
        if any(w in n for w in ("meat", "steak", "pork", "beef")):
            return "Meat"
        if any(w in n for w in ("crystal", "gem", "pearl", "dust", "essence")):
            return "Crystal"
    if kind == "Furniture":
        if any(w in n for w in ("chair", "sofa", "stool", "bench")):
            return "Chair"
        if any(w in n for w in ("table", "desk")):
            return "Table"
        if any(w in n for w in ("wall", "wallpaper", "window", "door")):
            return "Wall"
        if any(w in n for w in ("floor", "carpet", "rug", "tile")):
            return "Floor"
    if kind == "Mount" and any(w in n for w in ("wing", "fly", "griffin", "gryphon")):
        return "Mount"
    return kind

QUALITY = {"白": "White", "藍": "Blue", "黃": "Yellow", "金": "Gold",
           "綠": "Green", "紫": "Purple", "紅": "Red", "橙": "Orange"}


def as_int(raw) -> int:
    try:
        return int(float(raw or 0))
    except (TypeError, ValueError):
        return 0


def clean(raw) -> str:
    text = re.sub(r"\s+", " ", str(raw or "")).strip()
    if text in ("說明", "說明定義", "None"):
        return ""
    return text


def compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def load_icon_files() -> dict[int, str]:
    mapping: dict[int, str] = {}
    if not EXTRACT.exists():
        return mapping
    xmls = sorted(EXTRACT.rglob("itemicon*.xml"))
    for path in xmls:
        try:
            txt = path.read_text(encoding="utf-8", errors="replace")
            root = ET.fromstring(txt)
        except ET.ParseError:
            continue
        for el in root.iter("icon"):
            iid = as_int(el.attrib.get("id"))
            normal = (el.attrib.get("normal") or "").strip()
            if iid and normal and normal != "normal":
                mapping[iid] = normal
    return mapping


def gem_level_from_text(text: str) -> int:
    found = 0
    for match in GEM_LEVEL.finditer(text or ""):
        for group in match.groups():
            if group:
                found = int(group)
    return found


def gem_stat_signature(text: str) -> tuple:
    """Socket bonuses as (slot, ((stat, value), ...)), so two gems can be compared."""
    parts = []
    for slot_raw, body in _GEM_SLOT.findall(text or ""):
        slot = _GEM_SLOT_KEY.get(slot_raw.lower(), _GEM_SLOT_KEY.get(slot_raw))
        if not slot:
            continue
        bonuses = []
        for stat, value in _GEM_BONUS.findall(body):
            name = re.sub(r"\s+", "", stat).lower().replace("thunderbolt", "thunder")
            if name:
                bonuses.append((name, int(value)))
        if bonuses:
            parts.append((slot, tuple(sorted(bonuses))))
    return tuple(sorted(parts))


def infer_gem_level(signature: tuple, known: list[tuple[tuple, int]]) -> int:
    """Copy a stated level when the bonuses match, or the tier under level 20 when they are the same stats but weaker."""
    if not signature:
        return 0
    exact = {level for other, level in known if other == signature}
    if len(exact) == 1:
        return exact.pop()
    if len(exact) > 1:
        return 0

    def shape(sig: tuple) -> tuple:
        return tuple((slot, tuple(stat for stat, _value in bonuses)) for slot, bonuses in sig)

    def values(sig: tuple) -> tuple:
        return tuple(value for _slot, bonuses in sig for _stat, value in bonuses)

    mine_shape = shape(signature)
    siblings = [(other, level) for other, level in known if shape(other) == mine_shape]
    if not siblings:
        return 0
    lowest = min(level for _other, level in siblings)
    floors = [other for other, level in siblings if level == lowest]
    mine = values(signature)
    for other in floors:
        theirs = values(other)
        if len(theirs) != len(mine):
            return 0
        if not all(left <= right for left, right in zip(mine, theirs)):
            return 0
        if not any(left < right for left, right in zip(mine, theirs)):
            return 0
    # Stated gem levels start at 20. The same-shaped gem underneath that is the starter tier.
    return 1 if lowest == 20 else 0


def spell_line(name: str) -> str:
    text = clean(name)
    stripped = _RANK_TAIL.sub("", text).strip()
    return stripped or text


def load_magic_index(con: sqlite3.Connection) -> tuple[dict[int, int], dict[int, tuple[str, str]]]:
    """Spell id -> rank, and spell id -> (skill name, spell line)."""
    ranks: dict[int, int] = {}
    skills: dict[int, tuple[str, str]] = {}
    try:
        rows = list(con.execute(
            'select id, name, "法術等級", "技能限制1", "群組編號" from magic'
        ))
    except sqlite3.Error:
        return ranks, skills
    grp_skill: dict[str, str] = {}
    for _mid, _name, _rank, sk, grupo in rows:
        if sk and grupo:
            grp_skill.setdefault(str(grupo), str(sk).strip())
    for mid, name, rank, sk, grupo in rows:
        iid = as_int(mid)
        if not iid:
            continue
        lvl = as_int(rank)
        if lvl:
            ranks[iid] = lvl
        branch = str(sk).strip() if sk else ""
        if not branch and grupo:
            branch = grp_skill.get(str(grupo), "")
        tree = CHINO_SKILL.get(branch, "")
        if tree:
            skills[iid] = (tree, spell_line(str(name or "")))
    return ranks, skills


def load_items() -> list[dict]:
    if not DB.exists():
        raise SystemExit(f"missing {DB}")
    con = sqlite3.connect(DB)
    magic_ranks, magic_skills = load_magic_index(con)
    merged: dict[int, dict] = {}
    for table in TABLES:
        cols = {c[1] for c in con.execute(f"pragma table_info({table})")}
        want = ["id", "基本名稱", "物品類別", "原型名稱", "原型介面",
                "物品等級", "等級限制", "技能等限", "動態資料1",
                "price", "weight", "說明定義", "顏色", "_pak"]
        have = [c for c in want if c in cols]
        if "id" not in have or "基本名稱" not in have:
            continue
        q = "select " + ",".join(f'"{c}"' for c in have) + f" from {table}"
        for row in con.execute(q):
            rec = dict(zip(have, row))
            iid = as_int(rec.get("id"))
            name = clean(rec.get("基本名稱"))
            if not iid or not name or JUNK_NAME.match(name):
                continue
            zh = clean(rec.get("物品類別"))
            prefix = clean(rec.get("原型名稱"))
            display = f"{prefix} {name}".strip() if prefix and prefix.lower() not in name.lower() else name
            desc = clean(rec.get("說明定義"))[:180]
            kind = refine_kind(display, CAT_EN.get(zh, zh or "Unknown"), desc)
            group = GROUP_OF.get(kind, "Other")
            row = {
                "id": iid,
                "name": display,
                "kind": kind,
                "group": group,
                "icon": as_int(rec.get("原型介面")),
            }
            level = as_int(rec.get("物品等級") or rec.get("等級限制"))
            if level < 1:
                level = 0
            if not level:
                named = LV_NAME.search(display)
                if named:
                    level = int(named.group(1))
            if zh == "寶石":
                gem_text = str(rec.get("說明定義") or "")
                if not level:
                    level = gem_level_from_text(gem_text)
                row["_gemtext"] = gem_text
            skill_req = as_int(rec.get("技能等限"))
            rank = 0
            tree_line = None
            if zh == "卷軸":
                mid = as_int(rec.get("動態資料1"))
                rank = magic_ranks.get(mid, 0)
                tree_line = magic_skills.get(mid)
            price = as_int(rec.get("price"))
            quality = QUALITY.get(clean(rec.get("顏色")), "")
            if prefix:
                row["prefix"] = prefix
            if name != display:
                row["raw"] = name
            if level:
                row["level"] = level
            # Skill books can require a skill level that is not the item level
            # (Deadly Combo I is item 100, skill 80). Keep both so the filter
            # can follow the skill line, not only the character requirement.
            if skill_req and skill_req != level:
                row["skill"] = skill_req
            if tree_line:
                row["tree"] = tree_line[0]
                if tree_line[1]:
                    row["line"] = tree_line[1]
            if rank:
                row["rank"] = rank
            if price:
                row["price"] = price
            if desc:
                row["desc"] = desc
            if quality:
                row["quality"] = quality
            merged[iid] = row
    con.close()
    known: list[tuple[tuple, int]] = []
    pending: list[tuple[dict, str]] = []
    for row in merged.values():
        gem_text = row.pop("_gemtext", None)
        if gem_text is None:
            continue
        if row.get("level"):
            signature = gem_stat_signature(gem_text)
            if signature:
                known.append((signature, row["level"]))
        else:
            pending.append((row, gem_text))
    for row, gem_text in pending:
        level = infer_gem_level(gem_stat_signature(gem_text), known)
        if level:
            row["level"] = level
    return [merged[k] for k in sorted(merged)]


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Angels Online Item Wiki</title>
  <style>
    :root { color-scheme: dark; --bg:#0d1117; --panel:#151b23; --text:#e8eef7;
            --muted:#99a8bc; --line:#2b3848; --accent:#78b7ff; --good:#80d88a; --warn:#ffd166; }
    * { box-sizing: border-box; }
    body { margin:0; font-family: system-ui, Segoe UI, sans-serif; background:var(--bg); color:var(--text); }
    header, main { max-width: 1480px; margin: 0 auto; padding: 22px; }
    h1 { margin: 0 0 8px; }
    .subtitle { color:var(--muted); max-width: 980px; line-height:1.5; }
    .stats { display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; }
    .stat { border:1px solid var(--line); border-radius:999px; padding:8px 12px; color:var(--muted); }
    .stat strong { color:var(--text); }
    .controls { display:grid; grid-template-columns: minmax(220px,2fr) minmax(140px,1fr) minmax(160px,1fr) minmax(150px,.8fr) auto auto;
                gap:12px; margin:16px 0; padding:14px; border:1px solid var(--line); background:var(--panel); border-radius:18px; align-items:end; }
    .range { display:grid; grid-template-columns:1fr 1fr; gap:6px; }
    .tabs { display:flex; gap:8px; margin-top:16px; }
    .tabs button { background:transparent; color:var(--text); }
    .tabs button[aria-pressed="true"] { background:var(--accent); color:#082033; }
    .linehead td { background:#101722; color:var(--accent); font-weight:750; letter-spacing:0; text-transform:none; cursor:default; }
    body[data-tab="items"] .skills-only { display:none; }
    body[data-tab="skills"] .items-only { display:none; }
    body[data-tab="skills"] .controls { grid-template-columns: minmax(220px,2fr) minmax(180px,1fr) minmax(150px,.8fr) auto auto; }
    .field { display:flex; flex-direction:column; gap:6px; color:var(--muted); font-size:.78rem; letter-spacing:.04em; text-transform:uppercase; }
    .stat { cursor:pointer; }
    .stat.on { border-color:var(--accent); color:var(--accent); }
    input, select, button { width:100%; min-height:44px; border:1px solid var(--line); border-radius:12px;
                            padding:11px 12px; background:#101722; color:var(--text); font:inherit; }
    button { width:auto; cursor:pointer; background:var(--accent); color:#082033; font-weight:700; }
    button.ghost { background:transparent; color:var(--text); }
    .pager { display:flex; gap:10px; align-items:center; margin:10px 0; color:var(--muted); }
    .tableWrap { overflow:auto; border:1px solid var(--line); border-radius:18px; background:var(--panel); }
    table { width:100%; min-width:1100px; border-collapse:collapse; }
    th, td { padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
    th { color:var(--muted); font-size:.78rem; letter-spacing:.04em; text-transform:uppercase; cursor:pointer; }
    tbody tr:hover { background:rgba(120,183,255,.08); }
    .item { display:grid; grid-template-columns:48px 1fr; gap:10px; align-items:center; }
    .portrait { width:48px; height:48px; border-radius:12px; border:1px solid var(--line);
                display:grid; place-items:center; font-weight:800; font-size:.8rem;
                overflow:hidden; background:#101722; color:var(--accent); }
    .portrait img { width:100%; height:100%; object-fit:contain; image-rendering:pixelated; }
    .name { color:var(--accent); font-weight:750; }
    .muted { color:var(--muted); font-size:.88rem; }
    .badge { display:inline-flex; border:1px solid var(--line); border-radius:999px; padding:3px 8px; color:var(--muted); font-size:.78rem; margin:0 4px 4px 0; }
    .badge.good { color:var(--good); }
    .badge.warn { color:var(--warn); border-color:rgba(255,209,102,.45); }
    .idbtn { font:inherit; min-height:0; padding:4px 8px; border-radius:8px; background:#101722; color:var(--accent); }
    .empty { padding:28px; text-align:center; color:var(--muted); }
    .stage { display:grid; grid-template-columns:1fr 400px; gap:16px; align-items:start; }
    .tryon { position:sticky; top:16px; border:1px solid var(--line); border-radius:16px; padding:14px; background:#101722; }
    .tryon h2 { margin:0 0 6px; font-size:1rem; }
    .pd-stage { overflow:hidden; border:1px solid var(--line); border-radius:12px; background:#1a1d24; cursor:grab; }
    .tryon canvas {
      width:100%; height:420px; display:block; image-rendering:pixelated;
    }
    .pd-rotate { display:grid; grid-template-columns:48px 1fr 48px; gap:8px; align-items:center; margin-top:10px; }
    .pd-rotate span { text-align:center; color:var(--accent); font-size:.84rem; font-weight:750; }
    .pd-slots { display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:12px; }
    .slotBtn { min-height:52px; display:grid; grid-template-columns:36px 1fr; gap:6px; align-items:center; padding:6px; text-align:left; background:#0d121b; }
    .slotBtn:disabled { opacity:.7; cursor:default; }
    .slotBtn img, .slotPh { width:36px; height:36px; display:grid; place-items:center; border:1px solid var(--line); border-radius:8px; background:#101722; object-fit:contain; image-rendering:pixelated; }
    .slotName { display:block; color:var(--muted); font-size:.68rem; font-weight:750; text-transform:uppercase; }
    .slotItem { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:.76rem; font-weight:700; }
    .pd-controls { display:grid; gap:10px; margin-top:12px; padding-top:12px; border-top:1px solid var(--line); }
    .seg { display:grid; grid-template-columns:1fr 1fr; gap:6px; }
    .seg.three { grid-template-columns:1fr 1fr 1fr; }
    .seg button[aria-pressed="true"] { border-color:var(--accent); color:var(--accent); }
    .swatches { max-height:88px; overflow:auto; display:grid; grid-template-columns:repeat(auto-fill,minmax(28px,1fr)); gap:4px; }
    .swatch { min-height:28px; padding:0; border:2px solid var(--line); background:var(--swatch,#888); }
    .swatch[aria-pressed="true"] { border-color:var(--accent); box-shadow:0 0 0 2px rgba(120,183,255,.35); }
    .tryon .muted { margin-top:8px; }
    .tryon .rowbtns { display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; }
    .tryon a { color:var(--accent); }
    @media (max-width:1100px) { .stage { grid-template-columns:1fr 340px; } .tryon canvas { height:380px; } }
    @media (max-width:900px) { .stage { grid-template-columns:1fr; } .tryon { position:static; } }
    @media (max-width:800px) { .controls { grid-template-columns:1fr; } }
  </style>
</head>
<body data-tab="items">
  <header>
    <h1>Item Wiki</h1>
    <p class="subtitle">
      Local catalog from your extracted client (UPDATE25 / <code>content.db</code>),
      grouped like the old Angels Online wikis. Search a name or paste an ID.
      Use <strong>/item &lt;id&gt;</strong> on the Preservation server to summon it.
      The level filter covers gear requirements and skill progression: a scroll
      matches on its item level or, when they differ, the skill level it needs.
      Roman numerals are the spell rank (I–V).
      The Skills tab files every skill scroll under its skill, grouped by spell and rank.
      Icons are the client <code>shape/item/*.SHP</code> sprites. Click a row
      to try fashion, weapons, and mounts on a front-facing dummy.
    </p>
    <div class="tabs" id="tabs">
      <button type="button" data-tab="items" aria-pressed="true">Items</button>
      <button type="button" data-tab="skills">Skills</button>
    </div>
    <div class="stats" id="stats"></div>
  </header>
  <main>
    <div class="controls">
      <label class="field">Search
        <input id="search" type="search" placeholder="Name, ID, type...  e.g. potion, 19826, sabre">
      </label>
      <label class="field items-only">Group
        <select id="groupFilter"><option value="">All groups</option></select>
      </label>
      <label class="field items-only">Type in this group
        <select id="kindFilter"><option value="">All types</option></select>
      </label>
      <label class="field skills-only">Skill
        <select id="skillFilter"><option value="">All skills</option></select>
      </label>
      <label class="field">Level
        <span class="range">
          <input id="levelMin" type="number" min="0" placeholder="Min" inputmode="numeric" title="Minimum item or skill level">
          <input id="levelMax" type="number" min="0" placeholder="Max" inputmode="numeric" title="Maximum item or skill level">
        </span>
      </label>
      <button id="reset" type="button">Reset</button>
      <button id="copy" class="ghost" type="button">Copy visible IDs</button>
    </div>
    <div class="pager">
      <button id="prev" type="button">Prev</button>
      <span id="resultMeta"></span>
      <button id="next" type="button">Next</button>
    </div>
    <div class="stage">
    <div class="tableWrap">
      <table>
        <thead>
          <tr>
            <th data-k="name">Item</th>
            <th data-k="id">ID</th>
            <th data-k="level">Level</th>
            <th data-k="kind">Type</th>
            <th data-k="tree">Skill</th>
            <th data-k="group">Group</th>
            <th data-k="price">Price</th>
            <th data-k="quality">Quality</th>
            <th>Summon</th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
    <aside class="tryon">
      <h2>Paper doll</h2>
      <p class="muted" style="margin:0 0 8px">Same Wait.spr atlases, foot anchors, and hair/skin tint as angelsonline.wiki. Eternal wiki only ships the 36px bag icons already in the table.</p>
      <div class="pd-stage">
        <canvas id="doll" width="400" height="420"></canvas>
      </div>
      <div class="pd-rotate">
        <button type="button" id="dollLeft" aria-label="Rotate left">◀</button>
        <span id="dollDir">Front</span>
        <button type="button" id="dollRight" aria-label="Rotate right">▶</button>
      </div>
      <div class="pd-slots" id="dollSlots"></div>
      <div class="pd-controls">
        <div class="seg" id="dollSex">
          <button type="button" data-sex="female" aria-pressed="true">Female</button>
          <button type="button" data-sex="male">Male</button>
        </div>
        <label class="field">Hairstyle
          <select id="dollHair"></select>
        </label>
        <div class="swatches" id="dollHairColors" title="Hair color"></div>
        <div class="swatches" id="dollSkins" title="Skin tone"></div>
        <div class="seg three" id="dollHeight">
          <button type="button" data-h="short">Short</button>
          <button type="button" data-h="average" aria-pressed="true">Average</button>
          <button type="button" data-h="tall">Tall</button>
        </div>
      </div>
      <div class="muted" id="dollMeta">Loading paper-doll sprites…</div>
      <div class="rowbtns">
        <button type="button" id="dollReset">Reset dummy</button>
        <button type="button" id="dollExample">Wiki example</button>
      </div>
      <div class="muted"><a id="dollWiki" href="https://angelsonline.wiki/pd-preview/" target="_blank" rel="noreferrer">Open this loadout on angelsonline.wiki</a></div>
    </aside>
    </div>
  </main>
  <script>
    const FILES = __FILES__;
    const DATA = __DATA__;
    const GROUP_ORDER = __GROUPS__;
    const SKILL_FAMILIES = __SKILLS__;
    const skillNames = SKILL_FAMILIES.flatMap(f => f[1]);
    const PAGE = 60;
    const searchEl = document.querySelector("#search");
    const groupEl = document.querySelector("#groupFilter");
    const kindEl = document.querySelector("#kindFilter");
    const skillEl = document.querySelector("#skillFilter");
    const levelMinEl = document.querySelector("#levelMin");
    const levelMaxEl = document.querySelector("#levelMax");
    const rowsEl = document.querySelector("#rows");
    const ROMAN = ["", "I", "II", "III", "IV", "V"];
    let page = 1, sortKey = "id", sortDir = "asc", tab = "items";

    const counts = {};
    DATA.forEach(i => { counts[i.group] = (counts[i.group]||0)+1; });
    const groups = GROUP_ORDER.filter(g => counts[g]);
    groups.forEach(g => groupEl.insertAdjacentHTML("beforeend", `<option>${g}</option>`));

    function fillKinds() {
      const g = groupEl.value;
      const prev = kindEl.value;
      const kinds = [...new Set(DATA.filter(i => !g || i.group === g).map(i => i.kind))].sort();
      kindEl.innerHTML = `<option value="">${g ? "All " + g + " types" : "All types"}</option>` +
        kinds.map(k => `<option>${k}</option>`).join("");
      kindEl.value = kinds.includes(prev) ? prev : "";
    }
    function fillSkills() {
      const have = new Set(DATA.filter(i => i.tree).map(i => i.tree));
      const prev = skillEl.value;
      skillEl.innerHTML = `<option value="">All skills</option>` +
        SKILL_FAMILIES.map(([fam, names]) => {
          const opts = names.filter(n => have.has(n)).map(n => `<option>${n}</option>`).join("");
          return opts ? `<optgroup label="${fam}">${opts}</optgroup>` : "";
        }).join("");
      skillEl.value = have.has(prev) || prev === "" ? prev : "";
    }
    function paintStats() {
      if (tab === "skills") {
        const sc = {};
        DATA.forEach(i => { if (i.tree) sc[i.tree] = (sc[i.tree]||0)+1; });
        const total = skillNames.reduce((n, s) => n + (sc[s]||0), 0);
        document.querySelector("#stats").innerHTML =
          `<span class="stat" data-g=""><strong>${total}</strong> scrolls</span>` +
          skillNames.filter(s => sc[s]).map(s => `<span class="stat${skillEl.value===s?" on":""}" data-g="${s}"><strong>${sc[s]}</strong> ${s}</span>`).join("");
        return;
      }
      document.querySelector("#stats").innerHTML =
        `<span class="stat" data-g=""><strong>${DATA.length}</strong> items</span>` +
        groups.map(g => `<span class="stat${groupEl.value===g?" on":""}" data-g="${g}"><strong>${counts[g]}</strong> ${g}</span>`).join("");
    }
    function setTab(next) {
      tab = next === "skills" ? "skills" : "items";
      document.body.dataset.tab = tab;
      document.querySelectorAll("#tabs button").forEach(b => {
        b.setAttribute("aria-pressed", b.dataset.tab === tab ? "true" : "false");
      });
      if (tab === "skills") { sortKey = "line"; sortDir = "asc"; }
      else if (sortKey === "line") { sortKey = "id"; sortDir = "asc"; }
      page = 1;
      paintStats();
      render();
    }
    function openSkill(name) {
      skillEl.value = name;
      setTab("skills");
    }
    window.openSkill = openSkill;

    function hay(i) {
      return (i.hay || (i.name+" "+(i.raw||"")+" "+i.kind+" "+i.group+" "+(i.tree||"")+" "+(i.line||"")+" "+i.id)).toLowerCase().replace(/[^a-z0-9]+/g,"");
    }
    function bound(el) {
      const t = el.value.trim();
      if (t === "") return null;
      const n = Number(t);
      return Number.isFinite(n) ? n : null;
    }
    function levelHits(i, lo, hi) {
      const vals = [i.level, i.skill].filter(n => typeof n === "number" && n > 0);
      if (!vals.length) return false;
      return vals.some(n => (lo === null || n >= lo) && (hi === null || n <= hi));
    }
    function levelLabel(i) {
      const parts = [];
      if (i.level) parts.push(String(i.level));
      if (i.skill) parts.push("skill " + i.skill);
      if (i.rank && ROMAN[i.rank]) parts.push(ROMAN[i.rank]);
      return parts.join(" · ") || "-";
    }
    function filtered() {
      const q = searchEl.value.trim().toLowerCase();
      const cq = q.replace(/[^a-z0-9]+/g,"");
      const lo = bound(levelMinEl);
      const hi = bound(levelMaxEl);
      return DATA.filter(i => {
        if (tab === "skills") {
          if (!i.tree) return false;
          if (skillEl.value && i.tree !== skillEl.value) return false;
        } else {
          if (groupEl.value && i.group !== groupEl.value) return false;
          if (kindEl.value && i.kind !== kindEl.value) return false;
        }
        if ((lo !== null || hi !== null) && !levelHits(i, lo, hi)) return false;
        if (!q) return true;
        if (String(i.id) === q || String(i.icon) === q) return true;
        return hay(i).includes(cq) || i.name.toLowerCase().includes(q) || (i.desc||"").toLowerCase().includes(q);
      });
    }
    function iconHtml(i, initials) {
      const file = (FILES[String(i.icon)] || "").toLowerCase();
      if (!file) return initials;
      return `<img src="icons/${file}.png" alt="" data-fb="${initials}" onerror="iconFail(this)">`;
    }
    function iconFail(img) {
      let next = [];
      try { next = JSON.parse(img.dataset.next || "[]"); } catch (e) {}
      if (next.length) {
        img.dataset.next = JSON.stringify(next.slice(1));
        img.src = next[0];
        return;
      }
      img.replaceWith(Object.assign(document.createElement("span"), {textContent: img.dataset.fb || "?"}));
    }
    window.iconFail = iconFail;
    function copyId(id) {
      const text = "item " + id;
      navigator.clipboard.writeText(text).catch(() => {});
    }
    window.copyId = copyId;
    function skillOrder(a, b) {
      return (a.tree||"").localeCompare(b.tree||"")
        || (a.line||"").localeCompare(b.line||"")
        || (a.rank||0) - (b.rank||0)
        || (a.level||0) - (b.level||0)
        || a.id - b.id;
    }
    function render() {
      const list = filtered().sort((a,b) => {
        if (tab === "skills" && sortKey === "line") return skillOrder(a, b) * (sortDir==="asc"?1:-1);
        const num = sortKey === "level" || sortKey === "price" || sortKey === "id" || sortKey === "rank";
        const av = num ? (a[sortKey] || (sortKey === "level" ? a.skill : 0) || 0) : (a[sortKey] ?? "");
        const bv = num ? (b[sortKey] || (sortKey === "level" ? b.skill : 0) || 0) : (b[sortKey] ?? "");
        if (typeof av === "number" || typeof bv === "number") return (av-bv) * (sortDir==="asc"?1:-1);
        return String(av).localeCompare(String(bv)) * (sortDir==="asc"?1:-1);
      });
      const pages = Math.max(1, Math.ceil(list.length / PAGE));
      if (page > pages) page = pages;
      const slice = list.slice((page-1)*PAGE, page*PAGE);
      const noun = tab === "skills" ? "scrolls" : "items";
      document.querySelector("#resultMeta").textContent = `${list.length} ${noun} · page ${page}/${pages}`;
      let prevHead = "";
      const html = [];
      slice.forEach(i => {
        if (tab === "skills" && sortKey === "line") {
          const head = skillEl.value ? (i.line || i.tree) : `${i.tree} · ${i.line || "Other"}`;
          if (head !== prevHead) {
            html.push(`<tr class="linehead"><td colspan="9">${head}</td></tr>`);
            prevHead = head;
          }
        }
        const initials = i.name.split(/\s+/).slice(0,2).map(w => (w[0]||"").toUpperCase()).join("");
        const extra = [
          i.prefix ? `<div class="muted">${i.prefix}</div>` : "",
          i.desc ? `<div class="muted">${i.desc}</div>` : "",
          i.raw && i.raw !== i.name ? `<div class="muted">xml: ${i.raw}</div>` : "",
        ].join("");
        const skillCell = i.tree
          ? `<button class="idbtn" type="button" onclick="event.stopPropagation();openSkill('${i.tree}')">${i.tree}</button>`
          : "-";
        html.push(`<tr onclick="tryOn(DATA.find(x=>x.id===${i.id}))">
          <td><div class="item">
            <div class="portrait">${iconHtml(i, initials)}</div>
            <div><div class="name">${i.name}</div>${extra}</div>
          </div></td>
          <td>${i.id}</td>
          <td>${levelLabel(i)}</td>
          <td>${i.kind}</td>
          <td>${skillCell}</td>
          <td><span class="badge good">${i.group}</span></td>
          <td>${i.price || "-"}</td>
          <td>${i.quality ? `<span class="badge warn">${i.quality}</span>` : "-"}</td>
          <td><button class="idbtn" type="button" onclick="event.stopPropagation();copyId(${i.id})">item ${i.id}</button></td>
        </tr>`);
      });
      rowsEl.innerHTML = html.join("") || `<tr><td colspan="9" class="empty">No ${noun} match the current filters.</td></tr>`;
    }
    document.querySelectorAll("th[data-k]").forEach(th => th.addEventListener("click", () => {
      sortKey = th.dataset.k; sortDir = sortDir === "asc" ? "desc" : "asc"; page = 1; render();
    }));
    searchEl.addEventListener("input", () => { page = 1; render(); });
    groupEl.addEventListener("change", () => { fillKinds(); paintStats(); page = 1; render(); });
    kindEl.addEventListener("change", () => { page = 1; render(); });
    skillEl.addEventListener("change", () => { paintStats(); page = 1; render(); });
    levelMinEl.addEventListener("input", () => { page = 1; render(); });
    levelMaxEl.addEventListener("input", () => { page = 1; render(); });
    document.querySelector("#tabs").addEventListener("click", ev => {
      const btn = ev.target.closest("[data-tab]");
      if (!btn || btn.dataset.tab === tab) return;
      setTab(btn.dataset.tab);
    });
    document.querySelector("#stats").addEventListener("click", ev => {
      const chip = ev.target.closest("[data-g]");
      if (!chip) return;
      if (tab === "skills") skillEl.value = chip.dataset.g || "";
      else { groupEl.value = chip.dataset.g || ""; fillKinds(); }
      paintStats(); page = 1; render();
    });
    document.querySelector("#reset").addEventListener("click", () => {
      searchEl.value = ""; groupEl.value = ""; skillEl.value = "";
      levelMinEl.value = ""; levelMaxEl.value = "";
      if (tab === "skills") { sortKey = "line"; sortDir = "asc"; }
      fillKinds(); paintStats(); page = 1; render();
    });
    document.querySelector("#copy").addEventListener("click", () => {
      const ids = filtered().map(i => i.id).join("\n");
      navigator.clipboard.writeText(ids).catch(() => {});
    });
    document.querySelector("#prev").addEventListener("click", () => { if (page > 1) { page--; render(); } });
    document.querySelector("#next").addEventListener("click", () => { page++; render(); });
    const params = new URLSearchParams(location.hash.slice(1));
    if (params.get("q")) searchEl.value = params.get("q");
    if (params.get("g")) groupEl.value = params.get("g");
    if (params.get("min")) levelMinEl.value = params.get("min");
    if (params.get("max")) levelMaxEl.value = params.get("max");
    fillKinds();
    fillSkills();
    if (params.get("skill")) skillEl.value = params.get("skill");
    if (params.get("tab") === "skills" || params.get("skill")) setTab("skills");
    else { paintStats(); render(); }
  </script>
  <script src="pd/catalog.js"></script>
  <script src="pd/preview.js"></script>
</body>
</html>
"""


def main() -> None:
    print("loading items...")
    items = load_items()
    print(f"  {len(items)} unique items")
    print("loading icon map...")
    files = load_icon_files()
    print(f"  {len(files)} icon ids")
    if ICON_DIR.exists() and any(ICON_DIR.glob("*.png")):
        print("keeping existing bag icons")
    else:
        print("converting SHP icons...")
        pngs = convert_all(EXTRACT, [ICON_DIR, SHARE_ICONS])
        print(f"  {len(pngs)} pngs")
    trees = Counter(i.get("tree", "") for i in items if i.get("tree"))
    print(f"  skill scrolls {sum(trees.values())}")
    for name, n in trees.most_common():
        print(f"    {name:<18} {n:>5}")
    groups = Counter(i["group"] for i in items)
    for g in GROUP_ORDER:
        if groups.get(g):
            print(f"  {g:<18} {groups[g]:>6}")
    kinds = Counter((i["group"], i["kind"]) for i in items)
    print("  consumable types:")
    for (g, k), n in sorted(kinds.items()):
        if g == "Consumables":
            print(f"    {k:<24} {n}")
    html = (
        HTML.replace("__FILES__", json.dumps({str(k): v for k, v in files.items()}, separators=(",", ":")))
            .replace("__GROUPS__", json.dumps(GROUP_ORDER, separators=(",", ":")))
            .replace("__SKILLS__", json.dumps(SKILL_FAMILIES, separators=(",", ":")))
            .replace("__DATA__", json.dumps(items, ensure_ascii=False, separators=(",", ":")))
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    SHARE.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    SHARE.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"wrote {SHARE}")


if __name__ == "__main__":
    main()
