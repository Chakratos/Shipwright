"""Original compressed Skeleton channel controls must not be treated as angles."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyze_original_animation_channels import (
    analyze_raw_original_animation_descriptors,
    summarize_channel_anomalies
)

def pose():
    node={
        "ptr":0x07000100,"parent":None,"gfx":0,
        "scale":(-20224,-20224,-20224),
        "rotation":(-20480,-20480,-20480),
        "translation":(-20480,-20480,-20480)
    }
    body={
        "ptr":0x07000118,"parent":0x07000100,
        "gfx":0x09000020,
        "scale":(-20224,-20224,-20224),
        "rotation":(80,103,126),
        "translation":(149,172,195)
    }
    return {
        "format":"ng5e-original-rom-skeletal-poses-v1",
        "character":"Goemon",
        "original_source_poses":[
            {"candidate_number":0,
             "source_header_segment":"0x07",
             "source_header_offset":0x140,
             "original_skeleton_root":"0x07000100",
             "original_animation_pointer":"0x07000000",
             "original_animated_skeleton_flags":"0x80000111",
             "limbs":[node,body]}
        ]
    }

class OriginalAnimationChannelTests(unittest.TestCase):
    def test_tags_are_encoded_control_descriptors_not_literal_scale(self):
        r=analyze_raw_original_animation_descriptors(pose(),bytes(0x300))
        self.assertEqual(r["original_animation_descriptors"],1)
        self.assertEqual(r["stats"]["0xB100_markers"],6)
        self.assertFalse(r["literal_scale_rotation_claim_valid"])
        self.assertEqual(r["stats"]["0xB000_markers"],6)
        self.assertEqual(r["stats"]["numeric_channel_references"],6)
        self.assertEqual(r["stats"]["references_inside_candidate_payload"],6)
        d=r["first_descriptors"][0]
        self.assertEqual(d["candidate_animation_payload_length"],256)
        self.assertEqual(d["most_common_neighboring_offset_gaps"][0][0],23)
        self.assertFalse(r["literal_scale_rotation_claim_valid"])
        s=summarize_channel_anomalies(r)
        self.assertEqual(s["fraction_inside"],1.0)
        self.assertFalse(s["original_clip_decoder_complete"])

    def test_outside_animation_payload_classified_not_fake_keyframe(self):
        p=pose()
        p["original_source_poses"][0]["limbs"][1]["rotation"]=(80,300,126)
        r=analyze_raw_original_animation_descriptors(p,bytes(0x400))
        self.assertEqual(r["stats"]["numeric_channel_references"],6)
        self.assertEqual(r["stats"]["references_inside_candidate_payload"],5)

    def test_not_an_original_rom_catalog_rejected(self):
        with self.assertRaisesRegex(ValueError,"not original"):
            analyze_raw_original_animation_descriptors({"format":"fake"},bytes(0x300))

    def test_invalid_skeleton_crossing_animation_header_not_promoted(self):
        p=pose()
        p["original_source_poses"][0]["limbs"][0]["ptr"]=0x07000160
        r=analyze_raw_original_animation_descriptors(p,bytes(0x300))
        self.assertEqual(r["original_animation_descriptors"],0)
        self.assertEqual(r["stats"]["invalid_animation_or_skeleton_region"],1)

if __name__=="__main__":
    unittest.main()
