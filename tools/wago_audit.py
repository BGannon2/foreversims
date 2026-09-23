"""Build a reviewable, offline evidence snapshot from build-pinned Wago CSV exports.

Only explicitly reviewed spell IDs / effect indexes are imported. Names and the
largest ID are not reliable selectors: the client includes NPC and seasonal spells.
Run: python tools/wago_audit.py --raw PATH --output data/wago_verified.json
The resulting fields are client data; attack tables, proc behavior and rotation
choices remain separate engine assumptions.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

BUILD = "1.60.1.69913"
# spell ID, explicit mappings of model field -> (DB2 table, effect index, column).
# Whole-spell timing/cost imports are separately opted into below.
SPELLS = {
    "Mortal Strike": (21553, {"weapon.flat": (1, "EffectBasePointsF")}),
    "Bloodthirst": (23894, {"flat": (0, "EffectBasePointsF")}),
    "Shield Slam": (23925, {"base": (1, "range")}),
    "Revenge": (25288, {"base": (0, "range")}),
    "Insect Swarm": (24977, {"tick": (0, "EffectBasePointsF"), "dot_coeff": (0, "EffectBonusCoefficient"), "tick_len": (0, "period"), "ticks": (0, "ticks")}),
    "Arcane Blast": (1239700, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Pyroblast": (18809, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient"), "tick": (1, "EffectBasePointsF"), "dot_coeff": (1, "EffectBonusCoefficient")}),
    "Ice Lance": (1240047, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Shadow Word: Pain": (10894, {"tick": (0, "EffectBasePointsF"), "ticks": (0, "ticks")}),
    "Shadow Word: Death": (1309636, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Devouring Plague": (19280, {"tick": (0, "EffectBasePointsF"), "dot_coeff": (0, "EffectBonusCoefficient")}),
    "Lightning Bolt": (15208, {"coeff": (0, "EffectBonusCoefficient")}),
    "Chain Lightning": (10605, {"coeff": (0, "EffectBonusCoefficient")}),
    "Lava Burst": (1238300, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Flame Shock": (29228, {}),
    "Siphon Life": (18881, {"tick": (0, "EffectBasePointsF"), "dot_coeff": (0, "EffectBonusCoefficient")}),
    "Drain Soul": (11675, {"tick": (1, "EffectBasePointsF")}),
    "Incinerate": (1293813, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Conflagrate": (18932, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Shadowburn": (18871, {"base": (1, "range"), "coeff": (1, "EffectBonusCoefficient")}),
    "Strider Kick": (1317257, {}),
    # 2026-09-23 provisional-value audit. Ranks trained below 60 pick up client level growth;
    # trigger-spell damage rows take cost/cast/cooldown from the castable parent ("whole_spell").
    "Moonfire": (9835, {"base": (1, "range"), "coeff": (1, "EffectBonusCoefficient"), "tick": (0, "EffectBasePointsF"), "dot_coeff": (0, "EffectBonusCoefficient"), "ticks": (0, "ticks")}),
    "Wrath": (9912, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Starfire": (25298, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Scorch": (10207, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Fire Blast": (10199, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Fireball": (25306, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient"), "tick": (1, "EffectBasePointsF")}),
    "Frostbolt": (25304, {"base": (1, "range"), "coeff": (1, "EffectBonusCoefficient")}),
    "Frostfire Bolt": (1237313, {"base": (1, "range"), "coeff": (1, "EffectBonusCoefficient"), "tick": (2, "EffectBasePointsF")}),
    "Arcane Explosion": (10202, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Arcane Missiles": (25346, {"tick": (0, "point"), "coeff": (0, "EffectBonusCoefficient")}, {"whole_spell": 25345}),
    "Mind Blast": (10947, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Earth Shock": (10414, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Shadow Bolt": (25307, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Searing Pain": (17923, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient")}),
    "Immolate": (25309, {"base": (1, "range"), "coeff": (1, "EffectBonusCoefficient"), "tick": (0, "EffectBasePointsF"), "dot_coeff": (0, "EffectBonusCoefficient")}),
    "Corruption": (25311, {"tick": (0, "EffectBasePointsF"), "dot_coeff": (0, "EffectBonusCoefficient"), "ticks": (0, "ticks")}),
    "Curse of Agony": (11713, {"tick": (0, "EffectBasePointsF"), "dot_coeff": (0, "EffectBonusCoefficient"), "ticks": (0, "ticks")},
                       {"caveat": "Client name is Bane of Agony; its ramping tick distribution is modeled as an even split of the same total."}),
    "Wrack": (1316697, {"tick": (0, "EffectBasePointsF"), "dot_coeff": (0, "EffectBonusCoefficient")}),
    "Rain of Fire": (1282385, {"tick": (0, "point"), "coeff": (0, "EffectBonusCoefficient")}, {"whole_spell": 11678}),
    "Volley": (1279715, {"tick": (0, "point"), "coeff": (0, "EffectBonusCoefficient")}, {"whole_spell": 14295}),
    "Serpent Sting": (25295, {"tick": (0, "EffectBasePointsF"), "ticks": (0, "ticks")}),
    "Arcane Shot": (14287, {"base": (0, "range")}),
    "Aimed Shot": (20904, {"weapon.flat": (0, "EffectBasePointsF")}),
    "Raptor Strike": (14266, {"weapon.flat": (0, "EffectBasePointsF")}),
    "Summon Hawk": (1293527, {"base": (0, "range"), "coeff": (0, "EffectBonusCoefficient"), "rap_coeff": (3, "EffectBasePointsF", .01)},
                    {"caveat": "The 18 sec continued assault is a summoned hawk (spell 1293248) whose damage is not client spell data; it keeps the earlier 34-damage, 9 x 2 sec placeholder."}),
    "Mutilate": (1241586, {"weapon.flat": (0, "EffectBasePointsF")}, {"whole_spell": 1241584,
                 "caveat": "The +20% against Poisoned targets applies while Deadly Poison is ticking; Instant Poison is not tracked as a poison state."}),
    "Mangle (Bear)": (1238073, {"weapon.flat": (0, "EffectBasePointsF")}, {"caveat": "Threat multiplier assumed equal to Maul's."}),
    "Spearing Strike": (1310222, {}),
    "Rend": (11574, {"tick": (0, "EffectBasePointsF"), "ticks": (0, "ticks")}),
    "Thunder Clap": (11581, {"base": (0, "range")}, {"caveat": "Threat multiplier (1.75x) is WoWSims-sourced, not client data."}),
    "Demoralizing Shout": (11556, {}, {"caveat": "Flat threat per target (43.2) is WoWSims-sourced, not client data."}),
    "Berserk": (417141, {}, {"caveat": "Only guaranteed critical strikes on combo-point generators are modeled."}),
    "Tiger's Fury": (5217, {}),
    "Multi-Shot": (2643, {}),
    "Mind Flay": (18807, {"tick": (0, "EffectBasePointsF"), "coeff": (0, "EffectBonusCoefficient")}),
    "Blizzard": (1279949, {"tick": (0, "point"), "coeff": (0, "EffectBonusCoefficient")}, {"whole_spell": 10187}),
    "Rage of the Farseer": (425336, {}),
}
# Node -> model modifier -> (effect index, conversion from DB2 units).
# Explicitly mapped, never inferred from a similarly sized numeric value.
RANKS = {
    "104925": {"cost_pct_all": (0, .01)},
    "104936": {"dmg_school:arcane": (0, .01), "dmg_school:nature": (0, .01)},
    "104755": {"ap_from_int": (0, .01)},
    "104759": {"flag:lightning_overload": (0, .01)},
    "104765": {"cast:Lightning Bolt": (0, .001), "cast:Chain Lightning": (0, .001), "cast:Lava Burst": (0, .001)},
    "105001": {"dmg_ability:Multi-Shot": (0, .01), "dmg_ability:Aimed Shot": (0, .01), "dmg_ability:Volley": (0, .01)},
    "105708": {"dmg_ability:Eviscerate": (0, .01)},
    "105716": {"crit_dmg_builder": (0, .01)},
    "105741": {"cost:Sinister Strike": (0, 1)},
    "105768": {"flag:shatter": (0, .01)},
    "105803": {"flag:spirit_while_casting": (0, .01)},
    "105843": {"flag:spirit_while_casting": (0, .01)},
    "105853": {"flag:spiritual_guidance": (0, .01)},
    "105877": {"crit_ability:Conflagrate": (1, 1)},
    "105879": {"crit_ability:Searing Pain": (0, 1), "dmg_destruction": (1, .01)},
    "105887": {"cost_pct_school:fire": (0, .01), "cost_pct:Shadow Bolt": (0, .01), "cost_pct:Shadowburn": (0, .01)},
    "105917": {"crit_dmg_periodic": (0, .01)},
    "105932": {"cost:Execute": (0, .1)},
    "110870": {"dmg_ability:Serpent Sting": (0, .01)},
}


class Snapshot:
    def __init__(self, directory):
        self.tables = {}
        self.manifest = []
        for path in sorted(Path(directory).glob("*.csv")):
            payload = path.read_bytes()
            reader = csv.DictReader(payload.decode("utf-8-sig").splitlines())
            if "ID" not in (reader.fieldnames or []):
                raise ValueError(f"{path.name} is not a DB2 CSV")
            self.tables[path.stem] = list(reader)
            self.manifest.append({"table": path.stem, "sha256": hashlib.sha256(payload).hexdigest(),
                                  "bytes": len(payload), "url": f"https://wago.tools/db2/{path.stem}/csv?build={BUILD}"})

    def rows(self, table, column, value):
        return [r for r in self.tables[table] if r[column] == str(value)]

    def one(self, table, column, value):
        rows = self.rows(table, column, value)
        if len(rows) != 1:
            raise ValueError(f"Expected one {table}.{column}={value}, got {len(rows)}")
        return rows[0]

    def spell(self, spell_id):
        result = {table: self.rows(table, "SpellID", spell_id) for table in
                  ("SpellEffect", "SpellPower", "SpellCooldowns", "SpellLevels", "SpellMisc")}
        result.update({table: self.rows(table, "ID", spell_id) for table in ("Spell", "SpellName")})
        misc = self.one("SpellMisc", "SpellID", spell_id)
        result["SpellDuration"] = self.rows("SpellDuration", "ID", misc["DurationIndex"])
        result["SpellCastTimes"] = self.rows("SpellCastTimes", "ID", misc["CastingTimeIndex"])
        return result


def damage_range(effect, levels, level=60):
    base = float(effect["EffectBasePointsF"])
    # DB2 variance describes the full width around BasePointsF. Spell-level
    # growth is independent of variance and capped at MaxLevel when present.
    maximum = int(levels["MaxLevel"]) or level
    growth = max(0, min(level, maximum) - int(levels["SpellLevel"]))
    extra = growth * float(effect["EffectRealPointsPerLevel"])
    half_width = base * float(effect["Variance"]) / 2
    return [round(base - half_width + extra, 6), round(base + half_width + extra, 6)]


def build_evidence(snapshot):
    spells = {}
    for name, (sid, mappings, *extra) in SPELLS.items():
        options = extra[0] if extra else {}
        rows = snapshot.spell(sid)
        effects = {int(e["EffectIndex"]): e for e in rows["SpellEffect"] if e["DifficultyID"] == "0"}
        fields = {}
        for field, (index, column, *scale) in mappings.items():
            effect = effects[index]
            if column in ("range", "point"):
                value = damage_range(effect, snapshot.one("SpellLevels", "SpellID", sid))
                if column == "point": value = round(sum(value) / 2, 6)
            elif column == "period":
                value = float(effect["EffectAuraPeriod"]) / 1000
            elif column == "ticks":
                value = int(float(rows["SpellDuration"][0]["Duration"]) / float(effect["EffectAuraPeriod"]))
            else:
                value = round(float(effect[column]) * (scale[0] if scale else 1), 6)
            fields[field] = value
        whole = snapshot.spell(options["whole_spell"]) if options.get("whole_spell") else rows
        # Reviewed castable spells have at most one mana/rage/energy row (none: free).
        power = [r for r in whole["SpellPower"] if r["PowerType"] in ("0", "1", "3")]
        if len(power) > 1:
            raise ValueError(f"Ambiguous power rows for {name}")
        if power:
            fields["cost"] = float(power[0]["ManaCost"]) / (10 if power[0]["PowerType"] == "1" else 1)
            if float(power[0]["PowerCostPct"]):
                fields["cost_pct"] = round(float(power[0]["PowerCostPct"]) / 100, 6)
        cast = int(whole["SpellCastTimes"][0]["Base"])
        if cast > 0:
            fields["cast"] = cast / 1000
        if whole["SpellCooldowns"]:
            cooldown = whole["SpellCooldowns"][0]
            recovery = max(int(cooldown["RecoveryTime"]), int(cooldown["CategoryRecoveryTime"]))
            if recovery:
                fields["cooldown"] = recovery / 1000
        spells[name] = {"spell_id": sid, "fields": fields, "rows": rows,
                        "status": "client-values-verified; engine behavior separately modeled"}
        if options.get("whole_spell"):
            spells[name].update(whole_spell_id=options["whole_spell"], whole_spell_rows=whole)
        if options.get("caveat"):
            spells[name]["caveat"] = options["caveat"]
    talents = {}
    for node, mappings in RANKS.items():
        link = snapshot.one("TraitNodeXTraitNodeEntry", "TraitNodeID", node)
        entry = snapshot.one("TraitNodeEntry", "ID", link["TraitNodeEntryID"])
        definition = snapshot.one("TraitDefinition", "ID", entry["TraitDefinitionID"])
        points = snapshot.rows("TraitDefinitionEffectPoints", "TraitDefinitionID", definition["ID"])
        fields, evidence = {}, []
        for key, (index, scale) in mappings.items():
            p = next(p for p in points if int(p["EffectIndex"]) == index)
            if p["OperationType"] != "0":
                raise ValueError(f"Unsupported curve operation {p['OperationType']}")
            curve = snapshot.rows("CurvePoint", "CurveID", p["CurveID"])
            ranks = {int(float(r["Pos_0"])): float(r["Pos_1"]) for r in curve}
            fields[key] = [round(ranks[rank] * scale, 6) for rank in range(1, int(entry["MaxRanks"]) + 1)]
            evidence.append({"modifier": key, "unit_scale": scale, "effect_points": p, "curve_points": curve})
        talents[node] = {"fields": fields, "link": link, "entry": entry, "definition": definition,
                         "spell": snapshot.one("Spell", "ID", definition["SpellID"]), "effects": evidence}
    return {"build": BUILD, "product": "wow_classic_beta", "tables": snapshot.manifest,
            "interpretation": "Explicit reviewed IDs only. Client tables do not prove server proc rules, target eligibility, or spell availability. Remaining abilities are not certified by this snapshot.",
            "spells": spells, "talents": talents}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build_evidence(Snapshot(args.raw))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Recorded {len(result['spells'])} spells and {len(result['talents'])} talent curves in {args.output}")


if __name__ == "__main__":
    main()
