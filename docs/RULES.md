# Mechanics and coverage — 12 September 2026

This is a partial, uncalibrated combat model. See [audit corrections](AUDIT_CORRECTIONS.md) for the disposition of all 22 findings. Passing tests establishes internal behaviour; it does not establish agreement with the live game.

## Implemented calculation conventions

- Base ship stats receive additive bonuses in their own category. Officer points use the ship catalogue’s capped officer-bonus curves. Interpolation between exported thresholds is provisional. `stat_basis: account_adjusted` officer values are not multiplied by account bonuses a second time; `base` values are. Unknown provenance is disclosed.
- Hull and shield pools are distinct. Default shield absorption is a disclosed 80% model assumption; overflow reaches hull. A dead unit does not fire. Weapon schedules may specify `damage`, `shots`, `warmup` (rounds before first shot), and `cooldown` (round interval). Missing schedules become one disclosed aggregate attack per round.
- Standard mitigation uses the community logistic model and weights 0.55/0.20/0.20 for combat classes, 0.30/0.30/0.30 for Survey. The model is empirical, not an official published formula. The 65% warning is an advisory threshold.
- Ordinary Isolytic damage starts from pre-mitigation damage. Cascade remains separate, with the provisional combined formula shown in the app. Both tracks pass through Apex once. Critical reduction affects critical hits only; its interaction with Isolytic damage is not established.
- Critical Mitigation points use the provisional `points / (points + 50000)` curve. Legacy decimal overrides remain explicitly identified; they do not become points automatically. Scope is evaluated against the selected ship and actual enemy family. Simulacrum does not apply to Combat Drones simply because they are Academy enemies.
- Synergy uses captain-specific base/small/large increments. Captain promotion does not choose a different synergy-array entry. Unknown classes leave the maneuver value unconfirmed.
- Hugh uses a chance per received weapon attack, not a permanent critical chance. Seska, Suder and PIC Hugh have selected timed/repair rules. Unsupported status, captain and ship abilities are omitted with warnings. Decay accepts an explicit stabilizer offset; it is never added to ordinary Swarm targets merely from their name.

## Source registry and imports

`combat_sources` is a list of attributed values on a profile or ship. Use `status: manual` or `reviewed`, `effect`, `unit`, `contexts`, optional `conditions`, and a unique `id`. Fractions use 1 for 100%; Apex and Critical Mitigation use points. Examples of contexts: `pve`, `pvp`, `station`, `armada`, `wave_defense`. Conditions can constrain ship name/class or target family/class/ID/faction. Supported non-base-stat effects may have a round duration. Do not duplicate bonuses already entered in account totals.

Research CSV imports preserve each node/buff ID, completed level and raw source unit. They no longer divide decimal percentages by 100, classify every buff by one node-name regex, or overwrite unrelated manual totals. Unreviewed imports remain quarantined until their scope and effect are confirmed in the advanced account editor. Reimporting is idempotent and preserves reviewed mappings. Officer-sheet sync keeps its existing one-way ownership/progression behaviour and tags its calculated stats as account-adjusted.

## Estimates and mission boundaries

Exact enemy family, class, level and ID are required for catalogue encounters. No nearby enemy or generic wave is substituted. Academy source magnitudes may reflect historical published bonuses and require current logs after rebalancing.

The optimizer evaluates captain placements within a shortlist, simulates finalists, and ranks feasibility before numerical score. Below-deck choices re-evaluate capped marginal stat benefits; the search is not a proof of optimality. Unsupported effects receive no invented whole-crew benefit. Time-to-kill is absent when no run kills the target, timeouts are distinct, and Wilson intervals quantify sampling uncertainty only.

Wave, Duo, Dreadnought, station and anomaly contexts estimate an individual encounter. Allied targeting, complete waves, station platforms, cargo hauling, travel, loot per flight and anomaly phase/reward state are not represented. No complete-mission success claim is made.

## Evidence

- [Scopely Isolytic documentation](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/7300-isolytic-damage/)
- [Scopely Apex Barrier](https://startrekfleetcommand.com/news/new-battle-stat-apex-barrier-modifier/)
- [Critical Mitigation worked example](https://startrekfleetcommand.com/news/starfleet-academy-remote-campus-critical-mitigation/)
- [Update 90 source scopes](https://startrekfleetcommand.com/news/patch-notes-update-90-starfleet-academy-part-1/)
- [Update 91 rebalance](https://startrekfleetcommand.com/news/patch-notes-update-91-starfleet-academy-part-2/)
- [Hugh, Update M50](https://startrekfleetcommand.com/news/update-m50-patch-notes/)
- [Seska and Suder, Update 75](https://startrekfleetcommand.com/news/patch-notes-update-75-year-of-hell-part-2/)
- [Legacy caps, G7 notes](https://startrekfleetcommand.com/news/the-margins-g7-patch-notes/)
- [Update 94 identities and sources](https://startrekfleetcommand.com/news/patch-notes-update-94-cause-and-effect/)
- [Community mitigation calculator](https://stfc-toolbox.vercel.app/)

These sources establish selected mechanics and restrictions, not a complete or internally consistent combat specification. Exact ordering, curves and stacking still require real battle-log regression fixtures.

## Crew benchmark follow-up — 12 September 2026

- Chen and T'Laan now apply the exported rank values only to explicitly typed energy/kinetic enemy weapons, in eligible hostile contexts through level 51. Aggregate weapons remain unresolved and generate a warning.
- Moreau reduces the three hostile piercing stats within the existing empirical mitigation model through level 70. Pike in the captain seat amplifies these three reviewed legacy officer abilities using his synergy curve. Other Pike interactions remain disclosed as unsupported. This is an estimate, not a calibrated reproduction of stacking against existing enemy buffs.
- Nonconditional captain maneuvers with already supported effects now use the captain's synergy value. Generic mitigation, status chains and other unsupported maneuvers remain omitted; no arbitrary name/seat bonus forces a particular crew.
- NX-01 Polarized Hull removes nine shots from each explicitly scheduled Xindi-Aquatic Cruiser weapon in ordinary PvE. Aggregate schedules receive no inferred deflection. Ship damage/passive magnitudes and other mission contexts remain unresolved. [Scopely NX-01](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/7830-enterprise-nx-01/).
- Ranking no longer rewards fewer unmodelled abilities. It distinguishes short kill durations and retained hull. These scoring weights are product heuristics, not game formulas. Uncertainty is retained in the recommendation metadata and omissions.
- Legacy effect conditions are taken from the checked-in STFC Space export descriptions (ability IDs 56, 62, 128, 182). Public pages may require JavaScript: [Pike](https://stfc.space/officers/329940464), [T'Laan](https://stfc.space/officers/1455040265). The ability magnitudes retain their export-estimate status.

## Borg, Xindi and Explorer PvP follow-up

Trip Tucker now decreases the enemy critical multiplier, once per damaging received weapon attack, with two-round stacks and the target critical floor preserved. It is not Critical Mitigation points. Archer's critical damage increase uses the same received-weapon timing; his Xindi captain loot bonus is separate. [Trip, Update 62](https://startrekfleetcommand.com/news/update-62-patch-notes-enterprise-pt-1/) and [Archer, Update 63](https://startrekfleetcommand.com/news/update-63-patch-notes/). The proc follows the complete weapon attack, never each shot; current round counts toward duration. That expiry convention needs live-log confirmation.

Borg officer attack/defense/health bonuses now affect officer totals before the ship's stat curves. Five's captain maneuver adds a percentage of total officer health to armor, deflection and dodge. Seven's extra shots require the exact Borg Tactical Probe name, with chance read from the chance field rather than the shot magnitude. One combat-start proc is a provisional timing assumption. Borg Assailant is not silently treated as a Probe. Data: checked-in STFC Space officer records 3583932904, 3304441016, 1131760724 and 1859906553. Supplied officer totals and their interaction with already-applied research still require calibration.

Explorer PvP now evaluates captain morale before morale-dependent officer effects, expiring weapon damage/shot/critical chance stacks by round. Jack Ransom provides Cascade, not ordinary Isolytic Damage. Pon's captain delay requires explicit `is_defending: true` on the ship. [Update 48](https://startrekfleetcommand.com/news/update-48-patch-notes/) and [Ransom, Update 58](https://startrekfleetcommand.com/news/update-58-lower-decks-ii-part-1/). Weyoun's export says round-start morale for three rounds whereas original patch notes say combat-start/eight rounds: the model uses the export and reports this conflict. Fractional shots use floor rounding. These are provisional event models; other strike teams and general status interactions remain incomplete.

The planner offers Combat and Loot priority. Both sort kill and survival feasibility first. Loot then multiplies the relative combat score by `1 + supported loot bonus`; this is a documented product heuristic, not a game formula or a prediction of actual drops. Travel, cargo and full-flight yield are not simulated. API clients can send `objective: combat|loot`; default is combat, and PvP/raids reject loot mode.

Explicit weapon schedules also accept optional `crit_chance` and `crit_multiplier`. Omitted/null values inherit the combatant values; zero chance remains zero. This preserves different critical profiles within one encounter. The saved Xindi export and remaining importer uncertainties are documented in [the specialist report](../reports/crew-benchmark-2026-09-12/SPECIALIST_FOLLOWUP.md). Raw component schedules are not automatically enabled by this change.
