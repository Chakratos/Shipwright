"""Synthetic regression for verified 1024-step original N64 world heading."""
from __future__ import annotations
import csv
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yaw_trace_fit import analyze


class OriginalYawTraceTests(unittest.TestCase):
    def test_genuine_root_yaw_conversion(self):
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / "reference.csv"
            runtime = Path(folder) / "runtime.log"
            yaw = 761
            vx = 2.8 * math.sin(2 * math.pi * yaw / 1024)
            vz = 2.8 * math.cos(2 * math.pi * yaw / 1024)
            with reference.open("w", newline="", encoding="utf-8") as stream, \
                    runtime.open("w", encoding="utf-8") as game:
                writer = csv.writer(stream)
                writer.writerow([
                    "sample", "character_id", "game_frames", "action_id",
                    "root_rot_y", "stick_raw_x", "stick_raw_y",
                ])
                for index in range(7):
                    writer.writerow([index, 2, index+10, 15, yaw, 0, 93])
                    task = bytearray(240)
                    struct.pack_into(">f", task, 0x68, vx)
                    struct.pack_into(">f", task, 0x70, vz)
                    game.write(f"GOEMON_TASK,{index},0,2,15,{task.hex()}\n")
            result = analyze(reference, runtime)
        self.assertEqual(result["stable_full_speed_heading_samples"], 3)
        self.assertEqual(result["within_0_00002_degrees"], 3)


if __name__ == "__main__":
    unittest.main()
