@echo off
setlocal
set "SCRIPT=C:\actions-runner-goemon\_work\Shipwright\Shipwright\tools\goemon\diagnostic_mod\install_and_record_windows.ps1"
if not exist "%SCRIPT%" (
  echo Goemon-Quellcode auf dem Windows-Runner nicht gefunden: %SCRIPT%
  pause
  exit /b 2
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%"
if errorlevel 1 (
  echo.
  echo Der Original-Animations-Capture wurde nicht abgeschlossen.
  pause
  exit /b 1
)
echo.
echo Original-Aufzeichnung verarbeitet. Dateien bleiben auf diesem PC.
pause
