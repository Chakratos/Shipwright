"""F3DEX source-verified 0x09 self-bank prevents old wrong-root OBJ export."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_segmented_geometry import decode_original_segmented_geometry


class SourceAlignedGeometryTests(unittest.TestCase):
    def fixture(self):
        command_bank=bytearray(0x400)
        source07=bytes(0x800)
        wrong_root=bytearray(0x400)
        for i, xyz in enumerate(((3,4,5),(13,14,15),(23,24,25))):
            struct.pack_into(">hhhHhhBBBB",command_bank,0x100+i*16,
                             *xyz,0, i*16, 16,255,200,150,255)
            struct.pack_into(">hhhHhhBBBB",wrong_root,0x100+i*16,
                             800+i,800+i,800+i,0,i*16,16,255,200,150,255)
        struct.pack_into(">II",command_bank,0x40,
                         (4<<24)|(3<<10)|47,0x09000100)
        struct.pack_into(">II",command_bank,0x48,0xBF000000,0x00000204)
        struct.pack_into(">II",command_bank,0x50,0xB8000000,0)
        return bytes(command_bank), source07, bytes(wrong_root)

    def test_source_verified_09_vertex_read_is_not_character_root(self):
        commands,original07,wrong_root=self.fixture()
        corrected=decode_original_segmented_geometry(
            commands, commands, source_file_id=291,
            source_banks={7:original07,9:commands})
        legacy=decode_original_segmented_geometry(
            commands,wrong_root,source_file_id=291)
        self.assertEqual(len(corrected.mesh.faces),1)
        self.assertEqual(corrected.mesh.vertices[0].x,3)
        self.assertEqual(corrected.mesh.vertices[1].y,14)
        self.assertEqual(corrected.mesh.vertices[2].z,25)
        self.assertEqual(legacy.mesh.vertices[0].x,800)
        self.assertNotEqual(corrected.mesh.vertices,legacy.mesh.vertices)
        self.assertTrue(corrected.runs[0].terminated_by_enddl)

    def test_missing_actual_original_bank_fails_closed(self):
        commands,source07,_=self.fixture()
        with self.assertRaisesRegex(ValueError,"mapped 0x07 and 0x09"):
            decode_original_segmented_geometry(
                commands,commands,source_banks={7:source07})

if __name__=="__main__":
    unittest.main()
