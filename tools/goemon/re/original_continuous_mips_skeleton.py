#!/usr/bin/env python3
"""Execute one continuous ORIGINAL N64 MIPS player-skeleton matrix stack.

Unlike independently executed sample probes, a single original MIPS CPU
and RDRAM survive every limb evaluation. The matrix stack destination
D_80168530 is restored to the source graph parent's depth before
evaluating a sibling; original MIPS code actually pushes its own 64-byte
MtxF. We do not invent interpolation or per-limb time.

This is an OFFLINE hypothesis of traversal: the complete native
func_80018CA0 player implementation has conditional 0x4000 pops,
object transitions and relative right/left recursion not yet modeled.
No game ROM, source MIPS words or resulting matrices leave owner PC.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_mips_vm import OriginalMipsCPU,MipsFault,bits32,f32
from probe_original_mips_execution import (
    original_source_catalog,choose_source_candidate,
    verified_decoded_original_rom,SOURCE,ACTOR,ENTRY
)
from source_aligned_character_assets import CHARACTER_NAMES
from real_rom_check import locate_rom
from verify_original_rig_animation_pair import parse_rig_descriptors

HEADERS=(0x14F30,0x1CF8,0x105B0,0x23F60)
BASE=0x80510000
PROGRESS=(0.0,1.0,4.0)


def build_source_stack_plan(nodes:list[dict])->list[dict]:
    if not 1<=len(nodes)<=128:
        raise ValueError("invalid source Skeleton node count")
    depths={}
    out=[]
    for node in nodes:
        ptr=node["ptr"]
        parent=node["parent"]
        if ptr in depths or ptr>>24!=7:
            raise ValueError("duplicate or unsegmented original source limb")
        if parent is None:
            depth=0
        elif parent in depths:
            depth=depths[parent]+1
        else:
            raise ValueError("unresolved source Skeleton graph parent")
        if depth>=120:
            raise ValueError("original source stack depth exceeded")
        depths[ptr]=depth
        out.append({"ptr":ptr,"parent":parent,
                    "depth":depth,"gfx":node["gfx"]})
    return out


def setup_original_n64_cpu(rom:bytes,slot:int,progress:float,
                           candidate:dict,banks:dict)->OriginalMipsCPU:
    decoded=verified_decoded_original_rom(rom)
    vm=OriginalMipsCPU()
    vm.copy(0x80000400,decoded[0x1000:0x81000])
    vm.copy(SOURCE,banks[7])
    vm.source_region=(SOURCE,SOURCE+len(banks[7]))
    anim=SOURCE+(int(candidate["original_animation_pointer"],16)&0xFFFFFF)
    flags=int(candidate["original_animated_skeleton_flags"],16)
    vm.store(0x801684A0,ACTOR)
    vm.store(0x801684F0,anim)
    vm.store(0x80168520,anim)
    vm.store(0x80168530,BASE)
    vm.put_float(0x80168510,progress)
    vm.put_float(0x80168514,0.0)
    vm.put_float(0x80168518,float(flags&255))
    vm.store(0x8016851C,(flags>>31)&1)
    for i in range(16):
        vm.store(0x801684B0+i*4,
                 bits32(1.0 if i%5==0 else 0.0))
    for axis in range(3):
        vm.put_float(ACTOR+0x1c+4*axis,1.0)
    vm.put_float(ACTOR+0x28,progress)
    return vm


def run_source_stack_sequence(rom:bytes,slot:int,progress:float,*,capture_private_matrices:bool=False)->dict:
    banks,candidates=original_source_catalog(rom,slot)
    record=choose_source_candidate(candidates,HEADERS[slot])
    plan=build_source_stack_plan(record["limbs"])
    vm=setup_original_n64_cpu(rom,slot,progress,record,banks)
    rows=[]
    failure=None
    output_stack_pointers={}
    for node in plan:
        if node["parent"] is None:
            original_destination=BASE
        else:
            original_destination=output_stack_pointers.get(node["parent"])
            if original_destination is None:
                raise ValueError("missing original source parent stack cursor")
        # Source renderer's right and left object transitions remain
        # unverified; preserve each parent's actual MIPS stack-end cursor.
        vm.store(0x80168530,original_destination)
        vm.r[4]=SOURCE+(node["ptr"]&0xFFFFFF)
        vm.r[5]=ACTOR
        vm.executed=0
        try:
            vm.run(ENTRY,budget=200000)
            after=vm.load(0x80168530)
            push_size=after-original_destination
            if push_size not in (64,128):
                raise MipsFault(
                    "unsupported source MIPS stack push delta "+
                    str(push_size)+" at limb "+f"0x{node['ptr']:08X}")
            # Use the final MtxF before next push as a candidate
            # display-list draw matrix. The original renderer's
            # conditional intermediate pop still requires verification.
            draw_slot=after-64
            words=[vm.load(draw_slot+4*i) for i in range(16)]
            if any(not math.isfinite(f32(w)) for w in words):
                raise MipsFault("original MIPS output matrix contains nonfinite values")
            digest=hashlib.sha256(b"".join(
                (0 if (v&0x7FFFFFFF)==0 else v).to_bytes(4,"big")
                for v in words)).hexdigest()[:16]
            output_stack_pointers[node["ptr"]]=after
            item={
                "ptr":node["ptr"],"gfx":node["gfx"],"depth":node["depth"],
                "source_original_mips_matrix_digest":digest,
                "original_mips_stack_push_bytes":push_size,
                "mips_instructions":vm.executed,
            }
            if capture_private_matrices:
                item["private_original_mips_matrix_words"]=words
            rows.append(item)
        except (MipsFault,ValueError,TypeError,OverflowError) as e:
            failure=str(e)
            break
    return {
        "character":CHARACTER_NAMES[slot],
        "progress":progress,
        "source_descriptors_requested":len(plan),
        "source_mips_bones_executed":len(rows),
        "source_mips_sequence_completed":failure is None,
        "first_blocker":failure,
        "results":rows,
        "original_right_left_stack_pops_verified":False,
        "source_player_object_transitions_verified":False,
    }


def summarize_character_rows(records:list[dict],meshes:set[int])->dict:
    if len(records)!=len(PROGRESS):
        raise ValueError("source stack sequence needs three progress inputs")
    complete=all(r["source_mips_sequence_completed"] for r in records)
    n=min(len(r["results"]) for r in records)
    changed=0
    drawable_changed=0
    drawable=0
    for i in range(n):
        values=[row["results"][i] for row in records]
        if len({x["ptr"] for x in values})!=1:
            raise ValueError("source stack graph order changed across progress inputs")
        different=len(set(x["source_original_mips_matrix_digest"] for x in values))>1
        gfx=values[0]["gfx"]&0x8FFFFFFF
        has_mesh=gfx in meshes
        changed+=int(different)
        drawable_changed+=int(different and has_mesh)
        drawable+=int(has_mesh)
    return {
        "character":records[0]["character"],
        "source_nodes_executed_all_samples":n,
        "source_stack_sequence_completed_all_three":complete,
        "source_mips_matrix_nodes_changed":changed,
        "source_bones_with_original_double_matrix_push":sum(
            row.get("original_mips_stack_push_bytes")==128
            for row in records[0]["results"]),
        "original_mesh_drawable_nodes":drawable,
        "original_mesh_drawable_nodes_with_changed_matrix":drawable_changed,
        "first_blockers":[r["first_blocker"] for r in records if r["first_blocker"]],
        "actual_gameplay_renderer_stack_order_verified":False,
        "original_action_timing_verified":False,
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom",type=Path)
    parser.add_argument("--rigs",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-rom-rigs"))
    parser.add_argument("--output",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-continuous-mips-skeleton-stack.json"))
    a=parser.parse_args(argv)
    try:
        rom=(a.rom or locate_rom()).read_bytes()
        verified_decoded_original_rom(rom)
        target=a.output.resolve()
        root=Path(__file__).resolve().parents[3]
        if target==root or root in target.parents:
            raise ValueError("original ROM stack report must stay outside Git")
        records=[]
        for slot,name in enumerate(CHARACTER_NAMES):
            row=[run_source_stack_sequence(rom,slot,progress) for progress in PROGRESS]
            rig=(a.rigs/name/"original.goskel").read_bytes()
            _,meshes,_=parse_rig_descriptors(rig)
            summary=summarize_character_rows(row,meshes)
            records.append(summary)
            print("GOEMON_ORIGINAL_CONTINUOUS_MIPS_STACK "+
                  json.dumps(summary,separators=(",",":")))
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps({
            "schema":"goemon-source-n64-MIPS-continuous-skeleton-stack-v1",
            "source_right_left_renderer_semantics_confirmed":False,
            "original_playback_ready":False,
            "source_assets_uploaded":False,
            "results":records,
        },indent=2)+"\n",encoding="utf-8")
        print("GOEMON_ORIGINAL_CONTINUOUS_MIPS_STACK COMPLETE: original instructions, no original asset uploads")
    except (ValueError,OSError,TypeError,KeyError) as e:
        print("GOEMON_ORIGINAL_CONTINUOUS_MIPS_STACK FAILED:",e,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
