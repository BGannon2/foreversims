"""Source-based invariants independent of the Python/Rust parity checks."""
import random
import unittest

from forever.engine import apply_set_bonuses
from forever.engine_data import ABILITIES, CLASS_BASE, RAGE_CONVERSION_60
from tests.test_all_specs import config, iteration


class AccuracyRegressions(unittest.TestCase):
    def test_short_caster_item_labels_are_permanent_stats(self):
        from forever.profile_rules import annotate_rating_assumptions
        item = {'effects': ['Equip: +7 Mana Regeneration', 'Equip: +69 Shadow Spell Damage'], 'stats': {}}
        annotate_rating_assumptions(item)
        annotate_rating_assumptions(item)
        self.assertEqual(item['stats'], {'mp5': 7, 'shadowPower': 69})

    def test_pet_bloodlust_does_not_inherit_owner_haste(self):
        it = iteration('hunter-beast-mastery', buffs=['bloodlust'])
        self.assertAlmostEqual(it.pet_delay(2), 2 / 1.3)
        it.st['meleeHaste'] = 100
        self.assertAlmostEqual(it.pet_delay(2), 2 / 1.3)
        it.t = 39
        self.assertAlmostEqual(it.pet_delay(2), 1.7)
        it.t = 40
        self.assertEqual(it.pet_delay(2), 2)

    def test_restored_warrior_talents_scale_by_rank(self):
        opts = dict(talents={}, buffs=[], consumables=[], enchants=[])
        base = config('warrior-protection', **opts)
        for rank in range(1, 6):
            c = config('warrior-protection', **{**opts, 'talents': {'105975': rank, '105973': rank}})
            self.assertAlmostEqual(c.stats['defense'] - base.stats['defense'], 4 * rank)
            self.assertAlmostEqual(c.stats['armor'], base.stats['armor'] * (1 + .02 * rank))
        for rank in range(1, 4):
            c = config('warrior-protection', **{**opts, 'talents': {'105969': rank}})
            self.assertAlmostEqual(c.actions['Revenge']['mult'], 1 + .20 * rank)

    def test_hunter_talents_do_not_double_ranged_hit_or_crit(self):
        opts = dict(talents={}, buffs=[], consumables=[], enchants=[])
        base = config('hunter-marksmanship', **opts)
        for rank in range(1, 6):
            c = config('hunter-marksmanship', **{**opts, 'talents': {'105011': rank}})
            self.assertAlmostEqual(c.stats['rangedCrit'] - base.stats['rangedCrit'], rank)
        for rank in range(1, 4):
            c = config('hunter-marksmanship', **{**opts, 'talents': {'104987': rank}})
            self.assertAlmostEqual(c.stats['rangedHit'] - base.stats['rangedHit'], rank)

    def test_bloodlust_duration_and_swing_boundary(self):
        from forever.sim import Fight, preset
        it = iteration('mage-fire', buffs=['bloodlust'], consumables=[])
        self.assertEqual(it.haste('spell'), 1.30)
        it.t = 39
        self.assertAlmostEqual(it.attack_delay(2, 'melee'), 1.7)
        it.t = 40
        self.assertEqual(it.haste('spell'), 1)
        p = preset('retribution'); fight = Fight(p, 1)
        fight.c['weapon_speed'] = 2
        fight.time = 39
        self.assertAlmostEqual(fight.swing_delay(), 1.7)
        fight.time = 40
        self.assertEqual(fight.swing_delay(), 2)

    def test_small_defense_bonus_does_not_remove_crushing(self):
        class FixedRandom:
            def random(self): return .20
            def uniform(self, low, high): return low
        it = iteration('warrior-protection')
        it.st.update(defense=308, dodge=0, parry=0, block=0)
        it.taken_by = {}
        it.rng = FixedRandom()
        it.boss_swing()
        self.assertGreater(it.taken_by.get('crush', 0), 0)

    def test_frenzy_triggers_only_on_current_pet_crit(self):
        class FixedRandom:
            value = .6
            def random(self): return self.value
        it = iteration('hunter-beast-mastery')
        it.pet_setup(); it.pet_threat = 0
        it.c.mods['flag:pet_frenzy'] = 1
        it.rng = FixedRandom()
        it.pet_attack('Pet Melee', 100, 'physical', .20)
        self.assertEqual(it.pet_state['frenzy_until'], 8)
        it.t = 10; it.rng.value = .95
        it.pet_attack('Pet Melee', 100, 'physical', .20)
        self.assertEqual(it.pet_state['frenzy_until'], 8)

    def test_paladin_item_stats_and_timed_use(self):
        from forever.gear_data import ITEMS, item_stats_and_effects
        from forever.sim import Fight, preset
        self.assertEqual(item_stats_and_effects(ITEMS[11815])[0]['attackPower'], 20)
        self.assertEqual(item_stats_and_effects(ITEMS[11810])[0]['defense'], 7)
        stats, effects, unknown = item_stats_and_effects(ITEMS[18820])
        self.assertNotIn('spellPower', stats)
        self.assertEqual(unknown, [])
        p = preset('retribution'); p['item_effects'] = effects
        f = Fight(p, 1); before = f.item_stat('spell_power')
        f.decision()
        self.assertEqual(f.item_stat('spell_power'), before + 175)
        f.time = 15
        self.assertEqual(f.item_stat('spell_power'), before)
        self.assertEqual(f.item_ready[effects[0]['name']], 90)

    def test_paladin_holy_strike_scales_with_normalized_ap(self):
        import copy

        from forever.sim import Fight, preset
        p = preset('retribution'); p['talents'] = {k: 0 for k in p['talents']}
        p['rotation'].update(use_judgement=False, use_hammer_of_wrath=False)
        p['character'].update(attack_power=0, spell_power=0, crit_chance=0, hit_chance=1, weapon_skill=300, normalized_speed=3.3)
        p['debuffs']['judgement_of_the_crusader'] = False
        a = Fight(copy.deepcopy(p), 0); a.decision()
        p['character']['attack_power'] = 1400
        b = Fight(p, 0); b.decision()
        self.assertAlmostEqual(b.damage['Holy Strike'] - a.damage['Holy Strike'], 1400 / 14 * 3.3 * .4)

    def test_paladin_seal_rank_scales_nonzero_spell_power(self):
        import copy

        from forever.sim import Fight, preset
        p = preset('retribution')
        p['talents'] = {k: 0 for k in p['talents']}
        p['character'].update(spell_power=500, crit_chance=0)
        p['debuffs']['judgement_of_the_crusader'] = False
        a = Fight(copy.deepcopy(p), 0)
        a.seal_proc('righteousness', 100)
        p['talents']['105334'] = 5
        b = Fight(p, 0)
        b.seal_proc('righteousness', 100)
        self.assertAlmostEqual(b.damage['Seal of Righteousness'], a.damage['Seal of Righteousness'] * 1.25)

    def test_paladin_holy_wrath_does_not_cast_a_seal_on_same_gcd(self):
        from forever.sim import Fight, preset
        p = preset('retribution')
        p['encounter']['boss_type'] = 'undead'
        p['rotation'].update(use_holy_strike=False, use_exorcism=False, use_hammer_of_wrath=False)
        f = Fight(p, 0)
        f.decision()
        self.assertEqual(f.casts['Holy Wrath'], 1)
        self.assertFalse(f.seal)
        self.assertGreaterEqual(f.gcd, 1.5)

    def test_school_enchants_and_default_equipment_are_legal(self):
        from forever.all_specs import ITEMS, public_specs
        from forever.profile_rules import default_enchants, enchant_preferences, item_allowed
        from server import ENCHANT_DATA, PHASE12_BIS, default_request
        for s in public_specs():
            gear = PHASE12_BIS['profiles'][s['id']]['gear']
            for row in gear:
                if row['id']: self.assertTrue(item_allowed(ITEMS[row['id']], row['slot'], s['class_name']), (s['id'], row['slot']))
            self.assertEqual(default_request(s)['enchants'], default_enchants(s, gear, ITEMS, ENCHANT_DATA['slots']))
        self.assertEqual(enchant_preferences({'id': 'mage-frost', 'class_name': 'Mage', 'style': 'spell'})['hands'], ['frost_power'])

    def test_ranged_ap_excludes_strength_and_melee_buffs(self):
        opts = dict(gear=[], gear_slots=[], enchants=[], talents={}, buffs=[], consumables=[])
        base = config('hunter-marksmanship', **opts)
        buffed = config('hunter-marksmanship', **{**opts, 'buffs': ['blessing_of_might', 'battle_shout'], 'consumables': ['juju_power']})
        self.assertGreater(buffed.stats['attackPower'], base.stats['attackPower'])
        self.assertEqual(buffed.stats['rangedAttackPower'], base.stats['rangedAttackPower'])
        self.assertEqual(base.stats['rangedAttackPower'], CLASS_BASE['Hunter'].get('rangedAttackPower', 0) + base.stats['agility'] * 2 + 120)

    def test_percent_base_mana_cost_does_not_scale_with_intellect(self):
        opts = dict(gear=[], gear_slots=[], enchants=[], talents={}, consumables=[])
        base = config('hunter-marksmanship', buffs=[], **opts)
        buffed = config('hunter-marksmanship', buffs=['arcane_intellect', 'blessing_of_kings'], **opts)
        self.assertGreater(buffed.stats['mana'], base.stats['mana'])
        self.assertEqual(base.actions['Multi-Shot']['cost'], CLASS_BASE['Hunter']['mana'] * ABILITIES['Multi-Shot']['cost_pct'])
        self.assertEqual(base.actions['Multi-Shot']['cost'], buffed.actions['Multi-Shot']['cost'])

    def test_flurry_scales_with_allocated_rank(self):
        it = iteration('warrior-fury', buffs=[], consumables=[])
        it.flurry = 3
        it.c.mods['flag:flurry'] = .05
        low = it.haste('melee')
        it.c.mods['flag:flurry'] = .25
        self.assertAlmostEqual(it.haste('melee') / low, 1.25 / 1.05)

    def test_damage_rage_is_threat_free_and_other_rage_is_flat(self):
        it = iteration('warrior-protection')
        it.rage = 0
        before = it.threat
        it.white_rage(it.c.mh, 100)
        self.assertAlmostEqual(it.rage, 750 / RAGE_CONVERSION_60)
        self.assertEqual(it.threat, before)
        it.gain_rage(10)
        self.assertEqual(it.threat - before, 50)

    def test_bleeds_ignore_armor(self):
        it = iteration('rogue-combat', debuffs=[], armor=10000)
        bleed = it.deal('Rupture', 100, 'physical', 'melee', periodic=True)
        direct = it.deal('Rupture', 100, 'physical', 'melee')
        self.assertGreater(bleed, direct)
        self.assertAlmostEqual(direct / bleed, it.armor_mult())

    def test_pet_results_do_not_inherit_owner_hit_or_crit(self):
        a = iteration('hunter-beast-mastery')
        b = iteration('hunter-beast-mastery')
        a.pet_setup(); b.pet_setup()
        a.pet_threat = b.pet_threat = 0
        b.st['meleeHit'] = 100
        b.st['meleeCrit'] = 100
        b.st['spellHit'] = 100
        b.st['spellCrit'] = 100
        for school in ['physical', 'nature']:
            a.rng = random.Random(13); b.rng = random.Random(13)
            x = [a.pet_attack('Probe', 100, school, .10) for _ in range(100)]
            y = [b.pet_attack('Probe', 100, school, .10) for _ in range(100)]
            self.assertEqual(x, y)

    def test_hunter_can_choose_no_pet(self):
        self.assertIsNone(config('hunter-marksmanship', pet_family='none').pet)
        with self.assertRaises(ValueError):
            config('hunter-marksmanship', pet_family='invalid')

    def test_timed_set_proc_does_not_become_permanent_stats(self):
        gear = [{'set': {'name': 'Probe', 'bonuses': [
            {'required': 1, 'description': 'Chance on spellcast to increase spell damage by 100 for 10 sec.', 'stats': {'spellPower': 100}},
            {'required': 1, 'description': 'Improves your chance to get a critical strike by 1%.', 'stats': {'meleeCrit': 1}},
        ]}}]
        stats = {}
        apply_set_bonuses(gear, stats, {})
        self.assertNotIn('spellPower', stats)
        self.assertEqual(stats['meleeCrit'], 1)
