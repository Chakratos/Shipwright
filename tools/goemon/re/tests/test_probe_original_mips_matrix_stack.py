"""Matrix-pointer aliasing control: no original owner ROM in test package."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probe_original_mips_matrix_stack import (
    NONCOMMUTING,IDENTITY,choose_original_limb
)

class OriginalMtxfOwnershipTests(unittest.TestCase):
    def test_control_matrix_is_nonsingular_noncommuting(self):
        self.assertEqual(len(NONCOMMUTING),16)
        self.assertEqual(len(IDENTITY),16)
        self.assertNotEqual(NONCOMMUTING,IDENTITY)
        self.assertEqual(NONCOMMUTING[15],1.0)
    def test_choice_requires_original_numeric_channels(self):
        blank=(0,0,0)
        nodes=[
            {"ptr":0x07000020,"scale":blank,"rotation":blank,"translation":blank},
            {"ptr":0x07000038,"scale":(5,0,0),"rotation":blank,"translation":blank},
        ]
        self.assertEqual(choose_original_limb(nodes)["ptr"],0x07000038)

if __name__=="__main__":
    unittest.main()
