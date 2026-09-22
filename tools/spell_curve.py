"""Resolve a spell's real per-rank value(s) from Forever's retail-style Trait tables
(TraitDefinition -> TraitDefinitionEffectPoints -> CurveID -> CurvePoint) instead of trusting
SpellEffect.EffectBasePointsF alone.

Why: a parallel Forever conversion project (github.com/ElliotWood/Forever) documents that
Forever's talents live in the retail-style Trait tables, and that SpellEffect.EffectBasePointsF
"only holds one value and is sometimes stale" for those talent-scaled effects -- the real
per-rank progression lives in CurvePoint, addressed via TraitDefinitionEffectPoints.CurveID.
This sim has hit the same kind of staleness by hand this session (picking a single "Rank N"
SpellEffect row and hoping it's the right rank, with no way to see the other ranks to compare
against). This tool resolves the full picture in one shot: every SpellEffect row for the
spell, AND -- if it's a talent/trait-tree spell -- the actual curve-driven value at every rank,
so a sourcing note can cite the real progression instead of a single assumed number.

Usage:
    python tools/spell_curve.py <spell_id> [--build BUILD]
    python tools/spell_curve.py 16880                # Nature's Grace
    python tools/spell_curve.py 1316697               # Wrack (not a talent -- no curve)

If the spell isn't a talent/trait-tree spell (no TraitDefinition row references it), there's no
CurveID to check -- EffectBasePointsF is the only source, and if the ability has separate
Rank-N SpellIDs (the old Classic pattern, still used for baseline non-talent spells), each rank
needs its own lookup; this tool only resolves one spell ID at a time. Run it once per candidate
rank ID and compare EffectBasePointsF across them, rather than picking the id that "looks like"
the max rank.
"""
from __future__ import annotations

import argparse
import csv
import io
import urllib.request

BUILD_DEFAULT = "1.60.1.69913"


def fetch_csv(table: str, build: str, filters: dict | None = None) -> list[dict]:
    url = f"https://wago.tools/db2/{table}/csv?build={build}"
    if filters:
        for k, v in filters.items():
            url += f"&filter[{k}]={v}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; forever-sim-data-tools/1.0)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = r.read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spell_id", type=int)
    ap.add_argument("--build", default=BUILD_DEFAULT, help=f"wow_classic_beta build (default {BUILD_DEFAULT}; check https://wago.tools/builds for a newer one)")
    args = ap.parse_args()
    build = args.build

    print(f"== SpellEffect rows for spell {args.spell_id} (build {build}) ==")
    effects = fetch_csv("SpellEffect", build, {"SpellID": args.spell_id})
    if not effects:
        print("  (none -- check the spell id)")
    for e in effects:
        print(f"  effect {e['EffectIndex']} ({e.get('EffectAura', '')}): "
              f"EffectBasePointsF={e['EffectBasePointsF']}  "
              f"EffectBonusCoefficient={e['EffectBonusCoefficient']}  "
              f"EffectAuraPeriod={e['EffectAuraPeriod']}ms  "
              f"Variance={e.get('Variance', '')}")

    print("\n== Talent/trait-tree check ==")
    defs = fetch_csv("TraitDefinition", build, {"SpellID": args.spell_id})
    if not defs:
        print("  Not a talent/trait-tree spell (no TraitDefinition row references this SpellID).")
        print("  EffectBasePointsF above is the only source for this id. If this ability has")
        print("  separate Rank-N SpellIDs (the old Classic pattern for baseline spells), run")
        print("  this tool once per rank id and compare EffectBasePointsF across them instead")
        print("  of assuming which id is the max rank.")
        return

    for d in defs:
        def_id = d["ID"]
        print(f"  TraitDefinition {def_id} references this spell.")
        points = fetch_csv("TraitDefinitionEffectPoints", build, {"TraitDefinitionID": def_id})
        if not points:
            print("    No TraitDefinitionEffectPoints row -- this trait has no curve-scaled effect.")
            continue
        for p in points:
            curve_id = p["CurveID"]
            print(f"    effect {p['EffectIndex']}: CurveID={curve_id}")
            curve = fetch_csv("CurvePoint", build, {"CurveID": curve_id})
            curve.sort(key=lambda c: int(c["OrderIndex"]))
            ranks = [(c["Pos_0"], c["Pos_1"]) for c in curve]
            print(f"      per-rank values (rank -> value), from CurvePoint: {ranks}")
            print("      Compare this against the SpellEffect.EffectBasePointsF value above --")
            print("      if they disagree, CurvePoint is the one to trust.")


if __name__ == "__main__":
    main()
