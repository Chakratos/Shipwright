#!/usr/bin/env python3
"""Test ORIGINAL Goemon MIPS matrix-stack multiplication order offline.

This probes whether genuine source N64 MIPS child-limb evaluation with an
explicit parent MtxF equals a standard 4x4 row-major parent@child or
child@parent product of source-only isolated evaluator outputs.

No gameplay action ownership, true parent matrix stack or player pose is
claimed without numerical agreement. No original source matrices leave
the user's Windows PC; only scalar residual scores appear in job logs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_mips_vm import f32
from probe_original_mips_execution import (
    run_probe,original_source_context,verified_decoded_original_rom
)
from real_rom_check import locate_rom
from source_aligned_character_assets import CHARACTER_NAMES


def row_major_multiply(a:list[float],b:list[float])->list[float]:
    if len(a)!=16 or len(b)!=16 or any(
        not math.isfinite(v) for v in a+b):
        raise ValueError("invalid original MtxF multiplication operands")
    return [
        sum(a[row*4+k]*b[k*4+col] for k in range(4))
        for row in range(4) for col in range(4)
    ]


def normalized_matrix_error(expected:list[float],
                            actual:list[float])->float:
    if len(expected)!=16 or len(actual)!=16:
        raise ValueError("source matrix result must have 16 elements")
    if any(not math.isfinite(v) for v in expected+actual):
        raise ValueError("unverified nonfinite original MIPS matrix")
    diff=sum((x-y)**2 for x,y in zip(expected,actual))
    norm=max(16.0,sum(v*v for v in actual))
    return math.sqrt(diff/norm)


def matrix_values(sample:dict)->list[float]:
    if sample.get("returned") is not True or sample.get("matrix_finite_elements")!=16:
        raise ValueError(sample.get("blocker","source MIPS matrix evaluator did not return"))
    b=sample.get("private_matrix_u32")
    if not isinstance(b,list) or len(b)!=16:
        raise ValueError("source original MIPS matrix unavailable")
    return [f32(v) for v in b]


def find_child_with_original_parent(nodes:list[dict])->dict:
    indices={n["ptr"]:n for n in nodes}
    eligible=[
        n for n in nodes if n["parent"] in indices and
        any(0<x<32768 for x in (*n["scale"],*n["rotation"],*n["translation"]))
    ]
    if not eligible:
        raise ValueError("no original source numeric-channel limb with parent")
    return max(eligible,key=lambda n:sum(
        0<x<32768 for x in (*n["scale"],*n["rotation"],*n["translation"])))


def test_original_composition(rom:bytes,slot:int,progress:float)->dict:
    _,candidate=original_source_context(rom,slot)
    selected=find_child_with_original_parent(candidate["limbs"])
    parent=selected["parent"]
    child=selected["ptr"]
    a=run_probe(rom,progress,slot=slot,source_limb_ptr=parent,
                capture_local_matrix=True)
    b=run_probe(rom,progress,slot=slot,source_limb_ptr=child,
                capture_local_matrix=True)
    parent_words=a.get("private_matrix_u32")
    if a.get("returned") is not True or not isinstance(parent_words,list):
        raise ValueError("original source parent MIPS matrix did not return")
    c=run_probe(rom,progress,slot=slot,source_limb_ptr=child,
                capture_local_matrix=True,initial_matrix_u32=parent_words)
    parent_m=matrix_values(a)
    child_iso=matrix_values(b)
    actual=matrix_values(c)
    ab=row_major_multiply(parent_m,child_iso)
    ba=row_major_multiply(child_iso,parent_m)
    err_ab=normalized_matrix_error(ab,actual)
    err_ba=normalized_matrix_error(ba,actual)
    threshold=1e-4
    matches=[name for name,error in (
        ("parent_times_child",err_ab),
        ("child_times_parent",err_ba)) if error<=threshold]
    return {
        "character":CHARACTER_NAMES[slot],
        "sample_progress":progress,
        "child_has_source_parent":True,
        "original_source_parent_limb":f"0x{parent:08X}",
        "original_source_child_limb":f"0x{child:08X}",
        "parent_then_child_relative_error":round(err_ab,7),
        "child_then_parent_relative_error":round(err_ba,7),
        "exact_float_composition_candidates":matches,
        "source_game_playback_verified":False,
        "render_matrix_stack_verified":False,
        "source_mips_instructions_child_isolated":b.get("executed"),
        "source_mips_instructions_child_with_parent":c.get("executed"),
    }


def run_composition_probe(rom:bytes,destination:Path)->dict:
    verified_decoded_original_rom(rom)
    project=Path(__file__).resolve().parents[3]
    target=destination.resolve()
    if target==project or project in target.parents:
        raise ValueError("private MIPS matrix composition report cannot be in Git")
    rows=[]
    for slot,name in enumerate(CHARACTER_NAMES):
        for progress in (0.0,1.0):
            try:
                row=test_original_composition(rom,slot,progress)
            except (ValueError,OverflowError,ZeroDivisionError) as exc:
                row={"character":name,"sample_progress":progress,
                     "blocked":str(exc),
                     "exact_float_composition_candidates":[],
                     "render_matrix_stack_verified":False}
            rows.append(row)
            print("GOEMON_MIPS_MATRIX_COMPOSITION "+
                  json.dumps(row,separators=(",",":")))
    result={
        "format":"goemon-original-MIPS-source-parent-composition-probe-v1",
        "sources":"owner-owned hash-verified ROM machine instructions only",
        "results":rows,
        "active_character_action_and_gameplay_timing_verified":False,
        "original_source_bytes_uploaded":False,
    }
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


def main(argv=None)->int:
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--rom",type=Path)
    a.add_argument("--output",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-MIPS-parent-composition.json"))
    args=a.parse_args(argv)
    try:
        run_composition_probe((args.rom or locate_rom()).read_bytes(),args.output)
        print("GOEMON_MIPS_MATRIX_COMPOSITION COMPLETE: source-CPU parent propagation, no game frames claimed")
    except (OSError,ValueError,KeyError,TypeError) as e:
        print("GOEMON_MIPS_MATRIX_COMPOSITION FAILED:",e,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
