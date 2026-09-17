"""Small event-driven, source-audited Forever Paladin mechanics prototype.

No third-party dependencies. All unstated game rules are explicit model assumptions.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import heapq
import json
import math
import random
import statistics
from collections import defaultdict, deque
from pathlib import Path
from gear_data import apply_gear, phase6_gear
from engine_data import RACIALS, RACE_STATS, CLASS_BASE, CLASS_RACES

ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / 'data.json').read_text(encoding='utf-8'))
F = DATA['facts']
TALENT_DATA = json.loads((ROOT / 'paladin_talents.json').read_text(encoding='utf-8'))
CONSUMABLE_DATA = json.loads((ROOT / 'consumables.json').read_text(encoding='utf-8'))
CONSUMABLE_GROUPS = {item['key']: item['group'] for item in CONSUMABLE_DATA['items']}
TALENTS = {str(t['id']): t for tree in TALENT_DATA['trees'] for t in tree['talents']}
TREE_TALENTS = {tree['name']: [str(t['id']) for t in tree['talents']] for tree in TALENT_DATA['trees']}

PROTECTION_BUILD = {
    '105630': 5, '105626': 5, '105638': 3, '110875': 1, '105634': 3,
    '110874': 3, '110878': 1, '105629': 3, '105625': 1, '105627': 5, '105628': 1,
    '105707': 5, '105706': 5, '105705': 2, '105703': 4, '105701': 3, '105696': 1,
}
RETRIBUTION_BUILD = {
    '105707': 5, '105706': 5, '105705': 2, '105703': 5, '105701': 3,
    '105696': 1, '105700': 1, '110883': 2, '105697': 3, '105693': 3, '105692': 1,
    '105328': 2, '105639': 5, '105332': 3, '105333': 3, '105335': 2,
    '105334': 3, '105331': 2,
}

def talent_build(spec):
    build = {talent_id: 0 for talent_id in TALENTS}
    build.update(PROTECTION_BUILD if spec == 'protection' else RETRIBUTION_BUILD)
    return build

ASSUMPTIONS = [
    'Base attributes use the WoWSims Classic level-60 Paladin table plus Forever race offsets (Human, Dwarf, Undead). Race selection applies the sourced Forever racial (Sword/Mace Specialization, Touch of the Grave).',
    'The optional Classic Era audit converts equipped Strength, Agility, Stamina, Intellect, attack power and armor with level-60 Classic formulas. It is not asserted as a Forever ruleset.',
    'Weapon attacks add attack-power normalization (AP / 14 * weapon speed) when the Classic Era audit is enabled.',
    'Outgoing hit and conditional crit use independent rolls. Incoming avoidance/block/crit use one ordered table.',
    'The Classic Era audit derives armor mitigation and applies defense reduction to incoming critical chance plus level-63 crushing blows. Full attack-table ordering and resistances remain approximate.',
    'Thunderfury uses an explicit, editable Classic audit proc model because its item tooltip supplies damage but not proc rate or threat behavior.',
    'Default Classic Anniversary raid support excludes every world buff. It includes improved Fortitude, Mark, Arcane Intellect, improved Battle Shout, improved Might and Devotion Aura.',
    'Default target debuffs are the compatible physical/Holy tank package: five Sunders, Faerie Fire, Curse of Recklessness, Judgement of the Crusader, Gift of Arthas, Demoralizing Shout, Thunder Clap, Insect Swarm and Scorpid Sting.',
    'All Settings toggles affect the model. Judgement of the Crusader uses 140 Holy bonus with explicit spell coefficients; Demoralizing Shout provisionally reduces raw boss damage by 10%.',
    'Righteousness swing damage is a user-supplied effective value (default 50); its speed/scaling formula is unresolved.',
    'Command proc probability (default 25% per landed swing) is an experiment input, not a sourced Forever proc rate.',
    'Seal procs do not crit or roll a second hit check. Judgements may crit with the supplied spell multiplier.',
    'Judgement consumes the active seal; seal casts use 1.5 s GCD. Non-seal defensive GCDs also use 1.5 s provisionally.',
    'Twisting stores one echo, consumed on the next melee attempt even if it misses. No echo stacking or expiration.',
    'Vengeance refreshes all stacks together; only modeled direct attack and Judgement crits trigger it.',
    'Reckoning grants an immediate extra swing, can trigger seals, and does not reset the normal swing timer.',
    'Mana regenerates in two-second ticks: mp5 always, Spirit (Spirit/5 + 15 per tick) only outside the five-second rule or at the Reverence talent fraction while casting. Major Mana Potion and Demonic Rune are used on cooldown when the deficit allows.',
    'Healing is a fixed pulse on a configurable timer; no healer mana, aggro, reaction time or spell model.',
    'Enemy attacks stay on the tank regardless of threat. Damage uses one base threat per damage by default. Holy base threat is editable; the separate WoWSims Classic audit uses 1.5, which is not treated as a Forever fact.',
    'Equal-time order: player decision, player swing, enemy swings, healing. Events at fight end are excluded.',
    'A fresh fight starts at full health/mana, no active seal, and Righteous Fury pre-applied for Protection.',
    'The talent calculator enforces the sourced Forever ranks, prerequisites, five-points-per-tier rule and 51-point cap.',
    'Precision, Conviction, Deflection, Improved Seals, Crusade, and one/two-handed weapon specializations use their sourced Forever rank text.',
    'Sourced Forever set bonuses are applied at their equipped-piece thresholds. Unresolved proc/control effects remain labeled informational.',
    'Consecration Rank 5 uses its Forever level-60 tooltip: 565 mana, 384 Holy damage over 8 sec, 8 sec cooldown.',
    'Holy Strike uses the supplied unranked/low-rank record exactly (75 mana, next melee becomes Holy and gains 2 damage); its missing base cooldown is editable and defaults provisionally to 6 sec.',
    'Seal of Fury remains unresolved because its indexed Forever rank records omit cost, shield amount, duration and Judgement effect.'
]

def preset(spec='protection'):
    if spec not in ('protection', 'retribution'):
        raise ValueError('Spec must be protection or retribution')
    prot = spec == 'protection'
    return {
        'spec': spec, 'race':'Human', 'duration':120.0, 'duration_variance':0.0, 'iterations':300, 'seed':42,
        'character': {'health':1381.0, 'mana':1512.0,
            'base_mana':1512.0, 'mana_per_second':0.0, 'spirit':75.0, 'mp5':0.0,
            'level':60.0, 'strength':105.0, 'agility':65.0, 'stamina':100.0, 'intellect':70.0,
            'attack_power':160.0, 'spell_power':0.0, 'armor':0.0, 'defense':300.0,
            'weapon_min':1.0, 'weapon_max':2.0,
            'weapon_speed':2.0, 'hit_chance':0.92, 'crit_chance':0.007,
            'spell_hit_chance':0.83, 'spell_crit_chance':0.035,
            'physical_mitigation':0.0, 'avoidance':0.057,
            'block_chance':0.05 if prot else 0.0, 'block_value':0.0},
        'encounter': {'preset_name':'Patchwerk (120-second single-target model)',
            'enemies':1, 'enemy_swing':2.0, 'enemy_damage_min':2700.0, 'enemy_damage_max':3300.0,
            'target_level':63.0, 'target_armor':3731.0, 'boss_type':'none',
            'enemy_crit_chance':0.05, 'enemy_crit_multiplier':2.0,
            'target_physical_mitigation':0.3, 'heal_amount':2500.0,
            'heal_interval':2.0, 'incoming_enabled':prot},
        'raid_buffs': {'power_word_fortitude':True, 'mark_of_the_wild':True,
            'arcane_intellect':True, 'battle_shout':True, 'blessing_of_might':True,
            'devotion_aura':prot, 'blessing_of_kings':True, 'blessing_of_wisdom':True,
            'strength_of_earth':True, 'windfury_totem':not prot, 'grace_of_air':False,
            'mana_spring':True, 'leader_of_the_pack':True, 'moonkin_aura':False, 'trueshot_aura':False},
        'consumables': {'flask_of_the_titans':prot, 'elixir_of_the_mongoose':True,
            'elixir_of_superior_defense':prot, 'elixir_of_fortitude':prot,
            'greater_stoneshield_potion':prot, 'smoked_desert_dumplings':True,
            'rumsey_rum_black_label':prot, 'mageblood_potion':True,
            'juju_power':True, 'juju_might':True, 'brilliant_wizard_oil':True,
            'gift_of_arthas':prot, 'major_mana_potion':not prot, 'demonic_rune':True,
            'goblin_sapper_charge':True, 'dragonbreath_chili':True},
        'debuffs': {'sunder_armor_5':True, 'faerie_fire':True, 'curse_of_recklessness':True,
            'judgement_of_the_crusader':True, 'gift_of_arthas':True,
            'demoralizing_shout':True, 'thunder_clap':True,
            'insect_swarm':True, 'scorpid_sting':True},
        'model': {'command_proc_chance':0.25, 'righteousness_damage':50.0,
            'holy_strike_bonus':2.0, 'holy_strike_cost':75.0, 'holy_strike_cooldown':6.0,
            'melee_crit_multiplier':2.0, 'spell_crit_multiplier':1.5,
            'base_threat_per_damage':1.0, 'holy_threat_per_damage':1.0,
            'use_classic_era_conversions':True, 'thunderfury_proc_chance':0.20,
            'thunderfury_damage':300.0, 'thunderfury_threat_multiplier':1.43},
        'rotation': {'use_judgement':True, 'use_consecration':True, 'consecration_mana_floor':0.30, 'use_holy_strike':prot, 'use_exorcism':True, 'use_holy_wrath':True, 'twist_seals':not prot,
            'use_bulwark':prot, 'bulwark_health_threshold':0.5},
        'gear': phase6_gear(spec),
        'talents': talent_build(spec)
    }

def validate(p):
    if not isinstance(p, dict) or p.get('spec') not in ('protection','retribution'):
        raise ValueError('Choose protection or retribution.')
    if isinstance(p, dict) and 'race' not in p: p['race'] = 'Human'
    if p.get('race') not in CLASS_RACES['Paladin']:
        raise ValueError(f"{p.get('race')} cannot be a Paladin in World of Warcraft: Forever.")
    template = preset(p['spec'])
    def walk(value, schema, path='profile'):
        if isinstance(schema, dict):
            if not isinstance(value, dict) or set(value) != set(schema):
                raise ValueError(f'{path}: fields must be {", ".join(schema)}')
            for key in schema: walk(value[key], schema[key], f'{path}.{key}')
        elif isinstance(schema, bool):
            if type(value) is not bool: raise ValueError(f'{path} must be true or false')
        elif isinstance(schema, (float,int)):
            if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
                raise ValueError(f'{path} must be a finite number')
            if value < 0: raise ValueError(f'{path} must be nonnegative')
            if value > 2**32: raise ValueError(f'{path} exceeds the prototype numeric limit')
        elif not isinstance(value,str): raise ValueError(f'{path} must be text')
    walk(p,template)
    tree_points = {}
    for tree_name, ids in TREE_TALENTS.items():
        tree_points[tree_name] = sum(p['talents'][talent_id] for talent_id in ids)
        for talent_id in ids:
            rank = p['talents'][talent_id]
            talent = TALENTS[talent_id]
            if type(rank) is not int or not 0 <= rank <= len(talent['ranks']):
                raise ValueError(f"{talent['name']} rank must be 0..{len(talent['ranks'])}")
            if rank:
                prior = sum(p['talents'][other] for other in ids if TALENTS[other]['row'] < talent['row'])
                needed = talent['row'] * TALENT_DATA['points_per_tier']
                if prior < needed:
                    raise ValueError(f"{talent['name']} requires {needed} points in prior {tree_name} tiers")
                for requirement in talent['requires']:
                    if p['talents'][str(requirement['id'])] < requirement['qty']:
                        required_name = TALENTS[str(requirement['id'])]['name']
                        raise ValueError(f"{talent['name']} requires {required_name} rank {requirement['qty']}")
    if sum(tree_points.values()) > TALENT_DATA['max_points']:
        raise ValueError(f"Talent build exceeds the {TALENT_DATA['max_points']}-point level-60 limit")
    active_groups = {}
    for key, enabled in p['consumables'].items():
        if enabled:
            group = CONSUMABLE_GROUPS[key]
            if group in active_groups:
                raise ValueError(f"{key} cannot be combined with {active_groups[group]} ({group.replace('_',' ')} group)")
            active_groups[group] = key
    for key, low, high in [('duration',1,1800),('duration_variance',0,60),('iterations',1,10000),('seed',0,2**32-1)]:
        if not low <= p[key] <= high: raise ValueError(f'{key} must be {low}..{high}')
    for key in ('iterations','seed'):
        if type(p[key]) is not int: raise ValueError(f'{key} must be an integer')
    if p['duration'] * p['iterations'] > 400_000: raise ValueError('Run too large; keep duration x iterations at or below 400,000 seconds.')
    c,e,m,r = (p[k] for k in ('character','encounter','model','rotation'))
    for obj,key in [(c,'health'),(c,'mana'),(c,'weapon_speed'),(e,'enemy_swing'),(e,'heal_interval')]:
        if obj[key] < 0.1: raise ValueError(f'{key} must be at least 0.1')
    if type(e['enemies']) is not int or not 1 <= e['enemies'] <= 20:
        raise ValueError('enemies must be an integer from 1 to 20')
    if e['boss_type'] not in {'none','beast','demon','dragonkin','elemental','giant','humanoid','mechanical','undead'}:
        raise ValueError('Choose a supported boss creature type.')
    if c['weapon_min'] > c['weapon_max']: raise ValueError('weapon_min exceeds weapon_max')
    if e['enemy_damage_min'] > e['enemy_damage_max']: raise ValueError('enemy_damage_min exceeds enemy_damage_max')
    for obj,keys in [(c,['hit_chance','crit_chance','spell_hit_chance','spell_crit_chance','physical_mitigation','avoidance','block_chance']),
                     (e,['enemy_crit_chance','target_physical_mitigation']),
                     (m,['command_proc_chance','thunderfury_proc_chance']), (r,['bulwark_health_threshold','consecration_mana_floor'])]:
        for key in keys:
            if not 0 <= obj[key] <= 1: raise ValueError(f'{key} must be between 0 and 1')
    if p['duration'] * p['iterations'] * (1/c['weapon_speed'] + e['enemies']/e['enemy_swing'] + 10 + 1/e['heal_interval']) > 30_000_000:
        raise ValueError('Run too large; reduce iterations, duration, or enemies.')
    return p

class Fight:
    def __init__(self, profile, seed, trace=False):
        self.p=profile; self.c=profile['character']; self.e=profile['encounter']
        self.m=profile['model']; self.tal=profile['talents']; self.rot=profile['rotation']
        self.prot=profile['spec']=='protection'; self.rng=random.Random(seed)
        self.time=0.0; self.health=self.c['health']; self.mana=self.c['mana']
        self.queue=[]; self.serial=0; self.gcd=0.0; self.cd=defaultdict(float)
        self.seal=None; self.seal_until=0.0; self.echo=None
        self.holy_strike_queued=False; self.iron_until=0.0
        self.hs_until=0.0; self.hs_charges=0; self.red_until=0.0; self.red_charges=0
        self.absorb=0.0; self.absorb_until=0.0; self.forbearance=0.0
        self.vengeance=0; self.vengeance_until=0.0; self.mana_icd=0.0
        self.damage=defaultdict(float); self.threat_by_source=defaultdict(float); self.taken_by_source=defaultdict(float); self.hits=defaultdict(int); self.casts=defaultdict(int)
        self.threat=0.0; self.taken=0.0; self.absorbed=0.0; self.blocked=0.0
        self.healed=0.0; self.overheal=0.0; self.blocks=0; self.avoids=0
        self.mana_spent=0.0; self.mana_gained=0.0; self.oom=None
        self.alive=True; self.life=profile['duration']; self.trace=trace; self.log=[]
        self.damage_window=deque(); self.window_sum=0.0; self.peak_three_seconds=0.0
        self.race=profile.get('race','Human'); self.racial=RACIALS.get(self.race,{})
        self.last_cast=-10.0; self.next_mana_tick=2.0; self.potion_cd=0.0; self.rune_cd=0.0
        self.sapper_used=False

    def rank(self, talent_id):
        return self.tal[str(talent_id)]

    def pull_haste(self):
        return 1.30 if self.time < 40.0 else 1.0

    def schedule(self,time,kind):
        priority={'decision':0,'swing':1,'consecration':2,'enemy':3,'heal':4,'mana':5}[kind]
        self.serial+=1; heapq.heappush(self.queue,(time,priority,self.serial,kind))

    def record(self,event,amount=0):
        if self.trace:
            self.log.append({'time':round(self.time,4),'event':event,'amount':round(amount,3),
                             'health':round(self.health,3),'mana':round(self.mana,3)})

    def gain_mana(self,amount):
        gained=min(amount,self.c['mana']-self.mana)
        self.mana+=gained; self.mana_gained+=gained

    def spend(self,name,amount):
        amount*=1-0.10*self.rank(105706) if name.startswith('Seal') or name in ('Judgement','Holy Shield','Holy Strike',"Templar's Bulwark") else 1
        if self.mana+1e-9 < amount:
            if self.oom is None: self.oom=self.time
            return False
        self.mana=max(0,self.mana-amount); self.mana_spent+=amount; self.last_cast=self.time
        self.casts[name]+=1; self.record('Cast '+name)
        return True

    def mana_tick(self):
        c=self.c
        regen=c.get('mp5',0.0)/5*2
        spirit=c.get('spirit',0.0)/5+15
        if self.time-self.last_cast>=5: regen+=spirit
        else: regen+=spirit*0.10*self.rank(110871)
        self.gain_mana(regen)
        if self.p['consumables'].get('major_mana_potion') and self.time>=self.potion_cd and c['mana']-self.mana>=1800:
            self.gain_mana(self.rng.uniform(1350,2250)); self.potion_cd=self.time+120; self.casts['Major Mana Potion']+=1; self.record('Major Mana Potion')
        if self.p['consumables'].get('demonic_rune') and self.time>=self.rune_cd and c['mana']-self.mana>=1500:
            self.gain_mana(self.rng.uniform(900,1500)); self.rune_cd=self.time+120; self.casts['Demonic Rune']+=1; self.record('Demonic Rune')

    def touch_of_the_grave(self):
        tg=self.racial.get('touch_of_the_grave')
        if tg and self.rng.random()<tg['chance']:
            self.deal('Touch of the Grave',self.c['health']*tg['health_fraction'],holy=True,physical=False,hit=1)

    def deal(self,name,amount,holy=False,can_crit=False,hit=1.0,extra_threat=1.0,melee_crit=False,physical=None,spell_coefficient=0.0):
        precision=0.01*self.rank(105638)
        hit=min(1,hit+precision)
        if self.rng.random() >= hit:
            self.record(name+' miss'); return False
        crit=self.c['crit_chance' if melee_crit or not holy else 'spell_crit_chance']
        if melee_crit or not holy: crit+=0.01*self.rank(105703)
        critical=can_crit and self.rng.random() < min(1,crit)
        if self.time >= self.vengeance_until: self.vengeance=0
        if holy and spell_coefficient:
            holy_bonus=self.c['spell_power']+(140 if self.p['debuffs']['judgement_of_the_crusader'] else 0)
            amount+=holy_bonus*spell_coefficient
        amount*=1 + self.vengeance*F['vengeance_rank1']['bonus_per_stack']*self.rank(105693)
        crusade_rank=self.rank(110883)
        creature_crusade=crusade_rank if self.e['boss_type'] in {'demon','undead'} else 0
        amount*=1+0.01*(crusade_rank+creature_crusade)
        if physical is None: physical=not holy
        if physical and self.p['debuffs']['gift_of_arthas'] and self.p['consumables']['gift_of_arthas']: amount+=8
        if physical: amount*=1-self.e['target_physical_mitigation']
        if critical: amount*=self.m['melee_crit_multiplier' if melee_crit or not holy else 'spell_crit_multiplier']
        self.damage[name]+=amount; self.hits[name]+=1
        base_threat=self.m['holy_threat_per_damage'] if holy else self.m['base_threat_per_damage']
        generated=amount*base_threat*extra_threat*(F['righteous_fury']['holy_threat_multiplier'] if holy and self.prot else 1)
        self.threat+=generated; self.threat_by_source[name]+=generated
        self.record(name+(' crit' if critical else ''),amount)
        if name!='Touch of the Grave' and not name.startswith('Consecration'): self.touch_of_the_grave()
        if critical and self.rank(105693):
            self.vengeance=min(F['vengeance_rank1']['max_stacks'],self.vengeance+1)
            self.vengeance_until=self.time+F['vengeance_rank1']['duration']
        return True

    def seal_proc(self,seal,weapon,echo=False):
        suffix=' echo' if echo else ''
        seal_bonus=1+0.05*self.rank(105334)
        if seal=='command' and self.rng.random() < self.m['command_proc_chance']:
            self.deal('Seal of Command'+suffix,weapon*F['command']['weapon_fraction']*seal_bonus,holy=True,spell_coefficient=.29)
        elif seal=='righteousness':
            self.deal('Seal of Righteousness'+suffix,self.m['righteousness_damage']*seal_bonus,holy=True,spell_coefficient=.10)

    def swing(self,extra=False,bonus_ap=0.0):
        weapon=self.rng.uniform(self.c['weapon_min'],self.c['weapon_max'])
        if self.m['use_classic_era_conversions']:
            weapon += (self.c['attack_power']+bonus_ap)/14*self.c['weapon_speed']
        if self.c.get('weapon_hands')=='Two-Hand': weapon*=1+(0,0.03,0.06,0.09)[self.rank(105697)]
        elif self.c.get('weapon_hands') in ('One-Hand','Main Hand'): weapon*=1+(0,0.03,0.07,0.10)[self.rank(105629)]
        holy_strike=self.holy_strike_queued and not extra
        if holy_strike:
            self.holy_strike_queued=False; iron=self.rank(110879)
            landed=self.deal('Holy Strike',weapon+self.m['holy_strike_bonus'],holy=True,can_crit=True,
                             hit=self.c['hit_chance'],extra_threat=1+0.05*iron,melee_crit=True)
            if landed and iron: self.iron_until=self.time+6
        else:
            landed=self.deal('Windfury Attack' if bonus_ap else 'Reckoning' if extra else 'Melee',weapon,can_crit=True,hit=self.c['hit_chance'])
        if landed and not extra and self.p['raid_buffs'].get('windfury_totem') and self.rng.random()<0.20:
            self.swing(extra=True,bonus_ap=315)
        if landed:
            if self.p['consumables'].get('dragonbreath_chili') and self.rng.random()<0.05:
                self.deal('Dragonbreath Chili',self.rng.uniform(60,90),holy=False,physical=False,hit=1)
            if self.p['gear']['main_hand']==19019 and self.rng.random()<self.m['thunderfury_proc_chance']:
                self.deal('Thunderfury',self.m['thunderfury_damage'],holy=False,physical=False,hit=1,
                          extra_threat=self.m['thunderfury_threat_multiplier'])
            if self.time < self.seal_until: self.seal_proc(self.seal,weapon)
            if self.echo: self.seal_proc(self.echo,weapon,True)
        self.echo=None
        if not extra: self.schedule(self.time+self.c['weapon_speed']/self.pull_haste(),'swing')

    def cast_seal(self,seal):
        if not self.spend('Seal of '+seal.title(),F[seal]['cost']): return False
        if self.seal and self.time < self.seal_until and self.seal != seal and self.rank(105692):
            self.echo=self.seal
        self.seal=seal; self.seal_until=self.time+F[seal]['duration']
        self.gcd=self.time+F['righteousness']['gcd']/self.pull_haste(); return True

    def decision(self):
        # Judgement is off-GCD. Do not consume an already queued echo.
        if self.rot['use_judgement'] and self.time>=self.cd['judgement'] and self.time<self.seal_until:
            cost=F['judgement']['base_mana_fraction']*self.c['base_mana']
            if self.spend('Judgement',cost):
                seal=self.seal; f=F[seal]
                self.deal('Judgement of '+seal.title(),self.rng.uniform(f['judgement_min'],f['judgement_max'])*(1+0.05*self.rank(105334)),
                          holy=True,can_crit=True,hit=self.c['spell_hit_chance'],spell_coefficient=.43)
                self.seal=None; self.seal_until=0
                cd=F['judgement']['cooldown']-F['improved_judgement_rank1']['cooldown_reduction']*self.rank(105705)
                self.cd['judgement']=self.time+cd
                sj_rank=self.rank(105701)
                if sj_rank and self.rng.random()<min(1,F['sanctified_judgement_rank1']['proc']*sj_rank):
                    self.gain_mana(f['cost']*F['sanctified_judgement_rank1']['seal_refund_fraction']*sj_rank)
        if self.time+1e-9>=self.gcd:
            acted=False
            if self.prot and self.rank(105625) and self.rot['use_bulwark'] and self.time>=max(self.cd['bulwark'],self.forbearance) and self.health/self.c['health']<=self.rot['bulwark_health_threshold']:
                if self.spend("Templar's Bulwark",F['bulwark']['cost']):
                    self.absorb=self.c['health']*F['bulwark']['health_fraction']
                    self.absorb_until=self.time+F['bulwark']['duration']
                    self.cd['bulwark']=self.time+F['bulwark']['cooldown']-30*self.rank(105632)
                    self.forbearance=self.time+F['bulwark']['forbearance']; acted=True
            if not acted and self.prot and self.rank(105628) and self.time>=self.cd['holy_shield']:
                if self.spend('Holy Shield',F['holy_shield']['cost']):
                    self.hs_until=self.time+F['holy_shield']['duration']; self.hs_charges=F['holy_shield']['charges']
                    self.cd['holy_shield']=self.time+F['holy_shield']['cooldown']; acted=True
            eligible_holy_target=self.e['boss_type'] in {'demon','undead'}
            conduit_discount=1-.20*self.rank(105704)
            purifying_cd=(1,.83,.67)[self.rank(105327)]
            if not acted and eligible_holy_target and self.rot['use_exorcism'] and self.time>=self.cd['exorcism']:
                if self.spend('Exorcism',345*conduit_discount):
                    self.deal('Exorcism',self.rng.uniform(505,563),holy=True,can_crit=True,hit=self.c['spell_hit_chance'],spell_coefficient=.429)
                    self.cd['exorcism']=self.time+15*purifying_cd;acted=True
            if not acted and eligible_holy_target and self.rot['use_holy_wrath'] and self.time>=self.cd['holy_wrath']:
                if self.spend('Holy Wrath',805*conduit_discount):
                    self.deal('Holy Wrath',self.rng.uniform(490,576),holy=True,can_crit=True,hit=self.c['spell_hit_chance'],spell_coefficient=.19)
                    self.cd['holy_wrath']=self.time+60*purifying_cd
                    self.gcd=self.time+2.0/self.pull_haste();acted=True
            if not acted and self.rot['use_consecration'] and self.time>=self.cd['consecration'] and self.mana/self.c['mana']>=self.rot.get('consecration_mana_floor',0):
                con=F['consecration']
                if self.spend('Consecration',con['cost']):
                    for tick in range(1,con['ticks']+1): self.schedule(self.time+tick*con['duration']/con['ticks'],'consecration')
                    self.cd['consecration']=self.time+con['cooldown']; acted=True
            if acted and self.gcd<=self.time+1e-9: self.gcd=self.time+1.5/self.pull_haste()
            elif self.time>=self.seal_until:
                self.cast_seal('righteousness' if self.prot or not self.rank(105696) else 'command')
            elif self.rot['twist_seals'] and self.rank(105692) and not self.echo:
                self.cast_seal('righteousness' if self.seal=='command' else 'command')
        if self.rot['use_holy_strike'] and not self.holy_strike_queued and self.time>=self.cd['holy_strike']:
            if self.spend('Holy Strike',self.m['holy_strike_cost']):
                self.holy_strike_queued=True
                self.cd['holy_strike']=self.time+max(0.1,self.m['holy_strike_cooldown']-self.rank(105328))
        # Fixed decision cadence is explicitly a model assumption, not the event clock.
        self.schedule(round(self.time+0.1,8),'decision')

    def enemy(self):
        swing=self.e['enemy_swing']/(0.8 if self.p['debuffs']['thunder_clap'] else 1)
        self.schedule(self.time+swing,'enemy')
        hs=self.hs_charges>0 and self.time<self.hs_until
        red=self.red_charges>0 and self.time<self.red_until
        block=self.c['block_chance']+(F['holy_shield']['block_bonus'] if hs else 0)+(F['redoubt_rank1']['block_bonus']*self.rank(105626) if red else 0)
        miss_debuff=(0.02 if self.p['debuffs']['insect_swarm'] else 0)+(0.05 if self.p['debuffs']['scorpid_sting'] else 0)
        roll=self.rng.random(); avoid=min(1,self.c['avoidance']+0.01*self.rank(105707)+miss_debuff)
        if roll<avoid:
            self.avoids+=1; self.record('Enemy avoided'); return
        blocked=roll<min(1,avoid+block)
        defense_bonus=max(0,self.c['defense']-self.e['target_level']*5)
        crit_chance=max(0,self.e['enemy_crit_chance']-defense_bonus*0.0004) if self.m['use_classic_era_conversions'] else self.e['enemy_crit_chance']
        critical=not blocked and roll<min(1,avoid+block+crit_chance)
        crushing=False
        if self.m['use_classic_era_conversions'] and not blocked and not critical and self.e['target_level']-self.c['level']>=3:
            crushing=roll<min(1,avoid+block+crit_chance+0.15)
        multiplier=1.5 if crushing else self.e['enemy_crit_multiplier'] if critical else 1
        raw_damage=self.rng.uniform(self.e['enemy_damage_min'],self.e['enemy_damage_max'])
        if self.p['debuffs']['demoralizing_shout']: raw_damage*=0.90
        amount=raw_damage*multiplier*(1-self.c['physical_mitigation'])
        if blocked:
            self.blocks+=1
            ss_rank=self.rank(110874)
            value=self.c['block_value']*(1+F['shield_specialization_rank1']['block_value_bonus']*ss_rank)
            stopped=min(amount,value); self.blocked+=stopped; amount-=stopped
            if hs:
                self.hs_charges-=1
                self.deal('Holy Shield',F['holy_shield']['damage'],holy=True,extra_threat=F['holy_shield']['threat_multiplier'],spell_coefficient=.05)
            if red: self.red_charges-=1
            ss=F['shield_specialization_rank1']
            if ss_rank and self.time>=self.mana_icd and self.rng.random()<min(1,ss['mana_proc']*ss_rank):
                self.gain_mana(self.c['mana']*ss['mana_fraction']); self.mana_icd=self.time+ss['internal_cooldown']
        if self.prot and self.rank(105634): amount*=1-F['improved_righteous_fury_rank1']['damage_reduction']*self.rank(105634)
        if self.prot and self.time<self.iron_until: amount*=1-0.02*self.rank(110879)
        damaging=amount>0
        if self.time>=self.absorb_until: self.absorb=0
        absorbed=min(amount,self.absorb); self.absorb-=absorbed; self.absorbed+=absorbed; amount-=absorbed
        source='Boss block' if blocked else 'Boss critical' if critical else 'Boss crushing' if crushing else 'Boss melee'
        self.health=max(0,self.health-amount); self.taken+=amount; self.taken_by_source[source]+=amount
        self.damage_window.append((self.time,amount)); self.window_sum+=amount
        while self.damage_window and self.damage_window[0][0]<=self.time-3:
            self.window_sum-=self.damage_window.popleft()[1]
        self.peak_three_seconds=max(self.peak_three_seconds,self.window_sum)
        self.record('Enemy '+('block' if blocked else 'crit' if critical else 'crush' if crushing else 'hit'),amount)
        if self.health<=0:
            self.alive=False; self.life=self.time; self.record('Death'); return
        if damaging and self.rank(105626) and self.rng.random()<F['redoubt_rank1']['proc']:
            self.red_until=self.time+F['redoubt_rank1']['duration']; self.red_charges=F['redoubt_rank1']['charges']
        reck=F['reckoning_rank1']
        reck_rank=self.rank(105627)
        if reck_rank and ((blocked and self.rng.random()<min(1,reck['block_proc']*reck_rank)) or (critical and self.rng.random()<min(1,reck['crit_proc']*reck_rank))):
            self.swing(extra=True)

    def run(self):
        if self.prot:
            self.casts['Taunt']+=1
            self.record('Cast Taunt')
            self.schedule(1.5,'decision')
        else:
            self.schedule(0,'decision')
        self.schedule(self.c['weapon_speed']/1.30,'swing')
        self.schedule(2.0,'mana')
        if self.p['consumables'].get('goblin_sapper_charge'):
            self.deal('Goblin Sapper Charge',self.rng.uniform(450,750),holy=False,physical=False,hit=1)
        if self.e['incoming_enabled']:
            first_swing=self.e['enemy_swing']/(0.8 if self.p['debuffs']['thunder_clap'] else 1)
            for _ in range(self.e['enemies']): self.schedule(first_swing,'enemy')
            self.schedule(self.e['heal_interval'],'heal')
        previous=0
        while self.queue and self.alive:
            t,_,_,kind=heapq.heappop(self.queue)
            if t>=self.p['duration']: break
            self.time=t; self.gain_mana((t-previous)*self.c['mana_per_second']); previous=t
            if kind=='decision': self.decision()
            elif kind=='swing': self.swing()
            elif kind=='consecration': self.deal('Consecration',F['consecration']['total_damage']/F['consecration']['ticks'],holy=True,hit=1,spell_coefficient=.33/F['consecration']['ticks'])
            elif kind=='mana': self.mana_tick(); self.schedule(t+2.0,'mana')
            elif kind=='enemy': self.enemy()
            else:
                amount=min(self.e['heal_amount'],self.c['health']-self.health)
                self.health+=amount; self.healed+=amount; self.overheal+=self.e['heal_amount']-amount
                self.record('Healing',amount); self.schedule(t+self.e['heal_interval'],'heal')
        duration=self.p['duration']
        if self.alive: self.gain_mana((duration-previous)*self.c['mana_per_second'])
        return {'dps':sum(self.damage.values())/duration, 'tps':self.threat/duration,
            'dtps':self.taken/duration, 'alive_dtps':self.taken/max(self.life,0.001),
            'survived':self.alive,'alive_seconds':self.life,'peak_3s_damage':self.peak_three_seconds,
            'damage':dict(self.damage),'threat_by_source':dict(self.threat_by_source),'taken_by_source':dict(self.taken_by_source),'hits':dict(self.hits),'casts':dict(self.casts),
            'damage_taken':self.taken,'absorbed':self.absorbed,'blocked_damage':self.blocked,
            'blocks':self.blocks,'avoids':self.avoids,'effective_healing':self.healed,'overhealing':self.overheal,
            'mana_spent':self.mana_spent,'mana_gained':self.mana_gained,'ending_mana':self.mana,
            'first_unaffordable_cast':self.oom,'log':self.log}

def summarize(values):
    values=sorted(values); n=len(values); mean=statistics.fmean(values)
    se=statistics.stdev(values)/math.sqrt(n) if n>1 else None
    return {'mean':mean,'p05':values[int((n-1)*0.05)],'p95':values[int((n-1)*0.95)],
            'mean_95ci_half_width':1.96*se if se is not None else None}

def simulate(profile, progress=None):
    original=copy.deepcopy(validate(profile)); p,gear_summary=apply_gear(original); rows=[]; totals=defaultdict(float); damage_totals=defaultdict(float); threat_totals=defaultdict(float); taken_totals=defaultdict(float)
    for i in range(p['iterations']):
        iteration_profile=copy.deepcopy(p); iteration_profile['duration']=max(10,random.Random(p['seed']+i+100000).uniform(p['duration']-p['duration_variance'],p['duration']+p['duration_variance']))
        row=Fight(iteration_profile,p['seed']+i,trace=i==0).run(); rows.append(row)
        for name,damage in row['damage'].items():
            totals[name]+=damage/iteration_profile['duration']; damage_totals[name]+=damage
        for name,threat in row['threat_by_source'].items(): threat_totals[name]+=threat/iteration_profile['duration']
        for name,damage in row['taken_by_source'].items(): taken_totals[name]+=damage/iteration_profile['duration']
        if progress and (i%20==0 or i==p['iterations']-1): progress(i+1,p['iterations'])
    metrics={k:summarize([r[k] for r in rows]) for k in ['dps','tps','dtps','alive_dtps','alive_seconds','peak_3s_damage','ending_mana','absorbed','blocked_damage']}
    metrics['survival_fraction']=sum(r['survived'] for r in rows)/len(rows)
    metrics['unaffordable_cast_fraction']=sum(r['first_unaffordable_cast'] is not None for r in rows)/len(rows)
    return {'data_version':DATA['version'],'data_sha256':hashlib.sha256((ROOT/'data.json').read_bytes()).hexdigest(),
        'status':'EXPERIMENTAL — incomplete mechanics; not a validated Forever performance prediction',
        'profile':original,'effective_character':p['character'],'gear_summary':gear_summary,'metrics':metrics,
        'ability_dps':{k:v/len(rows) for k,v in sorted(totals.items(),key=lambda x:-x[1])},
        'ability_damage':{k:v/len(rows) for k,v in sorted(damage_totals.items(),key=lambda x:-x[1])},
        'ability_tps':{k:v/len(rows) for k,v in sorted(threat_totals.items(),key=lambda x:-x[1])},
        'taken_dtps':{k:v/len(rows) for k,v in sorted(taken_totals.items(),key=lambda x:-x[1])},
        'first_iteration':rows[0], 'sources':DATA['sources'],
        'assumptions':ASSUMPTIONS+['Rotation decisions are evaluated every 0.1 seconds; fixed-duration, single outgoing target.'],
        'notes':['DPS/TPS/DTPS divide by full fight duration, including time after death.',
                 'alive_dtps divides by time alive. Surviving time is censored at fight duration.',
                 'Confidence intervals cover random sampling only, not uncertainty in mechanics.',
                 'Independent seed per iteration; repeat the same profile and seed for identical results.']}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',choices=['protection','retribution'],default='protection')
    parser.add_argument('--race',choices=CLASS_RACES['Paladin'],default='Human')
    parser.add_argument('--profile',type=Path); parser.add_argument('--output',type=Path)
    parser.add_argument('--iterations',type=int); parser.add_argument('--seed',type=int)
    parser.add_argument('--write-profile',type=Path)
    args=parser.parse_args()
    p=json.loads(args.profile.read_text(encoding='utf-8')) if args.profile else preset(args.spec)
    if not args.profile: p['race']=args.race
    if args.iterations is not None: p['iterations']=args.iterations
    if args.seed is not None: p['seed']=args.seed
    if args.write_profile:
        args.write_profile.write_text(json.dumps(validate(p),indent=2),encoding='utf-8'); return
    result=simulate(p)
    if args.output: args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(result['status'])
    for name in ['dps','tps','dtps','alive_dtps','peak_3s_damage']:
        m=result['metrics'][name]; ci=m['mean_95ci_half_width']
        print(f'{name:18} {m["mean"]:10.2f}  mean 95% CI +/- {ci:.2f}' if ci is not None else f'{name}: {m["mean"]:.2f} (one sample)')
    print(f'Survived: {result["metrics"]["survival_fraction"]:.1%}')
    if args.output: print(f'Saved {args.output.resolve()}')

if __name__=='__main__': main()
