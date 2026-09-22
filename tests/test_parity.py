"""Rust engine parity and static-export freshness tests.

The Rust/WebAssembly engine (engine-rs) must reproduce the Python reference
exactly: same seeds, same RNG draw order, same numbers.  These tests run the
native CLI build when present and skip otherwise.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "engine-rs" / "target" / "release" / ("forever-sim.exe" if os.name == "nt" else "forever-sim")


def rust(kind, payload):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(payload, fh)
        path = fh.name
    try:
        out = subprocess.run([str(CLI), kind, path, "--data", str(ROOT / "web" / "data")], capture_output=True, text=True, encoding="utf-8", check=True)
        return json.loads(out.stdout)
    finally:
        os.unlink(path)


@unittest.skipUnless(CLI.is_file(), "engine-rs CLI not built (cd engine-rs && cargo build --release)")
class RustParityTests(unittest.TestCase):
    def assert_numeric_tree(self, expected, actual, path):
        if isinstance(expected, (float, int)) and not isinstance(expected, bool):
            self.assertIsInstance(actual, (float, int), path)
            tolerance = (.100000001 if path.endswith('.resource') else .010000001 if path.endswith('.time') else .001000001) if '.log.' in path else 1e-6
            self.assertAlmostEqual(expected, actual, delta=tolerance, msg=path)
        elif isinstance(expected, str) and '.log.' in path:
            self.assertEqual(expected, actual, path)
        elif isinstance(expected, dict):
            for key, value in expected.items():
                self.assert_numeric_tree(value, actual.get(key), f'{path}.{key}')
        elif isinstance(expected, list):
            self.assertEqual(len(expected), len(actual), path)
            for i, value in enumerate(expected): self.assert_numeric_tree(value, actual[i], f'{path}.{i}')

    def test_shared_engine_specs_match_python_exactly(self):
        from forever.all_specs import public_specs, simulate_spec
        from server import default_request
        for spec in public_specs():
            sid = spec['id']
            req = default_request(spec, spec["races"][0], iterations=4, duration=45, seed=31)
            py, rs = simulate_spec(req), rust("spec", req)
            self.assertNotIn("error", rs, sid)
            self.assertAlmostEqual(py["metrics"]["dps"]["mean"], rs["metrics"]["dps"]["mean"], places=6, msg=sid)
            self.assertAlmostEqual(py["metrics"]["tps"]["mean"], rs["metrics"]["tps"]["mean"], places=6, msg=sid)
            self.assertEqual(set(py["ability_dps"]), set(rs["ability_dps"]), sid)
            for name, value in py["ability_dps"].items():
                self.assertAlmostEqual(value, rs["ability_dps"][name], places=6, msg=f"{sid}: {name}")
            self.assertEqual(len(py["log"]), len(rs["log"]), sid)
            for key in ('metrics', 'ability_stats', 'log', 'taken_dtps'):
                if key in py: self.assert_numeric_tree(py[key], rs[key], f'{sid}.{key}')

    def test_paladin_matches_python_exactly(self):
        from forever.sim import preset, simulate
        for spec_id in ("protection", "retribution"):
            profile = preset(spec_id); profile["iterations"] = 4; profile["duration"] = 45; profile["seed"] = 31; profile["race"] = "Dwarf"
            py, rs = simulate(profile), rust("paladin", profile)
            self.assertNotIn("error", rs, spec_id)
            for key in ("dps", "tps", "dtps", "alive_dtps", "ending_mana"):
                self.assertAlmostEqual(py["metrics"][key]["mean"], rs["metrics"][key]["mean"], places=6, msg=f"{spec_id}: {key}")
            self.assertEqual(list(py["ability_dps"]), list(rs["ability_dps"]), spec_id)
            self.assertEqual(py["gear_summary"]["totals"], rs["gear_summary"]["totals"], spec_id)
            for key in ('metrics', 'ability_damage', 'log'):
                if key in py: self.assert_numeric_tree(py[key], rs[key], f'{spec_id}.{key}')

    def test_rust_reports_validation_errors(self):
        from forever.sim import preset
        profile = preset("protection"); profile["iterations"] = 0
        self.assertIn("iterations must be", rust("paladin", profile)["error"])
        self.assertIn("supported Forever", rust("spec", {"spec": "nope"})["error"])


class StaticExportTests(unittest.TestCase):
    """web/data must match what the Python API would serve right now."""

    def test_static_payloads_are_current(self):
        import sys
        sys.path.insert(0, str(ROOT / "tools"))
        import export_static_data as exp
        payloads = exp.api_payloads()
        for name in ("specs", "spec-bootstrap", "bootstrap"):
            path = ROOT / "web" / "data" / f"{name}.json"
            self.assertTrue(path.is_file(), f"missing {path}; run python tools/export_static_data.py")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), json.loads(json.dumps(payloads[name])), f"{name}.json is stale; run python tools/export_static_data.py")
        for name in ("engine_data", "paladin_data"):
            path = ROOT / "engine-rs" / "data" / f"{name}.json"
            current = exp.engine_tables() if name == "engine_data" else exp.paladin_tables()
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), json.loads(json.dumps(current)), f"{name}.json is stale; run python tools/export_static_data.py and rebuild the engine")


if __name__ == "__main__":
    unittest.main()
