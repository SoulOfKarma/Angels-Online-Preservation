"""Extract local Wait.spr atlases using CHARDEF.XML + char*.obd."""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from client_pd_map import find_spr, load_ride_rows, parse_obd, ride_by_appearance
from ewsp import decode_wait, pack_atlas

# The wiki dummy is the classic ~82px body. Later packs also ship a taller
# Wait.spr (12xxxx) in the same folder; that one floats above this body.
CLASSIC_BODY = 82

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "corpus" / "content.db"
PD_DIR = ROOT / "docs" / "pd"
SPRITE_DIR = PD_DIR / "sprites"
SHARE_SPRITE = ROOT / "share" / "items" / "pd" / "sprites"
CATALOG = PD_DIR / "client_pd_preview.json"
CATALOG_JS = PD_DIR / "catalog.js"
SHARE_CATALOG = ROOT / "share" / "items" / "pd" / "client_pd_preview.json"
SHARE_JS = ROOT / "share" / "items" / "pd" / "catalog.js"

SLOT_COLS = (
    ("頭部", "head"),
    ("身體", "body"),
    ("手部", "hands"),
    ("腳部", "feet"),
    ("背部", "back"),
    ("主手", "main"),
    ("副手", "off"),
)
WEAR_TYPES = {
    "紙娃娃", "座騎",
    "劍", "刀", "斧", "錘", "槍", "杖", "弓箭", "彈弓", "影刃", "盾",
    "衣服", "頭飾", "手套", "鞋子", "披風", "飾品", "背包",
}


def _int(val) -> int | None:
    try:
        n = int(float(val))
    except (TypeError, ValueError):
        return None
    return n if n else None


def load_dolls(db: Path) -> dict[int, dict]:
    con = sqlite3.connect(db)
    cols = {c[1] for c in con.execute("pragma table_info(doll)")}
    dolls = {}
    fields = [c for c, _ in SLOT_COLS if c in cols]
    extra = [c for c in ("頭部全罩", "頭部半罩") if c in cols]
    q = "select id," + ",".join(f'"{c}"' for c in fields + extra) + " from doll"
    for row in con.execute(q):
        did = _int(row[0])
        if did is None:
            continue
        parts = {}
        for name, val in zip(fields, row[1:1 + len(fields)]):
            n = _int(val)
            if n:
                parts[dict(SLOT_COLS)[name]] = n
        if not parts:
            continue
        extra_vals = dict(zip(extra, row[1 + len(fields):]))
        cover = "full" if _int(extra_vals.get("頭部全罩")) else ("half" if _int(extra_vals.get("頭部半罩")) else "none")
        dolls[did] = {"parts": parts, "headCover": cover}
    return dolls


def load_items(db: Path) -> list[dict]:
    con = sqlite3.connect(db)
    out = []
    for table in ("item", "item2", "item3", "item4", "item5", "item6", "item7", "item8", "item9"):
        cols = {c[1] for c in con.execute(f"pragma table_info({table})")}
        if "id" not in cols or "原型外觀" not in cols or "物品類別" not in cols:
            continue
        name_sql = '"基本名稱"' if "基本名稱" in cols else (
            '"原型名稱"' if "原型名稱" in cols else "null"
        )
        sel = f'select "id", "原型外觀", "物品類別", {name_sql} from {table}'
        try:
            rows = list(con.execute(sel))
        except sqlite3.OperationalError:
            continue
        for iid, look, typ, name in rows:
            if typ not in WEAR_TYPES:
                continue
            item_id, appearance = _int(iid), _int(look)
            if item_id is None or appearance is None:
                continue
            out.append({"id": item_id, "look": appearance, "type": typ, "name": str(name or item_id)})
    return out


def extract_sprite(path: Path, key: str, dests: list[Path], cache: dict) -> dict | None:
    if key in cache:
        return cache[key]
    frames = decode_wait(path)
    if not frames:
        return None
    atlas, meta, cell_w, cell_h = pack_atlas(frames)
    name = f"{key}.png"
    for dest in dests:
        dest.mkdir(parents=True, exist_ok=True)
        atlas.save(dest / name, optimize=True)
    rec = {
        "url": f"assets/pd-preview/sprites/{name}",
        "tint": None,
        "width": atlas.size[0],
        "height": atlas.size[1],
        "cellWidth": cell_w,
        "cellHeight": cell_h,
        "frames": meta,
        "sourceAsset": str(path),
    }
    cache[key] = rec
    return rec


def ensure_sprite(path: Path, key: str, dests: list[Path], cache: dict, pd: dict) -> str | None:
    existing = pd["sprites"].get(key)
    if existing and (not existing.get("sourceAsset") or existing.get("sourceAsset") == str(path)):
        return key
    rec = extract_sprite(path, key, dests, cache)
    if not rec:
        return None
    pd["sprites"][key] = rec
    return key


_wait_choice: dict[str, Path] = {}


def classic_wait(path: Path | None) -> Path | None:
    """Prefer the Wait.spr that matches the classic paper-doll body."""
    if path is None:
        return None
    folder = str(path.parent)
    if folder in _wait_choice:
        return _wait_choice[folder]
    waits = [p for p in path.parent.iterdir() if p.suffix.lower() == ".spr" and "wait" in p.name.lower()]
    best, best_score = path, 10**9
    for cand in waits or [path]:
        frames = decode_wait(cand)
        if not frames:
            continue
        score = abs(frames[0]["height"] - CLASSIC_BODY)
        if score < best_score:
            best, best_score = cand, score
    _wait_choice[folder] = best
    return best


def resolve_item(comp: int, sex: str, obd_items: dict) -> tuple[str, Path, Path | None] | None:
    suf = "g" if sex == "female" else "b"
    rec = obd_items.get((comp, suf)) or obd_items.get((comp, "")) or obd_items.get((comp, suf + "l"))
    if not rec:
        return None
    wait = classic_wait(find_spr(rec["folder"], rec["wait"]))
    if wait is None:
        return None
    sit = find_spr(rec["folder"], rec["sit"]) if rec.get("sit") else None
    key = f"item-{comp}{suf}"
    return key, wait, sit


def write_catalog(pd: dict) -> None:
    text = json.dumps(pd, ensure_ascii=False, separators=(",", ":"))
    for dest in (CATALOG, SHARE_CATALOG):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    js = "window.PD_CATALOG = " + text + ";\n"
    for dest in (CATALOG_JS, SHARE_JS):
        dest.write_text(js, encoding="utf-8")


def main() -> None:
    print("loading catalog...")
    pd = json.loads(CATALOG.read_text(encoding="utf-8"))
    kept = [it for it in pd["items"] if not it.get("local")]
    wiki_ids = set()
    for it in kept:
        wiki_ids.add(it["item_id"])
        wiki_ids.update(it.get("itemIds") or [])
    pd["items"] = kept
    print(f"  kept {len(kept)} wiki records")

    print("loading CHARDEF + OBD...")
    ride_rows = load_ride_rows()
    obd_items, obd_rides = parse_obd()
    print(f"  {len(ride_rows)} CHARDEF rides, {len(obd_rides)} H objects, {len(obd_items)} I objects")

    dolls = load_dolls(DB)
    items = load_items(DB)
    dests = [SPRITE_DIR, SHARE_SPRITE]
    cache: dict[str, dict] = {}
    added = []
    new_sprites = 0

    mounts = defaultdict(list)
    wears = defaultdict(list)
    for it in items:
        if it["id"] in wiki_ids:
            continue
        if it["type"] == "座騎":
            mounts[it["look"]].append(it)
        elif it["look"] in dolls:
            wears[it["look"]].append(it)

    print(f"  local mount groups {len(mounts)}, wear groups {len(wears)}")

    for look, group in mounts.items():
        row = ride_by_appearance(ride_rows, look)
        if not row or row["layer"] == "robot":
            continue
        obj = obd_rides.get(row["seq"])
        if not obj:
            continue
        path = find_spr(obj["folder"], obj["wait"])
        if path is None:
            continue
        key = f"ride-{row['seq']}"
        before = key in pd["sprites"]
        if not ensure_sprite(path, key, dests, cache, pd):
            continue
        if not before:
            new_sprites += 1
        names, ids = [], []
        for it in group:
            if it["name"] not in names:
                names.append(it["name"])
            ids.append(it["id"])
        ids = sorted(set(ids))
        comps = {s: {"standing": {}, "mounted": {"ride": key}} for s in ("male", "female")}
        added.append({
            "visualId": f"local-ride-{look}-{ids[0]}",
            "kind": "ride",
            "item_id": ids[0],
            "itemIds": ids,
            "appearanceIds": [look],
            "name": names[0],
            "aliases": names[:8],
            "sexes": ["male", "female"],
            "placements": [{"id": "ride", "occupies": ["ride"], "layers": ["ride"]}],
            "flags": {"headCover": "none", "robe": False, "capeLayer": False, "twoHanded": False, "flexibleHands": False},
            "componentIds": {"ride": row["seq"]},
            "components": comps,
            "ride": {
                "appearanceId": look,
                "sequence": row["seq"],
                "sprite": key,
                "riderOffsetY": row["y"],
                "layerMode": "ride",
            },
            "local": True,
        })

    print(f"  extracted {len(added)} mounts, {new_sprites} new atlases")

    wear_added = 0
    for look, group in wears.items():
        doll = dolls[look]
        sexes: list[str] = []
        comps = {"male": {"standing": {}, "mounted": {}}, "female": {"standing": {}, "mounted": {}}}
        component_ids = {}
        ok = False
        for slot, comp in doll["parts"].items():
            component_ids[slot] = comp
            for sex in ("male", "female"):
                resolved = resolve_item(comp, sex, obd_items)
                if not resolved:
                    continue
                key, wait, sit = resolved
                before = key in pd["sprites"]
                if not ensure_sprite(wait, key, dests, cache, pd):
                    continue
                if not before:
                    new_sprites += 1
                comps[sex]["standing"][slot] = key
                mounted_key = key
                if sit:
                    mkey = key + "-mounted"
                    if ensure_sprite(sit, mkey, dests, cache, pd):
                        if mkey not in cache and mkey not in pd["sprites"]:
                            pass
                        mounted_key = mkey if mkey in pd["sprites"] else key
                        if mkey in pd["sprites"] and mkey not in (pd["sprites"][key] and []):
                            if sit and mkey not in cache:
                                new_sprites += 0
                            mounted_key = mkey
                comps[sex]["mounted"][slot] = mounted_key
                if sex not in sexes:
                    sexes.append(sex)
                ok = True
        if not ok:
            continue
        occupies = [s for s in ("head", "body", "hands", "feet", "back", "main", "off") if s in component_ids]
        if not occupies:
            continue
        names, ids = [], []
        for it in group:
            if it["name"] not in names:
                names.append(it["name"])
            ids.append(it["id"])
        ids = sorted(set(ids))
        added.append({
            "visualId": f"local-{look}-{ids[0]}",
            "kind": "wearable",
            "item_id": ids[0],
            "itemIds": ids,
            "appearanceIds": [look],
            "name": names[0],
            "aliases": names[:8],
            "sexes": sexes or ["female"],
            "placements": [{"id": "default", "occupies": occupies, "layers": occupies}],
            "flags": {
                "headCover": doll["headCover"],
                "robe": False,
                "capeLayer": False,
                "twoHanded": False,
                "flexibleHands": False,
            },
            "componentIds": component_ids,
            "components": comps,
            "local": True,
        })
        wear_added += 1
        if wear_added % 200 == 0:
            print(f"  wear {wear_added}...")

    pd["items"].extend(added)
    write_catalog(pd)
    print(f"added {len(added)} groups ({sum(1 for i in added if i['kind']=='ride')} rides), {new_sprites} new atlases")
    print(f"catalog {len(pd['items'])} records, {len(pd['sprites'])} sprites")
    print(f"wrote {CATALOG} ({CATALOG.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
