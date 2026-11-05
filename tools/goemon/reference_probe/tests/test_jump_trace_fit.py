"""Synthetic regression for real-trace PlayerTask/Object decoding and jump replay."""
from __future__ import annotations

import csv
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jump_trace_fit import analyze, read_data


def recording(impulse: float, held_frames: int, character: int, initial_sample: int):
    height = 0.0
    velocity = impulse
    out = []
    for tick in range(30):
        pressed = 0x8000 if tick == 0 else 0
        held = 0x8000 if tick < held_frames else 0
        step = min(velocity, 2.0) if not held else velocity
        grounded = height + step <= 0.0001
        if grounded:
            step = -height
            height = 0.0
            velocity = 0.0
        else:
            height += step
            velocity = step - 2.0 / 3.0
        aid = 23 if step > 0 else (25 if height > 0 and velocity < 0 else 26)
        out.append({
            "sample": initial_sample + tick,
            "game_frames": initial_sample + tick + 100,
            "character_id": character,
            "action_id": aid,
            "buttons_held": held,
            "buttons_pressed": pressed,
            "root_pos_x": 10.0,
            "root_pos_y": -165.0,
            "root_pos_z": -20.0,
            "object_y": -165.0 + height,
            "vertical_step": step,
            "next_vertical_step": velocity,
        })
        if grounded:
            break
    return out


class JumpTraceFitTests(unittest.TestCase):
    def test_full_and_short_jump_exact_replay(self):
        full = recording(6.0, 19, 2, 0)
        short = recording(6.0, 1, 3, len(full))
        records = full + short
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "reference.csv"
            raw_path = Path(tmp) / "runtime.log"
            fields = (
                "sample", "game_frames", "character_id", "action_id",
                "buttons_held", "buttons_pressed", "root_pos_x",
                "root_pos_y", "root_pos_z",
            )
            with csv_path.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for row in records:
                    writer.writerow({field: row[field] for field in fields})
            with raw_path.open("w", encoding="utf-8") as stream:
                for row in records:
                    blob = bytearray(0xF0)
                    for address, value in (
                        (0x68, 0.0), (0x6C, row["vertical_step"]),
                        (0x70, 0.0), (0xA4, row["next_vertical_step"]),
                    ):
                        struct.pack_into(">f", blob, address, value)
                    i, ch, aid = (
                        row["sample"], row["character_id"], row["action_id"]
                    )
                    stream.write(f"GOEMON_TASK,{i},0,{ch},{aid},{blob.hex()}\n")
                    stream.write(
                        f"GOEMON_OBJ,{i},{ch},{aid},10.0,{row['object_y']},"
                        "-20.0,0,0,0,0.0\n"
                    )
            decoded = read_data(csv_path, raw_path)
            output = analyze(decoded)
            self.assertEqual(output["samples"], 29)
            self.assertEqual(output["jump_start_events"], 2)
            self.assertEqual(output["jump_replay_status"], {"exact_full_replay": 2})
            self.assertEqual(
                output["delta_equals_task_velocity_within_0_002"]["y"], 27
            )
            self.assertEqual([x["steps_compared"] for x in output["jump_replays"]],
                             [19, 10])
            self.assertEqual([x["max_height"] for x in output["jump_replays"]],
                             [30.0, 10.0])

    def test_wrong_original_task_size_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "reference.csv"
            raw_path = Path(tmp) / "runtime.log"
            csv_path.write_text(
                "sample,game_frames,character_id,action_id,buttons_held,"
                "buttons_pressed,root_pos_x,root_pos_y,root_pos_z\n"
                "0,1,2,23,32768,32768,0,-165,0\n", encoding="utf-8",
            )
            raw_path.write_text(
                "GOEMON_TASK,0,1,2,23,beef\n"
                "GOEMON_OBJ,0,2,23,0,-159,0,0,0,0,0\n", encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "PlayerTask length"):
                read_data(csv_path, raw_path)


if __name__ == "__main__":
    unittest.main()
