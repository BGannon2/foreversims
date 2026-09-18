"""Regenerate the race/spec comparison snapshot from the saved simulator defaults.

Usage: python generate_benchmarks.py [iterations]
Every race per spec, at every target count in server.TARGET_COUNTS (1/2/3/4/5; 1 is the
original single-target Patchwerk snapshot). Uses server.DEFAULTS (120 s Patchwerk, default
gear/talents/buffs/consumables, seed 917) and 300 iterations unless another count is given.
Rows are computed in parallel across CPU cores (each spec/race/target-count is an independent
simulation) via ProcessPoolExecutor.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import server

# Windows' multiprocessing "spawn" start method re-imports this file as a fresh module in each
# worker process; without this guard, that re-import would re-run the whole script (including
# starting its own pool) in every worker.
if __name__ == "__main__":
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else server.DEFAULTS["benchmark_iterations"]
    target = ROOT / "data" / "benchmarks.json"
    payload = server.build_benchmarks(iterations)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload['rows'])} benchmark rows ({payload['duration']} s, {iterations} iterations, "
          f"targets {payload['target_counts']}) to {target}")
