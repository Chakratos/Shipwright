#!/usr/bin/env python3
"""Summarize LIVE original Goemon AnimatedSkeleton ownership from mod logs.

Consumes GOEMON_ANIM_OWNER / GOEMON_ANIM_ACTIVE /
GOEMON_ANIM_MATRIX_CURSOR emitted by diagnostic_mod. These records
are addresses and metadata only, not source ROM/model/matrix contents.

A valid matched active pointer from the running original recomp is
evidence of actual player Object.animation ownership. It is NOT
proof of correctly animated numeric bone poses until per-frame source
matrix changes are independently checked.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

PREFIXES=("GOEMON_ANIM_OWNER,","GOEMON_ANIM_ACTIVE,",
          "GOEMON_ANIM_MATRIX_CURSOR,")


def read_capture_event(line:str):
    for prefix in PREFIXES:
        idx=line.find(prefix)
        if idx<0:
            continue
        data=line[idx+len(prefix):].strip().split(",")
        if prefix==PREFIXES[0] and len(data)==10:
            frame,char,action=(int(n) for n in data[:3])
            pointers=tuple(int(n,16) for n in data[3:])
            return ("owner",(frame,char,action,*pointers))
        if prefix==PREFIXES[1] and len(data)==7:
            frame,char,action=(int(n) for n in data[:3])
            obj,active,stack=(int(n,16) for n in data[3:6])
            progress=float(data[6])
            return ("active",(frame,char,action,obj,active,stack,progress))
        if prefix==PREFIXES[2] and len(data)==7:
            frame,char,action=(int(n) for n in data[:3])
            ptr,before,after=(int(n,16) for n in data[3:6])
            delta=int(data[6])
            return ("matrix_cursor",(frame,char,action,ptr,before,after,delta))
        raise ValueError(f"malformed {prefix.rstrip(',')} event")
    return None


def analyze_live_owner_events(lines,*,log_sha256:str|None=None)->dict:
    current_owner_by_object={}
    counts=Counter()
    active_linked=0
    mismatched=0
    events_by_action=defaultdict(lambda:{
        "owner_records":0,"active_records":0,"resolved_pointer_matches":0,
        "source_animation_pointers":set(),"graphics_tagged_pointers":set(),
        "original_animation_progress":set(),"matrix_push_bytes":Counter()
    })
    for original_line in lines:
        event=read_capture_event(original_line)
        if event is None:
            continue
        kind,p=event
        frame,char,action=p[:3]
        if not (0<=frame<1_000_000_000 and 0<=char<4 and 0<=action<256):
            raise ValueError("invalid original game player action identity")
        group=events_by_action[(char,action)]
        counts[kind]+=1
        if sum(counts.values())>1_000_000:
            raise ValueError("original live owner trace exceeds event budget")
        if kind=="owner":
            (_,_,_,obj,graphics,owner,flags,raw_animation,
             resolved_animation,root_skeleton)=p
            if obj==0 or owner==0 or (graphics&0x70000000)!=0x60000000:
                raise ValueError("invalid active original 0x60000000 player owner")
            current_owner_by_object[obj]=(char,action,resolved_animation)
            group["owner_records"]+=1
            group["source_animation_pointers"].add(f"0x{resolved_animation:08X}")
            group["graphics_tagged_pointers"].add(f"0x{graphics:08X}")
        elif kind=="active":
            (_,_,_,obj,active,stack,progress)=p
            if not math.isfinite(progress) or abs(progress)>1e7:
                raise ValueError("invalid original animation progress")
            group["active_records"]+=1
            group["original_animation_progress"].add(progress)
            owner=current_owner_by_object.get(obj)
            if owner is not None:
                if owner[0]==char and owner[1]==action and owner[2]==active:
                    active_linked+=1
                    group["resolved_pointer_matches"]+=1
                else:
                    mismatched+=1
        else:
            (_,_,_,node,before,after,delta)=p
            if node==0 or delta<0 or delta>4096 or after-before!=delta:
                raise ValueError("invalid original N64 matrix-stack push metadata")
            group["matrix_push_bytes"][delta]+=1
    summary=[]
    for (char,action),item in sorted(events_by_action.items()):
        summary.append({
            "character_slot":char,"source_action_id":action,
            "owner_records":item["owner_records"],
            "active_records":item["active_records"],
            "live_animation_pointer_matches":item["resolved_pointer_matches"],
            "distinct_resolved_source_animation_pointers":sorted(
                item["source_animation_pointers"]),
            "distinct_source_tagged_graphics":sorted(
                item["graphics_tagged_pointers"]),
            "distinct_source_animation_progress_count":len(
                item["original_animation_progress"]),
            "source_animation_progress_range":(
                [min(item["original_animation_progress"]),
                 max(item["original_animation_progress"])]
                if item["original_animation_progress"] else None),
            "original_matrix_push_bytes":dict(sorted(
                item["matrix_push_bytes"].items())),
        })
    return {
        "schema":"goemon-original-live-animation-owner-trace-v1",
        "source_original_game_runtime_capture":True,
        "original_log_sha256":log_sha256,
        "owner_events":counts["owner"],
        "active_player_events":counts["active"],
        "matrix_stack_push_events":counts["matrix_cursor"],
        "matched_resolved_owner_to_engine_animation_pointer":active_linked,
        "mismatched_engine_animation_pointers":mismatched,
        "verified_live_original_animation_pointer":active_linked>0,
        "verified_numerically_moving_original_bone_matrix":False,
        "verified_real_playback_in_ship":False,
        "characters_actions":summary,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("log",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args(argv)
    try:
        root=Path(__file__).resolve().parents[3]
        if a.output is not None:
            target=a.output.resolve()
            if target==root or root in target.parents:
                raise ValueError("original game runtime logs/metadata cannot be saved in Git")
        raw=a.log.read_bytes()
        if len(raw)>128*1024*1024:
            raise ValueError("source runtime trace larger than 128 MiB")
        result=analyze_live_owner_events(
            raw.decode("utf-8",errors="replace").splitlines(),
            log_sha256=hashlib.sha256(raw).hexdigest())
        serialized=json.dumps(result,indent=2)+"\n"
        if a.output is not None:
            a.output.parent.mkdir(parents=True,exist_ok=True)
            a.output.write_text(serialized,encoding="utf-8")
        print("GOEMON_LIVE_ANIMATION_OWNER "+json.dumps({
            key:result[key] for key in (
                "owner_events","active_player_events","matrix_stack_push_events",
                "matched_resolved_owner_to_engine_animation_pointer",
                "mismatched_engine_animation_pointers",
                "verified_live_original_animation_pointer"
            )},separators=(",",":")))
    except (OSError,ValueError,TypeError,UnicodeError) as error:
        print("GOEMON_LIVE_ANIMATION_OWNER FAILED:",error,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
