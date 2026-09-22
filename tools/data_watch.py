"""Check whether our upstream data sources have moved since the last known-good snapshot.

Watches two things, the same two a parallel Forever conversion project
(github.com/ElliotWood/Forever) watches on a 6-hour schedule:

1. The newest wow_classic_beta build on wago.tools (https://wago.tools/api/builds) -- a new
   build means the DB2 tables (abilities, talents, items) may have changed.
2. foreverchanges.pro's banner build tag and item counts ("5,340 new items and 4,292 changed")
   -- an independent read of roughly the same data; if it moves without wago.tools' build
   number moving, foreverchanges.pro re-parsed something (or Wowhead's Forever data changed
   under it), which is worth knowing even without a new client build.

This script only detects and records drift -- it deliberately does NOT re-run the fetch/build
pipeline itself, since every one of those tools (fetch_forever_items.py, generate_benchmarks.py,
build_engine.sh) needs a human to review what changed before regenerating data across the whole
site. Run standalone to check locally:

    python tools/data_watch.py

Exits 0 with "no drift" if the snapshot in data/.watch_state.json still matches; exits 0 and
prints a summary (plus, under GitHub Actions, sets `changed=true` in $GITHUB_OUTPUT) if it
doesn't. The GitHub Actions workflow (.github/workflows/watch_forever_data.yml) runs this on a
schedule and opens a pull request with the updated snapshot when something moved, so a human
sees a PR instead of having to remember to check.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "data" / ".watch_state.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; forever-sim-data-watch/1.0)"}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def latest_wago_build() -> str:
    """Newest wow_classic_beta version string, e.g. "1.60.1.69913"."""
    builds = json.loads(fetch("https://wago.tools/api/builds"))
    entries = builds.get("wow_classic_beta", [])
    if not entries:
        raise RuntimeError("no wow_classic_beta entries in wago.tools/api/builds")
    # created_at isn't guaranteed sorted (README notes this); pick the max by created_at.
    newest = max(entries, key=lambda e: e["created_at"])
    return newest["version"]


def foreverchanges_snapshot() -> dict:
    """Build tag and item counts off foreverchanges.pro's homepage banner/summary text."""
    html = fetch("https://foreverchanges.pro")
    text = re.sub(r"<[^>]+>", " ", html)
    build_match = re.search(r"[Bb]eta build\s+([\d.]+)", text)
    items_match = re.search(r"([\d,]+)\s+new items and\s+([\d,]+)\s+changed", text)
    talents_match = re.search(r"(\d[\d,]*)\s+[Tt]alent and spell changes", text)
    return {
        "build": build_match.group(1) if build_match else None,
        "new_items": items_match.group(1) if items_match else None,
        "changed_items": items_match.group(2) if items_match else None,
        "talents_changed": talents_match.group(1) if talents_match else None,
    }


def load_state() -> dict:
    if STATE_FILE.is_file():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def main():
    old = load_state()
    new = {
        "wago_build": latest_wago_build(),
        "foreverchanges": foreverchanges_snapshot(),
    }

    changed_fields = []
    if old.get("wago_build") != new["wago_build"]:
        changed_fields.append(f"wago.tools build: {old.get('wago_build')!r} -> {new['wago_build']!r}")
    for key in ("build", "new_items", "changed_items", "talents_changed"):
        old_v = (old.get("foreverchanges") or {}).get(key)
        new_v = new["foreverchanges"].get(key)
        if old_v != new_v:
            changed_fields.append(f"foreverchanges.pro {key}: {old_v!r} -> {new_v!r}")

    STATE_FILE.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")

    if not old:
        print("No prior snapshot (first run) -- wrote data/.watch_state.json, nothing to compare against yet.")
        return

    if changed_fields:
        print("Data source drift detected:")
        for line in changed_fields:
            print(f"  - {line}")
        print("\nThis does NOT mean anything is broken -- it means a human should look at what")
        print("moved and decide whether tools/fetch_forever_items.py, the ability sourcing in")
        print("forever/engine_data.py, or data/forever_talents_all.json need a refresh.")
        gh_out = os.environ.get("GITHUB_OUTPUT")
        if gh_out:
            with open(gh_out, "a", encoding="utf-8") as f:
                f.write("changed=true\n")
    else:
        print("No drift: wago.tools build and foreverchanges.pro snapshot both match the last known state.")
        gh_out = os.environ.get("GITHUB_OUTPUT")
        if gh_out:
            with open(gh_out, "a", encoding="utf-8") as f:
                f.write("changed=false\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"data_watch.py failed: {e}", file=sys.stderr)
        sys.exit(1)
