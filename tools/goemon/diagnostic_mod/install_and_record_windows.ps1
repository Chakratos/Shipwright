param(
    [string]$GameExe = "",
    [string]$ModsDir = (Join-Path $env:LOCALAPPDATA 'Goemon64Recompiled\mods')
)
# One-click original MNSG skeletal capture. The .nrm was compiled by
# the self-hosted runner and contains only hook code, never game assets.
$ErrorActionPreference = 'Stop'
$Project = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$ExpectedBinary = Join-Path $env:USERPROFILE 'Desktop\SoH Goemon Test\goemon_original_trace.nrm'
$RunnerBinary = 'C:\actions-runner-goemon\original-animation-capture\goemon_original_trace.nrm'

$ModFile = if (Test-Path -LiteralPath $ExpectedBinary -PathType Leaf) {
    $ExpectedBinary
} elseif (Test-Path -LiteralPath $RunnerBinary -PathType Leaf) {
    $RunnerBinary
} else {
    throw 'Die lokale N64-Animations-Capture-Mod ist nicht vorhanden.'
}
New-Item -ItemType Directory -Force -Path $ModsDir | Out-Null
Copy-Item -LiteralPath $ModFile -Destination (Join-Path $ModsDir 'goemon_original_trace.nrm') -Force
Write-Host "Original-Goemon-Skelett-Capture installiert: $ModsDir" -ForegroundColor Green

if (-not $GameExe) {
    $Candidates = @(
        (Join-Path $env:USERPROFILE 'Desktop\Goemon64Recompiled\Goemon64Recompiled.exe'),
        (Join-Path $env:USERPROFILE 'Desktop\Goemon64Recompiled.exe'),
        (Join-Path $env:USERPROFILE 'Downloads\Goemon64Recompiled\Goemon64Recompiled.exe'),
        (Join-Path $env:ProgramFiles 'Goemon64Recompiled\Goemon64Recompiled.exe'),
        'C:\Goemon64Recompiled\Goemon64Recompiled.exe'
    )
    foreach ($Candidate in $Candidates) {
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            $GameExe = $Candidate
            break
        }
    }
}
if (-not $GameExe -or -not (Test-Path -LiteralPath $GameExe -PathType Leaf)) {
    throw 'Original Goemon64Recompiled.exe nicht gefunden. Skript erneut mit -GameExe "Pfad" starten.'
}
Write-Host ""
Write-Host 'Original-Spiel wird gestartet. Im Mod-Menue aktivieren:' -ForegroundColor Cyan
Write-Host '  Goemon Original Animation & Reference Trace'
Write-Host '  Original-Skelettanimationen aufnehmen: Originalanimation aufnehmen'
Write-Host '  Danach Figur bewegen, drehen, springen und angreifen.'
Write-Host '  Fuer alle vier Figuren die Charaktere im Spiel wechseln.'
Write-Host 'Nach Schliessen des Spiels werden echte Matrix-Poseclips automatisch verarbeitet.'
Write-Host ""

& (Join-Path $PSScriptRoot 'capture_windows.ps1') -GameExe $GameExe
if ($LASTEXITCODE -ne 0) {
    throw "Goemon-Capture-Pipeline konnte Originalanimation nicht verarbeiten (Exit $LASTEXITCODE)"
}
