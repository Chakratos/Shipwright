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
    # Original mod v0.2 captured up to 2400 reference frames and 128 raw
    # Player snapshots. Count the latter per ID too: later characters may
    # have GOEMON_REF coverage but no GOEMON_MEM after the snapshot cap.
    count = 0
    memory_by_character: dict[int, int] = {}
    task_samples = 0
    original_bone_samples = 0
    original_matrix_samples = 0
    original_root_maps = 0
    object_samples = 0
    object_y_by_character: dict[int, list[float]] = {}
    object_animation_by_character: dict[int, list[float]] = {}
    for line in text.splitlines():
        if "GOEMON_ANIM_BONE," in line:
            original_bone_samples += 1
        if "GOEMON_ANIM_MATRIX," in line:
            original_matrix_samples += 1
        if "GOEMON_ANIM_ROOT," in line:
            original_root_maps += 1
        if "GOEMON_REF," in line:
            count += 1
        if "GOEMON_TASK," in line:
            task_samples += 1
        object_marker = line.find("GOEMON_OBJ,")
        if object_marker >= 0:
            fields = line[object_marker + len("GOEMON_OBJ,"):].strip().split(",")
            if len(fields) == 10:
                try:
                    ident = int(fields[1])
                    object_y = float(fields[4])
                    animation = float(fields[9])
                    if abs(object_y) < 1_000_000_000 and abs(animation) < 1_000_000_000:
                        object_y_by_character.setdefault(ident, []).append(object_y)
                        object_animation_by_character.setdefault(ident, []).append(animation)
                        object_samples += 1
                except ValueError:
                    pass
        marker = line.find("GOEMON_MEM,")
        if marker >= 0:
            values = line[marker + len("GOEMON_MEM,"):].split(",", 4)
            if len(values) >= 3:
                try:
                    character_id = int(values[2])
                except ValueError:
                    continue
                memory_by_character[character_id] = (
                    memory_by_character.get(character_id, 0) + 1
                )
    status: dict[str, object] = {
        "original_trace": raw.name,
        "reference_samples": count,
        "raw_player_memory_samples": sum(memory_by_character.values()),
        "raw_player_memory_samples_by_character": {
            str(key): value for key, value in sorted(memory_by_character.items())
        },
        "player_task_samples": task_samples,
        "original_skeletal_bone_events": original_bone_samples,
        "original_skeletal_matrix_events": original_matrix_samples,
        "original_render_root_overlay_mappings": original_root_maps,
        "player_object_samples": object_samples,
        "player_object_y_range_by_character": {
            str(key): [min(values), max(values)]
            for key, values in sorted(object_y_by_character.items())
        },
        "player_object_animation_range_by_character": {
            str(key): [min(values), max(values)]
            for key, values in sorted(object_animation_by_character.items())
        },
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
        parsers["player_state"] = run_parser(
            "player_state",
            [str(TOOLS / "player_state_fit.py"), str(raw),
             "--output", str(folder / "player_state.json")],
            folder,
        )
        if task_samples > 0 and csv.is_file():
            parsers["ship_replay"] = run_parser(
                "ship_replay",
                [str(TOOLS / "export_motion_replay.py"), str(csv), str(raw),
                 "--output", str(folder / "goemon_original_motion_replay.csv")],
                folder,
            )
        if task_samples > 0 and object_samples > 0 and csv.is_file():
            parsers["physics_fit"] = run_parser(
                "physics_fit",
                [str(TOOLS / "jump_trace_fit.py"), str(csv), str(raw),
                 "--output", str(folder / "physics_fit.json")],
                folder,
            )
            parsers["horizontal_fit"] = run_parser(
                "horizontal_fit",
                [str(TOOLS / "horizontal_trace_fit.py"), str(csv), str(raw),
                 "--output", str(folder / "horizontal_fit.json")],
                folder,
            )
            parsers["animation_fit"] = run_parser(
                "animation_fit",
                [str(TOOLS / "animation_trace_fit.py"), str(csv), str(raw),
                 "--output", str(folder / "animation_fit.json")],
                folder,
            )
            parsers["yaw_fit"] = run_parser(
                "yaw_fit",
                [str(TOOLS / "yaw_trace_fit.py"), str(csv), str(raw),
                 "--output", str(folder / "yaw_fit.json")],
                folder,
            )
            parsers["steering_fit"] = run_parser(
                "steering_fit",
                [str(TOOLS / "steering_trace_fit.py"), str(csv), str(raw),
                 "--output", str(folder / "steering_fit.json")],
                folder,
            )
            parsers["vector_fit"] = run_parser(
                "vector_fit",
                [str(TOOLS / "vector_trace_fit.py"), str(csv), str(raw),
                 "--output", str(folder / "vector_fit.json")],
                folder,
            )
    else:
        status["note"] = (
            "No GOEMON_REF in saved log. Check that the diagnostic mod was "
            "enabled, armed in-game and the player actually moved."
        )
        (folder / "ERROR.txt").write_text(str(status["note"]) + "\n", encoding="utf-8")

    # This parser handles original MNSG matrices independently of the
    # older GOEMON_REF physics logs, which may be absent when only the
    # new skeleton-capture option is enabled.
    if original_bone_samples > 0 and original_matrix_samples > 0:
        source_meshes = Path(r"C:\actions-runner-goemon\original-rom-meshes")
        command = [
            str(TOOLS / "original_skeletal_poses.py"), str(raw),
            "--output", str(folder / "original_skeletal_poses.json"),
        ]
        if source_meshes.is_dir():
            command.extend(["--meshes-dir", str(source_meshes)])
        parsers["original_skeletal_poses"] = run_parser(
            "original_skeletal_poses", command, folder
        )


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
