#!/usr/bin/env python3
"""Export numeric-only original Goemon desired-movement frames for Ship tests.

Reuses the independently verified original PlayerTask memory decoder.
The replay contains NO ROM bytes, character textures, sound, original
code or proprietary geometry: only measured positions/angles/velocities
and numeric original action and character IDs.

Ship can apply these vectors to Zelda collision *in a separate ghost
state* without modifying Link, and compare actual applied movement.
"""
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path
import sys
from steering_trace_fit import read_capture

HEADER = (
    "sample", "game_frames", "character_id", "action_id",
    "original_yaw10", "desired_dx", "desired_dz",
    "continuous_original_update",
)
MAX_SAMPLES = 12000


def make_replay(rows: list[dict]) -> str:
    if not rows or len(rows) > MAX_SAMPLES:
        raise ValueError("replay sample count outside validated bounds")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(HEADER)
    for index, row in enumerate(rows):
        if row["sample"] != index:
            raise ValueError(f"nonconsecutive source sample {index}")
        previous = rows[index-1] if index > 0 else None
        continuous = (
            previous is not None
            and row["game_frames"] == previous["game_frames"] + 1
            and row["character_id"] == previous["character_id"]
        )
        # Source floats reconstructed from raw N64 PlayerTask fields.
        # repr maintains Python float's exact parsed float32 value.
        writer.writerow((
            index, row["game_frames"], row["character_id"],
            row["action_id"], row["root_rot_y"] & 1023,
            repr(row["vx"]), repr(row["vz"]), int(continuous),
        ))
    return stream.getvalue()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_csv", type=Path)
    parser.add_argument("runtime_log", type=Path)
    parser.add_argument("--output", required=True, type=Path,
                        help="local-only numeric replay CSV for Ship")
    args = parser.parse_args(argv)
    try:
        rows = read_capture(args.reference_csv, args.runtime_log)
        data = make_replay(rows)
        args.output.write_text(data, encoding="utf-8")
    except (ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(f"Original measured movement: {len(rows)} numeric-only frames -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
