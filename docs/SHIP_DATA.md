# Ship data, autofill and source boundaries

Reviewed 12 September 2026. This update copies a dated public snapshot into the application; it does not silently change combat inputs via background network requests.

## What is bundled

- All 115 ship records returned by the current STFC Space ship summary, across grades. The user's grade-3 page filter does not restrict the database.
- Full raw tiers, component values, level hull/shield bonuses, officer thresholds, slot unlocks, abilities and refit metadata. Retaining an ability in the database does not mean its combat effect is supported.
- `data/stfc_space/SHIP_SNAPSHOT.json`: version, fetch timestamp, count and SHA-256 checksums. This ship snapshot has its own version; the older global VERSION still describes other datasets.
- `data/ship_sheet_reference.json`: 102 static Ship Stats references extracted from the supplied Officers Tool workbook. Only Ability/Crew/Bonuses rows were copied. No private Ships inputs, ownership, roster, shared URL or sync credentials are included.

The sheet tab is a lookup table, not a complete combat-stat table. Its values are displayed as reference information. STFC Space supplies base builds and slot thresholds; sheet ability prose is not parsed into numeric combat buffs. Missing/conflicting effects need review. Existing sheet polling still updates officers and account progression, not ship ownership or ship research.

## Build calculation

Select the exact ship, level, tier and installed component upgrades. Each upgrade selects the same component slot in the next tier only when the exported slot/tag layout matches. Unsupported builds fail explicitly. Level selection preserves installed component choices; changing tier resets component choices to that tier. The tool validates available exported levels/tiers, but does not establish every in-game upgrade prerequisite.

- Hull/shield use their component HP plus the exported bonus at the selected level. The bonus is treated as the total for that level, not a sum across earlier levels. This remains an export interpretation requiring in-game comparison.
- Armor = Armor.plating; shield deflection = Shield.absorption; dodge = Impulse.dodge. Accuracy/piercing use arithmetic weapon-component means, consistent with the public site's stat presentation.
- Weapon damage is the mean of minimum/maximum damage. Each shot is simulated using its own critical chance and multiplier. The reference damage-per-round is the sum of mean damage × shots / cooldown, excluding criticals; it is not the composite Attack power number.
- STFC Space weapon type 1 is energy, 2 kinetic. Its first firing round is `warm_up`; the simulator uses `warmup = warm_up - 1`. Cooldown is the interval in rounds. These mappings were checked against the site's public weapon display/firing-pattern code, retrieved 12 September 2026.
- Movement and cargo are reference fields; no travel/hauling simulation is implied. Cargo adds the tier cargo buffs to its component values. Criticals and shield absorption are separate from hull/shield HP.

## Account-specific research

The nine base-stat categories apply additive global account totals plus extra ship-specific totals and eligible officer bonuses to the unbuffed value. An extra 50% on top of 200% yields 3.5× base, not 4.5×. Enter percentages in forms; storage uses fractions. Do not duplicate bonuses already in global totals. Ship class, faction, combat context and target restrictions matter: contextual research belongs in reviewed attributed combat sources, not an unconditional total.

Displayed game stats already include account/crew contributions and must not be labelled unbuffed catalogue stats. Existing `displayed` builds retain the no-second-research-multiplier path; rebuilding from the catalogue explicitly replaces their basis with base. Autofill cannot know a player's completed research, buildings, artifacts, tech or fleet commanders from level alone. The existing research importer preserves node IDs and units but requires scope review; no arbitrary text-to-bonus mapping was introduced.

## Sources and refresh

- [STFC Space ships](https://stfc.space/ships) and its public data backend, https://data.stfc.space . This is a community database, not Scopely's official API or a live correctness guarantee.
- [Official Officers Guide](https://scopely.helpshift.com/hc/en/19-star-trek-fleet-command/faq/3737-officers-guide/) establishes officer stat contributions to ships.
- [Official Mess Hall update](https://startrekfleetcommand.com/news/update-52-the-mess-hall/) illustrates that buildings also change officer stats.
- [Official Update 64](https://startrekfleetcommand.com/news/update-64-patch-notes/) distinguishes effects on total critical stats after other bonuses; do not treat every research category as the same arithmetic operation.

Developers run `python refresh_ship_database.py`, review changes, run tests, then distribute a new build. Downloads finish and the upstream version is rechecked before replacing bundled records. A network/download validation failure leaves existing files intact. This is a development refresh, not an in-app transaction or account sync. The site client modules inspected were `index-DAVmwAuj.js` and `pages-DbaYKw2y.js`; no client code is executed or bundled.

Regression coverage includes all bundled tier-1 builds, exact input validation, level changes, individual component upgrades, additive research, displayed-stat protection, API preview and static sheet reference separation. Actual battle-log calibration is still needed for complete combat accuracy. Extra ship critical chance (percentage points) and critical damage bonuses can be supplied separately from each weapon’s base critical profile; omit bonuses already represented in those inputs.

## Verification for this update

226 tests passed; lint, JavaScript syntax and all 117 snapshot file checksums passed. Source startup smoke passed with a clean temporary account and sync disabled. Browser checks covered autofill, level/tier changes, saving/reopening, component preservation and 390-pixel layout without horizontal overflow. These are not a Windows EXE build or live-game battle verification.

## Research progression and ship reference coverage

The Spock's Club CSV importer treats `Yes` and `Current` as completed and selects the highest completed level once. The site's [research exporter](https://spocks.club/research/) marks the selected level Current and lower levels Yes. CSV Power is not a combat bonus. Node IDs and levels join to the bundled research records; native buff values and IDs are retained.

`data/research_effects.json` explicitly maps 136 research nodes (164 individual stat effects) with exact descriptions, units and ship/context conditions. New mapped sources start disabled. The import preview checkbox enables reviewed mappings only when the user's manual account and ship totals exclude those same bonuses. Existing manually reviewed sources retain their settings. All other effects remain unreviewed; missing upstream records are retained disabled. This is partial research coverage, not automatic modelling of every artifact, favor, refit or Fleet Commander record in the export. Completed levels are saved locally as `research_progress`.

The ship form now shows catalogue passive/active abilities, refits, selected-level native ability values, below-deck unlocks and officer stat thresholds. For [U.S.S. Vengeance](https://stfc.space/ships/782228494), these include two passive abilities, two active references and six refits. [Scopely's introduction](https://startrekfleetcommand.com/news/the-u-s-s-vengeance-star-trek-fleet-commands-first-legendary-ship/) confirms the non-armada scope of its Apex ability and its Breen shield interaction. These references do not confer ownership or activate arbitrary combat effects. Active ability resource/cooldown logic, refit ownership effects, repair/build/scrap economics and exact Breen shield bypass remain outside this form's automatic calculations. Ship level alone cannot establish research, equipped refits or actual account totals.

Research audit, 13 September: all 2,587 public records inventoried; 136 nodes mapped with 164 effects. See [coverage and correction details](RESEARCH_AUDIT.md). Keep reviewed record hashes, actual level bounds, native units, once-only damage application and explicit activation. Remaining records are not automatically simulated.

## Full public catalogue audit

See [catalogue audit](CATALOGUE_AUDIT.md) for the September 13 snapshot: 115 ships, 292 officers, 71 equipment items, 5,513 hostiles and 80 PvP bands. Rules & sources exposes searchable coverage. Ship editing supports separate Forbidden/Chaos equipment, explicit tier/level and opt-in mapped bonuses. PvP checks use opponent Operations independently of ship level. Source presence does not mean complete simulation support. Preserve native magnitudes versus trigger probabilities, canonical officer identity, stale-source guards and explicit equipment activation. Refresh with `refresh_game_catalogues.py`, then audit with `audit_game_catalogues.py`; review changed mechanics before shipping.
