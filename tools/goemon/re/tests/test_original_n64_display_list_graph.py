"""True N64 segmented Gfx call stack resolves bone-owned mesh parts."""
import struct
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_n64_display_list_graph import (
    trace_original_display_list,link_original_skeleton_gfx_roots
)

def fake_gfx():
    bank=bytearray(0x300)
    bank07=bytes(0x400)
    # gSPDisplayList(0x09000080) at original limb root.
    struct.pack_into(">II",bank,0x20,0x06000000,0x09000080)
    struct.pack_into(">II",bank,0x28,0xB8000000,0)
    struct.pack_into(">II",bank,0x80,(4<<24)|(3<<10)|47,0x09000100)
    struct.pack_into(">II",bank,0x88,0xBF000000,0x00000204)
    struct.pack_into(">II",bank,0x90,0xB8000000,0)
    return {7:bank07,9:bytes(bank)}

class OriginalN64DisplayListGraphTests(unittest.TestCase):
    def test_recurse_original_gdl_and_reach_real_mesh(self):
        out=trace_original_display_list(0x09000020,fake_gfx())
        self.assertTrue(out["complete"])
        self.assertEqual(out["reason"],"enddl")
        self.assertEqual(len(out["gdl_calls"]),1)
        self.assertEqual(out["gdl_calls"][0]["target"],"0x09000080")
        self.assertEqual(len(out["source_gspvertex_commands"]),1)
        vtx=out["source_gspvertex_commands"][0]
        self.assertEqual(vtx["command_offset"],0x80)
        self.assertEqual(vtx["source_vertex_segment"],9)
        self.assertEqual(vtx["vertex_count"],3)
        self.assertEqual(out["triangle_opcode_candidates"],1)

    def test_match_original_bone_root_to_immutable_gfx_file(self):
        poses={"format":"ng5e-original-rom-skeletal-poses-v1",
               "character":"Goemon",
               "original_source_poses":[{"limbs":[
                   {"gfx":0},{"gfx":0x09000020},{"gfx":0x09000020}]}]}
        meshes={"per_display_list_objects":[
            {"display_list_offset":0x80,
             "local_obj_file":"gfx_000_at_0x000080.obj"}]}
        linked=link_original_skeleton_gfx_roots(poses,fake_gfx(),meshes)
        self.assertEqual(linked["source_rom_skeleton_graphics_roots"],1)
        self.assertEqual(linked["fully_terminated_source_display_lists"],1)
        self.assertEqual(linked["roots_with_confirmed_mesh_parts"],1)
        self.assertEqual(linked["matched_unique_mesh_parts"],1)
        self.assertEqual(linked["sources"][0]["status"],"complete")
        self.assertEqual(
            linked["sources"][0]["matched_source_parts"][0]["model_part"],
            "gfx_000_at_0x000080.obj")
        self.assertFalse(linked["original_animation_timeline_decoded"])

    def test_invalid_or_recursive_source_pointers_rejected(self):
        bank=fake_gfx()
        out=trace_original_display_list(0x09000300,bank)
        self.assertFalse(out["complete"])
        self.assertEqual(out["reason"],"unresolved_or_unaligned_segmented_gfx")
        data=bytearray(bank[9])
        struct.pack_into(">II",data,0x20,0x06000000,0x09000020)
        out=trace_original_display_list(0x09000020,{7:bank[7],9:bytes(data)})
        self.assertFalse(out["complete"])
        self.assertEqual(out["reason"],"display_list_cycle")

    def test_no_false_binding_for_unresolved_call(self):
        data=bytearray(fake_gfx()[9])
        struct.pack_into(">II",data,0x20,0x06000000,0x0B000020)
        out=trace_original_display_list(0x09000020,{7:bytes(0x300),9:bytes(data)})
        self.assertFalse(out["complete"])
        self.assertEqual(out["reason"],"unresolved_or_unaligned_segmented_gfx")
        self.assertEqual(out["source_gspvertex_commands"],[])

if __name__=="__main__":
    unittest.main()
