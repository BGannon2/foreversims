"""Alliance/Horde-only gear is limited to its faction's races in every engine."""
import unittest

from forever import gear_data, sim
from forever.all_specs import ITEMS, public_specs, simulate_spec
from forever.profile_rules import faction_allowed
from server import default_request
from tests import test_parity as parity

HIGH_WARLORD_BLADE = next(i for i in ITEMS.values() if i["name"] == "High Warlord's Quickblade")
GRAND_MARSHAL_BLADE = next(i for i in ITEMS.values() if i["name"] == "Grand Marshal's Swiftblade")


def fury(race, main_hand):
    spec = next(s for s in public_specs() if s["id"] == "warrior-fury")
    req = default_request(spec, race, iterations=2, duration=30)
    for row in req["gear_slots"]:
        if row["slot"] == "Main Hand": row["id"] = main_hand
    req["gear"] = [row["id"] for row in req["gear_slots"]]
    return req


class FactionTests(unittest.TestCase):
    def test_tags_and_twins(self):
        self.assertEqual(HIGH_WARLORD_BLADE["faction"], "Horde")
        self.assertEqual(GRAND_MARSHAL_BLADE["faction"], "Alliance")
        self.assertEqual(next(i for i in ITEMS.values() if i["name"] == "Talisman of Arathor")["faction"], "Alliance")
        self.assertNotIn("faction", next(i for i in ITEMS.values() if i["name"] == "Hive Defiler Wristguards"))
        chest = next(i for i in ITEMS.values() if i["name"] == "Legionnaire's Dragonhide Chestpiece")
        self.assertEqual(ITEMS[chest["factionTwin"]]["name"], "Knight-Captain's Dragonhide Chestpiece")
        self.assertTrue(faction_allowed(HIGH_WARLORD_BLADE, "Orc"))
        self.assertTrue(faction_allowed(HIGH_WARLORD_BLADE, "Skyborne (Horde)"))
        self.assertFalse(faction_allowed(HIGH_WARLORD_BLADE, "Human"))

    def test_shared_engine_rejects_other_faction(self):
        with self.assertRaisesRegex(ValueError, "Horde-only"):
            simulate_spec(fury("Human", HIGH_WARLORD_BLADE["id"]))
        self.assertIn("metrics", simulate_spec(fury("Orc", HIGH_WARLORD_BLADE["id"])))

    def test_paladin_engine_rejects_other_faction(self):
        p = sim.preset("protection"); p["iterations"] = 2; p["race"] = "Undead"
        p["gear"] = gear_data.phase6_gear("protection"); p["gear"]["main_hand"] = GRAND_MARSHAL_BLADE["id"]
        with self.assertRaisesRegex(ValueError, "Alliance-only"):
            sim.simulate(sim.validate(p))

    def test_presets_match_their_default_race(self):
        for spec in public_specs():
            simulate_spec(default_request(spec, spec["races"][0], iterations=1, duration=10))

    @unittest.skipUnless(parity.CLI.is_file(), "engine-rs CLI not built")
    def test_rust_rejects_other_faction(self):
        self.assertIn("Horde-only", parity.rust("spec", fury("Human", HIGH_WARLORD_BLADE["id"])).get("error", ""))
        self.assertNotIn("error", parity.rust("spec", fury("Orc", HIGH_WARLORD_BLADE["id"])))

    @unittest.skipUnless(parity.CLI.is_file(), "engine-rs CLI not built")
    def test_rust_paladin_rejects_other_faction(self):
        p = sim.preset("protection"); p["iterations"] = 2; p["race"] = "Undead"
        p["gear"] = gear_data.phase6_gear("protection"); p["gear"]["main_hand"] = GRAND_MARSHAL_BLADE["id"]
        self.assertIn("Alliance-only", parity.rust("paladin", p).get("error", ""))
