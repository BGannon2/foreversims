# Direct client-data verification — 2026-09-22

Source priority: build-pinned Forever client rows from Wago for numeric fields;
Forever calculator / official mechanic descriptions for interpretation; WoWSims
Classic for unconfirmed baseline combat behavior. Derivative sites can discover
changes but agreement between them is not independent corroboration.

The Wago build API reported **1.60.1.69913**, created 2026-09-18, as the latest
`wow_classic_beta` build on this audit date. All exported tables used here are
pinned to that build. This report does not certify every spell or server behavior.

## Corrections

21 explicitly selected player spell IDs now override the older tooltip/Classic
baselines. `data/wago_verified.json` retains raw spell, effect, power, level,
cooldown and timing rows; source URLs and SHA-256 hashes identify the exports.

Examples before talents, gear and combat mitigation:

| Ability | Previous model | Verified client fields applied |
|---|---|---|
| Bloodthirst rank 4 | 35% AP + 30 | 35% AP + 48 |
| Mortal Strike rank 4 | Weapon damage + 85 | Weapon damage + 160 |
| Insect Swarm rank 5 | 8/tick, 155 mana, 0.127 SP/tick | 31/tick, 160 mana, 0.158 SP/tick |
| Pyroblast rank 8 | Low-rank direct damage and 11/tick | Rank-8 direct damage and 53/tick |
| Arcane Blast rank 5 | Low-rank damage, 250 mana, 0.68 SP | Rank-5 damage, 15% base mana, 0.714 SP |
| Shadow Word: Pain rank 8 | 95.25 × 8 base ticks | 127 × 6 base ticks; Improved SW:P adds ticks |
| Devouring Plague rank 6 | 16/tick, 215 mana | 106/tick, 985 mana |
| Incinerate rank 3 | Low-rank damage, 255 mana, 2 sec cast | Rank-3 damage, 325 mana, 2.5 sec cast |
| Strider Kick | Free | 5.81% base mana; 8 sec cooldown confirmed |

Shield Slam, Revenge, Ice Lance, Shadow Word: Death, Lightning Bolt, Chain
Lightning, Lava Burst, Flame Shock, Siphon Life, Drain Soul, Conflagrate and
Shadowburn have field-specific corrections too. Consult the snapshot's `fields`
for the precise imported scope. Damage ranges apply DB2 variance and independent
level growth, capped by the spell's MaxLevel. That interpretation remains an
engine calculation, not a combat-log observation.

19 talent nodes now use exact per-rank arrays in Python and Rust, including
Moonglow (-8/-17/-25%), Moonfury (2% per rank), Improved Execute (-3/-5 rage),
Improved Sinister Strike (-3/-5 energy), Lethality (4% per rank), and several
rounded percentage progressions. The arrays are joined through node → entry →
definition → effect-points → curve points. Only explicitly reviewed effect
indexes and unit conversions are applied. Elemental Alacrity now also affects
Lava Burst, and Barrage also affects Volley, as their client descriptions state.

The talent calculator may describe the initially learned rank. For example its
Bloodthirst flat bonus of 30 does not replace the level-60 rank-4 bonus of 48.
Selecting the highest spell ID or matching only by name is unsafe: these client
exports also contain NPC and seasonal variants.

## Reproduce

Download the tables named in `data/wago_verified.json` from their pinned URLs into
a directory, then run:

```sh
python tools/wago_audit.py --raw /path/to/csvs --output data/wago_verified.json
python tools/spell_curve.py 16880 --raw-dir /path/to/csvs
python tools/export_static_data.py
```

The audit generator rejects ambiguous spell rows and unsupported curve operations.
The curve-inspection utility also supports encoded exact Wago filters for live
queries. Offline input must contain exports from the specified build; table hashes
in the snapshot let reviewers check their copies.

## Remaining scope and assumptions

This is a field-level verification pass, not full validation of the 99 shared
engine abilities or the separate Paladin engine. Fields not in the snapshot are
still historical sourced values or estimates. In particular:

- Summon Hawk's summoned-unit attack schedule and scaling require tracing the
  summon chain; the old periodic approximation is not verified by its initial hit.
- Learned-rank availability and shared spell categories require spellbook / trainer
  and category checks; level eligibility alone does not establish availability.
- Proc flags, internal cooldowns, threat coefficients, healing/backlash, target
  restrictions, and periodic critical behavior need separate mechanic validation.
- Talent curves describe values and units, not all affected-spell masks or proc
  execution. Unmapped effects and rank-dependent triggered spells remain to audit.
- Paladin-specific formulas, racial actives, pet abilities, and item/set effects
  are not newly certified by this snapshot.

Do not treat parity between Python and Rust, or agreement with another derivative
site, as proof of game accuracy. Parity tests detect implementation drift;
source-row regression tests prevent the confirmed rank/value mistakes recurring.

## Validation

- 122 Python tests pass, including source-row assertions and exact partial-rank
  costs, base-mana percentage costs, tick counts, and talent interactions.
- 77 browser WebAssembly profiles / split-worker merges pass 91,902 numeric
  comparisons against Python; eight profiles specifically exercise partial ranks.
- Ruff, ESLint and Clippy pass.
- Comparison data regenerated for all 740 default race/spec/target combinations
  at 300 iterations, 120 seconds and 1–5 targets.

A matched 30-iteration diagnostic (seed 917, current default profiles, 120 sec)
changed Balance from 343.6 to 457.9 DPS, Arcane from 367.3 to 524.6, Elemental
from 336.2 to 319.7, and Affliction from 690.4 to 669.1. These are regression
comparisons, not external accuracy targets or claims about observed game DPS.
