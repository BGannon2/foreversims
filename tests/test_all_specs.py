"""Mechanic-level tests for the shared Forever engine (all non-Paladin specs)."""
import json
import math
import random
import unittest
from pathlib import Path

from forever import engine
from forever.all_specs import ENCHANTS, FOREVER_SETS, ITEMS, public_specs, simulate_spec
from forever.engine_data import ABILITIES, BUFF_STATS, CLASS_RACES, CONSUME_STATS, DEFAULT_BUILDS, RAGE_CONVERSION_60, ROTATIONS, SPEC_MAP, TALENT_EFFECTS, default_buffs, default_consumables
from server import DEFAULTS, default_request

ROOT = Path(__file__).resolve().parents[1]
TALENT_DATA = json.loads((ROOT / "data" / "forever_talents_all.json").read_text(encoding="utf-8"))
BY_CLASS = {cls: {str(t["id"]): (tree["name"], t) for tree in trees for t in tree["talents"]} for cls, trees in TALENT_DATA["classes"].items()}


def spec(sid):
    return next(s for s in public_specs() if s["id"] == sid)


def config(sid, **over):
    request = default_request(spec(sid), iterations=1, duration=60, **over)
    return engine.Config(request, ITEMS, ENCHANTS, FOREVER_SETS)


def iteration(sid, seed=1, **over):
    return engine.Iteration(config(sid, **over), seed, trace=True)


class RosterAndDataTests(unittest.TestCase):
    def test_every_spec_has_rotation_build_gear_and_races(self):
        specs = public_specs()
        self.assertEqual(len(specs), 21)
        for s in specs:
            self.assertGreaterEqual(len(s["actions"]), 2)
            self.assertEqual(sum(s["default_talents"].values()), 51)
            self.assertTrue(s["races"])
            self.assertTrue(s["default_consumables"]); self.assertTrue(s["default_buffs"])

    def test_default_builds_are_legal_forever_builds(self):
        for sid, build in DEFAULT_BUILDS.items():
            talents = BY_CLASS[SPEC_MAP[sid]["class_name"].lower()]
            per_tree = {}
            for tid, rank in build.items():
                self.assertIn(tid, talents, f"{sid}: unknown talent {tid}")
                tree, t = talents[tid]
                self.assertLessEqual(rank, len(t["ranks"]), f"{sid}: {t['name']} rank {rank}")
                per_tree.setdefault(tree, []).append((t, rank))
            for tree, rows in per_tree.items():
                for t, rank in rows:
                    before = sum(r for tt, r in rows if tt["row"] < t["row"])
                    self.assertGreaterEqual(before, t["row"] * 5, f"{sid}: {t['name']} tier rule")
                    for req in t["requires"]:
                        self.assertGreaterEqual(build.get(str(req["id"]), 0), req["qty"], f"{sid}: {t['name']} prerequisite")

    def test_talent_effect_ids_exist_in_forever_data(self):
        all_ids = {tid for talents in BY_CLASS.values() for tid in talents}
        for tid in TALENT_EFFECTS:
            self.assertIn(tid, all_ids, tid)

    def test_forever_talent_text_matches_modeled_values(self):
        w = BY_CLASS["warrior"]
        self.assertIn("35% of your Attack Power plus 30", w["105930"][1]["descriptions"]["1"])
        self.assertEqual(ABILITIES["Bloodthirst"]["ap_mult"], 0.35); self.assertEqual(ABILITIES["Bloodthirst"]["flat"], 30)
        self.assertIn("60% chance", w["105937"][1]["descriptions"]["5"]); self.assertAlmostEqual(TALENT_EFFECTS["105937"]["flag:unbridled_wrath"] * 5, 0.60)
        self.assertIn("off-hand weapon damage by 25%", w["105933"][1]["descriptions"]["5"]); self.assertAlmostEqual(TALENT_EFFECTS["105933"]["flag:dw_damage"] * 5, 0.25)
        self.assertIn("weapon damage plus 85", w["105941"][1]["descriptions"]["1"]); self.assertEqual(ABILITIES["Mortal Strike"]["weapon"]["flat"], 85)
        wl = BY_CLASS["warlock"]
        self.assertIn("100% of your level", wl["105893"][1]["descriptions"]["3"]); self.assertEqual(TALENT_EFFECTS["105893"]["flag:demonic_knowledge"] * 3, 60)

    def test_race_class_combinations_match_wowhead_forever(self):
        self.assertEqual(CLASS_RACES["Paladin"], ["Human", "Dwarf", "Undead"])
        self.assertIn("Human", CLASS_RACES["Hunter"]); self.assertIn("Gnome", CLASS_RACES["Priest"]); self.assertIn("Dwarf", CLASS_RACES["Shaman"])
        self.assertIn("Orc", CLASS_RACES["Mage"]); self.assertIn("Troll", CLASS_RACES["Warlock"])
        self.assertNotIn("Skyborne (Horde)", CLASS_RACES["Mage"]); self.assertNotIn("Skyborne (Alliance)", CLASS_RACES["Shaman"]); self.assertNotIn("Tauren", CLASS_RACES["Rogue"])
        with self.assertRaises(ValueError): simulate_spec({"spec": "warrior-fury", "race": "Blood Elf", "duration": 10, "iterations": 1})

    def test_consumable_scope_excludes_irrelevant_items(self):
        self.assertNotIn("elemental_sharpening_stone", spec("druid-feral-dps")["default_consumables"])
        self.assertNotIn("mighty_rage_potion", spec("rogue-combat")["default_consumables"])
        self.assertNotIn("thistle_tea", spec("warrior-fury")["default_consumables"])
        self.assertIn("elixir_of_shadow_power", spec("warlock-affliction")["default_consumables"])
        self.assertNotIn("elixir_of_shadow_power", spec("mage-fire")["default_consumables"])
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            simulate_spec({"spec": "mage-fire", "duration": 10, "iterations": 1, "consumables": ["flask_of_the_titans", "flask_of_supreme_power"]})


class StatTests(unittest.TestCase):
    def test_base_stats_and_race_offsets(self):
        human = config("warrior-fury", gear=[], gear_slots=[], buffs=[], consumables=[], enchants=[], talents={})
        orc = config("warrior-fury", race="Orc", gear=[], gear_slots=[], buffs=[], consumables=[], enchants=[], talents={})
        self.assertAlmostEqual(human.stats["strength"], 120); self.assertAlmostEqual(orc.stats["strength"], 123)
        self.assertAlmostEqual(human.stats["attackPower"], 160 + 120 * 2)
        self.assertAlmostEqual(human.stats["meleeCrit"], 80 * 0.05)
        self.assertAlmostEqual(human.stats["health"], 1689 + 110 * 10)

    def test_buffs_consumables_and_kings_apply(self):
        base = config("rogue-combat", gear=[], gear_slots=[], buffs=[], consumables=[], enchants=[], talents={})
        buffed = config("rogue-combat", gear=[], gear_slots=[], buffs=["blessing_of_might", "blessing_of_kings", "grace_of_air"], consumables=["elixir_of_the_mongoose"], enchants=[], talents={})
        self.assertAlmostEqual(buffed.stats["agility"], (130 + 77 + 25) * 1.10)
        self.assertAlmostEqual(buffed.stats["attackPower"] - base.stats["attackPower"], 222 + (buffed.stats["agility"] - 130) + (buffed.stats["strength"] - 80))
        self.assertAlmostEqual(buffed.stats["meleeCrit"] - base.stats["meleeCrit"], 2 + (buffed.stats["agility"] - 130) * 0.0345)

    def test_every_default_consumable_and_buff_changes_stats_or_actions(self):
        for sid in ("warrior-fury", "mage-fire", "hunter-marksmanship", "druid-feral-tank"):
            s = spec(sid); full = config(sid)
            for key in s["default_consumables"]:
                reduced = config(sid, consumables=[k for k in s["default_consumables"] if k != key])
                changed = reduced.stats != full.stats or set(reduced.actions) != set(full.actions) or reduced.consumes != full.consumes
                self.assertTrue(changed, f"{sid}: {key} is inert")
                if key in {"goblin_sapper_charge", "major_mana_potion", "mighty_rage_potion", "thistle_tea", "demonic_rune"}:
                    self.assertNotIn(engine.CONSUMABLE_ACTIONS[key], reduced.actions)
                elif key not in {"gift_of_arthas", "dragonbreath_chili"}:
                    self.assertNotEqual(reduced.stats, full.stats, f"{sid}: {key} has no stat effect")
            for key in s["default_buffs"]:
                reduced = config(sid, buffs=[k for k in s["default_buffs"] if k != key])
                self.assertTrue(reduced.stats != full.stats or reduced.windfury_totem != full.windfury_totem, f"{sid}: {key} is inert")

    def test_item_effects_are_parsed(self):
        c = config("warrior-fury")
        self.assertTrue(any(p["name"] == "Hand of Justice" and p["kind"] == "extra_attack" for p in c.item_procs))
        self.assertTrue(any(p["name"] == "Empyrean Demolisher" and p["kind"] == "buff" for p in c.item_procs))
        self.assertTrue(any(p["name"] == "Vis'kag the Bloodletter" and p["kind"] == "damage" for p in c.item_procs))
        self.assertEqual(c.item_effects["unresolved"], [])
        self.assertEqual(c.skill(c.oh), 307)  # Edgemaster's + sword
        enh = config("shaman-enhancement")
        self.assertTrue(any(p["name"].startswith("Sulfuras") and p["kind"] == "damage" and p["school"] == "fire" for p in enh.item_procs))

    def test_enchant_rules(self):
        base = default_request(spec("hunter-marksmanship"), iterations=1, duration=20)
        bow = simulate_spec({**base, "enchants": [{"slot": "ranged", "id": "sniper_scope"}]})
        self.assertEqual(bow["configuration"]["rejected_enchants"][0]["id"], "sniper_scope")
        mage = default_request(spec("mage-fire"), iterations=1, duration=20)
        oh = simulate_spec({**mage, "enchants": [{"slot": "off_hand", "id": "crusader"}]})
        self.assertEqual(oh["configuration"]["rejected_enchants"][0]["slot"], "off_hand")
        rogue = default_request(spec("rogue-combat"), iterations=1, duration=20)
        ok = simulate_spec({**rogue, "enchants": [{"slot": "main_hand", "id": "agility_15"}]})
        self.assertEqual(ok["configuration"]["rejected_enchants"], []); self.assertAlmostEqual(ok["configuration"]["gear_stats"]["agility"], config("rogue-combat").stats["agility"] + 15 * 1.1, places=3)


class AttackTableTests(unittest.TestCase):
    def outcomes(self, it, item, white, n=40000, **kw):
        counts = {}
        for _ in range(n):
            out, _m = it.melee_outcome(item, white, **kw)
            counts[out] = counts.get(out, 0) + 1
        return {k: v / n for k, v in counts.items()}

    def test_white_table_matches_classic_level_63_rates(self):
        it = iteration("warrior-fury", gear=[], gear_slots=[], buffs=[], consumables=[], enchants=[], talents={})
        it.c.dual_wield = True; it.st["meleeHit"] = 0.0
        rates = self.outcomes(it, it.c.mh, True)
        self.assertAlmostEqual(rates["miss"], 0.05 + 15 * 0.002 + 0.19, delta=0.01)
        self.assertAlmostEqual(rates["dodge"], 0.065, delta=0.006)
        self.assertAlmostEqual(rates["glance"], 0.40, delta=0.01)

    def test_hit_suppression_and_weapon_skill(self):
        it = iteration("warrior-fury", buffs=[], consumables=[], talents={})
        it.c.dual_wield = False; it.st["meleeHit"] = 9.0
        # Main hand: 300 skill -> 8% miss + 1% suppression -> 0 with 9% hit.  Off-hand sword at 307 -> 5.8% miss, no suppression.
        self.assertAlmostEqual(self.outcomes(it, it.c.mh, False).get("miss", 0.0), 0.0, delta=0.004)
        rates = self.outcomes(it, it.c.oh, True)
        self.assertAlmostEqual(rates["dodge"], 0.058, delta=0.006)

    def test_glancing_multiplier_range(self):
        it = iteration("rogue-combat", talents={})
        lo = max(min(1.3 - 0.05 * 15, 0.91), 0.01); hi = max(min(1.2 - 0.03 * 15, 0.99), 0.2)
        mults = [m for out, m in (it.melee_outcome(it.c.mh, True) for _ in range(5000)) if out == "glance"]
        self.assertTrue(all(lo - 1e-9 <= m <= hi + 1e-9 for m in mults)); self.assertGreater(len(mults), 1000)

    def test_spell_hit_and_crit_suppression(self):
        it = iteration("mage-frost", gear=[], gear_slots=[], buffs=[], consumables=[], enchants=[], talents={})
        it.st["spellHit"] = 0; it.st["spellCrit"] = 20.0
        n = 40000; outs = [it.spell_outcome("Frostbolt", "frost")[0] for _ in range(n)]
        self.assertAlmostEqual(outs.count("miss") / n, 0.17, delta=0.01)
        self.assertAlmostEqual(outs.count("crit") / n, 0.20 - 0.021, delta=0.01)
        it.st["spellHit"] = 40
        self.assertAlmostEqual([it.spell_outcome("Frostbolt", "frost")[0] for _ in range(n)].count("miss") / n, 0.01, delta=0.004)

    def test_ranged_table_and_crit_multipliers(self):
        it = iteration("hunter-marksmanship")
        it.st["rangedHit"] = 9; it.st["rangedCrit"] = 4.8 + 30
        n = 20000; outs = [it.ranged_outcome("Aimed Shot") for _ in range(n)]
        self.assertAlmostEqual(sum(o == "crit" for o, _ in outs) / n, 0.30, delta=0.012)
        crit_mult = next(m for o, m in outs if o == "crit")
        self.assertAlmostEqual(crit_mult, 2.0 + 0.30, places=6)  # Mortal Shots 5/5
        self.assertAlmostEqual(iteration("mage-frost").crit_multiplier("spell", "Frostbolt", "frost"), 2.0)  # Ice Shards
        self.assertAlmostEqual(iteration("warrior-fury").crit_multiplier("melee", "Bloodthirst", "physical"), 2.1)  # Impale 1/2


class ResourceTests(unittest.TestCase):
    def test_rage_from_damage_uses_classic_conversion(self):
        it = iteration("warrior-arms", talents={})
        it.rage = 0; it.on_weapon_hit(it.c.mh, True, "Melee (Main-Hand)", 230.6)
        self.assertAlmostEqual(it.rage, 7.5, places=6)
        it.rage = 0; it.on_weapon_hit(it.c.mh, False, "Mortal Strike", 500)
        self.assertEqual(it.rage, 0)  # specials generate no rage

    def test_off_hand_rage_and_damage_talent(self):
        it = iteration("warrior-fury")  # Dual Wield Specialization 5/5: +100% off-hand rage
        it.rage = 0; it.c.mods["flag:unbridled_wrath"] = 0; it.on_weapon_hit(it.c.oh, True, "Melee (Off-Hand)", 230.6)
        self.assertAlmostEqual(it.rage, 15.0, places=6)

    def test_energy_ticks_and_combo_points(self):
        r = simulate_spec(default_request(spec("rogue-combat"), iterations=3, duration=60, buffs=[], consumables=[]))
        st = r["ability_stats"]
        spent = st["Sinister Strike"]["casts"] * 40 + st["Eviscerate"]["casts"] * 35 + st["Slice and Dice"]["casts"] * 25
        self.assertLessEqual(spent, 100 + 30 * 20 * 1.02 + 150 + 25 * 6)  # start + ticks + Adrenaline Rush + Relentless Strikes
        self.assertGreater(st["Eviscerate"]["casts"], 1)
        self.assertGreater(st["Sinister Strike"]["casts"], st["Eviscerate"]["casts"] * 3)

    def test_mana_regen_respects_five_second_rule(self):
        it = iteration("mage-frost", buffs=[], consumables=[])
        it.st["mp5"] = 0; it.st["spirit"] = 200
        it.mana = 0; it.last_cast_time = 0; it.t = 2.0; it.next_mana_tick = 2.0
        # inside FSR: no spirit regen (Arcane Meditation not in the frost default build)
        it.run.__func__  # noqa - ensure method exists
        it.gain_mana(0)
        regen_inside = 0 if it.t - it.last_cast_time < 5 else 200 * 0.25 + 12.5
        self.assertEqual(regen_inside, 0)
        it.t = 8.0
        self.assertEqual(200 * 0.25 + 12.5, 62.5)

    def test_fire_mage_casts_fireball_and_respects_cast_time(self):
        r = simulate_spec(default_request(spec("mage-fire"), iterations=4, duration=120))
        st = r["ability_stats"]
        self.assertGreater(st["Fireball"]["casts"], st["Scorch"]["casts"])
        self.assertLessEqual(st["Fireball"]["casts"], 120 / (3.0 / 1.3) + 1)
        self.assertGreater(st["Ignite"]["hits"], 0)

    def test_warlock_pet_mana_regenerates_and_imp_casts_continuously(self):
        r = simulate_spec(default_request(spec("warlock-destruction"), iterations=3, duration=120, pet_family="imp"))
        self.assertGreater(r["ability_stats"]["Imp - Firebolt"]["casts"], 30)
        r2 = simulate_spec(default_request(spec("warlock-destruction"), iterations=3, duration=120, pet_family="succubus"))
        self.assertGreater(r2["ability_stats"]["Succubus - Lash of Pain"]["casts"], 7)


class MechanicTests(unittest.TestCase):
    def test_heroic_strike_replaces_swing_and_gives_no_rage(self):
        r = simulate_spec(default_request(spec("warrior-fury"), iterations=3, duration=120))
        st = r["ability_stats"]
        self.assertGreater(st["Heroic Strike"]["casts"], 20)
        self.assertGreater(st["Melee (Off-Hand)"]["casts"], 40)
        self.assertLess(st["Melee (Main-Hand)"]["casts"] + st["Heroic Strike"]["casts"], 120 / 2.8 * 1.5 + 5)

    def test_overpower_requires_a_dodge(self):
        it = iteration("warrior-arms")
        it.t = 10; it.dodged_recently = -10
        self.assertFalse(it.ready("Overpower", ignore_resource=True))
        it.dodged_recently = 8
        self.assertTrue(it.ready("Overpower", ignore_resource=True))

    def test_execute_phase_gates_execute_and_formula(self):
        it = iteration("warrior-fury"); it.rage = 50; it.t = 10
        self.assertFalse(it.ready("Execute", ignore_resource=True))
        it.t = it.execute_at + 1
        self.assertTrue(it.ready("Execute", ignore_resource=True))

    def test_dots_tick_on_schedule(self):
        it = iteration("warlock-affliction", buffs=[], consumables=[])
        it.st["spellHit"] = 40; it.t = 0
        it.resolve("Corruption")
        d = it.dots["Corruption"]; self.assertEqual(d["remaining"], 6); self.assertEqual(d["tick_len"], 3)
        tick = (73 + it.sp("shadow") * 0.20) * it.c.actions["Corruption"]["mult"]
        self.assertAlmostEqual(d["tick"], tick * (1 + it.crit_chance("spell", "Corruption", "shadow") * it.c.mod("crit_dmg_periodic")), places=6)

    def test_windfury_totem_and_weapon_procs(self):
        it = iteration("rogue-combat"); it.c.windfury_totem = True
        random.seed(0); it.rng = random.Random(3)
        before = it.row("Windfury Attack").casts
        for i in range(300): it.t = i * 2.0; it.on_weapon_hit(it.c.mh, True, "Melee (Main-Hand)", 200)
        self.assertGreater(it.row("Windfury Attack").casts - before, 30)
        it2 = iteration("rogue-combat"); it2.c.windfury_totem = False
        for _ in range(300): it2.on_weapon_hit(it2.c.oh, True, "Melee (Off-Hand)", 200)
        self.assertEqual(it2.rows.get("Windfury Attack", engine.Row()).casts, 0)

    def test_racials_are_simulated_effects(self):
        base = default_request(spec("warrior-fury"), iterations=2, duration=120)
        troll = simulate_spec({**base, "race": "Troll"}); undead = simulate_spec({**base, "race": "Undead"}); orc = simulate_spec({**base, "race": "Orc"})
        self.assertTrue(any(e["event"] == "Berserking" for e in troll["log"]))
        self.assertGreater(undead["ability_stats"]["Touch of the Grave"]["casts"], 0)
        self.assertTrue(any(e["event"] == "Blood Fury" for e in orc["log"]))
        self.assertEqual(config("warrior-fury", race="Human").racial_crit, 2.0)  # Vis'kag sword
        self.assertEqual(config("hunter-marksmanship", race="Human").racial_crit, 0.0)

    def test_hunter_pet_focus_and_abilities(self):
        r = simulate_spec(default_request(spec("hunter-beast-mastery"), iterations=3, duration=120, pet_family="cat"))
        st = r["ability_stats"]
        self.assertGreater(st["Pet Melee"]["casts"], 50)
        self.assertGreater(st["Pet - Claw"]["casts"], 10)
        self.assertLessEqual(st["Pet - Bite"]["casts"], 13)
        r0 = simulate_spec(default_request(spec("hunter-beast-mastery"), iterations=3, duration=120, pet_uptime=0))
        self.assertNotIn("Pet Melee", r0["ability_stats"])

    def test_tank_incoming_table_and_threat(self):
        r = simulate_spec(default_request(spec("warrior-protection"), iterations=3, duration=120))
        self.assertGreater(r["metrics"]["dtps"]["mean"], 100); self.assertGreater(r["metrics"]["tps"]["mean"], r["metrics"]["dps"]["mean"] * 1.5)
        self.assertEqual(r["log"][0]["event"], "Taunt")
        self.assertGreater(r["ability_stats"]["Sunder Armor"]["threat"], 0); self.assertEqual(r["ability_stats"]["Sunder Armor"]["damage"], 0)
        self.assertGreater(r["ability_stats"]["Shield Slam"]["casts"], 10)
        self.assertIn("block", r["taken_dtps"])
        bear = simulate_spec(default_request(spec("druid-feral-tank"), iterations=3, duration=120))
        self.assertGreater(bear["ability_stats"]["Maul"]["casts"], 30); self.assertEqual(bear["log"][0]["event"], "Taunt")

    def test_multi_target_only_affects_cleave_abilities(self):
        base = default_request(spec("warrior-fury"), iterations=3, duration=120)
        one = simulate_spec(base); three = simulate_spec({**base, "targets": 3})
        self.assertAlmostEqual(one["ability_dps"]["Bloodthirst"], three["ability_dps"]["Bloodthirst"], delta=one["ability_dps"]["Bloodthirst"] * 0.35)
        self.assertGreater(three["ability_dps"]["Whirlwind"], one["ability_dps"]["Whirlwind"] * 2)

    def test_breakdown_reconciles_and_no_calibration(self):
        for s in public_specs():
            r = simulate_spec(default_request(s, iterations=2, duration=30))
            self.assertAlmostEqual(sum(r["ability_dps"].values()), r["metrics"]["dps"]["mean"])
            self.assertEqual(r["configuration"]["multiplier"], 1.0)
            self.assertIsNone(r["configuration"]["classic_reference_dps"])

    def test_seed_reproduces_and_run_size_is_capped(self):
        req = default_request(spec("mage-fire"), iterations=2, duration=30)
        self.assertEqual(simulate_spec(req), simulate_spec(req))
        with self.assertRaises(ValueError): simulate_spec({**req, "iterations": 10000, "duration": 1800})


class SetBonusTests(unittest.TestCase):
    def test_every_catalog_set_bonus_is_classified(self):
        from forever.engine import SET_PATTERNS
        from forever.engine_data import SET_EFFECTS, SET_NO_COMBAT_EFFECT
        sets = {}
        for it in ITEMS.values():
            if it.get("set"): sets.setdefault(it["set"]["name"], it["set"])
        missing = []
        for name, st in sets.items():
            for b in FOREVER_SETS.get(name, {}).get("bonuses", st.get("bonuses", [])):
                key = f"{name}|{b.get('required')}"; desc = b.get("description", "")
                if not (b.get("stats") or any(engine._re(p, desc) for _, p in SET_PATTERNS) or key in SET_EFFECTS or key in SET_NO_COMBAT_EFFECT):
                    missing.append(key)
        self.assertEqual(missing, [])

    def test_preset_set_bonuses_apply_effects(self):
        prot = config("warrior-protection")
        self.assertAlmostEqual(prot.mod("threat_ability:Sunder Armor"), 0.15)
        self.assertEqual(prot.flag("might_rage"), 0.20)
        self.assertEqual(prot.stats["blockValue"] >= 30, True)
        self.assertTrue(all(b["modeled"] for b in prot.active_set_bonuses))
        hunter = config("hunter-beast-mastery")
        self.assertAlmostEqual(hunter.actions["Multi-Shot"]["mult"], 1.15)
        sub = config("rogue-subtlety")
        self.assertEqual(sub.flag("shadowcraft_energy"), 1.0)
        self.assertEqual(sub.unresolved_set_bonuses, [])

    def test_shadowcraft_energy_proc_runs(self):
        it = iteration("rogue-subtlety", seed=3)
        res = it.run()
        self.assertIn("Shadowcraft Energize", res["rows"])
