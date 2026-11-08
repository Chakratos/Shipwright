#!/usr/bin/env python3
"""Locate authentic time-sensitive AnimatedSkeleton descriptors in NG5E.

The owner's ROM has 371 structurally validated 0x07 source candidates.
Previous isolated MIPS tests sampled only the first descriptor per
character. Run the *original MIPS machine code* on the most numerically
channeled limb from EACH descriptor at progress=0,1,4, using distinct
D_80168530 destination MtxF and current MtxF globals.

This is a source channel/descriptor search, NOT a proof of active
player-action ownership or genuine animation frame timing.
No ROM bytes, matrices or disassembly leave the private Windows runner.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probe_original_mips_execution import (
    original_source_catalog,run_probe,verified_decoded_original_rom
)
from source_aligned_character_assets import CHARACTER_NAMES
from real_rom_check import locate_rom

PROGRESS=(0.0,1.0,4.0)

def select_numeric_limb(pose:dict)->tuple[dict,int]:
    if not pose.get("limbs"):
        raise ValueError("original source AnimatedSkeleton has no limbs")
    def score(node):
        channels=(*node["scale"],*node["rotation"],*node["translation"])
        return sum(0<field<32768 for field in channels)
    node=max(pose["limbs"],key=score)
    return node,score(node)

def classify_descriptor_samples(cases:list[dict])->dict:
    if len(cases)!=len(PROGRESS):
        raise ValueError("source MIPS progress-sweep requires three exact test inputs")
    valid=all(
        case.get("returned") is True and
        case.get("separate_original_matrix_stack_probe") is True and
        case.get("original_mtxf_stack_finite_elements")==16 and
        isinstance(case.get("original_mtxf_numeric_digest"),str)
        for case in cases)
    if not valid:
        return {"valid":False,"changed_at_1":False,
                "changed_at_4":False,"changed_any":False}
    keys=[case.get("original_mtxf_numeric_digest")
          for case in cases]
    if any(not isinstance(key,str) for key in keys):
        raise ValueError("real original MIPS numeric-zero-normalized matrix digest missing")
    return {
        "valid":True,
        "changed_at_1":keys[0]!=keys[1],
        "changed_at_4":keys[0]!=keys[2],
        "changed_any":len(set(keys))>1,
    }


def analyze_character(rom:bytes,slot:int)->tuple[dict,list[dict]]:
    _,candidates=original_source_catalog(rom,slot)
    first_changes=[]
    issues=Counter()
    changed_at_1=changed_at_4=changed_any=valid_count=0
    per_candidate=[]
    for candidate in candidates:
        node,numeric=select_numeric_limb(candidate)
        traces=[]
        for progress in PROGRESS:
            info=run_probe(rom,progress,slot=slot,
                           source_header_offset=candidate["source_header_offset"],
                           source_limb_ptr=node["ptr"],
                           separate_matrix_stack=True)
            traces.append(info)
        status=classify_descriptor_samples(traces)
        valid_count+=int(status["valid"])
        changed_at_1+=int(status["changed_at_1"])
        changed_at_4+=int(status["changed_at_4"])
        changed_any+=int(status["changed_any"])
        if status["changed_any"] and len(first_changes)<12:
            first_changes.append({
                "source_header":f"0x{candidate['source_header_offset']:06X}",
                "limb":f"0x{node['ptr']:08X}",
                "numeric_channels":numeric,
                "changed_0_to_1":status["changed_at_1"],
                "changed_0_to_4":status["changed_at_4"],
            })
        if not status["valid"]:
            issues[traces[0].get("blocker","unverified MtxF output")[:140]]+=1
        per_candidate.append({
            "source_header":f"0x{candidate['source_header_offset']:06X}",
            "selected_limb":f"0x{node['ptr']:08X}",
            "numeric_channels":numeric,
            "valid":status["valid"],
            "changed_at_1":status["changed_at_1"],
            "changed_at_4":status["changed_at_4"],
            "blocked_reason":next(
                (x["blocker"][:160] for x in traces if x.get("blocker")),None),
        })
    summary={
        "character":CHARACTER_NAMES[slot],
        "source_07_skeleton_descriptors":len(candidates),
        "controlled_progress_points":list(PROGRESS),
        "descriptors_all_mips_evaluations_valid":valid_count,
        "descriptors_with_distinct_stack_output_at_progress_1":changed_at_1,
        "descriptors_with_distinct_stack_output_at_progress_4":changed_at_4,
        "descriptors_with_any_progress_dependent_stack_output":changed_any,
        "first_time_sensitive_source_headers":first_changes,
        "first_cpu_failures":dict(issues.most_common(5)),
        "original_source_action_ids_verified":False,
        "real_gameplay_animation_timing_verified":False,
    }
    return summary,per_candidate


def scan_original_mips_descriptors(rom:bytes,destination:Path)->dict:
    verified_decoded_original_rom(rom)
    project=Path(__file__).resolve().parents[3]
    out=destination.resolve()
    if out==project or project in out.parents:
        raise ValueError("original ROM source results must remain outside Git checkout")
    summaries=[]
    records={}
    for slot in range(4):
        summary,candidates=analyze_character(rom,slot)
        summaries.append(summary)
        records[CHARACTER_NAMES[slot]]=candidates
        print("GOEMON_ORIGINAL_DESCRIPTOR_TIME_SWEEP "+json.dumps(
            summary,separators=(",",":")))
    report={
        "schema":"goemon-original-source-MIPS-descriptor-progress-sweep-v1",
        "progress_points":list(PROGRESS),
        "source_owned_rom_hash_verified":True,
        "actual_source_gameplay_action_mapping_verified":False,
        "source_matrix_memory_destination":"MtxF* D_80168530",
        "samples_uploaded":False,
        "summaries":summaries,
        "source_descriptor_diagnostics":records,
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


def main(argv=None)->int:
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--rom",type=Path)
    a.add_argument("--output",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-MIPS-descriptor-time-sweep.json"))
    args=a.parse_args(argv)
    try:
        scan_original_mips_descriptors(
            (args.rom or locate_rom()).read_bytes(),args.output)
        print("GOEMON_ORIGINAL_DESCRIPTOR_TIME_SWEEP COMPLETE: original MIPS animation candidate search, no asset uploads")
    except (OSError,ValueError,TypeError,KeyError) as ex:
        print("GOEMON_ORIGINAL_DESCRIPTOR_TIME_SWEEP FAILED:",ex,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
