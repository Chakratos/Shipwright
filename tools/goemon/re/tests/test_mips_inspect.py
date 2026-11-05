"""Synthetic tests for the original MIPS player instruction inspector."""
import struct
import sys
from pathlib import Path
import tomllib
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mips_inspect import decode, find_function, inspect, sign16

TEST_TABLE=tomllib.loads('''[[section]]
name = ".file_11"
rom = 0x40
vram = 0x801cb460
size = 0x200
functions = [ { name="candidate", vram=0x801cb460, size=0x20 } ]
''')

class Tests(unittest.TestCase):
    def test_signed(self):
        self.assertEqual(sign16(0xffff),-1)
        self.assertEqual(sign16(0x8000),-32768)

    def test_player_field_candidate(self):
        x=decode(0x801cb460,0x920800cc)
        self.assertEqual(x['candidate_field'],'PlayerTask.action_id')
        self.assertTrue(x['field_unconfirmed'])

    def test_jal(self):
        word=0x0c000000 | ((0x801daf54>>2)&0x03ffffff)
        self.assertEqual(decode(0x801cb464,word)['target'],'0x801DAF54')

    def test_branch(self):
        x=decode(0x801cb460,0x1109fffe)
        self.assertEqual(x['target'],'0x801CB45C')

    def test_cop1(self):
        x=decode(0x801cb460,0x46031080)
        self.assertEqual(x['mnemonic'],'add.s')

    def test_real_byte_offsets(self):
        rom=bytearray(0x300)
        rom[:4]=b'\x80\x37\x12\x40'
        for i,word in enumerate([
            0x920800cc,0x8E02005C,
            0x0c000000 | ((0x801daf54>>2)&0x03ffffff),
            0,0,0,0,0,
        ]):
            struct.pack_into('>I',rom,0x40+i*4,word)
        rep=inspect(bytes(rom),TEST_TABLE,'candidate')
        self.assertEqual(len(rep['instructions']),8)
        self.assertEqual(len(rep['field_candidates']),2)
        self.assertEqual(rep['direct_calls'],['0x801DAF54'])

    def test_invalid(self):
        with self.assertRaisesRegex(ValueError,'big-endian'):
            inspect(b'\0'*512,TEST_TABLE,'candidate')
        with self.assertRaisesRegex(ValueError,'unknown function'):
            find_function(TEST_TABLE,'missing')

if __name__=='__main__': unittest.main()
