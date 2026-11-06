"""Synthetic evidence checks for source-encoded original N64 graphics scan."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from original_graphics_scan import (
    scan_original_graphics_resource, valid_f3dex_vertex_dma
)

class OriginalGraphicsScanTests(unittest.TestCase):
    def test_verifies_actual_vertex_dma_encoding_not_just_opcode(self):
        d = bytearray(512)
        # Vertex DMA: 4 vertices to cache slots 0..3, in-file segment 8.
        struct.pack_into(">II", d, 0x40,
                         (0x04 << 24) | (4 << 10) | (4*16 - 1),
                         0x08000100)
        struct.pack_into(">II", d, 0x48, 0xBF000000, 0x00000204)
        struct.pack_into(">II", d, 0x50, 0xB8000000, 0)
        self.assertEqual(valid_f3dex_vertex_dma(bytes(d), 0x40), (4, 0x100))
        report = scan_original_graphics_resource(bytes(d))
        self.assertEqual(report["valid_f3dex_vertex_dmas"], 1)
        self.assertEqual(report["first_vtx_dma_offsets"], [0x40])
        self.assertEqual(report["f3dex_enddl_opcode_candidates"], 1)
        self.assertEqual(report["f3dex_tri1_opcode_candidates"], 1)
        self.assertNotIn("bytes", report)

    def test_rejects_fake_dma_addresses_counts_and_unaligned_vertices(self):
        d = bytearray(512)
        struct.pack_into(">II", d, 0x40,
                         (0x04 << 24) | (4 << 10) | 63,
                         0x09000100)
        self.assertIsNone(valid_f3dex_vertex_dma(d, 0x40))
        struct.pack_into(">II", d, 0x40,
                         (0x04 << 24) | (4 << 10) | 63,
                         0x08000101)
        self.assertIsNone(valid_f3dex_vertex_dma(d, 0x40))
        struct.pack_into(">II", d, 0x40,
                         (0x04 << 24) | (4 << 10) | 30,
                         0x08000100)
        self.assertIsNone(valid_f3dex_vertex_dma(d, 0x40))
        self.assertEqual(scan_original_graphics_resource(d)[
            "valid_f3dex_vertex_dmas"], 0)

    def test_segment8_rig_header_candidate_not_auto_claimed_renderable(self):
        d = bytearray(1024)
        flags = (2 << 8) | 7
        struct.pack_into(">III", d, 0x100, flags, 0x08000200,
                         0x08000300)
        struct.pack_into(">Ibb9h", d, 0x300,
                         0x08000380, 0, 0,
                         1,1,1,0,0,0,0,0,0)
        report = scan_original_graphics_resource(d)
        self.assertIn(0x100, report["first_rig_header_offsets"])
        self.assertGreaterEqual(report["animated_skeleton_header_candidates"], 1)
        self.assertIn("NOT confirmed", report["interpretation"])

if __name__ == "__main__":
    unittest.main()
