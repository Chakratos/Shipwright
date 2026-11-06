"""Original numeric character ID -> graphics root: synthetic opcode regression."""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from character_id_binding import (
    EXPECTED_ORIGINAL_INSTRUCTIONS, source_proven_character_graphics,
)


class OriginalCharacterIdBindingTests(unittest.TestCase):
    def original_fragment(self):
        data = bytearray(0x300)
        function = 0x20
        table = 0x200
        for offset, word in EXPECTED_ORIGINAL_INSTRUCTIONS.items():
            struct.pack_into(">I", data, function + offset, word)
        struct.pack_into(">4H", data, table, 288, 292, 296, 300)
        return data, function, table

    def test_character_id_indexes_four_original_graphics_ids(self):
        image, function, table = self.original_fragment()
        roots = source_proven_character_graphics(
            image, function_offset=function, table_offset=table)
        self.assertEqual(roots, (288, 292, 296, 300))
        self.assertEqual(dict(enumerate(roots))[2], 296)

    def test_different_original_indexing_opcode_is_not_accepted(self):
        image, function, table = self.original_fragment()
        struct.pack_into(">I", image, function + 0x18, 0x000E7880)
        with self.assertRaisesRegex(ValueError, "opcode differs"):
            source_proven_character_graphics(
                image, function_offset=function, table_offset=table)

    def test_duplicate_graphics_root_ids_rejected(self):
        image, function, table = self.original_fragment()
        struct.pack_into(">4H", image, table, 288, 288, 296, 300)
        with self.assertRaisesRegex(ValueError, "not unique"):
            source_proven_character_graphics(
                image, function_offset=function, table_offset=table)


if __name__ == "__main__":
    unittest.main()
