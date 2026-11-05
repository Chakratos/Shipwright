"""Source-free regression for the 1,311-entry real Goemon file-table shape.

The layout and entry count were verified with an owned NTSC-U NG5E ROM.
No original game bytes or assets are embedded here.
"""
from __future__ import annotations

import struct
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from character_assets import (
    CHARACTER_GRAPHICS_IDS_ROM_OFFSET,
    EXPECTED_CRC,
    FILE_TABLE_ROM_OFFSET,
    make_manifest,
    read_file_table,
)


class RealShapeTableTests(unittest.TestCase):
    def test_real_length_and_one_zero_sentinel(self):
        # Table contains 1,311 files and 227 zero-length entries, as seen
        # in the original Goemon64Recomp-decompressed NTSC-U ROM.
        buf = bytearray(0x600000)
        buf[:4] = bytes.fromhex("80371240")
        struct.pack_into(">II", buf, 0x10, *EXPECTED_CRC)
        for idx in range(1312):
            offset = 0x580000 + max(0, idx - 227) * 16
            struct.pack_into(">I", buf, FILE_TABLE_ROM_OFFSET + idx * 4, offset)
        # One-word terminator: previous non-zero offset and next zero.
        struct.pack_into(">I", buf, FILE_TABLE_ROM_OFFSET + 1312 * 4, 0)
        struct.pack_into(">4H", buf, CHARACTER_GRAPHICS_IDS_ROM_OFFSET,
                         288, 292, 296, 300)
        # Synthetic adjacent resource header mirrors the observed signature,
        # without copying any bytes from the original character assets.
        for slot_root in (288, 292, 296, 300):
            relative = slot_root + 1
            file_start = 0x580000 + max(0, relative - 227) * 16
            buf[file_start:file_start + 7] = b"PIC0000"
        entries = read_file_table(buf)
        self.assertEqual(len(entries), 1311)
        self.assertEqual(sum(e.size == 0 for e in entries), 227)
        manifest, selected = make_manifest(buf)
        self.assertEqual(manifest["file_table_count"], 1311)
        self.assertEqual([e["graphics_file_id"] for e in manifest["character_graphics"]],
                         [288, 292, 296, 300])
        self.assertEqual(len(selected), 4)
        for slot, root in enumerate((288, 292, 296, 300)):
            neighbors = manifest["character_graphics"][slot]["adjacent_resource_candidates"]
            self.assertEqual([x["file_id"] for x in neighbors], list(range(root, root + 4)))
            self.assertEqual(neighbors[1]["signature"], "PIC0000")
            self.assertTrue(all(x["format_role"] is None for x in neighbors))


if __name__ == "__main__":
    unittest.main()
