"""Tests of original Goemon signed relative Skeleton child/sibling offsets."""
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rig_hierarchy import traverse_hierarchy


def fixture():
    data=bytearray(0x300)
    def bone(at,dlist,right,left,translation):
        struct.pack_into('>Ibb9h',data,at,dlist,right,left,
                         1,1,1,0,0,0,*translation)
    bone(0x120,0x08001200,1,0,(10,0,0))
    bone(0x138,0x08001400,0,1,(20,0,0))
    bone(0x150,0x08001600,1,0,(30,0,0))
    bone(0x168,0x08001800,0,0,(40,0,0))
    return data


class Tests(unittest.TestCase):
    def test_relative_child_and_sibling_logic(self):
        report=traverse_hierarchy(fixture(),0x120)
        self.assertEqual(report['node_count'],4)
        self.assertEqual([n['offset'] for n in report['nodes']],
                         [0x120,0x138,0x150,0x168])
        self.assertEqual([(e['from_offset'],e['to_offset'],e['relation'])
                          for e in report['edges']],
                         [(0x120,0x138,'child'),(0x120,0x150,'sibling'),
                          (0x150,0x168,'child')])
        self.assertEqual(report['nodes'][3]['translation_raw'],[40,0,0])

    def test_loop_rejected(self):
        data=fixture()
        struct.pack_into('>b',data,0x138+4,-1)
        with self.assertRaisesRegex(ValueError,'cycle'):
            traverse_hierarchy(data,0x120)

    def test_bad_root_alignment(self):
        with self.assertRaisesRegex(ValueError,'aligned'):
            traverse_hierarchy(fixture(),0x121)

    def test_node_limit(self):
        with self.assertRaisesRegex(ValueError,'limit'):
            traverse_hierarchy(fixture(),0x120,max_nodes=2)

    def test_negative_child_reference(self):
        data=fixture()
        struct.pack_into('>b',data,0x150+4,-2)
        with self.assertRaisesRegex(ValueError,'cycle'):
            traverse_hierarchy(data,0x120)


if __name__=='__main__':
    unittest.main()
