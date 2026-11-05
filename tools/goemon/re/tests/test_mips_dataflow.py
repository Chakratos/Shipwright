"""Conservative register dataflow tests for original MIPS PlayerTask references."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mips_dataflow import trace_fields

class Tests(unittest.TestCase):
    def test_proven_read_write_original_player(self):
        code=[
            (0x100,0x3C088020), # lui t0 8020
            (0x104,0x8D08C604), # lw t0 -0x39FC(t0) = g_player_1_task
            (0x108,0x910900CC), # lbu t1, 0xCC(t0) action_id
            (0x10C,0xA10900CC), # sb t1, 0xCC(t0) action_id
            (0x110,0x910A0060), # lbu t2, 0x60(t0) character_id
        ]
        proof=trace_fields(code)
        self.assertEqual([(x['field'],x['direction']) for x in proof],
                         [('action_id','read'),('action_id','write'),('character_id','read')])
        self.assertTrue(all(x['global']=='g_player_1_task' for x in proof))

    def test_unrelated_field_offset_without_pointer_is_not_proven(self):
        self.assertEqual(trace_fields([(0x100,0x910900CC)]),[])

    def test_unknown_branch_invalidates_provenance(self):
        self.assertEqual(trace_fields([
            (0x100,0x3C088020),(0x104,0x8D08C604),
            (0x108,0x10000002), # branch
            (0x10c,0x910900CC)
        ]),[])

    def test_mov_task_provenance_through_addu(self):
        proof=trace_fields([(0x100,0x3C088020),(0x104,0x8D08C604),
                            (0x108,0x01008021),(0x10c,0x920900CC)])
        self.assertEqual(proof[0]['field'],'action_id')

    def test_unmodelled_xori_invalidates_pointer(self):
        proof=trace_fields([(0x100,0x3C088020),(0x104,0x8D08C604),
                            (0x108,0x390800FF), # xori t0,t0,255
                            (0x10c,0x910900CC)])
        self.assertEqual(proof,[])

    def test_mflo_invalidates_pointer(self):
        proof=trace_fields([(0x100,0x3C088020),(0x104,0x8D08C604),
                            (0x108,0x00004012), # mflo t0
                            (0x10c,0x910900CC)])
        self.assertEqual(proof,[])

    def test_unknown_register_write_drops_proof(self):
        proof=trace_fields([(0x100,0x3C088020),(0x104,0x8D08C604),
                            (0x108,0x25080004), # addiu t0,t0,4
                            (0x10c,0x910900CC)])
        self.assertEqual(proof,[])

if __name__=='__main__':unittest.main()
