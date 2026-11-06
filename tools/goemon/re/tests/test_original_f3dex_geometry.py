"""Executable synthetic tests for the original F3DEX geometry interpreter.

No copyright game assets are embedded. Command encoding corresponds to the
pinned original N64 gbi.h F3DEX_GBI macros, not the Zelda/Ship renderer.
"""
from __future__ import annotations
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from original_f3dex_geometry import (
    decode_f3dex, mesh_to_obj, UnsupportedGeometryCommand
)

VTX_ADDR = 0x08000100
LIST_ADDR = 0x08000040
CHILD_ADDR = 0x08000080

def gfx(data: bytearray, at: int, op: int, word1: int, lower: int = 0):
    struct.pack_into(">II", data, at, op << 24 | lower, word1)

def triangle(a: int, b: int, c: int) -> int:
    return (a * 2 << 16) | (b * 2 << 8) | (c * 2)

def fixture() -> bytearray:
    data = bytearray(512)
    for i, (x, y, z) in enumerate(
        ((10, 20, 30), (-10, 5, 20), (7, -2, -9), (4, 8, 12))
    ):
        struct.pack_into(">hhhHhhBBBB", data, 0x100 + i * 16,
                         x, y, z, 0, 32 * i, -32 * i,
                         255, 64, 32, 255)
    return data

def vtx(data: bytearray, at: int, n: int, v0: int = 0):
    gfx(data, at, 4, VTX_ADDR, (v0 * 2 << 16) | (n << 10) | (16*n-1))

class OriginalF3DEXGeometryTests(unittest.TestCase):
    def test_source_exact_vtx_tri1_and_enddl(self):
        raw = fixture()
        vtx(raw, 0x40, 3)
        gfx(raw, 0x48, 0xBF, triangle(0, 1, 2))
        gfx(raw, 0x50, 0xB8, 0)
        result = decode_f3dex(bytes(raw), LIST_ADDR)
        self.assertEqual(len(result.faces), 1)
        self.assertEqual(len(result.vertices), 3)
        self.assertEqual([(v.x, v.y, v.z) for v in result.vertices],
                         [(10,20,30), (-10,5,20), (7,-2,-9)])
        self.assertEqual(result.vertices[1].s, 32)
        self.assertEqual(result.vertices[1].t, -32)
        self.assertEqual(result.faces[0], (0,1,2))
        self.assertEqual(result.commands, 3)
        obj = mesh_to_obj(result)
        self.assertIn("v -10 5 20\n", obj)
        self.assertIn("f 1 2 3\n", obj)
        self.assertNotIn("vt ", obj)  # Unverified texture size, no fake UV.

    def test_nested_list_and_tri2_share_n64_vertex_cache(self):
        raw = fixture()
        gfx(raw, 0x40, 6, CHILD_ADDR)
        gfx(raw, 0x48, 0xB1, triangle(0,1,2),
            lower=triangle(0,2,3))
        gfx(raw, 0x50, 0xB8, 0)
        vtx(raw, 0x80, 4)
        gfx(raw, 0x88, 0xB8, 0)
        result = decode_f3dex(bytes(raw), LIST_ADDR)
        self.assertEqual(len(result.faces), 2)
        self.assertEqual(len(result.vertices), 6)
        self.assertEqual(result.vertices[3].x, 10)
        self.assertEqual(result.vertices[5].z, 12)

    def test_branch_list_not_return(self):
        raw = fixture()
        gfx(raw, 0x40, 6, CHILD_ADDR, lower=1 << 16)
        gfx(raw, 0x48, 0xBF, triangle(0,1,2)) # Must never run.
        vtx(raw, 0x80, 3)
        gfx(raw, 0x88, 0xBF, triangle(0,2,1))
        gfx(raw, 0x90, 0xB8, 0)
        result = decode_f3dex(bytes(raw), LIST_ADDR)
        self.assertEqual(len(result.faces), 1)
        self.assertEqual(result.vertices[1].x, 7)

    def test_no_vertex_cache_index_and_invalid_dma_fail(self):
        raw = fixture()
        gfx(raw, 0x40, 0xBF, triangle(0,1,2))
        gfx(raw, 0x48, 0xB8, 0)
        with self.assertRaisesRegex(ValueError, "unloaded"):
            decode_f3dex(bytes(raw), LIST_ADDR)
        vtx(raw, 0x40, 33)
        with self.assertRaisesRegex(ValueError, "vertex command"):
            decode_f3dex(bytes(raw), LIST_ADDR)
        vtx(raw, 0x40, 3)
        gfx(raw, 0x48, 0xBF, triangle(0,1,32))
        with self.assertRaisesRegex(ValueError, "index"):
            decode_f3dex(bytes(raw), LIST_ADDR)

    def test_wrong_microcode_transform_and_pointer_fail_closed(self):
        raw = fixture()
        gfx(raw, 0x40, 0x01, 0x08000080)
        with self.assertRaises(UnsupportedGeometryCommand):
            decode_f3dex(bytes(raw), LIST_ADDR)
        gfx(raw, 0x40, 0xB2, 0)
        with self.assertRaises(UnsupportedGeometryCommand):
            decode_f3dex(bytes(raw), LIST_ADDR)
        with self.assertRaisesRegex(ValueError, "unsupported original"):
            decode_f3dex(bytes(raw), 0x09000040)
        with self.assertRaisesRegex(ValueError, "eight-byte"):
            decode_f3dex(bytes(raw), 0x08000044)

    def test_command_budget_and_truncated_original_data(self):
        raw = fixture()
        vtx(raw, 0x40, 3)
        gfx(raw, 0x48, 0xBF, triangle(0,1,2))
        with self.assertRaisesRegex(ValueError, "budget"):
            decode_f3dex(bytes(raw), LIST_ADDR, max_commands=1)
        gfx(raw, 0x50, 0x06, LIST_ADDR, lower=1 << 16)
        with self.assertRaisesRegex(ValueError, "budget"):
            decode_f3dex(bytes(raw), LIST_ADDR, max_commands=30)
        with self.assertRaisesRegex(ValueError, "outside original resource"):
            decode_f3dex(bytes(raw)[:0x50], LIST_ADDR)

    def test_unknown_material_command_is_recorded_not_reinterpreted(self):
        raw = fixture()
        gfx(raw, 0x40, 0xFA, 0xFFFFFFFF) # N64 G_SETPRIMCOLOR
        vtx(raw, 0x48, 3)
        gfx(raw, 0x50, 0xBF, triangle(0,1,2))
        gfx(raw, 0x58, 0xB8, 0)
        result = decode_f3dex(bytes(raw), LIST_ADDR)
        self.assertEqual(result.ignored_opcodes, {"0xFA": 1})
        self.assertEqual(len(result.faces), 1)

if __name__ == "__main__":
    unittest.main()
