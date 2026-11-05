param(
    [Parameter(Mandatory=$true)][string]$GameExe,
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

$Date = Get-Date -Format "yyyyMMdd-HHmmss"
$Run = Join-Path $Output "run-$Date"
New-Item -ItemType Directory -Force -Path $Run | Out-Null
$StdOut = Join-Path $Run "stdout.log"
$StdErr = Join-Path $Run "stderr.log"
$WorkingDirectory = Split-Path $GameExe -Parent
Write-Host "Starte Goemon und sammle den Original-Trace ..." -ForegroundColor Cyan
Write-Host "Spiele 30-60 Sekunden: Stillstand, Laufen, Drehen, Springen und Angriff."
Write-Host "Danach das Spiel normal schliessen. Die Dateien werden automatisch gesammelt."
Write-Host ""

# Do not pass --show-console: the game's AllocConsole()/freopen(CONOUT$)
# deliberately replaces the standard handles that we redirect here.
$Process = Start-Process -FilePath $GameExe -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $StdOut -RedirectStandardError $StdErr -PassThru -Wait
if ($null -eq $Process) { throw "Goemon konnte nicht gestartet werden" }

$RawLog = Join-Path $Run "goemon_runtime.log"
$outText = if (Test-Path $StdOut) { Get-Content -Raw -Encoding UTF8 $StdOut } else { "" }
$errText = if (Test-Path $StdErr) { Get-Content -Raw -Encoding UTF8 $StdErr } else { "" }
[System.IO.File]::WriteAllText($RawLog, $outText + [Environment]::NewLine + $errText, [System.Text.Encoding]::UTF8)

$ToolRoot = Join-Path $Project "tools\goemon\reference_probe"
function Run-Parser([string]$Name, [string[]]$Arguments, [string]$OutputName = "") {
    $LogFile = Join-Path $Run ($Name + "_tool.log")
    $out = & py -3 @Arguments 2>&1 | Out-String
    $code = $LASTEXITCODE
    [System.IO.File]::WriteAllText($LogFile, "exit=$code" + [Environment]::NewLine + $out, [System.Text.Encoding]::UTF8)
    if ($OutputName -and $code -eq 0) {
        $dest = Join-Path $Run $OutputName
        [System.IO.File]::WriteAllText($dest, $out, [System.Text.Encoding]::UTF8)
    }
    if ($code -ne 0) { Write-Warning "Auswertung $Name ist fehlgeschlagen (Exit $code). Log im ZIP." }
}

if ($outText.Contains("GOEMON_REF,") -or $errText.Contains("GOEMON_REF,")) {
    $CSV = Join-Path $Run "goemon_raw.csv"
    Run-Parser "goemon_csv" @((Join-Path $ToolRoot "log_to_csv.py"),$RawLog,$CSV)
    if (Test-Path $CSV) {
        Run-Parser "actions" @((Join-Path $ToolRoot "action_transitions.py"),$CSV,"--output",(Join-Path $Run "actions.json"))
        Run-Parser "actions_dot" @((Join-Path $ToolRoot "action_transitions.py"),$CSV,"--format","dot","--output",(Join-Path $Run "actions.dot"))
    }
    Run-Parser "timing" @((Join-Path $ToolRoot "tick_analysis.py"),$RawLog,"--output",(Join-Path $Run "ticks.json"))
    Run-Parser "memory" @((Join-Path $ToolRoot "memory_candidates.py"),$RawLog,"--json") "memory_candidates.json"
} else {
    Write-Warning "Keine GOEMON_REF-Zeilen gefunden. Mod-Installation oder Protokollumleitung pruefen."
    Set-Content -Path (Join-Path $Run "ERROR.txt") -Value "Keine GOEMON_REF-Daten. Ist die Mod installiert/aktiviert?"
}

# Never package game ROM, extracted textures, geometry or executable binaries.
$Zip = $Run + ".zip"
$Extensions = @(".log", ".json", ".csv", ".dot", ".txt")
$Files = @(Get-ChildItem $Run -File | Where-Object { $Extensions -contains $_.Extension.ToLowerInvariant() })
if ($Files.Count -eq 0) { throw "Keine auswertbaren Dateien gefunden" }
Compress-Archive -Path $Files.FullName -DestinationPath $Zip -CompressionLevel Optimal
Write-Host "Fertig: $Zip" -ForegroundColor Green
Write-Host "Bitte diese ZIP hier hochladen, nicht die ROM."
