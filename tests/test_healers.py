"""Healer model: HPS until the fight ends, mana-paced rotations (priest-holy)."""
import unittest

from forever.all_specs import public_specs, simulate_spec
from server import default_request


def holy(**over):
    spec = next(s for s in public_specs() if s["id"] == "priest-holy")
    return simulate_spec(default_request(spec, iterations=20, duration=120, **over))


class HolyPriest(unittest.TestCase):
    def test_hps_reported_and_mana_paced(self):
        r = holy()
        self.assertGreater(r["metrics"]["hps"]["mean"], 300)
        self.assertEqual(r["metrics"]["hps"]["mean"], r["metrics"]["dps"]["mean"])
        self.assertLess(r["resource"]["mean_end"], 0.15 * r["resource"]["maximum"])  # spends its mana over the fight

    def test_group_heals_scale_with_injured_allies(self):
        self.assertGreater(holy(targets=5)["metrics"]["hps"]["mean"], holy(targets=1)["metrics"]["hps"]["mean"] * 1.3)

    def test_dps_specs_report_zero_hps(self):
        spec = next(s for s in public_specs() if s["id"] == "priest-shadow")
        self.assertEqual(simulate_spec(default_request(spec, iterations=2, duration=30))["metrics"]["hps"]["mean"], 0)


HEALERS = ("priest-holy", "druid-restoration", "shaman-restoration", "paladin-holy")


class AllHealers(unittest.TestCase):
    def test_every_healer_heals_and_spends_mana(self):
        for sid in HEALERS:
            with self.subTest(sid):
                spec = next(s for s in public_specs() if s["id"] == sid)
                self.assertEqual(spec["role"], "healer")
                r = simulate_spec(default_request(spec, iterations=10, duration=120, targets=3))
                self.assertGreater(r["metrics"]["hps"]["mean"], 200)
                self.assertLess(r["resource"]["mean_end"], 0.25 * r["resource"]["maximum"])

    def test_wild_growth_scales_with_allies(self):
        for sid in ("druid-restoration",):
            spec = next(s for s in public_specs() if s["id"] == sid)
            one = simulate_spec(default_request(spec, iterations=20, duration=120, targets=1))["metrics"]["hps"]["mean"]
            three = simulate_spec(default_request(spec, iterations=20, duration=120, targets=3))["metrics"]["hps"]["mean"]
            self.assertGreater(three, one * 1.15, sid)


class DataHygiene(unittest.TestCase):
    def test_talent_effects_have_no_duplicate_keys(self):
        """A repeated key in the TALENT_EFFECTS literal silently drops the earlier entry."""
        import ast
        from pathlib import Path
        tree = ast.parse((Path(__file__).resolve().parents[1] / "forever" / "engine_data.py").read_text(encoding="utf-8"))
        node = next(n.value for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", None) == "TALENT_EFFECTS")
        keys = [k.value for k in node.keys]
        self.assertEqual(sorted({k for k in keys if keys.count(k) > 1}), [])


if __name__ == "__main__":
    unittest.main()
