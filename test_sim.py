import copy
import copy
import math
import unittest
from urllib.parse import urlparse
from gear_data import apply_gear
from sim import CONSUMABLE_GROUPS, DATA, F, TALENT_DATA, TALENTS, Fight, preset, simulate, validate

class SimulationTests(unittest.TestCase):
    def basic(self,spec='protection'):
        p=preset(spec); p['duration']=20; p['iterations']=3
        p['model']['use_classic_era_conversions']=False
        p['raid_buffs']={k:False for k in p['raid_buffs']}
        p['consumables']={k:False for k in p['consumables']}
        p['debuffs']={k:False for k in p['debuffs']}
        return p

    def test_default_encounter_matches_wowsims_duration(self):
        p=preset('protection')
        self.assertEqual(p['duration'],120)
        self.assertEqual(p['iterations'],300)
        self.assertEqual(p['duration_variance'],0)
        self.assertEqual(p['race'],'Human')
        self.assertIn('Patchwerk',p['encounter']['preset_name'])
        self.assertEqual((p['encounter']['enemy_damage_min'],p['encounter']['enemy_damage_max']),(2700,3300))

    def test_paladin_pull_bloodlust_increases_opening_swing_cadence(self):
        p=self.basic('retribution');p['duration']=10;p['character'].update(weapon_speed=3.5,hit_chance=1,crit_chance=0)
        r=Fight(p,0,True).run()
        self.assertEqual(r['hits']['Melee'],3)

    def test_paladin_demon_and_undead_damage_rules(self):
        neutral=self.basic('retribution');neutral['duration']=60;neutral['iterations']=10
        neutral['rotation']['use_exorcism']=False;neutral['rotation']['use_holy_wrath']=False
        undead=copy.deepcopy(neutral);undead['encounter']['boss_type']='undead'
        self.assertGreater(simulate(undead)['metrics']['dps']['mean'],simulate(neutral)['metrics']['dps']['mean'])
        enabled=copy.deepcopy(undead);enabled['rotation']['use_exorcism']=True;enabled['rotation']['use_holy_wrath']=True
        result=simulate(enabled)
        self.assertGreater(result['ability_dps']['Exorcism'],0)
        self.assertGreater(result['ability_dps']['Holy Wrath'],0)
        demon=copy.deepcopy(enabled);demon['encounter']['boss_type']='demon'
        self.assertGreater(simulate(demon)['ability_dps']['Exorcism'],0)

    def test_defaults_have_raid_buffs_consumables_and_debuffs_without_world_buffs(self):
        p=preset('protection')
        core=('power_word_fortitude','mark_of_the_wild','arcane_intellect','battle_shout','blessing_of_might','devotion_aura','blessing_of_kings','blessing_of_wisdom','strength_of_earth','mana_spring','leader_of_the_pack')
        self.assertTrue(all(p['raid_buffs'][k] for k in core))
        self.assertFalse(p['raid_buffs']['grace_of_air']); self.assertTrue(preset('retribution')['raid_buffs']['windfury_totem'])
        self.assertTrue(all(v for k,v in p['consumables'].items() if k!='major_mana_potion'))
        self.assertTrue(all(p['debuffs'].values()))
        forbidden=('rallying','zandalar','songflower','dire_maul','sayge')
        self.assertFalse(any(word in key for key in p['raid_buffs'] for word in forbidden))

    def test_consumable_exclusivity_groups_are_enforced(self):
        p=preset('protection'); original=CONSUMABLE_GROUPS['elixir_of_fortitude']
        try:
            CONSUMABLE_GROUPS['elixir_of_fortitude']=CONSUMABLE_GROUPS['flask_of_the_titans']
            with self.assertRaisesRegex(ValueError,'cannot be combined'): validate(p)
        finally:
            CONSUMABLE_GROUPS['elixir_of_fortitude']=original

    def test_every_settings_toggle_is_connected_to_the_model(self):
        p=preset('protection'); base,_=apply_gear(p)
        fight_only={'gift_of_arthas','windfury_totem','grace_of_air','moonkin_aura','trueshot_aura','major_mana_potion','demonic_rune','goblin_sapper_charge','dragonbreath_chili'}
        for group in ('raid_buffs','consumables'):
            for key in p[group]:
                if key in fight_only or not p[group][key]: continue
                changed=copy.deepcopy(p); changed[group][key]=False; effective,_=apply_gear(changed)
                self.assertNotEqual(effective['character'],base['character'],f'{group}.{key} is inert')
        wf=self.basic('retribution'); wf['raid_buffs']['windfury_totem']=True; wf['character'].update(hit_chance=1,crit_chance=0); wf['duration']=60; wf['iterations']=2
        self.assertGreater(simulate(wf)['ability_dps'].get('Windfury Attack',0),0)
        sap=self.basic('retribution'); sap['consumables']['goblin_sapper_charge']=True
        self.assertGreater(simulate(sap)['ability_dps'].get('Goblin Sapper Charge',0),0)
        for key in ('sunder_armor_5','faerie_fire','curse_of_recklessness'):
            changed=copy.deepcopy(p); changed['debuffs'][key]=False; effective,_=apply_gear(changed)
            self.assertNotEqual(effective['encounter']['target_physical_mitigation'],base['encounter']['target_physical_mitigation'])
        clean=self.basic(); clean['gear']={k:0 for k in clean['gear']}; clean['character'].update(hit_chance=1,crit_chance=0)
        clean['talents']={k:0 for k in clean['talents']}; clean['model']['use_classic_era_conversions']=True
        clean['debuffs']['judgement_of_the_crusader']=True
        with_jotc=Fight(clean,1); with_jotc.deal('Holy',100,holy=True,hit=1,spell_coefficient=1)
        clean['debuffs']['judgement_of_the_crusader']=False
        without_jotc=Fight(clean,1); without_jotc.deal('Holy',100,holy=True,hit=1,spell_coefficient=1)
        self.assertGreater(with_jotc.damage['Holy'],without_jotc.damage['Holy'])
        clean['debuffs']['gift_of_arthas']=True; clean['consumables']['gift_of_arthas']=True
        with_gift=Fight(clean,2); with_gift.deal('Physical',100,hit=1)
        clean['consumables']['gift_of_arthas']=False
        without_gift=Fight(clean,2); without_gift.deal('Physical',100,hit=1)
        self.assertGreater(with_gift.damage['Physical'],without_gift.damage['Physical'])
        clean['character'].update(health=100000,avoidance=0,block_chance=0,physical_mitigation=0)
        clean['encounter'].update(enemy_crit_chance=0,enemy_damage_min=1000,enemy_damage_max=1000)
        clean['debuffs'].update(insect_swarm=False,scorpid_sting=False,demoralizing_shout=True)
        with_demo=Fight(clean,3); with_demo.enemy()
        clean['debuffs']['demoralizing_shout']=False
        without_demo=Fight(clean,3); without_demo.enemy()
        self.assertLess(with_demo.taken,without_demo.taken)
        clean['debuffs']['thunder_clap']=True; slowed=Fight(clean,4); slowed.enemy()
        clean['debuffs']['thunder_clap']=False; normal=Fight(clean,4); normal.enemy()
        self.assertGreater(next(t for t,_,_,k in slowed.queue if k=='enemy'),next(t for t,_,_,k in normal.queue if k=='enemy'))
        class FixedRandom:
            def __init__(self,value): self.value=value
            def random(self): return self.value
            def uniform(self,a,b): return a
        for key,value in [('insect_swarm',.01),('scorpid_sting',.04)]:
            clean['debuffs'].update(insect_swarm=False,scorpid_sting=False); clean['debuffs'][key]=True
            avoided=Fight(clean,5); avoided.rng=FixedRandom(value); avoided.enemy()
            clean['debuffs'][key]=False
            hit=Fight(clean,5); hit.rng=FixedRandom(value); hit.enemy()
            self.assertEqual(avoided.avoids,1,key); self.assertGreater(hit.taken,0,key)

    def test_sources_are_forever_only(self):
        for url in DATA['sources'].values():
            u=urlparse(url)
            self.assertEqual(u.netloc,'www.wowhead.com'); self.assertTrue(u.path.startswith('/forever/'))
        for fact in F.values(): self.assertIn(fact['source'],DATA['sources'])

    def test_seed_reproduces_entire_result(self):
        p=self.basic('retribution'); self.assertEqual(simulate(p),simulate(p))

    def test_protection_opens_with_taunt(self):
        p=preset('protection');p['iterations']=1;p['duration']=20
        result=simulate(p)
        self.assertEqual(result['first_iteration']['log'][0]['event'],'Cast Taunt')
        self.assertEqual(result['first_iteration']['log'][0]['time'],0)

    def test_different_seed_changes_log(self):
        p=self.basic('retribution'); a=simulate(p); p['seed']+=1
        self.assertNotEqual(a['first_iteration']['log'],simulate(p)['first_iteration']['log'])

    def test_profile_not_mutated(self):
        p=self.basic(); before=copy.deepcopy(p); simulate(p); self.assertEqual(p,before)

    def test_damage_breakdown_reconciles(self):
        for spec in ['protection','retribution']:
            r=simulate(self.basic(spec))
            self.assertAlmostEqual(sum(r['ability_dps'].values()),r['metrics']['dps']['mean'])
            for name,dps in r['ability_dps'].items():
                self.assertAlmostEqual(r['ability_damage'][name],dps*r['profile']['duration'])
            self.assertAlmostEqual(sum(r['ability_tps'].values()),r['metrics']['tps']['mean'])
            self.assertAlmostEqual(sum(r['taken_dtps'].values()),r['metrics']['dtps']['mean'])
            for e in r['first_iteration']['log']:
                self.assertGreaterEqual(e['mana'],0); self.assertLessEqual(e['mana'],r['profile']['character']['mana'])

    def test_sourced_damage_talents_change_damage(self):
        p=self.basic('retribution'); p['gear']={k:0 for k in p['gear']}
        p['character'].update(hit_chance=1,crit_chance=0,spell_hit_chance=1,spell_crit_chance=0)
        p['talents']={k:0 for k in p['talents']}; base=Fight(p,0); base.deal('Seal',100,holy=True)
        p['talents']['105334']=3; improved=Fight(p,0); improved.seal_proc('righteousness',100)
        self.assertAlmostEqual(improved.damage['Seal of Righteousness'],p['model']['righteousness_damage']*1.15)
        p['talents']['110883']=2; crusade=Fight(p,0); crusade.deal('Test',100,holy=True)
        self.assertAlmostEqual(crusade.damage['Test'],102)

    def test_consecration_rank_five_cost_ticks_and_damage(self):
        p=self.basic('retribution'); p['duration']=9; p['iterations']=1
        p['character'].update(mana=1000,mana_per_second=0,spell_hit_chance=0)
        p['rotation'].update(use_judgement=False,twist_seals=False)
        p['talents']={k:0 for k in p['talents']}
        first=Fight(p,0); first.decision()
        self.assertEqual(first.mana_spent,565)
        row=Fight(p,0).run()
        self.assertEqual(row['casts']['Consecration'],1)
        self.assertEqual(row['hits']['Consecration'],8)
        self.assertAlmostEqual(row['damage']['Consecration'],384)

    def test_holy_strike_replaces_next_melee_and_iron_creed_applies(self):
        p=self.basic('protection'); p['gear']={k:0 for k in p['gear']}
        p['character'].update(weapon_min=100,weapon_max=100,hit_chance=1,crit_chance=0)
        p['model']['holy_threat_per_damage']=1.5
        p['talents']={k:0 for k in p['talents']}; p['talents']['110879']=5
        f=Fight(p,0); f.decision(); self.assertTrue(f.holy_strike_queued)
        f.swing(); self.assertFalse(f.holy_strike_queued)
        self.assertAlmostEqual(f.damage['Holy Strike'],102)
        self.assertAlmostEqual(f.threat,102*1.5*1.25*F['righteous_fury']['holy_threat_multiplier'])
        self.assertEqual(f.iron_until,6)

    def test_holy_shield_four_charges_and_threat(self):
        p=self.basic(); p['character'].update(avoidance=0,block_chance=1,health=100000)
        p['model']['holy_threat_per_damage']=1.5
        p['talents']={k:0 for k in p['talents']}; p['talents']['105628']=1
        f=Fight(p,0); f.decision()
        for _ in range(8): f.enemy()
        self.assertEqual(f.hs_charges,0)
        self.assertEqual(f.hits['Holy Shield'],4)
        self.assertEqual(f.damage['Holy Shield'],440)
        self.assertAlmostEqual(f.threat,440*1.5*1.9*1.2)

    def test_classic_attack_power_adds_normalized_weapon_damage(self):
        p=self.basic(); p['gear']={k:0 for k in p['gear']}
        p['character'].update(weapon_min=100,weapon_max=100,weapon_speed=2,attack_power=140,hit_chance=1,crit_chance=0)
        p['model']['use_classic_era_conversions']=True
        p['talents']={k:0 for k in p['talents']}
        f=Fight(p,0); f.swing()
        self.assertAlmostEqual(f.damage['Melee'],120*(1-p['encounter']['target_physical_mitigation']))

    def test_thunderfury_proc_damage_and_threat(self):
        p=self.basic(); p['character'].update(hit_chance=1,crit_chance=0)
        p['gear']['main_hand']=19019
        p['model'].update(thunderfury_proc_chance=1,thunderfury_damage=300,thunderfury_threat_multiplier=1.43)
        p['talents']={k:0 for k in p['talents']}
        f=Fight(p,0); f.swing()
        self.assertEqual(f.damage['Thunderfury'],300)
        melee=f.damage['Melee']
        self.assertAlmostEqual(f.threat,melee+300*1.43)

    def test_classic_gear_bridge_derives_armor_and_primary_stats(self):
        p=self.basic(); p['model']['use_classic_era_conversions']=True
        r=simulate(p); c=r['effective_character']
        self.assertGreater(c['attack_power'],0); self.assertGreater(c['armor'],0)
        self.assertAlmostEqual(c['physical_mitigation'],c['armor']/(c['armor']+400+85*c['level']))

    def test_shield_expiration(self):
        p=self.basic(); p['character'].update(avoidance=0,block_chance=1)
        f=Fight(p,0); f.hs_charges=4; f.hs_until=10; f.time=10; f.enemy()
        self.assertEqual(f.damage['Holy Shield'],0)

    def test_bulwark_absorption_conserves_damage(self):
        p=self.basic(); p['character'].update(avoidance=0,block_chance=0,physical_mitigation=0)
        p['encounter'].update(enemy_damage_min=1000,enemy_damage_max=1000,enemy_crit_chance=0)
        p['talents']={k:0 for k in p['talents']}
        f=Fight(p,0); f.absorb=1500; f.absorb_until=8; f.enemy(); f.enemy()
        self.assertEqual(f.absorbed,1500); self.assertEqual(f.taken,500)
        self.assertEqual(f.health,p['character']['health']-500)

    def test_bulwark_expired_does_not_absorb(self):
        p=self.basic(); p['character'].update(avoidance=0,block_chance=0,physical_mitigation=0)
        p['encounter'].update(enemy_damage_min=1000,enemy_damage_max=1000,enemy_crit_chance=0)
        p['talents']={k:0 for k in p['talents']}
        f=Fight(p,0); f.time=8; f.absorb=1500; f.absorb_until=8; f.enemy()
        self.assertEqual(f.absorbed,0); self.assertEqual(f.taken,1000)

    def test_bulwark_health_threshold_and_cooldown(self):
        p=self.basic(); f=Fight(p,0); f.health=500; f.decision()
        self.assertEqual(f.absorb,p['character']['health'])
        self.assertEqual(f.cd['bulwark'],300); self.assertEqual(f.forbearance,60)
        f.time=9; f.decision(); self.assertEqual(f.casts["Templar's Bulwark"],1)

    def test_no_incoming_has_no_tank_damage(self):
        r=simulate(self.basic('retribution'))
        self.assertEqual(r['metrics']['dtps']['mean'],0); self.assertEqual(r['metrics']['survival_fraction'],1)

    def test_death_stops_all_future_player_actions(self):
        p=self.basic(); p['encounter'].update(enemy_damage_min=1e6,enemy_damage_max=1e6,heal_amount=0)
        p['character'].update(avoidance=0,block_chance=0)
        p['talents']={k:0 for k in p['talents']}
        r=Fight(p,0,True).run()
        self.assertFalse(r['survived']); self.assertEqual(r['alive_seconds'],2)
        self.assertEqual(r['log'][-1]['event'],'Death')
        self.assertTrue(all(x['time']<=2 for x in r['log']))

    def test_mana_never_negative_when_starved(self):
        p=self.basic('retribution'); p['character'].update(mana=10,mana_per_second=0)
        r=Fight(p,0,True).run()
        self.assertEqual(r['first_unaffordable_cast'],0); self.assertEqual(r['mana_spent'],0)
        self.assertGreater(r['damage']['Melee'],0)

    def test_echo_consumed_once(self):
        p=self.basic('retribution'); p['character'].update(hit_chance=1,crit_chance=0)
        p['model']['command_proc_chance']=1
        f=Fight(p,0); f.cast_seal('command'); f.time=1.5; f.cast_seal('righteousness')
        self.assertEqual(f.echo,'command'); f.swing(); f.swing()
        self.assertEqual(f.hits['Seal of Command echo'],1); self.assertIsNone(f.echo)

    def test_disabled_twisting_never_generates_echo(self):
        p=self.basic('retribution'); p['rotation']['twist_seals']=False
        r=simulate(p); self.assertFalse(any('echo' in name for name in r['ability_dps']))

    def test_vengeance_caps_and_expires(self):
        p=self.basic('retribution'); p['character']['crit_chance']=1
        p['talents']['110883']=0
        f=Fight(p,0)
        for _ in range(9): f.deal('Test melee',100,can_crit=True)
        self.assertEqual(f.vengeance,5)
        f.time=30; f.deal('After expiration',100,can_crit=False)
        self.assertEqual(f.vengeance,0); self.assertAlmostEqual(f.damage['After expiration'],70)

    def test_mana_proc_internal_cooldown(self):
        p=self.basic(); p['character'].update(avoidance=0,block_chance=1)
        p['talents']={k:0 for k in p['talents']}; p['talents']['110874']=1
        f=Fight(p,0); f.mana=0
        class ZeroRandom:
            def random(self): return 0
            def uniform(self,a,b): return a
        f.rng=ZeroRandom(); f.enemy(); first=f.mana; f.time=1; f.enemy()
        self.assertEqual(first,p['character']['mana']*.06); self.assertEqual(f.mana,first)
        f.time=3; f.enemy(); self.assertEqual(f.mana,first*2)

    def test_more_healing_does_not_resurrect(self):
        p=self.basic(); p['character'].update(avoidance=0,block_chance=0)
        p['encounter'].update(enemy_damage_min=1e6,enemy_damage_max=1e6,heal_amount=1e7,heal_interval=3)
        p['talents']={k:0 for k in p['talents']}
        r=Fight(p,0).run(); self.assertFalse(r['survived']); self.assertEqual(r['effective_healing'],0)

    def test_invalid_inputs_rejected(self):
        for path,value in [('duration',0),('iterations',1.5),('seed',-1),('character.weapon_speed',0),
                           ('character.hit_chance',1.1),('character.health',math.nan),('encounter.enemies',0),
                           ('encounter.incoming_enabled',1),('character.weapon_min',1e20)]:
            with self.subTest(path=path):
                p=self.basic(); keys=path.split('.'); obj=p
                for key in keys[:-1]: obj=obj[key]
                obj[keys[-1]]=value
                with self.assertRaises(ValueError): validate(p)

    def test_forever_talent_dataset_and_build_limits(self):
        self.assertEqual(sum(len(tree['talents']) for tree in TALENT_DATA['trees']), 52)
        self.assertEqual({tree['name'] for tree in TALENT_DATA['trees']}, {'Holy','Protection','Retribution'})
        self.assertTrue(all(url.startswith('https://www.wowhead.com/forever/')
                            for url in [TALENT_DATA['source']]))
        self.assertEqual(sum(preset('protection')['talents'].values()), 51)
        self.assertEqual(sum(preset('retribution')['talents'].values()), 51)
        p=self.basic(); p['talents']={k:0 for k in p['talents']}; p['talents']['105628']=1
        with self.assertRaisesRegex(ValueError,'prior Protection tiers'): validate(p)
        p=preset('protection'); p['talents']['105625']=0; p['talents']['110879']=1
        with self.assertRaisesRegex(ValueError,'requires Templar'): validate(p)
        p=preset('protection')
        for talent_id,talent in TALENTS.items(): p['talents'][talent_id]=len(talent['ranks'])
        with self.assertRaisesRegex(ValueError,'51-point'): validate(p)

    def test_role_presets_maximize_modeled_throughput_talents(self):
        prot=preset('protection')['talents']
        for talent_id in ('105626','105634','110874','105627','105628','105705','105701'):
            self.assertEqual(prot[talent_id],len(TALENTS[talent_id]['ranks']))
        ret=preset('retribution')['talents']
        for talent_id in ('105705','105701','105696','105693','105692','105697','110883'):
            self.assertEqual(ret[talent_id],len(TALENTS[talent_id]['ranks']))

    def test_one_iteration_has_no_false_precision(self):
        p=self.basic(); p['iterations']=1
        self.assertIsNone(simulate(p)['metrics']['dps']['mean_95ci_half_width'])

    def test_no_event_at_fight_endpoint(self):
        p=self.basic('retribution'); p['duration']=7; p['character']['weapon_speed']=3.5
        p['character']['hit_chance']=1
        r=Fight(p,0,True).run(); self.assertEqual(r['hits']['Melee'],2)
        self.assertTrue(all(e['time']<7 for e in r['log']))

if __name__=='__main__': unittest.main()

