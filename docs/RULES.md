# Mechanics audit — 12 September 2026

The user asked for current STFC rules. The live documentation corrects several assumptions in the older AGENTS.md examples. This implementation retains compatible interfaces where possible, but does not claim complete fidelity to the live game.

## Source-backed corrections

- [Scopely's Isolytic Damage documentation](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/7300-isolytic-damage/): calculate the independent track from total outgoing standard damage, before applying the defender's ordinary mitigation.
- [Update 65](https://startrekfleetcommand.com/news/update-65-gorn-invasion-pt-1/): Gorn **Hunters** are immune to all non-isolytic damage. The other names in the curated Gorn dataset have not been independently verified and do not inherit this property just from their category.
- [Apex Barrier](https://startrekfleetcommand.com/news/new-battle-stat-apex-barrier-modifier/): 10,000 points add 100% effective health. The model applies it exactly once through effective HP, including against incoming isolytic damage. An explicit enemy Apex Shred fraction reduces the barrier first.
- [Remote Campus and Critical Mitigation](https://startrekfleetcommand.com/news/starfleet-academy-remote-campus-critical-mitigation/): the worked example of 83,000 points and 62.41% reduction is consistent with `points / (points + 50,000)`. This curve is an **inference from the worked example**, not an assumption that 500 points always adds one percentage point of reduction.
- [Update 90](https://startrekfleetcommand.com/news/patch-notes-update-90-starfleet-academy-part-1/): Matter Beam mitigation is documented for PvP, not universally. Remote Campus applies to Academy encounters. Simulacrum eligibility is specific to ships. Academy content begins at Ops 61. Explorer Academy drones have non-isolytic immunity.
- [Update 91](https://startrekfleetcommand.com/news/patch-notes-update-91-starfleet-academy-part-2/): Academy stats were adjusted. Old published magnitudes must not be represented as guaranteed current values.
- [Update 94](https://startrekfleetcommand.com/news/patch-notes-update-94-cause-and-effect/): conditional station research and event anomalies add mechanics beyond the earlier Update 90 specification. They are disclosed as unsupported rather than invented.

## Profile compatibility

New fields under `research.critical_mitigation` are `remote_campus_points` and `programmable_matter_beam_points`. Ships accept `crit_mitigation_points`. These are **points**, not percentages. An explicit zero takes precedence over the old field. The old `remote_campus_bonus`, `programmable_matter_beam_value`, and `crit_mitigation_bonus` remain effective decimal reductions. Mixed profiles add the resolved point reduction and legacy effective override, clamp to 100%, and expose `legacy_override: true`. This is a compatibility estimate, not verified mixed-unit game stacking. The interface labels legacy values and offers point migration; it never silently rescales user data.

## Search and simulation

All three captain assignments are evaluated per triplet within a maximum 40-officer shortlist. Abilities are scored for their assigned station and target scope. Unknown and unavailable officers do not become hypothetical owned officers. Below deck is a separate pass and excludes the bridge. No unowned fallback ship is created. The result remains a **heuristic recommendation**, not a proof of a global optimum.

Supported unconditional per-rank effects (OA and BDA) enter numerical simulations. Inferred conditions, unsupported effects and CM arrays with ambiguous synergy semantics are reported in `unmodelled_abilities`. This avoids treating captain synergy entries as officer promotion tiers. A CM/BDA is never activated from the wrong seat. The numerical model still approximates officer stats, shields, simultaneous round exchanges and weapon firing; this is visible in each result.

Outgoing ordinary damage is reduced using available target defense statistics; isolytic damage bypasses ordinary defense and respects isolytic defense. Both tracks respect target Apex. Incoming Apex is represented by effective HP exactly once. Critical reduction applies to critical hits only. Explicit incoming isolytic and per-round decay parameters can be supplied from a log. The reported damage trace is the first round of the first seeded simulation, not an average or a claimed live-game battle log.

## Boundaries

The existing logistic mitigation model and ship class coefficients are retained under the project constitution; they are not represented as freshly verified game formulas. Building scope, artifacts, forbidden tech, active buffs, weapon timing, shield absorption, regeneration, critical floors, state transitions, full captain maneuver scaling and every officer's trigger need a richer event-based simulator and battle-log fixtures. Station platforms, multiple waves, allied ships, anomaly schedules and travel/warp constraints are not modelled. The rules view and result warnings make these limits explicit.

## Combat triangle and baseline PvP crews

[Scopely's SNW crew examples](https://startrekfleetcommand.com/news/snw-james-t-kirk-takes-the-captains-chair/) confirm Interceptor vs Battleship, Battleship vs Explorer, and Explorer vs Interceptor. The old project's counter map was reversed. It is corrected in `pvp_logic.py` and used as a modest heuristic preference, not a universal guarantee. [Scopely's Explorer Strike Team page](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/8439-explorer-strike-team/) identifies Weyoun, Pon and Ikat'ika as the baseline. The Battleship baseline uses the distinct Strike Team officer variants. Core strike-team bridge kits are not given their offensive/defensive heuristic scores on an incompatible player ship class.
