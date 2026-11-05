"""Four-character original steering ratios: synthetic MIPS PlayerTask replay."""
from __future__ import annotations
import csv
import math
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from steering_trace_fit import read_capture, analyze, classify

class SteeringTraceFitTests(unittest.TestCase):
    def make_run(self, folder:Path, fail_last_task:bool=False):
        reference=folder/"reference.csv"
        raw=folder/"runtime.log"
        rows=[]
        log=[]
        for character in range(4):
            for phase,coefficient,action in (("ground",0.336,15),("air",0.300,23)):
                yaw=100+character*210
                theta=(yaw&1023)*math.pi*2/1024
                vx,vz=2.8*math.sin(theta),2.8*math.cos(theta)
                for step in range(4):
                    if step: yaw+=13
                    if step:
                        target=(yaw&1023)*2*math.pi/1024
                        mx=vx/2.8+coefficient*math.sin(target)
                        mz=vz/2.8+coefficient*math.cos(target)
                        length=math.hypot(mx,mz)
                        vx,vz=2.8*mx/length,2.8*mz/length
                    index=len(rows)
                    rows.append({
                        "sample":index,"game_frames":index+10,"character_id":character,
                        "action_id":action,"root_rot_y":yaw,
                        "stick_raw_x":93,"stick_raw_y":0
                    })
                    buffer=bytearray(0xF0)
                    struct.pack_into(">f",buffer,0x68,vx)
                    struct.pack_into(">f",buffer,0x70,vz)
                    log.append(f"GOEMON_TASK,{index},{index+10},{character},{action},{buffer.hex()}")
        with reference.open("w",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        if fail_last_task:log.pop()
        raw.write_text("\n".join(log)+"\n",encoding="utf-8")
        return reference,raw

    def test_exact_two_source_measured_ratios_all_four(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=self.make_run(Path(folder))
            report=analyze(read_capture(*paths))
        self.assertEqual(report["qualifying_full_speed_pairs"],24)
        for phase,coefficient in (("ground",0.336),("air",0.300)):
            outcome=report["phase_results"][phase]
            self.assertEqual(outcome["pairs"],12)
            self.assertEqual(outcome["within_0_000002"],12)
            self.assertLess(outcome["maximum_velocity_error"],0.000002)
            self.assertAlmostEqual(outcome["direct_inference_median"],coefficient,places=5)
            self.assertEqual(sorted(outcome["by_character"].values()),[3]*4)

    def test_reject_missing_and_mismatched_task(self):
        with tempfile.TemporaryDirectory() as folder:
            reference,raw=self.make_run(Path(folder),fail_last_task=True)
            with self.assertRaisesRegex(ValueError,"incomplete"):
                read_capture(reference,raw)

    def test_unknown_actions_and_gaps_are_not_fitted(self):
        previous={"game_frames":100,"character_id":1,"stick_raw_x":93,
                  "stick_raw_y":0,"speed":2.8,"action_id":15}
        current=dict(previous,game_frames=101)
        self.assertEqual(classify(previous,current),"ground")
        self.assertIsNone(classify(previous,dict(current,game_frames=300)))
        self.assertIsNone(classify(previous,dict(current,action_id=162)))
        self.assertIsNone(classify(previous,dict(current,character_id=3)))
        self.assertIsNone(classify(previous,dict(current,speed=1.8)))
        self.assertIsNone(classify(previous,dict(current,stick_raw_x=0)))

if __name__=="__main__":
    unittest.main()
