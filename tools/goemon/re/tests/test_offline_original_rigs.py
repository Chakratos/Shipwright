"""Synthetic verification of Goemon source ROM-only animated rig traversal."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from offline_original_rigs import (
    read_skeletal_node, traverse_original_skeleton,
    candidate_animated_skeletons
)

class OfflineOriginalRigTests(unittest.TestCase):
    def fixture(self):
        skeleton_bank=bytearray(0x600)
        gfx_bank=bytearray(0x200)
        first=0x100
        for i in range(5):
            struct.pack_into(">Ibb9h",skeleton_bank, first+24*i,
                             0x09000080 + i*8,
                             1 if i<4 else 0,
                             0,
                             128,128,128, 0,i*32,0, 3,4,5)
        # AnimatedSkeleton.flags: one physical skeleton pointer, valid
        # count hint, original game animation ptr in the same real bank.
        struct.pack_into(">III",skeleton_bank,0x40,
                         (1 << 8)|12,0x07000400,0x07000100)
        return {7:bytes(skeleton_bank),9:bytes(gfx_bank)}

    def test_full_linked_original_skeleton_tree_without_game_capture(self):
        banks=self.fixture()
        result=traverse_original_skeleton(0x07000100,banks)
        self.assertEqual(result["limbs"],5)
        self.assertEqual(result["graphics_limb_count"],5)
        self.assertEqual(result["graphics_segments"],["0x09"])
        self.assertEqual(result["nodes"][0]["child"],1)
        self.assertEqual(result["nodes"][-1]["child"],0)
        report=candidate_animated_skeletons(banks,min_limbs=4)
        self.assertGreaterEqual(report["structurally_valid_candidate_count"],1)
        self.assertTrue(any(
            rec["header_offset"]==0x40 and rec["actual_traversed_limbs"]==5
            for rec in report["first_valid_candidates"]))
        self.assertFalse(report["runtime_player_identity_proven"])
        self.assertFalse(report["animation_sequence_decoded"])

    def test_source_sibling_edges_share_parent(self):
        banks=self.fixture()
        raw=bytearray(banks[7])
        struct.pack_into(">b",raw,0x100+4,1) # first child
        struct.pack_into(">b",raw,0x118+5,1) # second node sibling to third
        # node 0x130 still child of prior in this fixture, so repeated
        # traversal must reject duplicated references.
        with self.assertRaisesRegex(ValueError,"cycle"):
            traverse_original_skeleton(0x07000100,{**banks,7:bytes(raw)})

    def test_random_or_dangling_pointers_fail_closed(self):
        banks=self.fixture()
        with self.assertRaisesRegex(ValueError,"outside"):
            read_skeletal_node(0x06000100,banks)
        with self.assertRaisesRegex(ValueError,"outside"):
            read_skeletal_node(0x09010000,banks)
        broken=bytearray(banks[7])
        struct.pack_into(">I",broken,0x100,0x0B001000)
        with self.assertRaisesRegex(ValueError,"unresolved graphics"):
            traverse_original_skeleton(0x07000100,{**banks,7:bytes(broken)})
        invalid=bytearray(banks[7])
        struct.pack_into(">b",invalid,0x100+4,-128)
        with self.assertRaisesRegex(ValueError,"outside"):
            traverse_original_skeleton(0x07000100,{**banks,7:bytes(invalid)})

    def test_single_limb_not_sufficient_to_claim_original_model(self):
        banks=self.fixture()
        incomplete=bytearray(banks[7])
        struct.pack_into(">b",incomplete,0x100+4,0)
        report=candidate_animated_skeletons({**banks,7:bytes(incomplete)},
                                            min_limbs=4)
        self.assertFalse(any(x["header_offset"]==0x40
                             for x in report["first_valid_candidates"]))

if __name__=="__main__":
    unittest.main()
