"""CHARDEF.XML + char*.obd lookups, same path as angelsonline.wiki."""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from shp_icon import PAK_ORDER


def _extract_root() -> Path:
    """First extracted client that exists. AO_EXTRACT overrides the search."""
    candidates = []
    env = os.environ.get("AO_EXTRACT")
    if env:
        candidates.append(Path(env))
    candidates.extend([
        Path.home() / "OneDrive" / "Desktop" / "Angels Online" / "extracted",
        Path.home() / "Desktop" / "Angels Online" / "extracted",
        Path(r"C:\Program Files (x86)\Angels Online\extracted"),
    ])
    existing = [cand for cand in candidates if cand.is_dir()]
    for cand in existing:
        if (cand / "update26").is_dir() or (cand / "UPDATE26").is_dir():
            return cand
    if existing:
        return existing[0]
    return candidates[-1]


EXTRACT = _extract_root()
DIR_RE = re.compile(r"(?i)[\\/]chr[\\/]([ih])(\d+)([gbl]*)")


def _latest(name: str) -> Path | None:
    last = None
    for pak in PAK_ORDER:
        for folder in ("setting", "SETTING"):
            for cand in (
                EXTRACT / pak / folder / name,
                EXTRACT / pak / folder / name.upper(),
                EXTRACT / pak / folder / name.lower(),
            ):
                if cand.is_file():
                    last = cand
    return last


def load_ride_rows() -> list[dict]:
    path = _latest("CHARDEF.XML")
    if path is None:
        return []
    rows = []
    for el in ET.parse(path).getroot():
        if el.tag != "騎乘":
            continue
        layer = el.attrib.get("層級") or ""
        kind = el.attrib.get("種類") or "0"
        rows.append({
            "seq": int(el.attrib.get("號碼") or 0),
            "y": int(el.attrib.get("高度") or 0),
            "layer": "ride" if "ROBOT" not in layer else "robot",
            "kind": kind,
        })
    return rows


def ride_by_appearance(rows: list[dict], appearance: int) -> dict | None:
    if appearance < 1 or appearance > len(rows):
        return None
    return rows[appearance - 1]


def parse_obd(extract: Path = EXTRACT) -> tuple[dict, dict]:
    """Return (item_index, ride_by_seq). item key is (comp_id, suffix)."""
    items: dict[tuple[int, str], dict] = {}
    rides: dict[int, dict] = {}
    files = []
    for pak in PAK_ORDER:
        for folder in ("setting", "SETTING"):
            d = extract / pak / folder
            if not d.is_dir():
                continue
            for p in d.iterdir():
                if p.suffix.lower() == ".obd" and p.stem.lower().startswith("char"):
                    files.append(p)

    def flush(cur: dict) -> None:
        directory = cur.get("dir") or ""
        m = DIR_RE.search(directory.replace("/", "\\"))
        if not m:
            return
        kind, num, suf = m.group(1).lower(), int(m.group(2)), (m.group(3) or "").lower()
        rec = {
            "dir": m.group(0).split("chr")[-1].strip("\\/"),
            "folder": f"{kind}{num}{suf}" if kind == "i" else f"{kind}{num:03d}" if num < 1000 else f"{kind}{num}",
            "wait": cur.get("wait") or "",
            "sit": cur.get("sit") or "",
            "seq": cur.get("seq"),
        }
        # folder from directory tail is more reliable than zero-pad
        rec["folder"] = directory.strip().strip("\\").split("\\")[-1]
        if kind == "h" and rec.get("seq"):
            rides[int(rec["seq"])] = rec
        elif kind == "i":
            items[(num, suf)] = rec

    for path in files:
        cur: dict = {}
        with path.open(encoding="latin1", errors="replace") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("[") and line.upper() == "[OBJECT]":
                    flush(cur)
                    cur = {}
                    continue
                if "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key, val = key.strip().lower(), val.strip()
                if key == "directory":
                    cur["dir"] = val
                elif key == "sequence":
                    try:
                        cur["seq"] = int(val.split()[0])
                    except ValueError:
                        pass
                elif key == "spritefile":
                    kind, _, rest = val.partition(",")
                    fname = rest.split(",")[0].strip()
                    if kind.strip().lower() == "wait":
                        cur["wait"] = fname
                    elif kind.strip().lower() == "sit":
                        cur["sit"] = fname
        flush(cur)
    return items, rides


def find_spr(folder: str, filename: str, extract: Path = EXTRACT) -> Path | None:
    if not folder:
        return None

    def search(match) -> Path | None:
        last = None
        for pak in PAK_ORDER:
            d = extract / pak / "shape" / "chr" / folder
            if not d.is_dir():
                continue
            for p in d.iterdir():
                if p.suffix.lower() == ".spr" and match(p.name):
                    last = p
        return last

    want = (filename or "").lower()
    if want:
        exact = search(lambda n: n.lower() == want)
        if exact:
            return exact
        if want.endswith("_wait.spr"):
            run_name = want.replace("_wait.spr", "_run.spr")
            run = search(lambda n: n.lower() == run_name)
            if run:
                return run
    wait = search(lambda n: "wait" in n.lower())
    if wait:
        return wait
    return search(lambda n: "run" in n.lower())
