# Claude Code instructions

Read and follow [AGENTS.md](AGENTS.md) as the canonical project guidance. This file intentionally links to that guidance rather than duplicating combat formulas or architecture that could drift.

Before changing code:

1. Inspect the working tree and read the relevant modules and tests.
2. Use [README.md](README.md) for development and Windows setup.
3. For STFC mechanics, consult [docs/RULES.md](docs/RULES.md) and its primary sources; do not treat old example code as verified game behavior.

Keep these boundaries in view:

- FastAPI plus vanilla browser assets; Streamlit is no longer the frontend.
- Heuristic recommendations and estimated simulations, with unsupported effects disclosed.
- Per-user data stays local; imports and five-minute sheet sync preserve backups and revision checks.
- Never commit real account exports, shared-sheet links, credentials or private screenshots.
- Use the synthetic documentation fixture for screenshots and temporary profiles for tests.
- Windows artifacts must pass the Windows build and packaged startup checks; tray appearance requires a separate desktop check.

Use the verification commands and packaging workflow documented in AGENTS.md. Keep this file short; put shared project rules in AGENTS.md.

## Approved audit corrections — September 2026

The implementation disposition is in `docs/AUDIT_CORRECTIONS.md`. It supersedes historical example formulas and fixed-name heuristic rules. Do not restore raw officer points as ship stats, universal synergy multipliers, inferred extra Syndicate slots, automatic nearest-level substitution, 90% whole-officer cap penalties, or research text matching as numerical authority. Preserve research buff IDs, native units and manual account totals. Public exports and update overlays are partial; unresolved mechanics need explicit omissions and battle-log fixtures. Full game accuracy must never be claimed from passing synthetic tests.

## Specialist model boundaries

See [specialist follow-up](reports/crew-benchmark-2026-09-12/SPECIALIST_FOLLOWUP.md). Preserve per-weapon critical overrides, received-weapon procs, explicit defending/ship-class conditions and the Combat/Loot objective distinction. Weyoun timing, Seven cadence and shot rounding remain provisional. Do not import raw hostile weapon components without verifying units and hostile abilities.

## Ship data and autofill

See [SHIP_DATA.md](docs/SHIP_DATA.md). `engine/ship_builds.py` resolves base builds; `refresh_ship_database.py` explicitly refreshes the public ship snapshot. Keep SHIP_SNAPSHOT.json separate from other dataset versions. Level is not enough to infer tier, components or account research. Preserve manual-build opt-in, component choices during level changes, native units, and global versus extra ship research totals. Static Ship Stats sheet references never confer ownership or enable unreviewed combat effects.

Research CSV: Yes and Current are completed levels; highest level only. Reviewed mappings live in `data/research_effects.json` and default disabled on first import to prevent manual-total overlap. Preserve unsupported sources and local research progression. See `docs/SHIP_DATA.md` for partial coverage and ship ability/refit reference limits.
