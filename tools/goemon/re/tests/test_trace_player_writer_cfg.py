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

    def test_unsupported_branch_likely_fails_closed(self):
        words = [ins(0x14, 2, 3, 1), 0, ins(40, 4, 9, 0xCC)]
        self.assertFalse(origin_at(words, BASE, 0, 2, 4)['complete'])

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

    def test_no_entry_hint_no_proof(self):
        site = {'pc': f'0x{BASE:08X}', 'base_register': 'r4',
                'nearby_function_prologue_hint': None}
        self.assertEqual(analyze_cfg([ins(40, 4, 9, 0xCC)], BASE, [site])[site['pc']]['origin'], 'no_entry_hint')


if __name__ == '__main__':
    unittest.main()
