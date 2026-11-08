"""Validate strict source-MIPS descriptor time sweep without ROM fixtures."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sweep_original_mips_descriptors import (
    PROGRESS,select_numeric_limb,classify_descriptor_samples
)

def example(code):
    return {
        "returned":True,"separate_original_matrix_stack_probe":True,
        "original_mtxf_stack_finite_elements":16,
        "original_mtxf_stack_sha256_prefix":code,
        "original_mtxf_numeric_digest":code
    }

class MipsSourceDescriptorTimeSweepTests(unittest.TestCase):
    def test_identifies_genuine_output_change_only_not_alias_artifact(self):
        change=classify_descriptor_samples([
            example("1234"),example("1234"),example("5678")])
        self.assertTrue(change["valid"])
        self.assertFalse(change["changed_at_1"])
        self.assertTrue(change["changed_at_4"])
        self.assertTrue(change["changed_any"])
        blocked=example("5678")
        blocked["separate_original_matrix_stack_probe"]=False
        self.assertFalse(classify_descriptor_samples([
            example("1234"),blocked,example("5678")])["valid"])
    def test_numeric_limb_selected_from_original_channels(self):
        node=lambda ptr,first:{
            "ptr":ptr,"scale":(first,0,0),
            "rotation":(0,0,0),"translation":(0,0,0)}
        chosen,count=select_numeric_limb({
            "limbs":[node(0x07000100,0),node(0x07000118,1)]
        })
        self.assertEqual(chosen["ptr"],0x07000118)
        self.assertEqual(count,1)
    def test_requires_all_three_progress_samples(self):
        with self.assertRaisesRegex(ValueError,"three"):
            classify_descriptor_samples([example("a"),example("b")])
        self.assertEqual(PROGRESS,(0.0,1.0,4.0))

if __name__=="__main__":
    unittest.main()
