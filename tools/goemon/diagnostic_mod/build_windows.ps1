param(
    [string]$Workspace = "",
    [string]$ModsDir = "$env:LOCALAPPDATA\Goemon64Recompiled\mods",
    [switch]$SkipDownload,
    [switch]$NoInstall
)

$ErrorActionPreference = "Stop"
$Project = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
if (!$Workspace) {
    $Workspace = Join-Path (Split-Path $Project -Parent) "GoemonTraceModBuild"
}
$Workspace = [System.IO.Path]::GetFullPath($Workspace)
$TemplateUrl = "https://github.com/klorfmorf/MNSGRecompModTemplate.git"
$ToolUrl = "https://github.com/N64Recomp/N64Recomp/releases/download/mod-tool-release/RecompModTool.exe"

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Fehlt: $Name. Mod-Build erfordert Git, make, Clang mit MIPS-Target und ld.lld. Hinweise in docs/goemon/TRACE_MOD.md."
    }
}
foreach ($name in @("git", "clang", "ld.lld", "make")) {
    Require-Command $name
}

Write-Host "Build-Arbeitsverzeichnis: $Workspace"
if (-not (Test-Path $Workspace)) {
    & git clone --recurse-submodules $TemplateUrl $Workspace
    if ($LASTEXITCODE -ne 0) { throw "Klonen des offiziellen Goemon-Mod-Templates fehlgeschlagen" }
} else {
    if (-not (Test-Path (Join-Path $Workspace ".git"))) {
        throw "Zielverzeichnis existiert, ist aber kein geklontes Mod-Template: $Workspace"
    }
    # Avoid resetting the user's working tree or changing the remote source.
    & git -C $Workspace submodule update --init --recursive
    if ($LASTEXITCODE -ne 0) { throw "Submodule konnten nicht synchronisiert werden" }
}

$Source = Join-Path $Project "tools\goemon\diagnostic_mod\src\goemon_trace.c"
$Manifest = Join-Path $Project "tools\goemon\diagnostic_mod\mod.toml"
if (-not (Test-Path $Source) -or -not (Test-Path $Manifest)) {
    throw "Diagnose-Mod-Dateien fehlen im Feature-Branch"
}

# Replace only the original example hook in the dedicated cloned template.
$TemplateExample = Join-Path $Workspace "src\text_printing.c"
if (Test-Path $TemplateExample) {
    Remove-Item $TemplateExample
}
Copy-Item $Source (Join-Path $Workspace "src\goemon_trace.c") -Force
Copy-Item $Manifest (Join-Path $Workspace "mod.toml") -Force

# The official mod template warns that LLVM 19.1.0 lacks the needed MIPS backend.
$CompilerVersion = (& clang --version | Select-Object -First 1)
Write-Host "Compiler: $CompilerVersion"
$ProbeC = Join-Path $env:TEMP "goemon-mips-probe-$PID.c"
$ProbeO = Join-Path $env:TEMP "goemon-mips-probe-$PID.o"
try {
    "void goemon_probe(void) {}" | Set-Content -Path $ProbeC -Encoding Ascii
    & clang -target mips -mips2 -mabi=32 -c $ProbeC -o $ProbeO
    if ($LASTEXITCODE -ne 0) {
        throw "Clang kann das benötigte MIPS-Target nicht kompilieren. Verwende LLVM 18.1.8."
    }
} finally {
    Remove-Item $ProbeC, $ProbeO -ErrorAction SilentlyContinue
}

$Tool = Join-Path $Workspace "RecompModTool.exe"
if (-not (Test-Path $Tool)) {
    if ($SkipDownload) { throw "RecompModTool.exe fehlt in $Workspace" }
    Write-Host "Lade offizielles RecompModTool herunter ..."
    Invoke-WebRequest -Uri $ToolUrl -OutFile $Tool
}

Push-Location $Workspace
try {
    Write-Host "Kompiliere Goemon Diagnose-Hook (MIPS) ..."
    & make
    if ($LASTEXITCODE -ne 0) { throw "MIPS-Mod-Quellcode konnte nicht kompiliert werden" }

    Write-Host "Erzeuge installierbare .nrm-Mod-Datei ..."
    & $Tool "mod.toml" "build"
    if ($LASTEXITCODE -ne 0) { throw "RecompModTool hat die NRM-Erstellung abgebrochen" }

    $ModFile = Join-Path $Workspace "build\goemon_original_trace.nrm"
    if (-not (Test-Path $ModFile)) {
        $Found = @(Get-ChildItem (Join-Path $Workspace "build") -Filter *.nrm -File)
        if ($Found.Count -ne 1) {
            throw "Mod-Tool hat keine eindeutig zuordenbare .nrm-Datei erzeugt"
        }
        $ModFile = $Found[0].FullName
    }

    Write-Host ""
    Write-Host "Fertig: $ModFile" -ForegroundColor Green
    if (-not $NoInstall) {
        if (-not (Test-Path $ModsDir -PathType Container)) {
            throw "Mod-Verzeichnis nicht gefunden: $ModsDir"
        }
        $InstalledFile = Join-Path $ModsDir ([System.IO.Path]::GetFileName($ModFile))
        Copy-Item -LiteralPath $ModFile -Destination $InstalledFile -Force
        Write-Host "Automatisch installiert: $InstalledFile" -ForegroundColor Green
        Write-Host "Starte Goemon neu und aktiviere die Mod im Mod-Menue."
    } else {
        Write-Host "Manuelle Installation: $ModFile"
    }
} finally {
    Pop-Location
}
