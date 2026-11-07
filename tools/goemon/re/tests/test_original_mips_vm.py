"""Portable synthetic MIPS tests; original commercial code never bundled."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_mips_vm import OriginalMipsCPU,MipsFault,STOP,f32,bits32

def I(op,rs,rt,imm):
    return (op<<26)|(rs<<21)|(rt<<16)|(imm&65535)

def R(rs,rt,rd,shift,fn):
    return (rs<<21)|(rt<<16)|(rd<<11)|(shift<<6)|fn

class MipsEmulatorTests(unittest.TestCase):
    def setUp(self):
        self.cpu=OriginalMipsCPU()
    def execute(self,*words):
        self.cpu.copy(0x80002000,struct.pack(">"+"I"*len(words),*words))
        return self.cpu.run(0x80002000,budget=60)
    def test_real_mips_branch_delay_semantics(self):
        self.execute(I(9,0,8,1), I(5,8,0,2), I(9,0,9,7),
                     I(9,0,9,100), I(9,0,10,11), R(31,0,0,0,8), 0)
        self.assertEqual(self.cpu.r[9],7)
        self.assertEqual(self.cpu.r[10],11)
        self.assertEqual(self.cpu.executed,6)
        self.assertEqual(self.cpu.pc,STOP)
    def test_branch_likely_annuls_delay_on_not_taken(self):
        self.execute(I(9,0,8,0),I(0x15,8,0,1),
                     I(9,0,9,99),I(9,0,10,2),R(31,0,0,0,8),0)
        self.assertEqual(self.cpu.r[9],0)
        self.assertEqual(self.cpu.r[10],2)
    def test_float_cop1_roundtrip_and_memory_big_endian(self):
        self.cpu.store(0x80160020,0x3f800000)
        self.cpu.r[8]=0x80160020
        self.execute(I(0x31,8,4,0),I(0x39,8,4,4),
                     I(0x23,8,9,4),R(31,0,0,0,8),0)
        self.assertEqual(self.cpu.r[9],0x3f800000)
        self.assertEqual(self.cpu.load(0x80160024),0x3f800000)
        self.assertEqual(f32(self.cpu.f[4]),1.0)
        self.assertEqual(bits32(1.0),0x3f800000)
    def test_unsupported_code_and_invalid_pointer_fail_closed(self):
        with self.assertRaisesRegex(MipsFault,"unknown MIPS opcode"):
            self.execute(0xfc000000)
        with self.assertRaisesRegex(MipsFault,"unmapped"):
            self.cpu.load(0x07000000)

if __name__=="__main__":
    unittest.main()
