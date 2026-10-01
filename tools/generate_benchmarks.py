"""Regenerate the race/spec comparison snapshot from the saved simulator defaults.

Usage: python tools/generate_benchmarks.py [iterations] [--only TAG [TAG ...]]
Every race per spec, at every target count in server.TARGET_COUNTS (1/2/3/4/5; 1 is the
original single-target Patchwerk snapshot). Uses server.DEFAULTS (120 s Patchwerk, default
gear/talents/buffs/consumables, seed 917) and 300 iterations unless another count is given.

--only reruns just the matching specs and keeps every other row of data/benchmarks.json as
it is. A tag is a spec id (druid-feral-tank), a class (druid, paladin), a role (tank, dps)
or a style (melee, ranged, spell); several tags select their union. Example:
    python tools/generate_benchmarks.py --only warrior paladin-protection
Rows are computed in parallel across CPU cores via ProcessPoolExecutor.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server


def spec_tags():
    """Every benchmarked spec id -> the tags that select it."""
    tags = {}
    for spec in server.public_specs():
        tags[spec["id"]] = {spec["id"], spec["class_name"].lower(), spec["role"], spec["style"]}
    tags["paladin-protection"] = {"paladin-protection", "paladin", "tank", "melee"}
    tags["paladin-retribution"] = {"paladin-retribution", "paladin", "dps", "melee"}
    return tags


def select(only):
    tags = spec_tags()
    wanted = {t.lower() for t in only}
    unknown = wanted - set().union(*tags.values())
    if unknown:
        sys.exit(f"Unknown tag(s): {', '.join(sorted(unknown))}. Use a spec id, class, role (tank/dps) or style (melee/ranged/spell).")
    return {sid for sid, t in tags.items() if t & wanted}


# Windows' multiprocessing "spawn" start method re-imports this file as a fresh module in each
# worker process; without this guard, that re-import would re-run the whole script (including
# starting its own pool) in every worker.
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regenerate data/benchmarks.json.")
    parser.add_argument("iterations", nargs="?", type=int, default=server.DEFAULTS["benchmark_iterations"])
    parser.add_argument("--only", nargs="+", metavar="TAG", help="rerun only specs matching these tags; keep the other rows")
    args = parser.parse_args()
    target = ROOT / "data" / "benchmarks.json"
    only = select(args.only) if args.only else None
    payload = server.build_benchmarks(args.iterations, only=only)
    if only is not None:
        old = json.loads(target.read_text(encoding="utf-8"))
        if old.get("iterations") != args.iterations:
            sys.exit(f"Existing snapshot used {old.get('iterations')} iterations; rerun everything (no --only) to change the count.")
        fresh = {(r["id"], r["race"], r["targets"]): r for r in payload["rows"]}
        rows = [fresh.pop((r["id"], r["race"], r["targets"]), r) if r["id"] in only else r for r in old["rows"]]
        rows += fresh.values()  # races or specs that weren't in the old snapshot
        payload = {**old, "rows": rows}
        print(f"Reran {len(payload['rows']) - sum(1 for r in rows if r['id'] not in only)} rows for: {', '.join(sorted(only))}")
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload['rows'])} benchmark rows ({payload['duration']} s, {args.iterations} iterations, "
          f"targets {payload['target_counts']}) to {target}")
