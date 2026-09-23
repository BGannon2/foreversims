"""Compare the Python reference engines with the Rust port (engine-rs CLI).

Runs every shared-engine spec and both Paladin specs through both engines with
the same seed and prints DPS / TPS from each plus the relative difference.  The
Rust engine reproduces CPython's Mersenne Twister, so with identical RNG call
order the numbers should agree to floating-point noise.

Usage:  python tools/parity_check.py [--iterations N] [--duration S] [--spec ID ...]
Exit status 1 if any spec differs by more than --tolerance (default 0.5%).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CLI = ROOT / "engine-rs" / "target" / "release" / ("forever-sim.exe" if os.name == "nt" else "forever-sim")


def run_rust(kind: str, payload: dict) -> dict:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(payload, fh)
        path = fh.name
    try:
        out = subprocess.run([str(CLI), kind, path, "--data", str(ROOT / "web" / "data")], capture_output=True, text=True, encoding="utf-8", check=True)
        return json.loads(out.stdout)
    finally:
        os.unlink(path)


def compare(task):
    """Python and Rust results for one (label, kind, payload) task, run in a worker process."""
    _, kind, payload = task
    from forever.all_specs import simulate_spec
    from forever.sim import simulate
    return (simulate_spec if kind == "spec" else simulate)(payload), run_rust(kind, payload)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iterations", type=int, default=20)
    ap.add_argument("--duration", type=float, default=60)
    ap.add_argument("--tolerance", type=float, default=0.005)
    ap.add_argument("--spec", nargs="*")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if not CLI.is_file():
        print(f"Rust CLI not built: {CLI}\nRun: cd engine-rs && cargo build --release")
        return 2
    from forever.all_specs import public_specs
    from forever.engine_data import CLASS_RACES
    from forever.sim import preset
    from server import default_request

    tasks = []
    for spec in public_specs():
        if args.spec and spec["id"] not in args.spec:
            continue
        race = spec["races"][0] if "Human" not in spec["races"] else "Human"
        tasks.append((spec["id"], "spec", default_request(spec, race, iterations=args.iterations, duration=args.duration, seed=917)))
    for spec_id in ("protection", "retribution"):
        if args.spec and f"paladin-{spec_id}" not in args.spec:
            continue
        for race in CLASS_RACES["Paladin"][:1]:
            profile = preset(spec_id); profile["race"] = race; profile["iterations"] = args.iterations; profile["duration"] = args.duration; profile["seed"] = 917
            tasks.append((f"paladin-{spec_id}", "paladin", profile))
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:  # each comparison is independent
        results = list(pool.map(compare, tasks, chunksize=1))
    rows = []
    for (sid, _, _), (py, rs) in zip(tasks, results):
        if "error" in rs:
            rows.append((sid, py["metrics"]["dps"]["mean"], None, None, None, rs["error"]))
            continue
        rows.append((sid, py["metrics"]["dps"]["mean"], rs["metrics"]["dps"]["mean"], py["metrics"]["tps"]["mean"], rs["metrics"]["tps"]["mean"], None))
        if args.verbose:
            for name in py["ability_dps"]:
                a, b = py["ability_dps"][name], rs["ability_dps"].get(name)
                print(f"    {sid:22} {name:28} py={a:10.3f} rs={b if b is None else round(b, 3)}")
    bad = 0
    print(f"{'spec':24} {'py dps':>10} {'rs dps':>10} {'diff':>8}   {'py tps':>10} {'rs tps':>10}")
    for sid, pd, rd, pt, rt, err in rows:
        if err:
            print(f"{sid:24} {pd:10.2f} {'ERROR':>10}   {err}")
            bad += 1
            continue
        diff = max(abs(rd - pd) / max(abs(pd), 1e-9), abs(rt - pt) / max(abs(pt), 1e-9))
        flag = "" if diff <= args.tolerance else "  <-- MISMATCH"
        if flag:
            bad += 1
        print(f"{sid:24} {pd:10.2f} {rd:10.2f} {diff * 100:7.3f}%   {pt:10.2f} {rt:10.2f}{flag}")
    print(f"\n{len(rows) - bad}/{len(rows)} within {args.tolerance * 100:g}%")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
