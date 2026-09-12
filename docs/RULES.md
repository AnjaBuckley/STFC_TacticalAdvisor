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
