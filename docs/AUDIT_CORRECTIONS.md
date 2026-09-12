# Audit correction disposition — 12 September 2026

The approved audit contained 22 findings. This change corrects reproducible implementation defects and removes unsupported claims. It does **not** turn incomplete public documentation into a fully validated STFC simulator. Several findings are mitigated by explicit exclusions and honest scope labels; the remaining modelling work is listed below, rather than described as completed.

## Changes by finding

| Finding | Implemented correction | Remaining evidence or functionality |
|---|---|---|
| F01 Target identities | 44 exact family/class templates and 527 distinct cached hostile variants; strict level/ID selection in API and CLI; refresh builder uses the same identity rules. Removed wrong Actian/Gorn, Borg and generic-wave substitutions. | Current catalogue refresh and complete hostile abilities. |
| F02 Academy bonuses | Separate hull classes, published critical bonuses/floors and class-specific modifiers; correct Ops gate. | Historical magnitudes are flagged pending calibration after the Update 91 rebalance. |
| F03 Officer conversion | Ship-specific capped bonus tables; Attack/Defense/Health affect ship categories; uncapped officer totals retained separately. | Interpolation and stat-category mapping require ship-screen/log comparison; stat-dependent abilities remain partial. |
| F04 Double buffs | Sheet imports tag calculated officer stats as account-adjusted. Base, adjusted and unknown provenance are distinguished; no second research multiplier on adjusted values. | Legacy manual profiles need their provenance confirmed; no silent rewriting of saved accounts. |
| F05 Shields | Separate hull/shield pools, absorption and overflow; distinct input fields and actual damage units. | Default 80% absorption and special shield interactions require calibration. |
| F06 Mitigation | Combat-class coefficients corrected to 0.55/0.20/0.20; Survey coefficients added; finite/nonnegative checks and zero-stat behaviour. | Logistic formula remains an empirical community model. |
| F07 Ability coverage | Unsupported effects no longer gain numerical shortlist credit through descriptive keywords; omissions appear in every result. | Full officer trigger/condition coverage is not implemented. |
| F08 Hugh | Rank-dependent proc chance, one event per received weapon, additive two-round stacks; tested with a multi-shot weapon and a gap between firings. | Confirm exact event ordering against real logs. |
| F09 Synergy | Captain-specific base and synergy increments, independent of rank; unknown classes cannot manufacture full synergy. | Most captain maneuvers are explicitly omitted from numerical combat until modelled. |
| F10 Cascade | Ordinary Isolytic and Cascade are separate values and tracks; source classifications corrected. | Combined formula is labelled community-derived and provisional. |
| F11 Critical Mitigation | Source scope includes exact drone family; no invented Duo entry requirement; Toryn and typed sources can contribute points; initial displayed reduction includes active crew/source contributions. | Conversion curve and Isolytic interaction remain provisional. No claim of complete source catalogue. |
| F12 Research | Preserve individual node/buff IDs, native units, highest completed level and source ownership. Decimal fractions are not divided by 100. Reimport preserves reviewed mappings and never overwrites unrelated manual totals. | Imported effects remain quarantined until scope is reviewed. This deliberately replaces unsafe automatic text classification. |
| F13 Shred/ship bonuses | Player Shred works against enemy Apex. Ship and scoped source bonuses have explicit inputs. | Ship-specific passives and conditional refits are not comprehensively implemented; warnings state this. |
| F14 Weapons/events | Per-weapon warmup/cooldown/shots, no dead-unit retaliation, timed proc/repair events, explicit aggregate fallback. | Full morale/burning/hull-breach chains, every trigger and simultaneous firing semantics remain uncalibrated. |
| F15 Hostile specials | Exact per-class data, immunity and explicit missing-mechanic notices; no implication that descriptive notes are simulated. | Xindi, V’Ger, Krenim and other special counters need richer data and event rules. |
| F16 Decay | Stabilizer offsets explicit decay; no invented Swarm decay; direct hull damage separated from ordinary damage. | Current special-ship exemptions and encounter-specific decay bases need logs. |
| F17 Level caps | Removed the invented 90% whole-officer penalty. Known legacy restrictions are flagged per ability; Leslie’s captain level limit is explicit. | Exact revised legacy cap magnitudes remain unverified and are excluded. |
| F18 Mission modes | Removed fictional wave enemies and renamed multi-unit/event modes as individual-encounter estimates. Surveys are no longer universally excluded. | Complete waves, coordinated armadas, station platforms, hauling and anomaly-state/reward simulation are not implemented. |
| F19 Ranking | Feasibility/kill/survival precede final model score; no 75% heuristic blend. Below-deck selection re-evaluates marginal benefits against ship stat caps. | Search remains bounded and greedy; no proof of global optimum, joint exhaustive search or loot-per-flight objective. |
| F20 Results | Actual damage units, kill-only time-to-kill, explicit timeout rate, Wilson sampling intervals, missing-mechanic disclosure and shared renderer values. | Sampling intervals do not measure model error; no live win-rate claim. |
| F21 Provenance | Normalized officer lookup and unambiguous ship aliases; actual slot tables/explicit overrides; removed legacy Syndicate slot addition. | Historic officer identity/class metadata still needs confirmation for some imports. |
| F22 Stale snapshot | Update 94 Toryn/Trelane overlays; Neelix/Harry Kim migration flagged rather than blindly moving ownership/rank; source and snapshot limitations exposed. | This is not a complete live-game catalogue. |

## Validation

The regression suite exercises synthetic cases for damage routing, timed Hugh procs, weapon warmup, source scopes/units/duration, import idempotence, shield and stat inputs, exact hostile identity, wrong-source exclusion, API validation and desktop launching. The browser smoke test uses a temporary synthetic account with sheet sync paused; it checks recommendations, ship/account edits, and mobile layout. Documentation screenshots contain synthetic data only.

Final validation: **199 tests passed in both the application and GitHub checkout**; Ruff and whitespace checks passed. The isolated Chrome smoke test passed desktop recommendations, ship/account saves and a 390-pixel mobile layout, with no JavaScript errors. Six synthetic screenshots were refreshed. Windows executable packaging requires the Windows CI runner; these macOS checks do not certify a newly built Windows binary.

## Input changes

- Enter **hull and shield health separately**, and enter ship critical chance, critical multiplier, Cascade, Shred and Stabilizer when known.
- Use an **exact hostile variant ID** when several enemies share the same name/class/level.
- Officer values from the Officers Tool are already adjusted for the account. Legacy values of unknown provenance are treated as adjusted and produce a warning.
- Review research sources in the advanced Account editor. A reviewed source needs a supported effect, native unit, explicit contexts and any restrictions. Do not enable a source whose bonus is already included in the account totals.
- Source records support scoped Critical Mitigation, Apex, Isolytic and other implemented effects. Non-base-stat sources can expire after a specified number of combat rounds. Unsupported conditions remain excluded.

## What is needed for full accuracy

Real, reproducible battle logs with exact ship builds, officer ranks, account buffs, target IDs and weapon events are needed to calibrate the remaining curves and timing. Full mission simulation also requires explicit multi-ship state, waves, station defenses, event phase and loot/cargo objectives. These are unresolved modelling requirements, not defects that can be safely filled with guessed constants.

Sources and formula conventions are linked in [RULES.md](RULES.md). The original read-only audit remains unchanged in the workspace reports folder. The saved account, live sheet URL, logs and private backups are excluded from the GitHub checkout.
