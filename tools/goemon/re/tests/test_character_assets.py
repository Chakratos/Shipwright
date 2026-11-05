"""Validate original MNSG asset table parsing without shipping any ROM data."""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from character_assets import (
    CHARACTER_GRAPHICS_IDS_ROM_OFFSET,
    EXPECTED_CRC,
    FILE_TABLE_ROM_OFFSET,
    make_manifest,
    read_file_table,
    validate_decompressed_rom,
)


def fake_decompressed_rom():
    rom = bytearray(0x610000)
    rom[:4] = bytes.fromhex("80371240")
    struct.pack_into(">II", rom, 0x10, *EXPECTED_CRC)
    ids = (0, 3, 1, 2)
    struct.pack_into(">4H", rom, CHARACTER_GRAPHICS_IDS_ROM_OFFSET, *ids)
    for i in range(4):
        start = 0x600000 + i * 0x10
        end = start + 0x10
        struct.pack_into(">II", rom, FILE_TABLE_ROM_OFFSET + 8 * i, start, end)
        rom[start:end] = bytes([i + 1]) * 16
    return rom


class AssetManifestTests(unittest.TestCase):
    def test_character_file_ids_and_sha256_are_grounded_in_rom(self):
        rom = fake_decompressed_rom()
        manifest, entries = make_manifest(rom)
        self.assertEqual(manifest["file_table_count"], 4)
        self.assertEqual([x["graphics_file_id"] for x in manifest["character_graphics"]],
                         [0, 3, 1, 2])
        self.assertEqual(len(entries), 4)
        self.assertEqual(manifest["character_graphics"][1]["rom_start"], 0x600030)
        self.assertEqual(manifest["character_graphics"][1]["size"], 16)
        self.assertIsNone(manifest["character_graphics"][1]["character_name"])

    def test_compressed_rom_crc_is_rejected(self):
        rom = fake_decompressed_rom()
        struct.pack_into(">I", rom, 0x10, 0)
        with self.assertRaisesRegex(ValueError, "header CRC mismatch"):
            validate_decompressed_rom(rom)

    def test_invalid_file_id_is_rejected(self):
        rom = fake_decompressed_rom()
        struct.pack_into(">H", rom, CHARACTER_GRAPHICS_IDS_ROM_OFFSET, 999)
        with self.assertRaisesRegex(ValueError, "invalid character graphics file ID"):
            make_manifest(rom)

    def test_overlapping_file_ranges_are_rejected(self):
        rom = fake_decompressed_rom()
        struct.pack_into(">II", rom, FILE_TABLE_ROM_OFFSET + 8, 0x600008, 0x600020)
        with self.assertRaisesRegex(ValueError, "overlapping"):
            read_file_table(rom)

    def test_sentinel_termination_matches_original(self):
        rom = fake_decompressed_rom()
        struct.pack_into(">II", rom, FILE_TABLE_ROM_OFFSET + 4 * 8, 0, 0x7FFFFFFF)
        entries = read_file_table(rom)
        self.assertEqual(len(entries), 4)


if __name__ == "__main__":
    unittest.main()
