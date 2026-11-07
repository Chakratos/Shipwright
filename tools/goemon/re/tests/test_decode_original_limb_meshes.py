"""Offline true original F3DEX skeletal mesh reconstruction tests.

Synthetic executable Nintendo 64 display lists: no copied commercial assets.
"""
import struct
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from decode_original_limb_meshes import (
    decode_original_limb_mesh,decode_all_character_skeletal_meshes,
)


def fixture():
    bank=bytearray(0x300)
    bank07=bytes(0x500)
    # Parent limb display-list calls its geometry at 0x80.
    struct.pack_into(">II",bank,0x20,0x06000000,0x09000080)
    struct.pack_into(">II",bank,0x28,0xB8000000,0)
    struct.pack_into(">II",bank,0x80,
                     (4<<24)|(3<<10)|47,0x09000100)
    struct.pack_into(">II",bank,0x88,0xBF000000,0x00000204)
    struct.pack_into(">II",bank,0x90,0xB8000000,0)
    for i,(x,y,z) in enumerate(((3,4,5),(13,14,15),(23,24,25))):
        struct.pack_into(">hhhHhhBBBB",bank,0x100+16*i,
                         x,y,z,0,i*32,0,255,230,40,255)
    return {7:bank07,9:bytes(bank)}


class OriginalBoneMeshTests(unittest.TestCase):
    def test_source_root_gdl_recurses_and_preserves_real_3d_triangles(self):
        actual=decode_original_limb_mesh(0x09000020,fixture())
        self.assertEqual(len(actual.faces),1)
        self.assertEqual(actual.source_display_list_offset,0x09000020)
        self.assertEqual(actual.commands,5)
        self.assertEqual(actual.vertices[0].x,3)
        self.assertEqual(actual.vertices[1].y,14)
        self.assertEqual(actual.vertices[2].z,25)
        self.assertEqual(actual.vertices[1].s,32)
        self.assertEqual(actual.faces[0],(0,1,2))

    def test_character_meshes_are_per_genuine_source_bone_root(self):
        poses={
            "format":"ng5e-original-rom-skeletal-poses-v1",
            "character":"Goemon",
            "original_source_poses":[
                {"limbs":[{"gfx":0},{"gfx":0x09000020}]},
                {"limbs":[{"gfx":0x09000020},{"gfx":0x09000080},
                          {"gfx":0x090002F8}]}
            ]
        }
        result=decode_all_character_skeletal_meshes(poses,fixture())
        self.assertEqual(result["source_original_limb_gfx_count"],3)
        self.assertEqual(result["fully_decoded_limb_meshes"],2)
        self.assertEqual(result["decoded_source_triangles"],2)
        self.assertEqual(len(result["decode_failures"]),1)
        self.assertIn("0x09000020",result["source_meshes"])
        self.assertFalse(result["textures_decoded"])

    def test_invalid_child_display_list_is_not_guessed(self):
        banks=fixture()
        b=bytearray(banks[9])
        struct.pack_into(">II",b,0x20,0x06000000,0x0B000080)
        with self.assertRaisesRegex(ValueError,"unresolved"):
            decode_original_limb_mesh(0x09000020,{7:banks[7],9:bytes(b)})

    def test_invalid_triangles_fail_closed(self):
        banks=fixture()
        b=bytearray(banks[9])
        struct.pack_into(">II",b,0x88,0xBF000000,0x0000027E)
        with self.assertRaisesRegex(ValueError,"cache|triangle"):
            decode_original_limb_mesh(0x09000020,{7:banks[7],9:bytes(b)})

    def test_unresolved_geometry_transform_rejected(self):
        banks=fixture()
        b=bytearray(banks[9])
        struct.pack_into(">II",b,0x88,0x01000000,0x07000000)
        with self.assertRaisesRegex(ValueError,"unsupported original geometry state"):
            decode_original_limb_mesh(0x09000020,{7:banks[7],9:bytes(b)})

    def test_null_and_wrong_source_banks_rejected(self):
        with self.assertRaisesRegex(ValueError,"empty"):
            decode_original_limb_mesh(0,fixture())
        with self.assertRaisesRegex(ValueError,"source N64 limb needs"):
            decode_original_limb_mesh(0x09000020,{9:fixture()[9]})


if __name__=="__main__":
    unittest.main()
