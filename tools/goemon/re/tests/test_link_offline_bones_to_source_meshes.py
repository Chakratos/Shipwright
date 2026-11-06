"""Synthetic tests: authentic N64 pointer binding, no guessed limb ownership."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from link_offline_bones_to_source_meshes import match_pose_gfx_to_n64_mesh_runs


class OriginalOfflineBoneGfxBindingTests(unittest.TestCase):
    def fixture(self):
        poses={
            "format":"ng5e-original-rom-skeletal-poses-v1",
            "character":"Goemon",
            "structurally_valid_poses":2,
            "original_source_poses":[
                {"limbs":[
                    {"gfx":0},
                    {"gfx":0x09000040},
                    {"gfx":0x09000070},
                    {"gfx":0x09000150},
                    {"gfx":0x08000010},
                ]},
                {"limbs":[{"gfx":0x09000040}]}
            ]
        }
        meshes={"per_display_list_objects":[
            {"display_list_offset":0x40,"local_obj_file":"exact.obj"},
            {"display_list_offset":0xA0,"local_obj_file":"header.obj"},
        ]}
        return poses,meshes

    def test_recover_original_limb_graphics_pointers(self):
        poses,meshes=self.fixture()
        result=match_pose_gfx_to_n64_mesh_runs(poses,meshes)
        self.assertEqual(result["source_poses"],2)
        self.assertEqual(result["source_mesh_runs"],2)
        self.assertEqual(result["total_bone_references"],6)
        self.assertEqual(result["distinct_09_gfx_pointers"],3)
        self.assertEqual(result["matched_exact_refs"],2)
        self.assertEqual(result["matched_nearby_unverified"],1)
        self.assertEqual(result["null_refs"],1)
        self.assertEqual(result["unresolved_refs"],2)
        byptr={x["source_gfx"]:x for x in result["matches"]}
        self.assertTrue(byptr["0x09000040"]["verified"])
        self.assertEqual(byptr["0x09000070"]["relation"],"possible_display_list_header")
        self.assertFalse(byptr["0x09000070"]["verified"])
        self.assertEqual(byptr["0x09000150"]["relation"],"unresolved_source_graphics_pointer")
        self.assertFalse(result["automated_limb_to_mesh_bone_animation_ready"])

    def test_does_not_lie_about_nearby_source_list(self):
        poses,meshes=self.fixture()
        result=match_pose_gfx_to_n64_mesh_runs(poses,meshes,
                                                max_header_bytes=16)
        self.assertEqual(result["matched_nearby_unverified"],0)
        self.assertEqual(result["unresolved_refs"],3)

    def test_rejects_duplicate_gfx_runs_and_wrong_catalog(self):
        poses,meshes=self.fixture()
        meshes["per_display_list_objects"].append(
            {"display_list_offset":0x40,"local_obj_file":"other.obj"})
        with self.assertRaisesRegex(ValueError,"duplicate"):
            match_pose_gfx_to_n64_mesh_runs(poses,meshes)
        with self.assertRaisesRegex(ValueError,"source-verified"):
            match_pose_gfx_to_n64_mesh_runs({"format":"unknown"},meshes)

if __name__ == "__main__":
    unittest.main()
