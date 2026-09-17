"""Export the simulator's data tables and API payloads as static JSON.

Two consumers:
* ``engine-rs/data/*.json`` - embedded into the Rust/WebAssembly engine at
  compile time, so Python stays the single source of truth for every table.
* ``web/data/*.json`` - the former ``/api/*`` responses, served as static
  files so the site can be hosted on a CDN with no simulation server.

Run from the project root:  python tools/export_static_data.py
"""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import engine_data as ed  # noqa: E402
import engine  # noqa: E402
import sim  # noqa: E402
import gear_data  # noqa: E402
import all_specs  # noqa: E402
import server  # noqa: E402

WEB_DATA = ROOT / "web" / "data"
RS_DATA = ROOT / "engine-rs" / "data"


def dump(path: Path, value, compact=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, separators=(",", ":") if compact else None, indent=None if compact else 1, allow_nan=False, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)} ({len(text.encode('utf-8')):,} bytes)")


def engine_tables():
    stance = {("none" if k is None else k): v for k, v in ed.STANCE_MODS.items()}
    return {
        "CLASS_RACES": ed.CLASS_RACES, "CREATURE_TYPES": sorted(ed.CREATURE_TYPES), "RACE_STATS": ed.RACE_STATS, "CLASS_BASE": ed.CLASS_BASE,
        "AP_PER_STRENGTH": ed.AP_PER_STRENGTH, "AP_PER_AGILITY": ed.AP_PER_AGILITY, "MELEE_CRIT_PER_AGI": ed.MELEE_CRIT_PER_AGI,
        "SPELL_CRIT_PER_INT": ed.SPELL_CRIT_PER_INT, "DODGE_PER_AGI": ed.DODGE_PER_AGI, "SPIRIT_REGEN": ed.SPIRIT_REGEN,
        "RAGE_CONVERSION_60": ed.RAGE_CONVERSION_60, "LEVEL": ed.LEVEL, "TARGET_LEVEL": ed.TARGET_LEVEL, "TARGET_DEFENSE": ed.TARGET_DEFENSE,
        "BLOODLUST_DURATION": ed.BLOODLUST_DURATION, "BLOODLUST_HASTE": ed.BLOODLUST_HASTE, "GCD": ed.GCD, "ENERGY_GCD": ed.ENERGY_GCD,
        "RACIALS": ed.RACIALS, "BUFF_STATS": ed.BUFF_STATS, "BUFF_GROUPS": ed.BUFF_GROUPS, "WINDFURY_TOTEM": ed.WINDFURY_TOTEM,
        "DEBUFF_ARMOR": ed.DEBUFF_ARMOR, "CONSUME_STATS": ed.CONSUME_STATS, "SPEC_MAP": ed.SPEC_MAP, "STANCE_MODS": stance, "CLASS_THREAT": ed.CLASS_THREAT,
        "ABILITIES": ed.ABILITIES, "ROTATIONS": ed.ROTATIONS, "CONSUMABLE_ACTIONS": ed.CONSUMABLE_ACTIONS, "TALENT_EFFECTS": ed.TALENT_EFFECTS,
        "TALENT_GATED": ed.TALENT_GATED, "DEFAULT_BUILDS": ed.DEFAULT_BUILDS, "PET_FAMILIES": ed.PET_FAMILIES, "PET_ABILITIES": ed.PET_ABILITIES,
        "PET_FOCUS_PER_SEC": ed.PET_FOCUS_PER_SEC, "WARLOCK_PETS": ed.WARLOCK_PETS, "POISONS": ed.POISONS, "WINDFURY": ed.WINDFURY,
        "ITEM_PROC_PPM": {str(k): v for k, v in ed.ITEM_PROC_PPM.items()}, "CONSUMABLE_GROUPS": sim.CONSUMABLE_GROUPS,
        "SET_EFFECTS": ed.SET_EFFECTS, "SET_NO_COMBAT_EFFECT": sorted(ed.SET_NO_COMBAT_EFFECT), "SET_PROVISIONAL": ed.SET_PROVISIONAL,
    }


def paladin_tables():
    talents = {tid: {"name": t["name"], "row": t["row"], "ranks": len(t["ranks"]), "requires": [{"id": str(r["id"]), "qty": r["qty"]} for r in t["requires"]]} for tid, t in sim.TALENTS.items()}
    return {
        "facts": sim.F, "version": sim.DATA["version"], "sources": sim.DATA["sources"], "status": sim.DATA["status"], "excluded": sim.DATA["excluded"],
        "data_sha256": hashlib.sha256((ROOT / "data.json").read_bytes()).hexdigest(), "assumptions": sim.ASSUMPTIONS,
        "talents": talents, "tree_talents": sim.TREE_TALENTS, "points_per_tier": sim.TALENT_DATA["points_per_tier"], "max_points": sim.TALENT_DATA["max_points"],
        "protection_build": sim.PROTECTION_BUILD, "retribution_build": sim.RETRIBUTION_BUILD, "consumable_groups": sim.CONSUMABLE_GROUPS,
        "phase6_gear": {spec: gear_data.phase6_gear(spec) for spec in ("protection", "retribution")}, "gear_slots": list(gear_data.GEAR_SLOTS),
        "catalog": {key: gear_data.CATALOG[key] for key in ("version", "source", "scope")}, "forever_sets": gear_data.FOREVER_SETS["sets"],
        "consumable_stats": gear_data.CONSUMABLE_STATS, "direct_stats": {k: list(v) for k, v in gear_data.DIRECT_STATS.items()}, "classic_primary": gear_data.CLASSIC_PRIMARY,
    }


def api_payloads():
    """Same bodies server.py returns for the GET routes."""
    from sim import DATA, ASSUMPTIONS, TALENT_DATA, CONSUMABLE_DATA, preset
    from gear_data import CATALOG, PHASE6_BIS
    return {
        "bootstrap": {
            "presets": {name: preset(name) for name in ("protection", "retribution")}, "sources": DATA["sources"], "source_status": DATA["status"],
            "assumptions": ASSUMPTIONS, "excluded": DATA["excluded"], "gear_catalog": {key: CATALOG[key] for key in ("version", "source", "license", "scope")},
            "phase6_bis": PHASE6_BIS, "talent_data": TALENT_DATA, "consumable_data": CONSUMABLE_DATA, "setting_data": server.SETTING_DATA,
            "races": ed.CLASS_RACES["Paladin"], "racials": all_specs.public_racials(), "defaults": server.DEFAULTS,
        },
        "items": {"version": CATALOG["version"], "items": CATALOG["items"] + server.EXTRA_ITEMS["items"]},
        "specs": {"specs": all_specs.public_specs()},
        "benchmarks": server.default_benchmarks(),
        "spec-bootstrap": {
            "specs": all_specs.public_specs(), "talents": server.ALL_TALENTS, "gear": server.PHASE12_BIS, "consumables": CONSUMABLE_DATA,
            "settings": server.SETTING_DATA, "enchants": server.ENCHANT_DATA, "racials": all_specs.public_racials(), "defaults": server.DEFAULTS, "buff_groups": ed.BUFF_GROUPS,
            "set_effects": ed.SET_EFFECTS, "set_no_combat_effect": sorted(ed.SET_NO_COMBAT_EFFECT), "set_provisional": ed.SET_PROVISIONAL, "set_patterns": [p for _, p in engine.SET_PATTERNS],
        },
    }


def engine_items_extra(api_items):
    """Engine catalog rows that differ from (or are missing in) the public item payload."""
    public = {x["id"]: x for x in api_items}
    return [x for iid, x in all_specs.ITEMS.items() if public.get(iid) != x]


def main():
    dump(RS_DATA / "engine_data.json", engine_tables())
    dump(RS_DATA / "paladin_data.json", paladin_tables())
    payloads = api_payloads()
    for name, body in payloads.items():
        dump(WEB_DATA / f"{name}.json", body)
    dump(WEB_DATA / "engine-items-extra.json", {"items": engine_items_extra(payloads["items"]["items"])})
    dump(WEB_DATA / "enchants.json", server.ENCHANT_DATA)
    dump(WEB_DATA / "forever-sets.json", {"sets": all_specs.FOREVER_SETS})


if __name__ == "__main__":
    main()
