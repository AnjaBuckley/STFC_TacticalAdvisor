# Six-example rerun after ship/research integration

12 September 2026. Production optimizer rerun with the same six original scenario definitions, rosters, fixed synthetic ship statistics and random seed as the latest specialist benchmark. Historical results were preserved. No live profile was read or changed.

## Result

No improvement or regression in these six controlled examples compared with `results.json` from the specialist follow-up. All saved scenario fields, including the top-five crews, below-deck selections, estimated kill/survival values, rounds, hull loss and omissions, are identical.

| Scenario | First recommendation (captain first) | Published example rank, previous → now |
|---|---|---|
| Swarm 35 | SNW Pike / Moreau / SNW Spock | Outside top 10 → outside top 10 |
| Borg 40 | Eight of Eleven / Seven of Eleven / Nine of Eleven | Outside top 10 → outside top 10 |
| Gorn 60 | Kathryn Janeway / Ent-E Data / Ent-E Picard | 1 → 1 |
| Actian 40 | SNW Pike / Moreau / Chen | Outside top 10 → outside top 10 |
| Xindi 48 | SNW Pike / Trip Tucker / Moreau | Outside top 10 → outside top 10 |
| Explorer PvP | Weyoun / Jack Ransom / Pon | 1 → 1 |

Exact agreement means the same captain and side officers; side-officer order is irrelevant. Two of six published examples remain first. These are published crew comparisons with synthetic accounts, not six reproduced live battles. The Borg Assailant remains a proxy for the published Borg Probe example; the PvP opponent is synthetic. Historical source links and caveats remain in REPORT.md and SPECIALIST_FOLLOWUP.md; this rerun did not revalidate current web guidance.

## What the latest changes do and do not establish

The fixtures bypass ship autofill, deliberately supply fixed base statistics and have no imported research sources. Therefore they test regression in the existing recommendation path, not the benefit of filling a real account's missing fields. Importing research or replacing those ships with catalogue builds would change the inputs and would not be a like-for-like engine comparison.

The latest work improves data entry, provenance and scoped research handling. This run provides no evidence that it improves crew-ranking accuracy. Four published crews still fail to appear in the top ten, although a published example is not a universally optimal crew for every account.

Next useful validation needs exact hostile weapon schedules and abilities, real ship tier/components, officer ranks and account bonuses, plus battle logs. Those are particularly material for Swarm/Actian defenses and Borg/Xindi specialist effects. Gorn/PvP agreement alone does not validate their predicted damage or survival.

## Reproduce without replacing historical output

Run the existing run_benchmark.py source with its output path changed from results.json to research-rerun-results.json and its final scenario loop limited to SCENARIOS[:6]. No scenario inputs or optimizer options are changed. The resulting raw output is [research-rerun-results.json](research-rerun-results.json).
