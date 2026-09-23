"""Write data/item_raid_sources.json: catalog items from content the BiS optimizer excludes.

The catalog's "source" text can't tell a raid drop from a world drop ("Zone Drop") and says
nothing about where a quest is ("Quest: Conqueror's Spaulders" is an Ahn'Qiraj quest), and the
client has no Dungeon Journal tables. WoWSims Classic's item database (assets/database/db.json)
records each item's drop zones, quest sources and content phase, so an item is excluded if it
drops in a later-phase raid zone, or belongs to the Ahn'Qiraj patch or later (phase 5+: AQ40,
AQ20, Brood of Nozdormu / Cenarion Circle quest rewards, Naxxramas).
Run: python tools/fetch_item_raid_sources.py [--db PATH]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forever.all_specs import ITEMS  # noqa: E402

DB_URL = "https://raw.githubusercontent.com/wowsims/classic/master/assets/database/db.json"
RAID_ZONES = {2717: "Molten Core", 2677: "Blackwing Lair", 1977: "Zul'Gurub", 3429: "Ruins of Ahn'Qiraj",
              3428: "Temple of Ahn'Qiraj", 3456: "Naxxramas"}
FIRST_EXCLUDED_PHASE = 5  # WoWSims phases: 1 MC/Onyxia, 2 Dire Maul, 3 BWL, 4 ZG, 5 Ahn'Qiraj, 6 Naxxramas


def reasons(entry):
    out = [RAID_ZONES[s["drop"]["zoneId"]] for s in entry.get("sources", [])
           if "drop" in s and s["drop"].get("zoneId") in RAID_ZONES]
    if entry.get("phase", 1) >= FIRST_EXCLUDED_PHASE:
        out.append(f"phase {entry['phase']}")
    return sorted(set(out))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="local copy of WoWSims Classic db.json")
    args = parser.parse_args()
    if args.db:
        text = args.db.read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(urllib.request.Request(DB_URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=300) as r:
            text = r.read().decode("utf-8")
    db = {entry["id"]: entry for entry in json.loads(text)["items"]}
    result = {str(iid): why for iid in sorted(ITEMS) if iid in db and (why := reasons(db[iid]))}
    payload = {"source": DB_URL, "raid_zones": {str(k): v for k, v in RAID_ZONES.items()},
               "first_excluded_phase": FIRST_EXCLUDED_PHASE, "catalog_items_in_db": sum(i in db for i in ITEMS),
               "items": result}
    (ROOT / "data" / "item_raid_sources.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"{len(result)} of {payload['catalog_items_in_db']} catalog items in the WoWSims database are later-raid or AQ-phase+")


if __name__ == "__main__":
    main()
