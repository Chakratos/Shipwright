"""CPU-parent stack controls have known values, no user ROM included."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probe_original_mips_predecessor import (
    selected_parent_child_pairs,output_digest,IDENTITY,SEED,HEADERS
)

class SourcePredecessorTests(unittest.TestCase):
    def test_only_renderable_nodes_with_actual_parent(self):
        nodes=[
            {"ptr":0x07000020,"parent":None,"gfx":0},
            {"ptr":0x07000038,"parent":0x07000020,"gfx":0x09000100},
            {"ptr":0x07000050,"parent":0x07000020,"gfx":0},
            {"ptr":0x07000068,"parent":0x07000050,"gfx":0x29000120},
        ]
        self.assertEqual(selected_parent_child_pairs(nodes),[
            (0x07000020,0x07000038),
            (0x07000050,0x07000068)])
    def test_hash_gate_refuses_unverified_runtime_sample(self):
        ok={"returned":True,"separate_original_matrix_stack_probe":True,
            "original_mtxf_stack_finite_elements":16,
            "original_mtxf_stack_sha256_prefix":"abc"}
        self.assertEqual(output_digest(ok),"abc")
        self.assertIsNone(output_digest({**ok,"returned":False}))
        self.assertIsNone(output_digest({**ok,"original_mtxf_stack_finite_elements":15}))
    def test_noncommutative_parent_seed_not_identity(self):
        self.assertEqual(len(IDENTITY),16)
        self.assertEqual(len(SEED),16)
        self.assertNotEqual(SEED,IDENTITY)
        self.assertEqual(len(HEADERS),4)

if __name__=="__main__":
    unittest.main()
