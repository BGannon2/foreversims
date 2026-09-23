"""Write data/item_class_restrictions.json: catalog items only some classes may equip, plus
each item's client LimitCategory (items sharing one can't be equipped together, e.g. the
Signet Ring of the Bronze Dragonflight variants or Talisman of Arathor / Defiler's Talisman).

Source: the Forever client's ItemSparse.AllowableClass bitmask (Wago, pinned build), which is
authoritative for Forever (e.g. Highlander's gear is unrestricted there despite old tooltips).
Items missing from ItemSparse fall back to a "Classes: ..." tooltip line, if any.
Run: python tools/build_item_class_restrictions.py [--raw ItemSparse.csv]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forever.all_specs import ITEMS  # noqa: E402

BUILD = "1.60.1.69913"
URL = f"https://wago.tools/db2/ItemSparse/csv?build={BUILD}"
CLASS_BITS = {1: "Warrior", 2: "Paladin", 4: "Hunter", 8: "Rogue", 16: "Priest", 64: "Shaman", 128: "Mage", 256: "Warlock", 1024: "Druid"}
ALL = sum(CLASS_BITS)
# Faction-only gear. The client marks reputation vendors (MinFactionID) but not PvP rank gear,
# whose faction is its rank title; Alliance titles are matched first ("Knight-Champion's" vs
# the Horde "Champion's").
REP_FACTION = {509: "Alliance", 730: "Alliance", 890: "Alliance", 510: "Horde", 729: "Horde", 889: "Horde"}
ALLIANCE_TITLES = ("Grand Marshal's", "Field Marshal's", "Marshal's", "Lieutenant Commander's", "Knight-Captain's",
                   "Knight-Lieutenant's", "Knight-Champion's", "Sergeant Major's", "Sentinel's", "Highlander's")
HORDE_TITLES = ("High Warlord's", "Warlord's", "Lieutenant General's", "General's", "Champion's", "Legionnaire's",
                "Blood Guard's", "Stone Guard's", "First Sergeant's", "Outrider's", "Defiler's")
ALLIANCE_WORDS = ("Stormpike", "Silverwing", "Arathor")
HORDE_WORDS = ("Frostwolf", "Warsong")


# Same-rank title pairs (Alliance, Horde); twins share stats and differ only in title/vendor.
TWIN_TITLES = (("Grand Marshal's", "High Warlord's"), ("Field Marshal's", "Warlord's"), ("Marshal's", "General's"),
               ("Lieutenant Commander's", "Champion's"), ("Knight-Captain's", "Legionnaire's"),
               ("Knight-Lieutenant's", "Blood Guard's"), ("Sergeant Major's", "First Sergeant's"),
               ("Sentinel's", "Outrider's"), ("Highlander's", "Defiler's"), ("Stormpike", "Frostwolf"),
               ("Talisman of Arathor", "Defiler's Talisman"))


def swap_title(name, faction):
    """The other faction's version of a rank-titled name (Premier prefix kept), or None."""
    prefix = "Premier " if name.startswith("Premier ") else ""
    base = name[len(prefix):]
    for alliance, horde in TWIN_TITLES:
        src, dst = (alliance, horde) if faction == "Alliance" else (horde, alliance)
        if base.startswith(src):
            return prefix + dst + base[len(src):]
    return None


def stat_key(item):
    return (item["slot"], item.get("subclass"), item.get("itemLevel"), tuple(sorted(item.get("stats", {}).items())),
            tuple(item.get("effects", [])))


def faction_twins(factions):
    """Pair each faction item with the other faction's equivalent.

    1. "name": same name after swapping the rank title (Knight-Captain's <-> Legionnaire's).
    2. "stats": Blizzard often renamed the item too (Grand Marshal's Longsword <-> High Warlord's
       Blade), so fall back to the one other-faction item with identical slot, armor type, item
       level, stats and effects. When several match (the Silk / Dreadweave / Satin belts of
       different class sets), take the one in the same set under the other title, else none.

    TODO(gear data): the "stats" pairings and the unpaired items are inferred, not sourced. Revisit
    once there's concrete Forever evidence of which PvP/battleground gear exists per faction
    (vendor lists, datamined item ids), especially Horde Paladin gear (Lamellar sets were
    Alliance-only in Classic), Forever "Premier" items and reputation rewards whose stats differ.
    """
    by_name, by_stats = {}, {}
    for iid, faction in factions.items():
        item = ITEMS[int(iid)]
        by_name.setdefault(item["name"], []).append(item)
        by_stats.setdefault((faction, stat_key(item)), []).append(item)
    twins, method = {}, {}
    for iid, faction in factions.items():
        item = ITEMS[int(iid)]
        other = "Horde" if faction == "Alliance" else "Alliance"
        named = [x for x in by_name.get(swap_title(item["name"], faction) or "", [])
                 if factions.get(str(x["id"])) == other and x["slot"] == item["slot"]]
        if named:
            twins[iid], method[iid] = named[0]["id"], "name"
            continue
        same = by_stats.get((other, stat_key(item)), [])
        if len(same) > 1:
            own_set = (item.get("set") or {}).get("name")
            twin_set = swap_title(own_set, faction) if own_set else None
            same = [x for x in same if twin_set and (x.get("set") or {}).get("name") == twin_set]
        if len(same) == 1:
            twins[iid], method[iid] = same[0]["id"], "stats"
    # One-to-one only: duplicate catalog names/ids can otherwise send A -> B -> C on a round trip.
    mutual = {iid: t for iid, t in twins.items() if twins.get(str(t)) == int(iid)}
    return mutual, {iid: method[iid] for iid in mutual}


def faction_of(name, min_faction):
    if min_faction in REP_FACTION:
        return REP_FACTION[min_faction]
    title = re.sub(r"^Premier ", "", name)
    for titles, words, faction in ((ALLIANCE_TITLES, ALLIANCE_WORDS, "Alliance"), (HORDE_TITLES, HORDE_WORDS, "Horde")):
        if title.startswith(titles) or any(w in name for w in words):
            return faction
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, help="local ItemSparse CSV for the pinned build")
    args = parser.parse_args()
    if args.raw:
        text = args.raw.read_text(encoding="utf-8")
    else:
        request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=300) as response:
            text = response.read().decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(text)))
    masks = {int(r["ID"]): int(r["AllowableClass"]) for r in rows}
    limits = {str(r["ID"]): int(r["LimitCategory"]) for r in rows if int(r["ID"]) in ITEMS and int(r["LimitCategory"])}
    min_faction = {int(r["ID"]): int(r["MinFactionID"]) for r in rows}
    factions = {str(iid): f for iid, item in sorted(ITEMS.items()) if (f := faction_of(item["name"], min_faction.get(iid, 0)))}
    out, from_tooltip = {}, 0
    for iid, item in sorted(ITEMS.items()):
        if iid in masks:
            mask = masks[iid]
            if mask > 0 and mask & ALL != ALL:
                out[str(iid)] = [name for bit, name in CLASS_BITS.items() if mask & bit]
            continue
        label = next((t["label"] for t in item.get("tooltip") or [] if t.get("label", "").startswith("Classes:")), None)
        if label:
            out[str(iid)] = [c.strip() for c in label[len("Classes:"):].split(",")]
            from_tooltip += 1
    twins, twin_method = faction_twins(factions)
    payload = {"source": URL, "field": "ItemSparse.AllowableClass", "tooltip_fallback": from_tooltip, "items": out,
               "limit_categories": dict(sorted(limits.items(), key=lambda kv: int(kv[0]))), "factions": factions,
               "faction_twins": twins,
               "faction_twin_method": twin_method}
    (ROOT / "data" / "item_class_restrictions.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"{len(out)} restricted items ({from_tooltip} from tooltip fallback); {len(limits)} with a limit category; "
          f"{sum(f == 'Alliance' for f in factions.values())} Alliance-only, {sum(f == 'Horde' for f in factions.values())} Horde-only; "
          f"twins: {sum(m == 'name' for m in twin_method.values())} by name, {sum(m == 'stats' for m in twin_method.values())} by identical stats, "
          f"{len(factions) - len(twins)} unpaired")


if __name__ == "__main__":
    main()
