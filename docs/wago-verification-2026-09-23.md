# Provisional-value audit and item effects — 2026-09-23

Follow-up to `wago-verification-2026-09-22.md`, same method and tooling.

## Build 1.60.1.69977

The data watcher reported Wago build **1.60.1.69977**. Every table this project
reads (Spell, SpellName, SpellEffect, SpellMisc, SpellPower, SpellCooldowns,
SpellLevels, SpellCastTimes, SpellDuration, SpellTargetRestrictions,
SpellCategories) is byte-identical between 69913 and 69977, so the snapshot stays
pinned to 69913 and every value in it also holds for 69977. Re-downloading the
69913 exports reproduces the committed SHA-256 hashes and `wago_verified.json`
exactly.

## Provisional abilities

Before this pass, 40 shared-engine abilities carried free-text provisional notes
(tooltip-derived or placeholder values). 37 now take their numeric fields from
client rows (`tools/wago_audit.py`), for 58 reviewed spells in total. Trigger-spell
damage rows take cost/cast/cooldown from their castable parent (`whole_spell`).
Model assumptions that client data cannot settle stay attached as a `caveat`.

Default-profile impact at one target (race-averaged, 300 iterations): Assassination
+4.2% (Mutilate), Arms −2.8% (Spearing Strike's real 20 sec cooldown), Beast
Mastery +1.9% and Marksmanship +1.5% (ranged attack power gear, Summon Hawk),
Guardian −0.3% (Mangle's 20 rage cost); everything else moved under 0.3%.

Corrections (everything else matched the previous values):

| Ability | Previous | Client (level 60) |
|---|---|---|
| Mutilate rank 4 | 75% weapon + 13 per hand (engine hardcode; the ability data's 17 was never read) | 75% weapon + 67 per hand, now read from the ability data |
| Mangle (Bear) rank 4 | +26, 15 rage | +77, 20 rage |
| Spearing Strike | 20 rage, 6 sec cooldown (placeholder) | 15 rage, 20 sec cooldown |
| Summon Hawk rank 4 dive | 34, 120 mana, 0.15 SP | 108 + 5% RAP, 190 mana, no SP |
| Volley rank 3 | 0.056 SP coefficient (placeholder) | no coefficient |
| Rain of Fire rank 4 | 220 / tick | 221.2 / tick |
| Moonfire rank 10 | 124–146 direct | 129.1–150.1 |
| Wrath rank 8 | 58–64 | 61.8–68.6 |
| Scorch rank 7 | 163–193 | 166.7–196.1 |
| Fire Blast rank 7 | 402–474 | 416.7–489.3 |
| Arcane Explosion rank 6 | 232–252 | 238.9–258.1 |
| Mind Blast rank 9 | 472–498 | 477.1–503.3 |
| Searing Pain rank 6 | 105–123 | 107.2–125.6 |

The damage-range rows are ranks learned below level 60; they now include the
client's per-level growth (capped at MaxLevel), the interpretation already used
for Shadowburn and Conflagrate. Berserk (180 sec / 15 sec), Tiger's Fury,
Rage of the Farseer, Curse of Agony (client name Bane of Agony), Thunder Clap and
Demoralizing Shout cooldowns/costs are now client-confirmed.

Still provisional: **Mangle (Cat)** (spell 407993 has no client effect rows),
**Combustion** and **Demonic Sacrifice** (no numeric client fields to import), and
the Summon Hawk continued assault (a summoned unit; kept at the earlier 34 × 9
placeholder).

## Item effects

`engine_data.ITEM_EFFECTS` holds structured, id-keyed effects for items whose
tooltip text the generic parser missed or misread; both engines read it.
Values come from WoWSims Classic (`sim/common/item_effects.go`,
`sim/<class>/items.go`) with Forever tooltip cooldowns.

- All 66 on-use effects in the catalog resolve: 27 are modeled, 39 are marked as
  having no effect in this fight model (defensive, cosmetic, summons, healing).
  Newly modeled: Earthstrike, Jom Gabbar (5.5-stack average), Eye of Moam,
  Draconic Infused Emblem, Nat Pagle's Broken Reel, Mind Quickening Gem, both
  Hazza'rah's damage charms, Natural Alignment Crystal, The Black Book, Venomous
  Totem, Gri'lek's Charm of Might, Renataki's Charms of Trickery and Beasts,
  Badge of the Swarmguard, Burst of Knowledge, and several damage/mana items.
- Corrected: Second Wind and Mar'li's Eye restored one tick instead of the total;
  Cloak of Fire dealt one tick; Heart of the Scale (a thorns aura) was treated as a
  20-damage nuke; Lapidis Tankard requires sitting.
- On-use stat trinkets share the WoWSims offensive-trinket lockout for the buff's
  duration.
- The catalog importer had copied on-use values into permanent stats: Earthstrike
  (+280 AP), Nat Pagle's Broken Reel (+10% spell hit), Jom Gabbar (+65 AP) were
  always on. Structured uses now own those stats.
- Weapon procs: Ironfoe (2 extra attacks, 0.8 PPM), Felstriker, Bonereaver's Edge,
  Bashguuder/Rivenspike (Puncture Armor, exclusive with Faerie Fire as in WoWSims),
  Dark Iron Sunderer (1 PPM assumed), and life-steal weapons as shadow damage.
- "+N Ranged Attack Power" equip lines were ignored (Rhok'delar, Core Marksman
  Rifle, Swift Flight Bracers, PvP bows); they now apply.
- Set bonuses: The Elements (6) — 4% on spell cast for +95 spell power, 10 sec —
  was the only unmodeled active bonus in the catalog.

Remaining unresolved item text: Hand of Edward the Odd (instant-cast proc), Sword
of Zeal (tooltip split across lines by the importer), and Block/Parry Rating and
unknown "Stat 124/127" equip lines, which need a sourced Forever rating conversion.

## Faction gear — to revisit with better gear evidence

Alliance/Horde-only items are tagged from client reputation factions (`MinFactionID`) and,
for PvP rank gear the client doesn't mark, from the rank title in the name
(`tools/build_item_class_restrictions.py`). Switching race swaps each item to its
other-faction twin: 209 pairs match by name after swapping the title, 439 by identical slot,
armor type, item level, stats and effects (kept only when the pairing is one-to-one).

**Cleanup needed once there's concrete Forever evidence** (vendor lists, datamined item ids):

- The 439 stat-matched pairs are inferred, not sourced (e.g. Grand Marshal's Longsword vs
  High Warlord's Blade style renames).
- 149 faction items stay unpaired and are cleared on a faction switch: Paladin Lamellar PvP
  sets (Alliance-only in Classic, yet Forever allows Undead Paladins), rank items whose stats
  differ between factions, Forever "Premier" items, battleground reputation rewards, items
  with several identical candidates (Silk / Dreadweave / Satin belts), and duplicate catalog
  entries (two "Lieutenant Commander's Lamellar Headguard" ids).
- Faction tags for rank gear are name-based; a client or vendor source would replace them.
