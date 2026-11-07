"""Math control cases for original source CPU matrix composition identification."""
from pathlib import Path
import math
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probe_original_mips_composition import (
    row_major_multiply,normalized_matrix_error,find_child_with_original_parent
)

class SourceMipsCompositionTests(unittest.TestCase):
    def test_parent_child_multiplication_order_distinguishable(self):
        parent=[2,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
        child=[1,0,0,10,0,1,0,0,0,0,1,0,0,0,0,1]
        ab=row_major_multiply(parent,child)
        ba=row_major_multiply(child,parent)
        self.assertEqual(ab[3],20)
        self.assertEqual(ba[3],10)
        self.assertEqual(normalized_matrix_error(ab,ab),0.0)
        self.assertGreater(normalized_matrix_error(ab,ba),0.1)
    def test_only_source_tree_nodes_with_numeric_channels_selected(self):
        zero=(0,0,0)
        nodes=[
            {"ptr":0x07000100,"parent":None,"scale":zero,"rotation":zero,"translation":zero},
            {"ptr":0x07000118,"parent":0x07000100,
             "scale":(1,0,0),"rotation":zero,"translation":zero},
        ]
        self.assertEqual(find_child_with_original_parent(nodes)["ptr"],0x07000118)
        nodes[1]["parent"]=0x07000040
        with self.assertRaisesRegex(ValueError,"no original source"):
            find_child_with_original_parent(nodes)
    def test_reject_nan_original_matrix_without_inventing_values(self):
        with self.assertRaisesRegex(ValueError,"nonfinite"):
            normalized_matrix_error([0]*15+[math.nan],[0]*16)

if __name__=="__main__":
    unittest.main()
