"""Pure Python tests for bounded Goemon memory captures and field candidates."""
from __future__ import annotations

import math
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from memory_candidates import find_candidates, parse_log, score_pair


def simulated_log(samples: int = 30, *, character: int = 2) -> str:
    rows = ["random startup message"]
    for i in range(samples):
        x = float((i * i * 3) % 29) + i * 0.125
        y = float((i * 11) % 7)
        z = float((i * 13) % 23) - 11.0
        buf = bytearray(0x1C0)
        struct.pack_into(">f", buf, 0x30, x)
        struct.pack_into(">f", buf, 0x34, y)
        struct.pack_into(">f", buf, 0x38, z)
        rows.append(
            f"DEBUG GOEMON_MEM,{i * 4},{i},{character},3,"
            f"{x + 100.0},{5.0 + y * 0.75},{z * 2.0 - 3.0},{buf.hex()}"
        )
    return "\n".join(rows)


class MemoryCandidatesTests(unittest.TestCase):
    def test_parse_and_find_original_big_endian_xyz(self):
        samples = parse_log(simulated_log())
        self.assertEqual(len(samples), 30)
        self.assertEqual(samples[0].character_id, 2)
        out = find_candidates(samples, top=8, min_r2=0.99)
        for name, address in (("x", 0x30), ("y", 0x34), ("z", 0x38)):
            matched = [record for record in out[name]
                       if record["offset"] == address and record["endian"] == "big"]
            self.assertTrue(matched, f"no matching original field for {name}: {out[name]}")
            self.assertAlmostEqual(matched[0]["r2"], 1.0, places=5)

    def test_reject_truncated_player_memory(self):
        with self.assertRaisesRegex(ValueError, "expected 448 memory bytes"):
            parse_log("GOEMON_MEM,0,0,0,0,0,0,0,abcd")

    def test_reject_out_of_order_samples(self):
        row = simulated_log(1).splitlines()[1]
        with self.assertRaisesRegex(ValueError, "duplicate or out-of-order"):
            parse_log(row + "\n" + row)

    def test_reject_nonfinite_root(self):
        row = simulated_log(1).splitlines()[1].replace(",100.0,", ",nan,")
        with self.assertRaisesRegex(ValueError, "non-finite root"):
            parse_log(row)

    def test_insufficient_samples_and_mixed_characters(self):
        few = parse_log(simulated_log(7))
        with self.assertRaisesRegex(ValueError, "at least 8"):
            find_candidates(few)
        mixed = parse_log(simulated_log(15, character=0))
        alternate = parse_log(simulated_log(15, character=1))
        with self.assertRaisesRegex(ValueError, "one character"):
            find_candidates(mixed + alternate)

    def test_fits_preserve_reference_scale(self):
        fit = score_pair(list(range(10)), [5.0 + 3.0 * x for x in range(10)])
        self.assertIsNotNone(fit)
        r2, rmse, slope, intercept = fit
        self.assertAlmostEqual(r2, 1.0)
        self.assertAlmostEqual(rmse, 0.0)
        self.assertAlmostEqual(slope, 3.0)
        self.assertAlmostEqual(intercept, 5.0)

    def test_constant_player_field_is_not_interpreted_as_position(self):
        samples = parse_log(simulated_log(15))
        all_zero = [struct.unpack_from(">f", s.raw, 0xA0)[0] for s in samples]
        varied_root = [s.root[0] for s in samples]
        self.assertIsNone(score_pair(all_zero, varied_root))


if __name__ == "__main__":
    unittest.main()
