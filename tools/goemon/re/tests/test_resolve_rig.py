"""Verify pointer relocation against synthetic original-structure ROM assets."""
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from resolve_rig import decode_rig,resolve_pointer

class Tests(unittest.TestCase):
    def fixture(self):
        data=bytearray(1024)
        flags=(1<<28)|(2<<8)|0x10
        struct.pack_into('>III',data,0x100,flags,0x08000300,0x08000200)
        struct.pack_into('>Ibb9h',data,0x200,0x08000340,-1,0,1,2,3,4,5,6,7,8,9)
        capture={'character_id':2,'overlay_zero_file_id':31,'overlay_zero_base':0x80100000,
                 'graphics_pointer':0x68000100,'flags':flags,
                 'animation_pointer':0x08000300,'skeleton_pointer':0x08000200}
        return bytes(data),capture

    def test_original_rig_from_segmented_pointers(self):
        data,capture=self.fixture()
        result=decode_rig(data,capture,31)
        self.assertEqual(result['first_skeleton']['translation_raw'],[7,8,9])
        self.assertEqual(result['root_animated_skeleton']['limb_count'],2)
        self.assertEqual(result['root_animated_skeleton']['file_offset'],0x100)

    def test_root_direct_pointer(self):
        data,capture=self.fixture()
        capture['graphics_pointer']=0xE0100100
        self.assertEqual(resolve_pointer(0x80100100,0x80100000,len(data)),0x100)
        self.assertEqual(decode_rig(data,capture,31)['first_skeleton']['file_offset'],0x200)

    def test_flags_mismatch(self):
        data,capture=self.fixture()
        capture['flags']=1
        with self.assertRaisesRegex(ValueError,'flags differ'):
            decode_rig(data,capture,31)

    def test_overlay_mismatch(self):
        data,capture=self.fixture()
        with self.assertRaisesRegex(ValueError,'file ID'):
            decode_rig(data,capture,32)

    def test_segment_other_than_8(self):
        with self.assertRaisesRegex(ValueError,'separate overlay'):
            resolve_pointer(0x09000042,0x80100000,0x1000)

    def test_out_of_bounds(self):
        with self.assertRaisesRegex(ValueError,'outside'):
            resolve_pointer(0x08005000,0x80100000,0x1000)

if __name__=='__main__':unittest.main()
