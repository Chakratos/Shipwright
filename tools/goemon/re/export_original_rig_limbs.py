#!/usr/bin/env python3
"""Offline original ROM: decode every source Skeleton-owned limb to source meshes.

Runs on the user's private verified NG5E ROM; writes its original meshes
ONLY into C:/actions-runner-goemon/original-rig-limbs, never to GitHub.
Pure structural scan; does NOT invent game animation frames/action IDs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from real_rom_check import ORIGINAL_SHA256,DECOMPRESSED_SHA256,locate_rom
from character_assets import read_file_table
from decompress_rom import decompress_us_rom
from source_aligned_character_assets import source_align_character_files
from decode_original_limb_meshes import (
    decode_all_character_skeletal_meshes,decode_original_limb_mesh
)
from probe_yae_shared_graphics import (
    compare_yae_banks,collect_yae_source_gfx_roots
)
from original_f3dex_geometry import mesh_to_obj

CHARACTERS=("Goemon","Ebisumaru","Sasuke")


def export_original_limb_geometry(rom:bytes,poses_dir:Path,
                                  output_dir:Path) ->dict:
    if hashlib.sha256(rom).hexdigest()!=ORIGINAL_SHA256:
        raise ValueError("source ROM not recognized")
    decoded=decompress_us_rom(rom)
    if hashlib.sha256(decoded).hexdigest()!=DECOMPRESSED_SHA256:
        raise ValueError("source decompressed ROM mismatch")
    table=read_file_table(decoded)
    groups=source_align_character_files(decoded)
    target=output_dir.resolve()
    project=Path(__file__).resolve().parents[3]
    if target==project or project in target.parents:
        raise ValueError("cannot put original assets inside Git repo")
    target.mkdir(parents=True,exist_ok=True)
    summaries=[]
    for slot,name in enumerate(CHARACTERS):
        banks={}
        for source in groups[slot][2:4]:
            f=table[source.runtime_file_id]
            banks[source.source_segment]=decoded[f.start:f.end]
        pose=json.loads((poses_dir/(name+"_original_source_poses.json"))
                        .read_text("utf-8"))
        report=decode_all_character_skeletal_meshes(pose,banks)
        path=target/name
        path.mkdir(exist_ok=True)
        manifest={
            key:value for key,value in report.items() if key!="source_meshes"
        }
        mesh_files=[]
        for gfx,mesh in sorted(report["source_meshes"].items()):
            filename=f"limb_0x{gfx[2:].lower()}.obj"
            (path/filename).write_text(
                mesh_to_obj(mesh,name=f"{name}_{gfx}"),encoding="utf-8")
            mesh_files.append({
                "gfx":gfx,
                "triangles":len(mesh.faces),
                "vertex_instances":len(mesh.vertices),
                "source_file":filename,
                "source_display_list":f"0x{mesh.source_display_list_offset:08X}",
            })
        manifest["source_limb_meshes"]=mesh_files
        (path/"manifest.json").write_text(
            json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
        summaries.append({
            "character":name,
            "original_limb_gfx_roots":report["source_original_limb_gfx_count"],
            "valid_source_limb_meshes":report["fully_decoded_limb_meshes"],
            "source_triangles":report["decoded_source_triangles"],
            "failures":len(report["decode_failures"]),
            "failure_reasons":report["failure_reasons"],
        })
    # Yae's contiguous graphics group has no 0x09 bank. Her source 0x07
    # contains 118 traversable Skeleton-shaped descriptors, including raw
    # 0x29xxxxxx graphics pointers; the player renderer masks these to
    # 0x09xxxxxx. Evaluate all three known source-verified 0x09 banks.
    y_group=groups[3]
    source07=table[y_group[2].runtime_file_id]
    source08=table[y_group[3].runtime_file_id]
    yae07=decoded[source07.start:source07.end]
    yae08=decoded[source08.start:source08.end]
    hypotheses=[]
    for group in groups[:3]:
        entry=group[3]
        if entry.source_segment!=9:
            raise ValueError("original source graphics bank does not use segment 0x09")
        f=table[entry.runtime_file_id]
        hypotheses.append((entry.runtime_file_id,decoded[f.start:f.end]))
    comparison=compare_yae_banks(hypotheses,yae07,yae08)
    selected=comparison["unique_geometric_best_candidate_file"]
    if selected is None:
        raise ValueError("ambiguous Yae source 0x09 graphics bank; cannot export authentic limb meshes")
    best=next(item for item in comparison["candidate_09_banks"]
              if item["source_09_runtime_file_id"]==selected)
    # A partial candidate bank does not qualify as Yae geometry. Require
    # an exact F3DEX match for every distinct normalized Skeleton Gfx root.
    if (best["source_07_candidate_skeletons"]<1 or
        best["distinct_original_limb_display_lists"]<1 or
        best["executed_original_limb_meshes"]!=
        best["distinct_original_limb_display_lists"] or
        best["failed_limb_meshes"]):
        raise ValueError("Yae graphics candidate has unresolved Skeleton display lists")
    _, roots, _, unsupported=collect_yae_source_gfx_roots(yae07)
    source9=next(data for idx,data in hypotheses if idx==selected)
    bank_map={7:yae07,8:yae08,9:source9}
    ypath=target/"Yae"
    ypath.mkdir(exist_ok=True)
    mesh_files=[]
    face_count=0
    for gfx in sorted(roots):
        mesh=decode_original_limb_mesh(gfx,bank_map)
        fname=f"limb_0x{gfx:08x}.obj"
        (ypath/fname).write_text(
            mesh_to_obj(mesh,name=f"Yae_0x{gfx:08X}"),encoding="utf-8")
        count=len(mesh.faces)
        face_count+=count
        mesh_files.append({
            "gfx":f"0x{gfx:08X}",
            "triangles":count,
            "vertex_instances":len(mesh.vertices),
            "source_file":fname,
            "source_display_list":f"0x{mesh.source_display_list_offset:08X}",
        })
    yae_manifest={
        "character":"Yae",
        "source_limb_meshes":mesh_files,
        "original_source_07_file":y_group[2].runtime_file_id,
        "geometrically_confirmed_source_09_file":selected,
        "distinct_skeleton_display_list_roots":len(roots),
        "source_triangle_count":face_count,
        "unresolved_nonmesh_gfx_pointer_classes":dict(sorted(unsupported.items())),
        "graphics_bank_runtime_residency_verified":False,
        "active_animated_player_skeleton_verified":False,
        "original_animation_frames_decoded":0,
        "source_gfx_derived_from_rom":True,
    }
    (ypath/"manifest.json").write_text(
        json.dumps(yae_manifest,indent=2)+"\n",encoding="utf-8")
    summaries.append({
        "character":"Yae",
        "original_limb_gfx_roots":len(roots),
        "valid_source_limb_meshes":len(mesh_files),
        "source_triangles":face_count,
        "failures":0,
        "geometric_source_bank":selected,
        "runtime_bank_ownership_verified":False,
    })

    result={
        "format":"ng5e-original-rom-rigid-limb-geometry-v1",
        "characters":summaries,
        "static_rig_poses_extracted":True,
        "animation_timeline_extracted":False,
        "assets_uploaded":False,
    }
    (target/"original_limb_summary.json").write_text(
        json.dumps(result,indent=2)+"\n",encoding="utf-8")
    return result


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--poses-dir",type=Path,
                   default=Path(r"C:\actions-runner-goemon\original-rom-poses"))
    p.add_argument("--output-dir",type=Path,
                   default=Path(r"C:\actions-runner-goemon\original-rig-limbs"))
    a=p.parse_args(argv)
    try:
        r=export_original_limb_geometry(
            (a.rom or locate_rom()).read_bytes(),a.poses_dir,a.output_dir)
        for item in r["characters"]:
            print("GOEMON_ORIGINAL_LIMB_MESH "+json.dumps(
                item,separators=(",",":")))
        print("GOEMON_ORIGINAL_LIMB_MESH COMPLETE: source ROM only; no upload")
    except (ValueError,OSError,TypeError,KeyError) as e:
        print("GOEMON_ORIGINAL_LIMB_MESH FAILED:",e,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
