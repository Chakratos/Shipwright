#!/usr/bin/env python3
"""Validate original 10-bit N64 yaw -> world motion at steady full speed.

Frames during active turning, character changes, frame gaps or stick changes
are excluded. The dynamic turning and camera controller remain unported.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
import struct
import sys


def analyze(csv_file: Path, log_file: Path) -> dict:
    with csv_file.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = (
            "sample", "character_id", "game_frames", "action_id",
            "root_rot_y", "stick_raw_x", "stick_raw_y",
        )
        if not reader.fieldnames or not set(fields).issubset(reader.fieldnames):
            raise ValueError("original yaw/input columns missing")
        rows = [{key: int(row[key]) for key in fields} for row in reader]

    velocities = {}
    for line in log_file.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        start = line.find("GOEMON_TASK,")
        if start < 0:
            continue
        parts = line[start + len("GOEMON_TASK,"):].split(",")
        if len(parts) != 5:
            raise ValueError("malformed original PlayerTask record")
        index = int(parts[0])
        blob = bytes.fromhex(parts[4].strip())
        if len(blob) != 240 or index in velocities:
            raise ValueError("invalid original PlayerTask bytes/index")
        velocities[index] = (
            struct.unpack_from(">f", blob, 0x68)[0],
            struct.unpack_from(">f", blob, 0x70)[0],
        )
    if len(velocities) != len(rows):
        raise ValueError("incomplete original PlayerTask capture")

    tested = []
    for i in range(4, len(rows)):
        row = rows[i]
        vx, vz = velocities[i]
        if math.hypot(vx, vz) < 2.79 or row["action_id"] != 15:
            continue
        recent = rows[i-4:i+1]
        if any(
            new["game_frames"] - old["game_frames"] != 1 or
            new["character_id"] != row["character_id"]
            for old, new in zip(recent, recent[1:])
        ):
            continue
        if any(
            rows[i-j]["root_rot_y"] != row["root_rot_y"] or
            rows[i-j]["stick_raw_x"] != row["stick_raw_x"] or
            rows[i-j]["stick_raw_y"] != row["stick_raw_y"]
            for j in (1, 2, 3)
        ):
            continue

        observed = math.degrees(math.atan2(vz, vx))
        expected = 90.0 - ((row["root_rot_y"] & 1023) * 360.0 / 1024.0)
        error = (observed - expected + 180.0) % 360.0 - 180.0
        tested.append({
            "sample": i, "character_id": row["character_id"],
            "original_yaw": row["root_rot_y"],
            "observed_angle": round(observed, 8),
            "predicted_angle": round(expected, 8),
            "signed_error_degrees": round(error, 8),
        })

    return {
        "total_samples": len(rows),
        "stable_full_speed_heading_samples": len(tested),
        "within_0_00002_degrees": sum(
            abs(p["signed_error_degrees"]) <= 0.00002 for p in tested
        ),
        "max_absolute_angle_error_degrees": max(
            (abs(p["signed_error_degrees"]) for p in tested), default=None
        ),
        "formula": (
            "worldX=sin(2*pi*(rootYaw&1023)/1024), "
            "worldZ=cos(2*pi*(rootYaw&1023)/1024)"
        ),
        "samples": tested,
        "limitation": (
            "Only stable yaw and full stick. Dynamic turning, camera "
            "inputs and steering interpolation are not yet verified."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_csv", type=Path)
    parser.add_argument("runtime_log", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        output = json.dumps(
            analyze(args.reference_csv, args.runtime_log), indent=2
        ) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
