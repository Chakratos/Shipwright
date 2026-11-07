"""Source-only selection of observable original MIPS bodypart motion."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from select_original_visible_mips_descriptors import (
    rank_visible_original_descriptors
)
from test_verify_original_rig_animation_pair import pair

class OriginalVisibleMotionSelectionTests(unittest.TestCase):
    def test_only_time_sensitive_source_bones_with_real_meshes_preferred(self):
        rig,_=pair(slot=3)
        records=[
            {"source_header":"0x000140","selected_limb":"0x07000118",
             "valid":True,"changed_at_1":True},
            {"source_header":"0x000140","selected_limb":"0x07000100",
             "valid":True,"changed_at_1":False}
        ]
        ranked=rank_visible_original_descriptors(rig,records,character="Yae")
        self.assertEqual(len(ranked),1)
        self.assertEqual(ranked[0]["source_header"],"0x07000140")
        self.assertEqual(ranked[0]["source_drawable_bone_count"],1)
        self.assertTrue(ranked[0]["contains_original_gfx_data"])
        self.assertFalse(ranked[0]["original_action_identity_verified"])
    def test_source_rig_mismatch_fails(self):
        rig,_=pair(slot=3)
        with self.assertRaisesRegex(ValueError,"mismatch"):
            rank_visible_original_descriptors(rig,[],character="Goemon")
    def test_missing_original_source_header_never_fabricated(self):
        rig,_=pair(slot=3)
        with self.assertRaisesRegex(ValueError,"missing"):
            rank_visible_original_descriptors(rig,[{
                "source_header":"0x123456","selected_limb":"0x07000118",
                "valid":True,"changed_at_1":True}],character="Yae")

if __name__=="__main__":
    unittest.main()
