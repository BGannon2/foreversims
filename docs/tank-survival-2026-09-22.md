# Tank survival corrections — 2026-09-22

Warrior and Bear iterations previously continued after death, counting subsequent damage and healing against the original time alive. Iterations now stop at the lethal hit, including when a heal is scheduled for that same timestamp. Incoming rage uses the level-60 player conversion, and blocking requires an equipped shield.

Tank encounter settings now expose raw physical swing damage, swing interval, incoming attacker count, healing amount, and healing interval. Incoming attackers are independent of outgoing target count. Zero healing provides an unhealed survival scenario. This is a simplified physical-melee and fixed-healing model, not a complete raid boss or healer simulation.

Results distinguish full-encounter DTPS from damage per second alive and show time alive, survival fraction, peak three-second damage, damage taken, healing, and overhealing. The shared engine also reports ending health. Paladin results expose their existing healing and damage totals. Variable-duration damage breakdowns use each iteration's actual duration.

Validation: 128 Python tests; 82 browser WASM profiles and split-worker merges (97,578 numeric checks); Ruff, ESLint, and Clippy. Browser checks covered an unhealed Warrior death and a healed Protection Paladin. Regenerated 70 Warrior/Bear comparison rows at 300 iterations.

The Cloudflare build failure was separate: its dependency detector attempted `pip install .` because a Ruff-only pyproject.toml existed. Moving those lint settings to ruff.toml preserves linting without falsely declaring an installable Python package. The Cloudflare build for commit 55ffb20 succeeded.
