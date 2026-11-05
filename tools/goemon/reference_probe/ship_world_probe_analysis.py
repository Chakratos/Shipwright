#!/usr/bin/env python3
"""Analyze live Ship Zelda wall/floor probe CSV without guessing collision.

The probe is read-only. Its yaw comes from Link solely to select a test
direction, while the step length is the measured Goemon 2.8 units/update.
A hit is not equivalent to the original Goemon actor's final contact.
"""
from __future__ import annotations
import argparse
import csv
from collections import Counter
import json
import math
from pathlib import Path
import sys

REQUIRED = (
    "frame", "scene", "link_yaw", "link_x", "link_y", "link_z",
    "desired_dx", "desired_dz", "projected_x", "projected_z",
    "wall_hit", "wall_x", "wall_y", "wall_z", "floor_found", "floor_y",
)
EPS = 0.0005


def analyze(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"probe file not found: {path}")
    scenes: dict[int, dict] = {}
    samples = 0
    angles = Counter()
    errors: list[dict] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or set(REQUIRED).difference(reader.fieldnames):
            raise ValueError("invalid or incomplete Zelda probe CSV columns")
        for line, row in enumerate(reader, 2):
            try:
                frame = int(row["frame"])
                scene = int(row["scene"])
                yaw = int(row["link_yaw"])
                x, y, z = (float(row[k]) for k in ("link_x", "link_y", "link_z"))
                dx, dz = float(row["desired_dx"]), float(row["desired_dz"])
                px, pz = float(row["projected_x"]), float(row["projected_z"])
                wall, floor = int(row["wall_hit"]), int(row["floor_found"])
                wallxyz = [float(row[k]) for k in ("wall_x", "wall_y", "wall_z")]
                ground = float(row["floor_y"])
            except (KeyError, TypeError, ValueError) as err:
                raise ValueError(f"invalid Zelda probe CSV at line {line}") from err
            numbers = [x, y, z, dx, dz, px, pz, *wallxyz, ground]
            if any(not math.isfinite(v) for v in numbers):
                raise ValueError(f"nonfinite Zelda probe geometry at line {line}")
            if wall not in (0, 1) or floor not in (0, 1):
                raise ValueError(f"invalid Zelda collision boolean at line {line}")
            if frame != samples:
                raise ValueError(f"nonconsecutive Zelda probe frame at line {line}")
            actual_length = math.hypot(dx, dz)
            if abs(actual_length-2.8) > EPS:
                raise ValueError(f"Goemon expected 2.8-unit probe at line {line}")
            if math.hypot((x+dx)-px,(z+dz)-pz)>EPS:
                raise ValueError(f"projected position disagrees with desired vector at line {line}")
            expected = (yaw & 65535) * math.tau / 65536.0
            angular_error = math.hypot(dx-2.8*math.sin(expected),dz-2.8*math.cos(expected))
            if angular_error > EPS:
                raise ValueError(f"diagnostic Link yaw disagrees with probe direction at line {line}")
            stats = scenes.setdefault(scene, {
                "frames": 0, "wall_hits": 0, "floor_found": 0,
                "floor_not_found": 0, "min_floor_y": None, "max_floor_y": None,
                "max_absolute_floor_vs_actor_y": 0.0,
            })
            stats["frames"] += 1
            stats["wall_hits"] += wall
            stats["floor_found"] += floor
            stats["floor_not_found"] += 1-floor
            if floor:
                stats["min_floor_y"] = ground if stats["min_floor_y"] is None else min(stats["min_floor_y"],ground)
                stats["max_floor_y"] = ground if stats["max_floor_y"] is None else max(stats["max_floor_y"],ground)
                stats["max_absolute_floor_vs_actor_y"] = max(stats["max_absolute_floor_vs_actor_y"],abs(ground-y))
            if wall or not floor:
                if len(errors)<32:
                    errors.append({
                        "frame": frame, "scene": scene, "wall_hit": bool(wall),
                        "floor_missing": not bool(floor), "at": [x, y, z],
                        "projected": [px, pz],
                    })
            angles[yaw] += 1
            samples += 1
    if samples==0:
        raise ValueError("empty Zelda collision probe CSV")
    return {
        "frames": samples,
        "scenes": {str(k): v for k,v in sorted(scenes.items())},
        "unique_link_yaw_values": len(angles),
        "collision_or_missing_floor_examples": errors,
        "limit": (
            "A read-only Zelda world geometry PROBE. Uses Link actor yaw "
            "as a reference direction; does not drive player motion, "
            "implement Goemon camera controls, original collision radius, "
            "or original actor floor/step-up rules."
        ),
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ship_probe_csv",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    try:
        result=json.dumps(analyze(args.ship_probe_csv),indent=2)+"\n"
        if args.output:args.output.write_text(result,encoding="utf-8")
        else:print(result,end="")
    except (ValueError,OSError) as err:
        print(f"ERROR: {err}",file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
