"""Shared equipment eligibility and default enchant choices for profiles and the UI.

Missing level/availability metadata is not evidence that an item cannot be used.
Classic baseline items remain selectable; explicit test and encounter-only items do not.
"""
from __future__ import annotations

import re

SLOTS = {
    "Head": ["head"], "Neck": ["neck"], "Shoulders": ["shoulders"], "Back": ["back"],
    "Chest": ["chest"], "Wrist": ["wrist"], "Hands": ["hands"], "Waist": ["waist"],
    "Legs": ["legs"], "Feet": ["feet"], "Finger 1": ["finger1", "finger2"],
    "Finger 2": ["finger1", "finger2"], "Trinket 1": ["trinket1", "trinket2"],
    "Trinket 2": ["trinket1", "trinket2"], "Main Hand": ["main_hand"],
    "Off Hand": ["off_hand"], "Ranged / Relic": ["ranged", "relic"],
}
ENCHANT_SLOTS = {k: v[0] for k, v in SLOTS.items() if k not in {"Neck", "Waist", "Finger 1", "Finger 2", "Trinket 1", "Trinket 2"}}
ARMOR_ORDER = ["Cloth", "Leather", "Mail", "Plate"]
ARMOR_MAX = {"Warrior": 3, "Paladin": 3, "Hunter": 2, "Shaman": 2, "Rogue": 1, "Druid": 1, "Mage": 0, "Priest": 0, "Warlock": 0}
CLASS_WEAPONS = {
    "Warrior": ["Axe", "Bow", "Crossbow", "Dagger", "Fist Weapon", "Gun", "Mace", "Polearm", "Shield", "Staff", "Sword", "Thrown"],
    "Paladin": ["Axe", "Mace", "Polearm", "Shield", "Sword", "Libram"],
    "Druid": ["Dagger", "Mace", "Staff", "Fist Weapon", "Idol", "Off Hand"],
    "Hunter": ["Axe", "Bow", "Crossbow", "Dagger", "Fist Weapon", "Gun", "Polearm", "Staff", "Sword", "Thrown"],
    "Mage": ["Dagger", "Staff", "Sword", "Wand", "Off Hand"],
    "Priest": ["Dagger", "Mace", "Staff", "Wand", "Off Hand"],
    "Rogue": ["Bow", "Crossbow", "Dagger", "Fist Weapon", "Gun", "Mace", "Sword", "Thrown"],
    "Shaman": ["Axe", "Dagger", "Fist Weapon", "Mace", "Shield", "Staff", "Totem", "Off Hand"],
    "Warlock": ["Dagger", "Staff", "Sword", "Wand", "Off Hand"],
}
MELEE_WEAPONS = ["Axe", "Dagger", "Fist Weapon", "Mace", "Polearm", "Staff", "Sword"]
WEAPON_KINDS = MELEE_WEAPONS + ["Bow", "Crossbow", "Gun", "Shield", "Wand", "Thrown", "Idol", "Totem", "Libram", "Off Hand"]
DUAL_WIELD_CLASSES = ["Warrior", "Rogue", "Hunter"]
NON_PLAYER_ITEM_IDS = {22736: "Andonisus is an encounter-only weapon, not persistent raid equipment."}
TEST_NAME_PATTERN = r"\b(?:UNUSED|PH|TEST|PLACEHOLDER|DEPRECATED|DEP)\b|^\d+\s+(?:Epic|Rare|Green)\s+"


def equipment_rules():
    return {"slots": SLOTS, "enchant_slots": ENCHANT_SLOTS, "armor_order": ARMOR_ORDER,
            "armor_max": ARMOR_MAX, "class_weapons": CLASS_WEAPONS, "weapon_kinds": WEAPON_KINDS,
            "melee_weapons": MELEE_WEAPONS, "dual_wield_classes": DUAL_WIELD_CLASSES}


def classify_availability(item, absent_ids):
    """A diff snapshot's missing ID is uncertain, not a confirmed removal."""
    item.pop("removedFromForever", None)
    if item["id"] in NON_PLAYER_ITEM_IDS or re.search(TEST_NAME_PATTERN, item.get("name", ""), re.I):
        item["simulationAvailability"] = "excluded"
        item["availabilityNote"] = NON_PLAYER_ITEM_IDS.get(item["id"], "Test or placeholder item; unavailable as normal player equipment.")
    elif item["id"] in absent_ids:
        item["simulationAvailability"] = "unknown"
        item["availabilityNote"] = "Classic baseline item absent from the current Forever snapshot. Availability is unconfirmed; absence alone does not prove removal."
    elif str(item.get("source", "")).startswith("forever-"):
        item["simulationAvailability"] = "datamined"
        item["availabilityNote"] = "Present in Forever client data; acquisition and final tuning remain unconfirmed."
    else:
        item["simulationAvailability"] = "classic-baseline"
        item["availabilityNote"] = "Classic baseline item; Forever availability and tuning are not independently confirmed."


def annotate_rating_assumptions(item):
    """Preserve raw ratings so unsupported conversions cannot silently disappear."""
    # Some Classic tooltips use short labels instead of full Equip sentences.
    for effect in item.get('effects', []):
        match = re.fullmatch(r'Equip: \+(\d+) (Mana Regeneration|(?:Shadow|Fire|Frost|Arcane|Nature|Holy) Spell Damage)', effect)
        if match:
            label = match.group(2)
            key = 'mp5' if label == 'Mana Regeneration' else label.split()[0].lower() + 'Power'
            item.setdefault('stats', {}).setdefault(key, float(match.group(1)))
    for row in item.get('tooltip', []):
        text = str(row.get('label', ''))
        if not re.search(r'\b(?:Haste|Expertise|Critical Strike|Hit|Defense|Dodge) Rating\b', text, re.I):
            continue
        if re.search(r'\b(?:Haste|Expertise) Rating\b', text, re.I):
            effect = 'Unmodeled rating: ' + text
            if effect not in item.setdefault('effects', []): item['effects'].append(effect)
        else:
            note = 'Provisional level-60 Classic rating conversion; Forever conversion unconfirmed: ' + text
            if note not in item.setdefault('modelNotes', []): item['modelNotes'].append(note)


def weapon_kind(item):
    return next((k for k in WEAPON_KINDS if k in str(item.get("subclass", ""))), None)


def item_allowed(item, slot, class_name):
    if not item.get("id") or item.get("simulationAvailability") == "excluded":
        return False
    if not set(item.get("equipSlots", [])).intersection(SLOTS.get(slot, [])):
        return False
    if (item.get("requiredLevel") or 0) > 60:
        return False
    armor = item.get("subclass")
    if armor in ARMOR_ORDER and ARMOR_ORDER.index(armor) > ARMOR_MAX[class_name]:
        return False
    allowed = item.get("allowedClasses")
    if allowed and class_name not in allowed:
        return False
    for line in item.get("tooltip", []):
        label = str(line.get("label", ""))
        if label.startswith("Classes:") and class_name not in [x.strip() for x in label.split(":", 1)[1].split(",")]:
            return False
    kind = weapon_kind(item)
    if kind and kind not in CLASS_WEAPONS[class_name]:
        return False
    if slot == "Main Hand" and kind not in MELEE_WEAPONS:
        return False
    if slot == "Off Hand" and kind in MELEE_WEAPONS:
        return class_name in DUAL_WIELD_CLASSES and item.get("slot") != "Two-Hand"
    return True


def enchant_preferences(spec):
    """Per-slot defaults, with school damage enchants only for matching specs."""
    caster = spec["style"] == "spell"
    agility = spec["class_name"] in {"Rogue", "Hunter", "Druid"} and not caster
    out = {"head": ["focus" if caster else "voracity"], "legs": ["focus" if caster else "voracity"],
           "back": ["cloak_resist" if caster else "cloak_agi"], "chest": ["greater_stats"],
           "wrist": ["greater_intellect" if caster else "superior_strength"],
           "hands": [] if caster else ["greater_agility" if agility else "greater_strength"],
           "feet": ["greater_stamina" if caster else "greater_agility"],
           "main_hand": ["spell_power" if caster else "agility_15" if agility else "crusader"],
           "off_hand": ["spell_power" if caster else "agility_15" if agility else "crusader"],
           "ranged": ["biznicks_scope"]}
    school = {"mage-fire": "fire", "mage-frost": "frost", "priest-shadow": "shadow",
              "warlock-affliction": "shadow", "warlock-demonology": "shadow", "warlock-destruction": "fire"}.get(spec["id"])
    if school:
        out["hands"] = [f"{school}_power"]
    return out


def default_enchants(spec, gear, items, enchants):
    preferences = enchant_preferences(spec)
    selected = []
    for row in gear:
        item = items.get(row["id"], {})
        slot = ENCHANT_SLOTS.get(row["slot"])
        if not item or not slot:
            continue
        kind = weapon_kind(item)
        if slot == "ranged" and kind != "Gun":
            continue
        if slot in {"main_hand", "off_hand"} and kind not in MELEE_WEAPONS:
            continue
        available = {e["id"] for e in enchants.get(slot, [])}
        choice = next((eid for eid in preferences.get(slot, []) if eid in available), None)
        if choice:
            selected.append({"slot": slot, "id": choice})
    return selected
