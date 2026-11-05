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
        ongoing=sample(2,2,23,485,1.68,93)
        ongoing["vx"],ongoing["vz"]=predict(turned,ongoing,"air_acceleration")
        result=analyze([previous,turned,ongoing])
        self.assertEqual(result["phases"]["air_turn_reset"]["count"],1)
        self.assertEqual(result["phases"]["air_acceleration"]["count"],1)
        self.assertEqual(result["direction_matches_within_0_000002"],2)

    def test_speed_exception_is_not_hidden(self):
        prev=sample(0,3,15,700,2.8)
        cur=sample(1,3,15,620,2.725)
        direction=predict(prev,cur,"ground_acceleration")
        norm=math.hypot(*direction)
        cur["vx"],cur["vz"]=tuple(v*2.725/norm for v in direction)
        result=analyze([prev,cur])
        self.assertEqual(result["direction_matches_within_0_001"],1)
        self.assertEqual(result["speed_matches_within_0_012"],0)
        self.assertEqual(len(result["phases"]["ground_acceleration"]["exceptions"]),1)

    def test_discontinuous_actions_and_unknowns_excluded(self):
        a=sample(0,0,15,0,2.8)
        b=sample(1,0,162,0,2.8)
        self.assertIsNone(classify(a,b))
        self.assertIsNone(classify(a,dict(b,action_id=15,game_frames=500)))
        self.assertIsNone(classify(a,dict(b,action_id=15,character_id=2)))

if __name__=="__main__":
    unittest.main()
