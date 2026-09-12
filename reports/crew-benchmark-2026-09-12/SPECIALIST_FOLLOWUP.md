# Specialist mechanics follow-up — 12 September 2026

The model has broader coverage, but remains uncalibrated. These changes do not establish that Borg, Xindi or general PvP predictions match the live game.

## Changes

- Trip reduces enemy critical damage rather than contributing Critical Mitigation points. Trip and Archer trigger once per damaging weapon attack and retain two-round stacks.
- Borg officer stat bonuses feed the ship officer-bonus curves. Five uses officer health for defenses. Seven's extra shots require Borg Tactical Probe, never Borg Assailant.
- Explorer PvP models morale-dependent round effects, Ransom's Cascade, and Pon's defending condition. Weyoun's original official notes and export disagree on timing; the provisional export interpretation is disclosed.
- Combat and Loot priorities separate supported loot bonuses from ordinary combat scoring. Both prioritize kill/survival feasibility; neither estimates full-flight loot.
- Explicit weapons can carry individual critical chance/multiplier overrides, preserving explicit zero and falling back to ship/target values when omitted or null.

## Current synthetic comparisons

| Case | Exact published captain/crew rank | First recommendation |
|---|---|---|
| swarm_35 | Outside top 10 | SNW Pike / Moreau / SNW Spock |
| borg_40 | Outside top 10 | Eight Of Eleven / Seven Of Eleven / Nine Of Eleven |
| gorn_60 | 1 | Kathryn Janeway / Ent-E Data / Ent-E Picard |
| actian_40 | Outside top 10 | SNW Pike / Moreau / Chen |
| xindi_48 | Outside top 10 | SNW Pike / Trip Tucker / Moreau |
| pvp_explorer | 1 | Weyoun / Jack Ransom / Pon |
| swarm_wave | Outside top 10 | SNW Pike / Moreau / SNW Spock |
| borg_40_loot | 8 | Eight Of Eleven / Five Of Eleven / Seven Of Eleven |
| xindi_48_loot | 6 | Jonathan Archer / Trip Tucker / Moreau |

These are equal-rank, artificial account comparisons, not live battle reproductions. Fixture class/group metadata was corrected in this phase. Therefore these results are not a pure engine-only comparison to the earlier controlled run. Loot rows also use a different objective. PvP and Gorn match the referenced crew at rank one; several others remain outside the top ten. Published crews are examples, not universally optimal solutions.

## Xindi encounter evidence and remaining work

The saved [public export](xindi-2855506446-public-export.json) was fetched from https://data.stfc.space/hostile/2855506446.json on 12 September 2026. It contains six weapons: five with ten shots, a sixth with nine shots; one weapon has guaranteed criticals with multiplier 10, while others differ. Aggregating them loses mechanics that matter to Trip, Chen and NX-01.

This raw export is evidence, not an automatically enabled catalogue override. Its warm-up/cooldown units, weapon type mapping and additional hostile ability IDs need verified translation before import. The existing benchmark still uses aggregate hostile attacks; the new per-weapon critical fields are covered by deterministic tests instead. Do not read current Xindi rankings as validated.

Next calibration needs exact target ID, ship tier/components, officer ranks, account bonuses and round-by-round battle logs. Resolve Weyoun timing, Seven proc cadence, fractional shot rounding and durations. Other PvP strike teams, complete status interactions, ship passives, travel/cargo and loot-per-flight remain outside full coverage.

## Verification

All 218 regression tests passed; Python lint, JavaScript syntax, Git whitespace checks and synthetic desktop/phone planner checks also passed. Two dependency deprecation warnings remain. The UI roundtrip forwarded Loot priority, and switching to PvP reset it to Combat and disabled Loot. No live account data was used. See RULES.md for primary-source links and provisional assumptions.
