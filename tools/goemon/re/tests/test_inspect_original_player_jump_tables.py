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

    def test_lui_index_addu_and_lw_low_immediate_match_table_base(self):
        from inspect_original_player_jump_tables import link_candidate_table_to_lui
        words = [0] * 16
        words[0] = (15 << 26) | (1 << 16) | 0x8011  # lui at,0x8011
        words[1] = (2 << 16) | (3 << 11) | (2 << 6)  # sll v1,v0,2
        words[2] = (1 << 21) | (3 << 16) | (1 << 11) | 0x21  # addu at,at,v1
        words[3] = (35 << 26) | (1 << 21) | (12 << 16) | 0xF0C0  # lw t4,-0xF40(at)
        evidence = link_candidate_table_to_lui(
            blob(words), BASE, BASE, BASE + 12, 0x8010F0C0)
        self.assertEqual(evidence['exact_lui_plus_lw_offset_match_count'], 1)
        self.assertEqual(evidence['direct_or_indexed_base_register_chain_count'], 1)
        self.assertFalse(evidence['actual_runtime_jump_table_verified'])

    def test_mismatched_lui_high_not_linked_to_table(self):
        from inspect_original_player_jump_tables import link_candidate_table_to_lui
        words = [0] * 8
        words[0] = (15 << 26) | (1 << 16) | 0x8030
        words[1] = (35 << 26) | (1 << 21) | (12 << 16) | 0xF0C0
        evidence = link_candidate_table_to_lui(
            blob(words), BASE, BASE, BASE + 4, 0x8010F0C0)
        self.assertEqual(evidence['exact_lui_plus_lw_offset_match_count'], 0)

    def test_trace_synthetic_action_byte_selector_to_indirect_jr(self):
        from inspect_original_player_jump_tables import trace_index_register_load
        words = [0] * 20
        words[1] = (0x24 << 26) | (4 << 21) | (9 << 16) | 0xCC
        words[2] = (9 << 16) | (10 << 11) | (2 << 6)
        words[3] = (8 << 21) | (10 << 16) | (8 << 11) | 0x21
        words[4] = (0x23 << 26) | (8 << 21) | (12 << 16)
        report = trace_index_register_load(blob(words), BASE, BASE, BASE + 16)
        self.assertTrue(report['index_ancestry_within_source_function'])
        self.assertTrue(report['selector_offset_cc_syntactic_candidate'])
        self.assertEqual(report['selector_object_register'], 'r4')
        self.assertEqual(report['selector_load_width'], 'lbu')
        self.assertEqual(report['index_scale'], 2)
        self.assertFalse(not report['no_live_player_pointer_or_action_proven'])

    def test_trace_non_action_selector_retains_offset_without_proof(self):
        from inspect_original_player_jump_tables import trace_index_register_load
        words = [0] * 20
        words[1] = (0x24 << 26) | (16 << 21) | (9 << 16) | 0x60
        words[2] = (9 << 16) | (10 << 11) | (2 << 6)
        words[3] = (8 << 21) | (10 << 16) | (8 << 11) | 0x21
        words[4] = (0x23 << 26) | (8 << 21) | (12 << 16)
        report = trace_index_register_load(blob(words), BASE, BASE, BASE + 16)
        self.assertEqual(report['selector_field_offset'], 0x60)
        self.assertFalse(report['selector_offset_cc_syntactic_candidate'])

    def test_index_ancestry_reports_syntactic_operand_class_not_payload(self):
        from inspect_original_player_jump_tables import trace_index_register_load
        words = [0] * 8
        words[0] = (15 << 26) | (8 << 16) | 0x8011
        words[1] = (9 << 16) | (10 << 11) | (2 << 6)  # sll r10,r9,2
        words[2] = (8 << 21) | (10 << 16) | (8 << 11) | 0x21
        words[3] = (35 << 26) | (8 << 21) | (12 << 16)
        report = trace_index_register_load(blob(words), BASE, BASE, BASE + 12)
        self.assertEqual(report['indexed_operand_definition_kinds'], ['lui', 'sll'])
        self.assertIsNone(report['selector_load_pc'])

    def test_jr_ra_is_not_switch_dispatch(self):
        words = [0] * 4
        words[1] = (31 << 21) | 8
        with self.assertRaisesRegex(ValueError, 'JR ra'):
            inspect_indirect_jump(blob(words), BASE, BASE + 4, BASE, 16)


if __name__ == '__main__':
    unittest.main()
