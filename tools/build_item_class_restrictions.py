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
    payload = {"source": URL, "field": "ItemSparse.AllowableClass", "tooltip_fallback": from_tooltip, "items": out,
               "limit_categories": dict(sorted(limits.items(), key=lambda kv: int(kv[0])))}
    (ROOT / "data" / "item_class_restrictions.json").write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"{len(out)} restricted items ({from_tooltip} from tooltip fallback); {len(limits)} with a limit category")


if __name__ == "__main__":
    main()
