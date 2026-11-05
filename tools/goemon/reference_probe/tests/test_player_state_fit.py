"""Regression for correlations of original opaque Player memory offsets."""
from __future__ import annotations
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from memory_candidates import parse_log
from player_state_fit import analyze_samples

class PlayerStateFitTests(unittest.TestCase):
    @staticmethod
    def record(i:int,action:int,character:int=0,mode:int=2,marker:int=0,phase:int=0)->str:
        raw=bytearray(0x1C0)
        raw[0x18]=mode;raw[0x69]=marker;raw[0x2c]=phase
        return f"GOEMON_MEM,{i},{i},{character},{action},0,0,0,{raw.hex()}"

    def test_jump_mode_and_character_switch_marker(self):
        rows=[
            self.record(0,0,0,2,0),
            self.record(4,23,0,0,0),
            self.record(8,25,0,0,0),
            self.record(12,26,1,0,0),
            self.record(16,28,1,2,0),
            self.record(20,186,1,2,1),
            self.record(24,186,1,2,0),
            self.record(28,0,1,2,0),
        ]
        result=analyze_samples(parse_log("\n".join(rows)))
        self.assertEqual(result["samples"],8)
        self.assertEqual(result["normal_jump_samples"],3)
        self.assertEqual(result["other_action_samples"],5)
        self.assertEqual(
            result["measured_fields"]["jump_mode_byte_0x18"]
                  ["matches_observed_jumping_zero_other_two"],8
        )
        state=result["measured_fields"]["character_switch_marker_0x69"]
        self.assertEqual(state["marked_during_character_change"],1)
        self.assertEqual(state["marked_outside_character_change"],0)
        self.assertEqual(result["by_character"],{"0":3,"1":5})

    def test_mismatch_does_not_become_proven_state(self):
        rows=[
            self.record(0,23,mode=2),
            self.record(4,15,mode=0),
        ]
        result=analyze_samples(parse_log("\n".join(rows)))
        field=result["measured_fields"]["jump_mode_byte_0x18"]
        self.assertEqual(field["matches_observed_jumping_zero_other_two"],0)

if __name__=="__main__":
    unittest.main()
