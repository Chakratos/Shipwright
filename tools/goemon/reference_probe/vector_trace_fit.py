#!/usr/bin/env python3
"""Validate original acceleration direction and magnitude across game updates.

Original ground vector: (speed-0.30)*prevUnit + 0.84*targetYaw.
Original airborne vector: speed*prevUnit + 0.84*targetYaw.
Direction is normalized; scalar speeds advance 0.54 (ground) or
0.84 (air) subject to 2.8 cap. Exceptions are reported, not omitted.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import sys
from steering_trace_fit import read_capture

PHASES=("ground_start","ground_acceleration","air_acceleration","air_turn_reset")

def classify(a:dict,b:dict)->str|None:
    if b["game_frames"]-a["game_frames"]!=1 or a["character_id"]!=b["character_id"]:
        return None
    if max(abs(b["stick_raw_x"]),abs(b["stick_raw_y"]))<15:
        return None
    changed=(a["stick_raw_x"],a["stick_raw_y"])!=(b["stick_raw_x"],b["stick_raw_y"])
    if b["action_id"]==13 and a["speed"]<.01:
        return "ground_start"
    if b["action_id"]==15 and a["action_id"] in (13,15) and a["speed"]>.30001:
        return "ground_acceleration"
    if b["action_id"] in (23,25,26) and a["action_id"]==b["action_id"] and changed:
        return "air_turn_reset"
    if b["action_id"] in (23,25,26) and a["action_id"] in (23,25,26) and not changed and a["speed"]>.00001:
        return "air_acceleration"
    return None

def predict(a:dict,b:dict,phase:str)->tuple[float,float]:
    yaw=(b["root_rot_y"]&1023)*math.tau/1024
    target_x,target_z=math.sin(yaw),math.cos(yaw)
    if phase=="ground_start":return .7*target_x,.7*target_z
    if phase=="air_turn_reset":return .84*target_x,.84*target_z
    retain=a["speed"]-(.3 if phase=="ground_acceleration" else 0.0)
    vx=retain*a["vx"]/a["speed"]+.84*target_x
    vz=retain*a["vz"]/a["speed"]+.84*target_z
    magnitude=math.hypot(vx,vz)
    if magnitude<.000001:raise ValueError("cancelled original direction")
    predicted_speed=min(2.8,a["speed"]+(.54 if phase=="ground_acceleration" else .84))
    return predicted_speed*vx/magnitude,predicted_speed*vz/magnitude

def analyze(rows:list[dict])->dict:
    records={name:[] for name in PHASES}
    for i in range(1,len(rows)):
        prior,current=rows[i-1],rows[i]
        phase=classify(prior,current)
        if phase is None:continue
        x,z=predict(prior,current,phase)
        predicted_speed=math.hypot(x,z)
        actual_speed=current["speed"]
        direction_error=math.hypot(x/predicted_speed-current["vx"]/actual_speed,
                                   z/predicted_speed-current["vz"]/actual_speed)
        records[phase].append({
            "sample":i,"character_id":current["character_id"],
            "vector_error":math.hypot(x-current["vx"],z-current["vz"]),
            "direction_error":direction_error,
            "speed_error":actual_speed-predicted_speed,
        })
    results={}
    for name,group in records.items():
        results[name]={
            "count":len(group),
            "direction_within_0_000002":sum(x["direction_error"]<2e-6 for x in group),
            "direction_within_0_001":sum(x["direction_error"]<.001 for x in group),
            "speed_within_0_012":sum(abs(x["speed_error"])<.012 for x in group),
            "maximum_direction_error":max((x["direction_error"] for x in group),default=None),
            "maximum_abs_speed_error":max((abs(x["speed_error"]) for x in group),default=None),
            "by_character":{str(character):sum(x["character_id"]==character for x in group) for character in range(4)},
            "exceptions":[
                {"sample":r["sample"],"character_id":r["character_id"],
                 "speed_error":r["speed_error"],"direction_error":r["direction_error"]}
                for r in group if abs(r["speed_error"])>=.012 or r["direction_error"]>=.001
            ],
        }
    return {
        "capture_samples":len(rows),
        "qualified_original_transitions":sum(v["count"] for v in results.values()),
        "direction_matches_within_0_001":sum(v["direction_within_0_001"] for v in results.values()),
        "direction_matches_within_0_000002":sum(v["direction_within_0_000002"] for v in results.values()),
        "speed_matches_within_0_012":sum(v["speed_within_0_012"] for v in results.values()),
        "phases":results,
        "limitations":"Only tested original action and analog cases. One speed exception and one sub-millidegree start difference are preserved; no guessed landing/camera/partial-stick code.",
    }

def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("reference_csv",type=Path)
    p.add_argument("runtime_log",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args(argv)
    try:
        result=json.dumps(analyze(read_capture(a.reference_csv,a.runtime_log)),indent=2)+"\n"
        if a.output:a.output.write_text(result,encoding="utf-8")
        else:print(result,end="")
    except (OSError,ValueError) as err:
        print(f"ERROR: {err}",file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":sys.exit(main())
