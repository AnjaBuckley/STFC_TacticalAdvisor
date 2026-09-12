@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0packaging\Build-Windows.ps1"
if errorlevel 1 (
  echo Build failed. Read the message above.
  pause
  exit /b 1
)
echo The portable Windows ZIP is in the dist folder.
pause
