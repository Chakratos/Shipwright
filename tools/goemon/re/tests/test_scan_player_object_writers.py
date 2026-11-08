"""MIPS source player-object offset scanner synthetic opcode fixtures."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scan_player_object_writers import (
    decode_store_field,find_writer_candidates,
)

def i(op,rs,rt,offset):
    return ((op<<26)|(rs<<21)|(rt<<16)|(offset&0xFFFF))

class OriginalPlayerObjectWriterScanTests(unittest.TestCase):
    def test_mips_original_graphics_and_task_action_offsets(self):
        g=decode_store_field(i(0x2B,16,8,0x2C))
        self.assertEqual(g["field_candidate"],"Object.graphics_1_candidate")
        self.assertEqual((g["base_register"],g["value_register"]),(16,8))
        a=decode_store_field(i(0x28,17,9,0xCC))
        self.assertEqual(a["field_candidate"],"PlayerTask.action_id_candidate")
        self.assertEqual(a["store_instruction"],"sb")
        self.assertIsNone(decode_store_field(i(0x23,16,8,0x2C)))
        self.assertIsNone(decode_store_field(i(0x2B,16,8,-212)))
    def test_original_segmented_player_tag_context_is_just_hint(self):
        instructions=[
            i(0x0F,0,8,0x6700),
            i(0x2B,16,8,0x2C),
            i(0x28,17,9,0xCC),
            0,
            i(0x2B,16,8,0x2C),
        ]
        code=struct.pack(">"+"I"*len(instructions),*instructions)
        scan=find_writer_candidates(
            code,source_rom_offset=0x6000,
            code_vram_base=0x80100000,
            source_file="synthetic_original_overlay")
        self.assertEqual(scan["total_field_offset_store_candidates"],3)
        gfx=scan["fields"]["Object.graphics_1_candidate"]
        self.assertEqual(gfx["candidate_instruction_count"],2)
        self.assertEqual(gfx["first_candidates_by_source_pc"][0][
            "original_mips_pc"],"0x80100004")
        self.assertEqual(gfx["first_candidates_by_source_pc"][0][
            "nearby_tagged_player_type_lui_count"],1)
        self.assertFalse(gfx["first_candidates_by_source_pc"][0][
            "original_player_field_writer_verified"])
        self.assertEqual(scan["fields"]["PlayerTask.action_id_candidate"][
            "candidate_instruction_count"],1)
    def test_non_aligned_and_empty_code_refused(self):
        with self.assertRaisesRegex(ValueError,"unaligned or empty"):
            find_writer_candidates(b"",source_rom_offset=0,
                code_vram_base=0x80000400,source_file="bad")
        with self.assertRaisesRegex(ValueError,"unaligned or empty"):
            find_writer_candidates(b"\0\0\0\0",source_rom_offset=2,
                code_vram_base=0x80000400,source_file="bad")

if __name__=="__main__":
    unittest.main()
