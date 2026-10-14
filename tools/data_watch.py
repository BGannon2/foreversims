"""Check whether the Forever client builds we follow have moved.

Two wago.tools products are watched (https://wago.tools/api/builds):

1. **Live** (`wowf`): the client players actually run.
2. **Beta** (`wow_classic_beta`): upcoming changes.

PIN chooses which one the sim follows (BUILD in tools/wago_audit.py). A newer build of the pinned
product sets `pin_changed=true`, and the workflow opens a re-pin PR that refreshes the client data
and regenerates the engine, BiS sets and benchmarks. While pinned to live, each new beta build also
gets a report-only "Forever beta preview" issue diffing it against live (`preview_build`).

foreverchanges.pro's banner build tag and item counts are recorded too, as a secondary
freshness signal for the beta. Results go to data/.watch_state.json and, under GitHub Actions,
to $GITHUB_OUTPUT (pin_changed, pin_build, pin_label, preview_build). Run standalone to check locally:

    python tools/data_watch.py
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


LIVE_PRODUCT = "wowf"
BETA_PRODUCT = "wow_classic_beta"
PIN = "beta"  # "live" or "beta": which client the sim follows


def latest_builds() -> dict:
    """Newest Forever (1.60.x) version per watched product, e.g. {"live": "1.60.1.70245", ...}."""
    builds = json.loads(fetch("https://wago.tools/api/builds"))
    out = {}
    for key, product in (("live", LIVE_PRODUCT), ("beta", BETA_PRODUCT)):
        # The beta product also carries other Classic branches; keep Forever's 1.60 line only.
        entries = [e for e in builds.get(product, []) if str(e.get("version", "")).startswith("1.60.")]
        if not entries:
            raise RuntimeError(f"no Forever {product} entries in wago.tools/api/builds")
        # created_at isn't guaranteed sorted; pick the max by created_at.
        out[key] = max(entries, key=lambda e: e["created_at"])["version"]
    return out


def pinned_build() -> str:
    m = re.search(r'^BUILD = "([\d.]+)"', (ROOT / "tools" / "wago_audit.py").read_text(encoding="utf-8"), re.M)
    return m.group(1)


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
    builds = latest_builds()
    new = {"live_build": builds["live"], "beta_build": builds["beta"], "foreverchanges": foreverchanges_snapshot()}
    pinned = pinned_build()
    STATE_FILE.write_text(json.dumps(new, indent=2) + "\n", encoding="utf-8")

    target = builds[PIN]
    pin_changed = target != pinned
    preview = builds["beta"] if PIN == "live" and builds["beta"] != target else ""
    print(f"Sim follows the {PIN} client, pinned to {pinned}{f' -> re-pin to {target}' if pin_changed else ''}")
    print(f"Live ({LIVE_PRODUCT}): {builds['live']}   Beta ({BETA_PRODUCT}): {builds['beta']}")
    for key in ("build", "new_items", "changed_items", "talents_changed"):
        old_v, new_v = (old.get("foreverchanges") or {}).get(key), new["foreverchanges"].get(key)
        if old and old_v != new_v:
            print(f"foreverchanges.pro {key}: {old_v!r} -> {new_v!r}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"pin_changed={'true' if pin_changed else 'false'}\n")
            f.write(f"pin_build={target}\n")
            f.write(f"pin_label={PIN}\n")
            f.write(f"preview_build={preview}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"data_watch.py failed: {e}", file=sys.stderr)
        sys.exit(1)
