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


if __name__ == "__main__":
    unittest.main()
