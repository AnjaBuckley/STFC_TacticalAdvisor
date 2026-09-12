# STFC Tactical Advisor

A local Starfleet-inspired tactical console for your own ships, officers and research. The Streamlit frontend has been replaced by a responsive custom browser interface served by FastAPI. No Node build, CDN, external font service or Streamlit runtime is required.

## Run

Requires Python 3.11 or later.

```sh
cd STFC_TacticalAdvisor
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_app.py
```

The launcher opens http://127.0.0.1:8000. Use `--port 8001` to change the port or `--no-browser` to suppress automatic opening. Alternatively run `.venv/bin/uvicorn app:app --host 127.0.0.1 --port 8000`. The server is for local use and binds to loopback. If the preferred port is occupied, the launcher chooses an available port.

## Use

- **Mission planner:** choose hostile grinding, player combat, base hitting, station raids, solo/duo waves, Academy drones, anomalies or dreadnought encounters. Select a level and an owned ship, or compare all available combat ships. PvP requires opponent stats rather than silently inventing a mirror opponent.
- **Recommendations:** compare bridge and below-deck assignments, estimated outcomes, scoped Critical Mitigation, explanations, and an incoming damage trace. Export the result as JSON.
- **My fleet:** add owned ships using the local catalogue, edit the base stats for the current build, override below-deck slots or follow level unlocks, and mark ships unavailable.
- **Officer roster:** search and filter officers and mark officers assigned elsewhere unavailable. Import updated ranks, levels and stats through the Officers Tool workbook.
- **Account & research:** edit supported research totals, migrate legacy Critical Mitigation percentages to points, preview research CSV / officer XLSX / shared Google Sheet / account JSON imports, and apply changes. Connect a shared Officers Tool sheet for automatic five-minute updates, with pause/resume, sync now, and last-success status.
- **Rules & sources:** see verified mechanics, sources and explicit coverage boundaries.

The application does not access or modify the in-game account. Account/fleet/availability/import actions save locally. When Google Sheets auto-sync is enabled, the server also saves changed sheet data automatically. Each save checks a revision token, creates a timestamped backup and atomically replaces the profile. Stale edits return a conflict rather than overwriting another save.

## Google Sheets auto-sync

In Account & research, paste an STFC Officers Tool link and select **Enable auto-sync**. The sheet must be shared as **Anyone with the link → Viewer**. The server reads it immediately and checks every five minutes thereafter. The connection and status persist beside the profile in `google_sheet_sync.json`; they resume when the app starts again. Keep the server running and the computer awake with internet access. The browser tab can be closed. Run a single server process for this local account.

Sync is one-way: Google Sheets → the local account. Sheet values replace officer ranks, levels, stats and details, plus Operations and Syndicate levels. Ships, research, officer availability and manual officer class/ability enrichments are preserved. Officers absent from the sheet are retained. No Google Sheet or in-game values are written. Identical data does not create a backup or rewrite the profile. Failed or invalid downloads retain the saved account and retry on the next check. Local edits made during a download are included in the merge; sheet-owned fields still use the sheet values.

The interface shows the last successful check, last account update and next check, and offers **Pause sync** and **Sync now**. If the saved account changes while a form is open, a reload banner appears; unsaved inputs are not silently replaced. Existing recommendation results are snapshots and should be regenerated after an update.

## Accuracy

This is an estimated tactical advisor, **not a complete STFC simulator**. A heuristic shortlist evaluates all captain positions and simulates finalists. Scores are not live win probabilities. The local catalogue includes M92-derived and inferred officer metadata and estimated ship/target values. Numerical estimates must be calibrated against battle logs. See [the mechanics audit](docs/RULES.md) for verified corrections, compatibility handling and unsupported mechanics.

## Validation

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check app.py service.py run_app.py engine/effects.py tests/test_api.py tests/test_rules_regressions.py
node --check web/app.js
```

Tests use temporary profiles for API writes; they do not modify the saved account. The CLI remains available with `python main.py --help`.

## Desktop packaging

See [Windows build instructions](packaging/BUILD_WINDOWS.md). The PyInstaller spec bundles the frontend assets, local game data and blank profile template. Double-click `Build-Windows.cmd` on a build PC with Python 3.12 x64, or use the Windows portable app GitHub Actions workflow. The downloadable ZIP bundles Python, opens the browser automatically and provides a tray menu. Recipients do not install dependencies.
