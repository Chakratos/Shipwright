#!/usr/bin/env python3
"""Recover per-character action-state transition graphs from actual Goemon traces.

Only numeric action IDs and original input masks are reported. The tool never
invents action names such as 'jump' or 'attack' before those are confirmed via
controlled original-game input trials and code references.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import sys


REQUIRED = ("sample", "game_frames", "character_id", "action_id", "buttons_held", "buttons_pressed")


def read_reference_trace(path: Path) -> list[dict[str, int]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or set(REQUIRED) - set(reader.fieldnames):
            raise ValueError(f"trace missing required fields: {', '.join(REQUIRED)}")
        rows = []
        for line_number, entry in enumerate(reader, start=2):
            try:
                sample = {key: int(entry[key]) for key in REQUIRED}
            except (ValueError, TypeError) as error:
                raise ValueError(f"line {line_number}: invalid integer field") from error
            if sample["sample"] != len(rows):
                raise ValueError(f"line {line_number}: sample index must be consecutive from zero")
            if sample["character_id"] not in range(256) or sample["action_id"] not in range(256):
                raise ValueError(f"line {line_number}: character/action ID exceeds uint8 range")
            if sample["buttons_held"] not in range(65536) or sample["buttons_pressed"] not in range(65536):
                raise ValueError(f"line {line_number}: invalid original N64 button mask")
            rows.append(sample)
    if not rows:
        raise ValueError("reference trace contains no samples")
    return rows


def build_action_graph(rows: list[dict[str, int]]) -> dict:
    actions: dict[int, set[int]] = defaultdict(set)
    transitions: dict[tuple[int, int, int], dict] = {}
    switch_events = []
    prior = None

    for row in rows:
        character = row["character_id"]
        action = row["action_id"]
        actions[character].add(action)
        if prior is not None:
            if prior["character_id"] != character:
                switch_events.append({
                    "sample": row["sample"],
                    "previous_character": prior["character_id"],
                    "current_character": character,
                })
            elif action != prior["action_id"]:
                key = (character, prior["action_id"], action)
                if key not in transitions:
                    transitions[key] = {
                        "character_id": character, "from_action": prior["action_id"],
                        "to_action": action, "count": 0, "first_sample": row["sample"],
                        "pressed_masks": set(), "held_masks": set(),
                    }
                entry = transitions[key]
                entry["count"] += 1
                entry["pressed_masks"].add(row["buttons_pressed"])
                entry["held_masks"].add(row["buttons_held"])
        prior = row

    result = []
    for key in sorted(transitions):
        node = transitions[key]
        result.append({
            **{k: v for k, v in node.items() if k not in ("pressed_masks", "held_masks")},
            "pressed_masks": sorted(node["pressed_masks"]),
            "held_masks": sorted(node["held_masks"]),
        })
    return {
        "samples": len(rows),
        "character_actions": {str(k): sorted(v) for k, v in sorted(actions.items())},
        "character_switch_events": switch_events,
        "transitions": result,
    }


def graphviz(graph: dict) -> str:
    lines = [
        "digraph GoemonActions {",
        "  // Action labels are unknown numeric IDs until reverse-engineered.",
        "  rankdir=LR;",
    ]
    for character, actions in graph["character_actions"].items():
        lines.append(f"  subgraph cluster_character_{character} {{")
        lines.append(f'    label="Character {character}";')
        for action in actions:
            lines.append(f'    c{character}_a{action} [label="Action {action}"];')
        lines.append("  }")
    for edge in graph["transitions"]:
        char, start, end = (edge[k] for k in ("character_id", "from_action", "to_action"))
        lines.append(
            f'  c{char}_a{start} -> c{char}_a{end} '
            f'[label="{edge["count"]} transition(s)"];'
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_csv", type=Path, help="CSV produced by log_to_csv.py")
    parser.add_argument("--format", choices=("json", "dot"), default="json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        graph = build_action_graph(read_reference_trace(args.reference_csv))
        output = graphviz(graph) if args.format == "dot" else json.dumps(graph, indent=2) + "\n"
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            print(output, end="")
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
