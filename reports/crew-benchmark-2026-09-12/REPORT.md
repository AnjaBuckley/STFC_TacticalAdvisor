> Historical initial benchmark. See [implemented corrections and controlled rerun](FOLLOWUP.md) for the current results. Initial raw results are preserved in `baseline-results.json`.

# STFC Tactical Advisor — Crew Recommendation Benchmark

**Run date:** 12 September 2026
**Scope:** six controlled scenarios using real hostile records from the app and published crew examples
**Code changes:** none to the advisor; this report and its reproducible benchmark files are the only additions

## Executive finding

The advisor is directionally useful, but its current output should be treated as an **estimated shortlist**, not as a reliable “best crew” answer.

Of the six scenarios, the first recommendation was:

- **Partial alignment in the Swarm case:** level 35 Swarm. It chose SNW Pike / SNW Spock / Pike; ordinary Pike does not meet the published SNW synergy requirement.
- **Close but materially mis-slotted in 2/6:** Gorn and Xindi. It found the important officer family but put the wrong officer in the captain seat.
- **Partially aligned in 1/6:** Actian. It kept SNW Pike and SNW Hemmer but replaced the published class counter.
- **Not aligned in 2/6:** Borg and Explorer PvP.

The benchmark does **not** establish that a published crew is mathematically optimal for every account. Officer rank, research, ship tier, refits, artifacts, forbidden tech, target weapons, and battle duration all matter. It does establish that the optimizer does not yet reproduce several strong official examples even when every candidate has equal rank and stats.

## Method

Each scenario used a closed synthetic roster containing the published crew and plausible alternatives. Every officer was rank 5, level 30, with identical attack, defense, and health. This removes account progression as the explanation for ranking differences. The benchmark did not read or modify the user's synced profile.

The target was a real hostile record from the app's `hostile_stats.json`, selected by hostile ID and level. The ship hull, shield, and attack were scaled to the selected target so simulations completed in a useful number of rounds. The Gorn Eviscerator received an explicit 50% Isolytic Damage bonus because standard damage is ineffective for that loop. PvP used explicit opponent hull, shield, damage, defense, and piercing inputs, as required by the app.

For each scenario the production `find_optimal_crew()` function searched the roster, shortlisted candidates, ran 150 deterministic Monte Carlo simulations per finalist with seed 42, and returned the top ten. Results are in [results.json](./results.json); the exact runner is [run_benchmark.py](./run_benchmark.py).

The comparison distinguishes:

- **Exact:** captain and both side officers match.
- **Same members:** all three match, but captain placement may differ.
- **Valid alternate:** the top result is separately listed in official guidance.

## Results

| Scenario | Published example | Advisor #1 | Published rank | Assessment |
|---|---|---|---:|---|
| L35 Swarm Cluster, Franklin | Pike (C) / Moreau / T'Laan | SNW Pike (C) / SNW Spock / Pike | Outside top 10 | **Partial match only.** Scopely also lists SNW Pike / SNW Spock / any SNW synergy officer for Swarm up to 35. Pike is not an SNW officer, however, so the app's third seat misses the synergy instruction. |
| L40 Borg Assailant, Vi'Dar Talios | Five of Eleven (C) / Eight / Nine | SNW Pike (C) / Five / Pike | Outside top 10 | **Fail.** It retained only Five. The complete higher-Ops Borg trio was absent. |
| L60 Gorn Hunter, Eviscerator | Kathryn Janeway (C) / Ent-E Picard / Ent-E Data | Ent-E Data (C) / Kathryn Janeway / Ent-E Picard | Exact #9; same members #1 | **Close, wrong captain.** Membership is excellent, but Data in the captain seat discards Janeway's captain maneuver. |
| L40 Actian Apex, Mantis | SNW Pike (C) / class counter / SNW Hemmer | SNW Pike (C) / SNW Hemmer / Pike | Exact #8 | **Partial.** It kept the captain and Hemmer but replaced SNW Spock, the Interceptor counter used in this test. |
| L48 Xindi-Aquatic, NX-01 | Jonathan Archer (C) / Trip / Chen | Trip (C) / Jonathan Archer / Pike | Exact outside top 10; same members #10 | **Fail on placement and third seat.** Archer as captain with Trip appeared at #4, but with Pike rather than Chen. |
| Explorer PvP vs Battleship | Weyoun (C) / Jack Ransom / Pon | Khan (C) / Pike / Beverly Crusher | Outside top 10 | **Fail.** None of the official Explorer Strike Team combinations appeared in the top five. |

All top-five candidates in these controlled fights reported 100% kill and survival in most PvE cases. That saturation is itself a finding: the simulator could not discriminate among crews, so final ordering depended heavily on heuristic and “unmodelled ability” tie-breaks. These percentages should not be read as real-account win rates.

## Comparison to current guidance

Scopely's current [PvE crew guide](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/7093-for-pve/?l=en%2F1000&p=all) directly supports all five PvE reference cases:

- Franklin against Swarm: Pike / Moreau / T'Laan, or SNW Pike / SNW Spock / a synergy officer.
- Vi'Dar or Talios against Borg probes: Five / Eight / Nine at higher Ops.
- Mantis against Actian: SNW Pike / the matching SNW class officer / SNW Hemmer.
- NX-01 against Xindi-Aquatic: Archer / Trip / Chen.
- Eviscerator against Gorn: Janeway / Ent-E Picard / Ent-E Data, with WOK Saavik and SNW Nurse Chapel also identified.

The older independent [Franklin field guide](https://carnacsguide.com/uss-franklin/) corroborates Pike / Moreau / T'Laan and explains the purpose: the Franklin already has extreme Swarm damage, so the crew should emphasize mitigation. This source dates to 2020, so it is supporting evidence rather than the current authority.

Scopely's [Gorn Eviscerator guide](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/7929-the-gorn-eviscerator/) confirms that the ship's Hunt the Hunters passive adds Isolytic Damage specifically against Gorn Hunters. This supports the benchmark's explicit ship Isolytic bonus and the app's requirement for an Isolytic source.

Scopely's [Mantis guide](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/6880-mantis/) confirms the Mantis is designed for Actian hostiles. Scopely's [Enterprise NX-01 guide](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/7830-enterprise-nx-01/) likewise says its Xindi-Aquatic passive deflects nine of ten weapon shots and calls it the optimal ship for that encounter. The app currently does not model those complete ship-specific mechanics, so crew comparisons on those ships remain approximate.

For PvP, Scopely's [current PvP crew guide](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/7091-for-pvp/?l=ja) lists the Explorer Strike Team as Weyoun (C) / Jack Ransom / Pon or Ikat'ika. That is a stronger and more current reference than the older Weyoun / Pon / Ikat'ika rule in project documentation. The benchmark used the current version.

The [official officer guide](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/3737-officers-guide/) confirms why captain placement cannot be treated as a cosmetic permutation: only the captain activates the Captain's Maneuver, bridge officers activate Officer Abilities, and Below Deck Abilities only work below deck. It also says captain maneuvers scale through synergy rather than officer level or tier.

## Why the rankings diverge

### 1. Captain permutations are scored as if many were interchangeable

Gorn is the cleanest example. The app found exactly the right three officers at rank one, yet selected Ent-E Data as captain. The published Janeway captain version fell to rank nine. Xindi showed the same pattern: Trip captain ranked first, while the official Archer captain version did not enter the top ten.

The search enumerates every captain assignment correctly, but the numerical model does not give all captain maneuvers enough outcome value. It should explicitly penalize a no-CM captain when a companion has a relevant, modelled captain maneuver, and it should validate captain placement in known specialist families.

### 2. Unsupported effects become a ranking penalty instead of combat behavior

Top Swarm recommendations reported SNW Pike's enemy mitigation reduction and SNW Spock's stat multiplier as unsupported. Moreau's piercing reduction, T'Laan's damage reduction, Jaylah's extra shots, Weyoun's shots, and Pon's critical suppression were also reported as unsupported in relevant results.

The final sort prefers fewer unmodelled abilities after kill and survival rates. When every simulated crew wins, a crew with fully modelled but irrelevant generic effects can outrank a specialist crew whose key ability is merely unimplemented. This explains much of the Borg and PvP mismatch.

### 3. Simulations saturate too easily

The test ships were deliberately normalized, yet the top candidates usually achieved identical 100% kill and survival. Once outcomes tie, the engine cannot show the practical difference between longevity, kills per hull, loot per trip, or PvP damage exchange.

Scenario calibration should target a difficulty band where candidates produce different hull loss and kill reliability. For grinding, the primary measure should be expected kills before repair and loot per repair cost. For PvP, use remaining hull/shield or damage dealt before destruction, not merely a binary kill.

### 4. Ship passives are incomplete

The Eviscerator's Isolytic bonus can be supplied manually, but its tier scaling is not sourced automatically in this benchmark path. The NX-01's nine-shot Xindi-Aquatic deflection and the Mantis's Actian-specific scaling are not represented as full per-weapon mechanics. This limits any “best crew” conclusion even when officer abilities are perfect.

### 5. The official target label and the app target do not always match exactly

Scopely describes “Borg Probes”; the app's supported real target is “Borg Assailant.” The Vi'Dar/Talios loop and Borg targeting make the comparison useful, but it is not proof that those records are mechanically identical. The UI should expose the exact underlying hostile ID and source date so players can judge this uncertainty.

## Recommended corrections

### Approve first

1. **Implement the effects already identified as unsupported in these runs:** enemy mitigation down, stats multiplier, enemy piercing down, enemy damage down, extra shots, and enemy critical chance reduction. These are blocking known official crew families.
2. **Make captain-seat validity a first-class score.** Award the captain maneuver only in the captain seat, apply its actual synergy curve, and penalize placing a BDA-only or irrelevant-CM officer as captain when a relevant captain is available.
3. **Add regression fixtures from official examples.** Tests should assert the official crew appears in the top three for an equal-rank controlled roster, with the named captain in the captain seat. Allow documented official alternatives rather than forcing one lineup.
4. **Change the tie-breaker.** Do not reward a crew because fewer of its abilities are modelled. Mark rankings with unsupported decisive effects as indeterminate, or compare them in a separate “needs battle-log validation” group.

### Approve next

5. **Model specialist ship passives by hostile ID and ship tier:** Franklin Swarm bonus, Eviscerator Hunt the Hunters, NX-01 Learning the Hard Way and Polarized Hull, Mantis Actian effects, and Vi'Dar/Talios Borg effects.
6. **Add task-specific outcome metrics:** kills per hull for grinding; loot per trip where loot officers matter; central-entity leakage and travel time for Wave Defense; damage exchange and remaining hull for PvP.
7. **Calibrate from battle logs.** Ask the user for two or more reports from the same ship/target with one controlled crew change. Fit proc timing, weapon schedules, and conditional activation before claiming validated rankings.
8. **Version every public example.** Store URL, retrieved date, target, ship, crew, and whether the source is official. Current guidance can change with patches.

### Do not hard-code as universal truth

- Do not force Pike / Moreau / T'Laan above SNW alternatives for every Swarm level; Scopely lists both and separates recommendations by level.
- Do not force one Actian SNW side officer without considering the actual opponent class and ability condition.
- Do not assume published examples are optimal for every account. Treat them as regression anchors under controlled conditions.
- Do not mix loot efficiency with combat survival into one unexplained score. Show both so the player can choose the objective.

## Additional mission types

Academy Drones and Wave Defense need separate validation rather than recycling ordinary hostile tests. Scopely's [Academy Drones and Duo Wave Defense guide](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/8788-academy-drones-duo-wave-defense/) documents +1,000% critical chance, +5,000% critical damage and floor, an Explorer drone immune to non-Isolytic damage, a Battleship drone with 10,000 Apex Barrier, and a Survey drone with 100,000 Critical Mitigation. These mechanics are excellent deterministic regression targets, but the page does not publish a recommended crew lineup, so it cannot support a crew-similarity score.

Scopely's [Wave Defense update guide](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/7771-wave-defense-updates/?contact=1%2F1000&p=web) says waves combine Federation Explorers, Klingon Interceptors, Romulan Battleships, and specialist hostile types. A single-target optimizer cannot validate the real mode. A useful Wave Defense test must optimize two or three ships as a fleet, preserve combat-triangle coverage, account for impulse speed and travel, and avoid reusing the same officer twice.

## Reproduction

From the repository root:

```bash
cd stfc-advisor
.venv/bin/python reports/crew-benchmark-2026-09-12/run_benchmark.py
```

The command rewrites only `results.json`. It makes no network request and does not touch `profiles/player_profile.json`.
