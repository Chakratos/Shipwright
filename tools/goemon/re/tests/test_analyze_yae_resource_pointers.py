"""Source 0x07 Skeleton classification with no guessed shared graphics bank."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyze_yae_resource_pointers import (
    characterize_yae_bank07,traverse_yae_bank07_unresolved_skeletons,
    build_yae_source_animation_catalog
)

def fixture():
    bank=bytearray(0x500)
    struct.pack_into(">III",bank,0x40,0x00000511,0x07000300,0x07000100)
    for i in range(5):
        struct.pack_into(">Ibb9h",bank,0x100+24*i,
                         0x09000120 if i%2==0 else 0x08000008,
                         1 if i<4 else 0,0,
                         128,128,128,0,0,0,1,2,3)
    return bank

class YaeSource07PointerTests(unittest.TestCase):
    def test_uncertain_bank_still_reports_exact_encoded_segments(self):
        bank=fixture()
        details=characterize_yae_bank07(bytes(bank))
        self.assertGreaterEqual(details["structurally_traversable_headers"],1)
        self.assertGreaterEqual(details["original_limb_graphics_pointer_segments"].get("0x09",0),3)
        self.assertGreaterEqual(details["original_limb_graphics_pointer_segments"].get("0x08",0),2)
        self.assertFalse(details["gameplay_action_mapping_verified"])
    def test_bad_child_offset_rejected_without_gfx_verification(self):
        bank=fixture()
        struct.pack_into(">b",bank,0x100+4,-128)
        with self.assertRaisesRegex(ValueError,"unresolvable"):
            traverse_yae_bank07_unresolved_skeletons(bytes(bank),0x07000100)
    def test_cycle_rejected_without_bank_selection(self):
        bank=fixture()
        struct.pack_into(">b",bank,0x100+24*4+4,-1)
        with self.assertRaisesRegex(ValueError,"cyclic"):
            traverse_yae_bank07_unresolved_skeletons(bytes(bank),0x07000100)
    def test_yae_encoded_animation_fields_preserved_and_not_keyframes(self):
        bank=fixture()
        struct.pack_into(">III",bank,0x40,0x00000511,0x07000080,0x07000100)
        struct.pack_into(">I",bank,0x100,0x29000120)
        src=build_yae_source_animation_catalog(bytes(bank))
        self.assertEqual(src["character"],"Yae")
        self.assertEqual(src["original_animation_frames_recovered"],0)
        self.assertFalse(src["actual_gameplay_action_ids_verified"])
        first=src["original_source_poses"][0]
        self.assertEqual(first["limbs"][0]["gfx"],0x29000120)
        self.assertEqual(first["limbs"][1]["parent"],0x07000100)
        self.assertEqual(first["original_animation_pointer"],"0x07000080")

    def test_truncated_source_rejected(self):
        with self.assertRaisesRegex(ValueError,"truncated"):
            characterize_yae_bank07(bytes(8))

if __name__=="__main__":
    unittest.main()
