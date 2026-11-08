"""Source-free falsifiable static MIPS pointer origin regression fixtures."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trace_player_writer_provenance import (analyze_words, trace_register,
                                            control_transfer)


def ins(op, rs, rt, imm):
    return (op << 26) | (rs << 21) | (rt << 16) | (imm & 0xFFFF)


def addu(dst, src):
    return (src << 21) | (dst << 11) | 0x21


class ProvenanceTests(unittest.TestCase):
    def test_signed_low_global_task_load_through_saved_alias(self):
        # lui r8,0x8020; lw r4,-0x39FC(r8) -> D_801FC604; move r16,r4
        words = [ins(15, 0, 8, 0x8020), ins(35, 8, 4, 0xC604),
                 addu(16, 4), ins(40, 16, 9, 0xCC)]
        result = analyze_words(words, 0x80100000)
        hit = result['by_kind']['action_id_offset']['sites'][0]
        self.assertEqual(hit['known_player_global'], 'player_1_task')
        self.assertEqual(hit['base_origin'], 'known_player_pointer_global_load')
        self.assertFalse(hit['live_player_writer_verified'])
        self.assertFalse(result['execution_or_active_animation_verified'])

    def test_graphics_model_global_and_stack_exclusion(self):
        words = [ins(15, 0, 8, 0x8020), ins(35, 8, 4, 0xC60C),
                 ins(43, 4, 2, 0x2C), ins(43, 29, 2, 0x2C)]
        r = analyze_words(words, 0x80100000)['by_kind']['graphics_1_offset']
        self.assertEqual(r['non_stack_candidate_count'], 1)
        self.assertEqual(r['known_global_pointer_load_count'], 1)
        self.assertEqual(r['sites'][0]['known_player_global'], 'player_1_model_object')

    def test_control_flow_barrier_does_not_invent_pointer(self):
        words = [ins(15, 0, 8, 0x8020), ins(35, 8, 4, 0xC604),
                 0x0C000020, 0, ins(40, 4, 9, 0xCC)]  # jal + delay slot
        hit = analyze_words(words, 0x80100000)['by_kind']['action_id_offset']['sites'][0]
        self.assertIsNone(hit['known_player_global'])
        self.assertEqual(hit['base_origin'], 'control_flow_boundary')

    def test_overwrite_destroys_origin(self):
        words = [ins(15, 0, 8, 0x8020), ins(35, 8, 4, 0xC604),
                 ins(35, 6, 4, 8), ins(40, 4, 9, 0xCC)]
        self.assertEqual(trace_register(words, 3, 4), ('unresolved', None))

    def test_nearby_call_is_hint_not_ownership(self):
        base = 0x80100000
        start = base + 4 * 2
        jal = (3 << 26) | ((start >> 2) & 0x3FFFFFF)
        words = [jal, 0, ins(9, 29, 29, -32),
                 ins(40, 16, 9, 0xCC)]
        hit = analyze_words(words, base)['by_kind']['action_id_offset']['sites'][0]
        self.assertEqual(hit['nearby_function_prologue_hint'], '0x80100008')
        self.assertEqual(hit['direct_jal_to_prologue_hint_count'], 1)
        self.assertFalse(hit['prologue_is_verified_function_boundary'])
        self.assertIsNone(hit['known_player_global'])

    def test_literal_address_not_loaded_pointer(self):
        words = [ins(15, 0, 4, 0x8020), ins(9, 4, 4, 0xC604),
                 ins(40, 4, 9, 0xCC)]
        hit = analyze_words(words, 0x80100000)['by_kind']['action_id_offset']['sites'][0]
        self.assertEqual(hit['base_origin'], 'constant')
        self.assertIsNone(hit['known_player_global'])

    def test_direct_caller_argument_from_known_global_is_only_hint(self):
        base = 0x80100000
        start = base + 4 * 7
        jal = (3 << 26) | ((start >> 2) & 0x3FFFFFF)
        words = [ins(15, 0, 8, 0x8020), ins(35, 8, 4, 0xC604),
                 jal, 0, 0, 0, 0, ins(9, 29, 29, -32),
                 ins(40, 4, 9, 0xCC)]
        hit = analyze_words(words, base)['by_kind']['action_id_offset']['sites'][0]
        self.assertEqual(hit['caller_a0_known_player_global_hint_count'], 1)
        self.assertTrue(hit['direct_jal_caller_a0_hints'][0]['player_argument_candidate'])
        self.assertFalse(hit['direct_jal_caller_a0_hints'][0]['callee_identity_verified'])
        self.assertFalse(hit['live_player_writer_verified'])

    def test_jal_delay_slot_clobber_invalidates_caller_hint(self):
        base = 0x80100000
        start = base + 4 * 7
        jal = (3 << 26) | ((start >> 2) & 0x3FFFFFF)
        words = [ins(15, 0, 8, 0x8020), ins(35, 8, 4, 0xC604),
                 jal, ins(9, 5, 4, 8), 0, 0, 0,
                 ins(9, 29, 29, -32), ins(40, 4, 9, 0xCC)]
        hit = analyze_words(words, base)['by_kind']['action_id_offset']['sites'][0]
        self.assertEqual(hit['caller_a0_known_player_global_hint_count'], 0)
        self.assertTrue(hit['direct_jal_caller_a0_hints'][0]['delay_slot_may_override_a0'])

    def test_branch_and_jump_recognized(self):
        self.assertTrue(control_transfer(0x0C000020))
        self.assertTrue(control_transfer(ins(4, 4, 0, 12)))
        self.assertTrue(control_transfer(0x03E00008))
        self.assertFalse(control_transfer(ins(35, 8, 4, 0xC604)))


if __name__ == '__main__':
    unittest.main()
