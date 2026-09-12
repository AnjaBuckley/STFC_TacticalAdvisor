# Portable Windows build

The recipient extracts `STFC-Advisor-Windows-x64.zip` and opens `STFC-Advisor.exe`. Python and libraries are bundled. The browser opens after server startup; a notification-area icon provides **Open app**, **Open data and logs**, and **Quit**. Closing the browser leaves the app and Google Sheet sync running. A second launch opens the existing instance. An occupied port is handled automatically.

## Build locally on Windows

Install **Python 3.12 x64** on the build PC, including the Python launcher. Double-click `Build-Windows.cmd` in the project root. The script creates an isolated build environment, installs dependencies, runs tests, builds with PyInstaller, checks the built EXE against a temporary blank account, and creates `dist/STFC-Advisor-Windows-x64.zip`.

Alternatively, from PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging/Build-Windows.ps1
```

The process-level execution policy applies only to this script invocation; it does not change the system policy. The recipient does not run the build script or install Python.

## GitHub Actions

The `Windows portable app` workflow builds on pushes to `main` and supports **Actions → Windows portable app → Run workflow**. Choose a successful run for the commit you intend to distribute; an older green run does not include newer fixes. A successful run contains the `STFC-Advisor-Windows-x64` artifact. Download it, extract the inner portable ZIP and send that ZIP to the recipient. GitHub artifact downloads require a GitHub login; the ZIP itself does not. Artifacts are retained for 30 days.

## Distribution checks

Automated checks cover a clean account, local API and assets, disabled sync on first run, and duplicate launches. Before distributing a new build, open it on Windows 11 and check browser opening, the tray menu, Quit, desktop shortcut creation, and sheet reconnection after relaunch. A Windows Actions runner cannot confirm the appearance of the tray on a friend's desktop.

This is an unsigned portable build. Signing and an installer are separate distribution work; do not instruct recipients to disable Windows security.

## Personal data

Only the blank profile template and schema are bundled. Saved profiles, backups, Google Sheet links, logs and personal screenshots are excluded. Runtime data lives in `%LOCALAPPDATA%\STFC Advisor\profiles`, independently of the extracted app folder. Upgrades preserve that directory. A backup is created before any changed automatic sync or explicit save.

For isolated diagnostics, `STFC_ADVISOR_DATA_DIR` overrides the runtime data directory. `--headless --port 0` starts without a browser or tray and picks an unused local port. The selected port is recorded in `desktop.json`; `app.log` contains rotating diagnostics.

## Mechanics coverage in a new build

Read [the correction disposition](../docs/AUDIT_CORRECTIONS.md) and [mechanics conventions](../docs/RULES.md). A successful package build checks distribution and startup, not live-game accuracy. Existing accounts are preserved; enter separate hull/shield values and review imported research sources before relying on new estimates.
