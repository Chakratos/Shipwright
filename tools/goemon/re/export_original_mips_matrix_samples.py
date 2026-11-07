#!/usr/bin/env python3
"""Evaluate ALL limbs of one ROM-authored Skeleton per original character.

Source: exact MIPS instructions executed from the hash-verified NG5E ROM.
Each sample starts with an isolated identity current MtxF and independent
destination MtxF stack pointed to by D_80168530 at progress=0 and 1.
The separate destination is required by original N64 evaluator semantics:
aliasing current and stack created false progress differences.

The produced data are original-code *isolated limb matrices*, NOT final
gameplay animation frames: parent-space composition, active action ownership,
source tick mapping, and render memory convention remain unresolved.
Original matrix bits are PRIVATE and never printed or checked into Git.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from real_rom_check import locate_rom
from probe_original_mips_execution import (
    original_source_context,run_probe,verified_decoded_original_rom
)
from source_aligned_character_assets import CHARACTER_NAMES

PROGRESS=(0.0,1.0)


def validate_matrix_result(sample:dict)->list[int]:
    if (sample.get("returned") is not True or
        sample.get("separate_original_matrix_stack_probe") is not True or
        sample.get("original_mtxf_stack_finite_elements")!=16):
        raise ValueError("original source MIPS did not return 16 finite destination MtxF floats")
    bits=sample.get("private_matrix_stack_u32")
    if not isinstance(bits,list) or len(bits)!=16 or any(
        type(v)!=int or not 0<=v<=0xFFFFFFFF for v in bits
    ):
        raise ValueError("missing exact original 4x4 source matrix words")
    return bits


def classify_progress_changes(entries:list[dict])->dict:
    total=0
    changing=0
    static=0
    failed=0
    first_failures=[]
    for limb in entries:
        records=limb.get("samples",[])
        if len(records)!=len(PROGRESS):
            raise ValueError("source limb progress sample count inconsistent")
        total+=1
        if any("matrix_ieee754_u32" not in r for r in records):
            failed+=1
            if len(first_failures)<6:
                first_failures.append({
                    "source_limb_pointer":limb.get("source_limb_pointer"),
                    "reasons":[r.get("blocker","")[:180] for r in records
                               if "matrix_ieee754_u32" not in r],
                    "first_native_calls":records[0].get("first_native_calls",[]),
                    "read_dependencies":records[0].get("memory_reads_before_failure",[]),
                })
        elif records[0]["matrix_ieee754_u32"]!=records[1]["matrix_ieee754_u32"]:
            changing+=1
        else:
            static+=1
    return {
        "original_limb_count":total,
        "source_mips_matrix_pairs_changing":changing,
        "source_mips_matrix_pairs_static":static,
        "source_mips_matrix_pairs_blocked":failed,
        "first_blocked_limb_reasons":first_failures,
        "all_pairs_examined":changing+static+failed==total
    }


def evaluate_character(rom:bytes,slot:int)->tuple[dict,dict]:
    _,catalog=original_source_context(rom,slot)
    nodes=catalog["limbs"]
    if not nodes or len({n["ptr"] for n in nodes})!=len(nodes):
        raise ValueError("invalid original source Skeleton limb graph")
    limbs=[]
    for node in nodes:
        records=[]
        for progress in PROGRESS:
            record={
                "original_animation_progress":progress,
                "action_id":None,
                "physical_matrix_layout_verified":False
            }
            data=run_probe(rom,progress,slot=slot,
                           source_limb_ptr=node["ptr"],capture_local_matrix=True,
                           separate_matrix_stack=True)
            try:
                record["matrix_ieee754_u32"]=validate_matrix_result(data)
                record["source_instruction_count"]=data["executed"]
            except ValueError as ex:
                record["blocker"]=data.get("blocker",str(ex))
                # Only CPU register argument provenance, never source ROM bytes.
                # The failing Sasuke nodes exercise a different native helper.
                record["first_native_calls"]=data.get(
                    "first_original_function_calls",[])[:8]
                record["memory_reads_before_failure"]=data.get(
                    "first_original_memory_read_dependencies",[])[:12]
            records.append(record)
        limbs.append({
            "source_limb_pointer":f"0x{node['ptr']:08X}",
            "raw_original_gfx_pointer":f"0x{node['gfx']:08X}",
            "source_raw_srt_channels":[*node["scale"],*node["rotation"],*node["translation"]],
            "source_parent_pointer":(
                f"0x{node['parent']:08X}" if node["parent"] is not None else None),
            "samples":records,
        })
    summary=classify_progress_changes(limbs)
    file_doc={
        "format":"goemon-owner-rom-original-mips-isolated-bone-matrices-v2",
        "original_mtxf_output_pointer_global":"D_80168530",
        "output_stack_separate_from_current_mtxf":True,
        "previous_alias_based_matrix_samples_invalidated":True,
        "character":CHARACTER_NAMES[slot],
        "character_slot":slot,
        "source_original_skeleton_header":
            f"0x{(0x07000000 | catalog['source_header_offset']):08X}",
        "original_animated_skeleton_flags":catalog["original_animated_skeleton_flags"],
        "source_animation_pointer":catalog["original_animation_pointer"],
        "source_skeleton_root":catalog["original_skeleton_root"],
        "controlled_animation_progress_values":list(PROGRESS),
        "source_game_action_verified":False,
        "source_tick_mapping_verified":False,
        "parent_world_composition_verified":False,
        "engine_matrix_memory_layout_verified":False,
        "source_original_rom_bytes_uploaded":False,
        "limbs":limbs,
    }
    return file_doc,{"character":CHARACTER_NAMES[slot],**summary}


def generate_local_matrix_samples(rom:bytes,destination:Path)->dict:
    verified_decoded_original_rom(rom)
    root=Path(__file__).resolve().parents[3]
    target=destination.resolve()
    if target==root or root in target.parents:
        raise ValueError("original matrix samples must stay outside Git checkout")
    target.mkdir(parents=True,exist_ok=True)
    summaries=[]
    for slot,name in enumerate(CHARACTER_NAMES):
        data,summary=evaluate_character(rom,slot)
        (target/(name+"_source_mips_matrices.json")).write_text(
            json.dumps(data,indent=2)+"\n",encoding="utf-8")
        summaries.append(summary)
        print("GOEMON_MIPS_LIMB_MATRIX_BATCH "+json.dumps(
            summary,separators=(",",":")))
    report={
        "source":"user-owned hash-verified NG5E ROM",
        "engine":"original Nintendo 64 MIPS CPU",
        "matrix_sample_progress":[0.0,1.0],
        "characters":summaries,
        "total_source_bones":sum(x["original_limb_count"] for x in summaries),
        "total_evaluations":sum(x["original_limb_count"] for x in summaries)*2,
        "playback_ready":False,
        "raw_matrices_uploaded":False
    }
    (target/"manifest.json").write_text(json.dumps(report,indent=2)+"\n",
                                         encoding="utf-8")
    print("GOEMON_MIPS_LIMB_MATRIX_BATCH COMPLETE: owner-PC only, no frame ownership claimed")
    return report


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--output-dir",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-mips-isolated-limb-matrices"))
    a=p.parse_args(argv)
    try:
        generate_local_matrix_samples(
            (a.rom or locate_rom()).read_bytes(),a.output_dir)
    except (ValueError,OSError,TypeError,KeyError) as ex:
        print("GOEMON_MIPS_LIMB_MATRIX_BATCH FAILED:",ex,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
