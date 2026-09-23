"""Sourced data tables for the shared Forever DPS/tank engine.

Sources
-------
* Class/race roster and racials: https://www.wowhead.com/forever/guide/new-race-class-combinations
* Talent names, ranks, prerequisites and rank text: forever_talents_all.json
  (Wowhead Forever calculator payload).
* Level-60 base stats, stat conversions, attack-table constants, ability base
  damage, coefficients, cast times, costs and cooldowns: WoWSims Classic
  (https://github.com/wowsims/classic).  Values are Classic Anniversary rules
  unless a Forever talent tooltip overrides them; every such override is
  marked ``forever=True`` in the ability record.
* Anything marked ``provisional`` has no Forever or Classic source in the
  checked-in data and is exposed in the result configuration.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Roster (verified cell by cell against the Wowhead Forever table, 2026-09-17)
# ---------------------------------------------------------------------------
CLASS_RACES = {
    "Warrior": ["Human", "Dwarf", "Night Elf", "Gnome", "Orc", "Undead", "Tauren", "Troll", "Skyborne (Alliance)", "Skyborne (Horde)"],
    "Paladin": ["Human", "Dwarf", "Undead"],
    "Hunter": ["Human", "Dwarf", "Night Elf", "Orc", "Tauren", "Troll", "Skyborne (Alliance)", "Skyborne (Horde)"],
    "Rogue": ["Human", "Dwarf", "Night Elf", "Gnome", "Orc", "Undead", "Troll", "Skyborne (Alliance)", "Skyborne (Horde)"],
    "Priest": ["Human", "Dwarf", "Night Elf", "Gnome", "Undead", "Troll"],
    "Shaman": ["Dwarf", "Orc", "Tauren", "Troll", "Skyborne (Horde)"],
    "Mage": ["Human", "Gnome", "Orc", "Undead", "Troll", "Skyborne (Alliance)"],
    "Warlock": ["Human", "Gnome", "Orc", "Undead", "Troll"],
    "Druid": ["Night Elf", "Tauren", "Skyborne (Alliance)", "Skyborne (Horde)"],
}
CREATURE_TYPES = {"none", "beast", "demon", "dragonkin", "elemental", "giant", "humanoid", "mechanical", "undead"}

# WoWSims Classic sim/core/base_stats.go race offsets.  Skyborne has no
# published stat table; Human offsets (all zero) are used and flagged.
RACE_STATS = {
    "Human": {}, "Skyborne (Alliance)": {}, "Skyborne (Horde)": {},
    "Orc": {"agility": -3, "strength": 3, "intellect": -3, "spirit": 3, "stamina": 2},
    "Dwarf": {"agility": -4, "strength": 2, "intellect": -1, "spirit": -1, "stamina": 3},
    "Night Elf": {"agility": 5, "strength": -3, "stamina": -1},
    "Undead": {"agility": -2, "strength": -1, "intellect": -2, "spirit": 5, "stamina": 1},
    "Tauren": {"agility": -5, "strength": 5, "intellect": -5, "spirit": 2, "stamina": 2},
    "Gnome": {"agility": 3, "strength": -5, "intellect": 3, "stamina": -1},
    "Troll": {"agility": 2, "strength": 1, "intellect": -4, "spirit": 1, "stamina": 1},
}

# WoWSims Classic ClassBaseStats / ClassBaseCrit / APPer* / CritPer* tables.
CLASS_BASE = {
    "Warrior": {"health": 1689, "mana": 0, "agility": 80, "strength": 120, "intellect": 30, "spirit": 45, "stamina": 110, "attackPower": 160, "spellCrit": 0.0, "meleeCrit": 0.0, "dodge": 0.0},
    "Paladin": {"health": 1381, "mana": 1512, "agility": 65, "strength": 105, "intellect": 70, "spirit": 75, "stamina": 100, "attackPower": 160, "spellCrit": 3.5, "meleeCrit": 0.7, "dodge": 0.7},
    "Hunter": {"health": 1467, "mana": 1720, "agility": 125, "strength": 55, "intellect": 65, "spirit": 70, "stamina": 90, "attackPower": 100, "rangedAttackPower": 100, "spellCrit": 3.6, "meleeCrit": 0.0, "dodge": 0.0},
    "Rogue": {"health": 1523, "mana": 0, "agility": 130, "strength": 80, "intellect": 35, "spirit": 50, "stamina": 75, "attackPower": 100, "spellCrit": 0.0, "meleeCrit": 0.0, "dodge": 0.0},
    "Priest": {"health": 1397, "mana": 1376, "agility": 40, "strength": 35, "intellect": 120, "spirit": 125, "stamina": 50, "attackPower": -10, "spellCrit": 0.8, "meleeCrit": 3.0, "dodge": 3.0},
    "Shaman": {"health": 1280, "mana": 1520, "agility": 55, "strength": 85, "intellect": 90, "spirit": 100, "stamina": 95, "attackPower": 100, "spellCrit": 2.3, "meleeCrit": 1.7, "dodge": 1.7},
    "Mage": {"health": 1370, "mana": 1213, "agility": 35, "strength": 30, "intellect": 125, "spirit": 120, "stamina": 45, "attackPower": -10, "spellCrit": 0.2, "meleeCrit": 3.2, "dodge": 3.2},
    "Warlock": {"health": 1414, "mana": 1373, "agility": 50, "strength": 45, "intellect": 110, "spirit": 115, "stamina": 65, "attackPower": -10, "spellCrit": 1.7, "meleeCrit": 2.0, "dodge": 2.0},
    "Druid": {"health": 1483, "mana": 1244, "agility": 60, "strength": 65, "intellect": 100, "spirit": 110, "stamina": 70, "attackPower": -20, "spellCrit": 1.8, "meleeCrit": 0.9, "dodge": 0.9},
}
AP_PER_STRENGTH = {"Warrior": 2, "Paladin": 2, "Hunter": 1, "Rogue": 1, "Priest": 1, "Shaman": 2, "Mage": 1, "Warlock": 1, "Druid": 2}
AP_PER_AGILITY = {"Warrior": 0, "Paladin": 0, "Hunter": 0, "Rogue": 1, "Priest": 0, "Shaman": 0, "Mage": 0, "Warlock": 0, "Druid": 1}
MELEE_CRIT_PER_AGI = {"Warrior": .0500, "Paladin": .0506, "Hunter": .0189, "Rogue": .0345, "Priest": .0500, "Shaman": .0508, "Mage": .0514, "Warlock": .0500, "Druid": .0500}  # percent per point
SPELL_CRIT_PER_INT = {"Warrior": 0, "Paladin": .0167, "Hunter": .0165, "Rogue": 0, "Priest": .0168, "Shaman": .0169, "Mage": .0168, "Warlock": .0165, "Druid": .0167}
DODGE_PER_AGI = {"Warrior": .0500, "Paladin": .0506, "Hunter": .0378, "Rogue": .0690, "Priest": .0500, "Shaman": .0508, "Mage": .0514, "Warlock": .0500, "Druid": .0500}
# Classic level-60 mana regeneration per 2-second tick outside the five-second rule.
SPIRIT_REGEN = {"Mage": (0.25, 12.5), "Priest": (0.25, 12.5), "Warlock": (0.2, 15), "Druid": (0.2, 15), "Shaman": (0.2, 15), "Paladin": (0.2, 15), "Hunter": (0.2, 15)}

RAGE_CONVERSION_60 = 0.0091107836 * 60 * 60 + 3.225598133 * 60 + 4.2652911  # 230.6
LEVEL, TARGET_LEVEL = 60, 63
TARGET_DEFENSE = TARGET_LEVEL * 5
GCD, ENERGY_GCD = 1.5, 1.0

# ---------------------------------------------------------------------------
# Racials (Wowhead Forever guide).  Unpublished numbers are provisional.
# ---------------------------------------------------------------------------
RACIALS = {
    "Human": {"spirit_pct": 0.05, "weapon_crit": {"Sword": 2.0}, "summary": "The Human Spirit: +5% Spirit. Sword Specialization: +2% spell and ability critical chance while a sword is equipped."},
    "Dwarf": {"weapon_crit": {"Mace": 1.0}, "creature_damage": {"beast": 0.05}, "active": {"name": "Stoneform", "duration": 8, "cooldown": 180}, "summary": "Stoneform: 10% reduced Physical damage taken for 8 sec, 3 min cooldown. Mace Specialization: +1% critical chance with a mace equipped. Big Game Hunter: +5% damage to Beasts."},
    "Night Elf": {"dodge": 1.0, "active": {"name": "Elune's Light", "crit": 10.0, "duration": 15, "cooldown": 120, "provisional_cooldown": True}, "summary": "Elune's Light: +10% critical chance for 15 sec (cooldown unpublished; 2 min assumed). Quickness: +1% dodge."},
    "Gnome": {"active": {"name": "Eureka!", "charges": 3, "damage": 0.10, "cooldown": 120, "provisional_cooldown": True}, "summary": "Eureka!: next 3 spells or abilities deal +10% damage (cost reduction and cooldown unpublished; 2 min assumed)."},
    "Orc": {"weapon_crit": {"Axe": 1.0, "provisional": True}, "active": {"name": "Blood Fury", "ap_pct": 0.10, "sp_pct": 0.10, "duration": 15, "cooldown": 120}, "summary": "Blood Fury: +10% Attack Power and Spell Power for 15 sec, 2 min cooldown. Axe Specialization: critical chance with axes (amount unpublished; 1% assumed)."},
    "Undead": {"touch_of_the_grave": {"chance": 0.05, "health_fraction": 0.05}, "summary": "Touch of the Grave: 5% chance on spells and attacks to drain health for up to 5% of maximum health."},
    "Tauren": {"hit": 1.0, "health_pct": 0.05, "summary": "Endurance: +1% hit chance and +5% maximum health."},
    "Troll": {"creature_damage": {"beast": 0.05}, "active": {"name": "Berserking", "haste": 0.10, "duration": 10, "cooldown": 180, "provisional_cooldown": True}, "summary": "Berserking: +10% casting and attack speed for 10 sec (cooldown unpublished; 3 min assumed). Beast Slaying: +5% damage to Beasts."},
    "Skyborne (Alliance)": {"haste": 0.01, "creature_damage": {"elemental": 0.05}, "summary": "Wind Blessed: +1% melee, ranged and spell haste. Elemental Insight: +5% damage to Elementals."},
    "Skyborne (Horde)": {"haste": 0.01, "creature_damage": {"elemental": 0.05}, "summary": "Wind Blessed: +1% melee, ranged and spell haste. Elemental Insight: +5% damage to Elementals."},
}

# ---------------------------------------------------------------------------
# Raid buffs, target debuffs and consumables (Classic Anniversary values)
# ---------------------------------------------------------------------------
BUFF_STATS = {
    "bloodlust": {},  # Requested encounter assumption; timed haste in both engines.
    "power_word_fortitude": {"stamina": 70}, "mark_of_the_wild": {"strength": 16, "agility": 16, "stamina": 16, "intellect": 16, "spirit": 16, "armor": 385},
    "arcane_intellect": {"intellect": 31}, "battle_shout": {"attackPower": 290}, "blessing_of_might": {"attackPower": 222}, "devotion_aura": {"armor": 735},
    "blessing_of_wisdom": {"mp5": 33}, "strength_of_earth": {"strength": 77}, "grace_of_air": {"agility": 77}, "mana_spring": {"mp5": 15},
    "leader_of_the_pack": {"meleeCrit": 3, "rangedCrit": 3}, "moonkin_aura": {"spellCrit": 3}, "trueshot_aura": {"rangedAttackPower": 100},
    "blessing_of_kings": {}, "windfury_totem": {},
}
BUFF_GROUPS = {"air_totem": ["grace_of_air", "windfury_totem"], "crit_aura": ["leader_of_the_pack", "moonkin_aura"]}
WINDFURY_TOTEM = {"chance": 0.20, "ap": 315}

def default_buffs(spec):
    """Assume a full 40-man raid bringing every class: every raid buff is on by default,
    including ones that are a no-op for this spec's resource/damage type (e.g. Blessing of
    Wisdom for a Rage class) -- they're harmless to leave applied and match "every class is
    present" rather than "only the buffs that help me". The only buffs left out are the ones
    that are mechanically impossible to have simultaneously: each entry in BUFF_GROUPS is a
    single raid slot only one spell can occupy at a time (one Air Totem, one 3%-crit aura), so
    we pick whichever member of the group actually benefits this spec's style/class. Windfury
    Totem only procs off melee weapon swings, so it goes to melee specs only -- Druids never get
    it since it doesn't function while shapeshifted, and ranged/spell specs get Grace of Air
    (agility) instead, same as the crit aura pick (Leader of the Pack for melee/ranged physical
    crit, Moonkin Aura for spell crit)."""
    non_exclusive = sorted(set(BUFF_STATS) - {b for group in BUFF_GROUPS.values() for b in group})
    if spec["style"] == "spell":
        picks = ["moonkin_aura", "grace_of_air"]
    elif spec["style"] == "melee" and spec["class_name"] != "Druid":
        picks = ["leader_of_the_pack", "windfury_totem"]
    else:
        picks = ["leader_of_the_pack", "grace_of_air"]
    return non_exclusive + picks

DEBUFF_ARMOR = {"sunder_armor_5": 2250, "faerie_fire": 505, "curse_of_recklessness": 640}
CONSUME_STATS = {
    "flask_of_the_titans": {"health": 1200}, "elixir_of_the_mongoose": {"agility": 25, "meleeCrit": 2, "rangedCrit": 2},
    "elixir_of_superior_defense": {"armor": 450}, "elixir_of_fortitude": {"health": 120}, "greater_stoneshield_potion": {"armor": 2000},
    "smoked_desert_dumplings": {"strength": 20}, "rumsey_rum_black_label": {"stamina": 15}, "mageblood_potion": {"mp5": 12},
    "juju_power": {"strength": 30}, "juju_might": {"attackPower": 40}, "brilliant_wizard_oil": {"spellPower": 36, "spellCrit": 1},
    "flask_of_supreme_power": {"spellPower": 150}, "greater_arcane_elixir": {"spellPower": 35}, "elixir_of_greater_firepower": {"firePower": 40},
    "elixir_of_frost_power": {"frostPower": 15}, "elixir_of_shadow_power": {"shadowPower": 40}, "grilled_squid": {"agility": 10},
    "elemental_sharpening_stone": {"meleeCrit": 2}, "winterfall_firewater": {"attackPower": 35}, "gift_of_arthas": {},
    "major_mana_potion": {}, "demonic_rune": {}, "mighty_rage_potion": {}, "thistle_tea": {}, "goblin_sapper_charge": {}, "dragonbreath_chili": {},
}
# Consumables that only make sense for a subset of specs.
CONSUME_SCOPE = {
    "elemental_sharpening_stone": lambda spec: spec["style"] == "melee" and spec.get("form") is None,
    "mighty_rage_potion": lambda spec: spec["resource"] == "Rage" and spec["class_name"] == "Warrior",
    "thistle_tea": lambda spec: spec["class_name"] == "Rogue",
    "major_mana_potion": lambda spec: spec["resource"] == "Mana",
    "demonic_rune": lambda spec: spec["resource"] == "Mana",
    "elixir_of_greater_firepower": lambda spec: spec["id"] in {"mage-fire", "warlock-destruction"},
    "elixir_of_frost_power": lambda spec: spec["id"] == "mage-frost",
    "elixir_of_shadow_power": lambda spec: spec["id"] in {"priest-shadow", "warlock-affliction", "warlock-demonology"},
}

def default_consumables(spec):
    tank = ["flask_of_the_titans", "elixir_of_the_mongoose", "elixir_of_superior_defense", "elixir_of_fortitude", "greater_stoneshield_potion", "smoked_desert_dumplings", "rumsey_rum_black_label", "juju_power", "juju_might", "gift_of_arthas", "elemental_sharpening_stone", "goblin_sapper_charge", "dragonbreath_chili"]
    physical = ["elixir_of_the_mongoose", "smoked_desert_dumplings", "juju_power", "juju_might", "elemental_sharpening_stone", "goblin_sapper_charge", "dragonbreath_chili", "mighty_rage_potion"]
    agility = ["elixir_of_the_mongoose", "grilled_squid", "juju_might", "elemental_sharpening_stone", "goblin_sapper_charge", "dragonbreath_chili", "thistle_tea"]
    caster = ["flask_of_supreme_power", "greater_arcane_elixir", "mageblood_potion", "brilliant_wizard_oil", "major_mana_potion", "demonic_rune", "elixir_of_greater_firepower", "elixir_of_frost_power", "elixir_of_shadow_power"]
    if spec["role"] == "tank": chosen = tank
    elif spec["style"] == "spell": chosen = caster
    elif spec["class_name"] in {"Rogue", "Hunter", "Druid"}: chosen = agility
    else: chosen = physical
    if spec["class_name"] in {"Hunter", "Shaman"} and spec["style"] != "spell": chosen = chosen + ["major_mana_potion"]
    return [c for c in chosen if CONSUME_SCOPE.get(c, lambda s: True)(spec)]

# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------
SPECS = [
    ("warrior-arms", "Warrior", "Arms", "dps", "melee", "Rage", "Arms", None, "battle"),
    ("warrior-fury", "Warrior", "Fury", "dps", "melee", "Rage", "Fury", None, "berserker"),
    ("warrior-protection", "Warrior", "Protection", "tank", "melee", "Rage", "Protection", None, "defensive"),
    ("druid-balance", "Druid", "Balance", "dps", "spell", "Mana", "Balance", "moonkin", None),
    ("druid-feral-dps", "Druid", "Feral DPS", "dps", "melee", "Energy", "Feral", "cat", None),
    ("druid-feral-tank", "Druid", "Feral Tank", "tank", "melee", "Rage", "Feral", "bear", None),
    ("hunter-beast-mastery", "Hunter", "Beast Mastery", "dps", "ranged", "Mana", "BeastMastery", None, None),
    ("hunter-marksmanship", "Hunter", "Marksmanship", "dps", "ranged", "Mana", "Marksmanship", None, None),
    ("hunter-survival", "Hunter", "Survival", "dps", "melee", "Mana", "Survival", None, None),
    ("mage-arcane", "Mage", "Arcane", "dps", "spell", "Mana", "Arcane", None, None),
    ("mage-fire", "Mage", "Fire", "dps", "spell", "Mana", "Fire", None, None),
    ("mage-frost", "Mage", "Frost", "dps", "spell", "Mana", "Frost", None, None),
    ("priest-shadow", "Priest", "Shadow", "dps", "spell", "Mana", "Shadow", None, None),
    ("rogue-assassination", "Rogue", "Assassination", "dps", "melee", "Energy", "Assassination", None, None),
    ("rogue-combat", "Rogue", "Combat", "dps", "melee", "Energy", "Combat", None, None),
    ("rogue-subtlety", "Rogue", "Subtlety", "dps", "melee", "Energy", "Subtlety", None, None),
    ("shaman-elemental", "Shaman", "Elemental", "dps", "spell", "Mana", "Elemental", None, None),
    ("shaman-enhancement", "Shaman", "Enhancement", "dps", "melee", "Mana", "Enhancement", None, None),
    ("warlock-affliction", "Warlock", "Affliction", "dps", "spell", "Mana", "Affliction", None, None),
    ("warlock-demonology", "Warlock", "Demonology", "dps", "spell", "Mana", "Demonology", None, None),
    ("warlock-destruction", "Warlock", "Destruction", "dps", "spell", "Mana", "Destruction", None, None),
]
SPEC_MAP = {r[0]: {"id": r[0], "class_name": r[1], "name": r[2], "role": r[3], "style": r[4], "resource": r[5], "tree": r[6], "form": r[7], "stance": r[8]} for r in SPECS}

# Stance / form threat and damage modifiers (WoWSims Classic stances.go, forms.go).
STANCE_MODS = {"battle": {"threat": 0.8}, "berserker": {"threat": 0.8}, "defensive": {"threat": 1.3, "damage": 0.9, "taken": 0.9}, "cat": {"threat": 0.71}, "bear": {"threat": 1.45}, "moonkin": {"threat": 1.0}, None: {"threat": 1.0}}
CLASS_THREAT = {"Rogue": 0.71}

# ---------------------------------------------------------------------------
# Abilities.  Common keys:
#   kind: direct | dot | channel | swing (on-next-swing) | buff | builder/finisher via cp
#   school, cost, cooldown, cast (seconds, 0 = instant), gcd, base (lo,hi) or tick,
#   coeff (spell power per hit or per tick), ticks, tick_len, weapon {hand, normalized, mult, flat},
#   cp (+1 generate, -1 consume), threat_mult, flat_threat, execute (only below 20%),
#   requires ("dagger" | "dodge" | "block_dodge_parry"), forever (Forever tooltip value), provisional.
# ---------------------------------------------------------------------------
ABILITIES = {
    # ---- Warrior -----------------------------------------------------------
    "Heroic Strike": {"kind": "swing", "school": "physical", "cost": 15, "weapon": {"hand": "main", "flat": 157}, "flat_threat": 173},
    "Cleave": {"kind": "swing", "school": "physical", "cost": 20, "weapon": {"hand": "main", "flat": 50}, "flat_threat": 100},
    "Mortal Strike": {"kind": "direct", "school": "physical", "cost": 30, "cooldown": 6, "weapon": {"hand": "main", "normalized": True, "flat": 85}, "forever": True},
    "Overpower": {"kind": "direct", "school": "physical", "cost": 5, "cooldown": 5, "weapon": {"hand": "main", "normalized": True, "flat": 35}, "requires": "dodge", "no_dodge": True, "threat_mult": 0.75},
    "Whirlwind": {"kind": "direct", "school": "physical", "cost": 25, "cooldown": 10, "weapon": {"hand": "main", "normalized": True}, "threat_mult": 1.25},
    "Rend": {"kind": "dot", "school": "physical", "cost": 10, "tick": 21, "ticks": 7, "tick_len": 3, "dot_coeff": 0.0, "bleed": True, "forever": True,
              "provisional": "Rank 7 (max rank) confirmed via wago.tools DB2 (build 1.60.1.69913, spell 11574): 10 Rage, no cooldown beyond the GCD, 21 damage/tick over 7 ticks (21s). Real Classic Rend also adds a weapon-damage-based bonus to the initial tick that this flat-DoT model doesn't capture; treated as a flat bleed like this project's other DoTs. Confirmed missing from this sim entirely until a Mobalytics.gg guide audit flagged it as a core Arms/Fury rotation ability."},
    "Spearing Strike": {"kind": "direct", "school": "physical", "cost": 20, "cooldown": 6, "weapon": {"hand": "main", "normalized": True, "mult": 0.40}, "creature_mult": {"giant": 3.0, "dragonkin": 3.0}, "forever": True,
                        "provisional": "Damage formula (40% weapon, +80% additional i.e. 3x total against Giants/Dragonkin/mounted targets) is confirmed via foreverchanges.pro's beta-client talent data (build 1.60.1.69913): \"A brutal attack that deals 40% weapon damage. Deals an additional 80% weapon damage against Giants, Dragonkin, and mounted targets. Mounted targets are dismounted.\" Rage cost and cooldown are still not published by that source (talent tooltips there omit resource/cooldown fields) and remain a placeholder. The dismount-on-mounted-target effect has no combat relevance in this PvE model and isn't implemented."},
    "Execute": {"kind": "direct", "school": "physical", "cost": 15, "execute": True, "execute_formula": (600, 15), "threat_mult": 1.25},
    "Bloodthirst": {"kind": "direct", "school": "physical", "cost": 30, "cooldown": 6, "ap_mult": 0.35, "flat": 30, "forever": True},
    "Hamstring": {"kind": "direct", "school": "physical", "cost": 10, "flat": 45},
    "Shield Slam": {"kind": "direct", "school": "physical", "cost": 20, "cooldown": 6, "base": (421, 439), "add_block_value": True, "flat_threat": 250, "forever": True},
    "Revenge": {"kind": "direct", "school": "physical", "cost": 5, "cooldown": 5, "base": (81, 99), "requires": "block_dodge_parry", "threat_mult": 2.25, "flat_threat": 270},
    "Sunder Armor": {"kind": "direct", "school": "physical", "cost": 15, "no_damage": True, "flat_threat": 270},
    "Thunder Clap": {"kind": "direct", "school": "physical", "cost": 20, "cooldown": 6, "base": (103, 103), "threat_mult": 1.75, "forever": True,
                      "provisional": "Rank 6 (max rank, level 58) confirmed via wago.tools DB2 (build 1.60.1.69913, spell 11581): 20 Rage (PowerType 1, ManaCost 200 stored at the standard x10 rage convention), 6 sec cooldown, 103 flat physical damage, no AP/SP scaling, capped at 4 targets (SpellTargetRestrictions.MaxTargets=4, and this rank chain has a real BaseLevel progression -- 6/18/28/38/48/58 -- matching known Classic Thunder Clap; a higher-numbered duplicate id set with MaxTargets=10 exists in the same build but has BaseLevel=0 on every rank, meaning it isn't the level-gated chain a player actually trains). The 1.75x threat multiplier is not in wago.tools' DB2 data (PvE threat coefficients aren't spell data) and is WoWSims Classic's established value, same fallback convention this project already uses elsewhere for unpublished threat numbers. Missing from this sim entirely -- flagged when auditing why Protection Warrior's threat plateaus on 3+ targets: Cleave (2-target cap) and Swipe (3-target cap) are both accurate to the client, but Thunder Clap, the tool real Protection Warriors use to keep threat climbing past that, was never modeled at all."},
    "Bloodrage": {"kind": "buff", "cooldown": 60, "off_gcd": True, "rage": 10, "rage_over_time": (1, 10)},
    "Death Wish": {"kind": "buff", "cooldown": 180, "cost": 10, "duration": 30, "damage_mult_school": ("physical", 0.20), "forever": True},
    # ---- Druid ---------------------------------------------------------------
    "Shred": {"kind": "direct", "school": "physical", "cost": 60, "gcd": 1.0, "weapon": {"hand": "form", "mult": 1.55, "flat": 80}, "cp": 1},
    "Claw": {"kind": "direct", "school": "physical", "cost": 45, "gcd": 1.0, "weapon": {"hand": "form", "mult": 1.10, "flat": 27}, "cp": 1},
    "Ferocious Bite": {"kind": "direct", "school": "physical", "cost": 35, "gcd": 1.0, "finisher": "ferocious_bite"},
    "Rip": {"kind": "dot", "school": "physical", "cost": 30, "gcd": 1.0, "finisher": "rip", "ticks": 6, "tick_len": 2, "bleed": True},
    "Tiger's Fury": {"kind": "buff", "cost": 0, "gcd": 1.0, "cooldown": 30, "duration": 6, "damage_mult_school": ("physical", 0.15), "forever": True,
                      "provisional": "Confirmed via foreverchanges.pro (build 1.60.1.69913): costs nothing, 30 sec cooldown, +15% Physical damage for 6 sec (previously modeled as a flat +40 damage adder and a 30 Energy cost carried over from Classic)."},
    "Maul": {"kind": "swing", "school": "physical", "cost": 15, "weapon": {"hand": "form", "flat": 128}, "threat_mult": 1.75},
    "Swipe": {"kind": "direct", "school": "physical", "cost": 20, "base": (83, 83), "threat_mult": 2.0},
    "Mangle": {"kind": "direct", "school": "physical", "cost": 45, "gcd": 1.0, "cooldown": 6, "weapon": {"hand": "form", "flat": 26}, "cp": 1, "forever": True,
               "provisional": "Damage (100% weapon plus 26) is the sourced Forever talent tooltip; Wowhead's own guide flags Forever talent data as still incomplete, and real TBC-era Mangle also applies a bleed-vulnerability debuff and a higher weapon-damage percent not captured in this tooltip. Cooldown (6 sec) is not published and uses real Mangle's known Classic-era-adjacent value as a placeholder."},
    "Mangle (Bear)": {"kind": "direct", "school": "physical", "cost": 15, "gcd": 1.0, "cooldown": 6, "weapon": {"hand": "form", "flat": 26}, "threat_mult": 1.75, "forever": True,
                       "provisional": "Damage (100% weapon plus 26) is the sourced Forever talent tooltip. Cooldown (6 sec) and its Rage cost are not published; cost mirrors Maul's, cooldown uses real Mangle's known value as a placeholder. Threat multiplier assumed equal to Maul's, not separately sourced."},
    "Berserk": {"kind": "buff", "cost": 0, "gcd": 0, "cooldown": 180, "duration": 15, "forever": True,
                "provisional": "Duration (15 sec) is the sourced Forever talent tooltip; cooldown is not published (3 min assumed, matching this project's convention for other undocumented Forever cooldowns). Only the single-target-relevant effect (guaranteed critical strikes on combo-point generators) is modeled; the 3-target Mangle cleave, Mangle's cooldown removal, and the Fear-immunity clause have no effect in this single-target model."},
    "Moonfire": {"kind": "direct_dot", "school": "arcane", "cost": 375, "base": (124, 146), "coeff": 0.15, "tick": 60, "ticks": 4, "tick_len": 3, "dot_coeff": 0.13, "spreadable": True, "forever": True,
                 "provisional": "Rank 10 confirmed via wago.tools DB2 raw client data (build 1.60.1.69913, spell 9835): initial hit ~135 avg (124-146 range) and dot total 240 (60/tick x 4 ticks) both verified directly against SpellEffect basepoints, matching foreverchanges.pro's summary."},
    "Insect Swarm": {"kind": "dot", "school": "nature", "cost": 155, "tick": 8, "ticks": 6, "tick_len": 2, "dot_coeff": 0.127, "spreadable": True, "forever": True,
                      "provisional": "Total dot damage (48 over 12s) confirmed via foreverchanges.pro (build 1.60.1.69913); previous value (324 total) matched neither Classic (66) nor Forever (48) and was a pre-existing sourcing error."},
    "Starfire": {"kind": "direct", "school": "arcane", "cost": 340, "cast": 3.5, "base": (350, 412), "coeff": 1.0, "forever": True, "provisional": "Rank 7 value confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Wrath": {"kind": "direct", "school": "nature", "cost": 120, "cast": 2.0, "base": (58, 64), "coeff": 0.571, "forever": True, "provisional": "Rank 8 value confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    # ---- Hunter --------------------------------------------------------------
    "Aimed Shot": {"kind": "direct", "school": "physical", "cost": 310, "cooldown": 6, "cast": 2.0, "ranged_cast": True, "shared_cd": "aimed_multi", "weapon": {"hand": "ranged", "normalized": True, "flat": 166}, "forever": True,
                    "provisional": "Flat bonus (166) confirmed via foreverchanges.pro (build 1.60.1.69913); previous value (600) was a leftover Classic-scale figure."},
    "Multi-Shot": {"kind": "direct", "school": "physical", "cost": 230, "cost_pct": 0.139, "cooldown": 6, "cast": 0.5, "ranged_cast": True, "shared_cd": "aimed_multi", "weapon": {"hand": "ranged", "normalized": True, "flat": 0}, "forever": True,
                   "provisional": "Confirmed via wago.tools DB2 (build 1.60.1.69913, spell 2643): zero flat damage bonus (pure 100% weapon damage to 3 chain targets) and a mana cost of 13.9% of base mana rather than a flat value. Forever also collapsed this to a single rank."},
    "Volley": {"kind": "channel", "school": "arcane", "cost": 490, "cast": 6.0, "tick": 112, "ticks": 6, "coeff": 0.056, "ranged_cast": True, "aoe": True, "forever": True,
               "provisional": "Tick damage (112) and the removal of Volley's cooldown are confirmed via foreverchanges.pro (build 1.60.1.69913); Classic's 60 sec cooldown no longer applies. Mana cost and coefficient are still unpublished WoWSims Classic-derived placeholders."},
    "Arcane Shot": {"kind": "direct", "school": "arcane", "cost": 190, "cooldown": 6, "shared_cd": "arcane_hawk", "base": (217, 217), "coeff": 0.0, "forever": True,
                     "provisional": "Base damage (217) confirmed via foreverchanges.pro (build 1.60.1.69913); Forever also removed spell-power scaling from this ability (coefficient 0)."},
    "Summon Hawk": {"kind": "direct_dot", "school": "physical", "cost": 120, "cooldown": 6, "shared_cd": "arcane_hawk", "base": (34, 34), "coeff": 0.15, "tick": 34, "ticks": 9, "tick_len": 2, "dot_coeff": 0.0, "forever": True, "provisional": "Initial hit (34) is the sourced Forever talent tooltip (updated from an earlier 53 misread); the 18-second continued assault has no published tick rate or total, so this uses a 9-tick/2s cadence at the initial hit's magnitude. Modeled as a single refreshing DoT rather than genuinely stacking two simultaneous hawks. Mana cost and coefficient are not published and use placeholders."},
    "Serpent Sting": {"kind": "dot", "school": "nature", "cost": 250, "tick": 111, "ticks": 5, "tick_len": 3, "dot_coeff": 0.0, "forever": True, "provisional": "Forever removed spell-power scaling from this dot (dot_coeff 0); tick damage (111) unchanged from Classic per foreverchanges.pro."},
    "Explosive Trap": {"kind": "direct_dot", "school": "fire", "cost": 520, "cooldown": 15, "base": (208, 265), "coeff": 0.0, "tick": 33, "ticks": 10, "tick_len": 2, "dot_coeff": 0.0},
    "Bestial Wrath": {"kind": "buff", "cooldown": 120, "duration": 18, "pet_damage_mult": 0.50},
    "Rapid Fire": {"kind": "buff", "cooldown": 300, "duration": 15, "ranged_haste": 0.40, "off_gcd": True},
    "Mongoose Bite": {"kind": "direct", "school": "physical", "cost": 65, "cooldown": 5, "weapon": {"hand": "main", "normalized": True, "flat": 57}, "requires": "dodge_or_buff:Mongoose Bite Ready", "forever": True},
    "Strider Kick": {"kind": "direct", "school": "physical", "cost": 0, "cooldown": 8, "weapon": {"hand": "main", "normalized": True}, "forever": True, "provisional": "Formula (100% weapon damage, no flat bonus) confirmed via foreverchanges.pro (build 1.60.1.69913); resource cost and cooldown are still not published by that source and are treated as free/placeholder."},
    "Raptor Strike": {"kind": "direct", "school": "physical", "cost": 100, "cooldown": 6, "weapon": {"hand": "main", "flat": 70}, "forever": True,
                       "provisional": "Confirmed via foreverchanges.pro (build 1.60.1.69913): Forever gave Raptor Strike an independent 6 sec cooldown (cost 100, flat bonus 70), changing it from a next-swing-modifier ability into a direct instant-cast ability. Previously modeled as a swing-queue attack with Classic-era values (cost 75, flat 140)."},
    # ---- Mage ----------------------------------------------------------------
    "Fireball": {"kind": "direct_dot", "school": "fire", "cost": 410, "cast": 3.5, "base": (425, 541), "coeff": 1.0, "tick": 15, "ticks": 4, "tick_len": 2, "dot_coeff": 0.0, "forever": True,
                 "provisional": "Rank 12 values confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Scorch": {"kind": "direct", "school": "fire", "cost": 150, "cast": 1.5, "base": (163, 193), "coeff": 0.429, "forever": True, "provisional": "Rank 7 value confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Fire Blast": {"kind": "direct", "school": "fire", "cost": 340, "cooldown": 8, "base": (402, 474), "coeff": 0.429, "forever": True, "provisional": "Rank 7 value confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Frostbolt": {"kind": "direct", "school": "frost", "cost": 290, "cast": 3.0, "base": (457, 493), "coeff": 0.814, "forever": True, "provisional": "Rank 11 value confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Frostfire Bolt": {"kind": "direct_dot", "school": "frost", "cost": 370, "cast": 3.0, "base": (270, 314), "coeff": 0.814, "tick": 19, "ticks": 3, "tick_len": 3, "dot_coeff": 0.0, "forever": True,
                        "provisional": "New Forever baseline Mage nuke (Rank 3, max rank) confirmed via wago.tools DB2 (build 1.60.1.69913, spell 1237313): 370 mana, 3s cast, 270-314 direct + 57 total over 9s (19/tick), 0.814 SP coefficient on the direct hit (DoT coefficient not published, left at 0). Also slows movement 40% (not modeled). Counts as both Frost and Fire damage and can proc Hot Streak (Fire) and Missile Barrage (Arcane) per Mobalytics' class overview (both proc-trigger sets in engine.py were updated to include it, so it correctly generates procs whenever a rotation casts it). Deliberately NOT used as mage-fire's default filler: tested swapping it in for Fireball on the theory that its shorter cast (3.0s vs 3.5s) would buy more Hot Streak crit rolls per minute, but an actual A/B sim run showed a ~30% DPS loss (494.96 -> 348.35 on the default preset), far outweighing any proc-rate gain -- the raw-damage deficit (~349 total per cast vs Fireball's ~483) dominates. Kept out of mage-arcane's Missile Barrage fishing too: Frostfire Bolt and Frostbolt have identical cast time and identical 20% proc chance, so swapping one for the other has no proc-rate benefit, only a damage cost. Left in ABILITIES and wired into both proc systems for correctness and so it's available if a future talent/mechanic (e.g. an instant-cast proc) makes it situationally worth casting."},
    "Arcane Explosion": {"kind": "direct", "school": "arcane", "cost": 390, "base": (232, 252), "coeff": 0.143, "aoe": True, "forever": True,
                          "provisional": "Rank 6 value confirmed via foreverchanges.pro (build 1.60.1.69913), superseding the earlier WoWSims-Classic-derived guess. Damage applies once per target within range; this sim approximates that as a flat multiplier by the chosen target count rather than a real positional radius check."},
    "Blizzard": {"kind": "channel", "school": "frost", "cost": 1400, "cast": 8.0, "tick": 146, "ticks": 8, "coeff": 0.042, "aoe": True, "forever": True,
                 "provisional": "Rank 6 total damage (1168 over 8 ticks) confirmed via foreverchanges.pro (build 1.60.1.69913), superseding the earlier WoWSims-Classic-derived guess. Each tick applies to every target within range; approximated as a flat multiplier by the chosen target count."},
    "Arcane Missiles": {"kind": "channel", "school": "arcane", "cost": 655, "cast": 5.0, "tick": 209, "ticks": 5, "coeff": 0.286, "forever": True,
                         "provisional": "Rank 8 per-missile damage (209), coefficient, and mana cost (655) confirmed via wago.tools DB2 (build 1.60.1.69913, spell 25345/25346)."},
    "Arcane Power": {"kind": "buff", "cooldown": 180, "duration": 15, "damage_mult": 0.30, "cost_mult": 0.30, "off_gcd": True},
    "Combustion": {"kind": "buff", "cooldown": 180, "combustion": True, "off_gcd": True, "forever": True,
                    "provisional": "Forever changed Combustion to last through 4 non-periodic Fire crits instead of Classic's 3, per foreverchanges.pro (build 1.60.1.69913); the crit-count threshold is implemented in engine.py's combustion handling."},
    "Presence of Mind": {"kind": "buff", "cooldown": 180, "instant_next": True, "off_gcd": True},
    "Cold Snap": {"kind": "buff", "cooldown": 600, "off_gcd": True, "no_effect": "Resets Frost cooldowns; nothing in the single-target rotation uses one"},
    "Arcane Blast": {"kind": "direct", "school": "arcane", "cost": 250, "cast": 2.5, "base": (50, 58), "coeff": 0.68, "forever": True, "provisional": "Base damage (50-58) confirmed via foreverchanges.pro (build 1.60.1.69913), correcting an earlier misread (95-104). Cast time, mana cost, and spell-power coefficient are still not published and use a per-second-normalized placeholder comparable to this spec's other nukes."},
    "Pyroblast": {"kind": "direct_dot", "school": "fire", "cost": 440, "cast": 6.0, "base": (95, 125), "coeff": 1.0, "tick": 11, "ticks": 4, "tick_len": 3, "dot_coeff": 0.15, "forever": True, "provisional": "Direct damage (95-125) and total DoT damage (44 over 12s) confirmed via foreverchanges.pro (build 1.60.1.69913), correcting an earlier WoWSims-Classic-derived guess (155-185 direct / much larger DoT). Cast time (6.0s), mana cost (440), and DoT coefficient (0.15) are still not published for Forever's rebalanced version and remain placeholders."},
    "Ice Lance": {"kind": "direct", "school": "frost", "cost": 20, "base": (26, 30), "coeff": 0.1, "forever": True, "provisional": "Base damage (26-30) confirmed via foreverchanges.pro (build 1.60.1.69913); instant cast, mana cost, and coefficient are not published and use placeholders reflecting its role as a cheap filler amplified by Fingers of Frost."},
    # ---- Priest --------------------------------------------------------------
    "Shadow Word: Pain": {"kind": "dot", "school": "shadow", "cost": 470, "tick": 95.25, "ticks": 8, "tick_len": 3, "dot_coeff": 0.20, "spreadable": True, "forever": True,
                           "provisional": "Rank 8 total (762 over 8 ticks) and 20% SP bonus confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Mind Blast": {"kind": "direct", "school": "shadow", "cost": 350, "cast": 1.5, "cooldown": 8, "base": (472, 498), "coeff": 0.429, "forever": True, "provisional": "Rank 9 value confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Mind Flay": {"kind": "channel", "school": "shadow", "cost": 205, "cast": 3.0, "tick": 130, "ticks": 3, "coeff": 0.167, "forever": True,
                  "provisional": "Rank 6 (max rank) tick damage and coefficient confirmed via wago.tools DB2 (build 1.60.1.69913, spell 18807); mana cost (205) was already correct."},
    "Shadow Word: Death": {"kind": "direct", "school": "shadow", "cost": 175, "cooldown": 15, "base": (286, 304), "coeff": 0.429, "forever": True,
                            "provisional": "Cost, cooldown, and base damage confirmed via foreverchanges.pro (build 1.60.1.69913), replacing an earlier TBC-rank-2 guess. Forever's tooltip doesn't state a spell-power coefficient explicitly; the existing 0.429 placeholder is kept. Forever also added a 10%-of-max-health backlash to the caster if the target survives, which is not modeled in this single-target execute-range usage."},
    "Devouring Plague": {"kind": "dot", "school": "shadow", "cost": 215, "cooldown": 60, "tick": 16, "ticks": 8, "tick_len": 3, "dot_coeff": 0.10, "forever": True,
                          "provisional": "Now a baseline ability for every Priest (previously Undead-race-locked in Classic), per Mobalytics.gg's class overview and foreverchanges.pro (build 1.60.1.69913): 215 mana, 1 min cooldown, 128 total Shadow damage over 24s (16/tick). The life-drain-heals-caster mechanic isn't modeled. Confirmed missing from this sim entirely until a Mobalytics.gg guide audit flagged it as a new baseline ability."},
    # ---- Rogue ---------------------------------------------------------------
    "Sinister Strike": {"kind": "direct", "school": "physical", "cost": 45, "gcd": 1.0, "weapon": {"hand": "main", "normalized": True, "flat": 68}, "cp": 1},
    "Backstab": {"kind": "direct", "school": "physical", "cost": 60, "gcd": 1.0, "weapon": {"hand": "main", "normalized": True, "mult": 1.5, "flat": 150}, "cp": 1, "requires": "dagger"},
    "Hemorrhage": {"kind": "direct", "school": "physical", "cost": 35, "gcd": 1.0, "weapon": {"hand": "main", "normalized": True, "mult": 1.0, "dagger_mult": 1.45}, "cp": 1, "forever": True},
    "Mutilate": {"kind": "direct", "school": "physical", "cost": 60, "gcd": 1.0, "cp": 2, "requires": "dagger", "weapon": {"hand": "both", "normalized": True, "mult": 0.75, "flat": 17}, "forever": True,
                  "provisional": "Confirmed via foreverchanges.pro (build 1.60.1.69913): 75% weapon damage plus 17 with each weapon (dual-wield, both hands hit), +20% vs Poisoned targets. Previously had no weapon dict at all and dealt no weapon damage. The +20% Poisoned-target bonus isn't modeled since Poison application isn't tracked in this sim."},
    "Venom": {"kind": "buff", "cost": 25, "gcd": 1.0, "finisher": "venom_buff", "forever": True},
    "Eviscerate": {"kind": "direct", "school": "physical", "cost": 35, "gcd": 1.0, "finisher": "eviscerate"},
    "Rupture": {"kind": "dot", "school": "physical", "cost": 25, "gcd": 1.0, "finisher": "rupture", "tick_len": 2, "bleed": True},
    "Slice and Dice": {"kind": "buff", "cost": 25, "gcd": 1.0, "finisher": "slice_and_dice", "melee_haste": 0.30},
    "Blade Flurry": {"kind": "buff", "cost": 25, "gcd": 1.0, "cooldown": 120, "duration": 15, "melee_haste": 0.20},
    "Adrenaline Rush": {"kind": "buff", "cooldown": 300, "duration": 15, "energy_regen_mult": 2.0, "off_gcd": True},
    "Cold Blood": {"kind": "buff", "cooldown": 180, "next_crit": True, "off_gcd": True},
    "Thistle Tea": {"kind": "buff", "cooldown": 300, "energy": 100, "off_gcd": True},
    # ---- Shaman --------------------------------------------------------------
    "Lightning Bolt": {"kind": "direct", "school": "nature", "cost": 220, "cast": 2.5, "base": (185, 207), "coeff": 0.857, "forever": True, "provisional": "Rank 10 value confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Chain Lightning": {"kind": "direct", "school": "nature", "cost": 485, "cast": 2.0, "cooldown": 6, "base": (116, 130), "coeff": 0.714, "forever": True, "provisional": "Rank 4 value confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Lava Burst": {"kind": "direct", "school": "fire", "cost": 425, "cast": 2.5, "cooldown": 10, "base": (99, 127), "coeff": 0.5, "forever": True, "provisional": "Base damage (99-127) confirmed via foreverchanges.pro (build 1.60.1.69913); mana cost and spell-power coefficient are still not published and use a Lightning-Bolt-comparable placeholder."},
    "Flame Shock": {"kind": "direct_dot", "school": "fire", "cost": 345, "cooldown": 6, "shared_cd": "shock", "base": (166, 166), "coeff": 0.214, "tick": 44, "ticks": 4, "tick_len": 3, "dot_coeff": 0.1, "forever": True, "provisional": "Rank 6 value confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Earth Shock": {"kind": "direct", "school": "nature", "cost": 450, "cooldown": 6, "shared_cd": "shock", "base": (293, 309), "coeff": 0.386, "forever": True, "provisional": "Rank 7 value confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Stormstrike": {"kind": "direct", "school": "physical", "cost": 320, "cooldown": 8, "weapon": {"hand": "main"}, "apply_debuff": ("Stormstrike", 12, {"nature": 0.20}), "forever": True},
    "Elemental Mastery": {"kind": "buff", "cooldown": 180, "next_crit": True, "off_gcd": True},
    "Rage of the Farseer": {"kind": "buff", "cooldown": 180, "duration": 25, "melee_haste": 0.30, "spell_haste": 0.30, "off_gcd": True, "forever": True, "provisional": "cooldown not published; 3 min assumed"},
    # ---- Warlock -------------------------------------------------------------
    "Shadow Bolt": {"kind": "direct", "school": "shadow", "cost": 380, "cast": 3.0, "base": (253, 283), "coeff": 0.857, "forever": True, "provisional": "Rank 10 value confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Rain of Fire": {"kind": "channel", "school": "fire", "cost": 1185, "cast": 8.0, "tick": 220, "ticks": 4, "coeff": 0.083, "aoe": True, "forever": True,
                      "provisional": "Rank 4 total damage (880 over 4 ticks) confirmed via foreverchanges.pro (build 1.60.1.69913), superseding the earlier WoWSims-Classic-derived guess. Each tick applies to every target within range; approximated as a flat multiplier by the chosen target count."},
    "Corruption": {"kind": "dot", "school": "shadow", "cost": 340, "cast": 2.0, "tick": 73, "ticks": 6, "tick_len": 3, "dot_coeff": 0.20, "spreadable": True, "forever": True,
                    "provisional": "Rank 7 total (438 over 6 ticks) and 20% SP bonus confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Curse of Agony": {"kind": "dot", "school": "shadow", "cost": 215, "tick": 46, "ticks": 12, "tick_len": 2, "dot_coeff": 0.133, "curse": True, "spreadable": True, "forever": True,
                        "provisional": "Renamed \"Bane of Agony\" in Forever. Rank 6 total (552 over 12 ticks) and 13.3% SP bonus confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Siphon Life": {"kind": "dot", "school": "shadow", "cost": 365, "tick": 45, "ticks": 10, "tick_len": 3, "dot_coeff": 0.1, "spreadable": True,
                     "provisional": "foreverchanges.pro (build 1.60.1.69913) gives only the talent's per-tick value (11, vs Classic's 15 baseline), which doesn't cleanly map onto this sim's existing AP-scaled 45/tick figure; left unchanged pending a clearer source."},
    "Wrack": {"kind": "dot", "school": "shadow", "cost": 200, "tick": 36, "ticks": 6, "tick_len": 1, "dot_coeff": 0.143, "spreadable": True, "forever": True,
              "provisional": "New Affliction talent confirmed via wago.tools DB2 (build 1.60.1.69913, spell 1316697): 200 mana, 36 Shadow damage/sec for 6 sec, 0.143 SP coefficient. Also increases damage taken from the caster's other Shadow DoTs by 10% for 6 sec, which isn't modeled. Confirmed missing from this sim entirely until a Mobalytics.gg guide audit flagged it as a new Affliction ability."},
    "Drain Soul": {"kind": "channel", "school": "shadow", "cost": 290, "cast": 15.0, "tick": 91, "ticks": 5, "coeff": 0.1, "execute_bonus": True},
    "Immolate": {"kind": "direct_dot", "school": "fire", "cost": 380, "cast": 2.0, "base": (158, 158), "coeff": 0.2, "tick": 55, "ticks": 5, "tick_len": 3, "dot_coeff": 0.13, "forever": True,
                  "provisional": "Rank 8 initial hit (158) and dot total (275 over 5 ticks) confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Incinerate": {"kind": "direct", "school": "fire", "cost": 255, "cast": 2.0, "base": (90, 104), "coeff": 0.571, "forever": True, "provisional": "Base damage (90-104) confirmed via foreverchanges.pro (build 1.60.1.69913), correcting an earlier misread (125-140); the +25% Immolate bonus is unchanged. Cast time, cost and spell-power coefficient are still not published and use a Shadow-Bolt-comparable per-second placeholder."},
    "Conflagrate": {"kind": "direct", "school": "fire", "cost": 305, "cooldown": 10, "base": (84, 106), "coeff": 0.429, "requires": "dot:Immolate", "consumes_dot": "Immolate", "forever": True,
                     "provisional": "Base damage (84-106) confirmed via foreverchanges.pro (build 1.60.1.69913). The previous value (447-557) matched neither Classic (240-306) nor Forever and was a pre-existing sourcing bug unrelated to this redesign."},
    "Shadowburn": {"kind": "direct", "school": "shadow", "cost": 365, "cooldown": 15, "base": (62, 70), "coeff": 0.429, "forever": True,
                    "provisional": "Base damage (62-70) confirmed via foreverchanges.pro (build 1.60.1.69913). The previous value (462-514) matched neither Classic (87-99) nor Forever and was a pre-existing sourcing bug unrelated to this redesign."},
    "Searing Pain": {"kind": "direct", "school": "fire", "cost": 168, "cast": 1.5, "base": (105, 123), "coeff": 0.429, "threat_mult": 2.0, "forever": True, "provisional": "Rank 6 value confirmed via foreverchanges.pro (build 1.60.1.69913)."},
    "Life Tap": {"kind": "buff", "life_tap": 424},
    "Demonic Sacrifice": {"kind": "buff", "sacrifice": True, "off_gcd": True, "cooldown": 999999,
                          "provisional": "Talented, one-time pet sacrifice: kills the pet for a permanent +15% school damage buff (Shadow for Imp, Fire for Succubus) for the rest of the fight. Modeled as a single off-GCD activation at the first opportunity (cooldown set far beyond any fight length so it never refires); no cast time or GCD in Classic."},
    # ---- Consumables -----------------------------------------------------------
    "Goblin Sapper Charge": {"kind": "direct", "school": "fire", "cooldown": 300, "base": (450, 750), "off_gcd": True, "always_hit": True, "no_crit": True},
    "Major Mana Potion": {"kind": "buff", "cooldown": 120, "mana": (1350, 2250), "off_gcd": True, "shared_cd": "potion"},
    "Mighty Rage Potion": {"kind": "buff", "cooldown": 120, "rage": (45, 75), "duration": 20, "strength": 60, "off_gcd": True, "shared_cd": "potion"},
    "Demonic Rune": {"kind": "buff", "cooldown": 120, "mana": (900, 1500), "off_gcd": True},
}

# Rotation priority lists.  Each entry: (ability, condition) where condition is a
# small expression evaluated by engine.Sim.check().  Higher entries win.
ROTATIONS = {
    "warrior-arms": [("Bloodrage", "rage<60"), ("Death Wish", "true"), ("Execute", "execute"), ("Rend", "dot_missing and not execute"), ("Overpower", "true"), ("Mortal Strike", "true"), ("Whirlwind", "true"), ("Spearing Strike", "rage>=50"), ("Heroic Strike", "rage>=45 and not execute")],
    "warrior-fury": [("Bloodrage", "rage<60"), ("Death Wish", "true"), ("Execute", "execute"), ("Rend", "dot_missing and not execute"), ("Bloodthirst", "true"), ("Whirlwind", "true"), ("Hamstring", "rage>=60 and not execute and cd:Bloodthirst>1.5 and cd:Whirlwind>1.5"), ("Heroic Strike", "rage>=40 and not execute")],
    "warrior-protection": [("Bloodrage", "rage<60"), ("Shield Slam", "true"), ("Revenge", "true"), ("Thunder Clap", "targets>=3"), ("Sunder Armor", "stacks:Sunder Armor<5 or rage>=40"), ("Execute", "execute"), ("Cleave", "targets>=2 and rage>=20"), ("Heroic Strike", "rage>=30")],
    "druid-balance": [("Moonfire", "dot_missing"), ("Insect Swarm", "dot_missing"), ("Starfire", "true"), ("Wrath", "true")],
    "druid-feral-dps": [("Berserk", "true"), ("Tiger's Fury", "buff_missing and energy>=60"), ("Ferocious Bite", "cp>=5 and dot:Rip>4"), ("Rip", "cp>=5 and dot_missing"), ("Mangle", "true"), ("Shred", "true"), ("Claw", "no_shred")],
    "druid-feral-tank": [("Berserk", "true"), ("Mangle (Bear)", "true"), ("Swipe", "rage>=45"), ("Maul", "rage>=20")],
    "hunter-beast-mastery": [("Volley", "targets>=3"), ("Bestial Wrath", "true"), ("Rapid Fire", "true"), ("Serpent Sting", "dot_missing"), ("Summon Hawk", "dot_missing"), ("Multi-Shot", "true"), ("Arcane Shot", "mana>=1500")],
    "hunter-marksmanship": [("Volley", "targets>=3"), ("Rapid Fire", "true"), ("Serpent Sting", "dot_missing"), ("Aimed Shot", "true"), ("Multi-Shot", "true"), ("Arcane Shot", "mana>=1500")],
    "hunter-survival": [("Mongoose Bite", "true"), ("Strider Kick", "true"), ("Raptor Strike", "true")],
    "mage-arcane": [("Arcane Explosion", "targets>=3"), ("Arcane Power", "true"), ("Presence of Mind", "true"), ("Arcane Missiles", "buff:Missile Barrage>0"), ("Arcane Missiles", "buffstacks:Arcane Blast>=4"), ("Arcane Blast", "true"), ("Frostbolt", "true")],
    "mage-fire": [("Arcane Explosion", "targets>=3"), ("Scorch", "stacks:Improved Scorch<5 or debuff:Improved Scorch<4"), ("Combustion", "stacks:Improved Scorch>=5"), ("Pyroblast", "buffstacks:Hot Streak>=1"), ("Fire Blast", "moving"), ("Fireball", "true"), ("Scorch", "true")],
    "mage-frost": [("Blizzard", "targets>=3"), ("Cold Snap", "false"), ("Ice Lance", "buffstacks:Fingers of Frost>=1"), ("Frostbolt", "true"), ("Fire Blast", "moving")],
    "priest-shadow": [("Shadow Word: Pain", "dot_missing"), ("Devouring Plague", "dot_missing"), ("Shadow Word: Death", "execute"), ("Mind Blast", "true"), ("Mind Flay", "true")],
    "rogue-assassination": [("Thistle Tea", "energy<20"), ("Cold Blood", "cp>=5"), ("Venom", "cp>=2 and buff_missing"), ("Slice and Dice", "cp>=2 and buff_missing"), ("Eviscerate", "cp>=5"), ("Mutilate", "true")],
    "rogue-combat": [("Thistle Tea", "energy<20"), ("Adrenaline Rush", "true"), ("Blade Flurry", "true"), ("Slice and Dice", "cp>=2 and buff_missing"), ("Eviscerate", "cp>=5"), ("Sinister Strike", "true")],
    "rogue-subtlety": [("Thistle Tea", "energy<20"), ("Slice and Dice", "cp>=2 and buff_missing"), ("Rupture", "cp>=5 and dot_missing"), ("Eviscerate", "cp>=5"), ("Hemorrhage", "true")],
    # Elemental Mastery has no equivalent talent in the Forever Elemental tree (removed from the rotation; was unreachable dead code).
    "shaman-elemental": [("Flame Shock", "dot_missing and mana>=2000"), ("Lava Burst", "mana>=1500"), ("Chain Lightning", "mana>=2500"), ("Lightning Bolt", "true")],
    "shaman-enhancement": [("Rage of the Farseer", "true"), ("Lightning Bolt", "buffstacks:Maelstrom Weapon>=5"), ("Stormstrike", "true"), ("Earth Shock", "mana>=1200 or debuff:Stormstrike>0"), ("Flame Shock", "dot_missing and mana>=2500")],
    "warlock-affliction": [("Demonic Sacrifice", "true"), ("Rain of Fire", "targets>=3"), ("Life Tap", "mana<400"), ("Curse of Agony", "dot_missing"), ("Corruption", "dot_missing"), ("Siphon Life", "dot_missing"), ("Wrack", "dot_missing"), ("Drain Soul", "execute and dot:Corruption>0"), ("Shadow Bolt", "true")],
    "warlock-demonology": [("Rain of Fire", "targets>=3"), ("Life Tap", "mana<400"), ("Curse of Agony", "dot_missing"), ("Corruption", "dot_missing"), ("Shadow Bolt", "true")],
    "warlock-destruction": [("Demonic Sacrifice", "true"), ("Rain of Fire", "targets>=3"), ("Life Tap", "mana<400"), ("Immolate", "dot_missing"), ("Conflagrate", "dot:Immolate>0 and dot:Immolate<4"), ("Shadowburn", "execute"), ("Incinerate", "true")],
}
CONSUMABLE_ACTIONS = {"goblin_sapper_charge": "Goblin Sapper Charge", "major_mana_potion": "Major Mana Potion", "mighty_rage_potion": "Mighty Rage Potion", "demonic_rune": "Demonic Rune", "thistle_tea": "Thistle Tea"}

# ---------------------------------------------------------------------------
# Plain-language "how this spec's model works" text, shown on each spec's simulator page.
# Describes the actual priority rotation (from ROTATIONS above) and the threat formula that
# produces TPS, not a generic description - kept in sync by hand when either changes.
# ---------------------------------------------------------------------------
SPEC_ABOUT = {
    "warrior-arms": {
        "dps": "Priority: Death Wish on cooldown, Execute below 20% health, Overpower after a dodge, Mortal Strike, Whirlwind, Spearing Strike against Giants/Dragonkin at high rage, Heroic Strike queued whenever rage allows.",
        "tps": "Battle Stance carries a flat -20% threat penalty (×0.8) on every hit, so Arms' TPS trails its DPS more than a threat-neutral spec's would."},
    "warrior-fury": {
        "dps": "Priority: Death Wish on cooldown, Execute below 20% health, Bloodthirst, Whirlwind, Hamstring as a filler between Bloodthirst/Whirlwind cooldowns, Heroic Strike queued whenever rage allows.",
        "tps": "Berserker Stance carries the same flat -20% threat penalty (×0.8) as Battle Stance."},
    "warrior-protection": {
        "dps": "A threat rotation first: Shield Slam, Revenge, Sunder Armor upkeep, Execute, Cleave once 2+ targets are up, Heroic Strike as a rage dump. Damage output is a side effect of holding aggro, not the priority.",
        "tps": "Defensive Stance grants +30% threat (×1.3), and Shield Slam/Revenge/Sunder Armor/Cleave/Heroic Strike all add large flat threat bonuses on top of their damage-based threat - the most complete tank threat kit of the two shared-engine tanks."},
    "druid-balance": {
        "dps": "Priority: keep Moonfire and Insect Swarm up (spread across every available target once one is already active, rather than refreshing on the same target), Starfire as the main nuke, Wrath as filler. Eclipse lets Wrath charges shorten Starfire's cast time.",
        "tps": "Moonkin Form carries no threat modifier (×1.0) and Balance has no dedicated threat tool, so its TPS tracks its DPS almost 1:1."},
    "druid-feral-dps": {
        "dps": "Priority: Berserk on cooldown, Tiger's Fury to bank Energy (and, with King of the Jungle, extra Energy directly), Ferocious Bite at 5 combo points with a healthy Rip up, Rip to apply the bleed, Mangle as the primary builder ahead of Shred, Claw as a fallback when Shred is unusable.",
        "tps": "Cat Form carries the largest threat penalty modeled (×0.71), so Feral DPS's TPS trails its DPS more than any other melee spec."},
    "druid-feral-tank": {
        "dps": "A threat rotation: Berserk on cooldown, Mangle (Bear) as the primary attack, Swipe and Maul as rage allows.",
        "tps": "Bear Form carries the largest threat bonus modeled (×1.45); combined with Mangle, Feral Tank leads both the DPS and TPS side of the tank comparison at every target count."},
    "hunter-beast-mastery": {
        "dps": "Priority: Volley once 3+ targets are up, Bestial Wrath, Rapid Fire, Serpent Sting upkeep, Summon Hawk upkeep, Multi-Shot, Arcane Shot as a mana-gated filler. Pet damage (Claw/Bite) adds on top via its own attack timer.",
        "tps": "No stance or class threat modifier applies; pet damage generates its own threat independently, unscaled by any Hunter-specific multiplier."},
    "hunter-marksmanship": {
        "dps": "Priority: Volley once 3+ targets are up, Rapid Fire, Serpent Sting upkeep, Aimed Shot, Multi-Shot, Arcane Shot as a mana-gated filler.",
        "tps": "No stance or class threat modifier applies, same as Beast Mastery."},
    "hunter-survival": {
        "dps": "Forever's melee-rebuilt Survival kit: Mongoose Bite whenever a dodge or Expose Prey proc allows it, Strider Kick, Raptor Strike as the main-hand filler.",
        "tps": "No stance or class threat modifier applies; being melee range doesn't change Survival's threat math versus the ranged Hunter specs."},
    "mage-arcane": {
        "dps": "Priority: Arcane Explosion once 3+ targets are up, Arcane Power, Presence of Mind, Arcane Missiles under Missile Barrage or at 4 Arcane Blast stacks, Arcane Blast otherwise, Frostbolt as a fallback.",
        "tps": "No threat modifier applies; TPS tracks DPS 1:1 like the other two Mage specs."},
    "mage-fire": {
        "dps": "Priority: Arcane Explosion once 3+ targets are up, Combustion, Pyroblast under any Hot Streak stack, Scorch to maintain Improved Scorch stacks, Fire Blast while moving, Fireball as the default nuke.",
        "tps": "No threat modifier applies."},
    "mage-frost": {
        "dps": "Priority: Blizzard once 3+ targets are up, Ice Lance under a Fingers of Frost charge, Frostbolt as the main nuke, Fire Blast while moving.",
        "tps": "No threat modifier applies."},
    "priest-shadow": {
        "dps": "Priority: Shadow Word: Pain upkeep (spread across available targets rather than refreshed on one), Shadow Word: Death in execute range, Mind Blast, Mind Flay as filler.",
        "tps": "No threat modifier applies."},
    "rogue-assassination": {
        "dps": "Priority: Thistle Tea when low on Energy, Cold Blood at 5 combo points, Venom to buff poison effects, Slice and Dice upkeep, Eviscerate at 5 combo points, Mutilate as the main combo-point builder.",
        "tps": "Rogues carry a class-wide -29% threat modifier (×0.71) regardless of stance or talents - the only class-level (not stance-level) threat penalty modeled - so all three Rogue specs' TPS trails their DPS by roughly the same margin."},
    "rogue-combat": {
        "dps": "Priority: Thistle Tea when low on Energy, Adrenaline Rush, Blade Flurry, Slice and Dice upkeep, Eviscerate at 5 combo points, Sinister Strike as the main builder.",
        "tps": "Same class-wide -29% threat modifier (×0.71) as the other two Rogue specs."},
    "rogue-subtlety": {
        "dps": "Priority: Thistle Tea when low on Energy, Slice and Dice upkeep, Rupture at 5 combo points, Eviscerate at 5 combo points, Hemorrhage as the main builder.",
        "tps": "Same class-wide -29% threat modifier (×0.71) as the other two Rogue specs."},
    "shaman-elemental": {
        "dps": "Priority: Flame Shock upkeep, Lava Burst, Chain Lightning (bounces to up to 2 extra targets on its own), Lightning Bolt as the default nuke.",
        "tps": "No threat modifier applies."},
    "shaman-enhancement": {
        "dps": "Priority: Rage of the Farseer on cooldown, Lightning Bolt dumped free at 5 Maelstrom Weapon stacks, Stormstrike, Earth Shock, Flame Shock upkeep.",
        "tps": "No threat modifier applies, despite Enhancement being a melee spec."},
    "warlock-affliction": {
        "dps": "Priority: Rain of Fire once 3+ targets are up, Life Tap to sustain mana, Curse of Agony/Corruption/Siphon Life kept up and spread across available targets, Drain Soul in execute range, Shadow Bolt as filler.",
        "tps": "No threat modifier applies."},
    "warlock-demonology": {
        "dps": "Priority: Rain of Fire once 3+ targets are up, Life Tap, Curse of Agony/Corruption kept up and spread across available targets, Shadow Bolt as filler.",
        "tps": "No threat modifier applies.",
        "notes": "The default build's single point in Demonic Sacrifice (105900) is a pass-through toward Master Demonologist/Soul Link, not intended to be cast: sacrificing the pet trades away its DPS and pet-synergy talents for a flat +15% school damage buff, which is a net loss for a spec built around an empowered pet (tested: ~-18% DPS). Affliction and Destruction don't share that tradeoff -- their pets contribute comparatively little damage -- so Demonic Sacrifice is in their default rotations instead."},
    "warlock-destruction": {
        "dps": "Priority: Rain of Fire once 3+ targets are up, Life Tap, Immolate upkeep, Conflagrate while Immolate has time remaining, Shadowburn in execute range, Incinerate as the main nuke.",
        "tps": "No threat modifier applies."},
}

# Same purpose as SPEC_ABOUT, for the two Paladin specs (sim.py's separate engine).
PALADIN_ABOUT = {
    "protection": {
        "dps": "A threat rotation first: Templar's Bulwark as an emergency cooldown, Holy Shield upkeep, Exorcism/Holy Wrath against Undead or Demons, Consecration (its damage and threat both scale with the encounter's target count), Seal of Fury's melee swing proc plus Judgement.",
        "tps": "Righteous Fury adds +90% Holy threat, and that Holy-school bonus plus Judgement of Fury's guaranteed taunt is the whole threat model - there's no blanket stance-style multiplier the way the shared engine's Warrior/Druid tanks get. This produces a real, currently-unexplained gap versus their TPS at equal DPS, read as intentional (see CHANGELOG.md) but not confirmed by an explicit source."},
    "retribution": {
        "dps": "Twists Seal of Righteousness and Seal of Command (both scale with weapon speed/spell power now, not flat rolls), Judgement, Consecration, Exorcism/Holy Wrath against Undead or Demons, Holy Strike when talented.",
        "tps": "No Righteous Fury bonus (Protection-only); since Holy damage is already the threat baseline everywhere in this model, Retribution's TPS sits closer to a 1:1 ratio with its DPS than most shared-engine DPS specs, just without the tank multiplier."},
}

# ---------------------------------------------------------------------------
# Talent effects keyed by Forever talent id.  Each value is per rank.
# Keys understood by the engine:
#   melee_crit, spell_crit, hit, spell_hit, crit_dmg_school:<s>, crit_dmg_ability:<a>, crit_ability:<a>
#   dmg_school:<s>, dmg_ability:<a>, dmg_all, dmg_periodic, cast:<a> (seconds), cost:<a> (flat), cost_pct:<a>,
#   cost_pct_school:<s>, cooldown:<a>, stat_pct:<stat>, ap_from_int, sp_from_int, flag:<name>, threat_mult
# ---------------------------------------------------------------------------
TALENT_EFFECTS = {
    # Warrior Arms
    "105958": {"cost:Heroic Strike": -1}, "105950": {"flag:deep_wounds": 0.20}, "105947": {"crit_dmg_school:physical_ability": 0.10},
    "105948": {"flag:two_hand_spec": 0.01}, "105951": {"flag:anger_management": 1}, "105949": {"flag:spearing_strike": 1},
    "105944": {"flag:weaponmaster": 0.01}, "105941": {"flag:mortal_strike": 1}, "105952": {"crit_ability:Overpower": 25},
    # Warrior Fury
    "105939": {"melee_crit": 1}, "105937": {"flag:unbridled_wrath": 0.12}, "105933": {"flag:dw_damage": 0.05, "flag:dw_rage": 0.20, "dw_hit": 2},
    "105931": {"flag:enrage": 0.02}, "105932": {"cost:Execute": -2.5}, "105929": {"hit": 1}, "105927": {"flag:death_wish": 1}, "105928": {"flag:flurry": 0.05}, "105930": {"flag:bloodthirst": 1},
    "105953": {"flag:max_rage": 10},
    # Warrior Protection
    "105976": {"block": 1, "flag:shield_spec_rage": 0.20},
    "105975": {"defense": 4}, "105973": {"item_armor_pct": 0.02}, "105969": {"dmg_ability:Revenge": 0.20},
    "110856": {"flag:defiance": 0.05}, "105968": {"cost:Sunder Armor": -1}, "105962": {"stat_pct:strength": 0.02, "stat_pct:stamina": 0.02}, "105961": {"flag:focused_rage": 1},
    "105959": {"flag:shield_slam": 1}, "105974": {"flag:improved_bloodrage": 0.25}, "105971": {"flag:master_of_defense": 0.50},  # guide: 50%/rank chance on dodge OR parry for a flat 5 rage
    # Druid Balance
    "104923": {"cast:Wrath": -0.1, "cost_pct:Wrath": -0.10}, "104924": {"dmg_periodic": 0.01}, "104925": {"cost_pct_all": -0.03}, "104931": {"dmg_ability:Moonfire": 0.05, "crit_ability:Moonfire": 5},
    "104927": {"spell_crit": 2, "melee_crit": 2}, "104929": {"spell_hit": 2, "hit": 2}, "104930": {"flag:insect_swarm": 1}, "104932": {"crit_dmg_school:arcane": 0.20, "crit_dmg_school:nature": 0.20},
    "104933": {"cast:Starfire": -0.1}, "104934": {"flag:natures_grace": 1}, "104936": {"dmg_school:arcane": 0.01, "dmg_school:nature": 0.01}, "104937": {"flag:moonkin": 0.03}, "104935": {"flag:eclipse": 1},
    # Druid Feral
    "104938": {"cost:Maul": -1, "cost:Swipe": -1, "cost:Claw": -1, "cost:Mangle": -1, "cost:Mangle (Bear)": -1}, "104939": {"stat_pct:intellect": 0.02, "flag:hotw_cat_str": 0.02, "flag:hotw_bear_sta": 0.04},
    "104940": {"dmg_ability:Swipe": 0.10}, "104943": {"dodge": 2}, "104948": {"dmg_ability:Claw": 0.05, "dmg_ability:Shred": 0.05, "dmg_ability:Maul": 0.05, "dmg_ability:Swipe": 0.05},
    "104946": {"melee_crit": 3}, "104945": {"cost:Shred": -6}, "104952": {"flag:predatory_strikes": 30}, "104947": {"flag:primal_fury": 1},
    "104950": {"crit_dmg_school:physical_ability": 0.10}, "104953": {"flag:rend_and_tear": 0.02}, "104954": {"dodge": 1}, "104942": {"flag:thick_hide": 1},
    "104949": {"flag:mangle": 1}, "104951": {"flag:king_of_the_jungle": 20}, "104956": {"flag:berserk": 1},
    # Hunter BM
    "104969": {"flag:pet_damage": 0.03}, "104967": {"flag:pet_crit": 2}, "104962": {"flag:pet_frenzy": 0.2}, "104961": {"flag:bestial_wrath": 1}, "104975": {"dmg_all": 0.01}, "104963": {"flag:pet_focus": 0.10},
    # Hunter MM
    "105011": {"melee_crit": 1}, "110870": {"dmg_ability:Serpent Sting": 0.0667}, "105009": {"cost_pct_all": -0.03}, "105008": {"ap_from_int": 0.20},
    "105006": {"cooldown:Arcane Shot": -0.3}, "105007": {"flag:lone_wolf": 0.20}, "105002": {"crit_dmg_school:ranged": 0.06}, "105003": {"dmg_ability:Serpent Sting": 0.02},
    "105001": {"dmg_ability:Multi-Shot": 0.0333, "dmg_ability:Aimed Shot": 0.0333}, "104998": {"dmg_school:ranged": 0.01}, "105004": {},
    # Hunter Survival
    "104996": {"flag:improved_tracking": 0.01}, "104991": {"dmg_ability:Explosive Trap": 0.15}, "104987": {"hit": 1}, "104983": {"cost_pct:Explosive Trap": -0.30},
    "110859": {"stat_pct:agility": 0.02}, "104985": {"flag:expose_prey": 0.05}, "104984": {"flag:lacerating_strikes": 1}, "104981": {"flag:strider_kick": 1}, "104966": {"flag:summon_hawk": 1},
    # Mage Fire
    "105796": {"crit_ability:Fire Blast": 2, "crit_ability:Scorch": 2}, "105795": {"cast:Fireball": -0.1}, "105794": {"flag:ignite": 0.08}, "105797": {"cooldown:Fire Blast": -1},
    "105788": {"flag:improved_scorch": 1}, "105785": {"flag:master_of_elements": 0.10}, "105784": {"crit_school:fire": 2}, "105782": {"dmg_school:fire": 0.02}, "105781": {"flag:combustion": 1},
    "105790": {"flag:pyroblast": 1}, "105786": {"flag:hot_streak": 1},
    # Mage Frost
    "105779": {"cast:Frostbolt": -0.1}, "105778": {"spell_hit_school:frost": 1, "spell_hit_school:fire": 1}, "105777": {"crit_dmg_school:frost": 0.20}, "105773": {"dmg_school:frost": 0.02},
    "105772": {"cost_pct_school:frost": -0.05}, "105763": {"flag:winters_chill": 1}, "105766": {"flag:cold_snap": 1},
    "105768": {"flag:shatter": 0.1667}, "105767": {"flag:ice_lance": 1}, "105764": {"flag:fingers_of_frost": 1},
    # Mage Arcane
    "105814": {"spell_hit_school:arcane": 1}, "105810": {"flag:clearcasting": 0.02}, "105807": {"crit_school:arcane": 2}, "105803": {"flag:spirit_while_casting": 0.1667},
    "105801": {"flag:presence_of_mind": 1}, "105800": {"stat_pct:intellect": 0.02, "crit_dmg_school:arcane": 0.20}, "105799": {"dmg_all": 0.01, "spell_crit": 1, "melee_crit": 1}, "105798": {"flag:arcane_power": 1},
    "105806": {"flag:arcane_blast": 1}, "105802": {"flag:missile_barrage": 1},
    # Priest Shadow
    "110851": {"spell_hit_school:shadow": 1}, "105830": {"flag:swp_ticks": 1}, "105827": {"cooldown:Mind Blast": -0.5}, "105826": {"flag:mind_flay": 1}, "105825": {"dmg_ability:Mind Flay": 0.10},
    "105821": {"flag:shadow_weaving": 0.02}, "105818": {"dmg_school:shadow": 0.02}, "105817": {"flag:shadowform": 1}, "110854": {"flag:early_demise": 15}, "105833": {}, "105831": {"threat_school:shadow": -0.10},
    "105843": {"flag:spirit_while_casting": 0.1667}, "105837": {"stat_pct:intellect": 0.03}, "105853": {"flag:spiritual_guidance": 0.016},
    # Rogue Assassination
    "105722": {"melee_crit": 1}, "105720": {"flag:murder": 0.02}, "105739": {"flag:snd_duration": 0.15}, "105759": {"flag:relentless_strikes": 1}, "105716": {"crit_dmg_builder": 0.06},
    "105714": {"flag:poison_damage": 0.04}, "105715": {"flag:cold_blood": 1}, "105713": {"flag:poison_chance": 0.02}, "105718": {"flag:max_energy": 5}, "105710": {"flag:seal_fate": 0.20}, "105721": {"flag:ruthlessness": 0.20},
    "105709": {"flag:mutilate": 1}, "105712": {"flag:venom": 1},
    # Rogue Combat
    "105708": {"dmg_ability:Eviscerate": 0.0667}, "105741": {"cost:Sinister Strike": -2.5}, "105719": {"crit_ability:Backstab": 10}, "105737": {"hit": 1}, "108100": {"flag:restless_blades": 1},
    "105740": {"flag:dw_damage": 0.05}, "105728": {"flag:blade_flurry": 1}, "105727": {"flag:hack_and_slash": 0.01}, "105726": {"flag:expertise": 1},
    "105730": {"dmg_ability:Sinister Strike": 0.02, "dmg_ability:Backstab": 0.02, "dmg_ability:Eviscerate": 0.02}, "105724": {"flag:adrenaline_rush": 1},
    # Rogue Subtlety
    "105760": {"dmg_ability:Backstab": 0.05}, "105752": {"flag:armor_pen_pct": 0.03, "dmg_ability:Rupture": 0.10}, "105748": {"flag:hemorrhage": 1}, "110867": {"flag:quietus": 0.02},
    "105743": {"flag:premeditation": 1}, "110866": {"flag:thousand_cuts": 1},
    # Shaman Elemental
    "104773": {"cost_pct_school:nature": -0.02, "cost_pct_school:fire": -0.02}, "104772": {"dmg_ability:Lightning Bolt": 0.01, "dmg_ability:Chain Lightning": 0.01, "dmg_ability:Earth Shock": 0.01},
    "104767": {"cooldown:Flame Shock": -0.2, "cooldown:Earth Shock": -0.2}, "104770": {"dmg_ability:Flame Shock": 0.05}, "104768": {"flag:clearcasting": 0.10},
    "104766": {"crit_dmg_school:fire": 0.20, "crit_dmg_school:nature": 0.20, "crit_dmg_school:frost": 0.20}, "104762": {"crit_ability:Lightning Bolt": 3, "crit_ability:Chain Lightning": 3},
    "104759": {"flag:lightning_overload": 0.0333}, "104765": {"cast:Lightning Bolt": -0.1667, "cast:Chain Lightning": -0.1667}, "104758": {"flag:lava_burst": 1},
    # Shaman Enhancement
    "104753": {"melee_crit": 1, "spell_crit": 1}, "104756": {"stat_pct:intellect": 0.02}, "104755": {"ap_from_int": 0.3333}, "104750": {"flag:elemental_weapons": 0.1333},
    "104749": {"cost_pct:Earth Shock": -0.45, "cost_pct:Flame Shock": -0.45}, "104747": {"flag:flurry": 0.05}, "104743": {"flag:stormstrike": 1}, "104744": {"sp_from_int": 0.15},
    "104742": {"flag:improved_stormstrike": 0.5}, "104741": {"flag:maelstrom_weapon": 0.04}, "104740": {"flag:rage_of_the_farseer": 1},
    # Warlock Affliction
    "105925": {"spell_hit": 1, "threat_mult": -0.04}, "105924": {"cast:Corruption": -0.4, "dmg_ability:Corruption": 0.02}, "105923": {"dmg_periodic": 0.01},
    "105920": {"flag:improved_drains": 0.02}, "105919": {"dmg_ability:Curse of Agony": 0.05}, "105917": {"crit_dmg_periodic": 0.333}, "110876": {"crit_school:shadow": 1},
    "105914": {"flag:nightfall": 0.02}, "105912": {"flag:siphon_life": 1}, "105911": {"flag:soul_siphon": 0.1667}, "105910": {"dmg_school:shadow": 0.01},
    # Warlock Demonology
    "105908": {"flag:improved_imp": 0.10}, "105906": {"flag:pet_damage": 0.02}, "105903": {"stat_pct:mana": 0.05}, "105901": {"flag:improved_sayaad": 0.10},
    "105900": {"flag:demonic_sacrifice": 1}, "105892": {"flag:soul_link": 0.03}, "105893": {"flag:demonic_knowledge": 20}, "105891": {"flag:master_demonologist": 0.02},
    # Warlock Destruction
    "105889": {"flag:improved_shadow_bolt": 0.04}, "105888": {"cast:Shadow Bolt": -0.1, "cast:Immolate": -0.1}, "105887": {"cost_pct_school:fire": -0.0333, "cost_pct:Shadow Bolt": -0.0333, "cost_pct:Shadowburn": -0.0333},
    "105886": {"flag:aftermath": 0.10}, "105883": {"crit_dmg_destruction": 0.20}, "105884": {"flag:shadowburn": 1}, "105879": {"crit_ability:Searing Pain": 3.333, "dmg_destruction": 0.0333},
    "105880": {"flag:conflagrate": 1}, "105877": {"crit_ability:Conflagrate": 8.333}, "105875": {"flag:shadow_and_flame": 0.02}, "105874": {"flag:incinerate": 1},
}

# Abilities whose availability requires a talent flag.
TALENT_GATED = {"Mortal Strike": "mortal_strike", "Spearing Strike": "spearing_strike", "Bloodthirst": "bloodthirst", "Death Wish": "death_wish", "Shield Slam": "shield_slam", "Strider Kick": "strider_kick",
                "Insect Swarm": "insect_swarm", "Bestial Wrath": "bestial_wrath", "Combustion": "combustion", "Presence of Mind": "presence_of_mind", "Arcane Power": "arcane_power",
                "Cold Snap": "cold_snap", "Mind Flay": "mind_flay", "Cold Blood": "cold_blood", "Blade Flurry": "blade_flurry", "Adrenaline Rush": "adrenaline_rush",
                "Hemorrhage": "hemorrhage", "Stormstrike": "stormstrike", "Rage of the Farseer": "rage_of_the_farseer", "Siphon Life": "siphon_life", "Conflagrate": "conflagrate",
                "Shadowburn": "shadowburn", "Demonic Sacrifice": "demonic_sacrifice",
                "Arcane Blast": "arcane_blast", "Pyroblast": "pyroblast", "Ice Lance": "ice_lance", "Summon Hawk": "summon_hawk",
                "Mutilate": "mutilate", "Venom": "venom", "Lava Burst": "lava_burst", "Incinerate": "incinerate",
                "Mangle": "mangle", "Mangle (Bear)": "mangle", "Berserk": "berserk"}

# Default 51-point builds (validated against tier/prerequisite rules in tests).
DEFAULT_BUILDS = {
    "warrior-arms": {"105958": 3, "105956": 3, "105957": 1, "105954": 5, "105952": 2, "105951": 1, "105950": 3, "105949": 1, "105948": 3, "105947": 2, "105944": 5, "105945": 1, "105941": 1,
                     "105939": 5, "105938": 5, "105937": 5, "105933": 5},
    "warrior-fury": {"105958": 3, "105956": 3, "105954": 5, "105951": 1, "105950": 3, "105947": 1,
                     "105939": 5, "105938": 5, "105937": 5, "105933": 5, "105931": 5, "105929": 3, "105927": 1, "105928": 5, "105930": 1},
    "warrior-protection": {"105976": 5, "105975": 5, "105974": 2, "105973": 5, "105971": 2, "105969": 3, "110856": 3, "105968": 3, "105965": 1, "105962": 5, "105961": 3, "105959": 1,
                           "105958": 3, "105956": 3, "105954": 5, "105951": 1, "105950": 1},
    "druid-balance": {"104923": 5, "104924": 5, "104925": 3, "104931": 2, "104927": 2, "104929": 2, "104930": 1, "104932": 5, "104933": 5, "104934": 1, "104935": 3, "104936": 5, "104937": 1,
                      "104939": 5, "104938": 5, "104942": 1},
    # Mangle (row3) + King of the Jungle (row4, maxed) + Berserk (row6) added; Heart of the Wild
    # 5->2, Feral Swiftness 2->1, and Predatory Instincts 2->1 trimmed to stay at 51.
    "druid-feral-dps": {"104938": 5, "104939": 2, "104943": 1, "104940": 3, "104948": 2, "104946": 2, "104945": 3, "104952": 3, "104947": 2, "104949": 1, "104950": 1, "104951": 3, "104955": 1, "104953": 5, "104956": 1,
                        "104923": 5, "104924": 5, "104927": 2, "104929": 2, "104931": 2},
    # Mangle (row3) + Berserk (row6) added; Feral Swiftness 2->0 trimmed to stay at 51.
    # King of the Jungle skipped (Feral Tank's rotation never casts Tiger's Fury).
    "druid-feral-tank": {"104938": 5, "104939": 5, "104942": 3, "104940": 3, "104948": 2, "104946": 2, "104952": 3, "104947": 2, "104949": 1, "104950": 2, "104955": 1, "104954": 5, "104956": 1,
                         "104923": 5, "104924": 5, "104927": 2, "104929": 2, "104931": 2},
    # Summon Hawk (row3) added; off-tree Improved Stings trimmed 3->2 to stay at 51.
    "hunter-beast-mastery": {"104960": 5, "104976": 5, "104975": 2, "104970": 1, "104969": 5, "104967": 5, "104966": 1, "104963": 1, "104964": 1, "104962": 5, "104961": 1,
                             "105011": 5, "110870": 2, "105009": 5, "105008": 5, "105003": 2},
    "hunter-marksmanship": {"105011": 5, "105009": 5, "105008": 5, "110870": 3, "105003": 5, "105002": 5, "104998": 3,
                            "104960": 5, "104976": 5, "104975": 2, "104969": 5, "104967": 3},
    # Melee build (Strider Kick/Expose Prey/Lacerating Strikes maxed; validated 51-point spend).
    "hunter-survival": {"104996": 5, "104995": 4, "104994": 5, "104993": 2, "104992": 5, "104990": 3, "104991": 2, "104987": 3, "104986": 1,
                        "104988": 2, "110861": 5, "104989": 1, "104983": 2, "104985": 2, "110860": 2, "104981": 1, "110859": 5, "104984": 1},
    # Arcane Blast (row2) + Missile Barrage (row3) added; Improved Channeling (no combat value in
    # single-target sims) trimmed 5->3 to stay at 51, keeping every damage/crit talent at full rank.
    "mage-arcane": {"105814": 5, "105813": 3, "105810": 5, "105807": 3, "105806": 1, "105803": 3, "105802": 1, "105801": 1, "105800": 5, "105799": 3, "105798": 1,
                    "105795": 5, "105796": 3, "105794": 5, "105793": 2, "105790": 1, "105789": 2, "105785": 2},
    # Pyroblast (row2) + Hot Streak (row3) added, Fire Power kept at max rank; off-tree Magic
    # Absorption (no combat value in single-target sims) dropped entirely to stay at 51.
    "mage-fire": {"105796": 3, "105795": 5, "105794": 5, "105789": 3, "105790": 1, "105788": 3, "105785": 3, "105786": 1, "105784": 3, "105782": 5, "105781": 1,
                  "105814": 5, "105810": 5, "105807": 3, "105803": 3, "105813": 2},
    # Ice Lance (row2) + Fingers of Frost (row4) added; Arcane Meditation (105803) dropped to stay at 51.
    "mage-frost": {"105779": 5, "105778": 5, "105777": 5, "105773": 3, "105772": 3, "105768": 3, "105767": 1, "105766": 1, "105764": 2, "105763": 5, "105762": 1,
                   "105814": 5, "105813": 2, "105812": 2, "105810": 5, "105807": 3},
    "priest-shadow": {"110851": 5, "105833": 5, "105831": 3, "105830": 2, "105827": 5, "105826": 1, "105825": 2, "105821": 3, "105820": 1, "105818": 5, "105817": 1, "110854": 2,
                      "105849": 5, "105850": 2, "105846": 3, "105842": 3, "105843": 3},
    "rogue-assassination": {"105722": 5, "105721": 3, "105720": 2, "105739": 3, "105759": 1, "105716": 5, "105715": 1, "105713": 5, "105718": 1, "105710": 5,
                            "105709": 1, "105712": 1, "105708": 3, "105741": 2, "105719": 3, "105737": 3, "105736": 2, "105738": 2, "105740": 3},
    "rogue-combat": {"105708": 3, "105741": 2, "105719": 3, "105737": 3, "105738": 2, "105736": 2, "105740": 5, "108100": 1, "105728": 1, "105727": 5, "105726": 2, "105730": 1, "105724": 1,
                     "105722": 5, "105721": 3, "105720": 2, "105739": 3, "105759": 1, "105716": 5, "105723": 1},
    "rogue-subtlety": {"105760": 2, "105761": 3, "105756": 1, "105751": 3, "105757": 2, "105749": 1, "105755": 3, "105754": 1, "110868": 1, "105752": 3, "105743": 1, "105745": 2, "105746": 1, "105748": 1, "110867": 5, "110866": 1,
                       "105722": 5, "105721": 3, "105720": 2, "105739": 3, "105759": 1, "105716": 5, "105723": 1},
    "shaman-elemental": {"104773": 5, "104772": 5, "104767": 4, "104770": 3, "104768": 1, "104766": 5, "104762": 1, "104759": 3, "104765": 3, "104758": 1,
                         "104753": 5, "104756": 5, "104755": 3, "104750": 3, "104749": 1, "104747": 3},
    # Maelstrom Weapon maxed (3->5); two off-tree Elemental leaf picks dropped to stay at 51.
    "shaman-enhancement": {"104753": 5, "104756": 5, "104755": 3, "104750": 3, "104749": 1, "104747": 5, "104743": 1, "104744": 2, "104742": 2, "104741": 5, "104740": 1,
                           "104773": 5, "104772": 5, "104767": 5, "104770": 3},
    "warlock-affliction": {"105925": 5, "105924": 5, "105923": 5, "105919": 1, "105917": 3, "110876": 5, "105912": 1, "105910": 5, "105909": 1,
                           "105889": 5, "105888": 5, "105887": 3, "105886": 2, "105883": 5},
    "warlock-demonology": {"105908": 3, "105906": 5, "105907": 2, "105903": 3, "105899": 2, "105901": 3, "105900": 1, "105898": 2, "105892": 1, "105893": 3, "105891": 5, "105890": 1,
                           "105925": 5, "105924": 5, "105923": 5, "110876": 3, "105919": 2},
    "warlock-destruction": {"105889": 5, "105888": 5, "105887": 3, "105886": 2, "105883": 5, "105884": 1, "105879": 3, "105880": 1, "105877": 3, "105875": 5, "105874": 1, "105876": 1,
                            "105925": 5, "105924": 5, "105923": 5, "110876": 1},
}

# Hunter pets (WoWSims Classic level-60 pet_abilities.go / focus.go).
PET_FAMILIES = {
    "cat": {"damage": 1.10, "special": "Bite", "dump": "Claw"}, "wind_serpent": {"damage": 1.07, "special": "Bite", "dump": "Lightning Breath"},
    "bat": {"damage": 1.07, "special": "Bite", "dump": "Screech"}, "bear": {"damage": .91, "special": "Bite", "dump": "Claw"}, "boar": {"damage": .90, "special": None, "dump": "Bite"},
    "carrion_bird": {"damage": 1.00, "special": "Bite", "dump": "Claw"}, "owl": {"damage": 1.07, "special": None, "dump": "Claw"}, "crab": {"damage": .95, "special": None, "dump": "Claw"},
    "crocolisk": {"damage": 1.00, "special": None, "dump": "Bite"}, "gorilla": {"damage": 1.02, "special": None, "dump": "Bite"}, "hyena": {"damage": 1.00, "special": None, "dump": "Bite"},
    "raptor": {"damage": 1.10, "special": "Bite", "dump": "Claw"}, "scorpid": {"damage": .94, "special": "Scorpid Poison", "dump": "Claw"}, "spider": {"damage": 1.07, "special": None, "dump": "Bite"},
    "tallstrider": {"damage": 1.00, "special": None, "dump": "Bite"}, "turtle": {"damage": .90, "special": None, "dump": "Bite"}, "wolf": {"damage": 1.00, "special": None, "dump": "Bite"},
}
PET_ABILITIES = {"Claw": {"cost": 25, "cooldown": 0, "min": 43, "max": 59, "school": "physical"}, "Bite": {"cost": 35, "cooldown": 10, "min": 81, "max": 91, "school": "physical"},
                 "Lightning Breath": {"cost": 50, "cooldown": 0, "min": 99, "max": 113, "school": "nature"}, "Screech": {"cost": 20, "cooldown": 0, "min": 26, "max": 46, "school": "physical"},
                 "Scorpid Poison": {"cost": 30, "cooldown": 4, "min": 40, "max": 50, "school": "nature"}}
PET_FOCUS_PER_SEC = 26.25 / 5.25
# Warlock demons (WoWSims Classic imp.go / succubus.go / felhunter.go / voidwalker.go, level 60).
WARLOCK_PETS = {
    "imp": {"speed": 0, "melee": None, "spell": "Firebolt", "spell_cost": 115, "cast": 2.0, "spell_min": 85, "spell_max": 96, "school": "fire", "mana": 149 + 15 * 212, "intellect": 212, "spirit": 212, "stamina": 71},
    "succubus": {"speed": 2.0, "melee": (41, 61), "spell": "Lash of Pain", "spell_cost": 160, "cooldown": 12, "spell_min": 99, "spell_max": 99, "school": "shadow", "mana": 521 + 15 * 49, "intellect": 49, "spirit": 97, "strength": 74, "stamina": 148},
    "felhunter": {"speed": 2.0, "melee": (24, 40), "spell": None, "mana": 653 + 15 * 49, "intellect": 49, "spirit": 97, "strength": 74, "stamina": 148},
    "voidwalker": {"speed": 2.0, "melee": (31, 46), "spell": None, "utility": "Torment", "mana": 1066, "intellect": 49, "spirit": 97, "strength": 74, "stamina": 148},
}
# Rogue poisons (WoWSims level-60 values): Instant Poison VI 112-148, 20% chance; Deadly Poison V 27/tick per stack, 30% chance.
POISONS = {"instant": {"chance": 0.20, "min": 112, "max": 148}, "deadly": {"chance": 0.30, "tick": 27, "ticks": 4, "tick_len": 3, "max_stacks": 5}}
WINDFURY = {"chance": 0.20, "extra_attacks": 2, "ap": 333}
ITEM_PROC_PPM = {12798: 1.0, 17076: 2.0, 17075: 0.6, 17112: 1.0, 19019: 6.0}

WEAPON_CRIT_TYPES = ("Sword", "Mace", "Axe")

# Set bonuses with combat effects beyond flat stats, keyed "Set Name|pieces".  Values come from
# WoWSims Classic (sim/*/item_sets*.go, sim/common/item_sets/*.go) unless listed in SET_PROVISIONAL.
# Flat-stat bonuses are parsed from their text by engine.SET_PATTERNS.  Keys understood by the
# engine are the talent-effect keys plus: creature_dmg:<type>, buff_ap:battle_shout, buff_pct:mana_spring,
# hawk_pct, threat_ability:<a>, hit_ability:<a>, flat_ability:<a>, duration:<a>, ticks:<a>, skill:<weapon>,
# chain_lightning_bounce and the flag:* procs handled in engine.Iteration.
SET_EFFECTS = {
    # Warrior
    "Battlegear of Might|5": {"flag:might_rage": 0.20}, "Battlegear of Might|8": {"threat_ability:Sunder Armor": 0.15},
    "Battlegear of Wrath|3": {"buff_ap:battle_shout": 30}, "Battlegear of Wrath|5": {"flag:wrath_rage_proc": 0.20}, "Battlegear of Wrath|8": {"flag:wrath_parry": 0.04},
    "Dreadnaught's Battlegear|2": {"flat_ability:Revenge": 75},
    "Dreadnaught's Battlegear|6": {"hit_ability:Sunder Armor": 5, "hit_ability:Heroic Strike": 5, "hit_ability:Revenge": 5, "hit_ability:Shield Slam": 5},
    "Vindicator's Battlegear|5": {"cost:Whirlwind": -3}, "Conqueror's Battlegear|5": {"dmg_ability:Thunder Clap": 0.5},
    # Hunter
    "Giantstalker Armor|8": {"dmg_ability:Multi-Shot": 0.15}, "Beaststalker Armor|6": {"flag:beaststalker_mana": 0.04},
    "Dragonstalker Armor|3": {"hawk_pct": 0.25}, "Dragonstalker Armor|8": {"flag:dragonstalker_ew": 0.5},
    "Cryptstalker Armor|2": {"duration:Rapid Fire": 4}, "Cryptstalker Armor|6": {"flag:cryptstalker_mana": 50}, "Cryptstalker Armor|8": {"cost:Multi-Shot": -20, "cost:Aimed Shot": -20},
    "Striker's Garb|3": {"cost_pct:Arcane Shot": -0.10}, "Striker's Garb|5": {"cooldown:Rapid Fire": -120}, "Predator's Armor|5": {"ticks:Serpent Sting": 1},
    "Trappings of the Unseen Path|3": {"flag:pet_damage": 0.03}, "Beastmaster Armor|3": {"flag:pet_damage": 0.03},
    # Rogue
    "Shadowcraft Armor|6": {"flag:shadowcraft_energy": 1.0}, "Bloodfang Armor|3": {"flag:poison_chance": 0.05}, "Bloodfang Armor|8": {"flag:bloodfang_proc": 1.0},
    "Bonescythe Armor|4": {"flag:bonescythe_energy": 5},
    "Bonescythe Armor|6": {"threat_ability:Backstab": -0.0741, "threat_ability:Sinister Strike": -0.0741, "threat_ability:Hemorrhage": -0.0741, "threat_ability:Eviscerate": -0.0741},
    "Deathdealer's Embrace|5": {"dmg_ability:Eviscerate": 0.15}, "Madcap's Outfit|5": {"cost:Eviscerate": -5, "cost:Rupture": -5},
    "Emblems of Veiled Shadows|3": {"cost:Slice and Dice": -10}, "Symbols of Unending Life|3": {"flag:finisher_refund": 30},
    "Stormshroud Armor|2": {"flag:stormshroud_dmg": 0.05}, "Stormshroud Armor|3": {"flag:stormshroud_energy": 0.02},
    # Mage
    "Arcanist Regalia|5": {"flag:target_resist": 10}, "Netherwind Regalia|8": {"flag:netherwind_instant": 0.10}, "Enigma Vestments|5": {"flag:enigma_hit": 5},
    # Priest
    "Vestments of Prophecy|5": {"crit_school:holy": 2}, "Finery of Infinite Wisdom|3": {"dmg_ability:Shadow Word: Pain": 0.05},
    "Vestments of Transcendence|3": {"flag:spirit_while_casting": 0.15},
    # Shaman
    "The Ten Storms|5": {"crit_school:nature": 3}, "Stormcaller's Garb|3": {"flag:stormcaller": 0.20}, "Gift of the Gathering Storm|3": {"chain_lightning_bounce": 0.05},
    "The Earthshatterer|4": {"buff_pct:mana_spring": 0.25},
    "Champion's Earthshaker|4": {"crit_ability:Earth Shock": 2, "crit_ability:Flame Shock": 2}, "Champion's Stormcaller|4": {"crit_ability:Earth Shock": 2, "crit_ability:Flame Shock": 2},
    "Warlord's Earthshaker|3": {"crit_ability:Earth Shock": 2, "crit_ability:Flame Shock": 2},
    # Warlock
    "Felheart Raiment|8": {"cost_pct_school:shadow": -0.15}, "Demoniac's Threads|3": {"dmg_ability:Corruption": 0.02}, "Doomcaller's Attire|3": {"dmg_ability:Immolate": 0.05},
    "Doomcaller's Attire|5": {"cost_pct:Shadow Bolt": -0.15}, "Plagueheart Raiment|4": {"dmg_ability:Corruption": 0.12}, "Implements of Unspoken Names|3": {"flag:pet_damage": 0.05},
    "Champion's Dreadgear|4": {"cast:Immolate": -0.2}, "Champion's Threads|4": {"cast:Immolate": -0.2}, "Lieutenant Commander's Dreadgear|4": {"cast:Immolate": -0.2},
    "Lieutenant Commander's Threads|4": {"cast:Immolate": -0.2}, "Field Marshal's Threads|3": {"cast:Immolate": -0.2}, "Warlord's Threads|3": {"cast:Immolate": -0.2},
    # Druid
    "Haruspex's Garb|5": {"crit_ability:Starfire": 3}, "Stormrage Raiment|3": {"flag:spirit_while_casting": 0.15}, "Green Dragon Mail|3": {"flag:spirit_while_casting": 0.15},
    "Wildheart Raiment|6": {"flag:wildheart_proc": 0.02},
    # Shared
    "Battlegear of Undead Slaying|3": {"creature_dmg:undead": 0.02}, "Garb of the Undead Slayer|3": {"creature_dmg:undead": 0.02},
    "Regalia of Undead Cleansing|3": {"creature_dmg:undead": 0.02}, "Undead Slayer's Armor|3": {"creature_dmg:undead": 0.02},
    "The Twin Blades of Hakkari|2": {"skill:Sword": 6}, "Spider's Kiss|2": {"flag:spiders_kiss": 0.05},
}
# Bonuses with no effect in a single-target Patchwerk fight (healing, PvP utility, resistances, movement,
# utility cooldowns, Paladin-only effects handled by the Paladin engine).  Listed as modeled with no numbers.
SET_NO_COMBAT_EFFECT = ("""Arcanist Regalia|8 Augur's Regalia|3 Augur's Regalia|5 Avenger's Battlegear|3 Battlegear of Eternal Justice|3 Battlegear of Unyielding Strength|3
Battlegear of Valor|6 Battlegear of Valor|8 Beaststalker Armor|8 Black Dragon Mail|4 Blue Dragon Mail|2 Bonescythe Armor|2 Bonescythe Armor|8 Cadaverous Garb|4 Cenarion Raiment|3 Cenarion Raiment|8
Champion's Arcanum|4 Champion's Battlearmor|4 Champion's Battlegear|4 Champion's Guard|4 Champion's Investiture|4 Champion's Pursuance|4 Champion's Pursuit|4 Champion's Raiment|4 Champion's Regalia|4
Champion's Sanctuary|4 Champion's Vestments|4 Champion's Refuge|4 Confessor's Raiment|2 Confessor's Raiment|3 Confessor's Raiment|5 Conqueror's Battlegear|3 Cryptstalker Armor|4 Deathbone Guardian|4
Deathdealer's Embrace|3 Demoniac's Threads|5 Dragonstalker Armor|5 Dreadmist Raiment|6 Dreadmist Raiment|8 Dreadnaught's Battlegear|4 Dreadnaught's Battlegear|8 Dreamwalker Raiment|2
Dreamwalker Raiment|4 Dreamwalker Raiment|6 Dreamwalker Raiment|8 Enigma Vestments|3 Field Marshal's Aegis|3 Field Marshal's Battlegear|3 Field Marshal's Pursuit|3 Field Marshal's Raiment|3
Field Marshal's Regalia|3 Field Marshal's Sanctuary|3 Field Marshal's Vestments|3 Freethinker's Armor|3 Freethinker's Armor|5 Frostfire Regalia|2 Frostfire Regalia|4 Frostfire Regalia|6
Frostfire Regalia|8 Garments of the Oracle|3 Garments of the Oracle|5 Genesis Raiment|5 Haruspex's Garb|3 Illusionist's Attire|3 Illusionist's Attire|5 Ironweave Battlesuit|4 Judgement Armor|3
Judgement Armor|8 Lawbringer Armor|3 Lawbringer Armor|8 Lieutenant Commander's Aegis|4 Lieutenant Commander's Arcanum|4 Lieutenant Commander's Battlearmor|4 Lieutenant Commander's Battlegear|4
Lieutenant Commander's Guard|4 Lieutenant Commander's Investiture|4 Lieutenant Commander's Pursuance|4 Lieutenant Commander's Pursuit|4 Lieutenant Commander's Raiment|4 Lieutenant Commander's Redoubt|4
Lieutenant Commander's Refuge|4 Lieutenant Commander's Regalia|4 Lieutenant Commander's Sanctuary|4 Lieutenant Commander's Vestments|4 Lightforge Armor|4 Lightforge Armor|5 Madcap's Outfit|3
Magister's Regalia|6 Magister's Regalia|8 Necropile Raiment|4 Nemesis Raiment|5 Nemesis Raiment|8 Netherwind Regalia|3 Netherwind Regalia|5 Nightslayer Armor|3 Nightslayer Armor|8
Plagueheart Raiment|2 Plagueheart Raiment|6 Plagueheart Raiment|8 Prayer of the Primal|2 Predator's Armor|3 Primal Batskin|3 Redemption Armor|2 Redemption Armor|4 Redemption Armor|6
Redemption Armor|8 Shard of the Gods|2 Spirit of Eskhandar|4 Stormcaller's Garb|5 Stormrage Raiment|5 Stormrage Raiment|8 The Earthfury|3 The Earthfury|5 The Earthfury|8
The Earthshatterer|2 The Earthshatterer|6 The Earthshatterer|8 The Elements|8 The Postmaster|3 The Postmaster|5 Trappings of Vaulted Secrets|3 Vestments of Faith|2 Vestments of Faith|4
Vestments of Faith|6 Vestments of Faith|8 Vestments of Transcendence|5 Vestments of Transcendence|8 Vestments of the Devout|6 Vestments of the Devout|8 Vindicator's Battlegear|3
Warlord's Battlegear|3 Warlord's Pursuit|3 Warlord's Raiment|3 Warlord's Regalia|3 Warlord's Sanctuary|3 Warlord's Vestments|3 Wildheart Raiment|8 Giantstalker Armor|3 Giantstalker Armor|5
Felheart Raiment|3 Felheart Raiment|5 Vestments of Prophecy|3 Vestments of Prophecy|8 Bloodfang Armor|5 The Ten Storms|3 The Ten Storms|8 Bloodmail Regalia|4 Shadowcraft Armor|8""")
SET_NO_COMBAT_EFFECT = {m.strip() for m in re.findall(r"[^|]+?\|\d+", SET_NO_COMBAT_EFFECT)}
# Bonuses modeled with an assumption (surfaced as provisional in the result).
SET_PROVISIONAL = {"Bloodfang Armor|8": "6 x 1-second ticks of 283-317 total physical damage at 1 PPM; the heal is ignored.",
                   "Spider's Kiss|2": "5% chance per melee hit to lower target armor by 100 for 10 sec.",
                   "Dragonstalker Armor|8": "Expose Weakness modeled as +450 ranged attack power for 7 sec at 0.5 PPM."}
