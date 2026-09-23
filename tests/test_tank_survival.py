"""Tank survival must respond to the encounter and stop accounting at death."""
import copy
import unittest

from forever.all_specs import simulate_spec
from forever.sim import preset, simulate
from server import default_request
from tests.test_all_specs import spec


class TankSurvivalTests(unittest.TestCase):
    def request(self, sid, **overrides):
        return default_request(spec(sid), iterations=10, duration=60, seed=42, **overrides)

    def test_dead_shared_tank_is_not_attacked_or_healed_again(self):
        for sid in ('warrior-protection', 'druid-feral-tank'):
            result = simulate_spec(self.request(sid, enemy_damage_min=100000, enemy_damage_max=100000, heal_amount=100000))
            m = result['metrics']
            self.assertEqual(m['survival_fraction'], 0, sid)
            self.assertEqual(m['ending_health']['mean'], 0, sid)
            self.assertEqual(m['effective_healing']['mean'], 0, sid)
            self.assertGreater(m['alive_dtps']['mean'], m['dtps']['mean'], sid)
            self.assertEqual(result['log'][-1]['event'], 'Death', sid)
            self.assertEqual(sum(e['event'] == 'Death' for e in result['log']), 1, sid)

    def test_damage_controls_and_healing_change_results(self):
        for sid in ('warrior-protection', 'druid-feral-tank'):
            request = self.request(sid, enemy_damage_min=5000, enemy_damage_max=5000, heal_amount=100000)
            healed = simulate_spec(request)
            unhealed = simulate_spec({**request, 'heal_amount': 0})
            gentle = simulate_spec({**request, 'enemy_damage_min': 1000, 'enemy_damage_max': 1000})
            self.assertEqual(healed['metrics']['survival_fraction'], 1, sid)
            self.assertLess(unhealed['metrics']['alive_seconds']['mean'], 60, sid)
            self.assertLess(gentle['metrics']['dtps']['mean'], healed['metrics']['dtps']['mean'], sid)
            self.assertGreater(healed['metrics']['effective_healing']['mean'], 0, sid)
            self.assertEqual(unhealed['metrics']['effective_healing']['mean'], 0, sid)

    def test_incoming_attackers_are_independent_of_outgoing_targets(self):
        request = self.request('warrior-protection', heal_amount=100000)
        one = simulate_spec(request)
        three = simulate_spec({**request, 'enemies': 3})
        self.assertGreater(three['metrics']['dtps']['mean'], one['metrics']['dtps']['mean'] * 2)
        self.assertEqual(three['configuration']['targets'], 1)

    def test_variance_does_not_break_damage_breakdown_total(self):
        result = simulate_spec(self.request('warrior-protection', duration_variance=15))
        self.assertAlmostEqual(sum(result['taken_dtps'].values()), result['metrics']['dtps']['mean'])

    def test_encounter_validation(self):
        for values in ({'enemy_swing': 0}, {'enemies': 1.5}, {'heal_amount': -1}, {'enemy_damage_min': 4000, 'enemy_damage_max': 3000}, {'heal_interval': float('nan')}):
            with self.assertRaises(ValueError): simulate_spec(self.request('warrior-protection', **values))

    def test_paladin_death_and_healing_metrics(self):
        p = preset('protection'); p.update(iterations=10, duration=60)
        p['encounter'].update(enemy_damage_min=100000, enemy_damage_max=100000, heal_amount=100000)
        dead = simulate(p)
        self.assertEqual(dead['metrics']['survival_fraction'], 0)
        self.assertEqual(dead['first_iteration']['log'][-1]['event'], 'Death')
        q = copy.deepcopy(p)
        q['encounter'].update(enemy_damage_min=3000, enemy_damage_max=3000)
        healed = simulate(q)
        self.assertGreater(healed['metrics']['effective_healing']['mean'], 0)
        q['encounter']['heal_amount'] = 0
        unhealed = simulate(q)
        self.assertEqual(unhealed['metrics']['effective_healing']['mean'], 0)
        self.assertLess(unhealed['metrics']['alive_seconds']['mean'], healed['metrics']['alive_seconds']['mean'])


if __name__ == '__main__':
    unittest.main()
