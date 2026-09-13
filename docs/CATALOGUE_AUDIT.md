# Public catalogue audit — 13 September 2026

The complete STFC Space summaries and every detail record were retrieved at version `0f929edd-ec2d-4e76-9430-2cfe3cb4f619`. The audit ignores the page and grade filters in the supplied links. `data/stfc_space/CATALOGUE_SNAPSHOT.json` records the source, fetch time, counts and file hashes. These are bundled public reference data, not a player's owned inventory or independently verified live-game outcomes.

| Category | Records | Calculation coverage |
| --- | ---: | --- |
| Ships | 115 | Existing exact level/tier/component base builds, native weapon stats and crew unlocks. Ship abilities, active abilities and refits remain separately modelled or reference-only. |
| Officers | 292 | All 671 exported ability slots inventoried: 545 comparable model value tables agree, 13 lack model values, 27 lack a model, and 86 are zero-effect captain placeholders. Matching numbers do not establish correct conditions or timing. |
| Forbidden and Chaos Tech | 71 | All 242 buffs inventoried. 48 buffs across 28 items have explicit mappings; the other buffs remain omitted. The two equipment types have separate slots. |
| Hostiles | 5,513 | Every detailed record is bundled. All 527 existing curated variants match the refreshed source stats; no numeric changes were needed. Other records are reference-only, not automatically enabled encounter templates. |
| PvP bands | 80 | Standard Operations ranges available with separate ship/station protection thresholds. No extrapolation above the published range or event-specific eligibility claim. |

`data/catalogue_coverage.json` contains every record and the per-officer slot comparison, including source probabilities separately from effect magnitudes. Search it in **Rules & sources → Public database coverage**. A probability requiring further review remains disclosed in the detailed inventory. An unmodelled slot must not be interpreted as a zero-strength ability in the real game.

## Corrections

- Added explicit full-name aliases, including Grace Chen and SNW Christopher Pike. Full names now reach the same specialised mechanics as their established short names. Crew selection and below-deck exclusion use canonical identities to prevent assigning an alias twice.
- Separated Harry Mudd (The Ultimate Con / Down but Never Out) from Harcourt Fenton Mudd (Two steps ahead / 823 ways to die). The old short name Mudd resolves to Harry Mudd; the two officers no longer exchange their public kits.
- Corrected the current public Neelix/Harry Kim kit assignment in reference data. Their pre-existing account identity migration guard remains enabled; the source catalogue cannot establish which migrated officer/rank a player owns.
- Preserved effect magnitude and trigger probability as separate fields. Hugh's 25% critical-chance increase, for example, must not be replaced by his 45–100% trigger probability. Seven, Weyoun and Pon intentionally use probability-based captain synergy in their existing explicit models.
- Added source record hashes and exact source descriptions to matched officer entries. Changed source records are excluded pending mapping review. Probabilistic records without a supported event model remain conditional rather than unconditional stat increases.
- Added explicitly equipped technology to the ship form: item, tier, level and activation. Only reviewed bonuses apply, only to that ship, in the appropriate encounter/class context. Tier unlocks and actual tier level ceilings are enforced; padded 99-value export arrays do not allow nonexistent levels. Displayed ship stats omit these bonuses to prevent double counting. Activation acknowledges that the bonuses are excluded from manual totals.
- Added an optional opponent Operations field. Standard PvP range warnings use Operations, independently of the target ship level. They are advisory because Incursions and other events can use different rules.

## Sources and interpretation boundaries

- [STFC Space ships](https://stfc.space/ships), [officers](https://stfc.space/officers), [equipment](https://stfc.space/forbidden_and_chaos_tech), [hostiles](https://stfc.space/hostiles), [PvP bands](https://stfc.space/pvp_bands). Public JSON is supplied by `https://data.stfc.space`; per-record links are in the coverage inventory and effect registries.
- [Scopely Chaos Tech FAQ](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/8140-chaos-tech/): a separate ship equipment slot complements Forbidden Tech. Bonuses are tied to equipment on the ship. Conditional and timed examples in this FAQ are not converted into permanent stat increases.
- [Scopely Update 56](https://startrekfleetcommand.com/news/update-56-voyager-pt-3-patch-notes/): Forbidden Tech equipment framework and upgrades.
- [Scopely Combat Overview](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/3733-combat-overview/): ship PvP unlocks at Operations 10, station combat at 15, with Operations-based restrictions.
- [Scopely Incursions banding update](https://startrekfleetcommand.com/news/infinite-incursions-march-28th-2026-updates-pvp-banding-and-server-pairings/): event-specific banding must not be assumed to match the standard table.

The technology registry is a reviewed interpretation of explicit individual buff descriptions and native level values. It does not implement technology purchasing, unlocking, upgrade success chances, costs or inventory discovery. Selecting equipment is the user's declaration that it is owned and equipped. Bonuses with unresolved scope, stacking, per-round triggers, ship-specific unlock rules or native units remain omitted. A partially supported item can therefore contribute fewer bonuses than it does in game.

The hostile export includes weapons and abilities, but they are not automatically promoted into a complete battle model. Existing curated encounter overrides remain authoritative for the implemented specialist rules. Borg, Xindi, Gorn and PvP still need exact battle-log fixtures for mechanics not already modelled. Source inventory and successful synthetic tests are not a complete game-logic certification.

## Refresh and verification

The app uses the bundled snapshot offline. It does not silently replace validated calculation rules with live downloads. During development, stop the app, run `python refresh_game_catalogues.py`, then `python audit_game_catalogues.py`. The downloader checks the upstream version before and after fetching all summaries, details and translations. All downloads and basic validation complete before files are replaced. Replacement is per-file, so an interrupted installation must be rerun before restarting the app.

Review stale officer and technology mappings, curated hostile statistics, and shared ship manifest metadata before release. Research has its own snapshot, importer and audit. Refreshing public data never changes player ships, ranks, research progress or sheet connections. Keep intentional public changes aligned with the GitHub checkout and rerun tests before rebuilding Windows.

Verification covers snapshot hashes, all existing ship build checks, every technology tier endpoint, source units, class/context restrictions, tier unlocks, activation, displayed-stat protection, stale mapping exclusion, alias identity, standard PvP boundaries, and API persistence using synthetic accounts. UI checks exercise equipment save/reopen, searchable coverage, and desktop/phone layouts. No live battle logs were provided for this audit.
