"""Verify exact splat.yaml-file-to-ROM-table alignment (one-based labels).

Only synthetic offsets and source metadata: no commercial game bytes.
"""
from pathlib import Path
from unittest.mock import patch
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from character_assets import FileEntry
from source_aligned_character_assets import (
    SOURCE_SPLAT_GROUP_FILES, source_align_character_files,
)

class SourceAlignedFilesTests(unittest.TestCase):
    def setUp(self):
        starts = {source:offset for source,offset,_ in SOURCE_SPLAT_GROUP_FILES}
        self.entries = [FileEntry(i,0,0) for i in range(305)]
        for real in range(288,304):
            src=real+1
            self.entries[real]=FileEntry(
                real,starts[src],starts[src+1]
            )

    def align(self):
        with patch("source_aligned_character_assets.read_file_table",
                   return_value=self.entries):
            with patch("source_aligned_character_assets.character_graphics_ids",
                       return_value=(288,292,296,300)):
                return source_align_character_files(b"synthetic")
    def test_one_based_splat_maps_all_four_original_groups(self):
        groups=self.align()
        self.assertEqual(len(groups),4)
        self.assertEqual(groups[0][0].runtime_file_id,288)
        self.assertEqual(groups[0][0].splat_file_id,289)
        self.assertEqual(groups[0][2].source_segment,7)
        self.assertEqual(groups[0][3].source_segment,9)
        self.assertEqual(groups[1][2].splat_file_id,295)
        self.assertEqual(groups[1][3].splat_file_id,296)
        self.assertEqual(groups[2][2].source_segment,7)
        self.assertEqual(groups[2][3].source_segment,9)
        self.assertEqual(groups[3][2].runtime_file_id,302)
        self.assertEqual(groups[3][2].size,264336)
        self.assertEqual(groups[3][2].source_segment,7)
        self.assertEqual(groups[3][3].runtime_file_id,303)
        self.assertEqual(groups[3][3].size,464)
        self.assertEqual(groups[3][3].source_segment,8)

    def test_wrong_offset_cannot_pretend_to_be_correct_source(self):
        item=self.entries[302]
        self.entries[302]=FileEntry(item.file_id,item.start+16,item.end)
        with self.assertRaisesRegex(ValueError,"file index mismatch"):
            self.align()

    def test_wrong_source_file_length_fails_closed(self):
        item=self.entries[291]
        self.entries[291]=FileEntry(item.file_id,item.start,item.end-16)
        with self.assertRaisesRegex(ValueError,"end mismatch"):
            self.align()

if __name__=="__main__":
    unittest.main()
