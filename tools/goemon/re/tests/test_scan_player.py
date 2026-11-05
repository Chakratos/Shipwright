"""Synthetic ROM tests for the overlay-wide original Player writer scanner."""
import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scan_player import analyze


def synthetic_rom():
    data=bytearray(0x300)
    data[:4]=b'\x80\x37\x12\x40'
    struct.pack_into('>II',data,0x10,0x9cc11f4b,0xabaa8538)
    words=[0x3c088020,0x8d08c604,0x8d0a005c,0xe54c0010,
           0x910b00cc,0xa10b00cc,0,0]
    for i,word in enumerate(words):
        struct.pack_into('>I',data,0x40+i*4,word)
    return bytes(data)


def symbols():
    return {'section':[{'name':'.file_11','rom':0x40,
        'vram':0x801cb460,'size':0x100,
        'functions':[{'name':'player_state_writer','vram':0x801cb460,'size':32},
                     {'name':'no_access','vram':0x801cb480,'size':32}]}]}


class Tests(unittest.TestCase):
    def test_player_writer_recognized(self):
        r=analyze(synthetic_rom(),symbols())
        self.assertEqual(r['functions_scanned'],2)
        self.assertEqual(r['functions_with_evidence'],1)
        self.assertEqual(r['candidates'][0]['name'],'player_state_writer')
        self.assertEqual(r['accesses_by_field']['Player+0x010'],1)
        self.assertEqual(r['accesses_by_field']['action_id'],2)
        self.assertGreater(r['candidates'][0]['priority_score'],100)

    def test_crc_rejected(self):
        b=bytearray(synthetic_rom())
        b[0x10]=0
        with self.assertRaisesRegex(ValueError,'CRC'):
            analyze(bytes(b),symbols())

    def test_bad_rom_function(self):
        s=symbols()
        s['section'][0]['functions'][0]['vram']=0x801cb760
        with self.assertRaisesRegex(ValueError,'outside ROM section'):
            analyze(synthetic_rom(),s)

    def test_max_results_validation(self):
        with self.assertRaisesRegex(ValueError,'positive'):
            analyze(synthetic_rom(),symbols(),max_results=0)

    def test_zero_player_provenance_gives_no_candidate(self):
        b=bytearray(synthetic_rom())
        b[0x44:0x48]=b'\x00\x00\x00\x00'
        r=analyze(bytes(b),symbols())
        self.assertEqual(r['functions_with_evidence'],0)

    def test_call_to_known_entrypoint_is_candidate_even_without_access(self):
        b=bytearray(synthetic_rom())
        for i in range(8):
            struct.pack_into('>I',b,0x40+i*4,0)
        t=0x801cb800
        struct.pack_into('>I',b,0x40,0x0c000000|((t>>2)&0x03ffffff))
        r=analyze(bytes(b),symbols())
        self.assertEqual(r['functions_with_evidence'],1)
        self.assertEqual(r['candidates'][0]['priority_score'],2)


if __name__=='__main__':
    unittest.main()
