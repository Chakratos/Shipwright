"""Original N64 big-endian MIPS matrix routine disassembler (synthetic only)."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from disasm_original_animation_mips import (
    decode_instruction,analyze_original_matrix_mips,START_VRAM,
    START_ROM,END_ROM
)

def encode_i(op,rs,rt,imm):
    return (op<<26)|(rs<<21)|(rt<<16)|(imm&0xffff)

class OriginalMIPSAnimationDecoderTests(unittest.TestCase):
    def test_actual_original_animation_vram_to_rom_address(self):
        self.assertEqual(START_VRAM-0x80000000,0x192D0)
        self.assertEqual(START_ROM-0x192D0,0xC00)
        self.assertEqual(END_ROM-START_ROM,0x3D4)
        self.assertEqual((END_ROM-START_ROM)//4,245)

    def test_decode_mips_big_endian_memory_access_and_channel_masks(self):
        base=START_VRAM
        lhu=decode_instruction(base,encode_i(0x25,4,2,0x18))
        self.assertEqual(lhu.mnemonic,"lhu")
        self.assertIn("24($a0)",lhu.operands)
        lui=decode_instruction(base,encode_i(0xf,0,8,0xb100))
        self.assertEqual(lui.mnemonic,"lui")
        self.assertIn("0xB100",lui.operands)
        andi=decode_instruction(base,encode_i(0xc,9,10,0x3ff))
        self.assertEqual(andi.mnemonic,"andi")
        self.assertIn("0x03FF",andi.operands)
        branch=decode_instruction(base,encode_i(4,4,2,0xfffe))
        self.assertEqual(branch.mnemonic,"beq")
        self.assertIn("0x800192CC",branch.operands)

    def test_source_original_jump_target_and_float_instructions(self):
        jal=decode_instruction(START_VRAM,(3<<26)|(0x80012340>>2&0x3ffffff))
        self.assertEqual(jal.mnemonic,"jal")
        self.assertIn("0x80012340",jal.operands)
        nop=decode_instruction(START_VRAM,0)
        self.assertEqual(nop.mnemonic,"nop")
        self.assertEqual(nop.operands,"")
        fmul=decode_instruction(START_VRAM,(17<<26)|(16<<21)|(4<<16)|(2<<11)|(6<<6)|2)
        self.assertEqual(fmul.mnemonic,"mul.s")

    def test_original_function_boundaries_enforced(self):
        with self.assertRaisesRegex(ValueError,"length mismatch"):
            analyze_original_matrix_mips(bytes(0x3D0))
        sample=bytearray(END_ROM-START_ROM)
        struct.pack_into(">I",sample,0,encode_i(0x25,4,2,0x18))
        struct.pack_into(">I",sample,4,encode_i(0xf,0,8,0xb100))
        out=analyze_original_matrix_mips(bytes(sample))
        self.assertEqual(out["instruction_count"],245)
        self.assertEqual(out["opcode_frequency"]["lhu"],1)
        self.assertEqual(out["immediate_values"]["0xB100"],1)
        self.assertFalse(out["original_animation_math_extracted"])

if __name__=="__main__":
    unittest.main()
