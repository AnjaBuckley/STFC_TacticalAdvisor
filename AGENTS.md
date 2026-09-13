# STFC Tactical Advisor — contributor instructions

Updated September 2026. This file is the shared project guidance for coding agents. Read it before editing; use [README.md](README.md) for setup and [docs/RULES.md](docs/RULES.md) for the mechanics audit.

## Current product

A local Python tactical advisor with a **FastAPI backend and plain HTML/CSS/JavaScript frontend**. Streamlit has been removed. The Windows portable build uses PyInstaller, a notification-area tray launcher, and the user's default browser. The Typer CLI remains supported. There is no Node frontend build step.

The app recommends owned ships, bridge crews and below-deck crews for nine mission contexts. Rankings are heuristic and combat outcomes are estimates. Do not describe the model as a complete recreation of STFC or a guarantee of the globally optimal crew.

## Code map

- `run_app.py`, `desktop_launcher.py`: startup, one-instance lock, port selection, tray, browser opening and logs.
- `app.py`: FastAPI routes, local token/origin guards and application lifespan.
- `service.py`: catalogue, mission validation, profile revision checks, atomic saves and backups.
- `sheet_sync.py`: persistent one-way Google Sheets polling every 300 seconds.
- `paths.py`: bundled resources versus writable per-user data. `STFC_ADVISOR_DATA_DIR` supports isolated testing.
- `web/`: frontend assets. Escape user/imported text; preserve labels, keyboard access and responsive layouts.
- `engine/`: combat maths, ability scope/seat effects, synergy and simulation; `catalogue.py` handles ship identity/stat curves and `sources.py` validates attributed effects.
- `optimizer/`: bridge shortlist, captain assignments, below-deck selection and ranking.
- `ingest/`: research CSV and Officers Tool workbook parsing and merges.
- `fetch_stfc_space.py`: explicit public-data refresh utility; review generated changes before publishing.
- `data/`: static game metadata and curated rules. Player ranks, levels and stats belong in the profile, not the catalogue.
- `profiles/`: only the blank template and JSON schema are tracked.
- `tests/`: mechanics, import, API, sync and desktop regression checks.
- `packaging/`, `stfc_advisor.spec`, `.github/workflows/windows-build.yml`: Windows build, distribution and executable smoke test.
- `docs/demo-profile.json`, `docs/screenshots/`: synthetic documentation data and reviewed app screenshots.

## Mechanics and data integrity

1. Preserve additive base-stat buffs and marginal-gain/dilution handling. Keep research percentages distinct from point-based stats.
2. Keep standard and isolytic damage as separate tracks. Gorn Hunter standard-damage immunity must apply across API and CLI paths. Do not infer immunity for every unverified Gorn variant.
3. Apply Apex once. Critical Mitigation applies only to critical hits and valid sources for the task and ship. Preserve explicit-zero precedence over legacy fields. The point conversion curve is an inference documented in the rules audit.
4. Abilities must respect their seat and target conditions: captain maneuver on captain, officer ability on bridge, below-deck ability below deck. Unknown effects remain disclosed rather than assigned invented numeric bonuses.
5. Evaluate every captain assignment within the shortlist. Never duplicate an officer across bridge/below deck or invent an owned ship. Explicit unavailable or locked officers are excluded.
6. Re-evaluate below-deck marginal benefits using ship-specific stat caps; use actual slot unlocks or explicit overrides. Do not infer extra slots from Syndicate level.
7. Preserve exact hostile identity and Academy Operations gates. Do not invent a Duo Critical Mitigation entry requirement. Label wave/raid/anomaly predictions as individual encounters.
8. The combat triangle is Interceptor over Battleship, Battleship over Explorer, Explorer over Interceptor. Strike-team bonuses also depend on the player's ship class.
9. Keep repair-cost-per-kill meaningful when there are no kills. Simulation scores are estimates, not live win probabilities.
10. Verify new live-game claims against primary sources and update `docs/RULES.md`, `data/rules.json` and relevant regressions together. Older example code is not authoritative evidence.

## Account safety and syncing

- Never commit accounts, shared-sheet URLs, backups, runtime state, logs, credentials or unreviewed screenshots. Synthetic fixtures must be labelled as such.
- Use `service.save_profile` for app writes; retain revision checks, a backup before changed data is saved, and atomic replacement.
- Sync is Google Sheets → local account only. It updates sheet-owned officer fields, Operations and Syndicate. It does not discover a player's ships or fetch all research.
- Preserve ships, research, officer availability and manual enrichment during imports. Do not delete officers absent from the sheet without an explicit product change.
- Fetch outside the profile lock, merge with the latest saved account, avoid overlapping syncs, and discard in-flight data when the connection is paused or replaced.
- Failed downloads retain the account; unchanged downloads do not rewrite it. Persist the connection across launches. Sync runs only while the server runs.
- Do not silently overwrite an open form after an external save. Preserve the stale-edit conflict and reload notice.
- Bind to loopback and retain the local write token, origin checks, TrustedHost and content-security headers. Use explicit UTF-8 for text data on Windows.

## Development and verification

Use Python 3.11+ for source development and Python 3.12 x64 for Windows builds. Install `requirements.txt`; build-only dependencies are in `packaging/requirements-build.txt`.

```sh
python -m pytest -q
python -m ruff check <changed-python-files>
node --check web/app.js
python packaging/smoke_bundle.py run_app.py
```

The socket and launcher checks need permission to bind localhost. Use temporary profiles for mutation tests; never exercise writes against someone's real account. Add regressions for changed mechanics, persistence or lifecycle behavior. Documentation-only changes need link, image and ignore-rule checks, not redundant combat runs.

For UI changes, inspect desktop and phone layouts and the affected user flow. Capture documentation screenshots with the synthetic demo profile and no active sheet connection; see `docs/screenshots/README.md`.

## Windows delivery

Run `Build-Windows.cmd` on Windows or the GitHub Actions workflow. It runs tests, builds the EXE, smoke-tests a temporary blank account, and produces `dist/STFC-Advisor-Windows-x64.zip`. The recipient extracts the whole folder and runs the EXE; Python is bundled.

Never bundle the live profile or sync configuration. Keep account data outside the installation folder. Preserve tray Open/Quit behavior, duplicate-launch reuse, startup readiness checks and port fallback. The automated headless smoke test does not verify the Windows 11 tray visually; report that distinction accurately. Do not claim a signed build or publish release assets that were not actually produced and checked.

## Scope and communication

Make focused, reviewable changes. Inspect repository status before editing and preserve unrelated work. Do not reintroduce Streamlit, rewrite the frontend framework, replace game data wholesale, or rewrite Git history without a task that calls for it. Update README and relevant instructions when workflows change. Report concrete behavior, validation performed and material remaining limits.

## Approved audit corrections — September 2026

The implementation disposition is in `docs/AUDIT_CORRECTIONS.md`. It supersedes historical example formulas and fixed-name heuristic rules. Do not restore raw officer points as ship stats, universal synergy multipliers, inferred extra Syndicate slots, automatic nearest-level substitution, 90% whole-officer cap penalties, or research text matching as numerical authority. Preserve research buff IDs, native units and manual account totals. Public exports and update overlays are partial; unresolved mechanics need explicit omissions and battle-log fixtures. Full game accuracy must never be claimed from passing synthetic tests.

## Specialist model boundaries

See [specialist follow-up](reports/crew-benchmark-2026-09-12/SPECIALIST_FOLLOWUP.md). Preserve per-weapon critical overrides, received-weapon procs, explicit defending/ship-class conditions and the Combat/Loot objective distinction. Weyoun timing, Seven cadence and shot rounding remain provisional. Do not import raw hostile weapon components without verifying units and hostile abilities.

## Ship data and autofill

See [SHIP_DATA.md](docs/SHIP_DATA.md). `engine/ship_builds.py` resolves base builds; `refresh_ship_database.py` explicitly refreshes the public ship snapshot. Keep SHIP_SNAPSHOT.json separate from other dataset versions. Level is not enough to infer tier, components or account research. Preserve manual-build opt-in, component choices during level changes, native units, and global versus extra ship research totals. Static Ship Stats sheet references never confer ownership or enable unreviewed combat effects.

Research imports: count Yes and Current, select the highest completed level once, and preserve manual totals. `data/research_effects.json` is the explicit node/buff scope registry. New mappings default disabled; activation is an import choice acknowledging overlapping totals. Never convert CSV Power or description regex matches into applied bonuses. Ship catalogue reference panels do not activate ownership-dependent abilities/refits.

Research audit, 13 September: all 2,587 public records inventoried; 136 nodes mapped with 164 effects. See [coverage and correction details](docs/RESEARCH_AUDIT.md). Keep reviewed record hashes, actual level bounds, native units, once-only damage application and explicit activation. Remaining records are not automatically simulated.

## Full public catalogue audit

See [catalogue audit](docs/CATALOGUE_AUDIT.md) for the September 13 snapshot: 115 ships, 292 officers, 71 equipment items, 5,513 hostiles and 80 PvP bands. Rules & sources exposes searchable coverage. Ship editing supports separate Forbidden/Chaos equipment, explicit tier/level and opt-in mapped bonuses. PvP checks use opponent Operations independently of ship level. Source presence does not mean complete simulation support. Preserve native magnitudes versus trigger probabilities, canonical officer identity, stale-source guards and explicit equipment activation. Refresh with `refresh_game_catalogues.py`, then audit with `audit_game_catalogues.py`; review changed mechanics before shipping.

Dropdowns are enhanced globally by `web/searchable-select.js`. Keep native `<select>` elements, IDs, options and change events as the form state; the enhancement provides the searchable combobox and handles dynamically inserted fields. Preserve disabled options, required-state labels, keyboard navigation, and escaping through textContent.
