"""Numeric-only Goemon PlayerTask to Ship ghost trace export regressions."""
from __future__ import annotations

import csv
import io
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from export_motion_replay import HEADER, make_replay


def frame(sample, game, char, action, yaw, x, z):
    return {
        "sample": sample, "game_frames": game, "character_id": char,
        "action_id": action, "root_rot_y": yaw,
        "vx": x, "vz": z,
    }


class OriginalMotionExportTests(unittest.TestCase):
    def test_numeric_replay_preserves_exact_source_samples(self):
        source = [
            frame(0, 100, 0, 13, 761, -0.7351038455963135, 2.7017815113067627),
            frame(1, 101, 0, 15, 743, -1.4864791631698608, 2.2839555740356445),
            frame(2, 1542, 0, 25, 486, 0.129, 0.83),
            frame(3, 1543, 1, 186, 486, 0.0, 0.0),
            frame(4, 1544, 1, 0, 486, 0.0, 0.0),
        ]
        output = make_replay(source)
        parsed = csv.DictReader(io.StringIO(output))
        self.assertEqual(tuple(parsed.fieldnames), HEADER)
        data = list(parsed)
        self.assertEqual(len(data), 5)
        self.assertEqual([int(row["continuous_original_update"]) for row in data],
                         [0, 1, 0, 0, 1])
        self.assertEqual(float(data[1]["desired_dx"]), source[1]["vx"])
        self.assertEqual(float(data[1]["desired_dz"]), source[1]["vz"])
        self.assertEqual([int(r["character_id"]) for r in data], [0,0,0,1,1])
        self.assertNotIn("0x8000", output)  # no ROM pointers or memory dumps

    def test_missing_or_overlong_samples_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            make_replay([])
        rows = [
            frame(0, 1, 0, 13, 0, 0.7, 0),
            frame(10, 2, 0, 15, 0, 1.24, 0),
        ]
        with self.assertRaisesRegex(ValueError, "nonconsecutive"):
            make_replay(rows)


if __name__ == "__main__":
    unittest.main()
