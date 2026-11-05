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

# Prefer already-installed Clang if it supports MIPS. Otherwise use an
# official portable LLVM 18.1.8 archive in a sibling directory; no admin
# rights, global PATH modification, or GNU make required.
function Test-MipsClang([string]$Compiler) {
    if (-not (Test-Path -LiteralPath $Compiler -PathType Leaf)) { return $false }
    $SourceFile = Join-Path $env:TEMP ("goemon-clang-probe-" + $PID + ".c")
    $ObjectFile = Join-Path $env:TEMP ("goemon-clang-probe-" + $PID + ".o")
    try {
        Set-Content -LiteralPath $SourceFile -Value "void probe(void) {}" -Encoding ascii
        & $Compiler -target mips -mips2 -mabi=32 -c $SourceFile -o $ObjectFile 2>$null
        return ($LASTEXITCODE -eq 0 -and (Test-Path $ObjectFile -PathType Leaf))
    } catch {
        return $false
    } finally {
        Remove-Item -LiteralPath $SourceFile,$ObjectFile -Force -ErrorAction SilentlyContinue
    }
}
function Find-PortableClang([string]$Directory) {
    if (-not (Test-Path $Directory -PathType Container)) { return $null }
    $Files = @(Get-ChildItem -LiteralPath $Directory -Filter clang.exe -File -Recurse)
    foreach ($File in $Files) {
        $LldFile = Join-Path $File.DirectoryName "ld.lld.exe"
        if ((Test-Path $LldFile -PathType Leaf) -and (Test-MipsClang $File.FullName)) {
            return $File.FullName
        }
    }
    return $null
}
function Invoke-CheckedNative([string]$File, [string[]]$Arguments) {
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Kommando fehlgeschlagen mit Exitcode $LASTEXITCODE : $File"
    }
}

if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
    throw "Git for Windows ist nicht installiert."
}
$ClangPath = $null
$PathClang = Get-Command clang.exe -ErrorAction SilentlyContinue
$Candidates = @()
if ($PathClang) { $Candidates += $PathClang.Source }
$Candidates += (Join-Path $env:ProgramFiles "LLVM\bin\clang.exe")
$Candidates += (Join-Path $env:LOCALAPPDATA "Programs\LLVM\bin\clang.exe")
foreach ($Candidate in $Candidates) {
    $CandidateLld = Join-Path (Split-Path $Candidate -Parent) "ld.lld.exe"
    if ((Test-Path $CandidateLld -PathType Leaf) -and (Test-MipsClang $Candidate)) {
        $ClangPath = $Candidate
        break
    }
}
$PortableDir = Join-Path (Split-Path $Workspace -Parent) "GoemonTraceLLVM"
if (-not $ClangPath) { $ClangPath = Find-PortableClang $PortableDir }

if (-not $ClangPath) {
    if ($SkipDownload) {
        throw "Clang mit MIPS-Backend fehlt; ohne -SkipDownload wird LLVM 18.1.8 automatisch geladen."
    }
    if (-not (Get-Command tar.exe -ErrorAction SilentlyContinue)) {
        throw "Windows tar.exe fehlt; es wird zum Entpacken der portablen LLVM-Toolchain benoetigt."
    }
    New-Item -ItemType Directory -Force -Path $PortableDir | Out-Null
    $Archive = Join-Path $PortableDir "clang-llvm-18.1.8-win64.tar.xz"
    if (-not (Test-Path $Archive -PathType Leaf)) {
        $LLVMUrl = "https://github.com/llvm/llvm-project/releases/download/llvmorg-18.1.8/clang%2Bllvm-18.1.8-x86_64-pc-windows-msvc.tar.xz"
        $PartialArchive = $Archive + ".part"
        Write-Host "Lade offizielles portables LLVM 18.1.8 (~982 MB) ..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri $LLVMUrl -OutFile $PartialArchive -UseBasicParsing
        Move-Item -LiteralPath $PartialArchive -Destination $Archive -Force
    }
    $ExtractTo = Join-Path $PortableDir "extracted"
    New-Item -ItemType Directory -Force -Path $ExtractTo | Out-Null
    Write-Host "Entpacke LLVM lokal (ohne Administratorrechte) ..."
    Invoke-CheckedNative "tar.exe" @("-xJf",$Archive,"-C",$ExtractTo)
    $ClangPath = Find-PortableClang $ExtractTo
    if (-not $ClangPath) {
        throw "LLVM-Archiv entpackt, aber kein Clang mit MIPS-Target gefunden: $PortableDir"
    }
}
$LldPath = Join-Path (Split-Path $ClangPath -Parent) "ld.lld.exe"
Write-Host "Compiler: $ClangPath" -ForegroundColor Green
& $ClangPath --version | Select-Object -First 1

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
$GateHeader = Join-Path $Project "tools\goemon\diagnostic_mod\src\goemon_capture_gate.h"
$Manifest = Join-Path $Project "tools\goemon\diagnostic_mod\mod.toml"
if (-not (Test-Path $Source) -or -not (Test-Path $GateHeader) -or -not (Test-Path $Manifest)) {
    throw "Diagnose-Mod-Dateien fehlen im Feature-Branch"
}

# Replace only the original example hook in the dedicated cloned template.
$TemplateExample = Join-Path $Workspace "src\text_printing.c"
if (Test-Path $TemplateExample) {
    Remove-Item $TemplateExample
}
Copy-Item $Source (Join-Path $Workspace "src\goemon_trace.c") -Force
Copy-Item $GateHeader (Join-Path $Workspace "src\goemon_capture_gate.h") -Force
Copy-Item $Manifest (Join-Path $Workspace "mod.toml") -Force

$Tool = Join-Path $Workspace "RecompModTool.exe"
if (-not (Test-Path $Tool)) {
    if ($SkipDownload) { throw "RecompModTool.exe fehlt in $Workspace" }
    Write-Host "Lade offizielles RecompModTool herunter ..."
    Invoke-WebRequest -Uri $ToolUrl -OutFile $Tool
}

Push-Location $Workspace
try {
    # Equivalent to the official MNSGRecompModTemplate Makefile flags.
    # One C file and no assembly sources, so make is not needed.
    New-Item -ItemType Directory -Force -Path (Join-Path $Workspace "build\src") | Out-Null
    Write-Host "Kompiliere Goemon Diagnose-Hook direkt mit Clang (MIPS) ..."
    Invoke-CheckedNative $ClangPath @(
        "-target","mips","-mips2","-mabi=32","-O2","-G0",
        "-mno-abicalls","-mno-odd-spreg","-mno-check-zero-division",
        "-fomit-frame-pointer","-ffast-math","-fno-unsafe-math-optimizations",
        "-fno-builtin-memset","-Wall","-Wextra",
        "-Wno-incompatible-library-redeclaration",
        "-Wno-unused-parameter","-Wno-unknown-pragmas",
        "-Wno-unused-variable","-Wno-missing-braces",
        "-Wno-unsupported-floating-point-opt","-Werror=section",
        "-nostdinc","-D_LANGUAGE_C","-DMIPS","-DF3DEX_GBI",
        "-I","include","-I","include/dummy_headers",
        "-I","mnsg/include","-I","mnsg/libultra/include","-I","mnsg/src",
        "src/goemon_trace.c","-c","-o","build/src/goemon_trace.o"
    )
    Write-Host "Linke Mod-ELF direkt mit ld.lld ..."
    Invoke-CheckedNative $LldPath @(
        "build/src/goemon_trace.o","-nostdlib","-T","mod.ld",
        "-Map","build/mod.map","--unresolved-symbols=ignore-all",
        "--emit-relocs","-e","0","--no-nmagic","-o","build/mod.elf"
    )

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
