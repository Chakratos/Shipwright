#!/usr/bin/env python3
"""Verify original user-ROM rig and channel archives agree byte-for-byte.

Cross-check GOSKEL01 and GOANIM01 per-character source descriptors:
exact original 0x07 header, flags, bone order, parent, tagged graphics
pointers and all nine encoded 16-bit Skeleton channels. This guards the
future MIPS animation decoder against mispaired asset versions; it does
NOT prove active player ownership, timing or physical bone transforms.

Run only on the owner's locally generated source files. Do not upload ROM.
"""
from __future__ import annotations
from collections import Counter
import argparse
import json
from pathlib import Path
import struct
import sys

from archive_original_animation_streams import (
    MAGIC as AMAGIC, HEADER as AHEADER, CLIP, LIMB as ALIMB
)
from package_original_rig import (
    MAGIC as RMAGIC, HEADER as RHEADER, MESH_HEADER, POSE_HEADER,
    LIMB as RLIMB
)
from original_segmented_geometry import N64_VERTEX_STRUCT

CHARACTERS=("Goemon","Ebisumaru","Sasuke","Yae")

def parse_rig_descriptors(blob:bytes)->tuple[int,set[int],dict[int,tuple]]:
    if len(blob)<RHEADER.size:
        raise ValueError("truncated original source rig")
    magic,slot,nmeshes,nposes=RHEADER.unpack_from(blob)
    if magic!=RMAGIC or slot>3 or not 1<=nmeshes<=2048 or not 1<=nposes<=1024:
        raise ValueError("invalid original rig header")
    mesh_roots=set()
    pos=RHEADER.size
    for _ in range(nmeshes):
        if pos+MESH_HEADER.size>len(blob):
            raise ValueError("truncated source mesh header")
        ptr,tris=MESH_HEADER.unpack_from(blob,pos)
        pos+=MESH_HEADER.size
        if ptr>>24!=9 or not 1<=tris<=30000 or ptr in mesh_roots:
            raise ValueError("invalid or repeated source graphics mesh")
        mesh_roots.add(ptr)
        size=tris*3*N64_VERTEX_STRUCT.size
        if pos+size>len(blob):
            raise ValueError("truncated source graphics mesh")
        pos+=size
    descriptors={}
    for _ in range(nposes):
        if pos+POSE_HEADER.size>len(blob):
            raise ValueError("truncated original Skeleton descriptor")
        hdr,flags,n=POSE_HEADER.unpack_from(blob,pos)
        pos+=POSE_HEADER.size
        if hdr>>24!=7 or hdr in descriptors or not 1<=n<=128:
            raise ValueError("bad or duplicate original Skeleton header")
        bones=[]
        for idx in range(n):
            if pos+RLIMB.size>len(blob):
                raise ValueError("truncated original Skeleton bone")
            gfx,parent,*raw=RLIMB.unpack_from(blob,pos)
            if not -1<=parent<idx:
                raise ValueError("invalid source rig bone order")
            bones.append((gfx,parent,tuple(raw)))
            pos+=RLIMB.size
        descriptors[hdr]=(flags,bones)
    if pos!=len(blob):
        raise ValueError("trailing source rig bytes")
    return slot,mesh_roots,descriptors


def parse_animation_descriptors(blob:bytes)->tuple[int,dict[int,tuple]]:
    if len(blob)<AHEADER.size:
        raise ValueError("truncated source animation archive")
    magic,slot,n=AHEADER.unpack_from(blob)
    if magic!=AMAGIC or slot>3 or not 1<=n<=512:
        raise ValueError("invalid original animation archive header")
    pos=AHEADER.size
    descriptions={}
    for _ in range(n):
        if pos+CLIP.size>len(blob):
            raise ValueError("truncated source animation candidate")
        header,flags,stream,root,length,limbs=CLIP.unpack_from(blob,pos)
        pos+=CLIP.size
        if (header>>24,stream>>24,root>>24)!=(7,7,7) or (
            not 1<=limbs<=128 or length>1024*1024 or header in descriptions):
            raise ValueError("invalid source animation descriptor pointer/count")
        if pos+length+limbs*ALIMB.size>len(blob):
            raise ValueError("truncated source animation payload")
        pos+=length
        records=[]
        for idx in range(limbs):
            source_ptr,gfx,parent,*raw=ALIMB.unpack_from(blob,pos)
            pos+=ALIMB.size
            if source_ptr>>24!=7 or not -1<=parent<idx:
                raise ValueError("invalid source animation limb order")
            records.append((gfx,parent,tuple(raw)))
        descriptions[header]=(flags,records)
    if pos!=len(blob):
        raise ValueError("trailing original source animation bytes")
    return slot,descriptions


def compare_original_source_packages(rig:bytes,animation:bytes)->dict:
    slot,meshes,skeletons=parse_rig_descriptors(rig)
    anim_slot,channels=parse_animation_descriptors(animation)
    if slot!=anim_slot:
        raise ValueError("source rig and animation character mismatch")
    if skeletons.keys()!=channels.keys():
        raise ValueError("source rig/animation original header sets differ")
    missing=set()
    connected=set()
    unresolved=Counter()
    for hdr,(flags,bones) in skeletons.items():
        aflags,abones=channels[hdr]
        if flags!=aflags or bones!=abones:
            raise ValueError(
                f"original source rig and channel mismatch at header 0x{hdr:08X}")
        for gfx,_,_ in bones:
            if gfx==0:
                continue
            normalized=gfx&0x8FFFFFFF
            if normalized>>24!=9:
                unresolved[f"0x{gfx>>24:02X}"]+=1
            elif normalized not in meshes:
                missing.add(normalized)
            else:
                connected.add(normalized)
    if not connected:
        raise ValueError("no matching original ROM limb graphics in source rig")
    return {
        "character_slot":slot,
        "matched_exact_skeleton_descriptors":len(skeletons),
        "source_meshes":len(meshes),
        "distinct_matched_meshes":len(connected),
        "distinct_unresolved_geometric_meshes":len(missing),
        "unknown_tagged_source_graphics_records":dict(sorted(unresolved.items())),
        "animation_tick_or_action_ids_verified":False,
        "actual_source_matrix_codec_decoded":False,
        "byte_identical_raw_limb_channels":True,
    }


def verify_local_packages(rigs_dir:Path,anims_dir:Path)->dict:
    results=[]
    for slot,name in enumerate(CHARACTERS):
        rig=(rigs_dir/name/"original.goskel").read_bytes()
        anim=(anims_dir/name/"original.goanim").read_bytes()
        metrics=compare_original_source_packages(rig,anim)
        if metrics["character_slot"]!=slot:
            raise ValueError(f"{name} original asset slot mismatch")
        results.append({"character":name,**metrics})
    return {
        "format":"goemon-original-source-rig-animation-link-validation-v1",
        "characters":results,
        "real_character_animation_playback_ready":False,
        "original_assets_uploaded":False,
    }


def main(argv=None)->int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rigs",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-rom-rigs"))
    p.add_argument("--animations",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-animation-streams"))
    p.add_argument("--report",type=Path,default=Path(
        r"C:\actions-runner-goemon\original-rig-animation-link-report.json"))
    args=p.parse_args(argv)
    try:
        result=verify_local_packages(args.rigs,args.animations)
        root=Path(__file__).resolve().parents[3]
        target=args.report.resolve()
        if target==root or root in target.parents:
            raise ValueError("local owned-ROM report cannot be saved inside source repo")
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        for character in result["characters"]:
            print("GOEMON_ORIGINAL_SOURCE_PAIR "+json.dumps(
                character,separators=(",",":")))
        print("GOEMON_ORIGINAL_SOURCE_PAIR COMPLETE: four characters, no uploads")
    except (OSError,ValueError,TypeError,KeyError,struct.error) as exc:
        print("GOEMON_ORIGINAL_SOURCE_PAIR FAILED:",exc,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
