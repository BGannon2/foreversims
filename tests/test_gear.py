import copy
import unittest

from forever.gear_data import CATALOG, FOREVER_SETS, ITEMS, PHASE6_BIS, apply_gear, empty_gear
from forever.sim import preset, simulate


class GearTests(unittest.TestCase):
    def test_catalog_is_pre_tbc_classic_snapshot(self):
        self.assertTrue(CATALOG["version"].startswith("wow-classic-items-e848aab57261"))
        self.assertGreater(len(ITEMS), 2000)
        self.assertTrue(all(45 <= item["requiredLevel"] <= 60 or item["id"] in {18404, 21180}
                            for item in ITEMS.values()))
        self.assertTrue(all(item["quality"] in {"Rare", "Epic", "Legendary"} for item in ITEMS.values()))

    def test_known_original_cloak_stats(self):
        cloak = ITEMS[23050]
        self.assertEqual(cloak["name"], "Cloak of the Necropolis")
        self.assertEqual(cloak["stats"]["intellect"], 11)
        self.assertEqual(cloak["stats"]["stamina"], 12)
        self.assertEqual(cloak["stats"]["spellPower"], 26)
        self.assertEqual(cloak["stats"]["spellHit"], 1)
        self.assertEqual(cloak["stats"]["spellCrit"], 1)

    def test_set_metadata_and_equipped_counts(self):
        crown = ITEMS[21387]
        self.assertEqual(crown["set"]["name"], "Avenger's Battlegear")
        self.assertEqual(len(crown["set"]["pieces"]), 5)
        self.assertEqual([b["required"] for b in crown["set"]["bonuses"]], [3, 5])
        self.assertEqual(crown["set"]["ruleset"], "Forever")
        self.assertEqual(crown["set"]["bonuses"][1]["stats"]["spellPower"], 71)
        profile=preset("protection");profile["gear"]=empty_gear()
        profile["gear"].update(head=21387,shoulders=21391,chest=21389,legs=21390,feet=21388)
        _, summary = apply_gear(profile)
        avengers = next(s for s in summary["sets"] if s["name"] == "Avenger's Battlegear")
        self.assertEqual((avengers["count"], avengers["total"]), (5, 5))
        self.assertTrue(all(b["active"] for b in avengers["bonuses"]))
        self.assertEqual(avengers["ruleset"], "Forever")

    def test_forever_avengers_bonus_changes_the_algorithm(self):
        profile = preset("protection")
        profile["gear"]=empty_gear()
        profile["gear"].update(head=21387,shoulders=21391,chest=21389,legs=21390,feet=21388)
        effective, summary = apply_gear(profile)
        # 85 on equipped items + 36 Wizard Oil + 71 from the Forever 5-piece.
        self.assertEqual(effective["character"]["spell_power"], 192)
        bonus = next(b for b in summary["active_forever_set_bonuses"]
                     if b["set"] == "Avenger's Battlegear" and b["required"] == 5)
        self.assertEqual(bonus["stats"]["spellPower"], 71)
        self.assertTrue(bonus["modeled"])

    def test_revised_forever_dungeon_sets_are_registered(self):
        self.assertEqual([b["required"] for b in FOREVER_SETS["sets"]["Lightforge Armor"]["bonuses"]],
                         [2, 3, 4, 5, 6])
        self.assertEqual([b["required"] for b in FOREVER_SETS["sets"]["Soulforge Armor"]["bonuses"]],
                         [2, 3, 5, 6])

    def test_empty_gear_does_not_change_character(self):
        profile = preset("protection")
        profile["model"]["use_classic_era_conversions"] = False
        profile["gear"] = empty_gear()
        effective, summary = apply_gear(profile)
        for key, value in profile["character"].items():
            self.assertEqual(effective["character"][key], 0 if key == 'block_chance' else value)
        self.assertFalse(effective["character"]['has_shield'])
        self.assertEqual(summary["equipped"], [])

    def test_weapon_and_direct_stats_are_applied(self):
        profile = preset("retribution")
        profile["model"]["use_classic_era_conversions"] = False
        profile["gear"] = empty_gear()
        weapon = next(item for item in ITEMS.values()
                      if item["slot"] == "Two-Hand" and item["weaponDamageMin"] is not None)
        profile["gear"]["main_hand"] = weapon["id"]
        profile["gear"]["back"] = 23050
        effective, summary = apply_gear(profile)
        self.assertEqual(effective["character"]["weapon_min"], weapon["weaponDamageMin"])
        self.assertEqual(effective["character"]["weapon_speed"], weapon["weaponSpeed"])
        self.assertAlmostEqual(effective["character"]["spell_hit_chance"], .84)
        self.assertAlmostEqual(effective["character"]["spell_crit_chance"], .045)
        self.assertEqual(effective["character"]["mana"], profile["character"]["mana"])
        self.assertEqual(summary["unmodeled_totals"]["intellect"], 11)

    def test_two_hand_and_off_hand_is_rejected(self):
        profile = preset("protection")
        profile["gear"] = empty_gear()
        two_hand = next(item for item in ITEMS.values() if item["slot"] == "Two-Hand")
        off_hand = next(item for item in ITEMS.values() if "off_hand" in item["equipSlots"])
        profile["gear"]["main_hand"] = two_hand["id"]
        profile["gear"]["off_hand"] = off_hand["id"]
        with self.assertRaisesRegex(ValueError, "two-handed"):
            apply_gear(profile)

    def test_simulation_preserves_input_and_reports_effective_character(self):
        profile = preset("retribution")
        profile["model"]["use_classic_era_conversions"] = False
        profile["gear"] = empty_gear()
        profile["duration"] = 5
        profile["iterations"] = 1
        profile["gear"]["back"] = 23050
        original = copy.deepcopy(profile)
        result = simulate(profile)
        self.assertEqual(result["profile"], original)
        self.assertEqual(result["gear_summary"]["equipped"][0]["id"], 23050)
        self.assertAlmostEqual(result["effective_character"]["spell_hit_chance"], .84)

    def test_presets_use_complete_sourced_phase12_loadouts(self):
        for spec in ("protection", "retribution"):
            with self.subTest(spec=spec):
                profile = preset(spec)
                self.assertEqual(profile["gear"], PHASE6_BIS[spec]["gear"])
                self.assertNotEqual(profile["gear"]["relic"], 0)
                self.assertEqual(PHASE6_BIS[spec]["source"],"https://github.com/wowsims/classic")
                for slot, item_id in profile["gear"].items():
                    if item_id:
                        self.assertIn(item_id, ITEMS)
                        self.assertIn(slot, ITEMS[item_id]["equipSlots"])


if __name__ == "__main__":
    unittest.main()
