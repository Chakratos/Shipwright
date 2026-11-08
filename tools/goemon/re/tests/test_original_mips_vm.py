"""Portable synthetic MIPS tests; original commercial code never bundled."""
from pathlib import Path
import struct
import math
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_mips_vm import OriginalMipsCPU,MipsFault,STOP,f32,bits32,f64,bits64

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
    def test_real_mips_cvt_double_and_back(self):
        # cvt.d.s f6,f4 ; cvt.s.d f8,f6 ; jr ra ; nop
        self.cpu.f[4]=bits32(1.25)
        cvtd=(0x11<<26)|(0x10<<21)|(4<<11)|(6<<6)|0x21
        cvts=(0x11<<26)|(0x11<<21)|(6<<11)|(8<<6)|0x20
        self.execute(cvtd,cvts,R(31,0,0,0,8),0)
        self.assertEqual(f64(self.cpu.f[6],self.cpu.f[7]),1.25)
        self.assertEqual(f32(self.cpu.f[8]),1.25)

    def test_source_trunc_word_uses_mips_toward_zero_semantics(self):
        self.cpu.f[4]=bits32(-1.75)
        convert=(0x11<<26)|(0x10<<21)|(4<<11)|(6<<6)|0x0D
        self.execute(convert,R(31,0,0,0,8),0)
        self.assertEqual(self.cpu.f[6],0xFFFFFFFF)

    def test_original_n64_sqrt_single_precision(self):
        self.cpu.f[4]=bits32(9.0)
        sqrt=(0x11<<26)|(0x10<<21)|(4<<11)|(6<<6)|0x04
        self.execute(sqrt,R(31,0,0,0,8),0)
        self.assertEqual(f32(self.cpu.f[6]),3.0)

    def test_original_masked_fpu_zero_division_emits_ieee_value(self):
        self.cpu.f[4]=bits32(1.0)
        self.cpu.f[6]=bits32(0.0)
        divide=(0x11<<26)|(0x10<<21)|(6<<16)|(4<<11)|(8<<6)|0x03
        self.execute(divide,R(31,0,0,0,8),0)
        self.assertTrue(math.isinf(f32(self.cpu.f[8])))

    def test_original_cop1_truncate_word_double_and_invalid_indefinite(self):
        self.cpu.f[4],self.cpu.f[5]=bits64(5.875)
        trunc=(0x11<<26)|(0x11<<21)|(4<<11)|(8<<6)|0x0D
        self.execute(trunc,R(31,0,0,0,8),0)
        self.assertEqual(self.cpu.f[8],5)
        self.cpu=OriginalMipsCPU()
        self.cpu.f[4],self.cpu.f[5]=bits64(float("inf"))
        self.execute(trunc,R(31,0,0,0,8),0)
        self.assertEqual(self.cpu.f[8],0x80000000)

    def test_source_word_to_double_fpu_conversion(self):
        self.cpu.f[4]=0xFFFFFFF9
        cvt=(0x11<<26)|(0x14<<21)|(4<<11)|(6<<6)|0x21
        self.execute(cvt,R(31,0,0,0,8),0)
        self.assertEqual(f64(self.cpu.f[6],self.cpu.f[7]),-7.0)

    def test_source_rom_read_provenance_includes_exact_pc_address_and_width(self):
        self.cpu.source_region=(0x80400100,0x80400200)
        self.cpu.store(0x80400110,0x12345678)
        self.cpu.r[8]=0x80400110
        self.execute(I(0x23,8,9,0),R(31,0,0,0,8),0)
        self.assertEqual(self.cpu.r[9],0x12345678)
        self.assertEqual(self.cpu.original_source_read_offsets[0x80400110],1)
        self.assertEqual(self.cpu.original_source_read_sites[
            (0x80002000,0x80400110,4)],1)
        self.assertEqual(len(self.cpu.original_source_read_sites),1)

    def test_unsupported_code_and_invalid_pointer_fail_closed(self):
        with self.assertRaisesRegex(MipsFault,"unknown MIPS opcode"):
            self.execute(0xfc000000)
        with self.assertRaisesRegex(MipsFault,"unmapped"):
            self.cpu.load(0x07000000)

if __name__=="__main__":
    unittest.main()
