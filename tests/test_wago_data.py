"""Client-row regression checks: intentionally independent of engine parity."""
import json
import tempfile
import unittest
from pathlib import Path

from forever.engine_data import ABILITIES
from tests.test_all_specs import config
from tools.spell_curve import fetch_csv
from tools.wago_audit import Snapshot, damage_range


class WagoDataTests(unittest.TestCase):
    def test_max_rank_periodic_values_not_rank_one(self):
        self.assertEqual(ABILITIES['Insect Swarm']['spell_id'], 24977)
        self.assertEqual(ABILITIES['Insect Swarm']['tick'], 31)
        self.assertEqual(ABILITIES['Insect Swarm']['cost'], 160)
        self.assertEqual(ABILITIES['Insect Swarm']['dot_coeff'], .158)
        self.assertEqual(ABILITIES['Devouring Plague']['tick'], 106)
        self.assertEqual(ABILITIES['Devouring Plague']['cost'], 985)
        self.assertEqual(ABILITIES['Pyroblast']['tick'], 53)

    def test_pain_preserves_base_duration_before_talent_extension(self):
        a = ABILITIES['Shadow Word: Pain']
        self.assertEqual(a['tick'] * a['ticks'], 762)
        self.assertEqual(a['ticks'] * a['tick_len'], 18)
        c = config('priest-shadow', talents={'105830': 2})
        self.assertEqual(c.actions['Shadow Word: Pain']['ticks'], 8)
        self.assertEqual(c.actions['Shadow Word: Pain']['tick'], 127)

    def test_non_linear_cost_ranks_are_exact(self):
        for rank, cost in [(1, 12), (2, 10)]:
            c = config('warrior-fury', talents={'105932': rank})
            self.assertEqual(c.actions['Execute']['cost'], cost)
        for rank, cost in [(1, 42), (2, 40)]:
            c = config('rogue-combat', talents={'105741': rank})
            self.assertEqual(c.actions['Sinister Strike']['cost'], cost)

    def test_moonglow_and_moonfury_follow_client_curves(self):
        for rank, amount in [(1, -.08), (2, -.17), (3, -.25)]:
            c = config('druid-balance', talents={'104925': rank, '104936': 5})
            self.assertEqual(c.mod('cost_pct_all'), amount)
            self.assertEqual(c.mod('dmg_school:arcane'), .1)
            self.assertEqual(c.mod('dmg_school:nature'), .1)

    def test_percent_cost_uses_base_mana(self):
        c = config('mage-arcane', talents={'105806': 1})
        a = c.actions['Arcane Blast']
        self.assertAlmostEqual(a['cost'], 1213 * .15)

    def test_level_growth_is_separate_from_variance(self):
        effect = {'EffectBasePointsF': '100', 'Variance': '.2', 'EffectRealPointsPerLevel': '2'}
        levels = {'MaxLevel': '58', 'SpellLevel': '54'}
        self.assertEqual(damage_range(effect, levels), [98, 118])

    def test_cast_time_and_related_talents_come_from_client(self):
        self.assertEqual(ABILITIES['Incinerate']['cast'], 2.5)
        c = config('shaman-elemental', talents={'104765': 2, '104758': 1})
        self.assertAlmostEqual(c.actions['Lava Burst']['cast'], 2.17)

    def test_csv_id_need_not_be_first_column_and_offline_filter_is_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            (p / 'TraitDefinition.csv').write_text('Name,ID,SpellID\nOne,1,55\nTwo,2,555\n', encoding='utf-8')
            snapshot = Snapshot(p)
            self.assertEqual(len(snapshot.tables['TraitDefinition']), 2)
            self.assertEqual(fetch_csv('TraitDefinition', 'test', {'SpellID': 55}, p)[0]['ID'], '1')
            self.assertEqual(len(fetch_csv('TraitDefinition', 'test', {'SpellID': 55}, p)), 1)

    def test_evidence_retains_build_hashes_and_raw_rows(self):
        p = Path(__file__).resolve().parents[1] / 'data/wago_verified.json'
        evidence = json.loads(p.read_text(encoding='utf-8'))
        self.assertEqual(evidence['build'], '1.60.1.69913')
        for table in evidence['tables']:
            self.assertEqual(len(table['sha256']), 64)
        for spell in evidence['spells'].values():
            self.assertTrue(spell['rows']['SpellEffect'])
            self.assertTrue(spell['rows']['SpellLevels'])


if __name__ == '__main__':
    unittest.main()
