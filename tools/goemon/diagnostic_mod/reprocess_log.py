#!/usr/bin/env python3
"""Reprocess an existing Goemon64Recompiled capture; never starts the game.

Selects the most recent run with a saved raw log by default. Every parser
failure is nonfatal: retain original stdout/stderr and package them in the ZIP.
Only logs and derived measurements are included (no original game assets).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile


PROJECT = Path(__file__).resolve().parents[3]
TOOLS = PROJECT / "tools" / "goemon" / "reference_probe"
DEFAULT_RUNS = PROJECT.parent / "GoemonTraceRuns"
ALLOWED_SUFFIXES = frozenset({".log", ".json", ".csv", ".dot", ".txt"})


def find_run(base: Path) -> Path:
    if not base.is_dir():
        raise ValueError(f"No capture directory: {base}")
    directories = sorted(
        (p for p in base.glob("run-*")
         if p.is_dir() and (
             (p / "goemon_runtime.log").is_file()
             or (p / "stdout.log").is_file()
             or (p / "stderr.log").is_file())),
        key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True,
    )
    if not directories:
        raise ValueError(f"No saved Goemon run found in {base}")
    return directories[0]


def ensure_raw_log(folder: Path) -> Path:
    raw = folder / "goemon_runtime.log"
    if raw.is_file() and raw.stat().st_size:
        return raw
    stdout = folder / "stdout.log"
    stderr = folder / "stderr.log"
    if not stdout.is_file() and not stderr.is_file():
        raise ValueError(f"No raw trace logs in {folder}")
    out = stdout.read_text(encoding="utf-8", errors="replace") if stdout.is_file() else ""
    err = stderr.read_text(encoding="utf-8", errors="replace") if stderr.is_file() else ""
    raw.write_text(out + "\n" + err, encoding="utf-8")
    return raw


def run_parser(name: str, args: list[str], folder: Path,
               output: Path | None = None) -> dict[str, object]:
    command = [sys.executable, *args]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", cwd=PROJECT, timeout=180,
        )
        exit_code = result.returncode
        stdout, stderr = result.stdout, result.stderr
    except (OSError, subprocess.TimeoutExpired) as error:
        exit_code, stdout, stderr = 127, "", f"{type(error).__name__}: {error}\n"
    (folder / f"{name}_tool.log").write_text(
        f"exit={exit_code}\ncommand={' '.join(Path(c).name if i < 2 else c for i, c in enumerate(command))}\n"
        + stdout + ("\nSTDERR:\n" + stderr if stderr else ""),
        encoding="utf-8",
    )
    if exit_code == 0 and output is not None:
        output.write_text(stdout, encoding="utf-8")
    return {"exit_code": exit_code, "status": "ok" if exit_code == 0 else "failed"}


def reprocess(folder: Path) -> Path:
    folder = folder.resolve()
    if not folder.is_dir():
        raise ValueError(f"Capture folder does not exist: {folder}")
    raw = ensure_raw_log(folder)
    text = raw.read_text(encoding="utf-8", errors="replace")
    # This can include 2400 GOEMON_REF rows and max 128 full Player structures.
    count = sum("GOEMON_REF," in line for line in text.splitlines())
    status: dict[str, object] = {
        "original_trace": raw.name,
        "reference_samples": count,
        "recording_armed": "GOEMON_TRACE_ARMED" in text,
        "recording_started": "GOEMON_TRACE_BEGIN" in text,
        "recording_ended": "GOEMON_TRACE_END" in text,
        "parsers": {},
    }
    parsers: dict[str, dict[str, object]] = status["parsers"]  # type: ignore[assignment]
    if count:
        csv = folder / "goemon_raw.csv"
        parsers["csv"] = run_parser(
            "goemon_csv",
            [str(TOOLS / "log_to_csv.py"), str(raw), str(csv)],
            folder,
        )
        if csv.is_file():
            parsers["character_coverage"] = run_parser(
                "character_coverage",
                [str(TOOLS / "character_coverage.py"), str(csv),
                 "--output", str(folder / "character_coverage.json")],
                folder,
            )
            parsers["actions"] = run_parser(
                "actions",
                [str(TOOLS / "action_transitions.py"), str(csv),
                 "--output", str(folder / "actions.json")],
                folder,
            )
            parsers["actions_dot"] = run_parser(
                "actions_dot",
                [str(TOOLS / "action_transitions.py"), str(csv),
                 "--format", "dot", "--output", str(folder / "actions.dot")],
                folder,
            )
        parsers["timing"] = run_parser(
            "timing",
            [str(TOOLS / "tick_analysis.py"), str(raw),
             "--output", str(folder / "ticks.json")],
            folder,
        )
        parsers["memory"] = run_parser(
            "memory",
            [str(TOOLS / "memory_candidates.py"), str(raw), "--json"],
            folder, folder / "memory_candidates.json",
        )
    else:
        status["note"] = (
            "No GOEMON_REF in saved log. Check that the diagnostic mod was "
            "enabled, armed in-game and the player actually moved."
        )
        (folder / "ERROR.txt").write_text(str(status["note"]) + "\n", encoding="utf-8")

    (folder / "capture_summary.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )

    archive = folder.with_suffix(".zip")
    with zipfile.ZipFile(archive, mode="w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=7) as zip_file:
        for item in sorted(folder.iterdir()):
            if item.is_file() and item.suffix.lower() in ALLOWED_SUFFIXES:
                zip_file.write(item, arcname=item.name)
    print(f"Recording: {folder}")
    print(f"GOEMON_REF samples: {count}")
    for name, report in parsers.items():
        print(f"  {name}: {report['status']} (exit {report['exit_code']})")
    print(f"ZIP created: {archive}")
    return archive


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, help="Existing run directory (default: newest)")
    parser.add_argument("--runs-dir", type=Path, default=DEFAULT_RUNS)
    args = parser.parse_args(argv)
    try:
        folder = args.run if args.run else find_run(args.runs_dir)
        reprocess(folder)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
