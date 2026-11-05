"""Synthetic original model-animation progression and hold regression."""
from __future__ import annotations
import csv
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from animation_trace_fit import analyze

class OriginalAnimationTraceTests(unittest.TestCase):
    def test_action_tempo_and_stalled_animation(self):
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / "reference.csv"
            runtime = Path(folder) / "runtime.log"
            rows = []
            records = []
            for character, action, progress in (
                (0, 90, [i * 0.6 for i in range(7)]),
                (3, 162, [i * 0.4 for i in range(7)] + [2.4] * 13),
            ):
                for value in progress:
                    index = len(rows)
                    rows.append([index, index, character, action])
                    records.append(
                        "GOEMON_OBJ," + ",".join(map(str, [
                            index, character, action, 0, 0, 0, 0, 0, 0, value
                        ]))
                    )
            with reference.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(
                    ["sample", "game_frames", "character_id", "action_id"]
                )
                writer.writerows(rows)
            runtime.write_text("\n".join(records) + "\n", encoding="utf-8")
            report = analyze(reference, runtime)

        self.assertEqual(report["total_samples"], 27)
        self.assertEqual(report["total_character_action_pairs"], 2)
        self.assertEqual(report["stable_fixed_rate_pairs"], 1)
        catalog = {
            (p["character_id"], p["action_id"]): p
            for p in report["pairs"]
        }
        self.assertTrue(catalog[(0,90)]["stable_fixed_rate"])
        self.assertEqual(
            catalog[(0,90)]["dominant_positive_progress_step"], 0.6
        )
        self.assertFalse(catalog[(3,162)]["stable_fixed_rate"])
        self.assertEqual(catalog[(3,162)]["holds"], 13)

if __name__ == "__main__":
    unittest.main()
