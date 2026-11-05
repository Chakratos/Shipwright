"""Offline tests for MIPS player function references and ROM address mapping."""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import tomllib
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analyze_rom import analyze, functions_in_section, global_references, jal_destination


FAKE_SYMBOLS = """
[[section]]
name = ".file_11"
rom = 0x40
vram = 0x801CB7F0
size = 0x100

functions = [
  { name = "func_801CB800_587710", vram = 0x801CB800, size = 0x20 },
  { name = "test_caller", vram = 0x801CB840, size = 0x20 },
]
"""


def synthetic_rom():
    data = bytearray(0x200)
    data[:4] = bytes.fromhex("80371240")
    # test_caller is 0x50 bytes into the mapped ROM section -> offset 0x90.
    caller = 0x90
    jal = 0x0C000000 | ((0x801CB800 >> 2) & 0x03FFFFFF)
    struct.pack_into(">I", data, caller + 0, jal)
    struct.pack_into(">I", data, caller + 4, 0)
    struct.pack_into(">I", data, caller + 8, 0x3C088020)  # lui $t0, 0x8020
    struct.pack_into(">I", data, caller + 12, 0x8D09C604)  # lw $t1, -0x39fc($t0) -> 0x801fc604
    return bytes(data)


class GoemonRomAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.rom = synthetic_rom()
        self.table = tomllib.loads(FAKE_SYMBOLS)

    def test_function_vram_to_rom_translation(self):
        functions = functions_in_section(self.table, ".file_11")
        self.assertEqual([f.rom for f in functions], [0x50, 0x90])

    def test_direct_jal_and_lui_lw_reference(self):
        report = analyze(self.rom, self.table)
        self.assertEqual(report["functions_scanned"], 2)
        target = next(x for x in report["known_entrypoints"] if x["vram"] == 0x801CB800)
        self.assertEqual(target["rom"], 0x50)
        self.assertEqual(target["size"], 0x20)
        self.assertEqual(target["callers"], [
            {"caller": "test_caller", "callsite": 0x801CB840}
        ])
        refs = report["player_global_references"]
        self.assertEqual(refs, [{
            "function": "test_caller", "lui_pc": 0x801CB848,
            "access_pc": 0x801CB84C, "target": 0x801FC604,
            "global": "player_1_task", "access": "read",
        }])

    def test_wrong_endian_rom_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "big-endian"):
            analyze(b"\x37\x80\x40\x12" + bytes(0x100), self.table)

    def test_lui_register_clobber_prevents_false_positive(self):
        instructions = [
            (0x100, 0x3C088020),  # lui $t0
            (0x104, 0x24080001),  # addiu $t0, $zero, 1 (clobber)
            (0x108, 0x8D09C604),  # lw $t1, -0x39fc($t0)
        ]
        self.assertEqual(list(global_references(instructions)), [])

    def test_bare_lw_is_not_mistaken_for_global_access(self):
        self.assertEqual(list(global_references([(0x100, 0x8D09C604)])), [])

    def test_caller_too_small_is_rejected(self):
        bad = tomllib.loads(FAKE_SYMBOLS.replace(
            'vram = 0x801CB840, size = 0x20',
            'vram = 0x801CB840, size = 0x22'))
        with self.assertRaisesRegex(ValueError, "invalid function bounds"):
            functions_in_section(bad, ".file_11")


if __name__ == "__main__":
    unittest.main()
