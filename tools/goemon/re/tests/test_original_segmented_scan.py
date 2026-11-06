"""Synthetic checks for source-proven Goemon N64 segment 0x09/0x07 mapping."""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from original_segmented_scan import (
    dereference_segmented, n64_vtx_dma,
    scan_segmented_graphics, find_rig_header_candidates, validate_skeleton,
)

class OriginalSegmentedScanTests(unittest.TestCase):
    def fixture(self):
        model = bytearray(0x400)
        geometry = bytearray(0x400)
        # 0x09 root: animated skeleton header and child pointer into 0x09.
        flags = (2 << 8) | 10
        struct.pack_into(">III", model, 0x40, flags, 0x09000200, 0x09000100)
        struct.pack_into(">Ibb9h", model, 0x100,
                         0x07000080, 1, 0,
                         1,1,1, 0,0,0, 12,22,32)
        struct.pack_into(">Ibb9h", model, 0x118,
                         0x070000A0, 0, 0,
                         1,1,1, 0,0,0, 12,22,32)
        # On the source-proven 0x07 geometry bank:
        # gSPVertex 3 vertices, 0..2, 16 bytes each in the 0x07 bank.
        struct.pack_into(">II", geometry, 0x80,
                         (4 << 24) | (3 << 10) | (3*16 - 1),
                         0x07000200)
        struct.pack_into(">II", geometry, 0x88, 0xBF000000, 0x00000204)
        struct.pack_into(">II", geometry, 0x90, 0xB8000000, 0)
        return bytes(model), bytes(geometry)

    def test_segment7_gfx_and_segment9_skeleton_are_both_resolved(self):
        model, geometry = self.fixture()
        banks = {9: model, 7: geometry}
        header = find_rig_header_candidates(model, banks)
        self.assertGreaterEqual(header["candidate_count"], 1)
        self.assertIn(0x40, [x["header_offset"]
                            for x in header["first_candidates"]])
        self.assertEqual(
            [x["first_limb_offset"] for x in header["first_candidates"]
             if x["header_offset"] == 0x40], [0x100])
        result = scan_segmented_graphics(geometry, banks)
        self.assertEqual(result["valid_segmented_f3dex_vtx_dmas"], 1)
        self.assertEqual(result["first_valid_vertex_dmas"][0]["source_segment"], 7)
        self.assertEqual(
            result["raw_f3dex_triangle_command_candidates"], 1)

    def test_previous_segment8_only_heuristic_misses_valid_data(self):
        model, geometry = self.fixture()
        w0, w1 = struct.unpack_from(">II", geometry, 0x80)
        self.assertIsNone(n64_vtx_dma(w0, w1, {8: model}))
        self.assertEqual(n64_vtx_dma(w0, w1, {7: geometry}), (3,0,7))
        self.assertIsNone(dereference_segmented(0x08000100,
                                                {7: geometry, 9: model}))

    def test_outside_bounds_or_invalid_vtx_command_rejected(self):
        model, geometry = self.fixture()
        w0, _ = struct.unpack_from(">II", geometry, 0x80)
        self.assertIsNone(n64_vtx_dma(w0, 0x070003F0, {7: geometry}))
        self.assertIsNone(n64_vtx_dma(w0, 0x09000100, {7: geometry}))
        self.assertIsNone(n64_vtx_dma(
            (4 << 24) | (33 << 10) | (33 * 16 - 1),
            0x07000200, {7: geometry}))
        self.assertIsNone(dereference_segmented(0x07000080, {7:geometry}, 0))
        self.assertIsNone(dereference_segmented(0x80000000, {7:geometry}))

    def test_invalid_rig_child_is_rejected(self):
        model, geometry = self.fixture()
        bad = bytearray(model)
        struct.pack_into(">b", bad, 0x100+4, -128)
        self.assertIsNone(validate_skeleton(0x09000100, {9: bytes(bad),
                                                         7: geometry}))
        self.assertNotIn(0x40, [x["header_offset"] for x in
            find_rig_header_candidates(bytes(bad), {9:bytes(bad),
                                                    7:geometry})["first_candidates"]])

    def test_unmapped_skeleton_and_bad_animation_do_not_create_claims(self):
        model, geometry = self.fixture()
        bad = bytearray(model)
        struct.pack_into(">I", bad, 0x40 + 4, 0x0D000040)
        report = find_rig_header_candidates(bytes(bad),
                                            {9:bytes(bad),7:geometry})
        self.assertNotIn(0x40, [x["header_offset"] for x in
                               report["first_candidates"]])
        self.assertFalse(report["candidate_count"] == 0 and
                         report["first_candidates"])

if __name__ == "__main__":
    unittest.main()
