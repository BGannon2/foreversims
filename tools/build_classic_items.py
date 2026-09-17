"""Build a compact level-60 Classic Era gear catalog from wow-classic-items.

Input project: https://github.com/nexus-devs/wow-classic-items (MIT)
This is a development-time tool. The browser/server read the generated JSON only.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

SLOTS = {
    "Head": ["head"], "Neck": ["neck"], "Shoulder": ["shoulders"], "Back": ["back"],
    "Chest": ["chest"], "Wrist": ["wrist"], "Hands": ["hands"], "Waist": ["waist"],
    "Legs": ["legs"], "Feet": ["feet"], "Finger": ["finger1", "finger2"],
    "Trinket": ["trinket1", "trinket2"], "One-Hand": ["main_hand"],
    "Main Hand": ["main_hand"], "Two-Hand": ["main_hand"], "Off Hand": ["off_hand"],
    "Held In Off-hand": ["off_hand"], "Relic": ["relic"],
}
WEAPONS = {"Axe", "Mace", "Sword", "Polearm", "Shield", "Libram", "Miscellaneous"}
BIS_QUEST_REWARDS = {18404, 21180}
BASE_STATS = {
    "Strength":"strength", "Agility":"agility", "Stamina":"stamina", "Intellect":"intellect",
    "Spirit":"spirit", "Armor":"armor", "Health":"health", "Mana":"mana",
    "Fire Resistance":"fireResistance", "Frost Resistance":"frostResistance",
    "Nature Resistance":"natureResistance", "Shadow Resistance":"shadowResistance",
    "Arcane Resistance":"arcaneResistance",
}

def number(pattern, text):
    match = re.search(pattern, text, re.I)
    return float(match.group(1)) if match else None

def parse_item(item):
    if item.get("slot") not in SLOTS or not (45 <= item.get("requiredLevel", 0) <= 60 or item.get("itemId") in BIS_QUEST_REWARDS):
        return None
    if item.get("quality") not in {"Rare", "Epic", "Legendary"}:
        return None
    if item.get("class") == "Weapon" and item.get("subclass") not in WEAPONS:
        return None
    stats = {}
    damage_min = damage_max = speed = None
    effects = []
    tooltip = []
    set_data = None
    rows = item.get("tooltip", [])
    labels = [re.sub(r"\s+", " ", row.get("label", "")).strip() for row in rows]
    for index, row in enumerate(rows):
        label = re.sub(r"\s+", " ", row.get("label", "")).strip()
        if label:
            tooltip.append({"label": label, "format": row.get("format", "")})
        set_match = re.fullmatch(r"(.+) \((\d+)/(\d+)\)", label)
        if set_match and int(set_match.group(3)) >= 2:
            pieces, bonuses = [], []
            for following in labels[index + 1:]:
                bonus = re.fullmatch(r"\((\d+)\) Set\s*:\s*(.+)", following)
                if bonus:
                    bonuses.append({"required": int(bonus.group(1)), "description": bonus.group(2)})
                elif bonuses:
                    break
                elif following and not following.startswith(("Equip:", "Use:", "Chance on hit:")):
                    pieces.append(following)
                else:
                    break
            set_data = {"name": set_match.group(1), "pieces": pieces[:int(set_match.group(3))], "bonuses": bonuses}
        match = re.fullmatch(r"\+(\d+) (.+)", label)
        if match and match.group(2) in BASE_STATS:
            stats[BASE_STATS[match.group(2)]] = stats.get(BASE_STATS[match.group(2)], 0) + float(match.group(1))
        match = re.fullmatch(r"(\d+) Armor", label)
        if match: stats["armor"] = stats.get("armor", 0) + float(match.group(1))
        match = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?) Damage", label)
        if match: damage_min, damage_max = map(float, match.groups())
        match = re.search(r"Speed\s+(\d+(?:\.\d+)?)", label)
        if match: speed = float(match.group(1))
        if label.startswith(("Equip:", "Chance on hit:", "Use:")):
            effects.append(label)
            mappings = [
                (r"(?:attack power|Attack Power) by (\d+)", "attackPower"),
                (r"damage and healing done by magical spells and effects by up to (\d+)", "spellPower"),
                (r"healing done by spells and effects by up to (\d+)", "healingPower"),
                (r"damage done by Holy spells and effects by up to (\d+)", "holyPower"),
                (r"chance to hit with spells by (\d+(?:\.\d+)?)%", "spellHit"),
                (r"chance to get a critical strike with spells by (\d+(?:\.\d+)?)%", "spellCrit"),
                (r"chance to hit by (\d+(?:\.\d+)?)%", "meleeHit"),
                (r"chance to get a critical strike by (\d+(?:\.\d+)?)%", "meleeCrit"),
                (r"chance to block attacks with a shield by (\d+(?:\.\d+)?)%", "block"),
                (r"value of your shield block by (\d+)", "blockValue"),
                (r"Defense skill by (\d+)", "defense"),
                (r"restores (\d+) mana per 5 sec", "mp5"),
                (r"chance to dodge an attack by (\d+(?:\.\d+)?)%", "dodge"),
                (r"chance to parry an attack by (\d+(?:\.\d+)?)%", "parry"),
            ]
            for pattern, key in mappings:
                value = number(pattern, label)
                if value is not None: stats[key] = stats.get(key, 0) + value
    source = item.get("source") or {}
    source_name = source.get("category", "Unknown")
    if source.get("name"):
        source_name += ": " + source["name"]
    for key in ("quests", "creatures", "objects"):
        if source.get(key): source_name += ": " + source[key][0].get("name", "Unknown")
    return {
        "id": item["itemId"], "name": item["name"], "icon": item.get("icon"),
        "quality": item["quality"], "itemLevel": item.get("itemLevel", 0),
        "requiredLevel": item.get("requiredLevel", 0), "slot": item["slot"],
        "equipSlots": SLOTS[item["slot"]], "subclass": item.get("subclass"),
        "stats": stats, "weaponDamageMin": damage_min, "weaponDamageMax": damage_max,
        "weaponSpeed": speed, "effects": effects, "tooltip": tooltip, "set": set_data, "source": source_name,
        "wowhead": f"https://www.wowhead.com/classic/item={item['itemId']}",
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("output", type=Path)
    parser.add_argument("--git-repo", type=Path)
    parser.add_argument("--commit")
    args = parser.parse_args()
    if args.git_repo and args.commit:
        blob = subprocess.check_output(["git", "-C", str(args.git_repo), "show", f"{args.commit}:data/json/data.json"])
        raw = json.loads(blob)
        version = f"wow-classic-items-{args.commit[:12]}-2021-04-30"
    elif args.source:
        raw = json.loads(args.source.read_text(encoding="utf-8-sig"))
        version = "wow-classic-items-file-import"
    else:
        parser.error("provide a source file or --git-repo and --commit")
    items = [parsed for item in raw if (parsed := parse_item(item))]
    items.sort(key=lambda x: (x["equipSlots"][0], -x["itemLevel"], x["name"]))
    payload = {
        "version": version,
        "source": "https://github.com/nexus-devs/wow-classic-items",
        "license": "MIT",
        "scope": "Pre-TBC Classic snapshot; Rare, Epic, and Legendary equippable Paladin-compatible item types requiring level 45-60, plus two max-level Phase 6 BiS quest rewards whose records omit requiredLevel.",
        "items": items,
    }
    args.output.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(items)} items to {args.output}")

if __name__ == "__main__": main()
