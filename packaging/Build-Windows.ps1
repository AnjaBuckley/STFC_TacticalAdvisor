$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
Set-StrictMode -Version Latest
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    if ($env:OS -ne 'Windows_NT') { throw 'Build this package on Windows 11 or a Windows GitHub Actions runner.' }
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install Python 3.12 (64-bit) from python.org on this build PC, then run again. Recipients do not need Python.' }
    & py -3.12 -m venv .venv-windows-build
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python 3.12 build environment.' }
    $python = Join-Path $root '.venv-windows-build\Scripts\python.exe'
    & $python -m pip install -r requirements.txt -r packaging/requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; no distribution produced.' }
    & $python -m PyInstaller --noconfirm --clean stfc_advisor.spec
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
    Copy-Item packaging/START-HERE.txt dist/STFC-Advisor/START-HERE.txt -Force
    Copy-Item packaging/Create-Desktop-Shortcut.vbs dist/STFC-Advisor/Create-Desktop-Shortcut.vbs -Force
    & $python packaging/smoke_bundle.py dist/STFC-Advisor/STFC-Advisor.exe
    if ($LASTEXITCODE -ne 0) { throw 'Packaged app smoke test failed; do not distribute.' }
    Compress-Archive -Path dist/STFC-Advisor -DestinationPath dist/STFC-Advisor-Windows-x64.zip -Force
    Write-Host "Ready: $root\dist\STFC-Advisor-Windows-x64.zip"
    Write-Host 'Before sharing, double-click the EXE and check Open app and Quit in the system tray.'
} finally { Pop-Location }
