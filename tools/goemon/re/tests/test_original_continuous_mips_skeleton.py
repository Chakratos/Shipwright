"""Pure source graph stack-depth tests; no commercial ROM required."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_continuous_mips_skeleton import (
    build_source_stack_plan,summarize_character_rows,PROGRESS
)

class OriginalContinuousSourceStackTests(unittest.TestCase):
    def test_real_source_preorder_depth_siblings_restore_parent_stack(self):
        nodes=[
            {"ptr":0x07000100,"parent":None,"gfx":0},
            {"ptr":0x07000118,"parent":0x07000100,"gfx":0x09000020},
            {"ptr":0x07000130,"parent":0x07000118,"gfx":0x09000040},
            {"ptr":0x07000148,"parent":0x07000100,"gfx":0x29000020},
        ]
        self.assertEqual([x["depth"] for x in build_source_stack_plan(nodes)],
                         [0,1,2,1])
    def test_source_push_slot_output_tracks_original_per_bone_stack_cursor(self):
        nodes=[
            {"ptr":0x07000100,"parent":None,"gfx":0},
            {"ptr":0x07000118,"parent":0x07000100,"gfx":0x09000010},
            {"ptr":0x07000130,"parent":0x07000100,"gfx":0x09000020}
        ]
        self.assertEqual([n["depth"] for n in build_source_stack_plan(nodes)],
                         [0,1,1])

    def test_reject_cross_branch_unseen_parent(self):
        with self.assertRaisesRegex(ValueError,"unresolved"):
            build_source_stack_plan([
                {"ptr":0x07000118,"parent":0x07000100,"gfx":0}
            ])
    def test_changed_parent_and_drawable_child_counts_separate(self):
        nodes=[
            {"ptr":0x07000100,"gfx":0,"source_original_mips_matrix_digest":"a"},
            {"ptr":0x07000118,"gfx":0x29000020,"source_original_mips_matrix_digest":"b"},
        ]
        samples=[]
        for i in range(3):
            items=[dict(n) for n in nodes]
            items[0]["source_original_mips_matrix_digest"]="a" if i==0 else "z"
            items[1]["source_original_mips_matrix_digest"]="b" if i==0 else "c"
            samples.append({
                "character":"Yae","source_mips_sequence_completed":True,
                "results":items,"first_blocker":None
            })
        info=summarize_character_rows(samples,{0x09000020})
        self.assertEqual(info["source_mips_matrix_nodes_changed"],2)
        self.assertEqual(info["original_mesh_drawable_nodes_with_changed_matrix"],1)
        self.assertEqual(PROGRESS,(0.0,1.0,4.0))

if __name__=="__main__":
    unittest.main()
