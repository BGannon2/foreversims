"""Build the static data the browser needs to import a WoWSims Exporter addon dump
(https://www.curseforge.com/wow/addons/wowsimsexporter).

Reads the local WoWSims Classic checkout for two things Wowhead's Forever data doesn't
carry on its own:
  * per-class talent tree layout, in the exact declared order the addon's Blizzard-style
    talent string encodes (one digit per talent, trees joined with "-")
  * the enchant catalog, matched by name against our own curated `enchants.json` so an
    imported `effectId` can resolve to one of our enchant options

Output: web/data/wowsims-import.json (embedded, no server call needed at import time).

Run from the project root:  python tools/build_wowsims_import.py
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WOWSIMS = Path(r"C:\Users\brend\Documents\Codex\2026-09-16\bli\work\wowsims-classic")
sys.path.insert(0, str(ROOT))

# WoWSims ItemSlot enum order (proto/common.proto) -> our UI slot labels, in two flavors:
# the shared-engine spec pages' `gear_slots` label, and the Paladin engine's lowercase key.
SLOT_ORDER = [
    ("Head", "head"), ("Neck", "neck"), ("Shoulders", "shoulders"), ("Back", "back"), ("Chest", "chest"),
    ("Wrist", "wrist"), ("Hands", "hands"), ("Waist", "waist"), ("Legs", "legs"), ("Feet", "feet"),
    ("Finger 1", "finger1"), ("Finger 2", "finger2"), ("Trinket 1", "trinket1"), ("Trinket 2", "trinket2"),
    ("Main Hand", "main_hand"), ("Off Hand", "off_hand"), ("Ranged / Relic", "relic"),
]

WOWSIMS_CLASS_TO_FOREVER = {
    "Warrior": "Warrior", "Paladin": "Paladin", "Hunter": "Hunter", "Rogue": "Rogue", "Priest": "Priest",
    "Shaman": "Shaman", "Mage": "Mage", "Warlock": "Warlock", "Druid": "Druid",
}


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def build_tree_order():
    """{ forever_class_name: [tree_name, ...] } and { forever_class_name: { tree_name: [{row,col,maxPoints}, ...] } }
    in the exact order the addon's talent string encodes (declaration order per file, tree order = file array order)."""
    trees_dir = WOWSIMS / "ui" / "core" / "talents" / "trees"
    order, trees = {}, {}
    for f in sorted(trees_dir.glob("*.json")):
        cls = f.stem  # "warrior", "paladin", ...
        forever_cls = WOWSIMS_CLASS_TO_FOREVER.get(cls.capitalize())
        if not forever_cls:
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        order[forever_cls] = [t["name"] for t in data]
        trees[forever_cls] = {t["name"]: [{"row": tal["location"]["rowIdx"], "col": tal["location"]["colIdx"], "maxPoints": tal["maxPoints"]} for tal in t["talents"]] for t in data}
    return order, trees


def build_enchant_map():
    """{ wowsims_effect_id (str): [{"slot": our_slot_key, "id": our_enchant_id}, ...] } by exact name match.
    A list because the same enchant name can cover several class-restricted item ids (same effect,
    e.g. the five "Lesser Arcanum of Voracity" relics) or, in our own catalog, the same enchant id
    is offered on more than one slot (e.g. "voracity" on both head and legs); the importer picks the
    candidate matching the item's actual slot."""
    db = json.loads((WOWSIMS / "assets" / "database" / "db.json").read_text(encoding="utf-8"))
    by_name = {}
    for e in db["enchants"]:
        by_name.setdefault(norm(e["name"]), []).append(e["effectId"])
    ours = json.loads((ROOT / "data" / "enchants.json").read_text(encoding="utf-8"))["slots"]
    mapping, unmatched = {}, []
    for slot, rows in ours.items():
        for row in rows:
            if row["id"] == "none":
                continue
            ids = by_name.get(norm(row["name"]))
            if not ids:
                unmatched.append(f"{slot}/{row['id']}: {row['name']}")
                continue
            for effect_id in ids:
                mapping.setdefault(str(effect_id), []).append({"slot": slot, "id": row["id"]})
    return mapping, unmatched


def main():
    if not WOWSIMS.is_dir():
        print(f"WoWSims Classic checkout not found at {WOWSIMS}; nothing to build.")
        return 1
    tree_order, trees = build_tree_order()
    enchant_map, unmatched = build_enchant_map()
    out = {"tree_order": tree_order, "trees": trees, "enchant_map": enchant_map, "slot_order": SLOT_ORDER}
    dest = ROOT / "web" / "data" / "wowsims-import.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {dest.relative_to(ROOT)} ({dest.stat().st_size:,} bytes); {len(enchant_map)} enchants matched, {len(unmatched)} unmatched")
    if unmatched:
        print("Unmatched enchants (not importable from the addon export):")
        for u in unmatched:
            print(" ", u)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
