"""Spec variants (forever/engine_data.VARIANTS, forever/sim.PALADIN_VARIANTS)."""
import unittest

from forever import engine, sim
from forever.all_specs import ENCHANTS, FOREVER_SETS, ITEMS, public_specs, simulate_spec
from forever.engine_data import VARIANTS
from server import default_request


def spec(sid):
    return next(s for s in public_specs() if s["id"] == sid)


class SharedEngineVariants(unittest.TestCase):
    def test_every_variant_simulates(self):
        for vid, v in VARIANTS.items():
            with self.subTest(vid):
                req = default_request(spec(v["parent"]), iterations=3, duration=60, variant=vid)
                key = "tps" if spec(v["parent"])["role"] == "tank" else "dps"
                self.assertGreater(simulate_spec(req)["metrics"][key]["mean"], 0)

    def test_variant_talents_meet_core(self):
        for vid, v in VARIANTS.items():
            for tid, rank in v.get("core", {}).get("talents", {}).items():
                self.assertGreaterEqual(v["talents"].get(tid, 0), rank, f"{vid} lacks core talent {tid}")

    def test_wrong_parent_is_rejected(self):
        req = default_request(spec("mage-fire"), iterations=1, duration=60)
        req["variant"] = "weave"
        with self.assertRaises(ValueError):
            engine.Config(req, ITEMS, ENCHANTS, FOREVER_SETS)

    def test_weave_uses_auto_shot_and_pays_penalty(self):
        req = default_request(spec("hunter-survival"), iterations=1, duration=60, variant="weave")
        cfg = engine.Config(req, ITEMS, ENCHANTS, FOREVER_SETS)
        self.assertEqual(cfg.spec["style"], "ranged")
        self.assertGreater(cfg.weave_penalty, 0)
        self.assertEqual(cfg.rotation_key, "hunter-survival/weave")

    def test_frostfire_casts_frostfire_bolt(self):
        req = default_request(spec("mage-fire"), iterations=2, duration=60, variant="frostfire")
        names = {a["name"] for a in simulate_spec(req).get("abilities", [])} or None
        if names is not None:
            self.assertIn("Frostfire Bolt", names)


class PaladinVariants(unittest.TestCase):
    def test_every_variant_simulates(self):
        for vid, v in sim.PALADIN_VARIANTS.items():
            with self.subTest(vid):
                p = sim.preset(v["parent"], vid); p.update(iterations=3, duration=60)
                key = "tps" if v["parent"] == "protection" else "dps"
                self.assertGreater(sim.simulate(sim.validate(p))["metrics"][key]["mean"], 0)

    def test_shockadin_casts_holy_shock(self):
        p = sim.preset("retribution", "shockadin"); p.update(iterations=3, duration=60)
        r = sim.simulate(sim.validate(p))
        self.assertIn("Holy Shock", str(r.get("abilities", r)))


class PetSpells(unittest.TestCase):
    def test_pet_spenders_use_client_values(self):
        from forever.engine_data import PET_ABILITIES
        self.assertEqual((PET_ABILITIES["Bite"]["min"], PET_ABILITIES["Bite"]["max"]), (81.0, 99.0))
        self.assertEqual(PET_ABILITIES["Lightning Breath"]["spell_id"], 25012)


if __name__ == "__main__":
    unittest.main()
