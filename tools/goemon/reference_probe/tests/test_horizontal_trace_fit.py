"""Synthetic regression for measured original horizontal acceleration and braking."""
from __future__ import annotations
import csv
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from horizontal_trace_fit import load_capture, summarize

class OriginalHorizontalFitTests(unittest.TestCase):
    @staticmethod
    def make_capture(folder, rows):
        csv_file = Path(folder) / "reference.csv"
        log_file = Path(folder) / "game.log"
        columns = [
            "sample", "game_frames", "character_id", "action_id",
            "stick_raw_x", "stick_raw_y", "root_pos_x", "root_pos_z",
        ]
        with csv_file.open("w", encoding="utf-8", newline="") as stream, \
                log_file.open("w", encoding="utf-8") as game:
            writer = csv.DictWriter(stream, fieldnames=columns)
            writer.writeheader()
            for i, (frame, char, action, stick, speed, x, z) in enumerate(rows):
                writer.writerow(dict(zip(
                    columns, (i, frame, char, action, stick, 0, x, z)
                )))
                task = bytearray(0xF0)
                struct.pack_into(">f", task, 0x68, speed)
                struct.pack_into(">f", task, 0x70, 0.0)
                game.write(
                    f"GOEMON_TASK,{i},{frame},{char},{action},{task.hex()}\n"
                )
        return csv_file, log_file

    def test_ground_air_release_and_discontinuity(self):
        rows = [
            (0,0,0,0,0,0,0), (1,0,13,93,.7,.7,0),
            (2,0,15,93,1.24,1.94,0),
            (3,0,15,93,1.78,3.72,0),
            (4,0,15,93,2.32,6.04,0),
            (5,0,15,93,2.8,8.84,0),
            (6,0,16,0,2.0,10.84,0),
            (7,0,16,0,1.4,12.24,0),
            (8,0,16,0,.8,13.04,0),
            (9,0,16,0,.2,13.24,0),
            (10,0,16,0,.4,12.84,0),
            (20,1,0,0,0,100,0),
            (21,1,23,93,.84,100.84,0),
            (22,1,25,93,1.68,102.52,0),
            (23,1,26,93,2.52,105.04,0),
            (24,1,26,93,2.8,107.84,0),
        ]
        with tempfile.TemporaryDirectory() as folder:
            paths = self.make_capture(folder, rows)
            report = summarize(load_capture(*paths))
        phases = report["measured_phases"]
        for phase, count in (
            ("ground_first_0_70",1),
            ("ground_running_add_0_54",4),
            ("airborne_add_0_84",3),
            ("running_release_first_2_00",1),
            ("brake_subtract_0_60_magnitude",4),
        ):
            self.assertEqual(phases[phase]["observations"], count)
            self.assertEqual(phases[phase]["within_0_012"], count)
        self.assertEqual(report["continuous_update_pairs"], 14)
        self.assertEqual(set(report["characters"]), {"0","1"})

    def test_missing_original_task_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = self.make_capture(folder, [(0,0,0,0,0,0,0)])
            paths[1].write_text("", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing original PlayerTask"):
                load_capture(*paths)

if __name__ == "__main__":
    unittest.main()
