#!/usr/bin/env python3
"""Compare two frame-by-frame movement traces after explicit unit normalization.

This tool does not infer Goemon physics or synthesize reference measurements.
Both CSVs must contain samples recorded from running game code, under the same
scripted input sequence and at the same simulation frequency.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import math
from pathlib import Path
import sys


REQUIRED_COLUMNS = ("frame", "pos_x", "pos_y", "pos_z", "yaw", "grounded")


@dataclass(frozen=True)
class Sample:
    frame: int
    x: float
    y: float
    z: float
    yaw: int
    grounded: bool


class TraceError(ValueError):
    pass


def read_trace(path: Path) -> list[Sample]:
    samples: list[Sample] = []
    with path.open(newline="", encoding="utf-8-sig") as trace_file:
        reader = csv.DictReader(trace_file)
        if not reader.fieldnames:
            raise TraceError(f"{path}: missing CSV header")
        missing = set(REQUIRED_COLUMNS).difference(reader.fieldnames)
        if missing:
            raise TraceError(f"{path}: missing columns: {', '.join(sorted(missing))}")

        for line_number, row in enumerate(reader, start=2):
            try:
                frame = int(row["frame"])
                xyz = (float(row["pos_x"]), float(row["pos_y"]), float(row["pos_z"]))
                yaw = int(row["yaw"])
                ground = int(row["grounded"])
            except (ValueError, TypeError, KeyError) as error:
                raise TraceError(f"{path}:{line_number}: invalid numeric value") from error

            if not all(math.isfinite(value) for value in xyz):
                raise TraceError(f"{path}:{line_number}: non-finite position")
            if ground not in (0, 1):
                raise TraceError(f"{path}:{line_number}: grounded must be 0 or 1")
            if not -32768 <= yaw <= 32767:
                raise TraceError(f"{path}:{line_number}: yaw must be a signed 16-bit angle")
            if frame != len(samples):
                raise TraceError(f"{path}:{line_number}: frames must be consecutive from zero")
            samples.append(Sample(frame, *xyz, yaw, bool(ground)))

    if not samples:
        raise TraceError(f"{path}: trace contains no samples")
    return samples


def angle_difference(a: int, b: int) -> int:
    """Shortest signed difference in Nintendo 64 binary-angle units."""
    return ((a - b + 32768) % 65536) - 32768


def compare(
    reference: list[Sample],
    candidate: list[Sample],
    reference_scale: float,
) -> dict[str, float | int]:
    if not math.isfinite(reference_scale) or reference_scale <= 0:
        raise TraceError("reference scale must be finite and greater than zero")
    if len(reference) != len(candidate):
        raise TraceError(f"trace length differs: reference={len(reference)}, candidate={len(candidate)}")

    initial_ref, initial_candidate = reference[0], candidate[0]
    max_horizontal = 0.0
    max_vertical = 0.0
    max_yaw_degrees = 0.0
    total_horizontal_squared = 0.0
    ground_mismatches = 0

    for ref, current in zip(reference, candidate):
        # Compare displacement relative to each trace's initial position.
        # Units / coordinate axes must already have been calibrated.
        dx = ((ref.x - initial_ref.x) * reference_scale -
              (current.x - initial_candidate.x))
        dy = ((ref.y - initial_ref.y) * reference_scale -
              (current.y - initial_candidate.y))
        dz = ((ref.z - initial_ref.z) * reference_scale -
              (current.z - initial_candidate.z))
        horizontal = math.hypot(dx, dz)
        total_horizontal_squared += horizontal * horizontal
        max_horizontal = max(max_horizontal, horizontal)
        max_vertical = max(max_vertical, abs(dy))

        ref_turn = angle_difference(ref.yaw, initial_ref.yaw)
        current_turn = angle_difference(current.yaw, initial_candidate.yaw)
        yaw_error = abs(angle_difference(ref_turn, current_turn)) * (360.0 / 65536.0)
        max_yaw_degrees = max(max_yaw_degrees, yaw_error)
        ground_mismatches += ref.grounded != current.grounded

    return {
        "frames": len(reference),
        "max_horizontal_error": max_horizontal,
        "rms_horizontal_error": math.sqrt(total_horizontal_squared / len(reference)),
        "max_vertical_error": max_vertical,
        "max_yaw_error_degrees": max_yaw_degrees,
        "grounded_mismatch_frames": ground_mismatches,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path, help="normalized trace captured from Goemon")
    parser.add_argument("candidate", type=Path, help="normalized trace captured from Ship of Harkinian")
    parser.add_argument("--reference-scale", type=float, default=1.0,
                        help="measured factor converting Goemon displacement units into Ship units")
    parser.add_argument("--max-horizontal-error", type=float, default=0.0)
    parser.add_argument("--max-vertical-error", type=float, default=0.0)
    parser.add_argument("--max-yaw-error-degrees", type=float, default=0.0)
    parser.add_argument("--max-grounded-mismatches", type=int, default=0)
    args = parser.parse_args(argv)

    if any(value < 0 or not math.isfinite(value) for value in (
        args.max_horizontal_error, args.max_vertical_error, args.max_yaw_error_degrees
    )) or args.max_grounded_mismatches < 0:
        parser.error("tolerances must be finite and non-negative")

    try:
        result = compare(read_trace(args.reference), read_trace(args.candidate), args.reference_scale)
    except (OSError, TraceError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    passed = (
        result["max_horizontal_error"] <= args.max_horizontal_error
        and result["max_vertical_error"] <= args.max_vertical_error
        and result["max_yaw_error_degrees"] <= args.max_yaw_error_degrees
        and result["grounded_mismatch_frames"] <= args.max_grounded_mismatches
    )
    print("PASS" if passed else "FAIL")
    for key, value in result.items():
        print(f"{key}: {value}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
