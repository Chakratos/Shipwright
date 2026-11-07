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
from decode_original_limb_meshes import decode_all_character_skeletal_meshes
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
