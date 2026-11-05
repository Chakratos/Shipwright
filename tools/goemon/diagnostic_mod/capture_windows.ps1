param(
    [string]$GameExe = "$env:USERPROFILE\Desktop\Goemon64Recompiled\Goemon64Recompiled.exe",
    [string]$Output = ""
)

$ErrorActionPreference = "Stop"
$Project = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$GameExe = (Resolve-Path $GameExe).Path
if (-not $Output) { $Output = Join-Path (Split-Path $Project -Parent) "GoemonTraceRuns" }
$Output = [System.IO.Path]::GetFullPath($Output)
if (-not (Test-Path $GameExe -PathType Leaf)) {
    throw "Goemon64Recompiled.exe nicht gefunden: $GameExe"
}
if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher 'py -3' fehlt."
}

# Fail before launching the game if any postprocessor has a Python syntax
# defect. The 2026-11-05 v0.3 capture exposed why this guard matters.
$ScriptsToCheck = @(
    (Join-Path $PSScriptRoot "reprocess_log.py"),
    (Join-Path $Project "tools\goemon\reference_probe\log_to_csv.py"),
    (Join-Path $Project "tools\goemon\reference_probe\action_transitions.py"),
    (Join-Path $Project "tools\goemon\reference_probe\tick_analysis.py"),
    (Join-Path $Project "tools\goemon\reference_probe\memory_candidates.py"),
    (Join-Path $Project "tools\goemon\reference_probe\character_coverage.py"),
    (Join-Path $Project "tools\goemon\reference_probe\jump_trace_fit.py")
)
& py -3 -m py_compile @ScriptsToCheck
if ($LASTEXITCODE -ne 0) {
    throw "Fehler in einem Auswertungsskript. Aufnahme nicht gestartet; vorhandene Spielaufzeichnungen bleiben unangetastet."
}

$Date = Get-Date -Format "yyyyMMdd-HHmmss"
$Run = Join-Path $Output "run-$Date"
New-Item -ItemType Directory -Force -Path $Run | Out-Null
$StdOut = Join-Path $Run "stdout.log"
$StdErr = Join-Path $Run "stderr.log"
$WorkingDirectory = Split-Path $GameExe -Parent
Write-Host "Starte Goemon und sammle den Original-Trace ..." -ForegroundColor Cyan
Write-Host "Die Aufnahme ist standardmaessig AUS."
Write-Host "Lade deinen Spielstand, aktiviere im Mod-Menue Original-Daten aufnehmen,"
Write-Host "verlasse das Menue und bewege den Stick, um die Aufnahme zu starten."
Write-Host "Danach: Stillstand, Laufen, Drehen, Springen und Angriff."
Write-Host "Zur Beendigung Aufnahme im Mod-Menue auf Aus stellen."
Write-Host "Danach das Spiel normal schliessen. Die Dateien werden automatisch gesammelt."
Write-Host ""

# Do not pass --show-console: the game's AllocConsole()/freopen(CONOUT$)
# deliberately replaces the standard handles that we redirect here.
$Process = Start-Process -FilePath $GameExe -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $StdOut -RedirectStandardError $StdErr -PassThru -Wait
if ($null -eq $Process) { throw "Goemon konnte nicht gestartet werden" }

# Delegate all analysis to the same recoverable tool used for existing runs.
# A failed individual parser is logged and NEVER discards the original trace.
$Reprocess = Join-Path $PSScriptRoot "reprocess_log.py"
& py -3 $Reprocess --run $Run
if ($LASTEXITCODE -ne 0) {
    throw "Die Aufzeichnung liegt unter $Run, aber die Auswertung wurde nicht abgeschlossen. Sie kann jederzeit separat wiederholt werden."
}
