"""Synthetic reproducible coverage tests for the independent Actor CSV."""
from __future__ import annotations
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_actor_trace import REQUIRED, summarize_actor_trace

def make_csv(*rows: dict[str, object], with_pilot: bool = False) -> str:
    fields = REQUIRED + (
        ("pilot_enabled", "link_x", "link_y", "link_z") if with_pilot else ()
    )
    columns = ",".join(fields)
    payload = [columns]
    for i, updates in enumerate(rows):
        row: dict[str, object] = {key: "0" for key in fields}
        row.update({
            "frame": i, "scene": 1, "room": 2, "actor_y": 10,
            "floor_found": 1, "preview_floor_snap": 1,
            "measured_transition": 1, "desired_dx": 0.7,
            "applied_dx": 0.7, "action": 13,
        })
        row.update(updates)
        payload.append(",".join(str(row[key]) for key in fields))
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

    def test_pilot_link_drift_is_measured_not_guessed(self):
        capture = make_csv(
            {"pilot_enabled": 1, "link_x": 0},
            {"pilot_enabled": 1, "link_x": 2.5},
            {"pilot_enabled": 0, "link_x": 12},
            {"pilot_enabled": 1, "link_x": 15},
            with_pilot=True,
        )
        report = summarize_actor_trace(capture)
        self.assertEqual(report["pilot_frames"], 3)
        self.assertTrue(report["pilot_telemetry_present"])
        self.assertAlmostEqual(report["link_distance_during_pilot_units"], 2.5)

    def test_partial_pilot_telemetry_fails_explicitly(self):
        capture = make_csv({}, with_pilot=True)
        capture = capture.replace(",link_y,", ",", 1)
        with self.assertRaisesRegex(ValueError, "incomplete pilot"):
            summarize_actor_trace(capture)

    def test_reject_duplicate_frames(self):
        bad = make_csv({}, {}).replace("\n1,1,2,", "\n0,1,2,")
        with self.assertRaisesRegex(ValueError, "nonmonotonic"):
            summarize_actor_trace(bad)

if __name__ == "__main__":
    unittest.main()
