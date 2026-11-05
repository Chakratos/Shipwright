#!/usr/bin/env python3
"""Replay observed original Goemon jump motion against genuine runtime traces.

The 18-column GOEMON_REF CSV and a GOEMON_TASK/GOEMON_OBJ runtime log
must come from the same capture. No original ROM or assets are required.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
import json
from pathlib import Path
import struct
import sys


def read_data(csv_path: Path, log_path: Path) -> list[dict]:
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "sample", "game_frames", "character_id", "action_id",
            "buttons_held", "buttons_pressed", "root_pos_x", "root_pos_y",
            "root_pos_z",
        }
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("GOEMON_REF CSV missing required columns")
        rows = []
        for index, values in enumerate(reader):
            row = {
                key: int(values[key])
                for key in (
                    "sample", "game_frames", "character_id", "action_id",
                    "buttons_held", "buttons_pressed",
                )
            }
            row.update({
                key: float(values[key])
                for key in ("root_pos_x", "root_pos_y", "root_pos_z")
            })
            if row["sample"] != index:
                raise ValueError(f"non-consecutive GOEMON_REF index {index}")
            rows.append(row)

    tasks: dict[int, tuple] = {}
    objects: dict[int, tuple] = {}
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        task_at = line.find("GOEMON_TASK,")
        if task_at >= 0:
            fields = line[task_at + len("GOEMON_TASK,"):].strip().split(",")
            if len(fields) != 5:
                raise ValueError("invalid GOEMON_TASK record")
            sample = int(fields[0])
            raw = bytes.fromhex(fields[4])
            if len(raw) != 0xF0:
                raise ValueError(f"invalid original PlayerTask length, sample {sample}")
            if sample in tasks:
                raise ValueError(f"duplicate original task sample {sample}")
            task_floats = tuple(
                struct.unpack_from(">f", raw, offset)[0]
                for offset in (0x68, 0x6C, 0x70, 0xA4)
            )
            tasks[sample] = (int(fields[2]), int(fields[3]), task_floats)
        object_at = line.find("GOEMON_OBJ,")
        if object_at >= 0:
            fields = line[object_at + len("GOEMON_OBJ,"):].strip().split(",")
            if len(fields) != 10:
                raise ValueError("invalid GOEMON_OBJ record")
            sample = int(fields[0])
            if sample in objects:
                raise ValueError(f"duplicate original object sample {sample}")
            objects[sample] = (
                int(fields[1]), int(fields[2]), tuple(map(float, fields[3:6]))
            )

    for index, row in enumerate(rows):
        if index not in tasks or index not in objects:
            raise ValueError(f"missing original task/object sample {index}")
        task = tasks[index]
        obj = objects[index]
        if task[0] != row["character_id"] or obj[0] != row["character_id"]:
            raise ValueError(f"character-ID mismatch at sample {index}")
        if task[1] != row["action_id"] or obj[1] != row["action_id"]:
            raise ValueError(f"action-ID mismatch at sample {index}")
        row.update({
            "velocity_x": task[2][0],
            "vertical_step": task[2][1],
            "velocity_z": task[2][2],
            "next_vertical_step": task[2][3],
            "object_x": obj[2][0],
            "object_y": obj[2][1],
            "object_z": obj[2][2],
        })
    return rows


def analyze(rows: list[dict]) -> dict:
    tolerance = 0.002
    continuous = 0
    matches: Counter[str] = Counter()
    mismatches: Counter[str] = Counter()
    for previous, current in zip(rows, rows[1:]):
        if (current["character_id"] != previous["character_id"]
                or current["game_frames"] - previous["game_frames"] != 1):
            continue
        continuous += 1
        for axis, field, position in (
            ("x", "velocity_x", "root_pos_x"),
            ("y", "vertical_step", "object_y"),
            ("z", "velocity_z", "root_pos_z"),
        ):
            difference = abs(current[position] - previous[position] - current[field])
            if difference < tolerance:
                matches[axis] += 1
            else:
                mismatches[axis] += 1

    starts = [
        index for index, row in enumerate(rows)
        if row["action_id"] == 23
        and (index == 0 or rows[index - 1]["action_id"] != 23)
        and (row["buttons_pressed"] & 0x8000) != 0
    ]
    replays: list[dict] = []
    for start in starts:
        initial = rows[start]
        entry = {
            "sample": start,
            "character_id": initial["character_id"],
            "initial_vertical_impulse": round(initial["vertical_step"], 6),
            "status": "unknown",
            "steps_compared": 0,
            "max_height": 0.0,
            "a_held_steps": 0,
            "maximum_absolute_error": 0.0,
        }
        if (start and abs(rows[start - 1]["root_pos_y"] -
                          initial["root_pos_y"]) > 0.01):
            entry["status"] = "moving_ground_at_start"
            replays.append(entry)
            continue

        baseline = initial["root_pos_y"]
        predicted_height = 0.0
        predicted_next = initial["vertical_step"]
        for index in range(start, min(start + 40, len(rows))):
            row = rows[index]
            if row["character_id"] != initial["character_id"]:
                entry["status"] = "character_changed"
                break
            if (index > start and
                    row["game_frames"] - rows[index - 1]["game_frames"] != 1):
                entry["status"] = "frame_discontinuity"
                break
            if abs(row["root_pos_y"] - baseline) > 0.01:
                entry["status"] = "moving_ground"
                break

            held = bool(row["buttons_held"] & 0x8000)
            entry["a_held_steps"] += int(held)
            step = predicted_next
            if not held and step > 2.0:
                step = 2.0
            landed = predicted_height + step <= 0.0001
            if landed:
                step = -predicted_height
                predicted_height = 0.0
                predicted_next = 0.0
            else:
                predicted_height += step
                predicted_next = step - 2.0 / 3.0

            actual_height = row["object_y"] - row["root_pos_y"]
            differences = (
                abs(actual_height - predicted_height),
                abs(row["vertical_step"] - step),
                abs(row["next_vertical_step"] - predicted_next),
            )
            entry["maximum_absolute_error"] = max(
                entry["maximum_absolute_error"], *differences
            )
            entry["max_height"] = max(entry["max_height"], actual_height)
            entry["steps_compared"] += 1
            if max(differences) > tolerance:
                entry["status"] = "mismatch"
                break
            if landed:
                entry["status"] = "exact_full_replay"
                break
        if entry["status"] == "unknown":
            entry["status"] = "incomplete_trace"
        entry["maximum_absolute_error"] = round(
            entry["maximum_absolute_error"], 6
        )
        entry["max_height"] = round(entry["max_height"], 6)
        replays.append(entry)

    statuses = Counter(entry["status"] for entry in replays)
    return {
        "samples": len(rows),
        "measured_player_task_offsets": {
            "horizontal_x": "0x68", "vertical_applied": "0x6c",
            "horizontal_z": "0x70", "vertical_next": "0xa4",
        },
        "consecutive_single_game_update_pairs": continuous,
        "delta_equals_task_velocity_within_0_002": {
            axis: int(matches[axis]) for axis in ("x", "y", "z")
        },
        "nonmatching_pairs": {
            axis: int(mismatches[axis]) for axis in ("x", "y", "z")
        },
        "measured_gravity_per_update": -2.0 / 3.0,
        "measured_upward_release_cap": 2.0,
        "jump_start_events": len(starts),
        "jump_replay_status": dict(sorted(statuses.items())),
        "jump_replays": replays,
        "limits": (
            "Flat-ground model only. Root height changes on slopes; "
            "collisions may block X/Z. The 2.0-impulse variant is measured "
            "but its environment/state activation remains unidentified."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_csv", type=Path)
    parser.add_argument("runtime_log", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        output = json.dumps(
            analyze(read_data(args.reference_csv, args.runtime_log)), indent=2
        ) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
