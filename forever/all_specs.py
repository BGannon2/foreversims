"""Public API for the shared Forever DPS/tank engine (all non-Paladin specs).

The simulation lives in engine.py; sourced data in engine_data.py.  This module
loads the item catalog, enchants and set data, and exposes the functions used
by server.py, tools/generate_benchmarks.py, tools/validation_matrix.py and the tests.
"""
from __future__ import annotations
import json
from pathlib import Path

from . import engine
from .engine_data import CLASS_RACES, CREATURE_TYPES, SPEC_MAP, ROTATIONS, DEFAULT_BUILDS, ABILITIES, TALENT_EFFECTS, default_consumables, default_buffs, RACIALS, BLOODLUST_DURATION, SPEC_ABOUT

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCE = "https://www.wowhead.com/forever/"


def _load_items():
    items = {x["id"]: x for x in json.loads((DATA_DIR / "classic_era_items.json").read_text(encoding="utf-8"))["items"]}
    extra_path = DATA_DIR / "extra_items.json"
    if extra_path.is_file():
        for x in json.loads(extra_path.read_text(encoding="utf-8"))["items"]:
            items.setdefault(x["id"], x)
    for profile in json.loads((DATA_DIR / "phase12_bis_all.json").read_text(encoding="utf-8"))["profiles"].values():
        for row in profile["gear"]:
            if not row.get("id"): continue
            item = items.setdefault(row["id"], dict(row))
            if row.get("slot") == "Ranged / Relic":
                token = (row.get("name", "") + " " + row.get("icon", "")).lower()
                subclass = "Gun" if "gun" in token else "Bow" if "bow" in token else "Wand" if "wand" in token or "touch" in token else item.get("subclass")
                item.setdefault("subclass", subclass); item.setdefault("equipSlots", ["ranged"])
    # Items absent or incomplete in the Wowhead-derived catalog; WoWSims database values.
    items[14551] = {**items.get(14551, {}), "id": 14551, "name": "Edgemaster's Handguards", "slot": "Hands", "stats": {"armor": 201}, "effects": ["Increased Axes, Daggers, and Swords +7."]}
    items[13965] = {**items.get(13965, {}), "id": 13965, "name": "Blackhand's Breadth", "slot": "Trinket", "stats": {"meleeCrit": 2}, "effects": []}
    items[17069] = {**items.get(17069, {}), "id": 17069, "name": "Striker's Mark", "slot": "Ranged", "subclass": "Bow", "equipSlots": ["ranged"], "stats": {"attackPower": 22, "meleeHit": 1}, "effects": [], "weaponDamageMin": 69, "weaponDamageMax": 129, "weaponSpeed": 2.5}
    return items


ITEMS = _load_items()
ENCHANTS = json.loads((DATA_DIR / "enchants.json").read_text(encoding="utf-8"))["slots"]
FOREVER_SETS = json.loads((DATA_DIR / "forever_set_bonuses.json").read_text(encoding="utf-8"))["sets"]


def public_specs():
    out = []
    for spec in SPEC_MAP.values():
        out.append(dict(spec, actions=[n for n, _ in ROTATIONS[spec["id"]]], opener=("Taunt" if spec["role"] == "tank" else None),
                        races=CLASS_RACES[spec["class_name"]], default_talents=DEFAULT_BUILDS[spec["id"]],
                        default_consumables=default_consumables(spec), default_buffs=default_buffs(spec),
                        about=SPEC_ABOUT.get(spec["id"], {})))
    return out


def public_racials():
    return {race: data.get("summary") for race, data in RACIALS.items()}


def simulate_spec(request):
    if not isinstance(request, dict):
        raise ValueError("Choose a supported Forever DPS or tank spec.")
    return engine.simulate(request, ITEMS, ENCHANTS, FOREVER_SETS)


def enchant_compatible(slot, gear, gear_slots):
    return engine.enchant_compatible(slot, gear, gear_slots, ITEMS)


def equipped_item(request, gear, ui_slot):
    cfg_slots = request.get("gear_slots", [])
    for row in cfg_slots:
        if isinstance(row, dict) and row.get("slot") == ui_slot and str(row.get("id", "")).isdigit():
            return ITEMS.get(int(row["id"]), {})
    wanted = {"Main Hand": {"main_hand"}, "Off Hand": {"off_hand"}, "Ranged / Relic": {"ranged"}}.get(ui_slot, set())
    candidates = [x for x in gear if wanted.intersection(x.get("equipSlots", []))]
    if ui_slot == "Off Hand": return candidates[1] if len(candidates) > 1 else {}
    return candidates[0] if candidates else {}
