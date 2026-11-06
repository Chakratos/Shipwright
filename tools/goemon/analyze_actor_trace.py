#!/usr/bin/env python3
"""Analyze a locally recorded independent Goemon Actor CSV in one command.

No ROM data or geometry is required. Produces numeric acceptance metrics for
the temporary Zelda terrain adapter, not claims of original NG5E accuracy.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
import json
import math
from pathlib import Path

REQUIRED = (
    "frame", "scene", "room", "ship_stick_x", "ship_stick_y",
    "preview_yaw10", "action", "measured_transition", "actor_x",
    "actor_y", "actor_z", "desired_dx", "desired_dz",
    "applied_dx", "applied_dz", "wall_hit", "floor_found",
    "preview_floor_snap", "airborne", "terrain_reject_code"
)
REJECTIONS = {
    0: "accepted", 1: "wall", 2: "missing_floor",
    3: "step_too_high", 4: "drop_too_deep",
}

def summarize_actor_trace(text: str) -> dict:
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None:
        raise ValueError("empty Goemon prototype trace")
    missing = sorted(set(REQUIRED) - set(reader.fieldnames))
    if missing:
        raise ValueError("missing prototype trace columns: " + ", ".join(missing))
    pilot_keys = {"pilot_enabled", "link_x", "link_y", "link_z"}
    pilot_cols = set(reader.fieldnames) & pilot_keys
    if pilot_cols and pilot_cols != pilot_keys:
        raise ValueError("incomplete pilot telemetry columns")
    has_pilot = pilot_cols == pilot_keys
    counts = Counter()
    actions = Counter()
    scenes = set()
    rooms = set()
    distance_desired = 0.0
    distance_applied = 0.0
    last_frame: int | None = None
    last_pilot_link: tuple[int, int, float, float, float] | None = None
    link_distance_during_pilot = 0.0
    max_height = float("-inf")
    for row in reader:
        counts["frames"] += 1
        frame = int(row["frame"])
        scene = int(row["scene"])
        room = int(row["room"])
        action = int(row["action"])
        reject = int(row["terrain_reject_code"])
        if frame < 0 or (last_frame is not None and frame <= last_frame):
            raise ValueError(f"nonmonotonic prototype frame {frame}")
        last_frame = frame
        if reject not in REJECTIONS:
            raise ValueError(f"invalid terrain reject code {reject} at frame {frame}")
        values = [
            float(row[key]) for key in (
                "actor_x", "actor_y", "actor_z", "desired_dx", "desired_dz",
                "applied_dx", "applied_dz"
            )
        ]
        if not all(math.isfinite(x) for x in values):
            raise ValueError(f"nonfinite Actor position or movement at frame {frame}")
        if has_pilot:
            pilot = int(row["pilot_enabled"])
            if pilot not in (0, 1):
                raise ValueError(f"invalid pilot flag at frame {frame}")
            link_coords = tuple(float(row[key]) for key in
                                ("link_x", "link_y", "link_z"))
            if not all(math.isfinite(x) for x in link_coords):
                raise ValueError(f"nonfinite Link telemetry at frame {frame}")
            if pilot:
                counts["pilot_frames"] += 1
                if (last_pilot_link and last_pilot_link[:2] == (scene, room)):
                    link_distance_during_pilot += math.dist(
                        link_coords, last_pilot_link[2:])
                last_pilot_link = (scene, room, *link_coords)
            else:
                last_pilot_link = None
        accepted = reject == 0
        if not accepted and (abs(values[5]) > 0.0001 or abs(values[6]) > 0.0001):
            raise ValueError(f"rejected terrain still moved Actor at frame {frame}")
        for key in ("measured_transition", "wall_hit", "floor_found",
                    "preview_floor_snap", "airborne"):
            value = int(row[key])
            if value not in (0, 1):
                raise ValueError(f"invalid boolean {key} at frame {frame}")
            counts[key] += value
        if reject == 1 and int(row["wall_hit"]) != 1:
            raise ValueError(f"wall rejection without wall hit at frame {frame}")
        if int(row["preview_floor_snap"]) and (
            not accepted or int(row["airborne"]) or not int(row["floor_found"])
        ):
            raise ValueError(f"illegal diagnostic floor snap at frame {frame}")
        counts[REJECTIONS[reject]] += 1
        if reject != 0:
            counts["rejected"] += 1
        if int(row["measured_transition"]) == 0:
            counts["unsupported_motion"] += 1
        distance_desired += math.hypot(values[3], values[4])
        distance_applied += math.hypot(values[5], values[6])
        max_height = max(max_height, values[1])
        actions[action] += 1
        scenes.add(scene)
        rooms.add((scene, room))
    if not counts["frames"]:
        raise ValueError("prototype trace has no frames")
    report = {
        "schema": "goemon-prototype-actor-report-v1",
        "frames": counts["frames"],
        "measured_transitions": counts["measured_transition"],
        "unsupported_motion_frames": counts["unsupported_motion"],
        "measured_coverage_percent": round(
            100 * counts["measured_transition"] / counts["frames"], 2
        ),
        "airborne_frames": counts["airborne"],
        "floor_snap_frames": counts["preview_floor_snap"],
        "terrain_rejections": {REJECTIONS[i]: counts[REJECTIONS[i]] for i in range(5)},
        "scene_count": len(scenes),
        "scene_room_count": len(rooms),
        "desired_distance_units": round(distance_desired, 6),
        "applied_distance_units": round(distance_applied, 6),
        "max_actor_y": max_height,
        "action_frames": dict(sorted(actions.items())),
        "note": "Zelda collision metrics; NOT original Goemon validation.",
    }
    if has_pilot:
        report["pilot_frames"] = counts["pilot_frames"]
        report["link_distance_during_pilot_units"] = round(
            link_distance_during_pilot, 6
        )
        report["pilot_telemetry_present"] = True
    return report

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("trace", type=Path, help="goemon_prototype_actor.csv")
    p.add_argument("--output", type=Path, help="optional summary JSON output")
    args = p.parse_args(argv)
    try:
        result = summarize_actor_trace(args.trace.read_text(encoding="utf-8"))
        payload = json.dumps(result, indent=2) + "\n"
        if args.output:
            args.output.write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
    except (OSError, ValueError, KeyError, OverflowError) as exc:
        p.exit(2, f"ERROR: {exc}\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
