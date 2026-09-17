# Cross-spec validation matrix

60 iterations, 120 seconds, Phase 1-2 default gear, default 51-point builds, full compatible raid buffs, default consumables, no world buffs. No calibration multipliers are applied.

| Spec | DPS | TPS | No gear | No talents | No buffs | Starved | WoWSims (world-buffed) | Ratio | Result |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| warrior-arms | 809.2 | 762.1 | 211.4 | 516.5 | 380.9 | 0% | None–None | n/a | PASS |
| warrior-fury | 889.3 | 853.8 | 238.9 | 498.1 | 412.6 | 0% | 1454–1807 | 0.545 | PASS |
| warrior-protection | 328.1 | 830.0 | 183.2 | 254.2 | 217.8 | 0% | 385–416 | 0.819 | PASS |
| druid-balance | 367.1 | 367.1 | 205.0 | 227.8 | 170.7 | 30% | 217–242 | 1.599 | PASS |
| druid-feral-dps | 418.9 | 297.4 | 308.6 | 264.5 | 241.1 | 0% | 475–568 | 0.803 | PASS |
| druid-feral-tank | 314.0 | 811.7 | 238.8 | 221.6 | 218.2 | 0% | None–None | n/a | PASS |
| hunter-beast-mastery | 550.7 | 550.7 | 331.0 | 423.2 | 398.9 | 0% | 457–475 | 1.182 | PASS |
| hunter-marksmanship | 597.1 | 597.1 | 355.3 | 462.2 | 397.7 | 43% | 457–475 | 1.281 | PASS |
| hunter-survival | 588.4 | 588.4 | 356.7 | 451.5 | 401.0 | 46% | 457–475 | 1.263 | PASS |
| mage-arcane | 408.2 | 408.2 | 237.7 | 237.3 | 268.0 | 0% | 473–521 | 0.821 | PASS |
| mage-fire | 658.5 | 658.5 | 320.1 | 311.3 | 321.3 | 10% | 473–521 | 1.325 | PASS |
| mage-frost | 562.5 | 562.5 | 281.3 | 322.7 | 285.5 | 0% | 473–521 | 1.132 | PASS |
| priest-shadow | 486.8 | 340.8 | 389.7 | 157.4 | 387.0 | 0% | 483–504 | 0.986 | PASS |
| rogue-assassination | 660.7 | 469.1 | 255.7 | 466.0 | 397.3 | 0% | 1018–1221 | 0.59 | PASS |
| rogue-combat | 725.1 | 514.8 | 264.6 | 491.4 | 421.5 | 0% | 1018–1221 | 0.648 | PASS |
| rogue-subtlety | 628.8 | 446.5 | 240.6 | 291.0 | 358.4 | 0% | 1018–1221 | 0.562 | PASS |
| shaman-elemental | 415.8 | 401.8 | 210.5 | 246.6 | 200.0 | 29% | 524–583 | 0.751 | PASS |
| shaman-enhancement | 591.0 | 591.0 | 270.1 | 368.9 | 343.4 | 0% | 609–669 | 0.925 | PASS |
| warlock-affliction | 671.6 | 544.4 | 402.4 | 397.8 | 476.3 | 0% | 1008–1052 | 0.652 | PASS |
| warlock-demonology | 598.7 | 488.2 | 403.4 | 439.1 | 463.2 | 0% | 878–920 | 0.666 | PASS |
| warlock-destruction | 641.0 | 519.8 | 387.9 | 383.7 | 464.3 | 0% | 878–1052 | 0.664 | PASS |

## Focused checks

- PASS - hunter pet contributes: 612.7 vs 468.3
- PASS - imp casts firebolt continuously: 35.0 casts in 60 s
- PASS - warlock pet selection changes output: succubus 667.5, imp 647.3
- PASS - tank gear reduces incoming damage: 327.8 vs 634.5
- PASS - fire mage casts fireball as its primary spell: Fireball 31.6, Scorch 17.6
- PASS - combat rogue builds combo points before finishing: SS 34.4, Eviscerate 3.8

## Reading the table

The WoWSims column lists the checked-in WoWSims Classic test fixtures. Those runs use the Phase 5 test buff package with every world buff (Rallying Cry, Songflower, Zandalar, Warchief's, DMF, Dire Maul), Blessing of Kings/Sanctuary/Wisdom and P1 talents/APLs. The Forever defaults exclude world buffs, so ratios of roughly 0.6–0.9 are the expected envelope; the ratio is informational and is not a pass/fail criterion. Pass/fail comes from the mechanic checks: gear, talents and buffs must each raise DPS, the breakdown must reconcile, white melee must show glancing blows at the level-63 rate, cast counts must respect cast times, energy spending must respect the tick budget, and tanks must take damage and generate more threat than damage.
