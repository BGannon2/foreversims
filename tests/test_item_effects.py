"""Structured item effects (engine_data.ITEM_EFFECTS): each case equips the items, checks the
effect actually fires in the Python reference, and checks the Rust engine reproduces it exactly."""
import unittest

from forever.all_specs import public_specs, simulate_spec
from server import default_request
from tests import test_parity as parity

SPECS = {s["id"]: s for s in public_specs()}

# (spec, {slot: item id}, extra request fields, ability rows that must fire, buffs that must appear)
CASES = [
    ("warrior-fury", {"Trinket 1": 21180, "Trinket 2": 23570, "Main Hand": 11684}, {}, ["Item - Earthstrike", "Item - Jom Gabbar", "Melee (Extra Attack)"], []),
    ("warrior-fury", {"Trinket 1": 19951, "Trinket 2": 21670}, {}, ["Item - Gri'lek's Charm of Might", "Item - Badge of the Swarmguard"], ["Item - Insight of the Qiraji"]),
    ("warrior-arms", {"Main Hand": 17076}, {}, [], ["Item - Bonereaver's Edge"]),
    ("rogue-combat", {"Main Hand": 12590, "Off Hand": 13204, "Trinket 1": 19342, "Trinket 2": 19954}, {},
     ["Item - Venomous Totem", "Item - Renataki's Charm of Trickery"], ["Item - Felstriker", "Item - Puncture Armor"]),
    ("mage-arcane", {"Trinket 1": 19339, "Trinket 2": 19959}, {}, ["Item - Mind Quickening Gem", "Item - Hazza'rah's Charm of Magic"], []),
    ("mage-fire", {"Trinket 1": 22268, "Trinket 2": 19947}, {"targets": 3}, ["Item - Draconic Infused Emblem", "Item - Nat Pagle's Broken Reel"], []),
    ("mage-frost", {"Trinket 1": 11819, "Trinket 2": 21891}, {"targets": 3}, ["Item - Shard of the Fallen Star"], []),
    ("warlock-destruction", {"Trinket 1": 19957, "Trinket 2": 19337}, {}, ["Item - Hazza'rah's Charm of Destruction", "Item - The Black Book"], []),
    ("shaman-elemental", {"Trinket 1": 19344, "Head": 16667, "Chest": 16666, "Legs": 16668, "Shoulders": 16669, "Feet": 16670, "Wrist": 16671},
     {}, ["Item - Natural Alignment Crystal"], ["The Furious Storm"]),
    ("hunter-marksmanship", {"Trinket 1": 19953, "Trinket 2": 21670, "Ranged / Relic": 18282}, {}, ["Item - Badge of the Swarmguard"], ["Item - Insight of the Qiraji"]),
]


def request(spec_id, swaps, extra):
    spec = SPECS[spec_id]
    req = default_request(spec, spec["races"][0], iterations=6, duration=120, seed=77, **extra)
    for row in req["gear_slots"]:
        if row["slot"] in swaps: row["id"] = swaps[row["slot"]]
    req["gear"] = [row["id"] for row in req["gear_slots"]]
    return req


class ItemEffectTests(unittest.TestCase):
    def test_structured_effects_fire(self):
        for spec_id, swaps, extra, rows, buffs in CASES:
            with self.subTest(spec=spec_id, items=list(swaps.values())):
                out = simulate_spec(request(spec_id, swaps, extra))
                for name in rows:
                    self.assertGreater(out["ability_stats"].get(name, {}).get("casts", 0), 0, name)
                for name in buffs:
                    self.assertGreater(out["buff_uptimes"].get(name, 0), 0, name)

    def test_armor_shred_is_exclusive_with_faerie_fire(self):
        base = request("warrior-arms", {}, {})
        base["debuffs"] = [d for d in base["debuffs"] if d != "faerie_fire"] + ["faerie_fire"]
        from forever.all_specs import ENCHANTS, FOREVER_SETS, ITEMS
        from forever.engine import Config, Iteration
        it = Iteration(Config(base, ITEMS, ENCHANTS, FOREVER_SETS), 1, False)
        before = it.armor_mult()
        it.add_buff("Item - Puncture Armor", 30, stat="armorIgnore", value=200, stacks_max=3, exclusive="faerie_fire")
        self.assertAlmostEqual(before, it.armor_mult())  # 200 < Faerie Fire's 505: no extra reduction
        it.add_buff("Item - Puncture Armor", 30, stat="armorIgnore", value=200, stacks_max=3, exclusive="faerie_fire")
        it.add_buff("Item - Puncture Armor", 30, stat="armorIgnore", value=200, stacks_max=3, exclusive="faerie_fire")
        self.assertGreater(it.armor_mult(), before)  # 600 > 505: only the 95 difference applies


@unittest.skipUnless(parity.CLI.is_file(), "engine-rs CLI not built")
class ItemEffectRustParityTests(unittest.TestCase):
    assert_numeric_tree = parity.RustParityTests.assert_numeric_tree

    def test_structured_effects_match_python(self):
        for spec_id, swaps, extra, _, _ in CASES:
            with self.subTest(spec=spec_id, items=list(swaps.values())):
                req = request(spec_id, swaps, extra)
                py, rs = simulate_spec(req), parity.rust("spec", req)
                self.assertNotIn("error", rs)
                for key in ("metrics", "ability_stats", "buff_uptimes", "log"):
                    self.assert_numeric_tree(py[key], rs[key], f"{spec_id}.{key}")
