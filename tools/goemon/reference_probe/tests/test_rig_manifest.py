"""Tests for original animated-skeleton pointer capture manifests."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rig_manifest import parse_log

class Tests(unittest.TestCase):
    def test_rig_addresses_preserved_exactly(self):
        line='[goemon] GOEMON_RIG,12,3,18,68000001,812A0080,0800F00D,08000304,80200000,001f'
        output=parse_log([line])
        self.assertEqual(len(output['rig_captures']),1)
        entry=output['rig_captures'][0]
        self.assertEqual(entry['character_id'],3)
        self.assertEqual(entry['graphics_pointer'],0x68000001)
        self.assertEqual(entry['flags'],0x812a0080)
        self.assertEqual(entry['skeleton_pointer'],0x08000304)
        self.assertEqual(entry['overlay_zero_file_id'],0x1f)

    def test_unresolved_and_frame_order(self):
        data=parse_log(['GOEMON_RIG_UNRESOLVED,0,1,40000000'])
        self.assertEqual(data['unresolved_captures'][0]['graphics_pointer'],0x40000000)
        with self.assertRaisesRegex(ValueError,'out-of-order'):
            parse_log(['GOEMON_RIG,2,0,0,1,2,3,4,5,0',
                       'GOEMON_RIG,1,0,0,1,2,3,4,5,0'])

    def test_bad_field_count(self):
        with self.assertRaisesRegex(ValueError,'9 fields'):
            parse_log(['GOEMON_RIG,1,2'])

if __name__=='__main__':unittest.main()
