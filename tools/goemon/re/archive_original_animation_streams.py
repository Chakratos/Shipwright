#!/usr/bin/env python3
"""Extract candidate MNSG animation streams + encoded per-limb channels OFFLINE.

The original Nintendo 64 player renderer reads:
 AnimatedSkeleton.animation [segment 0x07] + animation_progress
 and Skeleton.scale/rotation/translation 16-bit descriptors evaluated by
 original MIPS func_800192D0_19ED0.

A repeated 0xB000/0xB100 signature in these raw words means they must
NOT be treated as literal Euler rotations / scales. This lossless
GOANIM01 archive retains all source bytes and skeleton channel selectors
without inventing action IDs, timing, curves or MIPS decoder semantics.

No ROM bytes are committed or uploaded; these files remain on the
user-owned Windows runner outside the Git checkout.
"""
from __future__ import annotations
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from real_rom_check import ORIGINAL_SHA256,DECOMPRESSED_SHA256,locate_rom
from character_assets import read_file_table
from decompress_rom import decompress_us_rom
from source_aligned_character_assets import source_align_character_files
from analyze_yae_resource_pointers import build_yae_source_animation_catalog
from analyze_original_animation_channels import (
    analyze_raw_original_animation_descriptors,
    summarize_channel_anomalies,
)

MAGIC=b"GOANIM01"
HEADER=struct.Struct("<8sII") # magic, character slot, candidate descriptor count
CLIP=struct.Struct("<IIIIII") # header ptr, flags, stream ptr, root ptr, bytes, limbs
LIMB=struct.Struct("<IIh9h") # original limb ptr, gfx ptr, parent index, encoded channel words
MAX_CLIPS=512
MAX_LIMBS=128
MAX_STREAM=1024*1024
CHARACTERS=("Goemon","Ebisumaru","Sasuke","Yae")


def extract_original_candidate_animation(
    pose:dict, bank07:bytes
)->tuple[bytes,list[tuple[int,int,int,tuple[int,...]]]]:
    if pose["source_header_segment"]!="0x07":
        raise ValueError("unverified original source segment for animation descriptor")
    origin=int(pose["original_animation_pointer"],16)
    root=int(pose["original_skeleton_root"],16)
    if origin>>24!=7 or root>>24!=7:
        raise ValueError("original animation requires 0x07 segmented pointer")
    limbs=pose["limbs"]
    if not 1<=len(limbs)<=MAX_LIMBS:
        raise ValueError("original Skeleton limb count outside source bounds")
    start=origin&0xFFFFFF
    bottom=min(n["ptr"]&0xFFFFFF for n in limbs)
    if not 0<=start<=bottom<=len(bank07) or bottom-start>MAX_STREAM:
        raise ValueError("source raw animation stream location invalid")
    lookup={int(n["ptr"]):i for i,n in enumerate(limbs)}
    if len(lookup)!=len(limbs):
        raise ValueError("duplicate original skeleton node pointer")
    records=[]
    for index,limb in enumerate(limbs):
        p=limb["parent"]
        parent=-1 if p is None else lookup.get(int(p))
        if parent is None or parent>=index:
            raise ValueError("original skeleton parent graph invalid")
        channels=tuple(limb["scale"])+tuple(limb["rotation"])+tuple(limb["translation"])
        if len(channels)!=9 or any(not -32768<=v<=32767 for v in channels):
            raise ValueError("invalid original encoded animation channels")
        records.append((limb["ptr"],limb["gfx"],parent,channels))
    return bank07[start:bottom], records


def create_original_animation_archive(
    slot:int, source_doc:dict, bank07:bytes
)->bytes:
    if not 0<=slot<4 or source_doc.get("format")!=(
        "ng5e-original-rom-skeletal-poses-v1"):
        raise ValueError("wrong original ROM animation source format")
    clips=[
        pose for pose in source_doc["original_source_poses"]
        if pose["source_header_segment"]=="0x07"
    ]
    if not 1<=len(clips)<=MAX_CLIPS:
        raise ValueError("original animation descriptor count outside limit")
    out=bytearray(HEADER.pack(MAGIC,slot,len(clips)))
    for pose in clips:
        stream,limbs=extract_original_candidate_animation(pose,bank07)
        ptr=0x07000000|int(pose["source_header_offset"])
        flags=int(pose["original_animated_skeleton_flags"],16)
        animation=int(pose["original_animation_pointer"],16)
        root=int(pose["original_skeleton_root"],16)
        out.extend(CLIP.pack(ptr,flags,animation,root,len(stream),len(limbs)))
        out.extend(stream)
        for record_ptr,gfx,parent,channels in limbs:
            out.extend(LIMB.pack(record_ptr,gfx,parent,*channels))
    return bytes(out)


def inspect_original_animation_archive(blob:bytes)->dict:
    if len(blob)<HEADER.size:
        raise ValueError("original animation source archive truncated")
    magic,slot,count=HEADER.unpack_from(blob)
    if magic!=MAGIC or slot>3 or not 1<=count<=MAX_CLIPS:
        raise ValueError("wrong original animation source archive header")
    pos=HEADER.size
    records=[]
    raw_total=0
    channel_marker=Counter()
    for _ in range(count):
        if pos+CLIP.size>len(blob):
            raise ValueError("truncated original source animation clip")
        header,flags,origin,root,length,n=CLIP.unpack_from(blob,pos)
        pos+=CLIP.size
        if (header>>24,origin>>24,root>>24)!=(7,7,7):
            raise ValueError("source animation pointer outside original 0x07")
        if not 0<=length<=MAX_STREAM or not 1<=n<=MAX_LIMBS:
            raise ValueError("unbounded original animation source payload/limbs")
        if pos+length+n*LIMB.size>len(blob):
            raise ValueError("source compressed animation records truncated")
        pos+=length
        raw_total+=length
        for _ in range(n):
            limb,gfx,parent,*values=LIMB.unpack_from(blob,pos)
            pos+=LIMB.size
            if limb>>24!=7 or parent<-1 or parent>=_:
                raise ValueError("original animation hierarchy corrupted")
            for val in values:
                if val&0xFF00 in (0xB000,0xB100):
                    channel_marker[f"0x{val&0xFF00:04X}"]+=1
        records.append({
            "source_animation_header":f"0x{header:08X}",
            "original_animation_pointer":f"0x{origin:08X}",
            "raw_payload_bytes":length,
            "skeleton_limb_records":n,
        })
    if pos!=len(blob):
        raise ValueError("source animation archive has trailing bytes")
    return {
        "character_slot":slot,
        "source_animation_descriptor_count":count,
        "raw_compressed_animation_bytes":raw_total,
        "encoded_channel_markers":dict(channel_marker),
        "first_3_descriptors":records[:3],
        "original_decoder_fully_ported":False,
        "real_action_timing_known":False,
    }


def export_original_animation_streams(rom:bytes,
                                      poses_dir:Path,output_dir:Path)->dict:
    if hashlib.sha256(rom).hexdigest()!=ORIGINAL_SHA256:
        raise ValueError("not recognized original private NG5E ROM")
    decompressed=decompress_us_rom(rom)
    if hashlib.sha256(decompressed).hexdigest()!=DECOMPRESSED_SHA256:
        raise ValueError("original decompressed ROM failed hash check")
    table=read_file_table(decompressed)
    groups=source_align_character_files(decompressed)
    project=Path(__file__).resolve().parents[3]
    out=output_dir.resolve()
    if out==project or project in out.parents:
        raise ValueError("raw original ROM-derived assets must stay outside Git")
    out.mkdir(parents=True,exist_ok=True)
    manifests=[]
    for slot,name in enumerate(CHARACTERS):
        file=table[groups[slot][2].runtime_file_id]
        bank=decompressed[file.start:file.end]
        if slot==3:
            doc=build_yae_source_animation_catalog(bank)
        else:
            doc=json.loads((poses_dir/(name+"_original_source_poses.json"))
                           .read_text("utf-8"))
        bytestring=create_original_animation_archive(slot,doc,bank)
        info=inspect_original_animation_archive(bytestring)
        dest=out/name
        dest.mkdir(exist_ok=True)
        (dest/"original.goanim").write_bytes(bytestring)
        profile=analyze_raw_original_animation_descriptors(doc,bank)
        (dest/"channel_metadata.json").write_text(
            json.dumps(profile,indent=2)+"\n",encoding="utf-8")
        manifests.append({
            "character":name,
            "compressed_animation_file":f"{name}/original.goanim",
            **info,
            "source_channel_analysis":summarize_channel_anomalies(profile),
            "source_yae_gfx_bank_runtime_verified":False if slot==3 else None,
        })
        print("GOEMON_ORIGINAL_ANIMATION_STREAM "+json.dumps({
            k:v for k,v in manifests[-1].items()
            if k!="first_3_descriptors"
        },separators=(",",":")))
    summary={
        "source":"hash-verified original ROM, not recorded gameplay",
        "characters":manifests,
        "original_animation_decoder_complete":False,
        "source_asset_upload":False,
    }
    (out/"manifest.json").write_text(
        json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    return summary


def main(argv=None)->int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom",type=Path)
    parser.add_argument("--poses-dir",type=Path,
                        default=Path(r"C:\actions-runner-goemon\original-rom-poses"))
    parser.add_argument("--output-dir",type=Path,
                        default=Path(r"C:\actions-runner-goemon\original-animation-streams"))
    args=parser.parse_args(argv)
    try:
        export_original_animation_streams(
            (args.rom or locate_rom()).read_bytes(),
            args.poses_dir,args.output_dir)
        print("GOEMON_ORIGINAL_ANIMATION_STREAM COMPLETE: ROM-only, no upload")
    except (OSError,ValueError,KeyError,TypeError,struct.error) as e:
        print("GOEMON_ORIGINAL_ANIMATION_STREAM FAILED:",e,file=sys.stderr)
        return 2
    return 0

if __name__=="__main__":
    raise SystemExit(main())
