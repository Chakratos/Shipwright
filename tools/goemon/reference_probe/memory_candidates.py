#!/usr/bin/env python3
"""Discover candidate float fields in Goemon's opaque Player memory.

Works on GOEMON_MEM records emitted by goemon_probe.c. This ranks correlation
against the rendered root-object axes; it does not claim to recover the game's
authoritative physics vectors without independent call-site verification.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import struct
import sys


PREFIX = "GOEMON_MEM,"
PLAYER_RECORD_LENGTH = 0x1C0


@dataclass(frozen=True)
class MemorySample:
    trace_frame: int
    game_frames: int
    character_id: int
    action_id: int
    root: tuple[float, float, float]
    raw: bytes


def parse_log(text: str) -> list[MemorySample]:
    records: list[MemorySample] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        begin = line.find(PREFIX)
        if begin == -1:
            continue
        fields = line[begin + len(PREFIX):].strip().split(",")
        if len(fields) != 8:
            raise ValueError(f"line {line_number}: expected 8 fields, got {len(fields)}")
        try:
            indices = [int(x) for x in fields[:4]]
            position = tuple(float(x) for x in fields[4:7])
            data = bytes.fromhex(fields[7])
        except ValueError as error:
            raise ValueError(f"line {line_number}: invalid memory record") from error
        if len(data) != PLAYER_RECORD_LENGTH:
            raise ValueError(
                f"line {line_number}: expected {PLAYER_RECORD_LENGTH} memory bytes, got {len(data)}"
            )
        if not all(math.isfinite(x) for x in position):
            raise ValueError(f"line {line_number}: non-finite root position")
        if indices[0] < 0 or (records and indices[0] <= records[-1].trace_frame):
            raise ValueError(f"line {line_number}: duplicate or out-of-order sample")
        records.append(MemorySample(*indices, position, data))
    if not records:
        raise ValueError("no GOEMON_MEM rows found")
    return records


def score_pair(xs: list[float], ys: list[float]) -> tuple[float, float, float, float] | None:
    """Fit y = slope*x + intercept; return (R2, RMSE, slope, intercept)."""
    if len(xs) != len(ys) or len(xs) < 8:
        return None
    mx = math.fsum(xs) / len(xs)
    my = math.fsum(ys) / len(ys)
    xx = math.fsum((x - mx) ** 2 for x in xs)
    yy = math.fsum((y - my) ** 2 for y in ys)
    if xx < 1e-8 or yy < 1e-8:
        return None
    xy = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = xy / xx
    intercept = my - slope * mx
    if not math.isfinite(slope) or not math.isfinite(intercept):
        return None
    residual = math.fsum((y - slope * x - intercept) ** 2 for x, y in zip(xs, ys))
    rmse = math.sqrt(residual / len(xs))
    r2 = 1.0 - residual / yy
    if not math.isfinite(rmse) or not math.isfinite(r2):
        return None
    return r2, rmse, slope, intercept


def find_candidates(
    samples: list[MemorySample], top: int = 8, min_r2: float = 0.5
) -> dict[str, list[dict[str, float | int | str]]]:
    if len(samples) < 8:
        raise ValueError("at least 8 samples are required for memory correlation")
    if top < 1 or not -1 <= min_r2 <= 1:
        raise ValueError("invalid candidate ranking parameters")
    if len({s.character_id for s in samples}) != 1:
        raise ValueError("analyze one character at a time (separate recordings)")
    results: dict[str, list[dict[str, float | int | str]]] = {}
    for axis, coordinate in (("x", 0), ("y", 1), ("z", 2)):
        target = [s.root[coordinate] for s in samples]
        if max(target) - min(target) < 0.01:
            results[axis] = []  # This axis did not move: correlation impossible.
            continue
        ranks: list[dict[str, float | int | str]] = []
        for offset in range(0, PLAYER_RECORD_LENGTH, 4):
            for endian in (">", "<"):
                values = [struct.unpack_from(endian + "f", s.raw, offset)[0] for s in samples]
                if not all(math.isfinite(x) and abs(x) < 1e10 for x in values):
                    continue
                fit = score_pair(values, target)
                if fit is None:
                    continue
                r2, rmse, slope, intercept = fit
                if r2 < min_r2:
                    continue
                ranks.append({
                    "offset": offset, "offset_hex": f"0x{offset:03x}",
                    "endian": "big" if endian == ">" else "little",
                    "r2": r2, "rmse": rmse, "scale": slope, "offset_value": intercept,
                })
        ranks.sort(key=lambda row: (-float(row["r2"]), float(row["rmse"]), int(row["offset"])))
        results[axis] = ranks[:top]
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_file", type=Path)
    parser.add_argument("--top", type=int, default=8)
    parser.add_argument("--min-r2", type=float, default=0.8)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)
    try:
        if args.top < 1 or not math.isfinite(args.min_r2):
            raise ValueError("invalid --top or --min-r2")
        samples = parse_log(args.log_file.read_text(encoding="utf-8", errors="replace"))
        results = find_candidates(samples, top=args.top, min_r2=args.min_r2)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "samples": len(samples), "character_id": samples[0].character_id,
            "candidates": results,
        }, indent=2))
    else:
        print(f"Memory samples: {len(samples)}; character ID: {samples[0].character_id}")
        for axis, records in results.items():
            print(f"Root {axis}:")
            for r in records:
                print(f"  {r['offset_hex']} {r['endian']:6} R2={r['r2']:.5f} "
                      f"RMSE={r['rmse']:.5f} scale={r['scale']:.6g} "
                      f"intercept={r['offset_value']:.6g}")
            if not records:
                print("  no qualifying moving float candidates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
