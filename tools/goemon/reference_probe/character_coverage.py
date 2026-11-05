#!/usr/bin/env python3
"""Summarize all character IDs and action states in a multi-character trace.

The IDs and actions here are raw original-game values. Neither a character
name nor weapon/equipment identity is inferred without original evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys


FIELDS = (
    "sample", "character_id", "global_character_id", "action_id",
    "buttons_held", "buttons_pressed", "stick_raw_x", "stick_raw_y",
    "root_pos_x", "root_pos_y", "root_pos_z",
)


def summarize_csv(path: Path) -> dict:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or set(FIELDS).difference(reader.fieldnames):
            raise ValueError("missing required Goemon reference columns")
        rows: list[dict] = []
        for i, entry in enumerate(reader):
            try:
                row = {k: int(entry[k]) for k in FIELDS[:8]}
                row.update({k: float(entry[k]) for k in FIELDS[8:]})
            except (ValueError, TypeError) as err:
                raise ValueError(f"invalid original reference row {i + 2}") from err
            if row["sample"] != i:
                raise ValueError(f"non-consecutive sample index on row {i + 2}")
            rows.append(row)

    if not rows:
        raise ValueError("empty original Goemon reference trace")

    characters: dict[int, dict] = {}
    segments: list[dict] = []
    previous: dict | None = None
    for row in rows:
        ident = row["character_id"]
        current = characters.setdefault(ident, {
            "samples": 0,
            "first_sample": row["sample"],
            "last_sample": row["sample"],
            "actions": Counter(),
            "button_masks_pressed": Counter(),
            "button_masks_held": Counter(),
            "samples_with_analog_input": 0,
            "samples_with_button_press": 0,
            "global_id_mismatches": 0,
        })
        current["samples"] += 1
        current["last_sample"] = row["sample"]
        current["actions"][row["action_id"]] += 1
        current["button_masks_pressed"][row["buttons_pressed"]] += 1
        current["button_masks_held"][row["buttons_held"]] += 1
        current["samples_with_analog_input"] += int(
            abs(row["stick_raw_x"]) >= 15 or abs(row["stick_raw_y"]) >= 15
        )
        current["samples_with_button_press"] += int(row["buttons_pressed"] != 0)
        current["global_id_mismatches"] += int(
            row["global_character_id"] != ident
        )
        if previous is None or previous["character_id"] != ident:
            segments.append({
                "character_id": ident,
                "first_sample": row["sample"],
                "last_sample": row["sample"],
                "samples": 1,
            })
        else:
            segments[-1]["last_sample"] = row["sample"]
            segments[-1]["samples"] += 1
        previous = row

    serializable: dict[str, dict] = {}
    for ident, values in sorted(characters.items()):
        serializable[str(ident)] = {
            **{k: v for k, v in values.items() if not isinstance(v, Counter)},
            "actions": {str(k): n for k, n in sorted(values["actions"].items())},
            "button_masks_pressed": {
                str(k): n for k, n in sorted(values["button_masks_pressed"].items())
            },
            "button_masks_held": {
                str(k): n for k, n in sorted(values["button_masks_held"].items())
            },
        }
    return {
        "total_samples": len(rows),
        "observed_character_ids": sorted(characters),
        "character_count": len(characters),
        "character_segments": segments,
        "characters": serializable,
        "interpretation": (
            "IDs, actions and buttons are raw original values. "
            "Equipment/weapon state is not directly identified by this capture. "
            "Different IDs may be actual swaps; validate with state memory."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_csv", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = json.dumps(summarize_csv(args.reference_csv), indent=2) + "\n"
        if args.output is None:
            print(result, end="")
        else:
            args.output.write_text(result, encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
