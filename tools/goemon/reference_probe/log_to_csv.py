#!/usr/bin/env python3
"""Extract raw exploratory Goemon reference probe rows from a Recomp log.

The output is deliberately NOT normalized to Ship's physics/angle units.
Do not pass it directly to compare_traces.py.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
import sys


PREFIX = "GOEMON_REF,"
COLUMNS = (
    "sample", "game_frames", "character_id", "action_id",
    "global_character_id", "buttons_held",
    "root_pos_x", "root_pos_y", "root_pos_z",
    "root_rot_x", "root_rot_y", "root_rot_z",
    "root_animation_progress", "buttons_pressed",
    "stick_raw_x", "stick_raw_y", "stick_x", "stick_y",
)
FLOAT_FIELDS = {
    "root_pos_x", "root_pos_y", "root_pos_z",
    "root_animation_progress", "stick_x", "stick_y",
}


def extract_lines(lines: list[str]) -> list[list[str]]:
    parsed: list[list[str]] = []
    for number, line in enumerate(lines, 1):
        start = line.find(PREFIX)
        if start < 0:
            continue
        values = line[start + len(PREFIX):].strip().split(",")
        if len(values) != len(COLUMNS):
            raise ValueError(f"log line {number}: expected {len(COLUMNS)} fields, got {len(values)}")
        for name, value in zip(COLUMNS, values):
            try:
                if name in FLOAT_FIELDS:
                    if not math.isfinite(float(value)):
                        raise ValueError("non-finite float")
                else:
                    int(value)
            except ValueError as error:
                raise ValueError(f"log line {number}: bad {name}: {value}") from error
        if int(values[0]) != len(parsed):
            raise ValueError(f"log line {number}: missing/duplicate sample index {values[0]}")
        parsed.append(values)

    if not parsed:
        raise ValueError("no Goemon reference probe rows found in log")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_file", type=Path)
    parser.add_argument("output_csv", type=Path)
    args = parser.parse_args(argv)

    try:
        rows = extract_lines(args.log_file.read_text(encoding="utf-8", errors="replace").splitlines())
        with args.output_csv.open("w", newline="", encoding="utf-8") as output:
            writer = csv.writer(output)
            writer.writerow(COLUMNS)
            writer.writerows(rows)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    print(f"Extracted {len(rows)} exploratory render samples into {args.output_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
