#!/usr/bin/env python3
"""Identify original Goemon MtxF stack ownership from real MIPS execution.

The N64 source code accepts an MtxF* at D_80168530. Earlier isolated
probes aliased this pointer to D_801684B0, while the game may use
separate source current and matrix-stack destinations. Compare controlled
alias/split-matrix cases. This is ABI evidence, not a game-pose capture.

The original ROM, executable instructions, and matrix values remain
private. Only hashes, status and changed/not-changed flags are logged.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_mips_vm import bits32
from probe_original_mips_execution import (
    run_probe,original_source_context,verified_decoded_original_rom
)
from source_aligned_character_assets import CHARACTER_NAMES
from real_rom_check import locate_rom

NONCOMMUTING=[
    0.0,0.0,1.0,11.0,
    0.0,1.0,0.0,7.0,
    -1.0,0.0,0.0,-5.0,
    0.0,0.0,0.0,1.0,
]
IDENTITY=[
    1.0,0.0,0.0,0.0,
    0.0,1.0,0.0,0.0,
    0.0,0.0,1.0,0.0,
    0.0,0.0,0.0,1.0,
]

def choose_original_limb(nodes):
    return max(nodes,key=lambda n:sum(
        0<x<32768 for x in (*n["scale"],*n["rotation"],*n["translation"])))


def run_matrix_abi(rom:bytes,slot:int)->dict:
    _,record=original_source_context(rom,slot)
    node=choose_original_limb(record["limbs"])
    ptr=node["ptr"]
    base=run_probe(rom,0.0,slot=slot,source_limb_ptr=ptr)
    split=run_probe(rom,0.0,slot=slot,source_limb_ptr=ptr,
                    separate_matrix_stack=True)
    variant=run_probe(rom,0.0,slot=slot,source_limb_ptr=ptr,
        separate_matrix_stack=True,
        stack_initial_matrix_u32=[bits32(v) for v in NONCOMMUTING])
    global_variant=run_probe(rom,0.0,slot=slot,source_limb_ptr=ptr,
        separate_matrix_stack=True,
        initial_matrix_u32=[bits32(v) for v in NONCOMMUTING])
    progressed=run_probe(rom,1.0,slot=slot,source_limb_ptr=ptr,
                         separate_matrix_stack=True)
    cases={"original_alias":base,"split_identity":split,
           "split_seeded_stack":variant,
           "split_seeded_current":global_variant,
           "split_progress_1":progressed}
    return {
        "character":CHARACTER_NAMES[slot],
        "source_limb":f"0x{ptr:08X}",
        "cases":{
            key:{
                "returned":bool(data.get("returned")),
                "blocker":data.get("blocker"),
                "executed":data.get("executed"),
                "current_mtxf_digest":data.get("matrix_fingerprint_sha256_prefix"),
                "stack_digest":data.get("original_mtxf_stack_sha256_prefix"),
                "stack_modified":data.get("original_mtxf_stack_changed_from_input"),
                "stack_pointer_delta":data.get("original_mtxf_destination_pointer_delta"),
                "stack_finite_floats":data.get("original_mtxf_stack_finite_elements"),
                "stack_nonidentity_floats":data.get("original_mtxf_stack_nonidentity_elements"),
            } for key,data in cases.items()
        },
        "stack_seed_alters_current_mtxf":(
            variant["matrix_fingerprint_sha256_prefix"] !=
            split["matrix_fingerprint_sha256_prefix"]),
        "current_seed_alters_current_mtxf":(
            global_variant["matrix_fingerprint_sha256_prefix"] !=
            split["matrix_fingerprint_sha256_prefix"]),
        "stack_output_changes_between_progress_0_and_1":(
            progressed.get("original_mtxf_stack_sha256_prefix") !=
            split.get("original_mtxf_stack_sha256_prefix")),
        "original_player_stack_ownership_verified":False,
        "actual_animation_action_verified":False,
    }


def analyze_source_mtxf_ownership(rom:bytes,outfile:Path)->dict:
    verified_decoded_original_rom(rom)
    folder=Path(__file__).resolve().parents[3]
    destination=outfile.resolve()
    if destination==folder or folder in destination.parents:
        raise ValueError("private source matrices must be stored outside Git")
    results=[]
    for slot in range(4):
        report=run_matrix_abi(rom,slot)
        results.append(report)
        print("GOEMON_ORIGINAL_MTXF_ABI "+json.dumps(
            report,separators=(",",":")))
    result={
        "schema":"original-ng5e-MtxF-pointer-alias-probe-v1",
        "original_rom_bytes_uploaded":False,
        "live_player_object_context_verified":False,
        "characters":results,
    }
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--output",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-mtxf-pointer-abi.json"))
    args=p.parse_args(argv)
    try:
        analyze_source_mtxf_ownership(
            (args.rom or locate_rom()).read_bytes(),args.output)
        print("GOEMON_ORIGINAL_MTXF_ABI COMPLETE: private source code execution")
    except (ValueError,OSError,TypeError,KeyError) as ex:
        print("GOEMON_ORIGINAL_MTXF_ABI FAILED:",ex,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
