"""Falsifiable source-free MIPS CFG provenance regression fixtures."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trace_player_writer_cfg import origin_at, analyze_cfg

BASE = 0x80100000


def ins(op, rs, rt, imm):
    return (op << 26) | (rs << 21) | (rt << 16) | (imm & 65535)


def addu(rd, rs):
    return (rs << 21) | (rd << 11) | 0x21


class MipsCFGProvenanceTests(unittest.TestCase):
    def test_exact_player_global_pointer_load(self):
        words = [ins(15, 0, 8, 0x8020), ins(35, 8, 4, 0xC604), ins(40, 4, 9, 0xCC)]
        self.assertEqual(origin_at(words, BASE, 0, 2, 4)['symbol'], 'player_1_task')

    def test_branch_merge_same_origin(self):
        words = [ins(4, 2, 3, 2), 0, ins(9, 0, 2, 9), 0,
                 ins(15, 0, 8, 0x8020), ins(35, 8, 4, 0xC604),
                 ins(40, 4, 9, 0xCC)]
        self.assertEqual(origin_at(words, BASE, 0, 6, 4)['symbol'], 'player_1_task')

    def test_divergent_branch_path_invalidates_proof(self):
        words = [ins(4, 2, 3, 3), 0,
                 ins(15, 0, 8, 0x8020), ins(35, 8, 4, 0xC604),
                 0, ins(40, 4, 9, 0xCC)]
        self.assertEqual(origin_at(words, BASE, 0, 5, 4)['origin'], 'unknown')

    def test_saved_register_survives_call_caller_saved_does_not(self):
        words = [ins(15, 0, 8, 0x8020), ins(35, 8, 4, 0xC604),
                 addu(16, 4), ins(3, 0, 0, 8), 0,
                 ins(40, 16, 9, 0xCC), ins(40, 4, 9, 0xCC)]
        self.assertEqual(origin_at(words, BASE, 0, 5, 16)['symbol'], 'player_1_task')
        self.assertEqual(origin_at(words, BASE, 0, 6, 4)['origin'], 'unknown')

    def test_delay_slot_store_reads_pretransfer_registers(self):
        words = [ins(15, 0, 8, 0x8020), ins(35, 8, 4, 0xC604),
                 ins(4, 1, 2, 5), ins(40, 4, 9, 0xCC)]
        self.assertEqual(origin_at(words, BASE, 0, 3, 4)['symbol'], 'player_1_task')

    def test_a0_parameter_alias_is_not_proven_player_pointer(self):
        words = [addu(16, 4), ins(40, 16, 9, 0xCC)]
        self.assertEqual(origin_at(words, BASE, 0, 1, 16)['origin'], 'entry_a0')

    def test_prologue_hint_does_not_prove_live_owner(self):
        words = [addu(16, 4), ins(40, 16, 9, 0xCC)]
        site = {'pc': f'0x{BASE+4:08X}', 'base_register': 'r16',
                'nearby_function_prologue_hint': f'0x{BASE:08X}'}
        self.assertEqual(analyze_cfg(words, BASE, [site])[site['pc']]['original_player_owner_verified'], False)

    def test_backjump_before_entry_marks_incomplete(self):
        words = [0, 0, ins(4, 2, 3, -3), 0, ins(40, 4, 9, 0xCC)]
        self.assertEqual(origin_at(words, BASE, 2, 4, 4)['origin'], 'incomplete_cfg')

    def test_supported_branch_likely_joins_taken_and_skipped_slot_paths(self):
        words = [ins(0x14, 2, 3, 1), 0, ins(40, 4, 9, 0xCC)]
        result = origin_at(words, BASE, 0, 2, 4)
        self.assertTrue(result['complete'])
        self.assertEqual(result['origin'], 'entry_a0')

    def test_pinned_symbol_map_covers_all_action_and_caller_sites(self):
        from trace_player_writer_cfg import read_pinned_player_overlay_functions
        data, functions = read_pinned_player_overlay_functions()
        self.assertEqual(len(data['action_sites']), 10)
        self.assertEqual(len(data['direct_caller_sites']), 7)
        self.assertEqual(
            next(f['start'] for f in functions if f['start'] <= 0x801DA5D8 <
                 f['start'] + f['size']), 0x801D9E9C)

    def test_pinned_symbol_alone_does_not_prove_player_owner(self):
        from trace_player_writer_cfg import (
            read_pinned_player_overlay_functions, analyze_cfg_from_pinned_functions)
        _, functions = read_pinned_player_overlay_functions()
        base, pc = 0x801CB460, 0x801CC3DC
        words = [0] * ((pc - base) // 4 + 1)
        words[(pc - base) // 4] = ins(40, 16, 9, 0xCC)
        result = analyze_cfg_from_pinned_functions(
            words, base, [{'pc': '0x801CC3DC', 'base_register': 'r16'}],
            functions)['0x801CC3DC']
        self.assertEqual(result['pinned_function_pc'], '0x801CC30C')
        self.assertFalse(result['live_player_owner_verified'])

    def test_reject_other_overlay_even_with_same_virtual_addresses(self):
        from trace_player_writer_cfg import read_pinned_player_overlay_functions
        import json
        import tempfile
        data, _ = read_pinned_player_overlay_functions()
        data['provenance']['section'] = '.file_13'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad-symbols.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'source symbols mismatch'):
                read_pinned_player_overlay_functions(path)

    def test_cop1_float_arithmetic_not_control_flow(self):
        from trace_player_writer_cfg import is_control
        cop1_adds = ins(0x11, 16, 2, 3)  # fmt=S, FP operation
        self.assertFalse(is_control(cop1_adds))
        words = [cop1_adds, ins(40, 4, 9, 0xCC)]
        r = origin_at(words, BASE, 0, 1, 4)
        self.assertEqual(r['origin'], 'entry_a0')
        self.assertTrue(r['complete'])

    def test_cop1_mfc1_clobbers_gpr_provenance(self):
        words = [ins(0x11, 0, 4, 3), ins(40, 4, 9, 0xCC)]
        self.assertEqual(origin_at(words, BASE, 0, 1, 4)['origin'], 'unknown')

    def test_cop1_conditional_branch_stays_unsupported(self):
        # COP1 BC1 branch, unlike ordinary FP arithmetic.
        from trace_player_writer_cfg import is_control
        bc1 = ins(0x11, 8, 0, 2)
        self.assertTrue(is_control(bc1))
        result = origin_at([bc1, 0, ins(40, 4, 9, 0xCC)], BASE, 0, 2, 4)
        self.assertFalse(result['complete'])
        self.assertEqual(result['blocker_classes'], {'coprocessor_branch': 1})

    def test_likely_branch_not_taken_skips_delay_store(self):
        # beql r0,r2 (r2=3) skips its delay-slot store.
        words = [ins(9, 0, 2, 3), ins(0x14, 0, 2, 2),
                 ins(40, 4, 9, 0xCC), 0]
        result = origin_at(words, BASE, 0, 2, 4)
        self.assertEqual(result['origin'], 'unreachable')
        self.assertTrue(result['complete'])

    def test_likely_branch_taken_executes_delay_store(self):
        words = [ins(0x14, 0, 0, 2), ins(40, 4, 9, 0xCC), 0]
        result = origin_at(words, BASE, 0, 1, 4)
        self.assertEqual(result['origin'], 'entry_a0')

    def test_unsupported_indirect_jalr_produces_pc_class_metadata(self):
        # jalr ra,t9 ; nop ; action store.
        words = [((25 << 21) | (31 << 11) | 9), 0, ins(40, 4, 9, 0xCC)]
        r = origin_at(words, BASE, 0, 2, 4)
        self.assertEqual(r['origin'], 'unreachable')
        self.assertEqual(r['blocker_classes']['indirect_jalr'], 1)
        self.assertEqual(r['first_blocker_pc_by_class']['indirect_jalr'], '0x80100000')

    def test_full_original_player_overlay_symbols_are_unique_nonoverlapping(self):
        from trace_player_writer_cfg import read_pinned_player_overlay_functions
        data, functions = read_pinned_player_overlay_functions()
        self.assertEqual(len(functions), 906)
        self.assertEqual(data['provenance']['function_count'], 906)
        self.assertEqual(len(data['direct_caller_sites']), 7)

    def test_exact_jal_target_and_a0_argument_from_pinned_function(self):
        from trace_player_writer_cfg import inspect_pinned_caller_a0
        base = 0x80100000
        start = base
        target = base + 0x40
        jal = (3 << 26) | ((target >> 2) & 0x3FFFFFF)
        words = [ins(15, 0, 8, 0x8020), ins(35, 8, 4, 0xC604),
                 jal, 0] + [0] * 20
        source = {'direct_caller_sites': [{'pc': f'0x{base+8:08X}',
                                          'target': f'0x{target:08X}'}]}
        funcs = [{'start': base, 'size': 0x30}]
        row = inspect_pinned_caller_a0(words, base, source, funcs)[0]
        self.assertEqual(row['call_argument_candidate_origin'], 'player_global_load')
        self.assertEqual(row['a0_pre_delay_slot_symbol'], 'player_1_task')
        self.assertFalse(row['live_player_action_owner_verified'])

    def test_wrong_target_jal_is_rejected(self):
        from trace_player_writer_cfg import inspect_pinned_caller_a0
        base, target = 0x80100000, 0x80100040
        words = [(3 << 26) | (((target + 4) >> 2) & 0x3FFFFFF), 0]
        source = {'direct_caller_sites': [{'pc': f'0x{base:08X}',
                                          'target': f'0x{target:08X}'}]}
        with self.assertRaisesRegex(ValueError, 'does not target'):
            inspect_pinned_caller_a0(words, base, source, [{'start': base, 'size': 8}])

    def test_two_level_direct_jal_provenance_finds_player_task_global(self):
        from trace_player_writer_cfg import follow_direct_call_a0_origin
        base = 0x80100000
        words = [0] * 40
        target = lambda offset: (3 << 26) | (((base + offset) >> 2) & 0x3ffffff)
        words[0] = ins(15, 0, 8, 0x8020)
        words[1] = ins(35, 8, 4, 0xC604)
        words[2] = target(0x40)   # caller root -> middle
        words[0x48 // 4] = target(0x80)  # middle -> action
        words[0x80 // 4] = ins(40, 4, 9, 0xCC)
        functions = [{'start': base, 'size': 0x20},
                     {'start': base + 0x40, 'size': 0x20},
                     {'start': base + 0x80, 'size': 0x20}]
        result = follow_direct_call_a0_origin(
            words, base, functions, [f'0x{base+0x80:08X}'])
        found = result[f'0x{base+0x80:08X}']
        self.assertEqual(found['known_global_path_count'], 1)
        self.assertEqual(found['static_global_entry_paths'][0]['global'], 'player_1_task')
        self.assertEqual(found['static_global_entry_paths'][0]['depth'], 2)
        self.assertFalse(found['verified_live_player_action_owner'])

    def test_caller_delay_slot_override_blocks_transitive_global_claim(self):
        from trace_player_writer_cfg import follow_direct_call_a0_origin
        base = 0x80100000
        words = [0] * 24
        words[0] = ins(15, 0, 8, 0x8020)
        words[1] = ins(35, 8, 4, 0xC604)
        words[2] = (3 << 26) | (((base + 0x40) >> 2) & 0x3ffffff)
        words[3] = ins(9, 0, 4, 7)
        functions = [{'start': base, 'size': 0x20},
                     {'start': base + 0x40, 'size': 0x20}]
        result = follow_direct_call_a0_origin(
            words, base, functions, [f'0x{base+0x40:08X}'])
        found = result[f'0x{base+0x40:08X}']
        self.assertEqual(found['known_global_path_count'], 0)
        self.assertIn('delay_slot_overwrites_a0', found['terminal_reasons'])

    def test_indirect_jr_table_hypothesis_reaches_case_but_not_live_proof(self):
        words = [0] * 20
        words[2] = (12 << 21) | 8  # jr t4, without supplied targets stops
        words[8] = ins(40, 4, 9, 0xCC)
        original = origin_at(words, BASE, 0, 8, 4)
        self.assertEqual(original['origin'], 'unreachable')
        possible = origin_at(words, BASE, 0, 8, 4,
                             indirect_jr_targets={BASE + 8: [BASE + 32, BASE + 48]})
        self.assertEqual(possible['origin'], 'incomplete_cfg')
        self.assertEqual(possible['bounded_origin'], 'entry_a0')
        self.assertEqual(possible['blocker_classes']['static_table_target_hypothesis'], 1)

    def test_indirect_jr_does_not_prove_pointer_when_case_clobbers_a0(self):
        words = [0] * 20
        words[2] = (12 << 21) | 8
        words[6] = ins(9, 0, 4, 10)
        words[8] = ins(40, 4, 9, 0xCC)
        result = origin_at(words, BASE, 0, 8, 4,
                           indirect_jr_targets={BASE + 8: [BASE + 24]})
        self.assertEqual(result['origin'], 'incomplete_cfg')
        self.assertEqual(result['bounded_origin'], 'constant')
        self.assertIsNone(result.get('symbol'))


    def test_constant_shift_and_arithmetic_right_shift(self):
        from trace_player_writer_cfg import initial_state, plain
        s = plain(ins(9, 0, 9, 3), initial_state())
        s = plain((9 << 16) | (10 << 11) | (2 << 6), s)
        self.assertEqual(s[10], ('constant', 12))
        s = plain(ins(15, 0, 9, 0x8000), s)
        s = plain((9 << 16) | (10 << 11) | (1 << 6) | 3, s)
        self.assertEqual(s[10], ('constant', 0xC0000000))

    def test_nested_a0_load_to_halfword_is_structural_not_player_identity(self):
        words = [ins(35, 4, 3, 0x5C), ins(0x25, 3, 9, 0x30), 0]
        result = origin_at(words, BASE, 0, 2, 9)
        self.assertEqual(result['origin'], 'entry_a0_lw_lhu_fields')
        self.assertEqual(result['entry_a0_field_offsets'], [0x5C, 0x30])
        self.assertIsNone(result['symbol'])

    def test_overwritten_nested_pointer_cannot_inherit_entry_a0(self):
        words = [ins(35, 4, 3, 0x5C), ins(35, 5, 3, 0), ins(0x25, 3, 9, 0x30), 0]
        result = origin_at(words, BASE, 0, 3, 9)
        self.assertEqual(result['origin'], 'unknown')

    def test_different_branch_source_values_cannot_be_called_constant(self):
        words = [ins(4, 2, 3, 3), 0, ins(9, 0, 9, 1), 0, ins(9, 9, 10, 0), 0]
        result = origin_at(words, BASE, 0, 5, 10)
        self.assertIsNone(result['constant_value'])

    def test_no_entry_hint_no_proof(self):
        site = {'pc': f'0x{BASE:08X}', 'base_register': 'r4',
                'nearby_function_prologue_hint': None}
        self.assertEqual(analyze_cfg([ins(40, 4, 9, 0xCC)], BASE, [site])[site['pc']]['origin'], 'no_entry_hint')


if __name__ == '__main__':
    unittest.main()
