"""Classic Era item catalog and temporary stat bridge for the Forever prototype."""
from __future__ import annotations

import copy
import json
import re
from collections import defaultdict
from pathlib import Path

from .all_specs import ITEMS as _ALL_ITEMS
from .profile_rules import annotate_rating_assumptions, faction_allowed

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CATALOG = json.loads((DATA_DIR / "classic_era_items.json").read_text(encoding="utf-8"))
PHASE6_BIS = json.loads((DATA_DIR / "phase6_bis.json").read_text(encoding="utf-8"))
FOREVER_SETS = json.loads((DATA_DIR / "forever_set_bonuses.json").read_text(encoding="utf-8"))
# Same merged catalog the gear picker shows (Classic Era + Forever extras); copied because the
# loop below rewrites set data in place.
ITEMS = {iid: copy.deepcopy(item) for iid, item in _ALL_ITEMS.items()}
for item in ITEMS.values():
    annotate_rating_assumptions(item)
    item_set = item.get("set")
    override = FOREVER_SETS["sets"].get(item_set["name"]) if item_set else None
    if override:
        item_set["bonuses"] = copy.deepcopy(override["bonuses"])
        item_set["ruleset"] = "Forever"
        item_set["source"] = override["source"]
GEAR_SLOTS = ("head", "neck", "shoulders", "back", "chest", "wrist", "main_hand", "off_hand",
              "hands", "waist", "legs", "feet", "finger1", "finger2", "trinket1", "trinket2", "relic")

DIRECT_STATS = {
    "health": ("health", 1), "mana": ("mana", 1), "mp5": ("mp5", 1), "spirit": ("spirit", 1),
    "meleeHit": ("hit_chance", 0.01), "meleeCrit": ("crit_chance", 0.01),
    "spellHit": ("spell_hit_chance", 0.01), "spellCrit": ("spell_crit_chance", 0.01),
    "block": ("block_chance", 0.01), "blockValue": ("block_value", 1),
    "dodge": ("avoidance", 0.01), "parry": ("avoidance", 0.01),
}

# Temporary level-60 Classic Era bridge. These conversions are intentionally
# kept here, beside the Classic item catalog, rather than presented as Forever
# rules.
CLASSIC_PRIMARY = {
    "strength": "strength", "agility": "agility", "stamina": "stamina",
    "intellect": "intellect", "attackPower": "attack_power", "spellPower": "spell_power", "armor": "armor",
    "defense": "defense",
}

from .engine import SET_PATTERNS, _cooldown_seconds, _re, normalized_speed, permanent_item_stats
from .engine_data import BUFF_STATS as RAID_BUFF_STATS
from .engine_data import RACE_STATS, RACIALS

# Set bonuses with a Paladin-engine effect beyond flat stats (Wowhead Classic tooltips).
PALADIN_SET_FLAGS = {"Judgement Armor|8": "judgement_bonus_damage", "Battlegear of Eternal Justice|3": "eternal_justice_mana"}

CONSUMABLE_STATS = {
    "flask_of_the_titans": {"health": 1200},
    "elixir_of_the_mongoose": {"agility": 25, "meleeCrit": 2},
    "elixir_of_superior_defense": {"armor": 450},
    "elixir_of_fortitude": {"health": 120},
    "greater_stoneshield_potion": {"armor": 2000},
    "smoked_desert_dumplings": {"strength": 20},
    "rumsey_rum_black_label": {"stamina": 15},
    "mageblood_potion": {"mp5": 12},
    "juju_power": {"strength": 30},
    "juju_might": {"attackPower": 40},
    "brilliant_wizard_oil": {"spellPower": 36, "spellCrit": 1},
    # Gift of Arthas's attacker debuff proc is listed in the audit summary but
    # does not receive an invented uptime or threat value.
    "gift_of_arthas": {}, "major_mana_potion": {}, "demonic_rune": {}, "goblin_sapper_charge": {}, "dragonbreath_chili": {},
}

ENCHANTS = json.loads((DATA_DIR / 'enchants.json').read_text(encoding='utf-8'))['slots']

def item_stats_and_effects(item):
    """Keep permanent stats separate from event-triggered effects; unknown effects stay visible."""
    stats = permanent_item_stats(item)
    effects, unresolved = [], []
    for text in item.get('effects', []):
        handled = False
        if text.startswith('Equip:'):
            if _re(r'^Equip: \+\d+ (?:Mana Regeneration|(?:Shadow|Fire|Frost|Arcane|Nature|Holy) Spell Damage)$', text): handled = True
            patterns = list(SET_PATTERNS) + [('holyPower', r'Holy spells and effects by up to (\d+)')]
            for key, pattern in patterns:
                match = _re(pattern, text)
                if match and 'chance on' not in text.lower() and 'when struck' not in text.lower():
                    if key not in stats: stats[key] = float(match.group(1))
                    handled = True; break
            match = _re(r'(\d+)% chance on melee hit to gain 1 extra attack', text)
            if match:
                effects.append({'name': item['name'], 'kind': 'extra_attack', 'chance': float(match.group(1))/100}); handled = True
            if item['id'] == 11810 and 'When struck' in text:
                effects.append({'name': item['name'], 'kind': 'incoming_flat', 'chance': .01, 'value': 25, 'duration': 10, 'provisional': 'Force of Will trigger chance: 1% assumed; Forever proc frequency unconfirmed.'}); handled = True
            match = _re(r'Reduces the mana cost of your Seal spells by (\d+)', text)
            if match: stats['sealCostReduction'] = float(match.group(1)); handled = True
            if _re(r'Increased .+ \+\d+', text): handled = True
        elif text.startswith('Use:'):
            for stat, pattern in [('spell_power', r'damage and healing.*?up to (\d+) for (\d+) sec'), ('attack_power', r'attack power by (\d+).*?(?:for|lasts for) (\d+) sec')]:
                match = _re(pattern, text)
                if match:
                    effects.append({'name': item['name'], 'kind': 'use', 'stat': stat, 'value': float(match.group(1)), 'duration': float(match.group(2)), 'cooldown': _cooldown_seconds(text), 'shared_cooldown': float(match.group(2)) if item.get('slot') == 'Trinket' else 0}); handled = True; break
        elif item['id'] == 18348 and text.startswith('Chance on hit:'):
            effects.append({'name': item['name'], 'kind': 'weapon_defense', 'ppm': 2.0, 'duration': 10, 'defense': 13, 'armor': 300, 'provisional': 'Quel\'Serrar proc frequency: 2 PPM Classic fallback.'}); handled = True
        elif item['id'] == 19019 and text.startswith('Chance on hit:'):
            handled = True  # Explicit configurable Thunderfury model in Fight.
        if not handled: unresolved.append({'item': item['name'], 'effect': text})
    return stats, effects, unresolved

def empty_gear():
    return {slot: 0 for slot in GEAR_SLOTS}

def phase6_gear(spec):
    gear = empty_gear()
    gear.update(PHASE6_BIS[spec]["gear"])
    return gear


def paladin_enchants(spec):
    from .profile_rules import SLOTS, default_enchants
    labels = {v[0]: k for k, v in SLOTS.items()}
    gear = [{'slot': labels.get(slot, slot), 'id': iid} for slot, iid in phase6_gear(spec).items() if iid]
    selected = default_enchants({'id': f'paladin-{spec}', 'class_name': 'Paladin', 'style': 'melee'}, gear, ITEMS, ENCHANTS)
    return {slot: next((e['id'] for e in selected if e['slot'] == slot), '') for slot in GEAR_SLOTS}

def apply_gear(profile):
    """Apply only direct stats and weapon data; return an effective profile and audit summary."""
    effective = copy.deepcopy(profile)
    totals = defaultdict(float)
    equipped = []
    main = None
    set_counts = defaultdict(int)
    set_definitions = {}
    item_effects, unresolved_effects, applied_enchants = [], [], []
    for slot in GEAR_SLOTS:
        item_id = effective["gear"][slot]
        if not item_id:
            continue
        item = ITEMS.get(item_id)
        if not item:
            raise ValueError(f"Unknown Classic Era item id {item_id} in {slot}.")
        if not faction_allowed(item, profile.get("race")):
            raise ValueError(f"{item['name']} is {item['faction']}-only and can't be equipped by a {profile.get('race')}.")
        if slot not in item["equipSlots"]:
            raise ValueError(f"{item['name']} cannot be equipped in {slot}.")
        equipped.append({"slot": slot, "id": item_id, "name": item["name"], "quality": item["quality"],
                         "itemLevel": item["itemLevel"], "wowhead": item.get("wowhead"), "set": item.get("set")})
        stats, effects, unresolved = item_stats_and_effects(item)
        for key, value in stats.items(): totals[key] += value
        item_effects.extend(effects); unresolved_effects.extend(unresolved)
        enchant_id = effective.get('enchants', {}).get(slot, '')
        if enchant_id:
            enchant = next((e for e in ENCHANTS.get(slot, []) if e['id'] == enchant_id), None)
            if not enchant: raise ValueError(f'Unknown enchant {enchant_id} in {slot}.')
            if slot in ('main_hand', 'off_hand') and not item.get('weaponDamageMin'):
                raise ValueError(f'{enchant["name"]} requires a weapon in {slot}.')
            for key, value in enchant.get('stats', {}).items(): totals['strength' if key == 'primary' else key] += value
            if enchant_id == 'crusader': item_effects.append({'name': 'Crusader', 'kind': 'strength', 'ppm': 1.0, 'value': 100, 'duration': 15})
            applied_enchants.append({'slot': slot, 'id': enchant_id, 'name': enchant['name']})
        if item.get("set"):
            set_counts[item["set"]["name"]] += 1
            set_definitions[item["set"]["name"]] = item["set"]
        if slot == "main_hand": main = item
    bonus_totals = defaultdict(float)
    active_forever_bonuses = []
    active_classic_bonuses = []
    set_flags = {}
    for name, count in set_counts.items():
        override = FOREVER_SETS["sets"].get(name)
        if not override:
            for bonus in set_definitions[name].get("bonuses", []):
                if count < int(bonus.get("required", 99)):
                    continue
                conditional = bool(_re(r'chance on|chance to (?:gain|increase|grant|restore|trigger)|proc|for \d+ sec|when |whenever |after |stack', bonus.get('description', '')))
                stats = {} if conditional else dict(bonus.get("stats") or {})
                if not stats and not conditional:
                    for key, pattern in SET_PATTERNS:
                        m = _re(pattern, bonus.get("description", ""))
                        if m: stats[key] = float(m.group(1)); break
                for stat, value in stats.items(): totals[stat] += value
                key = f"{name}|{bonus.get('required')}"
                if key in PALADIN_SET_FLAGS: set_flags[PALADIN_SET_FLAGS[key]] = True
                active_classic_bonuses.append({"set": name, "required": bonus.get("required"), "description": bonus.get("description", ""), "stats": stats, "modeled": bool(stats) or key in PALADIN_SET_FLAGS})
            continue
        for bonus in override["bonuses"]:
            if count < bonus["required"]:
                continue
            active_forever_bonuses.append({"set": name, "source": override["source"], **bonus})
            for stat, value in bonus.get("stats", {}).items():
                totals[stat] += value
    race = effective.get("race", "Human")
    for stat, value in RACE_STATS.get(race, {}).items(): totals[stat] += value
    if effective.get("model", {}).get("use_classic_era_conversions", False):
        for key, enabled in effective.get("raid_buffs", {}).items():
            if enabled:
                for stat, value in RAID_BUFF_STATS.get(key, {}).items(): bonus_totals[stat] += value
        for key, enabled in effective.get("consumables", {}).items():
            if enabled:
                for stat, value in CONSUMABLE_STATS.get(key, {}).items(): bonus_totals[stat] += value
        for stat, value in bonus_totals.items(): totals[stat] += value
    effective["set_flags"] = set_flags
    effective['item_effects'] = item_effects
    if main and main["slot"] == "Two-Hand" and effective["gear"]["off_hand"]:
        raise ValueError("A two-handed weapon cannot be combined with an off-hand item.")
    base = copy.deepcopy(effective["character"])
    ch = effective["character"]
    for stat, (field, scale) in DIRECT_STATS.items():
        ch[field] += totals.get(stat, 0) * scale
    if effective.get("model", {}).get("use_classic_era_conversions", False):
        for stat, field in CLASSIC_PRIMARY.items():
            ch[field] += totals.get(stat, 0)
        kings = 1.10 if effective.get("raid_buffs", {}).get("blessing_of_kings") else 1.0
        for field in ("strength", "agility", "stamina", "intellect", "spirit"): ch[field] *= kings
        if race == 'Human': ch['spirit'] *= 1.05
        talents = effective.get("talents", {})
        ch["strength"] *= 1 + 0.02 * talents.get("105639", 0)
        ch["intellect"] *= 1 + 0.02 * talents.get("105332", 0)
        ch["stamina"] *= 1 + 0.02 * talents.get("105632", 0)
        ch["armor"] *= 1 + 0.02 * talents.get("105630", 0)
        # Paladin level-60 Classic conversions: 1 Str = 2 AP, 1 Sta = 10 HP,
        # 1 Int = 15 mana, 19.77 Agi = 1 melee crit, 59.5 Int = 1 spell crit.
        ch["attack_power"] += ch["strength"] * 2
        ch["health"] += (ch["stamina"] - base["stamina"]) * 10 + base["stamina"] * 10
        ch["mana"] += ch["intellect"] * 15
        ch["crit_chance"] += ch["agility"] * 0.0506 / 100
        ch["spell_crit_chance"] += ch["intellect"] * 0.0167 / 100
        ch["avoidance"] += ch["agility"] * 0.0506 / 100
        ch["spell_power"] += ch["intellect"] * (1 / 3) * talents.get("110882", 0)
        ch["health"] *= 1 + RACIALS.get(race, {}).get("health_pct", 0)
        kinds = {weapon_kind for weapon_kind in (ITEMS.get(effective["gear"][slot], {}).get("subclass") for slot in ("main_hand", "off_hand")) if weapon_kind}
        for kind, bonus in RACIALS.get(race, {}).get("weapon_crit", {}).items():
            if kind != "provisional" and any(kind in k for k in kinds):
                ch["crit_chance"] += bonus / 100; ch["spell_crit_chance"] += bonus / 100
        # Level-63 boss: 4.8% melee crit suppression and 2.1% spell crit suppression (WoWSims Classic attack table).
        ch["crit_chance"] = max(0.0, ch["crit_chance"] - 0.048)
        ch["spell_crit_chance"] = max(0.0, ch["spell_crit_chance"] - 0.021)
        level = effective["character"]["level"]
        armor = effective["character"]["armor"]
        effective["character"]["physical_mitigation"] = min(0.75, armor / (armor + 400 + 85 * effective['encounter']['target_level']))
        reductions = (2250 if effective["debuffs"]["sunder_armor_5"] else 0)
        reductions += 505 if effective["debuffs"]["faerie_fire"] else 0
        reductions += 640 if effective["debuffs"]["curse_of_recklessness"] else 0
        target_armor = max(0, effective["encounter"]["target_armor"] - reductions)
        effective["encounter"]["target_physical_mitigation"] = target_armor / (target_armor + 400 + 85 * level)
    for key in ("crit_chance", "spell_hit_chance", "spell_crit_chance", "block_chance", "avoidance"):
        effective["character"][key] = min(1, effective["character"][key])
    if main and main.get("weaponDamageMin") is not None:
        effective["character"]["weapon_min"] = main["weaponDamageMin"]
        effective["character"]["weapon_max"] = main["weaponDamageMax"]
        effective["character"]["weapon_speed"] = main["weaponSpeed"]
        effective["character"]["weapon_hands"] = main["slot"]
        ch['normalized_speed'] = normalized_speed(main)
    ch['weapon_skill'] = ch['level'] * 5
    if main:
        kind = main.get('subclass', '')
        key = ('Two-Hand ' if main.get('slot') == 'Two-Hand' else '') + kind
        for slot in GEAR_SLOTS:
            item = ITEMS.get(effective['gear'][slot], {})
            for text in item.get('effects', []):
                match = _re(r'Increased (.+?) \+(\d+)', text)
                if match:
                    types = [s.strip().rstrip('s').replace('Two-handed', 'Two-Hand') for s in re.split(r', and |, | and ', match.group(1))]
                    if key in types or kind in types: ch['weapon_skill'] += float(match.group(2))
    ch['seal_cost_reduction'] = totals.get('sealCostReduction', 0)
    ch['threat_reduction'] = totals.get('threatReduction', 0) / 100
    ch['spell_power'] += totals.get('holyPower', 0)
    ch['has_shield'] = ITEMS.get(effective['gear']['off_hand'], {}).get('subclass') == 'Shield'
    if not ch['has_shield']: ch['block_chance'] = 0
    sets = []
    for name, count in sorted(set_counts.items()):
        definition = set_definitions[name]
        forever = FOREVER_SETS["sets"].get(name)
        raw_bonuses = forever["bonuses"] if forever else definition["bonuses"]
        bonuses = [{**bonus, "active": count >= bonus["required"]} for bonus in raw_bonuses]
        sets.append({"name": name, "count": count, "total": len(definition["pieces"]),
                     "pieces": definition["pieces"], "bonuses": bonuses,
                     "ruleset": "Forever" if forever else "Classic Era",
                     "source": forever["source"] if forever else CATALOG["source"]})
    modeled_keys = set(DIRECT_STATS) | (set(CLASSIC_PRIMARY) if effective.get("model", {}).get("use_classic_era_conversions", False) else set())
    modeled = {stat: totals[stat] for stat in modeled_keys if totals.get(stat)}
    unmodeled = {stat: value for stat, value in totals.items() if stat not in modeled_keys and value}
    summary = {"data_version": CATALOG["version"], "source": CATALOG["source"], "scope": CATALOG["scope"],
               "equipped": equipped, "totals": dict(totals), "modeled_totals": modeled,
               "unmodeled_totals": unmodeled, "sets": sets, "base_character": base,
               "raid_buff_totals": dict(bonus_totals),
               "active_raid_buffs": [k for k,v in effective.get("raid_buffs",{}).items() if v],
               "active_consumables": [k for k,v in effective.get("consumables",{}).items() if v],
               "active_debuffs": [k for k,v in effective.get("debuffs",{}).items() if v],
               "active_forever_set_bonuses": active_forever_bonuses, "active_classic_set_bonuses": active_classic_bonuses, "set_flags": set_flags,
               "effective_character": copy.deepcopy(effective["character"]),
               "item_effects": {"applied": item_effects, "unresolved": unresolved_effects}, "enchants": applied_enchants,
               "note": "Sourced Forever set bonuses apply at their equipped thresholds. Classic primary-stat, armor and attack-power conversions are applied only when the audit switch is enabled. Item effects are modeled individually when identified."}
    return effective, summary
