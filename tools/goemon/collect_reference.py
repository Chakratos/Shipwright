#!/usr/bin/env python3
"""One-command, local-only Goemon reference analysis for Windows/Linux/macOS.

Takes an owned original NTSC-U Goemon ROM and a Goemon64Recomp source
checkout. Decompresses in a temporary directory, gathers structured
reverse-engineering diagnostics, then creates a shareable ZIP containing
only JSON, text logs and source revision identifiers. Never includes the ROM,
recompiled machine code, textures, audio or raw extracted game assets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent / "re"))
from decompress_rom import ensure_decompressed_rom


def run_command(command: list[str], log_file: Path, *, cwd: Path) -> dict:
    try:
        result = subprocess.run(command, cwd=cwd, text=True, encoding="utf-8",
                                errors="replace", capture_output=True,
                                timeout=300, check=False)
        log_file.write_text(
            f"Exit code: {result.returncode}\n\nSTDOUT:\n{result.stdout}\n"
            f"\nSTDERR:\n{result.stderr}\n", encoding="utf-8")
        return {"status": "ok" if result.returncode == 0 else "failed",
                "exit_code": result.returncode, "log": log_file.name}
    except (OSError, subprocess.TimeoutExpired) as exc:
        log_file.write_text(str(exc) + "\n", encoding="utf-8")
        return {"status": "failed", "error": str(exc), "log": log_file.name}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path,
                        help="your local original US Goemon .z64, or decompressed .z64")
    parser.add_argument("--goemon", type=Path,
                        help="cloned Goemon64Recomp directory (default: sibling checkout)")
    parser.add_argument("--output", type=Path,
                        help="report directory (default: sibling goemon-reference-report)")
    parser.add_argument("--native", action="store_true",
                        help="also run local native C++20 tests (requires compiler)")
    args = parser.parse_args(argv)

    ship_root = Path(__file__).resolve().parents[2]
    goemon = (args.goemon or ship_root.parent / "Goemon64Recomp").resolve()
    output_base = (args.output or ship_root.parent / "goemon-reference-reports").resolve()
    rom_path = args.rom.resolve()
    sym_path = goemon / "Goemon64RecompSyms" / "mnsg.syms.toml"
    if not sym_path.is_file():
        parser.error(
            f"missing {sym_path}; clone Goemon64Recomp recursively "
            "or run 'git submodule update --init --recursive' in its checkout"
        )
    if not rom_path.is_file():
        parser.error(f"ROM not found: {rom_path}")
    if output_base == ship_root or output_base == goemon or output_base == rom_path.parent:
        parser.error("output directory must not overlap the game checkouts or ROM directory")

    output_base.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=output_base))
    # The ZIP is created after all subprocesses finish; no ROM bytes are
    # placed under the report directory, even transiently.
    results: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="goemon-local-rom-") as temporary:
        temporary_rom = Path(temporary) / "mnsg.decompressed.z64"
        try:
            data = ensure_decompressed_rom(rom_path.read_bytes())
        except (ValueError, OSError) as exc:
            print(f"ERROR: unsupported ROM: {exc}", file=sys.stderr)
            return 2
        temporary_rom.write_bytes(data)
        print("Original Goemon ROM recognized and decompressed locally.")
        python = sys.executable
        scripts = ship_root / "tools" / "goemon" / "re"

        tasks = {
            "player_candidates": [
                python, str(scripts / "scan_player.py"),
                str(temporary_rom), str(sym_path),
                "--top", "300", "--output", str(output / "player_candidates.json")],
            "player_callgraph": [
                python, str(scripts / "analyze_rom.py"),
                str(temporary_rom), str(sym_path),
                "--output", str(output / "player_callgraph.json")],
            "original_character_assets": [
                python, str(scripts / "character_assets.py"),
                str(temporary_rom),
                "--manifest", str(output / "original_character_assets.json")],
        }
        for name, command in tasks.items():
            print(f"Analyzing {name}...")
            results[name] = run_command(
                command, output / (name + ".log"), cwd=ship_root
            )
        # Deliberately do not include original ROM bytes, image slices or
        # custom patches generated from the original game.
        source_hash = hashlib.sha256(data).hexdigest()
        rom_size = len(data)

    tests_command = [
        sys.executable, str(ship_root / "tools" / "goemon" / "verify.py"),
    ]
    if args.native:
        tests_command.append("--native")
    results["local_tests"] = run_command(
        tests_command, output / "local_tests.log", cwd=ship_root)

    def revision(repo_dir: Path) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
                text=True, capture_output=True, timeout=10, check=False)
            return result.stdout.strip() if result.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired):
            return None

    summary = {
        "schema_version": 1,
        "rom": "NTSC-U Mystical Ninja Starring Goemon, decompressed in memory",
        "rom_sha256": source_hash,
        "decompressed_rom_size": rom_size,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "shipwright_commit": revision(ship_root),
        "goemon_commit": revision(goemon),
        "goemon_symbols_commit": revision(goemon / "Goemon64RecompSyms"),
        "jobs": results,
        "privacy": "No ROM, extracted art, textures, audio or machine-code blobs included."
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n",
                                         encoding="utf-8")
    archive = output.with_suffix(".zip")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for item in sorted(output.iterdir()):
            if item.is_file() and item.suffix in {".json", ".log", ".txt"}:
                bundle.write(item, arcname=item.name)
    print(f"Report ZIP: {archive}")
    print(f"Tasks successful: {sum(x['status'] == 'ok' for x in results.values())}/{len(results)}")
    print("Share only the report ZIP, not the ROM or raw character assets.")
    return 0 if all(x["status"] == "ok" for x in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
