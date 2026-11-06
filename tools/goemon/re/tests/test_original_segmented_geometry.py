"""Decode actual F3DEX commands across source-mapped 0x07 and 0x09 banks.

The fixture only contains synthetic N64 bytes, no copyrighted ROM data.
"""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from original_segmented_geometry import (
    decode_original_segmented_geometry, recovery_summary, _triangle_slots
)
from original_f3dex_geometry import mesh_to_obj


def gfx(raw: bytearray, offset: int, w0: int, w1: int):
    struct.pack_into(">II", raw, offset, w0, w1)


def fixture() -> tuple[bytes, bytes]:
    vertex_bank = bytearray(1024)
    cmds = bytearray(256)
    for i in range(4):
        struct.pack_into(">hhhHhhBBBB", vertex_bank, 0x100 + i * 16,
                         i * 10, i * 5, -i * 2, 0, i * 16, 16,
                         255, 127, 63, 255)
    gfx(cmds, 0x40, (4<<24) | (3<<10) | (47), 0x09000100)
    gfx(cmds, 0x48, 0xBF000000, 0x00000204)
    gfx(cmds, 0x50, 0xB8000000, 0)
    # Independent second original display-list with two triangles.
    gfx(cmds, 0x80, (4<<24) | (4<<10) | (63), 0x09000100)
    gfx(cmds, 0x88, 0xB1000004, 0x00020406)
    gfx(cmds, 0x90, 0xB8000000, 0)
    return bytes(cmds), bytes(vertex_bank)


class SourceOriginalGeometryTests(unittest.TestCase):
    def test_two_real_n64_gfx_streams_and_actual_vertex_data(self):
        commands, vertices = fixture()
        result = decode_original_segmented_geometry(commands, vertices)
        self.assertIsNotNone(result.mesh)
        self.assertEqual(len(result.mesh.faces), 3)
        self.assertEqual(len(result.mesh.vertices), 9)
        self.assertEqual(len(result.runs), 2)
        self.assertEqual(result.runs[0].start, 0x40)
        self.assertEqual(result.runs[1].start, 0x80)
        self.assertEqual(result.runs[0].triangles, 1)
        self.assertEqual(result.runs[1].triangles, 2)
        self.assertTrue(all(x.terminated_by_enddl for x in result.runs))
        self.assertEqual(result.mesh.vertices[0].x, 0)
        self.assertEqual(result.mesh.vertices[2].x, 20)
        self.assertEqual(result.mesh.vertices[8].x, 30)
        self.assertIn("v 30 15 -6", mesh_to_obj(result.mesh))
        self.assertEqual(recovery_summary(result)["triangles"], 3)
        self.assertFalse(recovery_summary(result)["skeletal_hierarchy_recovered"])

    def test_repeated_vertex_command_inside_one_display_list_is_not_double_counted(self):
        commands, vertices = fixture()
        cmds = bytearray(commands)
        gfx(cmds, 0x50, (4<<24) | (4<<10) | 63, 0x09000100)
        gfx(cmds, 0x58, 0xBF000000, 0x00020406)
        gfx(cmds, 0x60, 0xB8000000, 0)
        result = decode_original_segmented_geometry(bytes(cmds), vertices)
        self.assertEqual(len(result.runs), 2)
        self.assertEqual(result.runs[0].triangles, 2)
        self.assertEqual(len(result.mesh.faces), 4)

    def test_unmapped_bank_cannot_generate_fake_mesh(self):
        commands, vertices = fixture()
        cmds = bytearray(commands)
        gfx(cmds, 0x40, (4<<24) | (3<<10) | 47, 0x08000100)
        gfx(cmds, 0x80, (4<<24) | (4<<10) | 63, 0x08000100)
        result = decode_original_segmented_geometry(bytes(cmds), vertices)
        self.assertIsNone(result.mesh)
        self.assertEqual(len(result.runs), 0)

    def test_triangle_index_scale_and_out_of_range(self):
        self.assertEqual(_triangle_slots(0x00020406), (1,2,3))
        with self.assertRaisesRegex(ValueError, "invalid F3DEX"):
            _triangle_slots(0x00414002)

    def test_outside_vertex_cache_breaks_run_without_fabricated_faces(self):
        commands, vertices = fixture()
        cmds = bytearray(commands)
        gfx(cmds, 0x48, 0xBF000000, 0x00023E04)
        result = decode_original_segmented_geometry(bytes(cmds), vertices)
        self.assertIsNotNone(result.mesh)
        self.assertEqual(len(result.mesh.faces), 2)
        self.assertEqual(result.skipped_invalid_faces, 1)

if __name__ == "__main__":
    unittest.main()
