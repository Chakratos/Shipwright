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

    def test_selector_through_andi_then_lbu_is_structural_offset_candidate(self):
        from inspect_original_player_jump_tables import trace_index_register_load
        words = [0] * 14
        words[0] = (0x24 << 26) | (4 << 21) | (9 << 16) | 0xCC
        words[1] = (0x0C << 26) | (9 << 21) | (11 << 16) | 0xF  # andi r11,r9,15
        words[2] = (11 << 16) | (10 << 11) | (2 << 6)
        words[3] = (8 << 21) | (10 << 16) | (8 << 11) | 0x21
        words[4] = (0x23 << 26) | (8 << 21) | (12 << 16)
        r = trace_index_register_load(blob(words), BASE, BASE, BASE + 16)
        self.assertEqual(r['selector_chain_stop_reason'], 'memory_field_load')
        self.assertEqual(r['selector_transform_chain'][0]['operation'], 'andi')
        self.assertEqual(r['selector_field_offset'], 0xCC)
        self.assertTrue(r['selector_offset_cc_syntactic_candidate'])

    def test_unmodeled_comparison_is_reported_as_metadata_only(self):
        from inspect_original_player_jump_tables import trace_index_register_load
        words = [0] * 9
        words[0] = (8 << 21) | (11 << 16) | (9 << 11) | 0x2B  # sltu r9,r8,r11
        words[1] = (9 << 21) | (10 << 16) | (9 << 11) | 9  # addiu r9,r9,9
        words[2] = (9 << 16) | (12 << 11) | (2 << 6)
        words[3] = (1 << 21) | (12 << 16) | (1 << 11) | 0x21
        words[4] = (35 << 26) | (1 << 21) | (12 << 16)
        result = trace_index_register_load(blob(words), BASE, BASE, BASE + 16)
        self.assertEqual(result['selector_chain_stop_instruction_category'], 'comparison')
        self.assertEqual(result['selector_chain_stop_pc'], f'0x{BASE:08X}')
        self.assertFalse(result['index_ancestry_within_source_function'])

    def test_selector_shift_right_then_addiu_lhu_ancestry(self):
        from inspect_original_player_jump_tables import trace_index_register_load
        words = [0] * 14
        words[0] = (0x25 << 26) | (3 << 21) | (9 << 16) | 0x30  # lhu r9,0x30(r3)
        words[1] = (9 << 16) | (11 << 11) | (4 << 6) | 2       # srl r11,r9,4
        words[2] = (9 << 26) | (11 << 21) | (11 << 16) | 1    # addiu r11,r11,1
        words[3] = (11 << 16) | (10 << 11) | (2 << 6)        # sll r10,r11,2
        words[4] = (8 << 21) | (10 << 16) | (8 << 11) | 0x21 # addu r8,r8,r10
        words[5] = (35 << 26) | (8 << 21) | (12 << 16)
        report = trace_index_register_load(blob(words), BASE, BASE, BASE + 20)
        self.assertTrue(report['index_ancestry_within_source_function'])
        self.assertEqual(report['selector_field_offset'], 0x30)
        self.assertEqual([item['operation'] for item in report['selector_transform_chain']],
                         ['addiu', 'srl'])

    def test_function_bound_trace_reaches_load_older_than_64_instructions(self):
        from inspect_original_player_jump_tables import trace_index_register_load
        words = [0] * 128
        words[4] = (0x24 << 26) | (4 << 21) | (9 << 16) | 0xCC
        words[94] = (9 << 16) | (10 << 11) | (2 << 6)
        words[95] = (8 << 21) | (10 << 16) | (8 << 11) | 0x21
        words[96] = (0x23 << 26) | (8 << 21) | (12 << 16)
        result = trace_index_register_load(blob(words), BASE, BASE, BASE + 96 * 4)
        self.assertEqual(result['selector_load_pc'], f'0x{BASE + 16:08X}')
        self.assertEqual(result['selector_field_offset'], 0xCC)
        self.assertTrue(result['selector_source_straight_line_proven'])

    def test_selector_control_transfer_records_ambiguity_not_proof(self):
        from inspect_original_player_jump_tables import trace_index_register_load
        words = [0] * 12
        words[0] = (0x24 << 26) | (4 << 21) | (9 << 16) | 0xCC
        words[1] = (0x04 << 26) | (2 << 21) | (3 << 16) | 1
        words[3] = (9 << 16) | (10 << 11) | (2 << 6)
        words[4] = (8 << 21) | (10 << 16) | (8 << 11) | 0x21
        words[5] = (0x23 << 26) | (8 << 21) | (12 << 16)
        result = trace_index_register_load(blob(words), BASE, BASE, BASE + 20)
        self.assertEqual(result['selector_load_to_jr_control_transfer_count'], 1)
        self.assertFalse(result['selector_source_straight_line_proven'])
        self.assertTrue(result['no_live_player_pointer_or_action_proven'])

    def test_zero_register_does_not_inherit_nop_definitions(self):
        from inspect_original_player_jump_tables import trace_index_register_load
        words = [0] * 32
        words[12] = (9 << 26) | (0 << 21) | (9 << 16) | 3  # addiu r9,r0,3
        words[13] = (9 << 16) | (10 << 11) | (2 << 6)    # sll r10,r9,2
        words[14] = (8 << 21) | (10 << 16) | (8 << 11) | 0x21
        words[15] = (35 << 26) | (8 << 21) | (12 << 16)
        result = trace_index_register_load(blob(words), BASE, BASE, BASE + 60)
        self.assertEqual(result['selector_chain_stop_reason'], 'constant_zero_register')
        self.assertEqual(len(result['selector_transform_chain']), 1)
        self.assertEqual(result['selector_transform_chain'][0]['operation'], 'addiu')
        self.assertFalse(result['index_ancestry_within_source_function'])
        self.assertIsNone(result['selector_load_pc'])

    def test_selector_object_pointer_definition_is_source_load_metadata(self):
        from inspect_original_player_jump_tables import inspect_selector_object_base
        words = [0] * 12
        words[1] = (0x23 << 26) | (4 << 21) | (3 << 16) | 0x2C
        words[3] = (0x25 << 26) | (3 << 21) | (9 << 16) | 0x30
        report = inspect_selector_object_base(blob(words), BASE, BASE, BASE + 12)
        self.assertEqual(report['selector_object_nearest_definition_kind'], 'lw')
        self.assertEqual(report['selector_object_nearest_definition_offset'], 0x2C)
        self.assertEqual(report['selector_object_nearest_definition_base_register'], 'r4')
        self.assertFalse(report['actual_player_object_owner_verified'])

    def test_nested_selector_pointer_base_origin_from_entry_a0(self):
        from trace_player_writer_cfg import origin_at
        words = [0] * 12
        words[0] = (0x23 << 26) | (4 << 21) | (3 << 16) | 0x5C
        words[4] = (0x25 << 26) | (3 << 21) | (9 << 16) | 0x30
        r = origin_at(words, BASE, 0, 0, 4)
        self.assertEqual(r['origin'], 'entry_a0')
        self.assertTrue(r['complete'])


    def test_zero_anchored_addiu_recovers_nonzero_immediate(self):
        from inspect_original_player_jump_tables import trace_index_register_load
        words = [0] * 24
        words[3] = (9 << 26) | (9 << 16) | 3
        words[4] = (9 << 16) | (10 << 11) | (2 << 6)
        words[5] = (8 << 21) | (10 << 16) | (8 << 11) | 0x21
        words[6] = (35 << 26) | (8 << 21) | (12 << 16)
        got = trace_index_register_load(blob(words), BASE, BASE, BASE + 24)
        self.assertEqual(got['constant_selector_candidate_index'], 3)
        self.assertEqual(got['constant_selector_candidate_scaled_byte_offset'], 12)
        self.assertEqual(got['constant_selector_candidate_control_transfers'], 0)
        self.assertTrue(got['constant_selector_candidate_ignores_alternative_paths'])
        self.assertTrue(got['no_live_player_pointer_or_action_proven'])

    def test_zero_anchored_ori_and_addiu_chain(self):
        from inspect_original_player_jump_tables import trace_index_register_load
        words = [0] * 24
        words[1] = (13 << 26) | (9 << 16) | 5
        words[2] = (9 << 26) | (9 << 21) | (9 << 16) | 2
        words[3] = (9 << 16) | (10 << 11) | (2 << 6)
        words[4] = (8 << 21) | (10 << 16) | (8 << 11) | 0x21
        words[5] = (35 << 26) | (8 << 21) | (12 << 16)
        got = trace_index_register_load(blob(words), BASE, BASE, BASE + 20)
        self.assertEqual(got['constant_selector_candidate_index'], 7)
        self.assertEqual(got['constant_selector_candidate_scaled_byte_offset'], 28)

    def test_literal_candidate_across_branch_is_not_cfg_proof(self):
        from inspect_original_player_jump_tables import trace_index_register_load
        words = [0] * 24
        words[0] = (9 << 26) | (9 << 16) | 1
        words[1] = (4 << 26) | (2 << 21) | (3 << 16) | 2
        words[3] = (9 << 16) | (10 << 11) | (2 << 6)
        words[4] = (8 << 21) | (10 << 16) | (8 << 11) | 0x21
        words[5] = (35 << 26) | (8 << 21) | (12 << 16)
        got = trace_index_register_load(blob(words), BASE, BASE, BASE + 20)
        self.assertEqual(got['constant_selector_candidate_index'], 1)
        self.assertEqual(got['constant_selector_candidate_control_transfers'], 1)
        self.assertTrue(got['constant_selector_candidate_ignores_alternative_paths'])

    def test_unresolved_variable_shift_rejects_literal_index(self):
        from inspect_original_player_jump_tables import reconstruct_zero_register_selector_candidate
        shift = (7 << 21) | (9 << 16) | (9 << 11) | 4
        got = reconstruct_zero_register_selector_candidate(
            [('sllv', shift), ('addiu', (9 << 26) | (9 << 16) | 2)], 2)
        self.assertIsNone(got['candidate_index'])
        self.assertFalse(got['evaluation_complete'])

    def test_joined_cfg_index_shift_input_is_constant_when_supported(self):
        from trace_player_writer_cfg import origin_at
        words = [0] * 6
        words[0] = (9 << 26) | (9 << 16) | 1
        words[1] = (9 << 16) | (10 << 11) | (2 << 6)
        result = origin_at(words, BASE, 0, 1, 9)
        self.assertEqual(result['constant_value'], 1)
        self.assertTrue(result['complete'])


    def test_static_dispatch_entry_pointer_word_and_lui_low_pair_metadata(self):
        from inspect_original_player_jump_tables import inspect_static_dispatch_entry_refs
        target = 0x80100040
        words = [target, (15 << 26) | (8 << 16) | 0x8010,
                 (9 << 26) | (8 << 21) | (8 << 16) | 0x40, 0]
        funcs = [{'start': BASE, 'size': 16, 'name': 'fixture'}]
        result = inspect_static_dispatch_entry_refs(words, BASE, target, funcs)
        self.assertEqual(result['exact_unrelocated_word_count'], 1)
        self.assertEqual(result['lui_low_constant_pair_count'], 1)
        self.assertTrue(result['first_lui_low_constant_pairs'][0]['same_pinned_function'])
        self.assertFalse(result['function_pointer_usage_at_runtime_verified'])

    def test_static_entry_ref_register_clobber_rejects_false_pair(self):
        from inspect_original_player_jump_tables import inspect_static_dispatch_entry_refs
        target = 0x80100040
        words = [(15 << 26) | (8 << 16) | 0x8010,
                 (9 << 26) | (0 << 21) | (8 << 16) | 1,
                 (9 << 26) | (8 << 21) | (8 << 16) | 0x40]
        result = inspect_static_dispatch_entry_refs(
            words, BASE, target, [{'start': BASE, 'size': 12}])
        self.assertEqual(result['lui_low_constant_pair_count'], 0)

    def test_static_entry_ref_branch_barrier_rejects_false_pair(self):
        from inspect_original_player_jump_tables import inspect_static_dispatch_entry_refs
        target = 0x80100040
        words = [(15 << 26) | (8 << 16) | 0x8010,
                 (4 << 26) | (2 << 21) | (3 << 16) | 1,
                 (9 << 26) | (8 << 21) | (8 << 16) | 0x40]
        result = inspect_static_dispatch_entry_refs(
            words, BASE, target, [{'start': BASE, 'size': 12}])
        self.assertEqual(result['lui_low_constant_pair_count'], 0)


    def test_cfg_static_pointer_store_into_entry_a0_field(self):
        from inspect_original_player_jump_tables import (
            inspect_static_dispatch_entry_refs, inspect_static_callback_pointer_uses)
        target = 0x80100040
        words = [(15 << 26) | (8 << 16) | 0x8010,
                 (9 << 26) | (8 << 21) | (8 << 16) | 0x40,
                 (0x2B << 26) | (4 << 21) | (8 << 16) | 0x58,
                 0]
        functions = [{'start': BASE, 'size': 16, 'name': 'fixture'}]
        refs = inspect_static_dispatch_entry_refs(words, BASE, target, functions)
        use = inspect_static_callback_pointer_uses(
            words, BASE, target, functions, refs['first_lui_low_constant_pairs'])
        self.assertEqual(use['local_cfg_pointer_sw_count'], 1)
        self.assertEqual(use['first_local_cfg_pointer_stores'][0]['store_field_offset'], 0x58)
        self.assertEqual(use['first_local_cfg_pointer_stores'][0]['destination_base_origin'],
                         'entry_a0')
        self.assertFalse(use['first_local_cfg_pointer_stores'][0][
                         'original_callback_registration_executed'])

    def test_cfg_static_pointer_store_clobber_is_rejected(self):
        from inspect_original_player_jump_tables import (
            inspect_static_dispatch_entry_refs, inspect_static_callback_pointer_uses)
        target = 0x80100040
        words = [(15 << 26) | (8 << 16) | 0x8010,
                 (9 << 26) | (8 << 21) | (8 << 16) | 0x40,
                 (9 << 26) | (0 << 21) | (8 << 16) | 0,
                 (0x2B << 26) | (4 << 21) | (8 << 16) | 0x58]
        functions = [{'start': BASE, 'size': 16, 'name': 'fixture'}]
        refs = inspect_static_dispatch_entry_refs(words, BASE, target, functions)
        use = inspect_static_callback_pointer_uses(
            words, BASE, target, functions, refs['first_lui_low_constant_pairs'])
        self.assertEqual(use['local_cfg_pointer_sw_count'], 0)

    def test_callback_data_neighborhood_is_only_adjacency(self):
        from inspect_original_player_jump_tables import inspect_static_callback_pointer_uses
        target, other = BASE + 0x40, BASE + 0x60
        words = [0, target, other, target, 0]
        funcs = [{'start': target, 'size': 8}, {'start': other, 'size': 8}]
        r = inspect_static_callback_pointer_uses(words, BASE, target, funcs, [])
        self.assertEqual(r['raw_word_pinned_function_pointer_adjacency'][0][
            'adjacent_pinned_function_pointer_word_count'], 3)
        self.assertTrue(r['external_or_relocated_callback_registration_unresolved'])

    def test_callback_run_position_and_action_symbol_overlap_metadata(self):
        from inspect_original_player_jump_tables import inspect_static_callback_pointer_uses
        target, other, action = BASE + 0x40, BASE + 0x60, BASE + 0x80
        words = [0, other, target, action, target, 0]
        funcs = [{'start': target, 'size': 8}, {'start': other, 'size': 8},
                 {'start': action, 'size': 8}]
        use = inspect_static_callback_pointer_uses(
            words, BASE, target, funcs, [],
            action_sites=[{'pc': f'0x{action:08X}'}])
        run = use['raw_word_pinned_function_pointer_adjacency'][0]
        self.assertEqual(run['run_start_pc'], f'0x{BASE+4:08X}')
        self.assertEqual(run['run_end_pc_exclusive'], f'0x{BASE+20:08X}')
        self.assertEqual(run['index_within_adjacent_function_pointer_run'], 1)
        self.assertEqual(run['adjacent_pinned_function_pointer_word_count'], 4)
        self.assertEqual(run['distinct_pinned_function_pointer_count'], 3)
        self.assertEqual(run['candidate_action_writer_function_count_in_run'], 1)
        self.assertEqual(run['candidate_action_writer_function_pcs_in_run'], [
            f'0x{action:08X}'])


    def test_pointer_run_reader_lui_lw_then_indirect_jalr(self):
        from inspect_original_player_jump_tables import inspect_pointer_run_loads
        target = 0x80203B90
        words = [(15 << 26) | (8 << 16) | 0x8020,
                 (0x23 << 26) | (8 << 21) | (9 << 16) | 0x3B90,
                 (9 << 21) | 9,
                 0]
        funcs = [{'start': BASE, 'size': 16, 'name': 'fixture'}]
        r = inspect_pointer_run_loads(words, BASE, funcs, target, target + 16)
        self.assertEqual(r['syntactic_lw_low_field_match_count'], 1)
        self.assertEqual(r['high_lui_matched_count'], 1)
        match = r['first_candidate_lw_sites'][0]
        self.assertEqual(match['high_address_source'], 'direct_lui_hi')
        self.assertEqual(match['next_indirect_transfer_kind'], 'jalr')
        self.assertFalse(not match['not_proof_of_execution_or_dispatch'])

    def test_pointer_run_reader_no_lui_is_not_verified_base(self):
        from inspect_original_player_jump_tables import inspect_pointer_run_loads
        words = [(0x23 << 26) | (8 << 21) | (9 << 16) | 0x3B90]
        funcs = [{'start': BASE, 'size': 4}]
        result = inspect_pointer_run_loads(
            words, BASE, funcs, 0x80203B90, 0x80203C00)
        self.assertEqual(result['high_lui_matched_count'], 0)
        self.assertEqual(result['first_candidate_lw_sites'][0]['high_address_source'],
                         'unresolved_base')

    def test_pointer_run_reader_rejects_wrong_low_address(self):
        from inspect_original_player_jump_tables import inspect_pointer_run_loads
        words = [(15 << 26) | (8 << 16) | 0x8020,
                 (0x23 << 26) | (8 << 21) | (9 << 16) | 0x2B90]
        funcs = [{'start': BASE, 'size': 8}]
        result = inspect_pointer_run_loads(
            words, BASE, funcs, 0x80203B90, 0x80203C00)
        self.assertEqual(result['syntactic_lw_low_field_match_count'], 0)

    def test_jr_ra_is_not_switch_dispatch(self):
        words = [0] * 4
        words[1] = (31 << 21) | 8
        with self.assertRaisesRegex(ValueError, 'JR ra'):
            inspect_indirect_jump(blob(words), BASE, BASE + 4, BASE, 16)


if __name__ == '__main__':
    unittest.main()
