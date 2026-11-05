"""State-transition inventory tests for the original Goemon action IDs."""
from __future__ import annotations

import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from action_transitions import build_action_graph, graphviz, read_reference_trace


HEADERS = (
    "sample", "game_frames", "character_id", "action_id", "buttons_held",
    "buttons_pressed",
)


class ActionGraphTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"sample": 0, "game_frames": 0, "character_id": 1,
             "action_id": 4, "buttons_held": 0, "buttons_pressed": 0},
            {"sample": 1, "game_frames": 1, "character_id": 1,
             "action_id": 5, "buttons_held": 0x8000, "buttons_pressed": 0x8000},
            {"sample": 2, "game_frames": 2, "character_id": 1,
             "action_id": 5, "buttons_held": 0x8000, "buttons_pressed": 0},
            {"sample": 3, "game_frames": 3, "character_id": 1,
             "action_id": 4, "buttons_held": 0, "buttons_pressed": 0},
            {"sample": 4, "game_frames": 4, "character_id": 2,
             "action_id": 7, "buttons_held": 0, "buttons_pressed": 0},
        ]

    def test_transition_edges_and_character_switch(self):
        graph = build_action_graph(self.rows)
        self.assertEqual(graph["character_actions"], {"1": [4, 5], "2": [7]})
        self.assertEqual(graph["character_switch_events"], [
            {"sample": 4, "previous_character": 1, "current_character": 2}
        ])
        self.assertEqual(len(graph["transitions"]), 2)
        attack_edge = next(x for x in graph["transitions"]
                           if x["from_action"] == 4 and x["to_action"] == 5)
        self.assertEqual(attack_edge["pressed_masks"], [0x8000])
        self.assertEqual(attack_edge["first_sample"], 1)

    def test_graphviz_contains_no_guessed_action_labels(self):
        dot = graphviz(build_action_graph(self.rows))
        self.assertIn('c1_a4 -> c1_a5', dot)
        self.assertIn('Action 5', dot)
        self.assertNotIn('attack', dot.lower())

    def test_read_csv_rejects_skipped_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.csv"
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=HEADERS)
                writer.writeheader()
                writer.writerow(self.rows[0])
                writer.writerow(self.rows[2])
            with self.assertRaisesRegex(ValueError, "consecutive"):
                read_reference_trace(path)

    def test_read_csv_rejects_invalid_button_masks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.csv"
            bad = dict(self.rows[0], buttons_pressed=70000)
            with path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=HEADERS)
                writer.writeheader()
                writer.writerow(bad)
            with self.assertRaisesRegex(ValueError, "button mask"):
                read_reference_trace(path)


if __name__ == "__main__":
    unittest.main()
