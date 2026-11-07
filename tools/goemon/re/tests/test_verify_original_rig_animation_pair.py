"""Synthetic exact GOSKEL01/GOANIM01 source-channel provenance tests."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_original_rig_animation_pair import compare_original_source_packages

def pair(slot=3,gfx=0x29000020,flag=0x80000111):
    skeleton=bytearray(struct.pack("<8sIII",b"GOSKEL01",slot,1,1))
    skeleton.extend(struct.pack("<II",0x09000020,1))
    skeleton.extend(bytes(48))
    skeleton.extend(struct.pack("<III",0x07000140,flag,2))
    parent=(0x0F000120,-1,(-20224,)*3+(-20480,)*6)
    child=(gfx,0,(256,)*3+(0,)*6)
    for g,p,s in (parent,child):
        skeleton.extend(struct.pack("<Ih9h",g,p,*s))
    animation=bytearray(struct.pack("<8sII",b"GOANIM01",slot,1))
    animation.extend(struct.pack("<IIIIII",0x07000140,flag,0x07000000,
                                 0x07000100,16,2))
    animation.extend(bytes(range(16)))
    for ptr,(g,p,s) in ((0x07000100,parent),(0x07000118,child)):
        animation.extend(struct.pack("<IIh9h",ptr,g,p,*s))
    return bytes(skeleton),bytes(animation)

class SourceRigAnimationPairTests(unittest.TestCase):
    def test_exact_yae_raw_pointer_channels_and_masked_geometry(self):
        rig,animation=pair()
        report=compare_original_source_packages(rig,animation)
        self.assertEqual(report["character_slot"],3)
        self.assertEqual(report["matched_exact_skeleton_descriptors"],1)
        self.assertEqual(report["distinct_matched_meshes"],1)
        self.assertEqual(report["unknown_tagged_source_graphics_records"],{"0x0F":1})
        self.assertTrue(report["byte_identical_raw_limb_channels"])
        self.assertFalse(report["real_character_animation_playback_ready"] if "real_character_animation_playback_ready" in report else report["actual_source_matrix_codec_decoded"])
    def test_reject_mismatched_character_or_channel_or_flags(self):
        rig,animation=pair()
        bad=bytearray(animation);bad[8]=0
        with self.assertRaisesRegex(ValueError,"character mismatch"):
            compare_original_source_packages(rig,bytes(bad))
        bad=bytearray(animation);bad[16+4]=0
        with self.assertRaisesRegex(ValueError,"channel mismatch|header sets differ"):
            compare_original_source_packages(rig,bytes(bad))
        bad=bytearray(animation);bad[-2]^=1
        with self.assertRaisesRegex(ValueError,"channel mismatch"):
            compare_original_source_packages(rig,bytes(bad))
        bad=bytearray(rig);bad[20]=0
        with self.assertRaisesRegex(ValueError,"source graphics mesh"):
            compare_original_source_packages(bytes(bad),animation)
    def test_reject_source_animation_without_any_matching_original_gfx(self):
        rig,animation=pair(gfx=0x29000120)
        with self.assertRaisesRegex(ValueError,"no matching"):
            compare_original_source_packages(rig,animation)

if __name__=="__main__":
    unittest.main()
