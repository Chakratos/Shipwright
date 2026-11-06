#!/usr/bin/env python3
"""Match original ROM skeletal limb display lists to source-correct mesh runs.

No real-game capture: loads *locally extracted* source-aligned original
skeleton poses and original 0x09 F3DEX geometry on user's own PC.

Exact F3DEX start-address matches are confirmed. Header-to-first-vertex
matches are only candidates because original N64 DisplayLists begin with
RDP/Matrix commands before the first gSPVertex.
"""
from __future__ import annotations
from collections import Counter
import argparse
import json
from pathlib import Path
import sys


def match_pose_gfx_to_n64_mesh_runs(source_poses: dict, mesh_manifest: dict,
                                   *, max_header_bytes: int = 128) -> dict:
    if source_poses.get("format") != "ng5e-original-rom-skeletal-poses-v1":
        raise ValueError("not a source-verified original rig pose catalog")
    if not 0 <= max_header_bytes <= 1024:
        raise ValueError("invalid N64 display-list header search")
    entries = mesh_manifest.get("per_display_list_objects", [])
    starts={}
    for part in entries:
        start=int(part["display_list_offset"])
        if start in starts:
            raise ValueError("duplicate source F3DEX mesh run")
        starts[start] = part["local_obj_file"]

    total = Counter()
    gfx_index: dict[int,dict] = {}
    for pose in source_poses["original_source_poses"]:
        for bone in pose["limbs"]:
            ptr=bone["gfx"]
            if ptr==0:
                total["null"]+=1
                continue
            if ptr>>24 != 9:
                total["unresolved_segment"]+=1
                continue
            total["total_09_gfx_refs"]+=1
            at=ptr&0xFFFFFF
            if at not in gfx_index:
                if at in starts:
                    gfx_index[at] = {
                        "source_gfx":"0x%08X"%ptr,
                        "relation":"exact_first_vertex_command",
                        "source_mesh":starts[at],
                        "verified":True,
                    }
                else:
                    candidates=[
                        (start-at,start,filename)
                        for start,filename in starts.items()
                        if start>at and start-at<=max_header_bytes
                    ]
                    if candidates:
                        delta,start,filename=min(candidates)
                        gfx_index[at]={
                            "source_gfx":"0x%08X"%ptr,
                            "relation":"possible_display_list_header",
                            "first_vertex_after_header":delta,
                            "source_mesh":filename,
                            "verified":False,
                        }
                    else:
                        gfx_index[at]={
                            "source_gfx":"0x%08X"%ptr,
                            "relation":"unresolved_source_graphics_pointer",
                            "verified":False
                        }
            total[gfx_index[at]["relation"]]+=1
    links=sorted(gfx_index.values(),key=lambda item:int(item["source_gfx"],16))
    return {
        "character":source_poses.get("character"),
        "source_poses":source_poses.get("structurally_valid_poses"),
        "source_mesh_runs":len(entries),
        "total_bone_references":sum(total.values())-sum(
            total[key] for key in (
                "total_09_gfx_refs",
                "exact_first_vertex_command",
                "possible_display_list_header",
                "unresolved_source_graphics_pointer"
            )
        ),
        "distinct_09_gfx_pointers":len(gfx_index),
        "matched_exact_refs":total["exact_first_vertex_command"],
        "matched_nearby_unverified":total["possible_display_list_header"],
        "unresolved_refs":total["unresolved_segment"]+
                          total["unresolved_source_graphics_pointer"],
        "null_refs":total["null"],
        "matches":links,
        "automated_limb_to_mesh_bone_animation_ready":False,
        "limitations":"Near-header matches are not confirmed without tracing full N64 Gfx command list"
    }


def summarize_all_local(poses_dir:Path,meshes_dir:Path) -> dict:
    results=[]
    for name in ("Goemon","Ebisumaru","Sasuke"):
        pose=poses_dir/(name+"_original_source_poses.json")
        mesh=meshes_dir/name/"manifest.json"
        doc=json.loads(pose.read_text("utf-8"))
        manifest=json.loads(mesh.read_text("utf-8"))
        result=match_pose_gfx_to_n64_mesh_runs(doc,manifest)
        if result["character"]!=name:
            raise ValueError("source pose/matrix character mismatch")
        results.append(result)
    return {"schema":"goemon-source-bone-graphics-binding-v1",
            "characters":results,"original_assets_uploaded":False}


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--poses-dir",type=Path,default=Path(r"C:\actions-runner-goemon\original-rom-poses"))
    p.add_argument("--meshes-dir",type=Path,default=Path(r"C:\actions-runner-goemon\original-rom-meshes-source-aligned"))
    p.add_argument("--output",type=Path)
    args=p.parse_args(argv)
    try:
        doc=summarize_all_local(args.poses_dir,args.meshes_dir)
        for item in doc["characters"]:
            print("GOEMON_SOURCE_BONE_LINK "+json.dumps({
                k:v for k,v in item.items() if k!="matches"
            },separators=(",",":")))
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")
        print("GOEMON_SOURCE_BONE_LINK COMPLETE: exact N64 pointer cross-reference, no game capture")
    except (ValueError,OSError,KeyError,TypeError) as err:
        print(f"GOEMON_SOURCE_BONE_LINK FAILED: {err}",file=sys.stderr)
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
