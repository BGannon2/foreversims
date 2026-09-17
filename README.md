# Forever Paladin Lab



A working local browser and command-line prototype for every non-healer Classic class/spec, with dedicated Protection and Retribution Paladin models. Python 3.10+ with Tkinter; no packages, account, server, or network access required at runtime.

The browser server also includes an **All DPS & Tanks** workspace. It covers the other eight Forever classes with 21 additional configurations: Arms, Fury and Protection Warrior; Balance, Feral DPS and Feral Tank Druid; all three Hunter, Mage and Rogue trees; Shadow Priest; Elemental and Enhancement Shaman; and all three Warlock trees. Their roster and tree identities come from Wowhead's live Forever talent-calculator payload. Their numerical action models are provisional and are intentionally kept separate from the detailed Paladin engine until Forever spell ranks, gear profiles and combat logs are available.



## Start



Double-click **Launch Web.cmd** on Windows. It starts a network-accessible server on port `8765` and opens `http://127.0.0.1:8765/` locally. Other devices on the same network can open `http://<this-computer's-LAN-IP>:8765/`. Choose a specialization there. Protection and Retribution open the detailed Paladin simulator; the other cards open the expanded provisional simulator with that spec preselected. Keep the terminal window open while using it; press **Ctrl+C** there to stop the server. Use **Pin baseline** in the Paladin simulator before changing settings to compare results.

Every simulator has a **Back to all specs** link returning to the main menu. Direct URLs remain available at `http://127.0.0.1:8765/paladin.html` and `http://127.0.0.1:8765/all-specs.html`.



The browser layout follows the familiar WoWSims workflow: persistent run controls and quick stats in the left rail, with Gear, Character, Encounter, Talents, Rotation, Results, and Sources tabs in the main workspace. Each spec starts with a sourced Classic Anniversary Phase 1-2 loadout; Gear opens a searchable item picker with locally stored thumbnails. Hovering an equipped item or picker result shows its stats, effects, set pieces, equipped count, and active set thresholds.



Boss metrics default to a 120-second Patchwerk main-tank encounter: level 63, 2.0-second melee swings, a 2,700–3,300 raw physical damage range, and enough modeled healing to keep the baseline Protection profile active for the full sample. Blessing of Sanctuary is not modeled.

The default Classic Anniversary support package includes improved Power Word: Fortitude, improved Mark of the Wild, Arcane Intellect, improved Battle Shout, improved Blessing of Might and Devotion Aura. It deliberately excludes Rallying Cry, Spirit of Zandalar, Dire Maul tribute buffs, Songflower and Darkmoon Faire buffs. Consumable defaults are selected by role and damage style, enforce shared-category conflicts, and include physical, tank, caster, mana, rage, and energy choices. Gear profiles include editable Classic Phase 1–2 enchant selections whose stats are applied by the simulation.

The compatible target-debuff defaults are five stacks of Sunder Armor, Faerie Fire, Curse of Recklessness, Judgement of the Crusader, Gift of Arthas, Demoralizing Shout, Thunder Clap, Insect Swarm and Scorpid Sting. Every Settings toggle affects the algorithm. Judgement of the Crusader uses its 140 Holy bonus with explicit per-ability spell coefficients; Demoralizing Shout provisionally reduces raw boss damage by 10%. These assumptions remain editable and labeled.

Raid buffs and target debuffs use local spell thumbnails and cursor/focus tooltips showing their modeled effect, source and spell ID. The Results screen follows the WoWSims breakdown pattern with Damage, Threat, Damage Taken, Buffs, Debuffs, Resources and Log views. Contribution bars show each source as a share of the relevant total; the adjacent DPS, TPS or DTPS value and percentage use the same denominator.

Set definitions are overlaid with the sourced Forever rules before items reach the browser or simulation. The default five-piece Avenger's Battlegear now contributes its active +71 spell-damage bonus to both specs. The revised Forever Lightforge and Soulforge thresholds from Wowhead's gear-set update are attached to every matching catalog item; their static spell-power and mana-regeneration bonuses affect the model when active. Bonuses whose combat behavior is not fully exposed, including Rebuke and the Lightforge proc, remain visible and explicitly marked unmodeled rather than receiving invented values.

Consumables are assigned explicit exclusivity groups and incompatible choices are rejected by profile validation; the browser also clears another selection from the same group. The current default stack is legal under Vanilla/Classic Anniversary rules. In particular, Greater Stoneshield Potion uses the combat-potion cooldown but stacks with Elixir of Superior Defense, and Classic does not impose the later Burning Crusade one-battle/one-guardian restriction. Consumable cards use locally stored Wowhead thumbnails and show their effect, type, item ID and exclusivity group on hover. Talent nodes likewise show rank, current effect and next-rank text in cursor tooltips.



The original Tk desktop interface remains available through **Launch.cmd**.



The **Full profile** tab exposes every setting. Click **Apply JSON to controls** after editing it. Form controls drive the Run button. Probabilities and mitigation are entered as fractions (0.15 means 15%).



From this folder:



```powershell

python app.py

python server.py

python server.py --no-browser --port 8765

### Docker / Compose

From this directory, run `docker compose up -d --build`. The container publishes the simulator on port `8765` and restarts automatically unless stopped.

python sim.py --spec protection --iterations 300 --output prot-result.json

python sim.py --spec retribution --iterations 300 --output ret-result.json

python sim.py --spec protection --write-profile my-profile.json

python sim.py --profile my-profile.json --output my-result.json

python -m unittest -v

```



## Engine overview (2026-09-17 remediation)

All 21 non-Paladin specs run on `engine.py`, an event-driven model driven by the sourced tables in `engine_data.py`: level-60 base stats and stat conversions, Classic Anniversary ability data (base damage, coefficients, cast times, costs, cooldowns, DoT ticks, weapon rules) taken from WoWSims Classic, Forever talent effects keyed by Wowhead talent id, Forever racials, default 51-point builds, rotations, pets, raid buffs and consumables. The engine simulates swing timers, cast times and channels, DoT ticks, combo points, energy/mana/rage ticks with the five-second rule, the Classic level-63 attack tables (miss with hit suppression, dual-wield penalty, dodge, parry, block, glancing, crit suppression), procs (Windfury weapon and totem, Crusader, item procs, extra attacks, poisons), timed cooldowns and racial actives, Hunter and Warlock pets, and tank incoming attacks with health, healing, stance/form threat and flat threat. There is no calibration multiplier. Provisional values are listed under `configuration.notes` in every result.

The Paladin engine (`sim.py`) uses the same base-stat table, race offsets and racials (Human, Dwarf, Undead), spirit/mp5 mana ticks with the five-second rule, Windfury Totem, mana potions and runes.

Defaults are shared through `server.DEFAULTS`: 120-second Patchwerk, 300 iterations, 3,731 armor, Phase 1-2 gear, the saved 51-point builds, full compatible raid buffs (no world buffs) and spec-appropriate consumables. `python generate_benchmarks.py` rebuilds `benchmarks.json` from exactly those defaults; `python validation_matrix.py` rebuilds `VALIDATION_MATRIX.md`.

Visual theme: `web/theme.css` is the single design-token layer (Vaporwave/Outrun system adapted to the WoW Forever palette: bronze-gold-teal sunset gradient, class colors via `data-class`, local Orbitron/Share Tech Mono/JetBrains Mono, skewed buttons, perspective grid floor, glass cards with laser borders, CRT scanlines). It is loaded after the page stylesheets; edit tokens there rather than in `styles.css`.

Docker: the image is built from this directory (`docker compose up -d --build`); scratch files are excluded by `.dockerignore`.

## Scope and accuracy



This is an **experimental partial-mechanics simulator**, not a validated full rotation sim, DPS ranking or gearing recommendation. Presets use synthetic stats and encounter parameters. The talent planner reproduces the 52 talents, ranks, positions, descriptions, prerequisites, tier gates and 51-point cap exposed by Wowhead's Forever Paladin calculator. Both supplied builds spend all 51 level-60 talent points. Protection is optimized for TPS in the implemented model; Retribution maximizes every implemented DPS talent and favors the sourced melee damage talents for mechanics that remain unresolved.



The Forever mechanics snapshot is dated **2026-09-16**, and every ability or talent source is under **https://www.wowhead.com/forever/**. As a temporary, clearly labeled exception, the gear picker uses 2,355 pre-TBC Classic Era items from the MIT-licensed [nexus-devs/wow-classic-items](https://github.com/nexus-devs/wow-classic-items) dataset at commit `e848aab57261467479b7f0479607c05db024596f` (2021-04-30). The default sets follow Wowhead's Phase 6 [Paladin Tank BiS](https://www.wowhead.com/classic/guide/wow-classic-paladin-tank-naxxramas-best-in-slot-gear) and [Retribution Paladin BiS](https://www.wowhead.com/classic/guide/paladin-dps-naxxramas-best-in-slot-bis-gear-classic-era) guides. Item links open the Classic section of Wowhead. Classic combat conversions are confined to the clearly labeled audit switch.



### Implemented



- Seeded event queue: attack timers, cooldowns, mana costs, GCD, effects and expiration, death and fixed healing pulses.

- Protection: Righteous Fury; Holy Shield's block bonus, four charges and retaliatory threat; Templar's Bulwark; ranked Redoubt, Reckoning, Shield Specialization and Improved Righteous Fury effects.

- Protection Holy Strike: the supplied Forever record queues the next melee attack, converts the full hit to Holy damage, adds 2 damage, and costs 75 mana. Improved Holy Strike reduces its configured cooldown; Iron Creed increases its threat and grants its six-second damage reduction. Sacred Duty reduces Templar's Bulwark cooldown.

- Retribution: Seal of Command, Seal of Righteousness, Judgement, Twist of Light echo switching; ranked Vengeance, Sanctified Judgement and Improved Judgement effects.

- Consecration Rank 5: the sourced level-60 cast costs 565 mana and deals 384 Holy damage in eight one-second ticks over 8 seconds, with an 8-second cooldown.

- Sourced shared throughput talents: Precision, Conviction, Deflection, Improved Seals, Crusade, One-Handed Weapon Specialization and Two-Handed Weapon Specialization.

- Full interactive Forever Paladin talent trees for Holy, Protection and Retribution. Left click adds ranks; right click removes ranks. Lower tiers require five points per tier, prerequisite arrows are enforced, and total spending is capped at 51.

- Searchable level 45–60 Classic Era rare, epic and legendary gear. Weapon damage/speed and direct combat bonuses feed the simulation. The optional Classic audit also converts primary attributes, armor and attack power and models Thunderfury's proc. Parsed item effects and set bonuses are visible, with equipped piece counts and active/inactive thresholds.

- Pre-equipped Phase 1-2 Protection mitigation and Retribution DPS sets, including Libram of Hope for Protection and Libram of Fervor for Retribution. Exact item IDs, selection rules and source guides are recorded in `phase6_bis.json`.

- Single-target outgoing damage; configurable number of incoming attackers. All incoming attacks are physical, synchronized and keep targeting the player.

- Mean DPS, TPS, DTPS, damage taken per second alive, peak three-second incoming damage, survival fraction, mana, ability breakdowns, sampling intervals and a detailed first-iteration log.



### Explicit unresolved inputs



Command proc probability defaults to **25% per landed swing** as a synthetic experimental value. It is **not** a Forever proc-rate claim. Righteousness swing damage defaults to a manually supplied **50**; the tooltip's weapon-speed scaling remains unresolved. Critical multipliers, hit/avoidance tables, mitigation, base threat-per-damage and all character/boss stats are editable model assumptions. Classic AP, armor, defense and level conversions apply only when the audit switch is enabled.



`wowsims-comparison.md` records a controlled run against the public WoWSims Classic Protection Paladin simulator. It documents the matched configuration, results, ability breakdown and gaps exposed by the comparison. `profiles/protection-wowsims-audit.json` preserves the audit inputs. Classic-derived coefficients in that audit remain separate from the default Forever profile.



Classic Era conversions are isolated behind the `use_classic_era_conversions` audit switch because their Forever equivalents are unknown. Spirit, spell power, resistances, most item/set effects, enchants and gems remain informational. Every Forever talent can be selected and exported, while only talents explicitly named in the implemented mechanics list currently change simulation results.



The available Holy Strike record is implemented, but the level-60 rank remains unresolved. Wowhead Forever exposes eight Holy Strike libram ranks at levels 8–56, while those item pages currently point to Holy Light Rank 2 and spell search exposes only three unranked level-1 records. Because ID 17143 omits the base cooldown referenced by Improved Holy Strike, the simulator exposes that cooldown as a clearly labeled input and provisionally defaults it to six seconds. Seal of Fury remains unavailable because its indexed rank records contain no cost, shield amount, duration or Judgement effect. Buffs, resistances, glancing blows, parry haste, multi-target damage and special boss abilities remain outside this prototype.



### Metrics



DPS/TPS/DTPS use full requested fight duration, including time after death. Compare **survival and alive-DTPS together**: low full-fight DTPS can just mean an early death. Survival uses a fixed healing scenario; it is not universal tank quality. Time alive is capped at encounter duration. Sampling confidence intervals quantify RNG noise, not unknown mechanics. One iteration has no estimated confidence interval. Ret receives no attacks by default, so its survival metric is trivial unless incoming damage is enabled.



The engine evaluates rotation choices every 0.1 s. Simultaneous events resolve as decision, player swing, enemy swings, then healing. Events at the fight endpoint are excluded. Seed + iteration index determines each independent RNG stream. Identical data, inputs and seed reproduce results.



## Files



- `app.py`: Tk desktop interface.

- `server.py`: local browser server and JSON API.

- `web/`: responsive browser interface.

- `sim.py`: simulation engine and CLI.

- `all_specs.py`: isolated provisional models and sourced roster for the other DPS and tank configurations.

- `gear_data.py` and `classic_era_items.json`: Classic Era item bridge and generated catalog.

- `phase6_bis.json`: sourced default Protection and Retribution loadouts.

- `forever_set_bonuses.json`: Forever overrides, thresholds, modeled effects and source URLs for supported item sets.

- `paladin_talents.json` and `web/talent-icons/`: extracted Forever talent definitions and local icon assets.

- `web/item-icons/`: 709 locally stored Classic item thumbnails used by gear slots and the picker.

- `tools/download_item_icons.py`: reproducible downloader for catalog-referenced thumbnails.

- `tools/build_forever_talents.py`: reproducible extractor for the Wowhead Forever talent payload.

- `tools/build_classic_items.py`: reproducible catalog extractor pinned to the pre-TBC source commit.

- `data.json`: sourced values and Forever references, separate from assumptions.

- `test_sim.py`: behavioral and invariant tests.

- `profiles/`: editable sample profiles.

- `examples/`: generated example results (synthetic, not game benchmarks).



Next accuracy work: recover the corrected Forever rank records for Holy Strike and Seal of Fury, then reconcile the rotation and stat conversions against Forever combat logs. Replace the explicit assumptions with sourced rules as those become available.



## Verification



Automated engine, gear and server tests cover reproducibility, source boundaries, the pinned Classic snapshot, direct gear effects, weapon replacement, invalid loadouts, charge limits, expiration, mana conservation, echo consumption, Vengeance, death, input validation, output reconciliation, browser assets, local API simulation, invalid requests and path isolation. These checks verify the prototype's specified behavior, not accuracy against the game.

## Client-side engine (Rust → WebAssembly)

Simulations run in the visitor's browser. `engine-rs/` is a line-by-line Rust port of
`engine.py` (21 shared-engine specs) and `sim.py` + `gear_data.py` (Paladin), compiled to
WebAssembly and driven by a pool of Web Workers (`web/sim-client.js`, `web/sim-worker.js`).
It seeds a CPython-compatible Mersenne Twister and draws random numbers in the same order,
so a browser run and the Python reference produce identical numbers for the same request.

* Python stays the source of truth for every data table. `tools/export_static_data.py`
  writes them to `engine-rs/data/*.json` (embedded in the engine at compile time) and the
  former `/api/*` responses to `web/data/*.json` (served as static files).
* Rebuild after changing data or engine code: `tools/build_engine.sh` (needs rustup with
  the `wasm32-unknown-unknown` target and `wasm-bindgen-cli` 0.2.128).
* Parity: `python tools/parity_check.py` runs every spec through both engines;
  `test_parity.py` does the same in the test suite and also fails when `web/data` or
  `engine-rs/data` are stale.
* The Python server (`server.py`) still serves the site and the JSON API for tests and
  benchmark generation, but the UI no longer needs it. See `HOSTING.md` for static hosting
  on Cloudflare Pages at foreversims.com.
