# v0.22.0 accuracy release

This release addresses the reproducible defects from the September 22 audit of
v0.21.0 (`7335803`). Forever Sims remains an alpha: implementation parity is not
proof that every inferred game mechanic matches the unreleased game.

## Audit resolutions

| Finding | Change |
| --- | --- |
| F01: talent effects | Restore Anticipation, Toughness and Improved Revenge; scale Flurry by rank; stop double-counting Hunter hit/crit. |
| F02: Hunters and pets | Calculate ranged AP independently, use class base mana for percentage costs, restore pet AP, use independent pet attack tables, fix Frenzy triggers and support no-pet/Lone Wolf builds. |
| F03: combat tables | Roll spell hit and crit independently; bypass armor for actual bleeds; retain signed defense penalties and crushing blows until attack-table coverage pushes them off. Correct the shared armor formula to the Classic fallback. |
| F04: rage | Damage-derived rage has no threat; ability-derived rage grants flat threat per actual resource gained. Avoided white attacks use pre-outcome damage for rage. |
| F05: Paladins | Separate permanent item stats from timed effects; model Hand of Justice, Force of Will, Quel'Serrar, supported on-use stats and Crusader; include normalized AP in Holy Strike; scale seal coefficients; enforce Holy Wrath's GCD; expose gear enchants and enable Holy Strike in the Ret default. |
| F06: comparisons | Use the same default enchants as the UI, and preserve race, targets, iterations and seed in benchmark links. Regenerate the saved comparisons. |
| F07: equipment | Preserve equipment-slot identity when selecting an item, clear an offhand when equipping a two-hander, and validate class/slot compatibility in the shared engine and picker. |
| F08: caster defaults | Choose school-appropriate enchants; replace the Priest's illegal sword with Anathema; allow legitimate greens and items with unknown level metadata. Parse short mana regeneration and school-damage labels. |
| F09: item uncertainty | Preserve unsupported haste/expertise ratings, disclose provisional rating conversions, exclude explicit test/temporary items, and distinguish unknown availability from confirmed removal. Conditional set procs no longer become permanent stats. |
| F10: racials | Apply Human Spirit, Dwarf Beast damage and timed Stoneform consistently in the relevant engines. |
| F11: validation | Test every spec against native Rust and the actual shipped WASM, including ability/resource/log results and split-worker merges. Add independent mechanic regression tests and disclose periodic-crit approximation. |
| F12: feedback privacy | Keep contact details private in storage; exclude contact and user-agent data from GitHub/Discord forwarding and explain public feedback handling. |
| F13: admin links | Sanitize URL schemes/hosts/query fields, sanitize legacy stored links at render time, require same-origin admin writes, and add a restrictive admin CSP. |

Opening Bloodlust/Heroism now applies the requested 30% haste to both player engines
and pet swings/casts. Its 40-second duration remains an explicit scenario assumption,
pending confirmed Forever data. Swing intervals crossing expiration lose the haste
for the remaining part of the interval.

Asset stamping now updates HTML, client, worker and engine URLs, so returning visitors
receive the new engine rather than a cached worker. Benchmark generation uses at most
eight processes to avoid saturating large desktop machines.

## Evidence and validation

Classic fallback mechanics were cross-checked against
[WoWSims Classic commit 7779ebb](https://github.com/wowsims/classic/tree/7779ebbf79dc7f1341e6ab939b28a3402c9a730a),
especially Hunter pet stats and core attack/rage tables. Stored Forever spell/talent
data and the [Forever racial guide](https://www.wowhead.com/forever/guide/new-race-class-combinations)
take precedence over that fallback. Source provenance remains in the data tables.

- 113 Python tests, including independent regression expectations and all-spec native parity.
- 69 actual WASM profiles and split-worker merges, with 83,570 numerical checks.
- Three isolated Worker privacy/security tests, without sending real feedback.
- Ruff, ESLint and Clippy.
- Local browser simulations for Shadow Priest and Retribution, including gear/enchant UI and an Arms two-handed weapon swap/reopen.

Unrounded parity values use a 1e-6 absolute tolerance. Rounded combat-log values allow
one displayed unit for cross-language half-decimal rounding; event names, outcomes and
counts still have to agree. CI runs the native and shipped-WASM checks.

## Remaining limits

- Default builds are practical saved baselines, not a proof of globally optimal talents,
  rotations, gear or pets. Comparisons should not be treated as authoritative rankings.
- Periodic critical damage uses a snapshotted expected value. Independent tick-crit
  variance, tick-crit counts and every crit-trigger interaction are not modeled.
- Unknown item and set effects remain listed as unresolved instead of being silently
  treated as working. Unsupported ratings are disclosed rather than guessed.
- Force of Will and Quel'Serrar proc frequencies use explicitly identified assumptions;
  their exact Forever proc behavior still needs confirmation.
- Classic baseline availability, some rating conversions, encounter assumptions and
  other per-ability provisional values need verification against Forever combat logs.
- Monte Carlo confidence intervals measure sampling noise, not uncertainty in those
  mechanics. Passing Python/Rust/WASM parity only establishes implementation agreement.

Further releases should prioritize independently captured Forever logs and controlled
single-mechanic tests before tuning defaults or claiming exact BiS rankings.
