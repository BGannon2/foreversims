"""Builds a greedy stat-weight-based BiS gear set for every spec, including both Paladin
specs (which run on the separate Paladin engine but share this item catalog).

Approach (a heuristic greedy optimizer, not a full combinatorial solver):
  1. Filter the item catalog to items the spec's class can actually equip (armor type,
     weapon type) and that are level-60-appropriate (req level >= 50).
  2. Score every item per slot with a stat-weight table for that spec's archetype
     (physical melee dps, physical tank, caster dps, ranged dps).
  3. Pick weapons (2H vs 1H+offhand vs dual-wield vs ranged+melee) by comparing total
     score of each valid configuration.
  4. Greedily pick the top-scoring item per remaining slot (finger/trinket slots pick the
     best 2 distinct items).
  5. Hit-cap correction pass: if the greedily-picked set is under this spec's hit cap
     (computed from this engine's own miss-chance formula, not just folklore numbers),
     swap in the next-best alternative that contributes hit in the least-value-losing
     flexible slots (rings/trinkets/wrists/gloves) until the cap is met or no swaps help.
  6. Tank defense-cap correction pass: same idea, targeting this engine's own crit-immune
     defense threshold (TARGET_DEFENSE + 125 = 440 defense skill).
  7. Writes data/forever_bis_all.json in the same {"profiles": {spec_id: {"gear": [...]}}}
     shape as data/phase12_bis_all.json, and validates every generated set by actually
     running it through forever.all_specs.simulate_spec() and checking for a valid result
     with no unaffordable-cast/validation errors.

Known limitations (flagged, not silently hidden):
  - Class restrictions come from data/item_class_restrictions.json (client AllowableClass,
    built by tools/build_item_class_restrictions.py); on-use stats are scored as not always-on.
  - Set-bonus synergy isn't scored (an item that completes a 4pc bonus isn't weighted any
    higher than one that doesn't) -- this is a pure per-slot stat-weight greedy, not a
    true combinatorial optimizer.
  - Items recorded in data/forever_removed_item_ids.json (gone from Forever) are excluded
    from consideration here, but are NOT deleted from the catalog since older presets still
    reference them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forever.all_specs import ITEMS  # noqa: E402
from forever.engine import permanent_item_stats  # noqa: E402
from forever.engine_data import ITEM_EFFECTS, SPEC_MAP  # noqa: E402
from forever.profile_rules import RACE_FACTIONS  # noqa: E402

_RESTRICTIONS = json.loads((ROOT / "data" / "item_class_restrictions.json").read_text(encoding="utf-8"))
CLASS_RESTRICTIONS = _RESTRICTIONS["items"]
LIMIT_CATEGORY = {int(k): v for k, v in _RESTRICTIONS["limit_categories"].items()}
REMOVED_IDS = set(json.loads((ROOT / "data" / "forever_removed_item_ids.json").read_text(encoding="utf-8"))) \
    if (ROOT / "data" / "forever_removed_item_ids.json").is_file() else set()

ARMOR_ALLOWED = {
    "Warrior": {"Plate", "Mail", "Leather", "Cloth", "Miscellaneous", "Shield"},
    "Hunter": {"Mail", "Leather", "Cloth", "Miscellaneous"},
    "Rogue": {"Leather", "Cloth", "Miscellaneous"},
    "Priest": {"Cloth", "Miscellaneous"},
    "Shaman": {"Mail", "Leather", "Cloth", "Miscellaneous"},
    "Mage": {"Cloth", "Miscellaneous"},
    "Warlock": {"Cloth", "Miscellaneous"},
    "Druid": {"Leather", "Cloth", "Miscellaneous"},
    "Paladin": {"Plate", "Mail", "Leather", "Cloth", "Miscellaneous", "Shield"},
}

WEAPON_ALLOWED = {
    "Warrior": {"Axe", "Dagger", "Fist Weapon", "Mace", "Polearm", "Sword", "Bow", "Gun", "Crossbow", "Thrown", "Wand"},
    "Hunter": {"Axe", "Dagger", "Fist Weapon", "Polearm", "Sword", "Staff", "Bow", "Gun", "Crossbow", "Thrown"},
    "Rogue": {"Axe", "Dagger", "Fist Weapon", "Mace", "Sword", "Bow", "Gun", "Crossbow", "Thrown"},
    "Priest": {"Dagger", "Mace", "Staff", "Wand"},
    "Shaman": {"Axe", "Dagger", "Fist Weapon", "Mace", "Staff"},
    "Mage": {"Dagger", "Sword", "Staff", "Wand"},
    "Warlock": {"Dagger", "Sword", "Staff", "Wand"},
    "Druid": {"Dagger", "Fist Weapon", "Mace", "Staff"},
    "Paladin": {"Axe", "Mace", "Polearm", "Sword"},
}

# Melee weight archetypes. Every weight is per 1 point of the stat (except hit/crit/
# haste/dodge which are per 1%). Hit and defense are handled specially (cap-aware).
MELEE_DPS = {"attackPower": 1.0, "meleeCrit": 2.2, "strength": 1.5, "agility": 1.1,
             "stamina": 0.3, "armor": 0.02, "hitWeight": 2.5}
MELEE_DPS_AGI = {"attackPower": 1.0, "meleeCrit": 2.2, "agility": 1.8, "strength": 0.4,
                  "stamina": 0.3, "armor": 0.02, "hitWeight": 2.5}
CASTER_DPS = {"spellPower": 1.0, "spellCrit": 1.8, "intellect": 0.7, "spirit": 0.2,
              "stamina": 0.25, "mp5": 0.6, "hitWeight": 2.2}
RANGED_DPS = {"attackPower": 0.9, "meleeCrit": 2.0, "agility": 1.3, "stamina": 0.3,
              "armor": 0.01, "hitWeight": 2.3}
TANK = {"defense": 3.0, "stamina": 1.4, "dodge": 1.3, "parry": 1.1, "block": 0.8,
        "blockValue": 0.15, "armor": 0.03, "strength": 0.4, "agility": 0.3}

# Paladin weights come from the Paladin engine itself: finite differences on the Phase 1-2
# presets (1500 iterations, seed 11), normalized to attack power = 1. Protection is TPS per
# point -- spell power (holy threat) is its strongest stat at 3.8x attack power. For survival
# it keeps the shared TANK weights, with the threat weights scaled so strength matches
# TANK's 0.4. Retribution is DPS per point. Hit is handled by the cap pass (8% melee here:
# the Paladin engine starts at 92% melee hit), so it carries no weight.
_PROT_THREAT = {"strength": 2.2, "agility": 1.46, "attackPower": 1.0, "spellPower": 3.81, "holyPower": 3.81,
                "meleeCrit": 31.5, "spellCrit": 2.6, "spellHit": 10.4}
PALADIN_PROT = {**TANK, **{k: round(v * 0.4 / 2.2, 3) for k, v in _PROT_THREAT.items()}}
PALADIN_PROT["agility"] = max(PALADIN_PROT["agility"], TANK["agility"])
PALADIN_RET = {"strength": 2.42, "agility": 1.62, "attackPower": 1.0, "spellPower": 1.46, "holyPower": 1.46,
               "meleeCrit": 29.2, "spellCrit": 2.1, "spellHit": 1.6, "stamina": 0.3, "armor": 0.02}
PALADIN_SPECS = {"paladin-protection": {"class_name": "Paladin", "style": "melee"},
                 "paladin-retribution": {"class_name": "Paladin", "style": "melee"}}
PALADIN_HIT_CAP = 8.0

SPEC_ARCHETYPE = {
    "paladin-protection": PALADIN_PROT, "paladin-retribution": PALADIN_RET,
    "warrior-arms": MELEE_DPS, "warrior-fury": MELEE_DPS, "warrior-protection": TANK,
    "druid-balance": CASTER_DPS, "druid-feral-dps": MELEE_DPS_AGI, "druid-feral-tank": TANK,
    "hunter-beast-mastery": RANGED_DPS, "hunter-marksmanship": RANGED_DPS, "hunter-survival": RANGED_DPS,
    "mage-arcane": CASTER_DPS, "mage-fire": CASTER_DPS, "mage-frost": CASTER_DPS,
    "priest-shadow": CASTER_DPS,
    "rogue-assassination": MELEE_DPS_AGI, "rogue-combat": MELEE_DPS_AGI, "rogue-subtlety": MELEE_DPS_AGI,
    "shaman-elemental": CASTER_DPS, "shaman-enhancement": MELEE_DPS_AGI,
    "warlock-affliction": CASTER_DPS, "warlock-demonology": CASTER_DPS, "warlock-destruction": CASTER_DPS,
}

DUAL_WIELD = {"warrior-fury", "rogue-assassination", "rogue-combat", "rogue-subtlety"}
TWO_HAND_PREFERRED = {"warrior-arms", "paladin-retribution"}  # compared against 1H+offhand anyway; this just breaks ties
SHIELD_TANK = {"warrior-protection", "paladin-protection"}
RANGED_PRIMARY = {"hunter-beast-mastery", "hunter-marksmanship", "hunter-survival"}

CAN_DUAL_WIELD = {"Warrior", "Rogue", "Hunter"}  # the engine's equipment rules reject Shaman off-hand weapons


def off_hand_kind(item):
    if "Shield" in (item["slot"], item.get("subclass")): return "shield"
    return "held" if item["slot"] == "Held In Off-hand" else "weapon"


SLOTS = ["head", "neck", "shoulders", "back", "chest", "wrist", "hands", "waist", "legs", "feet"]

# This engine's own miss-chance formula (forever/engine.py melee_outcome/spell_outcome),
# not generic Classic folklore: TARGET_DEFENSE=315, LEVEL=60 give base 8% melee miss +
# 1% suppression-equivalent = 9% single-wield hit cap; +19% flat for dual wield = 28%;
# ranged uses the same table as single-wield melee = 9%; spell base miss is 17% (83% base
# hit), so 16% spell hit closes it to the 99% ceiling.
HIT_CAP = {"melee": 9.0, "melee_dw": 28.0, "ranged": 9.0, "spell": 16.0}
DEFENSE_CAP = 440.0  # this engine's crit-immune threshold: TARGET_DEFENSE(315) + 125

# Phase restriction: only Onyxia's Lair, the Forever-specific "Barrow Deeps"/"Hyjal Summit"
# zones, and 5-man dungeons are allowed -- not Molten Core, Blackwing Lair, Zul'Gurub, either
# Ahn'Qiraj raid, or Naxxramas (all later-phase raids). wago.tools' DB2 export has no
# spawn/encounter-to-zone table (that data lives server-side, not in client files), so this
# can't be derived programmatically; it's a hardcoded blocklist of each later-phase raid's
# well-documented, unambiguous boss roster. Everything NOT on this list (zone drops, vendor
# items, dungeon bosses, Onyxia, and anything from the Forever-only zones this project has no
# boss-roster data for) is allowed by default.
LATER_PHASE_RAID_BOSSES = {
    # Molten Core
    "Lucifron", "Magmadar", "Gehennas", "Garr", "Baron Geddon", "Shazzrah",
    "Sulfuron Harbinger", "Golemagg the Incinerator", "Majordomo Executus", "Ragnaros",
    # Blackwing Lair
    "Razorgore the Untamed", "Vaelastrasz the Corrupt", "Broodlord Lashlayer", "Firemaw",
    "Ebonroc", "Flamegor", "Chromaggus", "Nefarian",
    # Zul'Gurub
    "High Priestess Jeklik", "High Priest Venoxis", "High Priestess Mar'li", "Bloodlord Mandokir",
    "Wushoolay", "Renataki", "Gri'lek", "Hazza'rah", "High Priest Thekal", "High Priestess Arlokk",
    "Jin'do the Hexxer", "Hakkar", "Gahz'ranka",
    # Ruins of Ahn'Qiraj (AQ20)
    "Kurinnaxx", "General Rajaxx", "Moam", "Buru the Gorger", "Ayamiss the Hunter", "Ossirian the Unscarred",
    # Temple of Ahn'Qiraj (AQ40)
    "The Prophet Skeram", "Battleguard Sartura", "Fankriss the Unyielding", "Princess Huhuran",
    "Emperor Vek'lor", "Emperor Vek'nilash", "C'Thun", "Viscidus", "Princess Yauj", "Lord Kri", "Vem", "Ouro",
    # Naxxramas
    "Anub'Rekhan", "Grand Widow Faerlina", "Maexxna", "Noth the Plaguebringer", "Heigan the Unclean",
    "Loatheb", "Instructor Razuvious", "Gothik the Harvester", "Patchwerk", "Grobbulus", "Gluth",
    "Thaddius", "Sapphiron", "Kel'Thuzad",
}


# Backstop for later-phase QUEST rewards (raid attunement chains, tier-set quest rewards,
# etc.) that don't show up as "Boss Drop: X" and so aren't caught by the blocklist above --
# e.g. Bonescythe (Rogue Tier 3, Naxxramas) and AQ40/BWL attunement rewards are all "Quest:"
# sourced. Real Classic item levels: dungeon epics and Onyxia/Molten Core top out around
# ilvl 77-81; Ahn'Qiraj/Zul'Gurub epics run into the low 80s; Blackwing Lair/Naxxramas start
# at 86+. 82 is a deliberately generous ceiling that keeps Onyxia/MC-tier loot while cutting
# BWL/Naxx and most AQ/ZG epics -- an imperfect proxy (item level, not verified zone data),
# used because no zone/encounter data is available for Forever's exact drop locations.
PHASE1_ITEM_LEVEL_CEILING = 82
# Quest rewards whose quests start from a blocked raid (the boss blocklist only sees boss drops).
LATER_PHASE_QUESTS = {"Rise, Thunderfury!", "The Fall of Ossirian"}


def eligible(item, cls, style, faction=None):
    if item["id"] in REMOVED_IDS or item.get("simulationAvailability") == "excluded":
        return False
    if item.get("source", "").removeprefix("Quest: ") in LATER_PHASE_QUESTS:
        return False
    if cls not in CLASS_RESTRICTIONS.get(str(item["id"]), [cls]):
        return False
    if faction and item.get("faction") not in (None, faction):
        return False
    if item.get("itemLevel", 0) > PHASE1_ITEM_LEVEL_CEILING:
        return False
    source = item.get("source", "")
    if source.startswith("Boss Drop: ") and source[len("Boss Drop: "):] in LATER_PHASE_RAID_BOSSES:
        return False
    if item.get("requiredLevel", 0) and item["requiredLevel"] < 50:
        return False
    if item["quality"] not in ("Uncommon", "Rare", "Epic", "Legendary"):
        return False
    sub = item.get("subclass")
    slot = item["slot"]
    if sub == "Shield" or slot == "Shield":
        return cls in {"Warrior", "Paladin", "Shaman"}
    if slot in ("Two-Hand", "One-Hand", "Main Hand", "Off Hand", "Ranged", "Held In Off-hand"):
        if slot == "Held In Off-hand" or sub == "Off Hand" or sub is None:
            return True  # off-hand held items (tomes, etc.), not true weapons
        if sub not in WEAPON_ALLOWED.get(cls, set()):
            return False
        if slot == "Ranged" and sub not in {"Bow", "Gun", "Crossbow", "Thrown", "Wand"}:
            return False
        return True
    if slot == "Shield":
        return cls in {"Warrior", "Paladin", "Shaman"}
    if sub and sub not in ARMOR_ALLOWED.get(cls, {"Miscellaneous"}) and sub != "Miscellaneous":
        return False
    return True


def score(item, weights):
    stats = permanent_item_stats(item)  # on-use values (Earthstrike's 280 AP) aren't always-on
    total = 0.0
    if item.get("weaponSpeed") and "attackPower" in weights:
        # Weapon damage itself: 1 weapon DPS = 14 attack power (the melee/ranged AP-to-DPS rate).
        dps = (item.get("weaponDamageMin", 0) + item.get("weaponDamageMax", 0)) / 2 / item["weaponSpeed"]
        total += dps * 14 * weights["attackPower"]
    for key, w in weights.items():
        if key == "hitWeight":
            hv = stats.get("meleeHit", 0) + stats.get("spellHit", 0) + stats.get("rangedHit", 0)
            total += hv * w
            continue
        total += stats.get(key, 0) * w
    return total


def limit_taken(item, taken_ids):
    """Another equipped item already uses this item's client limit category (max one)."""
    cat = LIMIT_CATEGORY.get(item["id"])
    return bool(cat) and any(LIMIT_CATEGORY.get(t) == cat for t in taken_ids if t != item["id"])


def best_for_slot(candidates, weights, taken_ids, n=1):
    seen = set()
    picked = []
    for it in sorted(candidates, key=lambda it: score(it, weights), reverse=True):
        if it["id"] in taken_ids or it["id"] in seen or limit_taken(it, taken_ids | seen):
            continue
        seen.add(it["id"])
        picked.append(it)
        if len(picked) >= n:
            break
    return picked


def pick_weapons(items_by_slot, cls, spec_id, weights, taken_ids):
    picks = {}
    if spec_id in RANGED_PRIMARY:
        ranged = best_for_slot(items_by_slot.get("ranged", []), weights, taken_ids)
        if ranged: picks["ranged"] = ranged[0]
        mh = best_for_slot(items_by_slot.get("main_hand", []), weights, taken_ids)
        if mh: picks["main_hand"] = mh[0]
        return picks
    if spec_id in SHIELD_TANK:
        mh = best_for_slot(items_by_slot.get("main_hand", []), weights, taken_ids)
        if mh: picks["main_hand"] = mh[0]
        oh_shield = [it for it in items_by_slot.get("off_hand", []) if "Shield" in (it["slot"], it.get("subclass"))]
        sh = best_for_slot(oh_shield, weights, taken_ids)
        if sh: picks["off_hand"] = sh[0]
        return picks
    if spec_id in DUAL_WIELD:
        mh = best_for_slot(items_by_slot.get("main_hand", []), weights, taken_ids)
        if mh:
            picks["main_hand"] = mh[0]
            taken_ids = taken_ids | {mh[0]["id"]}
        oh = best_for_slot([it for it in items_by_slot.get("off_hand", []) if off_hand_kind(it) == "weapon"], weights, taken_ids)
        if oh: picks["off_hand"] = oh[0]
        return picks
    if SPEC_MAP.get(spec_id, PALADIN_SPECS.get(spec_id, {})).get("style") == "melee":
        # Non-dual-wield melee DPS: two-hander (no shield or caster off-hand).
        two_h = best_for_slot(items_by_slot.get("two_hand", []), weights, taken_ids)
        if two_h: picks["main_hand"] = two_h[0]
        return picks
    # 2H vs 1H+offhand comparison (melee 2H weapon, or caster staff vs wand+offhand-stat-item)
    two_h = best_for_slot(items_by_slot.get("two_hand", []), weights, taken_ids)
    mh = best_for_slot(items_by_slot.get("main_hand", []), weights, taken_ids)
    oh_candidates = items_by_slot.get("off_hand", []) + items_by_slot.get("held_off_hand", [])
    oh = best_for_slot(oh_candidates, weights, (taken_ids | ({mh[0]["id"]} if mh else set())))
    combo_score = (score(mh[0], weights) if mh else 0) + (score(oh[0], weights) if oh else 0)
    twoh_score = score(two_h[0], weights) if two_h else -1
    if two_h and (twoh_score >= combo_score or not mh):
        picks["main_hand"] = two_h[0]  # engine treats 2H as occupying main_hand
    else:
        if mh: picks["main_hand"] = mh[0]
        if oh: picks["off_hand"] = oh[0]
    return picks


def build_spec(spec_id, spec):
    cls, style = spec["class_name"], spec["style"]
    faction = RACE_FACTIONS[default_race(spec_id)]
    weights = dict(SPEC_ARCHETYPE[spec_id])

    by_slot = {s: [] for s in SLOTS}
    by_slot.update({"main_hand": [], "off_hand": [], "two_hand": [], "ranged": [],
                     "held_off_hand": [], "finger": [], "trinket": []})

    for item in ITEMS.values():
        if not eligible(item, cls, style, faction):
            continue
        for eq in item.get("equipSlots", []):
            if eq == "main_hand" and item["slot"] == "Two-Hand":
                by_slot["two_hand"].append(item)
            elif eq == "main_hand":
                by_slot["main_hand"].append(item)
            elif eq == "off_hand" and item["slot"] == "Held In Off-hand":
                by_slot["held_off_hand"].append(item)
            elif eq == "off_hand":
                if off_hand_kind(item) == "weapon" and cls not in CAN_DUAL_WIELD:
                    continue
                by_slot["off_hand"].append(item)
            elif eq == "ranged":
                by_slot["ranged"].append(item)
            elif eq in ("finger1", "finger2"):
                by_slot["finger"].append(item)
            elif eq in ("trinket1", "trinket2"):
                by_slot["trinket"].append(item)
            elif eq in by_slot:
                by_slot[eq].append(item)

    taken_ids = set()
    gear = {}
    weapon_picks = pick_weapons(by_slot, cls, spec_id, weights, taken_ids)
    for slot_key, item in weapon_picks.items():
        gear[slot_key] = item
        taken_ids.add(item["id"])

    for slot in SLOTS:
        picks = best_for_slot(by_slot[slot], weights, taken_ids)
        if picks:
            gear[slot] = picks[0]
            taken_ids.add(picks[0]["id"])

    finger_picks = best_for_slot(by_slot["finger"], weights, taken_ids, n=2)
    for i, item in enumerate(finger_picks):
        gear[f"finger{i+1}"] = item
        taken_ids.add(item["id"])
    trinket_picks = best_for_slot(by_slot["trinket"], weights, taken_ids, n=2)
    for i, item in enumerate(trinket_picks):
        gear[f"trinket{i+1}"] = item
        taken_ids.add(item["id"])
    relic_candidates = by_slot.get("relic", [])
    if relic_candidates:
        rel = best_for_slot(relic_candidates, weights, taken_ids)
        if rel:
            gear["relic"] = rel[0]
            taken_ids.add(rel[0]["id"])

    if cls == "Paladin":
        # Librams carry effects only, which stat weights can't rank; keep the preset's sourced pick.
        relic_id = json.loads((ROOT / "data" / "phase6_bis.json").read_text(encoding="utf-8"))[spec_id.split("-", 1)[1]]["gear"].get("relic")
        if relic_id in ITEMS:
            gear["relic"] = ITEMS[relic_id]

    def pool_key_for(slot_name):
        if slot_name.startswith("finger"): return "finger"
        if slot_name.startswith("trinket"): return "trinket"
        if slot_name == "main_hand" and gear[slot_name]["slot"] == "Two-Hand": return "two_hand"
        return slot_name

    def cap_correction_pass(stat_key, cap_value, max_iters, base=0.0):
        for _ in range(max_iters):
            total = base + sum(gear[s]["stats"].get(stat_key, 0) for s in gear)
            if total >= cap_value:
                break
            improved = False
            for slot_name in list(gear.keys()):
                pool = by_slot.get(pool_key_for(slot_name), [])
                current = gear[slot_name]
                alt_pool = sorted(
                    [it for it in pool if it["id"] not in taken_ids and not limit_taken(it, taken_ids - {current["id"]})
                     and it["stats"].get(stat_key, 0) > current["stats"].get(stat_key, 0)
                     and (slot_name != "off_hand" or off_hand_kind(it) == off_hand_kind(current))],
                    key=lambda it: (it["stats"].get(stat_key, 0), score(it, weights)), reverse=True)
                if alt_pool:
                    taken_ids.discard(current["id"])
                    taken_ids.add(alt_pool[0]["id"])
                    gear[slot_name] = alt_pool[0]
                    improved = True
                    break
            if not improved:
                break

    # --- hit-cap correction pass ---
    dw = spec_id in DUAL_WIELD
    cap = HIT_CAP["spell"] if style == "spell" else HIT_CAP["ranged"] if style == "ranged" else \
        (HIT_CAP["melee_dw"] if dw else PALADIN_HIT_CAP if cls == "Paladin" else HIT_CAP["melee"])
    hit_key = "spellHit" if style == "spell" else ("rangedHit" if style == "ranged" else "meleeHit")
    cap_correction_pass(hit_key, cap, 40)

    # --- tank defense-cap correction pass ---
    # Only chased for warrior-protection: get as close as the itemization pool allows,
    # even if it can't fully close the gap. Skipped for druid-feral-tank (Bear Form
    # itemization doesn't carry enough Defense Rating to make chasing this meaningful).
    if spec_id == "warrior-protection":
        cap_correction_pass("defense", DEFENSE_CAP, 30, base=300.0)

    sim_pass(spec_id, spec, gear, by_slot, weights, taken_ids)

    gear_list = []
    for slot_name, item in gear.items():
        row = {k: item.get(k) for k in ("id", "name", "icon", "quality", "itemLevel", "stats", "effects",
                                          "source", "subclass", "weaponDamageMin", "weaponDamageMax",
                                          "weaponSpeed", "equipSlots", "set")}
        row["slot"] = item["slot"]
        row["gear_slot"] = slot_name
        gear_list.append(row)
    return gear_list


def default_race(spec_id):
    """The race each spec's set is built for (its first listed race; Paladin presets are Human)."""
    if spec_id in PALADIN_SPECS:
        return "Human"
    from forever.all_specs import public_specs
    return next(x for x in public_specs() if x["id"] == spec_id)["races"][0]


TANK_SPECS = {"warrior-protection", "druid-feral-tank", "paladin-protection"}
UI_SLOT = {"head": "Head", "neck": "Neck", "shoulders": "Shoulders", "back": "Back", "chest": "Chest", "wrist": "Wrist",
           "hands": "Hands", "waist": "Waist", "legs": "Legs", "feet": "Feet", "finger1": "Finger 1", "finger2": "Finger 2",
           "trinket1": "Trinket 1", "trinket2": "Trinket 2", "main_hand": "Main Hand", "off_hand": "Off Hand",
           "ranged": "Ranged / Relic", "relic": "Ranged / Relic"}
SCORE_CANDIDATES = 4


def sim_value(spec_id, spec, gear):
    """Mean DPS (TPS for tanks) of a gear set in the engine that runs this spec."""
    key = "tps" if spec_id in TANK_SPECS else "dps"
    if spec["class_name"] == "Paladin":
        from forever import gear_data, sim
        name = spec_id.split("-", 1)[1]
        p = sim.preset(name); p.update(iterations=150, seed=7)
        p["enchants"] = gear_data.paladin_enchants(name)
        p["gear"] = gear_data.empty_gear(); p["gear"].update({slot: it["id"] for slot, it in gear.items()})
        return sim.simulate(sim.validate(p))["metrics"][key]["mean"]
    from forever.all_specs import public_specs, simulate_spec
    from server import default_request
    full = next(x for x in public_specs() if x["id"] == spec_id)
    req = default_request(full, default_race(spec_id), iterations=60, duration=120, seed=7)
    req["gear_slots"] = [{"slot": UI_SLOT[slot], "id": it["id"]} for slot, it in gear.items()]
    req["gear"] = [row["id"] for row in req["gear_slots"]]
    return simulate_spec(req)["metrics"][key]["mean"]


def has_effect(item):
    """True if the item has an on-use, proc or other triggered effect the engines might model."""
    override = ITEM_EFFECTS.get(item["id"], {})
    for text in item.get("effects", []):
        kind = text.split(":", 1)[0]
        if kind in override:
            if override[kind]:
                return True
        elif kind in ("Use", "Chance on hit") or (kind == "Equip" and ("chance" in text.lower() or "extra attack" in text.lower())):
            return True
    return False


def sim_pass(spec_id, spec, gear, by_slot, weights, taken_ids):
    """Stat weights can't see weapon speed or value procs and on-use effects (Hand of Justice has
    no stats at all), so the sim chooses, slot by slot, among the current pick, the next few by
    score and every item with a triggered effect. Weapons are skipped for casters (stat sticks)."""
    slots = ([] if spec["style"] == "spell" else ["ranged" if spec_id in RANGED_PRIMARY else "main_hand"])
    if spec_id in DUAL_WIELD or spec_id in SHIELD_TANK:
        slots.append("off_hand")
    slots += ["trinket1", "trinket2", "finger1", "finger2"] + SLOTS
    for slot in slots:
        current = gear.get(slot)
        if not current:
            continue
        pool_key = "two_hand" if current["slot"] == "Two-Hand" else "trinket" if slot.startswith("trinket") \
            else "finger" if slot.startswith("finger") else slot
        pool = [it for it in by_slot.get(pool_key, [])
                if slot != "off_hand" or off_hand_kind(it) == off_hand_kind(current)]
        others = taken_ids - {current["id"]}
        free = [it for it in pool if it["id"] not in taken_ids and not limit_taken(it, others)]
        effects = [it for it in free if has_effect(it)]
        if not effects and slot not in ("main_hand", "ranged"):
            continue
        ranked = sorted(free, key=lambda it: score(it, weights), reverse=True)[:SCORE_CANDIDATES]
        candidates = [current] + [it for it in {it["id"]: it for it in ranked + effects}.values()]
        best, best_value = current, None
        for it in candidates:
            gear[slot] = it
            try:
                value = sim_value(spec_id, spec, gear)
            except ValueError:  # the engine's equipment rules refuse this item for the class
                continue
            if best_value is None or value > best_value:
                best, best_value = it, value
        gear[slot] = best
        taken_ids.discard(current["id"]); taken_ids.add(best["id"])


def main():
    profiles = {}
    for spec_id, spec in {**SPEC_MAP, **PALADIN_SPECS}.items():
        gear = build_spec(spec_id, spec)
        profiles[spec_id] = {
            "source": "tools/build_bis_gearsets.py (greedy stat-weight optimizer over the Forever item catalog)",
            "source_label": f"Forever BiS (auto-generated, {RACE_FACTIONS[default_race(spec_id)]})",
            "race": default_race(spec_id),
            "gear": gear,
        }
        print(f"{spec_id}: {len(gear)} slots filled", file=sys.stderr)

    out = {"scope": "Forever level-60 auto-generated BiS, greedy stat-weight optimizer", "profiles": profiles}
    (ROOT / "data" / "forever_bis_all.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote data/forever_bis_all.json", file=sys.stderr)


if __name__ == "__main__":
    main()
