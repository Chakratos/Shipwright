"""Synthetic original player-overlay JR/table metadata tests; no ROM required."""
import sys
from pathlib import Path
import struct
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from inspect_original_player_jump_tables import (
    table_runs, inspect_indirect_jump, analyze_original_overlay)

BASE = 0x80100000


def blob(words):
    return struct.pack('>' + 'I' * len(words), *words)


class OriginalPlayerJumpTableTests(unittest.TestCase):
    def test_contiguous_absolute_vram_function_target_run(self):
        words = [0] * 80
        words[20:25] = [BASE + 0x100, BASE + 0x108,
                        BASE + 0x108, BASE + 0x114, BASE + 0x120]
        runs = table_runs(blob(words), BASE + 0x100, BASE + 0x130)
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]['entry_count'], 5)
        self.assertEqual(runs[0]['unique_in_function_target_count'], 4)
        self.assertFalse(runs[0]['is_verified_active_switch_table'])

    def test_non_contiguous_or_unaligned_target_is_not_a_table(self):
        words = [0, BASE + 0x100, 0, BASE + 0x110, 0, BASE + 0x111]
        self.assertEqual(table_runs(blob(words), BASE + 0x100,
                                    BASE + 0x130), [])

    def test_real_jr_register_and_last_lw_site_only(self):
        words = [0] * 32
        words[3] = (0x23 << 26) | (8 << 21) | (25 << 16) | 4
        words[5] = (25 << 21) | 8  # jr t9
        report = inspect_indirect_jump(blob(words), BASE, BASE + 20,
                                       BASE, 0x70)
        self.assertEqual(report['jr_target_register'], 'r25')
        self.assertEqual(report['last_syntactic_lw_to_jr_register_pc'],
                         f'0x{BASE+12:08X}')
        self.assertEqual(report['possible_absolute_vram_target_pointer_runs'], [])

    def test_source_function_match_and_wrong_opcode_refused(self):
        words = [0] * 24
        words[5] = (8 << 21) | 8  # jr t0
        funcs = [{'start': BASE, 'size': 0x40, 'name': 'synthetic'}]
        report = analyze_original_overlay(blob(words), BASE, funcs,
                                          [BASE + 20])
        self.assertFalse(report['confirmed_runtime_action_dispatch'])
        with self.assertRaisesRegex(ValueError, 'not a MIPS JR'):
            inspect_indirect_jump(blob(words), BASE, BASE + 12,
                                  BASE, 0x40)

    def test_jr_ra_is_not_switch_dispatch(self):
        words = [0] * 4
        words[1] = (31 << 21) | 8
        with self.assertRaisesRegex(ValueError, 'JR ra'):
            inspect_indirect_jump(blob(words), BASE, BASE + 4, BASE, 16)


if __name__ == '__main__':
    unittest.main()
