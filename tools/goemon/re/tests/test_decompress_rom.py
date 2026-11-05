"""Source-free tests of local US Goemon ROM decompression and file offsets."""
from __future__ import annotations

import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from decompress_rom import (
    FILE_TABLE, DECOMPRESSED_CRC, decode_lzkn64,
    decompress_us_rom, ensure_decompressed_rom,
)
from character_assets import read_file_table


def sample_original_rom():
    data = bytearray(0x1000000)
    data[:4] = bytes.fromhex("80371240")
    data[0x3B:0x3F] = b"NG5E"
    # Each file-table entry is an overlapping start/end 32-bit pair.
    start = 0x600000
    encoded = struct.pack(">I", 10) + b"\x83ABC\x00\x03"  # ABCAB
    data[start:start + len(encoded)] = encoded
    data[start + len(encoded):start + len(encoded) + 2] = b"xy"
    for i, value in enumerate((start | 0x80000000, start + len(encoded),
                               start + len(encoded) + 2, 0)):
        struct.pack_into(">I", data, FILE_TABLE + i * 4, value)
    return bytes(data)


class OriginalRomDecompressionTests(unittest.TestCase):
    def test_lzkn64_raw_and_backreference(self):
        encoded = struct.pack(">I", 10) + b"\x83ABC\x00\x03"
        self.assertEqual(decode_lzkn64(encoded), b"ABCAB")

    def test_original_compressed_and_uncompressed_file_table(self):
        result = decompress_us_rom(sample_original_rom())
        self.assertEqual(struct.unpack_from(">II", result, 0x10), DECOMPRESSED_CRC)
        entries = read_file_table(result)
        self.assertEqual(len(entries), 2)
        self.assertEqual(result[entries[0].start:entries[0].end][:5], b"ABCAB")
        self.assertEqual(result[entries[1].start:entries[1].end][:2], b"xy")
        self.assertEqual((entries[0].size, entries[1].size), (16, 16))
        self.assertEqual(ensure_decompressed_rom(result), result)

    def test_reject_wrong_region(self):
        original = bytearray(sample_original_rom())
        original[0x3B:0x3F] = b"NG5P"
        with self.assertRaisesRegex(ValueError, "NG5E"):
            decompress_us_rom(bytes(original))

    def test_reject_zero_backreference_offset(self):
        encoded = struct.pack(">I", 6) + b"\x00\x00"
        with self.assertRaisesRegex(ValueError, "sliding-window"):
            decode_lzkn64(encoded)

    def test_rle_and_zero_run(self):
        # length 2 of 'Q'; length 2 of zeros; long zero run length 3
        encoded = struct.pack(">I", 9) + b"\xC0Q\xE0\xFF\x01"
        # Header size must match: 4 + 5 bytes = 9
        self.assertEqual(decode_lzkn64(encoded), b"QQ" + b"\0" * 5)


if __name__ == "__main__":
    unittest.main()
