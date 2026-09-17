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
BLOODLUST_DURATION, BLOODLUST_HASTE = 40.0, 0.30
GCD, ENERGY_GCD = 1.5, 1.0

# ---------------------------------------------------------------------------
# Racials (Wowhead Forever guide).  Unpublished numbers are provisional.
# ---------------------------------------------------------------------------
RACIALS = {
    "Human": {"weapon_crit": {"Sword": 2.0}, "summary": "Sword Specialization: +2% spell and ability critical chance while a sword is equipped."},
    "Dwarf": {"weapon_crit": {"Mace": 1.0}, "creature_damage": {"beast": 0.05}, "summary": "Mace Specialization: +1% critical chance with a mace equipped. Big Game Hunter: +5% damage to Beasts."},
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
    "power_word_fortitude": {"stamina": 70}, "mark_of_the_wild": {"strength": 16, "agility": 16, "stamina": 16, "intellect": 16, "spirit": 16, "armor": 385},
    "arcane_intellect": {"intellect": 31}, "battle_shout": {"attackPower": 290}, "blessing_of_might": {"attackPower": 222}, "devotion_aura": {"armor": 735},
    "blessing_of_wisdom": {"mp5": 33}, "strength_of_earth": {"strength": 77}, "grace_of_air": {"agility": 77}, "mana_spring": {"mp5": 15},
    "leader_of_the_pack": {"meleeCrit": 3, "rangedCrit": 3}, "moonkin_aura": {"spellCrit": 3}, "trueshot_aura": {"rangedAttackPower": 100},
    "blessing_of_kings": {}, "windfury_totem": {},
}
BUFF_GROUPS = {"air_totem": ["grace_of_air", "windfury_totem"], "crit_aura": ["leader_of_the_pack", "moonkin_aura"]}
WINDFURY_TOTEM = {"chance": 0.20, "ap": 315}

def default_buffs(spec):
    """Full compatible raid package for a spec (no world buffs)."""
    core = ["power_word_fortitude", "mark_of_the_wild", "arcane_intellect", "blessing_of_kings", "devotion_aura"]
    if spec["style"] == "spell":
        return core + ["blessing_of_wisdom", "mana_spring", "moonkin_aura"]
    physical = core + ["battle_shout", "blessing_of_might", "strength_of_earth", "leader_of_the_pack"]
    if spec["style"] == "ranged":
        return physical + ["grace_of_air", "trueshot_aura", "blessing_of_wisdom", "mana_spring"]
    if spec["class_name"] in {"Shaman", "Hunter"}:
        return physical + ["windfury_totem", "blessing_of_wisdom", "mana_spring"]
    if spec["class_name"] == "Druid":
        return physical + ["grace_of_air"]  # Windfury does not work in forms
    return physical + ["windfury_totem"]

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
    ("hunter-survival", "Hunter", "Survival", "dps", "ranged", "Mana", "Survival", None, None),
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
    "Mortal Strike": {"kind": "direct", "school": "physical", "cost": 30, "cooldown": 6, "weapon": {"hand": "main", "normalized": True, "flat": 85}, "forever": True},
    "Overpower": {"kind": "direct", "school": "physical", "cost": 5, "cooldown": 5, "weapon": {"hand": "main", "normalized": True, "flat": 35}, "requires": "dodge", "no_dodge": True, "threat_mult": 0.75},
    "Whirlwind": {"kind": "direct", "school": "physical", "cost": 25, "cooldown": 10, "weapon": {"hand": "main", "normalized": True}, "threat_mult": 1.25},
    "Spearing Strike": {"kind": "direct", "school": "physical", "cost": 20, "cooldown": 6, "weapon": {"hand": "main", "normalized": True, "mult": 0.40}, "creature_mult": {"giant": 3.0, "dragonkin": 3.0}, "forever": True, "provisional": "rage cost and cooldown are not published"},
    "Execute": {"kind": "direct", "school": "physical", "cost": 15, "execute": True, "execute_formula": (600, 15), "threat_mult": 1.25},
    "Bloodthirst": {"kind": "direct", "school": "physical", "cost": 30, "cooldown": 6, "ap_mult": 0.35, "flat": 30, "forever": True},
    "Hamstring": {"kind": "direct", "school": "physical", "cost": 10, "flat": 45},
    "Shield Slam": {"kind": "direct", "school": "physical", "cost": 20, "cooldown": 6, "base": (421, 439), "add_block_value": True, "flat_threat": 250, "forever": True},
    "Revenge": {"kind": "direct", "school": "physical", "cost": 5, "cooldown": 5, "base": (81, 99), "requires": "block_dodge_parry", "threat_mult": 2.25, "flat_threat": 270},
    "Sunder Armor": {"kind": "direct", "school": "physical", "cost": 15, "no_damage": True, "flat_threat": 270},
    "Bloodrage": {"kind": "buff", "cooldown": 60, "off_gcd": True, "rage": 10, "rage_over_time": (1, 10)},
    "Death Wish": {"kind": "buff", "cooldown": 180, "cost": 10, "duration": 30, "damage_mult_school": ("physical", 0.20), "forever": True},
    # ---- Druid ---------------------------------------------------------------
    "Shred": {"kind": "direct", "school": "physical", "cost": 60, "gcd": 1.0, "weapon": {"hand": "form", "mult": 2.25, "flat": 80}, "cp": 1},
    "Claw": {"kind": "direct", "school": "physical", "cost": 45, "gcd": 1.0, "weapon": {"hand": "form", "flat": 115}, "cp": 1},
    "Ferocious Bite": {"kind": "direct", "school": "physical", "cost": 35, "gcd": 1.0, "finisher": "ferocious_bite"},
    "Rip": {"kind": "dot", "school": "physical", "cost": 30, "gcd": 1.0, "finisher": "rip", "ticks": 6, "tick_len": 2, "bleed": True},
    "Tiger's Fury": {"kind": "buff", "cost": 30, "gcd": 1.0, "duration": 6, "flat_damage_bonus": 40},
    "Maul": {"kind": "swing", "school": "physical", "cost": 15, "weapon": {"hand": "form", "flat": 128}, "threat_mult": 1.75},
    "Swipe": {"kind": "direct", "school": "physical", "cost": 20, "base": (83, 83), "threat_mult": 2.0},
    "Moonfire": {"kind": "direct_dot", "school": "arcane", "cost": 375, "base": (195, 228), "coeff": 0.15, "tick": 32, "ticks": 4, "tick_len": 3, "dot_coeff": 0.13},
    "Insect Swarm": {"kind": "dot", "school": "nature", "cost": 155, "tick": 54, "ticks": 6, "tick_len": 2, "dot_coeff": 0.127},
    "Starfire": {"kind": "direct", "school": "arcane", "cost": 340, "cast": 3.5, "base": (496, 584), "coeff": 1.0},
    "Wrath": {"kind": "direct", "school": "nature", "cost": 180, "cast": 2.0, "base": (248, 277), "coeff": 0.571},
    # ---- Hunter --------------------------------------------------------------
    "Aimed Shot": {"kind": "direct", "school": "physical", "cost": 310, "cooldown": 6, "cast": 3.0, "ranged_cast": True, "weapon": {"hand": "ranged", "normalized": True, "flat": 600}},
    "Multi-Shot": {"kind": "direct", "school": "physical", "cost": 230, "cooldown": 10, "cast": 0.5, "ranged_cast": True, "weapon": {"hand": "ranged", "normalized": True, "flat": 150}},
    "Arcane Shot": {"kind": "direct", "school": "arcane", "cost": 190, "cooldown": 6, "base": (183, 183), "coeff": 0.429},
    "Serpent Sting": {"kind": "dot", "school": "nature", "cost": 250, "tick": 111, "ticks": 5, "tick_len": 3, "dot_coeff": 0.2},
    "Explosive Trap": {"kind": "direct_dot", "school": "fire", "cost": 520, "cooldown": 15, "base": (208, 265), "coeff": 0.0, "tick": 33, "ticks": 10, "tick_len": 2, "dot_coeff": 0.0},
    "Bestial Wrath": {"kind": "buff", "cooldown": 120, "duration": 18, "pet_damage_mult": 0.50},
    "Rapid Fire": {"kind": "buff", "cooldown": 300, "duration": 15, "ranged_haste": 0.40, "off_gcd": True},
    # ---- Mage ----------------------------------------------------------------
    "Fireball": {"kind": "direct_dot", "school": "fire", "cost": 410, "cast": 3.5, "base": (596, 760), "coeff": 1.0, "tick": 19, "ticks": 4, "tick_len": 2, "dot_coeff": 0.0},
    "Scorch": {"kind": "direct", "school": "fire", "cost": 150, "cast": 1.5, "base": (237, 280), "coeff": 0.429},
    "Fire Blast": {"kind": "direct", "school": "fire", "cost": 340, "cooldown": 8, "base": (446, 524), "coeff": 0.429},
    "Frostbolt": {"kind": "direct", "school": "frost", "cost": 290, "cast": 3.0, "base": (515, 555), "coeff": 0.814},
    "Arcane Missiles": {"kind": "channel", "school": "arcane", "cost": 595, "cast": 5.0, "tick": 196, "ticks": 5, "coeff": 0.24},
    "Arcane Power": {"kind": "buff", "cooldown": 180, "duration": 15, "damage_mult": 0.30, "cost_mult": 0.30, "off_gcd": True},
    "Combustion": {"kind": "buff", "cooldown": 180, "combustion": True, "off_gcd": True},
    "Presence of Mind": {"kind": "buff", "cooldown": 180, "instant_next": True, "off_gcd": True},
    "Cold Snap": {"kind": "buff", "cooldown": 600, "off_gcd": True, "no_effect": "Resets Frost cooldowns; nothing in the single-target rotation uses one"},
    # ---- Priest --------------------------------------------------------------
    "Shadow Word: Pain": {"kind": "dot", "school": "shadow", "cost": 470, "tick": 106.5, "ticks": 8, "tick_len": 3, "dot_coeff": 0.167},
    "Mind Blast": {"kind": "direct", "school": "shadow", "cost": 350, "cast": 1.5, "cooldown": 8, "base": (508, 537), "coeff": 0.429},
    "Mind Flay": {"kind": "channel", "school": "shadow", "cost": 205, "cast": 3.0, "tick": 142, "ticks": 3, "coeff": 0.15},
    "Shadow Word: Death": {"kind": "direct", "school": "shadow", "cost": 309, "cooldown": 12, "base": (572, 664), "coeff": 0.429, "provisional": "Forever tooltip not in the dataset; TBC rank 2 values used"},
    # ---- Rogue ---------------------------------------------------------------
    "Sinister Strike": {"kind": "direct", "school": "physical", "cost": 45, "gcd": 1.0, "weapon": {"hand": "main", "normalized": True, "flat": 68}, "cp": 1},
    "Backstab": {"kind": "direct", "school": "physical", "cost": 60, "gcd": 1.0, "weapon": {"hand": "main", "normalized": True, "mult": 1.5, "flat": 150}, "cp": 1, "requires": "dagger"},
    "Hemorrhage": {"kind": "direct", "school": "physical", "cost": 35, "gcd": 1.0, "weapon": {"hand": "main", "normalized": True, "mult": 1.0, "dagger_mult": 1.45}, "cp": 1, "forever": True},
    "Eviscerate": {"kind": "direct", "school": "physical", "cost": 35, "gcd": 1.0, "finisher": "eviscerate"},
    "Rupture": {"kind": "dot", "school": "physical", "cost": 25, "gcd": 1.0, "finisher": "rupture", "tick_len": 2, "bleed": True},
    "Slice and Dice": {"kind": "buff", "cost": 25, "gcd": 1.0, "finisher": "slice_and_dice", "melee_haste": 0.30},
    "Blade Flurry": {"kind": "buff", "cost": 25, "gcd": 1.0, "cooldown": 120, "duration": 15, "melee_haste": 0.20},
    "Adrenaline Rush": {"kind": "buff", "cooldown": 300, "duration": 15, "energy_regen_mult": 2.0, "off_gcd": True},
    "Cold Blood": {"kind": "buff", "cooldown": 180, "next_crit": True, "off_gcd": True},
    "Thistle Tea": {"kind": "buff", "cooldown": 300, "energy": 100, "off_gcd": True},
    # ---- Shaman --------------------------------------------------------------
    "Lightning Bolt": {"kind": "direct", "school": "nature", "cost": 265, "cast": 3.0, "base": (428, 477), "coeff": 0.857},
    "Chain Lightning": {"kind": "direct", "school": "nature", "cost": 605, "cast": 2.5, "cooldown": 6, "base": (505, 564), "coeff": 0.714},
    "Flame Shock": {"kind": "direct_dot", "school": "fire", "cost": 345, "cooldown": 6, "shared_cd": "shock", "base": (292, 292), "coeff": 0.214, "tick": 80, "ticks": 4, "tick_len": 3, "dot_coeff": 0.1},
    "Earth Shock": {"kind": "direct", "school": "nature", "cost": 450, "cooldown": 6, "shared_cd": "shock", "base": (517, 545), "coeff": 0.386},
    "Stormstrike": {"kind": "direct", "school": "physical", "cost": 320, "cooldown": 20, "weapon": {"hand": "main"}, "apply_debuff": ("Stormstrike", 12, {"nature": 0.20}), "forever": True},
    "Elemental Mastery": {"kind": "buff", "cooldown": 180, "next_crit": True, "off_gcd": True},
    "Rage of the Farseer": {"kind": "buff", "cooldown": 180, "duration": 25, "melee_haste": 0.30, "spell_haste": 0.30, "off_gcd": True, "forever": True, "provisional": "cooldown not published; 3 min assumed"},
    # ---- Warlock -------------------------------------------------------------
    "Shadow Bolt": {"kind": "direct", "school": "shadow", "cost": 380, "cast": 3.0, "base": (482, 538), "coeff": 0.857},
    "Corruption": {"kind": "dot", "school": "shadow", "cost": 340, "cast": 2.0, "tick": 137, "ticks": 6, "tick_len": 3, "dot_coeff": 0.167},
    "Curse of Agony": {"kind": "dot", "school": "shadow", "cost": 215, "tick": 87, "ticks": 12, "tick_len": 2, "dot_coeff": 0.083, "curse": True},
    "Siphon Life": {"kind": "dot", "school": "shadow", "cost": 365, "tick": 45, "ticks": 10, "tick_len": 3, "dot_coeff": 0.1},
    "Drain Soul": {"kind": "channel", "school": "shadow", "cost": 290, "cast": 15.0, "tick": 91, "ticks": 5, "coeff": 0.1, "execute_bonus": True},
    "Immolate": {"kind": "direct_dot", "school": "fire", "cost": 380, "cast": 2.0, "base": (279, 279), "coeff": 0.2, "tick": 102, "ticks": 5, "tick_len": 3, "dot_coeff": 0.13},
    "Conflagrate": {"kind": "direct", "school": "fire", "cost": 305, "cooldown": 10, "base": (447, 557), "coeff": 0.429, "requires": "dot:Immolate", "consumes_dot": "Immolate"},
    "Shadowburn": {"kind": "direct", "school": "shadow", "cost": 365, "cooldown": 15, "base": (462, 514), "coeff": 0.429},
    "Searing Pain": {"kind": "direct", "school": "fire", "cost": 168, "cast": 1.5, "base": (208, 244), "coeff": 0.429, "threat_mult": 2.0},
    "Life Tap": {"kind": "buff", "life_tap": 424},
    "Demonic Sacrifice": {"kind": "buff", "sacrifice": True},
    # ---- Consumables -----------------------------------------------------------
    "Goblin Sapper Charge": {"kind": "direct", "school": "fire", "cooldown": 300, "base": (450, 750), "off_gcd": True, "always_hit": True, "no_crit": True},
    "Major Mana Potion": {"kind": "buff", "cooldown": 120, "mana": (1350, 2250), "off_gcd": True, "shared_cd": "potion"},
    "Mighty Rage Potion": {"kind": "buff", "cooldown": 120, "rage": (45, 75), "duration": 20, "strength": 60, "off_gcd": True, "shared_cd": "potion"},
    "Demonic Rune": {"kind": "buff", "cooldown": 120, "mana": (900, 1500), "off_gcd": True},
}

# Rotation priority lists.  Each entry: (ability, condition) where condition is a
# small expression evaluated by engine.Sim.check().  Higher entries win.
ROTATIONS = {
    "warrior-arms": [("Bloodrage", "rage<60"), ("Death Wish", "true"), ("Execute", "execute"), ("Overpower", "true"), ("Mortal Strike", "true"), ("Whirlwind", "true"), ("Spearing Strike", "rage>=50"), ("Heroic Strike", "rage>=45 and not execute")],
    "warrior-fury": [("Bloodrage", "rage<60"), ("Death Wish", "true"), ("Execute", "execute"), ("Bloodthirst", "true"), ("Whirlwind", "true"), ("Hamstring", "rage>=60 and not execute and cd:Bloodthirst>1.5 and cd:Whirlwind>1.5"), ("Heroic Strike", "rage>=40 and not execute")],
    "warrior-protection": [("Bloodrage", "rage<60"), ("Shield Slam", "true"), ("Revenge", "true"), ("Sunder Armor", "stacks:Sunder Armor<5 or rage>=40"), ("Execute", "execute"), ("Heroic Strike", "rage>=30")],
    "druid-balance": [("Moonfire", "dot_missing"), ("Insect Swarm", "dot_missing"), ("Starfire", "true"), ("Wrath", "true")],
    "druid-feral-dps": [("Tiger's Fury", "buff_missing and energy>=60"), ("Ferocious Bite", "cp>=5 and dot:Rip>4"), ("Rip", "cp>=5 and dot_missing"), ("Shred", "true"), ("Claw", "no_shred")],
    "druid-feral-tank": [("Swipe", "rage>=45"), ("Maul", "rage>=20")],
    "hunter-beast-mastery": [("Bestial Wrath", "true"), ("Rapid Fire", "true"), ("Serpent Sting", "dot_missing"), ("Multi-Shot", "true"), ("Arcane Shot", "mana>=1500")],
    "hunter-marksmanship": [("Rapid Fire", "true"), ("Serpent Sting", "dot_missing"), ("Aimed Shot", "true"), ("Multi-Shot", "true"), ("Arcane Shot", "mana>=1500")],
    "hunter-survival": [("Rapid Fire", "true"), ("Serpent Sting", "dot_missing"), ("Explosive Trap", "dot_missing"), ("Aimed Shot", "true"), ("Multi-Shot", "true"), ("Arcane Shot", "mana>=1500")],
    "mage-arcane": [("Arcane Power", "true"), ("Presence of Mind", "true"), ("Arcane Missiles", "true"), ("Frostbolt", "true")],
    "mage-fire": [("Combustion", "true"), ("Scorch", "stacks:Improved Scorch<5 or debuff:Improved Scorch<4"), ("Fire Blast", "moving"), ("Fireball", "true"), ("Scorch", "true")],
    "mage-frost": [("Cold Snap", "false"), ("Frostbolt", "true"), ("Fire Blast", "moving")],
    "priest-shadow": [("Shadow Word: Pain", "dot_missing"), ("Shadow Word: Death", "execute"), ("Mind Blast", "true"), ("Mind Flay", "true")],
    "rogue-assassination": [("Thistle Tea", "energy<20"), ("Cold Blood", "cp>=5"), ("Slice and Dice", "cp>=2 and buff_missing"), ("Eviscerate", "cp>=5"), ("Backstab", "true"), ("Sinister Strike", "no_dagger")],
    "rogue-combat": [("Thistle Tea", "energy<20"), ("Adrenaline Rush", "true"), ("Blade Flurry", "true"), ("Slice and Dice", "cp>=2 and buff_missing"), ("Eviscerate", "cp>=5"), ("Sinister Strike", "true")],
    "rogue-subtlety": [("Thistle Tea", "energy<20"), ("Slice and Dice", "cp>=2 and buff_missing"), ("Rupture", "cp>=5 and dot_missing"), ("Eviscerate", "cp>=5"), ("Hemorrhage", "true")],
    "shaman-elemental": [("Elemental Mastery", "true"), ("Flame Shock", "dot_missing and mana>=2000"), ("Chain Lightning", "mana>=2500"), ("Lightning Bolt", "true")],
    "shaman-enhancement": [("Rage of the Farseer", "true"), ("Stormstrike", "true"), ("Earth Shock", "mana>=1200 or debuff:Stormstrike>0"), ("Flame Shock", "dot_missing and mana>=2500")],
    "warlock-affliction": [("Life Tap", "mana<400"), ("Curse of Agony", "dot_missing"), ("Corruption", "dot_missing"), ("Siphon Life", "dot_missing"), ("Drain Soul", "execute and dot:Corruption>0"), ("Shadow Bolt", "true")],
    "warlock-demonology": [("Life Tap", "mana<400"), ("Curse of Agony", "dot_missing"), ("Corruption", "dot_missing"), ("Shadow Bolt", "true")],
    "warlock-destruction": [("Life Tap", "mana<400"), ("Immolate", "dot_missing"), ("Conflagrate", "dot:Immolate>0 and dot:Immolate<4"), ("Shadowburn", "execute"), ("Shadow Bolt", "true")],
}
CONSUMABLE_ACTIONS = {"goblin_sapper_charge": "Goblin Sapper Charge", "major_mana_potion": "Major Mana Potion", "mighty_rage_potion": "Mighty Rage Potion", "demonic_rune": "Demonic Rune", "thistle_tea": "Thistle Tea"}

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
    "105939": {"melee_crit": 1}, "105937": {"flag:unbridled_wrath": 0.12}, "105933": {"flag:dw_damage": 0.05, "flag:dw_rage": 0.20, "flag:dw_hit": 2},
    "105931": {"flag:enrage": 0.02}, "105932": {"cost:Execute": -2.5}, "105929": {"hit": 1}, "105927": {"flag:death_wish": 1}, "105928": {"flag:flurry": 0.05}, "105930": {"flag:bloodthirst": 1},
    "105953": {"flag:max_rage": 10},
    # Warrior Protection
    "105976": {"block": 1, "flag:shield_spec_rage": 5}, "105975": {"defense": 4}, "105973": {"stat_pct:armor": 0.02}, "105969": {"dmg_ability:Revenge": 0.20},
    "110856": {"flag:defiance": 0.05}, "105968": {"cost:Sunder Armor": -1}, "105962": {"stat_pct:strength": 0.02, "stat_pct:stamina": 0.02}, "105961": {"flag:focused_rage": 1},
    "105959": {"flag:shield_slam": 1}, "105974": {"flag:improved_bloodrage": 0.25}, "105971": {"flag:master_of_defense": 5},
    # Druid Balance
    "104923": {"cast:Wrath": -0.1, "cost_pct:Wrath": -0.10}, "104924": {"dmg_periodic": 0.01}, "104925": {"cost_pct_all": -0.03}, "104931": {"dmg_ability:Moonfire": 0.05, "crit_ability:Moonfire": 5},
    "104927": {"spell_crit": 2, "melee_crit": 2}, "104929": {"spell_hit": 2, "hit": 2}, "104930": {"flag:insect_swarm": 1}, "104932": {"crit_dmg_school:arcane": 0.20, "crit_dmg_school:nature": 0.20},
    "104933": {"cast:Starfire": -0.1}, "104934": {"flag:natures_grace": 1}, "104936": {"dmg_school:arcane": 0.01, "dmg_school:nature": 0.01}, "104937": {"flag:moonkin": 1}, "104935": {"flag:eclipse": 1},
    # Druid Feral
    "104938": {"cost:Maul": -1, "cost:Swipe": -1, "cost:Claw": -1}, "104939": {"stat_pct:intellect": 0.02, "flag:hotw_cat_str": 0.02, "flag:hotw_bear_sta": 0.04},
    "104940": {"dmg_ability:Swipe": 0.10}, "104943": {"dodge": 2}, "104948": {"dmg_ability:Claw": 0.05, "dmg_ability:Shred": 0.05, "dmg_ability:Maul": 0.05, "dmg_ability:Swipe": 0.05},
    "104946": {"melee_crit": 3}, "104945": {"cost:Shred": -6}, "104952": {"flag:predatory_strikes": 30}, "104947": {"flag:primal_fury": 1},
    "104950": {"crit_dmg_school:physical_ability": 0.10}, "104953": {"flag:rend_and_tear": 0.02}, "104954": {"dodge": 1}, "104942": {"flag:thick_hide": 1},
    # Hunter BM
    "104969": {"flag:pet_damage": 0.03}, "104967": {"flag:pet_crit": 2}, "104962": {"flag:pet_frenzy": 0.2}, "104961": {"flag:bestial_wrath": 1}, "104975": {"dmg_all": 0.01}, "104963": {"flag:pet_focus": 0.10},
    # Hunter MM
    "105011": {"melee_crit": 1, "ranged_crit": 1}, "110870": {"dmg_ability:Serpent Sting": 0.0667}, "105009": {"cost_pct_all": -0.03}, "105008": {"ap_from_int": 0.20},
    "105006": {"cooldown:Arcane Shot": -0.3}, "105007": {"flag:lone_wolf": 0.20}, "105002": {"crit_dmg_school:ranged": 0.06}, "105003": {"dmg_ability:Serpent Sting": 0.02},
    "105001": {"dmg_ability:Multi-Shot": 0.0333, "dmg_ability:Aimed Shot": 0.0333}, "104998": {"dmg_school:ranged": 0.01}, "105004": {},
    # Hunter Survival
    "104996": {"flag:improved_tracking": 0.01}, "104991": {"dmg_ability:Explosive Trap": 0.15}, "104987": {"hit": 1, "ranged_hit": 1}, "104983": {"cost_pct:Explosive Trap": -0.30},
    "110859": {"stat_pct:agility": 0.02},
    # Mage Fire
    "105796": {"crit_ability:Fire Blast": 2, "crit_ability:Scorch": 2}, "105795": {"cast:Fireball": -0.1}, "105794": {"flag:ignite": 0.08}, "105797": {"cooldown:Fire Blast": -1},
    "105788": {"flag:improved_scorch": 1}, "105785": {"flag:master_of_elements": 0.10}, "105784": {"crit_school:fire": 2}, "105782": {"dmg_school:fire": 0.02}, "105781": {"flag:combustion": 1},
    # Mage Frost
    "105779": {"cast:Frostbolt": -0.1}, "105778": {"spell_hit_school:frost": 1, "spell_hit_school:fire": 1}, "105777": {"crit_dmg_school:frost": 0.20}, "105773": {"dmg_school:frost": 0.02},
    "105772": {"cost_pct_school:frost": -0.05}, "105763": {"flag:winters_chill": 1}, "105766": {"flag:cold_snap": 1},
    # Mage Arcane
    "105814": {"spell_hit_school:arcane": 1}, "105810": {"flag:clearcasting": 0.02}, "105807": {"crit_school:arcane": 2}, "105803": {"flag:spirit_while_casting": 0.1667},
    "105801": {"flag:presence_of_mind": 1}, "105800": {"stat_pct:intellect": 0.02, "crit_dmg_school:arcane": 0.20}, "105799": {"dmg_all": 0.01, "spell_crit": 1, "melee_crit": 1}, "105798": {"flag:arcane_power": 1},
    # Priest Shadow
    "110851": {"spell_hit_school:shadow": 1}, "105830": {"flag:swp_ticks": 1}, "105827": {"cooldown:Mind Blast": -0.5}, "105826": {"flag:mind_flay": 1}, "105825": {"dmg_ability:Mind Flay": 0.10},
    "105821": {"flag:shadow_weaving": 0.02}, "105818": {"dmg_school:shadow": 0.02}, "105817": {"flag:shadowform": 1}, "110854": {"flag:early_demise": 15}, "105833": {}, "105831": {"threat_school:shadow": -0.10},
    "105843": {"flag:spirit_while_casting": 0.1667}, "105837": {"stat_pct:intellect": 0.03}, "105853": {"flag:spiritual_guidance": 0.016},
    # Rogue Assassination
    "105722": {"melee_crit": 1}, "105720": {"flag:murder": 0.02}, "105739": {"flag:snd_duration": 0.15}, "105759": {"flag:relentless_strikes": 1}, "105716": {"crit_dmg_builder": 0.06},
    "105714": {"flag:poison_damage": 0.04}, "105715": {"flag:cold_blood": 1}, "105713": {"flag:poison_chance": 0.02}, "105718": {"flag:max_energy": 5}, "105710": {"flag:seal_fate": 0.20}, "105721": {"flag:ruthlessness": 0.20},
    # Rogue Combat
    "105708": {"dmg_ability:Eviscerate": 0.0667}, "105741": {"cost:Sinister Strike": -2.5}, "105719": {"crit_ability:Backstab": 10}, "105737": {"hit": 1},
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
    "104742": {"flag:improved_stormstrike": 1}, "104741": {"flag:maelstrom": 1}, "104740": {"flag:rage_of_the_farseer": 1},
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
TALENT_GATED = {"Mortal Strike": "mortal_strike", "Spearing Strike": "spearing_strike", "Bloodthirst": "bloodthirst", "Death Wish": "death_wish", "Shield Slam": "shield_slam",
                "Insect Swarm": "insect_swarm", "Bestial Wrath": "bestial_wrath", "Combustion": "combustion", "Presence of Mind": "presence_of_mind", "Arcane Power": "arcane_power",
                "Cold Snap": "cold_snap", "Mind Flay": "mind_flay", "Cold Blood": "cold_blood", "Blade Flurry": "blade_flurry", "Adrenaline Rush": "adrenaline_rush",
                "Hemorrhage": "hemorrhage", "Stormstrike": "stormstrike", "Rage of the Farseer": "rage_of_the_farseer", "Siphon Life": "siphon_life", "Conflagrate": "conflagrate",
                "Shadowburn": "shadowburn", "Demonic Sacrifice": "demonic_sacrifice", "Elemental Mastery": "elemental_mastery"}

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
    "druid-feral-dps": {"104938": 5, "104939": 5, "104943": 2, "104940": 3, "104948": 2, "104946": 2, "104945": 3, "104952": 3, "104947": 2, "104950": 2, "104955": 1, "104953": 5,
                        "104923": 5, "104924": 5, "104927": 2, "104929": 2, "104931": 2},
    "druid-feral-tank": {"104938": 5, "104939": 5, "104942": 3, "104940": 3, "104948": 2, "104946": 2, "104952": 3, "104947": 2, "104950": 2, "104955": 1, "104954": 5,
                         "104923": 5, "104924": 5, "104927": 2, "104929": 2, "104931": 2, "104943": 2},
    "hunter-beast-mastery": {"104960": 5, "104976": 5, "104975": 2, "104970": 1, "104969": 5, "104967": 5, "104963": 1, "104964": 1, "104962": 5, "104961": 1,
                             "105011": 5, "110870": 3, "105009": 5, "105008": 5, "105003": 2},
    "hunter-marksmanship": {"105011": 5, "105009": 5, "105008": 5, "110870": 3, "105003": 5, "105002": 5, "104998": 3,
                            "104960": 5, "104976": 5, "104975": 2, "104969": 5, "104967": 3},
    "hunter-survival": {"104996": 5, "104993": 2, "104992": 5, "104991": 2, "104987": 3, "104986": 1, "110861": 5, "104983": 2, "110859": 5, "104994": 1,
                        "105011": 5, "110870": 3, "105009": 5, "105008": 5, "105003": 2},
    "mage-arcane": {"105814": 5, "105813": 5, "105810": 5, "105807": 3, "105803": 3, "105801": 1, "105800": 5, "105799": 3, "105798": 1,
                    "105795": 5, "105796": 3, "105794": 5, "105793": 2, "105790": 1, "105789": 2, "105785": 2},
    "mage-fire": {"105796": 3, "105795": 5, "105794": 5, "105789": 3, "105788": 3, "105785": 3, "105784": 3, "105782": 5, "105781": 1,
                  "105814": 5, "105810": 5, "105812": 2, "105807": 3, "105803": 3, "105813": 2},
    "mage-frost": {"105779": 5, "105778": 5, "105777": 5, "105773": 3, "105772": 3, "105768": 3, "105766": 1, "105763": 5, "105762": 1,
                   "105814": 5, "105810": 5, "105812": 2, "105807": 3, "105803": 3, "105813": 2},
    "priest-shadow": {"110851": 5, "105833": 5, "105831": 3, "105830": 2, "105827": 5, "105826": 1, "105825": 2, "105821": 3, "105820": 1, "105818": 5, "105817": 1, "110854": 2,
                      "105849": 5, "105850": 2, "105846": 3, "105842": 3, "105843": 3},
    "rogue-assassination": {"105722": 5, "105721": 3, "105720": 2, "105739": 3, "105759": 1, "105716": 5, "105715": 1, "105713": 5, "105718": 1, "105710": 5,
                            "105708": 3, "105741": 2, "105719": 3, "105737": 3, "105736": 2, "105738": 2, "105740": 5},
    "rogue-combat": {"105708": 3, "105741": 2, "105719": 3, "105737": 3, "105738": 2, "105736": 2, "105740": 5, "108100": 1, "105728": 1, "105727": 5, "105726": 2, "105730": 1, "105724": 1,
                     "105722": 5, "105721": 3, "105720": 2, "105739": 3, "105759": 1, "105716": 5, "105723": 1},
    "rogue-subtlety": {"105760": 2, "105761": 3, "105756": 1, "105751": 3, "105757": 2, "105749": 1, "105755": 3, "105754": 1, "110868": 1, "105752": 3, "105743": 1, "105745": 2, "105746": 1, "105748": 1, "110867": 5, "110866": 1,
                       "105722": 5, "105721": 3, "105720": 2, "105739": 3, "105759": 1, "105716": 5, "105723": 1},
    "shaman-elemental": {"104773": 5, "104772": 5, "104767": 4, "104770": 3, "104768": 1, "104766": 5, "104762": 1, "104759": 3, "104765": 3, "104758": 1,
                         "104753": 5, "104756": 5, "104755": 3, "104750": 3, "104749": 1, "104747": 3},
    "shaman-enhancement": {"104753": 5, "104756": 5, "104755": 3, "104750": 3, "104749": 1, "104747": 5, "104743": 1, "104744": 2, "104742": 2, "104741": 3, "104740": 1,
                           "104773": 5, "104772": 5, "104767": 5, "104770": 3, "104768": 1, "104766": 1},
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
