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
