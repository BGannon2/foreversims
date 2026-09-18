# WoW Forever vs. Classic: what actually changed, per spec

This is a running reference of every Forever-specific mechanic change this project has sourced
and implemented, organized by class. It exists to answer "what's different from regular Classic"
without re-deriving it from the codebase each time.

**Confidence key:**
- **Sourced** — pulled directly from a Forever tooltip/talent-calculator/guide, cited in
  `data.json`/`engine_data.json`/`paladin_talents.json`'s `"sources"` or `forever:true` markers.
- **Provisional** — Forever doesn't publish the exact number; the code uses a placeholder
  (usually a comparable Classic or same-spec value) and says so explicitly in the ability table.
- **Bug fix, not a Forever change** — something this sim got wrong internally; included here only
  where it could otherwise be mistaken for an intentional design difference.

Full incident-level detail (why each fix happened, what broke, what the numbers moved) lives in
`AUDIT_2026-09-17.md`. This doc is the distilled "what's different" summary, not the investigation
log.

---

## Character creation: new race/class combinations (sourced)

Source: https://www.wowhead.com/forever/guide/new-race-class-combinations. Diffed against
vanilla Classic's race/class matrix; `engine_data.py`'s `CLASS_RACES` already reflects the
Forever roster.

- **Undead can be Paladin** — the first Horde-side Paladin combination; vanilla Classic
  restricted Paladin to Human/Dwarf only.
- **Dwarf can be Shaman** — the first Alliance-side Shaman combination; vanilla Classic
  restricted Shaman to Orc/Tauren/Troll only.
- **Human can be Hunter** — not available in vanilla Classic.
- **Gnome can be Priest** — not available in vanilla Classic.
- **Orc can be Mage** — not available in vanilla Classic.
- New race: **Skyborne**, playable on both factions (Skyborne (Alliance) / Skyborne (Horde)),
  available to Warrior, Hunter, Rogue, and — notably — **Druid**, a class that was otherwise
  the most faction-locked in vanilla Classic (Night Elf/Tauren only).
- No change found for Warrior, Rogue, or Warlock's race lists (already broad in vanilla) or
  for Night Elf/Tauren Druid specifically (still faction-exclusive outside Skyborne).

## Gear: updated item set bonuses (sourced, Paladin-confirmed)

Source: https://www.wowhead.com/forever/news/new-and-updated-gear-set-bonuses-in-wow-forever-382958.
Blizzard's post covers dungeon/tier set reworks generally; this project has only cross-checked
and implemented the **Paladin** sets so far (`forever_set_bonuses.json`) — treat other classes'
sets as unaudited, not "unchanged."

- **Avenger's Battlegear** (Paladin tier): 3-piece now increases Judgement duration by 20%;
  5-piece grants up to 71 spell power (both reworked from their Classic bonuses).
- **Lightforge Armor** (Paladin dungeon set): 2/3/4/5/6-piece bonuses reworked, including a
  new 4-piece "Rebuke" effect and a 5-piece proc granting spell power on melee/spell casts.
- **Soulforge Armor** (Paladin dungeon set): similarly reworked 2/3/5/6-piece bonuses.
- Separately, Judgement Armor's 8-piece and Battlegear of Eternal Justice's 3-piece effects
  were added to this project's Paladin engine (Classic-era sets, not Forever-reworked, but
  previously unmodeled here).

---

## Threat generation

**Only Paladin has a confirmed, sourced Forever threat redesign.** Warrior Protection and Feral
Druid still run on Classic's standard stance/form threat multipliers (`STANCE_MODS` in
`engine_data.py`: Defensive Stance +30%, Bear Form +45% — both vanilla-Classic constants, not
Forever-new). No Forever-specific threat-system overhaul has been sourced for either of those two
tanks yet; that's a real gap, not a "nothing changed" finding — it just hasn't been audited to
Paladin's depth.

### Protection Paladin (sourced)
- **Righteous Fury** grants **+90% Holy threat** (Wowhead Forever tooltip). This project initially
  had it recorded as +60% — a mis-transcription, corrected 2026-09-18 (v0.9.5).
- **Seal of Fury** is a new Protection-oriented seal with no Classic equivalent: melee swings deal
  +10% spell power Holy damage (which benefits from the Righteous Fury threat bonus above), and
  while a shield is equipped each landed swing also grants a small self-absorb shield (50% of that
  Holy damage).
- **Judgement of Fury doubles as a taunt** (4 sec) — this is Protection's actual "hold aggro" tool
  in Forever, not a flat threat-stance multiplier the way Warrior/Druid tanks get.
- **Judgement no longer consumes the active seal** in Forever (unlike Classic, where Judgement
  clears your seal). This was found as a real bug in this sim, not a design choice — fixed
  2026-09-18, since without it Seal of Fury would need recasting after almost every Judgement.
- Net design read (from the Forever Protection class-overview guide, not just the spec page):
  Paladin threat in Forever leans on "Holy-school damage bonus + guaranteed taunt," structurally
  different from Warrior's Defensive Stance or Druid's Bear Form (a blanket multiplier on *all*
  damage). This reads as intentional but isn't confirmed by an explicit "Paladin threat is X% of
  Warrior's" source — flagged as an open question in `AUDIT_2026-09-17.md`.

### Retribution Paladin (sourced)
- Same seal/Judgement mechanics as above apply spec-wide, but Retribution isn't threat-optimized —
  it twists between Seal of Righteousness and Seal of Command instead of running Fury exclusively.
- **Seal of Righteousness**'s swing proc scales with weapon speed and hand type (18.8 base value ×
  0.85 one-hand / 1.2 two-hand × weapon speed), not a flat number — this project had it as a flat,
  user-configurable placeholder (50) until 2026-09-18 (v0.9.6).
- **Seal of Righteousness**'s Judgement deals 50% of spell power as Holy damage (was a flat,
  unsourced 170–187 roll before v0.9.6).
- **Seal of Command** costs 210 mana (was recorded at 65, an old talent-era value) and its
  Judgement deals 42.9% of spell power as Holy damage (was a flat, unsourced 68–73 roll).
- **Improved Seals** (105334) is sourced as a flat +5/10/15% bonus to *both* Seal and Judgement
  damage — as of v0.9.6 this is applied consistently to all three seals' swing procs and
  Judgements, including Fury's Judgement, which had been missing it entirely.
- **Sacred Arbiter** (105700): +10% Holy Strike damage (sourced). Its "refreshes all Judgement
  effects on the target" clause is a documented no-op in this model, since Judgement applies no
  persistent/refreshable debuff.

### Warrior Protection (sourced, ability-level only)
- `Shield Slam`'s base damage and flat threat value are Forever's own sourced numbers, not
  Classic's — but this is a single-ability tuning update, not a threat-system redesign.
- **Bug fix, not a Forever change**: `Master of Defense` and `Shield Specialization` were storing
  their per-rank *rage-proc chance* (50%/rank and 20%/rank) as a flat *rage amount* instead, so
  both mana/rage procs fired far too reliably. `Master of Defense` was also only checking for
  Dodge when the guide specifies both Dodge and Parry. Fixed 2026-09-17.

### Feral Druid (tank) — not yet audited
No Forever-specific threat sourcing has been done for Bear Form tanking beyond the standard
Classic 45% stance threat multiplier. Treat Feral Tank's threat numbers as Classic-baseline until
someone does the same tooltip-by-tooltip pass that Paladin got.

---

## Ability/mechanic changes by class

### Warrior
- `Weaponmaster`: mace/staff armor-ignore now scales **3%/rank** (was hardcoded at 15% regardless
  of rank); the axe/polearm crit bonus (**1%/rank**) didn't exist in this sim's model at all
  before — both sourced from the Forever guide.
- New talent: **Spearing Strike** (Arms) — a rage-cost direct hit dealing 3x damage against
  Giants and Dragonkin. No Classic equivalent.
- `Mortal Strike`, `Bloodthirst`, and `Death Wish` all carry Forever-sourced damage/duration
  values, retuned from their Classic numbers.

### Priest
- `Improved Shadow Word: Pain`: rank 1 now correctly grants **+1 DoT tick**, rank 2 grants +2
  (this sim was granting the full rank-2 bonus at rank 1).

### Shaman
- `Lightning Bolt` cast time: **2.5s** (Classic 3.0s); base damage also retuned to Forever's
  sourced value.
- `Chain Lightning` cast time: **2.0s** (Classic 2.5s); base damage also retuned to Forever's
  sourced value.
- `Stormstrike` cooldown: **8s** (Classic 20s) — a large uptime change for Enhancement's core
  ability.
- New talent: **Rage of the Farseer** (Enhancement) — a self-buff granting +30% melee haste and
  +30% spell haste for 25 sec, functioning like a personal Bloodlust/Heroism. No Classic
  equivalent; cooldown isn't published (provisionally modeled at 3 min).
- New ability: **Lava Burst** (Elemental) — a guaranteed-crit-adjacent nuke, +20% damage vs. an
  active Flame Shock. No Classic equivalent.
- New mechanic: **Maelstrom Weapon** (Enhancement) — landed melee hits have a (provisional, 20%)
  chance to grant a stack, up to 5, each cutting Lightning Bolt's cast time and mana cost by
  4%/rank (free and instant at 5 stacks/max rank). No Classic equivalent.

### Warlock
- `Conflagrate` no longer unconditionally consumes Immolate — `Shadow and Flame` gives a scaling
  (20%/rank, 100% at rank 5) chance to preserve it.
- New ability: **Incinerate** (Destruction) replaces Shadow Bolt as the spec's filler nuke, +25%
  damage vs. an active Immolate. Its spell-power coefficient is provisional (0.571,
  Shadow-Bolt-comparable) — Blizzard hasn't published the real number.

### Hunter
- `Aimed Shot` cast time: **2.0s** at rank 3 (Classic 3.0s).
- `Multi-Shot` cooldown: **6s** (Classic 10s), and it no longer shares a cooldown with Aimed Shot.
- **Survival rebuilt as a full melee spec** — the single biggest non-Paladin redesign in Forever.
  New kit: `Mongoose Bite` (dodge/Expose-Prey-gated), `Strider Kick` (talent-gated instant),
  `Raptor Strike` (next-swing melee, provisional damage — Forever's own tooltip isn't in this
  project's dataset), and `Lacerating Strikes` (a bleed DoT off Mongoose Bite). No Classic
  Survival kit resembles this at all.
- New ability: **Summon Hawk** (Beast Mastery) — initial hit plus a continued assault (modeled as
  a DoT; the assault's real tick rate isn't published). Shares a cooldown with Arcane Shot.
- Pets have **no stat inheritance** in Forever/Classic (confirmed via WoWSims Classic's
  `pet.go`) — this sim previously had a fabricated attack-power term roughly doubling pet swing
  damage; removed outright 2026-09-18, not replaced with a better guess.

### Rogue
- New ability: **Mutilate** + **Venom** (Assassination) — a dual-weapon builder (0.75× normalized
  weapon damage + 13/hand, +20% with Deadly Poison ticking) that replaces Backstab/Sinister
  Strike as the spec's opener. No Classic Assassination kit resembles this.
- New talent: **Restless Blades** (Combat) — damaging finishers cut the remaining cooldown on
  Adrenaline Rush/Blade Flurry by 2s per combo point spent.
- New talent: **Thousand Cuts** (Subtlety) — Rupture ticks grant stacks (up to 5) that discount
  the Energy cost of the next Hemorrhage/Backstab.
- `Hemorrhage` carries a Forever-sourced damage value, retuned from Classic.

### Mage
- New mechanic: **Arcane Blast** + **Missile Barrage** (Arcane) — Arcane Blast stacks a self-buff
  (up to 4, 8s) boosting every other spell's damage 10%/stack, at 175%/stack scaling mana cost;
  Missile Barrage gives Arcane Blast/Fireball/Frostbolt casts a chance to make Arcane Missiles
  free and double-speed. No Classic Arcane rotation resembles this.
- New mechanic: **Pyroblast** + **Hot Streak** (Fire) — non-periodic crits build stacks (up to 3,
  15s) that cut Pyroblast's cast time up to 75%. Pyroblast itself predates Forever as a real
  Classic Fire talent (its direct-damage/DoT numbers are Forever-sourced; cast time/cost/DoT
  coefficient are provisional, taken from vanilla Classic's rank-8 Pyroblast as a
  better-grounded placeholder than a same-spec-nuke guess). Hot Streak has no Classic equivalent.
- New mechanic: **Ice Lance** + **Fingers of Frost** + **Shatter** (Frost) — Frostbolt hits have a
  flat (not rank-scaled) 15% chance to grant up to 2 charges, each next Ice Lance treating the
  target as Frozen for +300% damage; Shatter (previously a dead 3/3 talent with no coded effect)
  adds its crit bonus to Ice Lance while a charge is up. No Classic Frost rotation resembles this.

---

## What's still genuinely unknown

- Whether Warrior Protection or Feral Druid tanking got any Forever-specific threat redesign at
  all, or whether Paladin is the outlier that got special attention. Not sourced either way.
- **No Druid-specific Forever ability retuning has been sourced at all** (Moonfire, Starfire,
  Wrath, Rip, Ferocious Bite all still run on plain Classic values) — Druid hasn't been audited
  to the depth the other seven classes have.
- Gear set-bonus changes (above) are confirmed only for Paladin's three dungeon/tier sets;
  Blizzard's gear-set post likely covers other classes too, but this project hasn't
  cross-checked them yet.
- Several provisional values (Raptor Strike's damage, Arcane Blast's cast time/cost, Incinerate's
  coefficient, Summon Hawk's continued-assault tick rate) are placeholders pending a real
  Blizzard/Wowhead source — don't cite these as confirmed Forever numbers.
- The original ground-floor audit (`AUDIT_2026-09-17.md` section 5, "Missing or unresolved
  mechanics") predates the current event-driven engine rewrite and is largely stale, but a few
  items in it (combo points, DoT snapshotting, glancing blows, dual-wield miss penalty) are still
  real gaps in the shared 21-spec engine as of this writing — check that section before assuming
  something's modeled.

*Last updated 2026-09-18. Update this doc whenever a Forever-vs-Classic mechanic gets newly
sourced or corrected — keep it in sync with `AUDIT_2026-09-17.md`'s resolution log rather than
letting the two drift apart.*
