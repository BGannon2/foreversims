"""Classic Era item catalog and temporary stat bridge for the Forever prototype."""
from __future__ import annotations

import copy
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CATALOG = json.loads((DATA_DIR / "classic_era_items.json").read_text(encoding="utf-8"))
PHASE6_BIS = json.loads((DATA_DIR / "phase6_bis.json").read_text(encoding="utf-8"))
FOREVER_SETS = json.loads((DATA_DIR / "forever_set_bonuses.json").read_text(encoding="utf-8"))
ITEMS = {item["id"]: item for item in CATALOG["items"]}
for item in ITEMS.values():
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

from .engine_data import BUFF_STATS as RAID_BUFF_STATS, RACE_STATS, RACIALS, WEAPON_CRIT_TYPES
from .engine import SET_PATTERNS, _re

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

def empty_gear():
    return {slot: 0 for slot in GEAR_SLOTS}

def phase6_gear(spec):
    gear = empty_gear()
    gear.update(PHASE6_BIS[spec]["gear"])
    return gear

def apply_gear(profile):
    """Apply only direct stats and weapon data; return an effective profile and audit summary."""
    effective = copy.deepcopy(profile)
    totals = defaultdict(float)
    equipped = []
    main = None
    set_counts = defaultdict(int)
    set_definitions = {}
    for slot in GEAR_SLOTS:
        item_id = effective["gear"][slot]
        if not item_id:
            continue
        item = ITEMS.get(item_id)
        if not item:
            raise ValueError(f"Unknown Classic Era item id {item_id} in {slot}.")
        if slot not in item["equipSlots"]:
            raise ValueError(f"{item['name']} cannot be equipped in {slot}.")
        equipped.append({"slot": slot, "id": item_id, "name": item["name"], "quality": item["quality"],
                         "itemLevel": item["itemLevel"], "wowhead": item["wowhead"], "set": item.get("set")})
        for key, value in item["stats"].items(): totals[key] += value
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
                stats = dict(bonus.get("stats") or {})
                if not stats:
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
        effective["character"]["physical_mitigation"] = min(0.75, armor / (armor + 400 + 85 * level))
        reductions = (2250 if effective["debuffs"]["sunder_armor_5"] else 0)
        reductions += 505 if effective["debuffs"]["faerie_fire"] else 0
        reductions += 640 if effective["debuffs"]["curse_of_recklessness"] else 0
        target_armor = max(0, effective["encounter"]["target_armor"] - reductions)
        effective["encounter"]["target_physical_mitigation"] = target_armor / (target_armor + 400 + 85 * level)
    for key in ("hit_chance", "crit_chance", "spell_hit_chance", "spell_crit_chance", "block_chance", "avoidance"):
        effective["character"][key] = min(1, effective["character"][key])
    if main and main.get("weaponDamageMin") is not None:
        effective["character"]["weapon_min"] = main["weaponDamageMin"]
        effective["character"]["weapon_max"] = main["weaponDamageMax"]
        effective["character"]["weapon_speed"] = main["weaponSpeed"]
        effective["character"]["weapon_hands"] = main["slot"]
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
               "note": "Sourced Forever set bonuses apply at their equipped thresholds. Classic primary-stat, armor and attack-power conversions are applied only when the audit switch is enabled. Item effects are modeled individually when identified."}
    return effective, summary
