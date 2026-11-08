#!/usr/bin/env python3
"""Verify source N64 MIPS child matrix inheritance from previous stack entry.

Runs original hash-verified NG5E MIPS evaluator using destination
D_80168530 = current stack frame+64 with independently configured
preceding MtxF. Compares identity, noncommuting parent matrix and
a parent MtxF computed by the original code at two source progress inputs.
This measures actual stack dependency, not inferred actions/timing.
No ROM instruction bytes or matrices are logged or uploaded.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_mips_vm import bits32
from probe_original_mips_execution import (
    original_source_catalog,choose_source_candidate,run_probe,
    verified_decoded_original_rom,
)
from source_aligned_character_assets import CHARACTER_NAMES
from real_rom_check import locate_rom

HEADERS=(0x14F30,0x1CF8,0x105B0,0x23F60)
IDENTITY=[bits32(1.0 if i%5==0 else 0.0) for i in range(16)]
SEED=[bits32(v) for v in (
    0,0,1,11, 0,1,0,7, -1,0,0,-5, 0,0,0,1
)]


def selected_parent_child_pairs(nodes:list[dict])->list[tuple[int,int]]:
    pointers={n["ptr"] for n in nodes}
    pairs=[(n["parent"],n["ptr"]) for n in nodes
           if n["parent"] in pointers and
           n["gfx"]!=0]
    if not pairs:
        raise ValueError("no rendered original bone with structural source parent")
    if len(pairs)>128:
        raise ValueError("original source skeleton limit exceeded")
    return pairs


def output_digest(data:dict)->str|None:
    if not data.get("returned") or not data.get(
        "separate_original_matrix_stack_probe"):
        return None
    if data.get("original_mtxf_stack_finite_elements")!=16:
        return None
    return data.get("original_mtxf_stack_sha256_prefix")


def analyze_source_parent_stack(rom:bytes,slot:int)->dict:
    _,all_candidates=original_source_catalog(rom,slot)
    candidate=choose_source_candidate(all_candidates,HEADERS[slot])
    pairs=selected_parent_child_pairs(candidate["limbs"])
    key=HEADERS[slot]
    inherited=0
    original_parent_changes=0
    failed=0
    first_inherited=[]
    first_errors=[]
    for parent,child in pairs:
        base=run_probe(
            rom,slot=slot,source_header_offset=key,source_limb_ptr=child,
            progress=0.0,separate_matrix_stack=True,
            previous_stack_matrix_u32=IDENTITY)
        variant=run_probe(
            rom,slot=slot,source_header_offset=key,source_limb_ptr=child,
            progress=0.0,separate_matrix_stack=True,
            previous_stack_matrix_u32=SEED)
        baseline_hash=output_digest(base)
        variant_hash=output_digest(variant)
        if baseline_hash is None or variant_hash is None:
            failed+=1
            if len(first_errors)<4:
                first_errors.append({
                    "parent":f"0x{parent:08X}",
                    "child":f"0x{child:08X}",
                    "reason":base.get("blocker") or variant.get("blocker") or
                             "invalid float output"})
            continue
        if baseline_hash!=variant_hash:
            inherited+=1
            if len(first_inherited)<6:
                first_inherited.append({
                    "parent":f"0x{parent:08X}",
                    "child":f"0x{child:08X}",
                    "source_stack_seed_changes_child_result":True})
        # Independently test original parent MtxF propagation at progress
        # 0 and 4, without assuming candidate source action or tick.
        p0=run_probe(rom,slot=slot,source_header_offset=key,
                     source_limb_ptr=parent,progress=0.0,
                     separate_matrix_stack=True,capture_local_matrix=True)
        p4=run_probe(rom,slot=slot,source_header_offset=key,
                     source_limb_ptr=parent,progress=4.0,
                     separate_matrix_stack=True,capture_local_matrix=True)
        m0=p0.get("private_matrix_stack_u32")
        m4=p4.get("private_matrix_stack_u32")
        if (output_digest(p0) is None or output_digest(p4) is None or
            not isinstance(m0,list) or not isinstance(m4,list)):
            continue
        if m0==m4:
            continue
        c0=run_probe(rom,slot=slot,source_header_offset=key,
                     source_limb_ptr=child,progress=0.0,
                     separate_matrix_stack=True,
                     previous_stack_matrix_u32=m0)
        c4=run_probe(rom,slot=slot,source_header_offset=key,
                     source_limb_ptr=child,progress=0.0,
                     separate_matrix_stack=True,
                     previous_stack_matrix_u32=m4)
        if output_digest(c0) is not None and output_digest(c4) is not None and (
            output_digest(c0)!=output_digest(c4)):
            original_parent_changes+=1
    return {
        "character":CHARACTER_NAMES[slot],
        "source_header":f"0x070{key:05X}",
        "direct_rendered_parent_child_pairs_tested":len(pairs),
        "child_outputs_changed_by_controlled_predecessor_matrix":inherited,
        "child_outputs_changed_by_original_parent_progress":original_parent_changes,
        "execution_blocked_pairs":failed,
        "first_affected_original_limb_pairs":first_inherited,
        "first_blockers":first_errors,
        "live_player_action_or_tick_verified":False,
        "real_source_renderer_stack_traversal_verified":False,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--output",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-MIPS-predecessor-matrix-probe.json"))
    a=p.parse_args(argv)
    try:
        rom=(a.rom or locate_rom()).read_bytes()
        verified_decoded_original_rom(rom)
        root=Path(__file__).resolve().parents[3]
        dest=a.output.resolve()
        if dest==root or root in dest.parents:
            raise ValueError("source ROM probe cannot be stored in git checkout")
        results=[]
        for slot in range(4):
            row=analyze_source_parent_stack(rom,slot)
            results.append(row)
            print("GOEMON_MIPS_PREVIOUS_STACK "+json.dumps(
                row,separators=(",",":")))
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps({
            "format":"original-source-mips-predecessor-experiment-v1",
            "source_matrix_stack_inheritance_verified":False,
            "real_gameplay_action_ownership_verified":False,
            "results":results,
        },indent=2)+"\n",encoding="utf-8")
        print("GOEMON_MIPS_PREVIOUS_STACK COMPLETE: source-only no uploads")
    except (OSError,TypeError,ValueError,KeyError) as ex:
        print("GOEMON_MIPS_PREVIOUS_STACK FAILED:",ex,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
