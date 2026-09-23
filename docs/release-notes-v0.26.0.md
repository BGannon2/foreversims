**Client-verified abilities, trinkets and weapon procs — v0.26.0 is live**

**Abilities checked against the game client**
• Every ability still using a tooltip or placeholder value was re-checked against the Forever beta client's own data. 37 more now come straight from the client, bringing the total to 58.
• Mutilate was hardcoded at +13 per hand instead of the client's +67 (Assassination +4.2%).
• Spearing Strike has a 20 sec cooldown, not 6 (Arms −2.8%). Bear Mangle is rank 4 (+77, 20 rage).
• Summon Hawk hits for 108 + 5% ranged AP instead of 34.
• Scorch, Fire Blast, Moonfire, Wrath, Mind Blast, Searing Pain and Arcane Explosion now include the client's per-level damage growth.

**Trinkets, on-use items and procs**
• All 66 on-use item effects are now handled. Earthstrike, Jom Gabbar, Badge of the Swarmguard, Mind Quickening Gem, the ZG class charms, The Black Book, Nat Pagle's and more now actually work.
• On-use stat trinkets share a cooldown the way they do in-game.
• Fixed Earthstrike, Jom Gabbar and Nat Pagle's giving their on-use bonus permanently.
• New weapon procs: Ironfoe, Felstriker, Bonereaver's Edge, Bashguuder/Rivenspike and the life-steal weapons.
• "+Ranged Attack Power" gear (Rhok'delar, Core Marksman Rifle and others) now counts (Hunters +1.5–1.9%).
• The Elements 6-piece bonus is modeled.

**Also since v0.23**
• Protection Warrior gains Thunder Clap (up to 4 targets) and Demoralizing Shout (3+ targets).
• Consecration hits at most 8 targets.
• Tank sims now stop when the tank dies and show survivability stats.

Validation: 132 tests. Python and Rust results match on all 23 specs. The browser engine passed 97,730 numeric checks.

**Still early alpha:** some Forever mechanics and proc rates remain unconfirmed; assumptions are shown in results.

Try it: https://foreversims.com
