"""Pulls foreverchanges.pro's level-60-gear item diff (new/changed/removed vs Classic Era)
and merges it into data/classic_era_items.json and data/extra_items.json.

Usage:
    python tools/fetch_forever_items.py [--download] [--build BUILD]

--download fetches fresh new.json/changed.json/missing.json from foreverchanges.pro into
a scratch dir; without it, expects those three files already sitting next to this script's
scratch output from a previous run (data/.forever_items_cache/).

Rating -> percent conversion uses the historically documented real-Blizzard level-60 combat
rating constants (the ones patch 2.0 retrofitted onto level-60 Classic characters before the
level-70 squish: 14 rating/1% crit, 8 rating/1% hit, 2.3554 rating/1 defense skill, etc).
Forever's own constants are NOT confirmed anywhere (no DB2 table for it, foreverchanges.pro
doesn't document it) -- this is a clearly-flagged provisional assumption, not sourced data.

Items removed from Forever are recorded in data/forever_removed_item_ids.json but NOT deleted
from the catalog, since hundreds of them are directly referenced by existing preset gear lists
(data/phase12_bis_all.json) that would otherwise break. A future BiS-rebuild pass should
exclude these ids from consideration and then this script (or a variant of it) can safely
delete them once nothing references them any more.
"""
from __future__ import annotations
import argparse, json, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = DATA / ".forever_items_cache"

RATING_PER_PCT_60 = {
    "crit": 14.0, "hit_melee": 8.0, "hit_spell": 8.0, "haste": 10.0,
    "expertise": 3.9, "defense": 2.3554, "dodge": 14.5,
}

SLOT_MAP = {
    "Head": ("Head", ["head"]), "Neck": ("Neck", ["neck"]), "Shoulder": ("Shoulder", ["shoulders"]),
    "Back": ("Back", ["back"]), "Chest": ("Chest", ["chest"]), "Wrist": ("Wrist", ["wrist"]),
    "Hands": ("Hands", ["hands"]), "Waist": ("Waist", ["waist"]), "Legs": ("Legs", ["legs"]),
    "Feet": ("Feet", ["feet"]), "Finger": ("Finger", ["finger1", "finger2"]),
    "Trinket": ("Trinket", ["trinket1", "trinket2"]), "Relic": ("Relic", ["relic"]),
    "Ranged": ("Ranged", ["ranged"]), "One-Hand": ("One-Hand", ["main_hand", "off_hand"]),
    "Two-Hand": ("Two-Hand", ["main_hand"]), "Main Hand": ("Main Hand", ["main_hand"]),
    "Off Hand": ("Off Hand", ["off_hand"]), "Held In Off-hand": ("Held In Off-hand", ["off_hand"]),
    "Shield": ("Off Hand", ["off_hand"]),
}

QUALITY = {0: "Poor", 1: "Common", 2: "Uncommon", 3: "Rare", 4: "Epic", 5: "Legendary", 6: "Artifact"}

STAT_LINE = re.compile(r"^\+(\d+) (.+)$")
ARMOR_LINE = re.compile(r"^(\d+) Armor$")
WEAPON_DMG = re.compile(r"^(\d+) - (\d+) Damage")
WEAPON_SPEED = re.compile(r"Speed ([\d.]+)")
DPS_LINE = re.compile(r"^\(([\d.]+) damage per second\)$")
REQ_LEVEL = re.compile(r"^Requires Level (\d+)$")
EQUIP_RATING = re.compile(r"Equip: \+(\d+) (Critical Strike|Hit|Defense|Dodge|Haste|Expertise) Rating")
EQUIP_STAT = re.compile(r"^Equip: \+(\d+) (Attack Power|Spell Power|Spell Damage|Healing|Block Value)$")

STAT_NAME_MAP = {
    "Strength": "strength", "Agility": "agility", "Stamina": "stamina", "Intellect": "intellect",
    "Spirit": "spirit", "Attack Power": "attackPower", "Spell Power": "spellPower",
    "Healing": "healingPower", "Spell Damage": "spellPower", "Defense Rating": "__defense_rating",
    "Dodge Rating": "__dodge_rating", "Critical Strike Rating": "__crit_rating",
    "Hit Rating": "__hit_rating", "Haste Rating": "__haste_rating", "Expertise Rating": "__expertise_rating",
    "Block Rating": "block", "Block Value": "blockValue", "Fire Resistance": "fireResistance",
    "Frost Resistance": "frostResistance", "Nature Resistance": "natureResistance",
    "Shadow Resistance": "shadowResistance", "Arcane Resistance": "arcaneResistance",
    "Mana every 5 sec.": "mp5",
}

TEST_JUNK = re.compile(r"^\d+ Test |^Test ", re.I)
PRESERVE_KEYS = ("set", "wowhead", "phase")


def convert_rating(key, amount, stats):
    if key == "__defense_rating":
        stats["defense"] = stats.get("defense", 0) + amount / RATING_PER_PCT_60["defense"]
    elif key == "__crit_rating":
        pct = amount / RATING_PER_PCT_60["crit"]
        stats["meleeCrit"] = stats.get("meleeCrit", 0) + pct
        stats["spellCrit"] = stats.get("spellCrit", 0) + pct
    elif key == "__hit_rating":
        stats["meleeHit"] = stats.get("meleeHit", 0) + amount / RATING_PER_PCT_60["hit_melee"]
        stats["spellHit"] = stats.get("spellHit", 0) + amount / RATING_PER_PCT_60["hit_spell"]
    elif key == "__dodge_rating":
        stats["dodge"] = stats.get("dodge", 0) + amount / RATING_PER_PCT_60["dodge"]
    # haste/expertise ratings dropped: not modeled anywhere in this sim yet


def parse_tooltip(it):
    lines = it["x"]
    name = it["n"]
    if TEST_JUNK.match(name):
        return None
    slot_raw = it.get("s")
    if slot_raw not in SLOT_MAP:
        return None
    slot, equip_slots = SLOT_MAP[slot_raw]
    stats, effects, tooltip = {}, [], []
    subclass = None
    armor = None
    weapon_min = weapon_max = weapon_speed = None
    req_level = it.get("r", 0)

    tooltip.append({"label": name, "format": QUALITY.get(it["q"], "Common")})
    tooltip.append({"label": f"Item Level {it['l']}", "format": "Misc"})

    for raw in lines:
        line = raw.split("\t")[0].strip() if "\t" in raw and not raw.startswith("(") else raw.strip()
        parts = raw.split("\t")
        if "\t" in raw and parts[0] in SLOT_MAP:
            if len(parts) > 1 and parts[1] not in ("",):
                subclass = parts[1].strip()
            continue
        m = WEAPON_DMG.match(raw)
        if m:
            weapon_min, weapon_max = float(m.group(1)), float(m.group(2))
            sm = WEAPON_SPEED.search(raw)
            if sm:
                weapon_speed = float(sm.group(1))
            tooltip.append({"label": raw.replace("\t", " "), "format": ""})
            continue
        if DPS_LINE.match(line):
            continue
        m = ARMOR_LINE.match(line)
        if m:
            armor = float(m.group(1))
            stats["armor"] = armor
            tooltip.append({"label": line, "format": ""})
            continue
        m = STAT_LINE.match(line)
        if m:
            amount, statname = float(m.group(1)), m.group(2).strip()
            key = STAT_NAME_MAP.get(statname)
            if key and key.startswith("__"):
                convert_rating(key, amount, stats)
            elif key:
                stats[key] = stats.get(key, 0) + amount
            tooltip.append({"label": line, "format": ""})
            continue
        if REQ_LEVEL.match(line):
            tooltip.append({"label": line, "format": ""})
            continue
        if line.startswith("Equip:"):
            tooltip.append({"label": line, "format": QUALITY.get(it["q"], "Common")})
            m2 = EQUIP_RATING.search(line)
            m3 = EQUIP_STAT.search(line)
            if m2:
                amt, kind = float(m2.group(1)), m2.group(2)
                convert_rating({"Critical Strike": "__crit_rating", "Hit": "__hit_rating",
                                 "Defense": "__defense_rating", "Dodge": "__dodge_rating",
                                 "Haste": "__haste_rating", "Expertise": "__expertise_rating"}[kind], amt, stats)
                # Recognized and captured structurally -- do NOT also emit as free-text `effects`:
                # the engine's old Classic-phrasing regex parser doesn't understand "+N X Rating"
                # text and would flag it "unresolved" if it were re-emitted here.
            elif m3:
                key = STAT_NAME_MAP.get(m3.group(2))
                if key and not key.startswith("__"):
                    stats[key] = stats.get(key, 0) + float(m3.group(1))
                else:
                    effects.append(line)
            else:
                effects.append(line)
            continue
        if line.startswith("Binds") or line.startswith("Unique") or line.startswith("Classes:") \
           or line.startswith("Sell Price") or line.startswith('"') or line.startswith("Requires ") \
           or "Set:" in line or re.match(r".+\(\d/\d\)$", line):
            continue

    if armor is None and weapon_min is None and not stats and not effects:
        return None  # nothing usable parsed; skip rather than emit a hollow record

    return {
        "id": it["i"], "name": name, "icon": it.get("k", ""),
        "quality": QUALITY.get(it["q"], "Common"), "itemLevel": it.get("l", 0),
        "requiredLevel": req_level, "slot": slot, "equipSlots": equip_slots,
        "subclass": subclass, "stats": stats,
        "weaponDamageMin": weapon_min, "weaponDamageMax": weapon_max, "weaponSpeed": weapon_speed,
        "effects": effects, "tooltip": tooltip,
    }


def gear_filter(it):
    return it["c"] in (2, 4) and it.get("r", 0) >= 55 and it.get("s") and it["q"] in (2, 3, 4, 5)


def download(build):
    CACHE.mkdir(exist_ok=True)
    for name in ("new", "changed", "missing"):
        url = f"https://foreverchanges.pro/items/{name}.json"
        print(f"downloading {url}", file=sys.stderr)
        with urllib.request.urlopen(url, timeout=60) as resp:
            (CACHE / f"{name}.json").write_bytes(resp.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true", help="fetch fresh JSON from foreverchanges.pro first")
    ap.add_argument("--build", default="1.60.1.69913")
    args = ap.parse_args()

    if args.download:
        download(args.build)

    newd = json.loads((CACHE / "new.json").read_text(encoding="utf-8"))
    changedd = json.loads((CACHE / "changed.json").read_text(encoding="utf-8"))
    missingd = json.loads((CACHE / "missing.json").read_text(encoding="utf-8"))

    new_gear = [it for it in newd["items"] if gear_filter(it)]
    changed_gear = [it for it in changedd["items"] if gear_filter(it)]
    missing_ids = sorted({it["i"] for it in missingd["items"] if gear_filter(it)})

    parsed_new = [r for it in new_gear if (r := parse_tooltip(it))]
    parsed_changed = [r for it in changed_gear if (r := parse_tooltip(it))]
    print(f"new_gear={len(new_gear)} parsed={len(parsed_new)}", file=sys.stderr)
    print(f"changed_gear={len(changed_gear)} parsed={len(parsed_changed)}", file=sys.stderr)
    print(f"missing_ids={len(missing_ids)}", file=sys.stderr)

    classic_path = DATA / "classic_era_items.json"
    extra_path = DATA / "extra_items.json"
    classic = json.loads(classic_path.read_text(encoding="utf-8"))
    extra = json.loads(extra_path.read_text(encoding="utf-8"))
    classic_items = {x["id"]: x for x in classic["items"]}
    extra_items = {x["id"]: x for x in extra["items"]}

    (DATA / "forever_removed_item_ids.json").write_text(json.dumps(missing_ids), encoding="utf-8")

    upserted_classic = upserted_extra = added_extra = 0
    for r in parsed_changed + parsed_new:
        r = dict(r)
        r["source"] = f"forever-{args.build}"
        r.setdefault("wowhead", "https://foreverchanges.pro/items")
        existing = classic_items.get(r["id"]) or extra_items.get(r["id"])
        if existing:
            for k in PRESERVE_KEYS:
                if k in existing:
                    r[k] = existing[k]
        if r["id"] in classic_items:
            classic_items[r["id"]] = r; upserted_classic += 1
        elif r["id"] in extra_items:
            extra_items[r["id"]] = r; upserted_extra += 1
        else:
            extra_items[r["id"]] = r; added_extra += 1

    classic["items"] = sorted(classic_items.values(), key=lambda x: x["id"])
    extra["items"] = sorted(extra_items.values(), key=lambda x: x["id"])
    classic_path.write_text(json.dumps(classic, ensure_ascii=False), encoding="utf-8")
    extra_path.write_text(json.dumps(extra, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"classic_era_items.json: upserted={upserted_classic} total={len(classic['items'])}", file=sys.stderr)
    print(f"extra_items.json: upserted={upserted_extra} added={added_extra} total={len(extra['items'])}", file=sys.stderr)
    print("Now run: python tools/export_static_data.py && bash tools/build_engine.sh", file=sys.stderr)


if __name__ == "__main__":
    main()
