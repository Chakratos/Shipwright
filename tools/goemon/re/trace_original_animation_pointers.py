#!/usr/bin/env python3
"""Audit candidate animation pointer ownership via exact original MIPS loads.

For each character, compare:
  * first source 0x07 structural AnimatedSkeleton
  * a source descriptor with the most numeric animation channel fields
  * previously selected source-compatible geometry header (historical)

Run original hash-verified NG5E instructions at controlled progress
0,1,4. Collect bounded MIPS program-counter/read-address/width metadata.
NO ROM payloads, original code words or matrix values are ever logged or
uploaded. Tested header/pointer ownership is NOT proof of active player
actions until traced back to Object.graphics_1 in a real game frame.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from original_continuous_mips_skeleton import HEADERS
from probe_original_mips_execution import (
    run_probe,original_source_catalog,verified_decoded_original_rom)
from source_aligned_character_assets import CHARACTER_NAMES
from real_rom_check import locate_rom

PROGRESS=(0.0,1.0,4.0)


def numeric_channels(node:dict)->int:
    return sum(0<x<32768 for x in (
        *node["scale"], *node["rotation"], *node["translation"]))


def choose_animation_owner_candidates(candidates:tuple[dict,...],
                                      previous_header_offset:int)->list[tuple[str,dict]]:
    if not candidates:
        raise ValueError("no original source descriptors")
    best=max(candidates,key=lambda item:max(
        (numeric_channels(limb) for limb in item["limbs"]),default=0))
    old=next((r for r in candidates if
              r["source_header_offset"]==previous_header_offset),None)
    selections=[("first_structural",candidates[0]),
                ("most_numeric_channels",best)]
    if old:
        selections.append(("historical_mesh_match_not_action_owner",old))
    used=set()
    dedup=[]
    for label,candidate in selections:
        if candidate["source_header_offset"] in used:
            continue
        used.add(candidate["source_header_offset"])
        dedup.append((label,candidate))
    return dedup


def summarize_exact_source_reads(samples:list[dict],
                                 candidate_pointer:int)->dict:
    """Address provenance only, no raw source ROM data or matrices."""
    if len(samples)!=len(PROGRESS):
        raise ValueError("must execute all three controlled progress samples")
    site_sets=[]
    near_counts=[]
    all_sites=set()
    read_counts=[]
    for sample in samples:
        if not sample.get("returned") or not sample.get(
            "separate_original_matrix_stack_probe"):
            raise ValueError("original source N64 CPU did not return")
        ptr=sample.get("private_candidate_animation_pointer")
        bounds=sample.get("private_source_bank_bounds")
        if ptr!=candidate_pointer or not isinstance(bounds,list) or len(bounds)!=2:
            raise ValueError("source candidate pointer/probe bank mismatch")
        sites=sample.get("private_original_source_read_sites")
        if not isinstance(sites,list):
            raise ValueError("missing bounded original source read site trace")
        unique=set()
        near=0
        total=0
        for site in sites:
            pc,address,width,count=(site[k] for k in
                ("pc","address","width","count"))
            if (not all(type(x)==int for x in (pc,address,width,count)) or
                count<1 or width not in (1,2,4,8) or
                not bounds[0]<=address<bounds[1]):
                raise ValueError("invalid original source read site provenance")
            unique.add((pc,address,width))
            total+=count
            if candidate_pointer<=address<candidate_pointer+128:
                near+=count
        site_sets.append(unique)
        near_counts.append(near)
        read_counts.append(total)
        all_sites.update(unique)
    changed_sites=site_sets[0]!=site_sets[1] or site_sets[0]!=site_sets[2]
    digests=[
        sample.get("original_mtxf_numeric_digest")
        for sample in samples
    ]
    if any(not isinstance(value,str) for value in digests):
        raise ValueError("missing signed-zero-normalized source MIPS matrix result")
    near_sites=sorted(
        (pc,address-candidate_pointer,width)
        for (pc,address,width) in all_sites
        if 0<=address-candidate_pointer<128
    )
    return {
        "source_cpu_returned_all_progress_samples":True,
        "original_source_bank_loads_by_progress":read_counts,
        "near_candidate_pointer_loads_by_progress":near_counts,
        "distinct_source_read_locations":len(all_sites),
        "source_read_locations_change_over_progress":changed_sites,
        "numeric_mtxf_changes_over_progress":len(set(digests))>1,
        "first_candidate_pointer_read_sites":[
            {"mips_pc":f"0x{pc:08X}",
             "relative_offset":offset,"width":width}
            for pc,offset,width in near_sites[:12]
        ],
        "candidate_pointer_is_proven_active_player_animation":False,
    }


def analyze_candidate(rom:bytes,slot:int,label:str,candidate:dict)->dict:
    head=candidate["source_header_offset"]
    best=max(candidate["limbs"],key=numeric_channels)
    samples=[
        run_probe(
            rom,progress,slot=slot,source_header_offset=head,
            source_limb_ptr=best["ptr"],separate_matrix_stack=True,
            capture_source_read_sites=True,
        ) for progress in PROGRESS
    ]
    raw_ptr=int(candidate["original_animation_pointer"],16)
    resolved=samples[0].get("private_candidate_animation_pointer")
    if resolved is None:
        raise ValueError("source animation pointer resolution failed")
    report=summarize_exact_source_reads(samples,resolved)
    return {
        "character":CHARACTER_NAMES[slot],
        "selection_reason":label,
        "source_candidate_header":f"0x{0x07000000|head:08X}",
        "source_candidate_animation_pointer":f"0x{raw_ptr:08X}",
        "source_animated_skeleton_flags":candidate["original_animated_skeleton_flags"],
        "tested_source_limb":f"0x{best['ptr']:08X}",
        "numeric_source_channel_fields":numeric_channels(best),
        "original_source_progress_points":list(PROGRESS),
        "resolved_candidate_pointer_in_segment_07":samples[0][
            "private_source_bank_bounds"][0]<=resolved<samples[0][
            "private_source_bank_bounds"][1],
        **report,
    }


def trace_original_candidate_ownership(rom:bytes,out:Path)->dict:
    verified_decoded_original_rom(rom)
    root=Path(__file__).resolve().parents[3]
    target=out.resolve()
    if target==root or root in target.parents:
        raise ValueError("ROM metadata cannot be written into Git checkout")
    summaries=[]
    for slot,name in enumerate(CHARACTER_NAMES):
        _,candidates=original_source_catalog(rom,slot)
        rows=[]
        for label,candidate in choose_animation_owner_candidates(
            candidates,HEADERS[slot]):
            row=analyze_candidate(rom,slot,label,candidate)
            rows.append(row)
            # Metadata only. Never serialize private decoded ROM or matrices.
            print("GOEMON_SOURCE_POINTER_PROVENANCE "+json.dumps(
                row,separators=(",",":")))
        summaries.append({
            "character":name,
            "source_candidates_examined":len(rows),
            "candidate_pointer_with_near_reads":sum(
                any(n>0 for n in row["near_candidate_pointer_loads_by_progress"])
                for row in rows),
            "candidate_with_numeric_animation_mtxf":sum(
                row["numeric_mtxf_changes_over_progress"] for row in rows),
        })
        print("GOEMON_SOURCE_POINTER_OWNERSHIP_SUMMARY "+json.dumps(
            summaries[-1],separators=(",",":")))
    report={
        "schema":"goemon-original-source-pointer-reads-v1",
        "verified_original_ROM":True,
        "real_player_Object_graphics_1_ownership_verified":False,
        "original_action_ownership_verified":False,
        "source_raw_assets_uploaded":False,
        "progress_points":list(PROGRESS),
        "summaries":summaries,
    }
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("GOEMON_SOURCE_POINTER_PROVENANCE COMPLETE: only read-site metadata printed")
    return report


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--output",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-source-animation-pointer-provenance.json"))
    a=p.parse_args(argv)
    try:
        trace_original_candidate_ownership(
            (a.rom or locate_rom()).read_bytes(),a.output)
    except (OSError,ValueError,TypeError,KeyError) as e:
        print("GOEMON_SOURCE_POINTER_PROVENANCE FAILED:",e,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
