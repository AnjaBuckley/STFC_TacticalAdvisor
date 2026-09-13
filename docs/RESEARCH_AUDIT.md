# Research database audit — 13 September 2026

The complete current STFC Space research export has been inventoried and its numeric level tables checked. This is **not** a claim that every effect is simulated correctly: coverage is explicitly recorded for every node in `data/research_coverage.json`, and available through Account & research → Research database coverage.

## Snapshot and coverage

Source: [STFC Space research database](https://stfc.space/researches), with records from [its public data backend](https://data.stfc.space/research/summary.json). Version `0f929edd-ec2d-4e76-9430-2cfe3cb4f619`; downloaded 13 September 2026. All 2,587 detail records, the summary and English descriptions were fetched, with the upstream version checked before and after downloading. `RESEARCH_SNAPSHOT.json` records per-file SHA-256 hashes independently of the ship snapshot and older datasets.

| Disposition | Nodes | Behaviour |
|---|---:|---|
| Explicit combat mappings | 136 | 164 individual effects; new imports default disabled until overlap with manual totals is excluded |
| No numeric buff | 141 | Unlock/reward/progression information; no fabricated combat bonus |
| Other progression systems | 833 | Not treated as owned/active research from CSV progression alone |
| Not modelled | 1,477 | Values retained for review; no automatic combat effect |
| Missing/invalid catalogue tables | 0 | All actual level tables and numeric values passed inventory checks |

The inventory covers every listed node and every defined level value. Semantic implementation review is limited to the explicit mapping registry. Unmapped descriptions are retained with their source links for further work; they have not all been established as numerically correct game models.

## Corrections

- Research weapon damage previously entered ship stats and was added again when firing. It now contributes once; aggregate and explicit-weapon regression fixtures match equivalent manual additive totals.
- Buff arrays can contain zero padding beyond a node's actual levels. Imported levels must appear in the research level table; padding cannot masquerade as a valid upgrade.
- Missing values remain missing rather than becoming zero. Import previews disclose invalid levels, missing records and missing values.
- CSV descriptions and Power do not define combat effects. The catalogue supplies descriptions; mappings require exact node/buff IDs, the reviewed description, raw record hash, export flag and deterministic chance. Changed catalogue records are quarantined pending review.
- `value_is_percentage` is not a universal semantic unit. For example [Pinpoint Targeting](https://stfc.space/researches/176472186) exports 0.01 for level one's additive critical-chance offset despite a false flag. Its explicit mapping uses a fractional offset. Flat Hull Density and Shield Modulation values are **not** relabelled as percentages; their stacking interpretation remains outside mapped coverage.
- Reviewed mappings include base hull/shield/weapon stats, defenses, piercing, critical chance/damage, ship-class/faction/minimum-grade restrictions and explicit PvP or armada contexts. Compound defense/piercing effects are separated into their individual stats.
- Reimport refreshes registry scopes instead of restoring stale scopes from the previous import. Unresolved old sources are retained disabled. Old mapped source versions cannot run until progression is reimported.
- Imported research is excluded for displayed ship stats, where existing account buffs could be counted twice. Base stats are required for those comparisons. Missing grade/faction metadata can resolve from an identified catalogue ship; unknown identities fail closed.

## Remaining gaps

Many records affect mining, movement, cargo, repair/build/research economics, station platforms, specific enemy families, weapons, status effects, temporary ship buffs, takeover events or other progression systems. Their conditions cannot be replaced with unconditional damage bonuses. Flat-stat stacking and several specialist mechanics still need verified translations and battle-log calibration. Runtime combat sources are not a complete account reconstruction; no research is inferred as completed from Operations level or prerequisites.

Manual totals must exclude any enabled mapped bonuses. The app cannot automatically subtract research from a displayed aggregate without knowing what it already includes. Existing saves are not silently rewritten by a public database refresh.

## Maintenance and verification

Run `python refresh_research_database.py` for an explicit staged public refresh. Downloads and basic validation finish before files are replaced; do this during development, then restart the app. Review registry/hash changes, run `python audit_research_database.py`, inspect coverage changes, and run the regression suite before publishing. Runtime does not apply newly fetched descriptions through keyword rules. No personal CSV, research levels or profile is bundled.

Tests cover the complete snapshot inventory, public mapping identities/units, maximum-level padding, changed record hashes, stale saved mappings, scope updates, displayed-stat overlap and once-only weapon damage. Matching a controlled test is not proof that all live battles or crew rankings are accurate.
