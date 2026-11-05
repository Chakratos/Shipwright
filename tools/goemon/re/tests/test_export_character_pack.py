"""Deterministic original-ROM local asset pack without proprietary test assets."""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from export_character_pack import make_archive, package_character_files
from pic0000_catalog import MAGIC


def picture(marker=15, flags=0, width=32, height=64, allocated=48):
    return (
        MAGIC + flags.to_bytes(4, "big") + bytes([marker])
        + width.to_bytes(2, "big") + height.to_bytes(2, "big")
        + bytes(allocated - 17)
    )


def fake_resources():
    groups = []
    for char in range(4):
        root = 288 + 4 * char
        images = picture(15, 0, allocated=32) + picture(8, 0x4000, allocated=48)
        groups.append([
            (root, bytes([char + 1]) * 32),
            (root + 1, images),
            (root + 2, bytes([char + 7]) * 48),
            (root + 3, bytes([char + 11]) * 16),
        ])
    return groups


class CharacterPackTests(unittest.TestCase):
    def test_four_groups_sixteen_files_eight_pics(self):
        metadata, files = package_character_files(
            fake_resources(), original_rom_hash="a" * 64,
            decompressed_rom_hash="b" * 64,
        )
        self.assertEqual(metadata["character_slots"], 4)
        self.assertEqual(metadata["resource_file_count"], 16)
        self.assertEqual(metadata["picture_block_count"], 8)
        self.assertEqual(len(files), 16 + 8 + 1)
        self.assertEqual(
            [c["original_root_id"] for c in metadata["characters"]],
            [288, 292, 296, 300],
        )
        for c in metadata["characters"]:
            self.assertEqual(len(c["source_files"]), 4)
            self.assertEqual(len(c["picture_chunks"]), 2)
            self.assertIsNone(c["character_name"])
            for file in c["source_files"]:
                payload = files[file["archive_path"]]
                self.assertEqual(sha256(payload).hexdigest(), file["sha256"])
            for img in c["picture_chunks"]:
                payload = files[img["archive_path"]]
                self.assertEqual(payload[:8], MAGIC)
                self.assertEqual(sha256(payload).hexdigest(), img["sha256"])
        archive = make_archive(files)
        self.assertEqual(archive, make_archive(files))
        with ZipFile(BytesIO(archive)) as z:
            self.assertEqual(sorted(z.namelist()), sorted(files))
            self.assertEqual(json.loads(z.read("manifest.json"))["picture_block_count"], 8)
            for path, raw in files.items():
                self.assertEqual(z.read(path), raw)

    def test_reject_nonoriginal_group_structure(self):
        with self.assertRaisesRegex(ValueError, "four original"):
            package_character_files([], original_rom_hash="a", decompressed_rom_hash="b")
        groups = fake_resources()
        groups[2][1] = (999, groups[2][1][1])
        with self.assertRaisesRegex(ValueError, "non-consecutive"):
            package_character_files(groups, original_rom_hash="a", decompressed_rom_hash="b")

    def test_reject_picture_missing_magic(self):
        groups = fake_resources()
        groups[0][1] = (289, b"\0" * 32)
        with self.assertRaisesRegex(ValueError, "lacks PIC0000"):
            package_character_files(groups, original_rom_hash="a", decompressed_rom_hash="b")

    def test_zip_path_escape_is_rejected(self):
        for bad in ("/absolute.bin", "../escape.bin", "a/../../escape", r"a\bad"):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "invalid original"):
                    make_archive({bad: b"data"})


if __name__ == "__main__":
    unittest.main()
