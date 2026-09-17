"""Regenerate the race/spec comparison snapshot from the saved simulator defaults.

Usage: python generate_benchmarks.py [iterations]
The snapshot uses server.DEFAULTS (120 s Patchwerk, default gear/talents/buffs/consumables,
seed 917) and 300 iterations unless another count is given.
"""
import json
import sys
from pathlib import Path

import server

iterations = int(sys.argv[1]) if len(sys.argv) > 1 else server.DEFAULTS["benchmark_iterations"]
target = Path(__file__).parent / "benchmarks.json"
payload = server.build_benchmarks(iterations)
target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"Wrote {len(payload['rows'])} benchmark rows ({payload['duration']} s, {iterations} iterations) to {target}")
