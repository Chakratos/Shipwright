"""Source player AnimatedSkeleton exact candidate dispatch, not timeline guessing."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probe_original_mips_execution import choose_source_candidate

class SourceMipsCandidateDispatchTests(unittest.TestCase):
    def test_select_exact_original_source_bank_header(self):
        candidates=(
            {"source_header_offset":0x100,"source_header_segment":"0x07"},
            {"source_header_offset":0x200,"source_header_segment":"0x07"},
        )
        self.assertEqual(choose_source_candidate(candidates,None),
                         candidates[0])
        self.assertEqual(choose_source_candidate(candidates,0x200),
                         candidates[1])
        with self.assertRaisesRegex(ValueError,"absent/ambiguous"):
            choose_source_candidate(candidates,0x300)
    def test_no_unverified_candidates_accepted(self):
        with self.assertRaisesRegex(ValueError,"no source"):
            choose_source_candidate((),None)

if __name__=="__main__":
    unittest.main()
