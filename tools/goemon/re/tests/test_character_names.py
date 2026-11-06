"""Original game character names: cross-source metadata, not ROM name strings."""
from __future__ import annotations
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from character_names import (
    CHARACTER_NAMES, NAME_SOURCES, GLOBAL_CHARACTER_U32_ADDR,
    GAMESHARK_CHARACTER_BYTE_ADDR, corroborated_character_names,
)

class CharacterNameEvidenceTests(unittest.TestCase):
    def test_gameshark_byte_matches_original_trace_global(self):
        self.assertEqual(GLOBAL_CHARACTER_U32_ADDR, 0x8015C5DC)
        self.assertEqual(GAMESHARK_CHARACTER_BYTE_ADDR, 0x8015C5DF)
        self.assertEqual(GAMESHARK_CHARACTER_BYTE_ADDR -
                         GLOBAL_CHARACTER_U32_ADDR, 3)
        self.assertEqual(len(NAME_SOURCES), 2)
        self.assertEqual(len(set(NAME_SOURCES)), 2)

    def test_all_four_names_and_original_graphics_roots(self):
        info = corroborated_character_names((288, 292, 296, 300))
        self.assertEqual(
            [info[i]["character_name"] for i in range(4)], list(CHARACTER_NAMES))
        self.assertEqual(list(CHARACTER_NAMES),
                         ["Goemon", "Ebisumaru", "Sasuke", "Yae"])
        self.assertEqual(
            [info[i]["graphics_root_file_id"] for i in range(4)],
            [288, 292, 296, 300])
        self.assertTrue(all(not x["rom_proven_name_string"] for x in info.values()))

    def test_unverified_roots_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "graphics roots differ"):
            corroborated_character_names((288, 292, 300, 296))
        with self.assertRaisesRegex(ValueError, "graphics roots differ"):
            corroborated_character_names((288, 292, 296))

if __name__ == "__main__":
    unittest.main()
