"""Unit tests for the Goemon/Ship movement trace comparator (stdlib only)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_traces import Sample, TraceError, angle_difference, compare, read_trace


class TraceComparatorTests(unittest.TestCase):
    def test_identical_trace_is_exact_match_including_wrapped_yaw(self):
        trace = [
            Sample(0, 0.0, 1.0, 0.0, 32760, True),
            Sample(1, 2.0, 3.0, 0.0, -32760, False),
        ]
        result = compare(trace, trace, 1.0)
        self.assertEqual(result["max_horizontal_error"], 0.0)
        self.assertEqual(result["max_vertical_error"], 0.0)
        self.assertEqual(result["max_yaw_error_degrees"], 0.0)
        self.assertEqual(result["grounded_mismatch_frames"], 0)
        self.assertEqual(angle_difference(-32760, 32760), 16)

    def test_mismatched_movement_and_grounding_reported(self):
        reference = [
            Sample(0, 0.0, 0.0, 0.0, 0, True),
            Sample(1, 2.0, 1.0, 0.0, 0, False),
        ]
        candidate = [
            Sample(0, 10.0, 10.0, 10.0, 0, True),
            Sample(1, 11.0, 10.0, 10.0, 16384, True),
        ]
        result = compare(reference, candidate, 1.0)
        self.assertEqual(result["max_horizontal_error"], 1.0)
        self.assertEqual(result["max_vertical_error"], 1.0)
        self.assertEqual(result["max_yaw_error_degrees"], 90.0)
        self.assertEqual(result["grounded_mismatch_frames"], 1)

    def test_reference_scale_is_explicit(self):
        reference = [Sample(0, 0.0, 0.0, 0.0, 0, True),
                     Sample(1, 4.0, 2.0, 0.0, 0, True)]
        candidate = [Sample(0, 0.0, 0.0, 0.0, 0, True),
                     Sample(1, 2.0, 1.0, 0.0, 0, True)]
        result = compare(reference, candidate, 0.5)
        self.assertEqual(result["max_horizontal_error"], 0.0)
        self.assertEqual(result["max_vertical_error"], 0.0)

    def test_different_frame_counts_are_rejected(self):
        sample = Sample(0, 0.0, 0.0, 0.0, 0, True)
        with self.assertRaises(TraceError):
            compare([sample], [sample, sample], 1.0)

    def test_parser_rejects_missing_or_skipped_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.csv"
            path.write_text("frame,pos_x,pos_y,pos_z,yaw,grounded\n"
                            "0,0,0,0,0,1\n2,0,0,0,0,1\n", encoding="utf-8")
            with self.assertRaisesRegex(TraceError, "consecutive"):
                read_trace(path)

    def test_parser_accepts_ship_trace_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trace.csv"
            path.write_text("frame,scene,buttons,stick_x,stick_y,pos_x,pos_y,pos_z,"
                            "velocity_x,velocity_y,velocity_z,linear_velocity,yaw,grounded,"
                            "state_flags1,state_flags2\n"
                            "0,1,0,0,0,0,0,0,0,0,0,0,-10,1,0,0\n",
                            encoding="utf-8")
            samples = read_trace(path)
            self.assertEqual(samples[0].yaw, -10)


if __name__ == "__main__":
    unittest.main()
