#!/usr/bin/env python3
"""Validate observed original NG5E planar-speed phases against PlayerTask.

Statistical verification only: does NOT invent camera-relative steering,
partial-analog scaling, collision response or unknown original action logic.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import struct
import sys

MAX_SPEED = 2.8
GROUND_FIRST = 0.7
GROUND_RUN_DELTA = 0.54
AIR_DELTA = 0.84
BRAKE_FIRST = 2.0
BRAKE_PER_STEP = 0.6
TOL = 0.012

def load_capture(csv_path: Path, log_path: Path) -> list[dict]:
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        mandatory = (
            "sample", "game_frames", "character_id", "action_id",
            "stick_raw_x", "stick_raw_y", "root_pos_x", "root_pos_z",
        )
        if not reader.fieldnames or not set(mandatory).issubset(reader.fieldnames):
            raise ValueError("GOEMON_REF CSV missing original horizontal fields")
        rows = []
        for index, entry in enumerate(reader):
            parsed = {key: int(entry[key]) for key in mandatory[:6]}
            parsed.update({key: float(entry[key]) for key in mandatory[6:]})
            if parsed["sample"] != index:
                raise ValueError("nonconsecutive original reference samples")
            rows.append(parsed)

    found = 0
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        marker = line.find("GOEMON_TASK,")
        if marker == -1:
            continue
        fields = line[marker + len("GOEMON_TASK,"):].split(",")
        if len(fields) != 5:
            raise ValueError("malformed GOEMON_TASK")
        index = int(fields[0])
        if index != found or index >= len(rows):
            raise ValueError(f"nonconsecutive original task sample {index}")
        memory = bytes.fromhex(fields[4].strip())
        if len(memory) != 0xF0:
            raise ValueError(f"invalid PlayerTask memory length at {index}")
        row = rows[index]
        if row["character_id"] != int(fields[2]) or row["action_id"] != int(fields[3]):
            raise ValueError(f"original player or action mismatch at {index}")
        row["vx"] = struct.unpack_from(">f", memory, 0x68)[0]
        row["vz"] = struct.unpack_from(">f", memory, 0x70)[0]
        if not math.isfinite(row["vx"]) or not math.isfinite(row["vz"]):
            raise ValueError(f"nonfinite original motion at {index}")
        row["speed"] = math.hypot(row["vx"], row["vz"])
        found += 1
    if found != len(rows) or not found:
        raise ValueError(f"missing original PlayerTask rows: {found}/{len(rows)}")
    return rows


def summarize(rows: list[dict]) -> dict:
    phases: dict[str, list[dict]] = {
        "ground_first_0_70": [],
        "ground_running_add_0_54": [],
        "airborne_add_0_84": [],
        "running_release_first_2_00": [],
        "brake_subtract_0_60_magnitude": [],
    }
    by_char: dict[str, dict] = {}
    collision_blocked = []
    continuous = 0
    air_actions = {23, 25, 26, 28}
    for i, row in enumerate(rows):
        ch = str(row["character_id"])
        character = by_char.setdefault(ch, {
            "samples": 0, "moving_samples": 0,
            "max_speed": 0.0, "at_max_speed": 0,
        })
        character["samples"] += 1
        speed = row["speed"]
        character["max_speed"] = max(character["max_speed"], speed)
        character["moving_samples"] += int(speed > 0.01)
        character["at_max_speed"] += int(abs(speed - MAX_SPEED) < 0.002)
        if speed > MAX_SPEED + 0.002:
            raise ValueError(f"original horizontal speed exceeds limit at {i}")
        if i == 0:
            continue
        previous = rows[i-1]
        if (row["character_id"] != previous["character_id"] or
                row["game_frames"] - previous["game_frames"] != 1):
            continue
        continuous += 1
        raw = (row["stick_raw_x"], row["stick_raw_y"])
        analog = max(abs(raw[0]), abs(raw[1])) >= 15
        prev_speed = previous["speed"]
        action, prev_action = row["action_id"], previous["action_id"]
        predicted = None
        phase = None
        if analog and action == 13 and prev_speed < 0.01:
            phase, predicted = "ground_first_0_70", GROUND_FIRST
        elif (analog and action == 15 and prev_action in (13, 15)
              and 0.01 < prev_speed < MAX_SPEED - TOL):
            phase, predicted = "ground_running_add_0_54", min(
                MAX_SPEED, prev_speed + GROUND_RUN_DELTA
            )
        elif (analog and action in air_actions and prev_action in air_actions
              and raw == (previous["stick_raw_x"], previous["stick_raw_y"])
              and 0.01 < prev_speed < MAX_SPEED - TOL):
            phase, predicted = "airborne_add_0_84", min(
                MAX_SPEED, prev_speed + AIR_DELTA
            )
        elif (not analog and action == 16 and prev_action == 15
              and abs(prev_speed - MAX_SPEED) < TOL):
            phase, predicted = "running_release_first_2_00", BRAKE_FIRST
        elif (not analog and action == 16 and prev_action == 16
              and prev_speed > TOL and
              any(abs(prev_speed - value) < TOL
                  for value in (2.0, 1.4, 0.8, 0.2))):
            phase = "brake_subtract_0_60_magnitude"
            predicted = abs(prev_speed - BRAKE_PER_STEP)
        if phase is not None:
            phases[phase].append({
                "sample": i, "character_id": row["character_id"],
                "actual": speed, "predicted": predicted,
                "error": speed - predicted,
            })

        displacement = math.hypot(
            row["root_pos_x"] - previous["root_pos_x"],
            row["root_pos_z"] - previous["root_pos_z"],
        )
        if speed > 0.05 and displacement < 0.002:
            collision_blocked.append(i)

    phase_summary = {}
    for name, values in phases.items():
        errors = [abs(value["error"]) for value in values]
        phase_summary[name] = {
            "observations": len(values),
            "within_0_012": sum(error <= TOL for error in errors),
            "largest_error": round(max(errors), 6) if errors else None,
            "examples": [{
                "sample": v["sample"], "character_id": v["character_id"],
                "observed": round(v["actual"], 5),
                "predicted": round(v["predicted"], 5),
            } for v in values[:6]],
        }
    return {
        "samples": len(rows),
        "continuous_update_pairs": continuous,
        "observed_speed_limit": MAX_SPEED,
        "original_task_velocity_offsets": ["0x68", "0x70"],
        "characters": by_char,
        "measured_phases": phase_summary,
        "blocked_desired_velocity_samples": len(collision_blocked),
        "blocked_sample_examples": collision_blocked[:20],
        "limitations": [
            "Phase rules verify speed magnitudes, not camera-relative steering or direction smoothing.",
            "A 0.4 braking residual can persist against geometry; no universal snap-to-zero rule is asserted.",
            "Frame gaps and character switches are excluded; intermediate analog inputs were not sampled.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_csv", type=Path)
    parser.add_argument("runtime_log", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.dumps(
            summarize(load_capture(args.reference_csv, args.runtime_log)),
            indent=2
        ) + "\n"
        if args.output:
            args.output.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
