"""Static original Goemon MIPS animation analysis, all instructions synthetic."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from original_mips_animation_flow import (
    classify_original_mips_transfer,
    build_original_mips_basic_blocks,
    find_original_animation_global_accesses,
    build_original_mips_instruction_flow,
    source_mips_flow_report,
)

BASE=0x800192D0

def i(op,rs,rt,imm):
    return ((op<<26)|(rs<<21)|(rt<<16)|(imm&0xFFFF))
def r(rs,rt,rd,sh,fun):
    return (rs<<21)|(rt<<16)|(rd<<11)|(sh<<6)|fun
def jal(address):
    return (3<<26)|((address>>2)&0x03FFFFFF)

def fixture():
    instructions=[
        i(0x0f,0,8,0x8017),    # 0 LUI t0, global page
        i(0x23,8,2,0x8520),    # 1 LW  v0, D_80168520
        i(0x04,2,0,3),         # 2 BEQ v0,zero => index6
        0,                     # 3 delay
        i(0x0f,0,9,0x8017),    # 4 LUI t1, global page
        i(0x2b,9,2,0x84B0),    # 5 SW v0, D_801684B0
        i(0x14,2,0,3),         # 6 BEQL v0,zero => index10
        0,                     # 7 delay annul if false
        jal(0x80010000),       # 8 JAL external helper
        0,                     # 9 delay
        r(31,0,0,0,8),         # 10 JR ra
        0,                     # 11 return delay
        i(0x0f,0,8,0x8017),    # 12 unreachable block
        i(0x23,8,2,0x8510),    # 13 LW D_80168510
    ]
    return struct.pack(">"+("I"*len(instructions)),*instructions)


class OriginalMipsControlFlowTests(unittest.TestCase):
    def test_source_branch_delay_slots_and_branch_likely_annulment(self):
        data=fixture()
        graph=build_original_mips_basic_blocks(data,BASE)
        self.assertEqual(graph["instructions"],14)
        self.assertEqual(graph["conditional_branch_count"],2)
        self.assertEqual(graph["branch_likely_count"],1)
        self.assertEqual(graph["delay_slot_count"],4)
        self.assertGreater(graph["reachable_blocks"],0)
        self.assertGreater(graph["unreachable_blocks"],0)
        branches=[edge for edge in graph["edges"]
                  if edge["kind"]=="conditional_branch"]
        self.assertTrue(any(edge["to"]==f"0x{BASE+6*4:08X}"
                            for edge in branches))
        self.assertTrue(any(edge["to"]==f"0x{BASE+10*4:08X}"
                            for edge in branches))
        unreachable=[x for x in graph["blocks"] if not x["reachable"]]
        self.assertEqual([x["start"] for x in unreachable],
                         [f"0x{BASE+12*4:08X}"])
        self.assertIn(f"0x{BASE+8*4:08X}",
                      [item["at"] for item in graph["calls"]])
        self.assertIn("0x80010000",
                      [item["target"] for item in graph["calls"]])

    def test_identify_true_global_addresses_using_signed_lui_offsets(self):
        refs=find_original_animation_global_accesses(fixture(),BASE)
        self.assertEqual(len(refs),3)
        self.assertEqual(
            [x["known_animation_global"] for x in refs],
            ["source_animation_data_pointer",
             "active_original_4x4_matrix",
             "source_animation_progress"])
        self.assertEqual([x["address"] for x in refs],
                         ["0x80168520","0x801684B0","0x80168510"])
        self.assertEqual(refs[0]["operation"],"lw")
        self.assertEqual(refs[1]["operation"],"sw")

    def test_regimm_conditional_branches_and_indirect_jump(self):
        bltzl=(1<<26)|(4<<21)|(2<<16)|0xFFFE
        t=classify_original_mips_transfer(BASE,bltzl)
        self.assertEqual(t.kind,"conditional_branch")
        self.assertTrue(t.annul_delay_if_not_taken)
        self.assertEqual(t.target,BASE-4)
        jr=classify_original_mips_transfer(BASE,r(31,0,0,0,8))
        self.assertEqual(jr.kind,"return")
        self.assertIsNone(jr.fallthrough)
        self.assertEqual(jr.delay_slot,BASE+4)

    def test_jump_into_delay_slot_is_not_misidentified_as_normal_cfg(self):
        # Source MIPS can branch into a delay slot, but this analyzer
        # must fail closed rather than invent a clean block graph.
        source=[i(4,0,0,0),0,r(31,0,0,0,8),0]
        with self.assertRaisesRegex(ValueError,"delay slot"):
            build_original_mips_basic_blocks(
                struct.pack(">IIII",*source),BASE)

    def test_ambiguous_delay_slot_preserves_diagnostics_without_fake_cfg(self):
        source=struct.pack(">IIII",i(4,0,0,0),0,r(31,0,0,0,8),0)
        report=source_mips_flow_report(source,BASE)
        graph=report["control_flow"]
        self.assertEqual(graph["instructions"],4)
        self.assertFalse(graph["cfg_verified"])
        self.assertIsNone(graph["basic_blocks"])
        self.assertEqual(graph["edges"],[])
        self.assertEqual(graph["delay_slot_conflicts"][0]["target_delay_slot"],
                         f"0x{BASE+4:08X}")
        self.assertIn("UNVERIFIED",report["limits"][-1])

    def test_instruction_flow_handles_branch_into_delay_slot_as_normal_entry(self):
        # BEQ +0: first execute PC+4 as its delay slot; the same address
        # is also a legal branch target executed as a normal instruction.
        data=struct.pack(">IIII",
                         i(4,0,0,0),i(9,8,8,1),r(31,0,0,0,8),0)
        graph=build_original_mips_instruction_flow(data,BASE)
        self.assertEqual(graph["total_instructions"],4)
        self.assertEqual(graph["reachable_instruction_entries"],3)
        self.assertEqual(graph["atomic_delay_slot_transfers"],2)
        self.assertEqual(graph["branch_delay_nesting_unresolved"],[])
        entry_edges=[e for e in graph["edges"]
                     if e["from"]==f"0x{BASE:08X}"]
        self.assertEqual({e["to"] for e in entry_edges},
                         {f"0x{BASE+4:08X}",f"0x{BASE+8:08X}"})
        self.assertFalse(graph["semantics_fully_verified"] is None)

    def test_branch_likely_marks_not_taken_delay_slot_as_annulled(self):
        data=struct.pack(">IIII",
                         i(0x14,2,0,1),i(9,8,8,1),r(31,0,0,0,8),0)
        graph=build_original_mips_instruction_flow(data,BASE)
        d=graph["delay_slot_execution"][f"0x{BASE:08X}"]
        self.assertTrue(d["on_taken"])
        self.assertFalse(d["on_fallthrough"])
        self.assertEqual(d["slot_pc"],f"0x{BASE+4:08X}")

    def test_conditional_global_report_never_claims_codec_is_decoded(self):
        analysis=source_mips_flow_report(fixture(),BASE)
        self.assertEqual(analysis["control_flow"]["instructions"],14)
        self.assertEqual(
            len(analysis["direct_animation_global_memory_accesses"]),3)
        self.assertTrue(any("not a full emulator" in s
                            for s in analysis["limits"]))

if __name__=="__main__":
    unittest.main()
