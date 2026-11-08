#!/usr/bin/env python3
"""Export source-original CPU-preserved MIPS matrix stack as native GOMIPS01 input.

The original MIPS CPU runs a complete source graph, persisting N64 RDRAM,
global animation state, and source parent matrix stack. Runtime renderer
object transitions and conditional 0x4000 pops remain unresolved.
Real action identities and game ticks are UNKNOWN. Source assets remain
on user's local PC, not in Git or build artifacts.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from original_continuous_mips_skeleton import (
    HEADERS,run_source_stack_sequence
)
from probe_original_mips_execution import (
    original_source_catalog,choose_source_candidate,
    verified_decoded_original_rom
)
from source_aligned_character_assets import CHARACTER_NAMES
from real_rom_check import locate_rom


def generate_continuous_source_archive(rom:bytes,slot:int)->tuple[dict,dict]:
    _,candidates=original_source_catalog(rom,slot)
    record=choose_source_candidate(candidates,HEADERS[slot])
    progress=(0.0,1.0)
    traces=[run_source_stack_sequence(rom,slot,t,capture_private_matrices=True)
            for t in progress]
    if any(not trace["source_mips_sequence_completed"] for trace in traces):
        raise ValueError("continuous original N64 MIPS skeleton did not return")
    nodes=record["limbs"]
    if any(len(t["results"])!=len(nodes) for t in traces):
        raise ValueError("source CPU matrices do not cover entire skeleton")
    limbs=[]
    for i,node in enumerate(nodes):
        samples=[]
        for j,t in enumerate(progress):
            raw=traces[j]["results"][i]
            if raw["ptr"]!=node["ptr"] or raw["gfx"]!=node["gfx"]:
                raise ValueError("original ROM source CPU bone index mismatch")
            matrix=raw["private_original_mips_matrix_words"]
            if not isinstance(matrix,list) or len(matrix)!=16:
                raise ValueError("missing original CPU evaluated matrix")
            samples.append({
                "original_animation_progress":t,
                "matrix_ieee754_u32":matrix,
                "source_native_push_bytes":raw["original_mips_stack_push_bytes"],
                "action_id":None,
            })
        limbs.append({
            "source_limb_pointer":f"0x{node['ptr']:08X}",
            "raw_original_gfx_pointer":f"0x{node['gfx']:08X}",
            "source_raw_srt_channels":[
                *node["scale"],*node["rotation"],*node["translation"]],
            "source_parent_pointer":(
                f"0x{node['parent']:08X}" if node["parent"] is not None else None),
            "samples":samples,
        })
    changed=sum(node["samples"][0]["matrix_ieee754_u32"]!=
                node["samples"][1]["matrix_ieee754_u32"] for node in limbs)
    source={
        "format":"goemon-owner-rom-original-mips-continuous-skeleton-bone-matrices-v4",
        "original_mtxf_output_pointer_global":"D_80168530",
        "output_stack_separate_from_current_mtxf":True,
        "previous_alias_based_matrix_samples_invalidated":True,
        "continuous_original_cpu_state_preserved":True,
        "actual_original_renderer_stack_pop_verified":False,
        "source_game_action_verified":False,
        "source_tick_mapping_verified":False,
        "parent_world_composition_verified":False,
        "engine_matrix_memory_layout_verified":False,
        "controlled_animation_progress_values":[0.0,1.0],
        "character":CHARACTER_NAMES[slot],
        "character_slot":slot,
        "source_original_skeleton_header":f"0x{0x07000000|HEADERS[slot]:08X}",
        "original_animated_skeleton_flags":
            record["original_animated_skeleton_flags"],
        "source_animation_pointer":record["original_animation_pointer"],
        "source_skeleton_root":record["original_skeleton_root"],
        "limbs":limbs,
    }
    summary={
        "character":CHARACTER_NAMES[slot],
        "source_nodes":len(nodes),
        "original_source_cpu_matrices":len(nodes)*2,
        "source_mips_bone_matrices_changed":changed,
        "actual_original_gameplay_action_verified":False,
        "source_original_renderer_object_transition_verified":False
    }
    return source,summary


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--output-dir",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-mips-isolated-limb-matrices"))
    a=p.parse_args(argv)
    try:
        rom=(a.rom or locate_rom()).read_bytes()
        verified_decoded_original_rom(rom)
        target=a.output_dir.resolve()
        git=Path(__file__).resolve().parents[3]
        if target==git or git in target.parents:
            raise ValueError("owner-ROM source output cannot be in Git")
        target.mkdir(parents=True,exist_ok=True)
        rows=[]
        for slot,name in enumerate(CHARACTER_NAMES):
            data,summary=generate_continuous_source_archive(rom,slot)
            (target/(name+"_source_mips_matrices.json")).write_text(
                json.dumps(data,indent=2)+"\n",encoding="utf-8")
            rows.append(summary)
            print("GOEMON_NATIVE_CONTINUOUS_MIPS_SOURCE "+json.dumps(
                summary,separators=(",",":")))
        (target/"manifest.json").write_text(json.dumps({
            "original_renderer_traversal_fully_verified":False,
            "real_action_clips_recovered":False,
            "owner_rom_uploaded":False,
            "figures":rows
        },indent=2)+"\n",encoding="utf-8")
        print("GOEMON_NATIVE_CONTINUOUS_MIPS_SOURCE COMPLETE: owner-PC only")
    except (ValueError,OSError,TypeError,KeyError) as ex:
        print("GOEMON_NATIVE_CONTINUOUS_MIPS_SOURCE FAILED:",ex,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
