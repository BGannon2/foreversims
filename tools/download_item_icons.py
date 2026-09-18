"""Download the Classic item thumbnails referenced by the generated catalog."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "data" / "classic_era_items.json").read_text(encoding="utf-8"))
OUTPUT = ROOT / "web" / "item-icons"
OUTPUT.mkdir(exist_ok=True)


def download(icon):
    target = OUTPUT / f"{icon}.jpg"
    if target.exists():
        return False
    url = f"https://wow.zamimg.com/images/wow/icons/medium/{icon}.jpg"
    target.write_bytes(urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read())
    return True


def main():
    icons = sorted({item["icon"] for item in CATALOG["items"] if item.get("icon")})
    with ThreadPoolExecutor(max_workers=16) as pool:
        downloaded = sum(pool.map(download, icons))
    print(f"Available: {len(icons)} item icons; downloaded: {downloaded}")


if __name__ == "__main__":
    main()
