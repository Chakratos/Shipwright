#!/usr/bin/env python3
"""Rank authentic time-sensitive Skeleton descriptors by renderable ROM geometry.

Input: owner-private original rig packages (GOSKEL01) and the successful
371-candidate original MIPS source sweep report. No ROM data is uploaded.

A score reflects only observed time-dependent MtxF outputs and
the number of original source graphics roots already decoded. It does
NOT identify action IDs, animation clip length or the live player rig.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_original_rig_animation_pair import parse_rig_descriptors
from source_aligned_character_assets import CHARACTER_NAMES


def rank_visible_original_descriptors(
    rig:bytes,records:list[dict],*,character:str
)->list[dict]:
    slot,meshes,descriptors=parse_rig_descriptors(rig)
    if CHARACTER_NAMES[slot]!=character:
        raise ValueError("private original source rig/character mismatch")
    ranked=[]
    for candidate in records:
        if not candidate.get("valid") or not candidate.get("changed_at_1"):
            continue
        header=0x07000000|int(candidate["source_header"],16)
        if header not in descriptors:
            raise ValueError("original time-dependent source header missing from rig")
        _,bones=descriptors[header]
        gfx=[raw&0x8FFFFFFF for raw,_,_ in bones]
        mapped=[g for g in gfx if g in meshes]
        changed_limb=int(candidate["selected_limb"],16)
        mapped_gfx=len(set(mapped))
        ranked.append({
            "character":character,
            "source_header":f"0x{header:08X}",
            "source_limb_count":len(bones),
            "source_drawable_bone_count":len(mapped),
            "source_distinct_original_meshes":mapped_gfx,
            "source_gfx_unresolved":sum(bool(g) and g>>24==9 and g not in meshes for g in gfx),
            "selected_time_sensitive_bone":f"0x{changed_limb:08X}",
            "contains_original_gfx_data":mapped_gfx>0,
            "original_action_identity_verified":False,
        })
    ranked.sort(key=lambda x:(
        x["source_distinct_original_meshes"],
        x["source_drawable_bone_count"],
        x["source_limb_count"]
    ),reverse=True)
    return ranked


def select_visible_original_mips_candidates(sweep:dict,rigs_dir:Path)->dict:
    if sweep.get("schema")!="goemon-original-source-MIPS-descriptor-progress-sweep-v1":
        raise ValueError("missing verified original 371-descriptor MIPS scan")
    summaries=[]
    for name in CHARACTER_NAMES:
        source=(rigs_dir/name/"original.goskel").read_bytes()
        records=sweep["source_descriptor_diagnostics"][name]
        candidates=rank_visible_original_descriptors(
            source,records,character=name)
        best=candidates[0] if candidates else None
        report={
            "character":name,
            "source_time_sensitive_descriptors_at_progress_1":len(candidates),
            "renderable_original_skeleton_candidates":sum(
                x["contains_original_gfx_data"] for x in candidates),
            "highest_source_geometry_coverage":best,
            "top_source_render_candidates":candidates[:8],
            "selected_active_game_player_animation":False,
        }
        summaries.append(report)
        print("GOEMON_ORIGINAL_MOTION_GEOMETRY_RANK "+json.dumps(
            report,separators=(",",":")))
    return {
        "schema":"goemon-original-source-mips-renderable-motion-coverage-v1",
        "verified_gameplay_action_timing":False,
        "rom_data_uploaded":False,
        "characters":summaries,
    }


def main(argv=None)->int:
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--sweep",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-MIPS-descriptor-time-sweep.json"))
    a.add_argument("--rigs",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-rom-rigs"))
    a.add_argument("--output",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-MIPS-visible-motion-candidates.json"))
    args=a.parse_args(argv)
    try:
        project=Path(__file__).resolve().parents[3]
        out=args.output.resolve()
        if out==project or project in out.parents:
            raise ValueError("private original source analysis cannot be saved to Git")
        sweep=json.loads(args.sweep.read_text("utf-8"))
        report=select_visible_original_mips_candidates(sweep,args.rigs)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print("GOEMON_ORIGINAL_MOTION_GEOMETRY_RANK COMPLETE: original asset metadata only")
    except (ValueError,KeyError,TypeError,OSError) as ex:
        print("GOEMON_ORIGINAL_MOTION_GEOMETRY_RANK FAILED:",ex,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
