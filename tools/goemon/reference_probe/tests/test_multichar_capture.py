"""Regressions for original mixed-character captures and ZIP recovery."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "diagnostic_mod"))
from character_coverage import summarize_csv
from reprocess_log import reprocess


def fake_multichar_trace(count: int = 40) -> str:
    # Synthetic telemetry; no original ROM bytes or textures.
    rows = [
        "GOEMON_TRACE_ARMED,wait_for_player_movement",
        "GOEMON_TRACE_BEGIN,2,trigger=player_movement",
    ]
    for i in range(count):
        character = i // 10
        x = i * 0.75
        z = i * 1.25
        buffer = bytearray(0x1C0)
        struct.pack_into(">f", buffer, 0x30, x + 7)
        struct.pack_into(">f", buffer, 0x34, z + 11)
        rows.extend((
            "GOEMON_REF," + ",".join(str(x) for x in (
                i, i, character, (i % 4), character, 0,
                x, 1.0, z, 0, 0, 0, 0.0,
                1 if i % 4 == 0 else 0,
                60, 0, 0.75, 0.0,
            )),
            f"GOEMON_MEM,{i},{i},{character},{i%4},{x},1.0,{z},{buffer.hex()}",
            f"GOEMON_TICK,{i},{i},{i},2,{i}",
        ))
    rows.append(f"GOEMON_TRACE_END,{count},{count},manual_stop")
    return "\n".join(rows) + "\n"


class MultiCharacterCaptureTests(unittest.TestCase):
    def test_character_coverage_counts_each_original_slot(self):
        with tempfile.TemporaryDirectory() as d:
            csv_file = Path(d) / "trace.csv"
            with csv_file.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow([
                    "sample","character_id","global_character_id",
                    "action_id","buttons_held","buttons_pressed",
                    "stick_raw_x","stick_raw_y",
                    "root_pos_x","root_pos_y","root_pos_z"
                ])
                for i in range(40):
                    writer.writerow([
                        i,i//10,i//10,i%4,0,1 if i%4 == 0 else 0,
                        60,0,i*.5,0,0
                    ])
            result = summarize_csv(csv_file)
            self.assertEqual(result["total_samples"], 40)
            self.assertEqual(result["observed_character_ids"], [0,1,2,3])
            self.assertEqual([c["samples"] for c in result["character_segments"]],
                             [10,10,10,10])
            for character in range(4):
                self.assertEqual(result["characters"][str(character)]["samples"], 10)
                self.assertEqual(sorted(result["characters"][str(character)]["actions"]),
                                 ["0","1","2","3"])

    def test_reprocess_old_run_without_game_or_repeat_capture(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "run-recovery"
            folder.mkdir()
            raw = folder / "goemon_runtime.log"
            trace = fake_multichar_trace()
            raw.write_text(trace, encoding="utf-8")
            archive = reprocess(folder)
            self.assertEqual(raw.read_text(encoding="utf-8"), trace)
            self.assertTrue(archive.is_file())
            with zipfile.ZipFile(archive) as z:
                files = set(z.namelist())
                self.assertIn("goemon_runtime.log", files)
                self.assertIn("goemon_raw.csv", files)
                self.assertIn("character_coverage.json", files)
                self.assertIn("actions.json", files)
                self.assertIn("ticks.json", files)
                self.assertIn("memory_candidates.json", files)
                summary = json.loads(z.read("capture_summary.json"))
                self.assertEqual(summary["reference_samples"], 40)
                self.assertTrue(all(report["exit_code"] == 0
                                    for report in summary["parsers"].values()))
                coverage = json.loads(z.read("character_coverage.json"))
                self.assertEqual(coverage["observed_character_ids"], [0,1,2,3])
                memory = json.loads(z.read("memory_candidates.json"))
                self.assertEqual(memory["character_ids"], [0,1,2,3])
                self.assertEqual(memory["samples"], 40)


if __name__ == "__main__":
    unittest.main()
