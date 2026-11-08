"""Synthetic original-runtime player animation owner and matrix-stack samples."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from animation_owner_trace import analyze_live_owner_events,read_capture_event

class LiveOriginalPlayerAnimationOwnerTests(unittest.TestCase):
    def test_owner_and_engine_global_pointer_match_through_original_action(self):
        lines=[
            "runtime: GOEMON_ANIM_OWNER,100,0,23,801fc60c,67000100,"
            "80400040,80000111,07002000,80402000,07001000",
            "GOEMON_ANIM_ACTIVE,100,0,23,801fc60c,80402000,80510000,3.0",
            "GOEMON_ANIM_MATRIX_CURSOR,100,0,23,80510220,"
            "80510000,80510080,128",
        ]
        report=analyze_live_owner_events(lines,log_sha256="synthetic")
        self.assertEqual(report["owner_events"],1)
        self.assertEqual(report["matched_resolved_owner_to_engine_animation_pointer"],1)
        self.assertEqual(report["matrix_stack_push_events"],1)
        self.assertTrue(report["verified_live_original_animation_pointer"])
        self.assertFalse(report["verified_numerically_moving_original_bone_matrix"])
        action=report["characters_actions"][0]
        self.assertEqual(action["source_action_id"],23)
        self.assertEqual(action["original_matrix_push_bytes"],{128:1})
        self.assertEqual(action["source_animation_progress_range"],[3.0,3.0])
    def test_pointer_mismatch_does_not_claim_live_source_owner(self):
        lines=[
            "GOEMON_ANIM_OWNER,15,3,0,801fc60c,67000100,"
            "80400040,80000111,07002000,80402000,07001000",
            "GOEMON_ANIM_ACTIVE,15,3,0,801fc60c,80402040,80510000,1.0"
        ]
        report=analyze_live_owner_events(lines)
        self.assertEqual(report["mismatched_engine_animation_pointers"],1)
        self.assertFalse(report["verified_live_original_animation_pointer"])
    def test_null_player_graphics_and_bad_push_detected(self):
        with self.assertRaisesRegex(ValueError,"active original"):
            analyze_live_owner_events([
                "GOEMON_ANIM_OWNER,2,0,0,801fc60c,00000000,"
                "80400040,80000111,07002000,80402000,07001000"
            ])
        with self.assertRaisesRegex(ValueError,"matrix-stack"):
            analyze_live_owner_events([
                "GOEMON_ANIM_MATRIX_CURSOR,1,0,0,80510000,"
                "80510000,80510040,128"
            ])
    def test_unknown_lines_dont_count(self):
        self.assertIsNone(read_capture_event("GOEMON_REF,1,0"))
        self.assertEqual(analyze_live_owner_events([])["owner_events"],0)

if __name__=="__main__":
    unittest.main()
