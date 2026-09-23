"""Repeatable mechanic-level validation for every spec.

Unlike the previous version, this matrix does not scale results toward any
reference number.  It checks that the modelled mechanics behave as the sourced
rules say (attack-table rates, cast cadence, resource behaviour, sensitivity to
gear/talents/buffs) and reports the WoWSims Classic test fixtures only as an
informational comparison.  Those fixtures were generated with the full Phase 5
buff package including world buffs, so a ratio well below 1.0 is expected for a
no-world-buff profile.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from forever.all_specs import public_specs, simulate_spec
from server import DEFAULTS, default_request

# WoWSims Classic test fixtures (sim/*/Test*.results, "LongSingleTarget" style runs, FullBuffs = world buffs on).
WOWSIMS_WORLD_BUFFED = {
    "warrior-fury": (1454, 1807), "warrior-protection": (385, 416), "druid-balance": (217, 242), "druid-feral-dps": (475, 568),
    "hunter-beast-mastery": (457, 475), "hunter-marksmanship": (457, 475), "hunter-survival": (457, 475), "mage-arcane": (473, 521), "mage-fire": (473, 521), "mage-frost": (473, 521),
    "priest-shadow": (483, 504), "rogue-assassination": (1018, 1221), "rogue-combat": (1018, 1221), "rogue-subtlety": (1018, 1221),
    "shaman-elemental": (524, 583), "shaman-enhancement": (609, 669), "warlock-affliction": (1008, 1052), "warlock-demonology": (878, 920), "warlock-destruction": (878, 1052),
}


def spec_row(task):
    """Mechanic checks for one spec (top-level so worker processes can run it)."""
    spec, iterations, duration = task
    sid = spec["id"]
    base = default_request(spec, iterations=iterations, seed=917, duration=duration)
    full = simulate_spec(base)
    no_gear = simulate_spec({**base, "gear": [], "gear_slots": []})
    no_talents = simulate_spec({**base, "talents": {}})
    no_buffs = simulate_spec({**base, "buffs": [], "consumables": []})
    dps = full["metrics"]["dps"]["mean"]
    st = full["ability_stats"]
    checks = {
        "gear_increases_dps": dps > no_gear["metrics"]["dps"]["mean"] * 1.05,
        "talents_increase_dps": dps > no_talents["metrics"]["dps"]["mean"] * 1.02,
        "buffs_increase_dps": dps > no_buffs["metrics"]["dps"]["mean"] * 1.02,
        "breakdown_reconciles": abs(sum(full["ability_dps"].values()) - dps) < 1e-6,
        "finite_positive": 0 < dps < 5000,
        "no_calibration": full["configuration"].get("multiplier", 1.0) == 1.0,
    }
    # Attack-table sanity: white melee against a level-63 target must show glancing blows and misses.
    white = st.get("Melee (Main-Hand)") or st.get("Auto Shot")
    if spec["style"] == "melee" and white:
        checks["glancing_blows_present"] = white["glances"] > 0
        checks["glance_rate_plausible"] = 0.25 <= white["glances"] / max(1, white["casts"]) <= 0.45
    if spec["style"] == "spell":
        checks["cast_time_respected"] = all(v["casts"] <= duration / (full["configuration"]["actions"][k]["cast"] / 1.35) + 2 for k, v in st.items() if v["casts"] > 0 and full["configuration"]["actions"].get(k, {}).get("cast", 0) > 0)
    if spec["resource"] == "Energy":
        energy_spent = sum(v["casts"] * full["configuration"]["actions"][k]["cost"] for k, v in st.items() if k in full["configuration"]["actions"])
        checks["energy_budget_respected"] = energy_spent <= (duration / 2 * 20 * 1.35 + 100 + 100 + 25 * 20)
    if spec["role"] == "tank":
        checks["tank_takes_damage"] = full["metrics"]["dtps"]["mean"] > 0
        checks["tank_threat_exceeds_damage"] = full["metrics"]["tps"]["mean"] > dps
    lo, hi = WOWSIMS_WORLD_BUFFED.get(sid, (None, None))
    ratio = round(dps / ((lo + hi) / 2), 3) if lo else None
    row = {"spec": sid, "dps": round(dps, 1), "tps": round(full["metrics"]["tps"]["mean"], 1), "without_gear": round(no_gear["metrics"]["dps"]["mean"], 1),
           "without_talents": round(no_talents["metrics"]["dps"]["mean"], 1), "without_buffs": round(no_buffs["metrics"]["dps"]["mean"], 1),
           "wowsims_world_buffed": [lo, hi], "ratio_to_world_buffed": ratio, "starved": round(full["resource"]["starved_fraction"], 3), "checks": checks}
    return row, [f"{sid}: {name}" for name, passed in checks.items() if not passed]


def run_matrix(iterations=60, duration=None):
    duration = duration or DEFAULTS["duration"]
    rows, failures = [], []
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=os.cpu_count()) as pool:  # each spec's checks are independent
        for row, spec_failures in pool.map(spec_row, [(spec, iterations, duration) for spec in public_specs()], chunksize=1):
            rows.append(row)
            failures.extend(spec_failures)

    focused = []
    def check(name, passed, detail):
        focused.append({"name": name, "passed": bool(passed), "detail": detail})
        if not passed: failures.append(name)
    bm = simulate_spec(default_request(public_specs()[6], iterations=iterations, duration=60, pet_uptime=1))
    bm0 = simulate_spec(default_request(public_specs()[6], iterations=iterations, duration=60, pet_uptime=0))
    check("hunter pet contributes", bm["metrics"]["dps"]["mean"] > bm0["metrics"]["dps"]["mean"], f"{bm['metrics']['dps']['mean']:.1f} vs {bm0['metrics']['dps']['mean']:.1f}")
    demo = [s for s in public_specs() if s["id"] == "warlock-demonology"][0]
    succ = simulate_spec(default_request(demo, iterations=iterations, duration=60, pet_family="succubus"))
    imp = simulate_spec(default_request(demo, iterations=iterations, duration=60, pet_family="imp"))
    check("imp casts firebolt continuously", imp["ability_stats"].get("Imp - Firebolt", {}).get("casts", 0) >= 20, f"{imp['ability_stats'].get('Imp - Firebolt', {}).get('casts', 0):.1f} casts in 60 s")
    check("warlock pet selection changes output", abs(succ["metrics"]["dps"]["mean"] - imp["metrics"]["dps"]["mean"]) > 1, f"succubus {succ['metrics']['dps']['mean']:.1f}, imp {imp['metrics']['dps']['mean']:.1f}")
    prot = [s for s in public_specs() if s["id"] == "warrior-protection"][0]
    tank = simulate_spec(default_request(prot, iterations=iterations, duration=60))
    naked = simulate_spec(default_request(prot, iterations=iterations, duration=60, gear=[], gear_slots=[]))
    check("tank gear reduces incoming damage", tank["metrics"]["dtps"]["mean"] < naked["metrics"]["dtps"]["mean"], f"{tank['metrics']['dtps']['mean']:.1f} vs {naked['metrics']['dtps']['mean']:.1f}")
    fire = [s for s in public_specs() if s["id"] == "mage-fire"][0]
    fm = simulate_spec(default_request(fire, iterations=iterations, duration=120))
    check("fire mage casts fireball as its primary spell", fm["ability_stats"]["Fireball"]["casts"] > fm["ability_stats"]["Scorch"]["casts"], f"Fireball {fm['ability_stats']['Fireball']['casts']:.1f}, Scorch {fm['ability_stats']['Scorch']['casts']:.1f}")
    combat = [s for s in public_specs() if s["id"] == "rogue-combat"][0]
    rc = simulate_spec(default_request(combat, iterations=iterations, duration=120))
    check("combat rogue builds combo points before finishing", rc["ability_stats"]["Sinister Strike"]["casts"] > 4 * rc["ability_stats"]["Eviscerate"]["casts"], f"SS {rc['ability_stats']['Sinister Strike']['casts']:.1f}, Eviscerate {rc['ability_stats']['Eviscerate']['casts']:.1f}")
    return {"duration": duration, "iterations": iterations, "rows": rows, "focused": focused, "failures": failures}


def write_report(result):
    (ROOT / "validation_matrix.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = ["# Cross-spec validation matrix", "", f"{result['iterations']} iterations, {result['duration']} seconds, Phase 1-2 default gear, default 51-point builds, full compatible raid buffs, default consumables, no world buffs. No calibration multipliers are applied.", "",
             "| Spec | DPS | TPS | No gear | No talents | No buffs | Starved | WoWSims (world-buffed) | Ratio | Result |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for x in result["rows"]:
        ok = all(x["checks"].values()); wb = x["wowsims_world_buffed"]
        lines.append(f"| {x['spec']} | {x['dps']} | {x['tps']} | {x['without_gear']} | {x['without_talents']} | {x['without_buffs']} | {x['starved']:.0%} | {wb[0]}–{wb[1]} | {x['ratio_to_world_buffed'] if x['ratio_to_world_buffed'] is not None else 'n/a'} | {'PASS' if ok else 'FAIL: ' + ', '.join(k for k, v in x['checks'].items() if not v)} |")
    lines += ["", "## Focused checks", ""] + [f"- {'PASS' if x['passed'] else 'FAIL'} - {x['name']}: {x['detail']}" for x in result["focused"]]
    lines += ["", "## Reading the table", "", "The WoWSims column lists the checked-in WoWSims Classic test fixtures. Those runs use the Phase 5 test buff package with every world buff (Rallying Cry, Songflower, Zandalar, Warchief's, DMF, Dire Maul), Blessing of Kings/Sanctuary/Wisdom and P1 talents/APLs. The Forever defaults exclude world buffs, so ratios of roughly 0.6–0.9 are the expected envelope; the ratio is informational and is not a pass/fail criterion. Pass/fail comes from the mechanic checks: gear, talents and buffs must each raise DPS, the breakdown must reconcile, white melee must show glancing blows at the level-63 rate, cast counts must respect cast times, energy spending must respect the tick budget, and tanks must take damage and generate more threat than damage."]
    if result["failures"]: lines += ["", "## Failures", ""] + [f"- {x}" for x in result["failures"]]
    (ROOT / "VALIDATION_MATRIX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    result = run_matrix()
    write_report(result)
    print(json.dumps({"specs": len(result["rows"]), "failures": result["failures"]}, indent=2))
    raise SystemExit(bool(result["failures"]))
