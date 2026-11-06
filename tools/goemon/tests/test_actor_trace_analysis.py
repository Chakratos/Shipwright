"""Synthetic reproducible coverage tests for the independent Actor CSV."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_actor_trace import REQUIRED, summarize_actor_trace

def make_csv(*rows: dict[str, object]) -> str:
    columns = ",".join(REQUIRED)
    payload = [columns]
    for i, updates in enumerate(rows):
        row: dict[str, object] = {key: "0" for key in REQUIRED}
        row.update({
            "frame": i, "scene": 1, "room": 2, "actor_y": 10,
            "floor_found": 1, "preview_floor_snap": 1,
            "measured_transition": 1, "desired_dx": 0.7,
            "applied_dx": 0.7, "action": 13,
        })
        row.update(updates)
        payload.append(",".join(str(row[key]) for key in REQUIRED))
    return "\n".join(payload) + "\n"

class ActorTraceAnalysisTests(unittest.TestCase):
    def test_mixed_source_and_collision_coverage(self):
        text = make_csv(
            {},
            {"room": 3, "terrain_reject_code": 1, "wall_hit": 1,
             "applied_dx": 0, "preview_floor_snap": 0, "floor_found": 0},
            {"room": 3, "terrain_reject_code": 2, "floor_found": 0,
             "applied_dx": 0, "preview_floor_snap": 0,
             "measured_transition": 0, "action": 0},
            {"room": 3, "airborne": 1, "preview_floor_snap": 0,
             "measured_transition": 1, "action": 23},
        )
        summary = summarize_actor_trace(text)
        self.assertEqual(summary["frames"], 4)
        self.assertEqual(summary["measured_transitions"], 3)
        self.assertEqual(summary["unsupported_motion_frames"], 1)
        self.assertEqual(summary["measured_coverage_percent"], 75.0)
        self.assertEqual(summary["scene_room_count"], 2)
        self.assertEqual(summary["airborne_frames"], 1)
        self.assertEqual(summary["terrain_rejections"]["wall"], 1)
        self.assertEqual(summary["terrain_rejections"]["missing_floor"], 1)
        self.assertAlmostEqual(summary["desired_distance_units"], 2.8)
        self.assertAlmostEqual(summary["applied_distance_units"], 1.4)

    def test_reject_moving_position_and_bad_floor_snap(self):
        bad = make_csv({"terrain_reject_code": 1, "wall_hit": 1})
        with self.assertRaisesRegex(ValueError, "still moved"):
            summarize_actor_trace(bad)
        bad = make_csv({"airborne": 1})
        with self.assertRaisesRegex(ValueError, "floor snap"):
            summarize_actor_trace(bad)

    def test_reject_missing_columns_and_nonfinite(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            summarize_actor_trace("frame,scene\n1,2\n")
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            summarize_actor_trace(make_csv({"actor_x": "nan"}))

    def test_reject_duplicate_frames(self):
        bad = make_csv({}, {}).replace("\n1,1,2,", "\n0,1,2,")
        with self.assertRaisesRegex(ValueError, "nonmonotonic"):
            summarize_actor_trace(bad)

if __name__ == "__main__":
    unittest.main()
