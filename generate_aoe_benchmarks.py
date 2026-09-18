"""Regenerate the AoE (multi-target) comparison snapshot from the saved simulator defaults.

Usage: python generate_aoe_benchmarks.py [iterations]
One representative race per spec (Human where available, else the spec's first race), run at
each of server.AOE_TARGET_COUNTS (2/3/4/5), 300 iterations unless another count is given.
"""
import json
import sys
from pathlib import Path

import server

iterations = int(sys.argv[1]) if len(sys.argv) > 1 else server.DEFAULTS["benchmark_iterations"]
target = Path(__file__).parent / "aoe_benchmarks.json"
payload = server.build_aoe_benchmarks(iterations)
target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"Wrote {len(payload['rows'])} AoE benchmark rows ({payload['duration']} s, {iterations} iterations, "
      f"targets {payload['target_counts']}) to {target}")
