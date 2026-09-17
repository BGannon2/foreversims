# Fury Warrior comparison with WoWSims Classic

Run date: 2026-09-17

This comparison used a 120-second encounter with 15-second duration variance, a 20% Execute phase, 1,000 iterations, no world buffs, and the closest available Phase 2 presets and raid effects in each simulator.

## Results

| Metric | WoWSims Classic | Forever prototype | Difference |
|---|---:|---:|---:|
| Total DPS | 968.68 | 481.54 | -50.3% |
| Melee, both hands | 301.60 | 215.09 | -28.7% |
| Heroic Strike | 261.69 | 52.36 | -80.0% |
| Execute | 195.61 | 81.27 | -58.5% |
| Bloodthirst | 142.19 | 83.08 | -41.6% |
| Whirlwind | 40.68 | 32.52 | -20.1% |
| Deep Wounds | 14.63 | 9.26 | -36.7% |

WoWSims used 17 Arms / 34 Fury / 0 Protection. The prototype automatically selected 20 Arms / 31 Fury / 0 Protection and sent only tree totals to the backend.

## Material setup differences

| Input | WoWSims | Forever prototype |
|---|---:|---:|
| Attack power | 1,598 | 1,309 |
| Melee crit | 31.15% | 23.70% |
| Displayed hit | 10% | 9% gear hit |
| Main hand | Rivenspike | Empyrean Demolisher |
| Off hand | Bone Slicing Hatchet | Vis'kag the Bloodletter |
| Target | Classic / level 60 | level-63 Patchwerk model |

## Accuracy gaps, ranked

1. **Heroic Strike queueing and rage spending.** WoWSims cast Heroic Strike 34.58 times per fight; the prototype cast it 9.49 times. The prototype lacks WoWSims' queue-delay behavior and does not model the complete queued-Heroic-Strike combat-table interaction.
2. **Derived stats and temporary effects.** The prototype starts almost 300 AP and 7.45 percentage points of crit behind the comparison. It folds Crusader into a permanent 100 AP enchant value and does not simulate Crusader, Flurry, Death Wish, or Mighty Rage as timed effects.
3. **Exact talents are disconnected from simulation.** The browser displays individual talents, but the request sends only points per tree. Fury mechanics therefore use hard-coded assumptions instead of the selected ranks. The default build also differs from WoWSims' 17/34 build.
4. **Combat tables are incomplete.** The prototype uses a single hit probability, omits dodge, glancing blows, weapon skill, racial expertise, and the queued Heroic Strike off-hand interaction. It reports approximately 1% special misses while WoWSims reports about 6% avoided specials in this setup.
5. **Gear presets do not match.** Different weapon damage, speed, skill requirements, procs, and total stats make ability averages and rage income diverge before rotation logic is considered.
6. **Rage remains incomplete despite the corrected damage-to-rage conversion.** Auto-attack rage now uses the level-60 conversion value, but avoidance, glancing damage, queued attacks, extra attacks, timed haste, and proc windows change both incoming rage and spending opportunities.
7. **Rotation omissions.** WoWSims uses Hamstring for proc fishing and models cooldown windows. The prototype has no Hamstring action and uses a fixed priority with a simple rage threshold.
8. **Damage-source details.** The prototype models one Sapper hit, simplified Dragonbreath Chili and Vis'kag procs, and no complete Hand of Justice/extra-attack chain. WoWSims reports more proc and engineering damage.

## Conclusion

The current result is not close enough to use as an accuracy benchmark. Correcting the rage conversion alone cannot close the gap. The next implementation pass needs exact talent-rank input, the full warrior combat table and Heroic Strike queue state, timed buffs/procs, and an identical gear preset before rotation tuning is meaningful.

Sources: [WoWSims Classic Warrior](https://wowsims.github.io/classic/warrior/), [WoWSims Classic source](https://github.com/wowsims/classic)


## Implemented correction pass

After the correction pass, the same local benchmark produces **760.32 DPS** and **918.11 TPS**. This is a 57.9% improvement over the prior 481.54 DPS result. The remaining 21.5% difference from the 968.68 WoWSims Classic run is no longer primarily a rage-throughput problem: Heroic Strike casts now match (34.8 local vs. 34.58 WoWSims), off-hand swing counts are close (55.6 vs. 59.74), and Whirlwind casts match (9.0 vs. 8.14).

The residual is expected to include ruleset differences: the local target remains the requested level-63 Patchwerk target, while the comparison used WoWSims' Classic/level-60 NPC; the local model uses Forever Bloodthirst (35% AP + 30) and Forever talent changes, while WoWSims uses Classic formulas. Further convergence requires a level-matched reference and Forever combat logs rather than calibrating Forever formulas to Classic output.


## 2026-09-17 engine replacement

The Fury path above (and every other non-Paladin spec) now runs on the shared event-driven engine described in `SIMULATOR_AUDIT.md`. With the saved defaults (120 s, Phase 2 gear, full compatible raid buffs including Windfury Totem and Blessing of Kings, no world buffs, pull Bloodlust) the Fury default produces roughly 890 DPS at 60-120 iterations; the WoWSims Classic test fixtures for the same class (1,454-1,807 DPS) are world-buffed Phase 5 runs and are not a like-for-like target. The remaining known differences from WoWSims are the Forever talent values (Bloodthirst 35 % AP + 30, Flurry 25 %, Dual Wield Specialization 25 %/+100 % rage/+10 % hit, Unbridled Wrath 60 %), the Forever racials, and the absence of world buffs.
