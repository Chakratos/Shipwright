"""Tests for reverse-engineered Goemon N64 skeleton record layouts."""
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from skeleton_inspect import parse_skeleton,parse_animated_skeleton

class Tests(unittest.TestCase):
    def test_original_skeleton_record_24_bytes(self):
        data=struct.pack('>Ibb9h',0x08001234,-1,2,100,200,-300,1000,-2000,32767,4,5,-6)
        self.assertEqual(len(data),24)
        x=parse_skeleton(data,0)
        self.assertEqual(x['display_list_pointer'],'0x08001234')
        self.assertEqual(x['offset_right'],-1)
        self.assertEqual(x['offset_left'],2)
        self.assertEqual(x['scale_raw'],[100,200,-300])
        self.assertEqual(x['rotation_raw'],[1000,-2000,32767])
        self.assertEqual(x['translation_raw'],[4,5,-6])

    def test_animation_flags_from_original_renderer(self):
        flags=0x80000000 | (3<<28) | (2<<24) | (42<<8) | 9
        data=b'X'*4+struct.pack('>IIII',flags,0x08001200,0x08003000,0x80004000)
        p=parse_animated_skeleton(data,4,2)
        self.assertEqual(p['limb_count'],42)
        self.assertEqual(p['base_transforms'],3)
        self.assertEqual(p['additional_transforms'],2)
        self.assertEqual(p['animation_parameter_low_byte'],9)
        self.assertEqual(p['skeleton_pointers'],['0x08003000','0x80004000'])
        self.assertTrue(p['high_bit_flag'])

    def test_bounds(self):
        with self.assertRaisesRegex(ValueError,'out of bounds'):
            parse_skeleton(b'\0'*23,0)
        with self.assertRaisesRegex(ValueError,'out of bounds'):
            parse_animated_skeleton(b'\0'*11,0)
        with self.assertRaisesRegex(ValueError,'pointer count'):
            parse_animated_skeleton(b'\0'*100,0,0)

if __name__=='__main__':unittest.main()
