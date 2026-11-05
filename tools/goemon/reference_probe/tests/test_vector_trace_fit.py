"""Original 0.3-drag / 0.84-target vector dynamics synthetic regression."""
from __future__ import annotations
import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from vector_trace_fit import analyze,classify,predict

def sample(frame,ch,action,yaw,speed,stick=93,prior_stick=93):
    angle=(yaw&1023)*math.tau/1024
    return {
        "sample":frame,"game_frames":frame+100,"character_id":ch,
        "action_id":action,"root_rot_y":yaw,"stick_raw_x":stick,
        "stick_raw_y":0,"vx":speed*math.sin(angle),
        "vz":speed*math.cos(angle),"speed":speed
    }

class OriginalVectorTraceTests(unittest.TestCase):
    def test_ground_start_and_continuous_direction(self):
        idle=sample(0,0,0,200,0)
        start=sample(1,0,13,200,.7)
        self.assertEqual(classify(idle,start),"ground_start")
        self.assertAlmostEqual(predict(idle,start,"ground_start")[0],start["vx"])
        update=sample(2,0,15,220,1.24)
        px,pz=predict(start,update,"ground_acceleration")
        update["vx"],update["vz"]=px,pz
        update["speed"]=math.hypot(px,pz)
        result=analyze([idle,start,update])
        self.assertEqual(result["qualified_original_transitions"],2)
        self.assertEqual(result["direction_matches_within_0_000002"],2)
        self.assertEqual(result["speed_matches_within_0_012"],2)

    def test_air_turn_reset_and_continuation(self):
        previous=sample(0,2,23,616,1.68,62)
        turned=sample(1,2,23,486,.84,93)
        self.assertEqual(classify(previous,turned),"air_turn_reset")
        tx,tz=predict(previous,turned,"air_turn_reset")
        self.assertAlmostEqual(tx,turned["vx"])
        turned["vx"],turned["vz"]=tx,tz
        turned["speed"]=math.hypot(tx,tz)
        ongoing=sample(2,2,23,485,1.68,93)
        ongoing["vx"],ongoing["vz"]=predict(turned,ongoing,"air_acceleration")
        ongoing["speed"]=math.hypot(ongoing["vx"],ongoing["vz"])
        result=analyze([previous,turned,ongoing])
        self.assertEqual(result["phases"]["air_turn_reset"]["count"],1)
        self.assertEqual(result["phases"]["air_acceleration"]["count"],1)
        self.assertEqual(result["direction_matches_within_0_000002"],2)

    def test_sharp_turn_deceleration_sample_35_to_36(self):
        # Actual NG5E sample 35 -> 36, character 2.
        # Old magnitude-only model wrongly snapped speed back to 2.8.
        prev=sample(0,2,15,865,2.8)
        prev["vx"],prev["vz"]=-0.7351038455963135,2.7017815113067627
        prev["speed"]=math.hypot(prev["vx"],prev["vz"])
        cur=sample(1,2,15,743,2.7250822678786526)
        cur["vx"],cur["vz"]=-1.4864791631698608,2.2839555740356445
        cur["speed"]=math.hypot(cur["vx"],cur["vz"])
        px,pz=predict(prev,cur,"ground_acceleration")
        self.assertLess(math.hypot(px-cur["vx"],pz-cur["vz"]),0.000001)
        self.assertLess(math.hypot(px,pz),2.8)
        result=analyze([prev,cur])
        self.assertEqual(result["direction_matches_within_0_001"],1)
        self.assertEqual(result["vector_matches_within_0_000002"],1)
        self.assertEqual(result["speed_matches_within_0_012"],1)
        self.assertEqual(result["phases"]["ground_acceleration"]["exceptions"],[])

    def test_discontinuous_actions_and_unknowns_excluded(self):
        a=sample(0,0,15,0,2.8)
        b=sample(1,0,162,0,2.8)
        self.assertIsNone(classify(a,b))
        self.assertIsNone(classify(a,dict(b,action_id=15,game_frames=500)))
        self.assertIsNone(classify(a,dict(b,action_id=15,character_id=2)))

if __name__=="__main__":
    unittest.main()
