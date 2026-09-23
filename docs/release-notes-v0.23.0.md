**Protection and Retribution Paladin threat/damage fix — v0.23.0 is live**

This release fixes a real damage/threat bug affecting both Paladin specs:
• Seal of Fury and all three Judgements (Fury, Righteousness, Command) were missing their flat base damage, applying only the spell-power scaling. Since Paladins gear for stamina/defense rather than spell power, this was the dominant part of each ability, not a rounding error.
• Protection: Seal of Fury and Judgement of Fury threat roughly tripled each; total TPS +19%, DPS +13% on the default preset.
• Retribution: Judgement of Command and Judgement of Righteousness damage roughly quintupled each; total DPS +6.7% on the default preset.
• Verified against the beta client's own tooltip data (wago.tools, build 1.60.1.69913) rather than assumption — all three seals' existing spell-power coefficients already matched the client exactly, confirming the flat base was the only missing piece.

Righteous Fury (+90% Holy-only threat), Iron Creed, and Holy Shield were checked against the same source and are unchanged.

Validation: 113 tests, 23/23 specs at 0.000% Python/Rust parity, and 69 browser-engine scenarios (83,570 numeric checks) all passed against the rebuilt WebAssembly engine.

**Still early alpha:** some Forever mechanics and proc rates remain unconfirmed. Unsupported effects and assumptions are shown in results. Default builds are baselines, not proven BiS rankings.

Try it: https://foreversims.com
