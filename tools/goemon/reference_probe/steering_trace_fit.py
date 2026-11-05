#!/usr/bin/env python3
"""Validate original 0.336-ground/0.300-air full-speed steering from NG5E.

Only consecutive, same-character, full-speed original action pairs qualify.
The destination root yaw is observed; camera->yaw and partial-stick handling
remain unresolved. These tools do not require or export ROM/assets.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import struct
import sys

SPEED = 2.8
COEFFICIENTS = {"ground": 0.336, "air": 0.300}
AIR_ACTIONS = {23,25,26,28}

def read_capture(reference: Path, log: Path) -> list[dict]:
    keys = ("sample","game_frames","character_id","action_id",
            "root_rot_y","stick_raw_x","stick_raw_y")
    with reference.open(encoding="utf-8-sig",newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not set(keys).issubset(reader.fieldnames):
            raise ValueError("missing original reference fields for steering")
        rows = [{key:int(entry[key]) for key in keys} for entry in reader]
    if not rows or any(row["sample"]!=i for i,row in enumerate(rows)):
        raise ValueError("empty or out-of-order original reference")
    n=0
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        index=line.find("GOEMON_TASK,")
        if index<0: continue
        fields=line[index+len("GOEMON_TASK,"):].strip().split(",")
        if len(fields)!=5 or int(fields[0])!=n or n>=len(rows):
            raise ValueError("misordered original PlayerTask sample")
        original=bytes.fromhex(fields[4])
        if len(original)!=240:
            raise ValueError("invalid original PlayerTask 240-byte record")
        row=rows[n]
        if int(fields[2])!=row["character_id"] or int(fields[3])!=row["action_id"]:
            raise ValueError("original PlayerTask character/action disagreement")
        row["vx"]=struct.unpack_from(">f",original,0x68)[0]
        row["vz"]=struct.unpack_from(">f",original,0x70)[0]
        row["speed"]=math.hypot(row["vx"],row["vz"])
        if not math.isfinite(row["speed"]):
            raise ValueError("nonfinite original vector")
        n+=1
    if n!=len(rows):
        raise ValueError(f"incomplete original PlayerTask capture: {n}/{len(rows)}")
    return rows

def classify(previous:dict,current:dict)->str|None:
    if (current["game_frames"]-previous["game_frames"]!=1 or
        current["character_id"]!=previous["character_id"] or
        max(abs(current["stick_raw_x"]),abs(current["stick_raw_y"]))<15 or
        abs(current["speed"]-SPEED)>0.001 or
        abs(previous["speed"]-SPEED)>0.001):
        return None
    if previous["action_id"]==current["action_id"]==15: return "ground"
    if previous["action_id"] in AIR_ACTIONS and current["action_id"] in AIR_ACTIONS:
        return "air"
    return None

def predicted(previous:dict,current:dict,coefficient:float)->tuple[float,float]:
    angle=(current["root_rot_y"]&1023)*2*math.pi/1024
    ux,uz=math.sin(angle),math.cos(angle)
    x=previous["vx"]/previous["speed"]+coefficient*ux
    z=previous["vz"]/previous["speed"]+coefficient*uz
    normal=math.hypot(x,z)
    if normal<0.000001: raise ValueError("steering vector cancelled")
    return SPEED*x/normal, SPEED*z/normal

def infer_coefficient(previous:dict,current:dict)->float|None:
    angle=(current["root_rot_y"]&1023)*2*math.pi/1024
    ux,uz=math.sin(angle),math.cos(angle)
    px,pz=previous["vx"]/previous["speed"],previous["vz"]/previous["speed"]
    cross_prev=current["vx"]*pz-current["vz"]*px
    cross_target=current["vx"]*uz-current["vz"]*ux
    if abs(cross_target)<0.001: return None
    return -cross_prev/cross_target

def analyze(rows:list[dict])->dict:
    groups={"ground":[],"air":[]}
    estimates={"ground":[],"air":[]}
    for index in range(1,len(rows)):
        previous,current=rows[index-1],rows[index]
        phase=classify(previous,current)
        if phase is None:continue
        predicted_x,predicted_z=predicted(previous,current,COEFFICIENTS[phase])
        error=math.hypot(predicted_x-current["vx"],predicted_z-current["vz"])
        groups[phase].append({
            "sample":index,"character_id":current["character_id"],
            "previous_action":previous["action_id"],"action":current["action_id"],
            "root_yaw":current["root_rot_y"],"velocity_error":error
        })
        estimate=infer_coefficient(previous,current)
        if estimate is not None: estimates[phase].append(estimate)
    return {
        "recording_samples":len(rows),
        "qualifying_full_speed_pairs":sum(map(len,groups.values())),
        "formula":"2.8 * normalize(normalize(previous_velocity) + k * yaw_direction)",
        "phase_results":{
            phase:{
                "k":COEFFICIENTS[phase],
                "pairs":len(points),
                "within_0_000002":sum(p["velocity_error"]<0.000002 for p in points),
                "maximum_velocity_error":max((p["velocity_error"] for p in points),default=None),
                "direct_inference_count":len(estimates[phase]),
                "direct_inference_median":statistics.median(estimates[phase]) if estimates[phase] else None,
                "by_character":{str(c):sum(p["character_id"]==c for p in points) for c in range(4)},
                "examples":points[:8],
            } for phase,points in groups.items()
        },
        "limitation":"Only full-speed, original action-gated, observed-yaw steering. No camera target, partial analog, unknown actions or world collision claim."
    }

def main(argv=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference_csv",type=Path)
    parser.add_argument("runtime_log",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    try:
        result=json.dumps(analyze(read_capture(args.reference_csv,args.runtime_log)),indent=2)+"\n"
        if args.output:args.output.write_text(result,encoding="utf-8")
        else:print(result,end="")
    except (ValueError,OSError) as ex:
        print(f"ERROR: {ex}",file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    sys.exit(main())
