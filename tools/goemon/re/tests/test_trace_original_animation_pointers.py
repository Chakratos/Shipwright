"""Exact MIPS source read-site and candidate pointer provenance controls."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trace_original_animation_pointers import (
    PROGRESS,choose_animation_owner_candidates,
    summarize_exact_source_reads
)

class ExactOriginalSourceReadSiteTests(unittest.TestCase):
    def sample(self,pc=0x800192D0,ptr=0x80400100,
               addresses=(0x80400100,),digest="abc"):
        return {
            "returned":True,
            "separate_original_matrix_stack_probe":True,
            "private_candidate_animation_pointer":ptr,
            "private_source_bank_bounds":[0x80400000,0x80410000],
            "private_original_source_read_sites":[
                {"pc":pc,"address":address,"width":4,"count":1}
                for address in addresses
            ],
            "original_mtxf_numeric_digest":digest
        }
    def test_exact_source_address_near_candidate_pointer_is_not_animation_proof(self):
        samples=[self.sample(),self.sample(),self.sample()]
        report=summarize_exact_source_reads(samples,0x80400100)
        self.assertEqual(report["near_candidate_pointer_loads_by_progress"],[1]*3)
        self.assertFalse(report["source_read_locations_change_over_progress"])
        self.assertFalse(report["numeric_mtxf_changes_over_progress"])
        self.assertFalse(report["candidate_pointer_is_proven_active_player_animation"])
        self.assertEqual(report["first_candidate_pointer_read_sites"][0],{
            "mips_pc":"0x800192D0","relative_offset":0,"width":4
        })
    def test_progress_read_location_changes_without_claiming_numerical_motion(self):
        samples=[
            self.sample(addresses=(0x80400104,)),
            self.sample(addresses=(0x80400108,)),
            self.sample(addresses=(0x80400110,))
        ]
        report=summarize_exact_source_reads(samples,0x80400100)
        self.assertTrue(report["source_read_locations_change_over_progress"])
        self.assertFalse(report["numeric_mtxf_changes_over_progress"])
    def test_failed_or_mismatched_original_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"source N64 CPU"):
            summarize_exact_source_reads([
                {**self.sample(),"returned":False},
                self.sample(),self.sample()],0x80400100)
        with self.assertRaisesRegex(ValueError,"pointer/probe"):
            summarize_exact_source_reads([
                self.sample(),self.sample(),self.sample()],0x80400200)
        self.assertEqual(PROGRESS,(0.0,1.0,4.0))
    def test_source_candidates_deduplicate_same_header(self):
        node={"scale":(1,0,0),"rotation":(0,0,0),"translation":(0,0,0)}
        records=(
            {"source_header_offset":12,"limbs":[node]},
            {"source_header_offset":64,"limbs":[node]}
        )
        self.assertEqual(len(choose_animation_owner_candidates(records,12)),1)
        self.assertEqual(len(choose_animation_owner_candidates(records,64)),2)

if __name__=="__main__":
    unittest.main()
