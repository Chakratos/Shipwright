#!/usr/bin/env python3
"""Measure original character/action model Object animation progress.

Output is an observational rate catalog. No guessed animation IDs,
skeletons, clip lengths, frame holds or rendering time base.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import sys


def analyze(reference_csv: Path, runtime_log: Path) -> dict:
    with reference_csv.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = ("sample", "game_frames", "character_id", "action_id")
        if reader.fieldnames is None or not set(required).issubset(reader.fieldnames):
            raise ValueError("original action/frame keys are missing")
        refs = [{key: int(row[key]) for key in required} for row in reader]

    objects: dict[int, tuple[int, int, float]] = {}
    for line in runtime_log.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        at = line.find("GOEMON_OBJ,")
        if at < 0:
            continue
        values = line[at + len("GOEMON_OBJ,"):].strip().split(",")
        if len(values) != 10:
            raise ValueError("original Object record has incorrect field count")
        index = int(values[0])
        character = int(values[1])
        action = int(values[2])
        progress = float(values[9])
        if not math.isfinite(progress):
            raise ValueError("nonfinite original animation progress")
        if index in objects:
            raise ValueError("duplicate original model Object record")
        objects[index] = (character, action, progress)

    if len(refs) != len(objects) or not refs:
        raise ValueError(
            f"original model Object mismatch: {len(objects)}/{len(refs)}"
        )
    for index, row in enumerate(refs):
        if (row["sample"] != index or
                objects[index][:2] != (row["character_id"], row["action_id"])):
            raise ValueError(f"character/action disagreement at sample {index}")

    groups = defaultdict(lambda: {"samples": 0, "steps": [], "progress": []})
    for i, row in enumerate(refs):
        character, action = row["character_id"], row["action_id"]
        value = objects[i][2]
        entry = groups[(character, action)]
        entry["samples"] += 1
        entry["progress"].append(value)
        if not i:
            continue
        prior = refs[i - 1]
        if (prior["character_id"] == character and
                prior["action_id"] == action and
                row["game_frames"] - prior["game_frames"] == 1):
            entry["steps"].append(round(value - objects[i-1][2], 4))

    entries = []
    for (character, action), source in sorted(groups.items()):
        steps = source["steps"]
        counts = Counter(steps)
        positive = Counter({
            delta: count for delta, count in counts.items() if delta > 0.0001
        })
        dominant, matching = (
            positive.most_common(1)[0] if positive else (None, 0)
        )
        positive_steps = sum(positive.values())
        consistency = matching / positive_steps if positive_steps else 0.0
        stable = bool(
            dominant is not None and matching >= 5 and
            consistency >= 0.95 and matching / max(1,len(steps)) >= 0.6
        )
        entries.append({
            "character_id": character,
            "action_id": action,
            "samples": source["samples"],
            "consecutive_same_action_updates": len(steps),
            "dominant_positive_progress_step": dominant,
            "dominant_positive_steps": matching,
            "positive_rate_consistency": round(consistency, 5),
            "holds": counts.get(0.0, 0),
            "wraps_or_resets": sum(
                count for delta, count in counts.items() if delta < -0.0001
            ),
            "other_positive_steps": positive_steps - matching,
            "min_progress": round(min(source["progress"]), 4),
            "max_progress": round(max(source["progress"]), 4),
            "stable_fixed_rate": stable,
            "observed_deltas": [
                {"delta": delta, "count": count}
                for delta, count in counts.most_common(6)
            ],
        })
    return {
        "total_samples": len(refs),
        "total_character_action_pairs": len(entries),
        "stable_fixed_rate_pairs": sum(p["stable_fixed_rate"] for p in entries),
        "pairs": entries,
        "limitations": [
            "Numeric model Object animation progress is not yet mapped to source animation clips.",
            "Frame holds, wraps and mixed progress increments need the original action/animation state logic.",
            "Progress deltas are per original GAME UPDATE, not variable render delta-time.",
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
            analyze(args.reference_csv, args.runtime_log), indent=2
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
