"""Synthetic live Zelda collision probe CSV regressions."""
from __future__ import annotations
import csv
import math
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ship_world_probe_analysis import analyze

COLUMNS = (
    "frame", "scene", "link_yaw", "link_x", "link_y", "link_z",
    "desired_dx", "desired_dz", "projected_x", "projected_z",
    "wall_hit", "wall_x", "wall_y", "wall_z", "floor_found", "floor_y",
)

class ShipZeldaWorldProbeTests(unittest.TestCase):
    def make_csv(self, folder: Path, broken=False):
        csv_path = folder / "probe.csv"
        rows = [
            [0, 10, 0, 1, 10, 3, 0, 2.8, 1, 5.8, 0, 0, 0, 0, 1, 10],
            [1, 10, 16384, 1, 10, 3, 2.8, 0, 3.8, 3, 1, 2.1, 20, 3, 1, 10],
            [2, 20, 32768, 6, 20, 9, 0, -2.8, 6, 6.2, 0, 0, 0, 0, 0, 0],
        ]
        if broken:
            rows[1][8] = 300.0
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(COLUMNS)
            writer.writerows(rows)
        return csv_path

    def test_wall_and_floor_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_csv(Path(tmp))
            result = analyze(path)
        self.assertEqual(result["frames"], 3)
        self.assertEqual(result["scenes"]["10"]["frames"], 2)
        self.assertEqual(result["scenes"]["10"]["wall_hits"], 1)
        self.assertEqual(result["scenes"]["20"]["floor_not_found"], 1)
        self.assertEqual(result["unique_link_yaw_values"], 3)
        self.assertEqual(len(result["collision_or_missing_floor_examples"]), 2)

    def test_malformed_projection_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_csv(Path(tmp),broken=True)
            with self.assertRaisesRegex(ValueError,"projected position"):
                analyze(path)

if __name__ == "__main__":
    unittest.main()
