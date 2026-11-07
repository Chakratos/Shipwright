"""Isolated synthetic source-ROM evidence for Yae shared 0x09 banks."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probe_yae_shared_graphics import (
    assess_yae_candidate_bank,compare_yae_banks
)

def synthetic():
    player=bytearray(0x600)
    good=bytearray(0x600)
    invalid=bytes(0x600)
    # 0x07 AnimatedSkeleton header points into five first-generation limbs.
    struct.pack_into(">III",player,0x40,0x00000511,0x07000400,0x07000100)
    for i in range(5):
        struct.pack_into(">Ibb9h",player,0x100+24*i,
                         0x29000020 if i%2==0 else 0x09000020,
                         1 if i<4 else 0,0,
                         128,128,128,0,0,0,0,0,0)
    struct.pack_into(">II",good,0x20,0x06000000,0x09000080)
    struct.pack_into(">II",good,0x28,0xB8000000,0)
    struct.pack_into(">II",good,0x80,(4<<24)|(3<<10)|47,0x09000100)
    struct.pack_into(">II",good,0x88,0xBF000000,0x00000204)
    struct.pack_into(">II",good,0x90,0xB8000000,0)
    for i,(x,y,z) in enumerate(((1,2,3),(4,5,6),(7,8,9))):
        struct.pack_into(">hhhHhhBBBB",good,0x100+16*i,
                         x,y,z,0,0,0,255,120,60,255)
    return bytes(player),bytes(good),invalid

class YaeSourceBankProbeTests(unittest.TestCase):
    def test_decoded_n64_triangles_belong_to_candidate_bank_only(self):
        y07,bank,_=synthetic()
        score=assess_yae_candidate_bank(
            {7:y07,8:bytes(32),9:bank},graphics_source_file=291)
        self.assertGreaterEqual(score["source_07_candidate_skeletons"],1)
        self.assertEqual(score["executed_original_limb_meshes"],1)
        self.assertEqual(score["tagged_0x29_display_list_roots"],1)
        self.assertEqual(score["decoded_original_triangles"],1)
        self.assertFalse(score["actual_runtime_bank_residency_verified"])
    def test_incompatible_bank_does_not_become_a_verified_owner(self):
        y07,bank,bad=synthetic()
        report=compare_yae_banks([(291,bad),(295,bank),(299,bad)],
                                 y07,bytes(32))
        self.assertEqual(report["unique_geometric_best_candidate_file"],295)
        self.assertFalse(report["winner_is_runtime_verified"])
        self.assertFalse(report["safe_to_publish_source_yae_player_rig"])
    def test_tied_valid_banks_are_not_assigned_to_yae(self):
        y07,bank,_=synthetic()
        report=compare_yae_banks([(291,bank),(295,bank)],y07,bytes(32))
        self.assertIsNone(report["unique_geometric_best_candidate_file"])
        self.assertFalse(report["safe_to_publish_source_yae_player_rig"])
    def test_source_bank_presence_checked(self):
        y07,bank,_=synthetic()
        with self.assertRaisesRegex(ValueError,"requires"):
            assess_yae_candidate_bank({7:y07},
                                      graphics_source_file=291)

if __name__=="__main__":
    unittest.main()
