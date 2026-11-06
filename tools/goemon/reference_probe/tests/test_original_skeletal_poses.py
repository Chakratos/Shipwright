"""Original animation trace parser and exact ROM mesh binding tests.

Synthetic text only. No original game bytes or invented player frames.
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from original_skeletal_poses import (
    parse_bone, parse_matrix, read_original_animation_log,
    bind_original_mesh_runs,
)


def bone(frame=12, action=15, bone_ptr="80123480", dl="070024A8"):
    return (f"GOEMON_ANIM_BONE,{frame},0,{action},{bone_ptr},{dl},"
            "1,0,100,100,100,10,20,30,40,50,60")


def matrix(frame=12, action=15, bone_ptr="80123480", progress=9.5):
    fields = "1,0,0,0,0,1,0,0,0,0,1,0,3,2,1,1"
    return (f"GOEMON_ANIM_MATRIX,{frame},0,{action},{bone_ptr},"
            f"{progress},{fields}")


def root(frame=12):
    slots = ",".join(f"{288+i},80100000" for i in range(6))
    return (f"GOEMON_ANIM_ROOT,{frame},0,15,80123400,68000001,9.5,{slots}")


class RealPoseParserTests(unittest.TestCase):
    def test_original_matrix_pairs_and_overlay_root(self):
        source = [
            "GOEMON_ANIM_BEGIN,1,12,source=func_800192D0_19ED0",
            root(),
            bone(),
            matrix(),
            bone(13),
            matrix(13, progress=10.5),
            "GOEMON_ANIM_END,14,limit",
        ]
        result = read_original_animation_log(source)
        self.assertEqual(result["original_game_frames"], 2)
        self.assertEqual(result["total_matched_original_matrices"], 2)
        self.assertEqual(result["unmatched_original_bones"], 0)
        self.assertEqual(result["frames"][0]["character_name"], "Goemon")
        self.assertEqual(
            result["frames"][0]["limbs"][0]["matrix_global_D_801684B0"],
            [1.0,0.0,0.0,0.0,0.0,1.0,0.0,0.0,
             0.0,0.0,1.0,0.0,3.0,2.0,1.0,1.0]
        )
        self.assertEqual(
            result["render_root_mappings"][0]["overlays"][0]["file_id"],288)
        self.assertTrue(result["matrices_are_original_game_values"])
        self.assertFalse(result["animation_clips_retargeted_to_Ship"])

    def test_exact_n64_display_list_binding_preserves_original_run_identity(self):
        doc = read_original_animation_log([bone(),matrix()])
        source = {0: {"per_display_list_objects": [
            {"display_list_offset": 0x24A8,
             "display_list_end": 0x26A0,
             "local_obj_file": "gfx_000_at_0x0024a8.obj"}
        ]}}
        matched = bind_original_mesh_runs(doc,source)
        self.assertEqual(
            matched["source_rom_graphics_binding"]["exact_gfx_matches"],1)
        self.assertEqual(
            matched["frames"][0]["limbs"][0]["source_obj"],
            "gfx_000_at_0x0024a8.obj")

    def test_nearby_but_not_exact_source_gfx_is_not_falsely_confirmed(self):
        doc = read_original_animation_log([bone(dl="07002490"),matrix()])
        source = {0: {"per_display_list_objects": [
            {"display_list_offset": 0x24A8,
             "display_list_end": 0x26A0,
             "local_obj_file": "gfx_000_at_0x0024a8.obj"}
        ]}}
        bind_original_mesh_runs(doc,source)
        limb=doc["frames"][0]["limbs"][0]
        self.assertEqual(limb["source_mesh_status"], "nearby_header_not_verified")
        self.assertNotIn("source_obj",limb)
        self.assertEqual(
            doc["source_rom_graphics_binding"]["nearby_unverified"],1)

    def test_rejects_corrupt_animation_matrix(self):
        bad=matrix().replace(",3,2,1,1",",nan,2,1,1")
        with self.assertRaisesRegex(ValueError,"invalid original 4x4"):
            read_original_animation_log([bone(),bad])
        bad2=bone().replace(",1,0,100",",200,0,100")
        with self.assertRaisesRegex(ValueError,"hierarchy"):
            parse_bone(bad2[len("GOEMON_ANIM_BONE,"):])
        with self.assertRaisesRegex(ValueError,"21"):
            parse_matrix("1,2,3,8,5,10")

    def test_matrices_without_matching_bones_are_rejected(self):
        with self.assertRaisesRegex(ValueError,"no paired original"):
            read_original_animation_log([matrix()])
        with self.assertRaisesRegex(ValueError,"no paired original"):
            read_original_animation_log([bone()])

    def test_duplicate_limb_does_not_invent_second_animation_keyframe(self):
        with self.assertRaisesRegex(ValueError,"more than once"):
            read_original_animation_log([bone(),matrix(),bone(),matrix()])

    def test_original_action_transitions_are_separate_frames(self):
        doc=read_original_animation_log([bone(20,15),matrix(20,15),
                                          bone(21,23),matrix(21,23)])
        self.assertEqual([x["action_id"] for x in doc["frames"]],[15,23])
        self.assertEqual(doc["original_game_frames"],2)

if __name__ == "__main__":
    unittest.main()
