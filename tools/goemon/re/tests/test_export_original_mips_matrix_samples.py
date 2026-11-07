"""Synthetic validation of per-limb matrix provenance without source assets."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from export_original_mips_matrix_samples import (
    classify_progress_changes,validate_matrix_result
)

class SourceMipsMatrixSamplesTests(unittest.TestCase):
    def test_two_progress_values_per_original_limb_are_compared(self):
        a=[0]*16
        b=[0]*16
        b[8]=0x3f800000
        items=[
            {"samples":[{"matrix_ieee754_u32":a},{"matrix_ieee754_u32":b}]},
            {"samples":[{"matrix_ieee754_u32":a},{"matrix_ieee754_u32":a}]},
            {"samples":[{"blocker":"unresolved"},{"matrix_ieee754_u32":b}]},
        ]
        result=classify_progress_changes(items)
        self.assertEqual(result["source_mips_matrix_pairs_changing"],1)
        self.assertEqual(result["source_mips_matrix_pairs_static"],1)
        self.assertEqual(result["source_mips_matrix_pairs_blocked"],1)
        self.assertTrue(result["all_pairs_examined"])
    def test_bad_matrix_or_unreturned_original_code_rejected(self):
        valid={"returned":True,"matrix_finite_elements":16,
               "private_matrix_u32":[0]*16}
        self.assertEqual(len(validate_matrix_result(valid)),16)
        for broken in (
            {**valid,"returned":False},
            {**valid,"matrix_finite_elements":15},
            {**valid,"private_matrix_u32":[0]*15},
            {**valid,"private_matrix_u32":[-1]*16}
        ):
            with self.assertRaisesRegex(ValueError,"source MIPS|matrix"):
                validate_matrix_result(broken)
    def test_missing_original_progress_samples_rejected(self):
        with self.assertRaisesRegex(ValueError,"count"):
            classify_progress_changes([{"samples":[{"matrix_ieee754_u32":[0]*16}]}])

if __name__=="__main__":
    unittest.main()
