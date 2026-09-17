"""Extract the Paladin trees from Wowhead's WoW Forever calculator payload."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

PAGE = "https://www.wowhead.com/forever/talent-calc/paladin"
DATA = "https://nether.wowhead.com/forever/data/talents-classic?dv=19"
TREE_NAMES = {"382": "Holy", "383": "Protection", "381": "Retribution"}


def fetch(url):
    return urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"})).read()


def main():
    root = Path(__file__).resolve().parents[1]
    raw = fetch(DATA).decode("utf-8")
    payload = json.loads(raw[raw.index("{"):raw.rindex("}") + 1])
    trees = []
    icon_dir = root / "web" / "talent-icons"
    icon_dir.mkdir(exist_ok=True)
    for tree_id, name in TREE_NAMES.items():
        talents = sorted(payload["talents"][tree_id].values(), key=lambda x: (x["row"], x["col"]))
        clean = []
        for talent in talents:
            clean.append({key: talent[key] for key in
                          ("id", "row", "col", "icon", "name", "ranks", "requires", "descriptions")})
            icon_path = icon_dir / f"{talent['icon']}.jpg"
            if not icon_path.exists():
                icon_path.write_bytes(fetch(f"https://wow.zamimg.com/images/wow/icons/large/{talent['icon']}.jpg"))
        trees.append({"id": int(tree_id), "name": name, "talents": clean})
    result = {"version": "wowhead-forever-paladin-2026-09-16", "source": PAGE,
              "data_source": DATA, "max_points": 51, "points_per_tier": 5, "trees": trees}
    (root / "paladin_talents.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {sum(len(t['talents']) for t in trees)} talents and local icons")


if __name__ == "__main__":
    main()
