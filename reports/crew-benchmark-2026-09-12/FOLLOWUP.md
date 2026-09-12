# Crew benchmark corrections and rerun

Historical first follow-up. See [SPECIALIST_FOLLOWUP.md](SPECIALIST_FOLLOWUP.md) for current results; results.json now belongs to that later run.

12 September 2026. Application improvements implemented; full live-game accuracy remains unverified.

## Implemented

- Removed the ranking advantage for having fewer unmodelled abilities.
- Score now distinguishes every kill duration and values remaining hull when feasibility ties.
- Supported nonconditional captain effects use their own synergy curve and captain seat.
- Chen/T’Laan reduce explicitly typed hostile energy/kinetic weapons through level 51.
- Moreau reduces hostile piercing through level 70; captain Pike amplifies these reviewed legacy defenses. Other Pike interactions remain unsupported.
- NX-01 removes nine shots per explicitly scheduled Xindi-Aquatic Cruiser weapon in ordinary PvE. No shot count is inferred from aggregate damage.

These changes implement known conditions within an estimated simulator. They do not manufacture a score bonus for published crew names.

## Controlled rerun

The first benchmark used actual ship officer-bonus tables on synthetic ship stats. Those combinations produced many trivial victories. The runner now uses an explicitly synthetic uniform officer-bonus table for every ship. All rosters remain synthetic, with manually specified class/group metadata, and cannot substitute for actual account battle logs. Chen and T’Laan's group labels were corrected. Borg Assailant is still a proxy rather than a verified match for the published Borg Probe example.

For a fair comparison, the previous engine and the updated engine were both run with this same revised fixture. `controlled-before.json` records the previous engine; `results.json` records the updated engine. `baseline-results.json` preserves the original experiment. Ordinary Wave Defense was added as an encounter-context check, not as a full mission simulation.

| Case | Exact published crew, previous engine | Updated engine |
|---|---|---|
| Swarm 35 | Outside top 10 | #8 |
| Gorn 60 | #9 | #2 |
| Actian 40 | #8 | Outside top 10 |
| Borg 40 | Outside top 10 | Outside top 10 |
| Xindi 48 | Outside top 10 | Outside top 10 |
| Explorer PvP | Outside top 10 | Outside top 10 |
| Swarm wave encounter | Outside top 10 | #8 |

Agreement improved for Swarm and Gorn, regressed for Actian, and remains incomplete elsewhere. Gorn's top choice is now Ent-E Picard captain with Janeway/Data; the published Janeway captain crew is second. PvP now selects Khan/Weyoun/Pon instead of Khan/Pike/Beverly, but still lacks enough strike-team ability coverage to validate that ranking.

The historical report incorrectly called SNW Pike/SNW Spock/ordinary Pike a valid official alternate. It is only a partial match: the third officer does not provide SNW synergy. That claim has been corrected. Passing unit tests was also previously described too strongly as validating the calculation framework; tests establish selected internal behaviours only.

## Remaining priorities

1. Verify SNW stat-dependent effects and strike-team conditions/values before enabling them. Actian and PvP remain unreliable for definitive crew selection.
2. Implement Janeway's hull-damage-triggered captain effect with verified timing; captain identity alone must not confer a fabricated bonus.
3. Obtain explicit weapon schedules so Chen/T’Laan and specialist ship mechanics are distinguishable. Catalogue targets in this benchmark have aggregate attacks, so those newly implemented weapon-specific mechanics are tested separately by deterministic regressions.
4. Calibrate against actual battle logs and objective-specific grinding/loot outcomes. Published crews are comparison evidence, not universal ranking assertions.

## Verification and evidence

Seven new regressions cover seat/context/level boundaries, Pike placement, weapon-type matching, missing schedules, supported captain effects, score resolution, and NX-01 deflection. Existing caps tests now reflect the newly implemented Moreau effect rather than expecting both levels to omit it.

Conditions and provisional modelling details are in [RULES.md](../../docs/RULES.md). Crew references: [Scopely PvE](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/7093-for-pve/) and [Scopely PvP](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/7091-for-pvp/). Shot deflection: [Scopely NX-01](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/7830-enterprise-nx-01/).
