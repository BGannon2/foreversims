# Forever Simulator Audit — status after the 2026-09-17 remediation

This file replaces the earlier implementation audit. The full finding list with
reproduction steps is in `CHANGELOG.md`; this page records what was
changed and what remains provisional.

## Architecture

| File | Role |
|---|---|
| `engine_data.py` | Sourced data: roster and racials (Wowhead Forever), level-60 base stats, stat conversions, ability records (base damage, coefficients, cast times, costs, cooldowns, DoT ticks, weapon rules), Forever talent effects keyed by talent id, default 51-point builds, rotations, pets, raid buffs, consumables. |
| `engine.py` | Event-driven simulation for all 21 non-Paladin specs: swing timers, cast times and channels, GCD, DoT ticks, combo points, energy/mana/rage ticks, Classic attack tables (miss, dodge, parry, glancing, block, crit suppression), spell hit table, procs (Windfury, weapon enchants, item procs, extra attacks, poisons), timed cooldowns, racial actives, hunter and warlock pets, tank incoming attacks with health and healing, threat with stance/form modifiers and flat threat. |
| `all_specs.py` | Public API: item catalog loading (`classic_era_items.json` + `extra_items.json` + preset rows), `public_specs`, `simulate_spec`. |
| `sim.py`, `gear_data.py` | Protection and Retribution Paladin engine: now driven by the same base-stat table, race offsets and racials, spirit/mp5 mana ticks with the five-second rule, Windfury Totem, mana potions/runes, sapper and chili, and 120 s defaults. |
| `server.py` | HTTP API, shared `DEFAULTS` (120 s, 300 iterations), `default_request` (the exact profile the UI loads) and benchmark generation from those defaults. |
| `validation_matrix.py` | Mechanic checks per spec; WoWSims fixtures are shown for context only. |

There is **no calibration multiplier** anywhere in the engine. `configuration.multiplier` is always 1.0 and `classic_reference_dps` is `null`.

## What the remediation changed

1. Calibration layer and `MODEL_BASELINE_DPS` removed; every packet is built from sourced base damage, coefficients, weapon damage and stats.
2. Cast times, channels and DoT ticks are simulated; casters no longer fire every 1.5 s.
3. Rotations use conditional priorities (execute phase, dot/buff uptime, combo points, pooling). Fire Mage casts Fireball, rogues build five combo points, feral druids Shred.
4. Passive effects are procs or buffs, not GCD abilities: Windfury (weapon and totem), Ignite, Deep Wounds, Slice and Dice, Blade Flurry, Adrenaline Rush, Death Wish, Combustion, Arcane Power, Bestial Wrath, Rapid Fire, Tiger's Fury, Elune's Light, Berserking, Blood Fury, Eureka!.
5. Warlock demons regenerate mana from Spirit and cast on real cast times; Imp Firebolt is continuous.
6. Attack tables follow WoWSims Classic: level-difference miss with hit suppression, 19 % dual-wield penalty, dodge, parry/block for tanks attacking from the front, 40 % glancing at the sourced multiplier range, 4.8 % melee and 2.1 % spell crit suppression, 17 % base spell miss capped at 1 %.
7. Tanks: 2,700–3,300 raw boss swings against armor (level-63 formula), dodge, parry, block, defense, crushing blows, health and healing; stance/form threat multipliers with Defiance; flat threat for Sunder Armor, Revenge, Shield Slam, Heroic Strike; Maul/Heroic Strike on next swing.
8. Every consumable and raid buff in a default list changes the simulation (tested); Fury no longer has inert consumables; Blessing of Kings/Wisdom, Strength of Earth, Grace of Air, Windfury Totem, Mana Spring, Leader of the Pack, Moonkin Aura and Trueshot Aura added.
9. Paladins: real base stats, race selection (Human, Dwarf, Undead) with sourced racials, spirit-based mana with the five-second rule, mana potions and runes, Consecration mana floor.
10. Defaults unified at 120 s / 300 iterations across engines, UI, benchmarks and tests. Benchmarks use the same talent builds, buffs and consumables the UI loads.
11. Item catalog extended with 128 daggers, fist weapons, staves, bows, guns, crossbows, wands and thrown weapons from the WoWSims database (`extra_items.json`) with class allow-lists honoured by the picker.
12. Item effects: Hand of Justice extra attacks, Sulfuras proc, Empyrean Demolisher haste, Vis'kag, Crusader, equip Attack Power text, Devilsaur/Nightslayer/Battlegear of Might set stats are parsed.
13. Server rejects runs above 400,000 simulated seconds; JS assets are served with `charset=utf-8`; scratch files are excluded from the Docker image.

## Provisional values (surfaced in `configuration.notes`)

- Elune's Light and Eureka! cooldowns (Wowhead publishes none; 120 s assumed), Berserking cooldown (180 s assumed), Orc Axe Specialization amount (1 % assumed), Rage of the Farseer cooldown.
- Spearing Strike rage cost and cooldown (Forever tooltip gives only the damage text).
- Shadow Word: Death uses TBC rank 2 numbers because the Forever tooltip is not in the dataset.
- Skyborne base attributes use the Human table.
- Hunter pet attack power is a fixed 252 (WoWSims Classic pet stat tables were not imported).
- Boss raw swing range 2,700–3,300 and the 2,500-per-2 s healing pulse are encounter assumptions, matching the Paladin preset.
- Spell resistance and partial resists are not modelled (level-63 Patchwerk with curses is treated as 0 resistance).

## Test coverage

`python -m unittest discover -v` runs 86 tests: attack-table rates against the Classic formulas, rage/energy/mana behaviour, cast-time and combo-point cadence, procs, racials, pets, tank tables, default build legality against the Forever tier/prerequisite rules, consumable and buff scope, enchant rules, server endpoints and the Paladin engine.
