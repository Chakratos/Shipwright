#!/usr/bin/env python3
"""GOSKEL01: deterministic local package of authentic NG5E N64 limb geometry
and original encoded Skeleton S/R/T channel words. Their true physical
meaning requires the original MIPS animation decoder before playback.

Data comes ONLY from the user's hash-verified original ROM, decoded actual
F3DEX Skeleton display-list roots, and the ROM-derived Skeleton hierarchy.
Frames, action timing, decoded affine S/R/T and interpolation are NOT invented:
the package preserves raw authored poses without assigning gameplay actions.

On-disk little-endian metadata; 16-byte original N64 Vtx records remain
big-endian (as in the ROM). No copyrighted source data goes into Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from real_rom_check import ORIGINAL_SHA256, DECOMPRESSED_SHA256, locate_rom
from character_assets import read_file_table
from decompress_rom import decompress_us_rom
from decode_original_limb_meshes import decode_all_character_skeletal_meshes
from source_aligned_character_assets import source_align_character_files
from original_segmented_geometry import N64_VERTEX_STRUCT
from analyze_yae_resource_pointers import build_yae_source_animation_catalog
from probe_yae_shared_graphics import (
    compare_yae_banks,collect_yae_source_gfx_roots
)
from decode_original_limb_meshes import decode_original_limb_mesh

MAGIC=b"GOSKEL01"
HEADER=struct.Struct("<8sIII") # magic, original character slot, mesh count, authored pose count
MESH_HEADER=struct.Struct("<II") # source segmented root gfx pointer, triangle count
POSE_HEADER=struct.Struct("<III") # original 0x07 header pointer, original flags, limb count
LIMB=struct.Struct("<Ih9h") # source Gfx, parent index, scale/rotation/translation (signed 16)
MAX_MESHES=2048
MAX_POSES=1024
MAX_TRIANGLES_PER_MESH=30000
MAX_BONES_PER_POSE=128

def valid_raw_original_limb_gfx(ptr:int)->bool:
    # The source N64 player renderer masks 0x29 -> 0x09 for geometry.
    # Some Yae nodes contain 0x0F, whose owner/semantics remain unknown.
    # GOSKEL01 preserves those exact raw words, but does not render them.
    return ptr==0 or (ptr>>24) in (0x09,0x29,0x0F)


def create_original_rig_package(character:int, doc:dict,
                                source_meshes:dict) -> bytes:
    if not 0<=character<4:
        raise ValueError("source character index invalid")
    if doc.get("format")!="ng5e-original-rom-skeletal-poses-v1":
        raise ValueError("requires ROM-authored original skeleton poses")
    originals=doc["original_source_poses"]
    if not 1<=len(originals)<=MAX_POSES or not 1<=len(source_meshes)<=MAX_MESHES:
        raise ValueError("original source rig package outside count limits")
    target=bytearray(HEADER.pack(MAGIC,character,len(source_meshes),len(originals)))

    for ptr,mesh in sorted(source_meshes.items(),key=lambda pair:int(pair[0],16)):
        gfx=int(ptr,16)
        if gfx>>24!=9 or not 1<=len(mesh.faces)<=MAX_TRIANGLES_PER_MESH:
            raise ValueError("source limb mesh has incorrect segment/triangle count")
        if len(mesh.vertices)!=3*len(mesh.faces):
            raise ValueError("source limb source vertices must be triangle independent")
        target.extend(MESH_HEADER.pack(gfx,len(mesh.faces)))
        for v in mesh.vertices:
            target.extend(N64_VERTEX_STRUCT.pack(
                v.x,v.y,v.z,v.flags,v.s,v.t,v.c0,v.c1,v.c2,v.alpha
            ))

    for pose in originals:
        if pose.get("source_header_segment")!="0x07":
            raise ValueError("unverified source rig overlay")
        header=int(pose["source_header_offset"])
        flags=int(pose["original_animated_skeleton_flags"],16)
        limbs=pose["limbs"]
        if not 1<=len(limbs)<=MAX_BONES_PER_POSE:
            raise ValueError("original skeleton limb count invalid")
        if not 0<=header<=0xFFFFFF:
            raise ValueError("source skeleton header outside segment")
        target.extend(POSE_HEADER.pack(0x07000000|header,flags,len(limbs)))
        index_by_ptr={int(bone["ptr"]):i for i,bone in enumerate(limbs)}
        if len(index_by_ptr)!=len(limbs):
            raise ValueError("duplicate source original limb pointer")
        for i,bone in enumerate(limbs):
            parent_ptr=bone["parent"]
            parent=-1 if parent_ptr is None else index_by_ptr.get(int(parent_ptr))
            if parent is None or parent>=i:
                raise ValueError("original rig hierarchy not parent-first")
            xyz=tuple(bone["scale"])+tuple(bone["rotation"])+tuple(bone["translation"])
            if len(xyz)!=9 or any(not isinstance(x,int) or not -32768<=x<=32767
                                  for x in xyz):
                raise ValueError("invalid original signed 16-bit S/R/T")
            raw_gfx=int(bone["gfx"])
            if not valid_raw_original_limb_gfx(raw_gfx):
                raise ValueError("unsupported original raw limb graphics pointer")
            target.extend(LIMB.pack(raw_gfx,parent,*xyz))
    return bytes(target)


def inspect_original_rig_package(data:bytes)->dict:
    if len(data)<HEADER.size:
        raise ValueError("source original rig truncated")
    magic,slot,meshes,poses=HEADER.unpack_from(data)
    if magic!=MAGIC or slot>3 or not 1<=meshes<=MAX_MESHES or not 1<=poses<=MAX_POSES:
        raise ValueError("bad original ROM rig header")
    at=HEADER.size
    triangle_total=0
    mesh_roots=[]
    for _ in range(meshes):
        if at+MESH_HEADER.size>len(data):
            raise ValueError("source original mesh header truncated")
        ptr,count=MESH_HEADER.unpack_from(data,at)
        at+=MESH_HEADER.size
        if ptr>>24!=9 or not 1<=count<=MAX_TRIANGLES_PER_MESH:
            raise ValueError("invalid source limb mesh pointer/count")
        size=count*3*N64_VERTEX_STRUCT.size
        if at+size>len(data):
            raise ValueError("truncated source limb vertices")
        at+=size
        triangle_total+=count
        mesh_roots.append(ptr)
    original_poses=[]
    for _ in range(poses):
        if at+POSE_HEADER.size>len(data):
            raise ValueError("truncated original pose header")
        header,flags,n=POSE_HEADER.unpack_from(data,at)
        at+=POSE_HEADER.size
        if header>>24!=7 or not 1<=n<=MAX_BONES_PER_POSE:
            raise ValueError("invalid original pose header/limb count")
        roots=[]
        for index in range(n):
            if at+LIMB.size>len(data):
                raise ValueError("truncated original skeletal transform")
            gfx,parent,*src=LIMB.unpack_from(data,at)
            at+=LIMB.size
            if not -1<=parent<index or not valid_raw_original_limb_gfx(gfx):
                raise ValueError("invalid original skeletal limb pointer/link")
            roots.append((gfx,parent,tuple(src)))
        original_poses.append((header,flags,roots))
    if at!=len(data) or len(set(mesh_roots))!=len(mesh_roots):
        raise ValueError("source original rig file has trailing/duplicate data")
    return {
        "character_id":slot,
        "rig_pose_count":poses,
        "decoded_original_mesh_roots":meshes,
        "source_triangle_count":triangle_total,
        "physical_bone_transform_decoder_verified":False,
        "first_original_pose_header":f"0x{original_poses[0][0]:08X}",
        "first_original_pose_limb_count":len(original_poses[0][2]),
        "first_original_limb_raw_transform":original_poses[0][2][0][2],
        "original_action_timing_extracted":False,
    }


def select_original_player_rig_descriptors(source_doc:dict)->tuple[dict,int]:
    """Keep only 0x07 player-resource descriptors; never reinterpret 0x09.

    Offline scans include valid Skeleton-shaped nodes inside the graphics
    bank (0x09). Those are useful diagnostic candidates but cannot be
    serialized as a 0x07 player rig. This is a source-bank filter, NOT
    verification of animation clip ownership or physical transforms.
    """
    if source_doc.get("format")!="ng5e-original-rom-skeletal-poses-v1":
        raise ValueError("requires ROM-authored original skeleton poses")
    all_records=source_doc["original_source_poses"]
    selected=[p for p in all_records
              if p.get("source_header_segment")=="0x07"]
    if not selected:
        raise ValueError("no source 0x07 player-resource rig descriptors")
    return {**source_doc,"original_source_poses":selected},len(all_records)-len(selected)


def package_original_rigs(rom:bytes,poses_dir:Path,output_dir:Path)->dict:
    if hashlib.sha256(rom).hexdigest()!=ORIGINAL_SHA256:
        raise ValueError("ROM SHA-256 not original")
    decoded=decompress_us_rom(rom)
    if hashlib.sha256(decoded).hexdigest()!=DECOMPRESSED_SHA256:
        raise ValueError("decompressed original ROM mismatch")
    groups=source_align_character_files(decoded)
    table=read_file_table(decoded)
    project=Path(__file__).resolve().parents[3]
    target=output_dir.resolve()
    if target==project or project in target.parents:
        raise ValueError("original rig package cannot be stored in Git source")
    target.mkdir(parents=True,exist_ok=True)
    names=("Goemon","Ebisumaru","Sasuke")
    results=[]
    for slot,name in enumerate(names):
        banks={}
        for f in groups[slot][2:4]:
            entry=table[f.runtime_file_id]
            banks[f.source_segment]=decoded[entry.start:entry.end]
        pose_doc=json.loads(
            (poses_dir/(name+"_original_source_poses.json")).read_text("utf-8"))
        player_doc,unverified_overlay_count=select_original_player_rig_descriptors(pose_doc)
        mesh_report=decode_all_character_skeletal_meshes(player_doc,banks)
        if not mesh_report["source_meshes"]:
            raise ValueError(f"no original source limb mesh decoded for {name}")
        blob=create_original_rig_package(slot,player_doc,mesh_report["source_meshes"])
        check=inspect_original_rig_package(blob)
        directory=target/name
        directory.mkdir(exist_ok=True)
        (directory/"original.goskel").write_bytes(blob)
        results.append({
            "character":name,
            **check,
            "source_rig_file":f"{name}/original.goskel",
            "original_gfx_roots_unresolved":len(mesh_report["decode_failures"]),
            "original_animation_action_mapping_complete":False,
            "skipped_nonplayer_segment_descriptors":unverified_overlay_count,
        })
        print("GOEMON_SOURCE_RIG_PACKAGE "+json.dumps(results[-1],separators=(",",":")))
    # Yae's source 0x07 has 118 Skeleton-shaped animation records.
    # 0x29 graphics pointers refer to 0x09 after the native N64 mask.
    # The unique candidate source bank (runtime file 299 in the verified
    # NG5E ROM) was proven by executing 40/40 original display lists.
    # Runtime overlay residency and active player ownership remain unknown.
    ygroup=groups[3]
    y07f=table[ygroup[2].runtime_file_id]
    y08f=table[ygroup[3].runtime_file_id]
    yae07=decoded[y07f.start:y07f.end]
    yae08=decoded[y08f.start:y08f.end]
    alternatives=[]
    for source in groups[:3]:
        entry=source[3]
        if entry.source_segment!=9:
            raise ValueError("invalid original source graphics segment")
        f=table[entry.runtime_file_id]
        alternatives.append((entry.runtime_file_id,decoded[f.start:f.end]))
    compare=compare_yae_banks(alternatives,yae07,yae08)
    selected=compare["unique_geometric_best_candidate_file"]
    if selected is None:
        raise ValueError("no unique geometrically valid Yae graphics bank")
    matching=next(x for x in compare["candidate_09_banks"]
                  if x["source_09_runtime_file_id"]==selected)
    if (matching["failed_limb_meshes"]!=0 or
        matching["executed_original_limb_meshes"]!=
        matching["distinct_original_limb_display_lists"]):
        raise ValueError("Yae original source skeleton references unresolved geometry")
    ybank9=next(data for fid,data in alternatives if fid==selected)
    _, roots, _, unresolved=collect_yae_source_gfx_roots(yae07)
    meshy={}
    for ptr in sorted(roots):
        meshy[f"0x{ptr:08X}"]=decode_original_limb_mesh(
            ptr,{7:yae07,8:yae08,9:ybank9})
    ydoc=build_yae_source_animation_catalog(yae07)
    yblob=create_original_rig_package(3,ydoc,meshy)
    yinfo=inspect_original_rig_package(yblob)
    ydest=target/"Yae"
    ydest.mkdir(exist_ok=True)
    (ydest/"original.goskel").write_bytes(yblob)
    results.append({
        "character":"Yae",
        **yinfo,
        "source_rig_file":"Yae/original.goskel",
        "original_gfx_roots_unresolved":sum(unresolved.values()),
        "original_animation_action_mapping_complete":False,
        "source_09_geometric_best_runtime_file":selected,
        "original_source_09_runtime_residency_verified":False,
        "active_player_rig_verified":False,
        "source_encoded_nonmesh_gfx_tags_preserved":True,
    })
    print("GOEMON_SOURCE_RIG_PACKAGE "+json.dumps(results[-1],separators=(",",":")))

    summary={
        "schema":"goemon-original-n64-rig-package-v1",
        "characters":results,
        "source":"hash-verified NG5E ROM and source N64 Skeleton/Gfx",
        "user_capture_required":False,
        "original_animation_playback_timing_verified":False,
        "source_mesh_uploaded":False,
    }
    (target/"manifest.json").write_text(
        json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    return summary


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rom",type=Path)
    p.add_argument("--poses-dir",type=Path,
                   default=Path(r"C:\actions-runner-goemon\original-rom-poses"))
    p.add_argument("--output-dir",type=Path,
                   default=Path(r"C:\actions-runner-goemon\original-rom-rigs"))
    args=p.parse_args(argv)
    try:
        package_original_rigs((args.rom or locate_rom()).read_bytes(),
                              args.poses_dir,args.output_dir)
        print("GOEMON_SOURCE_RIG_PACKAGE COMPLETE: original ROM only; no upload")
    except (ValueError,OSError,KeyError,TypeError,struct.error) as e:
        print("GOEMON_SOURCE_RIG_PACKAGE FAILED:",e,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
